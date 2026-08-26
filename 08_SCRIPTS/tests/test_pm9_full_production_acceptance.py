from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from asset_resolution import (  # noqa: E402
    ManifestAssetResolver,
    MediaFamily,
    ResolutionStatus,
)
from capability_resolver import CapabilityResolver  # noqa: E402
from creative_direction_planner import CreativeDirectionPlanner  # noqa: E402
from final_review import ReviewAction, ReviewDecision  # noqa: E402
from media_provider_registry import MediaProviderRegistry  # noqa: E402
from production_acceptance import (  # noqa: E402
    ApprovedAssetCatalog,
    ApprovedAssetCatalogProvider,
    CatalogEntry,
    FFprobeInspector,
    FullProductionAcceptance,
    MediaProbeError,
    ProductionAcceptanceBlockedError,
)
from production_manifest import AssetType  # noqa: E402
from production_manifest_compiler import ProductionManifestCompiler  # noqa: E402
from render_adapter import RenderResult, RenderStatus  # noqa: E402
import run_pm9_full_production_acceptance as pm9_cli  # noqa: E402
from style_profiles import IMMERSIVE_PROCESS_EXPLAINER_ID  # noqa: E402
from workspace_resolver import WorkspaceResolver  # noqa: E402


FIXTURE_PROJECT = Path(__file__).parent / "fixtures" / "pm9" / "editorial_project"
ASSET_TYPES = {
    1: AssetType.STOCK_VIDEO,
    2: AssetType.AI_IMAGE,
    3: AssetType.MOTION_GRAPHIC,
    4: AssetType.EXISTING_ASSET,
}
EXISTING_IDS = {4: "aligned-plank"}


def _probe_payload(
    *,
    width: int = 1080,
    height: int = 1920,
    fps: str = "30/1",
    duration: str = "46.000000",
) -> dict:
    return {
        "streams": [
            {
                "codec_type": "video",
                "codec_name": "h264",
                "width": width,
                "height": height,
                "avg_frame_rate": fps,
                "r_frame_rate": fps,
            },
            {
                "codec_type": "audio",
                "codec_name": "aac",
                "sample_rate": "48000",
            },
        ],
        "format": {
            "format_name": "mov,mp4,m4a,3gp,3g2,mj2",
            "duration": duration,
        },
    }


def _media_bytes(family: MediaFamily, identity: str) -> tuple[bytes, str, str]:
    suffix = identity.encode("utf-8")
    if family is MediaFamily.IMAGE:
        return b"\x89PNG\r\n\x1a\nPM9-" + suffix, "image/png", ".png"
    if family is MediaFamily.VIDEO:
        return (
            b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isomPM9-" + suffix,
            "video/mp4",
            ".mp4",
        )
    return (
        b"RIFF\x10\x00\x00\x00WAVEfmt PM9-" + suffix,
        "audio/wav",
        ".wav",
    )


def _catalog_entry(
    assets_root: Path,
    *,
    entry_id: str,
    capability: str,
    role: str,
    family: MediaFamily,
    scene_id: str | None = None,
    cue_id: str | None = None,
    existing_asset_id: str | None = None,
) -> CatalogEntry:
    content, mime_type, extension = _media_bytes(family, entry_id)
    relative = Path(family.value) / f"{entry_id}{extension}"
    path = assets_root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return CatalogEntry(
        entry_id=entry_id,
        capability=capability,
        role=role,
        relative_path=relative.as_posix(),
        delivery_uri=f"https://cdn.example.test/pm9/{entry_id}{extension}",
        mime_type=mime_type,
        media_family=family,
        file_extension=extension,
        scene_id=scene_id,
        cue_id=cue_id,
        existing_asset_id=existing_asset_id,
        source_url=f"https://source.example.test/pm9/{entry_id}",
        license_name="CC0-1.0 test fixture",
        attribution="PM9 deterministic offline fixture",
        actual_cost_usd=0.0,
    )


