from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from enum import Enum
from typing import Any, Iterable, Mapping
import uuid


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _tuple_str(values: Iterable[str] | None) -> tuple[str, ...]:
    if values is None:
        return ()
    return tuple(str(value).strip() for value in values if str(value).strip())


class StrEnum(str, Enum):
    def __str__(self) -> str:
        return self.value


class ContentStatus(StrEnum):
    IDEA = "idea"
    PLANNED = "planned"
    DRAFT = "draft"
    REVIEW = "review"
    APPROVED = "approved"
    SCHEDULED = "scheduled"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class ContentFormat(StrEnum):
    SHORT_VIDEO = "short_video"
    LONG_VIDEO = "long_video"
    CAROUSEL = "carousel"
    STATIC_IMAGE = "static_image"
    STORY = "story"
    ARTICLE = "article"
    NEWSLETTER = "newsletter"
    PODCAST = "podcast"
    LIVE = "live"
    THREAD = "thread"
    INFOGRAPHIC = "infographic"
    CASE_STUDY = "case_study"
    GUIDE = "guide"
    OTHER = "other"


class ContentIntent(StrEnum):
    AWARENESS = "awareness"
    EDUCATION = "education"
    CONSIDERATION = "consideration"
    CONVERSION = "conversion"
    RETENTION = "retention"
    COMMUNITY = "community"


class CTAType(StrEnum):
    ENGAGE = "engage"
    FOLLOW = "follow"
    SAVE = "save"
    SHARE = "share"
    COMMENT = "comment"
    CLICK = "click"
    REGISTER = "register"
    DOWNLOAD = "download"
    CONTACT = "contact"
    BUY = "buy"
    NONE = "none"


class CalendarCadence(StrEnum):
    DAILY = "daily"
    WEEKLY = "weekly"
    BIWEEKLY = "biweekly"
    MONTHLY = "monthly"
    CAMPAIGN = "campaign"


@dataclass(frozen=True, slots=True)
class ContentObjective:
    name: str
    intended_outcome: str
    metric: str
    target: str
    horizon: str
    objective_id: str = field(default_factory=lambda: _id("cobj"))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class AudienceSegment:
    name: str
    description: str
    needs: tuple[str, ...] = ()
    pain_points: tuple[str, ...] = ()
    objections: tuple[str, ...] = ()
    preferred_channels: tuple[str, ...] = ()
    audience_id: str = field(default_factory=lambda: _id("aud"))

    def __post_init__(self) -> None:
        object.__setattr__(self, "needs", _tuple_str(self.needs))
        object.__setattr__(self, "pain_points", _tuple_str(self.pain_points))
        object.__setattr__(self, "objections", _tuple_str(self.objections))
        object.__setattr__(self, "preferred_channels", _tuple_str(self.preferred_channels))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ContentPillar:
    name: str
    purpose: str
    themes: tuple[str, ...] = ()
    formats: tuple[ContentFormat, ...] = ()
    pillar_id: str = field(default_factory=lambda: _id("pillar"))

    def __post_init__(self) -> None:
        object.__setattr__(self, "themes", _tuple_str(self.themes))
        object.__setattr__(
            self,
            "formats",
            tuple(value if isinstance(value, ContentFormat) else ContentFormat(value) for value in self.formats),
        )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["formats"] = [item.value for item in self.formats]
        return data


@dataclass(frozen=True, slots=True)
class CallToAction:
    text: str
    type: CTAType
    destination: str | None = None
    tracking_code: str | None = None
    cta_id: str = field(default_factory=lambda: _id("cta"))

    def __post_init__(self) -> None:
        if not isinstance(self.type, CTAType):
            object.__setattr__(self, "type", CTAType(self.type))

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["type"] = self.type.value
        return data


