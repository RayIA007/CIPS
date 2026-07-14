"""
=========================================================
Proyecto : CIPS
Release  : 0.7
Build    : 054
Archivo  : full_export_smoke_test.py
Estado   : RELEASE
=========================================================

Prueba integral del Finalization & Export Framework.

Flujo validado:

FinalProjectBuilder
    ↓
FinalizationEngine
    ↓
ManifestEngine
    ↓
MetricsEngine
    ↓
ExportEngine
    ├── MarkdownExporter
    ├── JSONExporter
    └── ZIPExporter
    ↓
Validación de archivos
    ↓
Validación JSON
    ↓
Validación ZIP y CRC
    ↓
Validación del estado final

La prueba utiliza un proyecto CIPS ya completado.

No llama modelos de Inteligencia Artificial.
No modifica los Stages editoriales.
Regenera los artefactos de finalización y exportación.
"""

from __future__ import annotations

import json
import sys
import time
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from export_engine import ExportEngine
from final_project_builder import FinalProjectBuilder
from finalization_engine import FinalizationEngine
from manifest_engine import ManifestEngine
from metrics_engine import MetricsEngine
from project_manager import ProjectManager
from runtime_models import (
    EngineResult,
    FinalProjectObject,
)
from utils import ROOT

# --------------------------------------------------
# Configuración de la prueba
# --------------------------------------------------

DEFAULT_PROJECT_ID = "PROYECTO_0008"

EXPECTED_EXPORT_FILES = [
    "FINAL_EXPORT.md",
    "FINAL_EXPORT.json",
    "CIPS_PROJECT_PACKAGE.zip",
]

EXPECTED_ROOT_FILES = [
    "07_FINAL.md",
    "MANIFEST.json",
    "PROJECT_METRICS.json",
]

EXPECTED_STAGES = [
    "investigacion",
    "verificacion",
    "guion",
    "storyboard",
    "seo",
    "publicacion",
]


@dataclass
class ComponentExecution:
    """
    Registra el resultado de un componente.
    """

    component: str
    success: bool
    message: str = ""
    duration_seconds: float = 0.0
    warnings: list[str] = field(
        default_factory=list
    )
    errors: list[str] = field(
        default_factory=list
    )
    metadata: dict[str, Any] = field(
        default_factory=dict
    )


@dataclass
class ExportValidation:
    """
    Resultado consolidado de validación de exportaciones.
    """

    valid: bool
    errors: list[str] = field(
        default_factory=list
    )
    warnings: list[str] = field(
        default_factory=list
    )
    metadata: dict[str, Any] = field(
        default_factory=dict
    )


def resolve_project_path() -> Path:
    """
    Resuelve el proyecto utilizado por la prueba.

    Puede recibirse una ruta o ID como primer argumento:

        python full_export_smoke_test.py PROYECTO_0008

        python full_export_smoke_test.py
        C:\\ConsejoIA_V5\\04_PROYECTOS\\PROYECTO_0008
    """

    if len(sys.argv) > 1:
        input_value = sys.argv[1].strip()

        supplied_path = Path(
            input_value
        ).expanduser()

        if supplied_path.exists():
            return supplied_path.resolve()


        projects_root = (
            ROOT
            / "04_PROYECTOS"
        )

        candidate = (
            projects_root
            / input_value
        )

        if candidate.exists():
            return candidate.resolve()

        raise FileNotFoundError(
            "No se encontró el proyecto solicitado: "
            f"{input_value}"
        )

    manager = ProjectManager()

    projects_root = Path(
        manager.projects_dir
    )

    default_path = (
        projects_root
        / DEFAULT_PROJECT_ID
    )

    if default_path.exists():
        return default_path.resolve()

    project = manager.load_project()

    return Path(
        project.path
    ).resolve()


