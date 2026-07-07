"""
CIPS - Validator
Pruebas automáticas básicas del sistema.
"""

from pathlib import Path

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
    "CIPS",
]


class Validator:
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