def _environment(tmp_path: Path, *, probe_payload: dict | None = None):
    projects_root = tmp_path / "04_PROYECTOS"
    outputs_root = tmp_path / "05_OUTPUTS"
    assets_root = tmp_path / "approved_assets"
    projects_root.mkdir()
    outputs_root.mkdir()
    assets_root.mkdir()
    project_path = projects_root / "PROYECTO_PM9_PLANCHA_0001"
    shutil.copytree(FIXTURE_PROJECT, project_path)
    workspace = WorkspaceResolver(
        projects_root=projects_root,
        outputs_root=outputs_root,
    )

    source = ProductionManifestCompiler(
        workspace_resolver=workspace
    ).compile(project_path)
    scene_ids = {scene.sequence: scene.scene_id for scene in source.scenes}
    planned = CreativeDirectionPlanner(
        workspace_resolver=workspace
    ).plan(
        source,
        asset_types={scene_ids[key]: value for key, value in ASSET_TYPES.items()},
        existing_asset_ids={
            scene_ids[key]: value for key, value in EXISTING_IDS.items()
        },
    )

    entries = [
        _catalog_entry(
            assets_root,
            entry_id="scene-1-stock",
            capability="stock_video_search",
            role="scene_visual",
            family=MediaFamily.VIDEO,
            scene_id=planned.scenes[0].scene_id,
        ),
        _catalog_entry(
            assets_root,
            entry_id="scene-2-biomedical",
            capability="image_generation",
            role="scene_visual",
            family=MediaFamily.IMAGE,
            scene_id=planned.scenes[1].scene_id,
        ),
        _catalog_entry(
            assets_root,
            entry_id="scene-4-form",
            capability="existing_asset_resolution",
            role="scene_visual",
            family=MediaFamily.IMAGE,
            scene_id=planned.scenes[3].scene_id,
            existing_asset_id="aligned-plank",
        ),
    ]
    for scene in planned.scenes:
        entries.append(
            _catalog_entry(
                assets_root,
                entry_id=f"narration-{scene.sequence}",
                capability="voice_synthesis",
                role="scene_narration",
                family=MediaFamily.AUDIO,
                scene_id=scene.scene_id,
            )
        )
    entries.append(
        _catalog_entry(
            assets_root,
            entry_id="background-music",
            capability="music_generation",
            role="music",
            family=MediaFamily.AUDIO,
        )
    )
    for effect in planned.audio_design.sound_effects:
        entries.append(
            _catalog_entry(
                assets_root,
                entry_id=f"sfx-{effect.scene_id[-8:]}",
                capability="sound_effect_generation",
                role="sound_effect",
                family=MediaFamily.AUDIO,
                cue_id=effect.cue_id,
            )
        )
    catalog = ApprovedAssetCatalog(entries=tuple(entries))
    provider = ApprovedAssetCatalogProvider(catalog, assets_root=assets_root)
    resolver = ManifestAssetResolver(
        capability_resolver=CapabilityResolver(MediaProviderRegistry([provider])),
        workspace_resolver=workspace,
    )
    inspector = FFprobeInspector(
        runner=lambda command: probe_payload or _probe_payload()
    )
    acceptance = FullProductionAcceptance(
        workspace_resolver=workspace,
        asset_resolver=resolver,
        ffprobe_inspector=inspector,
    )
    return project_path, provider, acceptance, planned


def _prepare(tmp_path: Path, *, probe_payload: dict | None = None):
    project_path, provider, acceptance, expected_manifest = _environment(
        tmp_path,
        probe_payload=probe_payload,
    )
    prepared = acceptance.prepare(
        project_path,
        asset_types_by_sequence=ASSET_TYPES,
        existing_asset_ids_by_sequence=EXISTING_IDS,
    )
    return project_path, provider, acceptance, expected_manifest, prepared


