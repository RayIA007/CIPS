"""
=========================================================
Proyecto : CIPS
Release  : 0.7
Build    : 046
Archivo  : final_project_builder.py
Estado   : RELEASE
=========================================================

Construye un FinalProjectObject a partir de los archivos
reales de un proyecto CIPS.

Responsabilidades:
- cargar el proyecto;
- localizar los entregables de cada Stage;
- leer contenidos UTF-8;
- registrar archivos fuente y prompts;
- detectar Stages faltantes o vacíos;
- consolidar el contenido editorial;
- conservar trazabilidad para métricas, manifiesto y exportación.

Este componente no:
- genera contenido mediante IA;
- modifica los archivos de los Stages;
- calcula hashes;
- calcula métricas definitivas;
- exporta archivos;
- publica contenido.
"""

from pathlib import Path
from typing import Any

from project_manager import ProjectManager
from runtime_constants import FINAL_STAGE, STAGES, STAGE_FILES
from runtime_models import (
    EngineResult,
    FinalProjectObject,
    Project,
)
from utils import current_datetime, read_yaml


class FinalProjectBuilder:
    """
    Construye la representación consolidada de un proyecto.

    Formas de uso:

        FinalProjectBuilder().execute()

        FinalProjectBuilder().execute(project_path)

        FinalProjectBuilder().execute(project)

    Cuando no se proporciona entrada, se carga el proyecto
    activo mediante ProjectManager.
    """

    component_name = "final_project_builder"

    REQUIRED_PRODUCTION_STAGES = [
        stage
        for stage in STAGES
        if stage != FINAL_STAGE
    ]

    def __init__(
        self,
        project_manager: ProjectManager | None = None,
    ) -> None:
        """
        Inicializa el Builder.
        """

        self.project_manager = (
            project_manager
            or ProjectManager()
        )

    def execute(
        self,
        project_input: Project | Path | str | None = None,
        require_complete: bool = True,
    ) -> EngineResult:
        """
        Construye un FinalProjectObject.

        Args:
            project_input:
                Project, ruta del proyecto o None para utilizar
                el proyecto activo.

            require_complete:
                Si es True, falla cuando falta contenido en uno
                o más Stages de producción.

                Si es False, construye un objeto parcial y emite
                advertencias.

        Returns:
            EngineResult:
                FinalProjectObject dentro de data cuando la
                construcción puede completarse.
        """

        try:
            project = self._resolve_project(
                project_input
            )

            structural_errors = (
                self._validate_project_structure(
                    project
                )
            )

            if structural_errors:
                return EngineResult.fail(
                    message=(
                        "No fue posible construir el proyecto "
                        "final porque la estructura es inválida."
                    ),
                    errors=structural_errors,
                    metadata=self._base_metadata(
                        project
                    ),
                )

            final_project = FinalProjectObject(
                project=project,
                metadata={
                    "component": self.component_name,
                    "built_at": current_datetime(),
                    "project_id": project.project_id,
                    "project_path": str(project.path),
                    "project_stage": project.stage_actual,
                    "require_complete": require_complete,
                },
            )

            stage_warnings = self._load_stage_contents(
                final_project
            )

            prompt_warnings = self._load_prompt_files(
                final_project
            )

            auxiliary_warnings = (
                self._load_auxiliary_files(
                    final_project
                )
            )

            warnings = [
                *stage_warnings,
                *prompt_warnings,
                *auxiliary_warnings,
            ]

            missing_stages = final_project.missing_stages(
                self.REQUIRED_PRODUCTION_STAGES
            )

            empty_stage_files = (
                final_project.metadata.get(
                    "empty_stage_files",
                    [],
                )
            )

            final_project.metadata.update(
                {
                    "required_stages": list(
                        self.REQUIRED_PRODUCTION_STAGES
                    ),
                    "completed_stages": (
                        final_project.completed_stages()
                    ),
                    "missing_stages": missing_stages,
                    "source_files_count": len(
                        final_project.source_files
                    ),
                    "prompt_files_count": len(
                        final_project.prompt_files
                    ),
                    "complete": not missing_stages,
                    "empty_stage_files": empty_stage_files,
                }
            )

            final_project.warnings.extend(
                warnings
            )

            if missing_stages and require_complete:
                errors = [
                    (
                        "Falta contenido obligatorio para "
                        f"el Stage: {stage}."
                    )
                    for stage in missing_stages
                ]

                final_project.errors.extend(
                    errors
                )

                return EngineResult.fail(
                    message=(
                        "El proyecto todavía no contiene todos "
                        "los entregables requeridos."
                    ),
                    errors=errors,
                    warnings=warnings,
                    metadata={
                        **self._base_metadata(project),
                        "missing_stages": missing_stages,
                        "completed_stages": (
                            final_project.completed_stages()
                        ),
                        "source_files_count": len(
                            final_project.source_files
                        ),
                        "prompt_files_count": len(
                            final_project.prompt_files
                        ),
                    },
                )

            final_project.final_content = (
                self._build_consolidated_content(
                    final_project
                )
            )

            final_project.stage_contents[
                FINAL_STAGE
            ] = final_project.final_content

            metadata = {
                **self._base_metadata(project),
                "complete": final_project.is_complete(),
                "required_stages": list(
                    self.REQUIRED_PRODUCTION_STAGES
                ),
                "completed_stages": (
                    final_project.completed_stages()
                ),
                "missing_stages": missing_stages,
                "source_files_count": len(
                    final_project.source_files
                ),
                "prompt_files_count": len(
                    final_project.prompt_files
                ),
                "final_characters": len(
                    final_project.final_content
                ),
                "built_at": final_project.metadata.get(
                    "built_at"
                ),
            }

            if missing_stages:
                return EngineResult.ok(
                    data=final_project,
                    message=(
                        "FinalProjectObject parcial construido "
                        "correctamente."
                    ),
                    warnings=warnings,
                    metadata=metadata,
                )

            return EngineResult.ok(
                data=final_project,
                message=(
                    "FinalProjectObject completo construido "
                    "correctamente."
                ),
                warnings=warnings,
                metadata=metadata,
            )

        except Exception as error:
            return EngineResult.fail(
                message=(
                    "Error inesperado en FinalProjectBuilder."
                ),
                errors=[str(error)],
                metadata={
                    "component": self.component_name,
                },
            )

    def build(
        self,
        project_input: Project | Path | str | None = None,
        require_complete: bool = True,
    ) -> FinalProjectObject:
        """
        Construye y devuelve directamente FinalProjectObject.

        Raises:
            ValueError:
                Cuando execute() devuelve un resultado fallido.
        """

        result = self.execute(
            project_input=project_input,
            require_complete=require_complete,
        )

        if not result.success:
            details = "; ".join(
                result.errors
            )

            raise ValueError(
                result.message
                + (
                    f" {details}"
                    if details
                    else ""
                )
            )

        if not isinstance(
            result.data,
            FinalProjectObject,
        ):
            raise TypeError(
                "FinalProjectBuilder no devolvió "
                "un FinalProjectObject."
            )

        return result.data

    def _resolve_project(
        self,
        project_input: Project | Path | str | None,
    ) -> Project:
        """
        Resuelve el proyecto desde las entradas compatibles.
        """

        if isinstance(
            project_input,
            Project,
        ):
            return project_input

        if project_input is None:
            return self.project_manager.load_project()

        project_path = Path(
            project_input
        ).expanduser().resolve()

        return self.project_manager.load_project(
            project_path
        )

    def _validate_project_structure(
        self,
        project: Project,
    ) -> list[str]:
        """
        Comprueba la estructura mínima necesaria.
        """

        errors: list[str] = []

        if not project.path.exists():
            errors.append(
                f"No existe la ruta del proyecto: {project.path}"
            )

            return errors

        if not project.path.is_dir():
            errors.append(
                f"La ruta no es una carpeta: {project.path}"
            )

            return errors

        required_control_files = [
            project.path / "proyecto.yaml",
            project.path / "memoria.yaml",
        ]

        for file_path in required_control_files:
            if not file_path.exists():
                errors.append(
                    f"Falta archivo de control: {file_path.name}"
                )

        return errors

    def _load_stage_contents(
        self,
        final_project: FinalProjectObject,
    ) -> list[str]:
        """
        Lee todos los entregables definidos en STAGE_FILES.
        """

        warnings: list[str] = []
        empty_stage_files: list[str] = []

        for stage in self.REQUIRED_PRODUCTION_STAGES:
            filename = STAGE_FILES.get(
                stage
            )

            if not filename:
                warnings.append(
                    "No existe archivo configurado para "
                    f"el Stage '{stage}'."
                )
                continue

            file_path = (
                final_project.project.path
                / filename
            )

            final_project.source_files[
                stage
            ] = str(file_path)

            if not file_path.exists():
                warnings.append(
                    f"No existe el archivo del Stage "
                    f"'{stage}': {filename}."
                )
                continue

            content = self._read_text_file(
                file_path
            )

            if self._is_placeholder_content(
                content
            ):
                content = ""

            if not content:
                empty_stage_files.append(
                    str(file_path)
                )

                warnings.append(
                    f"El archivo del Stage '{stage}' "
                    "está vacío o contiene un marcador pendiente."
                )

            final_project.set_stage_content(
                stage=stage,
                content=content,
            )

        final_project.metadata[
            "empty_stage_files"
        ] = empty_stage_files

        return warnings

    def _load_prompt_files(
        self,
        final_project: FinalProjectObject,
    ) -> list[str]:
        """
        Registra los prompts existentes de cada Stage.
        """

        warnings: list[str] = []

        prompts_dir = (
            final_project.project.path
            / "02_PROMPTS"
        )

        if not prompts_dir.exists():
            warnings.append(
                "El proyecto no contiene la carpeta 02_PROMPTS."
            )

            return warnings

        for stage in self.REQUIRED_PRODUCTION_STAGES:
            prompt_path = (
                prompts_dir
                / f"PROMPT_{stage.upper()}.md"
            )

            if not prompt_path.exists():
                warnings.append(
                    f"No existe el prompt del Stage '{stage}'."
                )
                continue

            final_project.prompt_files[
                stage
            ] = str(prompt_path)

        return warnings

    def _load_auxiliary_files(
        self,
        final_project: FinalProjectObject,
    ) -> list[str]:
        """
        Carga información de control y archivos auxiliares.
        """

        warnings: list[str] = []

        project_path = final_project.project.path

        project_yaml_path = (
            project_path
            / "proyecto.yaml"
        )

        memory_yaml_path = (
            project_path
            / "memoria.yaml"
        )

        context_path = (
            project_path
            / "CONTEXTO.md"
        )

        topic_path = (
            project_path
            / "00_TEMA.md"
        )

        project_data = read_yaml(
            project_yaml_path
        )

        memory_data = read_yaml(
            memory_yaml_path
        )

        if not isinstance(
            project_data,
            dict,
        ):
            project_data = {}

            warnings.append(
                "proyecto.yaml no contiene una estructura válida."
            )

        if not isinstance(
            memory_data,
            dict,
        ):
            memory_data = {}

            warnings.append(
                "memoria.yaml no contiene una estructura válida."
            )

        final_project.metadata[
            "project_data"
        ] = project_data

        final_project.metadata[
            "memory_data"
        ] = memory_data

        final_project.metadata[
            "project_yaml_path"
        ] = str(project_yaml_path)

        final_project.metadata[
            "memory_yaml_path"
        ] = str(memory_yaml_path)

        if context_path.exists():
            final_project.metadata[
                "context_path"
            ] = str(context_path)

            final_project.metadata[
                "context_content"
            ] = self._read_text_file(
                context_path
            )

        else:
            warnings.append(
                "No existe CONTEXTO.md."
            )

        if topic_path.exists():
            final_project.metadata[
                "topic_path"
            ] = str(topic_path)

            final_project.metadata[
                "topic_content"
            ] = self._read_text_file(
                topic_path
            )

        else:
            warnings.append(
                "No existe 00_TEMA.md."
            )

        return warnings

    def _build_consolidated_content(
        self,
        final_project: FinalProjectObject,
    ) -> str:
        """
        Construye un Markdown consolidado y neutral.

        Este contenido servirá como base para FinalizationEngine
        y los futuros exportadores. No se guarda todavía.
        """

        project = final_project.project

        blocks: list[str] = [
            "# PROYECTO FINAL CIPS",
            "",
            "## Información del proyecto",
            "",
            f"- **ID:** {project.project_id}",
            f"- **Tema:** {project.tema}",
            f"- **Estado:** {project.estado}",
            f"- **Stage actual:** {project.stage_actual}",
            "",
        ]

        stage_titles = {
            "investigacion": "Investigación",
            "verificacion": "Verificación",
            "guion": "Guion",
            "storyboard": "Storyboard",
            "seo": "SEO",
            "publicacion": "Publicación",
        }

        for stage in self.REQUIRED_PRODUCTION_STAGES:
            content = final_project.get_stage_content(
                stage
            )

            if not content:
                continue

            title = stage_titles.get(
                stage,
                stage.replace(
                    "_",
                    " ",
                ).title(),
            )

            blocks.extend(
                [
                    "---",
                    "",
                    f"## {title}",
                    "",
                    content,
                    "",
                ]
            )

        return "\n".join(
            blocks
        ).strip()

    def _read_text_file(
        self,
        file_path: Path,
    ) -> str:
        """
        Lee un archivo UTF-8.
        """

        return file_path.read_text(
            encoding="utf-8"
        ).strip()

    def _is_placeholder_content(
        self,
        content: str,
    ) -> bool:
        """
        Detecta archivos aún pendientes.

        Solo se considera marcador cuando el contenido es corto,
        para evitar eliminar textos reales que mencionen la palabra
        pendiente dentro de una explicación.
        """

        normalized = (
            content
            or ""
        ).strip()

        if not normalized:
            return True

        if len(normalized) >= 250:
            return False

        lowered = normalized.lower()

        placeholder_markers = [
            "pendiente",
            "por completar",
            "contenido pendiente",
            "aquí va",
            "aqui va",
            "sin contenido",
            "todo",
        ]

        return any(
            marker in lowered
            for marker in placeholder_markers
        )

    def _base_metadata(
        self,
        project: Project,
    ) -> dict[str, Any]:
        """
        Construye metadatos comunes.
        """

        return {
            "component": self.component_name,
            "project_id": project.project_id,
            "project_path": str(project.path),
            "project_stage": project.stage_actual,
        }