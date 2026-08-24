from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest
from pydantic import ValidationError


SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from production_manifest import (  # noqa: E402
    PRODUCTION_MANIFEST_FILENAME,
    PRODUCTION_MANIFEST_SCHEMA_NAME,
    PRODUCTION_MANIFEST_SCHEMA_VERSION,
    AssetRequest,
    AssetType,
    ProductionManifest,
    SceneSpec,
    deserialize_manifest,
    deterministic_manifest_id,
    deterministic_scene_id,
    production_manifest_json_schema,
    serialize_manifest,
    validate_manifest_data,
)


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "pm1" / PRODUCTION_MANIFEST_FILENAME


def _fixture_text() -> str:
    return FIXTURE_PATH.read_text(encoding="utf-8")


def _fixture_data() -> dict:
    return json.loads(_fixture_text())


def _build(data: dict | None = None) -> ProductionManifest:
    return validate_manifest_data(_fixture_data() if data is None else data)


def test_complex_production_manifest_fixture_is_valid_and_complete() -> None:
    manifest = deserialize_manifest(_fixture_text())

    assert manifest.schema_name == PRODUCTION_MANIFEST_SCHEMA_NAME
    assert manifest.schema_version.value == PRODUCTION_MANIFEST_SCHEMA_VERSION
    assert manifest.manifest_id == "pm-7ca21a2565da86a062493357"
    assert manifest.output.width_px == 1080
    assert manifest.output.height_px == 1920
    assert manifest.output.aspect_ratio == "9:16"
    assert manifest.output.duration_seconds == 30.0
    assert len(manifest.scenes) == 3
    assert [scene.sequence for scene in manifest.scenes] == [1, 2, 3]
    assert manifest.scenes[-1].end_seconds == 30.0
    assert {scene.asset_request.asset_type for scene in manifest.scenes} == {
        AssetType.AI_VIDEO,
        AssetType.STOCK_VIDEO,
        AssetType.EXISTING_ASSET,
    }
    assert manifest.audio_design.music is not None
    assert len(manifest.audio_design.sound_effects) == 2
    assert len(manifest.quality_requirements) == 3
    assert len(manifest.source_references) == 3


def test_serialization_is_deterministic_and_round_trips() -> None:
    manifest = _build()

    first = serialize_manifest(manifest)
    second = serialize_manifest(manifest)
    reconstructed = deserialize_manifest(first)

    assert first == second
    assert reconstructed == manifest
    assert serialize_manifest(reconstructed) == first
    assert first.endswith("\n")
    assert "Cómo convertir una idea" in first


def test_serialized_manifest_can_be_written_as_expected_artifact(tmp_path: Path) -> None:
    manifest = _build()
    artifact_path = tmp_path / PRODUCTION_MANIFEST_FILENAME

    artifact_path.write_text(serialize_manifest(manifest), encoding="utf-8")
    reconstructed = deserialize_manifest(artifact_path.read_bytes())

    assert artifact_path.name == "production_manifest.json"
    assert reconstructed == manifest


def test_json_schema_is_versioned_and_forbids_structural_extras() -> None:
    schema = production_manifest_json_schema()

    assert schema["title"] == "ProductionManifest"
    assert schema["additionalProperties"] is False
    assert schema["properties"]["schema_name"]["const"] == PRODUCTION_MANIFEST_SCHEMA_NAME
    version_ref = schema["properties"]["schema_version"]["$ref"]
    version_name = version_ref.rsplit("/", 1)[-1]
    assert schema["$defs"][version_name]["enum"] == [PRODUCTION_MANIFEST_SCHEMA_VERSION]

    strict_models = {
        "AssetRequest",
        "AudioDesignSpec",
        "CaptionSpec",
        "NarrationSpec",
        "OnScreenTextSpec",
        "OutputSpec",
        "ProjectIdentity",
        "PublicationSpec",
        "QualityRequirement",
        "SafeAreaSpec",
        "SceneSpec",
        "SourceReference",
        "TransitionSpec",
        "VisualDirection",
    }
    for model_name in strict_models:
        assert schema["$defs"][model_name]["additionalProperties"] is False


def test_unsupported_manifest_version_is_rejected() -> None:
    data = _fixture_data()
    data["schema_version"] = "2.0"

    with pytest.raises(ValidationError, match="Input should be '1.0'"):
        _build(data)


