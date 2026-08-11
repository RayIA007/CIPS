"""Domain-specific errors for the CIPS F7 final-review domain."""


class FinalReviewError(RuntimeError):
    """Base error for final-review domain failures."""


class InvalidReviewTransitionError(FinalReviewError):
    """Raised when a requested final-review state transition is invalid."""


class ReviewTargetBuildError(FinalReviewError):
    """Raised when an execution result cannot produce a valid review target."""


class InconsistentReviewArtifactError(ReviewTargetBuildError):
    """Raised when Core exposes conflicting artifact identities for the same task."""


__all__ = [
    "FinalReviewError",
    "InconsistentReviewArtifactError",
    "InvalidReviewTransitionError",
    "ReviewTargetBuildError",
]
