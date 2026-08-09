"""
=========================================================
Proyecto : CIPS
Release  : 0.8
Build    : 064-F2
Archivo  : stage_executor.py
Estado   : RELEASE (Fase 2)
=========================================================

Stage Executor genérico.

Responsabilidades:
- Ejecutar una etapa del pipeline mediante un callable registrado en StageRegistry.
- Gestionar el ciclo de vida de la etapa: PENDING → RUNNING → resultado.
- Aplicar reintentos con backoff exponencial configurable por etapa.
- Validar la salida del callable contra un schema Pydantic opcional.
- Registrar métricas, logs y transiciones de estado vía ProductionStateManager
  y ProductionLogger (Fase 1).
- Aplicar la política de fallo configurada (abort, continue, skip).
- Devolver un StageResult estandarizado independientemente del resultado.

Patrones:
- Engine (procesamiento de etapas).
- Registry (resolución de callables vía StageRegistry).

Este módulo NO:
- Define callables de etapa (eso lo hacen los directores/stages).
- Modifica archivos del proyecto fuera del estado y logs.
- Calcula costos reales por proveedor (recibe métricas del director).
"""

from __future__ import annotations

import time
from typing import Any

from pydantic import BaseModel, ValidationError

from production_state import ProductionStateManager, StageStatus
from production_logger import ProductionLogger, LogLevel
from stage_executor_models import (
    StageConfig,
    StageExecutorContext,
    StageFailurePolicy,
    StageMetrics,
    StageResult,
    StageResultStatus,
)
from stage_registry import StageNotRegisteredError, StageRegistry


class StageExecutorError(Exception):
    """Excepción base del StageExecutor."""

    pass


class StageExecutionError(StageExecutorError):
    """Error durante la ejecución de una etapa."""

    pass


