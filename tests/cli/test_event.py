from dataclasses import FrozenInstanceError

import pytest

from noteforge.core.events import PipelineEvent, PipelineStatus


def test_pipeline_event_carries_optional_progress_metrics_and_duration() -> None:
    event = PipelineEvent(
        stage="knowledge",
        status=PipelineStatus.RUNNING,
        message="Generating knowledge",
        progress=0.5,
        metrics={"llm_calls": 2},
        duration=1.25,
    )

    assert event.status.value == "running"
    assert event.progress == 0.5
    assert event.metrics["llm_calls"] == 2
    assert event.duration == 1.25


def test_pipeline_event_is_immutable_and_validates_progress() -> None:
    event = PipelineEvent("chunk", PipelineStatus.SUCCESS, "Done")
    with pytest.raises(FrozenInstanceError):
        event.message = "Changed"  # type: ignore[misc]
    with pytest.raises(ValueError, match="between 0 and 1"):
        PipelineEvent("chunk", PipelineStatus.RUNNING, "Work", progress=1.1)

