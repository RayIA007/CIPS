from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from creative_direction_planner import CreativeDirectionPlanner  # noqa: E402
from creatomate_adapter import (  # noqa: E402
    CREATOMATE_PAYLOAD_FILENAME,
    CREATOMATE_PLACEHOLDER_ORIGIN,
    CreatomateAdapter,
    creatomate_capabilities,
    deserialize_creatomate_payload,
    serialize_creatomate_payload,
    validate_creatomate_payload,
)
from production_manifest import (  # noqa: E402
    AssetRequest,
    AssetType,
    CameraMovement,
    MotionSpec,
    OutputSpec,
    ProductionManifest,
    TransitionKind,
    TransitionSpec,
)
from production_manifest_compiler import ProductionManifestCompiler  # noqa: E402
from render_adapter import (  # noqa: E402
    RenderCapabilityError,
    RenderCompilationError,
)
from workspace_resolver import WorkspaceResolver  # noqa: E402

FIXTURE_PROJECT = Path(__file__).parent / "fixtures" / "pm2" / "editorial_project"
PAYLOAD_FIXTURE = (
    Path(__file__).parent / "fixtures" / "pm5" / CREATOMATE_PAYLOAD_FILENAME
)


@pytest.fixture()
def planned_manifest(tmp_path: Path) -> ProductionManifest:
    projects_root = tmp_path / "04_PROYECTOS"
    outputs_root = tmp_path / "05_OUTPUTS"
    projects_root.mkdir()
    outputs_root.mkdir()
    project_path = projects_root / "PROYECTO_PM5_0001"
    shutil.copytree(FIXTURE_PROJECT, project_path)
    resolver = WorkspaceResolver(
        projects_root=projects_root,
        outputs_root=outputs_root,
    )
    source = ProductionManifestCompiler(workspace_resolver=resolver).compile(
        project_path
    )
    return CreativeDirectionPlanner(workspace_resolver=resolver).plan(source)


def _visual_elements(payload: dict) -> list[dict]:
    return [
        element
        for element in payload["elements"]
        if element["name"].startswith("Scene:") and ":visual:" in element["name"]
    ]


def test_adapter_compiles_pm3_manifest_to_direct_vertical_renderscript(
    planned_manifest: ProductionManifest,
) -> None:
    plan = CreatomateAdapter().compile(planned_manifest)
    payload = plan.target_payload

    assert plan.target_id == "creatomate.renderscript"
    assert plan.adapter_name == "CreatomateAdapter"
    assert payload["output_format"] == "mp4"
    assert payload["render_scale"] == 1.0
    assert payload["width"] == 1080
    assert payload["height"] == 1920
    assert payload["frame_rate"] == 30
    assert payload["duration"] == 36
    visuals = _visual_elements(payload)
    assert [item["type"] for item in visuals] == ["shape", "video", "shape"]
    assert [item["time"] for item in visuals] == [0, 12.436364, 24.218182]
    assert [item["track"] for item in visuals] == [1, 1, 1]


def test_visual_assets_are_explicit_unresolved_placeholders(
    planned_manifest: ProductionManifest,
) -> None:
    payload = CreatomateAdapter().compile(planned_manifest).target_payload
    media_visuals = [
        element
        for element in _visual_elements(payload)
        if element["type"] in {"image", "video"}
    ]

    assert media_visuals
    assert all(
        element["source"].startswith(CREATOMATE_PLACEHOLDER_ORIGIN)
        for element in media_visuals
    )
    assert all("assets.invalid" in element["source"] for element in media_visuals)
    assert all("provider" not in element for element in media_visuals)


