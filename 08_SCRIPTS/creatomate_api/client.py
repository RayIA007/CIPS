"""Retrying Creatomate REST client and provider-to-PM4 status mapping."""

from __future__ import annotations

import json
import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import quote, urlparse

from render_adapter import RenderStatus, RenderSubmission
from retry_engine import RetryAttempt, RetryEngine
from retry_policy import RetryPolicy

from .config import CreatomateApiConfig
from .errors import (
    CreatomateAmbiguousSubmissionError,
    CreatomateApiError,
    CreatomateAuthenticationError,
    CreatomateFailureCategory,
    CreatomateInvalidResponseError,
    CreatomateRateLimitError,
    CreatomateTerminalError,
    CreatomateTransientError,
)
from .transport import (
    CreatomateHttpResponse,
    CreatomateHttpTransport,
    CreatomateTransportError,
    UrllibCreatomateTransport,
)

_CREATOMATE_STATUS_MAP: dict[str, RenderStatus] = {
    "planned": RenderStatus.QUEUED,
    "waiting": RenderStatus.RUNNING,
    "transcribing": RenderStatus.RUNNING,
    "rendering": RenderStatus.RUNNING,
    "succeeded": RenderStatus.SUCCEEDED,
    "failed": RenderStatus.FAILED,
}
_RETRYABLE_HTTP_STATUS = {408, 409, 425, 429, 500, 502, 503, 504}
_DATA_HTTP_STATUS = {400, 404, 405, 406, 410, 422}


@dataclass(frozen=True, slots=True)
class CreatomateApiCall:
    """One successful JSON call plus complete retry evidence."""

    data: Mapping[str, Any]
    attempts: tuple[RetryAttempt, ...]
    duration_seconds: float
    status_code: int


@dataclass(frozen=True, slots=True)
class CreatomateBinaryCall:
    """One successful binary download plus complete retry evidence."""

    content: bytes
    content_type: str
    attempts: tuple[RetryAttempt, ...]
    duration_seconds: float
    status_code: int


@dataclass(frozen=True, slots=True)
class CreatomateRenderSnapshot:
    """Validated, secret-free projection of one Creatomate render response."""

    external_job_id: str
    provider_status: str
    status: RenderStatus
    output_url: str | None = None
    error_message: str | None = None
    output_format: str | None = None
    width: int | None = None
    height: int | None = None
    frame_rate: float | None = None
    duration: float | None = None
    file_size: int | None = None
    credits_used: float | None = None

    def safe_metadata(self) -> dict[str, Any]:
        values: dict[str, Any] = {
            "provider_status": self.provider_status,
        }
        for name in (
            "output_format",
            "width",
            "height",
            "frame_rate",
            "duration",
            "file_size",
            "credits_used",
        ):
            value = getattr(self, name)
            if value is not None:
                values[name] = value
        return values


