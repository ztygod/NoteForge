from importlib.metadata import version

from typer.testing import CliRunner

from noteforge.cli.app import app
from noteforge.collector import bilibili, inspection
from noteforge.collector.models import (
    SubtitleTrack,
    VideoCollectionResult,
    VideoMetadata,
)
from noteforge.exceptions import RiskControlError
from noteforge.core import NoteGenerationPipeline
from noteforge.subtitle.downloader import YtDlpSubtitleDownloader
from noteforge.subtitle.models import SubtitleFile


runner = CliRunner()


def test_help_lists_inspect_command() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "inspect" in result.stdout
    assert "generate" in result.stdout
    assert "configure" in result.stdout


def test_configure_writes_ollama_dotenv(tmp_path) -> None:
    env_path = tmp_path / ".env"

    result = runner.invoke(
        app,
        ["configure", "--path", str(env_path)],
        input="ollama\nqwen-test\nhttp://localhost:11434\n90\n",
    )

    assert result.exit_code == 0
    content = env_path.read_text(encoding="utf-8")
    assert 'NOTEFORGE_LLM_PROVIDER="ollama"' in content
    assert 'NOTEFORGE_LLM_MODEL="qwen-test"' in content
    assert 'NOTEFORGE_LLM_TIMEOUT_SECONDS="90"' in content
    assert "配置已保存" in result.stdout


def test_generate_missing_config_points_to_configure(monkeypatch) -> None:
    def fail_to_create():
        from noteforge.exceptions import LLMConfigurationError

        raise LLMConfigurationError("缺少配置")

    monkeypatch.setattr(
        "noteforge.cli.configuration.create_llm_client",
        fail_to_create,
    )
    monkeypatch.setattr(
        "noteforge.cli.configuration.sys.stdin.isatty",
        lambda: False,
    )

    result = runner.invoke(
        app,
        ["generate", "https://www.bilibili.com/video/BV1CkArz1E4o"],
    )

    assert result.exit_code == 1
    assert "noteforge configure" in result.output
    assert "Traceback" not in result.output


def test_version() -> None:
    result = runner.invoke(app, ["--version"])

    assert result.exit_code == 0
    assert result.stdout.strip() == version("noteforge-cli")


