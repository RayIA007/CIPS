"""
=========================================================
Proyecto : CIPS
Release  : 0.6
Build    : 043
Archivo  : multistage_pipeline_smoke_test.py
Estado   : RELEASE
=========================================================

Prueba integral controlada de múltiples Stages automáticos.

Flujo validado:

Proyecto temporal
    ↓
Investigación
    ↓
Verificación
    ↓
Guion

Para cada Stage:

- genera el prompt;
- solicita una respuesta real a Gemini;
- persiste la respuesta;
- ejecuta ValidatorEngine 2.0;
- actualiza memoria;
- avanza al siguiente Stage;
- registra archivos modificados;
- registra tamaño de prompt y respuesta;
- vuelve a calcular la puntuación del Validator;
- detiene el proceso ante cualquier fallo.

La prueba no modifica proyectos anteriores.
El proyecto temporal se conserva para inspección manual.
"""

from __future__ import annotations

import hashlib
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from gemini_llm_provider import GeminiLLMProvider
from llm_adapter import LLMAdapter
from pipeline_engine import PipelineEngine
from project_manager import ProjectManager
from runtime_constants import FINAL_STAGE, STAGE_FILES
from runtime_models import LLMResponse, Project
from utils import read_yaml
from validator_engine import ValidatorEngine


TEST_TOPIC = (
    "Beneficios generales de realizar pausas activas "
    "durante una jornada de estudio"
)

TEST_MODEL = "gemini-3.5-flash"
TEST_TEMPERATURE = 0.0
TEST_MAX_OUTPUT_TOKENS = 4096
TEST_TIMEOUT_SECONDS = 120
TEST_THINKING_LEVEL = "low"

# Ejecutará:
# 1. investigacion
# 2. verificacion
# 3. guion
MAX_STAGES = 3


@dataclass
class StageExecution:
    """
    Registro completo de una ejecución individual.
    """

    stage: str
    success: bool
    message: str
    next_stage: str = ""
    duration_seconds: float = 0.0

    prompt_path: str = ""
    response_path: str = ""

    prompt_characters: int = 0
    response_characters: int = 0

    validation_score: int | None = None
    passing_score: int | None = None
    validation_approved: bool | None = None

    warnings: list[str] = field(
        default_factory=list
    )

    errors: list[str] = field(
        default_factory=list
    )

    added_files: list[str] = field(
        default_factory=list
    )

    modified_files: list[str] = field(
        default_factory=list
    )

    deleted_files: list[str] = field(
        default_factory=list
    )


