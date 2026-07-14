"""
=========================================================
Proyecto : CIPS
Release  : 0.5
Build    : 039
Archivo  : automatic_pipeline_smoke_test.py
Estado   : RELEASE
=========================================================

Prueba integral controlada del Pipeline automático:

ProjectManager
    ↓
PipelineEngine
    ↓
KnowledgeEngine
    ↓
KnowledgeResolver
    ↓
ContextCompressor
    ↓
ContextEngine
    ↓
PromptEngine
    ↓
LLMAdapter
    ↓
GeminiLLMProvider
    ↓
ValidatorEngine
    ↓
MemoryEngine
    ↓
Actualización de Stage

La prueba crea un proyecto temporal y no modifica proyectos
existentes.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path
from typing import Any

from gemini_llm_provider import GeminiLLMProvider
from llm_adapter import LLMAdapter
from pipeline_engine import PipelineEngine
from project_manager import ProjectManager
from runtime_constants import STAGE_FILES
from utils import read_yaml


TEST_TOPIC = (
    "Beneficios generales de realizar pausas activas "
    "durante una jornada de estudio"
)

TEST_MODEL = "gemini-3.5-flash"
TEST_MAX_OUTPUT_TOKENS = 4096
TEST_TEMPERATURE = 0.0


def file_hash(path: Path) -> str:
    """
    Calcula SHA-256 para detectar cambios de contenido.
    """

    hasher = hashlib.sha256()

    with path.open("rb") as file:
        while chunk := file.read(8192):
            hasher.update(chunk)

    return hasher.hexdigest()


def snapshot_directory(
    directory: Path,
) -> dict[str, dict[str, Any]]:
    """
    Registra los archivos existentes dentro de una carpeta.
    """

    snapshot: dict[str, dict[str, Any]] = {}

    if not directory.exists():
        return snapshot

    for path in sorted(directory.rglob("*")):
        if not path.is_file():
            continue

        relative_path = str(
            path.relative_to(directory)
        )

        snapshot[relative_path] = {
            "size": path.stat().st_size,
            "hash": file_hash(path),
        }

    return snapshot


def compare_snapshots(
    before: dict[str, dict[str, Any]],
    after: dict[str, dict[str, Any]],
) -> dict[str, list[str]]:
    """
    Identifica archivos agregados, modificados y eliminados.
    """

    before_paths = set(before)
    after_paths = set(after)

    added = sorted(
        after_paths - before_paths
    )

    deleted = sorted(
        before_paths - after_paths
    )

    modified = sorted(
        path
        for path in before_paths & after_paths
        if before[path]["hash"] != after[path]["hash"]
    )

    return {
        "added": added,
        "modified": modified,
        "deleted": deleted,
    }


def print_file_changes(
    changes: dict[str, list[str]],
) -> None:
    """
    Muestra los cambios producidos por el Pipeline.
    """

    print()
    print("Archivos modificados por la ejecución")
    print("-" * 50)

    for category, label in (
        ("added", "Agregados"),
        ("modified", "Modificados"),
        ("deleted", "Eliminados"),
    ):
        files = changes[category]

        print(f"{label}: {len(files)}")

        for filename in files:
            print(f"  - {filename}")


def create_test_project() -> Path:
    """
    Crea un proyecto independiente para la prueba.
    """

    manager = ProjectManager()

    result = manager.create_project(
        TEST_TOPIC
    )

    project_path = Path(
        result["path"]
    )

    return project_path


def build_controlled_pipeline() -> PipelineEngine:
    """
    Construye PipelineEngine con un proveedor Gemini limitado.
    """

    provider = GeminiLLMProvider(
        model=TEST_MODEL,
        temperature=TEST_TEMPERATURE,
        max_output_tokens=TEST_MAX_OUTPUT_TOKENS,
        timeout_seconds=120,
        thinking_level="low",
    )

    pipeline = PipelineEngine()

    pipeline.llm_adapter = LLMAdapter(
        provider=provider
    )

    return pipeline


def validate_execution(
    project_path: Path,
    result,
) -> tuple[bool, list[str]]:
    """
    Comprueba los resultados esenciales de la ejecución.
    """

    errors: list[str] = []

    if not result.success:
        errors.append(
            f"PipelineEngine falló: {result.message}"
        )

        errors.extend(
            result.errors
        )

        return False, errors

    project_yaml = read_yaml(
        project_path / "proyecto.yaml"
    )

    memory_yaml = read_yaml(
        project_path / "memoria.yaml"
    )

    completed_stage = None
    next_stage = None
    llm_response = None

    if isinstance(result.data, dict):
        completed_stage = result.data.get(
            "completed_stage"
        )

        next_stage = result.data.get(
            "next_stage"
        )

        llm_response = result.data.get(
            "llm_response"
        )

    if not completed_stage:
        errors.append(
            "El resultado no contiene completed_stage."
        )

    if not next_stage:
        errors.append(
            "El resultado no contiene next_stage."
        )

    if llm_response is None:
        errors.append(
            "El resultado no contiene LLMResponse."
        )
    else:
        response_content = (
            llm_response.content
            or ""
        ).strip()

        if not response_content:
            errors.append(
                "LLMResponse.content está vacío."
            )

    yaml_stage = (
        project_yaml.get("stage_actual")
        or project_yaml.get("estado")
    )

    if next_stage and yaml_stage != next_stage:
        errors.append(
            "proyecto.yaml no refleja el siguiente Stage. "
            f"Esperado: {next_stage}. Actual: {yaml_stage}."
        )

    memory_stage = memory_yaml.get(
        "ultimo_stage_validado"
    )

    if completed_stage and memory_stage != completed_stage:
        errors.append(
            "memoria.yaml no refleja el Stage validado. "
            f"Esperado: {completed_stage}. "
            f"Actual: {memory_stage}."
        )

    return not errors, errors


def inspect_stage_files(
    project_path: Path,
    completed_stage: str | None,
    next_stage: str | None,
) -> None:
    """
    Informa el estado de los archivos de salida por Stage.
    """

    print()
    print("Archivos de Stage")
    print("-" * 50)

    if completed_stage:
        completed_filename = STAGE_FILES.get(
            completed_stage
        )

        if completed_filename:
            completed_path = (
                project_path
                / completed_filename
            )

            size = (
                completed_path.stat().st_size
                if completed_path.exists()
                else 0
            )

            print(
                f"Stage completado: {completed_stage}"
            )
            print(
                f"Archivo: {completed_path}"
            )
            print(
                f"Tamaño actual: {size} bytes"
            )

    if next_stage:
        next_filename = STAGE_FILES.get(
            next_stage
        )

        if next_filename:
            print(
                f"Siguiente Stage: {next_stage}"
            )
            print(
                f"Archivo: {project_path / next_filename}"
            )


def main() -> int:
    """
    Ejecuta la prueba integral automática.
    """

    print("CIPS Automatic Pipeline Smoke Test")
    print("=" * 50)
    print(
        "Esta prueba realizará una solicitud real a Gemini."
    )
    print(
        "No modificará proyectos anteriores."
    )
    print()

    try:
        project_path = create_test_project()

    except Exception as error:
        print(
            f"No fue posible crear el proyecto temporal: {error}"
        )
        return 1

    print(f"Proyecto temporal: {project_path.name}")
    print(f"Ruta: {project_path}")
    print(f"Tema: {TEST_TOPIC}")
    print(f"Modelo: {TEST_MODEL}")
    print(
        f"Máximo de salida: "
        f"{TEST_MAX_OUTPUT_TOKENS} tokens"
    )
    print()

    before_snapshot = snapshot_directory(
        project_path
    )

    pipeline = build_controlled_pipeline()

    print("Ejecutando Pipeline automático...")
    print()

    result = pipeline.execute(
        project_path
    )

    after_snapshot = snapshot_directory(
        project_path
    )

    print("Resultado")
    print("-" * 50)
    print(f"Éxito: {result.success}")
    print(f"Mensaje: {result.message}")

    if result.warnings:
        print()
        print("Advertencias:")

        for warning in result.warnings:
            print(f"- {warning}")

    if result.errors:
        print()
        print("Errores:")

        for error in result.errors:
            print(f"- {error}")

    changes = compare_snapshots(
        before=before_snapshot,
        after=after_snapshot,
    )

    print_file_changes(
        changes
    )

    is_valid, validation_errors = (
        validate_execution(
            project_path=project_path,
            result=result,
        )
    )

    completed_stage = None
    next_stage = None
    llm_response = None

    if isinstance(result.data, dict):
        completed_stage = result.data.get(
            "completed_stage"
        )

        next_stage = result.data.get(
            "next_stage"
        )

        llm_response = result.data.get(
            "llm_response"
        )

    inspect_stage_files(
        project_path=project_path,
        completed_stage=completed_stage,
        next_stage=next_stage,
    )

    print()
    print("Validación integral")
    print("-" * 50)
    print(f"Resultado válido: {is_valid}")

    if validation_errors:
        for error in validation_errors:
            print(f"- {error}")

    if llm_response is not None:
        content = (
            llm_response.content
            or ""
        ).strip()

        print()
        print("Respuesta Gemini")
        print("-" * 50)
        print(
            f"Modelo registrado: "
            f"{llm_response.model}"
        )
        print(
            f"Caracteres recibidos: {len(content)}"
        )

        preview = content[:500]

        print()
        print("Vista previa:")
        print(preview)

        if len(content) > 500:
            print("...")

    print()
    print(
        "El proyecto temporal se conserva para "
        "inspección manual."
    )
    print(f"Ruta: {project_path}")

    if not is_valid:
        return 2

    print()
    print(
        "Automatic Pipeline Smoke Test "
        "completado correctamente."
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
    