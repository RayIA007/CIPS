"""Explicit, secret-safe failures for the Creatomate online boundary."""

from __future__ import annotations

from enum import Enum
from typing import Any

from render_adapter import RenderAdapterError


class CreatomateFailureCategory(str, Enum):
    """CIPS failure categories used by the PM6 provider integration."""

    CONFIGURATION = "CONFIGURACIÓN"
    PROVIDER_EXTERNAL = "PROVIDER EXTERNO"
    QUOTA = "CUOTA"
    DATA_VALIDATION = "DATOS / VALIDACIÓN"


class CreatomateApiError(RenderAdapterError):
    """Base failure carrying retry and classification information."""

    def __init__(
        self,
        message: str,
        *,
        operation: str,
        category: CreatomateFailureCategory,
        retryable: bool,
        status_code: int | None = None,
        retry_after_seconds: float | None = None,
        ambiguous_submission: bool = False,
        attempts: tuple[Any, ...] = (),
    ) -> None:
        self.operation = str(operation).strip()
        self.category = CreatomateFailureCategory(category)
        self.retryable = bool(retryable)
        self.status_code = status_code
        self.retry_after_seconds = retry_after_seconds
        self.ambiguous_submission = bool(ambiguous_submission)
        self.attempts = tuple(attempts)
        super().__init__(str(message).strip())

    def with_attempts(self, attempts: tuple[Any, ...]) -> CreatomateApiError:
        """Attach retry evidence without changing the safe public message."""

        self.attempts = tuple(attempts)
        return self


class CreatomateConfigurationError(CreatomateApiError):
    """Missing or unsafe local configuration."""


class CreatomateAuthenticationError(CreatomateApiError):
    """The provider rejected the configured credentials or permissions."""


class CreatomateRateLimitError(CreatomateApiError):
    """The provider returned HTTP 429 or an equivalent quota signal."""


class CreatomateTransientError(CreatomateApiError):
    """A retryable remote-service failure."""


class CreatomateTerminalError(CreatomateApiError):
    """A non-retryable provider or request failure."""


class CreatomateInvalidResponseError(CreatomateApiError):
    """The provider response violates the expected API contract."""


class CreatomateAmbiguousSubmissionError(CreatomateApiError):
    """A submit may have reached the provider, so replay is intentionally blocked."""


class CreatomatePollingTimeoutError(CreatomateApiError):
    """A render did not reach a terminal state within the configured window."""


__all__ = [
    "CreatomateAmbiguousSubmissionError",
    "CreatomateApiError",
    "CreatomateAuthenticationError",
    "CreatomateConfigurationError",
    "CreatomateFailureCategory",
    "CreatomateInvalidResponseError",
    "CreatomatePollingTimeoutError",
    "CreatomateRateLimitError",
    "CreatomateTerminalError",
    "CreatomateTransientError",
]
