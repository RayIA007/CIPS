"""
=========================================================
Proyecto : CIPS
Release  : 0.4
Build    : 021
Archivo  : context_compressor.py
Estado   : RELEASE
=========================================================

Prepara y reduce los Knowledge Modules antes de construir
el ContextObject.

Compatibilidad:
- PipelineEngine mediante execute(Project, modules).
- PipelineRunner mediante execute(RuntimeContext).
- Knowledge Modules v1 en Markdown.
- Knowledge Modules v2 basados en RUNTIME.yaml.
"""

from runtime_component import RuntimeComponent
from runtime_context import RuntimeContext
from runtime_models import (
    EngineResult,
    KnowledgeModule,
    Project,
)


class ContextCompressor(RuntimeComponent):
    """
    Normaliza y comprime los módulos seleccionados.

    Los módulos v2 ya contienen conocimiento operativo en
    RUNTIME.yaml, por lo que se conservan prácticamente sin
    modificaciones.

    Los módulos v1 en Markdown reciben una limpieza básica
    para eliminar secciones no necesarias durante el Runtime.
    """

    component_name = "context_compressor"

    EXCLUDED_HEADINGS = {
        "HISTORIAL",
        "CONTROL DE VERSIONES",
        "CHANGELOG",
        "DECLARACIÓN FINAL",
        "FIN DEL ARCHIVO",
        "FIN DEL DOCUMENTO",
        "FIN DEL KNOWLEDGE MODULE",
    }

    def execute(
        self,
        runtime_input: Project | RuntimeContext,
        knowledge_modules: list[KnowledgeModule] | None = None,
    ) -> EngineResult:
        """
        Prepara los módulos para la construcción del contexto.

        Formas compatibles:

        1. execute(Project, knowledge_modules)
           Utilizada por PipelineEngine.

        2. execute(RuntimeContext)
           Utilizada por PipelineRunner.
        """

        try:
            runtime_context = self._get_runtime_context(
                runtime_input
            )

            project = self._get_project(
                runtime_input
            )

            source_modules = self._get_source_modules(
                runtime_input=runtime_input,
                knowledge_modules=knowledge_modules,
            )

            if not source_modules:
                return EngineResult.fail(
                    message=(
                        "No se recibieron Knowledge Modules "
                        "para comprimir."
                    ),
                    errors=[
                        "No existen módulos resueltos o disponibles."
                    ],
                    metadata={
                        "component": self.component_name,
                        "project_id": project.project_id,
                        "stage": project.stage_actual,
                    },
                )

            compressed_modules: list[KnowledgeModule] = []

            original_size = 0
            compressed_size = 0
            v1_modules = 0
            v2_modules = 0

            for module in source_modules:
                original_content = module.content or ""
                original_size += len(original_content)

                module_format = str(
                    module.metadata.get("format", "v1")
                ).lower()

                if module_format == "v2":
                    compressed_content = (
                        original_content.strip()
                    )
                    v2_modules += 1
                else:
                    compressed_content = (
                        self._compress_v1_content(
                            original_content
                        )
                    )
                    v1_modules += 1

                compressed_size += len(
                    compressed_content
                )

                compressed_modules.append(
                    self._build_compressed_module(
                        module=module,
                        content=compressed_content,
                    )
                )

            reduction_percent = (
                self._calculate_reduction(
                    original_size=original_size,
                    compressed_size=compressed_size,
                )
            )

            metadata = {
                "component": self.component_name,
                "project_id": project.project_id,
                "stage": project.stage_actual,
                "modules_count": len(
                    compressed_modules
                ),
                "v1_modules": v1_modules,
                "v2_modules": v2_modules,
                "original_size": original_size,
                "compressed_size": compressed_size,
                "reduction_percent": reduction_percent,
            }

            if runtime_context is not None:
                runtime_context.compressed_modules = (
                    compressed_modules
                )

                return EngineResult.ok(
                    data=runtime_context,
                    message=(
                        "Knowledge Modules preparados en "
                        "RuntimeContext."
                    ),
                    metadata=metadata,
                )

            return EngineResult.ok(
                data=compressed_modules,
                message=(
                    "Knowledge Modules comprimidos "
                    "correctamente."
                ),
                metadata=metadata,
            )

        except Exception as error:
            return EngineResult.fail(
                message=(
                    "Error inesperado en "
                    "ContextCompressor."
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
            "ContextCompressor requiere "
            "Project o RuntimeContext."
        )

    def _get_source_modules(
        self,
        runtime_input: Project | RuntimeContext,
        knowledge_modules: list[KnowledgeModule] | None,
    ) -> list[KnowledgeModule]:
        """
        Obtiene los módulos seleccionados disponibles.

        En RuntimeContext se priorizan:

        1. resolved_modules
        2. knowledge_modules
        """

        if isinstance(
            runtime_input,
            RuntimeContext,
        ):
            if runtime_input.resolved_modules:
                return runtime_input.resolved_modules

            return runtime_input.knowledge_modules

        return knowledge_modules or []

    def _build_compressed_module(
        self,
        module: KnowledgeModule,
        content: str,
    ) -> KnowledgeModule:
        """
        Construye una nueva instancia sin modificar
        el módulo original.
        """

        return KnowledgeModule(
            module_id=module.module_id,
            name=module.name,
            path=module.path,
            category=module.category,
            content=content,
            dependencies=list(
                module.dependencies
            ),
            metadata={
                **module.metadata,
                "compressed": True,
                "original_size": len(
                    module.content or ""
                ),
                "compressed_size": len(content),
            },
        )

    def _compress_v1_content(
        self,
        content: str,
    ) -> str:
        """
        Limpia módulos Markdown v1.

        Elimina:

        - comentarios HTML;
        - líneas vacías repetidas;
        - secciones administrativas;
        - marcadores de cierre.
        """

        lines = content.splitlines()
        output: list[str] = []

        skip_section = False
        inside_html_comment = False
        previous_blank = False

        for line in lines:
            stripped = line.strip()

            if "<!--" in stripped:
                inside_html_comment = True

            if inside_html_comment:
                if "-->" in stripped:
                    inside_html_comment = False
                continue

            if self._is_heading(stripped):
                heading = self._normalize_heading(
                    stripped
                )

                skip_section = (
                    heading in self.EXCLUDED_HEADINGS
                )

                if skip_section:
                    continue

            if skip_section:
                continue

            if not stripped:
                if previous_blank:
                    continue

                output.append("")
                previous_blank = True
                continue

            output.append(line.rstrip())
            previous_blank = False

        return "\n".join(output).strip()

    def _is_heading(
        self,
        line: str,
    ) -> bool:
        """
        Indica si la línea es un encabezado Markdown.
        """

        return line.startswith("#")

    def _normalize_heading(
        self,
        line: str,
    ) -> str:
        """
        Normaliza el texto de un encabezado Markdown.
        """

        return line.lstrip("#").strip().upper()

    def _calculate_reduction(
        self,
        original_size: int,
        compressed_size: int,
    ) -> float:
        """
        Calcula el porcentaje de reducción.
        """

        if original_size <= 0:
            return 0.0

        reduction = (
            1
            - (
                compressed_size
                / original_size
            )
        ) * 100

        return round(
            reduction,
            2,
        )