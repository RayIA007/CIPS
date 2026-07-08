"""
=========================================================
Proyecto : CIPS
Release  : 0.3
Build    : 010A
Archivo  : pipeline_engine.py
Estado   : RELEASE
=========================================================
"""

from pathlib import Path

from runtime_models import EngineResult, Project, LLMResponse
from project_manager import ProjectManager
from knowledge_engine import KnowledgeEngine
from context_engine import ContextEngine
from prompt_engine import PromptEngine
from validator_engine import ValidatorEngine
from memory_engine import MemoryEngine


class PipelineEngine:
    """
    Orquesta el Runtime básico de CIPS.
    """

    STAGES = [
        "investigacion",
        "verificacion",
        "guion",
        "storyboard",
        "seo",
        "publicacion",
        "final",
    ]

    STAGE_FILES = {
        "investigacion": "01_INVESTIGACION.md",
        "verificacion": "02_VERIFICACION.md",
        "guion": "03_GUION.md",
        "storyboard": "04_STORYBOARD.md",
        "seo": "05_SEO.md",
        "publicacion": "06_PUBLICACION.md",
        "final": "07_FINAL.md",
    }

    def __init__(self):
        self.project_manager = ProjectManager()
        self.knowledge_engine = KnowledgeEngine()
        self.context_engine = ContextEngine()
        self.prompt_engine = PromptEngine()
        self.validator_engine = ValidatorEngine()
        self.memory_engine = MemoryEngine()

    def execute(self, project_path: Path | None = None) -> EngineResult:
        try:
            project = self.project_manager.load_project(project_path)

            if project.stage_actual == "final":
                return EngineResult.ok(
                    message="El proyecto ya se encuentra en etapa final.",
                    data=project,
                )

            response_path = project.path / self.STAGE_FILES[project.stage_actual]
            response_content = self._read_response(response_path)

            if not response_content:
                return self._generate_prompt(project)

            return self._validate_and_advance(project, response_content)

        except Exception as error:
            return EngineResult.fail(
                message="Error inesperado en PipelineEngine.",
                errors=[str(error)],
            )

    def _generate_prompt(self, project: Project) -> EngineResult:
        knowledge_result = self.knowledge_engine.execute(project)

        if not knowledge_result.success:
            return knowledge_result

        context_result = self.context_engine.execute(
            project,
            knowledge_result.data,
        )

        if not context_result.success:
            return context_result

        prompt_result = self.prompt_engine.execute(
            project,
            context_result.data,
        )

        if not prompt_result.success:
            return prompt_result

        return EngineResult.ok(
            data=prompt_result.data,
            message="Prompt generado. Copia el prompt en la IA y guarda la respuesta en el archivo del Stage actual.",
            metadata=prompt_result.metadata,
        )

    def _validate_and_advance(
        self,
        project: Project,
        response_content: str,
    ) -> EngineResult:

        response = LLMResponse(
            content=response_content,
            model="manual",
            metadata={
                "stage": project.stage_actual,
                "project_id": project.project_id,
            },
        )

        validation_result = self.validator_engine.execute(
            project,
            response,
        )

        if not validation_result.success:
            return validation_result

        memory_result = self.memory_engine.execute(
            project,
            validation_result.data,
        )

        if not memory_result.success:
            return memory_result

        next_stage = self._get_next_stage(project.stage_actual)

        self.project_manager.update_project_stage(
            project=project,
            next_stage=next_stage,
        )

        return EngineResult.ok(
            data={
                "project_id": project.project_id,
                "completed_stage": project.stage_actual,
                "next_stage": next_stage,
            },
            message=f"Stage '{project.stage_actual}' validado. Nuevo Stage: '{next_stage}'.",
        )

    def _read_response(self, response_path: Path) -> str:
        if not response_path.exists():
            return ""

        content = response_path.read_text(encoding="utf-8").strip()

        placeholder_markers = [
            "pendiente",
            "por completar",
            "aquí va",
        ]

        if len(content) < 50:
            lowered = content.lower()

            for marker in placeholder_markers:
                if marker in lowered:
                    return ""

        return content

    def _get_next_stage(self, current_stage: str) -> str:
        if current_stage not in self.STAGES:
            return "final"

        index = self.STAGES.index(current_stage)

        if index + 1 >= len(self.STAGES):
            return "final"

        return self.STAGES[index + 1]