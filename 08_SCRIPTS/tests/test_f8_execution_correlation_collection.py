from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import sys


SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from cips_core.agents import AgentDescriptor, AgentRegistry
from cips_core.engine import WorkflowEngine
from cips_core.messages import Message, MessageBus, MessagePriority, MessageType
from cips_core.tasks import TaskDefinition, WorkflowDefinition, WorkflowStatus
from observability_collector import CORE_EXECUTION_TOPICS, ObservabilityCollector
from telemetry_models import TelemetryEvent


class SpyRecorder:
    def __init__(self, *, success: bool = True) -> None:
        self.success = success
        self.calls: list[tuple[TelemetryEvent, dict[str, object]]] = []

    def record_event(self, event: TelemetryEvent, **kwargs: object):
        self.calls.append((event, dict(kwargs)))
        return SimpleNamespace(success=self.success)


class RaisingRecorder:
    def record_event(self, event: TelemetryEvent, **kwargs: object):
        raise RuntimeError("synthetic telemetry outage")


def _engine(message_bus: MessageBus | None = None) -> WorkflowEngine:
    registry = AgentRegistry()
    registry.register(
        AgentDescriptor(
            name="SyntheticAgent",
            handler=lambda payload: {"task_id": payload["task_id"]},
            capabilities={"synthetic.capability"},
        )
    )
    return WorkflowEngine(registry, message_bus=message_bus)


def _workflow() -> WorkflowDefinition:
    return WorkflowDefinition(
        name="F8.2 synthetic workflow",
        workflow_id="workflow-f82",
        tasks=[
            TaskDefinition(
                name="Synthetic task",
                capability="synthetic.capability",
                task_id="task-f82",
            )
        ],
    )


def test_core_messages_propagate_canonical_execution_correlation() -> None:
    bus = MessageBus()
    result = _engine(bus).run(_workflow(), project_id="project-f82")

    assert result.status is WorkflowStatus.SUCCEEDED
    messages = bus.history()
    assert [message.topic for message in messages] == [
        "workflow.started",
        "task.started",
        "task.succeeded",
        "workflow.finished",
    ]
    assert all(message.correlation_id == result.run_id for message in messages)
    assert all(message.payload["project_id"] == "project-f82" for message in messages)
    assert all(message.payload["workflow_id"] == "workflow-f82" for message in messages)
    assert all(message.payload["run_id"] == result.run_id for message in messages)
    assert messages[1].payload["task_id"] == "task-f82"
    assert messages[2].payload["task_id"] == "task-f82"


def test_collector_maps_core_messages_to_correlated_telemetry(tmp_path: Path) -> None:
    bus = MessageBus()
    recorder = SpyRecorder()
    collector = ObservabilityCollector(bus, recorder, output_directory=tmp_path)

    result = _engine(bus).run(_workflow(), project_id="project-f82")

    assert collector.collected_count == 4
    assert collector.failure_count == 0
    assert len(recorder.calls) == 4
    events = [call[0] for call in recorder.calls]
    assert [event.operation for event in events] == [
        "workflow.started",
        "task.started",
        "task.succeeded",
        "workflow.finished",
    ]
    assert all(event.project_id == "project-f82" for event in events)
    assert all(event.component == "workflow_engine" for event in events)
    assert all(event.workflow_id == "workflow-f82" for event in events)
    assert all(event.run_id == result.run_id for event in events)
    assert all(event.correlation_id == result.run_id for event in events)
    assert events[1].task_id == "task-f82"
    assert events[2].task_id == "task-f82"
    assert all(call[1]["output_directory"] == tmp_path for call in recorder.calls)
    assert all(call[1]["update_summary"] is True for call in recorder.calls)


