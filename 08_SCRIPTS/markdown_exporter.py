"""
=========================================================
Proyecto : CIPS
Release  : 0.7
Build    : 051
Archivo  : markdown_exporter.py
Estado   : RELEASE
=========================================================

Exporta un FinalProjectObject consolidado a Markdown.

Responsabilidades:
- recibir un FinalProjectObject válido;
- comprobar que exista contenido final;
- crear la carpeta de exportaciones;
- guardar FINAL_EXPORT.md de forma segura;
- registrar la exportación en FinalProjectObject;
- devolver EngineResult.

Este Exporter NO:
- genera contenido editorial;
- llama modelos de Inteligencia Artificial;
- calcula métricas;
- calcula hashes;
- genera manifiestos;
- publica contenido.
"""

from pathlib import Path
from typing import Any

from runtime_models import (
    EngineResult,
    FinalProjectObject,
)


class MarkdownExporter:
    """
    Exporta el documento maestro del proyecto a Markdown.

    Entrada:
        FinalProjectObject finalizado.

    Salida:
        FINAL_EXPORT.md
    """

    COMPONENT_NAME = "markdown_exporter"
    VERSION = "0.7"
    OUTPUT_FILENAME = "FINAL_EXPORT.md"

    def execute(
        self,
        final_project: FinalProjectObject,
        output_directory: Path | str,
    ) -> EngineResult:
        """
        Genera la exportación Markdown.
        """

        try:
            validation_result = self._validate(
                final_project=final_project,
                output_directory=output_directory,
            )

            if validation_result is not None:
                return validation_result

            resolved_directory = (
                self._resolve_output_directory(
                    final_project=final_project,
                    output_directory=output_directory,
                )
            )

            resolved_directory.mkdir(
                parents=True,
                exist_ok=True,
            )

            markdown = self._build_markdown(
                final_project
            )

            output_path = self._save_markdown(
                output_directory=resolved_directory,
                markdown=markdown,
            )

            final_project.register_export(
                "markdown",
                output_path,
            )

            final_project.metadata[
                self.COMPONENT_NAME
            ] = {
                "executed": True,
                "version": self.VERSION,
                "output_path": str(output_path),
                "characters": len(markdown),
                "words": len(markdown.split()),
                "lines": len(markdown.splitlines()),
            }

            return EngineResult.ok(
                data={
                    "final_project": final_project,
                    "output_path": str(output_path),
                },
                message=(
                    "Exportación Markdown generada "
                    "correctamente."
                ),
                warnings=list(
                    final_project.warnings
                ),
                metadata={
                    **self._base_metadata(
                        final_project
                    ),
                    "output_path": str(output_path),
                    "characters": len(markdown),
                    "words": len(markdown.split()),
                    "lines": len(markdown.splitlines()),
                    "size_bytes": (
                        output_path.stat().st_size
                    ),
                },
            )

        except Exception as error:
            return EngineResult.fail(
                message=(
                    "Error inesperado en "
                    "MarkdownExporter."
                ),
                errors=[str(error)],
                metadata={
                    "component": self.COMPONENT_NAME,
                },
            )

    def _validate(
        self,
        final_project: FinalProjectObject,
        output_directory: Path | str,
    ) -> EngineResult | None:
        """
        Comprueba que el proyecto pueda exportarse.
        """

        if final_project is None:
            return EngineResult.fail(
                message=(
                    "No se recibió un FinalProjectObject."
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
                    "MarkdownExporter requiere un "
                    "FinalProjectObject válido."
                ),
                errors=[
                    "Tipo de entrada incompatible: "
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
                    "FinalProjectObject no contiene Project."
                ),
                errors=[
                    "FinalProjectObject.project es None."
                ],
                metadata={
                    "component": self.COMPONENT_NAME,
                },
            )

        project_path = Path(
            project.path
        )

        if (
            not project_path.exists()
            or not project_path.is_dir()
        ):
            return EngineResult.fail(
                message=(
                    "La carpeta del proyecto no es válida."
                ),
                errors=[
                    str(project_path)
                ],
                metadata=self._base_metadata(
                    final_project
                ),
            )

        if not final_project.final_content.strip():
            return EngineResult.fail(
                message=(
                    "No existe contenido final para exportar."
                ),
                errors=[
                    "FinalProjectObject.final_content vacío."
                ],
                metadata=self._base_metadata(
                    final_project
                ),
            )

        final_path = (
            project_path
            / "07_FINAL.md"
        )

        if not final_path.exists():
            return EngineResult.fail(
                message=(
                    "No existe el documento maestro "
                    "07_FINAL.md."
                ),
                errors=[
                    str(final_path)
                ],
                metadata=self._base_metadata(
                    final_project
                ),
            )

        if output_directory is None:
            return EngineResult.fail(
                message=(
                    "No se recibió una carpeta de salida."
                ),
                errors=[
                    "output_directory es None."
                ],
                metadata=self._base_metadata(
                    final_project
                ),
            )

        return None

    def _resolve_output_directory(
        self,
        final_project: FinalProjectObject,
        output_directory: Path | str,
    ) -> Path:
        """
        Resuelve la carpeta de salida.
        """

        output_path = Path(
            output_directory
        ).expanduser()

        if not output_path.is_absolute():
            output_path = (
                Path(
                    final_project.project.path
                )
                / output_path
            )

        return output_path.resolve()

    def _build_markdown(
        self,
        final_project: FinalProjectObject,
    ) -> str:
        """
        Devuelve el contenido maestro sin reconstruirlo.
        """

        return (
            final_project.final_content
            .strip()
            + "\n"
        )

    def _save_markdown(
        self,
        output_directory: Path,
        markdown: str,
    ) -> Path:
        """
        Guarda FINAL_EXPORT.md de forma atómica.
        """

        output_path = (
            output_directory
            / self.OUTPUT_FILENAME
        )

        temporary_path = output_path.with_suffix(
            f"{output_path.suffix}.tmp"
        )

        temporary_path.write_text(
            markdown,
            encoding="utf-8",
        )

        temporary_path.replace(
            output_path
        )

        return output_path

    def _base_metadata(
        self,
        final_project: FinalProjectObject,
    ) -> dict[str, Any]:
        """
        Construye metadatos comunes.
        """

        project = final_project.project

        return {
            "component": self.COMPONENT_NAME,
            "version": self.VERSION,
            "project_id": project.project_id,
            "project_path": str(project.path),
            "project_stage": project.stage_actual,
            "output_filename": self.OUTPUT_FILENAME,
            "export_format": "markdown",
        }

    def get_component_info(
        self,
    ) -> dict[str, Any]:
        """
        Devuelve información pública del Exporter.
        """

        return {
            "component": self.COMPONENT_NAME,
            "version": self.VERSION,
            "output_file": self.OUTPUT_FILENAME,
            "export_format": "markdown",
            "writes_files": True,
            "requires_finalized_project": True,
            "next_exporter": "json_exporter",
        }