def execute_component(
    component_name: str,
    callable_object,
) -> tuple[ComponentExecution, EngineResult]:
    """
    Ejecuta un componente y registra su duración.
    """

    start_time = time.perf_counter()

    try:
        result = callable_object()

    except Exception as error:
        duration = round(
            time.perf_counter() - start_time,
            3,
        )

        failed_result = EngineResult.fail(
            message=(
                f"Excepción no controlada en "
                f"{component_name}."
            ),
            errors=[str(error)],
            metadata={
                "component": component_name,
                "exception_type": (
                    error.__class__.__name__
                ),
            },
        )

        execution = ComponentExecution(
            component=component_name,
            success=False,
            message=failed_result.message,
            duration_seconds=duration,
            errors=list(
                failed_result.errors
            ),
            metadata=dict(
                failed_result.metadata
            ),
        )

        return execution, failed_result

    duration = round(
        time.perf_counter() - start_time,
        3,
    )

    if not isinstance(
        result,
        EngineResult,
    ):
        result = EngineResult.fail(
            message=(
                f"{component_name} devolvió un "
                "resultado incompatible."
            ),
            errors=[
                "Se esperaba EngineResult y se recibió "
                f"{type(result).__name__}."
            ],
            metadata={
                "component": component_name,
            },
        )

    execution = ComponentExecution(
        component=component_name,
        success=result.success,
        message=result.message,
        duration_seconds=duration,
        warnings=list(
            result.warnings
        ),
        errors=list(
            result.errors
        ),
        metadata=dict(
            result.metadata
        ),
    )

    return execution, result


def validate_root_artifacts(
    project_path: Path,
) -> list[str]:
    """
    Comprueba los artefactos ubicados en la raíz.
    """

    errors: list[str] = []

    for filename in EXPECTED_ROOT_FILES:
        file_path = (
            project_path
            / filename
        )

        if not file_path.exists():
            errors.append(
                f"No existe el archivo raíz: {filename}."
            )

            continue

        if not file_path.is_file():
            errors.append(
                f"La ruta no es un archivo: {filename}."
            )

            continue

        if file_path.stat().st_size <= 0:
            errors.append(
                f"El archivo está vacío: {filename}."
            )

    return errors


def validate_export_artifacts(
    export_directory: Path,
) -> list[str]:
    """
    Comprueba los archivos de exportación.
    """

    errors: list[str] = []

    if not export_directory.exists():
        return [
            "No existe la carpeta 06_EXPORTACIONES."
        ]

    for filename in EXPECTED_EXPORT_FILES:
        file_path = (
            export_directory
            / filename
        )

        if not file_path.exists():
            errors.append(
                f"No existe la exportación: {filename}."
            )

            continue

        if not file_path.is_file():
            errors.append(
                f"La exportación no es un archivo: "
                f"{filename}."
            )

            continue

        if file_path.stat().st_size <= 0:
            errors.append(
                f"La exportación está vacía: {filename}."
            )

    return errors


def validate_markdown_export(
    project_path: Path,
    export_directory: Path,
) -> tuple[list[str], dict[str, Any]]:
    """
    Verifica que FINAL_EXPORT.md coincida con 07_FINAL.md.
    """

    errors: list[str] = []

    master_path = (
        project_path
        / "07_FINAL.md"
    )

    export_path = (
        export_directory
        / "FINAL_EXPORT.md"
    )

    if (
        not master_path.exists()
        or not export_path.exists()
    ):
        return errors, {}

    master_content = master_path.read_text(
        encoding="utf-8"
    ).strip()

    export_content = export_path.read_text(
        encoding="utf-8"
    ).strip()

    if master_content != export_content:
        errors.append(
            "FINAL_EXPORT.md no coincide con 07_FINAL.md."
        )

    metadata = {
        "master_characters": len(
            master_content
        ),
        "export_characters": len(
            export_content
        ),
        "content_matches": (
            master_content == export_content
        ),
    }

    return errors, metadata


