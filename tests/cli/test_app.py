from importlib.metadata import version

from typer.testing import CliRunner

from noteforge.cli.app import app
from noteforge.collector import inspection


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

    result = runner.invoke(app, ["inspect", "https://example.com/video"])

    assert result.exit_code == 0
    assert received == ["https://example.com/video"]
    assert "平台：bilibili" in result.stdout
    assert "视频 ID：BV1test" in result.stdout
    assert "分 P：2" in result.stdout
