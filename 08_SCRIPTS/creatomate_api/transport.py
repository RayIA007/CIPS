"""Small injectable HTTP transport used by the Creatomate API client."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


@dataclass(frozen=True, slots=True)
class CreatomateHttpResponse:
    status_code: int
    headers: Mapping[str, str]
    body: bytes


class CreatomateTransportError(RuntimeError):
    """A request ended without a definitive HTTP response."""


class CreatomateHttpTransport(Protocol):
    def request(
        self,
        *,
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: bytes | None,
        timeout_seconds: float,
        max_response_bytes: int,
    ) -> CreatomateHttpResponse: ...


class UrllibCreatomateTransport:
    """Standard-library transport so PM6 adds no runtime dependency."""

    user_agent = "CIPS-Creatomate-PM6/1.0"

    def request(
        self,
        *,
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: bytes | None,
        timeout_seconds: float,
        max_response_bytes: int,
    ) -> CreatomateHttpResponse:
        request_headers = {str(key): str(value) for key, value in headers.items()}
        request_headers.setdefault("User-Agent", self.user_agent)
        request = Request(
            str(url),
            data=body,
            headers=request_headers,
            method=str(method).upper(),
        )
        try:
            with urlopen(request, timeout=timeout_seconds) as response:
                payload = _read_limited(response, max_response_bytes)
                return CreatomateHttpResponse(
                    status_code=int(response.status),
                    headers=_normalize_headers(response.headers),
                    body=payload,
                )
        except HTTPError as error:
            payload = _read_limited(error, max_response_bytes)
            return CreatomateHttpResponse(
                status_code=int(error.code),
                headers=_normalize_headers(error.headers),
                body=payload,
            )
        except (TimeoutError, URLError, OSError) as error:
            raise CreatomateTransportError(
                f"La conexión HTTP terminó sin respuesta: {type(error).__name__}."
            ) from error


def _normalize_headers(headers: object) -> dict[str, str]:
    items = getattr(headers, "items", None)
    if not callable(items):
        return {}
    return {str(key).casefold(): str(value) for key, value in items()}


def _read_limited(stream: object, maximum: int) -> bytes:
    read = getattr(stream, "read", None)
    if not callable(read):
        return b""
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = read(min(1024 * 1024, maximum - total + 1))
        if not chunk:
            break
        chunks.append(bytes(chunk))
        total += len(chunk)
        if total > maximum:
            raise CreatomateTransportError(
                f"La respuesta excede el límite seguro de {maximum} bytes."
            )
    return b"".join(chunks)


__all__ = [
    "CreatomateHttpResponse",
    "CreatomateHttpTransport",
    "CreatomateTransportError",
    "UrllibCreatomateTransport",
]
