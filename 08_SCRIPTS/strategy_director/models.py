from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any
import time
import uuid


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


@dataclass(frozen=True, slots=True)
class StrategicObjective:
    name: str
    outcome: str
    metric: str
    target: str
    horizon: str


@dataclass(frozen=True, slots=True)
class AudienceProfile:
    name: str
    description: str
    needs: tuple[str, ...] = ()
    barriers: tuple[str, ...] = ()
    triggers: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ContentPillar:
    name: str
    purpose: str
    themes: tuple[str, ...] = ()
    formats: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class KPI:
    name: str
    definition: str
    cadence: str
    target: str


@dataclass(frozen=True, slots=True)
class RoadmapPhase:
    phase: str
    horizon: str
    outcomes: tuple[str, ...]
    deliverables: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class StrategyPackage:
    project_id: str
    topic: str
    business_objective: str
    executive_summary: str
    objectives: tuple[StrategicObjective, ...]
    audiences: tuple[AudienceProfile, ...]
    value_proposition: str
    positioning: str
    content_pillars: tuple[ContentPillar, ...]
    channels: tuple[str, ...]
    kpis: tuple[KPI, ...]
    roadmap: tuple[RoadmapPhase, ...]
    risks: tuple[str, ...]
    assumptions: tuple[str, ...]
    evidence: tuple[str, ...]
    source_references: tuple[str, ...]
    package_id: str = field(default_factory=lambda: _id("spkg"))
    schema_version: str = "1.0.0"
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class StrategyQualityScore:
    overall: float
    completeness: float
    evidence_coverage: float
    measurability: float
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class StrategyBuildResult:
    package: StrategyPackage
    score: StrategyQualityScore

    def to_dict(self) -> dict[str, Any]:
        return {"package": self.package.to_dict(), "score": self.score.to_dict()}
