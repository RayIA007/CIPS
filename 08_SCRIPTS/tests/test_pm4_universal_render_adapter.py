from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from creative_direction_planner import CreativeDirectionPlanner  # noqa: E402
from production_manifest import (  # noqa: E402
    AssetType,
    ProductionManifest,
    TransitionKind,
)
from production_manifest_compiler import ProductionManifestCompiler  # noqa: E402
from render_adapter import (  # noqa: E402
    FakeRenderTargetAdapter,
    RenderCapabilityError,
    RenderJob,
    RenderPlan,
    RenderResult,
    RenderStatus,
    RenderTargetAdapter,
    RenderTargetCapabilities,
    deserialize_render_plan,
    render_plan_json_schema,
    serialize_render_plan,
)
from workspace_resolver import WorkspaceResolver  # noqa: E402

FIXTURE_PROJECT = Path(__file__).parent / "fixtures" / "pm2" / "editorial_project"


@pytest.fixture()
def planned_manifest(tmp_path: Path) -> ProductionManifest:
    projects_root = tmp_path / "04_PROYECTOS"
    outputs_root = tmp_path / "05_OUTPUTS"
    projects_root.mkdir()
    outputs_root.mkdir()
    project_path = projects_root / "PROYECTO_PM4_0001"
    shutil.copytree(FIXTURE_PROJECT, project_path)
    resolver = WorkspaceResolver(
        projects_root=projects_root,
        outputs_root=outputs_root,
    )
    source = ProductionManifestCompiler(workspace_resolver=resolver).compile(
        project_path
    )
    return CreativeDirectionPlanner(workspace_resolver=resolver).plan(source)


def _compile(planned_manifest: ProductionManifest) -> RenderPlan:
    return FakeRenderTargetAdapter().compile(planned_manifest)


def _capabilities(**overrides) -> RenderTargetCapabilities:
    values = {
        "supported_asset_types": tuple(
            item for item in AssetType if item is not AssetType.NONE
        ),
        "supported_transition_kinds": tuple(TransitionKind),
        "supports_narration": True,
        "supports_motion": True,
        "supports_on_screen_text": True,
        "supports_captions": True,
        "supports_music": True,
        "supports_sound_effects": True,
    }
    values.update(overrides)
    return RenderTargetCapabilities(**values)


def test_fake_adapter_compiles_pm3_manifest_to_inspectable_render_plan(
    planned_manifest: ProductionManifest,
) -> None:
    plan = _compile(planned_manifest)

    assert plan.schema_name == "cips.render_plan"
    assert plan.schema_version.value == "1.0"
    assert plan.target_id == "fake.universal"
    assert plan.adapter_name == "FakeRenderTargetAdapter"
    assert plan.manifest_id == planned_manifest.manifest_id
    assert plan.target_payload["schema_name"] == "cips.fake_render_payload"
    assert [item["scene_id"] for item in plan.target_payload["timeline"]] == [
        scene.scene_id for scene in planned_manifest.scenes
    ]
    assert [scene.asset_request.asset_type for scene in plan.scenes] == [
        AssetType.TEXT_GRAPHIC,
        AssetType.STOCK_VIDEO,
        AssetType.MOTION_GRAPHIC,
    ]


def test_compilation_is_deterministic_serializable_and_round_trips(
    planned_manifest: ProductionManifest,
) -> None:
    adapter = FakeRenderTargetAdapter()
    first = adapter.compile(planned_manifest)
    second = adapter.compile(planned_manifest)
    payload = serialize_render_plan(first)

    assert first == second
    assert first.plan_id == second.plan_id
    assert serialize_render_plan(second) == payload
    assert deserialize_render_plan(payload) == first
    assert payload.endswith("\n")


def test_plan_preserves_identity_timeline_assets_and_traceability(
    planned_manifest: ProductionManifest,
) -> None:
    plan = _compile(planned_manifest)

    assert plan.project_id == planned_manifest.project.project_id
    assert plan.production_id == planned_manifest.project.production_id
    assert plan.output == planned_manifest.output
    assert plan.source_references == planned_manifest.source_references
    assert plan.audio_design == planned_manifest.audio_design
    assert plan.publication == planned_manifest.publication
    assert plan.quality_requirements == planned_manifest.quality_requirements
    for planned, source in zip(plan.scenes, planned_manifest.scenes):
        assert planned.scene_id == source.scene_id
        assert planned.sequence == source.sequence
        assert planned.start_seconds == source.start_seconds
        assert planned.duration_seconds == source.duration_seconds
        assert planned.asset_request == source.asset_request
        assert planned.source_reference_ids == source.source_reference_ids


def test_required_capabilities_are_stable_and_inspectable(
    planned_manifest: ProductionManifest,
) -> None:
    plan = _compile(planned_manifest)

    assert plan.required_capabilities == tuple(sorted(plan.required_capabilities))
    assert {
        "asset_type:text_graphic",
        "asset_type:stock_video",
        "asset_type:motion_graphic",
        "feature:captions",
        "feature:motion",
        "feature:music",
        "feature:narration",
        "feature:on_screen_text",
        "feature:sound_effects",
        "transition:cut",
        "transition:fade",
        "transition:slide",
        "transition:zoom",
    }.issubset(set(plan.required_capabilities))


def test_unsupported_asset_types_are_reported_explicitly(
    planned_manifest: ProductionManifest,
) -> None:
    capabilities = _capabilities(
        supported_asset_types=(AssetType.TEXT_GRAPHIC,),
    )

    with pytest.raises(RenderCapabilityError) as captured:
        FakeRenderTargetAdapter(capabilities=capabilities).compile(planned_manifest)

    assert captured.value.unsupported == (
        "asset_type:motion_graphic",
        "asset_type:stock_video",
    )
    assert "fake.universal" in str(captured.value)