def _render_result(prepared) -> RenderResult:
    return RenderResult(
        job_id="job-pm9-plank",
        plan_id=prepared.plan.plan_id,
        manifest_id=prepared.manifest.manifest_id,
        target_id=prepared.plan.target_id,
        status=RenderStatus.SUCCEEDED,
        output_artifact_ids=("render-artifact-pm9-plank",),
        metadata={
            "external_job_id": "creatomate-render-pm9",
            "estimated_credits": 2,
        },
    )


def _render_file(tmp_path: Path) -> Path:
    path = tmp_path / "render.mp4"
    path.write_bytes(
        b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isomPM9-final-render"
    )
    return path


def _approval() -> ReviewDecision:
    return ReviewDecision(
        decision_id="human-approve-pm9-plank-v1",
        action=ReviewAction.APPROVE,
        actor="human:production-owner",
        decided_at="2026-08-25T16:00:00+00:00",
        comments="Calidad visual, narrativa y técnica razonablemente publicable.",
        metadata={"quality_dimension": "human_publishability"},
    )


def test_new_editorial_project_is_scientifically_traced_and_vertical(tmp_path: Path) -> None:
    project_path, _, _, planned = _environment(tmp_path)

    assert planned.project.project_id == "PROYECTO_PM9_PLANCHA_0001"
    assert planned.style_profile == IMMERSIVE_PROCESS_EXPLAINER_ID
    assert (planned.output.width_px, planned.output.height_px) == (1080, 1920)
    assert planned.output.aspect_ratio == "9:16"
    assert len(planned.scenes) == 4
    assert len(planned.source_references) == 7
    assert all(len(reference.content_hash or "") == 64 for reference in planned.source_references)
    research = (project_path / "research" / "01_INVESTIGACION.md").read_text(
        encoding="utf-8"
    )
    verification = (
        project_path / "verification" / "02_VERIFICACION.md"
    ).read_text(encoding="utf-8")
    assert "https://pubmed.ncbi.nlm.nih.gov/10656518/" in research
    assert "inferencia fisiológica prudente" in research
    assert "no mide por sí solo progreso" in (
        project_path / "script" / "03_GUION.md"
    ).read_text(encoding="utf-8")


