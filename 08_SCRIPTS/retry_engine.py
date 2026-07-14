"""
=========================================================
Proyecto : CIPS
Release  : 0.8
Build    : 057
Archivo  : retry_engine.py
Estado   : RELEASE
=========================================================

Ejecuta operaciones con una política de reintentos.

Responsabilidades:
- ejecutar una operación invocable;
- detectar resultados exitosos o fallidos;
- clasificar fallos mediante RetryPolicy;
- aplicar esperas progresivas;
- detenerse ante errores permanentes;
- registrar intentos, decisiones y tiempos;
- devolver el resultado original enriquecido con metadata;
- funcionar con cualquier proveedor o componente.

Este Engine NO:
- depende directamente de Gemini;
- genera prompts;
- llama modelos por sí mismo;
- modifica contenido editorial;
- interpreta credenciales;
- sustituye la lógica de los Providers.
"""

from dataclasses import dataclass, field
import time
from typing import Any, Callable

from retry_policy import (
    RetryDecision,
    RetryPolicy,
)


@dataclass
class RetryAttempt:
    """
    Registro de un intento individual.

    Attributes:
        attempt_number:
            Número del intento, comenzando en 1.

        success:
            Indica si la operación terminó correctamente.

        duration_seconds:
            Duración de la operación.

        retryable:
            Indica si el fallo permite otro intento.

        delay_seconds:
            Espera aplicada después del intento.

        status_code:
            Código HTTP detectado.

        exception_type:
            Tipo de excepción detectado.

        message:
            Mensaje principal del resultado.

        matched_rule:
            Regla de RetryPolicy utilizada.

        metadata:
            Información adicional segura.
    """

    attempt_number: int
    success: bool
    duration_seconds: float = 0.0
    retryable: bool = False
    delay_seconds: float = 0.0
    status_code: int | None = None
    exception_type: str = ""
    message: str = ""
    matched_rule: str = ""
    metadata: dict[str, Any] = field(
        default_factory=dict
    )


@dataclass
class RetryExecutionResult:
    """
    Resultado consolidado de RetryEngine.

    result:
        Resultado original producido por la operación.

    attempts:
        Historial completo de intentos.
    """

    success: bool
    result: Any = None
    attempts: list[RetryAttempt] = field(
        default_factory=list
    )
    message: str = ""
    warnings: list[str] = field(
        default_factory=list
    )
    errors: list[str] = field(
        default_factory=list
    )
    metadata: dict[str, Any] = field(
        default_factory=dict
    )


