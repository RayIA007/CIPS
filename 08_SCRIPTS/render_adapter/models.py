"""Strict provider-neutral contracts for the PM4 render boundary.

The contracts describe an inspectable compilation plan and future render
lifecycle values.  They do not resolve assets, perform network I/O, execute a
render, persist artifacts, or expose fields owned by a concrete target.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable
from enum import Enum
from typing import Annotated, Any, Literal

from production_manifest import (
    AssetRequest,
    AssetType,
    AudioDesignSpec,
    CaptionSpec,
    MotionSpec,
    OnScreenTextSpec,
    OutputSpec,
    PublicationSpec,
    QualityRequirement,
    SourceReference,
    TransitionKind,
    TransitionSpec,
    VisualDirection,
)
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    StrictBool,
    field_validator,
    model_validator,
)

RENDER_PLAN_SCHEMA_NAME = "cips.render_plan"
RENDER_PLAN_SCHEMA_VERSION = "1.0"
RENDER_SUBMISSION_SCHEMA_NAME = "cips.render_submission"
RENDER_PLAN_FILENAME = "render_plan.json"

_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_TIMING_TOLERANCE = 1e-6

StrictPositiveSeconds = Annotated[
    float,
    Field(strict=True, gt=0.0, allow_inf_nan=False),
]
StrictNonNegativeSeconds = Annotated[
    float,
    Field(strict=True, ge=0.0, allow_inf_nan=False),
]
StrictPositiveInt = Annotated[int, Field(strict=True, gt=0)]


class RenderModel(BaseModel):
    """Strict immutable base for every universal render contract."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
        validate_default=True,
    )


class RenderContractVersion(str, Enum):
    V1_0 = RENDER_PLAN_SCHEMA_VERSION


class RenderStatus(str, Enum):
    """Provider-neutral lifecycle states for future render execution."""

    PREPARED = "prepared"
    SUBMITTED = "submitted"
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELED = "canceled"


class RenderTargetCapabilities(RenderModel):
    """Universal features and technical limits declared by one target."""

    supported_asset_types: tuple[AssetType, ...] = ()
    supported_transition_kinds: tuple[TransitionKind, ...] = (TransitionKind.CUT,)
    supports_narration: StrictBool = False
    supports_motion: StrictBool = False
    supports_on_screen_text: StrictBool = False
    supports_captions: StrictBool = False
    supports_music: StrictBool = False
    supports_sound_effects: StrictBool = False
    max_width_px: Annotated[int, Field(strict=True, gt=0)] | None = None
    max_height_px: Annotated[int, Field(strict=True, gt=0)] | None = None
    max_fps: (
        Annotated[
            float,
            Field(strict=True, gt=0.0, allow_inf_nan=False),
        ]
        | None
    ) = None
    max_duration_seconds: StrictPositiveSeconds | None = None

    @field_validator("supported_asset_types")
    @classmethod
    def _normalize_asset_types(
        cls,
        values: tuple[AssetType, ...],
    ) -> tuple[AssetType, ...]:
        normalized = tuple(AssetType(value) for value in values)
        if AssetType.NONE in normalized:
            raise ValueError("asset_type='none' no es una capability del target.")
        return _sorted_unique_enums(normalized, "supported_asset_types")

    @field_validator("supported_transition_kinds")
    @classmethod
    def _normalize_transition_kinds(
        cls,
        values: tuple[TransitionKind, ...],
    ) -> tuple[TransitionKind, ...]:
        normalized = tuple(TransitionKind(value) for value in values)
        return _sorted_unique_enums(normalized, "supported_transition_kinds")