def test_unknown_fields_are_rejected_at_root_and_nested_levels() -> None:
    root_data = _fixture_data()
    root_data["renderer_payload"] = {}
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        _build(root_data)

    nested_data = _fixture_data()
    nested_data["scenes"][0]["asset_request"]["template_id"] = "foreign-template"
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        _build(nested_data)


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("output", "duration_seconds"), "30.0"),
        (("output", "fps"), "30"),
        (("scenes", 0, "start_seconds"), False),
        (("scenes", 0, "duration_seconds"), "5.5"),
        (("scenes", 0, "on_screen_text", 0, "respect_safe_area"), "true"),
    ],
)
def test_timing_and_boolean_fields_reject_coercive_text(path: tuple, value: object) -> None:
    data = _fixture_data()
    target: object = data
    for key in path[:-1]:
        target = target[key]  # type: ignore[index]
    target[path[-1]] = value  # type: ignore[index]

    with pytest.raises(ValidationError):
        _build(data)


def test_manifest_and_scene_ids_are_deterministic() -> None:
    manifest_id = deterministic_manifest_id("Project-A", "Short-A", 2)
    assert manifest_id == deterministic_manifest_id(" project-a ", "short-a", 2)
    assert manifest_id != deterministic_manifest_id("Project-A", "Short-A", 3)

    scene_id = deterministic_scene_id(1, "  Una idea con   espacios. ")
    assert scene_id == deterministic_scene_id(1, "una idea con espacios.")
    assert scene_id != deterministic_scene_id(2, "una idea con espacios.")


def test_missing_manifest_and_scene_ids_are_derived() -> None:
    data = _fixture_data()
    expected_manifest_id = data.pop("manifest_id")
    expected_scene_id = deterministic_scene_id(
        data["scenes"][0]["sequence"],
        data["scenes"][0]["narration_text"],
    )
    data["scenes"][0].pop("scene_id")
    data["audio_design"]["sound_effects"][0]["scene_id"] = expected_scene_id

    manifest = _build(data)

    assert manifest.manifest_id == expected_manifest_id
    assert manifest.scenes[0].scene_id == expected_scene_id


def test_non_deterministic_manifest_id_is_rejected() -> None:
    data = _fixture_data()
    data["manifest_id"] = "pm-arbitrary"

    with pytest.raises(ValidationError, match="manifest_id no coincide"):
        _build(data)


def test_locale_is_normalized_and_invalid_locale_is_rejected() -> None:
    data = _fixture_data()
    data["locale"] = "es-mx"
    assert _build(data).locale == "es-MX"

    data["locale"] = "Spanish (Mexico)"
    with pytest.raises(ValidationError, match="BCP-47"):
        _build(data)


def test_output_resolution_must_match_declared_aspect_ratio() -> None:
    data = _fixture_data()
    data["output"]["aspect_ratio"] = "16:9"

    with pytest.raises(ValidationError, match="aspect_ratio no coincide"):
        _build(data)


@pytest.mark.parametrize(
    ("asset_type", "required_field"),
    [
        ("ai_image", "image_prompt"),
        ("ai_video", "video_prompt"),
        ("stock_image", "stock_query"),
        ("stock_video", "stock_query"),
        ("motion_graphic", "creative_brief"),
        ("text_graphic", "creative_brief"),
        ("existing_asset", "existing_asset_id"),
    ],
)
def test_asset_types_require_their_provider_neutral_planning_input(
    asset_type: str,
    required_field: str,
) -> None:
    base = {
        "asset_type": asset_type,
        "creative_brief": "Brief",
        "image_prompt": "Image prompt",
        "video_prompt": "Video prompt",
        "stock_query": "Stock query",
        "existing_asset_id": "artifact-1",
    }
    base.pop(required_field)

    with pytest.raises(ValidationError, match=required_field):
        AssetRequest.model_validate(base)


def test_none_asset_type_rejects_prompts_and_alternatives() -> None:
    with pytest.raises(ValidationError, match="asset_type='none'"):
        AssetRequest(
            asset_type=AssetType.NONE,
            image_prompt="No debe existir",
        )


def test_scene_rejects_text_or_transitions_outside_its_duration() -> None:
    text_data = _fixture_data()
    text_data["scenes"][0]["on_screen_text"][0]["duration_seconds"] = 5.5
    with pytest.raises(ValidationError, match="excede la duración de la escena"):
        _build(text_data)

    transition_data = _fixture_data()
    transition_data["scenes"][0]["transition_in"] = {
        "kind": "fade",
        "duration_seconds": 3.0,
    }
    transition_data["scenes"][0]["transition_out"]["duration_seconds"] = 3.0
    with pytest.raises(ValidationError, match="transiciones exceden"):
        _build(transition_data)


