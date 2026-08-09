"""
=========================================================
Proyecto : CIPS
Release  : 0.8
Build    : 064-F2
Archivo  : stage_executor_models.py
Estado   : RELEASE (Fase 2)
=========================================================

Modelos de datos del Stage Executor.

Responsabilidades:
- Definir la configuración declarativa de una etapa (StageConfig).
- Estandarizar el resultado de ejecución de una etapa (StageResult).
- Tipar el contexto inyectado en cada ejecución (StageExecutorContext).
- Definir políticas de fallo y métricas de etapa.

Este módulo NO:
- Ejecuta código de etapas.
- Registra logs ni modifica estado (eso es stage_executor.py).
- Depende de componentes del pipeline fuera de los modelos base.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class StageFailurePolicy(str, Enum):
    """
    Política de manejo de fallos para una etapa individual.

    - ABORT:    Detiene el pipeline completo. Etapas críticas.
    - CONTINUE: Marca la etapa como fallida pero avanza. Etapas no bloqueantes.
    - SKIP:     Omite la etapa y continúa. Etapas opcionales (ej. SEO en draft).
    """

    ABORT = "abort"
    CONTINUE = "continue"
    SKIP = "skip"


class StageResultStatus(str, Enum):
    """
    Estado final de la ejecución de una etapa tras el procesamiento
    del StageExecutor (incluyendo reintentos y políticas).
    """

    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    RETRY_EXHAUSTED = "retry_exhausted"


class StageMetrics(BaseModel):
    """
    Métricas operativas devueltas por el callable de una etapa.

    El StageExecutor recoge estas métricas y las registra en
    ProductionLogger para acumulación y telemetría.
    """

    model_config = ConfigDict(extra="allow")

    duration_seconds: float = Field(default=0.0, ge=0.0)
    tokens_in: int = Field(default=0, ge=0)
    tokens_out: int = Field(default=0, ge=0)
    tokens_thinking: int = Field(default=0, ge=0)
    cost: float = Field(default=0.0, ge=0.0)
    currency: str = Field(default="USD")
    metadata: dict[str, Any] = Field(default_factory=dict)


class StageResult(BaseModel):
    """
    Resultado estandarizado de la ejecución de una etapa.

    Es la interfaz de salida única del StageExecutor. Cualquier
    callable registrado en StageRegistry debe devolver datos que
    el executor pueda normalizar a esta estructura.
    """

    model_config = ConfigDict(extra="allow")

    stage_name: str
    status: StageResultStatus
    success: bool
    data: Any = None
    message: str = ""
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    metrics: StageMetrics = Field(default_factory=StageMetrics)
    retry_count: int = Field(default=0, ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def is_terminal(self) -> bool:
        """Devuelve True si la etapa terminó en un estado final."""
        return self.status in (
            StageResultStatus.SUCCESS,
            StageResultStatus.FAILED,
            StageResultStatus.SKIPPED,
            StageResultStatus.RETRY_EXHAUSTED,
        )


class StageConfig(BaseModel):
    """
    Configuración declarativa de una etapa del pipeline.

    Cada etapa se define con:
    - Un nombre único (stage_name).
    - Un callable registrado en StageRegistry (callable_name).
    - Un schema Pydantic opcional para validar la salida.
    - Política de reintentos y de fallo.
    - Timeout y metadatos adicionales.
    """

    model_config = ConfigDict(extra="allow")

    stage_name: str = Field(..., min_length=1)
    callable_name: str = Field(..., min_length=1)
    output_schema: type[BaseModel] | None = Field(default=None)
    max_retries: int = Field(default=3, ge=0)
    retry_delay_seconds: float = Field(default=1.0, ge=0.0)
    retry_backoff_multiplier: float = Field(default=2.0, ge=1.0)
    failure_policy: StageFailurePolicy = Field(default=StageFailurePolicy.ABORT)
    is_critical: bool = Field(default=True)
    timeout_seconds: float = Field(default=300.0, ge=0.0)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def get_effective_max_retries(self, global_default: int) -> int:
        """
        Devuelve el máximo de reintentos efectivo.

        Si el StageConfig define max_retries > 0, lo usa.
        De lo contrario, usa el global_default.
        """
        return self.max_retries if self.max_retries > 0 else max(global_default, 0)

    def get_effective_retry_delay(self, global_default: float) -> float:
        """
        Devuelve el delay inicial de reintento efectivo.
        """
        return self.retry_delay_seconds if self.retry_delay_seconds > 0 else max(global_default, 0.0)


class StageExecutorContext(BaseModel):
    """
    Contexto inyectado en cada ejecución de etapa.

    Es el bus de servicios compartidos que el StageExecutor
    pasa a cada callable registrado. Incluye:
    - production_state: ProductionStateManager (gestión de estado F1).
    - production_logger: ProductionLogger (logs estructurados F1).
    - runtime_context: RuntimeContext de CIPS (contexto operativo legacy).
    - pipeline_config: Configuración global del pipeline (opcional).
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    production_state: Any = Field(...)
    production_logger: Any = Field(...)
    runtime_context: Any = Field(...)
    pipeline_config: dict[str, Any] = Field(default_factory=dict)


def get_stage_executor_models_info() -> dict[str, Any]:
    """Devuelve información pública del módulo."""
    return {
        "component": "stage_executor_models",
        "version": "0.8",
        "build": "064-F2",
        "models": [
            "StageFailurePolicy",
            "StageResultStatus",
            "StageMetrics",
            "StageResult",
            "StageConfig",
            "StageExecutorContext",
        ],
        "serializable": True,
    }