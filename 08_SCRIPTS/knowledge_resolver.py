"""
=========================================================
Proyecto : CIPS
Release  : 0.4
Build    : 020
Archivo  : knowledge_resolver.py
Estado   : RELEASE
=========================================================

Selecciona los Knowledge Modules relevantes para el
Stage actual del proyecto.

Compatibilidad:
- PipelineEngine mediante execute(Project, modules).
- PipelineRunner mediante execute(RuntimeContext).
"""

from runtime_component import RuntimeComponent
from runtime_context import RuntimeContext
from runtime_models import (
    EngineResult,
    KnowledgeModule,
    Project,
)
from utils import ROOT, read_yaml


KNOWLEDGE_RULES_PATH = (
    ROOT
    / "01_CONFIG"
    / "knowledge_rules.yaml"
)


class KnowledgeResolver(RuntimeComponent):
    """
    Filtra los Knowledge Modules según el Stage actual.

    Admite dos formas de ejecución:

    1. execute(Project, knowledge_modules)
       Mantiene compatibilidad con PipelineEngine.

    2. execute(RuntimeContext)
       Implementa el contrato del Runtime Framework.
    """

    component_name = "knowledge_resolver"

    def execute(
        self,
        runtime_input: Project | RuntimeContext,
        knowledge_modules: list[KnowledgeModule] | None = None,
    ) -> EngineResult:
        """
        Selecciona los módulos requeridos para el Stage actual.
        """

        try:
            runtime_context = self._get_runtime_context(
                runtime_input
            )

            project = self._get_project(
                runtime_input
            )

            available_modules = self._get_available_modules(
                runtime_input=runtime_input,
                knowledge_modules=knowledge_modules,
            )

            if not available_modules:
                return EngineResult.fail(
                    message=(
                        "No se recibieron Knowledge Modules "
                        "para resolver."
                    ),
                    errors=[
                        "knowledge_modules vacío"
                    ],
                    metadata={
                        "component": self.component_name,
                        "project_id": project.project_id,
                        "stage": project.stage_actual,
                    },
                )

            required_ids = self._get_required_module_ids(
                project.stage_actual
            )

            if not required_ids:
                return EngineResult.fail(
                    message=(
                        "No existen reglas de conocimiento "
                        "para el Stage actual."
                    ),
                    errors=[
                        f"Stage actual: {project.stage_actual}",
                        f"Archivo: {KNOWLEDGE_RULES_PATH}",
                    ],
                    metadata={
                        "component": self.component_name,
                        "project_id": project.project_id,
                        "stage": project.stage_actual,
                    },
                )

            selected_modules = [
                module
                for module in available_modules
                if module.module_id in required_ids
            ]

            missing_ids = [
                module_id
                for module_id in required_ids
                if module_id not in {
                    module.module_id
                    for module in selected_modules
                }
            ]

            if not selected_modules:
                return EngineResult.fail(
                    message=(
                        "KnowledgeResolver no encontró "
                        "módulos relevantes."
                    ),
                    errors=[
                        f"Stage actual: {project.stage_actual}",
                        f"IDs requeridos: {required_ids}",
                    ],
                    metadata={
                        "component": self.component_name,
                        "project_id": project.project_id,
                        "stage": project.stage_actual,
                    },
                )

            warnings = []

            if missing_ids:
                warnings.append(
                    "No se encontraron algunos módulos "
                    f"requeridos: {missing_ids}"
                )

            metadata = {
                "component": self.component_name,
                "project_id": project.project_id,
                "stage": project.stage_actual,
                "received_modules": len(
                    available_modules
                ),
                "selected_modules": len(
                    selected_modules
                ),
                "required_ids": required_ids,
                "selected_ids": [
                    module.module_id
                    for module in selected_modules
                ],
                "missing_ids": missing_ids,
                "rules_path": str(
                    KNOWLEDGE_RULES_PATH
                ),
            }

            if runtime_context is not None:
                runtime_context.resolved_modules = (
                    selected_modules
                )

                return EngineResult.ok(
                    data=runtime_context,
                    message=(
                        "Knowledge Modules seleccionados "
                        "en RuntimeContext."
                    ),
                    warnings=warnings,
                    metadata=metadata,
                )

            return EngineResult.ok(
                data=selected_modules,
                message=(
                    "Knowledge Modules seleccionados "
                    "correctamente."
                ),
                warnings=warnings,
                metadata=metadata,
            )

        except Exception as error:
            return EngineResult.fail(
                message=(
                    "Error inesperado en "
                    "KnowledgeResolver."
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
        Obtiene Project desde cualquiera
        de las interfaces compatibles.
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
            "KnowledgeResolver requiere "
            "Project o RuntimeContext."
        )

    def _get_available_modules(
        self,
        runtime_input: Project | RuntimeContext,
        knowledge_modules: list[KnowledgeModule] | None,
    ) -> list[KnowledgeModule]:
        """
        Obtiene los módulos desde el argumento legado
        o desde RuntimeContext.
        """

        if isinstance(
            runtime_input,
            RuntimeContext,
        ):
            return runtime_input.knowledge_modules

        return knowledge_modules or []

    def _get_required_module_ids(
        self,
        stage: str,
    ) -> list[str]:
        """
        Lee las reglas de selección desde YAML.
        """

        rules = read_yaml(
            KNOWLEDGE_RULES_PATH
        )

        if not isinstance(
            rules,
            dict,
        ):
            return []

        default_stage = rules.get(
            "default_stage",
            "investigacion",
        )

        stages = rules.get(
            "stages",
            {},
        )

        if not isinstance(
            stages,
            dict,
        ):
            return []

        stage_rules = (
            stages.get(stage)
            or stages.get(default_stage)
            or {}
        )

        if not isinstance(
            stage_rules,
            dict,
        ):
            return []

        required_ids = stage_rules.get(
            "required",
            [],
        )

        if not isinstance(
            required_ids,
            list,
        ):
            return []

        normalized_ids = []

        for module_id in required_ids:
            value = str(
                module_id
            ).strip().upper()

            if (
                value
                and value not in normalized_ids
            ):
                normalized_ids.append(
                    value
                )

        return normalized_ids