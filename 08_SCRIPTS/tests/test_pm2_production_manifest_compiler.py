from __future__ import annotations

import json
from pathlib import Path
import shutil
import sys

import pytest


SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from production_manifest import AssetType, deserialize_manifest, serialize_manifest  # noqa: E402
from production_manifest_compiler import (  # noqa: E402
    MissingEditorialArtifactError,
    ProductionManifestCompiler,
)
from workspace_resolver import WorkspaceResolver  # noqa: E402


FIXTURE_PROJECT = Path(__file__).parent / "fixtures" / "pm2" / "editorial_project"


@pytest.fixture()
def project_env(tmp_path: Path) -> tuple[Path, ProductionManifestCompiler]:
    projects_root = tmp_path / "04_PROYECTOS"
    outputs_root = tmp_path / "05_OUTPUTS"
    projects_root.mkdir()
    outputs_root.mkdir()
    project_path = projects_root / "PROYECTO_PM2_0001"
    shutil.copytree(FIXTURE_PROJECT, project_path)
    resolver = WorkspaceResolver(
        projects_root=projects_root,
        outputs_root=outputs_root,
    )
    return project_path, ProductionManifestCompiler(workspace_resolver=resolver)


def test_representative_editorial_project_compiles_to_valid_manifest(project_env) -> None:
    project_path, compiler = project_env

    manifest = compiler.compile(project_path)

    assert manifest.project.project_id == "PROYECTO_PM2_0001"
    assert manifest.project.production_id == "SHORT_PM2_0001"
    assert manifest.output.platform.value == "youtube_shorts"
    assert manifest.output.duration_seconds == 36.0
    assert manifest.locale == "es-MX"
    assert len(manifest.scenes) == 3
    assert manifest.scenes[0].start_seconds == 0.0
    assert manifest.scenes[-1].end_seconds == 36.0
    assert all(scene.asset_request.asset_type is AssetType.NONE for scene in manifest.scenes)
    assert "afirmación llamativa" in manifest.scenes[0].visual_direction.intent.casefold()
    assert manifest.publication.hashtags == (
        "VerificaAntes",
        "FuentesConfiables",
        "CIPS",
    )
    assert manifest.publication.keywords == (
        "verificación de información",
        "fuentes confiables",
        "desinformación",
    )


def test_compilation_is_deterministic_and_round_trips(project_env) -> None:
    project_path, compiler = project_env

    first = compiler.compile(project_path)
    second = compiler.compile(project_path)
    payload = serialize_manifest(first)

    assert first == second
    assert first.manifest_id == second.manifest_id
    assert [scene.scene_id for scene in first.scenes] == [
        scene.scene_id for scene in second.scenes
    ]
    assert deserialize_manifest(payload) == first
    assert serialize_manifest(second) == payload


def test_all_editorial_sources_are_hash_traced_and_linked_to_scenes(project_env) -> None:
    project_path, compiler = project_env

    manifest = compiler.compile(project_path)

    assert [source.source_id for source in manifest.source_references] == [
        "source-investigacion",
        "source-verificacion",
        "source-guion",
        "source-storyboard",
        "source-narracion",
        "source-seo",
        "source-publicacion",
    ]
    assert all(source.content_hash and len(source.content_hash) == 64 for source in manifest.source_references)
    expected_ids = tuple(source.source_id for source in manifest.source_references)
    assert all(scene.source_reference_ids == expected_ids for scene in manifest.scenes)
    assert manifest.source_references[3].uri == "storyboard/04_STORYBOARD.md"


def test_narration_maps_to_every_scene_in_original_order(project_env) -> None:
    project_path, compiler = project_env

    manifest = compiler.compile(project_path)
    mapped = " ".join(scene.narration_text or "" for scene in manifest.scenes)

    assert mapped == manifest.narration.full_text
    assert manifest.narration.estimated_duration_seconds <= manifest.output.duration_seconds
    assert [scene.sequence for scene in manifest.scenes] == [1, 2, 3]
    assert all(scene.duration_seconds > 0.0 for scene in manifest.scenes)


def test_existing_markdown_table_storyboard_format_is_supported(project_env) -> None:
    project_path, compiler = project_env
    (project_path / "storyboard" / "04_STORYBOARD.md").write_text(
        "# STORYBOARD & VISUAL PROMPTS\n\n"
        "| Segundo | Escena | Prompt Imagen/Video |\n"
        "|---|---|---|\n"
        "| 00:00 - 00:03 | Una alerta detiene el envío | prompt no compilado |\n"
        "| 00:03 - 00:15 | Se inspecciona la fuente original | prompt no compilado |\n"
        "| 00:15 - 00:36 | Un sello separa hecho e hipótesis | prompt no compilado |\n",
        encoding="utf-8",
    )

    manifest = compiler.compile(project_path)

    assert len(manifest.scenes) == 3
    assert manifest.scenes[0].visual_direction.intent == "Una alerta detiene el envío"
    assert manifest.scenes[0].metadata["editorial_timing_label"] == "00:00 - 00:03"
    assert all(scene.asset_request.asset_type is AssetType.NONE for scene in manifest.scenes)


def test_persistence_writes_canonical_manifest_and_f3_sidecar(project_env) -> None:
    project_path, compiler = project_env

    result = compiler.compile_and_persist(project_path)

    assert result.manifest_path == project_path / "production_manifest.json"
    assert result.manifest_path.read_text(encoding="utf-8") == serialize_manifest(result.manifest)
    assert deserialize_manifest(result.manifest_path.read_bytes()) == result.manifest
    assert result.artifact_write.artifact.artifact_type == "production_manifest"
    assert result.artifact_write.artifact.mime_type == "application/json"
    assert result.artifact_write.event_created is True
    assert result.artifact_write.sidecar_path.is_file()
    sidecar = json.loads(result.artifact_write.sidecar_path.read_text(encoding="utf-8"))
    assert sidecar["content_hash"] == result.artifact_write.artifact.content_hash
    assert sidecar["events"][0]["metadata"]["manifest_id"] == result.manifest.manifest_id


def test_repeated_persistence_is_idempotent_and_deduplicated(project_env) -> None:
    project_path, compiler = project_env

    first = compiler.compile_and_persist(project_path)
    second = compiler.compile_and_persist(project_path)
    sidecar = json.loads(first.artifact_write.sidecar_path.read_text(encoding="utf-8"))

    assert second.manifest == first.manifest
    assert second.artifact_write.deduplicated is True
    assert second.artifact_write.event_created is False
    assert second.artifact_write.artifact.content_hash == first.artifact_write.artifact.content_hash
    assert len(sidecar["events"]) == 1


def test_missing_narration_is_rejected_before_persistence(project_env) -> None:
    project_path, compiler = project_env
    (project_path / "narration" / "narration.txt").unlink()

    with pytest.raises(MissingEditorialArtifactError, match="narracion"):
        compiler.compile_and_persist(project_path)

    assert not (project_path / "production_manifest.json").exists()


def test_compiler_contains_no_external_or_renderer_integration() -> None:
    source = (SCRIPTS_DIR / "production_manifest_compiler.py").read_text(encoding="utf-8").casefold()

    forbidden = (
        "creatomate",
        "renderscript",
        "render_target_adapter",
        "requests.",
        "httpx.",
        "urllib.request",
        "subprocess.",
    )
    assert all(token not in source for token in forbidden)
