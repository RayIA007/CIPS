"""Concrete provider boundaries reusable by PM8 without external SDK imports."""

from __future__ import annotations

import mimetypes
from collections.abc import Callable, Mapping
from copy import deepcopy
from pathlib import Path
from typing import Any

from media_provider import MediaProvider, MediaRequest, MediaResult, normalize_capability

from .models import AssetBinary, MediaFamily


AssetBackend = Callable[[MediaRequest], AssetBinary]
CostEstimator = Callable[[MediaRequest], float | None]


class BinaryAssetProviderAdapter(MediaProvider):
    """Adapt an injected scene-level backend to the F4 ``MediaProvider`` API."""

    provider_name = "binary_asset"

    def __init__(
        self,
        backend: AssetBackend,
        *,
        provider_name: str,
        capabilities: Mapping[str, Mapping[str, Any] | None],
        cost_estimator: CostEstimator | None = None,
    ) -> None:
        if not callable(backend):
            raise TypeError("backend debe ser callable.")
        if cost_estimator is not None and not callable(cost_estimator):
            raise TypeError("cost_estimator debe ser callable o None.")
        self.provider_name = _normalize_provider_name(provider_name)
        self._backend = backend
        self._capabilities = _normalize_capabilities(capabilities)
        self._cost_estimator = cost_estimator
        self.calls: list[MediaRequest] = []

    def capabilities(self) -> dict[str, dict[str, Any]]:
        return deepcopy(self._capabilities)

    def estimate_cost(self, request: MediaRequest) -> float | None:
        if self._cost_estimator is not None:
            return self._cost_estimator(request)
        capability = normalize_capability(request.capability)
        metadata = self._capabilities.get(capability, {})
        if metadata.get("cost_tier") == "free" or metadata.get("free_tier") is True:
            return 0.0
        return None

    def generate(self, request: MediaRequest) -> MediaResult:
        errors = self.validate_input(request)
        if errors:
            return MediaResult.fail(errors=errors)
        self.calls.append(request)
        try:
            output = self._backend(request)
        except Exception as error:
            return MediaResult.fail(
                message=f"El provider '{self.provider_name}' falló.",
                errors=[f"{type(error).__name__}: {error}"],
                metadata={"provider": self.provider_name},
            )
        if not isinstance(output, AssetBinary):
            return MediaResult.fail(
                message=f"El provider '{self.provider_name}' devolvió un contrato inválido.",
                errors=["output_not_asset_binary"],
                metadata={"provider": self.provider_name},
            )
        return MediaResult.ok(
            output,
            metadata={
                "provider": self.provider_name,
                "capability": normalize_capability(request.capability),
            },
        )


