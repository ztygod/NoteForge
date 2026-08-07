"""inspect 子命令。"""

from dataclasses import asdict
import json
from pathlib import Path

import typer

from noteforge.cli.serialization import subtitle_debug_output
from noteforge.exceptions import CollectionError, SubtitleError
from noteforge.collector import collect_video
from noteforge.collector import source as inspection


def inspect(
    url: str = typer.Argument(..., help="需要检查的公开课视频链接。"),
    cookies_from_browser: str = typer.Option(
        "chrome",  # 默认从谷歌浏览器读取 Cookie。
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

    if (
        inspect_result.platform in {
            inspection.InspectionPlatform.BILIBILI,
            inspection.InspectionPlatform.YOUTUBE,
        }
        and inspect_result.normalized_source is not None
    ):
        try:
            collection = collect_video(
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
        output["subtitle"] = subtitle_debug_output(collection)

    # 先输出便于阅读的摘要，再保留可供脚本和调试工具消费的 JSON。
    typer.echo(f"平台：{inspect_result.platform.value}")
    if inspect_result.source_id is not None:
        typer.echo(f"视频 ID：{inspect_result.source_id}")
    if inspect_result.page_number is not None:
        typer.echo(f"分 P：{inspect_result.page_number}")
    typer.echo("结构化数据：")
    typer.echo(json.dumps(output, ensure_ascii=False, indent=2))
