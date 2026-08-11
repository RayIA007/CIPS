from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sys

import pytest
from pydantic import ValidationError


SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from final_review import (
    AutoApproveReviewPolicy,
    InvalidReviewTransitionError,
    ManualReviewPolicy,
    ReviewAction,
    ReviewArtifactRef,
    ReviewDecision,
    ReviewDecisionRequiredError,
    ReviewGateway,
    ReviewGatewayResult,
    ReviewPolicyError,
    ReviewState,
    ReviewTarget,
)


def target() -> ReviewTarget:
    return ReviewTarget(
        project_id="project-f73",
        workflow_id="workflow-f73",
        run_id="run-f73",
        artifacts=(
            ReviewArtifactRef(
                artifact_id="artifact-final",
                content_hash="a" * 64,
                task_id="final",
                role="final_video",
            ),
        ),
    )


def decision(
    action: ReviewAction,
    *,
    decision_id: str | None = None,
    redo_target: str | None = None,
) -> ReviewDecision:
    return ReviewDecision(
        decision_id=decision_id or f"manual-{action.value}",
        action=action,
        actor="reviewer:test",
        decided_at="2026-08-10T22:30:00-06:00",
        redo_target=redo_target,
    )


def test_manual_policy_requires_explicit_decision() -> None:
    with pytest.raises(ReviewDecisionRequiredError, match="requiere una ReviewDecision"):
        ReviewGateway().present(target(), policy=ManualReviewPolicy())


def test_manual_approve_crosses_gateway_without_execution_side_effects() -> None:
    review_target = target()
    supplied = decision(ReviewAction.APPROVE)

    result = ReviewGateway().present(
        review_target,
        policy=ManualReviewPolicy(),
        decision=supplied,
    )

    assert result.target is review_target
    assert result.previous_state is ReviewState.READY_FOR_REVIEW
    assert result.state is ReviewState.APPROVED
    assert result.decision is supplied
    assert result.policy_name == "manual"
    assert result.approved is True
    assert result.redo_target is None


def test_manual_request_changes_returns_redo_target_but_does_not_execute_it() -> None:
    result = ReviewGateway().present(
        target(),
        policy=ManualReviewPolicy(),
        decision=decision(ReviewAction.REQUEST_CHANGES, redo_target="guion"),
    )

    assert result.state is ReviewState.CHANGES_REQUESTED
    assert result.redo_target == "guion"
    assert result.approved is False


def test_manual_cancel_stops_at_cancelled_review_state() -> None:
    result = ReviewGateway().present(
        target(),
        policy=ManualReviewPolicy(),
        decision=decision(ReviewAction.CANCEL),
    )

    assert result.state is ReviewState.CANCELLED
    assert result.approved is False


def test_auto_policy_emits_explicit_auditable_approval() -> None:
    fixed_time = datetime(2026, 8, 10, 22, 35, tzinfo=timezone.utc)
    policy = AutoApproveReviewPolicy(
        actor="review:auto-test",
        clock=lambda: fixed_time,
    )

    result = ReviewGateway().present(target(), policy=policy)

    assert result.state is ReviewState.APPROVED
    assert result.policy_name == "auto_approve"
    assert result.decision.action is ReviewAction.APPROVE
    assert result.decision.actor == "review:auto-test"
    assert result.decision.decided_at == fixed_time.isoformat()
    assert result.decision.decision_id == "auto-approve:workflow-f73:run-f73"
    assert result.decision.metadata == {
        "review_policy": "auto_approve",
        "decision_origin": "automated",
        "project_id": "project-f73",
        "workflow_id": "workflow-f73",
        "run_id": "run-f73",
    }


def test_auto_policy_decision_id_is_stable_for_same_review_target() -> None:
    policy = AutoApproveReviewPolicy(clock=lambda: "2026-08-10T22:40:00-06:00")
    first = policy.decide(target())
    second = policy.decide(target())

    assert first.decision_id == second.decision_id
    assert first == second


def test_auto_policy_rejects_supplied_manual_decision() -> None:
    with pytest.raises(ReviewPolicyError, match="no acepta una decisión manual"):
        ReviewGateway().present(
            target(),
            policy=AutoApproveReviewPolicy(),
            decision=decision(ReviewAction.CANCEL),
        )


def test_gateway_retry_of_same_terminal_decision_is_idempotent() -> None:
    supplied = decision(ReviewAction.APPROVE, decision_id="decision-stable")
    gateway = ReviewGateway()

    first = gateway.present(target(), policy=ManualReviewPolicy(), decision=supplied)
    retry = gateway.present(
        target(),
        policy=ManualReviewPolicy(),
        current_state=first.state,
        decision=supplied,
    )

    assert first.state is ReviewState.APPROVED
    assert retry.previous_state is ReviewState.APPROVED
    assert retry.state is ReviewState.APPROVED
    assert retry.decision.decision_id == "decision-stable"


def test_gateway_preserves_f71_transition_conflict_rules() -> None:
    with pytest.raises(InvalidReviewTransitionError, match="approved -> changes_requested"):
        ReviewGateway().present(
            target(),
            policy=ManualReviewPolicy(),
            current_state=ReviewState.APPROVED,
            decision=decision(ReviewAction.REQUEST_CHANGES, redo_target="guion"),
        )


def test_gateway_result_is_frozen_and_json_serializable() -> None:
    result = ReviewGateway().present(
        target(),
        policy=ManualReviewPolicy(),
        decision=decision(ReviewAction.APPROVE),
    )
    restored = ReviewGatewayResult.model_validate_json(result.model_dump_json())

    assert restored == result
    with pytest.raises(ValidationError):
        result.policy_name = "mutated"


def test_gateway_rejects_non_policy_objects() -> None:
    with pytest.raises(ReviewPolicyError, match="contrato ReviewPolicy"):
        ReviewGateway().present(target(), policy=object())


def test_gateway_rejects_policy_returning_non_decision() -> None:
    class BrokenPolicy:
        name = "broken"

        def decide(self, review_target, *, supplied_decision=None):
            del review_target, supplied_decision
            return "approve"

    with pytest.raises(ReviewPolicyError, match="debe devolver ReviewDecision"):
        ReviewGateway().present(target(), policy=BrokenPolicy())
