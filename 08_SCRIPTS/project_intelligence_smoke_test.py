"""
=========================================================
Proyecto : CIPS
Release  : 0.9
Build    : 080
Archivo  : project_intelligence_smoke_test.py
Estado   : RELEASE
=========================================================

Prueba integral del Sprint 022D — Project Intelligence.

La prueba no llama a Gemini, no requiere credenciales,
no modifica proyectos existentes y no aplica optimizaciones.
"""

from __future__ import annotations

import json
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from cost_models import (
    CostBreakdown,
    CostStatus,
    ProjectCostReport,
    StageCostAnalysis,
    TokenUsageBreakdown,
)
from health_models import (
    ComponentHealth,
    HealthStatus,
    RuntimeHealthReport,
)
from optimization_models import (
    OptimizationActionType,
    OptimizationAdjustment,
    OptimizationPlan,
    OptimizationPriority,
    OptimizationRecommendation,
    OptimizationStatus,
    StageOptimizationAnalysis,
)
from project_intelligence_engine import ProjectIntelligenceEngine
from project_intelligence_models import (
    FindingType,
    IntelligenceStatus,
    ProjectIntelligenceReport,
)
from prompt_intelligence_models import (
    PromptAnalysis,
    PromptEfficiencyStatus,
    PromptIntelligenceReport,
    PromptMetric,
)
from telemetry_models import TelemetrySummary


TEST_ROOT = (
    Path(__file__).resolve().parents[1]
    / "04_PROYECTOS"
    / "PROJECT_INTELLIGENCE_SMOKE_TEST"
)


