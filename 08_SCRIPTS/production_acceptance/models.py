"""Serializable PM9 contracts for full-production acceptance evidence."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


PRODUCTION_ACCEPTANCE_SCHEMA_NAME = "cips.production_acceptance"
PRODUCTION_ACCEPTANCE_SCHEMA_VERSION = "1.0"


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


class ProductionAcceptanceEvidence(AcceptanceModel):
    """Final PM9 acceptance record after QA, F7, export, and F8."""

    schema_name: Literal["cips.production_acceptance"] = (
        PRODUCTION_ACCEPTANCE_SCHEMA_NAME
    )
    schema_version: Literal["1.0"] = PRODUCTION_ACCEPTANCE_SCHEMA_VERSION
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
    "MediaCheck",
    "MediaProbeReport",
    "ProductionAcceptanceEvidence",
    "ProductionPreparationEvidence",
]
