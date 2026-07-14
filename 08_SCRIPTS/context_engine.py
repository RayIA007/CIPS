"""
=========================================================
Proyecto : CIPS
Release  : 0.4
Build    : 022
Archivo  : context_engine.py
Estado   : RELEASE
=========================================================

Construye el ContextObject a partir de los Knowledge
Modules activos.

Compatibilidad:
- PipelineEngine mediante execute(Project, modules).
- PipelineRunner mediante execute(RuntimeContext).
"""

from runtime_component import RuntimeComponent
from runtime_context import RuntimeContext
from runtime_models import (
    ContextObject,
    EngineResult,
    KnowledgeModule,
    Project,
)


class ContextEngine(RuntimeComponent):
    """
    Construye el contexto operativo utilizado por PromptEngine.

    Admite dos formas de ejecución:

    1. execute(Project, knowledge_modules)
       Mantiene compatibilidad con PipelineEngine.

    2. execute(RuntimeContext)
       Implementa el contrato del Runtime Framework.
    """

    component_name = "context_engine"

    def execute(
        self,
        runtime_input: Project | RuntimeContext,
        knowledge_modules: list[KnowledgeModule] | None = None,
    ) -> EngineResult:
        """
        Construye un ContextObject con los módulos activos.
        """

        try:
            runtime_context = self._get_runtime_context(
                runtime_input
            )

            project = self._get_project(
                runtime_input
            )

            active_modules = self._get_active_modules(
                runtime_input=runtime_input,
                knowledge_modules=knowledge_modules,
            )

            if not active_modules:
                return EngineResult.fail(
                    message=(
                        "No se recibieron Knowledge Modules "
                        "para construir el contexto."
                    ),
                    errors=[
                        "No existen módulos activos."
                    ],
                    metadata={
                        "component": self.component_name,
                        "project_id": project.project_id,
                        "stage": project.stage_actual,
                    },
                )

            ordered_modules = self._order_modules(
                active_modules
            )

            content = self._build_context(
                ordered_modules
            )

            if not content.strip():
                return EngineResult.fail(
                    message="El contexto generado está vacío.",
                    errors=[
                        "Los Knowledge Modules no contienen "
                        "contenido operativo."
                    ],
                    metadata={
                        "component": self.component_name,
                        "project_id": project.project_id,
                        "stage": project.stage_actual,
                    },
                )

            context_object = ContextObject(
                project=project,
                modules=ordered_modules,
                content=content,
                metadata={
                    "component": self.component_name,
                    "project_id": project.project_id,
                    "stage": project.stage_actual,
                    "modules_count": len(
                        ordered_modules
                    ),
                    "module_ids": [
                        module.module_id
                        for module in ordered_modules
                    ],
                    "characters": len(content),
                },
            )

            metadata = dict(
                context_object.metadata
            )

            if runtime_context is not None:
                runtime_context.context_object = (
                    context_object
                )

                return EngineResult.ok(
                    data=runtime_context,
                    message=(
                        "ContextObject construido en "
                        "RuntimeContext."
                    ),
                    metadata=metadata,
                )

            return EngineResult.ok(
                data=context_object,
                message=(
                    "Contexto construido correctamente."
                ),
                metadata=metadata,
            )

        except Exception as error:
            return EngineResult.fail(
                message=(
                    "Error inesperado en ContextEngine."
                ),
                errors=[str(error)],
                metadata={
                    "component": self.component_name,
                },
            )

    def _get_runtime_context(
        self,
        runtime_input: Project | RuntimeContext,
    ) -> RuntimeContext | None:
        """
        Devuelve RuntimeContext cuando se utiliza
        el nuevo Runtime Framework.
        """

        if isinstance(
            runtime_input,
            RuntimeContext,
        ):
            return runtime_input

        return None

    def _get_project(
        self,
        runtime_input: Project | RuntimeContext,
    ) -> Project:
        """
        Obtiene Project desde cualquiera de las interfaces.
        """

        if isinstance(
            runtime_input,
            RuntimeContext,
        ):
            return runtime_input.project

        if isinstance(
            runtime_input,
            Project,
        ):
            return runtime_input

        raise TypeError(
            "ContextEngine requiere "
            "Project o RuntimeContext."
        )

    def _get_active_modules(
        self,
        runtime_input: Project | RuntimeContext,
        knowledge_modules: list[KnowledgeModule] | None,
    ) -> list[KnowledgeModule]:
        """
        Obtiene el conjunto de módulos más procesado disponible.

        En RuntimeContext utiliza:

        1. compressed_modules
        2. resolved_modules
        3. knowledge_modules
        """

        if isinstance(
            runtime_input,
            RuntimeContext,
        ):
            return runtime_input.get_active_modules()

        return knowledge_modules or []

    def _order_modules(
        self,
        modules: list[KnowledgeModule],
    ) -> list[KnowledgeModule]:
        """
        Ordena los módulos por identificador.
        """

        return sorted(
            modules,
            key=lambda module: module.module_id,
        )

    def _build_context(
        self,
        modules: list[KnowledgeModule],
    ) -> str:
        """
        Ensambla el contenido de todos los módulos activos.
        """

        blocks: list[str] = []

        for module in modules:
            content = (
                module.content or ""
            ).strip()

            if not content:
                continue

            blocks.append(
                "\n".join(
                    [
                        f"# {module.module_id} — {module.name}",
                        "",
                        content,
                    ]
                )
            )

        return "\n\n---\n\n".join(
            blocks
        ).strip()