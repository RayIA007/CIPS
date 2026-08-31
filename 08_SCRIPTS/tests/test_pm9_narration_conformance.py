from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from types import ModuleType

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from creative_direction_planner import CreativeDirectionPlanner  # noqa: E402
from production_acceptance import (  # noqa: E402
    FasterWhisperTranscriber,
    NarrationConformanceGate,
    NarrationConformanceMismatchError,
    NarrationConformancePolicy,
    NarrationTranscription,
    acoustic_tokens,
    inspect_narration_conformance,
    token_differences,
)
from production_manifest import AssetType  # noqa: E402
from production_manifest_compiler import ProductionManifestCompiler  # noqa: E402
from workspace_resolver import WorkspaceResolver  # noqa: E402

FIXTURE_PROJECT = Path(__file__).parent / "fixtures" / "pm9" / "editorial_project"
ASSET_TYPES = {
    1: AssetType.STOCK_VIDEO,
    2: AssetType.AI_IMAGE,
    3: AssetType.AI_IMAGE,
    4: AssetType.EXISTING_ASSET,
}


class _TranscriptByFilename:
    def __init__(self, values: dict[str, str], *, model: str = "small") -> None:
        self.values = values
        self.network_called = False
        self.policy = NarrationConformancePolicy(
            enabled=True,
            model=model,
            adjudication_model=None,
        )
        self.calls: list[Path] = []

    def transcribe(self, audio_path: Path) -> NarrationTranscription:
        self.calls.append(audio_path)
        return NarrationTranscription(
            text=self.values[audio_path.name],
            detected_language="es",
            language_probability=0.99,
        )


def _manifest_and_audio(tmp_path: Path):
    projects_root = tmp_path / "04_PROYECTOS"
    outputs_root = tmp_path / "05_OUTPUTS"
    project = projects_root / "PROYECTO_PM9_PLANCHA_0001"
    projects_root.mkdir()
    outputs_root.mkdir()
    shutil.copytree(FIXTURE_PROJECT, project)
    workspace = WorkspaceResolver(projects_root, outputs_root)
    compiled = ProductionManifestCompiler(workspace_resolver=workspace).compile(project)
    scene_ids = {scene.sequence: scene.scene_id for scene in compiled.scenes}
    manifest = CreativeDirectionPlanner().plan(
        compiled,
        asset_types={scene_ids[key]: value for key, value in ASSET_TYPES.items()},
        existing_asset_ids={scene_ids[4]: "aligned-plank"},
    )
    audio_root = project / "source_assets" / "audio"
    audio_root.mkdir(parents=True)
    paths: dict[str, Path] = {}
    transcripts: dict[str, str] = {}
    for scene in manifest.scenes:
        path = audio_root / f"narration-{scene.sequence:03d}.mp3"
        path.write_bytes(f"physical-audio-{scene.sequence}".encode())
        paths[scene.scene_id] = path
        transcripts[path.name] = scene.narration_text or ""
    return project, manifest, paths, transcripts


def test_acoustic_diff_detects_desvian_to_desvidan_regression() -> None:
    differences = token_differences(
        acoustic_tokens("Las ondas se desvían mucho más."),
        acoustic_tokens("Las ondas se desvidan mucho más."),
    )

    assert len(differences) == 1
    assert differences[0].operation == "replace"
    assert differences[0].expected == ("desvian",)
    assert differences[0].observed == ("desvidan",)


def test_faster_whisper_uses_physical_files_without_windows_symlinks(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict] = []
    created_models: list[tuple[str, dict]] = []
    hub_module = ModuleType("huggingface_hub")

    def snapshot_download(
        *,
        repo_id,
        local_dir,
        allow_patterns,
        local_files_only,
    ):
        arguments = {
            "repo_id": repo_id,
            "local_dir": local_dir,
            "allow_patterns": allow_patterns,
            "local_files_only": local_files_only,
        }
        calls.append(arguments)
        destination = Path(local_dir)
        destination.mkdir(parents=True, exist_ok=True)
        for filename in (
            "config.json",
            "model.bin",
            "tokenizer.json",
            "vocabulary.json",
        ):
            (destination / filename).write_bytes(filename.encode())
        return str(destination)

    hub_module.snapshot_download = snapshot_download
    whisper_module = ModuleType("faster_whisper")

    class FakeWhisperModel:
        def __init__(self, model_path, **options) -> None:
            created_models.append((model_path, options))

    whisper_module.WhisperModel = FakeWhisperModel
    monkeypatch.setitem(sys.modules, "huggingface_hub", hub_module)
    monkeypatch.setitem(sys.modules, "faster_whisper", whisper_module)

    policy = NarrationConformancePolicy(enabled=True, model="small")
    model_root = tmp_path / "models"
    first = FasterWhisperTranscriber(
        policy,
        model_dir=model_root,
        allow_model_download=True,
    )

    loaded = first._load_model()

    assert isinstance(loaded, FakeWhisperModel)
    assert calls == [
        {
            "repo_id": "Systran/faster-whisper-small",
            "local_dir": str(model_root / "physical" / "small"),
            "allow_patterns": [
                "config.json",
                "preprocessor_config.json",
                "model.bin",
                "tokenizer.json",
                "vocabulary.*",
            ],
            "local_files_only": False,
        }
    ]
    assert created_models[0] == (
        str(model_root / "physical" / "small"),
        {"device": "cpu", "compute_type": "int8", "local_files_only": True},
    )
    assert first.network_called is True

    second = FasterWhisperTranscriber(
        policy,
        model_dir=model_root,
        allow_model_download=False,
    )
    second._load_model()
    assert len(calls) == 1
    assert second.network_called is False


