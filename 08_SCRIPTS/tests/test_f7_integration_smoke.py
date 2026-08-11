from __future__ import annotations

from pathlib import Path
import sys


SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from cips_core.context import ExecutionContext
from cips_core.engine import WorkflowResult
from cips_core.messages import MessageBus, MessageType
from cips_core.tasks import TaskResult, TaskStatus, WorkflowStatus
from final_review import (
    REVIEW_AUDIT_TOPIC,
    AutoApproveReviewPolicy,
    ReviewExportBoundary,
    ReviewGateway,
    ReviewState,
    build_review_target,
    persist_review_result,
)
from metadata_store import MetadataStore
from workspace_resolver import WorkspaceResolver


def test_f7_final_review_end_to_end_from_f6_result_to_audited_export(
    tmp_path: Path,
) -> None:
    """Exercise F7.1-F7.5 over an F6/Core-compatible result without real providers."""

    preview_artifact = {
        "artifact_id": "f7-smoke-preview",
        "content_hash": "a" * 64,
        "role": "preview_video",
        "media_type": "video",
        "mime_type": "video/mp4",
        "path": str(tmp_path / "physical" / "preview.mp4"),
        "sidecar_path": str(tmp_path / "physical" / "preview.mp4.meta.json"),
        "metadata": {"render_profile": "preview", "workspace_root": str(tmp_path)},
    }
    final_artifact = {
        "artifact_id": "f7-smoke-final",
        "content_hash": "b" * 64,
        "role": "final_video",
        "media_type": "video",
        "mime_type": "video/mp4",
        "path": str(tmp_path / "physical" / "final.mp4"),
        "sidecar_path": str(tmp_path / "physical" / "final.mp4.meta.json"),
        "metadata": {"render_profile": "final", "workspace_root": str(tmp_path)},
    }

    context = ExecutionContext(
        project_id="f7-smoke-project",
        workflow_id="f7-smoke-workflow",
        run_id="f7-smoke-run",
        metadata={"source": "f7.6-integration-smoke"},
    )
    context.set_output("preview", {"render_profile": "preview"})
    context.set_output("final", {"render_profile": "final"})
    context.set_artifacts("preview", (preview_artifact,))
    context.set_artifacts("final", (final_artifact,))

    result = WorkflowResult(
        workflow_id=context.workflow_id,
        run_id=context.run_id,
        status=WorkflowStatus.SUCCEEDED,
        context=context,
        task_results={
            "preview": TaskResult(
                task_id="preview",
                status=TaskStatus.SUCCEEDED,
                attempts=1,
                output=context.task_outputs["preview"],
                artifacts=(preview_artifact,),
            ),
            "final": TaskResult(
                task_id="final",
                status=TaskStatus.SUCCEEDED,
                attempts=1,
                output=context.task_outputs["final"],
                artifacts=(final_artifact,),
            ),
        },
        started_at="2026-08-11T18:00:00+00:00",
        finished_at="2026-08-11T18:01:00+00:00",
    )

    target = build_review_target(result, task_ids=("final",))
    assert target.project_id == result.context.project_id
    assert target.workflow_id == result.workflow_id
    assert target.run_id == result.run_id
    assert target.metadata["selected_task_ids"] == ["final"]
    assert [artifact.artifact_id for artifact in target.artifacts] == ["f7-smoke-final"]
    assert "path" not in target.artifacts[0].metadata
    assert "sidecar_path" not in target.artifacts[0].metadata
    assert "workspace_root" not in target.artifacts[0].metadata

    review_result = ReviewGateway().present(
        target,
        policy=AutoApproveReviewPolicy(
            clock=lambda: "2026-08-11T18:02:00+00:00",
        ),
    )
    assert result.status is WorkflowStatus.SUCCEEDED
    assert review_result.previous_state is ReviewState.READY_FOR_REVIEW
    assert review_result.state is ReviewState.APPROVED
    assert review_result.approved is True

    resolver = WorkspaceResolver(
        projects_root=tmp_path / "04_PROYECTOS",
        outputs_root=tmp_path / "05_OUTPUTS",
    )
    workspace = resolver.resolve_execution_workspace(
        "f7-smoke",
        result.run_id,
        create=True,
    )
    message_bus = MessageBus()
    persisted = persist_review_result(
        review_result,
        metadata_store=MetadataStore(resolver),
        workspace_root=workspace,
        message_bus=message_bus,
    )

    assert persisted.record.state is ReviewState.APPROVED
    assert persisted.record.workflow_id == result.workflow_id
    assert persisted.record.run_id == result.run_id
    assert [artifact.artifact_id for artifact in persisted.record.artifacts] == [
        "f7-smoke-final"
    ]
    assert persisted.event_created is True
    assert persisted.audit_event_published is True
    [audit_event] = message_bus.history()
    assert audit_event.topic == REVIEW_AUDIT_TOPIC
    assert audit_event.message_type is MessageType.AUDIT
    assert audit_event.payload["decision_id"] == review_result.decision.decision_id

    export_calls: list[str] = []

    def fake_export():
        export_calls.append(review_result.decision.decision_id)
        return {
            "exported": True,
            "artifact_ids": [artifact.artifact_id for artifact in target.artifacts],
        }

    export_result = ReviewExportBoundary().execute(review_result, fake_export)

    assert export_calls == [review_result.decision.decision_id]
    assert export_result == {
        "exported": True,
        "artifact_ids": ["f7-smoke-final"],
    }
    assert result.status is WorkflowStatus.SUCCEEDED
    assert review_result.state is ReviewState.APPROVED
