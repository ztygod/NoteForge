"""NoteForge CLI 子命令实现。"""

from noteforge.cli.commands.configure import configure
from noteforge.cli.commands.doctor import doctor
from noteforge.cli.commands.generate import generate
from noteforge.cli.commands.inspect import inspect

__all__ = ["configure", "doctor", "generate", "inspect"]
