from __future__ import annotations

import json
from pathlib import Path
import shutil
import sys

import pytest


SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from creative_direction_planner import (  # noqa: E402
    CreativeDirectionPlanner,
    CreativeDirectionPlanningError,
)
from production_manifest import (  # noqa: E402
    AssetType,
    CameraMovement,
    ProductionManifest,
    deserialize_manifest,
    serialize_manifest,
)
from production_manifest_compiler import ProductionManifestCompiler  # noqa: E402
from workspace_resolver import WorkspaceResolver  # noqa: E402


FIXTURE_PROJECT = Path(__file__).parent / "fixtures" / "pm2" / "editorial_project"
PM1_MANIFEST = Path(__file__).parent / "fixtures" / "pm1" / "production_manifest.json"


@pytest.fixture()
def planning_env(
    tmp_path: Path,
) -> tuple[Path, ProductionManifestCompiler, CreativeDirectionPlanner]:
    projects_root = tmp_path / "04_PROYECTOS"
    outputs_root = tmp_path / "05_OUTPUTS"
    projects_root.mkdir()
    outputs_root.mkdir()
    project_path = projects_root / "PROYECTO_PM3_0001"
    shutil.copytree(FIXTURE_PROJECT, project_path)
    resolver = WorkspaceResolver(
        projects_root=projects_root,
        outputs_root=outputs_root,
    )
    return (
        project_path,
        ProductionManifestCompiler(workspace_resolver=resolver),
        CreativeDirectionPlanner(workspace_resolver=resolver),
    )


def _compile_and_plan(planning_env) -> tuple[ProductionManifest, ProductionManifest]:
    project_path, compiler, planner = planning_env
    source = compiler.compile(project_path)
    return source, planner.plan(source)


def test_pm2_manifest_becomes_a_dynamic_provider_neutral_shot_plan(planning_env) -> None:
    _, planned = _compile_and_plan(planning_env)

    assert [scene.asset_request.asset_type for scene in planned.scenes] == [
        AssetType.TEXT_GRAPHIC,
        AssetType.STOCK_VIDEO,
        AssetType.MOTION_GRAPHIC,
    ]
    assert planned.scenes[0].asset_request.creative_brief
    assert planned.scenes[1].asset_request.stock_query
    assert planned.scenes[2].asset_request.creative_brief
    assert all(scene.motion.camera_movement is not CameraMovement.STATIC for scene in planned.scenes)
    assert all(scene.on_screen_text for scene in planned.scenes)
    assert all(scene.captions and scene.captions.emphasis_words for scene in planned.scenes)
    assert [scene.metadata["music_energy"] for scene in planned.scenes] == [
        0.72,
        0.58,
        0.68,
    ]
    assert all(scene.metadata["music_mood"] for scene in planned.scenes)
    assert planned.scenes[0].transition_out == planned.scenes[1].transition_in
    assert planned.scenes[1].transition_out == planned.scenes[2].transition_in
    assert planned.audio_design.music is not None
    assert planned.audio_design.music.mood == "analítico, moderno y confiable"
    assert planned.audio_design.music.energy == 0.62
    assert len(planned.audio_design.sound_effects) == len(planned.scenes)


def test_identity_timeline_narration_and_editorial_traceability_are_preserved(
    planning_env,
) -> None:
    source, planned = _compile_and_plan(planning_env)

    assert planned.manifest_id == source.manifest_id
    assert planned.project == source.project
    assert planned.output == source.output
    assert planned.narration == source.narration
    assert planned.publication == source.publication
    assert planned.quality_requirements == source.quality_requirements
    assert planned.source_references == source.source_references
    for original, enriched in zip(source.scenes, planned.scenes):
        assert enriched.scene_id == original.scene_id
        assert enriched.sequence == original.sequence
        assert enriched.start_seconds == original.start_seconds
        assert enriched.duration_seconds == original.duration_seconds
        assert enriched.narration_text == original.narration_text
        assert enriched.source_reference_ids == original.source_reference_ids
    assert planned.metadata["creative_source_manifest_sha256"]
    assert planned.metadata["creative_planner"] == "cips.creative_direction_planner"


def test_planning_is_deterministic_idempotent_and_round_trips(planning_env) -> None:
    project_path, compiler, planner = planning_env
    source = compiler.compile(project_path)

    first = planner.plan(source)
    second = planner.plan(source)
    replanned = planner.plan(first)
    payload = serialize_manifest(first)

    assert first == second == replanned
    assert serialize_manifest(second) == payload
    assert deserialize_manifest(payload) == first


