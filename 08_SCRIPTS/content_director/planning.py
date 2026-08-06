from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Mapping, Sequence

from .models import (
    AudienceSegment,
    CalendarCadence,
    ChannelPlan,
    ContentBrief,
    ContentFormat,
    ContentObjective,
    ContentPillar,
)
from .planning_models import (
    ContentAllocation,
    ContentPlan,
    EditorialPolicy,
    PlanningBuildResult,
    PlanningQualityScore,
)


@dataclass(frozen=True, slots=True)
class PlanningConfig:
    horizon_weeks: int = 12
    pieces_per_week: int = 3
    timezone_name: str = "America/Mexico_City"
    start_date: str | None = None
    publishing_days: tuple[int, ...] = (0, 2, 4)
    preferred_time_windows: tuple[str, ...] = ("09:00-11:00", "17:00-19:00")
    default_channels: tuple[str, ...] = ("blog",)

    def __post_init__(self) -> None:
        if self.horizon_weeks < 1:
            raise ValueError("horizon_weeks debe ser mayor o igual a 1")
        if self.pieces_per_week < 1:
            raise ValueError("pieces_per_week debe ser mayor o igual a 1")
        if self.start_date:
            date.fromisoformat(self.start_date)


class ContentPlanningError(ValueError):
    pass


_FORMAT_ALIASES: dict[str, ContentFormat] = {
    "short": ContentFormat.SHORT_VIDEO,
    "shorts": ContentFormat.SHORT_VIDEO,
    "reel": ContentFormat.SHORT_VIDEO,
    "reels": ContentFormat.SHORT_VIDEO,
    "tiktok": ContentFormat.SHORT_VIDEO,
    "video": ContentFormat.LONG_VIDEO,
    "video largo": ContentFormat.LONG_VIDEO,
    "carrusel": ContentFormat.CAROUSEL,
    "carousel": ContentFormat.CAROUSEL,
    "artículo": ContentFormat.ARTICLE,
    "articulo": ContentFormat.ARTICLE,
    "blog": ContentFormat.ARTICLE,
    "newsletter": ContentFormat.NEWSLETTER,
    "podcast": ContentFormat.PODCAST,
    "hilo": ContentFormat.THREAD,
    "thread": ContentFormat.THREAD,
    "infografía": ContentFormat.INFOGRAPHIC,
    "infografia": ContentFormat.INFOGRAPHIC,
    "guía": ContentFormat.GUIDE,
    "guia": ContentFormat.GUIDE,
}

_CHANNEL_DEFAULTS: dict[str, tuple[ContentFormat, ...]] = {
    "tiktok": (ContentFormat.SHORT_VIDEO,),
    "instagram": (ContentFormat.SHORT_VIDEO, ContentFormat.CAROUSEL, ContentFormat.STORY),
    "facebook": (ContentFormat.STATIC_IMAGE, ContentFormat.SHORT_VIDEO, ContentFormat.ARTICLE),
    "youtube": (ContentFormat.LONG_VIDEO, ContentFormat.SHORT_VIDEO),
    "youtube shorts": (ContentFormat.SHORT_VIDEO,),
    "linkedin": (ContentFormat.ARTICLE, ContentFormat.CAROUSEL),
    "x": (ContentFormat.THREAD,),
    "twitter": (ContentFormat.THREAD,),
    "blog": (ContentFormat.ARTICLE, ContentFormat.GUIDE),
    "newsletter": (ContentFormat.NEWSLETTER,),
    "podcast": (ContentFormat.PODCAST,),
}


def _text(value: Any, fallback: str = "") -> str:
    if value is None:
        return fallback
    result = str(value).strip()
    return result or fallback


def _items(value: Any) -> tuple[Any, ...]:
    if value is None:
        return ()
    if isinstance(value, (str, bytes)):
        return (value,)
    if isinstance(value, Sequence):
        return tuple(value)
    return (value,)


def _strings(value: Any) -> tuple[str, ...]:
    return tuple(text for item in _items(value) if (text := _text(item)))


def _mapping(item: Any) -> Mapping[str, Any]:
    return item if isinstance(item, Mapping) else {}


