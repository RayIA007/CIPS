"""
=========================================================
Proyecto : CIPS
Release  : 0.6
Build    : 041
Archivo  : gemini_llm_provider.py
Estado   : RELEASE
=========================================================

Implementa el proveedor Google Gemini mediante el SDK
oficial google-genai.

Funciones principales:
- obtener la clave desde variables de entorno;
- controlar temperatura y tokens de salida;
- configurar el nivel de razonamiento;
- generar LLMResponse;
- registrar métricas de uso;
- proteger credenciales en mensajes de error.
"""

import os
from typing import Any

from llm_provider import LLMProvider, ProviderResult
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

    def __init__(
        self,
        model: str = "gemini-3.5-flash",
        api_key: str | None = None,
        api_key_env: str = "GOOGLE_API_KEY",
        temperature: float = 0.2,
        max_output_tokens: int | None = None,
        timeout_seconds: int = 60,
        thinking_level: str = "low",
    ) -> None:
        """
        Inicializa el proveedor Gemini.

        Args:
            model:
                Identificador oficial del modelo.

            api_key:
                Credencial explícita opcional. Se recomienda
                utilizar una variable de entorno.

            api_key_env:
                Variable de entorno principal.

            temperature:
                Variación permitida en la generación.

            max_output_tokens:
                Presupuesto máximo de tokens de salida.

            timeout_seconds:
                Tiempo máximo previsto para la solicitud.

            thinking_level:
                Nivel de razonamiento del modelo:
                minimal, low, medium o high.
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

        self._client = None

    def generate(
        self,
        prompt: str,
        metadata: dict[str, Any] | None = None,
    ) -> ProviderResult:
        """
        Envía el prompt a Gemini y devuelve ProviderResult.
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
                metadata=self._build_metadata(
                    metadata
                ),
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
                },
            )

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
                },
            )

        except Exception as error:
            return ProviderResult.fail(
                message=(
                    "Google Gemini no pudo completar "
                    "la solicitud."
                ),
                errors=[
                    self._safe_error_message(error)
                ],
                metadata={
                    **self._build_metadata(metadata),
                    "exception_type": (
                        error.__class__.__name__
                    ),
                },
            )

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

        thinking_level controla el presupuesto de razonamiento
        de los modelos Gemini compatibles.
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
            return str(direct_text).strip()

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
        Extrae métricas de tokens cuando están disponibles.
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
            "response_tokens": "candidates_token_count",
            "thinking_tokens": "thoughts_token_count",
            "total_tokens": "total_token_count",
        }

        metadata: dict[str, Any] = {}

        for output_name, attribute_name in fields.items():
            value = getattr(
                usage,
                attribute_name,
                None,
            )

            if value is not None:
                metadata[output_name] = value

        return metadata

    def _extract_finish_metadata(
        self,
        response,
    ) -> dict[str, Any]:
        """
        Obtiene la causa de finalización de la respuesta.
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
            "finish_reason": str(reason_value)
        }

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
        }

    def _safe_error_message(
        self,
        error: Exception,
    ) -> str:
        """
        Evita mostrar accidentalmente la clave API.
        """

        message = str(error).strip()

        if not message:
            return error.__class__.__name__

        if self.api_key:
            message = message.replace(
                self.api_key,
                "[REDACTED]",
            )

        return message

    def _normalize_model(
        self,
        model: str,
    ) -> str:
        """
        Normaliza el identificador del modelo.
        """

        if not isinstance(model, str):
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

        if normalized not in self.VALID_THINKING_LEVELS:
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
            temperature = float(value)

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
            number = int(value)

        except (TypeError, ValueError):
            return None

        return number if number > 0 else None

    def _normalize_positive_int(
        self,
        value: Any,
        default: int,
    ) -> int:
        """
        Normaliza un entero positivo obligatorio.
        """

        try:
            number = int(value)

        except (TypeError, ValueError):
            return default

        return number if number > 0 else default