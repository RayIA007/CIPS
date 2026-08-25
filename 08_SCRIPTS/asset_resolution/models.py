"""Provider-neutral contracts for PM8 multi-asset resolution.

The production manifest continues to describe *what* a production needs.  The
models in this module describe the operational result of resolving those needs
without adding provider names, credentials, physical paths or delivery URLs to
``ProductionManifest``.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import PurePosixPath
from types import MappingProxyType
from typing import Annotated, Any, Mapping, Literal
from urllib.parse import urlsplit

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    StrictBool,
    field_validator,
    model_validator,
)


ASSET_RESOLUTION_SCHEMA_NAME = "cips.asset_resolution"
ASSET_RESOLUTION_SCHEMA_VERSION = "1.0"
ASSET_RESOLUTION_FILENAME = "asset_resolution.json"

_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_EXTENSION_PATTERN = re.compile(r"^\.[a-z0-9]{1,10}$")

StrictNonNegativeMoney = Annotated[
    float,
    Field(strict=True, ge=0.0, allow_inf_nan=False),
]
StrictNonNegativeInt = Annotated[int, Field(strict=True, ge=0)]


class ResolutionModel(BaseModel):
    """Strict immutable base for PM8 serializable contracts."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
        validate_default=True,
    )


class ResolutionStatus(str, Enum):
    PERSISTED = "persisted"
    RENDERER_NATIVE = "renderer_native"
    NOT_REQUIRED = "not_required"


class AssetRole(str, Enum):
    SCENE_VISUAL = "scene_visual"
    SCENE_NARRATION = "scene_narration"
    MUSIC = "music"
    SOUND_EFFECT = "sound_effect"


class MediaFamily(str, Enum):
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    METADATA = "metadata"


class CostStatus(str, Enum):
    FREE = "free"
    KNOWN = "known"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class AssetBinary:
    """Binary output returned by an F4 provider selected for PM8.

    ``delivery_uri`` is optional because a valid local artifact may not yet be
    published to an HTTPS origin.  Remote render adapters must reject missing
    delivery URLs explicitly instead of inventing one.
    """

    content: bytes
    mime_type: str
    file_extension: str
    media_family: MediaFamily
    delivery_uri: str | None = None
    actual_cost_usd: float | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.content, bytes) or not self.content:
            raise ValueError("AssetBinary.content debe contener bytes no vacíos.")
        mime_type = str(self.mime_type).strip().lower()
        extension = str(self.file_extension).strip().lower()
        media_family = MediaFamily(self.media_family)
        if not mime_type.startswith(f"{media_family.value}/") and not (
            media_family is MediaFamily.METADATA
            and mime_type == "application/json"
        ):
            raise ValueError(
                "AssetBinary.mime_type no coincide con media_family."
            )
        if not _has_valid_signature(self.content, mime_type, media_family):
            raise ValueError(
                f"AssetBinary.content no coincide con la firma esperada para '{mime_type}'."
            )
        if not _EXTENSION_PATTERN.fullmatch(extension):
            raise ValueError(
                "AssetBinary.file_extension debe usar una extensión segura, por ejemplo '.png'."
            )
        if self.delivery_uri is not None:
            _validate_https_uri(self.delivery_uri, "delivery_uri")
        actual_cost = self.actual_cost_usd
        if actual_cost is not None:
            if isinstance(actual_cost, bool) or not isinstance(actual_cost, (int, float)):
                raise TypeError("actual_cost_usd debe ser numérico o None.")
            if float(actual_cost) < 0.0:
                raise ValueError("actual_cost_usd no puede ser negativo.")
            actual_cost = float(actual_cost)
        if not isinstance(self.metadata, Mapping):
            raise TypeError("AssetBinary.metadata debe ser Mapping.")
        object.__setattr__(self, "mime_type", mime_type)
        object.__setattr__(self, "file_extension", extension)
        object.__setattr__(self, "media_family", media_family)
        object.__setattr__(self, "actual_cost_usd", actual_cost)
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


