"""
=========================================================
Proyecto : CIPS
Release  : 0.8
Build    : 056
Archivo  : retry_policy.py
Estado   : RELEASE
=========================================================

Define las reglas de reintento utilizadas por CIPS.

Responsabilidades:
- declarar cuántos intentos pueden realizarse;
- definir códigos HTTP reintentables;
- definir excepciones temporales reintentables;
- calcular tiempos de espera progresivos;
- aplicar un límite máximo de espera;
- permitir jitter opcional;
- clasificar errores sin depender de un proveedor específico.

Este componente NO:
- ejecuta solicitudes;
- duerme procesos;
- llama modelos de Inteligencia Artificial;
- modifica ProviderResult;
- depende directamente de Gemini, OpenAI o Claude.
"""

from dataclasses import dataclass, field
import random
import re
from typing import Any


@dataclass
class RetryDecision:
    """
    Resultado de clasificar un error.

    Attributes:
        retryable:
            Indica si debe intentarse nuevamente.

        reason:
            Explicación legible de la decisión.

        status_code:
            Código HTTP detectado, cuando existe.

        exception_type:
            Tipo de excepción detectado.

        matched_rule:
            Regla que produjo la decisión.
    """

    retryable: bool
    reason: str
    status_code: int | None = None
    exception_type: str = ""
    matched_rule: str = ""
    metadata: dict[str, Any] = field(
        default_factory=dict
    )


