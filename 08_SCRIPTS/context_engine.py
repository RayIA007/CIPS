"""
=========================================================
Proyecto : CIPS
Release  : 0.3
Build    : 006
Archivo  : context_engine.py
Estado   : RELEASE
=========================================================
"""

from runtime_models import (
    EngineResult,
    ContextObject,
    KnowledgeModule,
    Project,
)


class ContextEngine:
    """
    Construye el contexto que utilizará el Prompt Builder.
    """

    def execute(
        self,
        project: Project,
        knowledge_modules: list[KnowledgeModule],
    ) -> EngineResult:

        try:

            if not knowledge_modules:
                return EngineResult.fail(
                    message="No se recibieron Knowledge Modules.",
                    errors=["knowledge_modules vacío"],
                )

            ordered_modules = self._order_modules(
                knowledge_modules
            )

            content = self._build_context(
                ordered_modules
            )

            context = ContextObject(
                project=project,
                modules=ordered_modules,
                content=content,
                metadata={
                    "modules": len(ordered_modules),
                    "characters": len(content),
                },
            )

            return EngineResult.ok(
                data=context,
                message="Contexto construido correctamente.",
            )

        except Exception as error:

            return EngineResult.fail(
                message="Error inesperado en ContextEngine.",
                errors=[str(error)],
            )

    # --------------------------------------------------
    # Métodos privados
    # --------------------------------------------------

    def _order_modules(
        self,
        modules: list[KnowledgeModule],
    ) -> list[KnowledgeModule]:
        """
        Ordena los módulos por ID.
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
        Une el contenido de todos los módulos.
        """

        blocks = []

        for module in modules:

            blocks.append(
                f"# {module.name}\n\n{module.content}"
            )

        return "\n\n".join(blocks)