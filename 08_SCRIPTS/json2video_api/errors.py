"""Typed failures for the JSON2Video integration."""

from __future__ import annotations


class JSON2VideoApiError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        operation: str,
        category: str,
        retryable: bool,
        status_code: int | None = None,
        ambiguous_submission: bool = False,
    ) -> None:
        super().__init__(message)
        self.operation = str(operation)
        self.category = str(category)
        self.retryable = bool(retryable)
        self.status_code = status_code
        self.ambiguous_submission = bool(ambiguous_submission)


class JSON2VideoConfigurationError(JSON2VideoApiError):
    pass


class JSON2VideoAuthenticationError(JSON2VideoApiError):
    pass


class JSON2VideoInvalidResponseError(JSON2VideoApiError):
    pass


class JSON2VideoAmbiguousSubmissionError(JSON2VideoApiError):
    pass


class JSON2VideoPollingTimeoutError(JSON2VideoApiError):
    pass


__all__ = [
    "JSON2VideoAmbiguousSubmissionError",
    "JSON2VideoApiError",
    "JSON2VideoAuthenticationError",
    "JSON2VideoConfigurationError",
    "JSON2VideoInvalidResponseError",
    "JSON2VideoPollingTimeoutError",
]
