from __future__ import annotations
"""
=========================================================
Proyecto : CIPS
Release  : 0.8
Build    : 059
Archivo  : openai_provider.py
Estado   : RELEASE
=========================================================

Implementa el proveedor OpenAI mediante el SDK oficial.

Responsabilidades de hardening F4.3:
- preservar el contrato LLMProvider existente;
- aplicar timeout explícito al cliente;
- desactivar retries internos del SDK;
- delegar retries únicamente a RetryEngine/RetryPolicy de CIPS;
- clasificar fallos temporales y permanentes;
- proteger credenciales en mensajes de error;
- mantener un límite explícito de tokens de salida;
- no realizar llamadas reales durante pruebas.
"""

import os
import re
from typing import Any

try:
    from openai import OpenAI
except Exception:
    OpenAI = None

from llm_provider import LLMProvider, ProviderResult
from retry_engine import RetryEngine
from retry_policy import RetryPolicy
from runtime_models import LLMResponse


class OpenAIProvider(LLMProvider):
    provider_name = "openai"
    model_name = "gpt-5"
    supports_streaming = False
    supports_system_prompt = True
    supports_images = False
    supports_tools = False

    RETRYABLE_EXCEPTION_NAMES = {
        "APIConnectionError",
        "APITimeoutError",
        "RateLimitError",
        "InternalServerError",
        "TimeoutError",
        "ConnectionError",
        "ConnectionResetError",
        "ConnectionAbortedError",
        "ConnectionRefusedError",
    }

    NON_RETRYABLE_EXCEPTION_NAMES = {
        "BadRequestError",
        "AuthenticationError",
        "PermissionDeniedError",
        "NotFoundError",
        "UnprocessableEntityError",
    }

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "gpt-5",
        temperature: float = 0.2,
        max_tokens: int = 4000,
        timeout: int = 120,
        retry_enabled: bool = True,
        max_attempts: int = 3,
        initial_retry_delay_seconds: float = 5.0,
        retry_backoff_multiplier: float = 2.0,
        max_retry_delay_seconds: float = 30.0,
        retry_jitter_enabled: bool = True,
        retry_policy: RetryPolicy | None = None,
        retry_engine: RetryEngine | None = None,
        api_key_env: str = "OPENAI_API_KEY",
    ) -> None:
        self.api_key_env = self._normalize_api_key_env(api_key_env)
        self.api_key = api_key or os.getenv(self.api_key_env)
        self.model_name = self._normalize_model(model)
        self.temperature = self._normalize_temperature(temperature)
        self.max_tokens = self._normalize_positive_int(
            max_tokens,
            default=4000,
        )
        self.timeout = self._normalize_positive_int(
            timeout,
            default=120,
        )

        self.retry_enabled = bool(retry_enabled)
        self.retry_policy = retry_policy or RetryPolicy(
            max_attempts=max_attempts,
            initial_delay_seconds=initial_retry_delay_seconds,
            backoff_multiplier=retry_backoff_multiplier,
            max_delay_seconds=max_retry_delay_seconds,
            jitter_enabled=retry_jitter_enabled,
        )
        self.retry_engine = retry_engine or RetryEngine(
            policy=self.retry_policy,
        )

        self._client = None

    # --------------------------------------------------
    # Configuración pública
    # --------------------------------------------------
    def configure(self, **kwargs: Any) -> None:
        """Actualiza opciones conocidas preservando compatibilidad."""

        reset_client = False

        if "api_key" in kwargs:
            new_api_key = kwargs.get("api_key")
            if new_api_key != self.api_key:
                self.api_key = new_api_key
                reset_client = True

        if "api_key_env" in kwargs:
            new_env = self._normalize_api_key_env(
                kwargs.get("api_key_env")
            )
            if new_env != self.api_key_env:
                self.api_key_env = new_env
                if not self.api_key:
                    self.api_key = os.getenv(new_env)
                reset_client = True

        if "model" in kwargs:
            self.model_name = self._normalize_model(
                kwargs.get("model")
            )
        elif "model_name" in kwargs:
            self.model_name = self._normalize_model(
                kwargs.get("model_name")
            )

        if "temperature" in kwargs:
            self.temperature = self._normalize_temperature(
                kwargs.get("temperature")
            )

        if "max_tokens" in kwargs:
            self.max_tokens = self._normalize_positive_int(
                kwargs.get("max_tokens"),
                default=self.max_tokens,
            )

        if "timeout" in kwargs:
            new_timeout = self._normalize_positive_int(
                kwargs.get("timeout"),
                default=self.timeout,
            )
            if new_timeout != self.timeout:
                self.timeout = new_timeout
                reset_client = True

        if "retry_enabled" in kwargs:
            self.retry_enabled = bool(
                kwargs.get("retry_enabled")
            )

        if reset_client:
            self._client = None

    # --------------------------------------------------
    # Cliente
    # --------------------------------------------------
    def get_client(self):
        """
        Crea y reutiliza el cliente OpenAI.

        CIPS es el único propietario de la política de retry, por lo que
        el retry interno del SDK queda explícitamente desactivado.
        """

        if self._client is not None:
            return self._client

        if OpenAI is None:
            raise ImportError(
                "No está instalado el paquete openai."
            )

        self._client = OpenAI(
            api_key=self.api_key,
            timeout=float(self.timeout),
            max_retries=0,
        )
        return self._client

    # --------------------------------------------------
    # API pública
    # --------------------------------------------------
    def list_models(self) -> list[str]:
        return ["gpt-5", "gpt-5-mini"]

    def health_check(self) -> bool:
        return OpenAI is not None

    def generate(
        self,
        prompt: str,
        metadata: dict[str, Any] | None = None,
    ) -> ProviderResult:
        prompt_errors = self.validate_prompt(prompt)
        if prompt_errors:
            return ProviderResult.fail(
                message="El prompt para OpenAI no es válido.",
                errors=prompt_errors,
                metadata={
                    **self._build_metadata(metadata),
                    "retryable": False,
                    "retry_skipped": True,
                    "retry_skip_reason": "invalid_prompt",
                },
            )

        if not self.api_key:
            return ProviderResult.fail(
                message=(
                    "No se encontró una clave API para OpenAI."
                ),
                errors=[
                    "Configura la variable de entorno "
                    f"{self.api_key_env} antes de ejecutar "
                    "el proveedor automático."
                ],
                metadata={
                    **self._build_metadata(metadata),
                    "missing_credentials": True,
                    "required_environment_variable": (
                        self.api_key_env
                    ),
                    "retryable": False,
                    "retry_skipped": True,
                    "retry_skip_reason": "missing_credentials",
                },
            )

        if not self.retry_enabled:
            result = self._generate_once(
                prompt=prompt,
                metadata=metadata,
            )
            result.metadata.update(
                {
                    "retry": {
                        "enabled": False,
                        "attempts_count": 1,
                        "retries_count": 0,
                    }
                }
            )
            return result

        retry_result = self.retry_engine.execute(
            operation=lambda: self._generate_once(
                prompt=prompt,
                metadata=metadata,
            ),
            operation_name=(
                f"{self.provider_name}."
                f"{self.model_name}.generate"
            ),
            result_success_resolver=lambda result: bool(
                result.success
            ),
            error_resolver=self._resolve_provider_error,
            metadata_resolver=lambda result: dict(
                result.metadata
            ),
        )

        provider_result = retry_result.result
        if isinstance(provider_result, ProviderResult):
            provider_result.metadata.update(
                {
                    "retry_enabled": True,
                    "retry_attempts": (
                        retry_result.metadata.get(
                            "attempts_count",
                            0,
                        )
                    ),
                    "retry_count": (
                        retry_result.metadata.get(
                            "retries_count",
                            0,
                        )
                    ),
                    "retry_exhausted": (
                        retry_result.metadata.get(
                            "exhausted",
                            False,
                        )
                    ),
                    "succeeded_after_retry": (
                        retry_result.metadata.get(
                            "succeeded_after_retry",
                            False,
                        )
                    ),
                }
            )
            return provider_result

        return ProviderResult.fail(
            message=(
                "RetryEngine terminó sin devolver un "
                "ProviderResult válido."
            ),
            errors=list(retry_result.errors),
            warnings=list(retry_result.warnings),
            metadata={
                **self._build_metadata(metadata),
                "retry_enabled": True,
                "retry_engine_failure": True,
                **retry_result.metadata,
            },
        )

    # --------------------------------------------------
    # Solicitud individual
    # --------------------------------------------------
    def _generate_once(
        self,
        prompt: str,
        metadata: dict[str, Any] | None,
    ) -> ProviderResult:
        try:
            client = self.get_client()
            response = client.responses.create(
                model=self.model_name,
                input=self.prepare_prompt(prompt),
                max_output_tokens=self.max_tokens,
            )

            response_text = str(
                getattr(response, "output_text", "") or ""
            ).strip()
            usage_metadata = self._extract_usage_metadata(
                response
            )
            request_metadata = self._extract_request_metadata(
                response
            )

            if not response_text:
                return ProviderResult.fail(
                    message=(
                        "OpenAI respondió, pero no devolvió "
                        "contenido de texto."
                    ),
                    errors=[
                        "La respuesta no contiene texto utilizable."
                    ],
                    metadata={
                        **self._build_metadata(metadata),
                        **usage_metadata,
                        **request_metadata,
                        "empty_response": True,
                        "retryable": False,
                    },
                )

            llm_response = LLMResponse(
                content=response_text,
                model=self.model_name,
                metadata={
                    **dict(metadata or {}),
                    "provider": self.provider_name,
                    "mode": "automatic",
                    "prompt_characters": len(prompt),
                    "response_characters": len(response_text),
                    **usage_metadata,
                    **request_metadata,
                },
            )

            return ProviderResult.ok(
                response=llm_response,
                message=(
                    "Respuesta obtenida correctamente desde OpenAI."
                ),
                metadata={
                    **self._build_metadata(metadata),
                    "prompt_characters": len(prompt),
                    "response_characters": len(response_text),
                    **usage_metadata,
                    **request_metadata,
                    "retryable": False,
                },
            )

        except ImportError:
            return ProviderResult.fail(
                message="El SDK de OpenAI no está instalado.",
                errors=[
                    "Instala la dependencia oficial 'openai'."
                ],
                metadata={
                    **self._build_metadata(metadata),
                    "missing_dependency": "openai",
                    "retryable": False,
                },
            )
        except Exception as error:
            classification = self._classify_exception(error)
            return ProviderResult.fail(
                message=(
                    "OpenAI no pudo completar la solicitud."
                ),
                errors=[self._safe_error_message(error)],
                metadata={
                    **self._build_metadata(metadata),
                    "exception_type": (
                        error.__class__.__name__
                    ),
                    "status_code": classification[
                        "status_code"
                    ],
                    "retryable": classification[
                        "retryable"
                    ],
                    "error_classification": classification[
                        "classification"
                    ],
                    "classification_reason": classification[
                        "reason"
                    ],
                    "classification_rule": classification[
                        "matched_rule"
                    ],
                },
            )

    # --------------------------------------------------
    # Clasificación de errores
    # --------------------------------------------------
    def _classify_exception(
        self,
        error: Exception,
    ) -> dict[str, Any]:
        status_code = self._extract_status_code(error)
        exception_name = error.__class__.__name__

        if exception_name in self.RETRYABLE_EXCEPTION_NAMES:
            return {
                "status_code": status_code,
                "retryable": True,
                "classification": "temporary",
                "reason": (
                    "El SDK de OpenAI reportó un fallo "
                    "temporal de red, timeout, límite o servidor."
                ),
                "matched_rule": (
                    "openai_retryable_exception:"
                    + exception_name
                ),
            }

        if exception_name in self.NON_RETRYABLE_EXCEPTION_NAMES:
            return {
                "status_code": status_code,
                "retryable": False,
                "classification": "permanent",
                "reason": (
                    "El SDK de OpenAI reportó un fallo "
                    "permanente de solicitud, autenticación o acceso."
                ),
                "matched_rule": (
                    "openai_non_retryable_exception:"
                    + exception_name
                ),
            }

        decision = self.retry_policy.should_retry(
            error=error,
            status_code=status_code,
        )
        return {
            "status_code": decision.status_code,
            "retryable": decision.retryable,
            "classification": (
                "temporary"
                if decision.retryable
                else "permanent"
            ),
            "reason": decision.reason,
            "matched_rule": decision.matched_rule,
        }

    def _extract_status_code(
        self,
        error: Exception,
    ) -> int | None:
        for attribute_name in (
            "status_code",
            "code",
            "status",
            "http_status",
        ):
            normalized = self._normalize_status_code(
                getattr(error, attribute_name, None)
            )
            if normalized is not None:
                return normalized

        response = getattr(error, "response", None)
        if response is not None:
            normalized = self._normalize_status_code(
                getattr(response, "status_code", None)
            )
            if normalized is not None:
                return normalized

        message = str(error)
        for pattern in (
            r"\b([45]\d{2})\b",
            r"status[_\s:=]+([45]\d{2})",
        ):
            match = re.search(
                pattern,
                message,
                flags=re.IGNORECASE,
            )
            if match:
                return int(match.group(1))

        return None

    def _resolve_provider_error(
        self,
        result: ProviderResult,
    ) -> str:
        errors = getattr(result, "errors", [])
        if isinstance(errors, list) and errors:
            return "\n".join(str(error) for error in errors)

        return str(getattr(result, "message", ""))

    # --------------------------------------------------
    # Metadata y seguridad
    # --------------------------------------------------
    def _build_metadata(
        self,
        metadata: dict[str, Any] | None,
    ) -> dict[str, Any]:
        return {
            **dict(metadata or {}),
            "provider": self.provider_name,
            "model": self.model_name,
            "temperature": self.temperature,
            "max_output_tokens": self.max_tokens,
            "timeout_seconds": self.timeout,
            "credentials_available": bool(self.api_key),
            "retry_enabled": self.retry_enabled,
            "max_attempts": self.retry_policy.max_attempts,
            "sdk_retries_enabled": False,
        }

    def _safe_error_message(
        self,
        error: Exception,
    ) -> str:
        message = str(error).strip()
        if not message:
            return error.__class__.__name__

        if self.api_key:
            message = message.replace(
                self.api_key,
                "[REDACTED]",
            )
        return message

    def _extract_usage_metadata(
        self,
        response: Any,
    ) -> dict[str, Any]:
        usage = getattr(response, "usage", None)
        if usage is None:
            return {}

        metadata: dict[str, Any] = {}
        field_map = {
            "prompt_tokens": "input_tokens",
            "response_tokens": "output_tokens",
            "total_tokens": "total_tokens",
        }
        for output_name, attribute_name in field_map.items():
            value = getattr(usage, attribute_name, None)
            if value is not None:
                metadata[output_name] = value

        output_details = getattr(
            usage,
            "output_tokens_details",
            None,
        )
        reasoning_tokens = getattr(
            output_details,
            "reasoning_tokens",
            None,
        )
        if reasoning_tokens is not None:
            metadata["thinking_tokens"] = reasoning_tokens

        return metadata

    def _extract_request_metadata(
        self,
        response: Any,
    ) -> dict[str, Any]:
        request_id = getattr(response, "_request_id", None)
        if request_id:
            return {"request_id": str(request_id)}
        return {}

    # --------------------------------------------------
    # Normalización
    # --------------------------------------------------
    def _normalize_status_code(
        self,
        value: Any,
    ) -> int | None:
        if value is None:
            return None

        raw_value = getattr(value, "value", value)
        try:
            status_code = int(raw_value)
        except (TypeError, ValueError):
            match = re.search(
                r"\b([45]\d{2})\b",
                str(raw_value),
            )
            if not match:
                return None
            status_code = int(match.group(1))

        if 100 <= status_code <= 599:
            return status_code
        return None

    def _normalize_model(self, value: Any) -> str:
        if not isinstance(value, str):
            raise TypeError("model debe ser una cadena.")
        normalized = value.strip()
        if not normalized:
            raise ValueError("model no puede estar vacío.")
        return normalized

    def _normalize_api_key_env(self, value: Any) -> str:
        normalized = str(value or "OPENAI_API_KEY").strip()
        return normalized or "OPENAI_API_KEY"

    def _normalize_temperature(self, value: Any) -> float:
        try:
            temperature = float(value)
        except (TypeError, ValueError):
            return 0.2
        return min(max(temperature, 0.0), 2.0)

    def _normalize_positive_int(
        self,
        value: Any,
        default: int,
    ) -> int:
        try:
            number = int(value)
        except (TypeError, ValueError):
            return default
        return number if number > 0 else default

    def get_provider_info(self) -> dict[str, Any]:
        return {
            "provider": self.provider_name,
            "model": self.model_name,
            "retry_enabled": self.retry_enabled,
            "max_attempts": self.retry_policy.max_attempts,
            "initial_retry_delay_seconds": (
                self.retry_policy.initial_delay_seconds
            ),
            "retry_backoff_multiplier": (
                self.retry_policy.backoff_multiplier
            ),
            "max_retry_delay_seconds": (
                self.retry_policy.max_delay_seconds
            ),
            "retry_jitter_enabled": (
                self.retry_policy.jitter_enabled
            ),
            "timeout_seconds": self.timeout,
            "max_output_tokens": self.max_tokens,
            "sdk_retries_enabled": False,
        }
