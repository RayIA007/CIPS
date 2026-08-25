"""Canonical JSON helpers for PM8 resolution bundles."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from .models import AssetResolutionBundle


def serialize_asset_resolution(
    bundle: AssetResolutionBundle,
    *,
    indent: int = 2,
) -> str:
    if not isinstance(bundle, AssetResolutionBundle):
        raise TypeError("bundle debe ser AssetResolutionBundle.")
    return json.dumps(
        bundle.model_dump(mode="json"),
        ensure_ascii=False,
        indent=indent,
        sort_keys=True,
        allow_nan=False,
    )


def deserialize_asset_resolution(
    payload: str | bytes | bytearray | Mapping[str, Any],
) -> AssetResolutionBundle:
    if isinstance(payload, Mapping):
        return AssetResolutionBundle.model_validate(dict(payload))
    if isinstance(payload, (bytes, bytearray)):
        payload = bytes(payload).decode("utf-8")
    if not isinstance(payload, str):
        raise TypeError("payload debe ser JSON, bytes o Mapping.")
    return AssetResolutionBundle.model_validate_json(payload)


def asset_resolution_json_schema() -> dict[str, Any]:
    return AssetResolutionBundle.model_json_schema()


__all__ = [
    "asset_resolution_json_schema",
    "deserialize_asset_resolution",
    "serialize_asset_resolution",
]