@dataclass(frozen=True, slots=True)
class SEOBrief:
    primary_keyword: str = ""
    secondary_keywords: tuple[str, ...] = ()
    search_intent: str = ""
    title_suggestion: str = ""
    meta_description: str = ""
    hashtags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "secondary_keywords", _tuple_str(self.secondary_keywords))
        object.__setattr__(self, "hashtags", _tuple_str(self.hashtags))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ContentMetricsTarget:
    primary_metric: str
    target: str
    secondary_metrics: tuple[str, ...] = ()
    attribution_window: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "secondary_metrics", _tuple_str(self.secondary_metrics))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ContentPiece:
    title: str
    channel: str
    format: ContentFormat
    intent: ContentIntent
    pillar_id: str
    audience_id: str
    objective_id: str
    hook: str
    key_message: str
    outline: tuple[str, ...]
    cta: CallToAction
    metrics_target: ContentMetricsTarget
    seo: SEOBrief = field(default_factory=SEOBrief)
    status: ContentStatus = ContentStatus.PLANNED
    publish_date: str | None = None
    campaign_id: str | None = None
    dependencies: tuple[str, ...] = ()
    source_references: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()
    piece_id: str = field(default_factory=lambda: _id("content"))

    def __post_init__(self) -> None:
        if not isinstance(self.format, ContentFormat):
            object.__setattr__(self, "format", ContentFormat(self.format))
        if not isinstance(self.intent, ContentIntent):
            object.__setattr__(self, "intent", ContentIntent(self.intent))
        if not isinstance(self.status, ContentStatus):
            object.__setattr__(self, "status", ContentStatus(self.status))
        object.__setattr__(self, "outline", _tuple_str(self.outline))
        object.__setattr__(self, "dependencies", _tuple_str(self.dependencies))
        object.__setattr__(self, "source_references", _tuple_str(self.source_references))
        object.__setattr__(self, "notes", _tuple_str(self.notes))
        if self.publish_date:
            date.fromisoformat(self.publish_date)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["format"] = self.format.value
        data["intent"] = self.intent.value
        data["status"] = self.status.value
        data["cta"] = self.cta.to_dict()
        data["seo"] = self.seo.to_dict()
        data["metrics_target"] = self.metrics_target.to_dict()
        return data


@dataclass(frozen=True, slots=True)
class ChannelPlan:
    channel: str
    role: str
    audience_ids: tuple[str, ...]
    preferred_formats: tuple[ContentFormat, ...]
    cadence: CalendarCadence
    publishing_frequency: str
    content_mix: tuple[str, ...] = ()
    success_metrics: tuple[str, ...] = ()
    constraints: tuple[str, ...] = ()
    channel_plan_id: str = field(default_factory=lambda: _id("chplan"))

    def __post_init__(self) -> None:
        object.__setattr__(self, "audience_ids", _tuple_str(self.audience_ids))
        object.__setattr__(
            self,
            "preferred_formats",
            tuple(value if isinstance(value, ContentFormat) else ContentFormat(value) for value in self.preferred_formats),
        )
        if not isinstance(self.cadence, CalendarCadence):
            object.__setattr__(self, "cadence", CalendarCadence(self.cadence))
        object.__setattr__(self, "content_mix", _tuple_str(self.content_mix))
        object.__setattr__(self, "success_metrics", _tuple_str(self.success_metrics))
        object.__setattr__(self, "constraints", _tuple_str(self.constraints))

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["preferred_formats"] = [item.value for item in self.preferred_formats]
        data["cadence"] = self.cadence.value
        return data


@dataclass(frozen=True, slots=True)
class EditorialSlot:
    publish_date: str
    piece_id: str
    channel: str
    campaign_id: str | None = None
    time_window: str | None = None
    owner: str | None = None
    slot_id: str = field(default_factory=lambda: _id("slot"))

    def __post_init__(self) -> None:
        date.fromisoformat(self.publish_date)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class EditorialCalendar:
    name: str
    start_date: str
    end_date: str
    cadence: CalendarCadence
    slots: tuple[EditorialSlot, ...]
    timezone_name: str = "America/Mexico_City"
    calendar_id: str = field(default_factory=lambda: _id("calendar"))

    def __post_init__(self) -> None:
        start = date.fromisoformat(self.start_date)
        end = date.fromisoformat(self.end_date)
        if end < start:
            raise ValueError("end_date no puede ser anterior a start_date")
        if not isinstance(self.cadence, CalendarCadence):
            object.__setattr__(self, "cadence", CalendarCadence(self.cadence))
        object.__setattr__(self, "slots", tuple(self.slots))

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["cadence"] = self.cadence.value
        data["slots"] = [slot.to_dict() for slot in self.slots]
        return data


