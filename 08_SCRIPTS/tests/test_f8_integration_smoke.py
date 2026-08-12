from __future__ import annotations

from pathlib import Path
import sys


SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from cips_core.messages import Message, MessageBus, MessageType
from observability_collector import ObservabilityCollector
from observability_query import ObservabilityQuery, RunDiagnosticSnapshot
from telemetry_engine import TelemetryEngine


def test_f8_observability_end_to_end_from_bus_to_diagnostic_snapshot(
    tmp_path: Path,
) -> None:
    """Exercise F8.1-F8.5 end-to-end without real providers or external services."""
    project_id = "f8-smoke-project"
    workflow_id = "f8-smoke-workflow"
    run_id = "f8-smoke-run"
    output_directory = tmp_path / "telemetry"

    bus = MessageBus()
    telemetry = TelemetryEngine()
    collector = ObservabilityCollector(
        bus,
        telemetry,
        output_directory=output_directory,
        update_summary=False,
    )

    def publish(
        topic: str,
        payload: dict,
        *,
        message_type: MessageType,
        created_at: str,
        source: str = "WorkflowEngine",
    ) -> None:
        bus.publish(
            Message(
                topic=topic,
                payload={
                    "project_id": project_id,
                    "workflow_id": workflow_id,
                    "run_id": run_id,
                    **payload,
                },
                message_type=message_type,
                source=source,
                correlation_id=run_id,
                created_at=created_at,
            )
        )

    publish(
        "workflow.started",
        {
            "status": "running",
            "started_at": "2026-08-12T15:00:00+00:00",
        },
        message_type=MessageType.EVENT,
        created_at="2026-08-12T15:00:00+00:00",
    )
    publish(
        "task.started",
        {
            "task_id": "render",
            "status": "running",
            "max_attempts": 3,
            "started_at": "2026-08-12T15:00:01+00:00",
        },
        message_type=MessageType.EVENT,
        created_at="2026-08-12T15:00:01+00:00",
    )
    publish(
        "adapter.succeeded",
        {
            "task_id": "render",
            "status": "succeeded",
            "capability": "video_rendering",
            "adapter": "VideoMediaAdapter",
            "result_id": "result-f8-smoke",
            "duration_ms": 1250,
            "metrics": {
                "provider": "Fake-Media",
                "prompt": "sensitive provider prompt",
            },
            "artifacts": [
                {
                    "artifact_id": "artifact-f8-smoke",
                    "content_hash": "a" * 64,
                    "artifact_type": "video",
                    "path": "C:/secret/render.mp4",
                    "sidecar_path": "C:/secret/render.mp4.meta.json",
                    "metadata": {"prompt": "sensitive artifact prompt"},
                }
            ],
        },
        message_type=MessageType.RESULT,
        created_at="2026-08-12T15:00:02+00:00",
        source="VideoMediaAdapter",
    )
    publish(
        "task.succeeded",
        {
            "task_id": "render",
            "status": "succeeded",
            "attempts": 2,
            "max_attempts": 3,
            "started_at": "2026-08-12T15:00:01+00:00",
            "finished_at": "2026-08-12T15:00:04+00:00",
        },
        message_type=MessageType.RESULT,
        created_at="2026-08-12T15:00:04+00:00",
    )
    publish(
        "task.started",
        {
            "task_id": "quality_gate",
            "status": "running",
            "max_attempts": 3,
            "started_at": "2026-08-12T15:00:04+00:00",
        },
        message_type=MessageType.EVENT,
        created_at="2026-08-12T15:00:04+00:00",
    )
    publish(
        "task.failed",
        {
            "task_id": "quality_gate",
            "status": "failed",
            "attempts": 3,
            "max_attempts": 3,
            "started_at": "2026-08-12T15:00:04+00:00",
            "finished_at": "2026-08-12T15:00:06+00:00",
            "exception_type": "RuntimeError",
            "error": "api_token=must-not-be-persisted",
        },
        message_type=MessageType.ERROR,
        created_at="2026-08-12T15:00:06+00:00",
    )
    publish(
        "workflow.finished",
        {
            "status": "failed",
            "started_at": "2026-08-12T15:00:00+00:00",
            "finished_at": "2026-08-12T15:00:07+00:00",
        },
        message_type=MessageType.RESULT,
        created_at="2026-08-12T15:00:07+00:00",
    )
    publish(
        "review.decision_recorded",
        {
            "schema_version": "1",
            "record_id": "review-record-f8-smoke",
            "decision_id": "decision-f8-smoke",
            "action": "recorded",
            "state": "rejected",
            "policy_name": "SyntheticReviewPolicy",
            "artifact_id": "artifact-f8-smoke",
            "content_hash": "a" * 64,
            "actor": "private-reviewer",
            "comments": "private review comment",
        },
        message_type=MessageType.AUDIT,
        created_at="2026-08-12T15:00:08+00:00",
        source="ReviewAuditRecorder",
    )

    assert collector.collected_count == 8
    assert collector.failure_count == 0
    assert (output_directory / TelemetryEngine.EVENTS_FILENAME).is_file()

    persisted = telemetry.read_events(
        output_directory=output_directory,
        run_id=run_id,
    )
    assert persisted.success
    assert len(persisted.data) == 8
    assert all(event.run_id == run_id for event in persisted.data)
    assert all(event.correlation_id == run_id for event in persisted.data)

    query = ObservabilityQuery(telemetry)
    result = query.get_run(run_id, output_directory=output_directory)
    assert result.success
    snapshot = result.data
    assert isinstance(snapshot, RunDiagnosticSnapshot)
    assert snapshot.project_id == project_id
    assert snapshot.workflow_id == workflow_id
    assert snapshot.run_id == run_id
    assert snapshot.status == "failed"
    assert snapshot.started_at == "2026-08-12T15:00:00+00:00"
    assert snapshot.finished_at == "2026-08-12T15:00:07+00:00"
    assert snapshot.duration_seconds == 7.0
    assert snapshot.events_total == 8
    assert snapshot.failed_events == 1
    assert snapshot.retry_count == 3
    assert snapshot.recovered_tasks == 1
    assert snapshot.exhausted_tasks == 1
    assert snapshot.providers == ["fake-media"]
    assert snapshot.capabilities == ["video_rendering"]
    assert snapshot.artifacts == [
        {
            "artifact_id": "artifact-f8-smoke",
            "content_hash": "a" * 64,
            "artifact_type": "video",
        }
    ]
    assert snapshot.review["decision_id"] == "decision-f8-smoke"
    assert snapshot.review["state"] == "rejected"
    assert len(snapshot.failures) == 1
    assert snapshot.failures[0]["operation"] == "task.failed"
    assert snapshot.failures[0]["task_id"] == "quality_gate"
    assert snapshot.failures[0]["exception_type"] == "RuntimeError"
    assert [entry["operation"] for entry in snapshot.timeline] == [
        "workflow.started",
        "task.started",
        "adapter.succeeded",
        "task.succeeded",
        "task.started",
        "task.failed",
        "workflow.finished",
        "review.decision_recorded",
    ]

    telemetry_text = (output_directory / TelemetryEngine.EVENTS_FILENAME).read_text(encoding="utf-8")
    rendered = str(snapshot.to_dict())
    assert "must-not-be-persisted" not in telemetry_text
    assert "sensitive provider prompt" not in telemetry_text
    assert "sensitive artifact prompt" not in telemetry_text
    assert "C:/secret/render.mp4" not in telemetry_text
    assert "private-reviewer" not in telemetry_text
    assert "private review comment" not in telemetry_text
    assert "must-not-be-persisted" not in rendered
    assert "api_token" not in rendered
    assert "sensitive provider prompt" not in rendered
    assert "sensitive artifact prompt" not in rendered
    assert "C:/secret/render.mp4" not in rendered
    assert "sidecar_path" not in rendered
    assert "private-reviewer" not in rendered
    assert "private review comment" not in rendered

    failures = query.failures(run_id, output_directory=output_directory)
    artifacts = query.artifacts(run_id, output_directory=output_directory)
    review = query.review(run_id, output_directory=output_directory)
    assert failures.success and failures.data == snapshot.failures
    assert artifacts.success and artifacts.data == snapshot.artifacts
    assert review.success and review.data == snapshot.review
