"""Thin execution bridge from declarative video specs to the existing CIPS Core.

F6.3 intentionally does not implement an execution engine. It compiles the
validated declarative model and delegates execution to the supplied Core
orchestrator, preserving Core ownership of dependency ordering, retries,
context propagation, messages, checkpoints, and task lifecycle.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol, runtime_checkable

from .compiler import VideoPipelineCompiler
from .models import VideoPipelineSpec


@runtime_checkable
class CoreWorkflowRunner(Protocol):
    """Minimal structural contract required from the existing Core facade."""

    def run(
        self,
        workflow: Any,
        *,
        project_id: str,
        initial_data: Mapping[str, Any] | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> Any: ...


class VideoPipelineRunner:
    """Compile a declarative video pipeline and delegate it to CIPS Core."""

    def __init__(self, orchestrator: CoreWorkflowRunner) -> None:
        if not isinstance(orchestrator, CoreWorkflowRunner):
            raise TypeError("orchestrator debe exponer un método run(...) compatible con Core.")
        self._orchestrator = orchestrator

    @property
    def orchestrator(self) -> CoreWorkflowRunner:
        return self._orchestrator

    def run(
        self,
        spec: VideoPipelineSpec,
        *,
        project_id: str,
        initial_data: Mapping[str, Any] | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> Any:
        """Compile ``spec`` and execute it through the injected Core orchestrator."""
        if not isinstance(spec, VideoPipelineSpec):
            raise TypeError("spec debe ser VideoPipelineSpec.")
        workflow = VideoPipelineCompiler.compile(spec)
        return self._orchestrator.run(
            workflow,
            project_id=project_id,
            initial_data=initial_data,
            metadata=metadata,
        )


__all__ = ["CoreWorkflowRunner", "VideoPipelineRunner"]