class StageExecutor:
    """
    Motor de ejecución genérico para etapas del pipeline CIPS.

    Mantiene la interfaz pública:

        executor = StageExecutor()
        result = executor.execute(config=stage_config, context=ctx)

    El trabajo interno se delega a:
    - StageRegistry: resolución del callable.
    - ProductionStateManager: transiciones de estado.
    - ProductionLogger: logs estructurados y métricas.
    """

    component_name = "stage_executor"

    def __init__(
        self,
        default_max_retries: int = 3,
        default_retry_delay_seconds: float = 1.0,
        default_retry_backoff_multiplier: float = 2.0,
    ) -> None:
        """
        Inicializa el executor con defaults globales de reintentos.

        Args:
            default_max_retries: Reintentos por defecto si StageConfig no define.
            default_retry_delay_seconds: Delay inicial por defecto.
            default_retry_backoff_multiplier: Multiplicador de backoff por defecto.
        """
        self.default_max_retries = max(default_max_retries, 0)
        self.default_retry_delay_seconds = max(default_retry_delay_seconds, 0.0)
        self.default_retry_backoff_multiplier = max(default_retry_backoff_multiplier, 1.0)

    # --------------------------------------------------
    # Interfaz pública
    # --------------------------------------------------

    def execute(
        self,
        config: StageConfig,
        context: StageExecutorContext,
        **callable_kwargs: Any,
    ) -> StageResult:
        """
        Ejecuta una etapa completa: resolución, reintentos, validación,
        logging y transición de estado.

        Args:
            config: Configuración declarativa de la etapa.
            context: Contexto inyectado con state, logger y runtime.
            **callable_kwargs: Argumentos adicionales para el callable.

        Returns:
            StageResult estandarizado con el resultado final.
        """
        stage_name = config.stage_name
        started_at = time.perf_counter()
        state_manager: ProductionStateManager = context.production_state
        logger: ProductionLogger = context.production_logger

        # 1. Registrar inicio en estado
        self._transition_state(
            state_manager=state_manager,
            stage_name=stage_name,
            new_status=StageStatus.RUNNING,
        )

        # 2. Registrar inicio en logger
        self._log(
            logger=logger,
            level=LogLevel.INFO,
            stage=stage_name,
            message=f"Stage '{stage_name}' iniciado.",
            operation="execute",
        )

        # 3. Resolver callable
        try:
            callable_obj = StageRegistry.get(config.callable_name)
        except StageNotRegisteredError as exc:
            duration = round(time.perf_counter() - started_at, 6)
            return self._handle_fatal_error(
                config=config,
                state_manager=state_manager,
                logger=logger,
                error=exc,
                duration_seconds=duration,
                message=f"Callable no registrado: {config.callable_name}",
            )

        # 4. Ejecutar con reintentos
        max_retries = config.get_effective_max_retries(self.default_max_retries)
        retry_delay = config.get_effective_retry_delay(self.default_retry_delay_seconds)
        backoff = config.retry_backoff_multiplier or self.default_retry_backoff_multiplier

        last_exception: Exception | None = None
        retry_count = 0
        raw_output: Any = None

        for attempt in range(max_retries + 1):
            attempt_start = time.perf_counter()
            try:
                raw_output = callable_obj(
                    runtime_context=context.runtime_context,
                    production_state=state_manager,
                    production_logger=logger,
                    **callable_kwargs,
                )
                # Éxito: salir del loop de reintentos
                break

            except Exception as exc:
                last_exception = exc
                attempt_duration = round(time.perf_counter() - attempt_start, 6)

                is_last_attempt = attempt == max_retries

                self._log(
                    logger=logger,
                    level=LogLevel.WARNING if not is_last_attempt else LogLevel.ERROR,
                    stage=stage_name,
                    message=(
                        f"Intento {attempt + 1}/{max_retries + 1} fallido "
                        f"en '{stage_name}': {exc}"
                    ),
                    operation="execute_attempt",
                    duration_seconds=attempt_duration,
                    metadata={
                        "attempt": attempt + 1,
                        "max_attempts": max_retries + 1,
                        "exception_type": type(exc).__name__,
                        "error_message": str(exc),
                    },
                )

                if is_last_attempt:
                    break

                # Backoff antes del siguiente intento
                sleep_time = retry_delay * (backoff ** attempt)
                time.sleep(sleep_time)
                retry_count += 1

        # 5. Normalizar resultado
        if last_exception is not None and raw_output is None:
            duration = round(time.perf_counter() - started_at, 6)
            return self._handle_fatal_error(
                config=config,
                state_manager=state_manager,
                logger=logger,
                error=last_exception,
                duration_seconds=duration,
                retry_count=retry_count,
                message=f"Todos los intentos fallaron. Último error: {last_exception}",
            )

        # 6. Validar output contra schema Pydantic si está configurado
        validation_errors: list[str] = []
        if config.output_schema is not None:
            try:
                if isinstance(raw_output, dict):
                    config.output_schema.model_validate(raw_output)
                elif isinstance(raw_output, BaseModel):
                    config.output_schema.model_validate(raw_output.model_dump())
                else:
                    # Intentar construir el schema desde el output
                    config.output_schema.model_validate(raw_output)
            except ValidationError as val_err:
                validation_errors = [str(e) for e in val_err.errors()]
                self._log(
                    logger=logger,
                    level=LogLevel.ERROR,
                    stage=stage_name,
                    message=f"Validación de output fallida en '{stage_name}'.",
                    operation="validate_output",
                    metadata={"validation_errors": validation_errors},
                )

                if config.failure_policy == StageFailurePolicy.ABORT:
                    duration = round(time.perf_counter() - started_at, 6)
                    return self._handle_fatal_error(
                        config=config,
                        state_manager=state_manager,
                        logger=logger,
                        error=val_err,
                        duration_seconds=duration,
                        retry_count=retry_count,
                        message=f"Validación de output fallida: {val_err}",
                        extra_errors=validation_errors,
                    )

        # 7. Convertir output a StageResult
        stage_result = self._normalize_output(
            stage_name=stage_name,
            raw_output=raw_output,
            retry_count=retry_count,
            validation_errors=validation_errors,
        )

        # 8. Aplicar política de fallo si el callable reportó fallo
        if not stage_result.success:
            return self._apply_failure_policy(
                config=config,
                state_manager=state_manager,
                logger=logger,
                stage_result=stage_result,
                started_at=started_at,
            )

        # 9. Éxito: registrar métricas y estado
        duration = round(time.perf_counter() - started_at, 6)
        stage_result.metrics.duration_seconds = duration

        self._transition_state(
            state_manager=state_manager,
            stage_name=stage_name,
            new_status=StageStatus.COMPLETED,
            result_summary=stage_result.message,
            warnings=stage_result.warnings,
            metadata={
                "retry_count": retry_count,
                "duration_seconds": duration,
                **stage_result.metadata,
            },
        )

        self._log(
            logger=logger,
            level=LogLevel.INFO,
            stage=stage_name,
            message=stage_result.message,
            operation="execute",
            duration_seconds=duration,
            tokens_in=stage_result.metrics.tokens_in,
            tokens_out=stage_result.metrics.tokens_out,
            tokens_thinking=stage_result.metrics.tokens_thinking,
            cost=stage_result.metrics.cost,
            metadata={
                "retry_count": retry_count,
                "success": True,
                "warnings": stage_result.warnings,
            },
        )

        return stage_result

    # --------------------------------------------------
    # Manejo de errores y políticas
    # --------------------------------------------------

    def _handle_fatal_error(
        self,
        config: StageConfig,
        state_manager: ProductionStateManager,
        logger: ProductionLogger,
        error: Exception,
        duration_seconds: float,
        message: str,
        retry_count: int = 0,
        extra_errors: list[str] | None = None,
    ) -> StageResult:
        """
        Construye un StageResult de fallo y aplica la política configurada.
        """
        errors = [str(error)]
        if extra_errors:
            errors.extend(extra_errors)

        stage_result = StageResult(
            stage_name=config.stage_name,
            status=StageResultStatus.FAILED,
            success=False,
            message=message,
            errors=errors,
            retry_count=retry_count,
            metrics=StageMetrics(duration_seconds=duration_seconds),
        )

        return self._apply_failure_policy(
            config=config,
            state_manager=state_manager,
            logger=logger,
            stage_result=stage_result,
            started_at=None,  # Ya tenemos duration_seconds
            duration_seconds=duration_seconds,
        )

    def _apply_failure_policy(
        self,
        config: StageConfig,
        state_manager: ProductionStateManager,
        logger: ProductionLogger,
        stage_result: StageResult,
        started_at: float | None = None,
        duration_seconds: float | None = None,
    ) -> StageResult:
        """
        Aplica la política de fallo configurada y actualiza estado/logger.

        Args:
            config: Configuración de la etapa.
            state_manager: Gestor de estado de producción.
            logger: Logger estructurado.
            stage_result: Resultado de la etapa (ya contiene errores).
            started_at: Timestamp de inicio (opcional, para calcular duración).
            duration_seconds: Duración pre-calculada (opcional).

        Returns:
            StageResult ajustado según la política.
        """
        if duration_seconds is None and started_at is not None:
            duration_seconds = round(time.perf_counter() - started_at, 6)
        elif duration_seconds is None:
            duration_seconds = 0.0

        policy = config.failure_policy
        stage_name = config.stage_name

        if policy == StageFailurePolicy.SKIP:
            stage_result.status = StageResultStatus.SKIPPED
            stage_result.message = (
                f"Stage '{stage_name}' omitido por política SKIP. "
                f"Error original: {stage_result.message}"
            )

            self._transition_state(
                state_manager=state_manager,
                stage_name=stage_name,
                new_status=StageStatus.SKIPPED,
                error_message=stage_result.message,
                warnings=stage_result.warnings,
            )

            self._log(
                logger=logger,
                level=LogLevel.WARNING,
                stage=stage_name,
                message=stage_result.message,
                operation="apply_failure_policy",
                duration_seconds=duration_seconds,
                metadata={"policy": "skip", "original_errors": stage_result.errors},
            )

        elif policy == StageFailurePolicy.CONTINUE:
            stage_result.status = StageResultStatus.FAILED
            stage_result.message = (
                f"Stage '{stage_name}' falló pero continúa por política CONTINUE. "
                f"Error: {stage_result.message}"
            )

            self._transition_state(
                state_manager=state_manager,
                stage_name=stage_name,
                new_status=StageStatus.FAILED,
                error_message=stage_result.message,
                warnings=stage_result.warnings,
            )

            self._log(
                logger=logger,
                level=LogLevel.WARNING,
                stage=stage_name,
                message=stage_result.message,
                operation="apply_failure_policy",
                duration_seconds=duration_seconds,
                metadata={"policy": "continue", "errors": stage_result.errors},
            )

        else:  # ABORT
            stage_result.status = StageResultStatus.FAILED
            stage_result.message = (
                f"Stage '{stage_name}' abortado por política ABORT. "
                f"Error: {stage_result.message}"
            )

            self._transition_state(
                state_manager=state_manager,
                stage_name=stage_name,
                new_status=StageStatus.FAILED,
                error_message=stage_result.message,
                warnings=stage_result.warnings,
            )

            self._log(
                logger=logger,
                level=LogLevel.ERROR,
                stage=stage_name,
                message=stage_result.message,
                operation="apply_failure_policy",
                duration_seconds=duration_seconds,
                metadata={"policy": "abort", "errors": stage_result.errors},
            )

        # Actualizar métricas de duración si no estaban seteadas
        stage_result.metrics.duration_seconds = duration_seconds

        return stage_result

    # --------------------------------------------------
    # Normalización de output
    # --------------------------------------------------

    def _normalize_output(
        self,
        stage_name: str,
        raw_output: Any,
        retry_count: int,
        validation_errors: list[str],
    ) -> StageResult:
        """
        Convierte la salida cruda del callable en un StageResult estandarizado.

        Soporta:
        - dict con claves conocidas (success, data, message, metrics, etc.).
        - Objetos con atributos .success, .data, .message, etc.
        - Cualquier otro tipo (se envuelve en data).
        """
        # Caso 1: Ya es StageResult
        if isinstance(raw_output, StageResult):
            result = raw_output.model_copy(deep=True)
            result.retry_count = retry_count
            if validation_errors:
                result.errors.extend(validation_errors)
                result.success = False
            return result

        # Caso 2: dict
        if isinstance(raw_output, dict):
            metrics_data = raw_output.get("metrics") or {}
            metrics = (
                StageMetrics.model_validate(metrics_data)
                if isinstance(metrics_data, dict)
                else StageMetrics()
            )

            success = bool(raw_output.get("success", True))
            if validation_errors:
                success = False

            return StageResult(
                stage_name=stage_name,
                status=StageResultStatus.SUCCESS if success else StageResultStatus.FAILED,
                success=success,
                data=raw_output.get("data"),
                message=str(raw_output.get("message", "")),
                errors=[
                    *(raw_output.get("errors") or []),
                    *validation_errors,
                ],
                warnings=list(raw_output.get("warnings") or []),
                metrics=metrics,
                retry_count=retry_count,
                metadata=dict(raw_output.get("metadata") or {}),
            )

        # Caso 3: Objeto con atributos conocidos (ej. EngineResult)
        success = True
        data = raw_output
        message = ""
        errors: list[str] = []
        warnings: list[str] = []
        metrics = StageMetrics()

        if hasattr(raw_output, "success"):
            success = bool(getattr(raw_output, "success", True))
        if hasattr(raw_output, "data"):
            data = getattr(raw_output, "data", None)
        if hasattr(raw_output, "message"):
            message = str(getattr(raw_output, "message", ""))
        if hasattr(raw_output, "errors"):
            raw_errors = getattr(raw_output, "errors", [])
            errors = list(raw_errors) if raw_errors else []
        if hasattr(raw_output, "warnings"):
            raw_warnings = getattr(raw_output, "warnings", [])
            warnings = list(raw_warnings) if raw_warnings else []
        if hasattr(raw_output, "metadata"):
            meta = getattr(raw_output, "metadata", {})
            if isinstance(meta, dict):
                # Extraer métricas si existen en metadata
                metrics = StageMetrics(
                    tokens_in=meta.get("tokens_in", 0),
                    tokens_out=meta.get("tokens_out", 0),
                    tokens_thinking=meta.get("tokens_thinking", 0),
                    cost=meta.get("cost", 0.0),
                    duration_seconds=meta.get("duration_seconds", 0.0),
                )

        if validation_errors:
            success = False
            errors.extend(validation_errors)

        return StageResult(
            stage_name=stage_name,
            status=StageResultStatus.SUCCESS if success else StageResultStatus.FAILED,
            success=success,
            data=data,
            message=message,
            errors=errors,
            warnings=warnings,
            metrics=metrics,
            retry_count=retry_count,
            metadata={},
        )

    # --------------------------------------------------
    # Helpers de estado y logging
    # --------------------------------------------------

    def _transition_state(
        self,
        state_manager: ProductionStateManager,
        stage_name: str,
        new_status: StageStatus,
        result_summary: str = "",
        error_message: str = "",
        warnings: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """
        Transiciona el estado de una etapa vía ProductionStateManager.

        Silencia errores de estado para no romper la ejecución operativa.
        """
        try:
            state_manager.transition_stage(
                stage_name=stage_name,
                new_status=new_status,
                result_summary=result_summary,
                error_message=error_message,
                warnings=warnings,
                metadata=metadata or {},
            )
        except Exception as exc:
            # El fallo de estado no debe detener el pipeline
            pass

    def _log(
        self,
        logger: ProductionLogger,
        level: LogLevel,
        stage: str,
        message: str,
        operation: str = "",
        duration_seconds: float = 0.0,
        tokens_in: int = 0,
        tokens_out: int = 0,
        tokens_thinking: int = 0,
        cost: float = 0.0,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """
        Registra un evento en ProductionLogger.

        Silencia errores de logging para no romper la ejecución operativa.
        """
        try:
            logger.log(
                level=level,
                stage=stage,
                message=message,
                component=self.component_name,
                operation=operation,
                duration_seconds=duration_seconds,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                tokens_thinking=tokens_thinking,
                cost=cost,
                metadata=metadata or {},
            )
        except Exception:
            pass


def get_stage_executor_info() -> dict[str, Any]:
    """Devuelve información pública del módulo."""
    return {
        "component": "stage_executor",
        "version": "0.8",
        "build": "064-F2",
        "models": [
            "StageExecutorError",
            "StageExecutionError",
            "StageExecutor",
        ],
        "serializable": False,
    }