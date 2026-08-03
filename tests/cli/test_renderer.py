from rich.console import Console

from noteforge.cli.renderer import PipelineRenderer
from noteforge.core.events import PipelineEvent, PipelineStatus
from noteforge.exceptions import PipelineErrorContext, PipelineExecutionError


def make_renderer(*, verbose: bool = False) -> tuple[PipelineRenderer, Console]:
    console = Console(record=True, force_terminal=False, width=100)
    return PipelineRenderer(verbose=verbose, console=console), console


def test_default_renderer_only_prints_key_success_stages() -> None:
    renderer, console = make_renderer()
    renderer.handle(PipelineEvent("chunk", PipelineStatus.SUCCESS, "Raw chunks created"))
    renderer.handle(PipelineEvent("transcript", PipelineStatus.SUCCESS, "Transcript extracted"))
    renderer.handle(PipelineEvent("knowledge", PipelineStatus.SUCCESS, "Knowledge generated"))
    renderer.handle(PipelineEvent("output", PipelineStatus.SUCCESS, "Markdown saved"))

    output = console.export_text()
    assert "Raw chunks created" not in output
    assert "Transcript extracted" in output
    assert "Knowledge generated" in output
    assert "Markdown saved" in output


def test_verbose_renderer_prints_metrics_and_duration() -> None:
    renderer, console = make_renderer(verbose=True)
    renderer.handle(
        PipelineEvent(
            "knowledge",
            PipelineStatus.SUCCESS,
            "Knowledge points counted",
            metrics={"knowledge_points": 52, "llm_calls": 8, "retries": 1},
            duration=3.5,
        )
    )

    output = console.export_text()
    assert "knowledge_points: 52" in output
    assert "llm_calls: 8" in output
    assert "retries: 1" in output
    assert "(3.50s)" in output


def test_running_events_update_one_live_stage_until_success() -> None:
    renderer, console = make_renderer(verbose=True)
    renderer.handle(
        PipelineEvent(
            "semantic",
            PipelineStatus.RUNNING,
            "Semantic chunks generated",
        )
    )
    running = renderer._running
    renderer.handle(
        PipelineEvent(
            "semantic",
            PipelineStatus.RUNNING,
            "Semantic chunks generated",
            progress=0.5,
            metrics={
                "batch_current": 2,
                "batch_total": 4,
                "llm_calls": 2,
                "request_status": "等待模型响应",
            },
        )
    )

    assert renderer._running is running
    assert renderer._running is not None
    assert renderer._running.progress == 0.5

    renderer.handle(
        PipelineEvent(
            "semantic",
            PipelineStatus.SUCCESS,
            "Semantic chunks generated",
            duration=2.0,
        )
    )

    assert renderer._running is None
    assert renderer._live is None
    assert console.export_text().count("✓ Semantic chunks generated") == 1


def test_structured_error_includes_context_and_original_in_debug() -> None:
    renderer, console = make_renderer()
    original = ValueError("Knowledge point 14 contains invalid point_type: 'definition'")
    error = PipelineExecutionError(
        PipelineErrorContext(
            stage="KnowledgePointBuilder",
            object_name="KnowledgePoint #14",
            reason="Invalid point_type:\ndefinition",
            allowed_values=("concept", "example"),
            source_text="source excerpt",
        ),
        original,
    )
    renderer.render_error(error, debug=True)

    output = console.export_text()
    assert "KnowledgePointBuilder" in output
    assert "KnowledgePoint #14" in output
    assert "Allowed values" in output
    assert "source excerpt" in output
    assert "ValueError:" in output
