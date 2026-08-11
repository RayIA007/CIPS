"""Deterministic transition rules for the CIPS F7 final-review domain."""

from __future__ import annotations

from .errors import InvalidReviewTransitionError
from .models import ReviewAction, ReviewDecision, ReviewState


_ALLOWED_TRANSITIONS: dict[ReviewState, frozenset[ReviewState]] = {
    ReviewState.READY_FOR_REVIEW: frozenset(
        {
            ReviewState.APPROVED,
            ReviewState.CHANGES_REQUESTED,
            ReviewState.CANCELLED,
        }
    ),
    ReviewState.CHANGES_REQUESTED: frozenset(
        {
            ReviewState.READY_FOR_REVIEW,
            ReviewState.CANCELLED,
        }
    ),
    ReviewState.APPROVED: frozenset(),
    ReviewState.CANCELLED: frozenset(),
}

_ACTION_TO_STATE: dict[ReviewAction, ReviewState] = {
    ReviewAction.APPROVE: ReviewState.APPROVED,
    ReviewAction.REQUEST_CHANGES: ReviewState.CHANGES_REQUESTED,
    ReviewAction.CANCEL: ReviewState.CANCELLED,
}


def validate_review_transition(
    current: ReviewState | str,
    requested: ReviewState | str,
) -> ReviewState:
    """Validate and return the requested state; identical states are idempotent no-ops."""

    current_state = ReviewState(current)
    requested_state = ReviewState(requested)
    if current_state is requested_state:
        return current_state
    if requested_state not in _ALLOWED_TRANSITIONS[current_state]:
        raise InvalidReviewTransitionError(
            "Transición de final review inválida: "
            f"{current_state.value} -> {requested_state.value}."
        )
    return requested_state


def apply_review_decision(
    current: ReviewState | str,
    decision: ReviewDecision,
) -> ReviewState:
    """Map a decision to its state transition without executing any pipeline work."""

    requested_state = _ACTION_TO_STATE[decision.action]
    return validate_review_transition(current, requested_state)


__all__ = ["apply_review_decision", "validate_review_transition"]
