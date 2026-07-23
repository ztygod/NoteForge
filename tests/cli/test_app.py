from importlib.metadata import version

from typer.testing import CliRunner

from noteforge.cli.app import app
from noteforge.collector import bilibili, inspection
from noteforge.collector.models import VideoMetadata
from noteforge.exceptions import RiskControlError


runner = CliRunner()


def test_help_lists_inspect_command() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "inspect" in result.stdout


def test_version() -> None:
    result = runner.invoke(app, ["--version"])

    assert result.exit_code == 0
    assert result.stdout.strip() == version("noteforge")


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
    ) -> VideoMetadata:
        received.append(source)
        return VideoMetadata(
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


def test_inspect_does_not_collect_unknown_platform(monkeypatch) -> None:
    def fail_if_called(
        self: bilibili.BilibiliCollector, source: str
    ) -> VideoMetadata:
        raise AssertionError("未知平台不应调用 Bilibili collector")

    monkeypatch.setattr(bilibili.BilibiliCollector, "collect", fail_if_called)

    result = runner.invoke(app, ["inspect", "https://example.com/video"])

    assert result.exit_code == 0
    assert "平台：unknown" in result.stdout
    assert '"video_collection_result": null' in result.stdout


def test_inspect_displays_collection_error_without_traceback(monkeypatch) -> None:
    def fake_collect(
        self: bilibili.BilibiliCollector, source: str
    ) -> VideoMetadata:
        raise RiskControlError("B站拒绝了本次请求（HTTP 412）。")

    monkeypatch.setattr(bilibili.BilibiliCollector, "collect", fake_collect)

    result = runner.invoke(
        app,
        ["inspect", "https://www.bilibili.com/video/BV1CkArz1E4o"],
    )

    assert result.exit_code == 1
    assert "采集失败：B站拒绝了本次请求（HTTP 412）。" in result.output
    assert "Traceback" not in result.output
