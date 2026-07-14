"""
=========================================================
Proyecto : CIPS
Release  : 0.6
Build    : 044
Archivo  : full_pipeline_smoke_test.py
Estado   : RELEASE
=========================================================

Prueba integral del ciclo completo de producción de CIPS.

Flujo:

investigacion
    ↓
verificacion
    ↓
guion
    ↓
storyboard
    ↓
seo
    ↓
publicacion
    ↓
final

Para cada Stage:

- construye el contexto;
- genera el prompt;
- solicita una respuesta real a Gemini;
- persiste la respuesta;
- ejecuta ValidatorEngine 2.0;
- actualiza memoria;
- avanza el proyecto;
- registra archivos, puntuaciones, tokens y duración.

La prueba:

- crea un proyecto temporal;
- no modifica proyectos existentes;
- no publica en plataformas externas;
- se detiene inmediatamente ante cualquier fallo;
- conserva el proyecto generado para inspección.
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
from runtime_constants import FINAL_STAGE, STAGES, STAGE_FILES
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

MAX_EXECUTIONS = 10

EXPECTED_PRODUCTION_STAGES = [
    stage
    for stage in STAGES
    if stage != FINAL_STAGE
]


@dataclass
class FullStageExecution:
    """
    Resultado técnico de un Stage ejecutado.
    """

    stage: str
    next_stage: str
    success: bool
    message: str

    duration_seconds: float = 0.0

    prompt_path: str = ""
    response_path: str = ""

    prompt_characters: int = 0
    response_characters: int = 0

    validation_score: int | None = None
    passing_score: int | None = None
    validation_approved: bool | None = None

    prompt_tokens: int | None = None
    response_tokens: int | None = None
    thinking_tokens: int | None = None
    total_tokens: int | None = None

    provider: str = ""
    model: str = ""
    finish_reason: str = ""

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


def credentials_available() -> bool:
    """
    Comprueba credenciales sin mostrarlas.
    """

    return bool(
        os.getenv("GOOGLE_API_KEY")
        or os.getenv("GEMINI_API_KEY")
    )


def file_hash(path: Path) -> str:
    """
    Calcula SHA-256 de un archivo.
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
    Compara dos estados del proyecto.
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


def read_text_safely(
    path: Path | None,
) -> str:
    """
    Lee un archivo UTF-8 sin lanzar error si no existe.
    """

    if path is None or not path.exists():
        return ""

    return path.read_text(
        encoding="utf-8"
    ).strip()


def create_test_project() -> Path:
    """
    Crea un proyecto independiente para la prueba.
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


def get_prompt_path(
    project_path: Path,
    stage: str,
) -> Path:
    """
    Devuelve la ruta esperada del prompt.
    """

    return (
        project_path
        / "02_PROMPTS"
        / f"PROMPT_{stage.upper()}.md"
    )


def get_response_path(
    project_path: Path,
    stage: str,
) -> Path | None:
    """
    Devuelve el archivo de respuesta asociado al Stage.
    """

    filename = STAGE_FILES.get(stage)

    if not filename:
        return None

    return project_path / filename


def build_stage_project(
    project_path: Path,
    project_data: dict[str, Any],
    stage: str,
) -> Project:
    """
    Construye un Project representando el Stage evaluado.

    Permite volver a ejecutar ValidatorEngine después de que
    proyecto.yaml ya avanzó al siguiente Stage.
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
    Revalida una respuesta sin modificar memoria ni Stage.
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
            "test": "full_pipeline_smoke_test",
            "reevaluation": True,
            "stage": stage,
        },
    )

    result = ValidatorEngine().execute(
        stage_project,
        response,
    )

    return {
        "success": result.success,
        "message": result.message,
        "score": result.metadata.get(
            "score"
        ),
        "passing_score": result.metadata.get(
            "passing_score"
        ),
        "approved": result.metadata.get(
            "approved"
        ),
        "warnings": list(
            result.warnings
        ),
        "errors": list(
            result.errors
        ),
        "metadata": dict(
            result.metadata
        ),
    }


def extract_llm_metrics(
    result,
) -> dict[str, Any]:
    """
    Extrae métricas de LLMResponse del resultado del Pipeline.
    """

    if not isinstance(
        result.data,
        dict,
    ):
        return {}

    llm_response = result.data.get(
        "llm_response"
    )

    if llm_response is None:
        return {}

    metadata = getattr(
        llm_response,
        "metadata",
        {},
    )

    if not isinstance(
        metadata,
        dict,
    ):
        metadata = {}

    return {
        "provider": metadata.get(
            "provider",
            "",
        ),
        "model": getattr(
            llm_response,
            "model",
            "",
        ),
        "prompt_tokens": metadata.get(
            "prompt_tokens"
        ),
        "response_tokens": metadata.get(
            "response_tokens"
        ),
        "thinking_tokens": metadata.get(
            "thinking_tokens"
        ),
        "total_tokens": metadata.get(
            "total_tokens"
        ),
        "finish_reason": str(
            metadata.get(
                "finish_reason",
                "",
            )
        ),
    }


