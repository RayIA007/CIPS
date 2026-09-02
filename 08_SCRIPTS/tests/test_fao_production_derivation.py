from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

import pytest


SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import project_manager as project_manager_module  # noqa: E402
from editorial_contract import EDITORIAL_STAGES  # noqa: E402
from pipeline_engine import PipelineEngine  # noqa: E402
from production_derivation import (  # noqa: E402
    EditorialPackageValidationError,
    ProductionConfigurationValidationError,
    ProductionDerivationEngine,
)
from production_manifest import AssetType, deserialize_manifest  # noqa: E402
from project_manager import ProjectManager  # noqa: E402
from run_pm9_full_production_acceptance import _load_project_config  # noqa: E402
from style_profiles import IMMERSIVE_PROCESS_EXPLAINER_ID  # noqa: E402
from tests.test_fao_editorial_automation import _EditorialProvider  # noqa: E402


def _completed_project(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> tuple[Path, PipelineEngine, object]:
    projects_dir = tmp_path / "04_PROYECTOS"
    monkeypatch.setattr(project_manager_module, "PROJECTS_DIR", projects_dir)
    created = ProjectManager().create_project(
        "Cómo funcionan los eclipses solares",
        plataforma="YouTube Shorts",
        duracion_segundos=40,
        audiencia="público general",
        estilo_creativo="científico, visual y accesible",
    )
    project_path = Path(created["path"])
    pipeline = PipelineEngine(stage_delay_seconds=0)
    pipeline.llm_adapter.set_provider(_EditorialProvider())
    final_result = None
    for expected_stage in EDITORIAL_STAGES:
        assert ProjectManager().load_project(project_path).stage_actual == expected_stage
        final_result = pipeline.execute(project_path=project_path)
        assert final_result.success, final_result.errors
    assert final_result is not None
    return project_path, pipeline, final_result


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_pipeline_derives_complete_provider_neutral_production_inputs(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    project, _, result = _completed_project(monkeypatch, tmp_path)

    manifest_path = project / "production_manifest.json"
    config_path = project / "production_acceptance_config.json"
    evidence_path = project / "state" / "production_derivation.json"
    manifest = deserialize_manifest(manifest_path.read_bytes())
    config = json.loads(config_path.read_text(encoding="utf-8"))
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))

    assert result.metadata["production_derivation_complete"] is True
    assert result.metadata["next_stage"] == "voz"
    assert manifest.style_profile == IMMERSIVE_PROCESS_EXPLAINER_ID
    assert manifest.output.duration_seconds == 40.0
    assert manifest.output.aspect_ratio == "9:16"
    assert all(
        scene.asset_request.asset_type
        not in {AssetType.NONE, AssetType.AI_IMAGE, AssetType.AI_VIDEO, AssetType.STOCK_VIDEO}
        for scene in manifest.scenes
    )
    assert any(
        scene.asset_request.asset_type is AssetType.STOCK_IMAGE
        for scene in manifest.scenes
    )
    assert all(
        scene.asset_request.stock_query
        for scene in manifest.scenes
        if scene.asset_request.asset_type is AssetType.STOCK_IMAGE
    )

    assert config["schema_name"] == "cips.production_acceptance.project_config"
    assert set(config["asset_types_by_sequence"]) == {
        str(scene.sequence) for scene in manifest.scenes
    }
    assert config["on_screen_text_mode"] == "captions_only"
    assert not any("json2video" in key or "creatomate" in key for key in config)
    assert evidence["schema_name"] == "cips.fao.production_derivation"
    assert evidence["status"] == "production_inputs_ready"
    assert evidence["production_manifest_sha256"] == _sha256(manifest_path)
    assert evidence["production_config_sha256"] == _sha256(config_path)
    assert evidence["configuration_validated"] is True
    assert evidence["manifest_validated"] is True
    assert evidence["free_tier_default"] is True
    assert evidence["network_called"] is False
    assert evidence["paid_provider_called"] is False
    assert evidence["render_performed"] is False
    assert evidence["publication_performed"] is False

    for path in (manifest_path, config_path, evidence_path):
        assert Path(f"{path}.meta.json").is_file()