class ResolvedAsset(ResolutionModel):
    """One traceable outcome for a visual or audio need."""

    record_id: str = Field(..., min_length=1, max_length=128)
    request_sha256: str
    role: AssetRole
    status: ResolutionStatus
    asset_type: str = Field(..., min_length=1, max_length=64)
    scene_id: str | None = Field(default=None, min_length=1, max_length=128)
    cue_id: str | None = Field(default=None, min_length=1, max_length=128)
    source_reference_ids: tuple[str, ...] = ()
    selected_from_alternative: StrictBool = False
    provider_name: str | None = Field(default=None, min_length=1, max_length=128)
    capability: str | None = Field(default=None, min_length=1, max_length=128)
    media_family: MediaFamily | None = None
    artifact_id: str | None = Field(default=None, min_length=1, max_length=128)
    artifact_relative_path: str | None = Field(default=None, min_length=1)
    sidecar_relative_path: str | None = Field(default=None, min_length=1)
    content_sha256: str | None = None
    mime_type: str | None = Field(default=None, min_length=1, max_length=128)
    size_bytes: StrictNonNegativeInt | None = None
    delivery_uri: str | None = Field(default=None, min_length=1)
    estimated_cost_usd: StrictNonNegativeMoney | None = None
    actual_cost_usd: StrictNonNegativeMoney | None = None
    cost_status: CostStatus = CostStatus.UNKNOWN
    created_at: str | None = Field(default=None, min_length=1)
    metadata: dict[str, JsonValue] = Field(default_factory=dict)

    @field_validator("record_id", "scene_id", "cue_id", "provider_name", "capability", "artifact_id")
    @classmethod
    def _validate_identifiers(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_identifier(value, "resolved asset identifier")

    @field_validator("request_sha256", "content_sha256")
    @classmethod
    def _validate_hashes(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.lower()
        if not _SHA256_PATTERN.fullmatch(normalized):
            raise ValueError("Se esperaba un SHA-256 hexadecimal.")
        return normalized

    @field_validator("asset_type")
    @classmethod
    def _validate_asset_type(cls, value: str) -> str:
        return _validate_identifier(value, "asset_type")

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

    @field_validator("artifact_relative_path", "sidecar_relative_path")
    @classmethod
    def _validate_relative_paths(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.replace("\\", "/")
        path = PurePosixPath(normalized)
        if path.is_absolute() or not path.parts or ".." in path.parts:
            raise ValueError("Las rutas de assets resueltos deben ser relativas y confinadas.")
        return path.as_posix()

    @field_validator("delivery_uri")
    @classmethod
    def _validate_delivery_uri(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_https_uri(value, "delivery_uri")

    @model_validator(mode="after")
    def _validate_status_contract(self) -> "ResolvedAsset":
        artifact_fields = (
            self.provider_name,
            self.capability,
            self.media_family,
            self.artifact_id,
            self.artifact_relative_path,
            self.sidecar_relative_path,
            self.content_sha256,
            self.mime_type,
            self.size_bytes,
            self.created_at,
        )
        if self.status is ResolutionStatus.PERSISTED:
            if any(value is None for value in artifact_fields):
                raise ValueError(
                    "Un ResolvedAsset persisted requiere provider, capability y referencia F3 completa."
                )
        elif any(value is not None for value in artifact_fields):
            raise ValueError(
                "renderer_native/not_required no aceptan provider ni referencia física F3."
            )

        if self.role in {AssetRole.SCENE_VISUAL, AssetRole.SCENE_NARRATION}:
            if self.scene_id is None:
                raise ValueError(f"{self.role.value} requiere scene_id.")
        elif self.scene_id is not None:
            raise ValueError(f"{self.role.value} no acepta scene_id.")
        if self.role is AssetRole.SOUND_EFFECT:
            if self.cue_id is None:
                raise ValueError("sound_effect requiere cue_id.")
        elif self.cue_id is not None:
            raise ValueError(f"{self.role.value} no acepta cue_id.")

        known_cost = self.actual_cost_usd
        if known_cost is None:
            known_cost = self.estimated_cost_usd
        expected_cost_status = (
            CostStatus.UNKNOWN
            if known_cost is None
            else CostStatus.FREE
            if known_cost == 0.0
            else CostStatus.KNOWN
        )
        if self.cost_status is not expected_cost_status:
            raise ValueError(
                f"cost_status debe ser '{expected_cost_status.value}' para los costos registrados."
            )
        return self

    @property
    def locator(self) -> tuple[str, str, str]:
        return (self.role.value, self.scene_id or "", self.cue_id or "")


class AssetResolutionBundle(ResolutionModel):
    """Complete, deterministic catalog derived from one immutable manifest."""

    schema_name: Literal["cips.asset_resolution"] = ASSET_RESOLUTION_SCHEMA_NAME
    schema_version: Literal["1.0"] = ASSET_RESOLUTION_SCHEMA_VERSION
    resolution_id: str = Field(..., min_length=1, max_length=128)
    manifest_id: str = Field(..., min_length=1, max_length=128)
    manifest_sha256: str
    project_id: str = Field(..., min_length=1, max_length=128)
    production_id: str = Field(..., min_length=1, max_length=128)
    assets: tuple[ResolvedAsset, ...] = Field(..., min_length=1)
    total_estimated_cost_usd: StrictNonNegativeMoney = 0.0
    total_actual_cost_usd: StrictNonNegativeMoney = 0.0
    unknown_cost_count: StrictNonNegativeInt = 0
    metadata: dict[str, JsonValue] = Field(default_factory=dict)

    @field_validator("resolution_id", "manifest_id", "project_id", "production_id")
    @classmethod
    def _validate_ids(cls, value: str) -> str:
        return _validate_identifier(value, "asset resolution identifier")

    @field_validator("manifest_sha256")
    @classmethod
    def _validate_manifest_hash(cls, value: str) -> str:
        normalized = value.lower()
        if not _SHA256_PATTERN.fullmatch(normalized):
            raise ValueError("manifest_sha256 debe ser un SHA-256 hexadecimal.")
        return normalized

    @model_validator(mode="after")
    def _validate_bundle(self) -> "AssetResolutionBundle":
        record_ids = [asset.record_id for asset in self.assets]
        if len(set(record_ids)) != len(record_ids):
            raise ValueError("AssetResolutionBundle contiene record_id duplicados.")
        locators = [asset.locator for asset in self.assets]
        if len(set(locators)) != len(locators):
            raise ValueError("AssetResolutionBundle contiene roles/escenas/cues duplicados.")
        if tuple(sorted(self.assets, key=lambda item: item.locator)) != self.assets:
            raise ValueError("assets debe estar ordenado por role, scene_id y cue_id.")

        estimated = round(
            sum(asset.estimated_cost_usd or 0.0 for asset in self.assets),
            8,
        )
        actual = round(
            sum(asset.actual_cost_usd or 0.0 for asset in self.assets),
            8,
        )
        unknown = sum(
            asset.cost_status is CostStatus.UNKNOWN for asset in self.assets
        )
        if abs(self.total_estimated_cost_usd - estimated) > 1e-8:
            raise ValueError("total_estimated_cost_usd no coincide con los assets.")
        if abs(self.total_actual_cost_usd - actual) > 1e-8:
            raise ValueError("total_actual_cost_usd no coincide con los assets.")
        if self.unknown_cost_count != unknown:
            raise ValueError("unknown_cost_count no coincide con los assets.")
        expected_id = deterministic_resolution_id(
            manifest_id=self.manifest_id,
            manifest_sha256=self.manifest_sha256,
            assets=self.assets,
        )
        if self.resolution_id != expected_id:
            raise ValueError(
                "resolution_id no coincide con la identidad determinista esperada."
            )
        return self

    def scene_visual(self, scene_id: str) -> ResolvedAsset:
        return self._one(AssetRole.SCENE_VISUAL, scene_id=scene_id)

    def scene_narration(self, scene_id: str) -> ResolvedAsset:
        return self._one(AssetRole.SCENE_NARRATION, scene_id=scene_id)

    def music(self) -> ResolvedAsset:
        return self._one(AssetRole.MUSIC)

    def sound_effect(self, cue_id: str) -> ResolvedAsset:
        return self._one(AssetRole.SOUND_EFFECT, cue_id=cue_id)

    def _one(
        self,
        role: AssetRole,
        *,
        scene_id: str | None = None,
        cue_id: str | None = None,
    ) -> ResolvedAsset:
        matches = [
            asset
            for asset in self.assets
            if asset.role is role
            and asset.scene_id == scene_id
            and asset.cue_id == cue_id
        ]
        if len(matches) != 1:
            identity = scene_id or cue_id or role.value
            raise KeyError(f"No existe un asset resuelto único para '{identity}'.")
        return matches[0]


def deterministic_request_sha256(payload: Mapping[str, Any]) -> str:
    """Hash a JSON-compatible provider-neutral request deterministically."""

    encoded = json.dumps(
        dict(payload),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def deterministic_record_id(request_sha256: str, provider_name: str | None) -> str:
    provider = provider_name or "renderer"
    digest = hashlib.sha256(
        f"{request_sha256}|{provider}".encode("utf-8")
    ).hexdigest()[:24]
    return f"asset-{digest}"


def deterministic_resolution_id(
    *,
    manifest_id: str,
    manifest_sha256: str,
    assets: tuple[ResolvedAsset, ...],
) -> str:
    payload = {
        "manifest_id": manifest_id,
        "manifest_sha256": manifest_sha256,
        "records": [asset.record_id for asset in assets],
    }
    digest = deterministic_request_sha256(payload)[:24]
    return f"resolution-{digest}"


def _validate_identifier(value: str, label: str) -> str:
    normalized = str(value).strip()
    if not _ID_PATTERN.fullmatch(normalized):
        raise ValueError(
            f"{label} debe usar letras, números, punto, guion o guion bajo."
        )
    return normalized


def _validate_https_uri(value: str, label: str) -> str:
    normalized = str(value).strip()
    parsed = urlsplit(normalized)
    if (
        parsed.scheme.lower() != "https"
        or not parsed.netloc
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise ValueError(f"{label} debe ser una URL HTTPS sin credenciales.")
    return normalized


def _has_valid_signature(
    content: bytes,
    mime_type: str,
    media_family: MediaFamily,
) -> bool:
    """Apply lightweight binary guards without decoding or transcoding media."""

    head = content[:64]
    if media_family is MediaFamily.IMAGE:
        if mime_type == "image/png":
            return head.startswith(b"\x89PNG\r\n\x1a\n")
        if mime_type == "image/jpeg":
            return head.startswith(b"\xff\xd8\xff")
        if mime_type == "image/gif":
            return head.startswith((b"GIF87a", b"GIF89a"))
        if mime_type == "image/webp":
            return len(head) >= 12 and head.startswith(b"RIFF") and head[8:12] == b"WEBP"
        if mime_type == "image/bmp":
            return head.startswith(b"BM")
        if mime_type == "image/tiff":
            return head.startswith((b"II*\x00", b"MM\x00*"))
        if mime_type == "image/avif":
            return b"ftypavif" in head or b"ftypavis" in head
        if mime_type == "image/svg+xml":
            stripped = content.lstrip()[:256].lower()
            return stripped.startswith(b"<svg") or b"<svg" in stripped
        return False
    if media_family is MediaFamily.VIDEO:
        if mime_type in {"video/mp4", "video/quicktime", "video/x-m4v"}:
            return len(head) >= 12 and b"ftyp" in head[4:32]
        if mime_type in {"video/webm", "video/x-matroska"}:
            return head.startswith(b"\x1a\x45\xdf\xa3")
        if mime_type == "video/x-msvideo":
            return len(head) >= 12 and head.startswith(b"RIFF") and head[8:12] == b"AVI "
        if mime_type == "video/mpeg":
            return head.startswith((b"\x00\x00\x01\xba", b"\x00\x00\x01\xb3"))
        return False
    if media_family is MediaFamily.AUDIO:
        if mime_type == "audio/mpeg":
            return head.startswith(b"ID3") or (
                len(head) >= 2 and head[0] == 0xFF and (head[1] & 0xE0) == 0xE0
            )
        if mime_type in {"audio/wav", "audio/x-wav"}:
            return len(head) >= 12 and head.startswith(b"RIFF") and head[8:12] == b"WAVE"
        if mime_type == "audio/flac":
            return head.startswith(b"fLaC")
        if mime_type in {"audio/ogg", "audio/opus"}:
            return head.startswith(b"OggS")
        if mime_type == "audio/mp4":
            return len(head) >= 12 and b"ftyp" in head[4:32]
        if mime_type == "audio/aac":
            return len(head) >= 2 and head[0] == 0xFF and (head[1] & 0xF0) == 0xF0
        return False
    if media_family is MediaFamily.METADATA:
        try:
            return isinstance(json.loads(content.decode("utf-8")), dict)
        except (UnicodeDecodeError, json.JSONDecodeError):
            return False
    return False


__all__ = [
    "ASSET_RESOLUTION_FILENAME",
    "ASSET_RESOLUTION_SCHEMA_NAME",
    "ASSET_RESOLUTION_SCHEMA_VERSION",
    "AssetBinary",
    "AssetResolutionBundle",
    "AssetRole",
    "CostStatus",
    "MediaFamily",
    "ResolutionStatus",
    "ResolvedAsset",
    "deterministic_record_id",
    "deterministic_request_sha256",
    "deterministic_resolution_id",
]
