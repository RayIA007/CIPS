"""
=========================================================
Proyecto : CIPS
Release  : 0.9
Build    : 086
Archivo  : dashboard_smoke_test.py
Estado   : RELEASE
=========================================================

Prueba integral del Sprint 023B — Executive Dashboard.

Escenarios:
1. Generación con todas las fuentes.
2. Tarjetas KPI principales.
3. Gráficos y series.
4. Secciones ejecutivas.
5. Serialización y reconstrucción.
6. Exportación JSON.
7. Exportación Markdown.
8. Exportación HTML autónomo.
9. Escapado de contenido dinámico.
10. Tolerancia a fuentes opcionales faltantes.

La prueba:
- no llama a Gemini;
- no requiere credenciales;
- no modifica proyectos existentes;
- utiliza una carpeta temporal propia;
- no requiere conexión a Internet.
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
from dashboard_exporter import DashboardExporter
from dashboard_generator import DashboardGenerator
from dashboard_models import (
    DashboardChartType,
    DashboardStatus,
    ExecutiveDashboard,
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
from project_intelligence_models import (
    ExecutiveFinding,
    FindingType,
    IntelligenceRecommendation,
    IntelligenceStatus,
    ProjectIntelligenceReport,
)
from prompt_intelligence_models import (
    PromptAnalysis,
    PromptEfficiencyStatus,
    PromptIntelligenceReport,
    PromptMetric,
)


TEST_ROOT = (
    Path(__file__).resolve().parents[1]
    / "04_PROYECTOS"
    / "DASHBOARD_SMOKE_TEST"
)


@dataclass
class ScenarioResult:
    """
    Resultado de un escenario individual.
    """

    name: str
    passed: bool
    errors: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class DashboardSmokeTest:
    """
    Ejecuta la validación integral del Sprint 023B.
    """

    TEST_NAME = "CIPS Executive Dashboard Smoke Test"

    def __init__(self) -> None:
        self.generator = DashboardGenerator()
        self.exporter = DashboardExporter()
        self.results: list[ScenarioResult] = []

        self.project_intelligence = (
            self._build_project_intelligence()
        )
        self.health_report = self._build_health_report()
        self.prompt_report = self._build_prompt_report()
        self.cost_report = self._build_cost_report()
        self.optimization_plan = (
            self._build_optimization_plan()
        )

        self.dashboard: ExecutiveDashboard | None = None
        self.export_result = None

    def run(self) -> bool:
        """
        Ejecuta todos los escenarios.
        """

        self._prepare()

        print(self.TEST_NAME)
        print("=" * 70)
        print(
            "Esta prueba no llama a Gemini, no requiere credenciales "
            "y no necesita conexión a Internet."
        )
        print(f"Ruta temporal: {TEST_ROOT}")

        scenarios: list[Callable[[], ScenarioResult]] = [
            self._scenario_generate_dashboard,
            self._scenario_cards,
            self._scenario_charts,
            self._scenario_sections,
            self._scenario_serialization,
            self._scenario_json_export,
            self._scenario_markdown_export,
            self._scenario_html_export,
            self._scenario_html_escaping,
            self._scenario_optional_sources,
        ]

        for scenario in scenarios:
            result = scenario()
            self.results.append(result)
            self._print_scenario(result)

        return self._print_summary()

    def _prepare(self) -> None:
        """
        Recrea la carpeta temporal.
        """

        shutil.rmtree(
            TEST_ROOT,
            ignore_errors=True,
        )

        TEST_ROOT.mkdir(
            parents=True,
            exist_ok=True,
        )

    # --------------------------------------------------
    # Escenarios
    # --------------------------------------------------

    def _scenario_generate_dashboard(self) -> ScenarioResult:
        """
        Valida la generación integral.
        """

        dashboard = self.generator.generate(
            project_intelligence=self.project_intelligence,
            health_report=self.health_report,
            prompt_report=self.prompt_report,
            cost_report=self.cost_report,
            optimization_plan=self.optimization_plan,
        )

        self.dashboard = dashboard

        errors: list[str] = []

        if not isinstance(
            dashboard,
            ExecutiveDashboard,
        ):
            errors.append(
                "El resultado debía ser ExecutiveDashboard."
            )

        if dashboard.project_id != "DASHBOARD_TEST":
            errors.append(
                "project_id no coincide."
            )

        if not dashboard.executive_summary:
            errors.append(
                "El resumen ejecutivo quedó vacío."
            )

        if dashboard.status not in {
            DashboardStatus.ATTENTION,
            DashboardStatus.CRITICAL,
        }:
            errors.append(
                "El estado debía reflejar riesgos del proyecto."
            )

        return ScenarioResult(
            name="Generación con todas las fuentes",
            passed=not errors,
            errors=errors,
            metadata={
                "project_id": dashboard.project_id,
                "status": dashboard.status.value,
                "cards": len(dashboard.cards),
                "charts": len(dashboard.charts),
                "sections": len(dashboard.sections),
            },
        )

    def _scenario_cards(self) -> ScenarioResult:
        """
        Valida tarjetas KPI.
        """

        dashboard = self._require_dashboard()

        expected_ids = {
            "CARD-AI-PROJECT-SCORE",
            "CARD-HEALTH-SCORE",
            "CARD-PROMPT-EFFICIENCY",
            "CARD-RELIABILITY",
            "CARD-COST-EFFICIENCY",
            "CARD-OPTIMIZATION-POTENTIAL",
            "CARD-SUCCESS-RATE",
            "CARD-TOTAL-COST",
            "CARD-TOTAL-TOKENS",
            "CARD-RETRY-COUNT",
        }

        actual_ids = {
            card.card_id
            for card in dashboard.cards
        }

        errors: list[str] = []

        missing = sorted(
            expected_ids - actual_ids
        )

        if missing:
            errors.append(
                "Faltan tarjetas: "
                + ", ".join(missing)
            )

        ai_card = next(
            (
                card
                for card in dashboard.cards
                if card.card_id
                == "CARD-AI-PROJECT-SCORE"
            ),
            None,
        )

        if ai_card is None:
            errors.append(
                "No existe AI Project Score."
            )

        elif ai_card.value != 57.87:
            errors.append(
                "AI Project Score no conserva el valor fuente."
            )

        if not any(
            card.card_id
            == "CARD-ESTIMATED-SAVINGS"
            for card in dashboard.cards
        ):
            errors.append(
                "Falta Estimated Savings."
            )

        return ScenarioResult(
            name="Tarjetas KPI principales",
            passed=not errors,
            errors=errors,
            metadata={
                "cards_total": len(dashboard.cards),
                "visible_cards": len(
                    dashboard.visible_cards()
                ),
                "card_ids": sorted(actual_ids),
            },
        )

    def _scenario_charts(self) -> ScenarioResult:
        """
        Valida gráficos y series.
        """

        dashboard = self._require_dashboard()

        expected_types = {
            DashboardChartType.RADAR,
            DashboardChartType.BAR,
            DashboardChartType.AREA,
            DashboardChartType.DONUT,
        }

        actual_types = {
            chart.chart_type
            for chart in dashboard.charts
        }

        errors: list[str] = []

        if not expected_types.issubset(
            actual_types
        ):
            errors.append(
                "No se generaron todos los tipos esperados."
            )

        if len(dashboard.charts) < 8:
            errors.append(
                "Se esperaban al menos 8 gráficos."
            )

        if any(
            chart.total_points() <= 0
            for chart in dashboard.charts
        ):
            errors.append(
                "Todos los gráficos de prueba deben tener datos."
            )

        radar = next(
            (
                chart
                for chart in dashboard.charts
                if chart.chart_id == "CHART-KPI-RADAR"
            ),
            None,
        )

        if radar is None:
            errors.append(
                "Falta el perfil radar."
            )

        elif radar.total_points() != 5:
            errors.append(
                "El radar debía contener 5 puntos."
            )

        return ScenarioResult(
            name="Gráficos y series",
            passed=not errors,
            errors=errors,
            metadata={
                "charts_total": len(dashboard.charts),
                "chart_types": sorted(
                    chart_type.value
                    for chart_type in actual_types
                ),
                "points_total": sum(
                    chart.total_points()
                    for chart in dashboard.charts
                ),
            },
        )

    def _scenario_sections(self) -> ScenarioResult:
        """
        Valida secciones ejecutivas.
        """

        dashboard = self._require_dashboard()

        expected_ids = {
            "SECTION-EXECUTIVE",
            "SECTION-RUNTIME",
            "SECTION-PROMPTS",
            "SECTION-COST",
            "SECTION-OPTIMIZATION",
            "SECTION-RISKS",
        }

        actual_ids = {
            section.section_id
            for section in dashboard.sections
        }

        errors: list[str] = []

        if actual_ids != expected_ids:
            errors.append(
                "Las secciones no coinciden con el diseño."
            )

        optimization = next(
            (
                section
                for section in dashboard.sections
                if section.section_id
                == "SECTION-OPTIMIZATION"
            ),
            None,
        )

        if optimization is None:
            errors.append(
                "Falta sección Optimization."
            )

        elif not optimization.items:
            errors.append(
                "Optimization debía incluir recomendaciones."
            )

        risks = next(
            (
                section
                for section in dashboard.sections
                if section.section_id
                == "SECTION-RISKS"
            ),
            None,
        )

        if risks is None:
            errors.append(
                "Falta sección Risks & Strengths."
            )

        elif not any(
            item.startswith("RISK:")
            for item in risks.items
        ):
            errors.append(
                "La sección no contiene riesgos."
            )

        return ScenarioResult(
            name="Secciones ejecutivas",
            passed=not errors,
            errors=errors,
            metadata={
                "sections_total": len(
                    dashboard.sections
                ),
                "section_ids": sorted(actual_ids),
                "visible_sections": len(
                    dashboard.visible_sections()
                ),
            },
        )

    def _scenario_serialization(self) -> ScenarioResult:
        """
        Valida serialización y reconstrucción.
        """

        dashboard = self._require_dashboard()

        payload = dashboard.to_dict()
        serialized = json.dumps(
            payload,
            ensure_ascii=False,
        )

        restored = ExecutiveDashboard.from_dict(
            payload
        )

        restored_payload = restored.to_dict()

        errors: list[str] = []

        if restored.project_id != dashboard.project_id:
            errors.append(
                "La reconstrucción perdió project_id."
            )

        if len(restored.cards) != len(dashboard.cards):
            errors.append(
                "La reconstrucción perdió tarjetas."
            )

        if len(restored.charts) != len(dashboard.charts):
            errors.append(
                "La reconstrucción perdió gráficos."
            )

        if len(restored.sections) != len(dashboard.sections):
            errors.append(
                "La reconstrucción perdió secciones."
            )

        if (
            restored_payload["status"]
            != payload["status"]
        ):
            errors.append(
                "La reconstrucción cambió el estado."
            )

        return ScenarioResult(
            name="Serialización y reconstrucción",
            passed=not errors,
            errors=errors,
            metadata={
                "serialized_characters": len(serialized),
                "cards_total": len(restored.cards),
                "charts_total": len(restored.charts),
                "sections_total": len(restored.sections),
                "status": restored.status.value,
            },
        )

    def _scenario_json_export(self) -> ScenarioResult:
        """
        Valida exportación JSON.
        """

        dashboard = self._require_dashboard()

        result = self.exporter.execute(
            dashboard=dashboard,
            project_path=TEST_ROOT,
            export_json=True,
            export_markdown=True,
            export_html=True,
        )

        self.export_result = result

        json_path = (
            TEST_ROOT
            / "03_TELEMETRIA"
            / "EXECUTIVE_DASHBOARD.json"
        )

        errors: list[str] = []

        if not result.success:
            errors.append(
                "DashboardExporter.execute() falló."
            )

        if not json_path.exists():
            errors.append(
                "No se creó EXECUTIVE_DASHBOARD.json."
            )

        try:
            payload = json.loads(
                json_path.read_text(
                    encoding="utf-8"
                )
            )
        except Exception as error:
            payload = {}
            errors.append(
                f"JSON inválido: {error}"
            )

        if payload.get("project_id") != "DASHBOARD_TEST":
            errors.append(
                "project_id persistido incorrecto."
            )

        if payload.get("cards_total", 0) < 10:
            errors.append(
                "JSON sin tarjetas suficientes."
            )

        return ScenarioResult(
            name="Exportación JSON",
            passed=not errors,
            errors=errors,
            metadata={
                "success": result.success,
                "json_path": str(json_path),
                "size_bytes": (
                    json_path.stat().st_size
                    if json_path.exists()
                    else 0
                ),
                "cards_total": payload.get(
                    "cards_total"
                ),
            },
        )

    def _scenario_markdown_export(self) -> ScenarioResult:
        """
        Valida exportación Markdown.
        """

        markdown_path = (
            TEST_ROOT
            / "03_TELEMETRIA"
            / "EXECUTIVE_DASHBOARD.md"
        )

        markdown = (
            markdown_path.read_text(
                encoding="utf-8"
            )
            if markdown_path.exists()
            else ""
        )

        errors: list[str] = []

        required_sections = [
            "# CIPS Executive Dashboard",
            "## Resumen ejecutivo",
            "## Indicadores principales",
            "## Visualizaciones",
            "## Secciones",
        ]

        for section in required_sections:
            if section not in markdown:
                errors.append(
                    f"Falta sección Markdown: {section}"
                )

        if "AI Project Score" not in markdown:
            errors.append(
                "Markdown no contiene AI Project Score."
            )

        if "Executive KPI Profile" not in markdown:
            errors.append(
                "Markdown no contiene el gráfico radar."
            )

        return ScenarioResult(
            name="Exportación Markdown",
            passed=not errors,
            errors=errors,
            metadata={
                "markdown_path": str(
                    markdown_path
                ),
                "size_bytes": (
                    markdown_path.stat().st_size
                    if markdown_path.exists()
                    else 0
                ),
                "characters": len(markdown),
            },
        )

    def _scenario_html_export(self) -> ScenarioResult:
        """
        Valida HTML autónomo.
        """

        html_path = (
            TEST_ROOT
            / "03_TELEMETRIA"
            / "EXECUTIVE_DASHBOARD.html"
        )

        html = (
            html_path.read_text(
                encoding="utf-8"
            )
            if html_path.exists()
            else ""
        )

        errors: list[str] = []

        required_fragments = [
            "<!DOCTYPE html>",
            'id="dashboard-data"',
            "drawChart",
            "drawRadar",
            "drawPie",
            "CIPS Executive Analytics",
            "data-chart-id",
        ]

        for fragment in required_fragments:
            if fragment not in html:
                errors.append(
                    f"HTML sin fragmento: {fragment}"
                )

        forbidden_fragments = [
            "cdn.jsdelivr.net",
            "cdnjs.cloudflare.com",
            "unpkg.com",
            "https://",
            "http://",
        ]

        for fragment in forbidden_fragments:
            if fragment in html:
                errors.append(
                    f"HTML contiene dependencia externa: {fragment}"
                )

        if "<canvas" not in html:
            errors.append(
                "HTML no contiene canvas."
            )

        return ScenarioResult(
            name="Exportación HTML autónomo",
            passed=not errors,
            errors=errors,
            metadata={
                "html_path": str(html_path),
                "size_bytes": (
                    html_path.stat().st_size
                    if html_path.exists()
                    else 0
                ),
                "standalone": not any(
                    item in html
                    for item in forbidden_fragments
                ),
                "canvas_count": html.count("<canvas"),
            },
        )

    def _scenario_html_escaping(self) -> ScenarioResult:
        """
        Valida escapado de contenido dinámico.
        """

        dashboard = self._require_dashboard()

        original_title = dashboard.title
        original_summary = dashboard.executive_summary

        dashboard.title = (
            'Dashboard <script>alert("x")</script>'
        )
        dashboard.executive_summary = (
            "<b>Resumen & análisis</b>"
        )

        html = self.exporter.render_html(
            dashboard
        )

        dashboard.title = original_title
        dashboard.executive_summary = original_summary

        errors: list[str] = []

        if '<script>alert("x")</script>' in html:
            errors.append(
                "El título dinámico no fue escapado."
            )

        if "&lt;script&gt;" not in html:
            errors.append(
                "No se encontró el título escapado."
            )

        if "<b>Resumen & análisis</b>" in html:
            errors.append(
                "El resumen dinámico no fue escapado."
            )

        if "&lt;b&gt;Resumen &amp; análisis&lt;/b&gt;" not in html:
            errors.append(
                "No se encontró el resumen escapado."
            )

        return ScenarioResult(
            name="Escapado de contenido HTML",
            passed=not errors,
            errors=errors,
            metadata={
                "escaped_script": (
                    "&lt;script&gt;"
                    in html
                ),
                "escaped_ampersand": (
                    "&amp;"
                    in html
                ),
            },
        )

    def _scenario_optional_sources(self) -> ScenarioResult:
        """
        Valida generación con fuentes opcionales faltantes.
        """

        dashboard = self.generator.generate(
            project_intelligence=(
                self.project_intelligence
            )
        )

        errors: list[str] = []

        if len(dashboard.warnings) != 4:
            errors.append(
                "Se esperaban 4 advertencias."
            )

        if len(dashboard.cards) < 10:
            errors.append(
                "Las tarjetas base deben existir."
            )

        if not any(
            chart.chart_id == "CHART-KPI-RADAR"
            for chart in dashboard.charts
        ):
            errors.append(
                "El radar base debe existir."
            )

        if not any(
            chart.chart_id == "CHART-RELIABILITY"
            for chart in dashboard.charts
        ):
            errors.append(
                "El gráfico de confiabilidad debe existir."
            )

        return ScenarioResult(
            name="Tolerancia a fuentes opcionales faltantes",
            passed=not errors,
            errors=errors,
            metadata={
                "warnings": len(
                    dashboard.warnings
                ),
                "cards": len(
                    dashboard.cards
                ),
                "charts": len(
                    dashboard.charts
                ),
                "sections": len(
                    dashboard.sections
                ),
                "status": dashboard.status.value,
            },
        )

    # --------------------------------------------------
    # Datos simulados
    # --------------------------------------------------

    def _build_project_intelligence(
        self,
    ) -> ProjectIntelligenceReport:
        """
        Construye Project Intelligence de prueba.
        """

        findings = [
            ExecutiveFinding(
                finding_id="FINDING-DASH-001",
                title="Runtime no saludable",
                description=(
                    "Existen fallos y un evento "
                    "con Retry agotado."
                ),
                finding_type=FindingType.CRITICAL_RISK,
                priority="CRITICAL",
                stage="storyboard",
                impact_score=95,
                confidence_score=98,
                recommendation=(
                    "Revisar cuotas y política de Retry."
                ),
            ),
            ExecutiveFinding(
                finding_id="FINDING-DASH-002",
                title="Costos calculados",
                description=(
                    "Existe cobertura conocida de precios."
                ),
                finding_type=FindingType.STRENGTH,
                priority="LOW",
                impact_score=70,
                confidence_score=100,
            ),
        ]

        recommendations = [
            IntelligenceRecommendation(
                recommendation_id="REC-DASH-001",
                title="Reducir prompt del Storyboard",
                description=(
                    "Compactar contexto redundante."
                ),
                priority="CRITICAL",
                action_type="REDUCE_PROMPT",
                stage="storyboard",
                source="runtime_optimizer",
                confidence_score=95,
                expected_improvement_percent=40,
                estimated_savings=0.02,
                currency="USD",
                actionable=True,
            ),
            IntelligenceRecommendation(
                recommendation_id="REC-DASH-002",
                title="Ajustar max_output_tokens",
                description=(
                    "Alinear límite con la salida real."
                ),
                priority="HIGH",
                action_type=(
                    "REDUCE_MAX_OUTPUT_TOKENS"
                ),
                stage="storyboard",
                source="runtime_optimizer",
                confidence_score=88,
                expected_improvement_percent=20,
                estimated_savings=0.005,
                currency="USD",
                actionable=True,
                safe_for_automatic_apply=True,
            ),
        ]

        return ProjectIntelligenceReport(
            report_id="PROJECT-INTELLIGENCE-DASH-001",
            generated_at="2026-07-16T06:00:00Z",
            project_id="DASHBOARD_TEST",
            status=IntelligenceStatus.ATTENTION,
            executive_summary=(
                "El proyecto requiere atención en Runtime "
                "y eficiencia de prompts. Existen oportunidades "
                "de optimización con ahorro estimado."
            ),
            ai_project_score=57.87,
            health_score=37.67,
            prompt_efficiency_score=56.0,
            reliability_score=53.67,
            cost_efficiency_score=85.0,
            optimization_potential_score=72.5,
            telemetry_events=6,
            successful_events=4,
            failed_events=2,
            success_rate=66.67,
            total_tokens=60000,
            total_cost=0.11286,
            currency="USD",
            total_duration_seconds=360.0,
            average_duration_seconds=60.0,
            retry_count=2,
            exhausted_events=1,
            recovered_events=1,
            findings=findings,
            recommendations=recommendations,
            strengths=[
                "Costos calculados con cobertura conocida."
            ],
            risks=[
                "Runtime no saludable",
                "Prompt Intelligence crítico",
            ],
            opportunities=[
                "Reducir prompt del Storyboard",
                "Ajustar max_output_tokens",
            ],
            stages=[
                "storyboard",
                "seo",
                "publicacion",
            ],
            providers=["gemini"],
            models=["gemini-3.5-flash"],
        )

    def _build_health_report(
        self,
    ) -> RuntimeHealthReport:
        return RuntimeHealthReport(
            report_id="HEALTH-DASH-001",
            generated_at="2026-07-16T06:00:00Z",
            status=HealthStatus.UNHEALTHY,
            project_id="DASHBOARD_TEST",
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
                    events_total=2,
                    successful_events=1,
                    failed_events=1,
                    success_rate=50.0,
                    failure_rate=50.0,
                    average_duration_seconds=120.0,
                    maximum_duration_seconds=200.0,
                    retry_count=2,
                    exhausted_events=1,
                    total_tokens=19800,
                ),
                ComponentHealth(
                    component="stage:seo",
                    status=HealthStatus.HEALTHY,
                    category="stage",
                    events_total=2,
                    successful_events=2,
                    failed_events=0,
                    success_rate=100.0,
                    failure_rate=0.0,
                    average_duration_seconds=25.0,
                    maximum_duration_seconds=30.0,
                    total_tokens=8000,
                ),
                ComponentHealth(
                    component="stage:publicacion",
                    status=HealthStatus.DEGRADED,
                    category="stage",
                    events_total=2,
                    successful_events=1,
                    failed_events=1,
                    success_rate=50.0,
                    failure_rate=50.0,
                    average_duration_seconds=45.0,
                    maximum_duration_seconds=70.0,
                    total_tokens=9500,
                ),
            ],
        )

    def _build_prompt_report(
        self,
    ) -> PromptIntelligenceReport:
        analyses = [
            PromptAnalysis(
                analysis_id="PROMPT-DASH-001",
                project_id="DASHBOARD_TEST",
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
                        status=(
                            PromptEfficiencyStatus.CRITICAL
                        ),
                        value=18000,
                        unit="tokens",
                        score=20.0,
                    )
                ],
            ),
            PromptAnalysis(
                analysis_id="PROMPT-DASH-002",
                project_id="DASHBOARD_TEST",
                stage="seo",
                status=PromptEfficiencyStatus.EFFICIENT,
                provider="gemini",
                model="gemini-3.5-flash",
                prompt_tokens=4000,
                response_tokens=1200,
                thinking_tokens=300,
                total_tokens=5500,
                duration_seconds=25.0,
                prompt_response_token_ratio=3.33,
                response_yield_percent=30.0,
                efficiency_score=92.0,
                metrics=[
                    PromptMetric(
                        metric_id="prompt_length",
                        name="Longitud del prompt",
                        status=(
                            PromptEfficiencyStatus.EFFICIENT
                        ),
                        value=4000,
                        unit="tokens",
                        score=92.0,
                    )
                ],
            ),
        ]

        return PromptIntelligenceReport(
            report_id="PROMPT-DASH-REPORT",
            generated_at="2026-07-16T06:00:00Z",
            project_id="DASHBOARD_TEST",
            status=PromptEfficiencyStatus.CRITICAL,
            analyses=analyses,
        )

    def _build_cost_report(
        self,
    ) -> ProjectCostReport:
        analyses = [
            StageCostAnalysis(
                analysis_id="COST-DASH-001",
                project_id="DASHBOARD_TEST",
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
                    total_cost=0.07776,
                ),
                duration_seconds=200.0,
            ),
            StageCostAnalysis(
                analysis_id="COST-DASH-002",
                project_id="DASHBOARD_TEST",
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
                    total_cost=0.0351,
                ),
                duration_seconds=25.0,
            ),
        ]

        return ProjectCostReport(
            report_id="COST-DASH-REPORT",
            generated_at="2026-07-16T06:00:00Z",
            project_id="DASHBOARD_TEST",
            status=CostStatus.CALCULATED,
            analyses=analyses,
        )

    def _build_optimization_plan(
        self,
    ) -> OptimizationPlan:
        prompt_recommendation = (
            OptimizationRecommendation(
                recommendation_id="OPT-DASH-001",
                title="Reducir prompt del Storyboard",
                description=(
                    "Compactar contexto redundante."
                ),
                action_type=(
                    OptimizationActionType.REDUCE_PROMPT
                ),
                priority=OptimizationPriority.CRITICAL,
                status=OptimizationStatus.PROPOSED,
                project_id="DASHBOARD_TEST",
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
        )

        output_recommendation = (
            OptimizationRecommendation(
                recommendation_id="OPT-DASH-002",
                title="Ajustar max_output_tokens",
                description=(
                    "Alinear límite con la salida real."
                ),
                action_type=(
                    OptimizationActionType
                    .REDUCE_MAX_OUTPUT_TOKENS
                ),
                priority=OptimizationPriority.HIGH,
                status=OptimizationStatus.PROPOSED,
                project_id="DASHBOARD_TEST",
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
        )

        return OptimizationPlan(
            plan_id="OPT-DASH-PLAN",
            generated_at="2026-07-16T06:00:00Z",
            project_id="DASHBOARD_TEST",
            status=OptimizationStatus.PROPOSED,
            analyses=[
                StageOptimizationAnalysis(
                    analysis_id="STAGE-OPT-DASH-001",
                    project_id="DASHBOARD_TEST",
                    stage="storyboard",
                    optimization_score=20.0,
                    health_status="UNHEALTHY",
                    prompt_status="CRITICAL",
                    cost_status="CALCULATED",
                    duration_seconds=200.0,
                    prompt_tokens=18000,
                    response_tokens=600,
                    thinking_tokens=1200,
                    total_tokens=19800,
                    retry_count=2,
                    retry_exhausted=True,
                    estimated_cost=0.07776,
                    recommendations=[
                        prompt_recommendation,
                        output_recommendation,
                    ],
                ),
                StageOptimizationAnalysis(
                    analysis_id="STAGE-OPT-DASH-002",
                    project_id="DASHBOARD_TEST",
                    stage="seo",
                    optimization_score=90.0,
                    health_status="HEALTHY",
                    prompt_status="EFFICIENT",
                    cost_status="CALCULATED",
                    duration_seconds=25.0,
                    prompt_tokens=4000,
                    response_tokens=1200,
                    thinking_tokens=300,
                    total_tokens=5500,
                    estimated_cost=0.0351,
                    recommendations=[],
                ),
            ],
        )

    # --------------------------------------------------
    # Utilidades
    # --------------------------------------------------

    def _require_dashboard(
        self,
    ) -> ExecutiveDashboard:
        if self.dashboard is None:
            raise RuntimeError(
                "El Dashboard no ha sido generado."
            )

        return self.dashboard

    # --------------------------------------------------
    # Impresión
    # --------------------------------------------------

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
        print("RESUMEN EXECUTIVE DASHBOARD")
        print("=" * 70)
        print(
            f"Escenarios ejecutados: "
            f"{len(self.results)}"
        )
        print(
            f"Escenarios aprobados: {passed}"
        )
        print(
            f"Escenarios fallidos: {failed}"
        )
        print(
            f"Resultado integral válido: {valid}"
        )
        print()
        print(
            "Artefactos conservados para inspección:"
        )
        print(f"- {TEST_ROOT}")

        if valid:
            print()
            print(
                "Executive Dashboard Smoke Test "
                "completado correctamente."
            )

        return valid


def main() -> int:
    return 0 if DashboardSmokeTest().run() else 1


if __name__ == "__main__":
    sys.exit(main())