def validate_json_export(
    project_path: Path,
    export_directory: Path,
) -> tuple[list[str], dict[str, Any]]:
    """
    Valida estructura y contenido esencial del JSON.
    """

    errors: list[str] = []

    json_path = (
        export_directory
        / "FINAL_EXPORT.json"
    )

    if not json_path.exists():
        return errors, {}

    try:
        payload = json.loads(
            json_path.read_text(
                encoding="utf-8"
            )
        )

    except Exception as error:
        return [
            "FINAL_EXPORT.json no contiene JSON válido: "
            f"{error}"
        ], {}

    required_top_level_keys = {
        "schema",
        "project",
        "content",
        "files",
        "metrics",
        "manifest",
        "exports",
        "warnings",
        "errors",
        "metadata",
    }

    missing_keys = sorted(
        required_top_level_keys
        - set(payload)
    )

    if missing_keys:
        errors.append(
            "Faltan claves principales en JSON: "
            + ", ".join(missing_keys)
            + "."
        )

    project_data = payload.get(
        "project",
        {},
    )

    project_id = project_data.get(
        "project_id"
    )

    if project_id != project_path.name:
        errors.append(
            "El project_id del JSON no coincide con "
            "la carpeta del proyecto."
        )

    stages = (
        payload.get(
            "content",
            {},
        ).get(
            "stages",
            {},
        )
    )

    if not isinstance(
        stages,
        dict,
    ):
        errors.append(
            "content.stages no es un diccionario."
        )

        stages = {}

    for stage in EXPECTED_STAGES:
        content = stages.get(
            stage,
            "",
        )

        if not isinstance(
            content,
            str,
        ) or not content.strip():
            errors.append(
                f"El JSON no contiene un Stage válido: "
                f"{stage}."
            )

    metrics = payload.get(
        "metrics",
        {},
    )

    completion_percent = metrics.get(
        "completion_percent"
    )

    if completion_percent != 100.0:
        errors.append(
            "La métrica completion_percent no es 100.0."
        )

    manifest = payload.get(
        "manifest",
        {},
    )

    manifest_project_id = manifest.get(
        "project_id"
    )

    if manifest_project_id != project_path.name:
        errors.append(
            "El project_id del manifiesto incluido "
            "en JSON no coincide."
        )

    metadata = {
        "size_bytes": json_path.stat().st_size,
        "top_level_keys": list(
            payload.keys()
        ),
        "project_id": project_id,
        "stages_count": len(stages),
        "completion_percent": (
            completion_percent
        ),
        "manifest_file_count": (
            manifest.get(
                "file_count"
            )
        ),
    }

    return errors, metadata


def validate_manifest(
    project_path: Path,
) -> tuple[list[str], dict[str, Any]]:
    """
    Valida MANIFEST.json.
    """

    errors: list[str] = []

    manifest_path = (
        project_path
        / "MANIFEST.json"
    )

    if not manifest_path.exists():
        return errors, {}

    try:
        manifest = json.loads(
            manifest_path.read_text(
                encoding="utf-8"
            )
        )

    except Exception as error:
        return [
            "MANIFEST.json no contiene JSON válido: "
            f"{error}"
        ], {}

    if manifest.get(
        "project_id"
    ) != project_path.name:
        errors.append(
            "MANIFEST.json contiene un project_id "
            "incorrecto."
        )

    files = manifest.get(
        "files",
        [],
    )

    if not isinstance(
        files,
        list,
    ):
        errors.append(
            "MANIFEST.json.files no es una lista."
        )

        files = []

    declared_file_count = manifest.get(
        "file_count",
        0,
    )

    if declared_file_count != len(files):
        errors.append(
            "file_count no coincide con la cantidad "
            "de registros del manifiesto."
        )

    invalid_hashes = []

    for file_record in files:
        if not isinstance(
            file_record,
            dict,
        ):
            invalid_hashes.append(
                "<registro inválido>"
            )

            continue

        sha256 = str(
            file_record.get(
                "sha256",
                "",
            )
        )

        if len(sha256) != 64:
            invalid_hashes.append(
                str(
                    file_record.get(
                        "path",
                        "<sin ruta>",
                    )
                )
            )

    if invalid_hashes:
        errors.append(
            "Existen hashes SHA-256 inválidos: "
            + ", ".join(invalid_hashes)
            + "."
        )

    metadata = {
        "file_count": len(files),
        "declared_file_count": (
            declared_file_count
        ),
        "total_size_bytes": manifest.get(
            "total_size_bytes"
        ),
        "providers": manifest.get(
            "providers",
            [],
        ),
        "models": manifest.get(
            "models",
            [],
        ),
        "history_records": len(
            manifest.get(
                "history",
                [],
            )
            if isinstance(
                manifest.get(
                    "history",
                    [],
                ),
                list,
            )
            else []
        ),
        "hash_algorithm": (
            manifest.get(
                "algorithms",
                {},
            ).get(
                "file_hash"
            )
        ),
    }

    return errors, metadata


