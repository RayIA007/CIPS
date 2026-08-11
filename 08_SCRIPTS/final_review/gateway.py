"""Decision gateway for the CIPS F7 final-review domain.

The gateway is deliberately a boundary, not a workflow stage or execution
engine. It asks a policy for a decision, validates that decision through the
F7.1 transition rules, and returns an immutable result. It never reruns work,
mutates ``ProductionState``, persists review history, exports, or publishes.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from .errors import ReviewPolicyError
from .models import ReviewDecision, ReviewState, ReviewTarget
from .policies import ReviewPolicy
from .transitions import apply_review_decision


class ReviewGatewayResult(BaseModel):
    """Immutable result of presenting one target to one review policy."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    target: ReviewTarget
    previous_state: ReviewState
    state: ReviewState
    decision: ReviewDecision
    policy_name: str = Field(..., min_length=1)

    @property
    def approved(self) -> bool:
        return self.state is ReviewState.APPROVED

    @property
    def redo_target(self) -> str | None:
        return self.decision.redo_target


class ReviewGateway:
    """Apply review policies without taking ownership of pipeline execution."""

    def present(
        self,
        target: ReviewTarget,
        *,
        policy: ReviewPolicy,
        current_state: ReviewState | str = ReviewState.READY_FOR_REVIEW,
        decision: ReviewDecision | None = None,
    ) -> ReviewGatewayResult:
        if not isinstance(target, ReviewTarget):
            raise TypeError("target debe ser una instancia de ReviewTarget.")
        if not isinstance(policy, ReviewPolicy):
            raise ReviewPolicyError("policy no implementa el contrato ReviewPolicy.")

        policy_name = str(policy.name).strip()
        if not policy_name:
            raise ReviewPolicyError("ReviewPolicy.name no puede estar vacío.")

        previous_state = ReviewState(current_state)
        resolved_decision = policy.decide(target, supplied_decision=decision)
        if not isinstance(resolved_decision, ReviewDecision):
            raise ReviewPolicyError("ReviewPolicy.decide debe devolver ReviewDecision.")

        next_state = apply_review_decision(previous_state, resolved_decision)
        return ReviewGatewayResult(
            target=target,
            previous_state=previous_state,
            state=next_state,
            decision=resolved_decision,
            policy_name=policy_name,
        )


__all__ = ["ReviewGateway", "ReviewGatewayResult"]
