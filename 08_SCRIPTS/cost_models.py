"""
=========================================================
Proyecto : CIPS
Release  : 0.9
Build    : 072
Archivo  : cost_models.py
Estado   : RELEASE
=========================================================

Contratos de datos para Cost & Token Analytics.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Iterable


class CostStatus(str, Enum):
    CALCULATED = "CALCULATED"
    FREE_TIER = "FREE_TIER"
    PARTIAL = "PARTIAL"
    UNKNOWN_PRICING = "UNKNOWN_PRICING"
    INVALID = "INVALID"

    @classmethod
    def normalize(cls, value: Any) -> "CostStatus":
        if isinstance(value, cls):
            return value
        normalized = str(value or "").strip().upper()
        for status in cls:
            if status.value == normalized:
                return status
        return cls.INVALID


@dataclass
class TokenUsageBreakdown:
    prompt_tokens: int = 0
    response_tokens: int = 0
    thinking_tokens: int = 0
    cached_input_tokens: int = 0
    cache_write_tokens: int = 0
    total_tokens: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in (
            "prompt_tokens", "response_tokens", "thinking_tokens",
            "cached_input_tokens", "cache_write_tokens", "total_tokens",
        ):
            setattr(self, name, _non_negative_int(getattr(self, name)))
        if self.total_tokens == 0:
            self.total_tokens = (
                self.prompt_tokens
                + self.response_tokens
                + self.thinking_tokens
            )
        self.metadata = dict(self.metadata or {})

    def billable_input_tokens(self) -> int:
        return max(self.prompt_tokens - self.cached_input_tokens, 0)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CostBreakdown:
    status: CostStatus
    currency: str = "USD"
    token_unit: int = 1_000_000
    input_rate: float = 0.0
    output_rate: float = 0.0
    thinking_rate: float = 0.0
    cached_input_rate: float = 0.0
    cache_write_rate: float = 0.0
    input_cost: float = 0.0
    output_cost: float = 0.0
    thinking_cost: float = 0.0
    cached_input_cost: float = 0.0
    cache_write_cost: float = 0.0
    tool_cost: float = 0.0
    other_cost: float = 0.0
    total_cost: float = 0.0
    billing_tier: str = ""
    billing_mode: str = ""
    pricing_source: str = ""
    pricing_last_verified: str = ""
    pricing_is_estimate: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.status = CostStatus.normalize(self.status)
        self.currency = str(self.currency or "USD").strip().upper()
        self.token_unit = _positive_int(self.token_unit, 1_000_000)
        for name in (
            "input_rate", "output_rate", "thinking_rate",
            "cached_input_rate", "cache_write_rate",
            "input_cost", "output_cost", "thinking_cost",
            "cached_input_cost", "cache_write_cost",
            "tool_cost", "other_cost", "total_cost",
        ):
            setattr(self, name, _non_negative_float(getattr(self, name)))
        self.billing_tier = str(self.billing_tier or "").strip().lower()
        self.billing_mode = str(self.billing_mode or "").strip().lower()
        self.pricing_source = str(self.pricing_source or "").strip()
        self.pricing_last_verified = str(self.pricing_last_verified or "").strip()
        self.pricing_is_estimate = bool(self.pricing_is_estimate)
        self.metadata = dict(self.metadata or {})
        self.recalculate_total()

    def recalculate_total(self) -> float:
        self.total_cost = round(
            self.input_cost + self.output_cost + self.thinking_cost
            + self.cached_input_cost + self.cache_write_cost
            + self.tool_cost + self.other_cost,
            8,
        )
        return self.total_cost

    def is_free(self) -> bool:
        return self.status == CostStatus.FREE_TIER or self.total_cost == 0.0

    def to_dict(self) -> dict[str, Any]:
        self.recalculate_total()
        data = asdict(self)
        data["status"] = self.status.value
        return data


@dataclass
class StageCostAnalysis:
    analysis_id: str
    project_id: str
    stage: str
    provider: str
    model: str
    status: CostStatus
    token_usage: TokenUsageBreakdown = field(default_factory=TokenUsageBreakdown)
    cost: CostBreakdown = field(
        default_factory=lambda: CostBreakdown(status=CostStatus.INVALID)
    )
    duration_seconds: float = 0.0
    retry_count: int = 0
    retry_exhausted: bool = False
    succeeded_after_retry: bool = False
    cost_per_1k_total_tokens: float = 0.0
    cost_per_second: float = 0.0
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.analysis_id = str(self.analysis_id or "").strip()
        self.project_id = str(self.project_id or "").strip()
        self.stage = str(self.stage or "").strip().lower()
        self.provider = str(self.provider or "").strip().lower()
        self.model = str(self.model or "").strip()
        self.status = CostStatus.normalize(self.status)
        if isinstance(self.token_usage, dict):
            self.token_usage = TokenUsageBreakdown(**self.token_usage)
        if not isinstance(self.token_usage, TokenUsageBreakdown):
            self.token_usage = TokenUsageBreakdown()
        if isinstance(self.cost, dict):
            self.cost = CostBreakdown(**self.cost)
        if not isinstance(self.cost, CostBreakdown):
            self.cost = CostBreakdown(status=CostStatus.INVALID)
        self.duration_seconds = _non_negative_float(self.duration_seconds)
        self.retry_count = _non_negative_int(self.retry_count)
        self.retry_exhausted = bool(self.retry_exhausted)
        self.succeeded_after_retry = bool(self.succeeded_after_retry)
        self.warnings = _unique_strings(self.warnings)
        self.errors = _unique_strings(self.errors)
        self.metadata = dict(self.metadata or {})
        self.recalculate_efficiency_metrics()

    def recalculate_efficiency_metrics(self) -> None:
        if self.token_usage.total_tokens > 0:
            self.cost_per_1k_total_tokens = round(
                self.cost.total_cost / self.token_usage.total_tokens * 1000,
                8,
            )
        else:
            self.cost_per_1k_total_tokens = 0.0
        if self.duration_seconds > 0:
            self.cost_per_second = round(
                self.cost.total_cost / self.duration_seconds,
                8,
            )
        else:
            self.cost_per_second = 0.0

    def to_dict(self) -> dict[str, Any]:
        self.recalculate_efficiency_metrics()
        return {
            "analysis_id": self.analysis_id,
            "project_id": self.project_id,
            "stage": self.stage,
            "provider": self.provider,
            "model": self.model,
            "status": self.status.value,
            "token_usage": self.token_usage.to_dict(),
            "cost": self.cost.to_dict(),
            "duration_seconds": self.duration_seconds,
            "retry_count": self.retry_count,
            "retry_exhausted": self.retry_exhausted,
            "succeeded_after_retry": self.succeeded_after_retry,
            "cost_per_1k_total_tokens": self.cost_per_1k_total_tokens,
            "cost_per_second": self.cost_per_second,
            "warnings": list(self.warnings),
            "errors": list(self.errors),
            "metadata": dict(self.metadata),
        }


@dataclass
class ProjectCostReport:
    report_id: str
    generated_at: str
    project_id: str
    status: CostStatus
    scope: str = "project"
    currency: str = "USD"
    analyses: list[StageCostAnalysis] = field(default_factory=list)
    analyses_total: int = 0
    calculated_analyses: int = 0
    free_tier_analyses: int = 0
    partial_analyses: int = 0
    unknown_pricing_analyses: int = 0
    invalid_analyses: int = 0
    total_prompt_tokens: int = 0
    total_response_tokens: int = 0
    total_thinking_tokens: int = 0
    total_cached_input_tokens: int = 0
    total_tokens: int = 0
    total_input_cost: float = 0.0
    total_output_cost: float = 0.0
    total_thinking_cost: float = 0.0
    total_cached_input_cost: float = 0.0
    total_cache_write_cost: float = 0.0
    total_tool_cost: float = 0.0
    total_other_cost: float = 0.0
    total_cost: float = 0.0
    average_cost_per_stage: float = 0.0
    average_cost_per_1k_tokens: float = 0.0
    providers: list[str] = field(default_factory=list)
    models: list[str] = field(default_factory=list)
    stages: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.report_id = str(self.report_id or "").strip()
        self.generated_at = str(self.generated_at or "").strip()
        self.project_id = str(self.project_id or "").strip()
        self.status = CostStatus.normalize(self.status)
        self.scope = str(self.scope or "project").strip().lower()
        self.currency = str(self.currency or "USD").strip().upper()
        normalized: list[StageCostAnalysis] = []
        for analysis in self.analyses:
            if isinstance(analysis, StageCostAnalysis):
                normalized.append(analysis)
            elif isinstance(analysis, dict):
                normalized.append(StageCostAnalysis(**analysis))
        self.analyses = normalized
        self.warnings = _unique_strings(self.warnings)
        self.errors = _unique_strings(self.errors)
        self.metadata = dict(self.metadata or {})
        self.recalculate()

    def add_analysis(self, analysis: StageCostAnalysis) -> None:
        if not isinstance(analysis, StageCostAnalysis):
            raise TypeError("analysis debe ser StageCostAnalysis.")
        self.analyses.append(analysis)
        self.warnings = _unique_strings([*self.warnings, *analysis.warnings])
        self.errors = _unique_strings([*self.errors, *analysis.errors])
        self.recalculate()

    def recalculate(self) -> None:
        self.analyses_total = len(self.analyses)
        statuses = [analysis.status for analysis in self.analyses]
        self.calculated_analyses = statuses.count(CostStatus.CALCULATED)
        self.free_tier_analyses = statuses.count(CostStatus.FREE_TIER)
        self.partial_analyses = statuses.count(CostStatus.PARTIAL)
        self.unknown_pricing_analyses = statuses.count(CostStatus.UNKNOWN_PRICING)
        self.invalid_analyses = statuses.count(CostStatus.INVALID)

        self.total_prompt_tokens = sum(a.token_usage.prompt_tokens for a in self.analyses)
        self.total_response_tokens = sum(a.token_usage.response_tokens for a in self.analyses)
        self.total_thinking_tokens = sum(a.token_usage.thinking_tokens for a in self.analyses)
        self.total_cached_input_tokens = sum(a.token_usage.cached_input_tokens for a in self.analyses)
        self.total_tokens = sum(a.token_usage.total_tokens for a in self.analyses)

        self.total_input_cost = round(sum(a.cost.input_cost for a in self.analyses), 8)
        self.total_output_cost = round(sum(a.cost.output_cost for a in self.analyses), 8)
        self.total_thinking_cost = round(sum(a.cost.thinking_cost for a in self.analyses), 8)
        self.total_cached_input_cost = round(sum(a.cost.cached_input_cost for a in self.analyses), 8)
        self.total_cache_write_cost = round(sum(a.cost.cache_write_cost for a in self.analyses), 8)
        self.total_tool_cost = round(sum(a.cost.tool_cost for a in self.analyses), 8)
        self.total_other_cost = round(sum(a.cost.other_cost for a in self.analyses), 8)
        self.total_cost = round(sum(a.cost.total_cost for a in self.analyses), 8)

        self.average_cost_per_stage = round(
            self.total_cost / self.analyses_total,
            8,
        ) if self.analyses_total else 0.0
        self.average_cost_per_1k_tokens = round(
            self.total_cost / self.total_tokens * 1000,
            8,
        ) if self.total_tokens else 0.0

        self.providers = _unique_values(a.provider for a in self.analyses)
        self.models = _unique_values(a.model for a in self.analyses)
        self.stages = _unique_values(a.stage for a in self.analyses)
        self.status = worst_cost_status(statuses)

    def to_dict(self) -> dict[str, Any]:
        self.recalculate()
        data = asdict(self)
        data["status"] = self.status.value
        data["analyses"] = [analysis.to_dict() for analysis in self.analyses]
        return data


def worst_cost_status(statuses: list[CostStatus | str]) -> CostStatus:
    priority = {
        CostStatus.CALCULATED: 0,
        CostStatus.FREE_TIER: 0,
        CostStatus.PARTIAL: 1,
        CostStatus.UNKNOWN_PRICING: 2,
        CostStatus.INVALID: 3,
    }
    normalized = [CostStatus.normalize(status) for status in statuses]
    if not normalized:
        return CostStatus.INVALID
    return max(normalized, key=lambda status: priority[status])


def get_cost_models_info() -> dict[str, Any]:
    return {
        "component": "cost_models",
        "version": "0.9",
        "statuses": [status.value for status in CostStatus],
        "models": [
            "TokenUsageBreakdown",
            "CostBreakdown",
            "StageCostAnalysis",
            "ProjectCostReport",
        ],
        "serializable": True,
        "runtime_models_modified": False,
        "next_component": "cost_analyzer",
    }


def _non_negative_int(value: Any) -> int:
    try:
        return max(int(value), 0)
    except (TypeError, ValueError):
        return 0


def _positive_int(value: Any, default: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return number if number > 0 else default


def _non_negative_float(value: Any) -> float:
    try:
        return round(max(float(value), 0.0), 8)
    except (TypeError, ValueError):
        return 0.0


def _unique_strings(values: Iterable[Any] | None) -> list[str]:
    return _unique_values(values or [])


def _unique_values(values: Iterable[Any]) -> list[str]:
    result: list[str] = []
    for value in values:
        item = str(value or "").strip()
        if item and item not in result:
            result.append(item)
    return result