"""Canonical JSON serialization for the universal production manifest."""

from __future__ import annotations

import json
from typing import Any, Mapping

from .models import ProductionManifest


def serialize_manifest(manifest: ProductionManifest, *, indent: int = 2) -> str:
    """Serialize a validated manifest deterministically as UTF-8 JSON text."""

    if not isinstance(manifest, ProductionManifest):
        raise TypeError("manifest debe ser ProductionManifest.")
    if isinstance(indent, bool) or not isinstance(indent, int) or indent < 0:
        raise ValueError("indent debe ser un entero no negativo.")
    payload = manifest.model_dump(mode="json", exclude_none=True)
    return json.dumps(
        payload,
        ensure_ascii=False,
        indent=indent,
        sort_keys=True,
        allow_nan=False,
    ) + "\n"


def deserialize_manifest(payload: str | bytes | bytearray) -> ProductionManifest:
    """Validate and reconstruct a manifest from a JSON document."""

    if not isinstance(payload, (str, bytes, bytearray)):
        raise TypeError("payload debe ser JSON en str, bytes o bytearray.")
    return ProductionManifest.model_validate_json(payload)


def validate_manifest_data(payload: Mapping[str, Any]) -> ProductionManifest:
    """Validate an already decoded JSON-compatible mapping."""

    if not isinstance(payload, Mapping):
        raise TypeError("payload debe ser un Mapping.")
    return ProductionManifest.model_validate(dict(payload))


def production_manifest_json_schema() -> dict[str, Any]:
    """Return the JSON Schema for the currently supported contract version."""

    return ProductionManifest.model_json_schema(mode="serialization")


__all__ = [
    "deserialize_manifest",
    "production_manifest_json_schema",
    "serialize_manifest",
    "validate_manifest_data",
]
