"""NoteForge 命令行入口。"""

from dataclasses import asdict
from importlib.metadata import version
import json

import typer

from noteforge.collector import inspection
from noteforge.collector.collect import bilibili


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
) -> None:
    """检查视频链接，采集视频信息并输出结构化调试数据。"""
    inspect_result = inspection.inspect_source(url)

    typer.echo(f"平台：{inspect_result.platform.value}")
    if inspect_result.source_id is not None:
        typer.echo(f"视频 ID：{inspect_result.source_id}")
    if inspect_result.page_number is not None:
        typer.echo(f"分 P：{inspect_result.page_number}")

    output = {"inspection": asdict(inspect_result), "collection": None}

    if (
        inspect_result.platform is inspection.InspectionPlatform.BILIBILI
        and inspect_result.source_id is not None
    ):
        collect_result = bilibili.BilibiliCollector().collect(
            inspect_result.source_id
        )
        output["collection"] = asdict(collect_result)

    typer.echo("结构化数据：")
    typer.echo(json.dumps(output, ensure_ascii=False, indent=2))


def main() -> None:
    """启动 NoteForge 命令行程序。"""
    app()
