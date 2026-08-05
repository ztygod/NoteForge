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
    assert "Transcript extracted" not in output
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
                "batch_completed": 2,
                "batch_total": 4,
                "active_batch": 3,
                "llm_calls": 2,
                "request_status": "等待模型响应",
            },
        )
    )

    assert renderer._running is running
    assert renderer._running is not None
    assert renderer._running.progress == 0.5
    console.print(renderer._running)
    rendered = console.export_text()
    assert "已完成 2/4" in rendered
    assert "活动批次 #3" in rendered

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


def test_running_event_carries_tool_operation_details() -> None:
    renderer, _ = make_renderer()
    renderer.handle(PipelineEvent(
        "semantic", PipelineStatus.RUNNING, "Semantic chunks generated",
        metrics={
            "operation": "retrying_validation",
            "attempt": 2,
            "max_attempts": 2,
            "tool_name": "submit_semantic_analysis",
        },
    ))

    assert renderer._running is not None
    assert renderer._running.metrics["operation"] == "retrying_validation"
    assert renderer._running.metrics["attempt"] == 2
    renderer._stop_live()


def test_default_progress_does_not_present_active_batch_as_completion() -> None:
    renderer, console = make_renderer()
    renderer.handle(PipelineEvent(
        "semantic",
        PipelineStatus.RUNNING,
        "Semantic chunks generated",
        progress=2 / 6,
        metrics={
            "batch_completed": 2,
            "batch_total": 6,
            "active_batch": 5,
            "operation": "requesting_model",
        },
    ))

    assert renderer._running is not None
    console.print(renderer._running)
    output = console.export_text()
    assert "已完成 2/6" in output
    assert "5/6" not in output
    assert "活动批次 #5" not in output
    renderer._stop_live()


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
