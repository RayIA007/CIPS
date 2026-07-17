"""
=========================================================
Proyecto : CIPS
Release  : 0.9
Build    : 084
Archivo  : dashboard_generator.py
Estado   : RELEASE
=========================================================

Genera el Executive Dashboard a partir de los reportes
de inteligencia del proyecto.

Fuentes soportadas:
- ProjectIntelligenceReport;
- RuntimeHealthReport;
- PromptIntelligenceReport;
- ProjectCostReport;
- OptimizationPlan.

Responsabilidades:
- construir tarjetas KPI;
- construir gráficos por Stage;
- construir secciones ejecutivas;
- sintetizar riesgos, fortalezas y recomendaciones;
- devolver ExecutiveDashboard;
- mantener el generador desacoplado del exportador.

Este módulo NO:
- lee archivos;
- escribe archivos;
- genera HTML;
- ejecuta el Pipeline;
- llama proveedores;
- aplica optimizaciones.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from cost_models import ProjectCostReport
from dashboard_models import (
    DashboardCard,
    DashboardCardType,
    DashboardChart,
    DashboardChartType,
    DashboardSection,
    DashboardSeries,
    DashboardStatus,
    ExecutiveDashboard,
    dashboard_status_from_score,
    unique_strings,
)
from health_models import RuntimeHealthReport
from optimization_models import OptimizationPlan
from project_intelligence_models import (
    ProjectIntelligenceReport,
)
from prompt_intelligence_models import (
    PromptIntelligenceReport,
)


class DashboardGenerator:
    """
    Construye el Dashboard Ejecutivo de CIPS.
    """

    COMPONENT_NAME = "dashboard_generator"
    VERSION = "0.9"

    def generate(
        self,
        *,
        project_intelligence: ProjectIntelligenceReport,
        health_report: RuntimeHealthReport | None = None,
        prompt_report: PromptIntelligenceReport | None = None,
        cost_report: ProjectCostReport | None = None,
        optimization_plan: OptimizationPlan | None = None,
    ) -> ExecutiveDashboard:
        """
        Genera el Dashboard completo en memoria.
        """

        if not isinstance(
            project_intelligence,
            ProjectIntelligenceReport,
        ):
            raise TypeError(
                "project_intelligence debe ser "
                "ProjectIntelligenceReport."
            )

        cards = self._build_cards(
            project_intelligence=project_intelligence,
            health_report=health_report,
            prompt_report=prompt_report,
            cost_report=cost_report,
            optimization_plan=optimization_plan,
        )

        charts = self._build_charts(
            project_intelligence=project_intelligence,
            health_report=health_report,
            prompt_report=prompt_report,
            cost_report=cost_report,
            optimization_plan=optimization_plan,
        )

        sections = self._build_sections(
            project_intelligence=project_intelligence,
            cards=cards,
            charts=charts,
            optimization_plan=optimization_plan,
        )

        warnings = self._build_warnings(
            health_report=health_report,
            prompt_report=prompt_report,
            cost_report=cost_report,
            optimization_plan=optimization_plan,
        )

        dashboard = ExecutiveDashboard(
            dashboard_id=self._new_dashboard_id(),
            generated_at=self._utc_now(),
            project_id=project_intelligence.project_id,
            status=self._map_status(
                project_intelligence.status.value
            ),
            title="CIPS Executive Dashboard",
            executive_summary=(
                project_intelligence.executive_summary
            ),
            cards=cards,
            charts=charts,
            sections=sections,
            warnings=warnings,
            metadata={
                "component": self.COMPONENT_NAME,
                "version": self.VERSION,
                "source_report_id": (
                    project_intelligence.report_id
                ),
                "source_status": (
                    project_intelligence.status.value
                ),
                "sources": {
                    "project_intelligence": True,
                    "runtime_health": (
                        health_report is not None
                    ),
                    "prompt_intelligence": (
                        prompt_report is not None
                    ),
                    "cost_report": (
                        cost_report is not None
                    ),
                    "optimization_plan": (
                        optimization_plan is not None
                    ),
                },
            },
        )

        dashboard.recalculate_status()

        return dashboard

    def _build_cards(
        self,
        *,
        project_intelligence: ProjectIntelligenceReport,
        health_report: RuntimeHealthReport | None,
        prompt_report: PromptIntelligenceReport | None,
        cost_report: ProjectCostReport | None,
        optimization_plan: OptimizationPlan | None,
    ) -> list[DashboardCard]:
        """
        Construye las tarjetas principales.
        """

        cards = [
            DashboardCard(
                card_id="CARD-AI-PROJECT-SCORE",
                title="AI Project Score",
                value=project_intelligence.ai_project_score,
                status=dashboard_status_from_score(
                    project_intelligence.ai_project_score
                ),
                card_type=DashboardCardType.KPI,
                unit="/100",
                icon="brain",
                accent="primary",
                description=(
                    "Puntuación global consolidada "
                    "del proyecto."
                ),
                priority=100,
            ),
            DashboardCard(
                card_id="CARD-HEALTH-SCORE",
                title="Runtime Health",
                value=project_intelligence.health_score,
                status=dashboard_status_from_score(
                    project_intelligence.health_score
                ),
                card_type=DashboardCardType.STATUS,
                unit="/100",
                icon="activity",
                accent="health",
                description=(
                    "Estado operativo consolidado "
                    "del Runtime."
                ),
                priority=90,
            ),
            DashboardCard(
                card_id="CARD-PROMPT-EFFICIENCY",
                title="Prompt Efficiency",
                value=(
                    project_intelligence
                    .prompt_efficiency_score
                ),
                status=dashboard_status_from_score(
                    project_intelligence
                    .prompt_efficiency_score
                ),
                card_type=DashboardCardType.KPI,
                unit="/100",
                icon="message-square",
                accent="prompt",
                priority=85,
            ),
            DashboardCard(
                card_id="CARD-RELIABILITY",
                title="Reliability",
                value=(
                    project_intelligence
                    .reliability_score
                ),
                status=dashboard_status_from_score(
                    project_intelligence
                    .reliability_score
                ),
                card_type=DashboardCardType.KPI,
                unit="/100",
                icon="shield-check",
                accent="reliability",
                priority=80,
            ),
            DashboardCard(
                card_id="CARD-COST-EFFICIENCY",
                title="Cost Efficiency",
                value=(
                    project_intelligence
                    .cost_efficiency_score
                ),
                status=dashboard_status_from_score(
                    project_intelligence
                    .cost_efficiency_score
                ),
                card_type=DashboardCardType.COST,
                unit="/100",
                icon="coins",
                accent="cost",
                priority=75,
            ),
            DashboardCard(
                card_id="CARD-OPTIMIZATION-POTENTIAL",
                title="Optimization Potential",
                value=(
                    project_intelligence
                    .optimization_potential_score
                ),
                status=dashboard_status_from_score(
                    project_intelligence
                    .optimization_potential_score
                ),
                card_type=(
                    DashboardCardType.RECOMMENDATION
                ),
                unit="/100",
                icon="wrench",
                accent="optimization",
                priority=70,
                metadata={
                    "inverse_interpretation": False,
                },
            ),
            DashboardCard(
                card_id="CARD-SUCCESS-RATE",
                title="Success Rate",
                value=project_intelligence.success_rate,
                status=dashboard_status_from_score(
                    project_intelligence.success_rate
                ),
                card_type=DashboardCardType.METRIC,
                unit="%",
                icon="check-circle",
                accent="success",
                priority=65,
            ),
            DashboardCard(
                card_id="CARD-TOTAL-COST",
                title="Total Cost",
                value=project_intelligence.total_cost,
                status=self._cost_status(
                    cost_report
                ),
                card_type=DashboardCardType.COST,
                unit=project_intelligence.currency,
                icon="wallet",
                accent="cost",
                priority=60,
            ),
            DashboardCard(
                card_id="CARD-TOTAL-TOKENS",
                title="Total Tokens",
                value=project_intelligence.total_tokens,
                status=DashboardStatus.GOOD,
                card_type=DashboardCardType.METRIC,
                unit="tokens",
                icon="hash",
                accent="tokens",
                priority=55,
            ),
            DashboardCard(
                card_id="CARD-RETRY-COUNT",
                title="Retries",
                value=project_intelligence.retry_count,
                status=self._retry_status(
                    project_intelligence.retry_count,
                    project_intelligence.exhausted_events,
                ),
                card_type=DashboardCardType.METRIC,
                unit="retries",
                icon="rotate-cw",
                accent="retry",
                priority=50,
            ),
        ]

        if health_report is not None:
            cards.append(
                DashboardCard(
                    card_id="CARD-HEALTH-STATUS",
                    title="Health Status",
                    value=health_report.status.value,
                    status=self._map_status(
                        health_report.status.value
                    ),
                    card_type=DashboardCardType.STATUS,
                    icon="heart-pulse",
                    accent="health",
                    priority=68,
                )
            )

        if prompt_report is not None:
            cards.append(
                DashboardCard(
                    card_id="CARD-PROMPT-ANALYSES",
                    title="Prompt Analyses",
                    value=prompt_report.analyses_total,
                    status=self._map_status(
                        prompt_report.status.value
                    ),
                    card_type=DashboardCardType.METRIC,
                    unit="analyses",
                    icon="layers",
                    accent="prompt",
                    priority=45,
                )
            )

        if optimization_plan is not None:
            cards.append(
                DashboardCard(
                    card_id="CARD-RECOMMENDATIONS",
                    title="Recommendations",
                    value=(
                        optimization_plan
                        .recommendations_total
                    ),
                    status=self._priority_status(
                        optimization_plan.priority.value
                    ),
                    card_type=(
                        DashboardCardType.RECOMMENDATION
                    ),
                    unit="actions",
                    icon="list-checks",
                    accent="optimization",
                    priority=58,
                    description=(
                        "Cantidad total de recomendaciones "
                        "de optimización."
                    ),
                )
            )

            cards.append(
                DashboardCard(
                    card_id="CARD-ESTIMATED-SAVINGS",
                    title="Estimated Savings",
                    value=(
                        optimization_plan
                        .estimated_total_savings
                    ),
                    status=DashboardStatus.GOOD,
                    card_type=DashboardCardType.COST,
                    unit=optimization_plan.currency,
                    icon="piggy-bank",
                    accent="savings",
                    priority=57,
                )
            )

        return cards

    def _build_charts(
        self,
        *,
        project_intelligence: ProjectIntelligenceReport,
        health_report: RuntimeHealthReport | None,
        prompt_report: PromptIntelligenceReport | None,
        cost_report: ProjectCostReport | None,
        optimization_plan: OptimizationPlan | None,
    ) -> list[DashboardChart]:
        """
        Construye los gráficos ejecutivos.
        """

        charts: list[DashboardChart] = [
            self._build_kpi_radar(
                project_intelligence
            )
        ]

        if health_report is not None:
            charts.append(
                self._build_health_chart(
                    health_report
                )
            )

        if prompt_report is not None:
            charts.extend(
                [
                    self._build_prompt_score_chart(
                        prompt_report
                    ),
                    self._build_prompt_tokens_chart(
                        prompt_report
                    ),
                ]
            )

        if cost_report is not None:
            charts.extend(
                [
                    self._build_cost_chart(
                        cost_report
                    ),
                    self._build_cost_tokens_chart(
                        cost_report
                    ),
                ]
            )

        if optimization_plan is not None:
            charts.append(
                self._build_optimization_chart(
                    optimization_plan
                )
            )

        charts.append(
            self._build_reliability_donut(
                project_intelligence
            )
        )

        return charts

    def _build_kpi_radar(
        self,
        report: ProjectIntelligenceReport,
    ) -> DashboardChart:
        labels = [
            "Health",
            "Prompt Efficiency",
            "Reliability",
            "Cost Efficiency",
            "Optimization Potential",
        ]

        values = [
            report.health_score,
            report.prompt_efficiency_score,
            report.reliability_score,
            report.cost_efficiency_score,
            report.optimization_potential_score,
        ]

        return DashboardChart(
            chart_id="CHART-KPI-RADAR",
            title="Executive KPI Profile",
            chart_type=DashboardChartType.RADAR,
            series=[
                DashboardSeries(
                    series_id="SERIES-KPI",
                    name="Score",
                    values=values,
                    labels=labels,
                    unit="/100",
                )
            ],
            labels=labels,
            status=self._map_status(
                report.status.value
            ),
            priority=100,
            options={
                "minimum": 0,
                "maximum": 100,
            },
        )

    def _build_health_chart(
        self,
        report: RuntimeHealthReport,
    ) -> DashboardChart:
        labels: list[str] = []
        success_values: list[float] = []
        failure_values: list[float] = []

        for component in report.components:
            labels.append(
                component.component
            )
            success_values.append(
                component.success_rate
            )
            failure_values.append(
                component.failure_rate
            )

        return DashboardChart(
            chart_id="CHART-HEALTH-COMPONENTS",
            title="Runtime Health by Component",
            chart_type=DashboardChartType.BAR,
            series=[
                DashboardSeries(
                    series_id="SERIES-HEALTH-SUCCESS",
                    name="Success Rate",
                    values=success_values,
                    labels=labels,
                    unit="%",
                ),
                DashboardSeries(
                    series_id="SERIES-HEALTH-FAILURE",
                    name="Failure Rate",
                    values=failure_values,
                    labels=labels,
                    unit="%",
                    chart_role="secondary",
                ),
            ],
            labels=labels,
            status=self._map_status(
                report.status.value
            ),
            priority=90,
        )

    def _build_prompt_score_chart(
        self,
        report: PromptIntelligenceReport,
    ) -> DashboardChart:
        labels = [
            analysis.stage or "sin_stage"
            for analysis in report.analyses
        ]

        values = [
            analysis.efficiency_score
            for analysis in report.analyses
        ]

        return DashboardChart(
            chart_id="CHART-PROMPT-EFFICIENCY",
            title="Prompt Efficiency by Stage",
            chart_type=DashboardChartType.BAR,
            series=[
                DashboardSeries(
                    series_id="SERIES-PROMPT-EFFICIENCY",
                    name="Efficiency Score",
                    values=values,
                    labels=labels,
                    unit="/100",
                )
            ],
            labels=labels,
            status=self._map_status(
                report.status.value
            ),
            priority=85,
        )

    def _build_prompt_tokens_chart(
        self,
        report: PromptIntelligenceReport,
    ) -> DashboardChart:
        labels = [
            analysis.stage or "sin_stage"
            for analysis in report.analyses
        ]

        return DashboardChart(
            chart_id="CHART-PROMPT-TOKENS",
            title="Token Distribution by Stage",
            chart_type=DashboardChartType.BAR,
            series=[
                DashboardSeries(
                    series_id="SERIES-PROMPT-TOKENS",
                    name="Prompt Tokens",
                    values=[
                        analysis.prompt_tokens
                        for analysis in report.analyses
                    ],
                    labels=labels,
                    unit="tokens",
                ),
                DashboardSeries(
                    series_id="SERIES-RESPONSE-TOKENS",
                    name="Response Tokens",
                    values=[
                        analysis.response_tokens
                        for analysis in report.analyses
                    ],
                    labels=labels,
                    unit="tokens",
                    chart_role="secondary",
                ),
                DashboardSeries(
                    series_id="SERIES-THINKING-TOKENS",
                    name="Thinking Tokens",
                    values=[
                        analysis.thinking_tokens
                        for analysis in report.analyses
                    ],
                    labels=labels,
                    unit="tokens",
                    chart_role="secondary",
                ),
            ],
            labels=labels,
            status=self._map_status(
                report.status.value
            ),
            priority=80,
        )

    def _build_cost_chart(
        self,
        report: ProjectCostReport,
    ) -> DashboardChart:
        labels = [
            analysis.stage or "sin_stage"
            for analysis in report.analyses
        ]

        values = [
            analysis.cost.total_cost
            for analysis in report.analyses
        ]

        return DashboardChart(
            chart_id="CHART-COST-BY-STAGE",
            title="Cost by Stage",
            chart_type=DashboardChartType.BAR,
            series=[
                DashboardSeries(
                    series_id="SERIES-COST",
                    name="Cost",
                    values=values,
                    labels=labels,
                    unit=report.currency,
                )
            ],
            labels=labels,
            status=self._map_status(
                report.status.value
            ),
            priority=78,
        )

    def _build_cost_tokens_chart(
        self,
        report: ProjectCostReport,
    ) -> DashboardChart:
        labels = [
            analysis.stage or "sin_stage"
            for analysis in report.analyses
        ]

        values = [
            analysis.token_usage.total_tokens
            for analysis in report.analyses
        ]

        return DashboardChart(
            chart_id="CHART-COST-TOKENS",
            title="Billable Tokens by Stage",
            chart_type=DashboardChartType.AREA,
            series=[
                DashboardSeries(
                    series_id="SERIES-COST-TOKENS",
                    name="Total Tokens",
                    values=values,
                    labels=labels,
                    unit="tokens",
                )
            ],
            labels=labels,
            status=self._map_status(
                report.status.value
            ),
            priority=72,
        )

    def _build_optimization_chart(
        self,
        plan: OptimizationPlan,
    ) -> DashboardChart:
        labels = [
            analysis.stage or "sin_stage"
            for analysis in plan.analyses
        ]

        values = [
            analysis.optimization_score
            for analysis in plan.analyses
        ]

        return DashboardChart(
            chart_id="CHART-OPTIMIZATION",
            title="Optimization Score by Stage",
            chart_type=DashboardChartType.BAR,
            series=[
                DashboardSeries(
                    series_id="SERIES-OPTIMIZATION",
                    name="Optimization Score",
                    values=values,
                    labels=labels,
                    unit="/100",
                )
            ],
            labels=labels,
            status=self._priority_status(
                plan.priority.value
            ),
            priority=76,
        )

    def _build_reliability_donut(
        self,
        report: ProjectIntelligenceReport,
    ) -> DashboardChart:
        labels = [
            "Successful",
            "Failed",
        ]

        return DashboardChart(
            chart_id="CHART-RELIABILITY",
            title="Execution Reliability",
            chart_type=DashboardChartType.DONUT,
            series=[
                DashboardSeries(
                    series_id="SERIES-RELIABILITY",
                    name="Events",
                    values=[
                        report.successful_events,
                        report.failed_events,
                    ],
                    labels=labels,
                    unit="events",
                )
            ],
            labels=labels,
            status=dashboard_status_from_score(
                report.reliability_score
            ),
            priority=70,
        )

    def _build_sections(
        self,
        *,
        project_intelligence: ProjectIntelligenceReport,
        cards: list[DashboardCard],
        charts: list[DashboardChart],
        optimization_plan: OptimizationPlan | None,
    ) -> list[DashboardSection]:
        """
        Construye las secciones del Dashboard.
        """

        card_map = {
            card.card_id: card
            for card in cards
        }

        chart_map = {
            chart.chart_id: chart
            for chart in charts
        }

        recommendations = [
            (
                f"[{recommendation.priority}] "
                f"{recommendation.title}"
            )
            for recommendation
            in project_intelligence.top_recommendations(
                10
            )
        ]

        if (
            optimization_plan is not None
            and not recommendations
        ):
            recommendations = [
                (
                    f"[{recommendation.priority.value}] "
                    f"{recommendation.title}"
                )
                for analysis in optimization_plan.analyses
                for recommendation in analysis.recommendations
            ][:10]

        return [
            DashboardSection(
                section_id="SECTION-EXECUTIVE",
                title="Executive Summary",
                status=self._map_status(
                    project_intelligence.status.value
                ),
                description=(
                    project_intelligence.executive_summary
                ),
                cards=self._select_cards(
                    card_map,
                    [
                        "CARD-AI-PROJECT-SCORE",
                        "CARD-HEALTH-SCORE",
                        "CARD-PROMPT-EFFICIENCY",
                        "CARD-RELIABILITY",
                        "CARD-COST-EFFICIENCY",
                        "CARD-OPTIMIZATION-POTENTIAL",
                    ],
                ),
                charts=self._select_charts(
                    chart_map,
                    [
                        "CHART-KPI-RADAR",
                        "CHART-RELIABILITY",
                    ],
                ),
                priority=100,
            ),
            DashboardSection(
                section_id="SECTION-RUNTIME",
                title="Runtime & Reliability",
                status=dashboard_status_from_score(
                    project_intelligence.health_score
                ),
                cards=self._select_cards(
                    card_map,
                    [
                        "CARD-HEALTH-STATUS",
                        "CARD-SUCCESS-RATE",
                        "CARD-RETRY-COUNT",
                    ],
                ),
                charts=self._select_charts(
                    chart_map,
                    [
                        "CHART-HEALTH-COMPONENTS",
                        "CHART-RELIABILITY",
                    ],
                ),
                items=list(
                    project_intelligence.risks
                ),
                priority=90,
            ),
            DashboardSection(
                section_id="SECTION-PROMPTS",
                title="Prompt Intelligence",
                status=dashboard_status_from_score(
                    project_intelligence
                    .prompt_efficiency_score
                ),
                cards=self._select_cards(
                    card_map,
                    [
                        "CARD-PROMPT-EFFICIENCY",
                        "CARD-PROMPT-ANALYSES",
                        "CARD-TOTAL-TOKENS",
                    ],
                ),
                charts=self._select_charts(
                    chart_map,
                    [
                        "CHART-PROMPT-EFFICIENCY",
                        "CHART-PROMPT-TOKENS",
                    ],
                ),
                priority=85,
            ),
            DashboardSection(
                section_id="SECTION-COST",
                title="Cost Analytics",
                status=dashboard_status_from_score(
                    project_intelligence
                    .cost_efficiency_score
                ),
                cards=self._select_cards(
                    card_map,
                    [
                        "CARD-TOTAL-COST",
                        "CARD-COST-EFFICIENCY",
                        "CARD-ESTIMATED-SAVINGS",
                    ],
                ),
                charts=self._select_charts(
                    chart_map,
                    [
                        "CHART-COST-BY-STAGE",
                        "CHART-COST-TOKENS",
                    ],
                ),
                priority=80,
            ),
            DashboardSection(
                section_id="SECTION-OPTIMIZATION",
                title="Optimization",
                status=dashboard_status_from_score(
                    project_intelligence
                    .optimization_potential_score
                ),
                cards=self._select_cards(
                    card_map,
                    [
                        "CARD-OPTIMIZATION-POTENTIAL",
                        "CARD-RECOMMENDATIONS",
                        "CARD-ESTIMATED-SAVINGS",
                    ],
                ),
                charts=self._select_charts(
                    chart_map,
                    [
                        "CHART-OPTIMIZATION",
                    ],
                ),
                items=recommendations,
                priority=75,
            ),
            DashboardSection(
                section_id="SECTION-RISKS",
                title="Risks & Strengths",
                status=self._risk_section_status(
                    project_intelligence
                ),
                items=unique_strings(
                    [
                        *[
                            f"RISK: {item}"
                            for item in (
                                project_intelligence.risks
                            )
                        ],
                        *[
                            f"STRENGTH: {item}"
                            for item in (
                                project_intelligence.strengths
                            )
                        ],
                    ]
                ),
                priority=70,
            ),
        ]

    def _select_cards(
        self,
        card_map: dict[str, DashboardCard],
        card_ids: list[str],
    ) -> list[DashboardCard]:
        return [
            card_map[card_id]
            for card_id in card_ids
            if card_id in card_map
        ]

    def _select_charts(
        self,
        chart_map: dict[str, DashboardChart],
        chart_ids: list[str],
    ) -> list[DashboardChart]:
        return [
            chart_map[chart_id]
            for chart_id in chart_ids
            if chart_id in chart_map
        ]

    def _build_warnings(
        self,
        *,
        health_report: RuntimeHealthReport | None,
        prompt_report: PromptIntelligenceReport | None,
        cost_report: ProjectCostReport | None,
        optimization_plan: OptimizationPlan | None,
    ) -> list[str]:
        warnings: list[str] = []

        if health_report is None:
            warnings.append(
                "RuntimeHealthReport no disponible."
            )

        if prompt_report is None:
            warnings.append(
                "PromptIntelligenceReport no disponible."
            )

        if cost_report is None:
            warnings.append(
                "ProjectCostReport no disponible."
            )

        if optimization_plan is None:
            warnings.append(
                "OptimizationPlan no disponible."
            )

        return warnings

    def _map_status(
        self,
        value: str,
    ) -> DashboardStatus:
        normalized = str(
            value or ""
        ).strip().upper()

        aliases = {
            "HEALTHY": DashboardStatus.EXCELLENT,
            "DEGRADED": DashboardStatus.ATTENTION,
            "UNHEALTHY": DashboardStatus.CRITICAL,
            "EFFICIENT": DashboardStatus.EXCELLENT,
            "ACCEPTABLE": DashboardStatus.GOOD,
            "INEFFICIENT": DashboardStatus.ATTENTION,
            "CALCULATED": DashboardStatus.GOOD,
            "FREE_TIER": DashboardStatus.EXCELLENT,
            "PARTIAL": DashboardStatus.ATTENTION,
            "UNKNOWN_PRICING": DashboardStatus.ATTENTION,
            "INVALID": DashboardStatus.CRITICAL,
        }

        if normalized in aliases:
            return aliases[
                normalized
            ]

        return DashboardStatus.normalize(
            normalized
        )

    def _priority_status(
        self,
        priority: str,
    ) -> DashboardStatus:
        normalized = str(
            priority or ""
        ).strip().upper()

        return {
            "LOW": DashboardStatus.GOOD,
            "MEDIUM": DashboardStatus.ATTENTION,
            "HIGH": DashboardStatus.ATTENTION,
            "CRITICAL": DashboardStatus.CRITICAL,
            "UNKNOWN": DashboardStatus.UNKNOWN,
        }.get(
            normalized,
            DashboardStatus.UNKNOWN,
        )

    def _cost_status(
        self,
        report: ProjectCostReport | None,
    ) -> DashboardStatus:
        if report is None:
            return DashboardStatus.UNKNOWN

        return self._map_status(
            report.status.value
        )

    def _retry_status(
        self,
        retry_count: int,
        exhausted_events: int,
    ) -> DashboardStatus:
        if exhausted_events > 0:
            return DashboardStatus.CRITICAL

        if retry_count >= 3:
            return DashboardStatus.ATTENTION

        if retry_count > 0:
            return DashboardStatus.GOOD

        return DashboardStatus.EXCELLENT

    def _risk_section_status(
        self,
        report: ProjectIntelligenceReport,
    ) -> DashboardStatus:
        if report.critical_findings():
            return DashboardStatus.CRITICAL

        if report.risks:
            return DashboardStatus.ATTENTION

        return DashboardStatus.GOOD

    def _new_dashboard_id(
        self,
    ) -> str:
        return (
            "DASHBOARD-"
            + uuid4().hex.upper()
        )

    def _utc_now(
        self,
    ) -> str:
        return (
            datetime.now(
                timezone.utc
            )
            .isoformat(
                timespec="milliseconds"
            )
            .replace(
                "+00:00",
                "Z",
            )
        )

    def get_component_info(
        self,
    ) -> dict[str, Any]:
        """
        Devuelve información pública.
        """

        return {
            "component": self.COMPONENT_NAME,
            "version": self.VERSION,
            "reads_files": False,
            "writes_files": False,
            "input_models": [
                "ProjectIntelligenceReport",
                "RuntimeHealthReport",
                "PromptIntelligenceReport",
                "ProjectCostReport",
                "OptimizationPlan",
            ],
            "output_model": "ExecutiveDashboard",
            "cards_generated": [
                "AI Project Score",
                "Runtime Health",
                "Prompt Efficiency",
                "Reliability",
                "Cost Efficiency",
                "Optimization Potential",
                "Success Rate",
                "Total Cost",
                "Total Tokens",
                "Retries",
            ],
            "charts_generated": [
                "Executive KPI Profile",
                "Runtime Health by Component",
                "Prompt Efficiency by Stage",
                "Token Distribution by Stage",
                "Cost by Stage",
                "Billable Tokens by Stage",
                "Optimization Score by Stage",
                "Execution Reliability",
            ],
            "next_component": "dashboard_exporter",
        }