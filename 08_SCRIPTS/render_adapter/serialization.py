"""Canonical JSON helpers for universal render plans."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from .models import RenderPlan


def serialize_render_plan(plan: RenderPlan, *, indent: int = 2) -> str:
    """Serialize one validated render plan deterministically."""

    if not isinstance(plan, RenderPlan):
        raise TypeError("plan debe ser RenderPlan.")
    if isinstance(indent, bool) or not isinstance(indent, int) or indent < 0:
        raise ValueError("indent debe ser un entero no negativo.")
    return (
        json.dumps(
            plan.model_dump(mode="json", exclude_none=True),
            ensure_ascii=False,
            indent=indent,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n"
    )


def deserialize_render_plan(payload: str | bytes | bytearray) -> RenderPlan:
    """Validate and rebuild a render plan from JSON text."""

    if not isinstance(payload, (str, bytes, bytearray)):
        raise TypeError("payload debe ser JSON en str, bytes o bytearray.")
    return RenderPlan.model_validate_json(payload)


def validate_render_plan_data(payload: Mapping[str, Any]) -> RenderPlan:
    """Validate an already-decoded render plan mapping."""

    if not isinstance(payload, Mapping):
        raise TypeError("payload debe ser un Mapping.")
    return RenderPlan.model_validate(dict(payload))


def render_plan_json_schema() -> dict[str, Any]:
    """Return the versioned JSON Schema for the render-plan contract."""

    return RenderPlan.model_json_schema(mode="serialization")


__all__ = [
    "deserialize_render_plan",
    "render_plan_json_schema",
    "serialize_render_plan",
    "validate_render_plan_data",
]