def validate_metrics(
    project_path: Path,
) -> tuple[list[str], dict[str, Any]]:
    """
    Valida PROJECT_METRICS.json.
    """

    errors: list[str] = []

    metrics_path = (
        project_path
        / "PROJECT_METRICS.json"
    )

    if not metrics_path.exists():
        return errors, {}

    try:
        metrics = json.loads(
            metrics_path.read_text(
                encoding="utf-8"
            )
        )

    except Exception as error:
        return [
            "PROJECT_METRICS.json no contiene JSON válido: "
            f"{error}"
        ], {}

    if metrics.get(
        "stages_total"
    ) != len(EXPECTED_STAGES):
        errors.append(
            "stages_total no coincide con los "
            "Stages esperados."
        )

    if metrics.get(
        "stages_completed"
    ) != len(EXPECTED_STAGES):
        errors.append(
            "stages_completed no coincide con los "
            "Stages esperados."
        )

    if metrics.get(
        "completion_percent"
    ) != 100.0:
        errors.append(
            "completion_percent no es 100.0."
        )

    if int(
        metrics.get(
            "total_characters",
            0,
        )
    ) <= 0:
        errors.append(
            "total_characters no contiene un valor válido."
        )

    if int(
        metrics.get(
            "total_words",
            0,
        )
    ) <= 0:
        errors.append(
            "total_words no contiene un valor válido."
        )

    metadata = {
        "stages_total": metrics.get(
            "stages_total"
        ),
        "stages_completed": metrics.get(
            "stages_completed"
        ),
        "completion_percent": metrics.get(
            "completion_percent"
        ),
        "files_total": metrics.get(
            "files_total"
        ),
        "prompts_total": metrics.get(
            "prompts_total"
        ),
        "responses_total": metrics.get(
            "responses_total"
        ),
        "total_characters": metrics.get(
            "total_characters"
        ),
        "total_words": metrics.get(
            "total_words"
        ),
        "total_tokens": metrics.get(
            "total_tokens"
        ),
        "average_validation_score": (
            metrics.get(
                "average_validation_score"
            )
        ),
    }

    return errors, metadata


def validate_zip_export(
    project_path: Path,
    export_directory: Path,
) -> tuple[list[str], dict[str, Any]]:
    """
    Valida CRC y contenido esencial del ZIP.
    """

    errors: list[str] = []

    zip_path = (
        export_directory
        / "CIPS_PROJECT_PACKAGE.zip"
    )

    if not zip_path.exists():
        return errors, {}

    try:
        with zipfile.ZipFile(
            zip_path,
            mode="r",
        ) as archive:
            corrupted_file = archive.testzip()

            if corrupted_file:
                errors.append(
                    "El ZIP contiene un archivo corrupto: "
                    f"{corrupted_file}."
                )

            records = [
                info
                for info in archive.infolist()
                if not info.is_dir()
            ]

            names = {
                info.filename
                for info in records
            }

            expected_prefix = (
                f"{project_path.name}/"
            )

            required_inside_zip = {
                expected_prefix
                + "07_FINAL.md",
                expected_prefix
                + "MANIFEST.json",
                expected_prefix
                + "PROJECT_METRICS.json",
                expected_prefix
                + "06_EXPORTACIONES/"
                + "FINAL_EXPORT.md",
                expected_prefix
                + "06_EXPORTACIONES/"
                + "FINAL_EXPORT.json",
            }

            missing_files = sorted(
                required_inside_zip
                - names
            )

            if missing_files:
                errors.append(
                    "Faltan archivos requeridos dentro "
                    "del ZIP: "
                    + ", ".join(missing_files)
                    + "."
                )

            invalid_root_files = [
                name
                for name in names
                if not name.startswith(
                    expected_prefix
                )
            ]

            if invalid_root_files:
                errors.append(
                    "El ZIP contiene archivos fuera de "
                    "la carpeta raíz del proyecto."
                )

            uncompressed_size = sum(
                info.file_size
                for info in records
            )

    except Exception as error:
        return [
            "No fue posible abrir o validar el ZIP: "
            f"{error}"
        ], {}

    metadata = {
        "zip_path": str(zip_path),
        "compressed_size_bytes": (
            zip_path.stat().st_size
        ),
        "files_count": len(records),
        "uncompressed_size_bytes": (
            uncompressed_size
        ),
        "crc_valid": not bool(
            corrupted_file
        ),
        "project_root": project_path.name,
    }

    return errors, metadata


def validate_final_project_object(
    final_project: FinalProjectObject,
) -> list[str]:
    """
    Verifica el estado del objeto después de exportar.
    """

    errors: list[str] = []

    if not final_project.is_complete():
        errors.append(
            "FinalProjectObject no está completo."
        )

    if not final_project.final_content.strip():
        errors.append(
            "FinalProjectObject.final_content está vacío."
        )

    if final_project.manifest is None:
        errors.append(
            "FinalProjectObject.manifest es None."
        )

    if final_project.metrics is None:
        errors.append(
            "FinalProjectObject.metrics es None."
        )

    expected_export_types = {
        "master",
        "manifest",
        "metrics",
        "markdown",
        "json",
        "zip",
    }

    missing_exports = sorted(
        expected_export_types
        - set(
            final_project.exports
        )
    )

    if missing_exports:
        errors.append(
            "Faltan exportaciones registradas en el objeto: "
            + ", ".join(missing_exports)
            + "."
        )

    return errors


