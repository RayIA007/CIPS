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

import argparse
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
from production_media_router import ProductionMediaRouter
from production_final_review import ProductionFinalReviewBridge
from project_manager import ProjectManager
from runtime_constants import FINAL_STAGE, STAGES, STAGE_FILES
from runtime_models import LLMResponse, Project
from utils import read_yaml, write_yaml
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

EXPECTED_PRODUCTION_STAGES = [
    stage
    for stage in STAGES
    if stage != FINAL_STAGE
]

MAX_EXECUTIONS = len(EXPECTED_PRODUCTION_STAGES)
MEDIA_STAGES = frozenset(ProductionMediaRouter.handled_stages)


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
    response_size_bytes: int = 0
    response_kind: str = "text"
    artifact_paths: list[str] = field(default_factory=list)

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

    retry_enabled: bool = False

    retry_attempts: int = 0

    retry_count: int = 0

    retry_exhausted: bool = False

    succeeded_after_retry: bool = False

    retry_total_duration: float | None = None

    retry_attempt_history: list[dict[str, Any]] = field(
        default_factory=list
    )
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
    """Lee únicamente archivos UTF-8 regulares; nunca interpreta media binaria."""

    if path is None or not path.is_file():
        return ""

    try:
        return path.read_text(encoding="utf-8").strip()
    except UnicodeDecodeError:
        return ""


def response_size_bytes(path: Path | None) -> int:
    """Devuelve bytes de un archivo o de todos los archivos de un directorio."""

    if path is None or not path.exists():
        return 0
    if path.is_file():
        return path.stat().st_size
    if path.is_dir():
        return sum(
            item.stat().st_size
            for item in path.rglob("*")
            if item.is_file()
        )
    return 0


def memory_completed_stages(project_path: Path) -> list[str]:
    """Obtiene los Stages completados preservados en memoria.yaml."""

    memory_data = read_yaml(project_path / "memoria.yaml")
    history = memory_data.get("historial", [])
    if not isinstance(history, list):
        return []
    return [
        str(record.get("stage", "")).strip()
        for record in history
        if isinstance(record, dict) and str(record.get("stage", "")).strip()
    ]


def previous_stage(stage: str) -> str:
    """Devuelve el Stage anterior de la secuencia oficial."""

    if stage not in STAGES:
        return ""
    index = STAGES.index(stage)
    return STAGES[index - 1] if index > 0 else ""


def first_repair_stage(project_path: Path, current_stage: str) -> str | None:
    """Detecta el primer Stage ya superado cuyo artifact preservado es inválido."""

    router = ProductionMediaRouter()
    current_index = STAGES.index(current_stage) if current_stage in STAGES else len(STAGES)

    def already_required(stage: str) -> bool:
        return STAGES.index(stage) < current_index or current_stage == FINAL_STAGE

    def sidecar_invalid(path: Path) -> bool:
        sidecar = Path(f"{path}.meta.json")
        return (
            not sidecar.is_file()
            or bool(router._sidecar_integrity_error(path, sidecar))
        )

    audio = project_path / "voice" / "audio.mp3"
    if already_required("voz"):
        if router._validation_errors(audio, "audio") or sidecar_invalid(audio):
            return "voz"

    images_dir = project_path / "images"
    images = (
        sorted(
            path for path in images_dir.iterdir()
            if path.is_file() and path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}
        )
        if images_dir.is_dir()
        else []
    )
    if already_required("imagenes"):
        if not images:
            return "imagenes"
        if any(
            router._validation_errors(path, "image") or sidecar_invalid(path)
            for path in images
        ):
            return "imagenes"

    subtitles = project_path / "subtitles" / "subtitles.srt"
    if already_required("subtitulos"):
        if not subtitles.is_file() or subtitles.stat().st_size <= 0:
            return "subtitulos"
        try:
            subtitle_text = subtitles.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            return "subtitulos"
        if "-->" not in subtitle_text:
            return "subtitulos"

    raw_video = project_path / "video" / "raw_video.mp4"
    final_video = project_path / "final" / "short.mp4"
    if already_required("ensamblado"):
        for path in (raw_video, final_video):
            if router._validation_errors(path, "video") or sidecar_invalid(path):
                return "ensamblado"

    if (
        current_stage == FINAL_STAGE
        and not ProductionFinalReviewBridge.has_approved_review(project_path)
    ):
        return "control_calidad"

    return None


