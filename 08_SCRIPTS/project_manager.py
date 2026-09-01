"""
CIPS - Project Manager
Crea y administra proyectos de producción de contenido.
"""

from pathlib import Path
from datetime import datetime
import json
import re
import uuid

from production_state import ProductionStateManager
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
        projects = self.list_project_paths()

        if not projects:
            raise FileNotFoundError("No existe ningún proyecto creado.")

        numbered = [
            path
            for path in projects
            if re.fullmatch(r"PROYECTO_\d+", path.name)
        ]
        if numbered:
            return max(
                numbered,
                key=lambda path: int(path.name.split("_")[1]),
            )

        return projects[-1]

    def list_project_paths(
        self,
        *,
        resumable_only: bool = False,
    ) -> list[Path]:
        projects = sorted(
            [
                folder
                for folder in PROJECTS_DIR.iterdir()
                if folder.is_dir()
                and folder.name.startswith("PROYECTO_")
                and (folder / "proyecto.yaml").is_file()
            ],
            key=lambda path: path.name,
        )
        if resumable_only:
            projects = [
                path
                for path in projects
                if (path / "operational_request.json").is_file()
                and (path / "state" / "production_state.json").is_file()
            ]
        return projects

    def create_project(
        self,
        tema: str,
        *,
        plataforma: str = "YouTube Shorts",
        duracion_segundos: int = 45,
        audiencia: str = "público general",
        estilo_creativo: str = "educativo, claro y dinámico",
    ) -> dict:
        tema = tema.strip()
        plataforma = plataforma.strip()
        audiencia = audiencia.strip()
        estilo_creativo = estilo_creativo.strip()

        if not tema:
            raise ValueError("El tema no puede estar vacío.")
        if not plataforma:
            raise ValueError("La plataforma no puede estar vacía.")
        if not audiencia:
            raise ValueError("La audiencia no puede estar vacía.")
        if not estilo_creativo:
            raise ValueError("El estilo creativo no puede estar vacío.")
        if isinstance(duracion_segundos, bool) or not isinstance(
            duracion_segundos,
            int,
        ):
            raise ValueError("La duración debe ser un número entero de segundos.")
        if not 1 <= duracion_segundos <= 3600:
            raise ValueError("La duración debe estar entre 1 y 3600 segundos.")

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
            "research",
            "verification",
            "script",
            "storyboard",
            "narration",
            "seo",
            "publication",
            "assets",
            "voice",
            "images",
            "subtitles",
            "video",
            "final",
            "state",
        ]

        for folder in folders:
            ensure_directory(project_path / folder)

        fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        write_yaml(
            project_path / "proyecto.yaml",
            proyecto_yaml(
                project_id,
                project_uuid,
                tema,
                fecha,
                plataforma=plataforma,
                duracion_segundos=duracion_segundos,
                audiencia=audiencia,
                estilo_creativo=estilo_creativo,
            ),
        )

        write_yaml(
            project_path / "memoria.yaml",
            memoria_yaml(
                plataforma=plataforma,
                duracion_segundos=duracion_segundos,
                audiencia=audiencia,
                estilo_creativo=estilo_creativo,
            ),
        )

        request = {
            "schema_name": "cips.fao.operational_request",
            "schema_version": "1.0",
            "project_id": project_id,
            "project_uuid": project_uuid,
            "topic": tema,
            "platform": plataforma,
            "duration_seconds": duracion_segundos,
            "audience": audiencia,
            "creative_style": estilo_creativo,
            "created_at": fecha,
            "free_tier_default": True,
            "publication_performed": False,
        }
        self._write_json_atomic(
            project_path / "operational_request.json",
            request,
        )
        self._write_json_atomic(
            project_path / "production.json",
            {
                "schema_name": "cips.production_status",
                "schema_version": "1.0",
                "project_id": project_id,
                "status": "CREATED",
                "publication_performed": False,
            },
        )

        write_text(
            project_path / "00_TEMA.md",
            tema_md(
                tema,
                plataforma=plataforma,
                duracion_segundos=duracion_segundos,
                audiencia=audiencia,
                estilo_creativo=estilo_creativo,
            ),
        )
        write_text(
            project_path / "CONTEXTO.md",
            contexto_md(
                tema,
                plataforma=plataforma,
                duracion_segundos=duracion_segundos,
                audiencia=audiencia,
                estilo_creativo=estilo_creativo,
            ),
        )

        for filename, content in MARKDOWN_FILES.items():
            write_text(project_path / filename, content)

        self._initialize_checkpoint(
            project_path=project_path,
            project_id=project_id,
            request=request,
        )

        return {
            "id": project_id,
            "uuid": project_uuid,
            "tema": tema,
            "path": str(project_path),
            "operational_request": request,
            "checkpoint_path": str(
                project_path / "state" / "production_state.json"
            ),
        }

    def checkpoint_project(
        self,
        project_path: Path,
        *,
        label: str,
        metadata: dict | None = None,
    ) -> None:
        project = self.load_project(project_path)
        manager = ProductionStateManager(project.path)
        state = manager.load_or_create(
            project_id=project.project_id,
            current_stage=project.stage_actual,
        )
        state.global_metadata["fao_lifecycle_state"] = (
            metadata or {}
        ).get("lifecycle_state", state.global_metadata.get(
            "fao_lifecycle_state",
            "project_created",
        ))
        state.global_metadata["publication_performed"] = False
        manager.update_current_stage(project.stage_actual)
        manager.add_snapshot(label=label, metadata=metadata)

    @staticmethod
    def _write_json_atomic(path: Path, data: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = path.with_suffix(f"{path.suffix}.tmp")
        try:
            temporary_path.write_text(
                json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            temporary_path.replace(path)
        except Exception:
            temporary_path.unlink(missing_ok=True)
            raise

    def _initialize_checkpoint(
        self,
        *,
        project_path: Path,
        project_id: str,
        request: dict,
    ) -> None:
        manager = ProductionStateManager(project_path)
        state = manager.load_or_create(
            project_id=project_id,
            current_stage="investigacion",
        )
        state.global_metadata.update(
            {
                "fao_schema_name": "cips.fao.project_checkpoint",
                "fao_schema_version": "1.0",
                "fao_lifecycle_state": "project_created",
                "operational_request_path": "operational_request.json",
                "publication_performed": False,
            }
        )
        manager.add_snapshot(
            label="project_created",
            metadata={
                "lifecycle_state": "project_created",
                "topic": request["topic"],
                "platform": request["platform"],
                "duration_seconds": request["duration_seconds"],
                "audience": request["audience"],
                "creative_style": request["creative_style"],
                "publication_performed": False,
            },
        )

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
