"""Review policies for the CIPS F7 final-review gateway.

Policies resolve *how* a review decision is obtained. They do not transition
workflow state, execute stages, persist records, export files, or publish
content. Manual review consumes an explicit ``ReviewDecision`` supplied by the
caller; auto mode emits an explicit, auditable approval decision.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from typing import Protocol, runtime_checkable

from .errors import ReviewDecisionRequiredError, ReviewPolicyError
from .models import ReviewAction, ReviewDecision, ReviewTarget


@runtime_checkable
class ReviewPolicy(Protocol):
    """Minimal policy contract consumed by ``ReviewGateway``."""

    name: str

    def decide(
        self,
        target: ReviewTarget,
        *,
        supplied_decision: ReviewDecision | None = None,
    ) -> ReviewDecision:
        """Return the explicit decision to apply to ``target``."""


class ManualReviewPolicy:
    """Require the caller to provide an explicit human/manual decision."""

    name = "manual"

    def decide(
        self,
        target: ReviewTarget,
        *,
        supplied_decision: ReviewDecision | None = None,
    ) -> ReviewDecision:
        del target  # The policy does not inspect or mutate review artifacts.
        if supplied_decision is None:
            raise ReviewDecisionRequiredError(
                "La política manual requiere una ReviewDecision explícita."
            )
        return supplied_decision


class AutoApproveReviewPolicy:
    """Emit an explicit approval for non-interactive/automatic executions."""

    name = "auto_approve"

    def __init__(
        self,
        *,
        actor: str = "review:auto",
        clock: Callable[[], datetime | str] | None = None,
    ) -> None:
        normalized_actor = actor.strip()
        if not normalized_actor:
            raise ValueError("actor no puede estar vacío.")
        self._actor = normalized_actor
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def decide(
        self,
        target: ReviewTarget,
        *,
        supplied_decision: ReviewDecision | None = None,
    ) -> ReviewDecision:
        if supplied_decision is not None:
            raise ReviewPolicyError(
                "La política auto_approve no acepta una decisión manual suministrada."
            )

        return ReviewDecision(
            decision_id=f"auto-approve:{target.workflow_id}:{target.run_id}",
            action=ReviewAction.APPROVE,
            actor=self._actor,
            decided_at=self._timestamp(),
            metadata={
                "review_policy": self.name,
                "decision_origin": "automated",
                "project_id": target.project_id,
                "workflow_id": target.workflow_id,
                "run_id": target.run_id,
            },
        )

    def _timestamp(self) -> str:
        value = self._clock()
        if isinstance(value, datetime):
            if value.tzinfo is None:
                value = value.replace(tzinfo=timezone.utc)
            return value.isoformat()
        text = str(value).strip()
        if not text:
            raise ReviewPolicyError("La política auto_approve produjo un timestamp vacío.")
        return text


__all__ = [
    "AutoApproveReviewPolicy",
    "ManualReviewPolicy",
    "ReviewPolicy",
]
