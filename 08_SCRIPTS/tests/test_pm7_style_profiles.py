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
    CreatomateAdapter,
    serialize_creatomate_payload,
    validate_creatomate_payload,
)
from production_manifest import OutputSpec, ProductionManifest  # noqa: E402
from production_manifest_compiler import ProductionManifestCompiler  # noqa: E402
from render_adapter import RenderCompilationError  # noqa: E402
from style_profiles import (  # noqa: E402
    CINEMATIC_CELLULAR_DOCUMENTARY_ID,
    IMMERSIVE_PROCESS_EXPLAINER_ID,
    MINIMAL_BIOMEDICAL_EXPLAINER_ID,
    OutputLayoutFamily,
    classify_output_layout,
    list_style_profiles,
)
from workspace_resolver import WorkspaceResolver  # noqa: E402

FIXTURE_PROJECT = Path(__file__).parent / "fixtures" / "pm2" / "editorial_project"
PROFILE_IDS = (
    IMMERSIVE_PROCESS_EXPLAINER_ID,
    CINEMATIC_CELLULAR_DOCUMENTARY_ID,
    MINIMAL_BIOMEDICAL_EXPLAINER_ID,
)


@pytest.fixture()
def planned_manifest(tmp_path: Path) -> ProductionManifest:
    projects_root = tmp_path / "04_PROYECTOS"
    outputs_root = tmp_path / "05_OUTPUTS"
    projects_root.mkdir()
    outputs_root.mkdir()
    project_path = projects_root / "PROYECTO_PM7_0001"
    shutil.copytree(FIXTURE_PROJECT, project_path)
    resolver = WorkspaceResolver(
        projects_root=projects_root,
        outputs_root=outputs_root,
    )
    source = ProductionManifestCompiler(workspace_resolver=resolver).compile(
        project_path
    )
    return CreativeDirectionPlanner(workspace_resolver=resolver).plan(source)


def _with_output(
    manifest: ProductionManifest,
    *,
    width_px: int,
    height_px: int,
    aspect_ratio: str,
) -> ProductionManifest:
    output = OutputSpec(
        platform=manifest.output.platform,
        width_px=width_px,
        height_px=height_px,
        aspect_ratio=aspect_ratio,
        fps=manifest.output.fps,
        duration_seconds=manifest.output.duration_seconds,
        safe_area=manifest.output.safe_area,
    )
    return manifest.model_copy(update={"output": output})


def _captions(payload: dict) -> list[dict]:
    return [
        element for element in payload["elements"] if ":captions:" in element["name"]
    ]


def _percent(value: str) -> float:
    return float(value.removesuffix("%")) / 100.0


def test_three_profiles_are_evidence_backed_and_complete_for_every_layout() -> None:
    profiles = list_style_profiles()

    assert {profile.profile_id for profile in profiles} == set(PROFILE_IDS)
    assert all(profile.evidence for profile in profiles)
    assert all(profile.rhythm.preferred_shot_seconds > 0.0 for profile in profiles)
    assert all(profile.audio.maximum_true_peak_dbfs <= -0.1 for profile in profiles)
    assert all(profile.motion.techniques for profile in profiles)
    assert all(profile.motion_graphics.allowed_elements for profile in profiles)
    assert all(profile.b_roll.preferred_subjects for profile in profiles)
    assert all(
        {layout.family for layout in profile.composition.layouts}
        == set(OutputLayoutFamily)
        for profile in profiles
    )
    assert {
        evidence.source_id for profile in profiles for evidence in profile.evidence
    } == {
        "gold-scar-healing-short",
        "gold-immune-system-battleground",
        "gold-mitochondria-energy",
    }


@pytest.mark.parametrize(
    ("width", "height", "expected"),
    (
        (1080, 1920, OutputLayoutFamily.VERTICAL),
        (1080, 1350, OutputLayoutFamily.VERTICAL),
        (1920, 1080, OutputLayoutFamily.HORIZONTAL),
        (2560, 1080, OutputLayoutFamily.HORIZONTAL),
        (1080, 1080, OutputLayoutFamily.SQUARE),
        (1200, 1000, OutputLayoutFamily.HORIZONTAL),
    ),
)
def test_layout_family_depends_on_geometry_not_platform(
    width: int,
    height: int,
    expected: OutputLayoutFamily,
) -> None:
    assert classify_output_layout(width, height) is expected