def test_generated_config_is_consumable_by_existing_pm9_boundary(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    project, _, _ = _completed_project(monkeypatch, tmp_path)

    loaded = _load_project_config(project.resolve())
    manifest = deserialize_manifest((project / "production_manifest.json").read_bytes())

    assert loaded["asset_types_by_sequence"] == {
        scene.sequence: scene.asset_request.asset_type for scene in manifest.scenes
    }
    assert loaded["stock_queries_by_sequence"] == {
        scene.sequence: scene.asset_request.stock_query
        for scene in manifest.scenes
        if scene.asset_request.asset_type is AssetType.STOCK_IMAGE
    }
    assert loaded["frame_rate_policy"].mode.value == "normalize_to_manifest"
    assert loaded["narration_conformance_policy"].enabled is True


def test_identical_editorial_inputs_reuse_byte_identical_outputs(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    project, _, _ = _completed_project(monkeypatch, tmp_path)
    paths = (
        project / "production_manifest.json",
        project / "production_acceptance_config.json",
        project / "state" / "production_derivation.json",
    )
    before = {path: path.read_bytes() for path in paths}
    sidecars_before = {
        Path(f"{path}.meta.json"): Path(f"{path}.meta.json").read_bytes()
        for path in paths
    }

    repeated = ProductionDerivationEngine().derive_and_persist(project)

    assert repeated.reused_existing is True
    assert {path: path.read_bytes() for path in paths} == before
    assert {
        path: path.read_bytes() for path in sidecars_before
    } == sidecars_before


def test_tampered_editorial_artifact_blocks_derivation_without_overwriting_outputs(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    project, _, _ = _completed_project(monkeypatch, tmp_path)
    outputs = (
        project / "production_manifest.json",
        project / "production_acceptance_config.json",
        project / "state" / "production_derivation.json",
    )
    before = {path: path.read_bytes() for path in outputs}
    narration = project / "narration" / "narration.txt"
    narration.write_text(
        narration.read_text(encoding="utf-8") + " Alteración no validada.",
        encoding="utf-8",
    )

    with pytest.raises(EditorialPackageValidationError, match="hash físico"):
        ProductionDerivationEngine().derive_and_persist(project)

    assert {path: path.read_bytes() for path in outputs} == before


def test_config_validation_rejects_asset_type_divergence(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    project, _, _ = _completed_project(monkeypatch, tmp_path)
    manifest = deserialize_manifest((project / "production_manifest.json").read_bytes())
    config = json.loads(
        (project / "production_acceptance_config.json").read_text(encoding="utf-8")
    )
    config["asset_types_by_sequence"]["1"] = "ai_video"

    with pytest.raises(
        ProductionConfigurationValidationError,
        match="no coinciden",
    ):
        ProductionDerivationEngine.validate_production_config(config, manifest)


def test_pipeline_keeps_narration_stage_when_derivation_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    projects_dir = tmp_path / "04_PROYECTOS"
    monkeypatch.setattr(project_manager_module, "PROJECTS_DIR", projects_dir)
    created = ProjectManager().create_project(
        "Cómo funcionan los eclipses solares",
        plataforma="YouTube Shorts",
        duracion_segundos=40,
        audiencia="público general",
        estilo_creativo="científico, visual y accesible",
    )
    project = Path(created["path"])
    pipeline = PipelineEngine(stage_delay_seconds=0)
    pipeline.llm_adapter.set_provider(_EditorialProvider())
    for _ in EDITORIAL_STAGES[:-1]:
        result = pipeline.execute(project_path=project)
        assert result.success, result.errors

    def _fail_derivation(_: Path) -> None:
        raise EditorialPackageValidationError("fallo FAO.4 inyectado")

    monkeypatch.setattr(
        pipeline.production_derivation,
        "derive_and_persist",
        _fail_derivation,
    )
    failed = pipeline.execute(project_path=project)

    assert failed.success is False
    assert failed.metadata["production_derivation_failed"] is True
    assert ProjectManager().load_project(project).stage_actual == "narracion"
    assert not (project / "production_manifest.json").exists()
    assert not (project / "production_acceptance_config.json").exists()
    assert not (project / "state" / "production_derivation.json").exists()