class RenderScenePlan(RenderModel):
    """One manifest scene preserved at the target compilation boundary."""

    scene_id: str = Field(..., min_length=1, max_length=128)
    sequence: StrictPositiveInt
    start_seconds: StrictNonNegativeSeconds
    duration_seconds: StrictPositiveSeconds
    narration_text: str | None = Field(default=None, min_length=1)
    asset_request: AssetRequest
    visual_direction: VisualDirection
    motion: MotionSpec
    on_screen_text: tuple[OnScreenTextSpec, ...] = ()
    captions: CaptionSpec | None = None
    transition_in: TransitionSpec
    transition_out: TransitionSpec
    source_reference_ids: tuple[str, ...] = ()
    metadata: dict[str, JsonValue] = Field(default_factory=dict)

    @field_validator("scene_id")
    @classmethod
    def _validate_scene_id(cls, value: str) -> str:
        return _validate_identifier(value, "scene_id")

    @field_validator("source_reference_ids")
    @classmethod
    def _validate_source_reference_ids(
        cls,
        values: tuple[str, ...],
    ) -> tuple[str, ...]:
        normalized = tuple(
            _validate_identifier(value, "source_reference_id") for value in values
        )
        if len(set(normalized)) != len(normalized):
            raise ValueError("source_reference_ids contiene valores duplicados.")
        return normalized

    @property
    def end_seconds(self) -> float:
        return self.start_seconds + self.duration_seconds


class RenderPlan(RenderModel):
    """Inspectable target compilation derived from one immutable manifest."""

    schema_name: Literal["cips.render_plan"] = RENDER_PLAN_SCHEMA_NAME
    schema_version: RenderContractVersion = RenderContractVersion.V1_0
    plan_id: str = Field(..., min_length=1, max_length=128)
    target_id: str = Field(..., min_length=1, max_length=128)
    adapter_name: str = Field(..., min_length=1, max_length=128)
    adapter_version: str = Field(..., min_length=1, max_length=64)
    manifest_id: str = Field(..., min_length=1, max_length=128)
    manifest_sha256: str
    project_id: str = Field(..., min_length=1, max_length=128)
    production_id: str = Field(..., min_length=1, max_length=128)
    output: OutputSpec
    scenes: tuple[RenderScenePlan, ...] = Field(..., min_length=1)
    audio_design: AudioDesignSpec
    publication: PublicationSpec
    quality_requirements: tuple[QualityRequirement, ...] = Field(..., min_length=1)
    source_references: tuple[SourceReference, ...] = ()
    required_capabilities: tuple[str, ...]
    target_capabilities: RenderTargetCapabilities
    target_payload: dict[str, JsonValue]
    manifest_metadata: dict[str, JsonValue] = Field(default_factory=dict)

    @field_validator(
        "plan_id",
        "target_id",
        "adapter_name",
        "manifest_id",
        "project_id",
        "production_id",
    )
    @classmethod
    def _validate_ids(cls, value: str) -> str:
        return _validate_identifier(value, "render identifier")

    @field_validator("manifest_sha256")
    @classmethod
    def _validate_manifest_hash(cls, value: str) -> str:
        normalized = value.lower()
        if not _SHA256_PATTERN.fullmatch(normalized):
            raise ValueError("manifest_sha256 debe ser un SHA-256 hexadecimal.")
        return normalized

    @field_validator("required_capabilities")
    @classmethod
    def _normalize_required_capabilities(
        cls,
        values: tuple[str, ...],
    ) -> tuple[str, ...]:
        normalized = tuple(str(value).strip() for value in values)
        if any(not value for value in normalized):
            raise ValueError("required_capabilities no acepta valores vacíos.")
        if len(set(normalized)) != len(normalized):
            raise ValueError("required_capabilities contiene valores duplicados.")
        return tuple(sorted(normalized))

    @model_validator(mode="after")
    def _validate_plan_consistency(self) -> RenderPlan:
        expected_plan_id = deterministic_render_plan_id(
            target_id=self.target_id,
            adapter_name=self.adapter_name,
            adapter_version=self.adapter_version,
            manifest_id=self.manifest_id,
            manifest_sha256=self.manifest_sha256,
            schema_version=self.schema_version,
        )
        if self.plan_id != expected_plan_id:
            raise ValueError(
                "plan_id no coincide con la identidad determinista esperada: "
                f"{expected_plan_id}."
            )
        scene_ids = [scene.scene_id for scene in self.scenes]
        duplicates = _duplicates(scene_ids)
        if duplicates:
            raise ValueError(
                "RenderPlan contiene scene_id duplicados: "
                + ", ".join(duplicates)
                + "."
            )
        expected_sequence = tuple(range(1, len(self.scenes) + 1))
        actual_sequence = tuple(scene.sequence for scene in self.scenes)
        if actual_sequence != expected_sequence:
            raise ValueError(
                "RenderPlan.scenes requiere sequence contiguo iniciando en 1."
            )
        if abs(self.scenes[0].start_seconds) > _TIMING_TOLERANCE:
            raise ValueError("La primera escena del RenderPlan debe iniciar en 0.")
        for previous, current in zip(self.scenes, self.scenes[1:]):
            if current.start_seconds < previous.end_seconds - _TIMING_TOLERANCE:
                raise ValueError("Las escenas del RenderPlan no pueden solaparse.")
        timeline_end = max(scene.end_seconds for scene in self.scenes)
        if abs(timeline_end - self.output.duration_seconds) > _TIMING_TOLERANCE:
            raise ValueError(
                "RenderPlan.output.duration_seconds debe coincidir con la timeline."
            )
        return self


