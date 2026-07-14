"""
=========================================================
Proyecto : CIPS
Release  : 0.4
Build    : 018
Archivo  : pipeline_runner.py
Estado   : RELEASE
=========================================================

Ejecuta secuencialmente componentes compatibles con
RuntimeComponent utilizando un RuntimeContext compartido.
"""

from collections.abc import Iterable

from runtime_component import RuntimeComponent
from runtime_context import RuntimeContext
from runtime_models import EngineResult


class PipelineRunner:
    """
    Orquesta una secuencia de RuntimeComponents.

    El Runner no conoce la lógica interna de los componentes.
    Únicamente los ejecuta en orden, registra sus resultados
    y detiene el flujo cuando alguno falla.
    """

    def __init__(
        self,
        components: Iterable[RuntimeComponent] | None = None,
    ) -> None:
        self.components: list[RuntimeComponent] = list(
            components or []
        )

    def add_component(
        self,
        component: RuntimeComponent,
    ) -> None:
        """
        Agrega un componente al final del Pipeline.
        """

        if not isinstance(component, RuntimeComponent):
            raise TypeError(
                "El componente debe implementar RuntimeComponent."
            )

        self.components.append(component)

    def execute(
        self,
        runtime_context: RuntimeContext,
    ) -> EngineResult:
        """
        Ejecuta todos los componentes registrados en orden.
        """

        if not self.components:
            return EngineResult.fail(
                message="PipelineRunner no tiene componentes configurados.",
                errors=["La lista de componentes está vacía."],
            )

        executed_components: list[str] = []

        for component in self.components:
            component_name = self._get_component_name(component)

            try:
                result = component.execute(runtime_context)

            except Exception as error:
                result = EngineResult.fail(
                    message=(
                        f"Error inesperado al ejecutar "
                        f"{component_name}."
                    ),
                    errors=[str(error)],
                    metadata={
                        "component": component_name,
                    },
                )

            runtime_context.register_result(
                component_name,
                result,
            )

            executed_components.append(component_name)

            if not result.success:
                return EngineResult.fail(
                    message=(
                        f"Pipeline detenido en "
                        f"{component_name}: {result.message}"
                    ),
                    errors=result.errors,
                    warnings=result.warnings,
                    metadata={
                        "failed_component": component_name,
                        "executed_components": executed_components,
                        "component_metadata": result.metadata,
                    },
                )

        return EngineResult.ok(
            data=runtime_context,
            message="Pipeline ejecutado correctamente.",
            warnings=runtime_context.warnings,
            metadata={
                "executed_components": executed_components,
                "components_count": len(executed_components),
            },
        )

    def clear(self) -> None:
        """
        Elimina todos los componentes configurados.
        """

        self.components.clear()

    def component_names(self) -> list[str]:
        """
        Devuelve los nombres de los componentes configurados.
        """

        return [
            self._get_component_name(component)
            for component in self.components
        ]

    def _get_component_name(
        self,
        component: RuntimeComponent,
    ) -> str:
        """
        Obtiene el nombre oficial del componente.
        """

        return getattr(
            component,
            "component_name",
            component.__class__.__name__,
        )