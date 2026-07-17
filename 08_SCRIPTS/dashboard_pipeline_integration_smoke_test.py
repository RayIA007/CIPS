"""
=========================================================
Proyecto : CIPS
Release  : 0.9
Build    : 088
Archivo  : dashboard_pipeline_integration_smoke_test.py
Estado   : RELEASE
=========================================================

Prueba integral de la integración:

IntelligencePipeline
    -> DashboardGenerator
    -> DashboardExporter

Valida generación en memoria, exportación de los 13 artefactos,
metadata, rutas, persist=False y tolerancia a fallos del Dashboard.

No llama a Gemini, no requiere credenciales y no utiliza Internet.
"""

from __future__ import annotations

import json
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from cost_models import CostStatus, ProjectCostReport
from dashboard_exporter import DashboardExporter
from dashboard_generator import DashboardGenerator
from dashboard_models import ExecutiveDashboard
from health_models import HealthStatus, RuntimeHealthReport
from intelligence_pipeline import IntelligencePipeline
from optimization_models import (
    OptimizationPlan,
    OptimizationPriority,
    OptimizationStatus,
)
from project_intelligence_models import (
    IntelligenceStatus,
    ProjectIntelligenceReport,
)
from prompt_intelligence_models import (
    PromptEfficiencyStatus,
    PromptIntelligenceReport,
)
from runtime_models import EngineResult
from telemetry_models import TelemetryEvent


TEST_ROOT = (
    Path(__file__).resolve().parents[1]
    / "04_PROYECTOS"
    / "DASHBOARD_PIPELINE_INTEGRATION_TEST"
)

PROJECT_ID = "DASHBOARD_PIPELINE_TEST"

EXPECTED_FILES = {
    "RUNTIME_HEALTH.json",
    "RUNTIME_HEALTH.md",
    "PROMPT_INTELLIGENCE.json",
    "PROMPT_INTELLIGENCE.md",
    "PROJECT_COST.json",
    "PROJECT_COST.md",
    "OPTIMIZATION_PLAN.json",
    "OPTIMIZATION_PLAN.md",
    "PROJECT_INTELLIGENCE.json",
    "PROJECT_INTELLIGENCE.md",
    "EXECUTIVE_DASHBOARD.json",
    "EXECUTIVE_DASHBOARD.md",
    "EXECUTIVE_DASHBOARD.html",
}


