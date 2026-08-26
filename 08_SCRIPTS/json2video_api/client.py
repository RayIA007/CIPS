"""Authenticated JSON2Video client with conservative retry behavior."""

from __future__ import annotations

import json
import math
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote, urlsplit

from render_adapter import RenderStatus

from .config import JSON2VideoApiConfig
from .errors import (
    JSON2VideoAmbiguousSubmissionError,
    JSON2VideoApiError,
    JSON2VideoAuthenticationError,
    JSON2VideoInvalidResponseError,
)
from .transport import (
    JSON2VideoHttpResponse,
    JSON2VideoHttpTransport,
    JSON2VideoTransportError,
    UrllibJSON2VideoTransport,
)


_STATUS_MAP = {
    "pending": RenderStatus.QUEUED,
    "running": RenderStatus.RUNNING,
    "done": RenderStatus.SUCCEEDED,
    "error": RenderStatus.FAILED,
    "timeout": RenderStatus.FAILED,
}
_RETRYABLE_HTTP = {408, 425, 429, 500, 502, 503, 504}


@dataclass(frozen=True, slots=True)
class JSON2VideoMovieSnapshot:
    project_id: str
    provider_status: str
    status: RenderStatus
    output_url: str | None = None
    message: str | None = None
    width: int | None = None
    height: int | None = None
    duration: float | None = None
    size_bytes: int | None = None
    consumed_credits: float | None = None

    def safe_metadata(self) -> dict[str, Any]:
        values: dict[str, Any] = {"provider_status": self.provider_status}
        for name in (
            "width",
            "height",
            "duration",
            "size_bytes",
            "consumed_credits",
        ):
            value = getattr(self, name)
            if value is not None:
                values[name] = value
        return values


