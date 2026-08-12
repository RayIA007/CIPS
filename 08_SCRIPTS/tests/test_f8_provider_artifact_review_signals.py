from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import sys


SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from cips_core.agents import AgentDescriptor, AgentRegistry
from cips_core.engine import WorkflowEngine
from cips_core.messages import Message, MessageBus, MessageType
from cips_core.tasks import TaskDefinition, WorkflowDefinition
from observability_collector import ObservabilityCollector, REVIEW_AUDIT_TOPICS
from telemetry_models import TelemetryEvent


class SpyRecorder:
    def __init__(self) -> None:
        self.calls: list[TelemetryEvent] = []

    def record_event(self, event: TelemetryEvent, **kwargs: object):
        self.calls.append(event)
        return SimpleNamespace(success=True)


class SyntheticAdapterResult:
    adapter_name = "ImageMediaAdapter"
    capability = "image_generation"
    result_id = "ares-f84"
    duration_ms = 250.0
    succeeded = True
    error = ""
    output = {"binary": "not-copied-to-telemetry"}
    warnings = ()
    metrics = {
        "provider": " Image_Adapter ",
        "prompt": "api_token=must-not-be-persisted",
    }
    artifacts = (
        {
            "artifact_id": "artifact-f84",
            "content_hash": "sha256-f84",
            "artifact_type": "image",
            "path": "C:/secret/project/image.png",
            "sidecar_path": "C:/secret/project/image.png.meta.json",
            "metadata": {"prompt": "must-not-be-persisted"},
        },
    )
    status = SimpleNamespace(value="succeeded")


def _adapter_engine(bus: MessageBus) -> WorkflowEngine:
    registry = AgentRegistry()
    registry.register(
        AgentDescriptor(
            name="SyntheticMediaAgent",
            handler=lambda payload: SyntheticAdapterResult(),
            capabilities={"image_generation"},
        )
    )
    return WorkflowEngine(registry, message_bus=bus)


def _workflow() -> WorkflowDefinition:
    return WorkflowDefinition(
        name="F8.4 provider/artifact workflow",
        workflow_id="workflow-f84",
        tasks=[
            TaskDefinition(
                name="Generate image",
                capability="image_generation",
                task_id="task-f84",
            )
        ],
    )


def test_adapter_provider_capability_and_artifact_refs_are_correlated_safely(tmp_path: Path) -> None:
    bus = MessageBus()
    recorder = SpyRecorder()
    collector = ObservabilityCollector(bus, recorder, output_directory=tmp_path)

    result = _adapter_engine(bus).run(_workflow(), project_id="project-f84")

    adapter_message = next(m for m in bus.history() if m.topic == "adapter.succeeded")
    assert adapter_message.payload["capability"] == "image_generation"

    event = next(event for event in recorder.calls if event.operation == "adapter.succeeded")
    assert event.project_id == "project-f84"
    assert event.workflow_id == "workflow-f84"
    assert event.run_id == result.run_id
    assert event.task_id == "task-f84"
    assert event.correlation_id == result.run_id
    assert event.provider == "image_adapter"
    assert event.metadata["capability"] == "image_generation"
    assert event.metadata["artifact_count"] == 1
    assert event.metadata["artifact_refs"] == [
        {
            "artifact_id": "artifact-f84",
            "content_hash": "sha256-f84",
            "artifact_type": "image",
        }
    ]
    serialized = str(event.to_dict())
    assert "C:/secret" not in serialized
    assert "must-not-be-persisted" not in serialized
    assert "api_token" not in serialized
    assert "sidecar_path" not in serialized
    assert "metrics" not in event.metadata
    assert collector.failure_count == 0


def test_review_audit_signal_is_collected_without_actor_or_comments(tmp_path: Path) -> None:
    bus = MessageBus()
    recorder = SpyRecorder()
    collector = ObservabilityCollector(bus, recorder, output_directory=tmp_path)

    bus.publish(
        Message(
            topic="review.decision_recorded",
            message_type=MessageType.AUDIT,
            source="final_review.persistence",
            correlation_id="run-f84",
            payload={
                "schema_version": "1.0.0",
                "record_id": "final-review:project-f84:workflow-f84:run-f84:decision-f84",
                "project_id": "project-f84",
                "workflow_id": "workflow-f84",
                "run_id": "run-f84",
                "decision_id": "decision-f84",
                "action": "approve",
                "state": "approved",
                "actor": "must-not-be-persisted@example.test",
                "comments": "private review comments must-not-be-persisted",
                "policy_name": "AutoApproveReviewPolicy",
                "artifact_id": "final-review-artifact-f84",
                "content_hash": "review-hash-f84",
            },
        )
    )

    assert REVIEW_AUDIT_TOPICS == ("review.decision_recorded",)
    assert collector.collected_count == 1
    event = recorder.calls[0]
    assert event.component == "final_review"
    assert event.event_type == "audit"
    assert event.success is True
    assert event.project_id == "project-f84"
    assert event.workflow_id == "workflow-f84"
    assert event.run_id == "run-f84"
    assert event.correlation_id == "run-f84"
    assert event.metadata["decision_id"] == "decision-f84"
    assert event.metadata["action"] == "approve"
    assert event.metadata["state"] == "approved"
    assert event.metadata["policy_name"] == "AutoApproveReviewPolicy"
    assert event.metadata["artifact_id"] == "final-review-artifact-f84"
    assert event.metadata["content_hash"] == "review-hash-f84"
    serialized = str(event.to_dict())
    assert "must-not-be-persisted" not in serialized
    assert "actor" not in event.metadata
    assert "comments" not in event.metadata


def test_incomplete_review_audit_message_remains_ignored_for_backward_compatibility(tmp_path: Path) -> None:
    bus = MessageBus()
    recorder = SpyRecorder()
    collector = ObservabilityCollector(bus, recorder, output_directory=tmp_path)

    bus.publish(
        Message(
            topic="review.decision_recorded",
            payload={"project_id": "p", "workflow_id": "w", "run_id": "r"},
            message_type=MessageType.AUDIT,
            correlation_id="r",
        )
    )

    assert recorder.calls == []
    assert collector.collected_count == 0
    assert collector.failure_count == 0


def test_artifact_reference_filter_ignores_physical_only_or_malformed_entries(tmp_path: Path) -> None:
    event = ObservabilityCollector._to_event(
        Message(
            topic="adapter.succeeded",
            message_type=MessageType.RESULT,
            correlation_id="run-f84",
            payload={
                "project_id": "p",
                "workflow_id": "w",
                "run_id": "run-f84",
                "task_id": "t",
                "artifacts": [
                    {"path": "C:/physical-only.bin"},
                    "not-a-mapping",
                    {"artifact_id": "logical-id", "path": "C:/hidden.bin"},
                ],
            },
        )
    )

    assert event.metadata["artifact_count"] == 1
    assert event.metadata["artifact_refs"] == [{"artifact_id": "logical-id"}]
    assert "C:/" not in str(event.to_dict())
