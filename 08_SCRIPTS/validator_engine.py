"""
=========================================================
Proyecto : CIPS
Release  : 0.3
Build    : 008
Archivo  : validator_engine.py
Estado   : RELEASE
=========================================================
"""

from pathlib import Path

from runtime_models import EngineResult, LLMResponse, ValidationResult, Project
from utils import ROOT, read_yaml


REQUIRED_ROOT_FOLDERS = [
    "00_DOCUMENTACION",
    "01_CONFIG",
    "02_PROMPTS",
    "03_PLANTILLAS",
    "04_PROYECTOS",
    "05_OUTPUTS",
    "06_MEMORIA",
    "07_LOGS",
    "08_SCRIPTS",
    "09_KNOWLEDGE",
    "CIPS",
]


class Validator:
    """
    Validator legado del Release 0.2.
    Se conserva por compatibilidad.
    """

    def validate_system(self) -> list[str]:
        errors = []

        for folder in REQUIRED_ROOT_FOLDERS:
            if not (ROOT / folder).exists():
                errors.append(f"Falta carpeta raíz: {folder}")

        required_files = [
            ROOT / "PROJECT_MANIFEST.yaml",
            ROOT / "requirements.txt",
            ROOT / "01_CONFIG" / "config_global.yaml",
            ROOT / "01_CONFIG" / "pipeline.yaml",
            ROOT / "01_CONFIG" / "llm.yaml",
        ]

        for file in required_files:
            if not file.exists():
                errors.append(f"Falta archivo requerido: {file}")

        return errors

    def validate_project(self, project_path: Path) -> list[str]:
        errors = []

        required_files = [
            "proyecto.yaml",
            "memoria.yaml",
            "CONTEXTO.md",
            "00_TEMA.md",
            "01_INVESTIGACION.md",
            "02_VERIFICACION.md",
            "03_GUION.md",
            "04_STORYBOARD.md",
            "05_SEO.md",
            "06_PUBLICACION.md",
            "07_FINAL.md",
        ]

        for file in required_files:
            if not (project_path / file).exists():
                errors.append(f"Falta archivo en proyecto: {file}")

        project_yaml = read_yaml(project_path / "proyecto.yaml")

        if not project_yaml.get("id"):
            errors.append("proyecto.yaml no tiene ID")

        if not project_yaml.get("tema"):
            errors.append("proyecto.yaml no tiene tema")

        if not project_yaml.get("estado"):
            errors.append("proyecto.yaml no tiene estado")

        return errors


class ValidatorEngine:
    """
    Validator Engine del Runtime 0.3.
    Valida respuestas generadas o pegadas por el usuario.
    """

    def execute(
        self,
        project: Project,
        response: LLMResponse,
    ) -> EngineResult:

        try:
            errors = []
            warnings = []
            observations = []

            content = response.content.strip()

            if not content:
                errors.append("La respuesta está vacía.")

            if len(content) < 100:
                warnings.append("La respuesta parece demasiado corta.")

            if "no puedo" in content.lower():
                warnings.append("La respuesta puede contener una negativa del modelo IA.")

            if "como modelo de lenguaje" in content.lower():
                warnings.append("La respuesta incluye texto genérico del modelo IA.")

            if "no saludes" in content.lower():
                warnings.append("La respuesta parece incluir instrucciones del prompt.")

            approved = len(errors) == 0

            validation = ValidationResult(
                approved=approved,
                observations=observations,
                warnings=warnings,
                errors=errors,
                metadata={
                    "project_id": project.project_id,
                    "stage": project.stage_actual,
                    "characters": len(content),
                },
            )

            if not approved:
                return EngineResult.fail(
                    message="La respuesta no superó la validación.",
                    errors=errors,
                    warnings=warnings,
                    metadata=validation.metadata,
                )

            return EngineResult.ok(
                data=validation,
                message="Respuesta validada correctamente.",
                warnings=warnings,
                metadata=validation.metadata,
            )

        except Exception as error:
            return EngineResult.fail(
                message="Error inesperado en ValidatorEngine.",
                errors=[str(error)],
            )