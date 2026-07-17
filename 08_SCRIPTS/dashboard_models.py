"""
=========================================================
Proyecto : CIPS
Release  : 0.9
Build    : 083
Archivo  : dashboard_models.py
Estado   : RELEASE
=========================================================

Define los contratos de datos del Executive Dashboard.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any
from uuid import uuid4


class DashboardStatus(str, Enum):
    EXCELLENT = "EXCELLENT"
    GOOD = "GOOD"
    ATTENTION = "ATTENTION"
    CRITICAL = "CRITICAL"
    UNKNOWN = "UNKNOWN"

    @classmethod
    def normalize(cls, value: Any) -> "DashboardStatus":
        if isinstance(value, cls):
            return value
        normalized = str(value or "").strip().upper()
        for status in cls:
            if status.value == normalized:
                return status
        return cls.UNKNOWN


class DashboardCardType(str, Enum):
    KPI = "KPI"
    METRIC = "METRIC"
    STATUS = "STATUS"
    COST = "COST"
    RISK = "RISK"
    RECOMMENDATION = "RECOMMENDATION"
    INFORMATION = "INFORMATION"

    @classmethod
    def normalize(cls, value: Any) -> "DashboardCardType":
        if isinstance(value, cls):
            return value
        normalized = str(value or "").strip().upper()
        for card_type in cls:
            if card_type.value == normalized:
                return card_type
        return cls.INFORMATION


class DashboardChartType(str, Enum):
    BAR = "BAR"
    LINE = "LINE"
    AREA = "AREA"
    PIE = "PIE"
    DONUT = "DONUT"
    RADAR = "RADAR"
    GAUGE = "GAUGE"
    TABLE = "TABLE"
    TIMELINE = "TIMELINE"

    @classmethod
    def normalize(cls, value: Any) -> "DashboardChartType":
        if isinstance(value, cls):
            return value
        normalized = str(value or "").strip().upper()
        for chart_type in cls:
            if chart_type.value == normalized:
                return chart_type
        return cls.TABLE


@dataclass
class DashboardCard:
    card_id: str
    title: str
    value: Any
    status: DashboardStatus = DashboardStatus.UNKNOWN
    card_type: DashboardCardType = DashboardCardType.KPI
    subtitle: str = ""
    unit: str = ""
    icon: str = ""
    accent: str = ""
    trend: str = "STABLE"
    trend_value: float = 0.0
    description: str = ""
    recommendation: str = ""
    priority: int = 0
    visible: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.card_id = str(
            self.card_id or f"CARD-{uuid4().hex.upper()}"
        ).strip()
        self.title = str(self.title or "").strip()
        self.status = DashboardStatus.normalize(self.status)
        self.card_type = DashboardCardType.normalize(self.card_type)
        self.subtitle = str(self.subtitle or "").strip()
        self.unit = str(self.unit or "").strip()
        self.icon = str(self.icon or "").strip()
        self.accent = str(self.accent or "").strip()
        self.trend = str(self.trend or "STABLE").strip().upper()
        if self.trend not in {
            "IMPROVING",
            "STABLE",
            "DEGRADING",
            "UNKNOWN",
        }:
            self.trend = "UNKNOWN"
        self.trend_value = _safe_float(self.trend_value, 0.0)
        self.description = str(self.description or "").strip()
        self.recommendation = str(
            self.recommendation or ""
        ).strip()
        self.priority = _non_negative_int(self.priority)
        self.visible = bool(self.visible)
        self.metadata = dict(self.metadata or {})

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value
        data["card_type"] = self.card_type.value
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DashboardCard":
        return cls(**dict(data or {}))


@dataclass
class DashboardSeries:
    series_id: str
    name: str
    values: list[float] = field(default_factory=list)
    labels: list[str] = field(default_factory=list)
    unit: str = ""
    chart_role: str = "primary"
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.series_id = str(
            self.series_id or f"SERIES-{uuid4().hex.upper()}"
        ).strip()
        self.name = str(self.name or "").strip()
        self.values = [
            _safe_float(value, 0.0)
            for value in (self.values or [])
        ]
        self.labels = unique_strings(self.labels)
        self.unit = str(self.unit or "").strip()
        self.chart_role = str(
            self.chart_role or "primary"
        ).strip().lower()
        self.metadata = dict(self.metadata or {})

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DashboardSeries":
        return cls(**dict(data or {}))


@dataclass
class DashboardChart:
    chart_id: str
    title: str
    chart_type: DashboardChartType
    series: list[DashboardSeries] = field(default_factory=list)
    subtitle: str = ""
    x_axis_label: str = ""
    y_axis_label: str = ""
    labels: list[str] = field(default_factory=list)
    status: DashboardStatus = DashboardStatus.UNKNOWN
    priority: int = 0
    visible: bool = True
    options: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.chart_id = str(
            self.chart_id or f"CHART-{uuid4().hex.upper()}"
        ).strip()
        self.title = str(self.title or "").strip()
        self.chart_type = DashboardChartType.normalize(self.chart_type)
        self.series = [
            item
            if isinstance(item, DashboardSeries)
            else DashboardSeries.from_dict(item)
            for item in self.series or []
            if isinstance(item, (DashboardSeries, dict))
        ]
        self.subtitle = str(self.subtitle or "").strip()
        self.x_axis_label = str(self.x_axis_label or "").strip()
        self.y_axis_label = str(self.y_axis_label or "").strip()
        self.labels = unique_strings(self.labels)
        self.status = DashboardStatus.normalize(self.status)
        self.priority = _non_negative_int(self.priority)
        self.visible = bool(self.visible)
        self.options = dict(self.options or {})
        self.metadata = dict(self.metadata or {})

    def total_points(self) -> int:
        return sum(len(series.values) for series in self.series)

    def to_dict(self) -> dict[str, Any]:
        return {
            "chart_id": self.chart_id,
            "title": self.title,
            "chart_type": self.chart_type.value,
            "series": [series.to_dict() for series in self.series],
            "subtitle": self.subtitle,
            "x_axis_label": self.x_axis_label,
            "y_axis_label": self.y_axis_label,
            "labels": list(self.labels),
            "status": self.status.value,
            "priority": self.priority,
            "visible": self.visible,
            "options": dict(self.options),
            "metadata": dict(self.metadata),
            "total_points": self.total_points(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DashboardChart":
        payload = dict(data or {})
        payload.pop("total_points", None)
        return cls(**payload)


@dataclass
class DashboardSection:
    section_id: str
    title: str
    status: DashboardStatus = DashboardStatus.UNKNOWN
    description: str = ""
    cards: list[DashboardCard] = field(default_factory=list)
    charts: list[DashboardChart] = field(default_factory=list)
    items: list[str] = field(default_factory=list)
    priority: int = 0
    collapsed: bool = False
    visible: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.section_id = str(
            self.section_id or f"SECTION-{uuid4().hex.upper()}"
        ).strip()
        self.title = str(self.title or "").strip()
        self.status = DashboardStatus.normalize(self.status)
        self.description = str(self.description or "").strip()
        self.cards = [
            item
            if isinstance(item, DashboardCard)
            else DashboardCard.from_dict(item)
            for item in self.cards or []
            if isinstance(item, (DashboardCard, dict))
        ]
        self.charts = [
            item
            if isinstance(item, DashboardChart)
            else DashboardChart.from_dict(item)
            for item in self.charts or []
            if isinstance(item, (DashboardChart, dict))
        ]
        self.items = unique_strings(self.items)
        self.priority = _non_negative_int(self.priority)
        self.collapsed = bool(self.collapsed)
        self.visible = bool(self.visible)
        self.metadata = dict(self.metadata or {})

    def to_dict(self) -> dict[str, Any]:
        return {
            "section_id": self.section_id,
            "title": self.title,
            "status": self.status.value,
            "description": self.description,
            "cards": [card.to_dict() for card in self.cards],
            "charts": [chart.to_dict() for chart in self.charts],
            "items": list(self.items),
            "priority": self.priority,
            "collapsed": self.collapsed,
            "visible": self.visible,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DashboardSection":
        return cls(**dict(data or {}))


@dataclass
class ExecutiveDashboard:
    dashboard_id: str
    generated_at: str
    project_id: str
    status: DashboardStatus = DashboardStatus.UNKNOWN
    title: str = "CIPS Executive Dashboard"
    executive_summary: str = ""
    cards: list[DashboardCard] = field(default_factory=list)
    charts: list[DashboardChart] = field(default_factory=list)
    sections: list[DashboardSection] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.dashboard_id = str(
            self.dashboard_id or f"DASHBOARD-{uuid4().hex.upper()}"
        ).strip()
        self.generated_at = str(self.generated_at or "").strip()
        self.project_id = str(self.project_id or "").strip()
        self.status = DashboardStatus.normalize(self.status)
        self.title = str(
            self.title or "CIPS Executive Dashboard"
        ).strip()
        self.executive_summary = str(
            self.executive_summary or ""
        ).strip()
        self.cards = [
            item
            if isinstance(item, DashboardCard)
            else DashboardCard.from_dict(item)
            for item in self.cards or []
            if isinstance(item, (DashboardCard, dict))
        ]
        self.charts = [
            item
            if isinstance(item, DashboardChart)
            else DashboardChart.from_dict(item)
            for item in self.charts or []
            if isinstance(item, (DashboardChart, dict))
        ]
        self.sections = [
            item
            if isinstance(item, DashboardSection)
            else DashboardSection.from_dict(item)
            for item in self.sections or []
            if isinstance(item, (DashboardSection, dict))
        ]
        self.warnings = unique_strings(self.warnings)
        self.errors = unique_strings(self.errors)
        self.metadata = dict(self.metadata or {})
        self.recalculate_status()

    def recalculate_status(self) -> DashboardStatus:
        statuses = [
            card.status
            for card in self.cards
            if card.visible
        ]
        statuses.extend(
            chart.status
            for chart in self.charts
            if chart.visible
        )
        statuses.extend(
            section.status
            for section in self.sections
            if section.visible
        )
        if statuses:
            self.status = worst_dashboard_status(statuses)
        return self.status

    def visible_cards(self) -> list[DashboardCard]:
        return sorted(
            [card for card in self.cards if card.visible],
            key=lambda card: (-card.priority, card.title),
        )

    def visible_charts(self) -> list[DashboardChart]:
        return sorted(
            [chart for chart in self.charts if chart.visible],
            key=lambda chart: (-chart.priority, chart.title),
        )

    def visible_sections(self) -> list[DashboardSection]:
        return sorted(
            [
                section
                for section in self.sections
                if section.visible
            ],
            key=lambda section: (-section.priority, section.title),
        )

    def to_dict(self) -> dict[str, Any]:
        self.recalculate_status()
        return {
            "dashboard_id": self.dashboard_id,
            "generated_at": self.generated_at,
            "project_id": self.project_id,
            "status": self.status.value,
            "title": self.title,
            "executive_summary": self.executive_summary,
            "cards": [card.to_dict() for card in self.cards],
            "charts": [chart.to_dict() for chart in self.charts],
            "sections": [
                section.to_dict()
                for section in self.sections
            ],
            "warnings": list(self.warnings),
            "errors": list(self.errors),
            "metadata": dict(self.metadata),
            "cards_total": len(self.cards),
            "charts_total": len(self.charts),
            "sections_total": len(self.sections),
            "visible_cards_total": len(self.visible_cards()),
            "visible_charts_total": len(self.visible_charts()),
            "visible_sections_total": len(self.visible_sections()),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ExecutiveDashboard":
        payload = dict(data or {})
        for key in (
            "cards_total",
            "charts_total",
            "sections_total",
            "visible_cards_total",
            "visible_charts_total",
            "visible_sections_total",
        ):
            payload.pop(key, None)
        return cls(**payload)


def dashboard_status_from_score(score: Any) -> DashboardStatus:
    try:
        normalized = float(score)
    except (TypeError, ValueError):
        return DashboardStatus.UNKNOWN

    if normalized >= 90:
        return DashboardStatus.EXCELLENT
    if normalized >= 75:
        return DashboardStatus.GOOD
    if normalized >= 50:
        return DashboardStatus.ATTENTION
    return DashboardStatus.CRITICAL


def worst_dashboard_status(
    statuses: list[DashboardStatus | str],
) -> DashboardStatus:
    rank = {
        DashboardStatus.EXCELLENT: 0,
        DashboardStatus.GOOD: 1,
        DashboardStatus.ATTENTION: 2,
        DashboardStatus.CRITICAL: 3,
        DashboardStatus.UNKNOWN: 4,
    }
    normalized = [
        DashboardStatus.normalize(status)
        for status in statuses
    ]
    if not normalized:
        return DashboardStatus.UNKNOWN
    return max(normalized, key=lambda status: rank[status])


def unique_strings(values: list[Any] | None) -> list[str]:
    result: list[str] = []
    for value in values or []:
        item = str(value or "").strip()
        if item and item not in result:
            result.append(item)
    return result


def _safe_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _non_negative_int(value: Any) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return 0
    return max(number, 0)


def get_dashboard_models_info() -> dict[str, Any]:
    return {
        "component": "dashboard_models",
        "version": "0.9",
        "statuses": [
            status.value
            for status in DashboardStatus
        ],
        "card_types": [
            card_type.value
            for card_type in DashboardCardType
        ],
        "chart_types": [
            chart_type.value
            for chart_type in DashboardChartType
        ],
        "models": [
            "DashboardCard",
            "DashboardSeries",
            "DashboardChart",
            "DashboardSection",
            "ExecutiveDashboard",
        ],
        "serializable": True,
        "supports_from_dict": True,
        "runtime_models_modified": False,
        "next_component": "dashboard_generator",
    }