def test_collector_uses_allowlisted_metadata_and_does_not_copy_error_payload(tmp_path: Path) -> None:
    bus = MessageBus()
    recorder = SpyRecorder()
    ObservabilityCollector(bus, recorder, output_directory=tmp_path)
    bus.publish(
        Message(
            topic="task.failed",
            payload={
                "project_id": "project-f82",
                "workflow_id": "workflow-f82",
                "run_id": "run-f82",
                "task_id": "task-f82",
                "error": "api_token=must-not-be-persisted",
                "metrics": {"prompt": "must-not-be-persisted"},
                "attempt": 2,
            },
            message_type=MessageType.ERROR,
            priority=MessagePriority.HIGH,
            source="SyntheticAgent",
            correlation_id="run-f82",
        )
    )

    event = recorder.calls[0][0]
    serialized = str(event.to_dict())
    assert event.success is False
    assert event.metadata["attempt"] == 2
    assert "must-not-be-persisted" not in serialized
    assert "api_token" not in serialized
    assert "metrics" not in event.metadata
    assert "error" not in event.metadata


def test_observability_failure_does_not_fail_workflow(tmp_path: Path) -> None:
    bus = MessageBus()
    collector = ObservabilityCollector(bus, RaisingRecorder(), output_directory=tmp_path)

    result = _engine(bus).run(_workflow(), project_id="project-f82")

    assert result.status is WorkflowStatus.SUCCEEDED
    assert result.succeeded is True
    assert collector.collected_count == 0
    assert collector.failure_count == 4
    assert collector.last_failure_type == "RuntimeError"


def test_unsuccessful_recorder_result_is_fail_open(tmp_path: Path) -> None:
    bus = MessageBus()
    collector = ObservabilityCollector(
        bus,
        SpyRecorder(success=False),
        output_directory=tmp_path,
    )

    result = _engine(bus).run(_workflow(), project_id="project-f82")

    assert result.succeeded is True
    assert collector.collected_count == 0
    assert collector.failure_count == 4
    assert collector.last_failure_type == "record_failed"


def test_subscription_is_idempotent_and_scope_is_core_execution_only(tmp_path: Path) -> None:
    bus = MessageBus()
    recorder = SpyRecorder()
    collector = ObservabilityCollector(bus, recorder, output_directory=tmp_path)
    collector.subscribe()
    collector.subscribe()

    bus.publish(
        Message(
            "workflow.started",
            {"project_id": "p", "workflow_id": "w", "run_id": "r"},
            correlation_id="r",
        )
    )
    bus.publish(
        Message(
            "review.decision_recorded",
            {"project_id": "p", "workflow_id": "w", "run_id": "r"},
            message_type=MessageType.AUDIT,
            correlation_id="r",
        )
    )

    assert CORE_EXECUTION_TOPICS == (
        "workflow.started",
        "workflow.finished",
        "task.started",
        "task.succeeded",
        "task.failed",
        "adapter.succeeded",
    )
    assert len(recorder.calls) == 1
    assert collector.collected_count == 1


def test_failed_execution_remains_correlated_without_persisting_raw_error(tmp_path: Path) -> None:
    bus = MessageBus()
    recorder = SpyRecorder()
    collector = ObservabilityCollector(bus, recorder, output_directory=tmp_path)
    registry = AgentRegistry()

    def failing_handler(payload):
        raise RuntimeError("api_token=must-not-be-persisted")

    registry.register(
        AgentDescriptor(
            name="FailingAgent",
            handler=failing_handler,
            capabilities={"synthetic.capability"},
        )
    )
    engine = WorkflowEngine(registry, message_bus=bus)

    result = engine.run(_workflow(), project_id="project-f82")

    assert result.status is WorkflowStatus.FAILED
    assert collector.collected_count == 4
    events = [call[0] for call in recorder.calls]
    assert [event.operation for event in events] == [
        "workflow.started",
        "task.started",
        "task.failed",
        "workflow.finished",
    ]
    assert all(event.correlation_id == result.run_id for event in events)
    assert events[2].success is False
    assert events[3].success is False
    assert "must-not-be-persisted" not in str([event.to_dict() for event in events])
