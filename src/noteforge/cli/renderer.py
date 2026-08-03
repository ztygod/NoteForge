"""使用 Rich 动态展示 Pipeline 事件。"""

from time import monotonic
from typing import Any

from rich.console import Console, ConsoleOptions, Group, RenderResult
from rich.live import Live
from rich.panel import Panel
from rich.progress_bar import ProgressBar
from rich.spinner import Spinner
from rich.text import Text

from noteforge.core.events import PipelineEvent, PipelineStatus
from noteforge.exceptions import PipelineExecutionError


_KEY_STAGES = {"transcript", "semantic", "knowledge", "output"}

_OPERATION_LABELS = {
    "requesting_model": "请求模型",
    "tool_submitted": "工具已提交",
    "validating_response": "校验响应",
    "retrying_validation": "校验失败，正在重试",
}


class _RunningStage:
    """由 Rich Live 重复渲染的单阶段状态。"""

    def __init__(self, event: PipelineEvent) -> None:
        self.started_at = monotonic()
        self.spinner = Spinner("dots")
        self.update(event)

    def update(self, event: PipelineEvent) -> None:
        """使用新事件更新文案、进度和指标。"""

        self.message = event.message
        self.progress = event.progress
        self.metrics = dict(event.metrics)

    def __rich_console__(
        self,
        console: Console,
        options: ConsoleOptions,
    ) -> RenderResult:
        elapsed = monotonic() - self.started_at
        suffix = Text(f"  {elapsed:.1f}s", style="dim")
        batch_current = self.metrics.get("batch_current")
        batch_total = self.metrics.get("batch_total")
        request_status = self.metrics.get("request_status")
        llm_calls = self.metrics.get("llm_calls")
        model = self.metrics.get("model")
        output_tokens = self.metrics.get("output_tokens")
        operation = self.metrics.get("operation")
        attempt = self.metrics.get("attempt")
        max_attempts = self.metrics.get("max_attempts")
        tool_name = self.metrics.get("tool_name")

        description = Text(self.message)
        if batch_current is not None and batch_total is not None:
            description.append(f"  {batch_current}/{batch_total}", style="cyan")
        if request_status:
            description.append(f"  {request_status}", style="yellow")
        if operation:
            description.append(
                f"  {_OPERATION_LABELS.get(str(operation), operation)}",
                style="yellow",
            )
        if tool_name:
            description.append(f"  {tool_name}", style="cyan")
        if attempt is not None:
            attempt_text = f"{attempt}/{max_attempts}" if max_attempts else str(attempt)
            description.append(f"  attempt {attempt_text}", style="magenta")
        if llm_calls is not None:
            description.append(f"  LLM #{llm_calls}", style="magenta")
        if model:
            description.append(f"  {model}", style="blue")
        if output_tokens:
            description.append(f"  ↑{output_tokens} tokens", style="dim")
        description.append_text(suffix)
        self.spinner.update(text=description)

        renderables: list[Any] = [self.spinner]
        if self.progress is not None:
            renderables.append(
                Group(
                    ProgressBar(
                        total=100,
                        completed=self.progress * 100,
                        width=min(40, max(10, options.max_width - 12)),
                    ),
                    Text(f"{self.progress:.0%}", style="dim"),
                )
            )
        yield Group(*renderables)


class PipelineRenderer:
    """用单个动态状态区域消费事件，完成后再固化最终结果。"""

    def __init__(
        self,
        *,
        verbose: bool = False,
        console: Console | None = None,
    ) -> None:
        self.verbose = verbose
        self.console = console or Console()
        self._live: Live | None = None
        self._running: _RunningStage | None = None
        self._running_stage: str | None = None
        self.console.print("[bold cyan]🚀 NoteForge Generate[/bold cyan]\n")

    def _is_visible(self, event: PipelineEvent) -> bool:
        return self.verbose or event.stage in _KEY_STAGES

    def _start_or_update(self, event: PipelineEvent) -> None:
        if self._running_stage != event.stage:
            self._stop_live()
            self._running = _RunningStage(event)
            self._running_stage = event.stage
            self._live = Live(
                self._running,
                console=self.console,
                refresh_per_second=10,
                transient=True,
            )
            self._live.start(refresh=True)
            return
        if self._running is not None and self._live is not None:
            self._running.update(event)
            self._live.update(self._running, refresh=True)

    def _stop_live(self) -> None:
        if self._live is not None:
            self._live.stop()
        self._live = None
        self._running = None
        self._running_stage = None

    def handle(self, event: PipelineEvent) -> None:
        """消费单个事件并更新动态区域或最终输出。"""

        if event.stage == "pipeline" and event.status is PipelineStatus.SUCCESS:
            self._stop_live()
            self.console.print(
                f"\n[bold green]✨ Finished in {event.duration or 0:.1f}s[/bold green]"
            )
            return
        if not self._is_visible(event):
            return
        if event.status is PipelineStatus.RUNNING:
            self._start_or_update(event)
            return

        self._stop_live()
        if event.status is PipelineStatus.SUCCESS:
            duration = (
                f" [dim]({event.duration:.2f}s)[/dim]"
                if event.duration is not None
                else ""
            )
            self.console.print(f"[green]✓[/green] {event.message}{duration}")
            if self.verbose:
                self._details(event)
        elif event.status is PipelineStatus.ERROR:
            self.console.print(f"[red]✗[/red] {event.message}")

    def _details(self, event: PipelineEvent) -> None:
        for key, value in event.metrics.items():
            if value is None:
                continue
            if isinstance(value, dict):
                self.console.print(f"  {key}:")
                for nested_key, nested_value in value.items():
                    self.console.print(f"    {nested_key}: {nested_value}")
            else:
                self.console.print(f"  {key}: {value}")

    def render_error(
        self,
        error: PipelineExecutionError,
        *,
        debug: bool = False,
    ) -> None:
        """停止动态区域并展示结构化错误上下文。"""

        self._stop_live()
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
        title = (
            "Knowledge Generation Failed"
            if context.stage == "KnowledgePointBuilder"
            else "Generation Failed"
        )
        self.console.print(
            Panel(lines, title=f"❌ {title}", border_style="red")
        )