@dataclass(frozen=True, slots=True)
class ContentBrief:
    project_id: str
    topic: str
    business_objective: str
    value_proposition: str
    positioning: str
    brand_voice: tuple[str, ...]
    source_strategy_package_id: str | None = None
    source_references: tuple[str, ...] = ()
    constraints: tuple[str, ...] = ()
    brief_id: str = field(default_factory=lambda: _id("cbrief"))

    def __post_init__(self) -> None:
        object.__setattr__(self, "brand_voice", _tuple_str(self.brand_voice))
        object.__setattr__(self, "source_references", _tuple_str(self.source_references))
        object.__setattr__(self, "constraints", _tuple_str(self.constraints))

    @classmethod
    def from_strategy_dict(cls, strategy: Mapping[str, Any]) -> "ContentBrief":
        return cls(
            project_id=str(strategy.get("project_id", "")),
            topic=str(strategy.get("topic", "")),
            business_objective=str(strategy.get("business_objective", "")),
            value_proposition=str(strategy.get("value_proposition", "")),
            positioning=str(strategy.get("positioning", "")),
            brand_voice=_tuple_str(strategy.get("brand_voice") or ("claro", "confiable", "útil")),
            source_strategy_package_id=str(strategy.get("package_id")) if strategy.get("package_id") else None,
            source_references=_tuple_str(strategy.get("source_references")),
            constraints=_tuple_str(strategy.get("constraints")),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ContentPackage:
    brief: ContentBrief
    objectives: tuple[ContentObjective, ...]
    audiences: tuple[AudienceSegment, ...]
    pillars: tuple[ContentPillar, ...]
    channel_plans: tuple[ChannelPlan, ...]
    pieces: tuple[ContentPiece, ...]
    calendar: EditorialCalendar
    risks: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()
    source_references: tuple[str, ...] = ()
    package_id: str = field(default_factory=lambda: _id("cpkg"))
    schema_version: str = "1.0.0"
    created_at: str = field(default_factory=_utc_now_iso)

    def __post_init__(self) -> None:
        object.__setattr__(self, "objectives", tuple(self.objectives))
        object.__setattr__(self, "audiences", tuple(self.audiences))
        object.__setattr__(self, "pillars", tuple(self.pillars))
        object.__setattr__(self, "channel_plans", tuple(self.channel_plans))
        object.__setattr__(self, "pieces", tuple(self.pieces))
        object.__setattr__(self, "risks", _tuple_str(self.risks))
        object.__setattr__(self, "assumptions", _tuple_str(self.assumptions))
        object.__setattr__(self, "source_references", _tuple_str(self.source_references))

    def piece_by_id(self, piece_id: str) -> ContentPiece | None:
        return next((piece for piece in self.pieces if piece.piece_id == piece_id), None)

    def pieces_for_channel(self, channel: str) -> tuple[ContentPiece, ...]:
        normalized = channel.strip().casefold()
        return tuple(piece for piece in self.pieces if piece.channel.strip().casefold() == normalized)

    def to_dict(self) -> dict[str, Any]:
        return {
            "brief": self.brief.to_dict(),
            "objectives": [item.to_dict() for item in self.objectives],
            "audiences": [item.to_dict() for item in self.audiences],
            "pillars": [item.to_dict() for item in self.pillars],
            "channel_plans": [item.to_dict() for item in self.channel_plans],
            "pieces": [item.to_dict() for item in self.pieces],
            "calendar": self.calendar.to_dict(),
            "risks": list(self.risks),
            "assumptions": list(self.assumptions),
            "source_references": list(self.source_references),
            "package_id": self.package_id,
            "schema_version": self.schema_version,
            "created_at": self.created_at,
        }


@dataclass(frozen=True, slots=True)
class ContentQualityScore:
    overall: float
    completeness: float
    traceability: float
    channel_alignment: float
    calendar_integrity: float
    measurability: float
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ContentBuildResult:
    package: ContentPackage
    score: ContentQualityScore

    def to_dict(self) -> dict[str, Any]:
        return {"package": self.package.to_dict(), "score": self.score.to_dict()}