def test_text_and_captions_preserve_scene_content_and_safe_area(
    planned_manifest: ProductionManifest,
) -> None:
    payload = CreatomateAdapter().compile(planned_manifest).target_payload
    text_layers = [
        element for element in payload["elements"] if ":text:" in element["name"]
    ]
    captions = [
        element for element in payload["elements"] if ":captions:" in element["name"]
    ]

    assert [item["text"] for item in text_layers] == [
        scene.on_screen_text[0].text for scene in planned_manifest.scenes
    ]
    assert [item["text"] for item in captions] == [
        scene.narration_text for scene in planned_manifest.scenes
    ]
    assert all(item["track"] == 2 for item in text_layers)
    assert all(item["track"] == 3 for item in captions)
    assert all(item["x"] == "5%" and item["width"] == "90%" for item in captions)


def test_narration_music_and_sound_effects_map_to_offline_audio_layers(
    planned_manifest: ProductionManifest,
) -> None:
    payload = CreatomateAdapter().compile(planned_manifest).target_payload
    narration = [
        item for item in payload["elements"] if item["name"].endswith(":narration")
    ]
    music = [item for item in payload["elements"] if item["name"] == "Audio:music"]
    sound_effects = [
        item for item in payload["elements"] if item["name"].startswith("Audio:sfx:")
    ]

    assert len(narration) == len(planned_manifest.scenes)
    assert len(music) == 1
    assert len(sound_effects) == len(planned_manifest.audio_design.sound_effects)
    assert {item["track"] for item in narration} == {4}
    assert music[0]["track"] == 5
    assert {item["track"] for item in sound_effects} == {6}
    assert all(
        "assets.invalid" in item["source"] for item in narration + music + sound_effects
    )


def test_scene_motion_and_transitions_use_inspectable_animations(
    planned_manifest: ProductionManifest,
) -> None:
    visuals = _visual_elements(
        CreatomateAdapter().compile(planned_manifest).target_payload
    )
    transitions = [
        [
            animation
            for animation in visual["animations"]
            if animation.get("transition") is True
        ]
        for visual in visuals
    ]

    assert [item[0]["type"] for item in transitions] == ["slide", "slide", "scale"]
    assert [item[-1]["type"] for item in transitions] == ["slide", "scale", "fade"]
    assert transitions[0][-1]["enable"] == "first-only"
    assert transitions[1][0]["enable"] == "second-only"
    assert all(
        any(
            animation.get("transition") is not True
            for animation in visual["animations"]
        )
        for visual in visuals
    )


def test_payload_is_deterministic_canonical_and_matches_golden_fixture(
    planned_manifest: ProductionManifest,
) -> None:
    adapter = CreatomateAdapter()
    first = adapter.compile(planned_manifest)
    second = adapter.compile(planned_manifest)
    serialized = serialize_creatomate_payload(first.target_payload)

    assert first == second
    assert serialized == serialize_creatomate_payload(second.target_payload)
    assert serialized == PAYLOAD_FIXTURE.read_text(encoding="utf-8")
    assert deserialize_creatomate_payload(serialized) == first.target_payload
    assert serialized.endswith("\n")


def test_pm4_submission_remains_deterministic_and_offline(
    planned_manifest: ProductionManifest,
) -> None:
    adapter = CreatomateAdapter()
    plan = adapter.compile(planned_manifest)

    first = adapter.prepare_submission(plan)
    second = adapter.prepare_submission(plan)

    assert first == second
    assert first.target_id == "creatomate.renderscript"
    assert first.payload == plan.target_payload
    assert len(first.idempotency_key) == 64


def test_capabilities_are_explicit_and_reject_unsupported_requirements(
    planned_manifest: ProductionManifest,
) -> None:
    capabilities = creatomate_capabilities()

    assert capabilities.supported_transition_kinds == (
        TransitionKind.CUT,
        TransitionKind.DISSOLVE,
        TransitionKind.FADE,
        TransitionKind.SLIDE,
        TransitionKind.ZOOM,
    )
    assert set(capabilities.supported_asset_types) == {
        item for item in AssetType if item is not AssetType.NONE
    }

    changed_scene = planned_manifest.scenes[0].model_copy(
        update={
            "transition_out": TransitionSpec(
                kind=TransitionKind.WIPE,
                duration_seconds=0.3,
            )
        }
    )
    changed = planned_manifest.model_copy(
        update={"scenes": (changed_scene, *planned_manifest.scenes[1:])}
    )
    with pytest.raises(RenderCapabilityError) as captured:
        CreatomateAdapter().compile(changed)
    assert captured.value.unsupported == ("transition:wipe",)