class RenderSubmission(RenderModel):
    """Prepared, still-offline payload that a later phase may submit."""

    schema_name: Literal["cips.render_submission"] = RENDER_SUBMISSION_SCHEMA_NAME
    schema_version: RenderContractVersion = RenderContractVersion.V1_0
    submission_id: str = Field(..., min_length=1, max_length=128)
    plan_id: str = Field(..., min_length=1, max_length=128)
    manifest_id: str = Field(..., min_length=1, max_length=128)
    target_id: str = Field(..., min_length=1, max_length=128)
    idempotency_key: str
    payload: dict[str, JsonValue]

    @field_validator("submission_id", "plan_id", "manifest_id", "target_id")
    @classmethod
    def _validate_ids(cls, value: str) -> str:
        return _validate_identifier(value, "submission identifier")

    @field_validator("idempotency_key")
    @classmethod
    def _validate_idempotency_key(cls, value: str) -> str:
        normalized = value.lower()
        if not _SHA256_PATTERN.fullmatch(normalized):
            raise ValueError("idempotency_key debe ser un SHA-256 hexadecimal.")
        return normalized

    @model_validator(mode="after")
    def _validate_submission_id(self) -> RenderSubmission:
        expected = deterministic_submission_id(
            plan_id=self.plan_id,
            target_id=self.target_id,
            idempotency_key=self.idempotency_key,
        )
        if self.submission_id != expected:
            raise ValueError(
                "submission_id no coincide con la identidad determinista esperada: "
                f"{expected}."
            )
        return self


class RenderJob(RenderModel):
    """Provider-neutral identity and state for a future submitted render."""

    job_id: str = Field(..., min_length=1, max_length=128)
    submission_id: str = Field(..., min_length=1, max_length=128)
    target_id: str = Field(..., min_length=1, max_length=128)
    status: RenderStatus = RenderStatus.PREPARED
    external_job_id: str | None = Field(default=None, min_length=1, max_length=256)
    metadata: dict[str, JsonValue] = Field(default_factory=dict)

    @field_validator("job_id", "submission_id", "target_id")
    @classmethod
    def _validate_ids(cls, value: str) -> str:
        return _validate_identifier(value, "job identifier")

    @model_validator(mode="after")
    def _validate_external_identity(self) -> RenderJob:
        submitted_states = {
            RenderStatus.SUBMITTED,
            RenderStatus.QUEUED,
            RenderStatus.RUNNING,
            RenderStatus.SUCCEEDED,
            RenderStatus.FAILED,
            RenderStatus.CANCELED,
        }
        if self.status in submitted_states and self.external_job_id is None:
            raise ValueError("Un RenderJob enviado requiere external_job_id.")
        return self


