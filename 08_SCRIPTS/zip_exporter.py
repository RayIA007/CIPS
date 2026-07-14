"""
=========================================================
Proyecto : CIPS
Release  : 0.7
Build    : 053
Archivo  : zip_exporter.py
Estado   : RELEASE
=========================================================

Genera un paquete ZIP portable de un proyecto CIPS.

Responsabilidades:
- recibir un FinalProjectObject finalizado;
- validar la existencia de manifiesto y métricas;
- recopilar los archivos relevantes del proyecto;
- incluir las exportaciones Markdown y JSON;
- preservar rutas relativas dentro del paquete;
- crear el ZIP mediante escritura temporal segura;
- verificar la integridad del archivo generado;
- registrar la exportación en FinalProjectObject;
- devolver EngineResult.

Este Exporter NO:
- genera contenido editorial;
- llama modelos de Inteligencia Artificial;
- calcula métricas;
- modifica archivos de los Stages;
- publica contenido en plataformas externas.
"""

from pathlib import Path
from typing import Any
import zipfile

from runtime_models import (
    EngineResult,
    FinalProjectObject,
)


class ZIPExporter:
    """
    Construye el paquete distribuible de un proyecto CIPS.

    Entrada:
        FinalProjectObject finalizado, manifestado y medido.

    Salida:
        CIPS_PROJECT_PACKAGE.zip
    """

    COMPONENT_NAME = "zip_exporter"
    VERSION = "0.7"
    OUTPUT_FILENAME = "CIPS_PROJECT_PACKAGE.zip"

    EXCLUDED_SUFFIXES = {
        ".tmp",
        ".pyc",
    }

    EXCLUDED_DIRECTORIES = {
        ".git",
        "__pycache__",
    }

    EXCLUDED_FILENAMES = {
        OUTPUT_FILENAME,
    }

    REQUIRED_PACKAGE_FILES = {
        "07_FINAL.md",
        "MANIFEST.json",
        "PROJECT_METRICS.json",
        "06_EXPORTACIONES/FINAL_EXPORT.md",
        "06_EXPORTACIONES/FINAL_EXPORT.json",
    }

    def execute(
        self,
        final_project: FinalProjectObject,
        output_directory: Path | str,
    ) -> EngineResult:
        """
        Genera y valida el paquete ZIP.
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

            project_path = Path(
                final_project.project.path
            ).resolve()

            files = self._collect_project_files(
                project_path=project_path,
                output_directory=resolved_directory,
            )

            package_errors = (
                self._validate_package_sources(
                    project_path=project_path,
                    files=files,
                )
            )

            if package_errors:
                return EngineResult.fail(
                    message=(
                        "No se pudo construir el paquete ZIP "
                        "porque faltan archivos requeridos."
                    ),
                    errors=package_errors,
                    metadata={
                        **self._base_metadata(
                            final_project
                        ),
                        "output_directory": str(
                            resolved_directory
                        ),
                        "files_collected": len(files),
                    },
                )

            output_path = self._save_zip(
                project_path=project_path,
                output_directory=resolved_directory,
                files=files,
            )

            verification = self._verify_zip(
                output_path
            )

            if not verification["valid"]:
                output_path.unlink(
                    missing_ok=True
                )

                return EngineResult.fail(
                    message=(
                        "El paquete ZIP fue creado, pero "
                        "no superó la validación de integridad."
                    ),
                    errors=verification["errors"],
                    metadata={
                        **self._base_metadata(
                            final_project
                        ),
                        "output_path": str(
                            output_path
                        ),
                    },
                )

            final_project.register_export(
                "zip",
                output_path,
            )

            final_project.metadata[
                self.COMPONENT_NAME
            ] = {
                "executed": True,
                "version": self.VERSION,
                "output_path": str(output_path),
                "files_count": verification[
                    "files_count"
                ],
                "compressed_size_bytes": (
                    output_path.stat().st_size
                ),
                "uncompressed_size_bytes": (
                    verification[
                        "uncompressed_size_bytes"
                    ]
                ),
                "integrity_valid": True,
            }

            return EngineResult.ok(
                data={
                    "final_project": final_project,
                    "output_path": str(output_path),
                },
                message=(
                    "Paquete ZIP del proyecto generado "
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
                    "files_count": verification[
                        "files_count"
                    ],
                    "compressed_size_bytes": (
                        output_path.stat().st_size
                    ),
                    "uncompressed_size_bytes": (
                        verification[
                            "uncompressed_size_bytes"
                        ]
                    ),
                    "integrity_valid": True,
                    "exports_registered": len(
                        final_project.exports
                    ),
                },
            )

        except Exception as error:
            return EngineResult.fail(
                message=(
                    "Error inesperado en ZIPExporter."
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
        Comprueba que el proyecto pueda empaquetarse.
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
                    "ZIPExporter requiere un "
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
                    "El proyecto debe finalizarse antes "
                    "de generar el paquete ZIP."
                ),
                errors=[
                    "FinalProjectObject.final_content vacío."
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

        path = Path(
            output_directory
        ).expanduser()

        if not path.is_absolute():
            path = (
                Path(
                    final_project.project.path
                )
                / path
            )

        return path.resolve()

    def _collect_project_files(
        self,
        project_path: Path,
        output_directory: Path,
    ) -> list[Path]:
        """
        Recopila archivos válidos del proyecto.

        Se excluye el propio ZIP para impedir que el paquete
        termine incluyéndose a sí mismo.
        """

        files: list[Path] = []

        output_zip_path = (
            output_directory
            / self.OUTPUT_FILENAME
        ).resolve()

        for file_path in sorted(
            project_path.rglob("*")
        ):
            if not file_path.is_file():
                continue

            resolved_path = file_path.resolve()

            if resolved_path == output_zip_path:
                continue

            if file_path.name in self.EXCLUDED_FILENAMES:
                continue

            if file_path.suffix.lower() in (
                self.EXCLUDED_SUFFIXES
            ):
                continue

            relative_parts = file_path.relative_to(
                project_path
            ).parts

            if any(
                part in self.EXCLUDED_DIRECTORIES
                for part in relative_parts
            ):
                continue

            files.append(
                file_path
            )

        return files

    def _validate_package_sources(
        self,
        project_path: Path,
        files: list[Path],
    ) -> list[str]:
        """
        Comprueba que los archivos esenciales estén presentes.
        """

        archived_paths = {
            file_path.relative_to(
                project_path
            ).as_posix()
            for file_path in files
        }

        return [
            (
                "Falta archivo requerido para el paquete: "
                f"{required_path}."
            )
            for required_path in sorted(
                self.REQUIRED_PACKAGE_FILES
            )
            if required_path not in archived_paths
        ]

    def _save_zip(
        self,
        project_path: Path,
        output_directory: Path,
        files: list[Path],
    ) -> Path:
        """
        Genera el ZIP mediante un archivo temporal.
        """

        output_path = (
            output_directory
            / self.OUTPUT_FILENAME
        )

        temporary_path = output_path.with_suffix(
            f"{output_path.suffix}.tmp"
        )

        temporary_path.unlink(
            missing_ok=True
        )

        try:
            with zipfile.ZipFile(
                temporary_path,
                mode="w",
                compression=zipfile.ZIP_DEFLATED,
                compresslevel=9,
            ) as archive:
                for file_path in files:
                    archive_name = (
                        Path(
                            project_path.name
                        )
                        / file_path.relative_to(
                            project_path
                        )
                    )

                    archive.write(
                        filename=file_path,
                        arcname=archive_name.as_posix(),
                    )

            temporary_path.replace(
                output_path
            )

        except Exception:
            temporary_path.unlink(
                missing_ok=True
            )
            raise

        return output_path

    def _verify_zip(
        self,
        output_path: Path,
    ) -> dict[str, Any]:
        """
        Verifica la estructura e integridad CRC del ZIP.
        """

        errors: list[str] = []

        if (
            not output_path.exists()
            or not output_path.is_file()
        ):
            return {
                "valid": False,
                "errors": [
                    "El archivo ZIP no existe."
                ],
                "files_count": 0,
                "uncompressed_size_bytes": 0,
            }

        if output_path.stat().st_size <= 0:
            return {
                "valid": False,
                "errors": [
                    "El archivo ZIP está vacío."
                ],
                "files_count": 0,
                "uncompressed_size_bytes": 0,
            }

        with zipfile.ZipFile(
            output_path,
            mode="r",
        ) as archive:
            corrupted_file = archive.testzip()

            if corrupted_file:
                errors.append(
                    "Falló la comprobación CRC del archivo: "
                    f"{corrupted_file}."
                )

            file_records = [
                info
                for info in archive.infolist()
                if not info.is_dir()
            ]

            uncompressed_size = sum(
                info.file_size
                for info in file_records
            )

        return {
            "valid": not errors,
            "errors": errors,
            "files_count": len(
                file_records
            ),
            "uncompressed_size_bytes": (
                uncompressed_size
            ),
        }

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
            "export_format": "zip",
            "compression": "ZIP_DEFLATED",
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
            "export_format": "zip",
            "compression": "ZIP_DEFLATED",
            "writes_files": True,
            "verifies_crc": True,
            "requires_finalized_project": True,
            "requires_manifest": True,
            "requires_metrics": True,
            "required_package_files": sorted(
                self.REQUIRED_PACKAGE_FILES
            ),
            "next_component": (
                "full_export_smoke_test"
            ),
        }