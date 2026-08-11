from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest
from pydantic import ValidationError


SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from final_review import (
    InvalidReviewTransitionError,
    ReviewAction,
    ReviewArtifactRef,
    ReviewDecision,
    ReviewState,
    ReviewTarget,
    apply_review_decision,
    validate_review_transition,
)


def _artifact(artifact_id: str = "artifact-final") -> ReviewArtifactRef:
    return ReviewArtifactRef(
        artifact_id=artifact_id,
        content_hash="a" * 64,
        task_id="scene-final",
        role="final_video",
    )


def _target() -> ReviewTarget:
    return ReviewTarget(
        project_id="project-demo",
        workflow_id="workflow-demo",
        run_id="run-demo",
        artifacts=(_artifact(),),
    )


def _decision(action: ReviewAction, *, redo_target: str | None = None) -> ReviewDecision:
    return ReviewDecision(
        decision_id=f"decision-{action.value}",
        action=action,
        actor="reviewer:test",
        decided_at="2026-08-10T22:00:00-06:00",
        redo_target=redo_target,
    )


def test_review_target_uses_logical_artifact_references_only() -> None:
    target = _target()

    assert target.project_id == "project-demo"
    assert target.artifacts[0].artifact_id == "artifact-final"
    assert target.artifacts[0].content_hash == "a" * 64

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        ReviewArtifactRef(artifact_id="artifact", path="C:/forbidden/final.mp4")


def test_review_target_requires_at_least_one_artifact() -> None:
    with pytest.raises(ValidationError):
        ReviewTarget(
            project_id="project-demo",
            workflow_id="workflow-demo",
            run_id="run-demo",
            artifacts=(),
        )


def test_review_target_rejects_duplicate_artifact_ids() -> None:
    with pytest.raises(ValidationError, match="artifact_id duplicados"):
        ReviewTarget(
            project_id="project-demo",
            workflow_id="workflow-demo",
            run_id="run-demo",
            artifacts=(_artifact("same"), _artifact("same")),
        )


def test_artifact_reference_validates_optional_sha256() -> None:
    with pytest.raises(ValidationError, match="SHA-256"):
        ReviewArtifactRef(artifact_id="artifact", content_hash="not-a-sha256")


def test_request_changes_requires_redo_target() -> None:
    with pytest.raises(ValidationError, match="requiere redo_target"):
        _decision(ReviewAction.REQUEST_CHANGES)



def test_review_decision_requires_iso_timestamp() -> None:
    with pytest.raises(ValidationError, match="ISO-8601"):
        ReviewDecision(
            decision_id="decision-invalid-time",
            action=ReviewAction.APPROVE,
            actor="reviewer:test",
            decided_at="not-a-timestamp",
        )


def test_review_decision_json_round_trip_preserves_enum_contract() -> None:
    decision = _decision(ReviewAction.REQUEST_CHANGES, redo_target="guion")
    restored = ReviewDecision.model_validate_json(decision.model_dump_json())

    assert restored == decision
    assert restored.action is ReviewAction.REQUEST_CHANGES


def test_non_redo_decisions_reject_redo_target() -> None:
    with pytest.raises(ValidationError, match="solo es válido"):
        _decision(ReviewAction.APPROVE, redo_target="guion")


def test_models_are_frozen_and_json_serializable() -> None:
    target = _target()
    payload = json.loads(target.model_dump_json())

    assert payload["workflow_id"] == "workflow-demo"
    assert payload["artifacts"][0]["artifact_id"] == "artifact-final"
    with pytest.raises(ValidationError):
        target.run_id = "mutated"


def test_ready_for_review_accepts_all_gateway_outcomes() -> None:
    assert validate_review_transition(ReviewState.READY_FOR_REVIEW, ReviewState.APPROVED) is ReviewState.APPROVED
    assert validate_review_transition(ReviewState.READY_FOR_REVIEW, ReviewState.CHANGES_REQUESTED) is ReviewState.CHANGES_REQUESTED
    assert validate_review_transition(ReviewState.READY_FOR_REVIEW, ReviewState.CANCELLED) is ReviewState.CANCELLED


def test_changes_requested_can_be_resubmitted_without_rerun_logic() -> None:
    assert validate_review_transition(ReviewState.CHANGES_REQUESTED, ReviewState.READY_FOR_REVIEW) is ReviewState.READY_FOR_REVIEW


def test_identical_transition_is_an_idempotent_noop() -> None:
    assert validate_review_transition(ReviewState.APPROVED, ReviewState.APPROVED) is ReviewState.APPROVED


def test_terminal_review_states_reject_reopening() -> None:
    with pytest.raises(InvalidReviewTransitionError, match="approved -> ready_for_review"):
        validate_review_transition(ReviewState.APPROVED, ReviewState.READY_FOR_REVIEW)
    with pytest.raises(InvalidReviewTransitionError, match="cancelled -> ready_for_review"):
        validate_review_transition(ReviewState.CANCELLED, ReviewState.READY_FOR_REVIEW)


def test_apply_review_decision_maps_action_without_executing_pipeline() -> None:
    approved = apply_review_decision(
        ReviewState.READY_FOR_REVIEW,
        _decision(ReviewAction.APPROVE),
    )
    changes = apply_review_decision(
        ReviewState.READY_FOR_REVIEW,
        _decision(ReviewAction.REQUEST_CHANGES, redo_target="guion"),
    )
    cancelled = apply_review_decision(
        ReviewState.READY_FOR_REVIEW,
        _decision(ReviewAction.CANCEL),
    )

    assert approved is ReviewState.APPROVED
    assert changes is ReviewState.CHANGES_REQUESTED
    assert cancelled is ReviewState.CANCELLED


def test_review_decision_cannot_be_applied_after_approval() -> None:
    with pytest.raises(InvalidReviewTransitionError, match="approved -> changes_requested"):
        apply_review_decision(
            ReviewState.APPROVED,
            _decision(ReviewAction.REQUEST_CHANGES, redo_target="guion"),
        )