def _formats(raw_formats: Any, channel: str | None = None) -> tuple[ContentFormat, ...]:
    found: list[ContentFormat] = []
    for raw in _items(raw_formats):
        value = _text(raw).casefold()
        if not value:
            continue
        try:
            fmt = ContentFormat(value)
        except ValueError:
            fmt = _FORMAT_ALIASES.get(value, ContentFormat.OTHER)
        if fmt not in found:
            found.append(fmt)
    if not found and channel:
        found.extend(_CHANNEL_DEFAULTS.get(channel.casefold(), (ContentFormat.OTHER,)))
    return tuple(found or (ContentFormat.OTHER,))


class ContentPlanningEngine:
    """Convierte un StrategyPackage serializado en un ContentPlan trazable."""

    def __init__(self, config: PlanningConfig | None = None) -> None:
        self.config = config or PlanningConfig()

    def build(self, strategy: Mapping[str, Any]) -> PlanningBuildResult:
        if not isinstance(strategy, Mapping):
            raise TypeError("strategy debe ser un Mapping")
        self._assert_minimum_strategy(strategy)

        brief = ContentBrief.from_strategy_dict(strategy)
        objectives = self._build_objectives(strategy)
        audiences = self._build_audiences(strategy)
        pillars = self._build_pillars(strategy)
        channels = self._build_channels(strategy, audiences, pillars)
        editorial_policy = self._build_editorial_policy()
        allocations = self._build_allocations(pillars)

        kpis = tuple(
            _text(_mapping(item).get("name"), _text(item))
            for item in _items(strategy.get("kpis"))
            if _text(_mapping(item).get("name"), _text(item))
        )
        roadmap_horizons = tuple(
            _text(_mapping(item).get("horizon"), _mapping(item).get("phase", ""))
            for item in _items(strategy.get("roadmap"))
            if _text(_mapping(item).get("horizon"), _mapping(item).get("phase", ""))
        )

        plan = ContentPlan(
            brief=brief,
            objectives=objectives,
            audiences=audiences,
            pillars=pillars,
            channel_plans=channels,
            editorial_policy=editorial_policy,
            allocations=allocations,
            kpi_names=kpis,
            roadmap_horizons=roadmap_horizons,
            risks=_strings(strategy.get("risks")),
            assumptions=_strings(strategy.get("assumptions")),
            source_references=_strings(strategy.get("source_references")),
        )
        return PlanningBuildResult(plan=plan, score=self._score(plan))

    def _assert_minimum_strategy(self, strategy: Mapping[str, Any]) -> None:
        missing: list[str] = []
        for key in ("project_id", "topic", "business_objective", "objectives", "audiences", "content_pillars"):
            value = strategy.get(key)
            if value is None or value == "" or value == () or value == []:
                missing.append(key)
        if missing:
            raise ContentPlanningError("StrategyPackage incompleto: " + ", ".join(missing))

    def _build_objectives(self, strategy: Mapping[str, Any]) -> tuple[ContentObjective, ...]:
        result: list[ContentObjective] = []
        for item in _items(strategy.get("objectives")):
            data = _mapping(item)
            if not data:
                continue
            result.append(ContentObjective(
                name=_text(data.get("name"), "Objetivo de contenido"),
                intended_outcome=_text(data.get("outcome"), strategy.get("business_objective", "")),
                metric=_text(data.get("metric"), "avance del objetivo"),
                target=_text(data.get("target"), "por definir"),
                horizon=_text(data.get("horizon"), f"{self.config.horizon_weeks} semanas"),
            ))
        return tuple(result)

    def _build_audiences(self, strategy: Mapping[str, Any]) -> tuple[AudienceSegment, ...]:
        result: list[AudienceSegment] = []
        strategy_channels = _strings(strategy.get("channels"))
        for item in _items(strategy.get("audiences")):
            data = _mapping(item)
            if not data:
                continue
            result.append(AudienceSegment(
                name=_text(data.get("name"), "Audiencia principal"),
                description=_text(data.get("description"), "Audiencia definida por la estrategia"),
                needs=_strings(data.get("needs")),
                pain_points=_strings(data.get("pain_points") or data.get("barriers")),
                objections=_strings(data.get("objections") or data.get("barriers")),
                preferred_channels=_strings(data.get("preferred_channels")) or strategy_channels,
            ))
        return tuple(result)

    def _build_pillars(self, strategy: Mapping[str, Any]) -> tuple[ContentPillar, ...]:
        result: list[ContentPillar] = []
        for item in _items(strategy.get("content_pillars")):
            data = _mapping(item)
            if not data:
                continue
            result.append(ContentPillar(
                name=_text(data.get("name"), "Pilar estratégico"),
                purpose=_text(data.get("purpose"), "Apoyar el objetivo estratégico"),
                themes=_strings(data.get("themes")),
                formats=_formats(data.get("formats")),
            ))
        return tuple(result)

    def _build_channels(
        self,
        strategy: Mapping[str, Any],
        audiences: tuple[AudienceSegment, ...],
        pillars: tuple[ContentPillar, ...],
    ) -> tuple[ChannelPlan, ...]:
        raw_channels = _strings(strategy.get("channels")) or self.config.default_channels
        audience_ids = tuple(item.audience_id for item in audiences)
        result: list[ChannelPlan] = []
        for channel in dict.fromkeys(raw_channels):
            preferred = list(_CHANNEL_DEFAULTS.get(channel.casefold(), ()))
            if not preferred:
                for pillar in pillars:
                    for fmt in pillar.formats:
                        if fmt not in preferred:
                            preferred.append(fmt)
            result.append(ChannelPlan(
                channel=channel,
                role=f"Distribuir contenido estratégico en {channel}",
                audience_ids=audience_ids,
                preferred_formats=tuple(preferred or (ContentFormat.OTHER,)),
                cadence=CalendarCadence.WEEKLY,
                publishing_frequency=f"{self.config.pieces_per_week} piezas por semana entre todos los canales",
                content_mix=tuple(pillar.name for pillar in pillars),
                success_metrics=tuple(
                    _text(_mapping(item).get("name"), _text(item))
                    for item in _items(strategy.get("kpis"))
                    if _text(_mapping(item).get("name"), _text(item))
                ),
                constraints=_strings(strategy.get("constraints")),
            ))
        return tuple(result)

    def _build_editorial_policy(self) -> EditorialPolicy:
        start = date.fromisoformat(self.config.start_date) if self.config.start_date else date.today()
        end = start + timedelta(weeks=self.config.horizon_weeks) - timedelta(days=1)
        return EditorialPolicy(
            start_date=start.isoformat(),
            end_date=end.isoformat(),
            timezone_name=self.config.timezone_name,
            cadence=CalendarCadence.WEEKLY,
            total_weeks=self.config.horizon_weeks,
            target_pieces_per_week=self.config.pieces_per_week,
            publishing_days=self.config.publishing_days,
            preferred_time_windows=self.config.preferred_time_windows,
        )

    def _build_allocations(self, pillars: tuple[ContentPillar, ...]) -> tuple[ContentAllocation, ...]:
        count = len(pillars)
        base, remainder = divmod(100, count)
        return tuple(
            ContentAllocation(
                pillar_id=pillar.pillar_id,
                percentage=base + (1 if index < remainder else 0),
                rationale="Distribución inicial equilibrada; deberá ajustarse con analítica real.",
            )
            for index, pillar in enumerate(pillars)
        )

    def _score(self, plan: ContentPlan) -> PlanningQualityScore:
        warnings: list[str] = []
        strategy_coverage = 10.0
        if not plan.source_references:
            strategy_coverage -= 1.5
            warnings.append("El plan no contiene referencias de fuentes heredadas.")
        if not plan.roadmap_horizons:
            strategy_coverage -= 0.5
            warnings.append("No se heredaron horizontes del roadmap.")

        channel_readiness = 10.0 if plan.channel_plans else 0.0
        if any(plan_item.preferred_formats == (ContentFormat.OTHER,) for plan_item in plan.channel_plans):
            channel_readiness -= 1.0
            warnings.append("Al menos un canal requiere definición manual de formatos.")

        measurability = 10.0 if plan.kpi_names else 7.0
        if not plan.kpi_names:
            warnings.append("No se encontraron KPIs explícitos en la estrategia.")

        allocation_total = sum(item.percentage for item in plan.allocations)
        allocation_integrity = 10.0 if allocation_total == 100 else 0.0
        overall = round((strategy_coverage + channel_readiness + measurability + allocation_integrity) / 4, 2)
        return PlanningQualityScore(
            overall=overall,
            strategy_coverage=round(strategy_coverage, 2),
            channel_readiness=round(channel_readiness, 2),
            measurability=round(measurability, 2),
            allocation_integrity=round(allocation_integrity, 2),
            warnings=tuple(warnings),
        )