class ExistingAssetProvider(MediaProvider):
    """Resolve an explicit asset ID from an injected, allowlisted local catalog."""

    provider_name = "local_existing_assets"
    capability_name = "existing_asset_resolution"

    def __init__(
        self,
        assets: Mapping[str, str | Path],
        *,
        delivery_uris: Mapping[str, str] | None = None,
        provider_name: str | None = None,
    ) -> None:
        if not isinstance(assets, Mapping) or not assets:
            raise ValueError("assets debe ser un Mapping no vacío.")
        self.provider_name = _normalize_provider_name(
            provider_name or self.provider_name
        )
        self._assets = {
            _normalize_asset_id(asset_id): Path(path).expanduser().resolve(strict=False)
            for asset_id, path in assets.items()
        }
        self._delivery_uris = {
            _normalize_asset_id(asset_id): str(uri).strip()
            for asset_id, uri in dict(delivery_uris or {}).items()
        }
        unknown = sorted(set(self._delivery_uris) - set(self._assets))
        if unknown:
            raise ValueError(
                "delivery_uris contiene IDs que no existen en assets: "
                + ", ".join(unknown)
            )
        self.calls: list[MediaRequest] = []

    def capabilities(self) -> dict[str, dict[str, Any]]:
        return {
            self.capability_name: {
                "available": True,
                "cost_tier": "free",
                "free_tier": True,
                "local": True,
                "quality_tier": "high",
                "source": "allowlisted_local_catalog",
            }
        }

    def estimate_cost(self, request: MediaRequest) -> float | None:
        return 0.0

    def generate(self, request: MediaRequest) -> MediaResult:
        errors = self.validate_input(request)
        if errors:
            return MediaResult.fail(errors=errors)
        if not isinstance(request.payload, Mapping):
            return MediaResult.fail(errors=["payload debe ser Mapping."])
        raw_id = request.payload.get("existing_asset_id")
        try:
            asset_id = _normalize_asset_id(raw_id)
        except (TypeError, ValueError) as error:
            return MediaResult.fail(errors=[str(error)])
        path = self._assets.get(asset_id)
        if path is None:
            return MediaResult.fail(
                message="El asset existente solicitado no está en el catálogo permitido.",
                errors=[f"existing_asset_not_found:{asset_id}"],
                metadata={"provider": self.provider_name},
            )
        if not path.is_file() or path.stat().st_size <= 0:
            return MediaResult.fail(
                message="El asset existente no es un archivo físico válido.",
                errors=[f"existing_asset_invalid:{asset_id}"],
                metadata={"provider": self.provider_name},
            )
        try:
            mime_type, family = _media_contract(path)
            output = AssetBinary(
                content=path.read_bytes(),
                mime_type=mime_type,
                file_extension=path.suffix.lower(),
                media_family=family,
                delivery_uri=self._delivery_uris.get(asset_id),
                actual_cost_usd=0.0,
                metadata={
                    "existing_asset_id": asset_id,
                    "original_filename": path.name,
                    "source": "allowlisted_local_catalog",
                },
            )
        except (OSError, TypeError, ValueError) as error:
            return MediaResult.fail(
                message="No fue posible leer el asset existente.",
                errors=[f"{type(error).__name__}: {error}"],
                metadata={"provider": self.provider_name},
            )
        self.calls.append(request)
        return MediaResult.ok(
            output,
            metadata={
                "provider": self.provider_name,
                "capability": self.capability_name,
            },
        )


def _media_contract(path: Path) -> tuple[str, MediaFamily]:
    mime_type = (mimetypes.guess_type(path.name)[0] or "").lower()
    if mime_type.startswith("image/"):
        return mime_type, MediaFamily.IMAGE
    if mime_type.startswith("video/"):
        return mime_type, MediaFamily.VIDEO
    if mime_type.startswith("audio/"):
        return mime_type, MediaFamily.AUDIO
    raise ValueError(f"Tipo de asset existente no soportado: {path.suffix or '<sin extensión>'}")


def _normalize_provider_name(value: Any) -> str:
    normalized = str(value).strip().lower()
    if not normalized or normalized == "base":
        raise ValueError("provider_name no puede estar vacío ni ser 'base'.")
    return normalized


def _normalize_asset_id(value: Any) -> str:
    normalized = str(value).strip().lower()
    if not normalized:
        raise ValueError("existing_asset_id es obligatorio.")
    return normalized


def _normalize_capabilities(
    capabilities: Mapping[str, Mapping[str, Any] | None],
) -> dict[str, dict[str, Any]]:
    if not isinstance(capabilities, Mapping) or not capabilities:
        raise ValueError("capabilities debe ser un Mapping no vacío.")
    result: dict[str, dict[str, Any]] = {}
    for name, metadata in capabilities.items():
        capability = normalize_capability(name)
        if metadata is None:
            result[capability] = {}
        elif isinstance(metadata, Mapping):
            result[capability] = deepcopy(dict(metadata))
        else:
            raise TypeError("La metadata de capability debe ser Mapping o None.")
    return result


__all__ = [
    "AssetBackend",
    "BinaryAssetProviderAdapter",
    "CostEstimator",
    "ExistingAssetProvider",
]
