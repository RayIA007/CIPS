from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import sys


SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import cips_core.engine as engine_module
from cips_core.agents import AgentDescriptor, AgentRegistry
from cips_core.engine import WorkflowEngine
from cips_core.messages import Message, MessageBus, MessageType
from cips_core.tasks import RetryPolicy, TaskDefinition, WorkflowDefinition, WorkflowStatus
from observability_collector import ObservabilityCollector
from telemetry_models import TelemetryEvent, TelemetrySummary


class SpyRecorder:
    def __init__(self) -> None:
        self.calls: list[TelemetryEvent] = []

    def record_event(self, event: TelemetryEvent, **kwargs: object):
        self.calls.append(event)
        return SimpleNamespace(success=True)


def _clock(monkeypatch, *timestamps: str) -> None:
    values = iter(timestamps)
    monkeypatch.setattr(engine_module, "utc_now_iso", lambda: next(values))


def _engine(handler, *, bus: MessageBus | None = None) -> WorkflowEngine:
    registry = AgentRegistry()
    registry.register(
        AgentDescriptor(
            name="RuntimeAgent",
            handler=handler,
            capabilities={"runtime.observe"},
        )
    )
    return WorkflowEngine(registry, message_bus=bus)


def _workflow(*, max_attempts: int = 1) -> WorkflowDefinition:
    return WorkflowDefinition(
        name="F8.3 runtime workflow",
        workflow_id="workflow-f83",
        tasks=[
            TaskDefinition(
                name="Runtime task",
                capability="runtime.observe",
                task_id="task-f83",
                retry_policy=RetryPolicy(max_attempts=max_attempts),
            )
        ],
    )


def _events(recorder: SpyRecorder) -> dict[str, TelemetryEvent]:
    return {event.operation: event for event in recorder.calls}


def test_successful_runtime_maps_task_and_workflow_timing(monkeypatch, tmp_path: Path) -> None:
    _clock(
        monkeypatch,
        "2026-08-11T18:00:00+00:00",
        "2026-08-11T18:00:01+00:00",
        "2026-08-11T18:00:03.500000+00:00",
        "2026-08-11T18:00:05+00:00",
    )
    bus = MessageBus()
    recorder = SpyRecorder()
    ObservabilityCollector(bus, recorder, output_directory=tmp_path)

    result = _engine(lambda payload: {"ok": True}, bus=bus).run(
        _workflow(), project_id="project-f83"
    )

    assert result.status is WorkflowStatus.SUCCEEDED
    events = _events(recorder)
    task_event = events["task.succeeded"]
    workflow_event = events["workflow.finished"]

    assert task_event.duration_seconds == 2.5
    assert task_event.retry_enabled is False
    assert task_event.retry_attempts == 1
    assert task_event.retry_count == 0
    assert task_event.metadata["status"] == "succeeded"
    assert task_event.metadata["started_at"] == "2026-08-11T18:00:01+00:00"
    assert task_event.metadata["finished_at"] == "2026-08-11T18:00:03.500000+00:00"

    assert workflow_event.duration_seconds == 5.0
    assert workflow_event.metadata["status"] == "succeeded"
    assert workflow_event.correlation_id == result.run_id


def test_success_after_retry_maps_retry_metrics(monkeypatch, tmp_path: Path) -> None:
    _clock(
        monkeypatch,
        "2026-08-11T19:00:00+00:00",
        "2026-08-11T19:00:01+00:00",
        "2026-08-11T19:00:04+00:00",
        "2026-08-11T19:00:05+00:00",
    )
    attempts = {"count": 0}

    def flaky_handler(payload):
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise RuntimeError("temporary synthetic failure")
        return {"ok": True}

    bus = MessageBus()
    recorder = SpyRecorder()
    ObservabilityCollector(bus, recorder, output_directory=tmp_path)

    result = _engine(flaky_handler, bus=bus).run(
        _workflow(max_attempts=3), project_id="project-f83"
    )

    assert result.succeeded is True
    event = _events(recorder)["task.succeeded"]
    assert event.duration_seconds == 3.0
    assert event.retry_enabled is True
    assert event.retry_attempts == 2
    assert event.retry_count == 1
    assert event.retry_exhausted is False
    assert event.succeeded_after_retry is True
    assert event.exception_type == ""

    summary = TelemetrySummary(scope="run", scope_id=result.run_id)
    for item in recorder.calls:
        summary.register_event(item)
    assert summary.retry_attempts == 2
    assert summary.retry_count == 1
    assert summary.recovered_events == 1


