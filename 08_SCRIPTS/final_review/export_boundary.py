"""Review-aware authorization boundary placed immediately before export.

This adapter deliberately does not own export implementation. It receives an
already validated ``ReviewGatewayResult`` and invokes a supplied export
operation only when the result is an explicit approval. This keeps F7 separate
from ``ExportEngine`` while making the approval gate impossible to bypass
accidentally inside callers that use this boundary.
"""
from __future__ import annotations
from collections.abc import Callable
from typing import Any, TypeVar
from pydantic import BaseModel, ConfigDict, Field
from .errors import ReviewExportBlockedError, ReviewExportBoundaryError
from .gateway import ReviewGatewayResult
from .models import ReviewAction, ReviewState

T = TypeVar("T")

class ReviewExportAuthorization(BaseModel):
    """Immutable audit-friendly authorization emitted before export execution."""
    model_config = ConfigDict(extra="forbid", frozen=True)
    project_id: str = Field(..., min_length=1)
    workflow_id: str = Field(..., min_length=1)
    run_id: str = Field(..., min_length=1)
    decision_id: str = Field(..., min_length=1)
    policy_name: str = Field(..., min_length=1)
    review_state: ReviewState
    actor: str = Field(..., min_length=1)

class ReviewExportBoundary:
    """Authorize and invoke an export operation without owning export behavior."""
    def authorize(self, review_result: ReviewGatewayResult) -> ReviewExportAuthorization:
        if not isinstance(review_result, ReviewGatewayResult):
            raise ReviewExportBoundaryError(
                "review_result debe ser una instancia de ReviewGatewayResult."
            )
        decision = review_result.decision
        if (
            review_result.state is not ReviewState.APPROVED
            or decision.action is not ReviewAction.APPROVE
        ):
            state = review_result.state.value
            raise ReviewExportBlockedError(
                f"Exportación bloqueada por final review en estado '{state}'.",
                state=state,
                decision_id=decision.decision_id,
                redo_target=decision.redo_target,
            )
        target = review_result.target
        return ReviewExportAuthorization(
            project_id=target.project_id,
            workflow_id=target.workflow_id,
            run_id=target.run_id,
            decision_id=decision.decision_id,
            policy_name=review_result.policy_name,
            review_state=review_result.state,
            actor=decision.actor,
        )

    def execute(
        self,
        review_result: ReviewGatewayResult,
        export_operation: Callable[[], T],
    ) -> T:
        """Invoke ``export_operation`` exactly once after explicit approval."""
        if not callable(export_operation):
            raise ReviewExportBoundaryError("export_operation debe ser callable.")
        self.authorize(review_result)
        return export_operation()


def execute_after_review(
    review_result: ReviewGatewayResult,
    export_operation: Callable[[], T],
) -> T:
    """Convenience facade for one-shot review-gated export execution."""
    return ReviewExportBoundary().execute(review_result, export_operation)

__all__ = [
    "ReviewExportAuthorization",
    "ReviewExportBoundary",
    "execute_after_review",
]
