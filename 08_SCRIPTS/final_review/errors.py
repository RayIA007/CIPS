"""Domain-specific errors for the CIPS F7 final-review foundation."""


class FinalReviewError(RuntimeError):
    """Base error for final-review domain failures."""


class InvalidReviewTransitionError(FinalReviewError):
    """Raised when a requested final-review state transition is invalid."""


__all__ = ["FinalReviewError", "InvalidReviewTransitionError"]