@dataclass
class ScenarioResult:
    """Resultado de un escenario individual."""

    name: str
    passed: bool
    errors: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class TelemetryEngineDouble:
    """Doble de TelemetryEngine con eventos deterministas."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.events = [
            TelemetryEvent(
                event_id="TEL-DASH-001",
                timestamp="2026-07-16T06:00:00Z",
                project_id=PROJECT_ID,
                component="llm_adapter",
                operation="generate",
                stage="storyboard",
                success=True,
                provider="gemini",
                model="gemini-3.5-flash",
                duration_seconds=12.5,
                prompt_tokens=1200,
                response_tokens=300,
                thinking_tokens=100,
                total_tokens=1600,
            ),
            TelemetryEvent(
                event_id="TEL-DASH-002",
                timestamp="2026-07-16T06:01:00Z",
                project_id=PROJECT_ID,
                component="llm_adapter",
                operation="generate",
                stage="seo",
                success=False,
                provider="gemini",
                model="gemini-3.5-flash",
                duration_seconds=8.0,
                prompt_tokens=600,
                response_tokens=0,
                thinking_tokens=0,
                total_tokens=600,
                retry_enabled=True,
                retry_attempts=2,
                retry_count=1,
                retry_exhausted=True,
                errors=["Fallo simulado."],
            ),
        ]

    def read_events(
        self,
        project_path: Path | str,
        output_directory: Path | str | None = None,
        project_id: str | None = None,
    ) -> EngineResult:
        self.calls.append(
            {
                "project_path": str(project_path),
                "output_directory": str(output_directory),
                "project_id": project_id,
            }
        )
        return EngineResult.ok(
            data=list(self.events),
            message="Telemetría simulada leída.",
            metadata={
                "component": "telemetry_engine_double",
                "project_id": project_id or PROJECT_ID,
            },
        )


class RuntimeHealthMonitorDouble:
    """Genera Runtime Health y sus dos artefactos."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def execute(
        self,
        project_path: Path | str,
        project_id: str,
        scope: str,
        output_directory: Path | str,
        persist: bool,
    ) -> EngineResult:
        self.calls.append(
            {
                "project_path": str(project_path),
                "project_id": project_id,
                "scope": scope,
                "output_directory": str(output_directory),
                "persist": persist,
            }
        )

        report = RuntimeHealthReport(
            report_id="HEALTH-DASH-PIPELINE-001",
            generated_at="2026-07-16T06:02:00Z",
            status=HealthStatus.DEGRADED,
            project_id=project_id,
            scope=scope,
            events_total=2,
            successful_events=1,
            failed_events=1,
            success_rate=50.0,
            failure_rate=50.0,
            total_duration_seconds=20.5,
            average_duration_seconds=10.25,
            total_tokens=2200,
            retry_count=1,
            exhausted_events=1,
            recommendations=[
                "Revisar el Stage SEO."
            ],
        )

        metadata = {
            "component": "runtime_health_monitor_double",
            "project_id": project_id,
            "json_path": "",
            "markdown_path": "",
        }

        if persist:
            directory = Path(output_directory)
            directory.mkdir(parents=True, exist_ok=True)

            json_path = directory / "RUNTIME_HEALTH.json"
            markdown_path = directory / "RUNTIME_HEALTH.md"

            json_path.write_text(
                json.dumps(
                    report.to_dict(),
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            markdown_path.write_text(
                "# Runtime Health Report\n\n"
                f"**Proyecto:** {project_id}\n"
                f"**Estado:** {report.status.value}\n",
                encoding="utf-8",
            )

            metadata["json_path"] = str(json_path)
            metadata["markdown_path"] = str(markdown_path)

        return EngineResult.ok(
            data=report,
            message="Runtime Health simulado generado.",
            metadata=metadata,
        )


class PromptAnalyzerDouble:
    """Devuelve Prompt Intelligence determinista."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def analyze_events(
        self,
        events: list[TelemetryEvent],
        project_id: str,
        scope: str,
    ) -> PromptIntelligenceReport:
        self.calls.append(
            {
                "events_total": len(events),
                "project_id": project_id,
                "scope": scope,
            }
        )
        return PromptIntelligenceReport(
            report_id="PROMPT-DASH-PIPELINE-001",
            generated_at="2026-07-16T06:03:00Z",
            project_id=project_id,
            status=PromptEfficiencyStatus.ACCEPTABLE,
            scope=scope,
            analyses_total=2,
            acceptable_analyses=2,
            average_efficiency_score=72.0,
            total_prompt_tokens=1800,
            total_response_tokens=300,
            total_thinking_tokens=100,
            total_tokens=2200,
            recommendations=[
                "Reducir contexto redundante."
            ],
        )


class CostAnalyzerDouble:
    """Devuelve Project Cost determinista."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def analyze_events(
        self,
        events: list[TelemetryEvent],
        project_id: str,
        scope: str,
    ) -> ProjectCostReport:
        self.calls.append(
            {
                "events_total": len(events),
                "project_id": project_id,
                "scope": scope,
            }
        )
        return ProjectCostReport(
            report_id="COST-DASH-PIPELINE-001",
            generated_at="2026-07-16T06:04:00Z",
            project_id=project_id,
            status=CostStatus.CALCULATED,
            scope=scope,
            currency="USD",
            analyses_total=2,
            calculated_analyses=2,
            total_prompt_tokens=1800,
            total_response_tokens=300,
            total_thinking_tokens=100,
            total_tokens=2200,
            total_input_cost=0.00486,
            total_output_cost=0.00486,
            total_thinking_cost=0.00162,
            total_cost=0.01134,
            average_cost_per_stage=0.00567,
            providers=["gemini"],
            models=["gemini-3.5-flash"],
            stages=["storyboard", "seo"],
        )


class RuntimeOptimizerDouble:
    """Devuelve Optimization Plan determinista."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def optimize(
        self,
        project_id: str,
        telemetry_events: list[TelemetryEvent],
        health_report: RuntimeHealthReport,
        prompt_report: PromptIntelligenceReport,
        cost_report: ProjectCostReport,
    ) -> OptimizationPlan:
        self.calls.append(
            {
                "project_id": project_id,
                "events_total": len(telemetry_events),
                "health_status": health_report.status.value,
                "prompt_status": prompt_report.status.value,
                "cost_status": cost_report.status.value,
            }
        )
        return OptimizationPlan(
            plan_id="OPT-DASH-PIPELINE-001",
            generated_at="2026-07-16T06:05:00Z",
            project_id=project_id,
            status=OptimizationStatus.PROPOSED,
            overall_score=68.0,
            priority=OptimizationPriority.HIGH,
            recommendations_total=2,
            actionable_recommendations_total=2,
            automatic_recommendations_total=1,
            estimated_total_savings=0.003,
            currency="USD",
            recommended_execution_order=[
                "Reducir prompt del Storyboard.",
                "Revisar Retry del Stage SEO.",
            ],
        )


class ProjectIntelligenceEngineDouble:
    """Genera Project Intelligence y sus dos artefactos."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def execute(
        self,
        project_path: Path | str,
        telemetry_summary: Any,
        health_report: RuntimeHealthReport,
        prompt_report: PromptIntelligenceReport,
        cost_report: ProjectCostReport,
        optimization_plan: OptimizationPlan,
        persist: bool,
    ) -> EngineResult:
        project_path = Path(project_path)
        project_id = health_report.project_id

        self.calls.append(
            {
                "project_path": str(project_path),
                "project_id": project_id,
                "persist": persist,
                "events_total": telemetry_summary.events_total,
            }
        )

        report = ProjectIntelligenceReport(
            report_id="PROJECT-INTELLIGENCE-DASH-PIPELINE-001",
            generated_at="2026-07-16T06:06:00Z",
            project_id=project_id,
            status=IntelligenceStatus.ATTENTION,
            executive_summary=(
                "El proyecto requiere atención en salud y Retry, "
                "pero conserva oportunidades claras de optimización."
            ),
            ai_project_score=64.5,
            health_score=50.0,
            prompt_efficiency_score=72.0,
            reliability_score=50.0,
            cost_efficiency_score=88.0,
            optimization_potential_score=68.0,
            telemetry_events=2,
            successful_events=1,
            failed_events=1,
            success_rate=50.0,
            total_tokens=2200,
            total_cost=0.01134,
            currency="USD",
            total_duration_seconds=20.5,
            average_duration_seconds=10.25,
            retry_count=1,
            exhausted_events=1,
            strengths=[
                "Costos calculados correctamente."
            ],
            risks=[
                "Runtime degradado.",
                "Retry agotado en SEO.",
            ],
            opportunities=[
                "Reducir contexto redundante."
            ],
            stages=["storyboard", "seo"],
            providers=["gemini"],
            models=["gemini-3.5-flash"],
        )

        metadata = {
            "component": "project_intelligence_engine_double",
            "project_id": project_id,
            "json_path": "",
            "markdown_path": "",
        }

        if persist:
            directory = project_path / "03_TELEMETRIA"
            directory.mkdir(parents=True, exist_ok=True)

            json_path = directory / "PROJECT_INTELLIGENCE.json"
            markdown_path = directory / "PROJECT_INTELLIGENCE.md"

            json_path.write_text(
                json.dumps(
                    report.to_dict(),
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            markdown_path.write_text(
                "# Project Intelligence Report\n\n"
                f"**Proyecto:** {project_id}\n"
                f"**Estado:** {report.status.value}\n",
                encoding="utf-8",
            )

            metadata["json_path"] = str(json_path)
            metadata["markdown_path"] = str(markdown_path)

        return EngineResult.ok(
            data={"report": report},
            message="Project Intelligence simulado generado.",
            metadata=metadata,
        )


class FailingDashboardGenerator:
    """Simula una excepción al generar el Dashboard."""

    def generate(self, **_: Any) -> ExecutiveDashboard:
        raise RuntimeError("Fallo simulado de DashboardGenerator.")


class FailingDashboardExporter:
    """Simula un fallo controlado de exportación."""

    def execute(self, **_: Any) -> EngineResult:
        return EngineResult.fail(
            message="Fallo simulado de DashboardExporter.",
            errors=["No fue posible persistir el Dashboard."],
            metadata={
                "component": "dashboard_exporter_double",
            },
        )


class DashboardPipelineIntegrationSmokeTest:
    """
    Valida la integración completa del Dashboard.
    """

    TEST_NAME = (
        "CIPS Dashboard Pipeline Integration Smoke Test"
    )

    def __init__(self) -> None:
        self.results: list[ScenarioResult] = []
        self.pipeline: IntelligencePipeline | None = None
        self.result: EngineResult | None = None

    def run(self) -> bool:
        self._prepare()

        print(self.TEST_NAME)
        print("=" * 70)
        print(
            "Esta prueba no llama a Gemini, no requiere credenciales "
            "y no necesita conexión a Internet."
        )
        print(f"Ruta temporal: {TEST_ROOT}")

        scenarios: list[Callable[[], ScenarioResult]] = [
            self._scenario_component_registration,
            self._scenario_complete_execution,
            self._scenario_dashboard_attached,
            self._scenario_dashboard_metadata,
            self._scenario_thirteen_artifacts,
            self._scenario_exported_content,
            self._scenario_paths_registered,
            self._scenario_persist_false,
            self._scenario_exporter_failure_tolerance,
            self._scenario_generator_failure_tolerance,
        ]

        for scenario in scenarios:
            result = scenario()
            self.results.append(result)
            self._print_scenario(result)

        return self._print_summary()

    def _prepare(self) -> None:
        shutil.rmtree(TEST_ROOT, ignore_errors=True)
        TEST_ROOT.mkdir(parents=True, exist_ok=True)

    def _build_pipeline(
        self,
        *,
        dashboard_generator: Any | None = None,
        dashboard_exporter: Any | None = None,
    ) -> IntelligencePipeline:
        return IntelligencePipeline(
            telemetry_engine=TelemetryEngineDouble(),
            runtime_health_monitor=RuntimeHealthMonitorDouble(),
            prompt_intelligence_analyzer=PromptAnalyzerDouble(),
            cost_analyzer=CostAnalyzerDouble(),
            runtime_optimizer=RuntimeOptimizerDouble(),
            project_intelligence_engine=(
                ProjectIntelligenceEngineDouble()
            ),
            dashboard_generator=(
                dashboard_generator
                if dashboard_generator is not None
                else DashboardGenerator()
            ),
            dashboard_exporter=(
                dashboard_exporter
                if dashboard_exporter is not None
                else DashboardExporter()
            ),
        )

    def _require_result(self) -> EngineResult:
        if self.result is None:
            raise RuntimeError(
                "La ejecución integral aún no existe."
            )
        return self.result

    def _scenario_component_registration(
        self,
    ) -> ScenarioResult:
        pipeline = self._build_pipeline()
        info = pipeline.get_component_info()

        errors: list[str] = []

        if not info.get("uses_dashboard_generator"):
            errors.append(
                "get_component_info() no registra DashboardGenerator."
            )

        if not info.get("uses_dashboard_exporter"):
            errors.append(
                "get_component_info() no registra DashboardExporter."
            )

        if not info.get("dashboard_fault_tolerant"):
            errors.append(
                "No se declaró tolerancia a fallos del Dashboard."
            )

        report_files = set(info.get("report_files", []))
        missing = EXPECTED_FILES - report_files

        if missing:
            errors.append(
                "Faltan report_files: "
                + ", ".join(sorted(missing))
            )

        return ScenarioResult(
            name="Registro estructural del componente",
            passed=not errors,
            errors=errors,
            metadata={
                "component": info.get("component"),
                "version": info.get("version"),
                "report_files": len(report_files),
                "next_component": info.get("next_component"),
            },
        )

    def _scenario_complete_execution(
        self,
    ) -> ScenarioResult:
        self.pipeline = self._build_pipeline()
        self.result = self.pipeline.execute(
            project_path=TEST_ROOT,
            project_id=PROJECT_ID,
            persist=True,
        )

        result = self._require_result()
        errors: list[str] = []

        if not result.success:
            errors.append(
                "IntelligencePipeline.execute() debía ser exitoso."
            )
            errors.extend(result.errors)

        if not result.metadata.get(
            "intelligence_package_generated"
        ):
            errors.append(
                "No se marcó intelligence_package_generated."
            )

        if result.data.get("project_id") != PROJECT_ID:
            errors.append(
                "project_id no fue conservado."
            )

        return ScenarioResult(
            name="Ejecución integral con Dashboard",
            passed=not errors,
            errors=errors,
            metadata={
                "success": result.success,
                "message": result.message,
                "warnings": len(result.warnings),
                "project_id": result.data.get("project_id"),
            },
        )

    def _scenario_dashboard_attached(
        self,
    ) -> ScenarioResult:
        result = self._require_result()
        dashboard = result.data.get("executive_dashboard")

        errors: list[str] = []

        if not isinstance(
            dashboard,
            ExecutiveDashboard,
        ):
            errors.append(
                "executive_dashboard no es ExecutiveDashboard."
            )
        else:
            if dashboard.project_id != PROJECT_ID:
                errors.append(
                    "El Dashboard perdió project_id."
                )

            if not dashboard.cards:
                errors.append(
                    "El Dashboard no contiene tarjetas."
                )

            if not dashboard.charts:
                errors.append(
                    "El Dashboard no contiene gráficos."
                )

            if not dashboard.sections:
                errors.append(
                    "El Dashboard no contiene secciones."
                )

        return ScenarioResult(
            name="Dashboard adjunto al EngineResult",
            passed=not errors,
            errors=errors,
            metadata={
                "dashboard_type": type(dashboard).__name__,
                "cards": (
                    len(dashboard.cards)
                    if isinstance(dashboard, ExecutiveDashboard)
                    else 0
                ),
                "charts": (
                    len(dashboard.charts)
                    if isinstance(dashboard, ExecutiveDashboard)
                    else 0
                ),
                "sections": (
                    len(dashboard.sections)
                    if isinstance(dashboard, ExecutiveDashboard)
                    else 0
                ),
            },
        )

    def _scenario_dashboard_metadata(
        self,
    ) -> ScenarioResult:
        result = self._require_result()
        metadata = result.metadata

        errors: list[str] = []

        if metadata.get("dashboard_generated") is not True:
            errors.append(
                "dashboard_generated debía ser True."
            )

        if metadata.get("dashboard_exported") is not True:
            errors.append(
                "dashboard_exported debía ser True."
            )

        if not metadata.get("dashboard_status"):
            errors.append(
                "dashboard_status quedó vacío."
            )

        if metadata.get("persisted") is not True:
            errors.append(
                "persisted debía ser True."
            )

        return ScenarioResult(
            name="Metadata de integración",
            passed=not errors,
            errors=errors,
            metadata={
                "dashboard_generated": metadata.get(
                    "dashboard_generated"
                ),
                "dashboard_exported": metadata.get(
                    "dashboard_exported"
                ),
                "dashboard_status": metadata.get(
                    "dashboard_status"
                ),
                "persisted": metadata.get("persisted"),
            },
        )

    def _scenario_thirteen_artifacts(
        self,
    ) -> ScenarioResult:
        telemetry_directory = TEST_ROOT / "03_TELEMETRIA"

        actual_files = {
            path.name
            for path in telemetry_directory.iterdir()
            if path.is_file()
        }

        missing = EXPECTED_FILES - actual_files
        unexpected = actual_files - EXPECTED_FILES

        errors: list[str] = []

        if missing:
            errors.append(
                "Faltan artefactos: "
                + ", ".join(sorted(missing))
            )

        if unexpected:
            errors.append(
                "Existen artefactos inesperados: "
                + ", ".join(sorted(unexpected))
            )

        return ScenarioResult(
            name="Generación de los 13 artefactos",
            passed=not errors,
            errors=errors,
            metadata={
                "expected": len(EXPECTED_FILES),
                "generated": len(actual_files),
                "files": sorted(actual_files),
            },
        )

    def _scenario_exported_content(
        self,
    ) -> ScenarioResult:
        directory = TEST_ROOT / "03_TELEMETRIA"

        json_path = directory / "EXECUTIVE_DASHBOARD.json"
        markdown_path = directory / "EXECUTIVE_DASHBOARD.md"
        html_path = directory / "EXECUTIVE_DASHBOARD.html"

        errors: list[str] = []

        try:
            payload = json.loads(
                json_path.read_text(encoding="utf-8")
            )
        except Exception as error:
            payload = {}
            errors.append(f"JSON inválido: {error}")

        markdown = (
            markdown_path.read_text(encoding="utf-8")
            if markdown_path.exists()
            else ""
        )
        html = (
            html_path.read_text(encoding="utf-8")
            if html_path.exists()
            else ""
        )

        if payload.get("project_id") != PROJECT_ID:
            errors.append(
                "El JSON del Dashboard tiene project_id incorrecto."
            )

        if payload.get("cards_total", 0) <= 0:
            errors.append(
                "El JSON no registra tarjetas."
            )

        if "# CIPS Executive Dashboard" not in markdown:
            errors.append(
                "Markdown sin encabezado ejecutivo."
            )

        if "<!DOCTYPE html>" not in html:
            errors.append(
                "HTML sin DOCTYPE."
            )

        if "<canvas" not in html:
            errors.append(
                "HTML sin gráficos canvas."
            )

        if "https://" in html or "http://" in html:
            errors.append(
                "HTML contiene dependencias externas."
            )

        return ScenarioResult(
            name="Contenido JSON, Markdown y HTML",
            passed=not errors,
            errors=errors,
            metadata={
                "json_cards": payload.get("cards_total"),
                "markdown_characters": len(markdown),
                "html_characters": len(html),
                "html_canvas": html.count("<canvas"),
            },
        )

    def _scenario_paths_registered(
        self,
    ) -> ScenarioResult:
        result = self._require_result()
        paths = result.data.get("paths", {})

        expected_keys = {
            "runtime_health_json",
            "runtime_health_markdown",
            "prompt_intelligence_json",
            "prompt_intelligence_markdown",
            "project_cost_json",
            "project_cost_markdown",
            "optimization_plan_json",
            "optimization_plan_markdown",
            "project_intelligence_json",
            "project_intelligence_markdown",
            "executive_dashboard_json",
            "executive_dashboard_markdown",
            "executive_dashboard_html",
        }

        errors: list[str] = []

        missing = expected_keys - set(paths)

        if missing:
            errors.append(
                "Faltan rutas: "
                + ", ".join(sorted(missing))
            )

        nonexistent = [
            key
            for key in expected_keys
            if key in paths
            and (
                not paths[key]
                or not Path(paths[key]).exists()
            )
        ]

        if nonexistent:
            errors.append(
                "Rutas vacías o inexistentes: "
                + ", ".join(sorted(nonexistent))
            )

        return ScenarioResult(
            name="Registro de las 13 rutas",
            passed=not errors,
            errors=errors,
            metadata={
                "paths_total": len(paths),
                "validated_paths": len(expected_keys),
            },
        )

    def _scenario_persist_false(
        self,
    ) -> ScenarioResult:
        project_path = TEST_ROOT / "NO_PERSIST"
        project_path.mkdir(parents=True, exist_ok=True)

        pipeline = self._build_pipeline()
        result = pipeline.execute(
            project_path=project_path,
            project_id=PROJECT_ID,
            persist=False,
        )

        directory = project_path / "03_TELEMETRIA"
        files = (
            list(directory.iterdir())
            if directory.exists()
            else []
        )

        errors: list[str] = []

        if not result.success:
            errors.append(
                "persist=False debía conservar ejecución exitosa."
            )

        if not isinstance(
            result.data.get("executive_dashboard"),
            ExecutiveDashboard,
        ):
            errors.append(
                "persist=False debía generar Dashboard en memoria."
            )

        if result.metadata.get("dashboard_generated") is not True:
            errors.append(
                "persist=False no marcó dashboard_generated."
            )

        if result.metadata.get("dashboard_exported") is not False:
            errors.append(
                "persist=False debía dejar dashboard_exported=False."
            )

        if files:
            errors.append(
                "persist=False escribió archivos inesperados."
            )

        return ScenarioResult(
            name="Generación en memoria con persist=False",
            passed=not errors,
            errors=errors,
            metadata={
                "success": result.success,
                "dashboard_generated": result.metadata.get(
                    "dashboard_generated"
                ),
                "dashboard_exported": result.metadata.get(
                    "dashboard_exported"
                ),
                "files_written": len(files),
            },
        )

    def _scenario_exporter_failure_tolerance(
        self,
    ) -> ScenarioResult:
        project_path = TEST_ROOT / "EXPORTER_FAILURE"
        project_path.mkdir(parents=True, exist_ok=True)

        pipeline = self._build_pipeline(
            dashboard_exporter=FailingDashboardExporter()
        )
        result = pipeline.execute(
            project_path=project_path,
            project_id=PROJECT_ID,
            persist=True,
        )

        errors: list[str] = []

        if not result.success:
            errors.append(
                "Un fallo del exportador no debía invalidar "
                "el paquete de inteligencia."
            )

        if not isinstance(
            result.data.get("executive_dashboard"),
            ExecutiveDashboard,
        ):
            errors.append(
                "El Dashboard debía conservarse en memoria."
            )

        if result.metadata.get("dashboard_generated") is not True:
            errors.append(
                "dashboard_generated debía ser True."
            )

        if result.metadata.get("dashboard_exported") is not False:
            errors.append(
                "dashboard_exported debía ser False."
            )

        if not any(
            "no pudo exportarse" in warning.lower()
            for warning in result.warnings
        ):
            errors.append(
                "No se registró advertencia de exportación."
            )

        return ScenarioResult(
            name="Tolerancia a fallo de DashboardExporter",
            passed=not errors,
            errors=errors,
            metadata={
                "success": result.success,
                "dashboard_generated": result.metadata.get(
                    "dashboard_generated"
                ),
                "dashboard_exported": result.metadata.get(
                    "dashboard_exported"
                ),
                "warnings": len(result.warnings),
            },
        )

    def _scenario_generator_failure_tolerance(
        self,
    ) -> ScenarioResult:
        project_path = TEST_ROOT / "GENERATOR_FAILURE"
        project_path.mkdir(parents=True, exist_ok=True)

        pipeline = self._build_pipeline(
            dashboard_generator=FailingDashboardGenerator()
        )
        result = pipeline.execute(
            project_path=project_path,
            project_id=PROJECT_ID,
            persist=True,
        )

        errors: list[str] = []

        if not result.success:
            errors.append(
                "Un fallo del generador no debía invalidar "
                "el paquete de inteligencia."
            )

        if result.data.get("executive_dashboard") is not None:
            errors.append(
                "El Dashboard debía ser None tras fallar el generador."
            )

        if result.metadata.get("dashboard_generated") is not False:
            errors.append(
                "dashboard_generated debía ser False."
            )

        if result.metadata.get("dashboard_exported") is not False:
            errors.append(
                "dashboard_exported debía ser False."
            )

        if not any(
            "no fue posible generar" in warning.lower()
            for warning in result.warnings
        ):
            errors.append(
                "No se registró advertencia de generación."
            )

        return ScenarioResult(
            name="Tolerancia a fallo de DashboardGenerator",
            passed=not errors,
            errors=errors,
            metadata={
                "success": result.success,
                "dashboard_generated": result.metadata.get(
                    "dashboard_generated"
                ),
                "dashboard_exported": result.metadata.get(
                    "dashboard_exported"
                ),
                "warnings": len(result.warnings),
            },
        )

    def _print_scenario(
        self,
        result: ScenarioResult,
    ) -> None:
        print()
        print("-" * 70)
        print(f"Escenario: {result.name}")
        print("-" * 70)
        print(
            f"Resultado: "
            f"{'OK' if result.passed else 'ERROR'}"
        )

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
            result.passed
            for result in self.results
        )
        failed = len(self.results) - passed
        valid = failed == 0

        print()
        print("=" * 70)
        print("RESUMEN DASHBOARD PIPELINE INTEGRATION")
        print("=" * 70)
        print(
            f"Escenarios ejecutados: {len(self.results)}"
        )
        print(f"Escenarios aprobados: {passed}")
        print(f"Escenarios fallidos: {failed}")
        print(f"Resultado integral válido: {valid}")
        print()
        print("Artefactos conservados para inspección:")
        print(f"- {TEST_ROOT}")

        if valid:
            print()
            print(
                "Dashboard Pipeline Integration Smoke Test "
                "completado correctamente."
            )

        return valid


def main() -> int:
    return (
        0
        if DashboardPipelineIntegrationSmokeTest().run()
        else 1
    )


if __name__ == "__main__":
    sys.exit(main())