"""
=========================================================
Proyecto : CIPS
Release  : 0.7
Build    : 047
Archivo  : finalization_engine.py
Estado   : RELEASE
=========================================================

Construye el documento maestro de un proyecto CIPS.

Responsabilidades:
- recibir un FinalProjectObject;
- validar que el proyecto tenga todos los Stages requeridos;
- construir el documento maestro en Markdown;
- guardar 07_FINAL.md de forma segura;
- actualizar FinalProjectObject.final_content;
- registrar la exportación maestra;
- preparar el proyecto para ManifestEngine,
  MetricsEngine y ExportEngine.

Este Engine NO:
- llama modelos de Inteligencia Artificial;
- genera investigación, guion, SEO o publicación;
- modifica los entregables de Stages anteriores;
- calcula hashes;
- calcula métricas definitivas;
- genera PDF, DOCX, JSON o ZIP;
- publica contenido en plataformas externas.
"""

from pathlib import Path
from typing import Any

from runtime_models import (
    EngineResult,
    FinalProjectObject,
)
from utils import (
    current_datetime,
    write_text,
)


class FinalizationEngine:
    """
    Construye y persiste el documento maestro del proyecto.

    Entrada:
        FinalProjectObject completo.

    Salida:
        07_FINAL.md

    El documento y el objeto resultantes serán utilizados por:

    - ManifestEngine;
    - MetricsEngine;
    - ExportEngine;
    - exportadores;
    - futuros generadores multimedia;
    - futuros publicadores.
    """

    COMPONENT_NAME = "finalization_engine"
    OUTPUT_FILENAME = "07_FINAL.md"
    VERSION = "0.7"

    REQUIRED_STAGES = [
        "investigacion",
        "verificacion",
        "guion",
        "storyboard",
        "seo",
        "publicacion",
    ]

    # --------------------------------------------------
    # API pública
    # --------------------------------------------------

    def execute(
        self,
        final_project: FinalProjectObject,
    ) -> EngineResult:
        """
        Construye y guarda el documento maestro.

        Flujo:
        1. valida FinalProjectObject;
        2. construye el Markdown consolidado;
        3. guarda 07_FINAL.md de forma segura;
        4. actualiza FinalProjectObject;
        5. registra metadatos y exportación;
        6. devuelve EngineResult.
        """

        try:
            validation_result = self._validate(
                final_project
            )

            if validation_result is not None:
                return validation_result

            markdown = self._build_document(
                final_project
            )

            if not markdown.strip():
                return EngineResult.fail(
                    message=(
                        "FinalizationEngine generó un "
                        "documento maestro vacío."
                    ),
                    errors=[
                        "El Markdown final no contiene texto."
                    ],
                    metadata=self._base_metadata(
                        final_project
                    ),
                )

            output_path = self._save_document(
                final_project=final_project,
                markdown=markdown,
            )

            final_project.final_content = (
                markdown.strip()
            )

            final_project.stage_contents[
                "final"
            ] = final_project.final_content

            self._update_final_metadata(
                final_project=final_project,
                output_path=output_path,
                markdown=markdown,
            )

            statistics = self._document_statistics(
                markdown
            )

            return EngineResult.ok(
                data=final_project,
                message=(
                    "Proyecto final construido y guardado "
                    "correctamente."
                ),
                warnings=list(
                    final_project.warnings
                ),
                metadata={
                    **self._base_metadata(
                        final_project
                    ),
                    "output_path": str(
                        output_path
                    ),
                    "output_filename": (
                        output_path.name
                    ),
                    "characters": statistics[
                        "characters"
                    ],
                    "words": statistics[
                        "words"
                    ],
                    "lines": statistics[
                        "lines"
                    ],
                    "completed_stages": (
                        final_project.completed_stages()
                    ),
                    "exports_count": len(
                        final_project.exports
                    ),
                    "finalized": True,
                },
            )

        except Exception as error:
            return EngineResult.fail(
                message=(
                    "Error inesperado en "
                    "FinalizationEngine."
                ),
                errors=[
                    str(error)
                ],
                metadata={
                    "component": self.COMPONENT_NAME,
                },
            )

    # --------------------------------------------------
    # Validaciones
    # --------------------------------------------------

    def _validate(
        self,
        final_project: FinalProjectObject,
    ) -> EngineResult | None:
        """
        Valida que la entrada pueda finalizarse.

        Devuelve:
            None:
                Cuando la validación es correcta.

            EngineResult:
                Cuando debe detenerse el proceso.
        """

        if final_project is None:
            return EngineResult.fail(
                message=(
                    "No se recibió un "
                    "FinalProjectObject."
                ),
                errors=[
                    "final_project es None."
                ],
                metadata={
                    "component": self.COMPONENT_NAME,
                },
            )

        if not isinstance(
            final_project,
            FinalProjectObject,
        ):
            return EngineResult.fail(
                message=(
                    "FinalizationEngine requiere un "
                    "FinalProjectObject válido."
                ),
                errors=[
                    "El tipo de entrada es incompatible: "
                    f"{type(final_project).__name__}."
                ],
                metadata={
                    "component": self.COMPONENT_NAME,
                },
            )

        project = final_project.project

        if project is None:
            return EngineResult.fail(
                message=(
                    "FinalProjectObject no contiene "
                    "un Project."
                ),
                errors=[
                    "FinalProjectObject.project es None."
                ],
                metadata={
                    "component": self.COMPONENT_NAME,
                },
            )

        if not project.project_id.strip():
            return EngineResult.fail(
                message=(
                    "El proyecto no tiene un "
                    "identificador válido."
                ),
                errors=[
                    "Project.project_id está vacío."
                ],
                metadata={
                    "component": self.COMPONENT_NAME,
                },
            )

        project_path = Path(
            project.path
        )

        if not project_path.exists():
            return EngineResult.fail(
                message=(
                    "No existe la carpeta del proyecto."
                ),
                errors=[
                    str(project_path)
                ],
                metadata=self._base_metadata(
                    final_project
                ),
            )

        if not project_path.is_dir():
            return EngineResult.fail(
                message=(
                    "La ruta del proyecto no es "
                    "una carpeta válida."
                ),
                errors=[
                    str(project_path)
                ],
                metadata=self._base_metadata(
                    final_project
                ),
            )

        missing_stages = (
            final_project.missing_stages(
                self.REQUIRED_STAGES
            )
        )

        if missing_stages:
            return EngineResult.fail(
                message=(
                    "El proyecto todavía no contiene "
                    "todos los entregables requeridos."
                ),
                errors=[
                    (
                        "Falta contenido obligatorio "
                        f"para el Stage: {stage}."
                    )
                    for stage in missing_stages
                ],
                warnings=list(
                    final_project.warnings
                ),
                metadata={
                    **self._base_metadata(
                        final_project
                    ),
                    "missing_stages": (
                        missing_stages
                    ),
                    "completed_stages": (
                        final_project.completed_stages()
                    ),
                },
            )

        empty_required_contents = [
            stage
            for stage in self.REQUIRED_STAGES
            if not final_project.get_stage_content(
                stage
            ).strip()
        ]

        if empty_required_contents:
            return EngineResult.fail(
                message=(
                    "Uno o más Stages requeridos "
                    "están vacíos."
                ),
                errors=[
                    (
                        "El Stage no contiene texto "
                        f"utilizable: {stage}."
                    )
                    for stage in empty_required_contents
                ],
                metadata={
                    **self._base_metadata(
                        final_project
                    ),
                    "empty_stages": (
                        empty_required_contents
                    ),
                },
            )

        return None

    # --------------------------------------------------
    # Construcción del documento
    # --------------------------------------------------

    def _build_document(
        self,
        final_project: FinalProjectObject,
    ) -> str:
        """
        Construye el documento maestro en Markdown.

        Los métodos privados de renderizado se implementan
        en las siguientes partes del archivo.
        """

        blocks: list[str] = []

        blocks.extend(
            self._build_header(
                final_project
            )
        )

        blocks.extend(
            self._build_summary(
                final_project
            )
        )

        sections = [
            (
                "Investigación",
                final_project.investigation,
            ),
            (
                "Verificación",
                final_project.verification,
            ),
            (
                "Guion",
                final_project.script,
            ),
            (
                "Storyboard",
                final_project.storyboard,
            ),
            (
                "SEO",
                final_project.seo,
            ),
            (
                "Publicación",
                final_project.publication,
            ),
        ]

        for title, content in sections:
            blocks.extend(
                self._build_stage_section(
                    title=title,
                    content=content,
                )
            )

        blocks.extend(
            self._build_footer(
                final_project
            )
        )

        return "\n".join(
            blocks
        ).strip() + "\n"
    # --------------------------------------------------
    # Renderizado
    # --------------------------------------------------

    def _build_header(
        self,
        final_project: FinalProjectObject,
    ) -> list[str]:
        """
        Construye el encabezado del documento final.
        """

        project = final_project.project

        return [

            "# PROYECTO FINAL",

            "",

            "---",

            "",

            f"**Proyecto:** {project.project_id}",

            f"**Tema:** {project.tema}",

            f"**Estado:** {project.estado}",

            f"**Stage actual:** {project.stage_actual}",

            f"**Generado:** {current_datetime()}",

            "",

            "---",

            "",
        ]


    def _build_summary(
        self,
        final_project: FinalProjectObject,
    ) -> list[str]:
        """
        Construye el resumen ejecutivo.
        """

        completed = (
            final_project.completed_stages()
        )

        missing = (
            final_project.missing_stages()
        )

        blocks = [

            "# RESUMEN DEL PROYECTO",

            "",

            f"Stages completados: {len(completed)}",

            "",

            f"Stages pendientes: {len(missing)}",

            "",
        ]

        if missing:

            blocks.append(
                "Stages faltantes:"
            )

            blocks.append("")

            for stage in missing:

                blocks.append(
                    f"- {stage}"
                )

            blocks.append("")

        else:

            blocks.extend(

                [

                    "El proyecto contiene todos",

                    "los entregables de producción.",

                    "",
                ]
            )

        blocks.extend(

            [

                "---",

                "",
            ]
        )

        return blocks


    def _build_stage_section(
        self,
        title: str,
        content: str,
    ) -> list[str]:
        """
        Construye una sección del documento maestro.
        """

        blocks = [

            f"# {title}",

            "",
        ]

        normalized = (
            content.strip()
            if content
            else ""
        )

        if normalized:

            blocks.append(
                normalized
            )

        else:

            blocks.extend(

                [

                    "_Sin contenido._",
                ]
            )

        blocks.extend(

            [

                "",

                "---",

                "",
            ]
        )

        return blocks
    def _build_footer(
        self,
        final_project: FinalProjectObject,
    ) -> list[str]:
        """
        Construye el pie del documento maestro.
        """

        project = final_project.project

        completed = (
            final_project.completed_stages()
        )

        return [

            "# INFORMACIÓN TÉCNICA",

            "",

            f"Proyecto: {project.project_id}",

            f"Stages completados: {len(completed)}",

            f"Generado por: {self.COMPONENT_NAME}",

            f"Fecha: {current_datetime()}",

            "",

            "---",

            "",

            "Fin del documento.",

            "",
        ]

    # --------------------------------------------------
    # Persistencia
    # --------------------------------------------------

    def _save_document(
        self,
        final_project: FinalProjectObject,
        markdown: str,
    ) -> Path:
        """
        Guarda 07_FINAL.md dentro del proyecto.

        Este método es el único responsable
        de escribir el documento maestro.
        """

        output_path = (
            final_project.project.path
            / self.OUTPUT_FILENAME
        )

        write_text(
            output_path,
            markdown,
        )

        return output_path

    # --------------------------------------------------
    # Utilidades
    # --------------------------------------------------

    def _document_statistics(
        self,
        markdown: str,
    ) -> dict:
        """
        Calcula estadísticas básicas del documento.

        ManifestEngine y MetricsEngine
        calcularán información mucho
        más detallada posteriormente.
        """

        stripped = markdown.strip()

        if not stripped:

            return {

                "characters": 0,

                "words": 0,

                "lines": 0,
            }

        return {

            "characters": len(
                stripped
            ),

            "words": len(
                stripped.split()
            ),

            "lines": len(
                stripped.splitlines()
            ),
        }

    def _update_final_metadata(
        self,
        final_project: FinalProjectObject,
        output_path: Path,
        markdown: str,
    ) -> None:
        """
        Actualiza los metadatos básicos
        del proyecto final.
        """

        stats = self._document_statistics(
            markdown
        )

        final_project.metadata.update(

            {

                "final_document": str(
                    output_path
                ),

                "final_document_name": (
                    output_path.name
                ),

                "finalized": True,

                "finalized_at": (
                    current_datetime()
                ),

                "statistics": stats,
            }

        )

        final_project.register_export(

            "master",

            output_path,

        )

    def _safe_project_name(
        self,
        final_project: FinalProjectObject,
    ) -> str:
        """
        Devuelve un nombre seguro del proyecto.
        """

        tema = (
            final_project.project.tema
            or ""
        ).strip()

        if tema:

            return tema

        return (
            final_project.project.project_id
        )
    def _base_metadata(
        self,
        final_project: FinalProjectObject,
    ) -> dict[str, Any]:
        """
        Construye metadatos comunes del Engine.
        """

        project = final_project.project

        return {
            "component": self.COMPONENT_NAME,
            "version": self.VERSION,
            "project_id": project.project_id,
            "project_path": str(project.path),
            "project_stage": project.stage_actual,
            "output_filename": self.OUTPUT_FILENAME,
        }
    def get_component_info(
        self,
    ) -> dict[str, Any]:
        """
        Devuelve información pública del componente.
        """

        return {
            "component": self.COMPONENT_NAME,
            "version": self.VERSION,
            "output_file": self.OUTPUT_FILENAME,
            "writes_files": True,
            "requires_complete_project": True,
            "next_engine": "manifest_engine",
        }