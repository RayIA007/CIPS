"""
=========================================================
Proyecto : CIPS
Release  : 0.9
Build    : 079
Archivo  : project_intelligence_engine.py
Estado   : RELEASE
=========================================================

Genera el reporte ejecutivo consolidado de Project Intelligence.

Fuentes:
- TelemetrySummary;
- RuntimeHealthReport;
- PromptIntelligenceReport;
- ProjectCostReport;
- OptimizationPlan.

Responsabilidades:
- calcular KPIs ejecutivos;
- sintetizar hallazgos;
- consolidar recomendaciones;
- generar resumen ejecutivo;
- persistir PROJECT_INTELLIGENCE.json;
- persistir PROJECT_INTELLIGENCE.md;
- mantener el motor desacoplado del Pipeline.

Este componente NO:
- llama proveedores;
- ejecuta el Pipeline;
- modifica configuración;
- aplica optimizaciones;
- reescribe telemetría;
- sustituye los motores fuente.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from cost_models import (
    CostStatus,
    ProjectCostReport,
)
from health_models import (
    HealthStatus,
    RuntimeHealthReport,
)
from optimization_models import (
    OptimizationPlan,
    OptimizationPriority,
)
from project_intelligence_models import (
    ExecutiveFinding,
    FindingType,
    IntelligenceRecommendation,
    IntelligenceStatus,
    ProjectIntelligenceReport,
    ProjectKPI,
    intelligence_status_from_score,
    unique_strings,
)
from prompt_intelligence_models import (
    PromptEfficiencyStatus,
    PromptIntelligenceReport,
)
from runtime_models import EngineResult
from telemetry_models import TelemetrySummary


class ProjectIntelligenceEngine:
    """
    Motor ejecutivo de inteligencia del proyecto.
    """

    COMPONENT_NAME = "project_intelligence_engine"
    VERSION = "0.9"

    TELEMETRY_DIRECTORY = "03_TELEMETRIA"
    JSON_FILENAME = "PROJECT_INTELLIGENCE.json"
    MARKDOWN_FILENAME = "PROJECT_INTELLIGENCE.md"

    def execute(
        self,
        *,
        project_path: Path | str,
        telemetry_summary: TelemetrySummary | None = None,
        health_report: RuntimeHealthReport | None = None,
        prompt_report: PromptIntelligenceReport | None = None,
        cost_report: ProjectCostReport | None = None,
        optimization_plan: OptimizationPlan | None = None,
        persist: bool = True,
    ) -> EngineResult:
        """
        Genera y opcionalmente persiste Project Intelligence.
        """

        try:
            resolved_path = Path(
                project_path
            ).expanduser().resolve()

            if not resolved_path.exists():
                return EngineResult.fail(
                    message=(
                        "No existe la ruta del proyecto."
                    ),
                    errors=[
                        str(
                            resolved_path
                        )
                    ],
                    metadata={
                        "component": self.COMPONENT_NAME,
                        "version": self.VERSION,
                    },
                )

            report = self.build_report(
                project_path=resolved_path,
                telemetry_summary=telemetry_summary,
                health_report=health_report,
                prompt_report=prompt_report,
                cost_report=cost_report,
                optimization_plan=optimization_plan,
            )

            json_path = (
                resolved_path
                / self.TELEMETRY_DIRECTORY
                / self.JSON_FILENAME
            )

            markdown_path = (
                resolved_path
                / self.TELEMETRY_DIRECTORY
                / self.MARKDOWN_FILENAME
            )

            if persist:
                self.persist_report(
                    report=report,
                    json_path=json_path,
                    markdown_path=markdown_path,
                )

            return EngineResult.ok(
                data={
                    "report": report,
                    "json_path": str(
                        json_path
                    ),
                    "markdown_path": str(
                        markdown_path
                    ),
                },
                message=(
                    "Project Intelligence generado "
                    "correctamente."
                ),
                warnings=list(
                    report.warnings
                ),
                metadata={
                    "component": self.COMPONENT_NAME,
                    "version": self.VERSION,
                    "project_id": (
                        report.project_id
                    ),
                    "status": (
                        report.status.value
                    ),
                    "ai_project_score": (
                        report.ai_project_score
                    ),
                    "findings_total": len(
                        report.findings
                    ),
                    "recommendations_total": len(
                        report.recommendations
                    ),
                    "persisted": persist,
                    "json_path": str(
                        json_path
                    ),
                    "markdown_path": str(
                        markdown_path
                    ),
                },
            )

        except Exception as error:
            return EngineResult.fail(
                message=(
                    "No fue posible generar "
                    "Project Intelligence."
                ),
                errors=[
                    str(
                        error
                    )
                ],
                metadata={
                    "component": self.COMPONENT_NAME,
                    "version": self.VERSION,
                },
            )

    def build_report(
        self,
        *,
        project_path: Path | str,
        telemetry_summary: TelemetrySummary | None = None,
        health_report: RuntimeHealthReport | None = None,
        prompt_report: PromptIntelligenceReport | None = None,
        cost_report: ProjectCostReport | None = None,
        optimization_plan: OptimizationPlan | None = None,
    ) -> ProjectIntelligenceReport:
        """
        Construye el reporte ejecutivo sin persistirlo.
        """

        resolved_path = Path(
            project_path
        ).expanduser().resolve()

        project_id = self._infer_project_id(
            resolved_path=resolved_path,
            telemetry_summary=telemetry_summary,
            health_report=health_report,
            prompt_report=prompt_report,
            cost_report=cost_report,
            optimization_plan=optimization_plan,
        )

        telemetry_data = self._telemetry_data(
            telemetry_summary
        )

        health_score = self._calculate_health_score(
            health_report
        )

        prompt_score = self._calculate_prompt_score(
            prompt_report
        )

        reliability_score = self._calculate_reliability_score(
            telemetry_summary=telemetry_summary,
            health_report=health_report,
        )

        cost_efficiency_score = self._calculate_cost_efficiency_score(
            cost_report
        )

        optimization_potential_score = (
            self._calculate_optimization_potential_score(
                optimization_plan
            )
        )

        kpis = self._build_kpis(
            health_score=health_score,
            prompt_score=prompt_score,
            reliability_score=reliability_score,
            cost_efficiency_score=cost_efficiency_score,
            optimization_potential_score=(
                optimization_potential_score
            ),
        )

        findings = self._build_findings(
            telemetry_summary=telemetry_summary,
            health_report=health_report,
            prompt_report=prompt_report,
            cost_report=cost_report,
            optimization_plan=optimization_plan,
        )

        recommendations = self._build_recommendations(
            optimization_plan
        )

        strengths = self._build_strengths(
            telemetry_summary=telemetry_summary,
            health_report=health_report,
            prompt_report=prompt_report,
            cost_report=cost_report,
        )

        risks = self._build_risks(
            findings
        )

        opportunities = self._build_opportunities(
            recommendations
        )

        stages = self._collect_stages(
            health_report=health_report,
            prompt_report=prompt_report,
            cost_report=cost_report,
            optimization_plan=optimization_plan,
        )

        providers = self._collect_providers(
            telemetry_summary=telemetry_summary,
            prompt_report=prompt_report,
            cost_report=cost_report,
        )

        models = self._collect_models(
            telemetry_summary=telemetry_summary,
            prompt_report=prompt_report,
            cost_report=cost_report,
        )

        report = ProjectIntelligenceReport(
            report_id=self._new_report_id(),
            generated_at=self._utc_now(),
            project_id=project_id,
            health_score=health_score,
            prompt_efficiency_score=prompt_score,
            reliability_score=reliability_score,
            cost_efficiency_score=cost_efficiency_score,
            optimization_potential_score=(
                optimization_potential_score
            ),
            telemetry_events=telemetry_data[
                "events_total"
            ],
            successful_events=telemetry_data[
                "successful_events"
            ],
            failed_events=telemetry_data[
                "failed_events"
            ],
            success_rate=telemetry_data[
                "success_rate"
            ],
            total_tokens=telemetry_data[
                "total_tokens"
            ],
            total_cost=(
                cost_report.total_cost
                if cost_report is not None
                else telemetry_data[
                    "estimated_cost"
                ]
            ),
            currency=(
                cost_report.currency
                if cost_report is not None
                else telemetry_data[
                    "currency"
                ]
            ),
            total_duration_seconds=telemetry_data[
                "duration_seconds"
            ],
            average_duration_seconds=telemetry_data[
                "average_duration_seconds"
            ],
            retry_count=telemetry_data[
                "retry_count"
            ],
            exhausted_events=telemetry_data[
                "exhausted_events"
            ],
            recovered_events=telemetry_data[
                "recovered_events"
            ],
            kpis=kpis,
            findings=findings,
            recommendations=recommendations,
            strengths=strengths,
            risks=risks,
            opportunities=opportunities,
            stages=stages,
            providers=providers,
            models=models,
            warnings=self._build_warnings(
                telemetry_summary=telemetry_summary,
                health_report=health_report,
                prompt_report=prompt_report,
                cost_report=cost_report,
                optimization_plan=optimization_plan,
            ),
            metadata={
                "component": self.COMPONENT_NAME,
                "version": self.VERSION,
                "project_path": str(
                    resolved_path
                ),
                "sources": {
                    "telemetry_summary": (
                        telemetry_summary is not None
                    ),
                    "health_report": (
                        health_report is not None
                    ),
                    "prompt_report": (
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

        report.executive_summary = self._build_executive_summary(
            report
        )

        report.recalculate()

        return report

    def persist_report(
        self,
        *,
        report: ProjectIntelligenceReport,
        json_path: Path | str,
        markdown_path: Path | str,
    ) -> None:
        """
        Persiste JSON y Markdown.
        """

        resolved_json = Path(
            json_path
        )

        resolved_markdown = Path(
            markdown_path
        )

        resolved_json.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        resolved_markdown.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        resolved_json.write_text(
            json.dumps(
                report.to_dict(),
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        resolved_markdown.write_text(
            self.render_markdown(
                report
            ),
            encoding="utf-8",
        )

    def render_markdown(
        self,
        report: ProjectIntelligenceReport,
    ) -> str:
        """
        Renderiza el reporte ejecutivo en Markdown.
        """

        lines: list[str] = [
            "# Project Intelligence Report",
            "",
            f"**Proyecto:** {report.project_id}",
            f"**Generado:** {report.generated_at}",
            f"**Estado:** {report.status.value}",
            f"**AI Project Score:** {report.ai_project_score}/100",
            "",
            "## Resumen ejecutivo",
            "",
            report.executive_summary
            or "No existe resumen ejecutivo disponible.",
            "",
            "## KPIs",
            "",
            "| KPI | Score | Estado | Tendencia |",
            "|---|---:|---|---|",
        ]

        for kpi in report.kpis:
            lines.append(
                (
                    f"| {kpi.name} "
                    f"| {kpi.normalized_score()} "
                    f"| {kpi.status.value} "
                    f"| {kpi.trend} |"
                )
            )

        lines.extend(
            [
                "",
                "## Métricas operativas",
                "",
                f"- Eventos: {report.telemetry_events}",
                f"- Éxitos: {report.successful_events}",
                f"- Fallos: {report.failed_events}",
                f"- Tasa de éxito: {report.success_rate}%",
                f"- Tokens totales: {report.total_tokens}",
                (
                    f"- Costo estimado: "
                    f"{report.total_cost} {report.currency}"
                ),
                (
                    f"- Duración total: "
                    f"{report.total_duration_seconds} s"
                ),
                (
                    f"- Duración promedio: "
                    f"{report.average_duration_seconds} s"
                ),
                f"- Reintentos: {report.retry_count}",
                (
                    f"- Eventos agotados: "
                    f"{report.exhausted_events}"
                ),
                (
                    f"- Eventos recuperados: "
                    f"{report.recovered_events}"
                ),
                "",
                "## Fortalezas",
                "",
            ]
        )

        lines.extend(
            self._markdown_list(
                report.strengths,
                "No se identificaron fortalezas destacadas.",
            )
        )

        lines.extend(
            [
                "",
                "## Riesgos",
                "",
            ]
        )

        lines.extend(
            self._markdown_list(
                report.risks,
                "No se identificaron riesgos relevantes.",
            )
        )

        lines.extend(
            [
                "",
                "## Oportunidades",
                "",
            ]
        )

        lines.extend(
            self._markdown_list(
                report.opportunities,
                "No se identificaron oportunidades.",
            )
        )

        lines.extend(
            [
                "",
                "## Hallazgos",
                "",
            ]
        )

        if report.findings:
            for finding in sorted(
                report.findings,
                key=lambda item: (
                    -self._priority_rank(
                        item.priority
                    ),
                    -item.impact_score,
                ),
            ):
                lines.extend(
                    [
                        (
                            f"### {finding.priority} — "
                            f"{finding.title}"
                        ),
                        "",
                        finding.description,
                        "",
                        (
                            f"- Tipo: "
                            f"{finding.finding_type.value}"
                        ),
                        (
                            f"- Impacto: "
                            f"{finding.impact_score}/100"
                        ),
                        (
                            f"- Confianza: "
                            f"{finding.confidence_score}/100"
                        ),
                    ]
                )

                if finding.stage:
                    lines.append(
                        f"- Stage: {finding.stage}"
                    )

                if finding.evidence:
                    lines.append(
                        "- Evidencia:"
                    )

                    for evidence in finding.evidence:
                        lines.append(
                            f"  - {evidence}"
                        )

                if finding.recommendation:
                    lines.append(
                        (
                            "- Recomendación: "
                            f"{finding.recommendation}"
                        )
                    )

                lines.append(
                    ""
                )

        else:
            lines.append(
                "No existen hallazgos."
            )

        lines.extend(
            [
                "",
                "## Recomendaciones priorizadas",
                "",
            ]
        )

        top_recommendations = report.top_recommendations(
            10
        )

        if top_recommendations:
            for index, recommendation in enumerate(
                top_recommendations,
                start=1,
            ):
                lines.extend(
                    [
                        (
                            f"{index}. "
                            f"**[{recommendation.priority}] "
                            f"{recommendation.title}**"
                        ),
                        (
                            f"   - Acción: "
                            f"{recommendation.action_type}"
                        ),
                        (
                            f"   - Mejora esperada: "
                            f"{recommendation.expected_improvement_percent}%"
                        ),
                        (
                            f"   - Confianza: "
                            f"{recommendation.confidence_score}%"
                        ),
                        (
                            f"   - Ahorro estimado: "
                            f"{recommendation.estimated_savings} "
                            f"{recommendation.currency}"
                        ),
                    ]
                )

                if recommendation.stage:
                    lines.append(
                        f"   - Stage: {recommendation.stage}"
                    )

                lines.append(
                    ""
                )

        else:
            lines.append(
                "No existen recomendaciones."
            )

        lines.extend(
            [
                "",
                "## Cobertura",
                "",
                (
                    "- Stages: "
                    + (
                        ", ".join(
                            report.stages
                        )
                        if report.stages
                        else "No disponibles"
                    )
                ),
                (
                    "- Proveedores: "
                    + (
                        ", ".join(
                            report.providers
                        )
                        if report.providers
                        else "No disponibles"
                    )
                ),
                (
                    "- Modelos: "
                    + (
                        ", ".join(
                            report.models
                        )
                        if report.models
                        else "No disponibles"
                    )
                ),
            ]
        )

        if report.warnings:
            lines.extend(
                [
                    "",
                    "## Advertencias",
                    "",
                ]
            )

            lines.extend(
                [
                    f"- {warning}"
                    for warning in report.warnings
                ]
            )

        if report.errors:
            lines.extend(
                [
                    "",
                    "## Errores",
                    "",
                ]
            )

            lines.extend(
                [
                    f"- {error}"
                    for error in report.errors
                ]
            )

        lines.append(
            ""
        )

        return "\n".join(
            lines
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
            "json_filename": self.JSON_FILENAME,
            "markdown_filename": self.MARKDOWN_FILENAME,
            "reads_files": False,
            "writes_files": True,
            "uses_telemetry": True,
            "uses_health_report": True,
            "uses_prompt_report": True,
            "uses_cost_report": True,
            "uses_optimization_plan": True,
            "next_component": (
                "project_intelligence_smoke_test"
            ),
        }

    # --------------------------------------------------
    # KPIs
    # --------------------------------------------------

    def _calculate_health_score(
        self,
        report: RuntimeHealthReport | None,
    ) -> float:
        if report is None:
            return 50.0

        base = {
            HealthStatus.HEALTHY: 95.0,
            HealthStatus.DEGRADED: 70.0,
            HealthStatus.UNHEALTHY: 35.0,
            HealthStatus.UNKNOWN: 50.0,
        }.get(
            report.status,
            50.0,
        )

        if report.success_rate > 0:
            base = (
                base * 0.6
                + report.success_rate * 0.4
            )

        penalty = min(
            report.exhausted_events * 10,
            30,
        )

        return round(
            max(
                base - penalty,
                0.0,
            ),
            2,
        )

    def _calculate_prompt_score(
        self,
        report: PromptIntelligenceReport | None,
    ) -> float:
        if report is None:
            return 50.0

        if report.analyses_total <= 0:
            return 50.0

        return round(
            report.average_efficiency_score,
            2,
        )

    def _calculate_reliability_score(
        self,
        *,
        telemetry_summary: TelemetrySummary | None,
        health_report: RuntimeHealthReport | None,
    ) -> float:
        if telemetry_summary is None:
            if health_report is not None:
                return round(
                    health_report.success_rate,
                    2,
                )

            return 50.0

        score = telemetry_summary.success_rate

        score -= min(
            telemetry_summary.retry_count * 2,
            20,
        )

        score -= min(
            telemetry_summary.exhausted_events * 12,
            36,
        )

        score += min(
            telemetry_summary.recovered_events * 3,
            9,
        )

        return round(
            min(
                max(
                    score,
                    0.0,
                ),
                100.0,
            ),
            2,
        )

    def _calculate_cost_efficiency_score(
        self,
        report: ProjectCostReport | None,
    ) -> float:
        if report is None:
            return 50.0

        if report.status == CostStatus.UNKNOWN_PRICING:
            return 45.0

        if report.status == CostStatus.INVALID:
            return 30.0

        if report.status == CostStatus.PARTIAL:
            return 55.0

        if report.total_tokens <= 0:
            return 75.0

        cost_per_1k = (
            report.average_cost_per_1k_tokens
        )

        if cost_per_1k <= 0:
            return 100.0

        if cost_per_1k <= 0.003:
            return 95.0

        if cost_per_1k <= 0.006:
            return 85.0

        if cost_per_1k <= 0.012:
            return 70.0

        if cost_per_1k <= 0.025:
            return 50.0

        return 30.0

    def _calculate_optimization_potential_score(
        self,
        plan: OptimizationPlan | None,
    ) -> float:
        if plan is None:
            return 50.0

        if not plan.analyses:
            return 50.0

        return round(
            max(
                100.0 - plan.overall_score,
                0.0,
            ),
            2,
        )

    def _build_kpis(
        self,
        *,
        health_score: float,
        prompt_score: float,
        reliability_score: float,
        cost_efficiency_score: float,
        optimization_potential_score: float,
    ) -> list[ProjectKPI]:
        return [
            ProjectKPI(
                kpi_id="health",
                name="Health Score",
                value=health_score,
                weight=1.5,
            ),
            ProjectKPI(
                kpi_id="prompt_efficiency",
                name="Prompt Efficiency Score",
                value=prompt_score,
                weight=1.2,
            ),
            ProjectKPI(
                kpi_id="reliability",
                name="Reliability Score",
                value=reliability_score,
                weight=1.5,
            ),
            ProjectKPI(
                kpi_id="cost_efficiency",
                name="Cost Efficiency Score",
                value=cost_efficiency_score,
                weight=1.0,
            ),
            ProjectKPI(
                kpi_id="optimization_potential",
                name="Optimization Potential",
                value=optimization_potential_score,
                weight=0.8,
                message=(
                    "Un valor alto indica mayor margen "
                    "de mejora."
                ),
                metadata={
                    "inverse_metric": True,
                },
            ),
        ]

    # --------------------------------------------------
    # Findings
    # --------------------------------------------------

    def _build_findings(
        self,
        *,
        telemetry_summary: TelemetrySummary | None,
        health_report: RuntimeHealthReport | None,
        prompt_report: PromptIntelligenceReport | None,
        cost_report: ProjectCostReport | None,
        optimization_plan: OptimizationPlan | None,
    ) -> list[ExecutiveFinding]:
        findings: list[
            ExecutiveFinding
        ] = []

        if (
            health_report is not None
            and health_report.status
            == HealthStatus.UNHEALTHY
        ):
            findings.append(
                ExecutiveFinding(
                    finding_id=self._new_finding_id(),
                    title="Runtime no saludable",
                    description=(
                        "El monitor de salud clasificó "
                        "el proyecto como UNHEALTHY."
                    ),
                    finding_type=(
                        FindingType.CRITICAL_RISK
                    ),
                    priority="CRITICAL",
                    impact_score=95,
                    confidence_score=95,
                    evidence=[
                        (
                            "success_rate="
                            f"{health_report.success_rate}%"
                        ),
                        (
                            "exhausted_events="
                            f"{health_report.exhausted_events}"
                        ),
                    ],
                    recommendation=(
                        "Resolver fallos y agotamiento "
                        "de Retry antes de escalar."
                    ),
                    related_kpis=[
                        "health",
                        "reliability",
                    ],
                )
            )

        elif (
            health_report is not None
            and health_report.status
            == HealthStatus.DEGRADED
        ):
            findings.append(
                ExecutiveFinding(
                    finding_id=self._new_finding_id(),
                    title="Runtime degradado",
                    description=(
                        "El proyecto funciona, pero presenta "
                        "indicadores operativos degradados."
                    ),
                    finding_type=FindingType.RISK,
                    priority="HIGH",
                    impact_score=70,
                    confidence_score=90,
                    evidence=[
                        (
                            "health_status="
                            f"{health_report.status.value}"
                        )
                    ],
                    recommendation=(
                        "Revisar latencia, Retry y errores."
                    ),
                    related_kpis=[
                        "health",
                        "reliability",
                    ],
                )
            )

        if (
            prompt_report is not None
            and prompt_report.status
            == PromptEfficiencyStatus.CRITICAL
        ):
            worst_analysis = self._worst_prompt_analysis(
                prompt_report
            )

            findings.append(
                ExecutiveFinding(
                    finding_id=self._new_finding_id(),
                    title="Prompt Intelligence crítico",
                    description=(
                        "Al menos un Stage presenta "
                        "ineficiencia crítica de prompt."
                    ),
                    finding_type=FindingType.CRITICAL_RISK,
                    priority="CRITICAL",
                    stage=(
                        worst_analysis.stage
                        if worst_analysis is not None
                        else ""
                    ),
                    impact_score=90,
                    confidence_score=94,
                    evidence=[
                        (
                            "average_efficiency_score="
                            f"{prompt_report.average_efficiency_score}"
                        ),
                        (
                            "critical_analyses="
                            f"{prompt_report.critical_analyses}"
                        ),
                    ],
                    recommendation=(
                        "Reducir longitud, redundancia "
                        "y relación entrada/salida."
                    ),
                    related_kpis=[
                        "prompt_efficiency",
                        "cost_efficiency",
                    ],
                )
            )

        if (
            cost_report is not None
            and cost_report.unknown_pricing_analyses > 0
        ):
            findings.append(
                ExecutiveFinding(
                    finding_id=self._new_finding_id(),
                    title="Cobertura de costos incompleta",
                    description=(
                        "Existen ejecuciones sin precios "
                        "conocidos."
                    ),
                    finding_type=FindingType.RISK,
                    priority="HIGH",
                    impact_score=60,
                    confidence_score=100,
                    evidence=[
                        (
                            "unknown_pricing_analyses="
                            f"{cost_report.unknown_pricing_analyses}"
                        )
                    ],
                    recommendation=(
                        "Actualizar provider_pricing.yaml."
                    ),
                    related_kpis=[
                        "cost_efficiency",
                    ],
                )
            )

        if (
            telemetry_summary is not None
            and telemetry_summary.success_rate >= 95
            and telemetry_summary.exhausted_events == 0
        ):
            findings.append(
                ExecutiveFinding(
                    finding_id=self._new_finding_id(),
                    title="Alta confiabilidad operativa",
                    description=(
                        "La mayoría de ejecuciones finaliza "
                        "correctamente y sin agotamiento."
                    ),
                    finding_type=FindingType.STRENGTH,
                    priority="LOW",
                    impact_score=80,
                    confidence_score=95,
                    evidence=[
                        (
                            "success_rate="
                            f"{telemetry_summary.success_rate}%"
                        )
                    ],
                    related_kpis=[
                        "reliability",
                    ],
                )
            )

        if (
            optimization_plan is not None
            and optimization_plan.actionable_recommendations_total > 0
        ):
            findings.append(
                ExecutiveFinding(
                    finding_id=self._new_finding_id(),
                    title="Margen de optimización identificado",
                    description=(
                        "El Runtime Optimizer generó "
                        "recomendaciones accionables."
                    ),
                    finding_type=FindingType.OPPORTUNITY,
                    priority=(
                        optimization_plan.priority.value
                        if optimization_plan.priority
                        != OptimizationPriority.UNKNOWN
                        else "MEDIUM"
                    ),
                    impact_score=min(
                        (
                            optimization_plan
                            .actionable_recommendations_total
                            * 8
                        ),
                        100,
                    ),
                    confidence_score=85,
                    evidence=[
                        (
                            "actionable_recommendations="
                            f"{optimization_plan.actionable_recommendations_total}"
                        ),
                        (
                            "estimated_savings="
                            f"{optimization_plan.estimated_total_savings}"
                        ),
                    ],
                    recommendation=(
                        "Aplicar primero las acciones "
                        "CRITICAL y HIGH."
                    ),
                    related_kpis=[
                        "optimization_potential",
                    ],
                )
            )

        return self._deduplicate_findings(
            findings
        )

    def _build_recommendations(
        self,
        plan: OptimizationPlan | None,
    ) -> list[IntelligenceRecommendation]:
        if plan is None:
            return []

        recommendations: list[
            IntelligenceRecommendation
        ] = []

        for analysis in plan.analyses:
            for recommendation in analysis.recommendations:
                recommendations.append(
                    IntelligenceRecommendation(
                        recommendation_id=(
                            recommendation.recommendation_id
                        ),
                        title=recommendation.title,
                        description=(
                            recommendation.description
                        ),
                        priority=(
                            recommendation.priority.value
                        ),
                        action_type=(
                            recommendation.action_type.value
                        ),
                        stage=recommendation.stage,
                        source="runtime_optimizer",
                        confidence_score=(
                            recommendation.confidence_score
                        ),
                        expected_improvement_percent=(
                            recommendation
                            .expected_improvement_percent
                        ),
                        estimated_savings=(
                            recommendation.estimated_savings
                        ),
                        currency=(
                            recommendation.currency
                        ),
                        actionable=(
                            recommendation.is_actionable()
                        ),
                        safe_for_automatic_apply=(
                            recommendation
                            .is_safe_for_automatic_apply()
                        ),
                        evidence=list(
                            recommendation.evidence
                        ),
                        metadata={
                            "component": (
                                recommendation.component
                            ),
                            "provider": (
                                recommendation.provider
                            ),
                            "model": recommendation.model,
                        },
                    )
                )

        return self._deduplicate_recommendations(
            recommendations
        )

    # --------------------------------------------------
    # Summary
    # --------------------------------------------------

    def _build_executive_summary(
        self,
        report: ProjectIntelligenceReport,
    ) -> str:
        status_text = {
            IntelligenceStatus.EXCELLENT: (
                "presenta un desempeño excelente"
            ),
            IntelligenceStatus.GOOD: (
                "presenta un desempeño general sólido"
            ),
            IntelligenceStatus.ATTENTION: (
                "requiere atención en áreas específicas"
            ),
            IntelligenceStatus.CRITICAL: (
                "presenta riesgos críticos que deben "
                "resolverse"
            ),
            IntelligenceStatus.UNKNOWN: (
                "no dispone de información suficiente"
            ),
        }[
            report.status
        ]

        top_risk = (
            report.risks[0]
            if report.risks
            else ""
        )

        top_opportunity = (
            report.opportunities[0]
            if report.opportunities
            else ""
        )

        parts = [
            (
                f"El proyecto {report.project_id} "
                f"{status_text}, con un AI Project Score "
                f"de {report.ai_project_score}/100."
            )
        ]

        parts.append(
            (
                f"La confiabilidad operativa es "
                f"{report.reliability_score}/100, "
                f"la eficiencia de prompts es "
                f"{report.prompt_efficiency_score}/100 "
                f"y la eficiencia de costos es "
                f"{report.cost_efficiency_score}/100."
            )
        )

        if top_risk:
            parts.append(
                f"Riesgo principal: {top_risk}."
            )

        if top_opportunity:
            parts.append(
                f"Oportunidad principal: {top_opportunity}."
            )

        if report.recommendations:
            parts.append(
                (
                    f"Se identificaron "
                    f"{len(report.recommendations)} "
                    "recomendaciones, priorizando las "
                    "acciones CRITICAL y HIGH."
                )
            )

        return " ".join(
            parts
        )

    def _build_strengths(
        self,
        *,
        telemetry_summary: TelemetrySummary | None,
        health_report: RuntimeHealthReport | None,
        prompt_report: PromptIntelligenceReport | None,
        cost_report: ProjectCostReport | None,
    ) -> list[str]:
        strengths: list[str] = []

        if (
            telemetry_summary is not None
            and telemetry_summary.success_rate >= 90
        ):
            strengths.append(
                "Alta tasa de éxito operativo."
            )

        if (
            health_report is not None
            and health_report.status
            == HealthStatus.HEALTHY
        ):
            strengths.append(
                "Runtime en estado HEALTHY."
            )

        if (
            prompt_report is not None
            and prompt_report.status
            == PromptEfficiencyStatus.EFFICIENT
        ):
            strengths.append(
                "Prompts clasificados como eficientes."
            )

        if (
            cost_report is not None
            and cost_report.status
            in {
                CostStatus.CALCULATED,
                CostStatus.FREE_TIER,
            }
        ):
            strengths.append(
                "Costos calculados con cobertura conocida."
            )

        return unique_strings(
            strengths
        )

    def _build_risks(
        self,
        findings: list[ExecutiveFinding],
    ) -> list[str]:
        return unique_strings(
            [
                finding.title
                for finding in findings
                if finding.finding_type
                in {
                    FindingType.RISK,
                    FindingType.CRITICAL_RISK,
                }
            ]
        )

    def _build_opportunities(
        self,
        recommendations: list[
            IntelligenceRecommendation
        ],
    ) -> list[str]:
        return unique_strings(
            [
                recommendation.title
                for recommendation in recommendations
                if recommendation.actionable
            ]
        )

    def _build_warnings(
        self,
        *,
        telemetry_summary: TelemetrySummary | None,
        health_report: RuntimeHealthReport | None,
        prompt_report: PromptIntelligenceReport | None,
        cost_report: ProjectCostReport | None,
        optimization_plan: OptimizationPlan | None,
    ) -> list[str]:
        warnings: list[str] = []

        if telemetry_summary is None:
            warnings.append(
                "TelemetrySummary no disponible."
            )

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

    # --------------------------------------------------
    # Data extraction
    # --------------------------------------------------

    def _telemetry_data(
        self,
        summary: TelemetrySummary | None,
    ) -> dict[str, Any]:
        if summary is None:
            return {
                "events_total": 0,
                "successful_events": 0,
                "failed_events": 0,
                "success_rate": 0.0,
                "duration_seconds": 0.0,
                "average_duration_seconds": 0.0,
                "total_tokens": 0,
                "retry_count": 0,
                "exhausted_events": 0,
                "recovered_events": 0,
                "estimated_cost": 0.0,
                "currency": "USD",
            }

        return {
            "events_total": summary.events_total,
            "successful_events": (
                summary.successful_events
            ),
            "failed_events": summary.failed_events,
            "success_rate": summary.success_rate,
            "duration_seconds": (
                summary.duration_seconds
            ),
            "average_duration_seconds": (
                summary.average_duration_seconds
            ),
            "total_tokens": summary.total_tokens,
            "retry_count": summary.retry_count,
            "exhausted_events": (
                summary.exhausted_events
            ),
            "recovered_events": (
                summary.recovered_events
            ),
            "estimated_cost": (
                summary.estimated_cost
            ),
            "currency": summary.currency,
        }

    def _infer_project_id(
        self,
        *,
        resolved_path: Path,
        telemetry_summary: TelemetrySummary | None,
        health_report: RuntimeHealthReport | None,
        prompt_report: PromptIntelligenceReport | None,
        cost_report: ProjectCostReport | None,
        optimization_plan: OptimizationPlan | None,
    ) -> str:
        candidates = [
            getattr(
                telemetry_summary,
                "scope_id",
                "",
            ),
            getattr(
                health_report,
                "project_id",
                "",
            ),
            getattr(
                prompt_report,
                "project_id",
                "",
            ),
            getattr(
                cost_report,
                "project_id",
                "",
            ),
            getattr(
                optimization_plan,
                "project_id",
                "",
            ),
        ]

        for candidate in candidates:
            if str(
                candidate or ""
            ).strip():
                return str(
                    candidate
                ).strip()

        return resolved_path.name

    def _collect_stages(
        self,
        *,
        health_report: RuntimeHealthReport | None,
        prompt_report: PromptIntelligenceReport | None,
        cost_report: ProjectCostReport | None,
        optimization_plan: OptimizationPlan | None,
    ) -> list[str]:
        values: list[str] = []

        if health_report is not None:
            for component in health_report.components:
                if component.category == "stage":
                    value = component.component

                    if value.startswith(
                        "stage:"
                    ):
                        value = value.split(
                            ":",
                            1,
                        )[1]

                    values.append(
                        value
                    )

        if prompt_report is not None:
            values.extend(
                analysis.stage
                for analysis in prompt_report.analyses
            )

        if cost_report is not None:
            values.extend(
                analysis.stage
                for analysis in cost_report.analyses
            )

        if optimization_plan is not None:
            values.extend(
                analysis.stage
                for analysis in optimization_plan.analyses
            )

        return unique_strings(
            values
        )

    def _collect_providers(
        self,
        *,
        telemetry_summary: TelemetrySummary | None,
        prompt_report: PromptIntelligenceReport | None,
        cost_report: ProjectCostReport | None,
    ) -> list[str]:
        values: list[str] = []

        if telemetry_summary is not None:
            values.extend(
                telemetry_summary.providers
            )

        if prompt_report is not None:
            values.extend(
                analysis.provider
                for analysis in prompt_report.analyses
            )

        if cost_report is not None:
            values.extend(
                cost_report.providers
            )

        return unique_strings(
            values
        )

    def _collect_models(
        self,
        *,
        telemetry_summary: TelemetrySummary | None,
        prompt_report: PromptIntelligenceReport | None,
        cost_report: ProjectCostReport | None,
    ) -> list[str]:
        values: list[str] = []

        if telemetry_summary is not None:
            values.extend(
                telemetry_summary.models
            )

        if prompt_report is not None:
            values.extend(
                analysis.model
                for analysis in prompt_report.analyses
            )

        if cost_report is not None:
            values.extend(
                cost_report.models
            )

        return unique_strings(
            values
        )

    def _worst_prompt_analysis(
        self,
        report: PromptIntelligenceReport,
    ):
        if not report.analyses:
            return None

        return min(
            report.analyses,
            key=lambda analysis: (
                analysis.efficiency_score
            ),
        )

    # --------------------------------------------------
    # Utilities
    # --------------------------------------------------

    def _deduplicate_findings(
        self,
        findings: list[ExecutiveFinding],
    ) -> list[ExecutiveFinding]:
        seen: set[
            tuple[str, str]
        ] = set()

        result: list[
            ExecutiveFinding
        ] = []

        for finding in findings:
            key = (
                finding.title,
                finding.stage,
            )

            if key in seen:
                continue

            seen.add(
                key
            )

            result.append(
                finding
            )

        return result

    def _deduplicate_recommendations(
        self,
        recommendations: list[
            IntelligenceRecommendation
        ],
    ) -> list[IntelligenceRecommendation]:
        seen: set[str] = set()

        result: list[
            IntelligenceRecommendation
        ] = []

        for recommendation in recommendations:
            key = (
                recommendation.recommendation_id
                or (
                    recommendation.action_type
                    + ":"
                    + recommendation.stage
                )
            )

            if key in seen:
                continue

            seen.add(
                key
            )

            result.append(
                recommendation
            )

        return result

    def _priority_rank(
        self,
        priority: str,
    ) -> int:
        return {
            "LOW": 1,
            "MEDIUM": 2,
            "HIGH": 3,
            "CRITICAL": 4,
        }.get(
            str(
                priority or ""
            ).upper(),
            0,
        )

    def _markdown_list(
        self,
        values: list[str],
        empty_message: str,
    ) -> list[str]:
        if not values:
            return [
                empty_message
            ]

        return [
            f"- {value}"
            for value in values
        ]

    def _new_report_id(
        self,
    ) -> str:
        return (
            "PROJECT-INTELLIGENCE-"
            + uuid4().hex.upper()
        )

    def _new_finding_id(
        self,
    ) -> str:
        return (
            "FINDING-"
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