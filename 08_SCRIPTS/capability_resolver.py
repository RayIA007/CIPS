"""
=========================================================
Proyecto : CIPS
Release  : 0.5
Build    : 001
Archivo  : capability_resolver.py
Estado   : RELEASE
=========================================================

Resolución determinista de proveedores multimedia por capacidad.

F4.1 sólo establece una política mínima y testeable: preferencia
explícita cuando se solicita; en otro caso, primer candidato por nombre
normalizado. No implementa todavía ranking por coste/calidad/latencia,
health probing, retry ni failover de ejecución.
"""

from __future__ import annotations

from collections.abc import Iterable

from capability_registry import CapabilityRegistry
from media_provider import MediaProvider, normalize_capability
from media_provider_registry import (
    MediaProviderDisabledError,
    MediaProviderNotFoundError,
    MediaProviderRegistry,
)


class CapabilityResolutionError(RuntimeError):
    """Error base de resolución de capacidades multimedia."""


class CapabilityNotAvailableError(CapabilityResolutionError):
    """No hay un provider habilitado para la capacidad solicitada."""


class PreferredProviderUnavailableError(CapabilityResolutionError):
    """El provider preferido no puede satisfacer la capacidad solicitada."""


class CapabilityResolver:
    """Selecciona providers multimedia sin ejecutar llamadas externas."""

    def __init__(
        self,
        provider_registry: MediaProviderRegistry,
        capability_registry: CapabilityRegistry | None = None,
    ) -> None:
        if not isinstance(provider_registry, MediaProviderRegistry):
            raise TypeError(
                "provider_registry debe ser MediaProviderRegistry."
            )

        if capability_registry is None:
            capability_registry = CapabilityRegistry(provider_registry)
        elif not isinstance(capability_registry, CapabilityRegistry):
            raise TypeError(
                "capability_registry debe ser CapabilityRegistry."
            )
        elif capability_registry.provider_registry is not provider_registry:
            raise ValueError(
                "CapabilityRegistry debe usar el mismo MediaProviderRegistry."
            )

        self._provider_registry = provider_registry
        self._capability_registry = capability_registry

    def candidates(
        self,
        capability: str,
        *,
        exclude: Iterable[str] | None = None,
    ) -> list[MediaProvider]:
        """Devuelve candidatos habilitados en orden determinista."""

        normalized = normalize_capability(capability)
        excluded = {
            self._normalize_provider_name(name)
            for name in (exclude or ())
        }
        names = [
            name
            for name in self._capability_registry.providers_for(
                normalized,
                enabled_only=True,
            )
            if name not in excluded
        ]
        return [self._provider_registry.get(name) for name in names]

    def resolve(
        self,
        capability: str,
        *,
        preferred_provider: str | None = None,
        exclude: Iterable[str] | None = None,
    ) -> MediaProvider:
        """Resuelve un provider habilitado para la capacidad solicitada."""

        normalized = normalize_capability(capability)
        excluded = {
            self._normalize_provider_name(name)
            for name in (exclude or ())
        }

        if preferred_provider is not None:
            preferred = self._normalize_provider_name(preferred_provider)
            if preferred in excluded:
                raise PreferredProviderUnavailableError(
                    f"El proveedor preferido '{preferred}' está excluido."
                )
            try:
                provider = self._provider_registry.get(preferred)
            except (
                MediaProviderNotFoundError,
                MediaProviderDisabledError,
            ) as error:
                raise PreferredProviderUnavailableError(
                    f"El proveedor preferido '{preferred}' no está disponible."
                ) from error

            if not self._capability_registry.provider_supports(
                preferred,
                normalized,
            ):
                raise PreferredProviderUnavailableError(
                    f"El proveedor preferido '{preferred}' no soporta "
                    f"la capacidad '{normalized}'."
                )
            return provider

        candidates = self.candidates(normalized, exclude=excluded)
        if not candidates:
            raise CapabilityNotAvailableError(
                f"No hay proveedores habilitados para la capacidad "
                f"'{normalized}'."
            )
        return candidates[0]

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


__all__ = [
    "CapabilityNotAvailableError",
    "CapabilityResolutionError",
    "CapabilityResolver",
    "PreferredProviderUnavailableError",
]
