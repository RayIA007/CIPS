"""
=========================================================
Proyecto : CIPS
Release  : 0.4
Build    : 016
Archivo  : runtime_component.py
Estado   : RELEASE
=========================================================

Define el contrato común para los componentes del Runtime.
"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from runtime_models import EngineResult

if TYPE_CHECKING:
    from runtime_context import RuntimeContext


class RuntimeComponent(ABC):
    """
    Contrato base de todos los componentes ejecutables del Runtime.

    Cada componente deberá:

    - recibir un RuntimeContext;
    - ejecutar una única responsabilidad;
    - devolver un EngineResult;
    - no invocar directamente a otros componentes.
    """

    component_name = "runtime_component"

    @abstractmethod
    def execute(
        self,
        runtime_context: "RuntimeContext",
    ) -> EngineResult:
        """
        Ejecuta la responsabilidad del componente.

        Args:
            runtime_context:
                Estado compartido de la ejecución actual.

        Returns:
            EngineResult:
                Resultado estándar de la operación.
        """
        raise NotImplementedError

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}"
            f"(component_name='{self.component_name}')"
        )