"""Approved, allowlisted physical-asset catalog used by PM9 acceptance."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Literal
from urllib.parse import parse_qsl, urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from asset_resolution import AssetBinary, MediaFamily
from media_provider import MediaProvider, MediaRequest, MediaResult, normalize_capability


class AssetCatalogError(ValueError):
    """The PM9 catalog is missing, inconsistent, or unsafe."""


class CatalogEntry(BaseModel):
    """One preapproved local asset plus its stable HTTPS delivery location."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    entry_id: str = Field(..., min_length=1, max_length=128)
    capability: str = Field(..., min_length=1, max_length=128)
    role: Literal["scene_visual", "scene_narration", "music", "sound_effect"]
    relative_path: str = Field(..., min_length=1)
    delivery_uri: str = Field(..., min_length=1)
    mime_type: str = Field(..., min_length=1, max_length=128)
    media_family: MediaFamily
    file_extension: str = Field(..., pattern=r"^\.[a-z0-9]{1,10}$")
    scene_id: str | None = Field(default=None, min_length=1, max_length=128)
    cue_id: str | None = Field(default=None, min_length=1, max_length=128)
    existing_asset_id: str | None = Field(default=None, min_length=1, max_length=128)
    source_url: str = Field(..., min_length=1)
    license_name: str = Field(..., min_length=1, max_length=256)
    attribution: str | None = Field(default=None, min_length=1, max_length=512)
    actual_cost_usd: float = Field(default=0.0, ge=0.0)

    @field_validator("capability")
    @classmethod
    def _normalize_capability(cls, value: str) -> str:
        return normalize_capability(value)

    @field_validator("relative_path")
    @classmethod
    def _validate_relative_path(cls, value: str) -> str:
        normalized = value.replace("\\", "/")
        path = Path(normalized)
        if path.is_absolute() or ".." in path.parts or not path.parts:
            raise ValueError("relative_path debe ser relativo y confinado.")
        return path.as_posix()

    @field_validator("delivery_uri", "source_url")
    @classmethod
    def _validate_public_https(cls, value: str) -> str:
        normalized = value.strip()
        parsed = urlsplit(normalized)
        if (
            parsed.scheme.lower() != "https"
            or not parsed.netloc
            or parsed.username is not None
            or parsed.password is not None
        ):
            raise ValueError("Las URLs del catálogo deben ser HTTPS públicas.")
        sensitive_query_names = {
            "api_key",
            "apikey",
            "key",
            "signature",
            "sig",
            "token",
            "x-amz-signature",
        }
        present = {name.casefold() for name, _ in parse_qsl(parsed.query)}
        if sensitive_query_names & present:
            raise ValueError("El catálogo no acepta URLs firmadas ni credenciales.")
        return normalized

    @model_validator(mode="after")
    def _validate_locator(self) -> "CatalogEntry":
        if self.role in {"scene_visual", "scene_narration"}:
            if self.scene_id is None or self.cue_id is not None:
                raise ValueError(f"{self.role} requiere scene_id y no acepta cue_id.")
        elif self.role == "sound_effect":
            if self.cue_id is None or self.scene_id is not None:
                raise ValueError("sound_effect requiere cue_id y no acepta scene_id.")
        elif self.scene_id is not None or self.cue_id is not None:
            raise ValueError("music no acepta scene_id ni cue_id.")
        if self.capability == "existing_asset_resolution" and not self.existing_asset_id:
            raise ValueError(
                "existing_asset_resolution requiere existing_asset_id en el catálogo."
            )
        if self.capability != "existing_asset_resolution" and self.existing_asset_id:
            raise ValueError(
                "existing_asset_id solo corresponde a existing_asset_resolution."
            )
        if not self.mime_type.startswith(f"{self.media_family.value}/"):
            raise ValueError("mime_type no coincide con media_family.")
        return self

    @property
    def locator(self) -> tuple[str, str, str]:
        return (self.role, self.scene_id or "", self.cue_id or "")


