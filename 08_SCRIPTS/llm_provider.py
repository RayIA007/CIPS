"""
=========================================================
Proyecto : CIPS
Release  : 0.5
Build    : 028
Archivo  : llm_provider.py
Estado   : RELEASE
=========================================================

Define el contrato común para los proveedores de modelos
de Inteligencia Artificial utilizados por CIPS.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from runtime_models import LLMResponse


@dataclass
class ProviderResult:
    """
    Resultado estándar devuelto por un proveedor LLM.

    Este objeto separa los errores propios del proveedor
    del contenido final representado mediante LLMResponse.
    """

    success: bool
    response: LLMResponse | None = None
    message: str = ""
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def ok(
        cls,
        response: LLMResponse,
        message: str = "Respuesta LLM obtenida correctamente.",
        warnings: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> "ProviderResult":
        """
        Construye un resultado exitoso.
        """

        return cls(
            success=True,
            response=response,
            message=message,
            warnings=warnings or [],
            errors=[],
            metadata=metadata or {},
        )

    @classmethod
    def fail(
        cls,
        message: str = "El proveedor LLM no pudo completar la solicitud.",
        errors: list[str] | None = None,
        warnings: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> "ProviderResult":
        """
        Construye un resultado fallido.
        """

        return cls(
            success=False,
            response=None,
            message=message,
            warnings=warnings or [],
            errors=errors or [],
            metadata=metadata or {},
        )


class LLMProvider(ABC):
    """
    Contrato oficial para proveedores LLM de CIPS.

    Cada proveedor deberá:

    - recibir un prompt en texto;
    - procesarlo mediante una fuente manual, simulada,
      local o remota;
    - devolver ProviderResult;
    - no modificar directamente RuntimeContext;
    - no validar el contenido generado.
    """

    provider_name = "base"
    model_name = "unknown"

    @abstractmethod
    def generate(
        self,
        prompt: str,
        metadata: dict[str, Any] | None = None,
    ) -> ProviderResult:
        """
        Genera una respuesta a partir del prompt.

        Args:
            prompt:
                Contenido completo enviado al proveedor.

            metadata:
                Información adicional de la ejecución.

        Returns:
            ProviderResult:
                Resultado estándar del proveedor.
        """

        raise NotImplementedError

    def validate_prompt(
        self,
        prompt: str,
    ) -> list[str]:
        """
        Realiza validaciones mínimas antes de enviar el prompt.
        """

        errors: list[str] = []

        if not isinstance(prompt, str):
            errors.append(
                "El prompt debe ser una cadena de texto."
            )
            return errors

        if not prompt.strip():
            errors.append(
                "El prompt está vacío."
            )

        return errors

    def get_provider_info(self) -> dict[str, str]:
        """
        Devuelve información básica del proveedor.
        """

        return {
            "provider": self.provider_name,
            "model": self.model_name,
        }

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}"
            f"(provider_name='{self.provider_name}', "
            f"model_name='{self.model_name}')"
        )