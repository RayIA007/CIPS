from __future__ import annotations

from telemetry_engine import TelemetryEngine
from telemetry_models import TelemetryEvent
from observability_query import ObservabilityQuery, RunDiagnosticSnapshot


def _event(
    *,
    event_id: str,
    operation: str,
    run_id: str,
    timestamp: str,
    success: bool = True,
    task_id: str = "",
    provider: str = "",
    duration_seconds: float = 0.0,
    retry_count: int = 0,
    retry_exhausted: bool = False,
    succeeded_after_retry: bool = False,
    exception_type: str = "",
    total_tokens: int = 0,
    estimated_cost: float = 0.0,
    metadata: dict | None = None,
) -> TelemetryEvent:
    return TelemetryEvent(
        event_id=event_id,
        timestamp=timestamp,
        project_id="project-a",
        component="final_review" if operation == "review.decision_recorded" else "workflow_engine",
        operation=operation,
        event_type="error" if not success else "result",
        success=success,
        provider=provider,
        duration_seconds=duration_seconds,
        retry_count=retry_count,
        retry_exhausted=retry_exhausted,
        succeeded_after_retry=succeeded_after_retry,
        exception_type=exception_type,
        total_tokens=total_tokens,
        estimated_cost=estimated_cost,
        currency="USD",
        metadata=dict(metadata or {}),
        workflow_id="workflow-a",
        run_id=run_id,
        task_id=task_id,
        correlation_id=run_id,
    )


def _persist(engine: TelemetryEngine, output_directory, *events: TelemetryEvent) -> None:
    for event in events:
        result = engine.record_event(
            event,
            output_directory=output_directory,
            update_summary=False,
        )
        assert result.success


def test_telemetry_engine_filters_by_f8_correlation_ids(tmp_path):
    engine = TelemetryEngine()
    output = tmp_path / "telemetry"
    _persist(
        engine,
        output,
        _event(
            event_id="evt-1",
            operation="task.succeeded",
            run_id="run-1",
            task_id="task-1",
            timestamp="2026-08-11T10:00:00+00:00",
        ),
        _event(
            event_id="evt-2",
            operation="task.succeeded",
            run_id="run-2",
            task_id="task-2",
            timestamp="2026-08-11T10:01:00+00:00",
        ),
    )

    result = engine.read_events(
        output_directory=output,
        workflow_id="workflow-a",
        run_id="run-1",
        task_id="task-1",
        correlation_id="run-1",
    )

    assert result.success
    assert [event.event_id for event in result.data] == ["evt-1"]
    assert result.metadata["filters"]["run_id"] == "run-1"


def test_snapshot_reconstructs_run_without_exposing_raw_metadata(tmp_path):
    engine = TelemetryEngine()
    output = tmp_path / "telemetry"
    _persist(
        engine,
        output,
        _event(
            event_id="evt-start",
            operation="workflow.started",
            run_id="run-1",
            timestamp="2026-08-11T10:00:00+00:00",
            metadata={
                "status": "running",
                "started_at": "2026-08-11T10:00:00+00:00",
                "secret": "do-not-surface",
            },
        ),
        _event(
            event_id="evt-adapter",
            operation="adapter.succeeded",
            run_id="run-1",
            task_id="task-video",
            timestamp="2026-08-11T10:00:01+00:00",
            provider="fake-media",
            duration_seconds=1.25,
            total_tokens=120,
            estimated_cost=0.25,
            metadata={
                "capability": "video.generate",
                "artifact_refs": [
                    {
                        "artifact_id": "art-1",
                        "content_hash": "sha256-1",
                        "artifact_type": "video",
                        "path": "C:/secret/output.mp4",
                    }
                ],
                "prompt": "sensitive prompt",
            },
        ),
        _event(
            event_id="evt-fail",
            operation="task.failed",
            run_id="run-1",
            task_id="task-caption",
            timestamp="2026-08-11T10:00:02+00:00",
            success=False,
            retry_count=2,
            retry_exhausted=True,
            exception_type="RuntimeError",
            metadata={"status": "failed", "error": "secret failure body"},
        ),
        _event(
            event_id="evt-finish",
            operation="workflow.finished",
            run_id="run-1",
            timestamp="2026-08-11T10:00:03+00:00",
            success=False,
            duration_seconds=3.0,
            metadata={
                "status": "failed",
                "finished_at": "2026-08-11T10:00:03+00:00",
            },
        ),
        _event(
            event_id="evt-review",
            operation="review.decision_recorded",
            run_id="run-1",
            timestamp="2026-08-11T10:00:04+00:00",
            metadata={
                "schema_version": "1",
                "record_id": "record-1",
                "decision_id": "decision-1",
                "action": "recorded",
                "state": "rejected",
                "policy_name": "policy-a",
                "artifact_id": "art-1",
                "content_hash": "sha256-1",
                "actor": "private-user",
                "comments": "private comment",
            },
        ),
    )

    result = ObservabilityQuery(engine).get_run(
        "run-1",
        output_directory=output,
    )

    assert result.success
    snapshot = result.data
    assert isinstance(snapshot, RunDiagnosticSnapshot)
    assert snapshot.project_id == "project-a"
    assert snapshot.workflow_id == "workflow-a"
    assert snapshot.status == "failed"
    assert snapshot.duration_seconds == 3.0
    assert snapshot.events_total == 5
    assert snapshot.failed_events == 2
    assert snapshot.retry_count == 2
    assert snapshot.exhausted_tasks == 1
    assert snapshot.total_tokens == 120
    assert snapshot.estimated_cost == 0.25
    assert snapshot.providers == ["fake-media"]
    assert snapshot.capabilities == ["video.generate"]
    assert snapshot.artifacts == [
        {
            "artifact_id": "art-1",
            "content_hash": "sha256-1",
            "artifact_type": "video",
        }
    ]
    assert snapshot.review["decision_id"] == "decision-1"
    assert "actor" not in snapshot.review
    assert "comments" not in snapshot.review
    assert snapshot.failures[0]["exception_type"] == "RuntimeError"

    rendered = str(snapshot.to_dict())
    assert "do-not-surface" not in rendered
    assert "sensitive prompt" not in rendered
    assert "C:/secret/output.mp4" not in rendered
    assert "secret failure body" not in rendered
    assert "private-user" not in rendered
    assert "private comment" not in rendered


