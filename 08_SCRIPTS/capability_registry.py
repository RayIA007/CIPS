"""
=========================================================
Proyecto : CIPS
Release  : 0.5
Build    : 001
Archivo  : capability_registry.py
Estado   : RELEASE
=========================================================

Vista de capacidades multimedia registradas en CIPS.

``CapabilityRegistry`` no posee providers ni duplica su estado. Consulta
``MediaProviderRegistry`` para responder qué providers declaran una
capacidad. La selección estratégica pertenece a ``CapabilityResolver``.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from media_provider import MediaProvider, normalize_capability
from media_provider_registry import MediaProviderRegistry


class CapabilityRegistry:
    """Índice dinámico de capacidades sobre MediaProviderRegistry."""

    def __init__(self, provider_registry: MediaProviderRegistry) -> None:
        if not isinstance(provider_registry, MediaProviderRegistry):
            raise TypeError(
                "provider_registry debe ser MediaProviderRegistry."
            )
        self._provider_registry = provider_registry

    @property
    def provider_registry(self) -> MediaProviderRegistry:
        """Registro multimedia que actúa como fuente de verdad."""

        return self._provider_registry

    def capabilities(
        self,
        *,
        enabled_only: bool = True,
    ) -> dict[str, list[str]]:
        """Devuelve capability -> providers en orden determinista."""

        index: dict[str, list[str]] = {}
        for provider in self._provider_registry.providers(
            enabled_only=enabled_only
        ):
            provider_name = self._normalize_provider_name(
                provider.provider_name
            )
            for capability in self._provider_capabilities(provider):
                index.setdefault(capability, []).append(provider_name)

        return {
            capability: sorted(provider_names)
            for capability, provider_names in sorted(index.items())
        }

    def providers_for(
        self,
        capability: str,
        *,
        enabled_only: bool = True,
    ) -> list[str]:
        """Devuelve providers que declaran una capacidad concreta."""

        normalized = normalize_capability(capability)
        return list(
            self.capabilities(enabled_only=enabled_only).get(
                normalized,
                [],
            )
        )

    def provider_supports(
        self,
        provider_name: str,
        capability: str,
        *,
        require_enabled: bool = True,
    ) -> bool:
        """Indica si un provider registrado declara la capacidad."""

        provider = self._provider_registry.get(
            provider_name,
            require_enabled=require_enabled,
        )
        normalized = normalize_capability(capability)
        return normalized in self._provider_capabilities(provider)

    def metadata_for(
        self,
        provider_name: str,
        capability: str,
        *,
        require_enabled: bool = True,
    ) -> dict[str, Any]:
        """Devuelve una copia de metadatos declarativos de la capacidad."""

        provider = self._provider_registry.get(
            provider_name,
            require_enabled=require_enabled,
        )
        normalized = normalize_capability(capability)
        capabilities = self._provider_capabilities(provider)
        if normalized not in capabilities:
            return {}
        return deepcopy(capabilities[normalized])

    @staticmethod
    def _provider_capabilities(
        provider: MediaProvider,
    ) -> dict[str, dict[str, Any]]:
        declared = provider.capabilities()
        if not isinstance(declared, dict):
            raise TypeError(
                "capabilities() debe devolver un diccionario."
            )

        result: dict[str, dict[str, Any]] = {}
        for raw_name, raw_metadata in declared.items():
            capability = normalize_capability(raw_name)
            if raw_metadata is None:
                metadata: dict[str, Any] = {}
            elif isinstance(raw_metadata, dict):
                metadata = deepcopy(raw_metadata)
            else:
                raise TypeError(
                    "Los metadatos de una capacidad deben ser un diccionario."
                )
            result[capability] = metadata
        return result

    @staticmethod
    def _normalize_provider_name(name: str) -> str:
        if not isinstance(name, str):
            raise TypeError(
                "El nombre del proveedor debe ser una cadena de texto."
            )
        normalized = name.strip().lower()
        if not normalized:
            raise ValueError(
                "El nombre del proveedor no puede estar vacío."
            )
        return normalized


__all__ = ["CapabilityRegistry"]
