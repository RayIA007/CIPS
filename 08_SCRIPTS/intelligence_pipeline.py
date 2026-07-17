"""
=========================================================
Proyecto : CIPS
Release  : 0.9
Build    : 087
Archivo  : intelligence_pipeline.py
Estado   : RELEASE
=========================================================

Orquesta la generación completa del paquete de inteligencia.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from cost_analyzer import CostAnalyzer
from dashboard_exporter import DashboardExporter
from dashboard_generator import DashboardGenerator
from dashboard_models import ExecutiveDashboard
from cost_models import ProjectCostReport
from health_models import RuntimeHealthReport
from optimization_models import OptimizationPlan
from project_intelligence_engine import ProjectIntelligenceEngine
from project_intelligence_models import ProjectIntelligenceReport
from prompt_intelligence_analyzer import PromptIntelligenceAnalyzer
from prompt_intelligence_models import PromptIntelligenceReport
from runtime_health_monitor import RuntimeHealthMonitor
from runtime_models import EngineResult
from runtime_optimizer import RuntimeOptimizer
from telemetry_engine import TelemetryEngine
from telemetry_models import TelemetryEvent, TelemetrySummary


class IntelligencePipeline:
    """Orquestador único del Intelligence Framework."""

    COMPONENT_NAME = "intelligence_pipeline"
    VERSION = "0.9"

    TELEMETRY_DIRECTORY = "03_TELEMETRIA"
    PROMPT_JSON_FILENAME = "PROMPT_INTELLIGENCE.json"
    PROMPT_MARKDOWN_FILENAME = "PROMPT_INTELLIGENCE.md"
    COST_JSON_FILENAME = "PROJECT_COST.json"
    COST_MARKDOWN_FILENAME = "PROJECT_COST.md"
    OPTIMIZATION_JSON_FILENAME = "OPTIMIZATION_PLAN.json"
    OPTIMIZATION_MARKDOWN_FILENAME = "OPTIMIZATION_PLAN.md"

    def __init__(
        self,
        telemetry_engine: TelemetryEngine | None = None,
        runtime_health_monitor: RuntimeHealthMonitor | None = None,
        prompt_intelligence_analyzer: PromptIntelligenceAnalyzer | None = None,
        cost_analyzer: CostAnalyzer | None = None,
        runtime_optimizer: RuntimeOptimizer | None = None,
        project_intelligence_engine: ProjectIntelligenceEngine | None = None,
        dashboard_generator: DashboardGenerator | None = None,
        dashboard_exporter: DashboardExporter | None = None,
    ) -> None:
        self.telemetry_engine = telemetry_engine or TelemetryEngine()
        self.runtime_health_monitor = (
            runtime_health_monitor
            or RuntimeHealthMonitor(
                telemetry_engine=self.telemetry_engine
            )
        )
        self.prompt_intelligence_analyzer = (
            prompt_intelligence_analyzer
            or PromptIntelligenceAnalyzer()
        )
        self.cost_analyzer = cost_analyzer or CostAnalyzer()
        self.runtime_optimizer = runtime_optimizer or RuntimeOptimizer()
        self.project_intelligence_engine = (
            project_intelligence_engine
            or ProjectIntelligenceEngine()
        )
        self.dashboard_generator = (
            dashboard_generator
            or DashboardGenerator()
        )
        self.dashboard_exporter = (
            dashboard_exporter
            or DashboardExporter()
        )

    def execute(
        self,
        project_path: Path | str,
        project_id: str | None = None,
        persist: bool = True,
    ) -> EngineResult:
        """Genera el paquete completo de inteligencia."""

        try:
            resolved_project_path = Path(
                project_path
            ).expanduser().resolve()

            if not resolved_project_path.exists():
                return EngineResult.fail(
                    message=(
                        "No existe la ruta del proyecto "
                        "para generar inteligencia."
                    ),
                    errors=[str(resolved_project_path)],
                    metadata={
                        "component": self.COMPONENT_NAME,
                        "version": self.VERSION,
                    },
                )

            telemetry_directory = (
                resolved_project_path
                / self.TELEMETRY_DIRECTORY
            )

            events_result = self.telemetry_engine.read_events(
                project_path=resolved_project_path,
                output_directory=telemetry_directory,
                project_id=project_id,
            )

            if not events_result.success:
                return self._failure(
                    message=(
                        "No fue posible leer la telemetría "
                        "del proyecto."
                    ),
                    component="telemetry_engine",
                    source_result=events_result,
                    project_path=resolved_project_path,
                )

            events = [
                event
                for event in events_result.data
                if isinstance(event, TelemetryEvent)
            ]

            resolved_project_id = str(
                project_id
                or self._infer_project_id(events)
                or resolved_project_path.name
            ).strip()

            telemetry_summary = self._build_telemetry_summary(
                events=events,
                project_id=resolved_project_id,
            )

            health_result = self.runtime_health_monitor.execute(
                project_path=resolved_project_path,
                project_id=resolved_project_id,
                scope="project",
                output_directory=telemetry_directory,
                persist=persist,
            )

            if not health_result.success:
                return self._failure(
                    message="No fue posible generar Runtime Health.",
                    component="runtime_health_monitor",
                    source_result=health_result,
                    project_path=resolved_project_path,
                )

            health_report = health_result.data

            if not isinstance(health_report, RuntimeHealthReport):
                return EngineResult.fail(
                    message=(
                        "RuntimeHealthMonitor no devolvió "
                        "RuntimeHealthReport."
                    ),
                    errors=[
                        "Tipo de dato de salud incompatible."
                    ],
                    metadata=self._base_metadata(
                        resolved_project_path,
                        resolved_project_id,
                    ),
                )

            prompt_report = (
                self.prompt_intelligence_analyzer.analyze_events(
                    events=events,
                    project_id=resolved_project_id,
                    scope="project",
                )
            )

            cost_report = self.cost_analyzer.analyze_events(
                events=events,
                project_id=resolved_project_id,
                scope="project",
            )

            optimization_plan = self.runtime_optimizer.optimize(
                project_id=resolved_project_id,
                telemetry_events=events,
                health_report=health_report,
                prompt_report=prompt_report,
                cost_report=cost_report,
            )

            intermediate_paths = self._persist_intermediate_reports(
                telemetry_directory=telemetry_directory,
                prompt_report=prompt_report,
                cost_report=cost_report,
                optimization_plan=optimization_plan,
                persist=persist,
            )

            project_result = self.project_intelligence_engine.execute(
                project_path=resolved_project_path,
                telemetry_summary=telemetry_summary,
                health_report=health_report,
                prompt_report=prompt_report,
                cost_report=cost_report,
                optimization_plan=optimization_plan,
                persist=persist,
            )

            if not project_result.success:
                return self._failure(
                    message=(
                        "No fue posible generar "
                        "Project Intelligence."
                    ),
                    component="project_intelligence_engine",
                    source_result=project_result,
                    project_path=resolved_project_path,
                )

            project_report = (
                project_result.data.get("report")
                if isinstance(project_result.data, dict)
                else None
            )

            if not isinstance(
                project_report,
                ProjectIntelligenceReport,
            ):
                return EngineResult.fail(
                    message=(
                        "ProjectIntelligenceEngine no devolvió "
                        "ProjectIntelligenceReport."
                    ),
                    errors=[
                        "Tipo de Project Intelligence incompatible."
                    ],
                    metadata={
                        **self._base_metadata(
                            resolved_project_path,
                            resolved_project_id,
                        ),
                        "failed_component": (
                            "project_intelligence_engine"
                        ),
                        "intelligence_package_failed": True,
                    },
                )

            dashboard: ExecutiveDashboard | None = None
            dashboard_paths = {
                "executive_dashboard_json": "",
                "executive_dashboard_markdown": "",
                "executive_dashboard_html": "",
            }
            dashboard_warnings: list[str] = []
            dashboard_exported = False

            try:
                dashboard = self.dashboard_generator.generate(
                    project_intelligence=project_report,
                    health_report=health_report,
                    prompt_report=prompt_report,
                    cost_report=cost_report,
                    optimization_plan=optimization_plan,
                )

                if persist:
                    dashboard_result = (
                        self.dashboard_exporter.execute(
                            dashboard=dashboard,
                            project_path=resolved_project_path,
                            output_directory=telemetry_directory,
                            export_json=True,
                            export_markdown=True,
                            export_html=True,
                        )
                    )

                    if dashboard_result.success:
                        dashboard_exported = True
                        dashboard_paths = {
                            "executive_dashboard_json": (
                                dashboard_result.metadata.get(
                                    "json_path",
                                    "",
                                )
                            ),
                            "executive_dashboard_markdown": (
                                dashboard_result.metadata.get(
                                    "markdown_path",
                                    "",
                                )
                            ),
                            "executive_dashboard_html": (
                                dashboard_result.metadata.get(
                                    "html_path",
                                    "",
                                )
                            ),
                        }
                    else:
                        dashboard_warnings.append(
                            "El Dashboard fue generado en memoria, "
                            "pero no pudo exportarse: "
                            f"{dashboard_result.message}"
                        )
                        dashboard_warnings.extend(
                            dashboard_result.warnings
                        )
                        dashboard_warnings.extend(
                            dashboard_result.errors
                        )

            except Exception as error:
                dashboard_warnings.append(
                    "No fue posible generar el Executive "
                    f"Dashboard: {error}"
                )

            warnings = self._unique_strings(
                [
                    *events_result.warnings,
                    *health_result.warnings,
                    *prompt_report.warnings,
                    *cost_report.warnings,
                    *optimization_plan.warnings,
                    *project_result.warnings,
                    *dashboard_warnings,
                ]
            )

            return EngineResult.ok(
                data={
                    "project_id": resolved_project_id,
                    "events": events,
                    "telemetry_summary": telemetry_summary,
                    "health_report": health_report,
                    "prompt_report": prompt_report,
                    "cost_report": cost_report,
                    "optimization_plan": optimization_plan,
                    "project_intelligence": project_report,
                    "executive_dashboard": dashboard,
                    "paths": {
                        **intermediate_paths,
                        "runtime_health_json": (
                            health_result.metadata.get(
                                "json_path", ""
                            )
                        ),
                        "runtime_health_markdown": (
                            health_result.metadata.get(
                                "markdown_path", ""
                            )
                        ),
                        "project_intelligence_json": (
                            project_result.metadata.get(
                                "json_path", ""
                            )
                        ),
                        "project_intelligence_markdown": (
                            project_result.metadata.get(
                                "markdown_path", ""
                            )
                        ),
                        **dashboard_paths,
                    },
                },
                message=(
                    "Paquete de inteligencia generado "
                    "correctamente."
                ),
                warnings=warnings,
                metadata={
                    **self._base_metadata(
                        resolved_project_path,
                        resolved_project_id,
                    ),
                    "events_total": len(events),
                    "health_status": health_report.status.value,
                    "prompt_status": prompt_report.status.value,
                    "cost_status": cost_report.status.value,
                    "optimization_priority": (
                        optimization_plan.priority.value
                    ),
                    "project_intelligence_status": (
                        project_report.status.value
                    ),
                    "dashboard_generated": (
                        dashboard is not None
                    ),
                    "dashboard_exported": dashboard_exported,
                    "dashboard_status": (
                        dashboard.status.value
                        if dashboard is not None
                        else ""
                    ),
                    "persisted": bool(persist),
                    "intelligence_package_generated": True,
                },
            )

        except Exception as error:
            return EngineResult.fail(
                message="Error inesperado en IntelligencePipeline.",
                errors=[str(error)],
                metadata={
                    "component": self.COMPONENT_NAME,
                    "version": self.VERSION,
                    "exception_type": error.__class__.__name__,
                },
            )

    def _build_telemetry_summary(
        self,
        *,
        events: list[TelemetryEvent],
        project_id: str,
    ) -> TelemetrySummary:
        summary = TelemetrySummary(
            scope="project",
            scope_id=project_id,
            metadata={
                "component": self.COMPONENT_NAME,
                "version": self.VERSION,
                "source": "telemetry_events_reconstruction",
            },
        )

        for event in events:
            summary.register_event(event)

        return summary

    def _persist_intermediate_reports(
        self,
        *,
        telemetry_directory: Path,
        prompt_report: PromptIntelligenceReport,
        cost_report: ProjectCostReport,
        optimization_plan: OptimizationPlan,
        persist: bool,
    ) -> dict[str, str]:
        paths = {
            "prompt_intelligence_json": "",
            "prompt_intelligence_markdown": "",
            "project_cost_json": "",
            "project_cost_markdown": "",
            "optimization_plan_json": "",
            "optimization_plan_markdown": "",
        }

        if not persist:
            return paths

        telemetry_directory.mkdir(parents=True, exist_ok=True)

        prompt_json = telemetry_directory / self.PROMPT_JSON_FILENAME
        prompt_markdown = (
            telemetry_directory / self.PROMPT_MARKDOWN_FILENAME
        )
        cost_json = telemetry_directory / self.COST_JSON_FILENAME
        cost_markdown = telemetry_directory / self.COST_MARKDOWN_FILENAME
        optimization_json = (
            telemetry_directory / self.OPTIMIZATION_JSON_FILENAME
        )
        optimization_markdown = (
            telemetry_directory / self.OPTIMIZATION_MARKDOWN_FILENAME
        )

        self._write_json(prompt_json, prompt_report.to_dict())
        self._write_text(
            prompt_markdown,
            self._render_prompt_markdown(prompt_report),
        )
        self._write_json(cost_json, cost_report.to_dict())
        self._write_text(
            cost_markdown,
            self._render_cost_markdown(cost_report),
        )
        self._write_json(
            optimization_json,
            optimization_plan.to_dict(),
        )
        self._write_text(
            optimization_markdown,
            self._render_optimization_markdown(
                optimization_plan
            ),
        )

        return {
            "prompt_intelligence_json": str(prompt_json),
            "prompt_intelligence_markdown": str(prompt_markdown),
            "project_cost_json": str(cost_json),
            "project_cost_markdown": str(cost_markdown),
            "optimization_plan_json": str(optimization_json),
            "optimization_plan_markdown": str(
                optimization_markdown
            ),
        }

    def _render_prompt_markdown(
        self,
        report: PromptIntelligenceReport,
    ) -> str:
        lines = [
            "# Prompt Intelligence Report",
            "",
            f"**Proyecto:** {report.project_id}",
            f"**Estado:** {report.status.value}",
            (
                "**Eficiencia promedio:** "
                f"{report.average_efficiency_score}/100"
            ),
            f"**Análisis:** {report.analyses_total}",
            "",
            "## Stages",
            "",
        ]

        for analysis in report.analyses:
            lines.extend(
                [
                    f"### {analysis.stage or 'sin_stage'}",
                    "",
                    f"- Estado: {analysis.status.value}",
                    f"- Score: {analysis.efficiency_score}",
                    f"- Prompt tokens: {analysis.prompt_tokens}",
                    f"- Response tokens: {analysis.response_tokens}",
                    f"- Yield: {analysis.response_yield_percent}%",
                    "",
                ]
            )

        if report.recommendations:
            lines.extend(
                [
                    "## Recomendaciones",
                    "",
                    *[
                        f"- {item}"
                        for item in report.recommendations
                    ],
                    "",
                ]
            )

        return "\n".join(lines)

    def _render_cost_markdown(
        self,
        report: ProjectCostReport,
    ) -> str:
        lines = [
            "# Project Cost Report",
            "",
            f"**Proyecto:** {report.project_id}",
            f"**Estado:** {report.status.value}",
            (
                f"**Costo total:** {report.total_cost} "
                f"{report.currency}"
            ),
            f"**Tokens totales:** {report.total_tokens}",
            "",
            "## Costos por Stage",
            "",
            "| Stage | Estado | Tokens | Costo |",
            "|---|---|---:|---:|",
        ]

        for analysis in report.analyses:
            lines.append(
                (
                    f"| {analysis.stage} "
                    f"| {analysis.status.value} "
                    f"| {analysis.token_usage.total_tokens} "
                    f"| {analysis.cost.total_cost} |"
                )
            )

        lines.append("")
        return "\n".join(lines)

    def _render_optimization_markdown(
        self,
        plan: OptimizationPlan,
    ) -> str:
        lines = [
            "# Optimization Plan",
            "",
            f"**Proyecto:** {plan.project_id}",
            f"**Estado:** {plan.status.value}",
            f"**Prioridad:** {plan.priority.value}",
            f"**Score general:** {plan.overall_score}/100",
            f"**Recomendaciones:** {plan.recommendations_total}",
            (
                f"**Ahorro estimado:** "
                f"{plan.estimated_total_savings} {plan.currency}"
            ),
            "",
            "## Recomendaciones",
            "",
        ]

        recommendations = [
            recommendation
            for analysis in plan.analyses
            for recommendation in analysis.recommendations
        ]

        if recommendations:
            for recommendation in recommendations:
                lines.extend(
                    [
                        (
                            f"### [{recommendation.priority.value}] "
                            f"{recommendation.title}"
                        ),
                        "",
                        recommendation.description,
                        "",
                        (
                            f"- Acción: "
                            f"{recommendation.action_type.value}"
                        ),
                        f"- Stage: {recommendation.stage}",
                        (
                            f"- Confianza: "
                            f"{recommendation.confidence_score}%"
                        ),
                        (
                            f"- Mejora esperada: "
                            f"{recommendation.expected_improvement_percent}%"
                        ),
                        "",
                    ]
                )
        else:
            lines.append("No existen recomendaciones.")

        return "\n".join(lines)

    def _write_json(
        self,
        path: Path,
        payload: dict[str, Any],
    ) -> None:
        temporary_path = path.with_suffix(
            f"{path.suffix}.tmp"
        )
        temporary_path.write_text(
            json.dumps(
                payload,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        temporary_path.replace(path)

    def _write_text(
        self,
        path: Path,
        content: str,
    ) -> None:
        temporary_path = path.with_suffix(
            f"{path.suffix}.tmp"
        )
        temporary_path.write_text(
            content.rstrip() + "\n",
            encoding="utf-8",
        )
        temporary_path.replace(path)

    def _infer_project_id(
        self,
        events: list[TelemetryEvent],
    ) -> str:
        project_ids = {
            event.project_id
            for event in events
            if event.project_id
        }

        if len(project_ids) == 1:
            return next(iter(project_ids))

        return ""

    def _failure(
        self,
        *,
        message: str,
        component: str,
        source_result: EngineResult,
        project_path: Path,
    ) -> EngineResult:
        return EngineResult.fail(
            message=message,
            errors=list(source_result.errors),
            warnings=list(source_result.warnings),
            metadata={
                **self._base_metadata(
                    project_path,
                    str(
                        source_result.metadata.get(
                            "project_id",
                            project_path.name,
                        )
                    ),
                ),
                **dict(source_result.metadata),
                "failed_component": component,
                "intelligence_package_failed": True,
            },
        )

    def _base_metadata(
        self,
        project_path: Path,
        project_id: str,
    ) -> dict[str, Any]:
        return {
            "component": self.COMPONENT_NAME,
            "version": self.VERSION,
            "project_id": project_id,
            "project_path": str(project_path),
            "telemetry_directory": str(
                project_path / self.TELEMETRY_DIRECTORY
            ),
        }

    def _unique_strings(
        self,
        values: list[Any],
    ) -> list[str]:
        result: list[str] = []

        for value in values:
            item = str(value or "").strip()

            if item and item not in result:
                result.append(item)

        return result

    def get_component_info(self) -> dict[str, Any]:
        return {
            "component": self.COMPONENT_NAME,
            "version": self.VERSION,
            "reads_telemetry": True,
            "writes_reports": True,
            "applies_optimizations": False,
            "report_files": [
                "RUNTIME_HEALTH.json",
                "RUNTIME_HEALTH.md",
                self.PROMPT_JSON_FILENAME,
                self.PROMPT_MARKDOWN_FILENAME,
                self.COST_JSON_FILENAME,
                self.COST_MARKDOWN_FILENAME,
                self.OPTIMIZATION_JSON_FILENAME,
                self.OPTIMIZATION_MARKDOWN_FILENAME,
                "PROJECT_INTELLIGENCE.json",
                "PROJECT_INTELLIGENCE.md",
                "EXECUTIVE_DASHBOARD.json",
                "EXECUTIVE_DASHBOARD.md",
                "EXECUTIVE_DASHBOARD.html",
            ],
            "uses_dashboard_generator": True,
            "uses_dashboard_exporter": True,
            "dashboard_fault_tolerant": True,
            "next_component": (
                "dashboard_pipeline_integration_smoke_test"
            ),
        }