def test_failed_runtime_maps_exception_type_without_persisting_error_message(
    monkeypatch, tmp_path: Path
) -> None:
    _clock(
        monkeypatch,
        "2026-08-11T20:00:00+00:00",
        "2026-08-11T20:00:01+00:00",
        "2026-08-11T20:00:06+00:00",
        "2026-08-11T20:00:07+00:00",
    )

    def failing_handler(payload):
        raise RuntimeError("api_token=must-not-be-persisted")

    bus = MessageBus()
    recorder = SpyRecorder()
    ObservabilityCollector(bus, recorder, output_directory=tmp_path)

    result = _engine(failing_handler, bus=bus).run(
        _workflow(max_attempts=2), project_id="project-f83"
    )

    assert result.status is WorkflowStatus.FAILED
    event = _events(recorder)["task.failed"]
    serialized = str(event.to_dict())

    assert event.success is False
    assert event.duration_seconds == 5.0
    assert event.retry_enabled is True
    assert event.retry_attempts == 2
    assert event.retry_count == 1
    assert event.retry_exhausted is True
    assert event.succeeded_after_retry is False
    assert event.exception_type == "RuntimeError"
    assert "must-not-be-persisted" not in serialized
    assert "api_token" not in serialized
    assert "error" not in event.metadata

    summary = TelemetrySummary(scope="run", scope_id=result.run_id)
    summary.register_event(event)
    assert summary.failed_events == 1
    assert summary.exhausted_events == 1
    assert summary.exception_types == {"RuntimeError": 1}


def test_adapter_duration_ms_maps_to_telemetry_seconds(tmp_path: Path) -> None:
    bus = MessageBus()
    recorder = SpyRecorder()
    ObservabilityCollector(bus, recorder, output_directory=tmp_path)

    bus.publish(
        Message(
            topic="adapter.succeeded",
            payload={
                "project_id": "project-f83",
                "workflow_id": "workflow-f83",
                "run_id": "run-f83",
                "task_id": "task-f83",
                "adapter": "SyntheticAdapter",
                "result_id": "result-f83",
                "status": "succeeded",
                "duration_ms": 1250,
                "metrics": {"prompt": "must-not-be-persisted"},
            },
            message_type=MessageType.RESULT,
            source="SyntheticAdapter",
            correlation_id="run-f83",
        )
    )

    event = recorder.calls[0]
    assert event.duration_seconds == 1.25
    assert event.metadata["adapter"] == "SyntheticAdapter"
    assert event.metadata["status"] == "succeeded"
    assert "metrics" not in event.metadata
    assert "must-not-be-persisted" not in str(event.to_dict())


def test_invalid_or_reversed_timing_is_safe_and_non_negative(tmp_path: Path) -> None:
    bus = MessageBus()
    recorder = SpyRecorder()
    collector = ObservabilityCollector(bus, recorder, output_directory=tmp_path)

    invalid = collector._to_event(
        Message(
            topic="task.succeeded",
            payload={
                "project_id": "p",
                "workflow_id": "w",
                "run_id": "r",
                "task_id": "t",
                "started_at": "not-a-date",
                "finished_at": "also-not-a-date",
                "attempts": 1,
                "max_attempts": 1,
            },
            message_type=MessageType.RESULT,
            correlation_id="r",
        )
    )
    reversed_event = collector._to_event(
        Message(
            topic="task.succeeded",
            payload={
                "project_id": "p",
                "workflow_id": "w",
                "run_id": "r",
                "task_id": "t",
                "started_at": "2026-08-11T21:00:05+00:00",
                "finished_at": "2026-08-11T21:00:01+00:00",
                "attempts": 1,
                "max_attempts": 1,
            },
            message_type=MessageType.RESULT,
            correlation_id="r",
        )
    )

    mixed_timezone = collector._to_event(
        Message(
            topic="task.succeeded",
            payload={
                "project_id": "p",
                "workflow_id": "w",
                "run_id": "r",
                "task_id": "t",
                "started_at": "2026-08-11T21:00:01",
                "finished_at": "2026-08-11T21:00:05+00:00",
                "attempts": 1,
                "max_attempts": 1,
            },
            message_type=MessageType.RESULT,
            correlation_id="r",
        )
    )

    assert invalid.duration_seconds == 0.0
    assert reversed_event.duration_seconds == 0.0
    assert mixed_timezone.duration_seconds == 0.0
