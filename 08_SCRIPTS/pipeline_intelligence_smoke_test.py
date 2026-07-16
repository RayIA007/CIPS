"""
=========================================================
Proyecto : CIPS
Release  : 0.9
Build    : 082
Archivo  : pipeline_intelligence_smoke_test.py
Estado   : RELEASE
=========================================================

Prueba integral del Sprint 023A — Intelligence Pipeline Integration.

No llama a Gemini, no requiere credenciales, no ejecuta
finalización real y no escribe reportes reales.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from pipeline_engine import PipelineEngine
from runtime_constants import FINAL_STAGE
from runtime_models import EngineResult, Project


@dataclass
class ScenarioResult:
    name: str
    passed: bool
    errors: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class IntelligencePipelineDouble:
    """Doble configurable de IntelligencePipeline."""

    def __init__(self, success: bool = True) -> None:
        self.success = success
        self.calls: list[dict[str, Any]] = []
        self.telemetry_engine = None

    def execute(
        self,
        project_path: Path | str,
        project_id: str | None = None,
        persist: bool = True,
    ) -> EngineResult:
        self.calls.append(
            {
                "project_path": str(project_path),
                "project_id": project_id,
                "persist": persist,
            }
        )

        if self.success:
            return EngineResult.ok(
                data={
                    "project_id": project_id,
                    "telemetry_summary": {"events_total": 6},
                    "health_report": {"status": "HEALTHY"},
                    "prompt_report": {"status": "EFFICIENT"},
                    "cost_report": {"status": "CALCULATED"},
                    "optimization_plan": {"priority": "LOW"},
                    "project_intelligence": {"status": "GOOD"},
                    "paths": {
                        "project_intelligence_json":
                        "PROJECT_INTELLIGENCE.json"
                    },
                },
                message="Paquete de inteligencia generado correctamente.",
                metadata={
                    "component": "intelligence_pipeline",
                    "project_id": project_id,
                    "intelligence_package_generated": True,
                    "persisted": persist,
                },
            )

        return EngineResult.fail(
            message="Fallo simulado del paquete de inteligencia.",
            errors=["Error simulado."],
            warnings=["Advertencia interna simulada."],
            metadata={
                "component": "intelligence_pipeline",
                "project_id": project_id,
                "failed_component": "project_intelligence_engine",
                "intelligence_package_failed": True,
            },
        )


class PipelineEngineHarness(PipelineEngine):
    """Harness que evita dependencias operativas reales."""

    def __init__(self) -> None:
        self.telemetry_engine = object()
        self.intelligence_pipeline = IntelligencePipelineDouble()
        self.call_order: list[str] = []

    def _attach_telemetry(
        self,
        project: Project,
        stage: str,
        result: EngineResult,
        duration_seconds: float,
    ) -> EngineResult:
        self.call_order.append("telemetry")
        result.metadata["telemetry_recorded"] = True
        result.metadata["telemetry"] = {
            "stage": stage,
            "duration_seconds": duration_seconds,
        }
        return result

    def _attach_intelligence_package(
        self,
        project: Project,
        result: EngineResult,
    ) -> EngineResult:
        self.call_order.append("intelligence")
        return super()._attach_intelligence_package(
            project=project,
            result=result,
        )


class PipelineIntelligenceSmokeTest:
    TEST_NAME = "CIPS Pipeline Intelligence Smoke Test"

    def __init__(self) -> None:
        self.results: list[ScenarioResult] = []

    def run(self) -> bool:
        print(self.TEST_NAME)
        print("=" * 70)
        print(
            "Esta prueba no llama a Gemini, no requiere credenciales "
            "y no escribe reportes."
        )

        scenarios: list[Callable[[], ScenarioResult]] = [
            self._scenario_shared_telemetry_engine,
            self._scenario_intermediate_stage,
            self._scenario_final_publication,
            self._scenario_package_attached,
            self._scenario_success_metadata,
            self._scenario_failure_tolerance,
            self._scenario_failure_warning,
            self._scenario_arguments_propagated,
            self._scenario_execution_order,
            self._scenario_operational_result_preserved,
        ]

        for scenario in scenarios:
            result = scenario()
            self.results.append(result)
            self._print_scenario(result)

        return self._print_summary()

    def _scenario_shared_telemetry_engine(self) -> ScenarioResult:
        engine = PipelineEngine()
        shared = (
            engine.intelligence_pipeline.telemetry_engine
            is engine.telemetry_engine
        )
        errors = [] if shared else [
            "IntelligencePipeline no comparte TelemetryEngine."
        ]
        return ScenarioResult(
            "TelemetryEngine compartido",
            not errors,
            errors,
            {
                "shared_instance": shared,
                "pipeline_type":
                type(engine.intelligence_pipeline).__name__,
            },
        )

    def _scenario_intermediate_stage(self) -> ScenarioResult:
        engine = PipelineEngineHarness()
        project = self._build_project("guion")
        result = self._build_operational_result("storyboard")
        result = engine._attach_telemetry(
            project, "guion", result, 1.0
        )
        should_generate = self._should_generate(
            result, "guion"
        )
        if should_generate:
            result = engine._attach_intelligence_package(
                project, result
            )

        errors: list[str] = []
        if should_generate:
            errors.append(
                "Un Stage intermedio no debía generar inteligencia."
            )
        if engine.intelligence_pipeline.calls:
            errors.append(
                "IntelligencePipeline fue invocado en Stage intermedio."
            )

        return ScenarioResult(
            "Stage intermedio sin inteligencia",
            not errors,
            errors,
            {
                "should_generate": should_generate,
                "calls": len(engine.intelligence_pipeline.calls),
                "result_success": result.success,
            },
        )

    def _scenario_final_publication(self) -> ScenarioResult:
        engine = PipelineEngineHarness()
        project = self._build_project(FINAL_STAGE)
        result = self._build_operational_result(FINAL_STAGE)
        result = engine._attach_telemetry(
            project, "publicacion", result, 2.0
        )
        should_generate = self._should_generate(
            result, "publicacion"
        )
        if should_generate:
            result = engine._attach_intelligence_package(
                project, result
            )

        errors: list[str] = []
        if not should_generate:
            errors.append(
                "Publicación final debía activar inteligencia."
            )
        if len(engine.intelligence_pipeline.calls) != 1:
            errors.append(
                "IntelligencePipeline debía invocarse una vez."
            )

        return ScenarioResult(
            "Publicación final genera inteligencia",
            not errors,
            errors,
            {
                "should_generate": should_generate,
                "calls": len(engine.intelligence_pipeline.calls),
                "result_success": result.success,
            },
        )

    def _scenario_package_attached(self) -> ScenarioResult:
        engine = PipelineEngineHarness()
        result = engine._attach_intelligence_package(
            self._build_project(FINAL_STAGE),
            self._build_operational_result(FINAL_STAGE),
        )
        package = (
            result.data.get("intelligence_package")
            if isinstance(result.data, dict)
            else None
        )
        errors: list[str] = []
        if not isinstance(package, dict):
            errors.append("No se adjuntó intelligence_package.")
        elif "project_intelligence" not in package:
            errors.append(
                "Falta project_intelligence en el paquete."
            )

        return ScenarioResult(
            "Paquete adjunto a result.data",
            not errors,
            errors,
            {
                "package_available": isinstance(package, dict),
                "package_keys":
                sorted(package.keys()) if isinstance(package, dict) else [],
            },
        )

    def _scenario_success_metadata(self) -> ScenarioResult:
        engine = PipelineEngineHarness()
        result = engine._attach_intelligence_package(
            self._build_project(FINAL_STAGE),
            self._build_operational_result(FINAL_STAGE),
        )
        errors: list[str] = []

        if (
            result.metadata.get("intelligence_package_generated")
            is not True
        ):
            errors.append(
                "intelligence_package_generated debía ser True."
            )
        if not isinstance(
            result.metadata.get("intelligence"), dict
        ):
            errors.append("Falta metadata intelligence.")

        return ScenarioResult(
            "Metadata de inteligencia exitosa",
            not errors,
            errors,
            {
                "generated":
                result.metadata.get("intelligence_package_generated"),
                "intelligence_component":
                result.metadata.get("intelligence", {}).get("component"),
            },
        )

    def _scenario_failure_tolerance(self) -> ScenarioResult:
        engine = PipelineEngineHarness()
        engine.intelligence_pipeline = IntelligencePipelineDouble(
            success=False
        )
        result = engine._attach_intelligence_package(
            self._build_project(FINAL_STAGE),
            self._build_operational_result(FINAL_STAGE),
        )
        errors: list[str] = []

        if not result.success:
            errors.append(
                "El fallo de inteligencia no debía invalidar el Pipeline."
            )
        if (
            result.metadata.get("intelligence_package_generated")
            is not False
        ):
            errors.append(
                "intelligence_package_generated debía ser False."
            )
        if (
            result.metadata.get("intelligence_failed_component")
            != "project_intelligence_engine"
        ):
            errors.append("failed_component no se propagó.")

        return ScenarioResult(
            "Tolerancia a fallo de inteligencia",
            not errors,
            errors,
            {
                "result_success": result.success,
                "generated":
                result.metadata.get("intelligence_package_generated"),
                "failed_component":
                result.metadata.get("intelligence_failed_component"),
            },
        )

    def _scenario_failure_warning(self) -> ScenarioResult:
        engine = PipelineEngineHarness()
        engine.intelligence_pipeline = IntelligencePipelineDouble(
            success=False
        )
        result = engine._attach_intelligence_package(
            self._build_project(FINAL_STAGE),
            self._build_operational_result(FINAL_STAGE),
        )
        errors: list[str] = []

        if not any(
            "no fue posible generar el paquete de inteligencia"
            in warning.lower()
            for warning in result.warnings
        ):
            errors.append("Falta advertencia principal.")
        if "Advertencia interna simulada." not in result.warnings:
            errors.append(
                "No se propagó la advertencia interna."
            )

        return ScenarioResult(
            "Advertencia diagnóstica en fallo",
            not errors,
            errors,
            {"warnings": list(result.warnings)},
        )

    def _scenario_arguments_propagated(self) -> ScenarioResult:
        engine = PipelineEngineHarness()
        project = self._build_project(FINAL_STAGE)
        engine._attach_intelligence_package(
            project,
            self._build_operational_result(FINAL_STAGE),
        )
        call = (
            engine.intelligence_pipeline.calls[0]
            if engine.intelligence_pipeline.calls
            else {}
        )
        errors: list[str] = []

        if call.get("project_path") != str(project.path):
            errors.append("project_path no se propagó.")
        if call.get("project_id") != project.project_id:
            errors.append("project_id no se propagó.")
        if call.get("persist") is not True:
            errors.append("persist debía ser True.")

        return ScenarioResult(
            "Propagación de argumentos",
            not errors,
            errors,
            call,
        )

    def _scenario_execution_order(self) -> ScenarioResult:
        engine = PipelineEngineHarness()
        project = self._build_project(FINAL_STAGE)
        result = self._build_operational_result(FINAL_STAGE)
        result = engine._attach_telemetry(
            project, "publicacion", result, 3.0
        )
        if self._should_generate(result, "publicacion"):
            engine._attach_intelligence_package(
                project, result
            )

        errors = []
        if engine.call_order != ["telemetry", "intelligence"]:
            errors.append(
                "El orden esperado era Telemetry → Intelligence."
            )

        return ScenarioResult(
            "Orden Telemetry antes de Intelligence",
            not errors,
            errors,
            {"call_order": list(engine.call_order)},
        )

    def _scenario_operational_result_preserved(
        self,
    ) -> ScenarioResult:
        engine = PipelineEngineHarness()
        original = self._build_operational_result(FINAL_STAGE)
        original_message = original.message
        original_project_id = original.data.get("project_id")

        result = engine._attach_intelligence_package(
            self._build_project(FINAL_STAGE),
            original,
        )
        errors: list[str] = []

        if result.message != original_message:
            errors.append("El mensaje operativo fue modificado.")
        if result.data.get("project_id") != original_project_id:
            errors.append("Los datos operativos fueron modificados.")
        if not result.success:
            errors.append("El éxito operativo no se conservó.")

        return ScenarioResult(
            "Conservación del resultado operativo",
            not errors,
            errors,
            {
                "message_preserved":
                result.message == original_message,
                "project_id_preserved":
                result.data.get("project_id") == original_project_id,
                "success": result.success,
            },
        )

    def _should_generate(
        self,
        result: EngineResult,
        executed_stage: str,
    ) -> bool:
        return bool(
            result.success
            and executed_stage == "publicacion"
            and result.metadata.get("next_stage") == FINAL_STAGE
        )

    def _build_project(self, stage: str) -> Project:
        project_path = (
            Path(__file__).resolve().parents[1]
            / "04_PROYECTOS"
            / "PIPELINE_INTELLIGENCE_SMOKE_TEST"
        )
        return Project(
            project_id="PIPELINE_INTELLIGENCE_TEST",
            path=project_path,
            tema="Prueba de integración de inteligencia",
            stage_actual=stage,
        )

    def _build_operational_result(
        self,
        next_stage: str,
    ) -> EngineResult:
        return EngineResult.ok(
            data={
                "project_id": "PIPELINE_INTELLIGENCE_TEST",
                "completed_stage": "publicacion",
                "next_stage": next_stage,
            },
            message=(
                "Stage 'publicacion' validado. "
                f"Nuevo Stage: '{next_stage}'. "
                "Proyecto finalizado y paquete de exportación generado."
            ),
            metadata={
                "component": "pipeline_engine",
                "project_id": "PIPELINE_INTELLIGENCE_TEST",
                "completed_stage": "publicacion",
                "next_stage": next_stage,
                "finalized": True,
            },
        )

    def _print_scenario(self, result: ScenarioResult) -> None:
        print()
        print("-" * 70)
        print(f"Escenario: {result.name}")
        print("-" * 70)
        print(f"Resultado: {'OK' if result.passed else 'ERROR'}")

        if result.metadata:
            print("Datos:")
            for key, value in result.metadata.items():
                if isinstance(value, (list, dict)):
                    print(
                        f"  {key}: "
                        f"{json.dumps(value, ensure_ascii=False)}"
                    )
                else:
                    print(f"  {key}: {value}")

        if result.errors:
            print("Errores:")
            for error in result.errors:
                print(f"- {error}")

    def _print_summary(self) -> bool:
        passed = sum(
            1 for result in self.results if result.passed
        )
        failed = len(self.results) - passed
        valid = failed == 0

        print()
        print("=" * 70)
        print("RESUMEN PIPELINE INTELLIGENCE")
        print("=" * 70)
        print(f"Escenarios ejecutados: {len(self.results)}")
        print(f"Escenarios aprobados: {passed}")
        print(f"Escenarios fallidos: {failed}")
        print(f"Resultado integral válido: {valid}")

        if valid:
            print()
            print(
                "Pipeline Intelligence Smoke Test "
                "completado correctamente."
            )

        return valid


def main() -> int:
    return 0 if PipelineIntelligenceSmokeTest().run() else 1


if __name__ == "__main__":
    sys.exit(main())