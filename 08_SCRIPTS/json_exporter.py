"""
=========================================================
Proyecto : CIPS
Release  : 0.7
Build    : 052
Archivo  : json_exporter.py
Estado   : RELEASE
=========================================================

Exporta un FinalProjectObject consolidado a JSON.

Responsabilidades:
- recibir un FinalProjectObject válido;
- validar finalización, métricas y manifiesto;
- construir una representación serializable;
- guardar FINAL_EXPORT.json de forma segura;
- registrar la exportación;
- devolver EngineResult.

Este Exporter NO:
- genera contenido editorial;
- llama modelos de Inteligencia Artificial;
- calcula métricas;
- calcula hashes;
- publica contenido;
- genera archivos ZIP, PDF o DOCX.
"""

from dataclasses import asdict
import json
from pathlib import Path
from typing import Any

from runtime_models import (
    EngineResult,
    FinalProjectObject,
)


class JSONExporter:
    """
    Exporta el proyecto consolidado a un archivo JSON.

    Entrada:
        FinalProjectObject finalizado, medido y manifestado.

    Salida:
        FINAL_EXPORT.json
    """

    COMPONENT_NAME = "json_exporter"
    VERSION = "0.7"
    EXPORT_SCHEMA_VERSION = "1.0"
    OUTPUT_FILENAME = "FINAL_EXPORT.json"

    def execute(
        self,
        final_project: FinalProjectObject,
        output_directory: Path | str,
    ) -> EngineResult:
        """
        Genera la exportación JSON.
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

            payload = self._build_payload(
                final_project
            )

            output_path = self._save_json(
                output_directory=resolved_directory,
                payload=payload,
            )

            final_project.register_export(
                "json",
                output_path,
            )

            final_project.metadata[
                self.COMPONENT_NAME
            ] = {
                "executed": True,
                "version": self.VERSION,
                "schema_version": (
                    self.EXPORT_SCHEMA_VERSION
                ),
                "output_path": str(output_path),
                "size_bytes": (
                    output_path.stat().st_size
                ),
                "top_level_keys": list(
                    payload.keys()
                ),
            }

            return EngineResult.ok(
                data={
                    "final_project": final_project,
                    "output_path": str(output_path),
                    "payload": payload,
                },
                message=(
                    "Exportación JSON generada "
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
                    "size_bytes": (
                        output_path.stat().st_size
                    ),
                    "top_level_keys": list(
                        payload.keys()
                    ),
                    "stages_exported": len(
                        payload["content"]["stages"]
                    ),
                    "exports_registered": len(
                        final_project.exports
                    ),
                },
            )

        except Exception as error:
            return EngineResult.fail(
                message=(
                    "Error inesperado en JSONExporter."
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
        Comprueba que el proyecto pueda exportarse a JSON.
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
                    "JSONExporter requiere un "
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

        if final_project.metrics is None:
            return EngineResult.fail(
                message=(
                    "El proyecto no contiene métricas."
                ),
                errors=[
                    "FinalProjectObject.metrics es None."
                ],
                metadata=self._base_metadata(
                    final_project
                ),
            )

        if final_project.manifest is None:
            return EngineResult.fail(
                message=(
                    "El proyecto no contiene manifiesto."
                ),
                errors=[
                    "FinalProjectObject.manifest es None."
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

    def _build_payload(
        self,
        final_project: FinalProjectObject,
    ) -> dict[str, Any]:
        """
        Construye la estructura JSON exportable.
        """

        project = final_project.project

        stages = {
            "investigacion": (
                final_project.investigation
            ),
            "verificacion": (
                final_project.verification
            ),
            "guion": final_project.script,
            "storyboard": (
                final_project.storyboard
            ),
            "seo": final_project.seo,
            "publicacion": (
                final_project.publication
            ),
        }

        return {
            "schema": {
                "name": "CIPS Final Project Export",
                "version": (
                    self.EXPORT_SCHEMA_VERSION
                ),
                "exporter": self.COMPONENT_NAME,
                "exporter_version": self.VERSION,
            },
            "project": {
                "project_id": project.project_id,
                "tema": project.tema,
                "estado": project.estado,
                "stage_actual": (
                    project.stage_actual
                ),
                "ultimo_stage_validado": (
                    project.ultimo_stage_validado
                ),
                "path": str(project.path),
                "config": self._make_serializable(
                    project.config
                ),
                "memory": self._make_serializable(
                    project.memory
                ),
                "metadata": self._make_serializable(
                    project.metadata
                ),
            },
            "content": {
                "stages": stages,
                "final": (
                    final_project.final_content
                ),
            },
            "files": {
                "source_files": dict(
                    final_project.source_files
                ),
                "prompt_files": dict(
                    final_project.prompt_files
                ),
            },
            "metrics": asdict(
                final_project.metrics
            ),
            "manifest": asdict(
                final_project.manifest
            ),
            "exports": dict(
                final_project.exports
            ),
            "warnings": list(
                final_project.warnings
            ),
            "errors": list(
                final_project.errors
            ),
            "metadata": self._make_serializable(
                final_project.metadata
            ),
        }

    def _make_serializable(
        self,
        value: Any,
    ) -> Any:
        """
        Convierte estructuras comunes a valores JSON válidos.
        """

        if value is None:
            return None

        if isinstance(
            value,
            Path,
        ):
            return str(value)

        if isinstance(
            value,
            dict,
        ):
            return {
                str(key): self._make_serializable(
                    item
                )
                for key, item in value.items()
            }

        if isinstance(
            value,
            list,
        ):
            return [
                self._make_serializable(
                    item
                )
                for item in value
            ]

        if isinstance(
            value,
            tuple,
        ):
            return [
                self._make_serializable(
                    item
                )
                for item in value
            ]

        if isinstance(
            value,
            set,
        ):
            return [
                self._make_serializable(
                    item
                )
                for item in sorted(
                    value,
                    key=str,
                )
            ]

        if isinstance(
            value,
            (
                str,
                int,
                float,
                bool,
            ),
        ):
            return value

        return str(value)

    def _save_json(
        self,
        output_directory: Path,
        payload: dict[str, Any],
    ) -> Path:
        """
        Guarda FINAL_EXPORT.json de forma atómica.
        """

        output_path = (
            output_directory
            / self.OUTPUT_FILENAME
        )

        temporary_path = output_path.with_suffix(
            f"{output_path.suffix}.tmp"
        )

        json_content = json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
            sort_keys=False,
        )

        temporary_path.write_text(
            json_content + "\n",
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
            "schema_version": (
                self.EXPORT_SCHEMA_VERSION
            ),
            "project_id": project.project_id,
            "project_path": str(project.path),
            "project_stage": project.stage_actual,
            "output_filename": self.OUTPUT_FILENAME,
            "export_format": "json",
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
            "schema_version": (
                self.EXPORT_SCHEMA_VERSION
            ),
            "output_file": self.OUTPUT_FILENAME,
            "export_format": "json",
            "writes_files": True,
            "requires_finalized_project": True,
            "requires_manifest": True,
            "requires_metrics": True,
            "next_exporter": "zip_exporter",
        }