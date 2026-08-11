from __future__ import annotations
from pathlib import Path
import sys
import pytest
from pydantic import ValidationError

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from final_review import (
    ManualReviewPolicy,
    ReviewAction,
    ReviewArtifactRef,
    ReviewDecision,
    ReviewExportBlockedError,
    ReviewExportBoundary,
    ReviewExportBoundaryError,
    ReviewGateway,
    ReviewState,
    ReviewTarget,
    execute_after_review,
)

def target() -> ReviewTarget:
    return ReviewTarget(
        project_id="project-f74",
        workflow_id="workflow-f74",
        run_id="run-f74",
        artifacts=(
            ReviewArtifactRef(
                artifact_id="artifact-final",
                content_hash="a" * 64,
                task_id="final",
                role="final_video",
            ),
        ),
    )

def decision(action: ReviewAction, *, redo_target: str | None = None) -> ReviewDecision:
    return ReviewDecision(
        decision_id=f"decision-{action.value}",
        action=action,
        actor="reviewer:f74",
        decided_at="2026-08-10T22:55:00-06:00",
        redo_target=redo_target,
    )

def review(action: ReviewAction, *, redo_target: str | None = None):
    return ReviewGateway().present(
        target(),
        policy=ManualReviewPolicy(),
        decision=decision(action, redo_target=redo_target),
    )

def test_approved_review_authorizes_export_with_logical_audit_identity() -> None:
    result = review(ReviewAction.APPROVE)
    authorization = ReviewExportBoundary().authorize(result)
    assert authorization.project_id == "project-f74"
    assert authorization.workflow_id == "workflow-f74"
    assert authorization.run_id == "run-f74"
    assert authorization.decision_id == "decision-approve"
    assert authorization.policy_name == "manual"
    assert authorization.review_state is ReviewState.APPROVED
    assert authorization.actor == "reviewer:f74"

def test_approved_review_executes_export_operation_exactly_once_and_preserves_result() -> None:
    calls: list[str] = []
    expected = {"success": True, "component": "fake_export_engine"}
    def export_operation():
        calls.append("export")
        return expected
    actual = ReviewExportBoundary().execute(review(ReviewAction.APPROVE), export_operation)
    assert actual is expected
    assert calls == ["export"]

def test_request_changes_blocks_export_without_calling_operation() -> None:
    calls: list[str] = []
    with pytest.raises(ReviewExportBlockedError) as exc_info:
        ReviewExportBoundary().execute(
            review(ReviewAction.REQUEST_CHANGES, redo_target="guion"),
            lambda: calls.append("export"),
        )
    error = exc_info.value
    assert calls == []
    assert error.state == "changes_requested"
    assert error.decision_id == "decision-request_changes"
    assert error.redo_target == "guion"

def test_cancelled_review_blocks_export_without_calling_operation() -> None:
    calls: list[str] = []
    with pytest.raises(ReviewExportBlockedError) as exc_info:
        ReviewExportBoundary().execute(
            review(ReviewAction.CANCEL),
            lambda: calls.append("export"),
        )
    assert calls == []
    assert exc_info.value.state == "cancelled"
    assert exc_info.value.redo_target is None

def test_blocked_export_does_not_mutate_review_result() -> None:
    review_result = review(ReviewAction.REQUEST_CHANGES, redo_target="final")
    before = review_result.model_dump()
    with pytest.raises(ReviewExportBlockedError):
        ReviewExportBoundary().execute(review_result, lambda: None)
    assert review_result.model_dump() == before

def test_boundary_does_not_swallow_export_failure() -> None:
    class ExportFailure(RuntimeError):
        pass
    def failing_export():
        raise ExportFailure("export engine failed")
    with pytest.raises(ExportFailure, match="export engine failed"):
        ReviewExportBoundary().execute(review(ReviewAction.APPROVE), failing_export)

def test_boundary_rejects_non_gateway_result() -> None:
    with pytest.raises(ReviewExportBoundaryError, match="ReviewGatewayResult"):
        ReviewExportBoundary().authorize(object())

def test_boundary_rejects_non_callable_export_operation() -> None:
    with pytest.raises(ReviewExportBoundaryError, match="callable"):
        ReviewExportBoundary().execute(review(ReviewAction.APPROVE), None)

def test_convenience_facade_uses_same_approval_gate() -> None:
    calls: list[str] = []
    result = execute_after_review(
        review(ReviewAction.APPROVE),
        lambda: calls.append("export") or "exported",
    )
    assert result == "exported"
    assert calls == ["export"]

def test_convenience_facade_blocks_non_approved_review() -> None:
    calls: list[str] = []
    with pytest.raises(ReviewExportBlockedError):
        execute_after_review(
            review(ReviewAction.CANCEL),
            lambda: calls.append("export"),
        )
    assert calls == []


def test_authorization_is_frozen_and_json_serializable() -> None:
    authorization = ReviewExportBoundary().authorize(review(ReviewAction.APPROVE))
    restored = type(authorization).model_validate_json(authorization.model_dump_json())
    assert restored == authorization
    with pytest.raises(ValidationError):
        authorization.policy_name = "mutated"


def test_authorization_contains_no_artifact_or_filesystem_payload() -> None:
    authorization = ReviewExportBoundary().authorize(review(ReviewAction.APPROVE))
    payload = authorization.model_dump()
    assert "artifacts" not in payload
    assert "path" not in payload
    assert "sidecar_path" not in payload
