"""CLI 命令共享的轻量视觉组件。"""

from collections.abc import Iterator
from contextlib import contextmanager

from rich.console import Console
from rich.table import Table


class StatusUI:
    """用统一 icon、对齐方式和单活动 spinner 展示顺序任务。"""

    def __init__(self, console: Console | None = None) -> None:
        self.console = console or Console()

    def title(self, text: str) -> None:
        self.console.print(f"[bold cyan]{text}[/bold cyan]\n")

    def section(self, text: str) -> None:
        self.console.print(f"\n[bold]{text}[/bold]")

    def success(self, label: str, detail: str) -> None:
        self._row("✓", "green", label, detail)

    def warning(self, label: str, detail: str) -> None:
        self._row("!", "yellow", label, detail)

    def failure(self, label: str, detail: str) -> None:
        self._row("✗", "red", label, detail)

    def info(self, label: str, detail: str) -> None:
        self._row("", "dim", label, detail)

    def _row(self, icon: str, style: str, label: str, detail: str) -> None:
        # Rich 按终端显示宽度处理中文，比字符串 padding 更稳定。
        table = Table.grid(padding=(0, 2))
        table.add_column(no_wrap=True)
        table.add_column(no_wrap=True, min_width=10)
        table.add_column()
        table.add_row(f"[{style}]{icon}[/{style}]", label, detail)
        self.console.print(table)

    @contextmanager
    def running(self, label: str, detail: str) -> Iterator[None]:
        """交互终端显示动画；重定向和测试环境保持安静。"""

        if not self.console.is_terminal:
            yield
            return
        with self.console.status(
            f"[cyan]{label:<10}[/cyan]{detail}",
            spinner="dots",
            spinner_style="cyan",
        ):
            yield
