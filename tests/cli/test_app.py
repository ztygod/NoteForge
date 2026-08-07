from importlib.metadata import version
import importlib
import json
from dataclasses import dataclass

from typer.testing import CliRunner

from noteforge.cli.app import app
from noteforge.collector import source as inspection
from noteforge.media.models import Subtitle, SubtitleSegment, VideoMetadata as MediaMetadata, VideoResource
from noteforge.config import LLMSettings
from noteforge.exceptions import RiskControlError
from noteforge.exceptions import RemoteCollectionError
from noteforge.core import NoteGenerationPipeline


@dataclass(frozen=True)
class TranscriptSegment:
    """旧测试输入使用的临时字幕片段。"""

    start_seconds: float
    end_seconds: float
    text: str


@dataclass(frozen=True)
class Transcript:
    """旧测试输入使用的临时字幕集合。"""

    language: str
    segments: tuple[TranscriptSegment, ...]
    source: str


class VideoMetadata:
    """把旧测试参数转换成当前媒体元数据。"""

    def __new__(cls, **values):
        return MediaMetadata(
            id=values["id"], title=values["title"], uploader=values.get("uploader"),
            duration=values.get("duration"), thumbnail=values.get("thumbnail"),
            platform=str(values.get("extractor", "bilibili")).lower(),
            webpage_url=values["webpage_url"], description=values.get("description"),
        )


class SubtitleTrack:
    """把旧测试字幕参数转换成当前字幕模型。"""

    def __new__(cls, language, extension, url, name=None, is_automatic=False):
        del url, name
        return Subtitle(language, extension, is_automatic=is_automatic)


class VideoCollectionResult:
    """把旧测试夹具转换成当前视频资源。"""

    def __new__(cls, metadata, subtitle_tracks=(), selected_subtitle=None, transcript=None):
        del selected_subtitle
        segments = ()
        source = None
        if transcript:
            segments = tuple(
                SubtitleSegment(item.start_seconds, item.end_seconds, item.text)
                for item in transcript.segments
            )
            source = transcript.source
        return VideoResource(metadata, tuple(subtitle_tracks), segments, transcript_source=source)


runner = CliRunner()
doctor_module = importlib.import_module("noteforge.cli.commands.doctor")
configure_module = importlib.import_module("noteforge.cli.commands.configure")
generate_module = importlib.import_module("noteforge.cli.commands.generate")
inspect_module = importlib.import_module("noteforge.cli.commands.inspect")


def test_help_lists_inspect_command() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "inspect" in result.stdout
    assert "generate" in result.stdout
    assert "configure" in result.stdout
    assert "doctor" in result.stdout


def test_doctor_missing_config_points_to_configure(monkeypatch) -> None:
    def missing_settings():
        raise ValueError("缺少配置：NOTEFORGE_LLM_PROVIDER")

    monkeypatch.setattr(doctor_module.LLMSettings, "from_env", missing_settings)

    result = runner.invoke(app, ["doctor"])

    assert result.exit_code == 1
    assert "LLM 配置" in result.output
    assert "noteforge configure" in result.output


def test_doctor_checks_model_and_explains_optional_video_check(
    monkeypatch,
) -> None:
    settings = LLMSettings(
        provider="ollama",
        model="qwen-test",
        api_key=None,
        base_url="http://localhost:11434",
    )

    async def healthy_model(_settings):
        return "qwen-test"

    monkeypatch.setattr(doctor_module.LLMSettings, "from_env", lambda: settings)
    monkeypatch.setattr(doctor_module, "_check_model", healthy_model)

    result = runner.invoke(app, ["doctor"])

    assert result.exit_code == 0
    assert "Ollama native / qwen-test" in result.output
    assert "模型调用" in result.output
    assert "未提供 URL" in result.output
    assert "noteforge doctor 'https://www.bilibili.com/video/BV...'" in result.output


