"""
=========================================================
Proyecto : CIPS
Release  : 0.9
Build    : 077
Archivo  : runtime_optimizer_smoke_test.py
Estado   : RELEASE
=========================================================

Prueba integral del Adaptive Runtime Optimizer.

Escenarios:
1. Stage saludable sin cambios.
2. Prompt largo y baja eficiencia.
3. Thinking tokens elevados.
4. Latencia crítica.
5. Retry agotado con HTTP 429.
6. Caché candidata.
7. Costo elevado y cambio de modelo.
8. Integración de Health, Prompt y Cost.
9. Consolidación de OptimizationPlan.
10. Serialización, prioridad y orden de ejecución.

La prueba:
- no llama a Gemini;
- no requiere API Key;
- no modifica proyectos existentes;
- no aplica cambios de configuración;
- usa únicamente modelos y datos simulados.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
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
    OptimizationPlan,
    OptimizationPriority,
    OptimizationStatus,
    StageOptimizationAnalysis,
)
from prompt_intelligence_models import (
    PromptAnalysis,
    PromptEfficiencyStatus,
    PromptIntelligenceReport,
    PromptMetric,
)
from runtime_optimizer import RuntimeOptimizer
from telemetry_models import (
    TelemetryAttempt,
    TelemetryEvent,
)


@dataclass
class ScenarioResult:
    """
    Resultado de un escenario individual.
    """

    name: str
    passed: bool

    errors: list[str] = field(
        default_factory=list
    )

    metadata: dict[str, Any] = field(
        default_factory=dict
    )


class RuntimeOptimizerSmokeTest:
    """
    Ejecuta la validación integral del Sprint 022C.
    """

    TEST_NAME = "CIPS Runtime Optimizer Smoke Test"

    def __init__(
        self,
    ) -> None:
        self.optimizer = RuntimeOptimizer()

        self.results: list[
            ScenarioResult
        ] = []

        self.generated_analyses: list[
            StageOptimizationAnalysis
        ] = []

    def run(
        self,
    ) -> bool:
        """
        Ejecuta todos los escenarios.
        """

        print(
            self.TEST_NAME
        )

        print(
            "=" * 70
        )

        print(
            "Esta prueba no llama a Gemini, "
            "no requiere credenciales y no aplica cambios."
        )

        scenarios: list[
            Callable[
                [],
                ScenarioResult,
            ]
        ] = [
            self._scenario_healthy_stage,
            self._scenario_long_prompt,
            self._scenario_high_thinking,
            self._scenario_critical_latency,
            self._scenario_retry_429,
            self._scenario_cache_candidate,
            self._scenario_expensive_stage,
            self._scenario_integrated_reports,
            self._scenario_plan_consolidation,
            self._scenario_serialization_order,
        ]

        for scenario in scenarios:
            result = scenario()

            self.results.append(
                result
            )

            self._print_scenario(
                result
            )

        return self._print_summary()

    # --------------------------------------------------
    # Escenarios
    # --------------------------------------------------

    def _scenario_healthy_stage(
        self,
    ) -> ScenarioResult:
        """
        Valida NO_ACTION para un Stage saludable.
        """

        event = TelemetryEvent(
            event_id="OPT-HEALTHY-001",
            timestamp="2026-07-16T02:00:00Z",
            project_id="OPTIMIZER_TEST",
            component="pipeline_engine",
            operation="execute_stage",
            stage="investigacion",
            success=True,
            provider="gemini",
            model="gemini-3.5-flash",
            duration_seconds=20,
            prompt_tokens=2_000,
            response_tokens=800,
            thinking_tokens=200,
            total_tokens=3_000,
            retry_count=0,
            retry_exhausted=False,
            metadata={
                "max_output_tokens": 2048,
                "timeout_seconds": 120,
                "max_attempts": 3,
            },
        )

        analysis = self.optimizer.analyze_stage(
            project_id="OPTIMIZER_TEST",
            stage="investigacion",
            telemetry_events=[
                event
            ],
        )

        self.generated_analyses.append(
            analysis
        )

        errors: list[str] = []

        action_types = self._action_types(
            analysis
        )

        if (
            OptimizationActionType.NO_ACTION.value
            not in action_types
        ):
            errors.append(
                "El Stage saludable debía producir NO_ACTION."
            )

        if analysis.priority != OptimizationPriority.LOW:
            errors.append(
                "La prioridad esperada era LOW."
            )

        if analysis.actionable_recommendations():
            errors.append(
                "NO_ACTION no debía ser accionable."
            )

        return ScenarioResult(
            name="Stage saludable sin cambios",
            passed=not errors,
            errors=errors,
            metadata={
                "score": analysis.optimization_score,
                "priority": analysis.priority.value,
                "action_types": action_types,
            },
        )

    def _scenario_long_prompt(
        self,
    ) -> ScenarioResult:
        """
        Valida reducción de prompt y salida.
        """

        event = TelemetryEvent(
            event_id="OPT-PROMPT-001",
            timestamp="2026-07-16T02:05:00Z",
            project_id="OPTIMIZER_TEST",
            component="pipeline_engine",
            operation="execute_stage",
            stage="storyboard",
            success=True,
            provider="gemini",
            model="gemini-3.5-flash",
            duration_seconds=55,
            prompt_tokens=18_000,
            response_tokens=700,
            thinking_tokens=300,
            total_tokens=19_000,
            metadata={
                "max_output_tokens": 8192,
            },
        )

        analysis = self.optimizer.analyze_stage(
            project_id="OPTIMIZER_TEST",
            stage="storyboard",
            telemetry_events=[
                event
            ],
        )

        self.generated_analyses.append(
            analysis
        )

        action_types = self._action_types(
            analysis
        )

        errors: list[str] = []

        for required in (
            OptimizationActionType.REDUCE_PROMPT.value,
            OptimizationActionType.REDUCE_MAX_OUTPUT_TOKENS.value,
            OptimizationActionType.ENABLE_CACHE.value,
        ):
            if required not in action_types:
                errors.append(
                    f"Falta recomendación {required}."
                )

        if analysis.priority != OptimizationPriority.CRITICAL:
            errors.append(
                "La prioridad esperada era CRITICAL."
            )

        return ScenarioResult(
            name="Prompt largo y baja eficiencia",
            passed=not errors,
            errors=errors,
            metadata={
                "score": analysis.optimization_score,
                "priority": analysis.priority.value,
                "action_types": action_types,
            },
        )

    def _scenario_high_thinking(
        self,
    ) -> ScenarioResult:
        """
        Valida ajuste de thinking level.
        """

        event = TelemetryEvent(
            event_id="OPT-THINKING-001",
            timestamp="2026-07-16T02:10:00Z",
            project_id="OPTIMIZER_TEST",
            component="pipeline_engine",
            operation="execute_stage",
            stage="verificacion",
            success=True,
            provider="gemini",
            model="gemini-3.5-flash",
            thinking_level="high",
            duration_seconds=35,
            prompt_tokens=4_000,
            response_tokens=600,
            thinking_tokens=1_500,
            total_tokens=6_100,
        )

        analysis = self.optimizer.analyze_stage(
            project_id="OPTIMIZER_TEST",
            stage="verificacion",
            telemetry_events=[
                event
            ],
        )

        self.generated_analyses.append(
            analysis
        )

        action_types = self._action_types(
            analysis
        )

        errors: list[str] = []

        if (
            OptimizationActionType.ADJUST_THINKING_LEVEL.value
            not in action_types
        ):
            errors.append(
                "Falta ADJUST_THINKING_LEVEL."
            )

        recommendation = self._find_recommendation(
            analysis,
            OptimizationActionType.ADJUST_THINKING_LEVEL,
        )

        if recommendation is None:
            errors.append(
                "No se encontró la recomendación de thinking."
            )

        elif not recommendation.adjustments:
            errors.append(
                "La recomendación debía incluir un ajuste."
            )

        elif (
            recommendation.adjustments[0].proposed_value
            != "low"
        ):
            errors.append(
                "thinking_level propuesto debía ser low."
            )

        return ScenarioResult(
            name="Thinking tokens elevados",
            passed=not errors,
            errors=errors,
            metadata={
                "priority": analysis.priority.value,
                "action_types": action_types,
            },
        )

    def _scenario_critical_latency(
        self,
    ) -> ScenarioResult:
        """
        Valida ajuste de timeout por latencia.
        """

        event = TelemetryEvent(
            event_id="OPT-LATENCY-001",
            timestamp="2026-07-16T02:15:00Z",
            project_id="OPTIMIZER_TEST",
            component="pipeline_engine",
            operation="execute_stage",
            stage="guion",
            success=True,
            provider="gemini",
            model="gemini-3.5-flash",
            duration_seconds=210,
            prompt_tokens=4_000,
            response_tokens=1_200,
            thinking_tokens=300,
            total_tokens=5_500,
            metadata={
                "timeout_seconds": 120,
            },
        )

        analysis = self.optimizer.analyze_stage(
            project_id="OPTIMIZER_TEST",
            stage="guion",
            telemetry_events=[
                event
            ],
        )

        self.generated_analyses.append(
            analysis
        )

        recommendation = self._find_recommendation(
            analysis,
            OptimizationActionType.ADJUST_TIMEOUT,
        )

        errors: list[str] = []

        if recommendation is None:
            errors.append(
                "Falta ADJUST_TIMEOUT."
            )

        elif recommendation.priority != OptimizationPriority.CRITICAL:
            errors.append(
                "ADJUST_TIMEOUT debía ser CRITICAL."
            )

        elif not recommendation.adjustments:
            errors.append(
                "ADJUST_TIMEOUT debía incluir ajuste."
            )

        elif (
            recommendation.adjustments[0].proposed_value
            <= recommendation.adjustments[0].current_value
        ):
            errors.append(
                "El timeout propuesto debía ser mayor."
            )

        return ScenarioResult(
            name="Latencia crítica",
            passed=not errors,
            errors=errors,
            metadata={
                "score": analysis.optimization_score,
                "priority": analysis.priority.value,
                "proposed_timeout": (
                    recommendation.adjustments[0].proposed_value
                    if (
                        recommendation is not None
                        and recommendation.adjustments
                    )
                    else None
                ),
            },
        )

    def _scenario_retry_429(
        self,
    ) -> ScenarioResult:
        """
        Valida Retry y proveedor alternativo.
        """

        attempts = [
            TelemetryAttempt(
                attempt_number=1,
                success=False,
                duration_seconds=2,
                delay_seconds=5,
                retryable=True,
                status_code=503,
            ),
            TelemetryAttempt(
                attempt_number=2,
                success=False,
                duration_seconds=1,
                delay_seconds=10,
                retryable=True,
                status_code=503,
            ),
            TelemetryAttempt(
                attempt_number=3,
                success=False,
                duration_seconds=1,
                delay_seconds=0,
                retryable=False,
                status_code=429,
            ),
        ]

        event = TelemetryEvent(
            event_id="OPT-RETRY-001",
            timestamp="2026-07-16T02:20:00Z",
            project_id="OPTIMIZER_TEST",
            component="pipeline_engine",
            operation="execute_stage",
            stage="publicacion",
            success=False,
            provider="gemini",
            model="gemini-3.5-flash",
            duration_seconds=40,
            prompt_tokens=5_000,
            response_tokens=0,
            thinking_tokens=0,
            total_tokens=5_000,
            retry_count=2,
            retry_exhausted=True,
            status_code=429,
            attempts=attempts,
            metadata={
                "max_attempts": 3,
            },
        )

        analysis = self.optimizer.analyze_stage(
            project_id="OPTIMIZER_TEST",
            stage="publicacion",
            telemetry_events=[
                event
            ],
        )

        self.generated_analyses.append(
            analysis
        )

        action_types = self._action_types(
            analysis
        )

        errors: list[str] = []

        for required in (
            OptimizationActionType.ADJUST_RETRY_POLICY.value,
            OptimizationActionType.CHANGE_PROVIDER.value,
        ):
            if required not in action_types:
                errors.append(
                    f"Falta recomendación {required}."
                )

        if analysis.priority != OptimizationPriority.CRITICAL:
            errors.append(
                "La prioridad esperada era CRITICAL."
            )

        return ScenarioResult(
            name="Retry agotado con HTTP 429",
            passed=not errors,
            errors=errors,
            metadata={
                "priority": analysis.priority.value,
                "retry_count": analysis.retry_count,
                "retry_exhausted": analysis.retry_exhausted,
                "action_types": action_types,
            },
        )

    def _scenario_cache_candidate(
        self,
    ) -> ScenarioResult:
        """
        Valida recomendación de caché.
        """

        event = TelemetryEvent(
            event_id="OPT-CACHE-001",
            timestamp="2026-07-16T02:25:00Z",
            project_id="OPTIMIZER_TEST",
            component="pipeline_engine",
            operation="execute_stage",
            stage="seo",
            success=True,
            provider="gemini",
            model="gemini-3.5-flash",
            duration_seconds=25,
            prompt_tokens=7_000,
            response_tokens=1_500,
            thinking_tokens=200,
            total_tokens=8_700,
            metadata={
                "cached_input_tokens": 0,
            },
        )

        analysis = self.optimizer.analyze_stage(
            project_id="OPTIMIZER_TEST",
            stage="seo",
            telemetry_events=[
                event
            ],
        )

        self.generated_analyses.append(
            analysis
        )

        recommendation = self._find_recommendation(
            analysis,
            OptimizationActionType.ENABLE_CACHE,
        )

        errors: list[str] = []

        if recommendation is None:
            errors.append(
                "Falta ENABLE_CACHE."
            )

        elif not recommendation.adjustments:
            errors.append(
                "ENABLE_CACHE debía incluir ajuste."
            )

        elif (
            recommendation.adjustments[0].proposed_value
            is not True
        ):
            errors.append(
                "context_cache_enabled propuesto debía ser True."
            )

        return ScenarioResult(
            name="Caché candidata",
            passed=not errors,
            errors=errors,
            metadata={
                "priority": analysis.priority.value,
                "cache_recommendation": (
                    recommendation is not None
                ),
            },
        )

    def _scenario_expensive_stage(
        self,
    ) -> ScenarioResult:
        """
        Valida cambio de modelo por costo.
        """

        cost_analysis = StageCostAnalysis(
            analysis_id="COST-OPT-001",
            project_id="OPTIMIZER_TEST",
            stage="storyboard",
            provider="gemini",
            model="gemini-3.5-flash",
            status=CostStatus.CALCULATED,
            token_usage=TokenUsageBreakdown(
                prompt_tokens=18_000,
                response_tokens=2_000,
                thinking_tokens=1_000,
                total_tokens=21_000,
            ),
            cost=CostBreakdown(
                status=CostStatus.CALCULATED,
                input_rate=2.7,
                output_rate=16.2,
                thinking_rate=16.2,
                input_cost=0.0486,
                output_cost=0.0324,
                thinking_cost=0.0162,
            ),
            duration_seconds=70,
        )

        cost_report = ProjectCostReport(
            report_id="COST-REPORT-OPT",
            generated_at="2026-07-16T02:30:00Z",
            project_id="OPTIMIZER_TEST",
            status=CostStatus.CALCULATED,
            analyses=[
                cost_analysis
            ],
        )

        analysis = self.optimizer.analyze_stage(
            project_id="OPTIMIZER_TEST",
            stage="storyboard",
            cost_report=cost_report,
        )

        self.generated_analyses.append(
            analysis
        )

        recommendation = self._find_recommendation(
            analysis,
            OptimizationActionType.CHANGE_MODEL,
        )

        errors: list[str] = []

        if recommendation is None:
            errors.append(
                "Falta CHANGE_MODEL."
            )

        elif recommendation.estimated_savings <= 0:
            errors.append(
                "El ahorro estimado debía ser mayor a 0."
            )

        if analysis.estimated_cost <= 0:
            errors.append(
                "estimated_cost debía propagarse."
            )

        return ScenarioResult(
            name="Costo elevado y cambio de modelo",
            passed=not errors,
            errors=errors,
            metadata={
                "estimated_cost": analysis.estimated_cost,
                "estimated_savings": (
                    recommendation.estimated_savings
                    if recommendation is not None
                    else 0.0
                ),
                "priority": analysis.priority.value,
            },
        )

    def _scenario_integrated_reports(
        self,
    ) -> ScenarioResult:
        """
        Valida correlación Health + Prompt + Cost.
        """

        prompt_analysis = PromptAnalysis(
            analysis_id="PROMPT-OPT-001",
            project_id="OPTIMIZER_TEST",
            stage="storyboard",
            status=PromptEfficiencyStatus.CRITICAL,
            provider="gemini",
            model="gemini-3.5-flash",
            prompt_tokens=18_000,
            response_tokens=600,
            thinking_tokens=1_200,
            total_tokens=19_800,
            duration_seconds=200,
            prompt_response_token_ratio=30.0,
            response_yield_percent=3.33,
            efficiency_score=25,
            metrics=[
                PromptMetric(
                    metric_id="prompt_length",
                    name="Longitud",
                    status=PromptEfficiencyStatus.CRITICAL,
                    value=18_000,
                    unit="tokens",
                    score=20,
                )
            ],
        )

        prompt_report = PromptIntelligenceReport(
            report_id="PROMPT-REPORT-OPT",
            generated_at="2026-07-16T02:35:00Z",
            project_id="OPTIMIZER_TEST",
            status=PromptEfficiencyStatus.CRITICAL,
            analyses=[
                prompt_analysis
            ],
        )

        health_component = ComponentHealth(
            component="stage:storyboard",
            status=HealthStatus.UNHEALTHY,
            category="stage",
            events_total=2,
            successful_events=1,
            failed_events=1,
            average_duration_seconds=120,
            maximum_duration_seconds=200,
        )

        health_report = RuntimeHealthReport(
            report_id="HEALTH-OPT-001",
            generated_at="2026-07-16T02:35:00Z",
            status=HealthStatus.UNHEALTHY,
            project_id="OPTIMIZER_TEST",
            scope="project",
            events_total=2,
            successful_events=1,
            failed_events=1,
            components=[
                health_component
            ],
        )

        cost_analysis = StageCostAnalysis(
            analysis_id="COST-OPT-002",
            project_id="OPTIMIZER_TEST",
            stage="storyboard",
            provider="gemini",
            model="gemini-3.5-flash",
            status=CostStatus.CALCULATED,
            token_usage=TokenUsageBreakdown(
                prompt_tokens=18_000,
                response_tokens=600,
                thinking_tokens=1_200,
                total_tokens=19_800,
            ),
            cost=CostBreakdown(
                status=CostStatus.CALCULATED,
                input_cost=0.0486,
                output_cost=0.00972,
                thinking_cost=0.01944,
                input_rate=2.7,
                output_rate=16.2,
                thinking_rate=16.2,
                cached_input_rate=0.27,
            ),
            duration_seconds=200,
            retry_count=2,
            retry_exhausted=True,
        )

        cost_report = ProjectCostReport(
            report_id="COST-REPORT-OPT-2",
            generated_at="2026-07-16T02:35:00Z",
            project_id="OPTIMIZER_TEST",
            status=CostStatus.CALCULATED,
            analyses=[
                cost_analysis
            ],
        )

        event = TelemetryEvent(
            event_id="OPT-INTEGRATED-001",
            timestamp="2026-07-16T02:35:00Z",
            project_id="OPTIMIZER_TEST",
            component="pipeline_engine",
            operation="execute_stage",
            stage="storyboard",
            success=False,
            provider="gemini",
            model="gemini-3.5-flash",
            duration_seconds=200,
            prompt_tokens=18_000,
            response_tokens=600,
            thinking_tokens=1_200,
            total_tokens=19_800,
            retry_count=2,
            retry_exhausted=True,
            status_code=503,
        )

        analysis = self.optimizer.analyze_stage(
            project_id="OPTIMIZER_TEST",
            stage="storyboard",
            telemetry_events=[
                event
            ],
            health_report=health_report,
            prompt_report=prompt_report,
            cost_report=cost_report,
        )

        self.generated_analyses.append(
            analysis
        )

        action_types = self._action_types(
            analysis
        )

        errors: list[str] = []

        if analysis.health_status != "UNHEALTHY":
            errors.append(
                "health_status debía ser UNHEALTHY."
            )

        if analysis.prompt_status != "CRITICAL":
            errors.append(
                "prompt_status debía ser CRITICAL."
            )

        if analysis.cost_status != "CALCULATED":
            errors.append(
                "cost_status debía ser CALCULATED."
            )

        if (
            OptimizationActionType.SPLIT_STAGE.value
            not in action_types
        ):
            errors.append(
                "Falta SPLIT_STAGE."
            )

        if analysis.optimization_score != 0.0:
            errors.append(
                "El score integrado esperado era 0.0."
            )

        return ScenarioResult(
            name="Integración Health, Prompt y Cost",
            passed=not errors,
            errors=errors,
            metadata={
                "score": analysis.optimization_score,
                "priority": analysis.priority.value,
                "health_status": analysis.health_status,
                "prompt_status": analysis.prompt_status,
                "cost_status": analysis.cost_status,
                "action_types": action_types,
            },
        )

    def _scenario_plan_consolidation(
        self,
    ) -> ScenarioResult:
        """
        Valida acumulados del plan.
        """

        plan = OptimizationPlan(
            plan_id="OPT-PLAN-SMOKE",
            generated_at="2026-07-16T02:40:00Z",
            project_id="OPTIMIZER_TEST",
            status=OptimizationStatus.PROPOSED,
            analyses=list(
                self.generated_analyses
            ),
        )

        errors: list[str] = []

        if (
            len(
                plan.analyses
            )
            != len(
                self.generated_analyses
            )
        ):
            errors.append(
                "La cantidad de análisis es incorrecta."
            )

        if plan.recommendations_total <= 0:
            errors.append(
                "recommendations_total debía ser mayor a 0."
            )

        if plan.actionable_recommendations_total <= 0:
            errors.append(
                "Debían existir recomendaciones accionables."
            )

        if plan.priority != OptimizationPriority.CRITICAL:
            errors.append(
                "La prioridad global esperada era CRITICAL."
            )

        if not plan.recommended_execution_order:
            errors.append(
                "Falta recommended_execution_order."
            )

        return ScenarioResult(
            name="Consolidación de OptimizationPlan",
            passed=not errors,
            errors=errors,
            metadata={
                "analyses": len(
                    plan.analyses
                ),
                "overall_score": plan.overall_score,
                "priority": plan.priority.value,
                "recommendations_total": (
                    plan.recommendations_total
                ),
                "actionable_total": (
                    plan.actionable_recommendations_total
                ),
                "automatic_total": (
                    plan.automatic_recommendations_total
                ),
            },
        )

    def _scenario_serialization_order(
        self,
    ) -> ScenarioResult:
        """
        Valida serialización y prioridad del orden.
        """

        plan = OptimizationPlan(
            plan_id="OPT-PLAN-SERIALIZATION",
            generated_at="2026-07-16T02:45:00Z",
            project_id="OPTIMIZER_TEST",
            analyses=list(
                self.generated_analyses
            ),
        )

        payload = plan.to_dict()

        serialized = json.dumps(
            payload,
            ensure_ascii=False,
        )

        errors: list[str] = []

        if not serialized:
            errors.append(
                "La serialización quedó vacía."
            )

        if payload.get(
            "priority"
        ) != "CRITICAL":
            errors.append(
                "La prioridad serializada debía ser CRITICAL."
            )

        order = payload.get(
            "recommended_execution_order",
            [],
        )

        if not order:
            errors.append(
                "El orden de ejecución quedó vacío."
            )

        first_recommendation = self._find_recommendation_by_id(
            plan,
            order[0] if order else "",
        )

        if (
            first_recommendation is not None
            and first_recommendation.priority
            != OptimizationPriority.CRITICAL
        ):
            errors.append(
                "La primera recomendación debía ser CRITICAL."
            )

        return ScenarioResult(
            name="Serialización y orden de ejecución",
            passed=not errors,
            errors=errors,
            metadata={
                "serialized_characters": len(
                    serialized
                ),
                "priority": payload.get(
                    "priority"
                ),
                "execution_order_items": len(
                    order
                ),
                "first_priority": (
                    first_recommendation.priority.value
                    if first_recommendation is not None
                    else ""
                ),
            },
        )

    # --------------------------------------------------
    # Utilidades
    # --------------------------------------------------

    def _action_types(
        self,
        analysis: StageOptimizationAnalysis,
    ) -> list[str]:
        """
        Devuelve tipos de acción.
        """

        return [
            recommendation.action_type.value
            for recommendation
            in analysis.recommendations
        ]

    def _find_recommendation(
        self,
        analysis: StageOptimizationAnalysis,
        action_type: OptimizationActionType,
    ):
        """
        Busca recomendación por tipo.
        """

        for recommendation in analysis.recommendations:
            if recommendation.action_type == action_type:
                return recommendation

        return None

    def _find_recommendation_by_id(
        self,
        plan: OptimizationPlan,
        recommendation_id: str,
    ):
        """
        Busca recomendación por ID.
        """

        for analysis in plan.analyses:
            for recommendation in analysis.recommendations:
                if (
                    recommendation.recommendation_id
                    == recommendation_id
                ):
                    return recommendation

        return None

    # --------------------------------------------------
    # Impresión
    # --------------------------------------------------

    def _print_scenario(
        self,
        result: ScenarioResult,
    ) -> None:
        """
        Imprime un escenario.
        """

        print()

        print(
            "-" * 70
        )

        print(
            f"Escenario: {result.name}"
        )

        print(
            "-" * 70
        )

        print(
            "Resultado: "
            + (
                "OK"
                if result.passed
                else "ERROR"
            )
        )

        if result.metadata:
            print(
                "Datos:"
            )

            for key, value in (
                result.metadata.items()
            ):
                if isinstance(
                    value,
                    (
                        list,
                        dict,
                    ),
                ):
                    print(
                        f"  {key}: "
                        f"{json.dumps(value, ensure_ascii=False)}"
                    )

                else:
                    print(
                        f"  {key}: {value}"
                    )

        if result.errors:
            print(
                "Errores:"
            )

            for error in result.errors:
                print(
                    f"- {error}"
                )

    def _print_summary(
        self,
    ) -> bool:
        """
        Imprime resumen final.
        """

        passed = sum(
            1
            for result in self.results
            if result.passed
        )

        failed = (
            len(
                self.results
            )
            - passed
        )

        overall_valid = (
            failed == 0
        )

        print()

        print(
            "=" * 70
        )

        print(
            "RESUMEN RUNTIME OPTIMIZER"
        )

        print(
            "=" * 70
        )

        print(
            f"Escenarios ejecutados: "
            f"{len(self.results)}"
        )

        print(
            f"Escenarios aprobados: "
            f"{passed}"
        )

        print(
            f"Escenarios fallidos: "
            f"{failed}"
        )

        print(
            f"Resultado integral válido: "
            f"{overall_valid}"
        )

        if overall_valid:
            print()

            print(
                "Runtime Optimizer Smoke Test "
                "completado correctamente."
            )

        return overall_valid


def main(
) -> int:
    """
    Punto de entrada.
    """

    test = RuntimeOptimizerSmokeTest()

    return (
        0
        if test.run()
        else 1
    )


if __name__ == "__main__":
    sys.exit(
        main()
    )