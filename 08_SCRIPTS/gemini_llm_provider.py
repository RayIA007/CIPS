"""
=========================================================
Proyecto : CIPS
Release  : 0.8
Build    : 058
Archivo  : gemini_llm_provider.py
Estado   : RELEASE
=========================================================

Implementa el proveedor Google Gemini mediante el SDK
oficial google-genai, incorporando reintentos automáticos
para fallos temporales.

Funciones principales:
- obtener la clave desde variables de entorno;
- controlar temperatura y tokens de salida;
- configurar el nivel de razonamiento;
- generar LLMResponse;
- registrar métricas de uso;
- proteger credenciales en mensajes de error;
- clasificar errores temporales y permanentes;
- aplicar RetryEngine sin duplicar lógica del proveedor.
"""

import os
import re
from typing import Any

from llm_provider import LLMProvider, ProviderResult
from retry_engine import RetryEngine
from retry_policy import RetryPolicy
from runtime_models import LLMResponse


class GeminiLLMProvider(LLMProvider):
    """
    Proveedor automático para Google Gemini.

    Variables de entorno admitidas:

        GOOGLE_API_KEY
        GEMINI_API_KEY

    GOOGLE_API_KEY tiene prioridad cuando ambas existen.
    """

    provider_name = "gemini"

    VALID_THINKING_LEVELS = {
        "minimal",
        "low",
        "medium",
        "high",
    }

    RETRYABLE_STATUS_CODES = {
        408,
        409,
        425,
        429,
        500,
        502,
        503,
        504,
    }

    NON_RETRYABLE_STATUS_CODES = {
        400,
        401,
        403,
        404,
        405,
        406,
        410,
        422,
    }

    def __init__(
        self,
        model: str = "gemini-3.5-flash",
        api_key: str | None = None,
        api_key_env: str = "GOOGLE_API_KEY",
        temperature: float = 0.2,
        max_output_tokens: int | None = None,
        timeout_seconds: int = 60,
        thinking_level: str = "low",
        retry_enabled: bool = True,
        max_attempts: int = 3,
        initial_retry_delay_seconds: float = 5.0,
        retry_backoff_multiplier: float = 2.0,
        max_retry_delay_seconds: float = 30.0,
        retry_jitter_enabled: bool = True,
        retry_policy: RetryPolicy | None = None,
        retry_engine: RetryEngine | None = None,
    ) -> None:
        """
        Inicializa el proveedor Gemini.

        Args:
            model:
                Identificador oficial del modelo.

            api_key:
                Credencial explícita opcional.

            api_key_env:
                Variable de entorno principal.

            temperature:
                Variación permitida en la generación.

            max_output_tokens:
                Presupuesto máximo de tokens de salida.

            timeout_seconds:
                Tiempo máximo previsto para la solicitud.

            thinking_level:
                Nivel de razonamiento:
                minimal, low, medium o high.

            retry_enabled:
                Activa o desactiva reintentos automáticos.

            max_attempts:
                Cantidad total de intentos, incluido el primero.

            initial_retry_delay_seconds:
                Espera antes del primer reintento.

            retry_backoff_multiplier:
                Multiplicador de espera progresiva.

            max_retry_delay_seconds:
                Límite máximo de espera.

            retry_jitter_enabled:
                Introduce variación aleatoria en las esperas.

            retry_policy:
                Política personalizada opcional.

            retry_engine:
                Engine personalizado opcional.
        """

        self.model_name = self._normalize_model(
            model
        )

        self.api_key = (
            api_key
            or os.getenv(api_key_env)
            or os.getenv("GEMINI_API_KEY")
        )

        self.api_key_env = api_key_env

        self.temperature = (
            self._normalize_temperature(
                temperature
            )
        )

        self.max_output_tokens = (
            self._normalize_optional_int(
                max_output_tokens
            )
        )

        self.timeout_seconds = (
            self._normalize_positive_int(
                timeout_seconds,
                default=60,
            )
        )

        self.thinking_level = (
            self._normalize_thinking_level(
                thinking_level
            )
        )

        self.retry_enabled = bool(
            retry_enabled
        )

        self.retry_policy = (
            retry_policy
            or RetryPolicy(
                max_attempts=max_attempts,
                initial_delay_seconds=(
                    initial_retry_delay_seconds
                ),
                backoff_multiplier=(
                    retry_backoff_multiplier
                ),
                max_delay_seconds=(
                    max_retry_delay_seconds
                ),
                jitter_enabled=(
                    retry_jitter_enabled
                ),
            )
        )

        self.retry_engine = (
            retry_engine
            or RetryEngine(
                policy=self.retry_policy
            )
        )

        self._client = None

    # --------------------------------------------------
    # API pública
    # --------------------------------------------------

    def generate(
        self,
        prompt: str,
        metadata: dict[str, Any] | None = None,
    ) -> ProviderResult:
        """
        Envía el prompt a Gemini.

        Cuando retry_enabled es True, los errores temporales
        son procesados mediante RetryEngine.
        """

        prompt_errors = self.validate_prompt(
            prompt
        )

        if prompt_errors:
            return ProviderResult.fail(
                message=(
                    "El prompt para Gemini no es válido."
                ),
                errors=prompt_errors,
                metadata={
                    **self._build_metadata(metadata),
                    "retryable": False,
                    "retry_skipped": True,
                    "retry_skip_reason": (
                        "invalid_prompt"
                    ),
                },
            )

        if not self.api_key:
            return ProviderResult.fail(
                message=(
                    "No se encontró una clave API "
                    "para Gemini."
                ),
                errors=[
                    "Configura la variable de entorno "
                    "GOOGLE_API_KEY antes de ejecutar "
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
                    "retry_skip_reason": (
                        "missing_credentials"
                    ),
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
            result_success_resolver=lambda result: (
                bool(result.success)
            ),
            error_resolver=self._resolve_provider_error,
            metadata_resolver=lambda result: (
                dict(result.metadata)
            ),
        )

        provider_result = retry_result.result

        if isinstance(
            provider_result,
            ProviderResult,
        ):
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
                "RetryEngine terminó sin devolver "
                "un ProviderResult válido."
            ),
            errors=list(
                retry_result.errors
            ),
            warnings=list(
                retry_result.warnings
            ),
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
        """
        Ejecuta una única solicitud a Gemini.

        RetryEngine es responsable de decidir si este método
        debe invocarse nuevamente.
        """

        try:
            client = self._get_client()

            generation_config = (
                self._build_generation_config()
            )

            response = client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=generation_config,
            )

            response_text = (
                self._extract_response_text(
                    response
                )
            )

            usage_metadata = (
                self._extract_usage_metadata(
                    response
                )
            )

            finish_metadata = (
                self._extract_finish_metadata(
                    response
                )
            )

            if not response_text:
                return ProviderResult.fail(
                    message=(
                        "Gemini respondió, pero no devolvió "
                        "contenido de texto."
                    ),
                    errors=[
                        "La respuesta no contiene "
                        "texto utilizable."
                    ],
                    metadata={
                        **self._build_metadata(metadata),
                        **usage_metadata,
                        **finish_metadata,
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
                    "thinking_level": (
                        self.thinking_level
                    ),
                    "prompt_characters": len(prompt),
                    "response_characters": len(
                        response_text
                    ),
                    **usage_metadata,
                    **finish_metadata,
                },
            )

            return ProviderResult.ok(
                response=llm_response,
                message=(
                    "Respuesta obtenida correctamente "
                    "desde Google Gemini."
                ),
                metadata={
                    **self._build_metadata(metadata),
                    "prompt_characters": len(prompt),
                    "response_characters": len(
                        response_text
                    ),
                    **usage_metadata,
                    **finish_metadata,
                    "retryable": False,
                },
            )

        except ImportError:
            return ProviderResult.fail(
                message=(
                    "El SDK de Google Gemini "
                    "no está instalado."
                ),
                errors=[
                    "Instala la dependencia con: "
                    "python -m pip install -U google-genai"
                ],
                metadata={
                    **self._build_metadata(metadata),
                    "missing_dependency": "google-genai",
                    "retryable": False,
                },
            )

        except Exception as error:
            classification = (
                self._classify_exception(
                    error
                )
            )

            return ProviderResult.fail(
                message=(
                    "Google Gemini no pudo completar "
                    "la solicitud."
                ),
                errors=[
                    self._safe_error_message(
                        error
                    )
                ],
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
                    "error_classification": (
                        classification[
                            "classification"
                        ]
                    ),
                    "classification_reason": (
                        classification[
                            "reason"
                        ]
                    ),
                },
            )

    # --------------------------------------------------
    # Clasificación de errores
    # --------------------------------------------------

    def _classify_exception(
        self,
        error: Exception,
    ) -> dict[str, Any]:
        """
        Clasifica una excepción de Gemini.

        RetryPolicy realiza la decisión definitiva, pero el
        Provider aporta señales explícitas y seguras.
        """

        status_code = self._extract_status_code(
            error
        )

        safe_message = self._safe_error_message(
            error
        )

        decision = self.retry_policy.should_retry(
            error=safe_message,
            status_code=status_code,
            metadata={
                "exception_type": (
                    error.__class__.__name__
                ),
            },
        )

        classification = (
            "temporary"
            if decision.retryable
            else "permanent"
        )

        return {
            "status_code": decision.status_code,
            "retryable": decision.retryable,
            "classification": classification,
            "reason": decision.reason,
            "matched_rule": decision.matched_rule,
        }

    def _extract_status_code(
        self,
        error: Exception,
    ) -> int | None:
        """
        Obtiene un código HTTP desde la excepción o su mensaje.
        """

        for attribute_name in (
            "status_code",
            "code",
            "status",
            "http_status",
        ):
            value = getattr(
                error,
                attribute_name,
                None,
            )

            normalized = (
                self._normalize_status_code(
                    value
                )
            )

            if normalized is not None:
                return normalized

        message = str(
            error
        )

        patterns = (
            r"\b([45]\d{2})\b",
            r"'code'\s*:\s*([45]\d{2})",
            r'"code"\s*:\s*([45]\d{2})',
            r"status[_\s:=]+([45]\d{2})",
        )

        for pattern in patterns:
            match = re.search(
                pattern,
                message,
                flags=re.IGNORECASE,
            )

            if match:
                return int(
                    match.group(1)
                )

        return None

    def _resolve_provider_error(
        self,
        result: ProviderResult,
    ) -> str:
        """
        Extrae texto suficiente para que RetryPolicy clasifique
        un ProviderResult fallido.
        """

        errors = getattr(
            result,
            "errors",
            [],
        )

        if isinstance(
            errors,
            list,
        ) and errors:
            return "\n".join(
                str(error)
                for error in errors
            )

        return str(
            getattr(
                result,
                "message",
                "",
            )
        )

    # --------------------------------------------------
    # Cliente y configuración
    # --------------------------------------------------

    def _get_client(self):
        """
        Crea el cliente únicamente cuando se necesita.
        """

        if self._client is not None:
            return self._client

        try:
            from google import genai

        except ImportError as error:
            raise ImportError(
                "No está instalado el paquete google-genai."
            ) from error

        self._client = genai.Client(
            api_key=self.api_key
        )

        return self._client

    def _build_generation_config(self):
        """
        Construye la configuración de generación.
        """

        try:
            from google.genai import types

        except ImportError as error:
            raise ImportError(
                "No está instalado el paquete google-genai."
            ) from error

        config_data: dict[str, Any] = {
            "temperature": self.temperature,
            "thinking_config": types.ThinkingConfig(
                thinking_level=self.thinking_level
            ),
        }

        if self.max_output_tokens is not None:
            config_data["max_output_tokens"] = (
                self.max_output_tokens
            )

        return types.GenerateContentConfig(
            **config_data
        )

    # --------------------------------------------------
    # Extracción de respuesta
    # --------------------------------------------------

    def _extract_response_text(
        self,
        response,
    ) -> str:
        """
        Extrae el texto visible de la respuesta.
        """

        direct_text = getattr(
            response,
            "text",
            None,
        )

        if direct_text:
            return str(
                direct_text
            ).strip()

        candidates = getattr(
            response,
            "candidates",
            None,
        )

        if not candidates:
            return ""

        text_parts: list[str] = []

        for candidate in candidates:
            content = getattr(
                candidate,
                "content",
                None,
            )

            parts = getattr(
                content,
                "parts",
                None,
            )

            if not parts:
                continue

            for part in parts:
                text = getattr(
                    part,
                    "text",
                    None,
                )

                is_thought = bool(
                    getattr(
                        part,
                        "thought",
                        False,
                    )
                )

                if text and not is_thought:
                    text_parts.append(
                        str(text).strip()
                    )

        return "\n\n".join(
            part
            for part in text_parts
            if part
        ).strip()

    def _extract_usage_metadata(
        self,
        response,
    ) -> dict[str, Any]:
        """
        Extrae métricas de tokens.
        """

        usage = getattr(
            response,
            "usage_metadata",
            None,
        )

        if usage is None:
            return {}

        fields = {
            "prompt_tokens": "prompt_token_count",
            "response_tokens": (
                "candidates_token_count"
            ),
            "thinking_tokens": (
                "thoughts_token_count"
            ),
            "total_tokens": "total_token_count",
        }

        metadata: dict[str, Any] = {}

        for output_name, attribute_name in (
            fields.items()
        ):
            value = getattr(
                usage,
                attribute_name,
                None,
            )

            if value is not None:
                metadata[
                    output_name
                ] = value

        return metadata

    def _extract_finish_metadata(
        self,
        response,
    ) -> dict[str, Any]:
        """
        Obtiene la causa de finalización.
        """

        candidates = getattr(
            response,
            "candidates",
            None,
        )

        if not candidates:
            return {}

        first_candidate = candidates[0]

        finish_reason = getattr(
            first_candidate,
            "finish_reason",
            None,
        )

        if finish_reason is None:
            return {}

        reason_value = getattr(
            finish_reason,
            "value",
            finish_reason,
        )

        return {
            "finish_reason": str(
                reason_value
            )
        }

    # --------------------------------------------------
    # Metadatos y seguridad
    # --------------------------------------------------

    def _build_metadata(
        self,
        metadata: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """
        Construye metadatos seguros del proveedor.
        """

        return {
            **dict(metadata or {}),
            "provider": self.provider_name,
            "model": self.model_name,
            "temperature": self.temperature,
            "max_output_tokens": (
                self.max_output_tokens
            ),
            "timeout_seconds": (
                self.timeout_seconds
            ),
            "thinking_level": (
                self.thinking_level
            ),
            "credentials_available": bool(
                self.api_key
            ),
            "retry_enabled": (
                self.retry_enabled
            ),
            "max_attempts": (
                self.retry_policy.max_attempts
            ),
        }

    def _safe_error_message(
        self,
        error: Exception,
    ) -> str:
        """
        Evita mostrar accidentalmente la clave API.
        """

        message = str(
            error
        ).strip()

        if not message:
            return error.__class__.__name__

        if self.api_key:
            message = message.replace(
                self.api_key,
                "[REDACTED]",
            )

        return message

    # --------------------------------------------------
    # Normalización
    # --------------------------------------------------

    def _normalize_status_code(
        self,
        value: Any,
    ) -> int | None:
        """
        Normaliza un posible código HTTP.
        """

        if value is None:
            return None

        raw_value = getattr(
            value,
            "value",
            value,
        )

        try:
            status_code = int(
                raw_value
            )

        except (TypeError, ValueError):
            match = re.search(
                r"\b([45]\d{2})\b",
                str(raw_value),
            )

            if not match:
                return None

            status_code = int(
                match.group(1)
            )

        if 100 <= status_code <= 599:
            return status_code

        return None

    def _normalize_model(
        self,
        model: str,
    ) -> str:
        """
        Normaliza el identificador del modelo.
        """

        if not isinstance(
            model,
            str,
        ):
            raise TypeError(
                "model debe ser una cadena."
            )

        normalized = model.strip()

        if not normalized:
            raise ValueError(
                "model no puede estar vacío."
            )

        return normalized

    def _normalize_thinking_level(
        self,
        value: Any,
    ) -> str:
        """
        Valida el nivel de razonamiento.
        """

        normalized = str(
            value or "low"
        ).strip().lower()

        if normalized not in (
            self.VALID_THINKING_LEVELS
        ):
            raise ValueError(
                "thinking_level inválido: "
                f"{value}. Valores permitidos: "
                + ", ".join(
                    sorted(
                        self.VALID_THINKING_LEVELS
                    )
                )
            )

        return normalized

    def _normalize_temperature(
        self,
        value: Any,
    ) -> float:
        """
        Limita la temperatura al rango 0–2.
        """

        try:
            temperature = float(
                value
            )

        except (TypeError, ValueError):
            return 0.2

        return min(
            max(
                temperature,
                0.0,
            ),
            2.0,
        )

    def _normalize_optional_int(
        self,
        value: Any,
    ) -> int | None:
        """
        Normaliza un entero positivo opcional.
        """

        if value in (
            None,
            "",
        ):
            return None

        try:
            number = int(
                value
            )

        except (TypeError, ValueError):
            return None

        return (
            number
            if number > 0
            else None
        )

    def _normalize_positive_int(
        self,
        value: Any,
        default: int,
    ) -> int:
        """
        Normaliza un entero positivo obligatorio.
        """

        try:
            number = int(
                value
            )

        except (TypeError, ValueError):
            return default

        return (
            number
            if number > 0
            else default
        )

    def get_provider_info(
        self,
    ) -> dict[str, Any]:
        """
        Devuelve información pública y segura del proveedor.
        """

        return {
            "provider": self.provider_name,
            "model": self.model_name,
            "thinking_level": self.thinking_level,
            "retry_enabled": self.retry_enabled,
            "max_attempts": (
                self.retry_policy.max_attempts
            ),
            "initial_retry_delay_seconds": (
                self.retry_policy
                .initial_delay_seconds
            ),
            "retry_backoff_multiplier": (
                self.retry_policy
                .backoff_multiplier
            ),
            "max_retry_delay_seconds": (
                self.retry_policy
                .max_delay_seconds
            ),
            "retry_jitter_enabled": (
                self.retry_policy
                .jitter_enabled
            ),
        }