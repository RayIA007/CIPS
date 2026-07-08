"""
CIPS - Project Manager
Crea y administra proyectos de producción de contenido.
"""

from pathlib import Path
from datetime import datetime
import uuid

from runtime_models import Project
from utils import ROOT, PROJECTS_DIR, ensure_directory, write_text, write_yaml, read_yaml
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

        return max(numbers) + 1 if numbers else 1

    def get_latest_project_path(self) -> Path:
        projects = sorted(
            [
                folder for folder in PROJECTS_DIR.iterdir()
                if folder.is_dir() and folder.name.startswith("PROYECTO_")
            ]
        )

        if not projects:
            raise FileNotFoundError("No existe ningún proyecto creado.")

        return projects[-1]

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

    def load_project(self, project_path: Path | None = None) -> Project:
        project_path = project_path or self.get_latest_project_path()

        proyecto_data = read_yaml(project_path / "proyecto.yaml")
        memoria_data = read_yaml(project_path / "memoria.yaml")

        stage_actual = (
            proyecto_data.get("stage_actual")
            or proyecto_data.get("estado")
            or "investigacion"
        )

        return Project(
            project_id=proyecto_data.get("id", project_path.name),
            path=project_path,
            tema=proyecto_data.get("tema", ""),
            estado=proyecto_data.get("estado", "READY"),
            stage_actual=stage_actual,
            ultimo_stage_validado=proyecto_data.get("ultimo_stage_validado", ""),
            config={},
            memory=memoria_data if isinstance(memoria_data, dict) else {},
            metadata=proyecto_data,
        )

    def update_project_stage(self, project: Project, next_stage: str) -> None:
        yaml_path = project.path / "proyecto.yaml"
        data = read_yaml(yaml_path)

        data["ultimo_stage_validado"] = project.stage_actual
        data["stage_actual"] = next_stage
        data["estado"] = next_stage
        data["fecha_actualizacion"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        write_yaml(yaml_path, data)