@pytest.mark.parametrize("profile_id", PROFILE_IDS)
@pytest.mark.parametrize(
    ("width", "height", "ratio"),
    (
        (1080, 1920, "9:16"),
        (1920, 1080, "16:9"),
        (1080, 1080, "1:1"),
    ),
)
def test_every_profile_compiles_vertical_horizontal_and_square_inside_safe_area(
    planned_manifest: ProductionManifest,
    profile_id: str,
    width: int,
    height: int,
    ratio: str,
) -> None:
    manifest = _with_output(
        planned_manifest.model_copy(update={"style_profile": profile_id}),
        width_px=width,
        height_px=height,
        aspect_ratio=ratio,
    )
    payload = CreatomateAdapter().compile(manifest).target_payload

    assert (payload["width"], payload["height"]) == (width, height)
    captions = _captions(payload)
    assert captions
    safe = manifest.output.safe_area
    for caption in captions:
        x = _percent(caption["x"])
        y = _percent(caption["y"])
        caption_width = _percent(caption["width"])
        caption_height = _percent(caption["height"])
        assert x - caption_width / 2.0 >= safe.left - 1e-6
        assert x + caption_width / 2.0 <= 1.0 - safe.right + 1e-6
        assert y - caption_height / 2.0 >= safe.top - 1e-6
        assert y + caption_height / 2.0 <= 1.0 - safe.bottom + 1e-6


def test_same_content_produces_three_distinct_deterministic_style_payloads(
    planned_manifest: ProductionManifest,
) -> None:
    adapter = CreatomateAdapter()
    serialized: dict[str, str] = {}
    captions: dict[str, dict] = {}

    for profile_id in PROFILE_IDS:
        manifest = planned_manifest.model_copy(update={"style_profile": profile_id})
        first = adapter.compile(manifest).target_payload
        second = adapter.compile(manifest).target_payload
        assert first == second
        serialized[profile_id] = serialize_creatomate_payload(first)
        captions[profile_id] = _captions(first)[0]

    assert len(set(serialized.values())) == len(PROFILE_IDS)
    assert captions[IMMERSIVE_PROCESS_EXPLAINER_ID]["transcript_effect"] == "highlight"
    assert "text" not in captions[IMMERSIVE_PROCESS_EXPLAINER_ID]
    assert captions[CINEMATIC_CELLULAR_DOCUMENTARY_ID]["font_family"] == "Montserrat"
    assert captions[MINIMAL_BIOMEDICAL_EXPLAINER_ID]["font_family"] == "Aileron"
    assert (
        captions[CINEMATIC_CELLULAR_DOCUMENTARY_ID]["background_color"]
        != (captions[MINIMAL_BIOMEDICAL_EXPLAINER_ID]["background_color"])
    )


def test_profile_translation_does_not_mutate_or_expand_the_manifest_domain(
    planned_manifest: ProductionManifest,
) -> None:
    manifest = planned_manifest.model_copy(
        update={"style_profile": CINEMATIC_CELLULAR_DOCUMENTARY_ID}
    )
    before = manifest.model_dump(mode="json")

    CreatomateAdapter().compile(manifest)

    assert manifest.model_dump(mode="json") == before
    assert ProductionManifest.model_fields["style_profile"].annotation is str
    assert "creatomate" not in ProductionManifest.model_fields
    assert "template_id" not in ProductionManifest.model_fields


def test_one_profile_changes_layout_values_between_vertical_and_horizontal(
    planned_manifest: ProductionManifest,
) -> None:
    styled = planned_manifest.model_copy(
        update={"style_profile": IMMERSIVE_PROCESS_EXPLAINER_ID}
    )
    vertical = CreatomateAdapter().compile(styled).target_payload
    horizontal_manifest = _with_output(
        styled,
        width_px=1920,
        height_px=1080,
        aspect_ratio="16:9",
    )
    horizontal = CreatomateAdapter().compile(horizontal_manifest).target_payload
    vertical_caption = _captions(vertical)[0]
    horizontal_caption = _captions(horizontal)[0]

    assert vertical_caption["width"] == "86%"
    assert horizontal_caption["width"] == "70%"
    assert vertical_caption["font_size"] == "6.8 vmin"
    assert horizontal_caption["font_size"] == "4.896 vmin"


def test_synchronized_caption_requires_a_real_named_audio_or_video_source(
    planned_manifest: ProductionManifest,
) -> None:
    manifest = planned_manifest.model_copy(
        update={"style_profile": IMMERSIVE_PROCESS_EXPLAINER_ID}
    )
    payload = CreatomateAdapter().compile(manifest).target_payload
    invalid = dict(payload)
    invalid["elements"] = [dict(element) for element in payload["elements"]]
    caption = next(
        element for element in invalid["elements"] if ":captions:" in element["name"]
    )
    caption["transcript_source"] = "missing-narration"

    with pytest.raises(RenderCompilationError, match="inexistente"):
        validate_creatomate_payload(invalid)


def test_style_domain_is_provider_and_platform_neutral() -> None:
    source = "\n".join(
        path.read_text(encoding="utf-8").casefold()
        for path in sorted((SCRIPTS_DIR / "style_profiles").glob("*.py"))
    )
    forbidden = (
        "creatomate",
        "renderscript",
        "youtube",
        "tiktok",
        "instagram",
        "template_id",
        "modifications",
    )

    assert all(token not in source for token in forbidden)
