"""Environment-only JSON2Video configuration."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from urllib.parse import urlsplit

from .errors import JSON2VideoConfigurationError


JSON2VIDEO_API_KEY_ENV = "JSON2VIDEO_API_KEY"
JSON2VIDEO_API_BASE_URL = "https://api.json2video.com/v2"


@dataclass(frozen=True, slots=True)
class JSON2VideoApiConfig:
    api_key: str = field(repr=False)
    base_url: str = JSON2VIDEO_API_BASE_URL
    request_timeout_seconds: float = 30.0
    download_timeout_seconds: float = 120.0
    poll_interval_seconds: float = 5.0
    poll_timeout_seconds: float = 900.0
    max_attempts: int = 3
    max_json_bytes: int = 2 * 1024 * 1024
    max_download_bytes: int = 512 * 1024 * 1024

    def __post_init__(self) -> None:
        key = str(self.api_key).strip()
        if not key:
            raise JSON2VideoConfigurationError(
                f"La variable {JSON2VIDEO_API_KEY_ENV} no está configurada.",
                operation="configuration",
                category="configuration",
                retryable=False,
            )
        object.__setattr__(self, "api_key", key)
        base_url = str(self.base_url).strip().rstrip("/")
        parsed = urlsplit(base_url)
        if parsed.scheme.lower() != "https" or not parsed.netloc:
            raise JSON2VideoConfigurationError(
                "base_url de JSON2Video debe usar HTTPS.",
                operation="configuration",
                category="configuration",
                retryable=False,
            )
        object.__setattr__(self, "base_url", base_url)
        for name in (
            "request_timeout_seconds",
            "download_timeout_seconds",
            "poll_interval_seconds",
            "poll_timeout_seconds",
        ):
            value = getattr(self, name)
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or float(value) <= 0
            ):
                raise JSON2VideoConfigurationError(
                    f"{name} debe ser positivo.",
                    operation="configuration",
                    category="configuration",
                    retryable=False,
                )
            object.__setattr__(self, name, float(value))
        for name in ("max_attempts", "max_json_bytes", "max_download_bytes"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise JSON2VideoConfigurationError(
                    f"{name} debe ser un entero positivo.",
                    operation="configuration",
                    category="configuration",
                    retryable=False,
                )

    @classmethod
    def from_environment(
        cls,
        environ: Mapping[str, str] | None = None,
        **overrides: object,
    ) -> "JSON2VideoApiConfig":
        values = os.environ if environ is None else environ
        return cls(
            api_key=str(values.get(JSON2VIDEO_API_KEY_ENV, "") or "").strip(),
            **overrides,
        )

    def safe_descriptor(self) -> dict[str, object]:
        return {
            "base_url": self.base_url,
            "credential_source": JSON2VIDEO_API_KEY_ENV,
            "credential_configured": True,
            "poll_interval_seconds": self.poll_interval_seconds,
            "poll_timeout_seconds": self.poll_timeout_seconds,
            "max_attempts": self.max_attempts,
        }

    def redact(self, value: object) -> str:
        return str(value or "").replace(self.api_key, "[REDACTED]")


__all__ = [
    "JSON2VIDEO_API_BASE_URL",
    "JSON2VIDEO_API_KEY_ENV",
    "JSON2VideoApiConfig",
]