def test_doctor_checks_cookie_and_supported_subtitle(
    monkeypatch,
) -> None:
    source = "https://www.bilibili.com/video/BV1CkArz1E4o"
    settings = LLMSettings(
        provider="ollama",
        model="qwen-test",
        api_key=None,
        base_url="http://localhost:11434",
    )

    async def healthy_model(_settings):
        return "qwen-test"

    monkeypatch.setattr(doctor_module.LLMSettings, "from_env", lambda: settings)
    monkeypatch.setattr(doctor_module, "_check_model", healthy_model)

    received_cookies = []

    def video_info(url, *, cookies_from_browser):
        received_cookies.append(cookies_from_browser)
        return VideoCollectionResult(
            metadata=VideoMetadata(
                id="BV1CkArz1E4o",
                title="测试课程",
                description=None,
                uploader=None,
                uploader_id=None,
                duration=60,
                webpage_url=url,
                thumbnail=None,
                upload_date=None,
                view_count=None,
                like_count=None,
                extractor="BiliBili",
                extractor_key="BiliBili",
            ),
            subtitle_tracks=(
                SubtitleTrack(
                    language="zh-CN",
                    extension="vtt",
                    url="https://example.com/subtitle.vtt",
                ),
            ),
        )

    monkeypatch.setattr(doctor_module, "discover_video", video_info)

    result = runner.invoke(app, ["doctor", source])

    assert result.exit_code == 0
    assert received_cookies == [None]
    assert "无需浏览器 Cookie" in result.output
    assert "zh-CN · 人工字幕 · VTT" in result.output
    assert f"noteforge generate '{source}' --cookies-from-browser \"\"" in result.output


def test_doctor_reports_anonymous_failure_before_cookie_retry(
    monkeypatch,
) -> None:
    source = "https://www.bilibili.com/video/BV1CkArz1E4o"
    settings = LLMSettings(
        provider="ollama",
        model="qwen-test",
        api_key=None,
        base_url="http://localhost:11434",
    )

    async def healthy_model(_settings):
        return "qwen-test"

    monkeypatch.setattr(doctor_module.LLMSettings, "from_env", lambda: settings)
    monkeypatch.setattr(doctor_module, "_check_model", healthy_model)

    calls = []

    def video_info(url, *, cookies_from_browser):
        calls.append(cookies_from_browser)
        if cookies_from_browser is None:
            raise RemoteCollectionError("匿名响应中没有视频格式")
        return VideoCollectionResult(
            metadata=VideoMetadata(
                id="BV1CkArz1E4o",
                title="测试课程",
                description=None,
                uploader=None,
                uploader_id=None,
                duration=60,
                webpage_url=url,
                thumbnail=None,
                upload_date=None,
                view_count=None,
                like_count=None,
                extractor="BiliBili",
                extractor_key="BiliBili",
            ),
            subtitle_tracks=(
                SubtitleTrack(
                    language="zh-CN",
                    extension="vtt",
                    url="https://example.com/subtitle.vtt",
                ),
            ),
        )

    monkeypatch.setattr(doctor_module, "discover_video", video_info)

    result = runner.invoke(app, ["doctor", source])

    assert result.exit_code == 0
    assert calls == [None, "chrome"]
    assert "匿名访问" in result.output
    assert "失败，正在使用 chrome 浏览器 Cookie 重试" in result.output
    assert "需要 chrome 浏览器 Cookie" in result.output


def test_doctor_retries_with_cookie_when_anonymous_result_has_only_danmaku(
    monkeypatch,
) -> None:
    source = "https://www.bilibili.com/video/BV1CkArz1E4o"
    settings = LLMSettings(
        provider="ollama",
        model="qwen-test",
        api_key=None,
        base_url="http://localhost:11434",
    )

    async def healthy_model(_settings):
        return "qwen-test"

    monkeypatch.setattr(doctor_module.LLMSettings, "from_env", lambda: settings)
    monkeypatch.setattr(doctor_module, "_check_model", healthy_model)

    calls = []

    def video_info(url, *, cookies_from_browser):
        calls.append(cookies_from_browser)
        track = (
            SubtitleTrack(
                language="danmaku",
                extension="xml",
                url="https://comment.bilibili.com/test.xml",
            )
            if cookies_from_browser is None
            else SubtitleTrack(
                language="ai-zh",
                extension="srt",
                url="https://example.com/subtitle.srt",
                is_automatic=True,
            )
        )
        return VideoCollectionResult(
            metadata=VideoMetadata(
                id="BV1CkArz1E4o",
                title="测试课程",
                description=None,
                uploader=None,
                uploader_id=None,
                duration=60,
                webpage_url=url,
                thumbnail=None,
                upload_date=None,
                view_count=None,
                like_count=None,
                extractor="BiliBili",
                extractor_key="BiliBili",
            ),
            subtitle_tracks=(track,),
        )

    monkeypatch.setattr(doctor_module, "discover_video", video_info)

    result = runner.invoke(app, ["doctor", source])

    assert result.exit_code == 0
    assert calls == [None, "chrome"]
    assert "匿名字幕" in result.output
    assert "未发现 VTT/SRT，正在使用 chrome 浏览器 Cookie 重试" in result.output
    assert "已使用 chrome 浏览器 Cookie 重新检查" in result.output
    assert "ai-zh · 自动字幕 · SRT" in result.output


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


