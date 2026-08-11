"""Declarative domain models for CIPS F6 video pipelines.

These models describe *what* a video workflow intends to render. They do not
execute workflows, select providers, resolve artifacts, or manage filesystems.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


VIDEO_PIPELINE_SCHEMA_VERSION = "1.0.0"


class VideoTransitionSpec(BaseModel):
    """Declarative transition intent between video elements."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: str = Field(..., min_length=1)
    duration: float = Field(default=0.0, ge=0.0)
    parameters: dict[str, Any] = Field(default_factory=dict)

    @field_validator("kind")
    @classmethod
    def _normalize_kind(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("transition.kind es obligatorio.")
        return normalized

    @field_validator("duration", mode="before")
    @classmethod
    def _reject_text_duration(cls, value: Any) -> Any:
        if isinstance(value, bool) or isinstance(value, str):
            raise ValueError("transition.duration debe ser numérico, no texto.")
        return value


class VideoSceneSpec(BaseModel):
    """One declarative scene compiled later to a Core ``TaskDefinition``."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    scene_id: str = Field(..., min_length=1)
    name: str | None = None
    prompt: str = Field(..., min_length=1)
    duration: float = Field(..., gt=0.0)
    dependencies: tuple[str, ...] = ()
    media_refs: tuple[str, ...] = ()
    transitions: tuple[VideoTransitionSpec, ...] = ()
    audio_track: str | None = None
    subtitle_track: str | None = None

    @field_validator("scene_id", "prompt")
    @classmethod
    def _normalize_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("El texto obligatorio no puede quedar vacío.")
        return normalized

    @field_validator("name", "audio_track", "subtitle_track")
    @classmethod
    def _normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("Los campos de texto opcionales no pueden estar vacíos.")
        return normalized

    @field_validator("duration", mode="before")
    @classmethod
    def _reject_text_duration(cls, value: Any) -> Any:
        if isinstance(value, bool) or isinstance(value, str):
            raise ValueError("scene.duration debe ser numérico, no texto.")
        return value

    @field_validator("dependencies", "media_refs")
    @classmethod
    def _normalize_reference_list(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        normalized = tuple(str(value).strip() for value in values)
        if any(not value for value in normalized):
            raise ValueError("Las referencias no pueden contener valores vacíos.")
        return normalized


class VideoPipelineSpec(BaseModel):
    """Validated declarative video pipeline independent of runtime engines."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    pipeline_id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    version: str = Field(default=VIDEO_PIPELINE_SCHEMA_VERSION, min_length=1)
    scenes: tuple[VideoSceneSpec, ...] = Field(..., min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("pipeline_id", "name", "version")
    @classmethod
    def _normalize_pipeline_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Los identificadores y nombres del pipeline son obligatorios.")
        return normalized


__all__ = [
    "VIDEO_PIPELINE_SCHEMA_VERSION",
    "VideoTransitionSpec",
    "VideoSceneSpec",
    "VideoPipelineSpec",
]
