"""NoteForge 命令行入口。"""

from dataclasses import asdict
from importlib.metadata import version
import json

import typer

from noteforge.collector import bilibili, inspection
from noteforge.exceptions import CollectionError


app = typer.Typer(
    help="根据公开课视频生成结构化学习笔记。",
    no_args_is_help=True,
)


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
        "chrome", # 默认为谷歌浏览器
        "--cookies-from-browser",
        help="从指定浏览器读取 Cookie，例如 chrome、edge、firefox 或 safari。",
    ),
) -> None:
    """检查视频链接，采集视频信息并输出结构化调试数据。"""
    inspect_result = inspection.inspect_source(url)

    typer.echo(f"平台：{inspect_result.platform.value}")
    if inspect_result.source_id is not None:
        typer.echo(f"视频 ID：{inspect_result.source_id}")
    if inspect_result.page_number is not None:
        typer.echo(f"分 P：{inspect_result.page_number}")

    output = {"inspection": asdict(inspect_result), "video_collection_result": None}


    # 目前只实现了B站视频信息采集，其他平台暂不支持远程采集。
    if (
        inspect_result.platform is inspection.InspectionPlatform.BILIBILI
        and inspect_result.normalized_source is not None
    ):
        try:
            collector = bilibili.BilibiliCollector(
                cookies_from_browser=cookies_from_browser
            )
            collect_result = collector.collect(inspect_result.normalized_source)
        except CollectionError as error:
            typer.secho(f"采集失败：{error}", fg=typer.colors.RED, err=True)
            raise typer.Exit(code=1) from error
        output["video_collection_result"] = asdict(collect_result)

    typer.echo("结构化数据：")
    typer.echo(json.dumps(output, ensure_ascii=False, indent=2))


def main() -> None:
    """启动 NoteForge 命令行程序。"""
    app()
