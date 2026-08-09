"""
=========================================================
Proyecto : CIPS
Archivo  : test_f3_smoke.py
Estado   : SMOKE TEST F3.5
=========================================================

Prueba de humo no destructiva para validar el cierre de F3:

    WorkspaceResolver
            ↓
      ArtifactStore
            ↓
    Store especializado
            ↓
        artifact
            +
    artifact.meta.json

También valida deduplicación, evento temporal, idempotencia,
seguridad de paths, integración mínima con MasterProducer y,
cuando el repositorio completo está disponible, compatibilidad F2
mediante el smoke test oficial existente.

EJECUCIÓN SEGURA:
- NO consume tokens de LLM.
- NO usa Internet.
- NO modifica proyectos reales.
- Usa exclusivamente TemporaryDirectory para artifacts F3.

Uso:
    python C:\\ConsejoIA_V5\\08_SCRIPTS\\test_f3_smoke.py
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path


SCRIPTS_DIR = Path(__file__).parent.resolve()
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


from artifact_store import ArtifactStore
from audio_store import AudioStore
from image_store import ImageStore
from master_producer import MasterProducer
from master_producer_models import (
    ContentType,
    MasterProducerConfiguration,
    MonetizationObjective,
    PlatformType,
    ProductionBrief,
)
from metadata_store import MetadataStore
from text_store import TextStore
from video_store import VideoStore
from workspace_models import WorkspaceIdentity
from workspace_resolver import WorkspaceResolver, WorkspaceSecurityError


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _make_brief(project_id: str = "project-f35-smoke") -> ProductionBrief:
    return ProductionBrief(
        topic="Cierre F3.5",
        objective="Validar ArtifactStore + Workspace sin LLM",
        audience="equipo técnico",
        platform=PlatformType.YOUTUBE_SHORTS,
        content_type=ContentType.SHORT_VIDEO,
        project_name="CIPS F3.5 Smoke",
        project_id=project_id,
        monetization_objective=MonetizationObjective.NONE,
        requires_sources=False,
    )


def _make_configuration(root: Path) -> MasterProducerConfiguration:
    return MasterProducerConfiguration(
        persist_outputs=True,
        output_root=str(root / "legacy_output"),
        create_project_directory=True,
        overwrite_existing=False,
    )


def _run_f2_compatibility_smoke() -> str:
    """
    Ejecuta el smoke F2.3 oficial sin ejecutar PipelineEngine real.

    En un fixture parcial usado por desarrollo puede faltar cips_core;
    en el repositorio CIPS completo la comprobación es obligatoria.
    """

    smoke_path = SCRIPTS_DIR / "test_f2_smoke.py"
    core_package = SCRIPTS_DIR / "cips_core"
    if not smoke_path.is_file() or not core_package.is_dir():
        return "SKIPPED_PARTIAL_FIXTURE"

    completed = subprocess.run(
        [sys.executable, str(smoke_path)],
        cwd=str(SCRIPTS_DIR.parent),
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    if completed.returncode != 0:
        details = "\n".join(
            part.strip()
            for part in (completed.stdout, completed.stderr)
            if part.strip()
        )
        raise AssertionError(
            "El smoke F2.3 falló durante F3.5.\n" + details
        )
    _assert(
        "SMOKE TEST PASSED" in completed.stdout,
        "El smoke F2.3 terminó sin su marcador de PASS.",
    )
    return "VALID"


def main() -> int:
    print("=" * 76)
    print("CIPS F3.5 ArtifactStore + Workspace Integration Smoke Test")
    print("=" * 76)

    # ------------------------------------------------------------------
    # 1. Arquitectura: todos los stores especializados heredan del core.
    # ------------------------------------------------------------------
    for store_type in (
        TextStore,
        ImageStore,
        AudioStore,
        VideoStore,
        MetadataStore,
    ):
        _assert(
            issubclass(store_type, ArtifactStore),
            f"{store_type.__name__} debe heredar de ArtifactStore.",
        )

    with tempfile.TemporaryDirectory(prefix="cips_f35_smoke_") as temp_dir:
        temp_root = Path(temp_dir)
        resolver = WorkspaceResolver(
            projects_root=temp_root / "04_PROYECTOS",
            outputs_root=temp_root / "05_OUTPUTS",
        )

        # --------------------------------------------------------------
        # 2. WorkspaceResolver: project/platform/execution + reapertura.
        # --------------------------------------------------------------
        identity = WorkspaceIdentity(
            project_id="project-f35-smoke",
            platform="youtube_shorts",
            execution_id="execution-f35-smoke",
        )
        first_paths = resolver.resolve(identity, create=True)
        second_paths = resolver.resolve(identity, create=True)

        _assert(
            first_paths == second_paths,
            "Reabrir la misma identidad debe resolver las mismas rutas.",
        )
        _assert(
            first_paths.project_root.is_dir(),
            "El workspace de proyecto no fue creado.",
        )
        _assert(
            first_paths.execution_root is not None
            and first_paths.execution_root.is_dir(),
            "El workspace de ejecución no fue creado.",
        )
        execution_root = first_paths.execution_root
        _assert(execution_root is not None, "execution_root no disponible.")

        # --------------------------------------------------------------
        # 3. TextStore -> ArtifactStore -> artifact + sidecar.
        # --------------------------------------------------------------
        text_store = TextStore(resolver)
        payload = "CIPS F3.5 smoke artifact\n"
        created_at_1 = "2026-08-09T16:00:00+00:00"
        created_at_2 = "2026-08-09T16:00:01+00:00"

        first_write = text_store.persist_text(
            workspace_root=execution_root,
            relative_path="smoke/artifact.md",
            content=payload,
            artifact_type="f3_smoke_text",
            metadata={"source": "F3.5 smoke"},
            created_at=created_at_1,
        )
        artifact_path = Path(first_write.artifact.path)
        sidecar_path = first_write.sidecar_path

        _assert(artifact_path.is_file(), "El artifact físico no existe.")
        _assert(sidecar_path.is_file(), "El sidecar .meta.json no existe.")
        _assert(
            sidecar_path == Path(f"{artifact_path}.meta.json"),
            "La relación artifact -> artifact.meta.json es incorrecta.",
        )
        expected_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        _assert(
            first_write.artifact.content_hash == expected_hash,
            "content_hash no corresponde al SHA-256 de los bytes persistidos.",
        )
        _assert(
            text_store.read_bytes(execution_root, "smoke/artifact.md")
            == payload.encode("utf-8"),
            "La lectura del artifact no reproduce los bytes persistidos.",
        )
        _assert(
            text_store.verify_hash(execution_root, "smoke/artifact.md", expected_hash),
            "La verificación de hash del artifact falló.",
        )

        # --------------------------------------------------------------
        # 4. Deduplicación + evento temporal + idempotencia física.
        # --------------------------------------------------------------
        second_write = text_store.persist_text(
            workspace_root=execution_root,
            relative_path="smoke/artifact.md",
            content=payload,
            artifact_type="f3_smoke_text",
            metadata={"source": "F3.5 smoke"},
            created_at=created_at_2,
        )
        _assert(
            Path(second_write.artifact.path) == artifact_path,
            "Contenido idéntico no debe crear otro archivo físico.",
        )
        _assert(
            second_write.artifact.content_hash == expected_hash,
            "La deduplicación alteró content_hash.",
        )
        _assert(
            second_write.deduplicated is True,
            "La segunda persistencia idéntica debe marcar deduplicación.",
        )

        sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
        _assert(sidecar["content_hash"] == expected_hash, "Hash de sidecar inválido.")
        _assert(len(sidecar["events"]) == 2, "El sidecar debe registrar dos eventos.")
        event_times = [event["created_at"] for event in sidecar["events"]]
        _assert(
            event_times == [created_at_1, created_at_2],
            "Los timestamps de generación no fueron preservados.",
        )
        physical_artifacts = [
            path
            for path in (execution_root / "smoke").iterdir()
            if path.is_file() and not path.name.endswith(".meta.json")
        ]
        _assert(
            physical_artifacts == [artifact_path],
            "Idempotencia rota: apareció duplicación física innecesaria.",
        )

        # --------------------------------------------------------------
        # 5. Seguridad: traversal no puede escapar del workspace.
        # --------------------------------------------------------------
        escaped_path = temp_root / "escape.md"
        try:
            text_store.persist_text(
                workspace_root=execution_root,
                relative_path="../../escape.md",
                content="escape",
                artifact_type="f3_smoke_text",
            )
        except WorkspaceSecurityError:
            pass
        else:
            raise AssertionError("Path traversal no fue bloqueado.")
        _assert(not escaped_path.exists(), "Path traversal creó un archivo externo.")

        # --------------------------------------------------------------
        # 6. Runtime mínimo: MasterProducer usa F3 sin executor/LLM.
        # --------------------------------------------------------------
        producer = MasterProducer(
            configuration=_make_configuration(temp_root),
            workspace_resolver=resolver,
        )
        brief = _make_brief()
        result = producer.execute(brief, persist=True)
        _assert(result.success is True, "MasterProducer F3 no terminó correctamente.")
        _assert(producer._last_context is not None, "MasterProducer no creó contexto.")
        runtime_root = Path(producer._last_context.output_root)
        _assert(
            runtime_root.is_relative_to(resolver.outputs_root),
            "MasterProducer escribió fuera de outputs_root.",
        )
        runtime_workspace = producer._last_context.working_data.get("f3_workspace", {})
        _assert(
            runtime_workspace.get("managed") is True,
            "MasterProducer no marcó el contexto como workspace F3 administrado.",
        )

        expected_runtime_files = {
            "README.md",
            "brief.json",
            "context.json",
            "plan.json",
            "prompt_package.json",
            "result.json",
        }
        for filename in expected_runtime_files:
            runtime_artifact = runtime_root / filename
            runtime_sidecar = Path(f"{runtime_artifact}.meta.json")
            _assert(runtime_artifact.is_file(), f"Runtime artifact ausente: {filename}")
            _assert(runtime_sidecar.is_file(), f"Runtime sidecar ausente: {filename}")

        # --------------------------------------------------------------
        # 7. Compatibilidad legacy de MasterProducer sin F3 opt-in.
        # --------------------------------------------------------------
        legacy_producer = MasterProducer(configuration=_make_configuration(temp_root))
        legacy_context = legacy_producer.create_context(_make_brief("legacy-f35"))
        _assert(
            "f3_workspace" not in legacy_context.working_data,
            "El camino legacy no debe activar F3 implícitamente.",
        )
        _assert(
            legacy_producer.workspace_resolver is None,
            "El camino legacy no debe crear WorkspaceResolver implícito.",
        )

    # ------------------------------------------------------------------
    # 8. Regresión F2/CoreOrchestrator usando el smoke oficial existente.
    # ------------------------------------------------------------------
    f2_status = _run_f2_compatibility_smoke()

    print("SMOKE TEST PASSED")
    print("Workspace resolution       : VALID")
    print("Artifact + sidecar         : VALID")
    print("SHA-256                    : VALID")
    print("Deduplication              : VALID")
    print("Generation timestamps      : VALID")
    print("Idempotency                : VALID")
    print("Path confinement           : VALID")
    print("MasterProducer F3 runtime  : VALID")
    print("MasterProducer legacy      : VALID")
    print(f"F2/CoreOrchestrator smoke  : {f2_status}")
    print("NO LLM / TEMP WORKSPACE    : VALID")
    print("=" * 76)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