def file_hash(path: Path) -> str:
    """
    Calcula SHA-256 para detectar cambios reales.
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
    Registra tamaño y hash de todos los archivos.
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
    Detecta archivos agregados, modificados y eliminados.
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


def credentials_available() -> bool:
    """
    Comprueba la presencia de una credencial sin mostrarla.
    """

    return bool(
        os.getenv("GOOGLE_API_KEY")
        or os.getenv("GEMINI_API_KEY")
    )


def create_test_project() -> Path:
    """
    Crea un proyecto exclusivo para esta prueba.
    """

    result = ProjectManager().create_project(
        TEST_TOPIC
    )

    return Path(
        result["path"]
    )


def build_controlled_pipeline() -> PipelineEngine:
    """
    Construye PipelineEngine con Gemini controlado.
    """

    provider = GeminiLLMProvider(
        model=TEST_MODEL,
        temperature=TEST_TEMPERATURE,
        max_output_tokens=TEST_MAX_OUTPUT_TOKENS,
        timeout_seconds=TEST_TIMEOUT_SECONDS,
        thinking_level=TEST_THINKING_LEVEL,
    )

    pipeline = PipelineEngine()

    pipeline.llm_adapter = LLMAdapter(
        provider=provider
    )

    return pipeline


def get_stage_response_path(
    project_path: Path,
    stage: str,
) -> Path | None:
    """
    Obtiene el archivo asociado al Stage indicado.
    """

    filename = STAGE_FILES.get(stage)

    if not filename:
        return None

    return project_path / filename


def get_prompt_path(
    project_path: Path,
    stage: str,
) -> Path:
    """
    Obtiene la ruta esperada del prompt de un Stage.
    """

    return (
        project_path
        / "02_PROMPTS"
        / f"PROMPT_{stage.upper()}.md"
    )


def read_text_safely(
    path: Path | None,
) -> str:
    """
    Lee UTF-8 sin lanzar error cuando el archivo no existe.
    """

    if path is None or not path.exists():
        return ""

    return path.read_text(
        encoding="utf-8"
    ).strip()


def build_stage_project(
    project_path: Path,
    project_data: dict,
    stage: str,
) -> Project:
    """
    Construye un Project representando el Stage completado.

    Se utiliza para volver a calcular la puntuación después
    de que PipelineEngine ya actualizó proyecto.yaml.
    """

    return Project(
        project_id=project_data.get(
            "id",
            project_path.name,
        ),
        path=project_path,
        tema=project_data.get(
            "tema",
            TEST_TOPIC,
        ),
        estado=stage,
        stage_actual=stage,
        ultimo_stage_validado=project_data.get(
            "ultimo_stage_validado",
            "",
        ),
        config={},
        memory={},
        metadata=dict(project_data),
    )


def reevaluate_response(
    project_path: Path,
    stage: str,
    response_content: str,
    model: str,
) -> dict[str, Any]:
    """
    Recalcula la validación para extraer puntuación y métricas.

    No modifica memoria ni proyecto.yaml.
    """

    project_data = read_yaml(
        project_path / "proyecto.yaml"
    )

    stage_project = build_stage_project(
        project_path=project_path,
        project_data=project_data,
        stage=stage,
    )

    response = LLMResponse(
        content=response_content,
        model=model,
        metadata={
            "test": "multistage_pipeline_smoke_test",
            "reevaluation": True,
            "stage": stage,
        },
    )

    validation = ValidatorEngine().execute(
        stage_project,
        response,
    )

    return {
        "success": validation.success,
        "message": validation.message,
        "score": validation.metadata.get(
            "score"
        ),
        "passing_score": validation.metadata.get(
            "passing_score"
        ),
        "approved": validation.metadata.get(
            "approved"
        ),
        "warnings": list(
            validation.warnings
        ),
        "errors": list(
            validation.errors
        ),
        "metadata": dict(
            validation.metadata
        ),
    }


def execute_stage(
    pipeline: PipelineEngine,
    project_path: Path,
) -> StageExecution:
    """
    Ejecuta exactamente un Stage del proyecto.
    """

    manager = ProjectManager()

    project_before = manager.load_project(
        project_path
    )

    stage = project_before.stage_actual

    before_snapshot = snapshot_directory(
        project_path
    )

    start_time = time.perf_counter()

    result = pipeline.execute(
        project_path
    )

    duration_seconds = round(
        time.perf_counter() - start_time,
        2,
    )

    after_snapshot = snapshot_directory(
        project_path
    )

    changes = compare_snapshots(
        before=before_snapshot,
        after=after_snapshot,
    )

    prompt_path = get_prompt_path(
        project_path=project_path,
        stage=stage,
    )

    response_path = get_stage_response_path(
        project_path=project_path,
        stage=stage,
    )

    prompt_content = read_text_safely(
        prompt_path
    )

    response_content = read_text_safely(
        response_path
    )

    next_stage = ""

    if isinstance(result.data, dict):
        next_stage = str(
            result.data.get(
                "next_stage",
                "",
            )
        )

    if not next_stage:
        project_after_data = read_yaml(
            project_path / "proyecto.yaml"
        )

        next_stage = str(
            project_after_data.get(
                "stage_actual",
                "",
            )
        )

    model = TEST_MODEL

    if isinstance(result.data, dict):
        llm_response = result.data.get(
            "llm_response"
        )

        if llm_response is not None:
            model = getattr(
                llm_response,
                "model",
                TEST_MODEL,
            )

    validation_data: dict[str, Any] = {}

    if response_content:
        validation_data = reevaluate_response(
            project_path=project_path,
            stage=stage,
            response_content=response_content,
            model=model,
        )

    stage_errors = list(
        result.errors
    )

    stage_warnings = list(
        result.warnings
    )

    if (
        result.success
        and validation_data
        and not validation_data.get(
            "success",
            False,
        )
    ):
        stage_errors.append(
            "La reevaluación independiente "
            "del Validator no fue aprobada."
        )

        stage_errors.extend(
            validation_data.get(
                "errors",
                [],
            )
        )

    return StageExecution(
        stage=stage,
        success=(
            result.success
            and not stage_errors
        ),
        message=result.message,
        next_stage=next_stage,
        duration_seconds=duration_seconds,
        prompt_path=str(prompt_path),
        response_path=(
            str(response_path)
            if response_path
            else ""
        ),
        prompt_characters=len(
            prompt_content
        ),
        response_characters=len(
            response_content
        ),
        validation_score=validation_data.get(
            "score"
        ),
        passing_score=validation_data.get(
            "passing_score"
        ),
        validation_approved=validation_data.get(
            "approved"
        ),
        warnings=stage_warnings,
        errors=stage_errors,
        added_files=changes["added"],
        modified_files=changes["modified"],
        deleted_files=changes["deleted"],
    )


def print_stage_result(
    index: int,
    execution: StageExecution,
) -> None:
    """
    Muestra el resultado completo de un Stage.
    """

    print()
    print(
        f"Stage {index}: {execution.stage}"
    )
    print("-" * 60)

    print(
        f"Éxito: {execution.success}"
    )

    print(
        f"Mensaje: {execution.message}"
    )

    print(
        f"Siguiente Stage: "
        f"{execution.next_stage or 'No disponible'}"
    )

    print(
        f"Duración: "
        f"{execution.duration_seconds} segundos"
    )

    print(
        f"Caracteres del prompt: "
        f"{execution.prompt_characters}"
    )

    print(
        f"Caracteres de respuesta: "
        f"{execution.response_characters}"
    )

    if execution.validation_score is not None:
        print(
            "Puntuación de validación: "
            f"{execution.validation_score}/100"
        )

    if execution.passing_score is not None:
        print(
            "Puntuación mínima: "
            f"{execution.passing_score}/100"
        )

    if execution.validation_approved is not None:
        print(
            "Validación aprobada: "
            f"{execution.validation_approved}"
        )

    print()
    print(
        f"Prompt: {execution.prompt_path}"
    )

    print(
        f"Respuesta: {execution.response_path}"
    )

    print()
    print("Cambios de archivos:")

    print(
        f"  Agregados: "
        f"{len(execution.added_files)}"
    )

    for filename in execution.added_files:
        print(f"    - {filename}")

    print(
        f"  Modificados: "
        f"{len(execution.modified_files)}"
    )

    for filename in execution.modified_files:
        print(f"    - {filename}")

    print(
        f"  Eliminados: "
        f"{len(execution.deleted_files)}"
    )

    for filename in execution.deleted_files:
        print(f"    - {filename}")

    if execution.warnings:
        print()
        print("Advertencias:")

        for warning in execution.warnings:
            print(f"- {warning}")

    if execution.errors:
        print()
        print("Errores:")

        for error in execution.errors:
            print(f"- {error}")


def print_final_summary(
    project_path: Path,
    executions: list[StageExecution],
) -> None:
    """
    Muestra el resumen integral de la prueba.
    """

    project_data = read_yaml(
        project_path / "proyecto.yaml"
    )

    memory_data = read_yaml(
        project_path / "memoria.yaml"
    )

    total_duration = round(
        sum(
            execution.duration_seconds
            for execution in executions
        ),
        2,
    )

    successful_stages = sum(
        1
        for execution in executions
        if execution.success
    )

    print()
    print("=" * 60)
    print("RESUMEN MULTISTAGE")
    print("=" * 60)

    print(
        f"Proyecto: {project_path.name}"
    )

    print(
        f"Stages solicitados: {MAX_STAGES}"
    )

    print(
        f"Stages ejecutados: {len(executions)}"
    )

    print(
        f"Stages aprobados: {successful_stages}"
    )

    print(
        f"Duración total: {total_duration} segundos"
    )

    print(
        "Stage actual en proyecto.yaml: "
        f"{project_data.get('stage_actual')}"
    )

    print(
        "Último Stage validado: "
        f"{memory_data.get('ultimo_stage_validado')}"
    )

    print(
        "Siguiente Stage en memoria: "
        f"{memory_data.get('siguiente_stage')}"
    )

    history = memory_data.get(
        "historial",
        [],
    )

    print(
        "Registros de memoria: "
        f"{len(history) if isinstance(history, list) else 0}"
    )

    print()
    print("Transiciones:")

    for execution in executions:
        status = (
            "APROBADO"
            if execution.success
            else "DETENIDO"
        )

        print(
            f"- {execution.stage} "
            f"→ {execution.next_stage or '?'} "
            f"[{status}]"
        )

    print()
    print("Puntuaciones:")

    for execution in executions:
        score = (
            f"{execution.validation_score}/100"
            if execution.validation_score is not None
            else "No disponible"
        )

        print(
            f"- {execution.stage}: {score}"
        )

    print()
    print(
        "El proyecto temporal se conserva "
        "para inspección manual."
    )

    print(
        f"Ruta: {project_path}"
    )


def validate_final_state(
    project_path: Path,
    executions: list[StageExecution],
) -> tuple[bool, list[str]]:
    """
    Comprueba coherencia global del proyecto temporal.
    """

    errors: list[str] = []

    if not executions:
        errors.append(
            "No se ejecutó ningún Stage."
        )

        return False, errors

    for execution in executions:
        if not execution.success:
            errors.append(
                f"El Stage '{execution.stage}' falló."
            )

        if execution.response_characters <= 0:
            errors.append(
                f"El Stage '{execution.stage}' "
                "no guardó una respuesta."
            )

        if execution.validation_approved is not True:
            errors.append(
                f"El Stage '{execution.stage}' "
                "no quedó aprobado por ValidatorEngine."
            )

        if (
            execution.validation_score is not None
            and execution.passing_score is not None
            and execution.validation_score
            < execution.passing_score
        ):
            errors.append(
                f"El Stage '{execution.stage}' obtuvo "
                "una puntuación menor al mínimo."
            )

    project_data = read_yaml(
        project_path / "proyecto.yaml"
    )

    expected_stage = executions[-1].next_stage

    actual_stage = project_data.get(
        "stage_actual"
    )

    if (
        expected_stage
        and actual_stage != expected_stage
    ):
        errors.append(
            "El Stage final de proyecto.yaml "
            "no coincide con la última transición. "
            f"Esperado: {expected_stage}. "
            f"Actual: {actual_stage}."
        )

    return not errors, errors


def main() -> int:
    """
    Ejecuta la prueba automática de múltiples Stages.
    """

    print("CIPS Multistage Pipeline Smoke Test")
    print("=" * 60)

    print(
        "Esta prueba realizará varias solicitudes "
        "reales a Gemini."
    )

    print(
        "No modificará proyectos existentes."
    )

    print(
        f"Stages máximos: {MAX_STAGES}"
    )

    print(
        f"Modelo: {TEST_MODEL}"
    )

    print(
        "Thinking level: "
        f"{TEST_THINKING_LEVEL}"
    )

    print(
        "Máximo de salida por Stage: "
        f"{TEST_MAX_OUTPUT_TOKENS} tokens"
    )

    print()

    if not credentials_available():
        print(
            "ERROR: No se encontró GOOGLE_API_KEY "
            "ni GEMINI_API_KEY."
        )

        return 1

    try:
        project_path = create_test_project()

    except Exception as error:
        print(
            "No fue posible crear el proyecto temporal: "
            f"{error}"
        )

        return 1

    print(
        f"Proyecto temporal: {project_path.name}"
    )

    print(
        f"Ruta: {project_path}"
    )

    print(
        f"Tema: {TEST_TOPIC}"
    )

    pipeline = build_controlled_pipeline()

    executions: list[StageExecution] = []

    for index in range(
        1,
        MAX_STAGES + 1,
    ):
        project = ProjectManager().load_project(
            project_path
        )

        if project.stage_actual == FINAL_STAGE:
            print()
            print(
                "El proyecto alcanzó la etapa final."
            )

            break

        print()
        print(
            f"Ejecutando Stage {index}/{MAX_STAGES}: "
            f"{project.stage_actual}"
        )

        execution = execute_stage(
            pipeline=pipeline,
            project_path=project_path,
        )

        executions.append(
            execution
        )

        print_stage_result(
            index=index,
            execution=execution,
        )

        if not execution.success:
            print()
            print(
                "Pipeline detenido para evitar continuar "
                "después de una validación fallida."
            )

            break

    print_final_summary(
        project_path=project_path,
        executions=executions,
    )

    final_valid, final_errors = (
        validate_final_state(
            project_path=project_path,
            executions=executions,
        )
    )

    print()
    print("=" * 60)
    print("VALIDACIÓN FINAL")
    print("=" * 60)

    print(
        f"Resultado integral válido: {final_valid}"
    )

    if final_errors:
        print()

        for error in final_errors:
            print(f"- {error}")

    if not final_valid:
        return 2

    print()
    print(
        "Multistage Pipeline Smoke Test "
        "completado correctamente."
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())