def test_cli_inventory_is_offline_and_matches_pm8_requirements(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    projects_root = tmp_path / "04_PROYECTOS"
    projects_root.mkdir()
    project_path = projects_root / "PROYECTO_PM9_PLANCHA_0001"
    shutil.copytree(FIXTURE_PROJECT, project_path)

    assert pm9_cli.main(["inventory", "--project", str(project_path)]) == 0

    output = json.loads(capsys.readouterr().out)
    inventory_path = project_path / "acceptance" / "asset_requirements.json"
    assert output["success"] is True
    assert output["network_called"] is False
    assert output["publication_performed"] is False
    assert output["required_catalog_entries"] == 12
    assert output["renderer_native_entries"] == 1
    assert inventory_path.is_file()
    assert Path(f"{inventory_path}.meta.json").is_file()


def test_prepare_reuses_pm1_pm8_and_compiles_only_https_sources(tmp_path: Path) -> None:
    project_path, provider, acceptance, expected, prepared = _prepare(tmp_path)

    assert prepared.manifest == expected
    assert prepared.evidence.ready_for_real_render is True
    assert prepared.evidence.blockers == ()
    assert prepared.evidence.scene_count == 4
    assert prepared.evidence.persisted_asset_count == 12
    assert prepared.evidence.renderer_native_asset_count == 1
    assert prepared.evidence.total_actual_cost_usd == 0.0
    assert prepared.preparation_path.is_file()
    assert prepared.payload_path.is_file()
    assert (project_path / "production_manifest.json").is_file()
    assert (project_path / prepared.asset_run.bundle_relative_path).is_file()

    payload = prepared.plan.target_payload
    media = [
        element
        for element in payload["elements"]
        if element["type"] in {"audio", "image", "video"}
    ]
    assert media
    assert all(element["source"].startswith("https://cdn.example.test/") for element in media)
    assert all("provider" not in element for element in media)

    call_count = len(provider.calls)
    repeated = acceptance.prepare(
        project_path,
        asset_types_by_sequence=ASSET_TYPES,
        existing_asset_ids_by_sequence=EXISTING_IDS,
    )
    assert repeated.evidence == prepared.evidence
    assert repeated.asset_run.reused_existing is True
    assert len(provider.calls) == call_count


def test_real_render_command_is_blocked_without_explicit_credit_authorization(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, _, acceptance, _, prepared = _prepare(tmp_path)
    monkeypatch.delenv(pm9_cli.CONFIRMATION_ENV, raising=False)

    with pytest.raises(
        ProductionAcceptanceBlockedError,
        match="29 créditos",
    ):
        pm9_cli._render_command(prepared, acceptance, max_credits=999)


def test_finalize_requires_explicit_human_publishability_decision(tmp_path: Path) -> None:
    project_path, _, acceptance, _, prepared = _prepare(tmp_path)
    render = _render_file(tmp_path)

    with pytest.raises(
        ProductionAcceptanceBlockedError,
        match="ReviewDecision humana explícita",
    ):
        acceptance.finalize(
            prepared,
            render_result=_render_result(prepared),
            render_path=render,
            review_decision=None,
        )

    assert (project_path / "acceptance" / "qa_report.json").is_file()
    assert not (project_path / "final" / "short.mp4").exists()
    assert not (project_path / "acceptance" / "final_acceptance.json").exists()


def test_f7_persists_request_changes_and_blocks_export(tmp_path: Path) -> None:
    project_path, _, acceptance, _, prepared = _prepare(tmp_path)
    decision = ReviewDecision(
        decision_id="human-redo-pm9-plank-v1",
        action=ReviewAction.REQUEST_CHANGES,
        actor="human:production-owner",
        decided_at="2026-08-25T16:00:00+00:00",
        comments="La narración necesita una pausa más clara antes del aviso de seguridad.",
        redo_target="narration",
        metadata={"quality_dimension": "human_publishability"},
    )

    with pytest.raises(
        ProductionAcceptanceBlockedError,
        match="changes_requested",
    ):
        acceptance.finalize(
            prepared,
            render_result=_render_result(prepared),
            render_path=_render_file(tmp_path),
            review_decision=decision,
        )

    decisions = [
        path
        for path in (project_path / "final_review" / "decisions").glob("*.json")
        if not path.name.endswith(".meta.json")
    ]
    assert len(decisions) == 1
    assert json.loads(decisions[0].read_text(encoding="utf-8"))["state"] == (
        "changes_requested"
    )
    assert not (project_path / "final" / "short.mp4").exists()
    assert not (project_path / "acceptance" / "final_acceptance.json").exists()


def test_full_acceptance_persists_f7_export_f8_and_reuses_result(tmp_path: Path) -> None:
    project_path, provider, acceptance, _, prepared = _prepare(tmp_path)
    render = _render_file(tmp_path)
    result = acceptance.finalize(
        prepared,
        render_result=_render_result(prepared),
        render_path=render,
        review_decision=_approval(),
    )

    assert result.reused_existing is False
    assert result.evidence.qa_approved is True
    assert result.evidence.human_approved is True
    assert result.evidence.review_state == "approved"
    assert result.evidence.publication_performed is False
    assert result.evidence.observed_credits == 2.0
    assert result.export_path == project_path / "final" / "short.mp4"
    assert result.export_path.read_bytes() == render.read_bytes()
    assert Path(f"{result.export_path}.meta.json").is_file()
    assert result.evidence_path.is_file()
    assert list((project_path / "final_review" / "decisions").glob("*.json"))
    assert (project_path / "03_TELEMETRIA" / "TELEMETRY.jsonl").is_file()
    assert (project_path / "03_TELEMETRIA" / "TELEMETRY_SUMMARY.json").is_file()
    assert result.diagnostic_snapshot.status == "succeeded"
    assert result.diagnostic_snapshot.review["state"] == "approved"
    assert result.diagnostic_snapshot.artifacts == [
        {
            "artifact_id": result.evidence.export_artifact_id,
            "content_hash": result.evidence.export_content_sha256,
            "artifact_type": "final_video",
        }
    ]

    calls = len(provider.calls)
    repeated = acceptance.finalize(
        prepared,
        render_result=_render_result(prepared),
        render_path=render,
        review_decision=None,
    )
    assert repeated.reused_existing is True
    assert repeated.evidence == result.evidence
    assert len(provider.calls) == calls


def test_technical_gate_blocks_wrong_vertical_resolution_before_f7(tmp_path: Path) -> None:
    project_path, _, acceptance, _, prepared = _prepare(
        tmp_path,
        probe_payload=_probe_payload(width=720, height=1280),
    )
    with pytest.raises(ProductionAcceptanceBlockedError, match="vertical-resolution"):
        acceptance.finalize(
            prepared,
            render_result=_render_result(prepared),
            render_path=_render_file(tmp_path),
            review_decision=_approval(),
        )

    assert (project_path / "acceptance" / "qa_report.json").is_file()
    assert not (project_path / "final_review").exists()
    assert not (project_path / "final" / "short.mp4").exists()


def test_catalog_rejects_signed_or_credentialed_delivery_urls(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="firmadas"):
        CatalogEntry(
            entry_id="unsafe",
            capability="image_generation",
            role="scene_visual",
            relative_path="image/unsafe.png",
            delivery_uri="https://cdn.example.test/unsafe.png?token=secret",
            mime_type="image/png",
            media_family=MediaFamily.IMAGE,
            file_extension=".png",
            scene_id="scene-unsafe",
            source_url="https://source.example.test/unsafe",
            license_name="test",
        )


def test_ffprobe_inspector_rejects_missing_audio_stream(tmp_path: Path) -> None:
    media = _render_file(tmp_path)
    payload = _probe_payload()
    payload["streams"] = [payload["streams"][0]]
    inspector = FFprobeInspector(runner=lambda command: payload)

    with pytest.raises(MediaProbeError, match="stream de audio"):
        inspector.inspect(
            media,
            expected_width=1080,
            expected_height=1920,
            expected_fps=30.0,
            expected_duration_seconds=44.0,
        )


@pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="FFmpeg/ffprobe no están instalados.",
)
def test_real_ffmpeg_ffprobe_validates_physical_vertical_mp4(tmp_path: Path) -> None:
    media = tmp_path / "physical-vertical.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=c=#0F172A:s=1080x1920:r=30:d=1",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:sample_rate=48000:duration=1",
            "-shortest",
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-y",
            str(media),
        ],
        check=True,
        capture_output=True,
        timeout=90,
    )

    report = FFprobeInspector().inspect(
        media,
        expected_width=1080,
        expected_height=1920,
        expected_fps=30.0,
        expected_duration_seconds=1.0,
        duration_tolerance_seconds=0.2,
    )

    assert report.approved is True
    assert report.video_codec == "h264"
    assert report.audio_codec == "aac"
    assert report.audio_sample_rate_hz == 48000


def test_pm9_keeps_universal_manifest_free_of_provider_fields() -> None:
    manifest_source = (SCRIPTS_DIR / "production_manifest" / "models.py").read_text(
        encoding="utf-8"
    ).lower()
    package_source = "\n".join(
        path.read_text(encoding="utf-8").lower()
        for path in sorted((SCRIPTS_DIR / "production_acceptance").glob("*.py"))
    )

    assert "provider_name" not in manifest_source
    assert "delivery_uri" not in manifest_source
    assert "api_key" not in manifest_source
    assert "import requests" not in package_source
    assert "import openai" not in package_source
    assert "import google" not in package_source
