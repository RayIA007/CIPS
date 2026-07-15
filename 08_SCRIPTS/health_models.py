"""
=========================================================
Proyecto : CIPS
Release  : 0.8
Build    : 064
Archivo  : health_models.py
Estado   : RELEASE
=========================================================

Define los contratos de datos del Runtime Health Monitor.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class HealthStatus(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNHEALTHY = "UNHEALTHY"
    UNKNOWN = "UNKNOWN"

    @classmethod
    def normalize(cls, value: Any) -> "HealthStatus":
        if isinstance(value, cls):
            return value
        normalized = str(value or "").strip().upper()
        for status in cls:
            if status.value == normalized:
                return status
        return cls.UNKNOWN


@dataclass
class HealthIndicator:
    indicator_id: str
    name: str
    status: HealthStatus
    value: Any = None
    unit: str = ""
    threshold_warning: Any = None
    threshold_critical: Any = None
    message: str = ""
    recommendation: str = ""
    severity: int = 0
    critical: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.indicator_id = str(self.indicator_id or "").strip()
        self.name = str(self.name or "").strip()
        self.status = HealthStatus.normalize(self.status)
        self.unit = str(self.unit or "").strip()
        self.message = str(self.message or "").strip()
        self.recommendation = str(self.recommendation or "").strip()
        self.severity = self._normalize_severity(self.severity)
        self.critical = bool(self.critical)
        self.metadata = dict(self.metadata or {})

    def is_problem(self) -> bool:
        return self.status in {HealthStatus.DEGRADED, HealthStatus.UNHEALTHY}

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value
        return data

    @staticmethod
    def _normalize_severity(value: Any) -> int:
        try:
            severity = int(value)
        except (TypeError, ValueError):
            return 0
        return min(max(severity, 0), 100)


@dataclass
class ComponentHealth:
    component: str
    status: HealthStatus
    category: str = "runtime"
    events_total: int = 0
    successful_events: int = 0
    failed_events: int = 0
    success_rate: float = 0.0
    failure_rate: float = 0.0
    average_duration_seconds: float = 0.0
    maximum_duration_seconds: float = 0.0
    retry_attempts: int = 0
    retry_count: int = 0
    exhausted_events: int = 0
    recovered_events: int = 0
    total_tokens: int = 0
    estimated_cost: float = 0.0
    currency: str = "USD"
    indicators: list[HealthIndicator] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.component = str(self.component or "").strip()
        self.status = HealthStatus.normalize(self.status)
        self.category = str(self.category or "runtime").strip().lower()
        self.events_total = self._non_negative_int(self.events_total)
        self.successful_events = self._non_negative_int(self.successful_events)
        self.failed_events = self._non_negative_int(self.failed_events)
        self.average_duration_seconds = self._non_negative_float(self.average_duration_seconds)
        self.maximum_duration_seconds = self._non_negative_float(self.maximum_duration_seconds)
        self.retry_attempts = self._non_negative_int(self.retry_attempts)
        self.retry_count = self._non_negative_int(self.retry_count)
        self.exhausted_events = self._non_negative_int(self.exhausted_events)
        self.recovered_events = self._non_negative_int(self.recovered_events)
        self.total_tokens = self._non_negative_int(self.total_tokens)
        self.estimated_cost = self._non_negative_float(self.estimated_cost)
        self.currency = str(self.currency or "USD").strip().upper()
        self.indicators = [i if isinstance(i, HealthIndicator) else HealthIndicator(**i) for i in self.indicators]
        self.warnings = [str(item) for item in (self.warnings or [])]
        self.errors = [str(item) for item in (self.errors or [])]
        self.metadata = dict(self.metadata or {})
        self.recalculate_rates()

    def recalculate_rates(self) -> None:
        if self.events_total <= 0:
            self.success_rate = 0.0
            self.failure_rate = 0.0
            return
        self.success_rate = round((self.successful_events / self.events_total) * 100, 2)
        self.failure_rate = round((self.failed_events / self.events_total) * 100, 2)

    def add_indicator(self, indicator: HealthIndicator) -> None:
        if not isinstance(indicator, HealthIndicator):
            raise TypeError("indicator debe ser HealthIndicator.")
        self.indicators.append(indicator)
        self.status = worst_health_status([self.status, indicator.status])

    def problem_indicators(self) -> list[HealthIndicator]:
        return [indicator for indicator in self.indicators if indicator.is_problem()]

    def to_dict(self) -> dict[str, Any]:
        return {
            "component": self.component,
            "status": self.status.value,
            "category": self.category,
            "events_total": self.events_total,
            "successful_events": self.successful_events,
            "failed_events": self.failed_events,
            "success_rate": self.success_rate,
            "failure_rate": self.failure_rate,
            "average_duration_seconds": self.average_duration_seconds,
            "maximum_duration_seconds": self.maximum_duration_seconds,
            "retry_attempts": self.retry_attempts,
            "retry_count": self.retry_count,
            "exhausted_events": self.exhausted_events,
            "recovered_events": self.recovered_events,
            "total_tokens": self.total_tokens,
            "estimated_cost": self.estimated_cost,
            "currency": self.currency,
            "indicators": [indicator.to_dict() for indicator in self.indicators],
            "warnings": list(self.warnings),
            "errors": list(self.errors),
            "metadata": dict(self.metadata),
        }

    @staticmethod
    def _non_negative_int(value: Any) -> int:
        try:
            number = int(value)
        except (TypeError, ValueError):
            return 0
        return max(number, 0)

    @staticmethod
    def _non_negative_float(value: Any) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return 0.0
        return round(max(number, 0.0), 6)


@dataclass
class RuntimeHealthReport:
    report_id: str
    generated_at: str
    status: HealthStatus
    project_id: str = ""
    scope: str = "project"
    events_total: int = 0
    successful_events: int = 0
    failed_events: int = 0
    success_rate: float = 0.0
    failure_rate: float = 0.0
    total_duration_seconds: float = 0.0
    average_duration_seconds: float = 0.0
    total_tokens: int = 0
    retry_count: int = 0
    exhausted_events: int = 0
    recovered_events: int = 0
    components: list[ComponentHealth] = field(default_factory=list)
    indicators: list[HealthIndicator] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.report_id = str(self.report_id or "").strip()
        self.generated_at = str(self.generated_at or "").strip()
        self.status = HealthStatus.normalize(self.status)
        self.project_id = str(self.project_id or "").strip()
        self.scope = str(self.scope or "project").strip().lower()
        self.events_total = ComponentHealth._non_negative_int(self.events_total)
        self.successful_events = ComponentHealth._non_negative_int(self.successful_events)
        self.failed_events = ComponentHealth._non_negative_int(self.failed_events)
        self.total_duration_seconds = ComponentHealth._non_negative_float(self.total_duration_seconds)
        self.average_duration_seconds = ComponentHealth._non_negative_float(self.average_duration_seconds)
        self.total_tokens = ComponentHealth._non_negative_int(self.total_tokens)
        self.retry_count = ComponentHealth._non_negative_int(self.retry_count)
        self.exhausted_events = ComponentHealth._non_negative_int(self.exhausted_events)
        self.recovered_events = ComponentHealth._non_negative_int(self.recovered_events)
        self.components = [c if isinstance(c, ComponentHealth) else ComponentHealth(**c) for c in self.components]
        self.indicators = [i if isinstance(i, HealthIndicator) else HealthIndicator(**i) for i in self.indicators]
        self.recommendations = self._unique_strings(self.recommendations)
        self.warnings = self._unique_strings(self.warnings)
        self.errors = self._unique_strings(self.errors)
        self.metadata = dict(self.metadata or {})
        self.recalculate_rates()

    def recalculate_rates(self) -> None:
        if self.events_total <= 0:
            self.success_rate = 0.0
            self.failure_rate = 0.0
            return
        self.success_rate = round((self.successful_events / self.events_total) * 100, 2)
        self.failure_rate = round((self.failed_events / self.events_total) * 100, 2)

    def recalculate_status(self) -> HealthStatus:
        statuses = [component.status for component in self.components]
        statuses.extend(indicator.status for indicator in self.indicators)
        if statuses:
            self.status = worst_health_status(statuses)
        elif self.events_total <= 0:
            self.status = HealthStatus.UNKNOWN
        return self.status

    def add_component(self, component: ComponentHealth) -> None:
        if not isinstance(component, ComponentHealth):
            raise TypeError("component debe ser ComponentHealth.")
        self.components.append(component)
        self.recalculate_status()

    def add_indicator(self, indicator: HealthIndicator) -> None:
        if not isinstance(indicator, HealthIndicator):
            raise TypeError("indicator debe ser HealthIndicator.")
        self.indicators.append(indicator)
        if indicator.recommendation:
            self.recommendations = self._unique_strings([*self.recommendations, indicator.recommendation])
        self.recalculate_status()

    def unhealthy_components(self) -> list[ComponentHealth]:
        return [component for component in self.components if component.status == HealthStatus.UNHEALTHY]

    def degraded_components(self) -> list[ComponentHealth]:
        return [component for component in self.components if component.status == HealthStatus.DEGRADED]

    def to_dict(self) -> dict[str, Any]:
        self.recalculate_rates()
        self.recalculate_status()
        return {
            "report_id": self.report_id,
            "generated_at": self.generated_at,
            "status": self.status.value,
            "project_id": self.project_id,
            "scope": self.scope,
            "events_total": self.events_total,
            "successful_events": self.successful_events,
            "failed_events": self.failed_events,
            "success_rate": self.success_rate,
            "failure_rate": self.failure_rate,
            "total_duration_seconds": self.total_duration_seconds,
            "average_duration_seconds": self.average_duration_seconds,
            "total_tokens": self.total_tokens,
            "retry_count": self.retry_count,
            "exhausted_events": self.exhausted_events,
            "recovered_events": self.recovered_events,
            "components": [component.to_dict() for component in self.components],
            "indicators": [indicator.to_dict() for indicator in self.indicators],
            "recommendations": list(self.recommendations),
            "warnings": list(self.warnings),
            "errors": list(self.errors),
            "metadata": dict(self.metadata),
        }

    @staticmethod
    def _unique_strings(values: list[Any] | None) -> list[str]:
        normalized: list[str] = []
        for value in values or []:
            item = str(value or "").strip()
            if item and item not in normalized:
                normalized.append(item)
        return normalized


def worst_health_status(statuses: list[HealthStatus | str]) -> HealthStatus:
    priority = {
        HealthStatus.UNKNOWN: 0,
        HealthStatus.HEALTHY: 1,
        HealthStatus.DEGRADED: 2,
        HealthStatus.UNHEALTHY: 3,
    }
    normalized = [HealthStatus.normalize(status) for status in statuses]
    if not normalized:
        return HealthStatus.UNKNOWN
    return max(normalized, key=lambda status: priority[status])


def get_health_models_info() -> dict[str, Any]:
    return {
        "component": "health_models",
        "version": "0.8",
        "statuses": [status.value for status in HealthStatus],
        "models": ["HealthIndicator", "ComponentHealth", "RuntimeHealthReport"],
        "serializable": True,
        "runtime_models_modified": False,
        "next_component": "health_analyzer",
    }