def test_multiple_output_formats_compile_while_none_assets_and_custom_motion_fail(
    planned_manifest: ProductionManifest,
) -> None:
    for width, height, ratio in (
        (720, 1280, "9:16"),
        (1920, 1080, "16:9"),
        (1080, 1080, "1:1"),
    ):
        output = OutputSpec(
            platform=planned_manifest.output.platform,
            width_px=width,
            height_px=height,
            aspect_ratio=ratio,
            fps=planned_manifest.output.fps,
            duration_seconds=planned_manifest.output.duration_seconds,
            safe_area=planned_manifest.output.safe_area,
        )
        changed_output = planned_manifest.model_copy(update={"output": output})
        payload = CreatomateAdapter().compile(changed_output).target_payload
        assert (payload["width"], payload["height"]) == (width, height)

    none_scene = planned_manifest.scenes[0].model_copy(
        update={"asset_request": AssetRequest(asset_type=AssetType.NONE)}
    )
    changed_none = planned_manifest.model_copy(
        update={"scenes": (none_scene, *planned_manifest.scenes[1:])}
    )
    with pytest.raises(RenderCapabilityError) as captured_none:
        CreatomateAdapter().compile(changed_none)
    assert captured_none.value.unsupported == ("asset_type:none",)

    custom_scene = planned_manifest.scenes[0].model_copy(
        update={
            "motion": MotionSpec(
                camera_movement=CameraMovement.CUSTOM,
                intensity=0.5,
                notes="Movimiento definido por dirección creativa externa.",
            )
        }
    )
    changed_motion = planned_manifest.model_copy(
        update={"scenes": (custom_scene, *planned_manifest.scenes[1:])}
    )
    with pytest.raises(RenderCapabilityError) as captured_motion:
        CreatomateAdapter().compile(changed_motion)
    assert captured_motion.value.unsupported == ("camera_movement:custom",)


def test_payload_validation_rejects_invalid_or_inconsistent_data(
    planned_manifest: ProductionManifest,
) -> None:
    payload = CreatomateAdapter().compile(planned_manifest).target_payload
    preview_scale = dict(payload)
    preview_scale["render_scale"] = 0.25
    with pytest.raises(RenderCompilationError, match="render_scale"):
        validate_creatomate_payload(preview_scale)

    invalid = dict(payload)
    invalid["elements"] = [dict(payload["elements"][0])]
    invalid["elements"][0]["duration"] = 1000

    with pytest.raises(RenderCompilationError, match="excede"):
        validate_creatomate_payload(invalid)
    with pytest.raises(TypeError, match="Mapping"):
        validate_creatomate_payload([])  # type: ignore[arg-type]
    with pytest.raises(RenderCompilationError, match="JSON"):
        deserialize_creatomate_payload("{")


def test_pm5_is_confined_offline_and_does_not_contaminate_universal_domain() -> None:
    source = (
        (SCRIPTS_DIR / "creatomate_adapter.py").read_text(encoding="utf-8").casefold()
    )
    forbidden_execution = (
        "requests.",
        "httpx.",
        "urllib.request",
        "socket.",
        "subprocess.",
        "api_key",
        "authorization",
        "bearer ",
    )
    universal_source = "\n".join(
        path.read_text(encoding="utf-8").casefold()
        for path in sorted((SCRIPTS_DIR / "production_manifest").glob("*.py"))
    )

    assert all(token not in source for token in forbidden_execution)
    assert "creatomate" not in universal_source
    assert "renderscript" not in universal_source
