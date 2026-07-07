"""
CIPS - Project Manager
Crea y administra proyectos de producción de contenido.
"""

from pathlib import Path
from datetime import datetime
import uuid

from utils import ROOT, PROJECTS_DIR, ensure_directory, write_text, write_yaml
from templates import (
    tema_md,
    contexto_md,
    proyecto_yaml,
    memoria_yaml,
    MARKDOWN_FILES,
)


class ProjectManager:
    def __init__(self):
        ensure_directory(PROJECTS_DIR)

    def get_next_project_number(self) -> int:
        projects = [
            folder.name
            for folder in PROJECTS_DIR.iterdir()
            if folder.is_dir() and folder.name.startswith("PROYECTO_")
        ]

        if not projects:
            return 1

        numbers = []

        for project in projects:
            try:
                numbers.append(int(project.split("_")[1]))
            except (IndexError, ValueError):
                continue

        if not numbers:
            return 1

        return max(numbers) + 1

    def create_project(self, tema: str) -> dict:
        tema = tema.strip()

        if not tema:
            raise ValueError("El tema no puede estar vacío.")

        number = self.get_next_project_number()
        project_id = f"PROYECTO_{number:04d}"
        project_uuid = str(uuid.uuid4())

        project_path = PROJECTS_DIR / project_id
        ensure_directory(project_path)

        folders = [
            "01_FUENTES",
            "02_PROMPTS",
            "03_RESPUESTAS",
            "04_CONTENIDO",
            "05_RECURSOS",
            "06_EXPORTACIONES",
        ]

        for folder in folders:
            ensure_directory(project_path / folder)

        fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        write_yaml(
            project_path / "proyecto.yaml",
            proyecto_yaml(project_id, project_uuid, tema, fecha),
        )

        write_yaml(
            project_path / "memoria.yaml",
            memoria_yaml(),
        )

        write_text(project_path / "00_TEMA.md", tema_md(tema))
        write_text(project_path / "CONTEXTO.md", contexto_md(tema))

        for filename, content in MARKDOWN_FILES.items():
            write_text(project_path / filename, content)

        return {
            "id": project_id,
            "uuid": project_uuid,
            "tema": tema,
            "path": str(project_path),
        }