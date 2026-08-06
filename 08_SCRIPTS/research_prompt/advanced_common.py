"""Utilidades compartidas por los módulos avanzados."""
from __future__ import annotations

from dataclasses import fields, is_dataclass
from datetime import datetime, timezone
from enum import Enum
import math
import re
from typing import Any, Mapping

from .common import normalize_text

try:
    from research_director_models import (
        ResearchConstraint, ResearchObjective, ResearchPriority, ResearchQuestion
    )
except ImportError:  # pragma: no cover
    from ..research_director_models import (
        ResearchConstraint, ResearchObjective, ResearchPriority, ResearchQuestion
    )

def _serialize(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat(timespec="seconds")
    if is_dataclass(value):
        return {item.name: _serialize(getattr(value, item.name)) for item in fields(value)}
    if isinstance(value, Mapping):
        return {str(key): _serialize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_serialize(item) for item in value]
    return value


def _key(value: Any) -> str:
    return re.sub(r"\s+", " ", normalize_text(value).casefold()).strip()


def _get(value: Any, *names: str, default: Any = None) -> Any:
    for name in names:
        if isinstance(value, Mapping) and name in value:
            return value[name]
        if hasattr(value, name):
            return getattr(value, name)
    return default


def _list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, (tuple, set)):
        return list(value)
    return [value]


def _tokens(text: str) -> int:
    return max(0, math.ceil(len(text) / 4))


def _clamp(value: float) -> float:
    return round(max(0.0, min(10.0, float(value))), 2)


def _question(text: str, priority: ResearchPriority = ResearchPriority.NORMAL, rationale: str = "") -> ResearchQuestion:
    kwargs = {"question": text, "priority": priority}
    if rationale:
        kwargs["rationale"] = rationale
    try:
        return ResearchQuestion(**kwargs)
    except TypeError:
        kwargs.pop("rationale", None)
        return ResearchQuestion(**kwargs)


def _objective(text: str, priority: ResearchPriority = ResearchPriority.NORMAL) -> ResearchObjective:
    return ResearchObjective(statement=text, priority=priority)


def _constraint(text: str, category: str = "general", mandatory: bool = True) -> ResearchConstraint:
    return ResearchConstraint(description=text, category=category, mandatory=mandatory)
