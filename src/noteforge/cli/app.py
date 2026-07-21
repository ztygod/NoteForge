"""NoteForge 命令行入口。"""

from importlib.metadata import version

import typer

from noteforge.collector import inspection


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
    """本地检查并规范化视频链接，不执行网络请求。"""
    result = inspection.inspect_source(url)
    typer.echo(f"平台：{result.platform.value}")
    typer.echo(f"视频 ID：{result.source_id or '未识别'}")
    typer.echo(
        f"分 P：{result.page_number if result.page_number is not None else '未指定'}"
    )
    typer.echo(f"规范链接：{result.normalized_source or result.original_source}")


def main() -> None:
    """启动 NoteForge 命令行程序。"""
    app()