def test_gate_approves_exact_physical_narration_and_binds_hashes(
    tmp_path: Path,
) -> None:
    project, manifest, paths, transcripts = _manifest_and_audio(tmp_path)
    policy = NarrationConformancePolicy(enabled=True)
    gate = NarrationConformanceGate(
        policy,
        _TranscriptByFilename(transcripts),
    )

    report = gate.validate_and_persist(
        manifest,
        paths,
        project_path=project,
    )

    assert report.approved is True
    assert report.blockers == ()
    assert all(clip.approved for clip in report.clips)
    assert report.actual_cost_usd == 0.0
    assert report.paid_provider_called is False
    assert report.render_performed is False
    report_path = project / "acceptance" / "narration_conformance.json"
    assert report_path.is_file()

    inspection = inspect_narration_conformance(
        manifest,
        project_path=project,
        audio_sha256_by_scene_id={
            clip.scene_id: clip.audio_sha256 for clip in report.clips
        },
        policy=policy,
    )
    assert inspection.blockers == ()
    assert inspection.report_sha256 is not None


def test_secondary_model_clears_a_primary_false_positive_and_persists_both(
    tmp_path: Path,
) -> None:
    project, manifest, paths, canonical_transcripts = _manifest_and_audio(tmp_path)
    target = manifest.scenes[0]
    target_path = paths[target.scene_id]
    primary_transcripts = dict(canonical_transcripts)
    primary_transcripts[target_path.name] = "pintar " + (target.narration_text or "")
    primary = _TranscriptByFilename(primary_transcripts, model="small")
    adjudicator = _TranscriptByFilename(canonical_transcripts, model="medium")
    policy = NarrationConformancePolicy(
        enabled=True,
        model="small",
        adjudication_model="medium",
    )

    report = NarrationConformanceGate(
        policy,
        primary,
        adjudicator=adjudicator,
    ).validate_and_persist(manifest, paths, project_path=project)

    clip = next(item for item in report.clips if item.scene_id == target.scene_id)
    assert report.approved is True
    assert clip.approved is True
    assert clip.differences
    assert clip.adjudication_model == "medium"
    assert clip.adjudication_observed_text == target.narration_text
    assert clip.adjudication_differences == ()
    assert clip.adjudication_approved is True
    assert adjudicator.calls == [target_path]
    inspection = inspect_narration_conformance(
        manifest,
        project_path=project,
        audio_sha256_by_scene_id={
            item.scene_id: item.audio_sha256 for item in report.clips
        },
        policy=policy,
    )
    assert inspection.blockers == ()


def test_gate_persists_exact_difference_and_blocks_before_render(
    tmp_path: Path,
) -> None:
    project, manifest, paths, transcripts = _manifest_and_audio(tmp_path)
    target = manifest.scenes[1]
    target_path = paths[target.scene_id]
    canonical_words = (target.narration_text or "").split()
    transcripts[target_path.name] = " ".join([*canonical_words[:-1], "desvidan"])
    gate = NarrationConformanceGate(
        NarrationConformancePolicy(enabled=True),
        _TranscriptByFilename(transcripts),
    )

    with pytest.raises(
        NarrationConformanceMismatchError,
        match="bloqueó la narración antes del render",
    ):
        gate.validate_and_persist(manifest, paths, project_path=project)

    payload = json.loads(
        (project / "acceptance" / "narration_conformance.json").read_text(
            encoding="utf-8"
        )
    )
    assert payload["approved"] is False
    rejected = next(clip for clip in payload["clips"] if not clip["approved"])
    assert rejected["differences"]
    assert rejected["differences"][0]["operation"] in {"replace", "delete"}
    assert payload["render_performed"] is False
    assert payload["publication_performed"] is False


def test_secondary_model_cannot_clear_a_confirmed_lexical_difference(
    tmp_path: Path,
) -> None:
    project, manifest, paths, canonical_transcripts = _manifest_and_audio(tmp_path)
    target = manifest.scenes[1]
    target_path = paths[target.scene_id]
    mismatched_transcripts = dict(canonical_transcripts)
    mismatched_transcripts[target_path.name] = "desvidan " + (
        target.narration_text or ""
    )
    policy = NarrationConformancePolicy(
        enabled=True,
        model="small",
        adjudication_model="medium",
    )

    with pytest.raises(
        NarrationConformanceMismatchError,
        match="adjudicación medium",
    ):
        NarrationConformanceGate(
            policy,
            _TranscriptByFilename(mismatched_transcripts, model="small"),
            adjudicator=_TranscriptByFilename(
                mismatched_transcripts,
                model="medium",
            ),
        ).validate_and_persist(manifest, paths, project_path=project)

    payload = json.loads(
        (project / "acceptance" / "narration_conformance.json").read_text(
            encoding="utf-8"
        )
    )
    rejected = next(clip for clip in payload["clips"] if not clip["approved"])
    assert payload["approved"] is False
    assert rejected["differences"]
    assert rejected["adjudication_differences"]
    assert rejected["adjudication_approved"] is False
    assert payload["render_performed"] is False
    assert payload["paid_provider_called"] is False


def test_changed_audio_hash_invalidates_previous_approval(tmp_path: Path) -> None:
    project, manifest, paths, transcripts = _manifest_and_audio(tmp_path)
    policy = NarrationConformancePolicy(enabled=True)
    report = NarrationConformanceGate(
        policy,
        _TranscriptByFilename(transcripts),
    ).validate_and_persist(manifest, paths, project_path=project)
    hashes = {clip.scene_id: clip.audio_sha256 for clip in report.clips}
    hashes[manifest.scenes[0].scene_id] = "f" * 64

    inspection = inspect_narration_conformance(
        manifest,
        project_path=project,
        audio_sha256_by_scene_id=hashes,
        policy=policy,
    )

    assert inspection.blockers == ("narration_conformance_missing_or_stale",)
