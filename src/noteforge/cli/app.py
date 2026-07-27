"""NoteForge 命令行入口。"""

from dataclasses import asdict
from importlib.metadata import version
import json
from pathlib import Path

import typer

from noteforge.collector import bilibili, inspection
from noteforge.collector.models import VideoCollectionResult
from noteforge.exceptions import CollectionError, SubtitleError


app = typer.Typer(
    help="根据公开课视频生成结构化学习笔记。",
    no_args_is_help=True,
)

_SUBTITLE_PREVIEW_LIMIT = 5


def _subtitle_debug_output(
    collection: VideoCollectionResult,
) -> dict[str, object]:
    selected = collection.selected_subtitle
    transcript = collection.transcript
    return {
        "available_track_count": len(collection.subtitle_tracks),
        "subtitle_tracks": [
            asdict(track)
            for track in collection.subtitle_tracks
        ],
        "selected_subtitle": asdict(selected) if selected else None,
        "transcript": (
            {
                "language": transcript.language,
                "source": transcript.source,
                "segment_count": len(transcript.segments),
                "preview_limit": _SUBTITLE_PREVIEW_LIMIT,
                "preview": [
                    asdict(segment)
                    for segment in transcript.segments[
                        :_SUBTITLE_PREVIEW_LIMIT
                    ]
                ],
            }
            if transcript
            else None
        ),
    }


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(version("noteforge"))
        raise typer.Exit()


@app.callback()
def cli(
    version_requested: bool = typer.Option(
        False,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="显示 NoteForge 版本并退出。",
    ),
) -> None:
    """NoteForge 命令行接口。"""


@app.command()
def inspect(
    url: str = typer.Argument(..., help="需要检查的公开课视频链接。"),
    cookies_from_browser: str = typer.Option(
        "chrome",  # 默认为谷歌浏览器
        "--cookies-from-browser",
        help="从指定浏览器读取 Cookie，例如 chrome、edge、firefox 或 safari。",
    ),
    subtitle_language: str | None = typer.Option(
        None,
        "--subtitle-language",
        help="优先选择的字幕语言，例如 zh-Hans、zh-CN 或 en。",
    ),
    subtitle_output_dir: Path = typer.Option(
        Path(".cache/noteforge/subtitles"),
        "--subtitle-output-dir",
        help="字幕缓存根目录。",
    ),
) -> None:
    """检查视频链接，采集视频信息并输出结构化调试数据。"""
    inspect_result = inspection.inspect_source(url)

    output = {
        "inspection": asdict(inspect_result),
        "video_collection_result": None,
        "subtitle": None,
    }

    # 目前只实现了B站视频信息采集，其他平台暂不支持远程采集。
    if (
        inspect_result.platform is inspection.InspectionPlatform.BILIBILI
        and inspect_result.normalized_source is not None
    ):
        try:
            collection = bilibili.collect_bilibili_video(
                source=inspect_result.normalized_source,
                cookies_from_browser=cookies_from_browser,
                subtitle_language=subtitle_language,
                subtitle_output_dir=subtitle_output_dir,
                page_number=inspect_result.page_number,
            )
        except (CollectionError, SubtitleError) as error:
            typer.secho(f"采集失败：{error}", fg=typer.colors.RED, err=True)
            raise typer.Exit(code=1) from error
        output["video_collection_result"] = asdict(collection.metadata)
        output["subtitle"] = _subtitle_debug_output(collection)

    # 简要摘要便于人类阅读，后面的 JSON 保留给脚本和调试工具消费。
    typer.echo(f"平台：{inspect_result.platform.value}")
    if inspect_result.source_id is not None:
        typer.echo(f"视频 ID：{inspect_result.source_id}")
    if inspect_result.page_number is not None:
        typer.echo(f"分 P：{inspect_result.page_number}")
    typer.echo("结构化数据：")
    typer.echo(json.dumps(output, ensure_ascii=False, indent=2))


def main() -> None:
    """启动 NoteForge 命令行程序。"""
    app()