def test_manifest_rejects_non_contiguous_scene_order() -> None:
    data = _fixture_data()
    data["scenes"][1]["sequence"] = 3

    with pytest.raises(ValidationError, match="sequence contiguo"):
        _build(data)


def test_manifest_rejects_overlapping_scenes() -> None:
    data = _fixture_data()
    data["scenes"][1]["start_seconds"] = 5.0

    with pytest.raises(ValidationError, match="se solapan"):
        _build(data)


def test_manifest_rejects_timeline_duration_mismatch() -> None:
    data = _fixture_data()
    data["output"]["duration_seconds"] = 31.0

    with pytest.raises(ValidationError, match="final de la timeline"):
        _build(data)


def test_manifest_rejects_duplicate_scene_and_quality_ids() -> None:
    scene_data = _fixture_data()
    scene_data["scenes"][2]["scene_id"] = scene_data["scenes"][0]["scene_id"]
    with pytest.raises(ValidationError, match="scene_id duplicados"):
        _build(scene_data)

    quality_data = _fixture_data()
    quality_data["quality_requirements"][1]["requirement_id"] = (
        quality_data["quality_requirements"][0]["requirement_id"]
    )
    with pytest.raises(ValidationError, match="requirement_id duplicados"):
        _build(quality_data)


def test_scene_source_references_must_resolve() -> None:
    data = _fixture_data()
    data["scenes"][0]["source_reference_ids"] = ["source-missing"]

    with pytest.raises(ValidationError, match="fuentes inexistentes"):
        _build(data)


def test_sound_effects_must_resolve_and_fit_their_scene() -> None:
    missing_scene = _fixture_data()
    missing_scene["audio_design"]["sound_effects"][0]["scene_id"] = "scene-missing"
    with pytest.raises(ValidationError, match="escena inexistente"):
        _build(missing_scene)

    outside_scene = _fixture_data()
    outside_scene["audio_design"]["sound_effects"][0]["start_offset_seconds"] = 5.25
    outside_scene["audio_design"]["sound_effects"][0]["duration_seconds"] = 0.5
    with pytest.raises(ValidationError, match="cue 'sfx-reveal' excede"):
        _build(outside_scene)


def test_music_must_start_and_end_inside_output_duration() -> None:
    late_start = _fixture_data()
    late_start["audio_design"]["music"]["start_seconds"] = 30.0
    late_start["audio_design"]["music"].pop("duration_seconds")
    with pytest.raises(ValidationError, match="música debe iniciar"):
        _build(late_start)

    late_end = _fixture_data()
    late_end["audio_design"]["music"]["duration_seconds"] = 31.0
    with pytest.raises(ValidationError, match="música excede"):
        _build(late_end)


def test_scene_narration_must_follow_full_narration_order() -> None:
    data = _fixture_data()
    data["scenes"][1]["narration_text"] = "Este fragmento no existe en la narración."

    with pytest.raises(ValidationError, match="no aparece en orden"):
        _build(data)


def test_hashtags_are_neutral_normalized_and_unique() -> None:
    data = _fixture_data()
    data["publication"]["hashtags"] = ["#CIPS", "Produccion"]
    assert _build(data).publication.hashtags == ("CIPS", "Produccion")

    data["publication"]["hashtags"] = ["CIPS", "cips"]
    with pytest.raises(ValidationError, match="hashtags contiene valores duplicados"):
        _build(data)


def test_domain_and_fixture_contain_no_first_renderer_contract_dependency() -> None:
    package_root = SCRIPTS_DIR / "production_manifest"
    combined = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(package_root.glob("*.py"))
    ) + _fixture_text()
    normalized = combined.casefold()

    assert "creatomate" not in normalized
    assert "renderscript" not in normalized


def test_public_serialization_helpers_reject_wrong_input_types() -> None:
    with pytest.raises(TypeError, match="ProductionManifest"):
        serialize_manifest({})  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="str, bytes o bytearray"):
        deserialize_manifest({})  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="Mapping"):
        validate_manifest_data([])  # type: ignore[arg-type]


def test_scene_model_derives_same_id_from_equivalent_input() -> None:
    scene_data = deepcopy(_fixture_data()["scenes"][0])
    scene_data.pop("scene_id")
    first = SceneSpec.model_validate(scene_data)
    scene_data["narration_text"] = "  " + scene_data["narration_text"] + "  "
    second = SceneSpec.model_validate(scene_data)

    assert first.scene_id == second.scene_id