class RenderResult(RenderModel):
    """Terminal outcome contract for later online execution phases."""

    job_id: str = Field(..., min_length=1, max_length=128)
    plan_id: str = Field(..., min_length=1, max_length=128)
    manifest_id: str = Field(..., min_length=1, max_length=128)
    target_id: str = Field(..., min_length=1, max_length=128)
    status: RenderStatus
    output_artifact_ids: tuple[str, ...] = ()
    error: str | None = Field(default=None, min_length=1)
    metadata: dict[str, JsonValue] = Field(default_factory=dict)

    @field_validator("job_id", "plan_id", "manifest_id", "target_id")
    @classmethod
    def _validate_ids(cls, value: str) -> str:
        return _validate_identifier(value, "result identifier")

    @field_validator("output_artifact_ids")
    @classmethod
    def _validate_artifact_ids(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        normalized = tuple(
            _validate_identifier(value, "output_artifact_id") for value in values
        )
        if len(set(normalized)) != len(normalized):
            raise ValueError("output_artifact_ids contiene valores duplicados.")
        return normalized

    @model_validator(mode="after")
    def _validate_terminal_result(self) -> RenderResult:
        terminal_states = {
            RenderStatus.SUCCEEDED,
            RenderStatus.FAILED,
            RenderStatus.CANCELED,
        }
        if self.status not in terminal_states:
            raise ValueError("RenderResult requiere un estado terminal.")
        if self.status is RenderStatus.SUCCEEDED:
            if not self.output_artifact_ids:
                raise ValueError("RenderResult exitoso requiere output_artifact_ids.")
            if self.error is not None:
                raise ValueError("RenderResult exitoso no acepta error.")
        elif self.error is None:
            raise ValueError("RenderResult fallido o cancelado requiere error.")
        return self


def deterministic_render_plan_id(
    *,
    target_id: str,
    adapter_name: str,
    adapter_version: str,
    manifest_id: str,
    manifest_sha256: str,
    schema_version: RenderContractVersion | str = RenderContractVersion.V1_0,
) -> str:
    """Derive a stable plan identity from immutable compilation inputs."""

    version = (
        schema_version.value
        if isinstance(schema_version, RenderContractVersion)
        else str(schema_version)
    )
    parts = (
        _validate_identifier(target_id, "target_id"),
        _validate_identifier(adapter_name, "adapter_name"),
        str(adapter_version).strip(),
        _validate_identifier(manifest_id, "manifest_id"),
        str(manifest_sha256).lower(),
        version.strip(),
    )
    if not parts[2] or not parts[5]:
        raise ValueError("adapter_version y schema_version son obligatorios.")
    if not _SHA256_PATTERN.fullmatch(parts[4]):
        raise ValueError("manifest_sha256 debe ser un SHA-256 hexadecimal.")
    digest = hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()
    return f"rp-{digest[:24]}"


def deterministic_submission_id(
    *,
    plan_id: str,
    target_id: str,
    idempotency_key: str,
) -> str:
    """Derive an offline submission identity without contacting a target."""

    normalized_key = str(idempotency_key).lower()
    if not _SHA256_PATTERN.fullmatch(normalized_key):
        raise ValueError("idempotency_key debe ser un SHA-256 hexadecimal.")
    basis = "\x1f".join(
        (
            _validate_identifier(plan_id, "plan_id"),
            _validate_identifier(target_id, "target_id"),
            normalized_key,
        )
    )
    return f"rs-{hashlib.sha256(basis.encode('utf-8')).hexdigest()[:24]}"


def _validate_identifier(value: str, field_name: str) -> str:
    normalized = str(value).strip()
    if not _ID_PATTERN.fullmatch(normalized):
        raise ValueError(
            f"{field_name} debe usar letras, números, punto, guion o guion bajo."
        )
    return normalized


def _sorted_unique_enums(values: Iterable[Enum], field_name: str) -> tuple[Any, ...]:
    items = tuple(values)
    identities = tuple(item.value for item in items)
    if len(set(identities)) != len(identities):
        raise ValueError(f"{field_name} contiene valores duplicados.")
    return tuple(sorted(items, key=lambda item: item.value))


def _duplicates(values: Iterable[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        else:
            seen.add(value)
    return tuple(sorted(duplicates))


__all__ = [
    "RENDER_PLAN_FILENAME",
    "RENDER_PLAN_SCHEMA_NAME",
    "RENDER_PLAN_SCHEMA_VERSION",
    "RENDER_SUBMISSION_SCHEMA_NAME",
    "RenderContractVersion",
    "RenderJob",
    "RenderPlan",
    "RenderResult",
    "RenderScenePlan",
    "RenderStatus",
    "RenderSubmission",
    "RenderTargetCapabilities",
    "deterministic_render_plan_id",
    "deterministic_submission_id",
]
