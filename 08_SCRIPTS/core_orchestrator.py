from __future__ import annotations

from pathlib import Path as _Path
from typing import TYPE_CHECKING as _TYPE_CHECKING

from cips_core import *
from cips_core import CIPSOrchestrator as _BaseCIPSOrchestrator

if _TYPE_CHECKING:
    from pipeline_engine import PipelineEngine as _PipelineEngine
    from runtime_models import EngineResult as _EngineResult


class CIPSOrchestrator(_BaseCIPSOrchestrator):
    """
    Fachada de integración entre CIPS Core y el Pipeline editorial.

    Conserva la API pública del Orchestrator legacy y añade una entrada
    explícita al PipelineEngine de producción sin alterar WorkflowEngine.
    """

    def __init__(
        self,
        *,
        registry=None,
        adapter_registry=None,
        message_bus=None,
        checkpoint_store=None,
        pipeline_engine: _PipelineEngine | None = None,
    ) -> None:
        super().__init__(
            registry=registry,
            adapter_registry=adapter_registry,
            message_bus=message_bus,
            checkpoint_store=checkpoint_store,
        )
        self._pipeline_engine = pipeline_engine

    @property
    def pipeline_engine(self) -> _PipelineEngine:
        """
        Devuelve el PipelineEngine asociado al Orchestrator.

        La instancia se crea de forma diferida para evitar cargar el
        pipeline cuando únicamente se utiliza la API legacy de cips_core.
        """

        if self._pipeline_engine is None:
            from pipeline_engine import PipelineEngine

            self._pipeline_engine = PipelineEngine()

        return self._pipeline_engine

    def execute_pipeline(
        self,
        project_path: _Path | None = None,
    ) -> _EngineResult:
        """
        Ejecuta el Pipeline editorial y conserva su EngineResult público.
        """

        return self.pipeline_engine.execute(project_path)
