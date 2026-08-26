"""Small injectable standard-library HTTP transport."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


@dataclass(frozen=True, slots=True)
class JSON2VideoHttpResponse:
    status_code: int
    headers: Mapping[str, str]
    body: bytes


class JSON2VideoTransportError(RuntimeError):
    pass


class JSON2VideoHttpTransport(Protocol):
    def request(
        self,
        *,
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: bytes | None,
        timeout_seconds: float,
        max_response_bytes: int,
    ) -> JSON2VideoHttpResponse: ...


class UrllibJSON2VideoTransport:
    user_agent = "CIPS-PM9/1.0"

    def request(
        self,
        *,
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: bytes | None,
        timeout_seconds: float,
        max_response_bytes: int,
    ) -> JSON2VideoHttpResponse:
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
                return JSON2VideoHttpResponse(
                    status_code=int(response.status),
                    headers=_headers(response.headers),
                    body=_read_limited(response, max_response_bytes),
                )
        except HTTPError as error:
            return JSON2VideoHttpResponse(
                status_code=int(error.code),
                headers=_headers(error.headers),
                body=_read_limited(error, max_response_bytes),
            )
        except (TimeoutError, URLError, OSError) as error:
            raise JSON2VideoTransportError(
                f"La conexión terminó sin respuesta: {type(error).__name__}."
            ) from error


def _headers(value: object) -> dict[str, str]:
    items = getattr(value, "items", None)
    return (
        {str(key).casefold(): str(item) for key, item in items()}
        if callable(items)
        else {}
    )


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
            raise JSON2VideoTransportError(
                f"La respuesta excede el límite seguro de {maximum} bytes."
            )
    return b"".join(chunks)


__all__ = [
    "JSON2VideoHttpResponse",
    "JSON2VideoHttpTransport",
    "JSON2VideoTransportError",
    "UrllibJSON2VideoTransport",
]
