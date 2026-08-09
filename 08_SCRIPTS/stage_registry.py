"""
=========================================================
Proyecto : CIPS
Release  : 0.8
Build    : 064-F2
Archivo  : stage_registry.py
Estado   : RELEASE (Fase 2)
=========================================================

Registro dinámico de callables de etapa.

Responsabilidades:
- Registrar callables (funciones, métodos, clases callable) por nombre.
- Resolver un callable por su nombre para el StageExecutor.
- Listar los callables disponibles.
- Permitir desregistro para pruebas.

Patrón:
- Registry (consistente con provider_registry.py).

Este módulo NO:
- Ejecuta callables.
- Valida la firma de los callables (eso es stage_executor.py).
- Depende de componentes del pipeline.
"""

from __future__ import annotations

from typing import Any, Callable


class StageRegistryError(Exception):
    """Excepción base del registro de etapas."""

    pass


class StageNotRegisteredError(StageRegistryError):
    """El callable solicitado no está registrado."""

    pass


class StageAlreadyRegisteredError(StageRegistryError):
    """El callable ya existe en el registro."""

    pass


class StageRegistry:
    """
    Registro global de callables de etapa.

    Uso típico:
        StageRegistry.register("research", research_director.execute)
        callable_obj = StageRegistry.get("research")
    """

    _registry: dict[str, Callable] = {}

    @classmethod
    def register(
        cls,
        name: str,
        callable_obj: Callable,
        force: bool = False,
    ) -> None:
        """
        Registra un callable bajo un nombre único.

        Args:
            name: Identificador único de la etapa (ej. "research", "script").
            callable_obj: Función, método o clase callable a invocar.
            force: Si True, sobrescribe un registro existente.

        Raises:
            StageAlreadyRegisteredError: Si el nombre ya existe y force=False.
        """
        key = str(name).strip().lower()
        if not key:
            raise ValueError("El nombre de etapa no puede estar vacío.")

        if not callable(callable_obj):
            raise TypeError(f"El objeto registrado para '{key}' debe ser callable.")

        if key in cls._registry and not force:
            raise StageAlreadyRegisteredError(
                f"La etapa '{key}' ya está registrada. "
                f"Use force=True para sobrescribir."
            )

        cls._registry[key] = callable_obj

    @classmethod
    def get(cls, name: str) -> Callable:
        """
        Resuelve un callable por su nombre.

        Args:
            name: Identificador de la etapa.

        Returns:
            El callable registrado.

        Raises:
            StageNotRegisteredError: Si el nombre no existe en el registro.
        """
        key = str(name).strip().lower()
        if key not in cls._registry:
            raise StageNotRegisteredError(
                f"La etapa '{key}' no está registrada. "
                f"Registradas: {cls.list_registered()}"
            )
        return cls._registry[key]

    @classmethod
    def unregister(cls, name: str) -> None:
        """
        Elimina un callable del registro.

        Args:
            name: Identificador de la etapa.

        Raises:
            StageNotRegisteredError: Si el nombre no existe.
        """
        key = str(name).strip().lower()
        if key not in cls._registry:
            raise StageNotRegisteredError(f"La etapa '{key}' no está registrada.")
        del cls._registry[key]

    @classmethod
    def list_registered(cls) -> list[str]:
        """
        Devuelve la lista de nombres de etapas registradas.

        Returns:
            Lista ordenada de identificadores.
        """
        return sorted(cls._registry.keys())

    @classmethod
    def is_registered(cls, name: str) -> bool:
        """
        Verifica si un nombre está registrado.

        Args:
            name: Identificador de la etapa.

        Returns:
            True si existe en el registro.
        """
        return str(name).strip().lower() in cls._registry

    @classmethod
    def clear(cls) -> None:
        """
        Elimina TODOS los registros. Útil únicamente en pruebas.
        """
        cls._registry.clear()

    @classmethod
    def get_info(cls) -> dict[str, Any]:
        """
        Devuelve información pública del registro.

        Returns:
            Dict con metadatos del registro.
        """
        return {
            "component": "stage_registry",
            "version": "0.8",
            "build": "064-F2",
            "registered_count": len(cls._registry),
            "registered_stages": cls.list_registered(),
        }


def get_stage_registry_info() -> dict[str, Any]:
    """Devuelve información pública del módulo."""
    return StageRegistry.get_info()