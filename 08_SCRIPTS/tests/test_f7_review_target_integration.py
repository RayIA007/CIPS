from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys

import pytest


SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from cips_core.context import ExecutionContext
from cips_core.tasks import TaskResult, TaskStatus, WorkflowStatus

from final_review import (
    InconsistentReviewArtifactError,
    ReviewTargetBuildError,
    build_review_target,
)


@dataclass
class FakeWorkflowResult:
    workflow_id: str
    run_id: str
    status: WorkflowStatus
    context: ExecutionContext
    task_results: dict[str, TaskResult]
    started_at: str = "2026-08-10T21:00:00-06:00"
    finished_at: str = "2026-08-10T21:01:00-06:00"


def artifact(artifact_id: str, content_hash: str, *, role: str | None = None) -> dict:
    payload = {
        "artifact_id": artifact_id,
        "content_hash": content_hash,
        "artifact_type": "video",
        "mime_type": "video/mp4",
        "path": f"C:/outputs/{artifact_id}.mp4",
        "sidecar_path": f"C:/outputs/{artifact_id}.mp4.meta.json",
        "metadata": {
            "media_type": "video",
            "relative_path": f"video/{artifact_id}.mp4",
            "requested_relative_path": f"video/{artifact_id}.mp4",
            "sidecar_path": f"C:/outputs/{artifact_id}.mp4.meta.json",
            "provider": "fake-media",
        },
    }
    if role is not None:
        payload["role"] = role
    return payload


def workflow_result(*, status: WorkflowStatus = WorkflowStatus.SUCCEEDED) -> FakeWorkflowResult:
    preview = artifact("artifact-preview", "a" * 64, role="preview_video")
    final = artifact("artifact-final", "b" * 64, role="final_video")
    context = ExecutionContext(
        project_id="project-f72",
        workflow_id="workflow-f72",
        run_id="run-f72",
    )
    context.set_artifacts("preview", (preview,))
    context.set_artifacts("final", (final,))
    return FakeWorkflowResult(
        workflow_id="workflow-f72",
        run_id="run-f72",
        status=status,
        context=context,
        task_results={
            "preview": TaskResult("preview", TaskStatus.SUCCEEDED, artifacts=(preview,)),
            "final": TaskResult("final", TaskStatus.SUCCEEDED, artifacts=(final,)),
        },
    )


def test_builds_review_target_from_f6_shaped_workflow_result() -> None:
    target = build_review_target(workflow_result())

    assert target.project_id == "project-f72"
    assert target.workflow_id == "workflow-f72"
    assert target.run_id == "run-f72"
    assert [item.artifact_id for item in target.artifacts] == [
        "artifact-preview",
        "artifact-final",
    ]
    assert target.metadata["source"] == "f6_workflow_result"
    assert target.metadata["workflow_status"] == "succeeded"
    assert target.metadata["selected_task_ids"] == ["preview", "final"]


def test_explicit_task_selection_does_not_guess_finality_from_task_name() -> None:
    target = build_review_target(workflow_result(), task_ids=("final",))

    assert len(target.artifacts) == 1
    assert target.artifacts[0].artifact_id == "artifact-final"
    assert target.artifacts[0].task_id == "final"
    assert target.artifacts[0].role == "final_video"
    assert target.metadata["selected_task_ids"] == ["final"]


def test_review_artifact_strips_physical_paths_but_keeps_logical_metadata() -> None:
    target = build_review_target(workflow_result(), task_ids=("final",))
    ref = target.artifacts[0]

    assert "path" not in ref.model_dump()
    assert "sidecar_path" not in ref.model_dump()
    assert "relative_path" not in ref.metadata
    assert "requested_relative_path" not in ref.metadata
    assert "sidecar_path" not in ref.metadata
    assert ref.metadata["artifact_type"] == "video"
    assert ref.metadata["mime_type"] == "video/mp4"
    assert ref.metadata["media_type"] == "video"
    assert ref.metadata["provider"] == "fake-media"


def test_rejects_non_succeeded_workflow() -> None:
    with pytest.raises(ReviewTargetBuildError, match="status='succeeded'"):
        build_review_target(workflow_result(status=WorkflowStatus.FAILED))


def test_rejects_selected_task_without_artifacts() -> None:
    result = workflow_result()
    result.task_results["final"].artifacts = ()
    result.context.task_artifacts["final"] = ()

    with pytest.raises(ReviewTargetBuildError, match="no produjo artifacts"):
        build_review_target(result, task_ids=("final",))


def test_rejects_context_identity_mismatch() -> None:
    result = workflow_result()
    changed = dict(result.context.task_artifacts["final"][0])
    changed["artifact_id"] = "artifact-other"
    result.context.task_artifacts["final"] = (changed,)

    with pytest.raises(InconsistentReviewArtifactError, match="difieren"):
        build_review_target(result, task_ids=("final",))


def test_rejects_context_artifact_count_mismatch() -> None:
    result = workflow_result()
    result.context.task_artifacts["final"] = ()

    with pytest.raises(InconsistentReviewArtifactError, match="TaskResult=1"):
        build_review_target(result, task_ids=("final",))


def test_rejects_missing_artifact_id() -> None:
    result = workflow_result()
    broken = dict(result.task_results["final"].artifacts[0])
    broken.pop("artifact_id")
    result.task_results["final"].artifacts = (broken,)
    result.context.task_artifacts["final"] = (dict(broken),)

    with pytest.raises(ReviewTargetBuildError, match="artifact_id"):
        build_review_target(result, task_ids=("final",))


def test_rejects_unknown_or_duplicate_task_selection() -> None:
    result = workflow_result()
    with pytest.raises(ReviewTargetBuildError, match="no existen"):
        build_review_target(result, task_ids=("missing",))
    with pytest.raises(ReviewTargetBuildError, match="duplicados"):
        build_review_target(result, task_ids=("final", "final"))


def test_rejects_workflow_and_context_identity_mismatch() -> None:
    result = workflow_result()
    result.context.run_id = "different-run"

    with pytest.raises(ReviewTargetBuildError, match="run_id"):
        build_review_target(result)


def test_builder_does_not_read_filesystem_or_execute_pipeline() -> None:
    target = build_review_target(workflow_result(), task_ids=("final",))
    assert target.artifacts[0].artifact_id == "artifact-final"