def test_unsupported_features_and_transitions_are_reported_together(
    planned_manifest: ProductionManifest,
) -> None:
    capabilities = _capabilities(
        supported_transition_kinds=(TransitionKind.CUT,),
        supports_motion=False,
        supports_captions=False,
        supports_music=False,
    )

    with pytest.raises(RenderCapabilityError) as captured:
        FakeRenderTargetAdapter(capabilities=capabilities).compile(planned_manifest)

    assert {
        "feature:captions",
        "feature:motion",
        "feature:music",
        "transition:fade",
        "transition:slide",
        "transition:zoom",
    }.issubset(set(captured.value.unsupported))


def test_output_limits_are_validated_before_payload_compilation(
    planned_manifest: ProductionManifest,
) -> None:
    capabilities = _capabilities(
        max_width_px=720,
        max_height_px=1280,
        max_fps=24.0,
        max_duration_seconds=30.0,
    )

    with pytest.raises(RenderCapabilityError) as captured:
        FakeRenderTargetAdapter(capabilities=capabilities).compile(planned_manifest)

    assert captured.value.unsupported == (
        "output:duration_seconds=36.0>30.0",
        "output:fps=30.0>24.0",
        "output:height_px=1920>1280",
        "output:width_px=1080>720",
    )


def test_fake_adapter_can_represent_an_arbitrary_target_identity(
    planned_manifest: ProductionManifest,
) -> None:
    first = FakeRenderTargetAdapter(target_id="renderer.alpha").compile(
        planned_manifest
    )
    second = FakeRenderTargetAdapter(target_id="renderer.beta").compile(
        planned_manifest
    )

    assert first.target_id == "renderer.alpha"
    assert second.target_id == "renderer.beta"
    assert first.plan_id != second.plan_id
    assert first.manifest_id == second.manifest_id


def test_submission_contract_is_deterministic_and_offline(
    planned_manifest: ProductionManifest,
) -> None:
    adapter = FakeRenderTargetAdapter()
    plan = adapter.compile(planned_manifest)

    first = adapter.prepare_submission(plan)
    second = adapter.prepare_submission(plan)

    assert first == second
    assert first.plan_id == plan.plan_id
    assert first.manifest_id == plan.manifest_id
    assert first.payload == plan.target_payload
    assert len(first.idempotency_key) == 64


def test_render_lifecycle_contracts_reject_inconsistent_states() -> None:
    with pytest.raises(ValidationError, match="external_job_id"):
        RenderJob(
            job_id="job-1",
            submission_id="submission-1",
            target_id="target-1",
            status=RenderStatus.RUNNING,
        )

    with pytest.raises(ValidationError, match="estado terminal"):
        RenderResult(
            job_id="job-1",
            plan_id="plan-1",
            manifest_id="manifest-1",
            target_id="target-1",
            status=RenderStatus.RUNNING,
        )

    with pytest.raises(ValidationError, match="output_artifact_ids"):
        RenderResult(
            job_id="job-1",
            plan_id="plan-1",
            manifest_id="manifest-1",
            target_id="target-1",
            status=RenderStatus.SUCCEEDED,
        )


def test_render_plan_schema_is_versioned_strict_and_target_neutral() -> None:
    schema = render_plan_json_schema()

    assert schema["title"] == "RenderPlan"
    assert schema["additionalProperties"] is False
    assert schema["properties"]["schema_name"]["const"] == "cips.render_plan"
    for model_name in (
        "RenderPlan",
        "RenderScenePlan",
        "RenderTargetCapabilities",
    ):
        model_schema = (
            schema if model_name == "RenderPlan" else schema["$defs"][model_name]
        )
        assert model_schema["additionalProperties"] is False


def test_render_target_adapter_is_an_abstract_contract() -> None:
    class IncompleteAdapter(RenderTargetAdapter):
        adapter_name = "IncompleteAdapter"
        target_id = "incomplete.target"

    with pytest.raises(TypeError):
        IncompleteAdapter(capabilities=_capabilities())


def test_adapter_rejects_wrong_manifest_and_plan_types(
    planned_manifest: ProductionManifest,
) -> None:
    adapter = FakeRenderTargetAdapter()

    with pytest.raises(TypeError, match="ProductionManifest"):
        adapter.compile({})  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="RenderPlan"):
        adapter.prepare_submission({})  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="ProductionManifest"):
        adapter.required_capabilities({})  # type: ignore[arg-type]


def test_capabilities_are_normalized_and_reject_duplicates() -> None:
    capabilities = RenderTargetCapabilities(
        supported_asset_types=(AssetType.STOCK_VIDEO, AssetType.AI_IMAGE),
        supported_transition_kinds=(TransitionKind.ZOOM, TransitionKind.CUT),
    )

    assert capabilities.supported_asset_types == (
        AssetType.AI_IMAGE,
        AssetType.STOCK_VIDEO,
    )
    assert capabilities.supported_transition_kinds == (
        TransitionKind.CUT,
        TransitionKind.ZOOM,
    )
    with pytest.raises(ValidationError, match="duplicados"):
        RenderTargetCapabilities(
            supported_asset_types=(AssetType.AI_IMAGE, AssetType.AI_IMAGE),
        )


def test_pm4_boundary_contains_no_external_execution_or_specific_target_contract() -> (
    None
):
    package_root = SCRIPTS_DIR / "render_adapter"
    combined = "\n".join(
        path.read_text(encoding="utf-8") for path in sorted(package_root.glob("*.py"))
    ).casefold()
    forbidden = (
        "creatomate",
        "renderscript",
        "template_id",
        "requests.",
        "httpx.",
        "urllib.request",
        "subprocess.",
    )

    assert all(token not in combined for token in forbidden)
