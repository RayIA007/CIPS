"""Safe YAML loading for declarative CIPS video pipelines."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml

from .models import VideoPipelineSpec


class VideoPipelineSourceError(ValueError):
    """Raised when a YAML source cannot represent a pipeline mapping."""


class VideoPipelineLoader:
    """Load YAML safely and validate it as a ``VideoPipelineSpec``."""

    @staticmethod
    def load(path: str | Path) -> VideoPipelineSpec:
        source = Path(path)
        return VideoPipelineLoader.loads(source.read_text(encoding="utf-8"))

    @staticmethod
    def loads(text: str) -> VideoPipelineSpec:
        raw = yaml.safe_load(text)
        return VideoPipelineLoader.load_mapping(raw)

    @staticmethod
    def load_mapping(raw: Any) -> VideoPipelineSpec:
        if raw is None:
            raise VideoPipelineSourceError("El YAML del video pipeline está vacío.")
        if not isinstance(raw, Mapping):
            raise VideoPipelineSourceError(
                "La raíz del video pipeline debe ser un objeto YAML (mapping)."
            )
        return VideoPipelineSpec.model_validate(dict(raw))


__all__ = ["VideoPipelineLoader", "VideoPipelineSourceError"]
