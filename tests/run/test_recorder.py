import json
from pathlib import Path

from noteforge.core.events import PipelineEvent, PipelineStatus
from noteforge.run import RunRecorder


def make_recorder(tmp_path: Path) -> RunRecorder:
    return RunRecorder.start(
        root=tmp_path / "runs",
        source="https://www.bilibili.com/video/BV18fcozAEsy",
        source_id="BV18fcozAEsy",
        platform="bilibili",
        normalized_source="https://www.bilibili.com/video/BV18fcozAEsy",
        page_number=1,
        output_path=Path("output/BV18fcozAEsy.md"),
    )


def test_records_events_artifacts_and_success_manifest(tmp_path: Path) -> None:
    recorder = make_recorder(tmp_path)
    recorder.configure(
        api_format="openai",
        model="deepseek-v4-flash",
        base_url="https://user:secret@api.deepseek.com/v1?token=secret",
        llm_concurrency=3,
        subtitle_language=None,
        cookie_strategy="chrome",
    )
    recorder.handle_event(PipelineEvent(
        "semantic",
        PipelineStatus.RUNNING,
        "Semantic chunks generated",
        progress=0.5,
        metrics={"batch_completed": 2, "batch_total": 4},
    ))
    recorder.save_artifact("semantic_chunks", ("first", "second"))
    recorder.save_note("# Note\n")
    recorder.complete(Path("output/BV18fcozAEsy.md"))

    manifest = json.loads(recorder.manifest_path.read_text(encoding="utf-8"))
    assert manifest["status"] == "success"
    assert manifest["configuration"]["api_format"] == "openai"
    assert manifest["configuration"]["base_url_origin"] == (
        "https://api.deepseek.com"
    )
    assert manifest["stages"]["semantic"]["progress"] == 0.5
    assert manifest["artifacts"]["semantic_chunks"]["item_count"] == 2
    assert (recorder.artifacts_dir / "note.md").read_text() == "# Note\n"

    events = [
        json.loads(line)
        for line in recorder.events_path.read_text(encoding="utf-8").splitlines()
    ]
    assert [event["sequence"] for event in events] == list(
        range(1, len(events) + 1)
    )
    assert events[0]["type"] == "run.started"
    assert any(event["type"] == "stage.started" for event in events)
    assert events[-1]["type"] == "run.completed"


def test_failure_writes_redacted_error_record(tmp_path: Path) -> None:
    recorder = make_recorder(tmp_path)
    recorder.fail(RuntimeError("Authorization: Bearer sk-supersecret123"))

    manifest = json.loads(recorder.manifest_path.read_text(encoding="utf-8"))
    error = json.loads(
        (recorder.logs_dir / "error.json").read_text(encoding="utf-8")
    )
    assert manifest["status"] == "failed"
    assert "supersecret" not in json.dumps(manifest)
    assert "supersecret" not in json.dumps(error)
    assert "[REDACTED]" in error["message"]


def test_cancel_closes_running_manifest(tmp_path: Path) -> None:
    recorder = make_recorder(tmp_path)
    recorder.cancel()

    manifest = json.loads(recorder.manifest_path.read_text(encoding="utf-8"))
    assert manifest["status"] == "cancelled"
    assert manifest["completed_at"] is not None
