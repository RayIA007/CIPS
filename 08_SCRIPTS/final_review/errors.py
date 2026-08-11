"""Domain-specific errors for the CIPS F7 final-review domain."""


class FinalReviewError(RuntimeError):
    """Base error for final-review domain failures."""


class InvalidReviewTransitionError(FinalReviewError):
    """Raised when a requested final-review state transition is invalid."""


class ReviewTargetBuildError(FinalReviewError):
    """Raised when an execution result cannot produce a valid review target."""


class InconsistentReviewArtifactError(ReviewTargetBuildError):
    """Raised when Core exposes conflicting artifact identities for the same task."""


class ReviewGatewayError(FinalReviewError):
    """Base error for final-review gateway failures."""


class ReviewDecisionRequiredError(ReviewGatewayError):
    """Raised when a policy requires an explicit decision and none was supplied."""


class ReviewPolicyError(ReviewGatewayError):
    """Raised when a review policy violates the gateway contract."""


class ReviewExportBoundaryError(FinalReviewError):
    """Base error for failures at the review-to-export boundary."""


class ReviewExportBlockedError(ReviewExportBoundaryError):
    """Raised when export is attempted without an approved review result."""

    def __init__(
        self,
        message: str,
        *,
        state: str,
        decision_id: str,
        redo_target: str | None = None,
    ) -> None:
        super().__init__(message)
        self.state = state
        self.decision_id = decision_id
        self.redo_target = redo_target


class ReviewPersistenceError(FinalReviewError):
    """Raised when an F7 review audit record cannot be persisted or loaded."""


__all__ = [
    "FinalReviewError",
    "InconsistentReviewArtifactError",
    "InvalidReviewTransitionError",
    "ReviewDecisionRequiredError",
    "ReviewExportBlockedError",
    "ReviewExportBoundaryError",
    "ReviewGatewayError",
    "ReviewPolicyError",
    "ReviewPersistenceError",
    "ReviewTargetBuildError",
]
