"""
=========================================================
Proyecto : CIPS
Release  : 0.9
Build    : 075
Archivo  : optimization_models.py
Estado   : RELEASE
=========================================================

Define los contratos de datos del Adaptive Runtime Optimizer.

Responsabilidades:
- representar prioridades de optimización;
- representar tipos de acción;
- representar recomendaciones;
- representar ajustes propuestos;
- representar análisis por Stage;
- representar planes consolidados por proyecto;
- normalizar valores;
- producir estructuras serializables;
- mantener el optimizador desacoplado del Runtime Core.

Este módulo NO:
- modifica configuración;
- ejecuta optimizaciones;
- llama proveedores;
- escribe archivos;
- altera el Pipeline;
- sustituye runtime_models.py.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class OptimizationPriority(str, Enum):
    """
    Prioridad operativa de una recomendación.
    """

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"
    UNKNOWN = "UNKNOWN"

    @classmethod
    def normalize(
        cls,
        value: Any,
    ) -> "OptimizationPriority":
        if isinstance(
            value,
            cls,
        ):
            return value

        normalized = str(
            value or ""
        ).strip().upper()

        for priority in cls:
            if priority.value == normalized:
                return priority

        return cls.UNKNOWN


class OptimizationActionType(str, Enum):
    """
    Tipos oficiales de acción de optimización.
    """

    REDUCE_PROMPT = "REDUCE_PROMPT"
    REDUCE_MAX_OUTPUT_TOKENS = "REDUCE_MAX_OUTPUT_TOKENS"
    ADJUST_THINKING_LEVEL = "ADJUST_THINKING_LEVEL"
    ADJUST_TEMPERATURE = "ADJUST_TEMPERATURE"
    ADJUST_TIMEOUT = "ADJUST_TIMEOUT"
    ADJUST_RETRY_POLICY = "ADJUST_RETRY_POLICY"
    ENABLE_CACHE = "ENABLE_CACHE"
    CHANGE_MODEL = "CHANGE_MODEL"
    CHANGE_PROVIDER = "CHANGE_PROVIDER"
    SPLIT_STAGE = "SPLIT_STAGE"
    REVIEW_KNOWLEDGE = "REVIEW_KNOWLEDGE"
    REVIEW_VALIDATION = "REVIEW_VALIDATION"
    NO_ACTION = "NO_ACTION"
    CUSTOM = "CUSTOM"

    @classmethod
    def normalize(
        cls,
        value: Any,
    ) -> "OptimizationActionType":
        if isinstance(
            value,
            cls,
        ):
            return value

        normalized = str(
            value or ""
        ).strip().upper()

        for action_type in cls:
            if action_type.value == normalized:
                return action_type

        return cls.CUSTOM


class OptimizationStatus(str, Enum):
    """
    Estado de una recomendación o plan.
    """

    PROPOSED = "PROPOSED"
    APPROVED = "APPROVED"
    APPLIED = "APPLIED"
    REJECTED = "REJECTED"
    SKIPPED = "SKIPPED"
    INVALID = "INVALID"

    @classmethod
    def normalize(
        cls,
        value: Any,
    ) -> "OptimizationStatus":
        if isinstance(
            value,
            cls,
        ):
            return value

        normalized = str(
            value or ""
        ).strip().upper()

        for status in cls:
            if status.value == normalized:
                return status

        return cls.INVALID


@dataclass
class OptimizationAdjustment:
    """
    Representa un cambio propuesto de configuración.
    """

    target: str
    parameter: str
    current_value: Any = None
    proposed_value: Any = None
    unit: str = ""

    safe_to_apply_automatically: bool = False
    requires_restart: bool = False

    rationale: str = ""
    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    def __post_init__(
        self,
    ) -> None:
        self.target = str(
            self.target or ""
        ).strip()

        self.parameter = str(
            self.parameter or ""
        ).strip()

        self.unit = str(
            self.unit or ""
        ).strip()

        self.safe_to_apply_automatically = bool(
            self.safe_to_apply_automatically
        )

        self.requires_restart = bool(
            self.requires_restart
        )

        self.rationale = str(
            self.rationale or ""
        ).strip()

        self.metadata = dict(
            self.metadata or {}
        )

    def has_change(
        self,
    ) -> bool:
        """
        Indica si el valor propuesto difiere del actual.
        """

        return (
            self.current_value
            != self.proposed_value
        )

    def to_dict(
        self,
    ) -> dict[str, Any]:
        return asdict(
            self
        )


@dataclass
class OptimizationRecommendation:
    """
    Recomendación individual de optimización.
    """

    recommendation_id: str
    title: str
    description: str

    action_type: OptimizationActionType
    priority: OptimizationPriority
    status: OptimizationStatus = (
        OptimizationStatus.PROPOSED
    )

    project_id: str = ""
    stage: str = ""
    component: str = ""
    provider: str = ""
    model: str = ""

    confidence_score: float = 0.0
    expected_improvement_percent: float = 0.0
    estimated_savings: float = 0.0
    currency: str = "USD"

    evidence: list[str] = field(
        default_factory=list
    )

    adjustments: list[
        OptimizationAdjustment
    ] = field(
        default_factory=list
    )

    risks: list[str] = field(
        default_factory=list
    )

    prerequisites: list[str] = field(
        default_factory=list
    )

    warnings: list[str] = field(
        default_factory=list
    )

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    def __post_init__(
        self,
    ) -> None:
        self.recommendation_id = str(
            self.recommendation_id or ""
        ).strip()

        self.title = str(
            self.title or ""
        ).strip()

        self.description = str(
            self.description or ""
        ).strip()

        self.action_type = (
            OptimizationActionType.normalize(
                self.action_type
            )
        )

        self.priority = OptimizationPriority.normalize(
            self.priority
        )

        self.status = OptimizationStatus.normalize(
            self.status
        )

        self.project_id = str(
            self.project_id or ""
        ).strip()

        self.stage = str(
            self.stage or ""
        ).strip().lower()

        self.component = str(
            self.component or ""
        ).strip()

        self.provider = str(
            self.provider or ""
        ).strip().lower()

        self.model = str(
            self.model or ""
        ).strip()

        self.confidence_score = self._bounded_float(
            self.confidence_score,
            0.0,
            100.0,
        )

        self.expected_improvement_percent = (
            self._bounded_float(
                self.expected_improvement_percent,
                0.0,
                100.0,
            )
        )

        self.estimated_savings = (
            self._non_negative_float(
                self.estimated_savings
            )
        )

        self.currency = str(
            self.currency or "USD"
        ).strip().upper()

        self.evidence = self._unique_strings(
            self.evidence
        )

        normalized_adjustments: list[
            OptimizationAdjustment
        ] = []

        for adjustment in self.adjustments:
            if isinstance(
                adjustment,
                OptimizationAdjustment,
            ):
                normalized_adjustments.append(
                    adjustment
                )

            elif isinstance(
                adjustment,
                dict,
            ):
                normalized_adjustments.append(
                    OptimizationAdjustment(
                        **adjustment
                    )
                )

        self.adjustments = normalized_adjustments

        self.risks = self._unique_strings(
            self.risks
        )

        self.prerequisites = self._unique_strings(
            self.prerequisites
        )

        self.warnings = self._unique_strings(
            self.warnings
        )

        self.metadata = dict(
            self.metadata or {}
        )

    def is_actionable(
        self,
    ) -> bool:
        """
        Indica si existe una acción real por ejecutar.
        """

        return (
            self.status
            == OptimizationStatus.PROPOSED
            and self.action_type
            != OptimizationActionType.NO_ACTION
        )

    def is_safe_for_automatic_apply(
        self,
    ) -> bool:
        """
        Indica si todos los ajustes son seguros.
        """

        return bool(
            self.adjustments
        ) and all(
            adjustment.safe_to_apply_automatically
            for adjustment in self.adjustments
        )

    def to_dict(
        self,
    ) -> dict[str, Any]:
        return {
            "recommendation_id": (
                self.recommendation_id
            ),
            "title": self.title,
            "description": self.description,
            "action_type": (
                self.action_type.value
            ),
            "priority": self.priority.value,
            "status": self.status.value,
            "project_id": self.project_id,
            "stage": self.stage,
            "component": self.component,
            "provider": self.provider,
            "model": self.model,
            "confidence_score": (
                self.confidence_score
            ),
            "expected_improvement_percent": (
                self.expected_improvement_percent
            ),
            "estimated_savings": (
                self.estimated_savings
            ),
            "currency": self.currency,
            "evidence": list(
                self.evidence
            ),
            "adjustments": [
                adjustment.to_dict()
                for adjustment in self.adjustments
            ],
            "risks": list(
                self.risks
            ),
            "prerequisites": list(
                self.prerequisites
            ),
            "warnings": list(
                self.warnings
            ),
            "metadata": dict(
                self.metadata
            ),
            "actionable": self.is_actionable(),
            "safe_for_automatic_apply": (
                self.is_safe_for_automatic_apply()
            ),
        }

    @staticmethod
    def _bounded_float(
        value: Any,
        minimum: float,
        maximum: float,
    ) -> float:
        try:
            number = float(
                value
            )
        except (TypeError, ValueError):
            return minimum

        return round(
            min(
                max(
                    number,
                    minimum,
                ),
                maximum,
            ),
            6,
        )

    @staticmethod
    def _non_negative_float(
        value: Any,
    ) -> float:
        try:
            number = float(
                value
            )
        except (TypeError, ValueError):
            return 0.0

        return round(
            max(
                number,
                0.0,
            ),
            8,
        )

    @staticmethod
    def _unique_strings(
        values: list[Any] | None,
    ) -> list[str]:
        result: list[str] = []

        for value in values or []:
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


@dataclass
class StageOptimizationAnalysis:
    """
    Análisis de optimización de un Stage.
    """

    analysis_id: str
    project_id: str
    stage: str

    optimization_score: float = 0.0
    priority: OptimizationPriority = (
        OptimizationPriority.UNKNOWN
    )

    health_status: str = ""
    prompt_status: str = ""
    cost_status: str = ""

    duration_seconds: float = 0.0
    prompt_tokens: int = 0
    response_tokens: int = 0
    thinking_tokens: int = 0
    total_tokens: int = 0

    retry_count: int = 0
    retry_exhausted: bool = False

    estimated_cost: float = 0.0
    currency: str = "USD"

    recommendations: list[
        OptimizationRecommendation
    ] = field(
        default_factory=list
    )

    warnings: list[str] = field(
        default_factory=list
    )

    errors: list[str] = field(
        default_factory=list
    )

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    def __post_init__(
        self,
    ) -> None:
        self.analysis_id = str(
            self.analysis_id or ""
        ).strip()

        self.project_id = str(
            self.project_id or ""
        ).strip()

        self.stage = str(
            self.stage or ""
        ).strip().lower()

        self.optimization_score = (
            OptimizationRecommendation._bounded_float(
                self.optimization_score,
                0.0,
                100.0,
            )
        )

        self.priority = OptimizationPriority.normalize(
            self.priority
        )

        self.health_status = str(
            self.health_status or ""
        ).strip().upper()

        self.prompt_status = str(
            self.prompt_status or ""
        ).strip().upper()

        self.cost_status = str(
            self.cost_status or ""
        ).strip().upper()

        self.duration_seconds = (
            OptimizationRecommendation._non_negative_float(
                self.duration_seconds
            )
        )

        for field_name in (
            "prompt_tokens",
            "response_tokens",
            "thinking_tokens",
            "total_tokens",
            "retry_count",
        ):
            setattr(
                self,
                field_name,
                self._non_negative_int(
                    getattr(
                        self,
                        field_name,
                    )
                ),
            )

        self.retry_exhausted = bool(
            self.retry_exhausted
        )

        self.estimated_cost = (
            OptimizationRecommendation._non_negative_float(
                self.estimated_cost
            )
        )

        self.currency = str(
            self.currency or "USD"
        ).strip().upper()

        normalized: list[
            OptimizationRecommendation
        ] = []

        for recommendation in self.recommendations:
            if isinstance(
                recommendation,
                OptimizationRecommendation,
            ):
                normalized.append(
                    recommendation
                )

            elif isinstance(
                recommendation,
                dict,
            ):
                normalized.append(
                    OptimizationRecommendation(
                        **recommendation
                    )
                )

        self.recommendations = normalized

        self.warnings = (
            OptimizationRecommendation._unique_strings(
                self.warnings
            )
        )

        self.errors = (
            OptimizationRecommendation._unique_strings(
                self.errors
            )
        )

        self.metadata = dict(
            self.metadata or {}
        )

        self.recalculate_priority()

    def recalculate_priority(
        self,
    ) -> OptimizationPriority:
        """
        Recalcula la prioridad según recomendaciones.
        """

        if self.recommendations:
            self.priority = worst_optimization_priority(
                [
                    recommendation.priority
                    for recommendation in self.recommendations
                ]
            )

        elif self.optimization_score >= 85:
            self.priority = OptimizationPriority.LOW

        elif self.optimization_score >= 70:
            self.priority = OptimizationPriority.MEDIUM

        elif self.optimization_score >= 40:
            self.priority = OptimizationPriority.HIGH

        else:
            self.priority = OptimizationPriority.CRITICAL

        return self.priority

    def actionable_recommendations(
        self,
    ) -> list[OptimizationRecommendation]:
        """
        Devuelve recomendaciones accionables.
        """

        return [
            recommendation
            for recommendation in self.recommendations
            if recommendation.is_actionable()
        ]

    def automatic_recommendations(
        self,
    ) -> list[OptimizationRecommendation]:
        """
        Devuelve recomendaciones aplicables automáticamente.
        """

        return [
            recommendation
            for recommendation
            in self.actionable_recommendations()
            if recommendation.is_safe_for_automatic_apply()
        ]

    def to_dict(
        self,
    ) -> dict[str, Any]:
        self.recalculate_priority()

        return {
            "analysis_id": self.analysis_id,
            "project_id": self.project_id,
            "stage": self.stage,
            "optimization_score": (
                self.optimization_score
            ),
            "priority": self.priority.value,
            "health_status": self.health_status,
            "prompt_status": self.prompt_status,
            "cost_status": self.cost_status,
            "duration_seconds": (
                self.duration_seconds
            ),
            "prompt_tokens": self.prompt_tokens,
            "response_tokens": self.response_tokens,
            "thinking_tokens": (
                self.thinking_tokens
            ),
            "total_tokens": self.total_tokens,
            "retry_count": self.retry_count,
            "retry_exhausted": (
                self.retry_exhausted
            ),
            "estimated_cost": (
                self.estimated_cost
            ),
            "currency": self.currency,
            "recommendations": [
                recommendation.to_dict()
                for recommendation
                in self.recommendations
            ],
            "warnings": list(
                self.warnings
            ),
            "errors": list(
                self.errors
            ),
            "metadata": dict(
                self.metadata
            ),
        }

    @staticmethod
    def _non_negative_int(
        value: Any,
    ) -> int:
        try:
            number = int(
                value
            )
        except (TypeError, ValueError):
            return 0

        return max(
            number,
            0,
        )


@dataclass
class OptimizationPlan:
    """
    Plan consolidado de optimización por proyecto.
    """

    plan_id: str
    generated_at: str
    project_id: str

    status: OptimizationStatus = (
        OptimizationStatus.PROPOSED
    )

    overall_score: float = 0.0
    priority: OptimizationPriority = (
        OptimizationPriority.UNKNOWN
    )

    analyses: list[
        StageOptimizationAnalysis
    ] = field(
        default_factory=list
    )

    recommendations_total: int = 0
    actionable_recommendations_total: int = 0
    automatic_recommendations_total: int = 0

    estimated_total_savings: float = 0.0
    currency: str = "USD"

    recommended_execution_order: list[str] = field(
        default_factory=list
    )

    warnings: list[str] = field(
        default_factory=list
    )

    errors: list[str] = field(
        default_factory=list
    )

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    def __post_init__(
        self,
    ) -> None:
        self.plan_id = str(
            self.plan_id or ""
        ).strip()

        self.generated_at = str(
            self.generated_at or ""
        ).strip()

        self.project_id = str(
            self.project_id or ""
        ).strip()

        self.status = OptimizationStatus.normalize(
            self.status
        )

        self.overall_score = (
            OptimizationRecommendation._bounded_float(
                self.overall_score,
                0.0,
                100.0,
            )
        )

        self.priority = OptimizationPriority.normalize(
            self.priority
        )

        normalized: list[
            StageOptimizationAnalysis
        ] = []

        for analysis in self.analyses:
            if isinstance(
                analysis,
                StageOptimizationAnalysis,
            ):
                normalized.append(
                    analysis
                )

            elif isinstance(
                analysis,
                dict,
            ):
                normalized.append(
                    StageOptimizationAnalysis(
                        **analysis
                    )
                )

        self.analyses = normalized

        self.currency = str(
            self.currency or "USD"
        ).strip().upper()

        self.recommended_execution_order = (
            OptimizationRecommendation._unique_strings(
                self.recommended_execution_order
            )
        )

        self.warnings = (
            OptimizationRecommendation._unique_strings(
                self.warnings
            )
        )

        self.errors = (
            OptimizationRecommendation._unique_strings(
                self.errors
            )
        )

        self.metadata = dict(
            self.metadata or {}
        )

        self.recalculate()

    def add_analysis(
        self,
        analysis: StageOptimizationAnalysis,
    ) -> None:
        """
        Agrega un análisis al plan.
        """

        if not isinstance(
            analysis,
            StageOptimizationAnalysis,
        ):
            raise TypeError(
                "analysis debe ser StageOptimizationAnalysis."
            )

        self.analyses.append(
            analysis
        )

        self.recalculate()

    def recalculate(
        self,
    ) -> None:
        """
        Recalcula score, prioridad y acumulados.
        """

        if self.analyses:
            self.overall_score = round(
                sum(
                    analysis.optimization_score
                    for analysis in self.analyses
                )
                / len(
                    self.analyses
                ),
                2,
            )

            self.priority = worst_optimization_priority(
                [
                    analysis.priority
                    for analysis in self.analyses
                ]
            )

        else:
            self.overall_score = 0.0
            self.priority = OptimizationPriority.UNKNOWN

        all_recommendations = [
            recommendation
            for analysis in self.analyses
            for recommendation in analysis.recommendations
        ]

        self.recommendations_total = len(
            all_recommendations
        )

        self.actionable_recommendations_total = sum(
            1
            for recommendation in all_recommendations
            if recommendation.is_actionable()
        )

        self.automatic_recommendations_total = sum(
            1
            for recommendation in all_recommendations
            if (
                recommendation.is_actionable()
                and recommendation.is_safe_for_automatic_apply()
            )
        )

        self.estimated_total_savings = round(
            sum(
                recommendation.estimated_savings
                for recommendation in all_recommendations
            ),
            8,
        )

        ordered = sorted(
            all_recommendations,
            key=lambda recommendation: (
                -optimization_priority_rank(
                    recommendation.priority
                ),
                -recommendation.confidence_score,
                recommendation.recommendation_id,
            ),
        )

        self.recommended_execution_order = [
            recommendation.recommendation_id
            for recommendation in ordered
            if recommendation.is_actionable()
        ]

    def to_dict(
        self,
    ) -> dict[str, Any]:
        self.recalculate()

        return {
            "plan_id": self.plan_id,
            "generated_at": self.generated_at,
            "project_id": self.project_id,
            "status": self.status.value,
            "overall_score": self.overall_score,
            "priority": self.priority.value,
            "analyses": [
                analysis.to_dict()
                for analysis in self.analyses
            ],
            "recommendations_total": (
                self.recommendations_total
            ),
            "actionable_recommendations_total": (
                self.actionable_recommendations_total
            ),
            "automatic_recommendations_total": (
                self.automatic_recommendations_total
            ),
            "estimated_total_savings": (
                self.estimated_total_savings
            ),
            "currency": self.currency,
            "recommended_execution_order": list(
                self.recommended_execution_order
            ),
            "warnings": list(
                self.warnings
            ),
            "errors": list(
                self.errors
            ),
            "metadata": dict(
                self.metadata
            ),
        }


def optimization_priority_rank(
    priority: OptimizationPriority | str,
) -> int:
    """
    Devuelve ranking numérico de prioridad.
    """

    normalized = OptimizationPriority.normalize(
        priority
    )

    return {
        OptimizationPriority.UNKNOWN: 0,
        OptimizationPriority.LOW: 1,
        OptimizationPriority.MEDIUM: 2,
        OptimizationPriority.HIGH: 3,
        OptimizationPriority.CRITICAL: 4,
    }[
        normalized
    ]


def worst_optimization_priority(
    priorities: list[
        OptimizationPriority | str
    ],
) -> OptimizationPriority:
    """
    Devuelve la prioridad más alta.
    """

    normalized = [
        OptimizationPriority.normalize(
            priority
        )
        for priority in priorities
    ]

    if not normalized:
        return OptimizationPriority.UNKNOWN

    return max(
        normalized,
        key=optimization_priority_rank,
    )


def get_optimization_models_info(
) -> dict[str, Any]:
    """
    Devuelve información pública del módulo.
    """

    return {
        "component": "optimization_models",
        "version": "0.9",
        "priorities": [
            priority.value
            for priority in OptimizationPriority
        ],
        "action_types": [
            action_type.value
            for action_type in OptimizationActionType
        ],
        "statuses": [
            status.value
            for status in OptimizationStatus
        ],
        "models": [
            "OptimizationAdjustment",
            "OptimizationRecommendation",
            "StageOptimizationAnalysis",
            "OptimizationPlan",
        ],
        "serializable": True,
        "runtime_models_modified": False,
        "next_component": "runtime_optimizer",
    }