def test_generate_runs_pipeline_and_writes_output(
    monkeypatch,
    tmp_path,
) -> None:
    output_path = tmp_path / "notes" / "note.md"
    received = []

    class FakePipeline:
        async def run(self, source, output, **options):
            received.append((source, output, options))
            output.parent.mkdir(parents=True)
            output.write_text("# 已生成\n", encoding="utf-8")
            return output

    class FakeClient:
        async def aclose(self):
            pass

    monkeypatch.setattr(
        "noteforge.cli.configuration.create_llm_client",
        FakeClient,
    )
    monkeypatch.setattr(
        NoteGenerationPipeline,
        "from_llm_client",
        classmethod(lambda cls, client, **kwargs: FakePipeline()),
    )

    result = runner.invoke(
        app,
        [
            "generate",
            "https://www.bilibili.com/video/BV1CkArz1E4o",
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code == 0
    assert output_path.exists()
    assert output_path.read_text(encoding="utf-8") == "# 已生成\n"
    assert received[0][0] == (
        "https://www.bilibili.com/video/BV1CkArz1E4o"
    )
    assert received[0][1] == output_path
    assert "学习笔记已生成" in result.stdout


def test_inspect_requires_url() -> None:
    result = runner.invoke(app, ["inspect"])

    assert result.exit_code != 0
    assert "Missing argument" in result.output


def test_inspect_calls_business_layer(monkeypatch) -> None:
    received = []
    received_browsers = []

    def fake_inspect_source(url: str) -> inspection.InspectionResult:
        received.append(url)
        return inspection.InspectionResult(
            original_source=url,
            platform=inspection.InspectionPlatform.BILIBILI,
            source_id="BV1test",
            normalized_source="https://www.bilibili.com/video/BV1test?p=2",
            page_number=2,
        )

    monkeypatch.setattr(inspection, "inspect_source", fake_inspect_source)

    def fake_init(
        self: bilibili.BilibiliCollector,
        cookies_from_browser: str | None = "chrome",
    ) -> None:
        received_browsers.append(cookies_from_browser)

    monkeypatch.setattr(bilibili.BilibiliCollector, "__init__", fake_init)

    def fake_collect(
        self: bilibili.BilibiliCollector, source: str
    ) -> VideoCollectionResult:
        received.append(source)
        return VideoCollectionResult(
            metadata=VideoMetadata(
                id="BV1test",
                title="测试视频",
                description=None,
                uploader=None,
                uploader_id=None,
                duration=None,
                webpage_url=source,
                thumbnail=None,
                upload_date=None,
                view_count=None,
                like_count=None,
                extractor="BiliBili",
                extractor_key="BiliBili",
            ),
            subtitle_tracks=(),
        )

    monkeypatch.setattr(bilibili.BilibiliCollector, "collect", fake_collect)

    result = runner.invoke(
        app,
        [
            "inspect",
            "https://example.com/video",
            "--cookies-from-browser",
            "chrome",
        ],
    )

    assert result.exit_code == 0
    assert received == [
        "https://example.com/video",
        "https://www.bilibili.com/video/BV1test?p=2",
    ]
    assert received_browsers == ["chrome"]
    assert "平台：bilibili" in result.stdout
    assert "视频 ID：BV1test" in result.stdout
    assert "分 P：2" in result.stdout
    assert '"video_collection_result": {' in result.stdout
    assert '"id": "BV1test"' in result.stdout
    assert '"available_track_count": 0' in result.stdout
    assert '"subtitle_tracks": []' in result.stdout


def test_inspect_does_not_collect_unknown_platform(monkeypatch) -> None:
    def fail_if_called(
        self: bilibili.BilibiliCollector, source: str
    ) -> VideoCollectionResult:
        raise AssertionError("未知平台不应调用 Bilibili collector")

    monkeypatch.setattr(bilibili.BilibiliCollector, "collect", fail_if_called)

    result = runner.invoke(app, ["inspect", "https://example.com/video"])

    assert result.exit_code == 0
    assert "平台：unknown" in result.stdout
    assert '"video_collection_result": null' in result.stdout


def test_inspect_displays_collection_error_without_traceback(monkeypatch) -> None:
    def fake_collect(
        self: bilibili.BilibiliCollector, source: str
    ) -> VideoCollectionResult:
        raise RiskControlError("B站拒绝了本次请求（HTTP 412）。")

    monkeypatch.setattr(bilibili.BilibiliCollector, "collect", fake_collect)

    result = runner.invoke(
        app,
        ["inspect", "https://www.bilibili.com/video/BV1CkArz1E4o"],
    )

    assert result.exit_code == 1
    assert "采集失败：B站拒绝了本次请求（HTTP 412）。" in result.output
    assert "Traceback" not in result.output


def test_inspect_outputs_subtitle_preview(monkeypatch, tmp_path) -> None:
    source = "https://www.bilibili.com/video/BV1CkArz1E4o"
    metadata = VideoMetadata(
        id="BV1CkArz1E4o",
        title="测试视频",
        description=None,
        uploader=None,
        uploader_id=None,
        duration=3,
        webpage_url=source,
        thumbnail=None,
        upload_date=None,
        view_count=None,
        like_count=None,
        extractor="BiliBili",
        extractor_key="BiliBili",
    )
    track = SubtitleTrack(
        language="zh-CN",
        extension="vtt",
        url="https://example.com/subtitle.vtt",
    )

    def fake_collect(self, url):
        return VideoCollectionResult(metadata, (track,))

    subtitle_path = tmp_path / "subtitle.vtt"
    subtitle_path.write_text(
        "WEBVTT\n\n00:00.000 --> 00:03.000\n大家好\n",
        encoding="utf-8",
    )

    def fake_download(self, source, track, **kwargs):
        return SubtitleFile(
            path=subtitle_path,
            language=track.language,
            extension=track.extension,
            is_automatic=track.is_automatic,
        )

    monkeypatch.setattr(bilibili.BilibiliCollector, "collect", fake_collect)
    monkeypatch.setattr(
        YtDlpSubtitleDownloader,
        "download",
        fake_download,
    )

    result = runner.invoke(app, ["inspect", source])

    assert result.exit_code == 0
    assert '"available_track_count": 1' in result.stdout
    assert '"selected_subtitle": {' in result.stdout
    assert '"language": "zh-CN"' in result.stdout
    assert '"extension": "vtt"' in result.stdout
    assert '"transcript": {' in result.stdout
    assert '"source": "manual_subtitle"' in result.stdout
    assert '"segment_count": 1' in result.stdout
    assert '"preview_limit": 5' in result.stdout
    assert '"text": "大家好"' in result.stdout