@dataclass
class RetryPolicy:
    """
    Contrato de reintentos reutilizable por proveedores LLM.

    La política utiliza backoff exponencial:

        delay = initial_delay * multiplier ** retry_index

    Ejemplo con:

        initial_delay_seconds = 5
        backoff_multiplier = 2

    Produce aproximadamente:

        5, 10, 20 segundos

    El jitter puede modificar ligeramente cada espera para evitar
    que múltiples procesos repitan solicitudes al mismo tiempo.
    """

    max_attempts: int = 3

    initial_delay_seconds: float = 5.0

    backoff_multiplier: float = 2.0

    max_delay_seconds: float = 30.0

    jitter_enabled: bool = True

    jitter_ratio: float = 0.15

    retryable_status_codes: set[int] = field(
        default_factory=lambda: {
            408,
            409,
            425,
            429,
            500,
            502,
            503,
            504,
        }
    )

    non_retryable_status_codes: set[int] = field(
        default_factory=lambda: {
            400,
            401,
            403,
            404,
            405,
            406,
            410,
            422,
        }
    )

    retryable_exception_names: set[str] = field(
        default_factory=lambda: {
            "TimeoutError",
            "ConnectionError",
            "ConnectionResetError",
            "ConnectionAbortedError",
            "ConnectionRefusedError",
            "BrokenPipeError",
            "ServerError",
            "ServiceUnavailable",
            "TooManyRequests",
            "ResourceExhausted",
            "DeadlineExceeded",
            "InternalServerError",
        }
    )

    retryable_message_markers: tuple[str, ...] = (
        "temporarily unavailable",
        "temporary failure",
        "service unavailable",
        "high demand",
        "too many requests",
        "rate limit",
        "rate-limit",
        "resource exhausted",
        "connection reset",
        "connection aborted",
        "connection refused",
        "connection timed out",
        "timeout",
        "timed out",
        "deadline exceeded",
        "server error",
        "internal error",
        "bad gateway",
        "gateway timeout",
        "try again later",
    )

    non_retryable_message_markers: tuple[str, ...] = (
        "invalid api key",
        "api key not valid",
        "authentication failed",
        "unauthorized",
        "permission denied",
        "forbidden",
        "invalid argument",
        "unsupported model",
        "model not found",
        "malformed request",
        "billing disabled",
        "quota permanently exceeded",
    )

    def __post_init__(
        self,
    ) -> None:
        """
        Normaliza y valida la configuración.
        """

        self.max_attempts = self._normalize_positive_int(
            self.max_attempts,
            default=3,
        )

        self.initial_delay_seconds = (
            self._normalize_non_negative_float(
                self.initial_delay_seconds,
                default=5.0,
            )
        )

        self.backoff_multiplier = (
            self._normalize_positive_float(
                self.backoff_multiplier,
                default=2.0,
            )
        )

        self.max_delay_seconds = (
            self._normalize_non_negative_float(
                self.max_delay_seconds,
                default=30.0,
            )
        )

        self.jitter_ratio = min(
            max(
                self._normalize_non_negative_float(
                    self.jitter_ratio,
                    default=0.15,
                ),
                0.0,
            ),
            1.0,
        )

        if (
            self.max_delay_seconds
            < self.initial_delay_seconds
        ):
            self.max_delay_seconds = (
                self.initial_delay_seconds
            )

    # --------------------------------------------------
    # API pública
    # --------------------------------------------------

    def should_retry(
        self,
        error: Exception | str | None = None,
        status_code: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> RetryDecision:
        """
        Clasifica un fallo y determina si debe reintentarse.

        Prioridad de decisión:

        1. retryable explícito en metadata;
        2. códigos HTTP no reintentables;
        3. códigos HTTP reintentables;
        4. mensajes no reintentables;
        5. tipos de excepción reintentables;
        6. mensajes temporales;
        7. decisión conservadora: no reintentar.
        """

        safe_metadata = dict(
            metadata or {}
        )

        explicit_retryable = safe_metadata.get(
            "retryable"
        )

        detected_status_code = (
            self._normalize_status_code(
                status_code
            )
            or self._extract_status_code(
                error
            )
            or self._extract_status_code_from_metadata(
                safe_metadata
            )
        )

        exception_type = self._extract_exception_type(
            error
        )

        message = self._extract_message(
            error
        )

        normalized_message = message.lower()

        if isinstance(
            explicit_retryable,
            bool,
        ):
            return RetryDecision(
                retryable=explicit_retryable,
                reason=(
                    "La metadata del proveedor indicó "
                    f"retryable={explicit_retryable}."
                ),
                status_code=detected_status_code,
                exception_type=exception_type,
                matched_rule="metadata.retryable",
                metadata=safe_metadata,
            )

        if (
            detected_status_code
            in self.non_retryable_status_codes
        ):
            return RetryDecision(
                retryable=False,
                reason=(
                    "El código HTTP indica un error "
                    "permanente o de configuración."
                ),
                status_code=detected_status_code,
                exception_type=exception_type,
                matched_rule="non_retryable_status_code",
                metadata=safe_metadata,
            )

        if (
            detected_status_code
            in self.retryable_status_codes
        ):
            return RetryDecision(
                retryable=True,
                reason=(
                    "El código HTTP corresponde a un "
                    "fallo temporal reintentable."
                ),
                status_code=detected_status_code,
                exception_type=exception_type,
                matched_rule="retryable_status_code",
                metadata=safe_metadata,
            )

        non_retryable_marker = (
            self._find_marker(
                normalized_message,
                self.non_retryable_message_markers,
            )
        )

        if non_retryable_marker:
            return RetryDecision(
                retryable=False,
                reason=(
                    "El mensaje corresponde a un error "
                    "permanente o de configuración."
                ),
                status_code=detected_status_code,
                exception_type=exception_type,
                matched_rule=(
                    "non_retryable_message:"
                    + non_retryable_marker
                ),
                metadata=safe_metadata,
            )

        if (
            exception_type
            in self.retryable_exception_names
        ):
            return RetryDecision(
                retryable=True,
                reason=(
                    "El tipo de excepción corresponde a "
                    "un fallo temporal de red o servicio."
                ),
                status_code=detected_status_code,
                exception_type=exception_type,
                matched_rule="retryable_exception",
                metadata=safe_metadata,
            )

        retryable_marker = self._find_marker(
            normalized_message,
            self.retryable_message_markers,
        )

        if retryable_marker:
            return RetryDecision(
                retryable=True,
                reason=(
                    "El mensaje contiene una señal de "
                    "fallo temporal."
                ),
                status_code=detected_status_code,
                exception_type=exception_type,
                matched_rule=(
                    "retryable_message:"
                    + retryable_marker
                ),
                metadata=safe_metadata,
            )

        return RetryDecision(
            retryable=False,
            reason=(
                "El error no coincide con ninguna regla "
                "de reintento segura."
            ),
            status_code=detected_status_code,
            exception_type=exception_type,
            matched_rule="default_no_retry",
            metadata=safe_metadata,
        )

    def calculate_delay(
        self,
        retry_number: int,
    ) -> float:
        """
        Calcula la espera anterior al siguiente intento.

        Args:
            retry_number:
                Número de reintento comenzando en 1.

                retry_number=1 corresponde a la espera
                entre el intento 1 y el intento 2.
        """

        normalized_retry_number = max(
            int(retry_number),
            1,
        )

        exponential_delay = (
            self.initial_delay_seconds
            * (
                self.backoff_multiplier
                ** (
                    normalized_retry_number
                    - 1
                )
            )
        )

        delay = min(
            exponential_delay,
            self.max_delay_seconds,
        )

        if (
            self.jitter_enabled
            and delay > 0
            and self.jitter_ratio > 0
        ):
            variation = (
                delay
                * self.jitter_ratio
            )

            delay = random.uniform(
                max(
                    0.0,
                    delay - variation,
                ),
                delay + variation,
            )

        return round(
            min(
                delay,
                self.max_delay_seconds,
            ),
            3,
        )

    def can_attempt(
        self,
        attempt_number: int,
    ) -> bool:
        """
        Indica si un número de intento está permitido.

        Los intentos comienzan en 1.
        """

        try:
            normalized_attempt = int(
                attempt_number
            )

        except (TypeError, ValueError):
            return False

        return (
            1
            <= normalized_attempt
            <= self.max_attempts
        )

    def retries_available_after(
        self,
        attempt_number: int,
    ) -> int:
        """
        Devuelve cuántos intentos quedan disponibles.
        """

        try:
            normalized_attempt = int(
                attempt_number
            )

        except (TypeError, ValueError):
            normalized_attempt = 0

        return max(
            self.max_attempts
            - normalized_attempt,
            0,
        )

    def get_policy_info(
        self,
    ) -> dict[str, Any]:
        """
        Devuelve la configuración pública de la política.
        """

        return {
            "component": "retry_policy",
            "version": "0.8",
            "max_attempts": self.max_attempts,
            "maximum_retries": max(
                self.max_attempts - 1,
                0,
            ),
            "initial_delay_seconds": (
                self.initial_delay_seconds
            ),
            "backoff_multiplier": (
                self.backoff_multiplier
            ),
            "max_delay_seconds": (
                self.max_delay_seconds
            ),
            "jitter_enabled": (
                self.jitter_enabled
            ),
            "jitter_ratio": self.jitter_ratio,
            "retryable_status_codes": sorted(
                self.retryable_status_codes
            ),
            "non_retryable_status_codes": sorted(
                self.non_retryable_status_codes
            ),
        }

    # --------------------------------------------------
    # Extracción y clasificación
    # --------------------------------------------------

    def _extract_status_code(
        self,
        error: Exception | str | None,
    ) -> int | None:
        """
        Intenta obtener un código HTTP desde una excepción
        o desde su representación textual.
        """

        if error is None:
            return None

        if isinstance(
            error,
            Exception,
        ):
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

                normalized = self._normalize_status_code(
                    value
                )

                if normalized is not None:
                    return normalized

        message = self._extract_message(
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
                return self._normalize_status_code(
                    match.group(1)
                )

        return None

    def _extract_status_code_from_metadata(
        self,
        metadata: dict[str, Any],
    ) -> int | None:
        """
        Busca un código HTTP dentro de metadata.
        """

        for key in (
            "status_code",
            "http_status",
            "error_code",
            "code",
        ):
            normalized = self._normalize_status_code(
                metadata.get(key)
            )

            if normalized is not None:
                return normalized

        return None

    def _extract_exception_type(
        self,
        error: Exception | str | None,
    ) -> str:
        """
        Obtiene el nombre del tipo de excepción.
        """

        if isinstance(
            error,
            Exception,
        ):
            return error.__class__.__name__

        return ""

    def _extract_message(
        self,
        error: Exception | str | None,
    ) -> str:
        """
        Convierte el error a texto seguro.
        """

        if error is None:
            return ""

        return str(
            error
        ).strip()

    def _find_marker(
        self,
        message: str,
        markers: tuple[str, ...],
    ) -> str:
        """
        Devuelve el primer marcador encontrado.
        """

        for marker in markers:
            if marker in message:
                return marker

        return ""

    # --------------------------------------------------
    # Normalización
    # --------------------------------------------------

    def _normalize_status_code(
        self,
        value: Any,
    ) -> int | None:
        """
        Normaliza un código HTTP.
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

    def _normalize_positive_int(
        self,
        value: Any,
        default: int,
    ) -> int:
        """
        Normaliza un entero positivo.
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

    def _normalize_positive_float(
        self,
        value: Any,
        default: float,
    ) -> float:
        """
        Normaliza un flotante positivo.
        """

        try:
            number = float(
                value
            )

        except (TypeError, ValueError):
            return default

        return (
            number
            if number > 0
            else default
        )

    def _normalize_non_negative_float(
        self,
        value: Any,
        default: float,
    ) -> float:
        """
        Normaliza un flotante mayor o igual que cero.
        """

        try:
            number = float(
                value
            )

        except (TypeError, ValueError):
            return default

        return max(
            number,
            0.0,
        )