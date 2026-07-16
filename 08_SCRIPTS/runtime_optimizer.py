"""
=========================================================
Proyecto : CIPS
Release  : 0.9
Build    : 076
Archivo  : runtime_optimizer.py
Estado   : RELEASE
=========================================================

Genera planes de optimización adaptativa combinando:
- RuntimeHealthReport;
- PromptIntelligenceReport;
- ProjectCostReport;
- TelemetryEvent.

Responsabilidades:
- correlacionar métricas por Stage;
- calcular optimization_score;
- priorizar problemas;
- generar recomendaciones accionables;
- proponer ajustes seguros;
- estimar mejoras y ahorros;
- construir OptimizationPlan.

Este componente NO:
- modifica archivos de configuración;
- aplica cambios automáticamente;
- llama proveedores;
- ejecuta el Pipeline;
- escribe reportes;
- altera proyectos.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Iterable
from uuid import uuid4

from cost_models import (
    ProjectCostReport,
    StageCostAnalysis,
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
from prompt_intelligence_models import (
    PromptAnalysis,
    PromptEfficiencyStatus,
    PromptIntelligenceReport,
)
from telemetry_models import TelemetryEvent


class RuntimeOptimizer:
    """
    Motor de recomendaciones del Adaptive Runtime Optimizer.
    """

    COMPONENT_NAME = "runtime_optimizer"
    VERSION = "0.9"

    def __init__(
        self,
        long_duration_seconds: float = 60.0,
        critical_duration_seconds: float = 180.0,
        high_prompt_tokens: int = 8_000,
        critical_prompt_tokens: int = 16_000,
        high_retry_count: int = 1,
        critical_retry_count: int = 2,
        low_response_yield_percent: float = 10.0,
        critical_response_yield_percent: float = 5.0,
        high_prompt_ratio: float = 8.0,
        critical_prompt_ratio: float = 12.0,
        cache_candidate_prompt_tokens: int = 6_000,
        expensive_stage_cost: float = 0.05,
    ) -> None:
        self.long_duration_seconds = self._non_negative_float(
            long_duration_seconds,
            60.0,
        )
        self.critical_duration_seconds = self._non_negative_float(
            critical_duration_seconds,
            180.0,
        )
        self.high_prompt_tokens = self._positive_int(
            high_prompt_tokens,
            8_000,
        )
        self.critical_prompt_tokens = self._positive_int(
            critical_prompt_tokens,
            16_000,
        )
        self.high_retry_count = self._positive_int(
            high_retry_count,
            1,
        )
        self.critical_retry_count = self._positive_int(
            critical_retry_count,
            2,
        )
        self.low_response_yield_percent = self._percent(
            low_response_yield_percent,
            10.0,
        )
        self.critical_response_yield_percent = self._percent(
            critical_response_yield_percent,
            5.0,
        )
        self.high_prompt_ratio = self._non_negative_float(
            high_prompt_ratio,
            8.0,
        )
        self.critical_prompt_ratio = self._non_negative_float(
            critical_prompt_ratio,
            12.0,
        )
        self.cache_candidate_prompt_tokens = self._positive_int(
            cache_candidate_prompt_tokens,
            6_000,
        )
        self.expensive_stage_cost = self._non_negative_float(
            expensive_stage_cost,
            0.05,
        )

    # --------------------------------------------------
    # API pública
    # --------------------------------------------------

    def optimize(
        self,
        *,
        project_id: str = "",
        telemetry_events: Iterable[
            TelemetryEvent | dict[str, Any]
        ] | None = None,
        health_report: RuntimeHealthReport | None = None,
        prompt_report: PromptIntelligenceReport | None = None,
        cost_report: ProjectCostReport | None = None,
    ) -> OptimizationPlan:
        """
        Construye un plan consolidado de optimización.
        """

        events = self._normalize_events(
            telemetry_events or []
        )

        resolved_project_id = str(
            project_id
            or self._infer_project_id(
                events=events,
                health_report=health_report,
                prompt_report=prompt_report,
                cost_report=cost_report,
            )
            or ""
        ).strip()

        stage_names = self._collect_stage_names(
            events=events,
            health_report=health_report,
            prompt_report=prompt_report,
            cost_report=cost_report,
        )

        plan = OptimizationPlan(
            plan_id=self._new_plan_id(),
            generated_at=self._utc_now(),
            project_id=resolved_project_id,
            status=OptimizationStatus.PROPOSED,
            metadata={
                "component": self.COMPONENT_NAME,
                "version": self.VERSION,
                "stages_detected": len(stage_names),
                "telemetry_events": len(events),
                "health_report_available": (
                    health_report is not None
                ),
                "prompt_report_available": (
                    prompt_report is not None
                ),
                "cost_report_available": (
                    cost_report is not None
                ),
                "thresholds": self.get_thresholds(),
            },
        )

        if not stage_names:
            plan.warnings.append(
                "No existen Stages suficientes para generar "
                "un plan de optimización."
            )
            return plan

        for stage in stage_names:
            analysis = self.analyze_stage(
                project_id=resolved_project_id,
                stage=stage,
                telemetry_events=events,
                health_report=health_report,
                prompt_report=prompt_report,
                cost_report=cost_report,
            )
            plan.add_analysis(
                analysis
            )

        self._add_global_recommendations(
            plan=plan,
            health_report=health_report,
            prompt_report=prompt_report,
            cost_report=cost_report,
        )

        plan.warnings = self._unique_strings(
            plan.warnings
        )
        plan.errors = self._unique_strings(
            plan.errors
        )

        return plan

    def analyze_stage(
        self,
        *,
        project_id: str,
        stage: str,
        telemetry_events: Iterable[
            TelemetryEvent | dict[str, Any]
        ] | None = None,
        health_report: RuntimeHealthReport | None = None,
        prompt_report: PromptIntelligenceReport | None = None,
        cost_report: ProjectCostReport | None = None,
    ) -> StageOptimizationAnalysis:
        """
        Analiza un Stage y genera recomendaciones.
        """

        normalized_stage = str(
            stage or ""
        ).strip().lower()

        events = [
            event
            for event in self._normalize_events(
                telemetry_events or []
            )
            if event.stage == normalized_stage
        ]

        prompt_analysis = self._find_prompt_analysis(
            prompt_report,
            normalized_stage,
        )

        cost_analysis = self._find_cost_analysis(
            cost_report,
            normalized_stage,
        )

        health_component = self._find_stage_health(
            health_report,
            normalized_stage,
        )

        duration_seconds = self._resolve_duration(
            events=events,
            prompt_analysis=prompt_analysis,
            cost_analysis=cost_analysis,
            health_component=health_component,
        )

        prompt_tokens = self._resolve_int_metric(
            events=events,
            prompt_analysis=prompt_analysis,
            cost_analysis=cost_analysis,
            event_attribute="prompt_tokens",
            prompt_attribute="prompt_tokens",
            cost_attribute="prompt_tokens",
        )

        response_tokens = self._resolve_int_metric(
            events=events,
            prompt_analysis=prompt_analysis,
            cost_analysis=cost_analysis,
            event_attribute="response_tokens",
            prompt_attribute="response_tokens",
            cost_attribute="response_tokens",
        )

        thinking_tokens = self._resolve_int_metric(
            events=events,
            prompt_analysis=prompt_analysis,
            cost_analysis=cost_analysis,
            event_attribute="thinking_tokens",
            prompt_attribute="thinking_tokens",
            cost_attribute="thinking_tokens",
        )

        total_tokens = self._resolve_int_metric(
            events=events,
            prompt_analysis=prompt_analysis,
            cost_analysis=cost_analysis,
            event_attribute="total_tokens",
            prompt_attribute="total_tokens",
            cost_attribute="total_tokens",
        )

        retry_count = max(
            [
                event.retry_count
                for event in events
            ]
            or [0]
        )

        retry_exhausted = any(
            event.retry_exhausted
            for event in events
        )

        if cost_analysis is not None:
            retry_count = max(
                retry_count,
                cost_analysis.retry_count,
            )
            retry_exhausted = (
                retry_exhausted
                or cost_analysis.retry_exhausted
            )

        estimated_cost = (
            cost_analysis.cost.total_cost
            if cost_analysis is not None
            else 0.0
        )

        currency = (
            cost_analysis.cost.currency
            if cost_analysis is not None
            else (
                cost_report.currency
                if cost_report is not None
                else "USD"
            )
        )

        recommendations = self._build_stage_recommendations(
            project_id=project_id,
            stage=normalized_stage,
            events=events,
            health_component=health_component,
            prompt_analysis=prompt_analysis,
            cost_analysis=cost_analysis,
            duration_seconds=duration_seconds,
            prompt_tokens=prompt_tokens,
            response_tokens=response_tokens,
            thinking_tokens=thinking_tokens,
            total_tokens=total_tokens,
            retry_count=retry_count,
            retry_exhausted=retry_exhausted,
            estimated_cost=estimated_cost,
            currency=currency,
        )

        optimization_score = self._calculate_stage_score(
            health_component=health_component,
            prompt_analysis=prompt_analysis,
            cost_analysis=cost_analysis,
            duration_seconds=duration_seconds,
            prompt_tokens=prompt_tokens,
            response_tokens=response_tokens,
            thinking_tokens=thinking_tokens,
            retry_count=retry_count,
            retry_exhausted=retry_exhausted,
        )

        analysis = StageOptimizationAnalysis(
            analysis_id=self._new_stage_analysis_id(),
            project_id=project_id,
            stage=normalized_stage,
            optimization_score=optimization_score,
            health_status=(
                health_component.status.value
                if health_component is not None
                else ""
            ),
            prompt_status=(
                prompt_analysis.status.value
                if prompt_analysis is not None
                else ""
            ),
            cost_status=(
                cost_analysis.status.value
                if cost_analysis is not None
                else ""
            ),
            duration_seconds=duration_seconds,
            prompt_tokens=prompt_tokens,
            response_tokens=response_tokens,
            thinking_tokens=thinking_tokens,
            total_tokens=total_tokens,
            retry_count=retry_count,
            retry_exhausted=retry_exhausted,
            estimated_cost=estimated_cost,
            currency=currency,
            recommendations=recommendations,
            metadata={
                "component": self.COMPONENT_NAME,
                "version": self.VERSION,
                "events_analyzed": len(events),
                "health_data_available": (
                    health_component is not None
                ),
                "prompt_data_available": (
                    prompt_analysis is not None
                ),
                "cost_data_available": (
                    cost_analysis is not None
                ),
            },
        )

        if not recommendations:
            analysis.recommendations.append(
                self._no_action_recommendation(
                    project_id=project_id,
                    stage=normalized_stage,
                )
            )
            analysis.recalculate_priority()

        return analysis

    def get_thresholds(
        self,
    ) -> dict[str, Any]:
        """
        Devuelve umbrales públicos.
        """

        return {
            "long_duration_seconds": (
                self.long_duration_seconds
            ),
            "critical_duration_seconds": (
                self.critical_duration_seconds
            ),
            "high_prompt_tokens": (
                self.high_prompt_tokens
            ),
            "critical_prompt_tokens": (
                self.critical_prompt_tokens
            ),
            "high_retry_count": (
                self.high_retry_count
            ),
            "critical_retry_count": (
                self.critical_retry_count
            ),
            "low_response_yield_percent": (
                self.low_response_yield_percent
            ),
            "critical_response_yield_percent": (
                self.critical_response_yield_percent
            ),
            "high_prompt_ratio": (
                self.high_prompt_ratio
            ),
            "critical_prompt_ratio": (
                self.critical_prompt_ratio
            ),
            "cache_candidate_prompt_tokens": (
                self.cache_candidate_prompt_tokens
            ),
            "expensive_stage_cost": (
                self.expensive_stage_cost
            ),
        }

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
            "applies_changes": False,
            "uses_telemetry": True,
            "uses_health_report": True,
            "uses_prompt_report": True,
            "uses_cost_report": True,
            "action_types": [
                action_type.value
                for action_type in OptimizationActionType
            ],
            "next_component": (
                "runtime_optimizer_smoke_test"
            ),
        }

    # --------------------------------------------------
    # Recomendaciones por Stage
    # --------------------------------------------------

    def _build_stage_recommendations(
        self,
        *,
        project_id: str,
        stage: str,
        events: list[TelemetryEvent],
        health_component: ComponentHealth | None,
        prompt_analysis: PromptAnalysis | None,
        cost_analysis: StageCostAnalysis | None,
        duration_seconds: float,
        prompt_tokens: int,
        response_tokens: int,
        thinking_tokens: int,
        total_tokens: int,
        retry_count: int,
        retry_exhausted: bool,
        estimated_cost: float,
        currency: str,
    ) -> list[OptimizationRecommendation]:
        recommendations: list[
            OptimizationRecommendation
        ] = []

        prompt_ratio = self._safe_ratio(
            prompt_tokens,
            response_tokens,
        )

        response_yield = self._rate(
            response_tokens,
            prompt_tokens,
        )

        provider = self._resolve_provider(
            events,
            prompt_analysis,
            cost_analysis,
        )

        model = self._resolve_model(
            events,
            prompt_analysis,
            cost_analysis,
        )

        if (
            prompt_tokens >= self.high_prompt_tokens
            or (
                prompt_analysis is not None
                and prompt_analysis.status
                in {
                    PromptEfficiencyStatus.INEFFICIENT,
                    PromptEfficiencyStatus.CRITICAL,
                }
            )
        ):
            priority = (
                OptimizationPriority.CRITICAL
                if (
                    prompt_tokens
                    >= self.critical_prompt_tokens
                    or (
                        prompt_analysis is not None
                        and prompt_analysis.status
                        == PromptEfficiencyStatus.CRITICAL
                    )
                )
                else OptimizationPriority.HIGH
            )

            reduction_percent = (
                40.0
                if priority
                == OptimizationPriority.CRITICAL
                else 25.0
            )

            proposed_tokens = max(
                int(
                    prompt_tokens
                    * (
                        1
                        - reduction_percent
                        / 100
                    )
                ),
                1_000,
            )

            estimated_savings = self._estimate_prompt_savings(
                cost_analysis=cost_analysis,
                reduction_percent=reduction_percent,
            )

            recommendations.append(
                OptimizationRecommendation(
                    recommendation_id=(
                        self._new_recommendation_id()
                    ),
                    title="Reducir longitud del prompt",
                    description=(
                        "El Stage consume un contexto elevado "
                        "o fue clasificado como ineficiente."
                    ),
                    action_type=(
                        OptimizationActionType.REDUCE_PROMPT
                    ),
                    priority=priority,
                    project_id=project_id,
                    stage=stage,
                    provider=provider,
                    model=model,
                    confidence_score=92,
                    expected_improvement_percent=(
                        reduction_percent
                    ),
                    estimated_savings=estimated_savings,
                    currency=currency,
                    evidence=[
                        f"prompt_tokens={prompt_tokens}",
                        (
                            "prompt_status="
                            f"{prompt_analysis.status.value}"
                            if prompt_analysis is not None
                            else "prompt_status=no_disponible"
                        ),
                    ],
                    adjustments=[
                        OptimizationAdjustment(
                            target="prompt_engine",
                            parameter=(
                                "target_prompt_tokens"
                            ),
                            current_value=prompt_tokens,
                            proposed_value=(
                                proposed_tokens
                            ),
                            unit="tokens",
                            safe_to_apply_automatically=False,
                            rationale=(
                                "Reducir contexto redundante "
                                "sin perder requisitos críticos."
                            ),
                        )
                    ],
                    risks=[
                        "Una reducción excesiva puede eliminar "
                        "contexto relevante."
                    ],
                    prerequisites=[
                        "Revisar módulos de conocimiento y "
                        "restricciones obligatorias."
                    ],
                )
            )

        if (
            prompt_ratio >= self.high_prompt_ratio
            or (
                response_yield > 0
                and response_yield
                <= self.low_response_yield_percent
            )
        ):
            priority = (
                OptimizationPriority.CRITICAL
                if (
                    prompt_ratio
                    >= self.critical_prompt_ratio
                    or (
                        response_yield > 0
                        and response_yield
                        <= self.critical_response_yield_percent
                    )
                )
                else OptimizationPriority.HIGH
            )

            current_max_output = self._infer_max_output_tokens(
                events
            )

            proposed_max_output = (
                max(
                    response_tokens * 2,
                    1_024,
                )
                if response_tokens > 0
                else max(
                    int(
                        current_max_output
                        * 0.75
                    ),
                    1_024,
                )
            )

            recommendations.append(
                OptimizationRecommendation(
                    recommendation_id=(
                        self._new_recommendation_id()
                    ),
                    title=(
                        "Alinear límite de salida "
                        "con la respuesta real"
                    ),
                    description=(
                        "La relación entre entrada y salida "
                        "indica sobreaprovisionamiento o bajo "
                        "rendimiento de respuesta."
                    ),
                    action_type=(
                        OptimizationActionType
                        .REDUCE_MAX_OUTPUT_TOKENS
                    ),
                    priority=priority,
                    project_id=project_id,
                    stage=stage,
                    provider=provider,
                    model=model,
                    confidence_score=86,
                    expected_improvement_percent=20,
                    estimated_savings=0.0,
                    currency=currency,
                    evidence=[
                        f"prompt_response_ratio={prompt_ratio}",
                        f"response_yield={response_yield}%",
                        (
                            "response_tokens="
                            f"{response_tokens}"
                        ),
                    ],
                    adjustments=[
                        OptimizationAdjustment(
                            target="llm",
                            parameter=(
                                "max_output_tokens"
                            ),
                            current_value=(
                                current_max_output
                            ),
                            proposed_value=(
                                proposed_max_output
                            ),
                            unit="tokens",
                            safe_to_apply_automatically=(
                                response_tokens > 0
                                and proposed_max_output
                                >= response_tokens
                            ),
                            rationale=(
                                "Ajustar el límite a la "
                                "producción observada."
                            ),
                        )
                    ],
                    risks=[
                        "Un límite demasiado bajo puede truncar "
                        "respuestas excepcionales."
                    ],
                )
            )

        if (
            thinking_tokens > response_tokens
            and thinking_tokens > 500
        ):
            proposed_level = (
                "low"
            )

            recommendations.append(
                OptimizationRecommendation(
                    recommendation_id=(
                        self._new_recommendation_id()
                    ),
                    title="Reducir nivel de razonamiento",
                    description=(
                        "El Stage usa más tokens de pensamiento "
                        "que tokens de respuesta."
                    ),
                    action_type=(
                        OptimizationActionType
                        .ADJUST_THINKING_LEVEL
                    ),
                    priority=OptimizationPriority.MEDIUM,
                    project_id=project_id,
                    stage=stage,
                    provider=provider,
                    model=model,
                    confidence_score=78,
                    expected_improvement_percent=15,
                    estimated_savings=(
                        self._estimate_thinking_savings(
                            cost_analysis
                        )
                    ),
                    currency=currency,
                    evidence=[
                        (
                            "thinking_tokens="
                            f"{thinking_tokens}"
                        ),
                        (
                            "response_tokens="
                            f"{response_tokens}"
                        ),
                    ],
                    adjustments=[
                        OptimizationAdjustment(
                            target="llm",
                            parameter="thinking_level",
                            current_value=(
                                self._infer_thinking_level(
                                    events
                                )
                            ),
                            proposed_value=proposed_level,
                            safe_to_apply_automatically=False,
                            rationale=(
                                "Reducir razonamiento cuando "
                                "el Stage no requiere alta "
                                "complejidad."
                            ),
                        )
                    ],
                    risks=[
                        "Puede reducir profundidad analítica."
                    ],
                    prerequisites=[
                        "Confirmar que el Stage no exige "
                        "razonamiento complejo."
                    ],
                )
            )

        if (
            duration_seconds
            >= self.long_duration_seconds
        ):
            priority = (
                OptimizationPriority.CRITICAL
                if duration_seconds
                >= self.critical_duration_seconds
                else OptimizationPriority.HIGH
            )

            current_timeout = self._infer_timeout(
                events
            )

            proposed_timeout = max(
                int(
                    duration_seconds
                    * 1.35
                ),
                current_timeout,
                60,
            )

            recommendations.append(
                OptimizationRecommendation(
                    recommendation_id=(
                        self._new_recommendation_id()
                    ),
                    title="Revisar latencia y timeout",
                    description=(
                        "La duración del Stage supera el "
                        "umbral operativo."
                    ),
                    action_type=(
                        OptimizationActionType.ADJUST_TIMEOUT
                    ),
                    priority=priority,
                    project_id=project_id,
                    stage=stage,
                    component="pipeline_engine",
                    provider=provider,
                    model=model,
                    confidence_score=88,
                    expected_improvement_percent=10,
                    evidence=[
                        (
                            "duration_seconds="
                            f"{duration_seconds}"
                        ),
                        (
                            "health_status="
                            f"{health_component.status.value}"
                            if health_component is not None
                            else "health_status=no_disponible"
                        ),
                    ],
                    adjustments=[
                        OptimizationAdjustment(
                            target="llm",
                            parameter="timeout_seconds",
                            current_value=current_timeout,
                            proposed_value=proposed_timeout,
                            unit="seconds",
                            safe_to_apply_automatically=False,
                            rationale=(
                                "Evitar timeouts prematuros "
                                "mientras se investiga la causa."
                            ),
                        )
                    ],
                    risks=[
                        "Aumentar timeout puede ocultar "
                        "problemas de rendimiento."
                    ],
                    prerequisites=[
                        "Revisar tamaño del prompt y estado "
                        "del proveedor."
                    ],
                )
            )

        if (
            retry_count >= self.high_retry_count
            or retry_exhausted
        ):
            priority = (
                OptimizationPriority.CRITICAL
                if (
                    retry_exhausted
                    or retry_count
                    >= self.critical_retry_count
                )
                else OptimizationPriority.HIGH
            )

            recommendations.append(
                OptimizationRecommendation(
                    recommendation_id=(
                        self._new_recommendation_id()
                    ),
                    title="Ajustar política de Retry",
                    description=(
                        "El Stage utiliza reintentos frecuentes "
                        "o agotó la política actual."
                    ),
                    action_type=(
                        OptimizationActionType
                        .ADJUST_RETRY_POLICY
                    ),
                    priority=priority,
                    project_id=project_id,
                    stage=stage,
                    component="retry_engine",
                    provider=provider,
                    model=model,
                    confidence_score=94,
                    expected_improvement_percent=20,
                    evidence=[
                        f"retry_count={retry_count}",
                        (
                            "retry_exhausted="
                            f"{retry_exhausted}"
                        ),
                    ],
                    adjustments=[
                        OptimizationAdjustment(
                            target="retry_policy",
                            parameter="max_attempts",
                            current_value=(
                                self._infer_max_attempts(
                                    events
                                )
                            ),
                            proposed_value=(
                                max(
                                    self._infer_max_attempts(
                                        events
                                    ),
                                    3,
                                )
                            ),
                            safe_to_apply_automatically=False,
                            rationale=(
                                "Alinear intentos y backoff "
                                "con errores temporales."
                            ),
                        )
                    ],
                    risks=[
                        "Más reintentos pueden aumentar tiempo "
                        "y costo."
                    ],
                    prerequisites=[
                        "Distinguir cuota agotada de errores "
                        "temporales."
                    ],
                )
            )

            if self._contains_status_code(
                events,
                429,
            ):
                recommendations.append(
                    OptimizationRecommendation(
                        recommendation_id=(
                            self._new_recommendation_id()
                        ),
                        title=(
                            "Configurar proveedor alternativo"
                        ),
                        description=(
                            "Se detectó presión de cuota o "
                            "rate limit."
                        ),
                        action_type=(
                            OptimizationActionType
                            .CHANGE_PROVIDER
                        ),
                        priority=(
                            OptimizationPriority.CRITICAL
                        ),
                        project_id=project_id,
                        stage=stage,
                        provider=provider,
                        model=model,
                        confidence_score=96,
                        expected_improvement_percent=35,
                        evidence=[
                            "status_code=429",
                            (
                                "retry_exhausted="
                                f"{retry_exhausted}"
                            ),
                        ],
                        adjustments=[
                            OptimizationAdjustment(
                                target="llm",
                                parameter="provider",
                                current_value=provider,
                                proposed_value=(
                                    "fallback_provider"
                                ),
                                safe_to_apply_automatically=False,
                                rationale=(
                                    "Evitar bloqueo por cuota "
                                    "del proveedor principal."
                                ),
                            )
                        ],
                        risks=[
                            "La salida puede variar entre "
                            "proveedores."
                        ],
                        prerequisites=[
                            "Completar Sprint Multi Provider "
                            "Framework."
                        ],
                    )
                )

        if (
            prompt_tokens
            >= self.cache_candidate_prompt_tokens
            and self._cached_input_tokens(
                events,
                cost_analysis,
            )
            == 0
        ):
            recommendations.append(
                OptimizationRecommendation(
                    recommendation_id=(
                        self._new_recommendation_id()
                    ),
                    title="Evaluar caché de contexto",
                    description=(
                        "El Stage usa un prompt grande sin "
                        "tokens de entrada cacheados."
                    ),
                    action_type=(
                        OptimizationActionType.ENABLE_CACHE
                    ),
                    priority=OptimizationPriority.MEDIUM,
                    project_id=project_id,
                    stage=stage,
                    provider=provider,
                    model=model,
                    confidence_score=72,
                    expected_improvement_percent=10,
                    estimated_savings=(
                        self._estimate_cache_savings(
                            cost_analysis
                        )
                    ),
                    currency=currency,
                    evidence=[
                        f"prompt_tokens={prompt_tokens}",
                        "cached_input_tokens=0",
                    ],
                    adjustments=[
                        OptimizationAdjustment(
                            target="llm",
                            parameter="context_cache_enabled",
                            current_value=False,
                            proposed_value=True,
                            safe_to_apply_automatically=False,
                            rationale=(
                                "Reducir costo de contexto "
                                "repetido."
                            ),
                        )
                    ],
                    risks=[
                        "La caché puede generar costos de "
                        "almacenamiento."
                    ],
                    prerequisites=[
                        "Confirmar reutilización real del "
                        "contexto entre ejecuciones."
                    ],
                )
            )

        if (
            estimated_cost
            >= self.expensive_stage_cost
        ):
            recommendations.append(
                OptimizationRecommendation(
                    recommendation_id=(
                        self._new_recommendation_id()
                    ),
                    title="Revisar modelo por costo",
                    description=(
                        "El costo estimado del Stage supera "
                        "el umbral configurado."
                    ),
                    action_type=(
                        OptimizationActionType.CHANGE_MODEL
                    ),
                    priority=OptimizationPriority.MEDIUM,
                    project_id=project_id,
                    stage=stage,
                    provider=provider,
                    model=model,
                    confidence_score=68,
                    expected_improvement_percent=25,
                    estimated_savings=round(
                        estimated_cost * 0.25,
                        8,
                    ),
                    currency=currency,
                    evidence=[
                        (
                            "estimated_cost="
                            f"{estimated_cost} {currency}"
                        )
                    ],
                    adjustments=[
                        OptimizationAdjustment(
                            target="llm",
                            parameter="model",
                            current_value=model,
                            proposed_value=(
                                "lower_cost_model"
                            ),
                            safe_to_apply_automatically=False,
                            rationale=(
                                "Evaluar un modelo más "
                                "económico para este Stage."
                            ),
                        )
                    ],
                    risks=[
                        "Un modelo económico puede reducir "
                        "calidad."
                    ],
                    prerequisites=[
                        "Comparar calidad y validación con "
                        "un modelo alternativo."
                    ],
                )
            )

        if (
            health_component is not None
            and health_component.status
            == HealthStatus.UNHEALTHY
            and (
                prompt_tokens
                >= self.critical_prompt_tokens
                or duration_seconds
                >= self.critical_duration_seconds
            )
        ):
            recommendations.append(
                OptimizationRecommendation(
                    recommendation_id=(
                        self._new_recommendation_id()
                    ),
                    title="Dividir el Stage",
                    description=(
                        "El Stage combina alta complejidad "
                        "con un estado no saludable."
                    ),
                    action_type=(
                        OptimizationActionType.SPLIT_STAGE
                    ),
                    priority=OptimizationPriority.CRITICAL,
                    project_id=project_id,
                    stage=stage,
                    component="pipeline_engine",
                    provider=provider,
                    model=model,
                    confidence_score=82,
                    expected_improvement_percent=30,
                    evidence=[
                        (
                            "health_status="
                            f"{health_component.status.value}"
                        ),
                        f"prompt_tokens={prompt_tokens}",
                        (
                            "duration_seconds="
                            f"{duration_seconds}"
                        ),
                    ],
                    adjustments=[
                        OptimizationAdjustment(
                            target="pipeline",
                            parameter="stage_partition",
                            current_value=stage,
                            proposed_value=[
                                f"{stage}_parte_1",
                                f"{stage}_parte_2",
                            ],
                            safe_to_apply_automatically=False,
                            rationale=(
                                "Reducir carga de contexto y "
                                "facilitar validación."
                            ),
                        )
                    ],
                    risks=[
                        "Aumenta complejidad del Pipeline."
                    ],
                    prerequisites=[
                        "Definir transición y memoria entre "
                        "sub-Stages."
                    ],
                )
            )

        return self._deduplicate_recommendations(
            recommendations
        )

    # --------------------------------------------------
    # Score
    # --------------------------------------------------

    def _calculate_stage_score(
        self,
        *,
        health_component: ComponentHealth | None,
        prompt_analysis: PromptAnalysis | None,
        cost_analysis: StageCostAnalysis | None,
        duration_seconds: float,
        prompt_tokens: int,
        response_tokens: int,
        thinking_tokens: int,
        retry_count: int,
        retry_exhausted: bool,
    ) -> float:
        """
        Calcula score de 0 a 100.
        """

        score = 100.0

        if health_component is not None:
            score -= {
                HealthStatus.HEALTHY: 0,
                HealthStatus.UNKNOWN: 5,
                HealthStatus.DEGRADED: 20,
                HealthStatus.UNHEALTHY: 40,
            }.get(
                health_component.status,
                5,
            )

        if prompt_analysis is not None:
            score -= {
                PromptEfficiencyStatus.EFFICIENT: 0,
                PromptEfficiencyStatus.UNKNOWN: 5,
                PromptEfficiencyStatus.ACCEPTABLE: 10,
                PromptEfficiencyStatus.INEFFICIENT: 25,
                PromptEfficiencyStatus.CRITICAL: 40,
            }.get(
                prompt_analysis.status,
                5,
            )

        if cost_analysis is not None:
            status_name = cost_analysis.status.value

            if status_name == "PARTIAL":
                score -= 10
            elif status_name == "UNKNOWN_PRICING":
                score -= 15
            elif status_name == "INVALID":
                score -= 20

            if (
                cost_analysis.cost.total_cost
                >= self.expensive_stage_cost
            ):
                score -= 10

        if duration_seconds >= self.critical_duration_seconds:
            score -= 25
        elif duration_seconds >= self.long_duration_seconds:
            score -= 12

        if prompt_tokens >= self.critical_prompt_tokens:
            score -= 20
        elif prompt_tokens >= self.high_prompt_tokens:
            score -= 10

        prompt_ratio = self._safe_ratio(
            prompt_tokens,
            response_tokens,
        )

        if prompt_ratio >= self.critical_prompt_ratio:
            score -= 20
        elif prompt_ratio >= self.high_prompt_ratio:
            score -= 10

        if thinking_tokens > response_tokens and thinking_tokens > 500:
            score -= 8

        if retry_exhausted:
            score -= 30
        elif retry_count >= self.critical_retry_count:
            score -= 20
        elif retry_count >= self.high_retry_count:
            score -= 10

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

    # --------------------------------------------------
    # Global
    # --------------------------------------------------

    def _add_global_recommendations(
        self,
        *,
        plan: OptimizationPlan,
        health_report: RuntimeHealthReport | None,
        prompt_report: PromptIntelligenceReport | None,
        cost_report: ProjectCostReport | None,
    ) -> None:
        """
        Agrega observaciones globales al plan.
        """

        if (
            health_report is not None
            and health_report.status
            == HealthStatus.UNHEALTHY
        ):
            plan.warnings.append(
                "El Runtime presenta estado UNHEALTHY; "
                "prioriza estabilidad antes de optimizar costo."
            )

        if (
            prompt_report is not None
            and prompt_report.status
            == PromptEfficiencyStatus.CRITICAL
        ):
            plan.warnings.append(
                "Prompt Intelligence detectó al menos un "
                "análisis CRITICAL."
            )

        if (
            cost_report is not None
            and cost_report.unknown_pricing_analyses > 0
        ):
            plan.warnings.append(
                "Existen Stages sin precios conocidos; "
                "los ahorros estimados pueden ser incompletos."
            )

    # --------------------------------------------------
    # Búsqueda de datos
    # --------------------------------------------------

    def _collect_stage_names(
        self,
        *,
        events: list[TelemetryEvent],
        health_report: RuntimeHealthReport | None,
        prompt_report: PromptIntelligenceReport | None,
        cost_report: ProjectCostReport | None,
    ) -> list[str]:
        stages: list[str] = []

        stages.extend(
            event.stage
            for event in events
            if event.stage
        )

        if prompt_report is not None:
            stages.extend(
                analysis.stage
                for analysis in prompt_report.analyses
                if analysis.stage
            )

        if cost_report is not None:
            stages.extend(
                analysis.stage
                for analysis in cost_report.analyses
                if analysis.stage
            )

        if health_report is not None:
            for component in health_report.components:
                if component.category == "stage":
                    name = component.component

                    if name.startswith(
                        "stage:"
                    ):
                        name = name.split(
                            ":",
                            1,
                        )[1]

                    if name:
                        stages.append(
                            name
                        )

        return self._unique_strings(
            [
                str(
                    stage or ""
                ).strip().lower()
                for stage in stages
            ]
        )

    def _find_prompt_analysis(
        self,
        report: PromptIntelligenceReport | None,
        stage: str,
    ) -> PromptAnalysis | None:
        if report is None:
            return None

        matches = [
            analysis
            for analysis in report.analyses
            if analysis.stage == stage
        ]

        if not matches:
            return None

        return min(
            matches,
            key=lambda analysis: (
                analysis.efficiency_score
            ),
        )

    def _find_cost_analysis(
        self,
        report: ProjectCostReport | None,
        stage: str,
    ) -> StageCostAnalysis | None:
        if report is None:
            return None

        matches = [
            analysis
            for analysis in report.analyses
            if analysis.stage == stage
        ]

        if not matches:
            return None

        return max(
            matches,
            key=lambda analysis: (
                analysis.cost.total_cost
            ),
        )

    def _find_stage_health(
        self,
        report: RuntimeHealthReport | None,
        stage: str,
    ) -> ComponentHealth | None:
        if report is None:
            return None

        possible_names = {
            stage,
            f"stage:{stage}",
        }

        matches = [
            component
            for component in report.components
            if (
                component.category == "stage"
                and component.component
                in possible_names
            )
        ]

        if not matches:
            return None

        return matches[0]

    # --------------------------------------------------
    # Resolución de métricas
    # --------------------------------------------------

    def _resolve_duration(
        self,
        *,
        events: list[TelemetryEvent],
        prompt_analysis: PromptAnalysis | None,
        cost_analysis: StageCostAnalysis | None,
        health_component: ComponentHealth | None,
    ) -> float:
        values = [
            event.duration_seconds
            for event in events
            if event.duration_seconds > 0
        ]

        if prompt_analysis is not None:
            values.append(
                prompt_analysis.duration_seconds
            )

        if cost_analysis is not None:
            values.append(
                cost_analysis.duration_seconds
            )

        if health_component is not None:
            values.append(
                health_component.maximum_duration_seconds
            )

        return round(
            max(
                values or [0.0]
            ),
            6,
        )

    def _resolve_int_metric(
        self,
        *,
        events: list[TelemetryEvent],
        prompt_analysis: PromptAnalysis | None,
        cost_analysis: StageCostAnalysis | None,
        event_attribute: str,
        prompt_attribute: str,
        cost_attribute: str,
    ) -> int:
        values = [
            int(
                getattr(
                    event,
                    event_attribute,
                    0,
                )
                or 0
            )
            for event in events
        ]

        if prompt_analysis is not None:
            values.append(
                int(
                    getattr(
                        prompt_analysis,
                        prompt_attribute,
                        0,
                    )
                    or 0
                )
            )

        if cost_analysis is not None:
            values.append(
                int(
                    getattr(
                        cost_analysis.token_usage,
                        cost_attribute,
                        0,
                    )
                    or 0
                )
            )

        return max(
            values or [0]
        )

    def _resolve_provider(
        self,
        events: list[TelemetryEvent],
        prompt_analysis: PromptAnalysis | None,
        cost_analysis: StageCostAnalysis | None,
    ) -> str:
        if cost_analysis is not None:
            return cost_analysis.provider

        if prompt_analysis is not None:
            return prompt_analysis.provider

        for event in events:
            if event.provider:
                return event.provider

        return ""

    def _resolve_model(
        self,
        events: list[TelemetryEvent],
        prompt_analysis: PromptAnalysis | None,
        cost_analysis: StageCostAnalysis | None,
    ) -> str:
        if cost_analysis is not None:
            return cost_analysis.model

        if prompt_analysis is not None:
            return prompt_analysis.model

        for event in events:
            if event.model:
                return event.model

        return ""

    # --------------------------------------------------
    # Inferencias
    # --------------------------------------------------

    def _infer_max_output_tokens(
        self,
        events: list[TelemetryEvent],
    ) -> int:
        values = [
            int(
                event.metadata.get(
                    "max_output_tokens",
                    0,
                )
                or 0
            )
            for event in events
        ]

        return max(
            values or [8192]
        ) or 8192

    def _infer_timeout(
        self,
        events: list[TelemetryEvent],
    ) -> int:
        values = [
            int(
                event.metadata.get(
                    "timeout_seconds",
                    0,
                )
                or 0
            )
            for event in events
        ]

        return max(
            values or [120]
        ) or 120

    def _infer_max_attempts(
        self,
        events: list[TelemetryEvent],
    ) -> int:
        values = [
            int(
                event.metadata.get(
                    "max_attempts",
                    0,
                )
                or 0
            )
            for event in events
        ]

        return max(
            values or [3]
        ) or 3

    def _infer_thinking_level(
        self,
        events: list[TelemetryEvent],
    ) -> str:
        for event in events:
            if event.thinking_level:
                return event.thinking_level

        return "low"

    def _cached_input_tokens(
        self,
        events: list[TelemetryEvent],
        cost_analysis: StageCostAnalysis | None,
    ) -> int:
        values = [
            int(
                event.metadata.get(
                    "cached_input_tokens",
                    0,
                )
                or 0
            )
            for event in events
        ]

        if cost_analysis is not None:
            values.append(
                cost_analysis.token_usage.cached_input_tokens
            )

        return max(
            values or [0]
        )

    def _contains_status_code(
        self,
        events: list[TelemetryEvent],
        status_code: int,
    ) -> bool:
        for event in events:
            if event.status_code == status_code:
                return True

            if any(
                attempt.status_code == status_code
                for attempt in event.attempts
            ):
                return True

        return False

    # --------------------------------------------------
    # Ahorros
    # --------------------------------------------------

    def _estimate_prompt_savings(
        self,
        *,
        cost_analysis: StageCostAnalysis | None,
        reduction_percent: float,
    ) -> float:
        if cost_analysis is None:
            return 0.0

        reducible_cost = (
            cost_analysis.cost.input_cost
            + cost_analysis.cost.cached_input_cost
        )

        return round(
            reducible_cost
            * reduction_percent
            / 100,
            8,
        )

    def _estimate_thinking_savings(
        self,
        cost_analysis: StageCostAnalysis | None,
    ) -> float:
        if cost_analysis is None:
            return 0.0

        return round(
            cost_analysis.cost.thinking_cost
            * 0.30,
            8,
        )

    def _estimate_cache_savings(
        self,
        cost_analysis: StageCostAnalysis | None,
    ) -> float:
        if cost_analysis is None:
            return 0.0

        difference = (
            cost_analysis.cost.input_rate
            - cost_analysis.cost.cached_input_rate
        )

        if (
            difference <= 0
            or cost_analysis.token_usage.prompt_tokens <= 0
        ):
            return 0.0

        return round(
            (
                cost_analysis.token_usage.prompt_tokens
                / cost_analysis.cost.token_unit
            )
            * difference,
            8,
        )

    # --------------------------------------------------
    # No action
    # --------------------------------------------------

    def _no_action_recommendation(
        self,
        *,
        project_id: str,
        stage: str,
    ) -> OptimizationRecommendation:
        return OptimizationRecommendation(
            recommendation_id=(
                self._new_recommendation_id()
            ),
            title="Sin cambios recomendados",
            description=(
                "Las métricas disponibles no requieren "
                "optimización inmediata."
            ),
            action_type=(
                OptimizationActionType.NO_ACTION
            ),
            priority=OptimizationPriority.LOW,
            status=OptimizationStatus.SKIPPED,
            project_id=project_id,
            stage=stage,
            confidence_score=70,
            evidence=[
                "No se superaron los umbrales configurados."
            ],
        )

    # --------------------------------------------------
    # Normalización
    # --------------------------------------------------

    def _normalize_events(
        self,
        events: Iterable[
            TelemetryEvent | dict[str, Any]
        ],
    ) -> list[TelemetryEvent]:
        normalized: list[TelemetryEvent] = []

        for event in events or []:
            if isinstance(
                event,
                TelemetryEvent,
            ):
                normalized.append(
                    event
                )

            elif isinstance(
                event,
                dict,
            ):
                data = {
                    key: value
                    for key, value in event.items()
                    if key
                    in TelemetryEvent.__dataclass_fields__
                }

                normalized.append(
                    TelemetryEvent(
                        **data
                    )
                )

        return normalized

    def _infer_project_id(
        self,
        *,
        events: list[TelemetryEvent],
        health_report: RuntimeHealthReport | None,
        prompt_report: PromptIntelligenceReport | None,
        cost_report: ProjectCostReport | None,
    ) -> str:
        candidates: list[str] = []

        candidates.extend(
            event.project_id
            for event in events
            if event.project_id
        )

        if health_report is not None:
            candidates.append(
                health_report.project_id
            )

        if prompt_report is not None:
            candidates.append(
                prompt_report.project_id
            )

        if cost_report is not None:
            candidates.append(
                cost_report.project_id
            )

        unique = self._unique_strings(
            candidates
        )

        return (
            unique[0]
            if len(unique) == 1
            else ""
        )

    def _deduplicate_recommendations(
        self,
        recommendations: list[
            OptimizationRecommendation
        ],
    ) -> list[OptimizationRecommendation]:
        seen: set[
            tuple[str, str]
        ] = set()

        result: list[
            OptimizationRecommendation
        ] = []

        for recommendation in recommendations:
            key = (
                recommendation.action_type.value,
                recommendation.stage,
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

    def _safe_ratio(
        self,
        numerator: float,
        denominator: float,
    ) -> float:
        if denominator <= 0:
            return 0.0

        return round(
            numerator
            / denominator,
            6,
        )

    def _rate(
        self,
        numerator: float,
        denominator: float,
    ) -> float:
        if denominator <= 0:
            return 0.0

        return round(
            (
                numerator
                / denominator
            )
            * 100,
            6,
        )

    def _positive_int(
        self,
        value: Any,
        default: int,
    ) -> int:
        try:
            number = int(
                value
            )
        except (TypeError, ValueError):
            return default

        return (
            number
            if number > 0
            else default
        )

    def _non_negative_float(
        self,
        value: Any,
        default: float,
    ) -> float:
        try:
            number = float(
                value
            )
        except (TypeError, ValueError):
            return default

        return max(
            number,
            0.0,
        )

    def _percent(
        self,
        value: Any,
        default: float,
    ) -> float:
        try:
            number = float(
                value
            )
        except (TypeError, ValueError):
            return default

        return min(
            max(
                number,
                0.0,
            ),
            100.0,
        )

    def _unique_strings(
        self,
        values: Iterable[Any],
    ) -> list[str]:
        result: list[str] = []

        for value in values:
            item = str(
                value or ""
            ).strip()

            if (
                item
                and item not in result
            ):
                result.append(
                    item
                )

        return result

    def _new_recommendation_id(
        self,
    ) -> str:
        return (
            "OPT-"
            + uuid4().hex.upper()
        )

    def _new_stage_analysis_id(
        self,
    ) -> str:
        return (
            "STAGE-OPT-"
            + uuid4().hex.upper()
        )

    def _new_plan_id(
        self,
    ) -> str:
        return (
            "OPT-PLAN-"
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