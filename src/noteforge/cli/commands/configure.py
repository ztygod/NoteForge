"""configure 子命令。"""

from pathlib import Path

import typer

from noteforge.cli.configuration import run_configuration_wizard


def configure(
    path: Path = typer.Option(
        Path(".env"),
        "--path",
        help="保存 NoteForge 环境变量的 dotenv 文件。",
    ),
) -> None:
    """交互设置 LLM 环境变量，首次使用时建议先运行。"""

    run_configuration_wizard(path)

