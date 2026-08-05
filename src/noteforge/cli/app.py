"""NoteForge 命令行入口与子命令注册。"""

from importlib.metadata import version

import typer

from noteforge.cli.commands import configure, doctor, generate, inspect


_DISTRIBUTION_NAME = "noteforge-cli"

app = typer.Typer(
    help="根据公开课视频生成结构化学习笔记。",
    no_args_is_help=True,
)


def _version_callback(value: bool) -> None:
    """按需输出当前安装版本并结束命令。"""

    if value:
        typer.echo(version(_DISTRIBUTION_NAME))
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


app.command()(configure)
app.command()(doctor)
app.command()(inspect)
app.command()(generate)


def main() -> None:
    """启动 NoteForge 命令行程序。"""

    app()
