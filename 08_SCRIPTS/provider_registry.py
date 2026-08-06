"""
=========================================================
Proyecto : CIPS
Release  : 0.5
Build    : 001
Archivo  : provider_registry.py
Estado   : RELEASE
=========================================================

Registro central de proveedores LLM disponibles en CIPS.

Responsabilidades:
- registrar y retirar proveedores;
- habilitar o deshabilitar proveedores;
- resolver proveedores por nombre;
- exponer capacidades y modelos declarados;
- mantener el inventario desacoplado de la ejecución.

Este componente no envía prompts ni selecciona estrategias de
reintento, failover o balanceo. Esas responsabilidades pertenecen
al administrador u orquestador de proveedores.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from llm_provider import LLMProvider


class ProviderRegistryError(RuntimeError):
    """Error base del registro de proveedores."""


class ProviderAlreadyRegisteredError(ProviderRegistryError):
    """El nombre solicitado ya pertenece a otro proveedor."""


class ProviderNotFoundError(ProviderRegistryError):
    """El proveedor solicitado no está registrado."""


class ProviderDisabledError(ProviderRegistryError):
    """El proveedor solicitado está deshabilitado."""


@dataclass(slots=True)
class ProviderRegistration:
    """Entrada interna asociada con un proveedor registrado."""

    provider: LLMProvider
    enabled: bool = True


class ProviderRegistry:
    """
    Inventario central de proveedores LLM.

    Los nombres se normalizan eliminando espacios laterales y
    convirtiéndolos a minúsculas. De esta forma, ``Mock`` y ``mock``
    representan el mismo identificador.
    """

    def __init__(
        self,
        providers: Iterable[LLMProvider] | None = None,
    ) -> None:
        self._registrations: dict[str, ProviderRegistration] = {}

        for provider in providers or ():
            self.register(provider)

    def register(
        self,
        provider: LLMProvider,
        *,
        enabled: bool = True,
        replace: bool = False,
    ) -> LLMProvider:
        """
        Registra un proveedor y devuelve la misma instancia.

        Args:
            provider:
                Instancia que implementa ``LLMProvider``.
            enabled:
                Estado inicial del proveedor.
            replace:
                Permite sustituir explícitamente un registro previo.

        Raises:
            TypeError:
                Si ``provider`` no implementa ``LLMProvider``.
            ValueError:
                Si ``provider_name`` está vacío o reservado.
            ProviderAlreadyRegisteredError:
                Si el nombre ya existe y ``replace`` es falso.
        """

        self._validate_provider(provider)
        name = self._normalize_name(provider.provider_name)

        if name == "base":
            raise ValueError(
                "'base' es un nombre reservado y no puede registrarse."
            )

        if name in self._registrations and not replace:
            raise ProviderAlreadyRegisteredError(
                f"El proveedor '{name}' ya está registrado."
            )

        self._registrations[name] = ProviderRegistration(
            provider=provider,
            enabled=bool(enabled),
        )
        return provider

    def unregister(self, name: str) -> LLMProvider:
        """Retira y devuelve el proveedor registrado."""

        normalized = self._normalize_name(name)
        registration = self._registrations.pop(normalized, None)

        if registration is None:
            raise ProviderNotFoundError(
                f"El proveedor '{normalized}' no está registrado."
            )

        return registration.provider

    def exists(self, name: str) -> bool:
        """Indica si existe un registro con el nombre solicitado."""

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
    ) -> LLMProvider:
        """
        Obtiene un proveedor por nombre.

        Por defecto rechaza proveedores deshabilitados. Para tareas
        administrativas puede usarse ``require_enabled=False``.
        """

        normalized = self._normalize_name(name)
        registration = self._registrations.get(normalized)

        if registration is None:
            raise ProviderNotFoundError(
                f"El proveedor '{normalized}' no está registrado."
            )

        if require_enabled and not registration.enabled:
            raise ProviderDisabledError(
                f"El proveedor '{normalized}' está deshabilitado."
            )

        return registration.provider

    def enable(self, name: str) -> None:
        """Habilita un proveedor registrado."""

        self._get_registration(name).enabled = True

    def disable(self, name: str) -> None:
        """Deshabilita un proveedor sin eliminar su registro."""

        self._get_registration(name).enabled = False

    def is_enabled(self, name: str) -> bool:
        """Devuelve el estado de habilitación del proveedor."""

        return self._get_registration(name).enabled

    def list(self, *, enabled_only: bool = False) -> list[str]:
        """Devuelve los nombres registrados en orden alfabético."""

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
    ) -> list[LLMProvider]:
        """Devuelve las instancias registradas en orden por nombre."""

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
        """
        Devuelve capacidades de un proveedor o de todo el registro.
        """

        if name is not None:
            provider = self.get(
                name,
                require_enabled=enabled_only,
            )
            return dict(provider.capabilities())

        return {
            provider_name: dict(
                self._registrations[
                    provider_name
                ].provider.capabilities()
            )
            for provider_name in self.list(
                enabled_only=enabled_only
            )
        }

    def available_models(
        self,
        name: str | None = None,
        *,
        enabled_only: bool = False,
    ) -> list[str] | dict[str, list[str]]:
        """
        Devuelve los modelos declarados por uno o todos los proveedores.

        Se admite que un proveedor exponga ``available_models`` como
        método o atributo iterable. Si no lo hace, se utiliza su
        ``model_name`` siempre que sea un valor concreto.
        """

        if name is not None:
            provider = self.get(
                name,
                require_enabled=enabled_only,
            )
            return self._extract_models(provider)

        return {
            provider_name: self._extract_models(
                self._registrations[provider_name].provider
            )
            for provider_name in self.list(
                enabled_only=enabled_only
            )
        }

    def status(self) -> dict[str, dict[str, Any]]:
        """Construye un resumen serializable del inventario."""

        return {
            name: {
                "enabled": registration.enabled,
                "provider": registration.provider.provider_name,
                "model": registration.provider.model_name,
                "capabilities": dict(
                    registration.provider.capabilities()
                ),
                "available_models": self._extract_models(
                    registration.provider
                ),
            }
            for name, registration in sorted(
                self._registrations.items()
            )
        }

    def clear(self) -> None:
        """Elimina todos los registros."""

        self._registrations.clear()

    def __contains__(self, name: object) -> bool:
        if not isinstance(name, str):
            return False
        return self.exists(name)

    def __len__(self) -> int:
        return len(self._registrations)

    def __iter__(self):
        return iter(self.list())

    def _get_registration(
        self,
        name: str,
    ) -> ProviderRegistration:
        normalized = self._normalize_name(name)
        registration = self._registrations.get(normalized)

        if registration is None:
            raise ProviderNotFoundError(
                f"El proveedor '{normalized}' no está registrado."
            )

        return registration

    @staticmethod
    def _validate_provider(provider: LLMProvider) -> None:
        if not isinstance(provider, LLMProvider):
            raise TypeError(
                "provider debe ser una instancia de LLMProvider."
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
    def _extract_models(provider: LLMProvider) -> list[str]:
        declared = getattr(provider, "available_models", None)

        if callable(declared):
            declared = declared()

        if declared is None:
            model_name = str(
                getattr(provider, "model_name", "") or ""
            ).strip()
            if model_name and model_name.lower() != "unknown":
                return [model_name]
            return []

        if isinstance(declared, str):
            declared = [declared]

        try:
            candidates = list(declared)
        except TypeError as error:
            raise TypeError(
                "available_models debe ser iterable o invocable."
            ) from error

        models: list[str] = []
        seen: set[str] = set()

        for candidate in candidates:
            model = str(candidate or "").strip()
            key = model.casefold()
            if not model or key in seen:
                continue
            seen.add(key)
            models.append(model)

        return models


__all__ = [
    "ProviderAlreadyRegisteredError",
    "ProviderDisabledError",
    "ProviderNotFoundError",
    "ProviderRegistration",
    "ProviderRegistry",
    "ProviderRegistryError",
]