def test_query_views_are_run_scoped_and_deterministic(tmp_path):
    engine = TelemetryEngine()
    output = tmp_path / "telemetry"
    _persist(
        engine,
        output,
        _event(
            event_id="evt-1",
            operation="adapter.succeeded",
            run_id="run-1",
            timestamp="2026-08-11T10:00:00+00:00",
            provider="provider-a",
            total_tokens=10,
            estimated_cost=0.10,
            metadata={
                "capability": "image.generate",
                "artifact_refs": [{"artifact_id": "art-1"}],
            },
        ),
        _event(
            event_id="evt-2",
            operation="review.decision_recorded",
            run_id="run-1",
            timestamp="2026-08-11T10:00:01+00:00",
            metadata={
                "decision_id": "decision-1",
                "action": "recorded",
                "state": "approved",
            },
        ),
        _event(
            event_id="evt-other",
            operation="task.failed",
            run_id="run-2",
            timestamp="2026-08-11T10:00:02+00:00",
            success=False,
            exception_type="ValueError",
        ),
    )
    query = ObservabilityQuery(engine)

    timeline = query.timeline("run-1", output_directory=output)
    artifacts = query.artifacts("run-1", output_directory=output)
    review = query.review("run-1", output_directory=output)
    failures = query.failures("run-1", output_directory=output)
    cost = query.cost("run-1", output_directory=output)

    assert [item["event_id"] for item in timeline.data] == ["evt-1", "evt-2"]
    assert artifacts.data == [{"artifact_id": "art-1"}]
    assert review.data["decision_id"] == "decision-1"
    assert failures.data == []
    assert cost.data == {
        "run_id": "run-1",
        "total_tokens": 10,
        "estimated_cost": 0.1,
        "currencies": ["USD"],
    }


def test_missing_run_and_empty_run_id_return_engine_failures(tmp_path):
    engine = TelemetryEngine()
    query = ObservabilityQuery(engine)
    output = tmp_path / "telemetry"

    empty = query.get_run("", output_directory=output)
    missing = query.get_run("run-missing", output_directory=output)

    assert not empty.success
    assert empty.metadata["component"] == "observability_query"
    assert not missing.success
    assert missing.metadata["run_id"] == "run-missing"


def test_conflicting_project_or_workflow_ids_are_not_guessed(tmp_path):
    engine = TelemetryEngine()
    output = tmp_path / "telemetry"
    first = _event(
        event_id="evt-1",
        operation="task.succeeded",
        run_id="run-1",
        timestamp="2026-08-11T10:00:00+00:00",
    )
    second = _event(
        event_id="evt-2",
        operation="task.succeeded",
        run_id="run-1",
        timestamp="2026-08-11T10:00:01+00:00",
    )
    second.project_id = "project-b"
    second.workflow_id = "workflow-b"
    _persist(engine, output, first, second)

    result = ObservabilityQuery(engine).get_run("run-1", output_directory=output)

    assert result.success
    assert result.data.project_id == ""
    assert result.data.workflow_id == ""
    assert len(result.data.warnings) == 2
    assert len(result.warnings) == 2