class JSON2VideoApiClient:
    def __init__(
        self,
        config: JSON2VideoApiConfig,
        *,
        transport: JSON2VideoHttpTransport | None = None,
        sleep_function: Callable[[float], None] | None = None,
    ) -> None:
        if not isinstance(config, JSON2VideoApiConfig):
            raise TypeError("config debe ser JSON2VideoApiConfig.")
        self.config = config
        self.transport = transport or UrllibJSON2VideoTransport()
        self.sleep_function = sleep_function or time.sleep

    def create_movie(self, payload: Mapping[str, Any]) -> JSON2VideoMovieSnapshot:
        if not isinstance(payload, Mapping):
            raise TypeError("payload debe ser un Mapping.")
        body = json.dumps(
            dict(payload),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        response = self._request_once(
            method="POST",
            url=f"{self.config.base_url}/movies",
            body=body,
            operation="render.submit",
            timeout=self.config.request_timeout_seconds,
            maximum=self.config.max_json_bytes,
            ambiguous_on_transport=True,
            authenticated=True,
        )
        data = self._decode_json(response, "render.submit")
        if data.get("success") is not True:
            raise self._invalid("JSON2Video no confirmó el envío.", "render.submit")
        project_id = _project_id(data.get("project"))
        return JSON2VideoMovieSnapshot(
            project_id=project_id,
            provider_status="pending",
            status=RenderStatus.QUEUED,
        )

    def get_movie(self, project_id: str) -> JSON2VideoMovieSnapshot:
        normalized = _project_id(project_id)
        response = self._request_with_retries(
            method="GET",
            url=(
                f"{self.config.base_url}/movies?project="
                f"{quote(normalized, safe='')}&format=simple"
            ),
            operation="render.status",
            timeout=self.config.request_timeout_seconds,
            maximum=self.config.max_json_bytes,
            authenticated=True,
        )
        data = self._decode_json(response, "render.status")
        movie = data.get("movie")
        if data.get("success") is not True or not isinstance(movie, Mapping):
            raise self._invalid("Respuesta de estado sin movie.", "render.status")
        returned_id = _project_id(movie.get("project"))
        if returned_id != normalized:
            raise self._invalid(
                "La respuesta pertenece a otro proyecto JSON2Video.",
                "render.status",
            )
        provider_status = str(movie.get("status", "")).strip().lower()
        status = _STATUS_MAP.get(provider_status)
        if status is None:
            raise self._invalid(
                f"Estado JSON2Video desconocido: {provider_status or '<vacío>'}.",
                "render.status",
            )
        output_url = _optional_text(movie.get("url"))
        if status is RenderStatus.SUCCEEDED:
            if output_url is None or not _public_https(output_url):
                raise self._invalid(
                    "El render terminado no contiene una URL HTTPS pública.",
                    "render.status",
                )
        message = _optional_text(movie.get("message"))
        if status is RenderStatus.FAILED and message is None:
            message = f"JSON2Video terminó en estado {provider_status}."
        return JSON2VideoMovieSnapshot(
            project_id=returned_id,
            provider_status=provider_status,
            status=status,
            output_url=output_url,
            message=self.config.redact(message) if message else None,
            width=_positive_int(movie.get("width")),
            height=_positive_int(movie.get("height")),
            duration=_positive_float(movie.get("duration")),
            size_bytes=_positive_int(movie.get("size")),
            consumed_credits=_credits(movie.get("consumed_credits")),
        )

    def download_movie(self, output_url: str) -> bytes:
        if not _public_https(output_url):
            raise ValueError("output_url debe ser HTTPS pública.")
        response = self._request_with_retries(
            method="GET",
            url=output_url,
            operation="render.download",
            timeout=self.config.download_timeout_seconds,
            maximum=self.config.max_download_bytes,
            authenticated=False,
        )
        content_type = str(response.headers.get("content-type", "")).split(";", 1)[0]
        if content_type and content_type.casefold() not in {
            "video/mp4",
            "application/octet-stream",
        }:
            raise self._invalid(
                f"Content-Type inesperado al descargar: {content_type}.",
                "render.download",
            )
        if len(response.body) < 12 or b"ftyp" not in response.body[4:32]:
            raise self._invalid(
                "La descarga no tiene firma de contenedor MP4.",
                "render.download",
            )
        return response.body

    def _request_with_retries(
        self,
        *,
        method: str,
        url: str,
        operation: str,
        timeout: float,
        maximum: int,
        authenticated: bool,
    ) -> JSON2VideoHttpResponse:
        last_error: JSON2VideoApiError | None = None
        for attempt in range(1, self.config.max_attempts + 1):
            try:
                return self._request_once(
                    method=method,
                    url=url,
                    body=None,
                    operation=operation,
                    timeout=timeout,
                    maximum=maximum,
                    ambiguous_on_transport=False,
                    authenticated=authenticated,
                )
            except JSON2VideoApiError as error:
                last_error = error
                if not error.retryable or attempt >= self.config.max_attempts:
                    raise
                self.sleep_function(float(2 ** (attempt - 1)))
        if last_error is not None:
            raise last_error
        raise AssertionError("retry loop vacío")

    def _request_once(
        self,
        *,
        method: str,
        url: str,
        body: bytes | None,
        operation: str,
        timeout: float,
        maximum: int,
        ambiguous_on_transport: bool,
        authenticated: bool,
    ) -> JSON2VideoHttpResponse:
        headers = {"Accept": "application/json" if authenticated else "video/mp4,*/*"}
        if authenticated:
            headers["x-api-key"] = self.config.api_key
        if body is not None:
            headers["Content-Type"] = "application/json"
        try:
            response = self.transport.request(
                method=method,
                url=url,
                headers=headers,
                body=body,
                timeout_seconds=timeout,
                max_response_bytes=maximum,
            )
        except JSON2VideoTransportError as error:
            message = self.config.redact(error)
            if ambiguous_on_transport:
                raise JSON2VideoAmbiguousSubmissionError(
                    "El envío terminó sin respuesta; no se repetirá para evitar "
                    "consumir créditos dos veces. " + message,
                    operation=operation,
                    category="provider_external",
                    retryable=False,
                    ambiguous_submission=True,
                ) from error
            raise JSON2VideoApiError(
                message,
                operation=operation,
                category="provider_external",
                retryable=True,
            ) from error
        status = response.status_code
        if 200 <= status < 300:
            return response
        message = self._response_message(response)
        if status in {401, 403}:
            raise JSON2VideoAuthenticationError(
                message,
                operation=operation,
                category="authentication_or_quota",
                retryable=False,
                status_code=status,
            )
        ambiguous = operation == "render.submit" and status in _RETRYABLE_HTTP
        raise JSON2VideoApiError(
            message,
            operation=operation,
            category=("provider_external" if status in _RETRYABLE_HTTP else "data_validation"),
            retryable=status in _RETRYABLE_HTTP,
            status_code=status,
            ambiguous_submission=ambiguous,
        )

    def _decode_json(
        self,
        response: JSON2VideoHttpResponse,
        operation: str,
    ) -> Mapping[str, Any]:
        try:
            data = json.loads(response.body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise self._invalid("JSON de respuesta inválido.", operation) from error
        if not isinstance(data, Mapping):
            raise self._invalid("La respuesta JSON no es un objeto.", operation)
        return data

    def _response_message(self, response: JSON2VideoHttpResponse) -> str:
        try:
            data = json.loads(response.body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            data = None
        if isinstance(data, Mapping):
            raw = data.get("message") or data.get("error")
            if raw:
                return self.config.redact(raw)
        return f"JSON2Video respondió HTTP {response.status_code}."

    @staticmethod
    def _invalid(message: str, operation: str) -> JSON2VideoInvalidResponseError:
        return JSON2VideoInvalidResponseError(
            message,
            operation=operation,
            category="invalid_response",
            retryable=False,
        )


def _project_id(value: Any) -> str:
    normalized = str(value or "").strip()
    if len(normalized) != 16 or not normalized.isalnum():
        raise JSON2VideoInvalidResponseError(
            "project debe ser un identificador alfanumérico de 16 caracteres.",
            operation="render.response",
            category="invalid_response",
            retryable=False,
        )
    return normalized


def _optional_text(value: Any) -> str | None:
    normalized = str(value or "").strip()
    return normalized or None


def _positive_int(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    rendered = int(value)
    return rendered if rendered > 0 and rendered == value else None


def _positive_float(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    rendered = float(value)
    return rendered if math.isfinite(rendered) and rendered > 0 else None


def _credits(value: Any) -> float | None:
    if not isinstance(value, list):
        return None
    total = 0.0
    found = False
    for item in value:
        if not isinstance(item, Mapping):
            continue
        raw = item.get("credits", item.get("amount", item.get("time")))
        if isinstance(raw, bool) or not isinstance(raw, (int, float)):
            continue
        if float(raw) < 0 or not math.isfinite(float(raw)):
            continue
        total += float(raw)
        found = True
    if not found:
        return None
    return round(total, 6)


def _public_https(value: str) -> bool:
    parsed = urlsplit(str(value))
    return (
        parsed.scheme.lower() == "https"
        and bool(parsed.netloc)
        and parsed.username is None
        and parsed.password is None
    )


__all__ = [
    "JSON2VideoApiClient",
    "JSON2VideoMovieSnapshot",
]
