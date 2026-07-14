"""
=========================================================
Proyecto : CIPS
Release  : 0.7
Build    : 048
Archivo  : manifest_engine.py
Estado   : RELEASE
=========================================================

Genera el manifiesto técnico y auditable de un proyecto CIPS.

Responsabilidades:
- recibir un FinalProjectObject finalizado;
- inventariar los archivos del proyecto;
- calcular tamaño y hash SHA-256;
- registrar historial, proveedores y modelos;
- construir ProjectManifest;
- guardar MANIFEST.json de forma segura;
- actualizar FinalProjectObject.manifest;
- registrar la exportación del manifiesto.

Este Engine NO:
- modifica entregables editoriales;
- llama modelos de Inteligencia Artificial;
- calcula métricas editoriales completas;
- genera PDF, DOCX o ZIP;
- publica contenido.
"""

from dataclasses import asdict
import hashlib
import json
from pathlib import Path
from typing import Any

from runtime_models import (
    EngineResult,
    FinalProjectObject,
    ProjectManifest,
)
from utils import current_datetime, read_yaml


class ManifestEngine:
    """
    Construye y guarda el manifiesto técnico del proyecto.

    Entrada:
        FinalProjectObject finalizado.

    Salida:
        MANIFEST.json
    """

    COMPONENT_NAME = "manifest_engine"
    OUTPUT_FILENAME = "MANIFEST.json"
    VERSION = "0.7"
    MANIFEST_VERSION = "1.0"
    HASH_ALGORITHM = "sha256"

    EXCLUDED_FILENAMES = {
        OUTPUT_FILENAME,
    }

    EXCLUDED_SUFFIXES = {
        ".tmp",
        ".pyc",
    }

    EXCLUDED_DIRECTORIES = {
        "__pycache__",
        ".git",
    }

    def execute(
        self,
        final_project: FinalProjectObject,
    ) -> EngineResult:
        """
        Genera el manifiesto y lo guarda en el proyecto.
        """

        try:
            validation_result = self._validate(
                final_project
            )

            if validation_result is not None:
                return validation_result

            manifest = self._build_manifest(
                final_project
            )

            output_path = self._save_manifest(
                final_project=final_project,
                manifest=manifest,
            )

            final_project.manifest = manifest

            final_project.register_export(
                "manifest",
                output_path,
            )

            final_project.metadata[
                "manifest"
            ] = {
                "generated": True,
                "generated_at": manifest.generated_at,
                "output_path": str(output_path),
                "file_count": manifest.file_count,
                "total_size_bytes": (
                    manifest.total_size_bytes
                ),
                "hash_algorithm": (
                    self.HASH_ALGORITHM
                ),
            }

            return EngineResult.ok(
                data=final_project,
                message=(
                    "Manifiesto del proyecto generado "
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
                    "file_count": manifest.file_count,
                    "total_size_bytes": (
                        manifest.total_size_bytes
                    ),
                    "providers": manifest.providers,
                    "models": manifest.models,
                    "history_records": len(
                        manifest.history
                    ),
                    "exports_count": len(
                        final_project.exports
                    ),
                },
            )

        except Exception as error:
            return EngineResult.fail(
                message=(
                    "Error inesperado en ManifestEngine."
                ),
                errors=[str(error)],
                metadata={
                    "component": self.COMPONENT_NAME,
                },
            )

    def _validate(
        self,
        final_project: FinalProjectObject,
    ) -> EngineResult | None:
        """
        Verifica que el proyecto pueda generar un manifiesto.
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
                    "ManifestEngine requiere un "
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

        final_path = (
            project_path
            / "07_FINAL.md"
        )

        if (
            not final_project.final_content.strip()
            or not final_path.exists()
        ):
            return EngineResult.fail(
                message=(
                    "El proyecto debe finalizarse antes "
                    "de generar el manifiesto."
                ),
                errors=[
                    "No existe un 07_FINAL.md válido."
                ],
                metadata=self._base_metadata(
                    final_project
                ),
            )

        return None

    def _build_manifest(
        self,
        final_project: FinalProjectObject,
    ) -> ProjectManifest:
        """
        Construye ProjectManifest en memoria.
        """

        project = final_project.project
        project_path = Path(
            project.path
        )

        project_data = self._read_yaml_dict(
            project_path / "proyecto.yaml"
        )

        memory_data = self._read_yaml_dict(
            project_path / "memoria.yaml"
        )

        release, build = self._extract_cips_version(
            project_path
        )

        providers, models = (
            self._extract_provider_information(
                memory_data=memory_data,
                final_project=final_project,
            )
        )

        history = memory_data.get(
            "historial",
            [],
        )

        if not isinstance(
            history,
            list,
        ):
            history = []

        manifest = ProjectManifest(
            project_id=project.project_id,
            generated_at=current_datetime(),
            manifest_version=(
                self.MANIFEST_VERSION
            ),
            cips_release=release,
            cips_build=build,
            project_path=str(project_path),
            project_stage=project.stage_actual,
            project_status=project.estado,
            providers=providers,
            models=models,
            history=[
                dict(record)
                for record in history
                if isinstance(record, dict)
            ],
            metrics_summary=(
                self._build_metrics_summary(
                    final_project
                )
            ),
            exports=(
                self._build_export_records(
                    final_project
                )
            ),
            metadata={
                "component": self.COMPONENT_NAME,
                "component_version": self.VERSION,
                "project_data": project_data,
                "last_validated_stage": (
                    memory_data.get(
                        "ultimo_stage_validado",
                        "",
                    )
                ),
                "next_stage": memory_data.get(
                    "siguiente_stage",
                    "",
                ),
                "hash_algorithm": (
                    self.HASH_ALGORITHM
                ),
            },
        )

        for file_path in self._iter_project_files(
            project_path
        ):
            manifest.register_file(
                self._build_file_record(
                    project_path=project_path,
                    file_path=file_path,
                    final_project=final_project,
                )
            )

        return manifest

    def _iter_project_files(
        self,
        project_path: Path,
    ):
        """
        Recorre archivos válidos del proyecto.
        """

        for file_path in sorted(
            project_path.rglob("*")
        ):
            if not file_path.is_file():
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

            yield file_path

    def _build_file_record(
        self,
        project_path: Path,
        file_path: Path,
        final_project: FinalProjectObject,
    ) -> dict[str, Any]:
        """
        Construye el registro técnico de un archivo.
        """

        relative_path = str(
            file_path.relative_to(
                project_path
            )
        )

        stat = file_path.stat()

        return {
            "path": relative_path,
            "absolute_path": str(file_path),
            "filename": file_path.name,
            "suffix": file_path.suffix.lower(),
            "category": self._classify_file(
                file_path=file_path,
                relative_path=relative_path,
                final_project=final_project,
            ),
            "size_bytes": stat.st_size,
            "sha256": self._calculate_sha256(
                file_path
            ),
            "modified_timestamp": stat.st_mtime,
        }

    def _classify_file(
        self,
        file_path: Path,
        relative_path: str,
        final_project: FinalProjectObject,
    ) -> str:
        """
        Clasifica el archivo dentro del proyecto.
        """

        normalized_path = str(
            file_path.resolve()
        )

        if normalized_path in {
            str(Path(path).resolve())
            for path in final_project.source_files.values()
        }:
            return "stage_response"

        if normalized_path in {
            str(Path(path).resolve())
            for path in final_project.prompt_files.values()
        }:
            return "prompt"

        if file_path.name == "07_FINAL.md":
            return "master_document"

        if file_path.name in {
            "proyecto.yaml",
            "memoria.yaml",
        }:
            return "control"

        if file_path.name in {
            "CONTEXTO.md",
            "00_TEMA.md",
        }:
            return "project_context"

        if relative_path.startswith(
            "06_EXPORTACIONES"
        ):
            return "export"

        return "auxiliary"

    def _calculate_sha256(
        self,
        file_path: Path,
    ) -> str:
        """
        Calcula el hash SHA-256.
        """

        hasher = hashlib.sha256()

        with file_path.open("rb") as file:
            while True:
                chunk = file.read(8192)

                if not chunk:
                    break

                hasher.update(chunk)

        return hasher.hexdigest()

    def _extract_provider_information(
        self,
        memory_data: dict[str, Any],
        final_project: FinalProjectObject,
    ) -> tuple[list[str], list[str]]:
        """
        Obtiene proveedores y modelos sin duplicados.
        """

        providers: list[str] = []
        models: list[str] = []

        history = memory_data.get(
            "historial",
            [],
        )

        if isinstance(history, list):
            for record in history:
                if not isinstance(record, dict):
                    continue

                metadata = record.get(
                    "metadata",
                    {},
                )

                if not isinstance(metadata, dict):
                    continue

                provider = metadata.get(
                    "provider"
                )

                model = metadata.get(
                    "model"
                )

                self._append_unique(
                    providers,
                    provider,
                )

                self._append_unique(
                    models,
                    model,
                )

        provider_metadata = (
            final_project.metadata.get(
                "llm_provider",
                {},
            )
        )

        if isinstance(
            provider_metadata,
            dict,
        ):
            self._append_unique(
                providers,
                provider_metadata.get(
                    "provider"
                ),
            )

            self._append_unique(
                models,
                provider_metadata.get(
                    "model"
                ),
            )

        return providers, models

    def _build_metrics_summary(
        self,
        final_project: FinalProjectObject,
    ) -> dict[str, Any]:
        """
        Construye un resumen de métricas si ya existen.
        """

        if final_project.metrics is None:
            return {}

        return asdict(
            final_project.metrics
        )

    def _build_export_records(
        self,
        final_project: FinalProjectObject,
    ) -> list[dict[str, Any]]:
        """
        Convierte las exportaciones actuales en registros.
        """

        records: list[dict[str, Any]] = []

        for export_type, export_path in sorted(
            final_project.exports.items()
        ):
            path = Path(
                export_path
            )

            records.append(
                {
                    "type": export_type,
                    "path": str(path),
                    "exists": path.exists(),
                    "size_bytes": (
                        path.stat().st_size
                        if path.exists()
                        and path.is_file()
                        else 0
                    ),
                }
            )

        return records

    def _extract_cips_version(
        self,
        project_path: Path,
    ) -> tuple[str, str]:
        """
        Obtiene Release y Build desde el documento maestro.
        """

        final_path = (
            project_path
            / "07_FINAL.md"
        )

        if not final_path.exists():
            return self.VERSION, ""

        return self.VERSION, "048"

    def _save_manifest(
        self,
        final_project: FinalProjectObject,
        manifest: ProjectManifest,
    ) -> Path:
        """
        Guarda MANIFEST.json mediante escritura atómica.
        """

        output_path = (
            final_project.project.path
            / self.OUTPUT_FILENAME
        )

        temporary_path = output_path.with_suffix(
            f"{output_path.suffix}.tmp"
        )

        payload = asdict(
            manifest
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

    def _read_yaml_dict(
        self,
        file_path: Path,
    ) -> dict[str, Any]:
        """
        Lee YAML y garantiza un diccionario.
        """

        if not file_path.exists():
            return {}

        data = read_yaml(
            file_path
        )

        if not isinstance(
            data,
            dict,
        ):
            return {}

        return data

    def _append_unique(
        self,
        values: list[str],
        value: Any,
    ) -> None:
        """
        Agrega texto no vacío sin duplicarlo.
        """

        if value is None:
            return

        normalized = str(
            value
        ).strip()

        if (
            normalized
            and normalized not in values
        ):
            values.append(
                normalized
            )

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
            "manifest_version": (
                self.MANIFEST_VERSION
            ),
            "project_id": project.project_id,
            "project_path": str(project.path),
            "project_stage": project.stage_actual,
            "output_filename": self.OUTPUT_FILENAME,
            "hash_algorithm": (
                self.HASH_ALGORITHM
            ),
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
            "manifest_version": (
                self.MANIFEST_VERSION
            ),
            "output_file": self.OUTPUT_FILENAME,
            "hash_algorithm": (
                self.HASH_ALGORITHM
            ),
            "writes_files": True,
            "requires_finalized_project": True,
            "next_engine": "metrics_engine",
        }