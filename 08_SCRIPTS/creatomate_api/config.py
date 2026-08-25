"""Environment-only configuration for the Creatomate PM6 integration."""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from urllib.parse import urlparse

from .errors import (
    CreatomateConfigurationError,
    CreatomateFailureCategory,
)

CREATOMATE_API_KEY_ENV = "CREATOMATE_API_KEY"
CREATOMATE_API_BASE_URL = "https://api.creatomate.com/v2"


@dataclass(frozen=True, slots=True)
class CreatomateApiConfig:
    """Validated runtime configuration whose representation never reveals the key."""

    api_key: str = field(repr=False)
    base_url: str = CREATOMATE_API_BASE_URL
    request_timeout_seconds: float = 30.0
    download_timeout_seconds: float = 120.0
    poll_interval_seconds: float = 2.0
    poll_timeout_seconds: float = 300.0
    max_attempts: int = 3
    initial_retry_delay_seconds: float = 1.0
    max_retry_delay_seconds: float = 10.0
    max_json_bytes: int = 2 * 1024 * 1024
    max_download_bytes: int = 512 * 1024 * 1024

    def __post_init__(self) -> None:
        key = str(self.api_key).strip()
        if not key:
            raise _configuration_error(
                f"La variable de entorno {CREATOMATE_API_KEY_ENV} no está configurada."
            )
        object.__setattr__(self, "api_key", key)

        base_url = str(self.base_url).strip().rstrip("/")
        parsed = urlparse(base_url)
        if parsed.scheme != "https" or not parsed.netloc:
            raise _configuration_error("base_url de Creatomate debe usar HTTPS.")
        object.__setattr__(self, "base_url", base_url)

        for name in (
            "request_timeout_seconds",
            "download_timeout_seconds",
            "poll_interval_seconds",
            "poll_timeout_seconds",
            "initial_retry_delay_seconds",
            "max_retry_delay_seconds",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise _configuration_error(f"{name} debe ser numérico.")
            if float(value) < 0.0 or (
                name not in {"poll_interval_seconds", "initial_retry_delay_seconds"}
                and float(value) == 0.0
            ):
                raise _configuration_error(f"{name} contiene un valor inválido.")
            object.__setattr__(self, name, float(value))

        if isinstance(self.max_attempts, bool) or self.max_attempts < 1:
            raise _configuration_error("max_attempts debe ser un entero positivo.")
        for name in ("max_json_bytes", "max_download_bytes"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise _configuration_error(f"{name} debe ser un entero positivo.")

    @classmethod
    def from_environment(
        cls,
        environ: Mapping[str, str] | None = None,
        **overrides: object,
    ) -> CreatomateApiConfig:
        """Read the project key from the process environment only."""

        values = os.environ if environ is None else environ
        api_key = str(values.get(CREATOMATE_API_KEY_ENV, "") or "").strip()
        return cls(api_key=api_key, **overrides)

    def safe_descriptor(self) -> dict[str, object]:
        """Return diagnostics that deliberately omit credentials."""

        return {
            "base_url": self.base_url,
            "request_timeout_seconds": self.request_timeout_seconds,
            "download_timeout_seconds": self.download_timeout_seconds,
            "poll_interval_seconds": self.poll_interval_seconds,
            "poll_timeout_seconds": self.poll_timeout_seconds,
            "max_attempts": self.max_attempts,
            "credential_source": CREATOMATE_API_KEY_ENV,
            "credential_configured": True,
        }

    def redact(self, value: object) -> str:
        """Remove the configured key and common authorization forms from text."""

        text = str(value or "")
        if self.api_key:
            text = text.replace(self.api_key, "[REDACTED]")
        return re.sub(
            r"(?i)(authorization\s*:\s*bearer\s+)[^\s,;]+",
            r"\1[REDACTED]",
            text,
        )


def _configuration_error(message: str) -> CreatomateConfigurationError:
    return CreatomateConfigurationError(
        message,
        operation="configuration",
        category=CreatomateFailureCategory.CONFIGURATION,
        retryable=False,
    )


__all__ = [
    "CREATOMATE_API_BASE_URL",
    "CREATOMATE_API_KEY_ENV",
    "CreatomateApiConfig",
]
