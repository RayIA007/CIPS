"""
=========================================================
Proyecto : CIPS
Release  : 0.9
Build    : 078
Archivo  : project_intelligence_models.py
Estado   : RELEASE
=========================================================

Define los contratos de datos del Project Intelligence Report.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class IntelligenceStatus(str, Enum):
    EXCELLENT = "EXCELLENT"
    GOOD = "GOOD"
    ATTENTION = "ATTENTION"
    CRITICAL = "CRITICAL"
    UNKNOWN = "UNKNOWN"

    @classmethod
    def normalize(cls, value: Any) -> "IntelligenceStatus":
        if isinstance(value, cls):
            return value

        normalized = str(value or "").strip().upper()

        for status in cls:
            if status.value == normalized:
                return status

        return cls.UNKNOWN


class FindingType(str, Enum):
    STRENGTH = "STRENGTH"
    OPPORTUNITY = "OPPORTUNITY"
    RISK = "RISK"
    CRITICAL_RISK = "CRITICAL_RISK"
    INFORMATION = "INFORMATION"

    @classmethod
    def normalize(cls, value: Any) -> "FindingType":
        if isinstance(value, cls):
            return value

        normalized = str(value or "").strip().upper()

        for finding_type in cls:
            if finding_type.value == normalized:
                return finding_type

        return cls.INFORMATION


@dataclass
class ProjectKPI:
    kpi_id: str
    name: str
    value: float

    status: IntelligenceStatus = IntelligenceStatus.UNKNOWN
    unit: str = "score"
    minimum: float = 0.0
    maximum: float = 100.0
    weight: float = 1.0
    trend: str = "STABLE"
    message: str = ""
    recommendation: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.kpi_id = str(self.kpi_id or "").strip()
        self.name = str(self.name or "").strip()
        self.minimum = self._safe_float(self.minimum, 0.0)
        self.maximum = self._safe_float(self.maximum, 100.0)

        if self.maximum <= self.minimum:
            self.maximum = self.minimum + 100.0

        self.value = self._bounded_float(
            self.value,
            self.minimum,
            self.maximum,
        )
        self.status = IntelligenceStatus.normalize(self.status)
        self.unit = str(self.unit or "").strip()
        self.weight = self._non_negative_float(self.weight)
        self.trend = str(self.trend or "STABLE").strip().upper()

        if self.trend not in {
            "IMPROVING",
            "STABLE",
            "DEGRADING",
            "UNKNOWN",
        }:
            self.trend = "UNKNOWN"

        self.message = str(self.message or "").strip()
        self.recommendation = str(
            self.recommendation or ""
        ).strip()
        self.metadata = dict(self.metadata or {})

        if self.status == IntelligenceStatus.UNKNOWN:
            self.status = intelligence_status_from_score(
                self.normalized_score()
            )

    def normalized_score(self) -> float:
        range_size = self.maximum - self.minimum

        if range_size <= 0:
            return 0.0

        return round(
            ((self.value - self.minimum) / range_size) * 100,
            2,
        )

    def weighted_score(self) -> float:
        return round(
            self.normalized_score() * self.weight,
            6,
        )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value
        data["normalized_score"] = self.normalized_score()
        return data

    @staticmethod
    def _safe_float(value: Any, default: float) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
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

    @staticmethod
    def _non_negative_float(value: Any) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return 0.0

        return round(max(number, 0.0), 6)


@dataclass
class ExecutiveFinding:
    finding_id: str
    title: str
    description: str
    finding_type: FindingType

    priority: str = "MEDIUM"
    stage: str = ""
    component: str = ""
    impact_score: float = 0.0
    confidence_score: float = 0.0
    evidence: list[str] = field(default_factory=list)
    recommendation: str = ""
    related_kpis: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.finding_id = str(self.finding_id or "").strip()
        self.title = str(self.title or "").strip()
        self.description = str(self.description or "").strip()
        self.finding_type = FindingType.normalize(self.finding_type)
        self.priority = str(
            self.priority or "MEDIUM"
        ).strip().upper()

        if self.priority not in {
            "LOW",
            "MEDIUM",
            "HIGH",
            "CRITICAL",
        }:
            self.priority = "MEDIUM"

        self.stage = str(self.stage or "").strip().lower()
        self.component = str(self.component or "").strip()
        self.impact_score = ProjectKPI._bounded_float(
            self.impact_score,
            0.0,
            100.0,
        )
        self.confidence_score = ProjectKPI._bounded_float(
            self.confidence_score,
            0.0,
            100.0,
        )
        self.evidence = unique_strings(self.evidence)
        self.recommendation = str(
            self.recommendation or ""
        ).strip()
        self.related_kpis = unique_strings(self.related_kpis)
        self.metadata = dict(self.metadata or {})

    def is_critical(self) -> bool:
        return (
            self.finding_type == FindingType.CRITICAL_RISK
            or self.priority == "CRITICAL"
        )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["finding_type"] = self.finding_type.value
        data["critical"] = self.is_critical()
        return data


@dataclass
class IntelligenceRecommendation:
    recommendation_id: str
    title: str
    description: str

    priority: str = "MEDIUM"
    action_type: str = ""
    stage: str = ""
    source: str = ""
    confidence_score: float = 0.0
    expected_improvement_percent: float = 0.0
    estimated_savings: float = 0.0
    currency: str = "USD"
    actionable: bool = True
    safe_for_automatic_apply: bool = False
    evidence: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.recommendation_id = str(
            self.recommendation_id or ""
        ).strip()
        self.title = str(self.title or "").strip()
        self.description = str(self.description or "").strip()
        self.priority = str(
            self.priority or "MEDIUM"
        ).strip().upper()

        if self.priority not in {
            "LOW",
            "MEDIUM",
            "HIGH",
            "CRITICAL",
        }:
            self.priority = "MEDIUM"

        self.action_type = str(
            self.action_type or ""
        ).strip().upper()
        self.stage = str(self.stage or "").strip().lower()
        self.source = str(self.source or "").strip()
        self.confidence_score = ProjectKPI._bounded_float(
            self.confidence_score,
            0.0,
            100.0,
        )
        self.expected_improvement_percent = (
            ProjectKPI._bounded_float(
                self.expected_improvement_percent,
                0.0,
                100.0,
            )
        )
        self.estimated_savings = ProjectKPI._non_negative_float(
            self.estimated_savings
        )
        self.currency = str(
            self.currency or "USD"
        ).strip().upper()
        self.actionable = bool(self.actionable)
        self.safe_for_automatic_apply = bool(
            self.safe_for_automatic_apply
        )
        self.evidence = unique_strings(self.evidence)
        self.metadata = dict(self.metadata or {})

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ProjectIntelligenceReport:
    report_id: str
    generated_at: str
    project_id: str

    status: IntelligenceStatus = IntelligenceStatus.UNKNOWN
    executive_summary: str = ""

    ai_project_score: float = 0.0
    health_score: float = 0.0
    prompt_efficiency_score: float = 0.0
    reliability_score: float = 0.0
    cost_efficiency_score: float = 0.0
    optimization_potential_score: float = 0.0

    telemetry_events: int = 0
    successful_events: int = 0
    failed_events: int = 0
    success_rate: float = 0.0

    total_tokens: int = 0
    total_cost: float = 0.0
    currency: str = "USD"

    total_duration_seconds: float = 0.0
    average_duration_seconds: float = 0.0

    retry_count: int = 0
    exhausted_events: int = 0
    recovered_events: int = 0

    kpis: list[ProjectKPI] = field(default_factory=list)
    findings: list[ExecutiveFinding] = field(default_factory=list)
    recommendations: list[
        IntelligenceRecommendation
    ] = field(default_factory=list)

    strengths: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    opportunities: list[str] = field(default_factory=list)
    stages: list[str] = field(default_factory=list)
    providers: list[str] = field(default_factory=list)
    models: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.report_id = str(self.report_id or "").strip()
        self.generated_at = str(self.generated_at or "").strip()
        self.project_id = str(self.project_id or "").strip()
        self.status = IntelligenceStatus.normalize(self.status)
        self.executive_summary = str(
            self.executive_summary or ""
        ).strip()

        for field_name in (
            "ai_project_score",
            "health_score",
            "prompt_efficiency_score",
            "reliability_score",
            "cost_efficiency_score",
            "optimization_potential_score",
            "success_rate",
        ):
            setattr(
                self,
                field_name,
                ProjectKPI._bounded_float(
                    getattr(self, field_name),
                    0.0,
                    100.0,
                ),
            )

        for field_name in (
            "telemetry_events",
            "successful_events",
            "failed_events",
            "total_tokens",
            "retry_count",
            "exhausted_events",
            "recovered_events",
        ):
            setattr(
                self,
                field_name,
                self._non_negative_int(
                    getattr(self, field_name)
                ),
            )

        for field_name in (
            "total_cost",
            "total_duration_seconds",
            "average_duration_seconds",
        ):
            setattr(
                self,
                field_name,
                ProjectKPI._non_negative_float(
                    getattr(self, field_name)
                ),
            )

        self.currency = str(
            self.currency or "USD"
        ).strip().upper()

        self.kpis = [
            item
            if isinstance(item, ProjectKPI)
            else ProjectKPI(**item)
            for item in self.kpis
            if isinstance(item, (ProjectKPI, dict))
        ]

        self.findings = [
            item
            if isinstance(item, ExecutiveFinding)
            else ExecutiveFinding(**item)
            for item in self.findings
            if isinstance(item, (ExecutiveFinding, dict))
        ]

        self.recommendations = [
            item
            if isinstance(item, IntelligenceRecommendation)
            else IntelligenceRecommendation(**item)
            for item in self.recommendations
            if isinstance(
                item,
                (IntelligenceRecommendation, dict),
            )
        ]

        self.strengths = unique_strings(self.strengths)
        self.risks = unique_strings(self.risks)
        self.opportunities = unique_strings(self.opportunities)
        self.stages = unique_strings(self.stages)
        self.providers = unique_strings(self.providers)
        self.models = unique_strings(self.models)
        self.warnings = unique_strings(self.warnings)
        self.errors = unique_strings(self.errors)
        self.metadata = dict(self.metadata or {})

        self.recalculate()

    def recalculate(self) -> None:
        self._sync_kpis()

        if self.kpis:
            total_weight = sum(
                kpi.weight
                for kpi in self.kpis
            )

            if total_weight > 0:
                self.ai_project_score = round(
                    sum(
                        kpi.weighted_score()
                        for kpi in self.kpis
                    )
                    / total_weight,
                    2,
                )

        self.status = intelligence_status_from_score(
            self.ai_project_score
        )

        if self.telemetry_events > 0:
            self.success_rate = round(
                (
                    self.successful_events
                    / self.telemetry_events
                )
                * 100,
                2,
            )

    def _sync_kpis(self) -> None:
        mapping = {
            "health_score": "health",
            "prompt_efficiency_score": "prompt_efficiency",
            "reliability_score": "reliability",
            "cost_efficiency_score": "cost_efficiency",
            "optimization_potential_score": (
                "optimization_potential"
            ),
        }

        names = {
            "health": "Health Score",
            "prompt_efficiency": "Prompt Efficiency Score",
            "reliability": "Reliability Score",
            "cost_efficiency": "Cost Efficiency Score",
            "optimization_potential": "Optimization Potential",
        }

        weights = {
            "health": 1.5,
            "prompt_efficiency": 1.2,
            "reliability": 1.5,
            "cost_efficiency": 1.0,
            "optimization_potential": 0.8,
        }

        existing = {
            kpi.kpi_id: kpi
            for kpi in self.kpis
        }

        for field_name, kpi_id in mapping.items():
            if kpi_id in existing:
                setattr(
                    self,
                    field_name,
                    existing[kpi_id].normalized_score(),
                )
                continue

            value = getattr(self, field_name)

            kpi = ProjectKPI(
                kpi_id=kpi_id,
                name=names[kpi_id],
                value=value,
                status=intelligence_status_from_score(value),
                weight=weights[kpi_id],
            )

            self.kpis.append(kpi)
            existing[kpi_id] = kpi

    def critical_findings(self) -> list[ExecutiveFinding]:
        return [
            finding
            for finding in self.findings
            if finding.is_critical()
        ]

    def top_recommendations(
        self,
        limit: int = 5,
    ) -> list[IntelligenceRecommendation]:
        rank = {
            "LOW": 1,
            "MEDIUM": 2,
            "HIGH": 3,
            "CRITICAL": 4,
        }

        ordered = sorted(
            self.recommendations,
            key=lambda recommendation: (
                -rank.get(recommendation.priority, 0),
                -recommendation.confidence_score,
                -recommendation.expected_improvement_percent,
                recommendation.recommendation_id,
            ),
        )

        return ordered[:max(int(limit), 0)]

    def to_dict(self) -> dict[str, Any]:
        self.recalculate()

        return {
            "report_id": self.report_id,
            "generated_at": self.generated_at,
            "project_id": self.project_id,
            "status": self.status.value,
            "executive_summary": self.executive_summary,
            "ai_project_score": self.ai_project_score,
            "health_score": self.health_score,
            "prompt_efficiency_score": (
                self.prompt_efficiency_score
            ),
            "reliability_score": self.reliability_score,
            "cost_efficiency_score": (
                self.cost_efficiency_score
            ),
            "optimization_potential_score": (
                self.optimization_potential_score
            ),
            "telemetry_events": self.telemetry_events,
            "successful_events": self.successful_events,
            "failed_events": self.failed_events,
            "success_rate": self.success_rate,
            "total_tokens": self.total_tokens,
            "total_cost": self.total_cost,
            "currency": self.currency,
            "total_duration_seconds": (
                self.total_duration_seconds
            ),
            "average_duration_seconds": (
                self.average_duration_seconds
            ),
            "retry_count": self.retry_count,
            "exhausted_events": self.exhausted_events,
            "recovered_events": self.recovered_events,
            "kpis": [kpi.to_dict() for kpi in self.kpis],
            "findings": [
                finding.to_dict()
                for finding in self.findings
            ],
            "recommendations": [
                recommendation.to_dict()
                for recommendation in self.recommendations
            ],
            "strengths": list(self.strengths),
            "risks": list(self.risks),
            "opportunities": list(self.opportunities),
            "stages": list(self.stages),
            "providers": list(self.providers),
            "models": list(self.models),
            "warnings": list(self.warnings),
            "errors": list(self.errors),
            "metadata": dict(self.metadata),
            "critical_findings_total": len(
                self.critical_findings()
            ),
        }

    @staticmethod
    def _non_negative_int(value: Any) -> int:
        try:
            number = int(value)
        except (TypeError, ValueError):
            return 0

        return max(number, 0)


def intelligence_status_from_score(
    score: Any,
) -> IntelligenceStatus:
    try:
        normalized = float(score)
    except (TypeError, ValueError):
        return IntelligenceStatus.UNKNOWN

    if normalized >= 90:
        return IntelligenceStatus.EXCELLENT
    if normalized >= 75:
        return IntelligenceStatus.GOOD
    if normalized >= 50:
        return IntelligenceStatus.ATTENTION
    return IntelligenceStatus.CRITICAL


def worst_intelligence_status(
    statuses: list[IntelligenceStatus | str],
) -> IntelligenceStatus:
    priority = {
        IntelligenceStatus.EXCELLENT: 0,
        IntelligenceStatus.GOOD: 1,
        IntelligenceStatus.ATTENTION: 2,
        IntelligenceStatus.CRITICAL: 3,
        IntelligenceStatus.UNKNOWN: 4,
    }

    normalized = [
        IntelligenceStatus.normalize(status)
        for status in statuses
    ]

    if not normalized:
        return IntelligenceStatus.UNKNOWN

    return max(
        normalized,
        key=lambda status: priority[status],
    )


def unique_strings(
    values: list[Any] | None,
) -> list[str]:
    result: list[str] = []

    for value in values or []:
        item = str(value or "").strip()

        if item and item not in result:
            result.append(item)

    return result


def get_project_intelligence_models_info() -> dict[str, Any]:
    return {
        "component": "project_intelligence_models",
        "version": "0.9",
        "statuses": [
            status.value
            for status in IntelligenceStatus
        ],
        "finding_types": [
            finding_type.value
            for finding_type in FindingType
        ],
        "models": [
            "ProjectKPI",
            "ExecutiveFinding",
            "IntelligenceRecommendation",
            "ProjectIntelligenceReport",
        ],
        "serializable": True,
        "runtime_models_modified": False,
        "next_component": "project_intelligence_engine",
    }