"""Serializable PM9 contracts for full-production acceptance evidence."""

from __future__ import annotations

import math
from enum import Enum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

PRODUCTION_ACCEPTANCE_SCHEMA_NAME = "cips.production_acceptance"
PRODUCTION_ACCEPTANCE_SCHEMA_VERSION = "1.1"

StrictFps = Annotated[
    float,
    Field(strict=True, gt=0.0, le=240.0, allow_inf_nan=False),
]


class AcceptanceModel(BaseModel):
    """Strict immutable base shared by PM9 evidence models."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
        validate_default=True,
    )


class MediaCheck(AcceptanceModel):
    """One machine-verifiable condition from the physical MP4 probe."""

    check_id: str = Field(..., min_length=1, max_length=128)
    passed: bool
    expected: str = Field(..., min_length=1)
    actual: str = Field(..., min_length=1)


class MediaProbeReport(AcceptanceModel):
    """Normalized FFprobe evidence for one final render candidate."""

    schema_name: Literal["cips.production_acceptance.media_probe"] = (
        "cips.production_acceptance.media_probe"
    )
    schema_version: Literal["1.0"] = "1.0"
    file_sha256: str
    size_bytes: int = Field(..., gt=0)
    format_names: tuple[str, ...] = Field(..., min_length=1)
    duration_seconds: float = Field(..., gt=0.0)
    width_px: int = Field(..., gt=0)
    height_px: int = Field(..., gt=0)
    fps: float = Field(..., gt=0.0)
    video_codec: str = Field(..., min_length=1)
    audio_codec: str = Field(..., min_length=1)
    audio_sample_rate_hz: int = Field(..., gt=0)
    checks: tuple[MediaCheck, ...] = Field(..., min_length=1)

    @field_validator("file_sha256")
    @classmethod
    def _validate_sha256(cls, value: str) -> str:
        normalized = value.strip().lower()
        if len(normalized) != 64 or any(
            character not in "0123456789abcdef" for character in normalized
        ):
            raise ValueError("file_sha256 debe ser un SHA-256 hexadecimal.")
        return normalized

    @property
    def approved(self) -> bool:
        return all(check.passed for check in self.checks)


class FrameRateMode(str, Enum):
    """Provider-neutral response to a physical FPS observation."""

    STRICT = "strict"
    ACCEPT_SOURCE = "accept_source"
    NORMALIZE_TO_MANIFEST = "normalize_to_manifest"


class FrameRateAction(str, Enum):
    """Physical action selected by the frame-rate policy."""

    PASSTHROUGH = "passthrough"
    ACCEPTED_SOURCE = "accepted_source"
    NORMALIZED = "normalized"
    BLOCKED = "blocked"


class FrameRatePolicy(AcceptanceModel):
    """FPS policy kept outside the provider-neutral ProductionManifest."""

    mode: FrameRateMode = FrameRateMode.STRICT
    accepted_source_fps: tuple[StrictFps, ...] = ()
    tolerance_fps: Annotated[
        float,
        Field(strict=True, ge=0.0, le=1.0, allow_inf_nan=False),
    ] = 0.15

    @field_validator("accepted_source_fps")
    @classmethod
    def _normalize_source_fps(cls, values: tuple[float, ...]) -> tuple[float, ...]:
        normalized = tuple(sorted({round(float(value), 6) for value in values}))
        if len(normalized) != len(values):
            raise ValueError("accepted_source_fps no admite valores duplicados.")
        return normalized

    @model_validator(mode="after")
    def _validate_strict_sources(self) -> "FrameRatePolicy":
        if self.mode is FrameRateMode.STRICT and self.accepted_source_fps:
            raise ValueError("El modo strict no admite FPS físicos alternativos.")
        return self

    def accepted_fps(self, target_fps: float) -> tuple[float, ...]:
        """Return the target plus explicitly authorized physical source rates."""

        if isinstance(target_fps, bool):
            raise TypeError("target_fps debe ser numérico.")
        normalized = float(target_fps)
        if not math.isfinite(normalized) or not 0.0 < normalized <= 240.0:
            raise ValueError("target_fps debe estar entre 0 y 240.")
        return tuple(sorted({round(normalized, 6), *self.accepted_source_fps}))


class FrameRateTransformationEvidence(AcceptanceModel):
    """Reproducible local transformation metadata for one normalization."""

    tool: Literal["ffmpeg"] = "ffmpeg"
    tool_version: str = Field(..., min_length=1)
    video_filter: str = Field(..., min_length=1)
    video_codec: Literal["libx264"] = "libx264"
    audio_strategy: Literal["copy"] = "copy"
    temporal_strategy: Literal["duplicate_drop_nearest"] = "duplicate_drop_nearest"
    pixel_format: Literal["yuv420p"] = "yuv420p"
    quality_profile: Literal["crf18-medium"] = "crf18-medium"


class FrameRateEvidence(AcceptanceModel):
    """Input, output, policy, hashes, and cost for the PM9 FPS boundary."""

    schema_name: Literal["cips.production_acceptance.frame_rate"] = (
        "cips.production_acceptance.frame_rate"
    )
    schema_version: Literal["1.0"] = "1.0"
    policy: FrameRatePolicy
    action: FrameRateAction
    target_fps: StrictFps
    input_artifact_id: str = Field(..., min_length=1)
    output_artifact_id: str = Field(..., min_length=1)
    input_locator: str = Field(..., min_length=1)
    output_locator: str = Field(..., min_length=1)
    input_probe: MediaProbeReport
    output_probe: MediaProbeReport
    transformation: FrameRateTransformationEvidence | None = None
    actual_cost_usd: Literal[0.0] = 0.0
    network_called: Literal[False] = False
    publication_performed: Literal[False] = False

    @model_validator(mode="after")
    def _validate_transformation(self) -> "FrameRateEvidence":
        normalized = self.action is FrameRateAction.NORMALIZED
        if normalized != (self.transformation is not None):
            raise ValueError(
                "Sólo action=normalized admite evidencia de transformación."
            )
        if normalized and self.input_artifact_id == self.output_artifact_id:
            raise ValueError("La normalización debe crear un artefacto derivado.")
        if (
            not normalized
            and self.input_probe.file_sha256 != self.output_probe.file_sha256
        ):
            raise ValueError("Sin normalización, entrada y salida deben ser idénticas.")
        return self


class ProductionPreparationEvidence(AcceptanceModel):
    """Durable evidence that PM1-PM8 produced a renderable submission."""

    schema_name: Literal["cips.production_acceptance.preparation"] = (
        "cips.production_acceptance.preparation"
    )
    schema_version: Literal["1.0"] = "1.0"
    project_id: str = Field(..., min_length=1)
    production_id: str = Field(..., min_length=1)
    manifest_id: str = Field(..., min_length=1)
    manifest_sha256: str
    resolution_id: str = Field(..., min_length=1)
    plan_id: str = Field(..., min_length=1)
    submission_id: str = Field(..., min_length=1)
    idempotency_key: str
    workflow_id: str = Field(..., min_length=1)
    run_id: str = Field(..., min_length=1)
    scene_count: int = Field(..., gt=0)
    persisted_asset_count: int = Field(..., ge=0)
    renderer_native_asset_count: int = Field(..., ge=0)
    total_estimated_cost_usd: float = Field(..., ge=0.0)
    total_actual_cost_usd: float = Field(..., ge=0.0)
    unknown_cost_count: int = Field(..., ge=0)
    manifest_relative_path: str = Field(..., min_length=1)
    asset_bundle_relative_path: str = Field(..., min_length=1)
    payload_relative_path: str = Field(..., min_length=1)
    canonical_subtitles_relative_path: str | None = Field(default=None, min_length=1)
    canonical_subtitles_sha256: str | None = None
    canonical_subtitles_lexical_source: str | None = Field(default=None, min_length=1)
    canonical_subtitles_timing_source: str | None = Field(default=None, min_length=1)
    narration_conformance_required: bool = False
    narration_conformance_relative_path: str | None = Field(default=None, min_length=1)
    narration_conformance_sha256: str | None = None
    narration_conformance_approved: bool | None = None
    ready_for_real_render: bool
    blockers: tuple[str, ...] = ()

    @field_validator("manifest_sha256", "idempotency_key")
    @classmethod
    def _validate_hash(cls, value: str) -> str:
        normalized = value.strip().lower()
        if len(normalized) != 64 or any(
            character not in "0123456789abcdef" for character in normalized
        ):
            raise ValueError("Se esperaba un SHA-256 hexadecimal.")
        return normalized

    @field_validator(
        "canonical_subtitles_sha256",
        "narration_conformance_sha256",
    )
    @classmethod
    def _validate_optional_hash(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower()
        if len(normalized) != 64 or any(
            character not in "0123456789abcdef" for character in normalized
        ):
            raise ValueError("canonical_subtitles_sha256 debe ser SHA-256 hexadecimal.")
        return normalized

    @model_validator(mode="after")
    def _validate_canonical_subtitle_evidence(self) -> "ProductionPreparationEvidence":
        subtitle_fields = (
            self.canonical_subtitles_relative_path,
            self.canonical_subtitles_sha256,
            self.canonical_subtitles_lexical_source,
            self.canonical_subtitles_timing_source,
        )
        if any(value is not None for value in subtitle_fields) and any(
            value is None for value in subtitle_fields
        ):
            raise ValueError(
                "La evidencia de subtítulos canónicos debe estar completa o ausente."
            )
        return self

    @model_validator(mode="after")
    def _validate_narration_conformance_evidence(
        self,
    ) -> "ProductionPreparationEvidence":
        if not self.narration_conformance_required:
            if any(
                value is not None
                for value in (
                    self.narration_conformance_relative_path,
                    self.narration_conformance_sha256,
                    self.narration_conformance_approved,
                )
            ):
                raise ValueError(
                    "La evidencia acústica sólo corresponde a una política requerida."
                )
            return self
        if self.narration_conformance_relative_path is None:
            raise ValueError("La política acústica requiere la ruta de su evidencia.")
        if self.narration_conformance_approved is True and (
            self.narration_conformance_sha256 is None
        ):
            raise ValueError("Una aprobación acústica requiere SHA-256 de evidencia.")
        if (
            self.ready_for_real_render
            and self.narration_conformance_approved is not True
        ):
            raise ValueError(
                "ready_for_real_render requiere aprobación acústica "
                "cuando es obligatoria."
            )
        return self


class ProductionAcceptanceEvidence(AcceptanceModel):
    """Final PM9 acceptance record after QA, F7, export, and F8."""

    schema_name: Literal["cips.production_acceptance"] = (
        PRODUCTION_ACCEPTANCE_SCHEMA_NAME
    )
    schema_version: Literal["1.1"] = PRODUCTION_ACCEPTANCE_SCHEMA_VERSION
    project_id: str = Field(..., min_length=1)
    production_id: str = Field(..., min_length=1)
    manifest_id: str = Field(..., min_length=1)
    resolution_id: str = Field(..., min_length=1)
    plan_id: str = Field(..., min_length=1)
    submission_id: str = Field(..., min_length=1)
    workflow_id: str = Field(..., min_length=1)
    run_id: str = Field(..., min_length=1)
    render_job_id: str = Field(..., min_length=1)
    render_artifact_id: str = Field(..., min_length=1)
    render_external_job_id: str | None = None
    frame_rate: FrameRateEvidence
    media_probe: MediaProbeReport
    qa_approved: bool
    human_approved: bool
    review_record_id: str = Field(..., min_length=1)
    review_decision_id: str = Field(..., min_length=1)
    review_state: Literal["approved"]
    export_artifact_id: str = Field(..., min_length=1)
    export_content_sha256: str
    export_relative_path: str = Field(..., min_length=1)
    telemetry_relative_path: str = Field(..., min_length=1)
    observed_estimated_cost_usd: float = Field(..., ge=0.0)
    observed_credits: float | None = Field(default=None, ge=0.0)
    publication_performed: Literal[False] = False
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("export_content_sha256")
    @classmethod
    def _validate_export_hash(cls, value: str) -> str:
        normalized = value.strip().lower()
        if len(normalized) != 64 or any(
            character not in "0123456789abcdef" for character in normalized
        ):
            raise ValueError("export_content_sha256 debe ser SHA-256 hexadecimal.")
        return normalized


__all__ = [
    "PRODUCTION_ACCEPTANCE_SCHEMA_NAME",
    "PRODUCTION_ACCEPTANCE_SCHEMA_VERSION",
    "FrameRateAction",
    "FrameRateEvidence",
    "FrameRateMode",
    "FrameRatePolicy",
    "FrameRateTransformationEvidence",
    "MediaCheck",
    "MediaProbeReport",
    "ProductionAcceptanceEvidence",
    "ProductionPreparationEvidence",
]