@dataclass(slots=True)
class _RequestAttempt:
    success: bool
    response: CreatomateHttpResponse | None = None
    error: CreatomateApiError | None = None
    message: str = ""
    errors: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class CreatomateApiClient:
    """Perform authenticated render calls while keeping credentials out of results."""

    def __init__(
        self,
        config: CreatomateApiConfig,
        *,
        transport: CreatomateHttpTransport | None = None,
        retry_engine: RetryEngine | None = None,
        sleep_function: Callable[[float], None] | None = None,
        clock_function: Callable[[], float] | None = None,
    ) -> None:
        if not isinstance(config, CreatomateApiConfig):
            raise TypeError("config debe ser CreatomateApiConfig.")
        self.config = config
        self.transport = transport or UrllibCreatomateTransport()
        self.retry_engine = retry_engine or RetryEngine(
            policy=RetryPolicy(
                max_attempts=config.max_attempts,
                initial_delay_seconds=config.initial_retry_delay_seconds,
                max_delay_seconds=config.max_retry_delay_seconds,
                jitter_enabled=True,
            ),
            sleep_function=sleep_function,
            clock_function=clock_function,
        )

    def create_render(self, submission: RenderSubmission) -> CreatomateApiCall:
        """Submit PM5 RenderScript without mutating the PM4 submission."""

        if not isinstance(submission, RenderSubmission):
            raise TypeError("submission debe ser RenderSubmission.")
        payload = dict(submission.payload)
        if "metadata" in payload:
            raise CreatomateInvalidResponseError(
                "El payload RenderScript ya usa el campo reservado metadata.",
                operation="render.submit",
                category=CreatomateFailureCategory.DATA_VALIDATION,
                retryable=False,
            )
        payload["metadata"] = json.dumps(
            {
                "cips_submission_id": submission.submission_id,
                "cips_idempotency_key": submission.idempotency_key,
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return self._request_json(
            method="POST",
            url=f"{self.config.base_url}/renders",
            payload=payload,
            operation="render.submit",
            retry_transport_failures=False,
        )

    def get_render(self, external_job_id: str) -> CreatomateApiCall:
        """Retrieve current state for one previously submitted render."""

        normalized = str(external_job_id).strip()
        if not normalized:
            raise ValueError("external_job_id no puede estar vacío.")
        return self._request_json(
            method="GET",
            url=f"{self.config.base_url}/renders/{quote(normalized, safe='')}",
            payload=None,
            operation="render.status",
            retry_transport_failures=True,
        )

    def download_render(self, output_url: str) -> CreatomateBinaryCall:
        """Download a finished render without sending the project API key to the CDN."""

        try:
            _validate_download_url(output_url)
        except ValueError as error:
            raise self._invalid_response(
                str(error), operation="render.download"
            ) from error
        execution = self.retry_engine.execute(
            operation=lambda: self._binary_attempt(output_url),
            operation_name="creatomate.render.download",
            result_success_resolver=lambda result: result.success,
            error_resolver=lambda result: result.error,
            metadata_resolver=lambda result: result.metadata,
        )
        if not execution.success:
            raise self._execution_error(execution, "render.download")
        attempt = execution.result
        if not isinstance(attempt, _RequestAttempt) or attempt.response is None:
            raise self._invalid_response(
                "La descarga terminó sin una respuesta HTTP utilizable.",
                operation="render.download",
            )
        return CreatomateBinaryCall(
            content=attempt.response.body,
            content_type=str(
                attempt.response.headers.get("content-type", "")
            ).split(";", 1)[0].strip().casefold(),
            attempts=tuple(execution.attempts),
            duration_seconds=float(
                execution.metadata.get("total_duration_seconds", 0.0)
            ),
            status_code=attempt.response.status_code,
        )

    def parse_snapshot(
        self,
        data: Mapping[str, Any],
        *,
        expected_external_job_id: str | None = None,
    ) -> CreatomateRenderSnapshot:
        """Map the documented Creatomate lifecycle into PM4 states."""

        if not isinstance(data, Mapping):
            raise self._invalid_response("La respuesta de render debe ser un objeto JSON.")
        external_job_id = str(data.get("id", "") or "").strip()
        if not external_job_id:
            raise self._invalid_response("La respuesta de render no contiene id.")
        expected = str(expected_external_job_id or "").strip()
        if expected and external_job_id != expected:
            raise self._invalid_response("El id devuelto no coincide con el render consultado.")

        provider_status = str(data.get("status", "") or "").strip().casefold()
        status = _CREATOMATE_STATUS_MAP.get(provider_status)
        if status is None:
            raise self._invalid_response(
                f"Estado Creatomate no reconocido: {provider_status or '<vacío>'}."
            )

        output_url = _optional_text(data.get("url"))
        error_message = _optional_text(data.get("error_message"))
        if status is RenderStatus.SUCCEEDED:
            if output_url is None:
                raise self._invalid_response(
                    "Un render succeeded requiere URL de descarga."
                )
            try:
                _validate_download_url(output_url)
            except ValueError as error:
                raise self._invalid_response(str(error)) from error
        if status is RenderStatus.FAILED and error_message is None:
            error_message = "Creatomate indicó que el render falló."

        return CreatomateRenderSnapshot(
            external_job_id=external_job_id,
            provider_status=provider_status,
            status=status,
            output_url=output_url,
            error_message=(
                self.config.redact(error_message) if error_message is not None else None
            ),
            output_format=_optional_text(data.get("output_format")),
            width=_optional_positive_int(data.get("width")),
            height=_optional_positive_int(data.get("height")),
            frame_rate=_optional_positive_float(data.get("frame_rate")),
            duration=_optional_positive_float(data.get("duration")),
            file_size=_optional_positive_int(data.get("file_size")),
            credits_used=_extract_credits(data),
        )

    def _request_json(
        self,
        *,
        method: str,
        url: str,
        payload: Mapping[str, Any] | None,
        operation: str,
        retry_transport_failures: bool,
    ) -> CreatomateApiCall:
        body = None
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.config.api_key}",
        }
        if payload is not None:
            body = json.dumps(
                dict(payload),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8")
            headers["Content-Type"] = "application/json"

        execution = self.retry_engine.execute(
            operation=lambda: self._http_attempt(
                method=method,
                url=url,
                headers=headers,
                body=body,
                operation=operation,
                retry_transport_failures=retry_transport_failures,
            ),
            operation_name=f"creatomate.{operation}",
            result_success_resolver=lambda result: result.success,
            error_resolver=lambda result: result.error,
            metadata_resolver=lambda result: result.metadata,
        )
        if not execution.success:
            raise self._execution_error(execution, operation)
        attempt = execution.result
        if not isinstance(attempt, _RequestAttempt) or attempt.response is None:
            raise self._invalid_response(
                "La operación terminó sin una respuesta HTTP utilizable.",
                operation=operation,
            )
        data = self._decode_json_response(attempt.response, operation)
        return CreatomateApiCall(
            data=data,
            attempts=tuple(execution.attempts),
            duration_seconds=float(
                execution.metadata.get("total_duration_seconds", 0.0)
            ),
            status_code=attempt.response.status_code,
        )

    def _http_attempt(
        self,
        *,
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: bytes | None,
        operation: str,
        retry_transport_failures: bool,
    ) -> _RequestAttempt:
        try:
            response = self.transport.request(
                method=method,
                url=url,
                headers=headers,
                body=body,
                timeout_seconds=self.config.request_timeout_seconds,
                max_response_bytes=self.config.max_json_bytes,
            )
        except CreatomateTransportError as error:
            if operation == "render.submit" and not retry_transport_failures:
                resolved: CreatomateApiError = CreatomateAmbiguousSubmissionError(
                    "El envío terminó sin respuesta; no se repetirá automáticamente para evitar un render duplicado.",
                    operation=operation,
                    category=CreatomateFailureCategory.PROVIDER_EXTERNAL,
                    retryable=False,
                    ambiguous_submission=True,
                )
            else:
                resolved = CreatomateTransientError(
                    self.config.redact(error),
                    operation=operation,
                    category=CreatomateFailureCategory.PROVIDER_EXTERNAL,
                    retryable=True,
                )
            return _failed_attempt(resolved)
        return self._response_attempt(response, operation)

    def _binary_attempt(self, output_url: str) -> _RequestAttempt:
        try:
            response = self.transport.request(
                method="GET",
                url=output_url,
                headers={"Accept": "video/mp4,application/octet-stream"},
                body=None,
                timeout_seconds=self.config.download_timeout_seconds,
                max_response_bytes=self.config.max_download_bytes,
            )
        except CreatomateTransportError as error:
            return _failed_attempt(
                CreatomateTransientError(
                    self.config.redact(error),
                    operation="render.download",
                    category=CreatomateFailureCategory.PROVIDER_EXTERNAL,
                    retryable=True,
                )
            )
        return self._response_attempt(response, "render.download")

    def _response_attempt(
        self,
        response: CreatomateHttpResponse,
        operation: str,
    ) -> _RequestAttempt:
        if 200 <= response.status_code <= 299:
            return _RequestAttempt(
                success=True,
                response=response,
                message="Solicitud Creatomate completada.",
                metadata={"status_code": response.status_code},
            )
        error = self._classify_http_error(response, operation)
        return _failed_attempt(error)

    def _classify_http_error(
        self,
        response: CreatomateHttpResponse,
        operation: str,
    ) -> CreatomateApiError:
        status = int(response.status_code)
        provider_message = self._safe_provider_message(response.body)
        message = f"Creatomate devolvió HTTP {status}"
        if provider_message:
            message += f": {provider_message}"
        message += "."
        retry_after = _retry_after_seconds(response.headers.get("retry-after"))

        if status in {401, 403}:
            return CreatomateAuthenticationError(
                message,
                operation=operation,
                category=CreatomateFailureCategory.CONFIGURATION,
                retryable=False,
                status_code=status,
            )
        if status == 429:
            return CreatomateRateLimitError(
                message,
                operation=operation,
                category=CreatomateFailureCategory.QUOTA,
                retryable=True,
                status_code=status,
                retry_after_seconds=retry_after,
            )
        if status == 402 or any(
            marker in provider_message.casefold()
            for marker in ("credit", "quota", "budget")
        ):
            return CreatomateTerminalError(
                message,
                operation=operation,
                category=CreatomateFailureCategory.QUOTA,
                retryable=False,
                status_code=status,
            )
        if status in _RETRYABLE_HTTP_STATUS or 500 <= status <= 599:
            return CreatomateTransientError(
                message,
                operation=operation,
                category=CreatomateFailureCategory.PROVIDER_EXTERNAL,
                retryable=True,
                status_code=status,
                retry_after_seconds=retry_after,
            )
        category = (
            CreatomateFailureCategory.DATA_VALIDATION
            if status in _DATA_HTTP_STATUS
            else CreatomateFailureCategory.PROVIDER_EXTERNAL
        )
        return CreatomateTerminalError(
            message,
            operation=operation,
            category=category,
            retryable=False,
            status_code=status,
        )

    def _decode_json_response(
        self,
        response: CreatomateHttpResponse,
        operation: str,
    ) -> Mapping[str, Any]:
        try:
            decoded = json.loads(response.body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise self._invalid_response(
                f"Creatomate devolvió JSON inválido: {type(error).__name__}.",
                operation=operation,
            ) from error
        if isinstance(decoded, list):
            if len(decoded) != 1 or not isinstance(decoded[0], Mapping):
                raise self._invalid_response(
                    "La respuesta de creación debe contener exactamente un render.",
                    operation=operation,
                )
            decoded = decoded[0]
        if not isinstance(decoded, Mapping):
            raise self._invalid_response(
                "La respuesta de Creatomate debe ser un objeto JSON.",
                operation=operation,
            )
        return dict(decoded)

    def _safe_provider_message(self, body: bytes) -> str:
        try:
            value = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return ""
        if not isinstance(value, Mapping):
            return ""
        for key in ("error_message", "message", "error"):
            candidate = value.get(key)
            if isinstance(candidate, str) and candidate.strip():
                return self.config.redact(candidate.strip())[:500]
        return ""

    def _execution_error(self, execution: Any, operation: str) -> CreatomateApiError:
        result = getattr(execution, "result", None)
        error = getattr(result, "error", None)
        if isinstance(error, CreatomateApiError):
            return error.with_attempts(tuple(execution.attempts))
        return CreatomateTransientError(
            "La operación Creatomate falló sin un error estructurado.",
            operation=operation,
            category=CreatomateFailureCategory.PROVIDER_EXTERNAL,
            retryable=False,
            attempts=tuple(getattr(execution, "attempts", ())),
        )

    def _invalid_response(
        self,
        message: str,
        *,
        operation: str = "render.status",
    ) -> CreatomateInvalidResponseError:
        return CreatomateInvalidResponseError(
            self.config.redact(message),
            operation=operation,
            category=CreatomateFailureCategory.PROVIDER_EXTERNAL,
            retryable=False,
        )


def _failed_attempt(error: CreatomateApiError) -> _RequestAttempt:
    metadata: dict[str, Any] = {
        "retryable": error.retryable,
        "category": error.category.value,
    }
    if error.status_code is not None:
        metadata["status_code"] = error.status_code
    if error.retry_after_seconds is not None:
        metadata["retry_after_seconds"] = error.retry_after_seconds
    return _RequestAttempt(
        success=False,
        error=error,
        message=str(error),
        errors=[str(error)],
        metadata=metadata,
    )


def _validate_download_url(value: str) -> None:
    parsed = urlparse(str(value).strip())
    host = str(parsed.hostname or "").casefold()
    if parsed.scheme != "https" or not host:
        raise ValueError("La URL de descarga de Creatomate debe usar HTTPS.")
    allowed_hosts = ("creatomate.com", "backblazeb2.com")
    if not any(host == item or host.endswith(f".{item}") for item in allowed_hosts):
        raise ValueError("La URL de descarga no pertenece a Creatomate.")


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _optional_positive_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _optional_positive_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) and number > 0.0 else None


def _extract_credits(data: Mapping[str, Any]) -> float | None:
    for key in ("credits_used", "credit_usage", "credits"):
        value = data.get(key)
        if value is None or isinstance(value, bool):
            continue
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(number) and number >= 0.0:
            return number
    return None


def _retry_after_seconds(value: str | None) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        seconds = float(text)
    except ValueError:
        try:
            moment = parsedate_to_datetime(text)
            if moment.tzinfo is None:
                moment = moment.replace(tzinfo=timezone.utc)
            seconds = (moment - datetime.now(timezone.utc)).total_seconds()
        except (TypeError, ValueError, OverflowError):
            return None
    if not math.isfinite(seconds) or seconds < 0.0:
        return None
    return round(seconds, 3)


__all__ = [
    "CreatomateApiCall",
    "CreatomateApiClient",
    "CreatomateBinaryCall",
    "CreatomateRenderSnapshot",
]