def test_generate_missing_config_points_to_configure(monkeypatch, tmp_path) -> None:
    def fail_to_load():
        from noteforge.exceptions import LLMConfigurationError

        raise LLMConfigurationError("缺少配置；请先运行 `noteforge configure`。")

    monkeypatch.setattr(generate_module, "load_configured_llm_settings", fail_to_load)

    result = runner.invoke(
        app,
        [
            "generate",
            "https://www.bilibili.com/video/BV1CkArz1E4o",
            "--run-dir",
            str(tmp_path / "runs"),
        ],
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

    settings = LLMSettings(
        provider="ollama",
        model="qwen-test",
        api_key=None,
        base_url="http://localhost:11434",
    )
    precollected = VideoCollectionResult(
        metadata=VideoMetadata(
            id="BV1CkArz1E4o",
            title="测试课程",
            description=None,
            uploader=None,
            uploader_id=None,
            duration=60,
            webpage_url="https://www.bilibili.com/video/BV1CkArz1E4o",
            thumbnail=None,
            upload_date=None,
            view_count=None,
            like_count=None,
            extractor="BiliBili",
            extractor_key="BiliBili",
        ),
        subtitle_tracks=(),
        transcript=Transcript(
            language="zh-CN",
            segments=(TranscriptSegment(0, 1, "测试字幕"),),
            source="manual_subtitle",
        ),
    )
    monkeypatch.setattr(
        generate_module,
        "load_configured_llm_settings",
        lambda: settings,
    )
    monkeypatch.setattr(
        generate_module,
        "_run_preflight",
        lambda *args, **kwargs: precollected,
    )
    monkeypatch.setattr(generate_module, "create_llm_client", lambda settings: FakeClient())
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
            "--run-dir",
            str(tmp_path / "runs"),
        ],
    )

    assert result.exit_code == 0
    assert output_path.exists()
    assert output_path.read_text(encoding="utf-8") == "# 已生成\n"
    assert received[0][0] == (
        "https://www.bilibili.com/video/BV1CkArz1E4o"
    )
    assert received[0][1] == output_path
    assert received[0][2]["precollected"] is precollected
    assert str(output_path) in result.output
    assert "Ollama native / qwen-test" in result.output
    assert "学习笔记已生成" in result.stdout
    run_dirs = list((tmp_path / "runs").iterdir())
    assert len(run_dirs) == 1
    manifest = json.loads((run_dirs[0] / "manifest.json").read_text())
    assert manifest["status"] == "success"
    assert (run_dirs[0] / "artifacts" / "transcript.json").exists()


