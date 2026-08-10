"""
=========================================================
Proyecto : CIPS
Release  : 0.5
Build    : 001
Archivo  : media_provider_registry.py
Estado   : RELEASE
=========================================================

Inventario de proveedores multimedia de CIPS.

Este registro está separado del ``ProviderRegistry`` LLM existente. No
selecciona estrategias, no ejecuta failover y no realiza llamadas a
proveedores. Su responsabilidad es inventariar instancias multimedia y
su estado de habilitación.
"""

from __future__ import annotations

from copy import deepcopy
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from media_provider import MediaProvider, normalize_capability


class MediaProviderRegistryError(RuntimeError):
    """Error base del registro de proveedores multimedia."""


class MediaProviderAlreadyRegisteredError(MediaProviderRegistryError):
    """El nombre solicitado ya pertenece a otro proveedor multimedia."""


class MediaProviderNotFoundError(MediaProviderRegistryError):
    """El proveedor multimedia solicitado no está registrado."""


class MediaProviderDisabledError(MediaProviderRegistryError):
    """El proveedor multimedia solicitado está deshabilitado."""


@dataclass(slots=True)
class MediaProviderRegistration:
    """Entrada interna asociada con un proveedor multimedia."""

    provider: MediaProvider
    enabled: bool = True


class MediaProviderRegistry:
    """Inventario central de proveedores multimedia."""

    def __init__(
        self,
        providers: Iterable[MediaProvider] | None = None,
    ) -> None:
        self._registrations: dict[str, MediaProviderRegistration] = {}
        for provider in providers or ():
            self.register(provider)

    def register(
        self,
        provider: MediaProvider,
        *,
        enabled: bool = True,
        replace: bool = False,
    ) -> MediaProvider:
        """Registra un provider multimedia y devuelve la misma instancia."""

        self._validate_provider(provider)
        name = self._normalize_name(provider.provider_name)
        if name == "base":
            raise ValueError(
                "'base' es un nombre reservado y no puede registrarse."
            )

        if name in self._registrations and not replace:
            raise MediaProviderAlreadyRegisteredError(
                f"El proveedor multimedia '{name}' ya está registrado."
            )

        self._registrations[name] = MediaProviderRegistration(
            provider=provider,
            enabled=bool(enabled),
        )
        return provider

    def unregister(self, name: str) -> MediaProvider:
        """Retira y devuelve el provider multimedia registrado."""

        normalized = self._normalize_name(name)
        registration = self._registrations.pop(normalized, None)
        if registration is None:
            raise MediaProviderNotFoundError(
                f"El proveedor multimedia '{normalized}' no está registrado."
            )
        return registration.provider

    def exists(self, name: str) -> bool:
        """Indica si existe un provider multimedia con ese nombre."""

        try:
            normalized = self._normalize_name(name)
        except (TypeError, ValueError):
            return False
        return normalized in self._registrations

    def get(
        self,
        name: str,
        *,
        require_enabled: bool = True,
    ) -> MediaProvider:
        """Obtiene un provider multimedia por nombre."""

        normalized = self._normalize_name(name)
        registration = self._registrations.get(normalized)
        if registration is None:
            raise MediaProviderNotFoundError(
                f"El proveedor multimedia '{normalized}' no está registrado."
            )
        if require_enabled and not registration.enabled:
            raise MediaProviderDisabledError(
                f"El proveedor multimedia '{normalized}' está deshabilitado."
            )
        return registration.provider

    def enable(self, name: str) -> None:
        """Habilita un provider registrado."""

        self._get_registration(name).enabled = True

    def disable(self, name: str) -> None:
        """Deshabilita un provider registrado sin eliminarlo."""

        self._get_registration(name).enabled = False

    def is_enabled(self, name: str) -> bool:
        """Devuelve el estado de habilitación del provider."""

        return self._get_registration(name).enabled

    def list(self, *, enabled_only: bool = False) -> list[str]:
        """Devuelve nombres registrados en orden alfabético."""

        names = [
            name
            for name, registration in self._registrations.items()
            if not enabled_only or registration.enabled
        ]
        return sorted(names)

    def providers(
        self,
        *,
        enabled_only: bool = False,
    ) -> list[MediaProvider]:
        """Devuelve providers registrados en orden por nombre."""

        return [
            self._registrations[name].provider
            for name in self.list(enabled_only=enabled_only)
        ]

    def capabilities(
        self,
        name: str | None = None,
        *,
        enabled_only: bool = False,
    ) -> dict[str, Any]:
        """Expone una copia de las capacidades declaradas."""

        if name is not None:
            provider = self.get(name, require_enabled=enabled_only)
            return self._copy_capabilities(provider)

        return {
            provider_name: self._copy_capabilities(
                self._registrations[provider_name].provider
            )
            for provider_name in self.list(enabled_only=enabled_only)
        }

    def status(self) -> dict[str, dict[str, Any]]:
        """Construye un resumen serializable del inventario multimedia."""

        return {
            name: {
                "enabled": registration.enabled,
                "provider": registration.provider.provider_name,
                "capabilities": self._copy_capabilities(
                    registration.provider
                ),
            }
            for name, registration in sorted(self._registrations.items())
        }

    def clear(self) -> None:
        """Elimina todos los registros multimedia."""

        self._registrations.clear()

    def __contains__(self, name: object) -> bool:
        return isinstance(name, str) and self.exists(name)

    def __len__(self) -> int:
        return len(self._registrations)

    def __iter__(self):
        return iter(self.list())

    def _get_registration(self, name: str) -> MediaProviderRegistration:
        normalized = self._normalize_name(name)
        registration = self._registrations.get(normalized)
        if registration is None:
            raise MediaProviderNotFoundError(
                f"El proveedor multimedia '{normalized}' no está registrado."
            )
        return registration

    @staticmethod
    def _validate_provider(provider: MediaProvider) -> None:
        if not isinstance(provider, MediaProvider):
            raise TypeError(
                "provider debe ser una instancia de MediaProvider."
            )

    @staticmethod
    def _normalize_name(name: str) -> str:
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

    @staticmethod
    def _copy_capabilities(
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


__all__ = [
    "MediaProviderAlreadyRegisteredError",
    "MediaProviderDisabledError",
    "MediaProviderNotFoundError",
    "MediaProviderRegistration",
    "MediaProviderRegistry",
    "MediaProviderRegistryError",
]
