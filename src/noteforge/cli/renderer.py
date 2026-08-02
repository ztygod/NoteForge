"""使用 Rich 展示 Pipeline 事件的终端适配器。"""

from rich.console import Console
from rich.panel import Panel
from rich.progress_bar import ProgressBar
from rich.text import Text

from noteforge.core.events import PipelineEvent, PipelineStatus
from noteforge.exceptions import PipelineExecutionError


_KEY_STAGES = {"transcript", "knowledge", "output"}


class PipelineRenderer:
    """消费并展示事件，避免 Pipeline 代码直接依赖终端。"""

    def __init__(self, *, verbose: bool = False, console: Console | None = None) -> None:
        self.verbose = verbose
        self.console = console or Console()
        self.console.print("[bold cyan]🚀 NoteForge Generate[/bold cyan]\n")

    def handle(self, event: PipelineEvent) -> None:
        if event.stage == "pipeline" and event.status is PipelineStatus.SUCCESS:
            self.console.print(f"\n[bold green]✨ Finished in {event.duration or 0:.1f}s[/bold green]")
            return
        if not self.verbose and event.stage not in _KEY_STAGES:
            return
        if not self.verbose and event.metrics:
            return
        if event.status is PipelineStatus.RUNNING:
            if self.verbose:
                self.console.print(f"[cyan]⠋[/cyan] {event.message}")
            return
        if event.status is PipelineStatus.SUCCESS:
            self.console.print(f"[green]✓[/green] {event.message}")
            if self.verbose:
                self._details(event)
        elif event.status is PipelineStatus.ERROR:
            self.console.print(f"[red]✗[/red] {event.message}")

    def _details(self, event: PipelineEvent) -> None:
        if event.progress is not None:
            self.console.print(ProgressBar(total=100, completed=event.progress * 100, width=30))
        for key, value in event.metrics.items():
            if isinstance(value, dict):
                self.console.print(f"  {key}:")
                for nested_key, nested_value in value.items():
                    self.console.print(f"    {nested_key}: {nested_value}")
            else:
                self.console.print(f"  {key}: {value}")
        if event.duration is not None:
            self.console.print(f"  duration: {event.duration:.2f}s", style="dim")

    def render_error(self, error: PipelineExecutionError, *, debug: bool = False) -> None:
        context = error.context
        lines = Text()
        lines.append("Stage:\n", style="bold")
        lines.append(f"{context.stage}\n")
        if context.object_name:
            lines.append("\nObject:\n", style="bold")
            lines.append(f"{context.object_name}\n")
        lines.append("\nReason:\n", style="bold")
        lines.append(f"{context.reason or error}\n")
        if context.allowed_values:
            lines.append("\nAllowed values:\n", style="bold")
            lines.append("".join(f"- {value}\n" for value in context.allowed_values))
        if context.source_text:
            lines.append("\nSource text:\n", style="bold")
            lines.append(context.source_text[:1000])
        if debug:
            lines.append("\n\nOriginal exception:\n", style="bold")
            lines.append(f"{type(error.original).__name__}: {error.original}")
        title = "Knowledge Generation Failed" if context.stage == "KnowledgePointBuilder" else "Generation Failed"
        self.console.print(Panel(lines, title=f"❌ {title}", border_style="red"))
