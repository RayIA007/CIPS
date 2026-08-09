"""
=========================================================
Proyecto : CIPS
Archivo  : test_f2_smoke.py
Estado   : SMOKE TEST F2.3
=========================================================

Prueba de humo no destructiva para validar la integración
CoreOrchestrator -> PipelineEngine introducida en F2.3.

EJECUCIÓN SEGURA:
- NO consume tokens de LLM.
- NO modifica proyectos reales.
- NO ejecuta el PipelineEngine real.
- Valida compatibilidad legacy, inyección y carga lazy.

Uso:
    python C:\\ConsejoIA_V5\\08_SCRIPTS\\test_f2_smoke.py
"""

from __future__ import annotations

import inspect
import sys
from pathlib import Path
from types import ModuleType


scripts_dir = Path(__file__).parent.resolve()
if str(scripts_dir) not in sys.path:
    sys.path.insert(0, str(scripts_dir))


class _FakePipelineEngine:
    def __init__(self, result: object) -> None:
        self.result = result
        self.calls: list[Path | None] = []

    def execute(self, project_path: Path | None = None) -> object:
        self.calls.append(project_path)
        return self.result


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    import cips_core
    import core_orchestrator

    print("=" * 72)
    print("CIPS F2.3 CoreOrchestrator Integration Smoke Test")
    print("=" * 72)

    # ------------------------------------------------------------------
    # 1. Compatibilidad de la fachada legacy
    # ------------------------------------------------------------------
    _assert(
        issubclass(
            core_orchestrator.CIPSOrchestrator,
            cips_core.CIPSOrchestrator,
        ),
        "CIPSOrchestrator F2.3 debe extender la fachada legacy.",
    )

    for method_name in (
        "register_agent",
        "register_adapter",
        "create_workflow",
        "run",
    ):
        _assert(
            hasattr(core_orchestrator.CIPSOrchestrator, method_name),
            f"API legacy ausente: {method_name}",
        )

    for export_name in (
        "AgentRegistry",
        "WorkflowEngine",
        "WorkflowDefinition",
    ):
        _assert(
            getattr(core_orchestrator, export_name)
            is getattr(cips_core, export_name),
            f"Export legacy alterado: {export_name}",
        )

    # ------------------------------------------------------------------
    # 2. Inyección explícita: no debe crear ni ejecutar PipelineEngine real
    # ------------------------------------------------------------------
    sentinel = object()
    fake_pipeline = _FakePipelineEngine(sentinel)
    orchestrator = core_orchestrator.CIPSOrchestrator(
        pipeline_engine=fake_pipeline
    )

    _assert(
        orchestrator.pipeline_engine is fake_pipeline,
        "La dependencia PipelineEngine inyectada no fue preservada.",
    )

    project_path = Path("CIPS_F2_3_SMOKE_PROJECT")
    result = orchestrator.execute_pipeline(project_path)

    _assert(
        result is sentinel,
        "execute_pipeline debe devolver sin transformar el resultado del PipelineEngine.",
    )
    _assert(
        fake_pipeline.calls == [project_path],
        "execute_pipeline no delegó exactamente una vez con project_path.",
    )

    # ------------------------------------------------------------------
    # 3. Carga lazy: PipelineEngine debe construirse solo al solicitarlo
    # ------------------------------------------------------------------
    original_pipeline_module = sys.modules.get("pipeline_engine")
    fake_pipeline_module = ModuleType("pipeline_engine")
    lazy_instances: list[object] = []

    class _LazyPipelineEngine:
        def __init__(self) -> None:
            lazy_instances.append(self)

        def execute(self, project_path: Path | None = None) -> object:
            return project_path

    fake_pipeline_module.PipelineEngine = _LazyPipelineEngine
    sys.modules["pipeline_engine"] = fake_pipeline_module

    try:
        lazy_orchestrator = core_orchestrator.CIPSOrchestrator()
        _assert(
            lazy_orchestrator._pipeline_engine is None,
            "PipelineEngine no debe inicializarse durante __init__.",
        )
        _assert(
            len(lazy_instances) == 0,
            "PipelineEngine fue construido antes de acceder a la propiedad.",
        )

        first_instance = lazy_orchestrator.pipeline_engine
        second_instance = lazy_orchestrator.pipeline_engine

        _assert(
            first_instance is second_instance,
            "La carga lazy debe reutilizar la misma instancia.",
        )
        _assert(
            len(lazy_instances) == 1,
            "La carga lazy debe construir PipelineEngine exactamente una vez.",
        )
    finally:
        if original_pipeline_module is None:
            sys.modules.pop("pipeline_engine", None)
        else:
            sys.modules["pipeline_engine"] = original_pipeline_module

    # ------------------------------------------------------------------
    # 4. Contrato público F2.3
    # ------------------------------------------------------------------
    execute_signature = inspect.signature(
        core_orchestrator.CIPSOrchestrator.execute_pipeline
    )
    _assert(
        "project_path" in execute_signature.parameters,
        "execute_pipeline debe publicar el parámetro project_path.",
    )

    init_signature = inspect.signature(
        core_orchestrator.CIPSOrchestrator.__init__
    )
    _assert(
        "pipeline_engine" in init_signature.parameters,
        "CIPSOrchestrator debe admitir inyección de pipeline_engine.",
    )

    print("SMOKE TEST PASSED")
    print("Legacy facade      : VALID")
    print("Pipeline delegation: VALID")
    print("Lazy initialization: VALID")
    print("Public contract    : VALID")
    print("NO LLM / READ ONLY : VALID")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