class RetryEngine:
    """
    Ejecuta una operación utilizando RetryPolicy.

    Ejemplo:

        engine = RetryEngine()

        result = engine.execute(
            operation=lambda: provider.generate(prompt),
        )

    La operación puede:

    - devolver un resultado con atributo ``success``;
    - devolver cualquier valor válido;
    - lanzar una excepción.

    Por defecto:
    - un objeto con ``success=True`` se considera exitoso;
    - un objeto con ``success=False`` se clasifica usando
      sus errores y metadata;
    - un valor sin atributo ``success`` se considera exitoso;
    - una excepción se clasifica mediante RetryPolicy.
    """

    COMPONENT_NAME = "retry_engine"
    VERSION = "0.8"

    def __init__(
        self,
        policy: RetryPolicy | None = None,
        sleep_function: Callable[[float], None] | None = None,
        clock_function: Callable[[], float] | None = None,
    ) -> None:
        """
        Inicializa RetryEngine.

        Args:
            policy:
                Política de reintentos.

            sleep_function:
                Función utilizada para esperar. Se puede sustituir
                durante pruebas para evitar esperas reales.

            clock_function:
                Reloj monotónico para medir duraciones.
        """

        self.policy = (
            policy
            or RetryPolicy()
        )

        self.sleep_function = (
            sleep_function
            or time.sleep
        )

        self.clock_function = (
            clock_function
            or time.perf_counter
        )

    # --------------------------------------------------
    # API pública
    # --------------------------------------------------

    def execute(
        self,
        operation: Callable[[], Any],
        operation_name: str = "operation",
        result_success_resolver: (
            Callable[[Any], bool] | None
        ) = None,
        error_resolver: (
            Callable[[Any], Exception | str | None]
            | None
        ) = None,
        metadata_resolver: (
            Callable[[Any], dict[str, Any]]
            | None
        ) = None,
        on_retry: (
            Callable[
                [RetryAttempt, RetryDecision],
                None,
            ]
            | None
        ) = None,
    ) -> RetryExecutionResult:
        """
        Ejecuta una operación con reintentos.

        Args:
            operation:
                Función sin argumentos que ejecutará el trabajo.

            operation_name:
                Nombre legible de la operación.

            result_success_resolver:
                Función opcional para determinar si un resultado
                fue exitoso.

            error_resolver:
                Función opcional para extraer el error principal.

            metadata_resolver:
                Función opcional para extraer metadata.

            on_retry:
                Callback ejecutado antes de esperar y reintentar.

        Returns:
            RetryExecutionResult.
        """

        if not callable(
            operation
        ):
            return RetryExecutionResult(
                success=False,
                message=(
                    "RetryEngine requiere una operación "
                    "invocable."
                ),
                errors=[
                    "operation no es callable."
                ],
                metadata={
                    "component": self.COMPONENT_NAME,
                    "operation_name": operation_name,
                },
            )

        attempts: list[RetryAttempt] = []
        total_start = self.clock_function()
        final_result: Any = None
        final_errors: list[str] = []
        warnings: list[str] = []

        for attempt_number in range(
            1,
            self.policy.max_attempts + 1,
        ):
            attempt_start = self.clock_function()

            try:
                result = operation()

                duration = round(
                    self.clock_function()
                    - attempt_start,
                    3,
                )

                success = self._resolve_success(
                    result=result,
                    resolver=result_success_resolver,
                )

                result_metadata = (
                    self._resolve_metadata(
                        result=result,
                        resolver=metadata_resolver,
                    )
                )

                result_message = (
                    self._extract_result_message(
                        result
                    )
                )

                if success:
                    attempt = RetryAttempt(
                        attempt_number=attempt_number,
                        success=True,
                        duration_seconds=duration,
                        retryable=False,
                        delay_seconds=0.0,
                        message=result_message,
                        metadata=result_metadata,
                    )

                    attempts.append(
                        attempt
                    )

                    total_duration = round(
                        self.clock_function()
                        - total_start,
                        3,
                    )

                    enriched_result = (
                        self._enrich_original_result(
                            result=result,
                            attempts=attempts,
                            total_duration=total_duration,
                            operation_name=operation_name,
                        )
                    )

                    return RetryExecutionResult(
                        success=True,
                        result=enriched_result,
                        attempts=attempts,
                        message=(
                            result_message
                            or (
                                "Operación completada "
                                "correctamente."
                            )
                        ),
                        warnings=warnings,
                        errors=[],
                        metadata=self._build_execution_metadata(
                            operation_name=operation_name,
                            attempts=attempts,
                            total_duration=total_duration,
                            exhausted=False,
                        ),
                    )

                resolved_error = self._resolve_error(
                    result=result,
                    resolver=error_resolver,
                )

                decision = self.policy.should_retry(
                    error=resolved_error,
                    metadata=result_metadata,
                )

                retries_remaining = (
                    self.policy.retries_available_after(
                        attempt_number
                    )
                )

                should_retry = (
                    decision.retryable
                    and retries_remaining > 0
                )

                delay = (
                    self.policy.calculate_delay(
                        attempt_number
                    )
                    if should_retry
                    else 0.0
                )

                attempt = RetryAttempt(
                    attempt_number=attempt_number,
                    success=False,
                    duration_seconds=duration,
                    retryable=should_retry,
                    delay_seconds=delay,
                    status_code=decision.status_code,
                    exception_type=(
                        decision.exception_type
                    ),
                    message=(
                        result_message
                        or str(
                            resolved_error
                            or ""
                        )
                    ),
                    matched_rule=(
                        decision.matched_rule
                    ),
                    metadata={
                        **result_metadata,
                        "decision_reason": (
                            decision.reason
                        ),
                        "retries_remaining": (
                            retries_remaining
                        ),
                    },
                )

                attempts.append(
                    attempt
                )

                final_result = result
                final_errors = (
                    self._extract_result_errors(
                        result
                    )
                )

                if not should_retry:
                    break

                if callable(
                    on_retry
                ):
                    on_retry(
                        attempt,
                        decision,
                    )

                self.sleep_function(
                    delay
                )

            except Exception as error:
                duration = round(
                    self.clock_function()
                    - attempt_start,
                    3,
                )

                decision = self.policy.should_retry(
                    error=error,
                    metadata={
                        "exception_type": (
                            error.__class__.__name__
                        ),
                    },
                )

                retries_remaining = (
                    self.policy.retries_available_after(
                        attempt_number
                    )
                )

                should_retry = (
                    decision.retryable
                    and retries_remaining > 0
                )

                delay = (
                    self.policy.calculate_delay(
                        attempt_number
                    )
                    if should_retry
                    else 0.0
                )

                attempt = RetryAttempt(
                    attempt_number=attempt_number,
                    success=False,
                    duration_seconds=duration,
                    retryable=should_retry,
                    delay_seconds=delay,
                    status_code=decision.status_code,
                    exception_type=(
                        error.__class__.__name__
                    ),
                    message=str(error),
                    matched_rule=(
                        decision.matched_rule
                    ),
                    metadata={
                        "decision_reason": decision.reason,
                        "retries_remaining": (
                            retries_remaining
                        ),
                    },
                )

                attempts.append(
                    attempt
                )

                final_result = None
                final_errors = [
                    str(error)
                ]

                if not should_retry:
                    break

                if callable(
                    on_retry
                ):
                    on_retry(
                        attempt,
                        decision,
                    )

                self.sleep_function(
                    delay
                )

        total_duration = round(
            self.clock_function()
            - total_start,
            3,
        )

        exhausted = (
            len(attempts)
            >= self.policy.max_attempts
            and bool(attempts)
            and not attempts[-1].success
            and attempts[-1].metadata.get(
                "retries_remaining",
                0,
            )
            == 0
        )

        enriched_result = self._enrich_original_result(
            result=final_result,
            attempts=attempts,
            total_duration=total_duration,
            operation_name=operation_name,
        )

        return RetryExecutionResult(
            success=False,
            result=enriched_result,
            attempts=attempts,
            message=(
                "La operación no pudo completarse "
                "después de aplicar la política "
                "de reintentos."
                if exhausted
                else (
                    "La operación falló y el error "
                    "no es reintentable."
                )
            ),
            warnings=warnings,
            errors=(
                final_errors
                or [
                    "La operación terminó sin éxito."
                ]
            ),
            metadata=self._build_execution_metadata(
                operation_name=operation_name,
                attempts=attempts,
                total_duration=total_duration,
                exhausted=exhausted,
            ),
        )

    # --------------------------------------------------
    # Resolución de resultados
    # --------------------------------------------------

    def _resolve_success(
        self,
        result: Any,
        resolver: Callable[[Any], bool] | None,
    ) -> bool:
        """
        Determina si el resultado fue exitoso.
        """

        if resolver is not None:
            return bool(
                resolver(result)
            )

        if hasattr(
            result,
            "success",
        ):
            return bool(
                getattr(
                    result,
                    "success",
                )
            )

        return True

    def _resolve_error(
        self,
        result: Any,
        resolver: (
            Callable[[Any], Exception | str | None]
            | None
        ),
    ) -> Exception | str | None:
        """
        Extrae el error principal del resultado.
        """

        if resolver is not None:
            return resolver(
                result
            )

        errors = getattr(
            result,
            "errors",
            None,
        )

        if isinstance(
            errors,
            list,
        ) and errors:
            return "\n".join(
                str(error)
                for error in errors
            )

        message = getattr(
            result,
            "message",
            None,
        )

        if message:
            return str(message)

        return str(result)

    def _resolve_metadata(
        self,
        result: Any,
        resolver: (
            Callable[[Any], dict[str, Any]]
            | None
        ),
    ) -> dict[str, Any]:
        """
        Extrae metadata segura del resultado.
        """

        if resolver is not None:
            metadata = resolver(
                result
            )

            return (
                dict(metadata)
                if isinstance(metadata, dict)
                else {}
            )

        metadata = getattr(
            result,
            "metadata",
            None,
        )

        return (
            dict(metadata)
            if isinstance(metadata, dict)
            else {}
        )

    def _extract_result_message(
        self,
        result: Any,
    ) -> str:
        """
        Obtiene un mensaje legible del resultado.
        """

        message = getattr(
            result,
            "message",
            "",
        )

        return str(
            message or ""
        ).strip()

    def _extract_result_errors(
        self,
        result: Any,
    ) -> list[str]:
        """
        Obtiene errores del resultado.
        """

        errors = getattr(
            result,
            "errors",
            None,
        )

        if isinstance(
            errors,
            list,
        ):
            return [
                str(error)
                for error in errors
            ]

        if errors:
            return [
                str(errors)
            ]

        message = self._extract_result_message(
            result
        )

        return (
            [message]
            if message
            else []
        )

    # --------------------------------------------------
    # Enriquecimiento
    # --------------------------------------------------

    def _enrich_original_result(
        self,
        result: Any,
        attempts: list[RetryAttempt],
        total_duration: float,
        operation_name: str,
    ) -> Any:
        """
        Agrega metadata de reintentos al resultado original.

        Si el objeto no permite modificar metadata,
        se devuelve sin cambios.
        """

        if result is None:
            return None

        metadata = getattr(
            result,
            "metadata",
            None,
        )

        if not isinstance(
            metadata,
            dict,
        ):
            return result

        metadata.update(
            {
                "retry": {
                    "operation_name": (
                        operation_name
                    ),
                    "attempts_count": len(
                        attempts
                    ),
                    "retries_count": max(
                        len(attempts) - 1,
                        0,
                    ),
                    "total_duration_seconds": (
                        total_duration
                    ),
                    "succeeded_after_retry": (
                        len(attempts) > 1
                        and attempts[-1].success
                    ),
                    "attempts": [
                        self._attempt_to_dict(
                            attempt
                        )
                        for attempt in attempts
                    ],
                }
            }
        )

        return result

    def _build_execution_metadata(
        self,
        operation_name: str,
        attempts: list[RetryAttempt],
        total_duration: float,
        exhausted: bool,
    ) -> dict[str, Any]:
        """
        Construye metadata consolidada.
        """

        return {
            "component": self.COMPONENT_NAME,
            "version": self.VERSION,
            "operation_name": operation_name,
            "attempts_count": len(
                attempts
            ),
            "retries_count": max(
                len(attempts) - 1,
                0,
            ),
            "max_attempts": (
                self.policy.max_attempts
            ),
            "total_duration_seconds": (
                total_duration
            ),
            "exhausted": exhausted,
            "succeeded_after_retry": (
                bool(attempts)
                and attempts[-1].success
                and len(attempts) > 1
            ),
            "attempts": [
                self._attempt_to_dict(
                    attempt
                )
                for attempt in attempts
            ],
        }

    def _attempt_to_dict(
        self,
        attempt: RetryAttempt,
    ) -> dict[str, Any]:
        """
        Convierte RetryAttempt a diccionario.
        """

        return {
            "attempt_number": (
                attempt.attempt_number
            ),
            "success": attempt.success,
            "duration_seconds": (
                attempt.duration_seconds
            ),
            "retryable": attempt.retryable,
            "delay_seconds": (
                attempt.delay_seconds
            ),
            "status_code": attempt.status_code,
            "exception_type": (
                attempt.exception_type
            ),
            "message": attempt.message,
            "matched_rule": (
                attempt.matched_rule
            ),
            "metadata": dict(
                attempt.metadata
            ),
        }

    def get_component_info(
        self,
    ) -> dict[str, Any]:
        """
        Devuelve información pública del componente.
        """

        return {
            "component": self.COMPONENT_NAME,
            "version": self.VERSION,
            "max_attempts": (
                self.policy.max_attempts
            ),
            "maximum_retries": max(
                self.policy.max_attempts - 1,
                0,
            ),
            "initial_delay_seconds": (
                self.policy.initial_delay_seconds
            ),
            "backoff_multiplier": (
                self.policy.backoff_multiplier
            ),
            "max_delay_seconds": (
                self.policy.max_delay_seconds
            ),
            "jitter_enabled": (
                self.policy.jitter_enabled
            ),
            "provider_agnostic": True,
            "next_component": (
                "gemini_llm_provider"
            ),
        }