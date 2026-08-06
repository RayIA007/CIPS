from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
import uuid

from .models import (
    AudienceSegment,
    CalendarCadence,
    ChannelPlan,
    ContentBrief,
    ContentObjective,
    ContentPillar,
)


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True, slots=True)
class EditorialPolicy:
    start_date: str
    end_date: str
    timezone_name: str
    cadence: CalendarCadence
    total_weeks: int
    target_pieces_per_week: int
    publishing_days: tuple[int, ...] = (0, 2, 4)
    preferred_time_windows: tuple[str, ...] = ("09:00-11:00",)

    def __post_init__(self) -> None:
        if not isinstance(self.cadence, CalendarCadence):
            object.__setattr__(self, "cadence", CalendarCadence(self.cadence))
        if self.total_weeks < 1:
            raise ValueError("total_weeks debe ser mayor o igual a 1")
        if self.target_pieces_per_week < 1:
            raise ValueError("target_pieces_per_week debe ser mayor o igual a 1")
        days = tuple(int(day) for day in self.publishing_days)
        if any(day < 0 or day > 6 for day in days):
            raise ValueError("publishing_days debe usar valores de 0 a 6")
        object.__setattr__(self, "publishing_days", days)
        object.__setattr__(self, "preferred_time_windows", tuple(self.preferred_time_windows))

    @property
    def target_piece_count(self) -> int:
        return self.total_weeks * self.target_pieces_per_week

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["cadence"] = self.cadence.value
        data["target_piece_count"] = self.target_piece_count
        return data


@dataclass(frozen=True, slots=True)
class ContentAllocation:
    pillar_id: str
    percentage: int
    rationale: str

    def __post_init__(self) -> None:
        if not 0 <= self.percentage <= 100:
            raise ValueError("percentage debe estar entre 0 y 100")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ContentPlan:
    brief: ContentBrief
    objectives: tuple[ContentObjective, ...]
    audiences: tuple[AudienceSegment, ...]
    pillars: tuple[ContentPillar, ...]
    channel_plans: tuple[ChannelPlan, ...]
    editorial_policy: EditorialPolicy
    allocations: tuple[ContentAllocation, ...]
    kpi_names: tuple[str, ...]
    roadmap_horizons: tuple[str, ...]
    risks: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()
    source_references: tuple[str, ...] = ()
    plan_id: str = field(default_factory=lambda: _id("cplan"))
    schema_version: str = "1.0.0"
    created_at: str = field(default_factory=_utc_now_iso)

    def __post_init__(self) -> None:
        object.__setattr__(self, "objectives", tuple(self.objectives))
        object.__setattr__(self, "audiences", tuple(self.audiences))
        object.__setattr__(self, "pillars", tuple(self.pillars))
        object.__setattr__(self, "channel_plans", tuple(self.channel_plans))
        object.__setattr__(self, "allocations", tuple(self.allocations))
        object.__setattr__(self, "kpi_names", tuple(self.kpi_names))
        object.__setattr__(self, "roadmap_horizons", tuple(self.roadmap_horizons))
        object.__setattr__(self, "risks", tuple(self.risks))
        object.__setattr__(self, "assumptions", tuple(self.assumptions))
        object.__setattr__(self, "source_references", tuple(self.source_references))

    def to_dict(self) -> dict[str, Any]:
        return {
            "brief": self.brief.to_dict(),
            "objectives": [item.to_dict() for item in self.objectives],
            "audiences": [item.to_dict() for item in self.audiences],
            "pillars": [item.to_dict() for item in self.pillars],
            "channel_plans": [item.to_dict() for item in self.channel_plans],
            "editorial_policy": self.editorial_policy.to_dict(),
            "allocations": [item.to_dict() for item in self.allocations],
            "kpi_names": list(self.kpi_names),
            "roadmap_horizons": list(self.roadmap_horizons),
            "risks": list(self.risks),
            "assumptions": list(self.assumptions),
            "source_references": list(self.source_references),
            "plan_id": self.plan_id,
            "schema_version": self.schema_version,
            "created_at": self.created_at,
        }


@dataclass(frozen=True, slots=True)
class PlanningQualityScore:
    overall: float
    strategy_coverage: float
    channel_readiness: float
    measurability: float
    allocation_integrity: float
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class PlanningBuildResult:
    plan: ContentPlan
    score: PlanningQualityScore

    def to_dict(self) -> dict[str, Any]:
        return {"plan": self.plan.to_dict(), "score": self.score.to_dict()}