class ApprovedAssetCatalog(BaseModel):
    """Immutable catalog loaded by the PM9 provider boundary."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["cips.production_acceptance.asset_catalog"] = (
        "cips.production_acceptance.asset_catalog"
    )
    schema_version: Literal["1.0"] = "1.0"
    entries: tuple[CatalogEntry, ...] = Field(..., min_length=1)

    @model_validator(mode="after")
    def _validate_unique_entries(self) -> "ApprovedAssetCatalog":
        entry_ids = [entry.entry_id for entry in self.entries]
        if len(set(entry_ids)) != len(entry_ids):
            raise ValueError("El catálogo contiene entry_id duplicados.")
        locators = [entry.locator for entry in self.entries]
        if len(set(locators)) != len(locators):
            raise ValueError("El catálogo contiene locators de asset duplicados.")
        return self

    @classmethod
    def load(cls, path: str | Path) -> "ApprovedAssetCatalog":
        catalog_path = Path(path).expanduser().resolve(strict=False)
        try:
            payload = json.loads(catalog_path.read_text(encoding="utf-8"))
            return cls.model_validate(payload)
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as error:
            raise AssetCatalogError(
                f"No se pudo cargar un catálogo PM9 válido: {catalog_path}"
            ) from error


class ApprovedAssetCatalogProvider(MediaProvider):
    """Serve only exact, locally allowlisted catalog entries through F4/PM8."""

    provider_name = "pm9_approved_asset_catalog"

    def __init__(
        self,
        catalog: ApprovedAssetCatalog,
        *,
        assets_root: str | Path,
    ) -> None:
        if not isinstance(catalog, ApprovedAssetCatalog):
            raise TypeError("catalog debe ser ApprovedAssetCatalog.")
        self._catalog = catalog
        self._assets_root = Path(assets_root).expanduser().resolve(strict=False)
        self.calls: list[MediaRequest] = []

    @property
    def catalog(self) -> ApprovedAssetCatalog:
        return self._catalog

    def capabilities(self) -> dict[str, dict[str, Any]]:
        return {
            capability: {
                "available": True,
                "cost_tier": "free",
                "free_tier": True,
                "quality_tier": "high",
                "priority": 100,
                "source": "pm9_approved_catalog",
            }
            for capability in sorted(
                {entry.capability for entry in self._catalog.entries}
            )
        }

    def estimate_cost(self, request: MediaRequest) -> float | None:
        entry = self._match(request)
        return entry.actual_cost_usd if entry is not None else None

    def generate(self, request: MediaRequest) -> MediaResult:
        errors = self.validate_input(request)
        if errors:
            return MediaResult.fail(errors=errors)
        entry = self._match(request)
        if entry is None:
            return MediaResult.fail(
                message="El catálogo PM9 no contiene el asset solicitado.",
                errors=["pm9_catalog_entry_not_found"],
                metadata={"provider": self.provider_name},
            )
        path = (self._assets_root / entry.relative_path).resolve(strict=False)
        try:
            path.relative_to(self._assets_root)
        except ValueError:
            return MediaResult.fail(errors=["pm9_catalog_path_escape"])
        if not path.is_file() or path.stat().st_size <= 0:
            return MediaResult.fail(
                message="El asset físico del catálogo no existe o está vacío.",
                errors=[f"pm9_catalog_asset_missing:{entry.entry_id}"],
            )
        try:
            output = AssetBinary(
                content=path.read_bytes(),
                mime_type=entry.mime_type,
                file_extension=entry.file_extension,
                media_family=entry.media_family,
                delivery_uri=entry.delivery_uri,
                actual_cost_usd=entry.actual_cost_usd,
                metadata={
                    "catalog_entry_id": entry.entry_id,
                    "source_url": entry.source_url,
                    "license_name": entry.license_name,
                    "attribution": entry.attribution or "",
                },
            )
        except (OSError, ValueError) as error:
            return MediaResult.fail(
                message="El asset del catálogo no cumple el contrato binario PM8.",
                errors=[f"{type(error).__name__}: {error}"],
            )
        self.calls.append(request)
        return MediaResult.ok(
            output,
            metadata={
                "provider": self.provider_name,
                "capability": entry.capability,
                "catalog_entry_id": entry.entry_id,
            },
        )

    def _match(self, request: MediaRequest) -> CatalogEntry | None:
        if not isinstance(request, MediaRequest) or not isinstance(
            request.payload, Mapping
        ):
            return None
        try:
            capability = normalize_capability(request.capability)
        except (TypeError, ValueError):
            return None
        role = str(request.payload.get("role", "")).strip()
        scene_id = str(request.payload.get("scene_id") or "").strip()
        cue_id = str(request.payload.get("cue_id") or "").strip()
        existing_asset_id = str(
            request.payload.get("existing_asset_id") or ""
        ).strip()
        matches = [
            entry
            for entry in self._catalog.entries
            if entry.capability == capability
            and entry.role == role
            and (entry.scene_id or "") == scene_id
            and (entry.cue_id or "") == cue_id
            and (entry.existing_asset_id or "") == existing_asset_id
        ]
        return matches[0] if len(matches) == 1 else None


__all__ = [
    "ApprovedAssetCatalog",
    "ApprovedAssetCatalogProvider",
    "AssetCatalogError",
    "CatalogEntry",
]
