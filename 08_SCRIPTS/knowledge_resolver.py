"""
=========================================================
Proyecto : CIPS
Release  : 0.3
Build    : 012
Archivo  : knowledge_resolver.py
Estado   : RELEASE
=========================================================

Selecciona únicamente los Knowledge Modules relevantes
para el Stage actual del proyecto.
"""

from runtime_models import EngineResult, KnowledgeModule, Project
from utils import ROOT, read_yaml
KNOWLEDGE_RULES_PATH = ROOT / "01_CONFIG" / "knowledge_rules.yaml"

class KnowledgeResolver:
    """
    Filtra Knowledge Modules según el Stage actual del proyecto.
    """

    

    def execute(
        self,
        project: Project,
        knowledge_modules: list[KnowledgeModule],
    ) -> EngineResult:
        try:
            if not knowledge_modules:
                return EngineResult.fail(
                    message="No se recibieron Knowledge Modules para resolver.",
                    errors=["knowledge_modules vacío"],
                )

            required_ids = self._get_required_module_ids(project.stage_actual)

            selected_modules = [
                module for module in knowledge_modules
                if module.module_id in required_ids
            ]

            if not selected_modules:
                return EngineResult.fail(
                    message="KnowledgeResolver no encontró módulos relevantes.",
                    errors=[
                        f"Stage actual: {project.stage_actual}",
                        f"IDs requeridos: {required_ids}",
                    ],
                )

            return EngineResult.ok(
                data=selected_modules,
                message="Knowledge Modules seleccionados correctamente.",
                metadata={
                    "stage": project.stage_actual,
                    "received_modules": len(knowledge_modules),
                    "selected_modules": len(selected_modules),
                    "selected_ids": [
                        module.module_id for module in selected_modules
                    ],
                },
            )

        except Exception as error:
            return EngineResult.fail(
                message="Error inesperado en KnowledgeResolver.",
                errors=[str(error)],
            )
    def _get_required_module_ids(self, stage: str) -> list[str]:
        rules = read_yaml(KNOWLEDGE_RULES_PATH)

        default_stage = rules.get("default_stage", "investigacion")
        stages = rules.get("stages", {})

        stage_rules = stages.get(stage) or stages.get(default_stage, {})

        return stage_rules.get("required", [])