@pytest.mark.parametrize(
    ("asset_type", "required_field"),
    [
        (AssetType.AI_VIDEO, "video_prompt"),
        (AssetType.AI_IMAGE, "image_prompt"),
        (AssetType.STOCK_VIDEO, "stock_query"),
        (AssetType.STOCK_IMAGE, "stock_query"),
        (AssetType.MOTION_GRAPHIC, "creative_brief"),
        (AssetType.TEXT_GRAPHIC, "creative_brief"),
        (AssetType.EXISTING_ASSET, "existing_asset_id"),
        (AssetType.NONE, None),
    ],
)
def test_every_universal_asset_type_can_be_planned_explicitly(
    planning_env,
    asset_type: AssetType,
    required_field: str | None,
) -> None:
    project_path, compiler, planner = planning_env
    source = compiler.compile(project_path)
    scene_id = source.scenes[0].scene_id
    existing_ids = (
        {scene_id: "artifact-editorial-existing-v1"}
        if asset_type is AssetType.EXISTING_ASSET
        else None
    )

    planned = planner.plan(
        source,
        asset_types={scene_id: asset_type},
        existing_asset_ids=existing_ids,
    )
    request = planned.scenes[0].asset_request

    assert request.asset_type is asset_type
    if required_field is not None:
        assert getattr(request, required_field)
    else:
        assert request.creative_brief is None
        assert request.image_prompt is None
        assert request.video_prompt is None
        assert request.stock_query is None
        assert request.existing_asset_id is None


def test_existing_asset_requires_a_neutral_artifact_reference(planning_env) -> None:
    project_path, compiler, planner = planning_env
    source = compiler.compile(project_path)
    scene_id = source.scenes[0].scene_id

    with pytest.raises(CreativeDirectionPlanningError, match="existing_asset_id"):
        planner.plan(source, asset_types={scene_id: AssetType.EXISTING_ASSET})


def test_unknown_scene_overrides_are_rejected(planning_env) -> None:
    project_path, compiler, planner = planning_env
    source = compiler.compile(project_path)

    with pytest.raises(CreativeDirectionPlanningError, match="desconocidos"):
        planner.plan(source, asset_types={"scene-missing": AssetType.AI_IMAGE})

    with pytest.raises(CreativeDirectionPlanningError, match="solo acepta"):
        planner.plan(
            source,
            existing_asset_ids={source.scenes[0].scene_id: "artifact-unused"},
        )


def test_existing_explicit_creative_plan_is_not_destroyed(planning_env) -> None:
    _, _, planner = planning_env
    existing = deserialize_manifest(PM1_MANIFEST.read_bytes())

    planned = planner.plan(existing)

    for original, enriched in zip(existing.scenes, planned.scenes):
        assert enriched.asset_request == original.asset_request
        assert enriched.visual_direction == original.visual_direction
        assert enriched.motion == original.motion
        assert enriched.on_screen_text == original.on_screen_text
        assert enriched.captions == original.captions
        assert enriched.transition_in == original.transition_in
        assert enriched.transition_out == original.transition_out
    assert planned.audio_design == existing.audio_design
    assert planned.manifest_id == existing.manifest_id
    assert planned.source_references == existing.source_references


def test_enriched_manifest_replaces_pm2_canonical_file_and_is_idempotent_in_f3(
    planning_env,
) -> None:
    project_path, compiler, planner = planning_env
    compiled = compiler.compile_and_persist(project_path)
    source_hash = compiled.artifact_write.artifact.content_hash

    first = planner.plan_and_persist(compiled.manifest, workspace_root=project_path)
    second = planner.plan_and_persist(compiled.manifest, workspace_root=project_path)
    sidecar = json.loads(first.artifact_write.sidecar_path.read_text(encoding="utf-8"))

    assert first.manifest_path == project_path / "production_manifest.json"
    assert deserialize_manifest(first.manifest_path.read_bytes()) == first.manifest
    assert first.artifact_write.artifact.content_hash != source_hash
    assert first.artifact_write.artifact.artifact_type == "production_manifest"
    assert sidecar["content_hash"] == first.artifact_write.artifact.content_hash
    assert sidecar["events"][0]["metadata"]["planner"] == (
        "cips.creative_direction_planner"
    )
    assert sidecar["events"][0]["metadata"]["source_manifest_sha256"] == source_hash
    assert second.manifest == first.manifest
    assert second.artifact_write.deduplicated is True
    assert second.artifact_write.event_created is False


def test_planner_rejects_wrong_manifest_type(planning_env) -> None:
    _, _, planner = planning_env

    with pytest.raises(TypeError, match="ProductionManifest"):
        planner.plan({})  # type: ignore[arg-type]


def test_planner_contains_no_external_asset_or_render_integration() -> None:
    source = (SCRIPTS_DIR / "creative_direction_planner.py").read_text(
        encoding="utf-8"
    ).casefold()
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