def validate_all_exports(
    project_path: Path,
    final_project: FinalProjectObject,
) -> ExportValidation:
    """
    Ejecuta todas las comprobaciones finales.
    """

    export_directory = (
        project_path
        / "06_EXPORTACIONES"
    )

    errors: list[str] = []
    warnings: list[str] = []

    errors.extend(
        validate_root_artifacts(
            project_path
        )
    )

    errors.extend(
        validate_export_artifacts(
            export_directory
        )
    )

    markdown_errors, markdown_metadata = (
        validate_markdown_export(
            project_path=project_path,
            export_directory=export_directory,
        )
    )

    errors.extend(
        markdown_errors
    )

    json_errors, json_metadata = (
        validate_json_export(
            project_path=project_path,
            export_directory=export_directory,
        )
    )

    errors.extend(
        json_errors
    )

    manifest_errors, manifest_metadata = (
        validate_manifest(
            project_path
        )
    )

    errors.extend(
        manifest_errors
    )

    metrics_errors, metrics_metadata = (
        validate_metrics(
            project_path
        )
    )

    errors.extend(
        metrics_errors
    )

    zip_errors, zip_metadata = (
        validate_zip_export(
            project_path=project_path,
            export_directory=export_directory,
        )
    )

    errors.extend(
        zip_errors
    )

    errors.extend(
        validate_final_project_object(
            final_project
        )
    )

    if not manifest_metadata.get(
        "providers"
    ):
        warnings.append(
            "El manifiesto todavía no registra proveedores."
        )

    if not manifest_metadata.get(
        "models"
    ):
        warnings.append(
            "El manifiesto todavía no registra modelos."
        )

    if (
        metrics_metadata.get(
            "total_tokens",
            0,
        )
        == 0
    ):
        warnings.append(
            "Las métricas todavía no registran tokens."
        )

    if (
        metrics_metadata.get(
            "average_validation_score",
            0,
        )
        == 0
    ):
        warnings.append(
            "Las métricas todavía no registran "
            "puntuaciones de validación."
        )

    return ExportValidation(
        valid=not errors,
        errors=errors,
        warnings=warnings,
        metadata={
            "project_id": project_path.name,
            "project_path": str(project_path),
            "export_directory": str(
                export_directory
            ),
            "markdown": markdown_metadata,
            "json": json_metadata,
            "manifest": manifest_metadata,
            "metrics": metrics_metadata,
            "zip": zip_metadata,
            "registered_exports": dict(
                final_project.exports
            ),
        },
    )


def print_component_execution(
    execution: ComponentExecution,
) -> None:
    """
    Muestra el resultado de un componente.
    """

    status = (
        "OK"
        if execution.success
        else "ERROR"
    )

    print()
    print(
        f"{execution.component}: {status}"
    )

    print(
        f"  Mensaje: {execution.message}"
    )

    print(
        f"  Duración: "
        f"{execution.duration_seconds} segundos"
    )

    if execution.warnings:
        print("  Advertencias:")

        for warning in execution.warnings:
            print(
                f"    - {warning}"
            )

    if execution.errors:
        print("  Errores:")

        for error in execution.errors:
            print(
                f"    - {error}"
            )


def print_validation_summary(
    validation: ExportValidation,
) -> None:
    """
    Muestra el resumen de validación integral.
    """

    print()
    print("=" * 70)
    print("VALIDACIÓN DE ARTEFACTOS")
    print("=" * 70)

    print(
        f"Resultado integral válido: "
        f"{validation.valid}"
    )

    metadata = validation.metadata

    print()
    print("Markdown:")

    for key, value in metadata.get(
        "markdown",
        {},
    ).items():
        print(
            f"  - {key}: {value}"
        )

    print()
    print("JSON:")

    for key, value in metadata.get(
        "json",
        {},
    ).items():
        print(
            f"  - {key}: {value}"
        )

    print()
    print("Manifest:")

    for key, value in metadata.get(
        "manifest",
        {},
    ).items():
        print(
            f"  - {key}: {value}"
        )

    print()
    print("Metrics:")

    for key, value in metadata.get(
        "metrics",
        {},
    ).items():
        print(
            f"  - {key}: {value}"
        )

    print()
    print("ZIP:")

    for key, value in metadata.get(
        "zip",
        {},
    ).items():
        print(
            f"  - {key}: {value}"
        )

    print()
    print("Exportaciones registradas:")

    for export_type, export_path in metadata.get(
        "registered_exports",
        {},
    ).items():
        print(
            f"  - {export_type}: {export_path}"
        )

    if validation.warnings:
        print()
        print("Advertencias:")

        for warning in validation.warnings:
            print(
                f"- {warning}"
            )

    if validation.errors:
        print()
        print("Errores:")

        for error in validation.errors:
            print(
                f"- {error}"
            )