def test_generate_uses_video_id_default_and_stops_before_llm_without_subtitle(
    monkeypatch,
    tmp_path,
) -> None:
    source = "https://www.bilibili.com/video/BV1CkArz1E4o"
    settings = LLMSettings(
        provider="ollama",
        model="qwen-test",
        api_key=None,
        base_url="http://localhost:11434",
    )
    collection = VideoCollectionResult(
        metadata=VideoMetadata(
            id="BV1CkArz1E4o",
            title="无字幕课程",
            description=None,
            uploader=None,
            uploader_id=None,
            duration=7560,
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
    client_created = False

    def create_client(_settings):
        nonlocal client_created
        client_created = True
        raise AssertionError("没有字幕时不应创建 LLM client")

    monkeypatch.setattr(
        generate_module,
        "load_configured_llm_settings",
        lambda: settings,
    )
    monkeypatch.setattr(
        generate_module, "collect_video", lambda **kwargs: collection
    )
    monkeypatch.setattr(generate_module, "create_llm_client", create_client)

    result = runner.invoke(app, [
        "generate",
        source,
        "--run-dir",
        str(tmp_path / "runs"),
    ])

    assert result.exit_code == 1
    assert client_created is False
    assert "output/BV1CkArz1E4o.md" in result.output
    assert "Ollama native / qwen-test" in result.output
    assert "无字幕课程 · 2h 06m" in result.output
    assert "没有可用字幕" in result.output
    assert "noteforge doctor" in result.output
    run_dirs = list((tmp_path / "runs").iterdir())
    assert len(run_dirs) == 1
    manifest = json.loads((run_dirs[0] / "manifest.json").read_text())
    assert manifest["status"] == "failed"
    assert (run_dirs[0] / "logs" / "error.json").exists()


def test_inspect_requires_url() -> None:
    result = runner.invoke(app, ["inspect"])

    assert result.exit_code != 0
    assert "Missing argument" in result.output


def test_inspect_calls_business_layer(monkeypatch) -> None:
    received = []

    def fake_inspect_source(url: str) -> inspection.InspectionResult:
        received.append(url)
        return inspection.InspectionResult(
            original_source=url,
            platform=inspection.InspectionPlatform.BILIBILI,
            source_id="BV1test",
            normalized_source="https://www.bilibili.com/video/BV1test?p=2",
            page_number=2,
        )

    monkeypatch.setattr(inspect_module.inspection, "inspect_source", fake_inspect_source)

    def fake_collect(*, source: str, **kwargs) -> VideoCollectionResult:
        received.append(source)
        assert kwargs["cookies_from_browser"] == "chrome"
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

    monkeypatch.setattr(inspect_module, "collect_video", fake_collect)

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
    assert "平台：bilibili" in result.stdout
    assert "视频 ID：BV1test" in result.stdout
    assert "分 P：2" in result.stdout
    assert '"video_collection_result": {' in result.stdout
    assert '"id": "BV1test"' in result.stdout
    assert '"available_track_count": 0' in result.stdout
    assert '"subtitle_tracks": []' in result.stdout


def test_inspect_does_not_collect_unknown_platform(monkeypatch) -> None:
    def fail_if_called(**kwargs) -> VideoCollectionResult:
        raise AssertionError("未知平台不应调用 Bilibili collector")

    monkeypatch.setattr(inspect_module, "collect_video", fail_if_called)

    result = runner.invoke(app, ["inspect", "https://example.com/video"])

    assert result.exit_code == 0
    assert "平台：unknown" in result.stdout
    assert '"video_collection_result": null' in result.stdout


def test_inspect_displays_collection_error_without_traceback(monkeypatch) -> None:
    def fake_collect(**kwargs) -> VideoCollectionResult:
        raise RiskControlError("B站拒绝了本次请求（HTTP 412）。")

    monkeypatch.setattr(inspect_module, "collect_video", fake_collect)

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

    def fake_collect(**kwargs):
        return VideoCollectionResult(
            metadata,
            (track,),
            selected_subtitle=track,
            transcript=Transcript(
                language="zh-CN",
                source="manual_subtitle",
                segments=(TranscriptSegment(0, 3, "大家好"),),
            ),
        )

    monkeypatch.setattr(inspect_module, "collect_video", fake_collect)

    result = runner.invoke(app, ["inspect", source])

    assert result.exit_code == 0
    assert '"available_track_count": 1' in result.stdout
    assert '"selected_subtitle": {' in result.stdout
    assert '"language": "zh-CN"' in result.stdout
    assert '"format": "vtt"' in result.stdout
    assert '"transcript": {' in result.stdout
    assert '"source": "manual_subtitle"' in result.stdout
    assert '"segment_count": 1' in result.stdout
    assert '"preview_limit": 5' in result.stdout
    assert '"text": "大家好"' in result.stdout
