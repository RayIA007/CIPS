"""
=========================================================
Proyecto : CIPS
Release  : 0.9
Build    : 068
Archivo  : prompt_intelligence_models.py
Estado   : RELEASE
=========================================================

Contratos de datos para Sprint 022A — Prompt Intelligence.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class PromptEfficiencyStatus(str, Enum):
    EFFICIENT = "EFFICIENT"
    ACCEPTABLE = "ACCEPTABLE"
    INEFFICIENT = "INEFFICIENT"
    CRITICAL = "CRITICAL"
    UNKNOWN = "UNKNOWN"

    @classmethod
    def normalize(cls, value: Any) -> "PromptEfficiencyStatus":
        if isinstance(value, cls):
            return value

        normalized = str(value or "").strip().upper()

        for status in cls:
            if status.value == normalized:
                return status

        return cls.UNKNOWN


@dataclass
class PromptMetric:
    metric_id: str
    name: str
    status: PromptEfficiencyStatus

    value: Any = None
    unit: str = ""
    target_value: Any = None
    warning_threshold: Any = None
    critical_threshold: Any = None

    score: float = 0.0
    weight: float = 1.0

    message: str = ""
    recommendation: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.metric_id = str(self.metric_id or "").strip()
        self.name = str(self.name or "").strip()
        self.status = PromptEfficiencyStatus.normalize(self.status)
        self.unit = str(self.unit or "").strip()
        self.score = _bounded_float(self.score, 0.0, 100.0)
        self.weight = _non_negative_float(self.weight)
        self.message = str(self.message or "").strip()
        self.recommendation = str(
            self.recommendation or ""
        ).strip()
        self.metadata = dict(self.metadata or {})

    def is_problem(self) -> bool:
        return self.status in {
            PromptEfficiencyStatus.INEFFICIENT,
            PromptEfficiencyStatus.CRITICAL,
        }

    def weighted_score(self) -> float:
        return round(self.score * self.weight, 6)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value
        return data


@dataclass
class PromptAnalysis:
    analysis_id: str
    project_id: str
    stage: str
    status: PromptEfficiencyStatus

    provider: str = ""
    model: str = ""
    prompt_path: str = ""

    prompt_characters: int = 0
    prompt_words: int = 0
    prompt_lines: int = 0
    prompt_tokens: int = 0

    response_characters: int = 0
    response_words: int = 0
    response_lines: int = 0
    response_tokens: int = 0

    thinking_tokens: int = 0
    total_tokens: int = 0
    duration_seconds: float = 0.0

    prompt_response_character_ratio: float = 0.0
    prompt_response_token_ratio: float = 0.0
    response_yield_percent: float = 0.0
    tokens_per_second: float = 0.0

    redundancy_score: float = 0.0
    density_score: float = 0.0
    efficiency_score: float = 0.0

    metrics: list[PromptMetric] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.analysis_id = str(self.analysis_id or "").strip()
        self.project_id = str(self.project_id or "").strip()
        self.stage = str(self.stage or "").strip().lower()
        self.status = PromptEfficiencyStatus.normalize(self.status)
        self.provider = str(self.provider or "").strip()
        self.model = str(self.model or "").strip()
        self.prompt_path = str(self.prompt_path or "").strip()

        for name in (
            "prompt_characters",
            "prompt_words",
            "prompt_lines",
            "prompt_tokens",
            "response_characters",
            "response_words",
            "response_lines",
            "response_tokens",
            "thinking_tokens",
            "total_tokens",
        ):
            setattr(self, name, _non_negative_int(getattr(self, name)))

        for name in (
            "duration_seconds",
            "prompt_response_character_ratio",
            "prompt_response_token_ratio",
            "response_yield_percent",
            "tokens_per_second",
            "redundancy_score",
            "density_score",
            "efficiency_score",
        ):
            setattr(
                self,
                name,
                _non_negative_float(getattr(self, name)),
            )

        normalized_metrics: list[PromptMetric] = []

        for metric in self.metrics:
            if isinstance(metric, PromptMetric):
                normalized_metrics.append(metric)
            elif isinstance(metric, dict):
                normalized_metrics.append(PromptMetric(**metric))

        self.metrics = normalized_metrics
        self.recommendations = _unique_strings(
            self.recommendations
        )
        self.warnings = _unique_strings(self.warnings)
        self.errors = _unique_strings(self.errors)
        self.metadata = dict(self.metadata or {})

        if self.metrics:
            self.calculate_weighted_score()
            self.recalculate_status()
        elif self.efficiency_score <= 0:
            self.status = PromptEfficiencyStatus.UNKNOWN

    def add_metric(self, metric: PromptMetric) -> None:
        if not isinstance(metric, PromptMetric):
            raise TypeError("metric debe ser PromptMetric.")

        self.metrics.append(metric)

        if metric.recommendation:
            self.recommendations = _unique_strings(
                [
                    *self.recommendations,
                    metric.recommendation,
                ]
            )

        self.calculate_weighted_score()
        self.recalculate_status()

    def calculate_weighted_score(self) -> float:
        if not self.metrics:
            return round(self.efficiency_score, 2)

        total_weight = sum(metric.weight for metric in self.metrics)

        if total_weight <= 0:
            self.efficiency_score = 0.0
            return 0.0

        self.efficiency_score = round(
            sum(metric.weighted_score() for metric in self.metrics)
            / total_weight,
            2,
        )

        return self.efficiency_score

    def recalculate_status(self) -> PromptEfficiencyStatus:
        if self.metrics:
            self.status = worst_prompt_status(
                [metric.status for metric in self.metrics]
            )

        return self.status

    def problem_metrics(self) -> list[PromptMetric]:
        return [
            metric
            for metric in self.metrics
            if metric.is_problem()
        ]

    def to_dict(self) -> dict[str, Any]:
        self.calculate_weighted_score()
        self.recalculate_status()

        data = asdict(self)
        data["status"] = self.status.value
        data["metrics"] = [
            metric.to_dict()
            for metric in self.metrics
        ]
        return data


@dataclass
class PromptIntelligenceReport:
    report_id: str
    generated_at: str
    project_id: str
    status: PromptEfficiencyStatus

    scope: str = "project"
    analyses: list[PromptAnalysis] = field(default_factory=list)

    analyses_total: int = 0
    efficient_analyses: int = 0
    acceptable_analyses: int = 0
    inefficient_analyses: int = 0
    critical_analyses: int = 0
    unknown_analyses: int = 0

    average_efficiency_score: float = 0.0

    total_prompt_characters: int = 0
    total_response_characters: int = 0
    total_prompt_tokens: int = 0
    total_response_tokens: int = 0
    total_thinking_tokens: int = 0
    total_tokens: int = 0

    average_prompt_response_token_ratio: float = 0.0
    average_response_yield_percent: float = 0.0
    average_duration_seconds: float = 0.0

    recommendations: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.report_id = str(self.report_id or "").strip()
        self.generated_at = str(self.generated_at or "").strip()
        self.project_id = str(self.project_id or "").strip()
        self.status = PromptEfficiencyStatus.normalize(self.status)
        self.scope = str(self.scope or "project").strip().lower()

        normalized_analyses: list[PromptAnalysis] = []

        for analysis in self.analyses:
            if isinstance(analysis, PromptAnalysis):
                normalized_analyses.append(analysis)
            elif isinstance(analysis, dict):
                normalized_analyses.append(
                    PromptAnalysis(**analysis)
                )

        self.analyses = normalized_analyses
        self.recommendations = _unique_strings(
            self.recommendations
        )
        self.warnings = _unique_strings(self.warnings)
        self.errors = _unique_strings(self.errors)
        self.metadata = dict(self.metadata or {})
        self.recalculate()

    def add_analysis(self, analysis: PromptAnalysis) -> None:
        if not isinstance(analysis, PromptAnalysis):
            raise TypeError(
                "analysis debe ser PromptAnalysis."
            )

        self.analyses.append(analysis)
        self.recommendations = _unique_strings(
            [
                *self.recommendations,
                *analysis.recommendations,
            ]
        )
        self.recalculate()

    def recalculate(self) -> None:
        self.analyses_total = len(self.analyses)
        statuses = [
            analysis.status
            for analysis in self.analyses
        ]

        self.efficient_analyses = statuses.count(
            PromptEfficiencyStatus.EFFICIENT
        )
        self.acceptable_analyses = statuses.count(
            PromptEfficiencyStatus.ACCEPTABLE
        )
        self.inefficient_analyses = statuses.count(
            PromptEfficiencyStatus.INEFFICIENT
        )
        self.critical_analyses = statuses.count(
            PromptEfficiencyStatus.CRITICAL
        )
        self.unknown_analyses = statuses.count(
            PromptEfficiencyStatus.UNKNOWN
        )

        if not self.analyses:
            self.status = PromptEfficiencyStatus.UNKNOWN
            self.average_efficiency_score = 0.0
            self.average_prompt_response_token_ratio = 0.0
            self.average_response_yield_percent = 0.0
            self.average_duration_seconds = 0.0
        else:
            self.status = worst_prompt_status(statuses)
            count = len(self.analyses)

            self.average_efficiency_score = round(
                sum(
                    analysis.calculate_weighted_score()
                    for analysis in self.analyses
                )
                / count,
                2,
            )

            self.average_prompt_response_token_ratio = round(
                sum(
                    analysis.prompt_response_token_ratio
                    for analysis in self.analyses
                )
                / count,
                6,
            )

            self.average_response_yield_percent = round(
                sum(
                    analysis.response_yield_percent
                    for analysis in self.analyses
                )
                / count,
                6,
            )

            self.average_duration_seconds = round(
                sum(
                    analysis.duration_seconds
                    for analysis in self.analyses
                )
                / count,
                6,
            )

        self.total_prompt_characters = sum(
            analysis.prompt_characters
            for analysis in self.analyses
        )
        self.total_response_characters = sum(
            analysis.response_characters
            for analysis in self.analyses
        )
        self.total_prompt_tokens = sum(
            analysis.prompt_tokens
            for analysis in self.analyses
        )
        self.total_response_tokens = sum(
            analysis.response_tokens
            for analysis in self.analyses
        )
        self.total_thinking_tokens = sum(
            analysis.thinking_tokens
            for analysis in self.analyses
        )
        self.total_tokens = sum(
            analysis.total_tokens
            for analysis in self.analyses
        )

    def problematic_analyses(self) -> list[PromptAnalysis]:
        return [
            analysis
            for analysis in self.analyses
            if analysis.status
            in {
                PromptEfficiencyStatus.INEFFICIENT,
                PromptEfficiencyStatus.CRITICAL,
            }
        ]

    def to_dict(self) -> dict[str, Any]:
        self.recalculate()
        data = asdict(self)
        data["status"] = self.status.value
        data["analyses"] = [
            analysis.to_dict()
            for analysis in self.analyses
        ]
        return data


def worst_prompt_status(
    statuses: list[PromptEfficiencyStatus | str],
) -> PromptEfficiencyStatus:
    priority = {
        PromptEfficiencyStatus.UNKNOWN: 0,
        PromptEfficiencyStatus.EFFICIENT: 1,
        PromptEfficiencyStatus.ACCEPTABLE: 2,
        PromptEfficiencyStatus.INEFFICIENT: 3,
        PromptEfficiencyStatus.CRITICAL: 4,
    }

    normalized = [
        PromptEfficiencyStatus.normalize(status)
        for status in statuses
    ]

    if not normalized:
        return PromptEfficiencyStatus.UNKNOWN

    return max(
        normalized,
        key=lambda status: priority[status],
    )


def get_prompt_intelligence_models_info() -> dict[str, Any]:
    return {
        "component": "prompt_intelligence_models",
        "version": "0.9",
        "statuses": [
            status.value
            for status in PromptEfficiencyStatus
        ],
        "models": [
            "PromptMetric",
            "PromptAnalysis",
            "PromptIntelligenceReport",
        ],
        "serializable": True,
        "runtime_models_modified": False,
        "next_component": (
            "prompt_intelligence_analyzer"
        ),
    }


def _non_negative_int(value: Any) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return 0

    return max(number, 0)


def _non_negative_float(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0

    return round(max(number, 0.0), 6)


def _bounded_float(
    value: Any,
    minimum: float,
    maximum: float,
) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return minimum

    return round(
        min(max(number, minimum), maximum),
        6,
    )


def _unique_strings(
    values: list[Any] | None,
) -> list[str]:
    result: list[str] = []

    for value in values or []:
        item = str(value or "").strip()

        if item and item not in result:
            result.append(item)

    return result