@dataclass
class ScenarioResult:
    name: str
    passed: bool
    errors: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class ProjectIntelligenceSmokeTest:
    TEST_NAME = "CIPS Project Intelligence Smoke Test"

    def __init__(self) -> None:
        self.engine = ProjectIntelligenceEngine()
        self.results: list[ScenarioResult] = []
        self.telemetry_summary = self._build_telemetry_summary()
        self.health_report = self._build_health_report()
        self.prompt_report = self._build_prompt_report()
        self.cost_report = self._build_cost_report()
        self.optimization_plan = self._build_optimization_plan()
        self.report: ProjectIntelligenceReport | None = None

    def run(self) -> bool:
        shutil.rmtree(TEST_ROOT, ignore_errors=True)
        TEST_ROOT.mkdir(parents=True, exist_ok=True)

        print(self.TEST_NAME)
        print("=" * 70)
        print(
            "Esta prueba no llama a Gemini, "
            "no requiere credenciales y no aplica cambios."
        )
        print(f"Ruta temporal: {TEST_ROOT}")

        scenarios: list[Callable[[], ScenarioResult]] = [
            self._scenario_build_report,
            self._scenario_kpis,
            self._scenario_global_status,
            self._scenario_critical_findings,
            self._scenario_strengths_risks_opportunities,
            self._scenario_recommendations,
            self._scenario_executive_summary,
            self._scenario_persistence,
            self._scenario_persisted_files,
            self._scenario_incomplete_sources,
        ]

        for scenario in scenarios:
            result = scenario()
            self.results.append(result)
            self._print_scenario(result)

        return self._print_summary()

    def _scenario_build_report(self) -> ScenarioResult:
        report = self.engine.build_report(
            project_path=TEST_ROOT,
            telemetry_summary=self.telemetry_summary,
            health_report=self.health_report,
            prompt_report=self.prompt_report,
            cost_report=self.cost_report,
            optimization_plan=self.optimization_plan,
        )
        self.report = report
        errors: list[str] = []

        if report.project_id != "PROJECT_INTELLIGENCE_TEST":
            errors.append("project_id no fue inferido correctamente.")
        if report.telemetry_events != 6:
            errors.append("telemetry_events debía ser 6.")
        if report.total_tokens != 60000:
            errors.append("total_tokens debía ser 60000.")
        if report.total_cost <= 0:
            errors.append("total_cost debía ser mayor a 0.")

        return ScenarioResult(
            "Construcción con todas las fuentes",
            not errors,
            errors,
            {
                "project_id": report.project_id,
                "telemetry_events": report.telemetry_events,
                "total_tokens": report.total_tokens,
                "total_cost": report.total_cost,
            },
        )

    def _scenario_kpis(self) -> ScenarioResult:
        report = self._require_report()
        expected = {
            "health",
            "prompt_efficiency",
            "reliability",
            "cost_efficiency",
            "optimization_potential",
        }
        actual = {kpi.kpi_id for kpi in report.kpis}
        errors: list[str] = []

        if actual != expected:
            errors.append("Los IDs de KPI no coinciden.")
        if report.health_score >= 75:
            errors.append("health_score debía reflejar UNHEALTHY.")
        if report.prompt_efficiency_score >= 75:
            errors.append(
                "prompt_efficiency_score debía reflejar CRITICAL."
            )

        return ScenarioResult(
            "Cálculo de KPIs ejecutivos",
            not errors,
            errors,
            {
                "kpis": {
                    kpi.kpi_id: kpi.normalized_score()
                    for kpi in report.kpis
                }
            },
        )

    def _scenario_global_status(self) -> ScenarioResult:
        report = self._require_report()
        errors: list[str] = []

        if not 0 <= report.ai_project_score <= 100:
            errors.append("AI Project Score fuera de rango.")
        if report.status not in {
            IntelligenceStatus.ATTENTION,
            IntelligenceStatus.CRITICAL,
        }:
            errors.append(
                "El estado global debía ser ATTENTION o CRITICAL."
            )
        if report.success_rate != 66.67:
            errors.append(
                f"success_rate esperado 66.67, actual {report.success_rate}."
            )

        return ScenarioResult(
            "Estado global y AI Project Score",
            not errors,
            errors,
            {
                "ai_project_score": report.ai_project_score,
                "status": report.status.value,
                "success_rate": report.success_rate,
            },
        )

    def _scenario_critical_findings(self) -> ScenarioResult:
        report = self._require_report()
        critical = report.critical_findings()
        titles = {finding.title for finding in report.findings}
        errors: list[str] = []

        if not critical:
            errors.append("Debían existir hallazgos críticos.")
        if "Runtime no saludable" not in titles:
            errors.append("Falta hallazgo de Runtime.")
        if "Prompt Intelligence crítico" not in titles:
            errors.append("Falta hallazgo de prompts.")
        if not any(
            finding.finding_type == FindingType.CRITICAL_RISK
            for finding in report.findings
        ):
            errors.append("Falta finding_type CRITICAL_RISK.")

        return ScenarioResult(
            "Hallazgos críticos",
            not errors,
            errors,
            {
                "findings_total": len(report.findings),
                "critical_total": len(critical),
                "titles": sorted(titles),
            },
        )

    def _scenario_strengths_risks_opportunities(self) -> ScenarioResult:
        report = self._require_report()
        errors: list[str] = []

        if not report.risks:
            errors.append("Debían existir riesgos.")
        if not report.opportunities:
            errors.append("Debían existir oportunidades.")
        if "Runtime no saludable" not in report.risks:
            errors.append("El riesgo principal no fue sintetizado.")
        if "Reducir prompt del Storyboard" not in report.opportunities:
            errors.append("La oportunidad de prompt no fue sintetizada.")

        return ScenarioResult(
            "Fortalezas, riesgos y oportunidades",
            not errors,
            errors,
            {
                "strengths": report.strengths,
                "risks": report.risks,
                "opportunities": report.opportunities,
            },
        )

    def _scenario_recommendations(self) -> ScenarioResult:
        report = self._require_report()
        top = report.top_recommendations(3)
        errors: list[str] = []

        if len(report.recommendations) != 3:
            errors.append("Debían consolidarse 3 recomendaciones.")
        if not top or top[0].priority != "CRITICAL":
            errors.append("La primera recomendación debía ser CRITICAL.")
        if not any(
            recommendation.safe_for_automatic_apply
            for recommendation in report.recommendations
        ):
            errors.append(
                "Debía existir una recomendación automática segura."
            )

        return ScenarioResult(
            "Consolidación de recomendaciones",
            not errors,
            errors,
            {
                "recommendations_total": len(report.recommendations),
                "top_priorities": [item.priority for item in top],
                "automatic_safe": sum(
                    item.safe_for_automatic_apply
                    for item in report.recommendations
                ),
            },
        )

    def _scenario_executive_summary(self) -> ScenarioResult:
        report = self._require_report()
        summary = report.executive_summary
        errors: list[str] = []

        for required in (
            report.project_id,
            "AI Project Score",
            "Riesgo principal",
            "Oportunidad principal",
        ):
            if required not in summary:
                errors.append(
                    f"El resumen no contiene: {required}."
                )

        return ScenarioResult(
            "Resumen ejecutivo",
            not errors,
            errors,
            {
                "characters": len(summary),
                "summary": summary,
            },
        )

    def _scenario_persistence(self) -> ScenarioResult:
        result = self.engine.execute(
            project_path=TEST_ROOT,
            telemetry_summary=self.telemetry_summary,
            health_report=self.health_report,
            prompt_report=self.prompt_report,
            cost_report=self.cost_report,
            optimization_plan=self.optimization_plan,
            persist=True,
        )
        json_path = (
            TEST_ROOT
            / "03_TELEMETRIA"
            / "PROJECT_INTELLIGENCE.json"
        )
        markdown_path = (
            TEST_ROOT
            / "03_TELEMETRIA"
            / "PROJECT_INTELLIGENCE.md"
        )
        errors: list[str] = []

        if not result.success:
            errors.append("ProjectIntelligenceEngine.execute() falló.")
        if not json_path.exists():
            errors.append("No se creó PROJECT_INTELLIGENCE.json.")
        if not markdown_path.exists():
            errors.append("No se creó PROJECT_INTELLIGENCE.md.")
        if result.metadata.get("persisted") is not True:
            errors.append("metadata.persisted debía ser True.")

        return ScenarioResult(
            "Persistencia JSON y Markdown",
            not errors,
            errors,
            {
                "success": result.success,
                "json_path": str(json_path),
                "markdown_path": str(markdown_path),
                "json_size_bytes": (
                    json_path.stat().st_size
                    if json_path.exists()
                    else 0
                ),
                "markdown_size_bytes": (
                    markdown_path.stat().st_size
                    if markdown_path.exists()
                    else 0
                ),
            },
        )

    def _scenario_persisted_files(self) -> ScenarioResult:
        json_path = (
            TEST_ROOT
            / "03_TELEMETRIA"
            / "PROJECT_INTELLIGENCE.json"
        )
        markdown_path = (
            TEST_ROOT
            / "03_TELEMETRIA"
            / "PROJECT_INTELLIGENCE.md"
        )
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

        for key in ("kpis", "findings", "recommendations"):
            if key not in payload:
                errors.append(f"Falta {key} en JSON.")

        for section in (
            "# Project Intelligence Report",
            "## KPIs",
            "## Recomendaciones priorizadas",
        ):
            if section not in markdown:
                errors.append(f"Markdown sin sección: {section}.")

        return ScenarioResult(
            "Validación de archivos persistidos",
            not errors,
            errors,
            {
                "json_keys": sorted(payload.keys()),
                "markdown_characters": len(markdown),
                "critical_findings_total": payload.get(
                    "critical_findings_total"
                ),
            },
        )

    def _scenario_incomplete_sources(self) -> ScenarioResult:
        incomplete_path = TEST_ROOT / "INCOMPLETE_PROJECT"
        incomplete_path.mkdir(parents=True, exist_ok=True)

        report = self.engine.build_report(
            project_path=incomplete_path
        )
        errors: list[str] = []

        if report.project_id != "INCOMPLETE_PROJECT":
            errors.append(
                "El project_id debía usar el nombre de carpeta."
            )
        if len(report.warnings) != 5:
            errors.append(
                f"Se esperaban 5 advertencias, actual {len(report.warnings)}."
            )
        if not report.executive_summary:
            errors.append("Incluso incompleto debe generar resumen.")

        return ScenarioResult(
            "Tolerancia a fuentes incompletas",
            not errors,
            errors,
            {
                "project_id": report.project_id,
                "status": report.status.value,
                "ai_project_score": report.ai_project_score,
                "warnings": len(report.warnings),
            },
        )

    def _build_telemetry_summary(self) -> TelemetrySummary:
        return TelemetrySummary(
            scope="project",
            scope_id="PROJECT_INTELLIGENCE_TEST",
            events_total=6,
            successful_events=4,
            failed_events=2,
            success_rate=66.67,
            duration_seconds=360.0,
            average_duration_seconds=60.0,
            prompt_tokens=45000,
            response_tokens=9000,
            thinking_tokens=6000,
            total_tokens=60000,
            retry_attempts=8,
            retry_count=2,
            exhausted_events=1,
            recovered_events=1,
            estimated_cost=0.25,
            currency="USD",
            providers=["gemini"],
            models=["gemini-3.5-flash"],
            stages=[
                "investigacion",
                "verificacion",
                "guion",
                "storyboard",
                "seo",
                "publicacion",
            ],
            status_codes={"429": 1, "503": 1},
            exception_types={
                "ClientError": 1,
                "ServerError": 1,
            },
        )

    def _build_health_report(self) -> RuntimeHealthReport:
        return RuntimeHealthReport(
            report_id="HEALTH-INTELLIGENCE-001",
            generated_at="2026-07-16T04:00:00Z",
            status=HealthStatus.UNHEALTHY,
            project_id="PROJECT_INTELLIGENCE_TEST",
            scope="project",
            events_total=6,
            successful_events=4,
            failed_events=2,
            success_rate=66.67,
            failure_rate=33.33,
            total_duration_seconds=360.0,
            average_duration_seconds=60.0,
            total_tokens=60000,
            retry_count=2,
            exhausted_events=1,
            recovered_events=1,
            components=[
                ComponentHealth(
                    component="stage:storyboard",
                    status=HealthStatus.UNHEALTHY,
                    category="stage",
                    events_total=1,
                    successful_events=0,
                    failed_events=1,
                    success_rate=0.0,
                    failure_rate=100.0,
                    average_duration_seconds=200.0,
                    maximum_duration_seconds=200.0,
                    retry_count=2,
                    exhausted_events=1,
                    total_tokens=19800,
                ),
                ComponentHealth(
                    component="stage:seo",
                    status=HealthStatus.HEALTHY,
                    category="stage",
                    events_total=1,
                    successful_events=1,
                    failed_events=0,
                    success_rate=100.0,
                    failure_rate=0.0,
                    average_duration_seconds=25.0,
                    maximum_duration_seconds=25.0,
                    total_tokens=8000,
                ),
            ],
        )

    def _build_prompt_report(self) -> PromptIntelligenceReport:
        storyboard = PromptAnalysis(
            analysis_id="PROMPT-INTELLIGENCE-001",
            project_id="PROJECT_INTELLIGENCE_TEST",
            stage="storyboard",
            status=PromptEfficiencyStatus.CRITICAL,
            provider="gemini",
            model="gemini-3.5-flash",
            prompt_tokens=18000,
            response_tokens=600,
            thinking_tokens=1200,
            total_tokens=19800,
            duration_seconds=200.0,
            prompt_response_token_ratio=30.0,
            response_yield_percent=3.33,
            redundancy_score=55.0,
            density_score=30.0,
            efficiency_score=25.0,
            metrics=[
                PromptMetric(
                    metric_id="prompt_length",
                    name="Longitud del prompt",
                    status=PromptEfficiencyStatus.CRITICAL,
                    value=18000,
                    unit="tokens",
                    score=20.0,
                    weight=1.5,
                )
            ],
        )
        seo = PromptAnalysis(
            analysis_id="PROMPT-INTELLIGENCE-002",
            project_id="PROJECT_INTELLIGENCE_TEST",
            stage="seo",
            status=PromptEfficiencyStatus.EFFICIENT,
            provider="gemini",
            model="gemini-3.5-flash",
            prompt_tokens=4000,
            response_tokens=1200,
            thinking_tokens=300,
            total_tokens=5500,
            duration_seconds=25.0,
            efficiency_score=92.0,
            metrics=[
                PromptMetric(
                    metric_id="prompt_length",
                    name="Longitud del prompt",
                    status=PromptEfficiencyStatus.EFFICIENT,
                    value=4000,
                    unit="tokens",
                    score=92.0,
                )
            ],
        )
        return PromptIntelligenceReport(
            report_id="PROMPT-REPORT-INTELLIGENCE",
            generated_at="2026-07-16T04:00:00Z",
            project_id="PROJECT_INTELLIGENCE_TEST",
            status=PromptEfficiencyStatus.CRITICAL,
            analyses=[storyboard, seo],
        )

    def _build_cost_report(self) -> ProjectCostReport:
        storyboard = StageCostAnalysis(
            analysis_id="COST-INTELLIGENCE-001",
            project_id="PROJECT_INTELLIGENCE_TEST",
            stage="storyboard",
            provider="gemini",
            model="gemini-3.5-flash",
            status=CostStatus.CALCULATED,
            token_usage=TokenUsageBreakdown(
                prompt_tokens=18000,
                response_tokens=600,
                thinking_tokens=1200,
                total_tokens=19800,
            ),
            cost=CostBreakdown(
                status=CostStatus.CALCULATED,
                input_rate=2.7,
                output_rate=16.2,
                thinking_rate=16.2,
                input_cost=0.0486,
                output_cost=0.00972,
                thinking_cost=0.01944,
            ),
            duration_seconds=200.0,
        )
        seo = StageCostAnalysis(
            analysis_id="COST-INTELLIGENCE-002",
            project_id="PROJECT_INTELLIGENCE_TEST",
            stage="seo",
            provider="gemini",
            model="gemini-3.5-flash",
            status=CostStatus.CALCULATED,
            token_usage=TokenUsageBreakdown(
                prompt_tokens=4000,
                response_tokens=1200,
                thinking_tokens=300,
                total_tokens=5500,
            ),
            cost=CostBreakdown(
                status=CostStatus.CALCULATED,
                input_rate=2.7,
                output_rate=16.2,
                thinking_rate=16.2,
                input_cost=0.0108,
                output_cost=0.01944,
                thinking_cost=0.00486,
            ),
            duration_seconds=25.0,
        )
        return ProjectCostReport(
            report_id="COST-REPORT-INTELLIGENCE",
            generated_at="2026-07-16T04:00:00Z",
            project_id="PROJECT_INTELLIGENCE_TEST",
            status=CostStatus.CALCULATED,
            analyses=[storyboard, seo],
        )

    def _build_optimization_plan(self) -> OptimizationPlan:
        critical_prompt = OptimizationRecommendation(
            recommendation_id="OPT-INT-001",
            title="Reducir prompt del Storyboard",
            description="Compactar contexto redundante.",
            action_type=OptimizationActionType.REDUCE_PROMPT,
            priority=OptimizationPriority.CRITICAL,
            status=OptimizationStatus.PROPOSED,
            project_id="PROJECT_INTELLIGENCE_TEST",
            stage="storyboard",
            confidence_score=95.0,
            expected_improvement_percent=40.0,
            estimated_savings=0.02,
            adjustments=[
                OptimizationAdjustment(
                    target="prompt_engine",
                    parameter="target_prompt_tokens",
                    current_value=18000,
                    proposed_value=10800,
                    unit="tokens",
                    safe_to_apply_automatically=False,
                )
            ],
        )
        safe_output = OptimizationRecommendation(
            recommendation_id="OPT-INT-002",
            title="Reducir max_output_tokens",
            description="Alinear límite con salida real.",
            action_type=(
                OptimizationActionType.REDUCE_MAX_OUTPUT_TOKENS
            ),
            priority=OptimizationPriority.HIGH,
            status=OptimizationStatus.PROPOSED,
            project_id="PROJECT_INTELLIGENCE_TEST",
            stage="storyboard",
            confidence_score=88.0,
            expected_improvement_percent=20.0,
            estimated_savings=0.005,
            adjustments=[
                OptimizationAdjustment(
                    target="llm",
                    parameter="max_output_tokens",
                    current_value=8192,
                    proposed_value=2048,
                    unit="tokens",
                    safe_to_apply_automatically=True,
                )
            ],
        )
        provider = OptimizationRecommendation(
            recommendation_id="OPT-INT-003",
            title="Configurar proveedor alternativo",
            description="Mitigar presión de cuota.",
            action_type=OptimizationActionType.CHANGE_PROVIDER,
            priority=OptimizationPriority.CRITICAL,
            status=OptimizationStatus.PROPOSED,
            project_id="PROJECT_INTELLIGENCE_TEST",
            stage="publicacion",
            confidence_score=96.0,
            expected_improvement_percent=35.0,
            adjustments=[
                OptimizationAdjustment(
                    target="llm",
                    parameter="provider",
                    current_value="gemini",
                    proposed_value="fallback_provider",
                    safe_to_apply_automatically=False,
                )
            ],
        )
        return OptimizationPlan(
            plan_id="OPT-PLAN-INTELLIGENCE",
            generated_at="2026-07-16T04:00:00Z",
            project_id="PROJECT_INTELLIGENCE_TEST",
            analyses=[
                StageOptimizationAnalysis(
                    analysis_id="STAGE-OPT-INT-001",
                    project_id="PROJECT_INTELLIGENCE_TEST",
                    stage="storyboard",
                    optimization_score=20.0,
                    recommendations=[critical_prompt, safe_output],
                ),
                StageOptimizationAnalysis(
                    analysis_id="STAGE-OPT-INT-002",
                    project_id="PROJECT_INTELLIGENCE_TEST",
                    stage="publicacion",
                    optimization_score=35.0,
                    recommendations=[provider],
                ),
            ],
        )

    def _require_report(self) -> ProjectIntelligenceReport:
        if self.report is None:
            raise RuntimeError("El reporte no ha sido construido.")
        return self.report

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
        passed = sum(result.passed for result in self.results)
        failed = len(self.results) - passed
        valid = failed == 0

        print()
        print("=" * 70)
        print("RESUMEN PROJECT INTELLIGENCE")
        print("=" * 70)
        print(f"Escenarios ejecutados: {len(self.results)}")
        print(f"Escenarios aprobados: {passed}")
        print(f"Escenarios fallidos: {failed}")
        print(f"Resultado integral válido: {valid}")
        print()
        print("Artefactos conservados para inspección:")
        print(f"- {TEST_ROOT}")

        if valid:
            print()
            print(
                "Project Intelligence Smoke Test "
                "completado correctamente."
            )

        return valid


def main() -> int:
    return 0 if ProjectIntelligenceSmokeTest().run() else 1


if __name__ == "__main__":
    sys.exit(main())