def main() -> int:
    """
    Ejecuta la prueba integral de exportación.
    """

    print("CIPS Full Export Smoke Test")
    print("=" * 70)

    try:
        project_path = resolve_project_path()

    except Exception as error:
        print(
            "No fue posible resolver el proyecto: "
            f"{error}"
        )

        return 1

    print(
        f"Proyecto: {project_path.name}"
    )

    print(
        f"Ruta: {project_path}"
    )

    print(
        "Flujo: Builder → Finalization → Manifest "
        "→ Metrics → ExportEngine"
    )

    executions: list[ComponentExecution] = []

    builder = FinalProjectBuilder()

    builder_execution, builder_result = (
        execute_component(
            component_name=(
                "final_project_builder"
            ),
            callable_object=lambda: (
                builder.execute(
                    project_path,
                    require_complete=True,
                )
            ),
        )
    )

    executions.append(
        builder_execution
    )

    print_component_execution(
        builder_execution
    )

    if not builder_result.success:
        return 2

    final_project = builder_result.data

    if not isinstance(
        final_project,
        FinalProjectObject,
    ):
        print(
            "El Builder no devolvió "
            "FinalProjectObject."
        )

        return 2

    finalization_execution, finalization_result = (
        execute_component(
            component_name=(
                "finalization_engine"
            ),
            callable_object=lambda: (
                FinalizationEngine().execute(
                    final_project
                )
            ),
        )
    )

    executions.append(
        finalization_execution
    )

    print_component_execution(
        finalization_execution
    )

    if not finalization_result.success:
        return 3

    final_project = finalization_result.data

    manifest_execution, manifest_result = (
        execute_component(
            component_name="manifest_engine",
            callable_object=lambda: (
                ManifestEngine().execute(
                    final_project
                )
            ),
        )
    )

    executions.append(
        manifest_execution
    )

    print_component_execution(
        manifest_execution
    )

    if not manifest_result.success:
        return 4

    final_project = manifest_result.data

    metrics_execution, metrics_result = (
        execute_component(
            component_name="metrics_engine",
            callable_object=lambda: (
                MetricsEngine().execute(
                    final_project
                )
            ),
        )
    )

    executions.append(
        metrics_execution
    )

    print_component_execution(
        metrics_execution
    )

    if not metrics_result.success:
        return 5

    final_project = metrics_result.data

    export_execution, export_result = (
        execute_component(
            component_name="export_engine",
            callable_object=lambda: (
                ExportEngine().execute(
                    final_project=final_project,
                    formats=[
                        "markdown",
                        "json",
                        "zip",
                    ],
                    output_directory=(
                        project_path
                        / "06_EXPORTACIONES"
                    ),
                    stop_on_error=True,
                )
            ),
        )
    )

    executions.append(
        export_execution
    )

    print_component_execution(
        export_execution
    )

    if not export_result.success:
        return 6

    final_project = export_result.data

    validation = validate_all_exports(
        project_path=project_path,
        final_project=final_project,
    )

    print_validation_summary(
        validation
    )

    total_duration = round(
        sum(
            execution.duration_seconds
            for execution in executions
        ),
        3,
    )

    print()
    print("=" * 70)
    print("RESUMEN FINAL")
    print("=" * 70)

    print(
        f"Componentes ejecutados: "
        f"{len(executions)}"
    )

    print(
        "Componentes aprobados: "
        f"{sum(1 for item in executions if item.success)}"
    )

    print(
        f"Duración total: "
        f"{total_duration} segundos"
    )

    print(
        f"Exportaciones registradas: "
        f"{len(final_project.exports)}"
    )

    print(
        f"Resultado final: "
        f"{validation.valid}"
    )

    print(
        "Paquete ZIP: "
        + str(
            final_project.exports.get(
                "zip",
                "No disponible",
            )
        )
    )

    if not validation.valid:
        return 7

    print()
    print(
        "Full Export Smoke Test "
        "completado correctamente."
    )

    return 0


if __name__ == "__main__":
    sys.exit(
        main()
    )