"""
=========================================================
Proyecto : CIPS
Release  : 0.5
Build    : 001
Archivo  : media_provider.py
Estado   : RELEASE
=========================================================

Contrato base para proveedores multimedia de CIPS.

Este módulo define una abstracción separada de ``LLMProvider``. Un
proveedor multimedia declara capacidades por nombre y genera un
``MediaResult`` a partir de un ``MediaRequest`` sin asumir persistencia,
workspace, retry, failover ni políticas de selección.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class MediaRequest:
    """Solicitud normalizada para un proveedor multimedia."""

    capability: str
    payload: Any
    options: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class MediaResult:
    """Resultado normalizado de una operación multimedia."""

    success: bool
    output: Any = None
    message: str = ""
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def ok(
        cls,
        output: Any,
        *,
        message: str = "Contenido multimedia generado correctamente.",
        warnings: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> "MediaResult":
        """Construye un resultado multimedia exitoso."""

        return cls(
            success=True,
            output=output,
            message=message,
            warnings=list(warnings or ()),
            errors=[],
            metadata=dict(metadata or {}),
        )

    @classmethod
    def fail(
        cls,
        *,
        message: str = "El proveedor multimedia no pudo completar la solicitud.",
        errors: list[str] | None = None,
        warnings: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> "MediaResult":
        """Construye un resultado multimedia fallido."""

        return cls(
            success=False,
            output=None,
            message=message,
            warnings=list(warnings or ()),
            errors=list(errors or ()),
            metadata=dict(metadata or {}),
        )


class MediaProvider(ABC):
    """
    Contrato oficial para proveedores multimedia de CIPS.

    Cada proveedor debe declarar un ``provider_name`` y las capacidades
    que implementa. ``generate`` es la única operación obligatoria de
    ejecución. La validación y la estimación de coste tienen defaults
    seguros que pueden especializarse sin obligar a inventar precios.
    """

    provider_name = "base"

    @abstractmethod
    def generate(self, request: MediaRequest) -> MediaResult:
        """Genera contenido multimedia para una solicitud normalizada."""

        raise NotImplementedError

    def capabilities(self) -> dict[str, dict[str, Any]]:
        """
        Devuelve las capacidades declaradas por el proveedor.

        La clave es el nombre lógico de la capacidad, por ejemplo
        ``voice_synthesis``. Los metadatos asociados son informativos y
        todavía no implican una política de selección.
        """

        return {}

    def validate_input(self, request: MediaRequest) -> list[str]:
        """Realiza validaciones de contrato antes de ejecutar el provider."""

        if not isinstance(request, MediaRequest):
            return ["request debe ser una instancia de MediaRequest."]

        try:
            capability = normalize_capability(request.capability)
        except (TypeError, ValueError) as error:
            return [str(error)]

        declared = {
            normalize_capability(name)
            for name in self.capabilities()
        }
        if capability not in declared:
            return [
                f"El proveedor '{self.provider_name}' no soporta "
                f"la capacidad '{capability}'."
            ]

        return []

    def estimate_cost(self, request: MediaRequest) -> float | None:
        """
        Devuelve una estimación monetaria cuando el provider puede calcularla.

        ``None`` significa que el coste no está disponible o que no aplica.
        F4.1 no introduce tablas de precios ni valores hardcodeados.
        """

        return None

    def health_check(self) -> bool:
        """Verificación básica; providers concretos pueden especializarla."""

        return True

    def get_provider_info(self) -> dict[str, Any]:
        """Devuelve información básica serializable del provider."""

        return {
            "provider": self.provider_name,
            "capabilities": sorted(
                normalize_capability(name)
                for name in self.capabilities()
            ),
        }

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}"
            f"(provider_name='{self.provider_name}')"
        )


def normalize_capability(capability: str) -> str:
    """Normaliza un identificador de capacidad multimedia."""

    if not isinstance(capability, str):
        raise TypeError("La capacidad debe ser una cadena de texto.")

    normalized = capability.strip().lower()
    if not normalized:
        raise ValueError("La capacidad no puede estar vacía.")

    return normalized


__all__ = [
    "MediaProvider",
    "MediaRequest",
    "MediaResult",
    "normalize_capability",
]