def prepare_project_for_resume(project_path: Path) -> str | None:
    """Rebobina solo cuando un Stage ya superado dejó evidencia inválida."""

    project = ProjectManager().load_project(project_path)
    repair_stage = first_repair_stage(project_path, project.stage_actual)
    if repair_stage is None:
        return None

    if project.stage_actual in STAGES and STAGES.index(repair_stage) >= STAGES.index(project.stage_actual):
        return None

    project_yaml = project_path / "proyecto.yaml"
    project_data = read_yaml(project_yaml)
    project_data["stage_actual"] = repair_stage
    project_data["estado"] = repair_stage
    project_data["ultimo_stage_validado"] = previous_stage(repair_stage)
    write_yaml(project_yaml, project_data)

    memory_yaml = project_path / "memoria.yaml"
    memory_data = read_yaml(memory_yaml)
    if not isinstance(memory_data, dict):
        memory_data = {}
    memory_data["ultimo_stage_validado"] = previous_stage(repair_stage)
    memory_data["siguiente_stage"] = repair_stage
    write_yaml(memory_yaml, memory_data)
    return repair_stage


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
    Extrae métricas del LLM tanto en ejecuciones exitosas
    como en fallos del proveedor.
    """

    result_metadata = getattr(
        result,
        "metadata",
        {},
    )

    if not isinstance(
        result_metadata,
        dict,
    ):
        result_metadata = {}

    llm_response = None

    if isinstance(
        result.data,
        dict,
    ):
        llm_response = result.data.get(
            "llm_response"
        )

    response_metadata: dict[str, Any] = {}

    if llm_response is not None:
        raw_metadata = getattr(
            llm_response,
            "metadata",
            {},
        )

        if isinstance(
            raw_metadata,
            dict,
        ):
            response_metadata = raw_metadata

    metadata = {
        **result_metadata,
        **response_metadata,
    }

    retry = metadata.get(
        "retry",
        {},
    )

    if not isinstance(
        retry,
        dict,
    ):
        retry = {}

    return {
        "provider": metadata.get(
            "provider",
            "",
        ),
        "model": (
            getattr(
                llm_response,
                "model",
                "",
            )
            if llm_response is not None
            else metadata.get(
                "model",
                "",
            )
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
        "retry_enabled": bool(
            metadata.get(
                "retry_enabled",
                bool(retry),
            )
        ),
        "retry_attempts": int(
            metadata.get(
                "retry_attempts",
                retry.get(
                    "attempts_count",
                    0,
                ),
            )
            or 0
        ),
        "retry_count": int(
            metadata.get(
                "retry_count",
                retry.get(
                    "retries_count",
                    0,
                ),
            )
            or 0
        ),
        "retry_exhausted": bool(
            metadata.get(
                "retry_exhausted",
                retry.get(
                    "exhausted",
                    False,
                ),
            )
        ),
        "succeeded_after_retry": bool(
            metadata.get(
                "succeeded_after_retry",
                retry.get(
                    "succeeded_after_retry",
                    False,
                ),
            )
        ),
        "retry_total_duration": retry.get(
            "total_duration_seconds"
        ),
        "retry_attempt_history": list(
            retry.get(
                "attempts",
                [],
            )
        ),
    }

def execute_stage(
    pipeline: PipelineEngine,
    project_path: Path,
) -> FullStageExecution:
    """Ejecuta un único Stage y recopila métricas textuales o multimedia."""

    manager = ProjectManager()
    project_before = manager.load_project(project_path)
    stage = project_before.stage_actual
    media_stage = stage in MEDIA_STAGES
    before_snapshot = snapshot_directory(project_path)
    start_time = time.perf_counter()
    result = pipeline.execute(project_path)
    duration_seconds = round(time.perf_counter() - start_time, 2)
    after_snapshot = snapshot_directory(project_path)
    changes = compare_snapshots(before=before_snapshot, after=after_snapshot)

    prompt_path = get_prompt_path(project_path=project_path, stage=stage)
    response_path = get_response_path(project_path=project_path, stage=stage)
    prompt_content = "" if media_stage else read_text_safely(prompt_path)
    response_content = "" if media_stage else read_text_safely(response_path)
    stored_bytes = response_size_bytes(response_path)

    next_stage = ""
    if isinstance(result.data, dict):
        next_stage = str(result.data.get("next_stage", ""))
    if not next_stage:
        project_after = read_yaml(project_path / "proyecto.yaml")
        next_stage = str(project_after.get("stage_actual", ""))

    llm_metrics = extract_llm_metrics(result)
    validation_data: dict[str, Any] = {}
    if media_stage:
        validation_data = {
            "success": bool(result.success),
            "score": result.metadata.get("validation_score"),
            "passing_score": result.metadata.get("validation_passing_score"),
            "approved": result.metadata.get("validation_approved"),
            "warnings": list(result.warnings),
            "errors": list(result.errors),
            "metadata": dict(result.metadata),
        }
    elif response_content:
        validation_data = reevaluate_response(
            project_path=project_path,
            stage=stage,
            response_content=response_content,
            model=(llm_metrics.get("model") or TEST_MODEL),
        )

    errors = list(result.errors)
    warnings = list(result.warnings)
    if result.success and validation_data and not validation_data.get("success", False):
        errors.append(
            "La validación independiente del Stage no fue aprobada."
        )
        errors.extend(validation_data.get("errors", []))

    if result.success:
        if media_stage and stored_bytes <= 0:
            errors.append(f"El Stage multimedia '{stage}' no guardó artifacts físicos.")
        elif not media_stage and not response_content:
            errors.append(f"El Stage '{stage}' no guardó contenido en su archivo de respuesta.")

    artifact_paths: list[str] = []
    if isinstance(result.data, dict):
        raw_artifacts = result.data.get("artifact_paths", [])
        if isinstance(raw_artifacts, list):
            artifact_paths = [str(item) for item in raw_artifacts]
    if not artifact_paths:
        raw_artifacts = result.metadata.get("artifact_paths", [])
        if isinstance(raw_artifacts, list):
            artifact_paths = [str(item) for item in raw_artifacts]

    return FullStageExecution(
        stage=stage,
        next_stage=next_stage,
        success=(result.success and not errors),
        message=result.message,
        duration_seconds=duration_seconds,
        prompt_path=("" if media_stage else str(prompt_path)),
        response_path=(str(response_path) if response_path else ""),
        prompt_characters=len(prompt_content),
        response_characters=len(response_content),
        response_size_bytes=stored_bytes,
        response_kind=("binary_media" if media_stage else "text"),
        artifact_paths=artifact_paths,
        validation_score=validation_data.get("score"),
        passing_score=validation_data.get("passing_score"),
        validation_approved=validation_data.get("approved"),
        prompt_tokens=llm_metrics.get("prompt_tokens"),
        response_tokens=llm_metrics.get("response_tokens"),
        thinking_tokens=llm_metrics.get("thinking_tokens"),
        total_tokens=llm_metrics.get("total_tokens"),
        provider=str(llm_metrics.get("provider", "")),
        model=str(llm_metrics.get("model", "")),
        finish_reason=str(llm_metrics.get("finish_reason", "")),
        retry_enabled=bool(llm_metrics.get("retry_enabled", False)),
        retry_attempts=int(llm_metrics.get("retry_attempts", 0)),
        retry_count=int(llm_metrics.get("retry_count", 0)),
        retry_exhausted=bool(llm_metrics.get("retry_exhausted", False)),
        succeeded_after_retry=bool(llm_metrics.get("succeeded_after_retry", False)),
        retry_total_duration=llm_metrics.get("retry_total_duration"),
        retry_attempt_history=list(llm_metrics.get("retry_attempt_history", [])),
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

    if execution.response_kind == "binary_media":
        print(
            f"Artifacts multimedia: {execution.response_size_bytes} bytes"
        )
    else:
        print(
            f"Respuesta: {execution.response_characters} caracteres"
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
        
    if (
        execution.retry_enabled
        or execution.retry_attempts > 0
    ):

        print()
        print("Retry:")

        print(
            f"  Habilitado: "
            f"{execution.retry_enabled}"
        )

        print(
            f"  Intentos: "
            f"{execution.retry_attempts}"
        )

        print(
            f"  Reintentos: "
            f"{execution.retry_count}"
        )

        print(
            f"  Agotado: "
            f"{execution.retry_exhausted}"
        )

        print(
            "  Éxito después de reintento: "
            f"{execution.succeeded_after_retry}"
        )

        if execution.retry_total_duration is not None:

            print(
                "  Duración Retry: "
                f"{execution.retry_total_duration} s"
            )

        if execution.retry_attempt_history:

            print()

            print("  Historial:")

            for attempt in execution.retry_attempt_history:

                print(
                    f"    Intento "
                    f"{attempt.get('attempt_number')}:"
                )

                print(
                    "      éxito="
                    f"{attempt.get('success')}"
                )

                print(
                    "      código="
                    f"{attempt.get('status_code')}"
                )
                
                print(
                    "      duración="
                    f"{attempt.get('duration_seconds')} s"
                )
                
                print(
                    "      espera="
                    f"{attempt.get('delay_seconds')} s"
                )

                print(
                    "      regla="
                    f"{attempt.get('matched_rule')}"
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
        f"Tema: {project_data.get('tema') or TEST_TOPIC}"
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
    """Comprueba respuestas históricas y artifacts físicos del proyecto."""

    errors: list[str] = []
    completed = set(memory_completed_stages(project_path))
    for stage in EXPECTED_PRODUCTION_STAGES:
        if stage not in completed:
            continue
        if stage in MEDIA_STAGES:
            continue

        prompt_path = get_prompt_path(project_path=project_path, stage=stage)
        if not prompt_path.is_file() or prompt_path.stat().st_size <= 0:
            errors.append(f"No existe un prompt válido para '{stage}'.")

        response_path = get_response_path(project_path=project_path, stage=stage)
        if response_path is None or not response_path.is_file() or response_path.stat().st_size <= 0:
            errors.append(f"No existe una respuesta válida para '{stage}'.")

    try:
        project = ProjectManager().load_project(project_path)
        quality = ProductionMediaRouter().validate_quality_gate(project)
    except Exception as error:
        errors.append(f"No fue posible validar artifacts multimedia: {error}")
    else:
        errors.extend(quality.errors)
    return errors


def validate_final_state(
    project_path: Path,
    executions: list[FullStageExecution],
) -> tuple[bool, list[str]]:
    """Valida el proyecto completo, incluyendo Stages preservados de intentos previos."""

    errors: list[str] = []
    project_data = read_yaml(project_path / "proyecto.yaml")
    memory_data = read_yaml(project_path / "memoria.yaml")
    completed_stages = set(memory_completed_stages(project_path))

    for expected_stage in EXPECTED_PRODUCTION_STAGES:
        if expected_stage not in completed_stages:
            errors.append(f"No existe evidencia en memoria del Stage requerido: {expected_stage}.")

    for execution in executions:
        if not execution.success:
            errors.append(f"El Stage '{execution.stage}' falló.")
        if execution.response_kind == "binary_media":
            if execution.response_size_bytes <= 0:
                errors.append(f"El Stage multimedia '{execution.stage}' no guardó artifacts.")
        elif execution.response_characters <= 0:
            errors.append(f"El Stage '{execution.stage}' no guardó respuesta.")
        if execution.validation_approved is not True:
            errors.append(f"El Stage '{execution.stage}' no fue aprobado por su validador.")
        if (
            execution.validation_score is not None
            and execution.passing_score is not None
            and execution.validation_score < execution.passing_score
        ):
            errors.append(f"El Stage '{execution.stage}' obtuvo una puntuación insuficiente.")

    actual_stage = project_data.get("stage_actual")
    if actual_stage != FINAL_STAGE:
        errors.append(f"El proyecto no terminó en Stage final. Stage actual: {actual_stage}.")

    expected_last_stage = EXPECTED_PRODUCTION_STAGES[-1] if EXPECTED_PRODUCTION_STAGES else ""
    actual_last_validated = memory_data.get("ultimo_stage_validado")
    if actual_last_validated != expected_last_stage:
        errors.append(
            "El último Stage validado no coincide. "
            f"Esperado: {expected_last_stage}. Actual: {actual_last_validated}."
        )
    if memory_data.get("siguiente_stage") != FINAL_STAGE:
        errors.append(
            "La memoria no apunta a final. "
            f"Actual: {memory_data.get('siguiente_stage')}."
        )

    history = memory_data.get("historial", [])
    if not isinstance(history, list):
        errors.append("El historial de memoria no es una lista.")

    errors.extend(validate_expected_files(project_path=project_path, executions=executions))
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


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ejecuta o reanuda el Full Pipeline Smoke real de CIPS."
    )
    parser.add_argument(
        "--project-path",
        type=Path,
        default=None,
        help=(
            "Proyecto existente a reanudar. Si está marcado final pero el media "
            "preflight falla, se reabre desde el primer Stage multimedia inválido."
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Ejecuta un proyecto nuevo o reanuda el proyecto indicado."""

    args = parse_args(argv)
    print("CIPS Full Pipeline Smoke Test")
    print("=" * 70)
    print("Esta prueba realizará solicitudes reales a Google Gemini solo cuando un Stage LLM no tenga respuesta válida preservada.")
    print("Los Stages voz, imágenes y ensamblado usan backends multimedia locales.")
    print("Stages de producción: " + " → ".join(EXPECTED_PRODUCTION_STAGES))
    print(f"Estado final esperado: {FINAL_STAGE}")
    print(f"Modelo: {TEST_MODEL}")
    print(f"Thinking level: {TEST_THINKING_LEVEL}")
    print(f"Máximo de salida por Stage: {TEST_MAX_OUTPUT_TOKENS} tokens")
    print()

    if args.project_path is None:
        if not credentials_available():
            print("ERROR: No se encontró GOOGLE_API_KEY ni GEMINI_API_KEY.")
            return 1
        try:
            project_path = create_test_project()
        except Exception as error:
            print(f"No fue posible crear el proyecto temporal: {error}")
            return 1
        print(f"Proyecto temporal: {project_path.name}")
    else:
        project_path = args.project_path.expanduser().resolve()
        if not project_path.is_dir() or not (project_path / "proyecto.yaml").is_file():
            print(f"ERROR: Proyecto no válido para reanudar: {project_path}")
            return 1
        try:
            repair_stage = prepare_project_for_resume(project_path)
        except Exception as error:
            print(f"ERROR: No fue posible evaluar la reanudación del proyecto: {error}")
            return 1
        if repair_stage:
            print(
                "Se detectó evidencia inválida en un Stage ya superado; "
                f"se preservó el proyecto y se reanudará desde: {repair_stage}."
            )
        else:
            print(f"Reanudando proyecto existente: {project_path.name}")
        current_stage = ProjectManager().load_project(project_path).stage_actual
        if current_stage != FINAL_STAGE and not credentials_available():
            print("ERROR: No se encontró GOOGLE_API_KEY ni GEMINI_API_KEY para los Stages LLM pendientes.")
            return 1

    project_info = ProjectManager().load_project(project_path)
    print(f"Ruta: {project_path}")
    print(f"Tema: {project_info.tema or TEST_TOPIC}")
    print(f"Stage de inicio/reanudación: {project_info.stage_actual}")

    pipeline = build_controlled_pipeline()
    executions: list[FullStageExecution] = []

    for _ in range(MAX_EXECUTIONS):
        project = ProjectManager().load_project(project_path)
        if project.stage_actual == FINAL_STAGE:
            print()
            print("El proyecto alcanzó el Stage final.")
            break
        stage_index = (
            EXPECTED_PRODUCTION_STAGES.index(project.stage_actual) + 1
            if project.stage_actual in EXPECTED_PRODUCTION_STAGES
            else len(executions) + 1
        )
        print()
        print(f"Ejecutando Stage {stage_index}: {project.stage_actual}")
        execution = execute_stage(pipeline=pipeline, project_path=project_path)
        executions.append(execution)
        print_stage_result(index=stage_index, execution=execution)
        if not execution.success:
            print()
            print("Pipeline detenido. El proyecto se conserva y puede reanudarse desde este mismo Stage.")
            break

    print_final_summary(project_path=project_path, executions=executions)
    final_valid, final_errors = validate_final_state(
        project_path=project_path, executions=executions
    )
    final_guard_valid = False
    final_guard_message = "No ejecutado porque el proyecto no alcanzó final."
    if final_valid:
        final_guard_valid, final_guard_message = verify_final_guard(
            pipeline=pipeline, project_path=project_path
        )
        if not final_guard_valid:
            final_errors.append(final_guard_message)
            final_valid = False

    print()
    print("=" * 70)
    print("VALIDACIÓN FINAL")
    print("=" * 70)
    print(f"Resultado integral válido: {final_valid}")
    print(f"Protección de proyecto finalizado: {final_guard_valid}")
    print(f"Mensaje de protección: {final_guard_message}")
    if final_errors:
        print()
        print("Errores finales:")
        for error in final_errors:
            print(f"- {error}")
    if not final_valid:
        return 2
    print()
    print("Full Pipeline Smoke Test completado correctamente.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
    