def execute_stage(
    pipeline: PipelineEngine,
    project_path: Path,
) -> FullStageExecution:
    """
    Ejecuta un único Stage y recopila sus métricas.
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

    response_path = get_response_path(
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

    if isinstance(
        result.data,
        dict,
    ):
        next_stage = str(
            result.data.get(
                "next_stage",
                "",
            )
        )

    if not next_stage:
        project_after = read_yaml(
            project_path / "proyecto.yaml"
        )

        next_stage = str(
            project_after.get(
                "stage_actual",
                "",
            )
        )

    llm_metrics = extract_llm_metrics(
        result
    )

    validation_data: dict[str, Any] = {}

    if response_content:
        validation_data = reevaluate_response(
            project_path=project_path,
            stage=stage,
            response_content=response_content,
            model=(
                llm_metrics.get("model")
                or TEST_MODEL
            ),
        )

    errors = list(
        result.errors
    )

    warnings = list(
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
        errors.append(
            "La reevaluación independiente del "
            "ValidatorEngine no fue aprobada."
        )

        errors.extend(
            validation_data.get(
                "errors",
                [],
            )
        )

    if result.success and not response_content:
        errors.append(
            f"El Stage '{stage}' no guardó contenido "
            "en su archivo de respuesta."
        )

    return FullStageExecution(
        stage=stage,
        next_stage=next_stage,
        success=(
            result.success
            and not errors
        ),
        message=result.message,
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
        prompt_tokens=llm_metrics.get(
            "prompt_tokens"
        ),
        response_tokens=llm_metrics.get(
            "response_tokens"
        ),
        thinking_tokens=llm_metrics.get(
            "thinking_tokens"
        ),
        total_tokens=llm_metrics.get(
            "total_tokens"
        ),
        provider=str(
            llm_metrics.get(
                "provider",
                "",
            )
        ),
        model=str(
            llm_metrics.get(
                "model",
                "",
            )
        ),
        finish_reason=str(
            llm_metrics.get(
                "finish_reason",
                "",
            )
        ),
        warnings=warnings,
        errors=errors,
        added_files=changes["added"],
        modified_files=changes["modified"],
        deleted_files=changes["deleted"],
    )


def print_file_list(
    label: str,
    files: list[str],
) -> None:
    """
    Imprime un grupo de archivos.
    """

    print(
        f"  {label}: {len(files)}"
    )

    for filename in files:
        print(
            f"    - {filename}"
        )


def print_stage_result(
    index: int,
    execution: FullStageExecution,
) -> None:
    """
    Muestra el resultado de un Stage.
    """

    print()
    print(
        f"Stage {index}: {execution.stage}"
    )
    print("-" * 70)

    print(
        f"Éxito: {execution.success}"
    )

    print(
        f"Mensaje: {execution.message}"
    )

    print(
        f"Transición: {execution.stage} "
        f"→ {execution.next_stage or '?'}"
    )

    print(
        f"Duración: "
        f"{execution.duration_seconds} segundos"
    )

    print(
        f"Prompt: "
        f"{execution.prompt_characters} caracteres"
    )

    print(
        f"Respuesta: "
        f"{execution.response_characters} caracteres"
    )

    if execution.validation_score is not None:
        print(
            "Validación: "
            f"{execution.validation_score}/100 "
            f"(mínimo {execution.passing_score}/100)"
        )

    print(
        f"Aprobada: "
        f"{execution.validation_approved}"
    )

    if execution.provider:
        print(
            f"Proveedor: {execution.provider}"
        )

    if execution.model:
        print(
            f"Modelo: {execution.model}"
        )

    if execution.finish_reason:
        print(
            f"Finish reason: "
            f"{execution.finish_reason}"
        )

    print()
    print("Tokens:")

    print(
        f"  Prompt: "
        f"{execution.prompt_tokens}"
    )

    print(
        f"  Respuesta: "
        f"{execution.response_tokens}"
    )

    print(
        f"  Razonamiento: "
        f"{execution.thinking_tokens}"
    )

    print(
        f"  Total: "
        f"{execution.total_tokens}"
    )

    print()
    print(
        f"Prompt guardado: "
        f"{execution.prompt_path}"
    )

    print(
        f"Respuesta guardada: "
        f"{execution.response_path}"
    )

    print()
    print("Cambios de archivos:")

    print_file_list(
        "Agregados",
        execution.added_files,
    )

    print_file_list(
        "Modificados",
        execution.modified_files,
    )

    print_file_list(
        "Eliminados",
        execution.deleted_files,
    )

    if execution.warnings:
        print()
        print("Advertencias:")

        for warning in execution.warnings:
            print(
                f"- {warning}"
            )

    if execution.errors:
        print()
        print("Errores:")

        for error in execution.errors:
            print(
                f"- {error}"
            )


def sum_optional_metrics(
    executions: list[FullStageExecution],
    attribute_name: str,
) -> int:
    """
    Suma métricas opcionales.
    """

    total = 0

    for execution in executions:
        value = getattr(
            execution,
            attribute_name,
            None,
        )

        if isinstance(
            value,
            int,
        ):
            total += value

    return total


def print_final_summary(
    project_path: Path,
    executions: list[FullStageExecution],
) -> None:
    """
    Imprime el resumen del ciclo completo.
    """

    project_data = read_yaml(
        project_path / "proyecto.yaml"
    )

    memory_data = read_yaml(
        project_path / "memoria.yaml"
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

    successful_stages = sum(
        1
        for execution in executions
        if execution.success
    )

    total_duration = round(
        sum(
            execution.duration_seconds
            for execution in executions
        ),
        2,
    )

    total_prompt_characters = sum(
        execution.prompt_characters
        for execution in executions
    )

    total_response_characters = sum(
        execution.response_characters
        for execution in executions
    )

    total_prompt_tokens = sum_optional_metrics(
        executions,
        "prompt_tokens",
    )

    total_response_tokens = sum_optional_metrics(
        executions,
        "response_tokens",
    )

    total_thinking_tokens = sum_optional_metrics(
        executions,
        "thinking_tokens",
    )

    total_tokens = sum_optional_metrics(
        executions,
        "total_tokens",
    )

    print()
    print("=" * 70)
    print("RESUMEN DEL PIPELINE COMPLETO")
    print("=" * 70)

    print(
        f"Proyecto: {project_path.name}"
    )

    print(
        f"Tema: {TEST_TOPIC}"
    )

    print(
        f"Stages esperados: "
        f"{len(EXPECTED_PRODUCTION_STAGES)}"
    )

    print(
        f"Stages ejecutados: "
        f"{len(executions)}"
    )

    print(
        f"Stages aprobados: "
        f"{successful_stages}"
    )

    print(
        f"Duración total: "
        f"{total_duration} segundos"
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

    print(
        f"Registros de memoria: "
        f"{len(history)}"
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
    print("Totales de contenido:")

    print(
        f"- Caracteres de prompts: "
        f"{total_prompt_characters}"
    )

    print(
        f"- Caracteres de respuestas: "
        f"{total_response_characters}"
    )

    print()
    print("Totales de tokens:")

    print(
        f"- Prompt: {total_prompt_tokens}"
    )

    print(
        f"- Respuesta: {total_response_tokens}"
    )

    print(
        f"- Razonamiento: "
        f"{total_thinking_tokens}"
    )

    print(
        f"- Total: {total_tokens}"
    )

    print()
    print(
        "El proyecto temporal se conserva "
        "para inspección manual."
    )

    print(
        f"Ruta: {project_path}"
    )


def validate_expected_files(
    project_path: Path,
    executions: list[FullStageExecution],
) -> list[str]:
    """
    Comprueba prompts y respuestas de cada Stage ejecutado.
    """

    errors: list[str] = []

    executed_stages = {
        execution.stage
        for execution in executions
    }

    for stage in executed_stages:
        prompt_path = get_prompt_path(
            project_path=project_path,
            stage=stage,
        )

        if (
            not prompt_path.exists()
            or prompt_path.stat().st_size <= 0
        ):
            errors.append(
                f"No existe un prompt válido para '{stage}'."
            )

        response_path = get_response_path(
            project_path=project_path,
            stage=stage,
        )

        if (
            response_path is None
            or not response_path.exists()
            or response_path.stat().st_size <= 0
        ):
            errors.append(
                f"No existe una respuesta válida para '{stage}'."
            )

    return errors


def validate_final_state(
    project_path: Path,
    executions: list[FullStageExecution],
) -> tuple[bool, list[str]]:
    """
    Valida coherencia integral del proyecto terminado.
    """

    errors: list[str] = []

    project_data = read_yaml(
        project_path / "proyecto.yaml"
    )

    memory_data = read_yaml(
        project_path / "memoria.yaml"
    )

    executed_stages = [
        execution.stage
        for execution in executions
    ]

    for expected_stage in EXPECTED_PRODUCTION_STAGES:
        if expected_stage not in executed_stages:
            errors.append(
                f"No se ejecutó el Stage requerido: "
                f"{expected_stage}."
            )

    for execution in executions:
        if not execution.success:
            errors.append(
                f"El Stage '{execution.stage}' falló."
            )

        if execution.response_characters <= 0:
            errors.append(
                f"El Stage '{execution.stage}' "
                "no guardó respuesta."
            )

        if execution.validation_approved is not True:
            errors.append(
                f"El Stage '{execution.stage}' "
                "no fue aprobado por ValidatorEngine."
            )

        if (
            execution.validation_score is not None
            and execution.passing_score is not None
            and execution.validation_score
            < execution.passing_score
        ):
            errors.append(
                f"El Stage '{execution.stage}' "
                "obtuvo una puntuación insuficiente."
            )

    actual_stage = project_data.get(
        "stage_actual"
    )

    if actual_stage != FINAL_STAGE:
        errors.append(
            "El proyecto no terminó en Stage final. "
            f"Stage actual: {actual_stage}."
        )

    expected_last_stage = (
        EXPECTED_PRODUCTION_STAGES[-1]
        if EXPECTED_PRODUCTION_STAGES
        else ""
    )

    actual_last_validated = memory_data.get(
        "ultimo_stage_validado"
    )

    if actual_last_validated != expected_last_stage:
        errors.append(
            "El último Stage validado no coincide. "
            f"Esperado: {expected_last_stage}. "
            f"Actual: {actual_last_validated}."
        )

    memory_next_stage = memory_data.get(
        "siguiente_stage"
    )

    if memory_next_stage != FINAL_STAGE:
        errors.append(
            "La memoria no apunta a final. "
            f"Actual: {memory_next_stage}."
        )

    history = memory_data.get(
        "historial",
        [],
    )

    if not isinstance(
        history,
        list,
    ):
        errors.append(
            "El historial de memoria no es una lista."
        )

    elif len(history) < len(
        EXPECTED_PRODUCTION_STAGES
    ):
        errors.append(
            "El historial de memoria no contiene "
            "todos los Stages ejecutados."
        )

    errors.extend(
        validate_expected_files(
            project_path=project_path,
            executions=executions,
        )
    )

    return not errors, errors


def verify_final_guard(
    pipeline: PipelineEngine,
    project_path: Path,
) -> tuple[bool, str]:
    """
    Confirma que PipelineEngine no vuelva a ejecutar un
    proyecto que ya alcanzó final.
    """

    result = pipeline.execute(
        project_path
    )

    if not result.success:
        return (
            False,
            result.message,
        )

    finished = bool(
        result.metadata.get(
            "finished",
            False,
        )
    )

    if not finished:
        return (
            False,
            (
                "PipelineEngine no informó que el "
                "proyecto estaba finalizado."
            ),
        )

    return (
        True,
        result.message,
    )


def main() -> int:
    """
    Ejecuta el pipeline completo.
    """

    print("CIPS Full Pipeline Smoke Test")
    print("=" * 70)

    print(
        "Esta prueba realizará solicitudes reales "
        "a Google Gemini."
    )

    print(
        "No publicará contenido ni modificará "
        "proyectos anteriores."
    )

    print(
        "Stages de producción: "
        + " → ".join(
            EXPECTED_PRODUCTION_STAGES
        )
    )

    print(
        f"Estado final esperado: {FINAL_STAGE}"
    )

    print(
        f"Modelo: {TEST_MODEL}"
    )

    print(
        f"Thinking level: "
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

    executions: list[FullStageExecution] = []

    for index in range(
        1,
        MAX_EXECUTIONS + 1,
    ):
        project = ProjectManager().load_project(
            project_path
        )

        if project.stage_actual == FINAL_STAGE:
            print()
            print(
                "El proyecto alcanzó el Stage final."
            )

            break

        print()
        print(
            f"Ejecutando Stage {index}: "
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
                "Pipeline detenido para impedir "
                "continuar después de un fallo."
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

    final_guard_valid = False
    final_guard_message = (
        "No ejecutado porque el proyecto "
        "no alcanzó final."
    )

    if final_valid:
        (
            final_guard_valid,
            final_guard_message,
        ) = verify_final_guard(
            pipeline=pipeline,
            project_path=project_path,
        )

        if not final_guard_valid:
            final_errors.append(
                final_guard_message
            )

            final_valid = False

    print()
    print("=" * 70)
    print("VALIDACIÓN FINAL")
    print("=" * 70)

    print(
        f"Resultado integral válido: "
        f"{final_valid}"
    )

    print(
        f"Protección de proyecto finalizado: "
        f"{final_guard_valid}"
    )

    print(
        f"Mensaje de protección: "
        f"{final_guard_message}"
    )

    if final_errors:
        print()
        print("Errores finales:")

        for error in final_errors:
            print(
                f"- {error}"
            )

    if not final_valid:
        return 2

    print()
    print(
        "Full Pipeline Smoke Test "
        "completado correctamente."
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
    