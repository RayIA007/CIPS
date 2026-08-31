from __future__ import annotations

import json
import shutil
import subprocess
import sys
import wave
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import production_acceptance.source_assets as source_assets  # noqa: E402
from creative_direction_planner import CreativeDirectionPlanner  # noqa: E402
from metadata_store import MetadataStore  # noqa: E402
from production_acceptance import (  # noqa: E402
    ApprovedAssetCatalog,
    NarrationConformanceGate,
    NarrationConformancePolicy,
    NarrationTranscription,
    PM9SourceAssetBuilder,
    SourceAssetBuildError,
    derive_github_raw_base,
    verify_catalog_delivery,
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


def _planned_manifest(tmp_path: Path):
    projects_root = tmp_path / "04_PROYECTOS"
    outputs_root = tmp_path / "05_OUTPUTS"
    project = projects_root / "PROYECTO_PM9_PLANCHA_0001"
    projects_root.mkdir()
    outputs_root.mkdir()
    shutil.copytree(FIXTURE_PROJECT, project)
    workspace = WorkspaceResolver(projects_root, outputs_root)
    compiled = ProductionManifestCompiler(workspace_resolver=workspace).compile(project)
    scene_ids = {scene.sequence: scene.scene_id for scene in compiled.scenes}
    planned = CreativeDirectionPlanner().plan(
        compiled,
        asset_types={scene_ids[key]: value for key, value in ASSET_TYPES.items()},
        existing_asset_ids={scene_ids[4]: "aligned-plank"},
    )
    return project, outputs_root, planned


def _completed(stdout: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess([], 0, stdout=stdout, stderr="")


def _write_wav(path: Path, *, seconds: float = 0.1) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(8_000)
        stream.writeframes(b"\x00\x00" * max(1, round(seconds * 8_000)))


class _ExactManifestTranscriber:
    def __init__(self, manifest) -> None:
        self.text_by_filename = {
            f"narration-{scene.sequence:03d}.mp3": scene.narration_text or ""
            for scene in manifest.scenes
            if scene.narration_text is not None
        }
        self.network_called = False

    def transcribe(self, audio_path: Path) -> NarrationTranscription:
        return NarrationTranscription(text=self.text_by_filename[audio_path.name])


class _PrimaryVoiceMismatchThenExactTranscriber(_ExactManifestTranscriber):
    def __init__(self, manifest) -> None:
        super().__init__(manifest)
        self.scene_count = len(self.text_by_filename)
        self.call_count = 0

    def transcribe(self, audio_path: Path) -> NarrationTranscription:
        attempt = self.call_count // self.scene_count
        self.call_count += 1
        text = self.text_by_filename[audio_path.name]
        if attempt == 0 and audio_path.name == "narration-001.mp3":
            text += " desvidan"
        return NarrationTranscription(text=text)


def test_derive_github_raw_base_supports_https_origin(tmp_path: Path) -> None:
    repository = tmp_path / "repo"
    project = repository / "04_PROYECTOS" / "PM9"
    assets = project / "source_assets"
    (repository / ".git").mkdir(parents=True)
    assets.mkdir(parents=True)
    commands: list[tuple[str, ...]] = []

    def runner(command):
        commands.append(tuple(command))
        if command[-3:] == ("remote", "get-url", "origin"):
            return _completed("https://github.com/RayIA007/CIPS.git\n")
        return _completed("main\n")

    result = derive_github_raw_base(project, assets, runner=runner)

    assert result == (
        "https://raw.githubusercontent.com/RayIA007/CIPS/main/"
        "04_PROYECTOS/PM9/source_assets"
    )
    assert all(command[1:3] == ("-C", str(repository)) for command in commands)


def test_derive_github_raw_base_supports_ssh_origin(tmp_path: Path) -> None:
    repository = tmp_path / "repo"
    project = repository / "04_PROYECTOS" / "PM9"
    assets = project / "source_assets"
    (repository / ".git").mkdir(parents=True)
    assets.mkdir(parents=True)

    def runner(command):
        if command[-3:] == ("remote", "get-url", "origin"):
            return _completed("git@github.com:RayIA007/CIPS.git\n")
        return _completed("release/pm9\n")

    result = derive_github_raw_base(project, assets, runner=runner)

    assert result.endswith("/release%2Fpm9/04_PROYECTOS/PM9/source_assets")


def test_full_asset_build_is_zero_cost_and_idempotent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project, outputs_root, manifest = _planned_manifest(tmp_path)
    assets_root = project / "source_assets"
    model_dir = outputs_root / "pm9_models" / "piper"
    visual_root = assets_root / "visual"
    visual_root.mkdir(parents=True)
    for name in (
        "scene-002-biomedical-v2.png",
        "scene-003-motor-units-v2.png",
        "scene-004-aligned-plank-v2.png",
    ):
        (visual_root / name).write_bytes(b"\x89PNG\r\n\x1a\ncurated-pm9")

    monkeypatch.setattr(source_assets.shutil, "which", lambda name: f"/bin/{name}")
    monkeypatch.setattr(
        source_assets.importlib.util, "find_spec", lambda name: object()
    )
    monkeypatch.setattr(
        source_assets,
        "_write_procedural_audio",
        lambda path, duration_seconds, kind: _write_wav(path),
    )
    calls: list[tuple[str, ...]] = []

    def runner(command):
        command = tuple(str(item) for item in command)
        calls.append(command)
        if "piper.download_voices" in command:
            voice_id = command[command.index("piper.download_voices") + 1]
            (model_dir / f"{voice_id}.onnx").write_bytes(b"onnx-model")
            (model_dir / f"{voice_id}.onnx.json").write_text("{}", encoding="utf-8")
        elif command[0] == sys.executable and "piper" in command:
            _write_wav(Path(command[command.index("-f") + 1]), seconds=1.0)
        elif command[0] == "ffprobe":
            return _completed("1.000000\n")
        elif command[0] == "ffmpeg":
            destination = Path(command[-1])
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(b"generated-media-" + destination.name.encode())
        return _completed()

    conformance_transcriber = _PrimaryVoiceMismatchThenExactTranscriber(manifest)
    builder = PM9SourceAssetBuilder(
        manifest,
        project_path=project,
        assets_root=assets_root,
        model_dir=model_dir,
        delivery_base_uri=(
            "https://raw.githubusercontent.com/RayIA007/CIPS/main/"
            "04_PROYECTOS/PROYECTO_PM9_PLANCHA_0001/source_assets"
        ),
        runner=runner,
        fetch_bytes=lambda url: b"\xff\xd8" + (b"x" * 100_001),
        narration_conformance_gate=NarrationConformanceGate(
            NarrationConformancePolicy(enabled=True),
            conformance_transcriber,
            metadata_store=MetadataStore(
                WorkspaceResolver(project.parent, outputs_root)
            ),
        ),
    )

    first = builder.build()
    second = builder.build()

    assert len(first.catalog.entries) == 13
    assert first.generated_count == 13
    assert first.network_called is True
    assert first.reused_existing is False
    assert first.narration_conformance_approved is True
    assert first.conformance_report_path is not None
    assert first.conformance_report_path.is_file()
    assert Path(f"{first.conformance_report_path}.meta.json").is_file()
    assert second.generated_count == 0
    assert second.network_called is False
    assert second.reused_existing is True
    assert second.narration_conformance_approved is True
    assert all(entry.actual_cost_usd == 0 for entry in first.catalog.entries)
    assert all(
        parse_qs(urlsplit(entry.delivery_uri).query).get("content_sha256")
        == [source_assets._sha256_path(first.assets_root / entry.relative_path)]
        for entry in first.catalog.entries
    )
    assert {entry.role for entry in first.catalog.entries} == {
        "scene_visual",
        "scene_narration",
        "music",
        "sound_effect",
    }
    report = json.loads(first.report_path.read_text(encoding="utf-8"))
    assert report["actual_cost_usd"] == 0.0
    assert report["paid_provider_called"] is False
    assert report["publication_performed"] is False
    assert report["delivery_uri_versioning"] == "content_sha256_query_v1"
    assert len(report["files"]) == 13
    assert report["voice"]["model"] == "es_ES-sharvard-medium"
    assert report["voice"]["fallback_used"] is True
    assert report["voice"]["attempted_models"] == [
        "es_MX-claude-high",
        "es_ES-sharvard-medium",
    ]
    conformance = json.loads(first.conformance_report_path.read_text(encoding="utf-8"))
    assert [attempt["approved"] for attempt in conformance["synthesis_attempts"]] == [
        False,
        True,
    ]
    assert conformance["synthesis_voice_id"] == "es_ES-sharvard-medium"
    downloaded_voices = [
        command[command.index("piper.download_voices") + 1]
        for command in calls
        if "piper.download_voices" in command
    ]
    assert downloaded_voices == [
        "es_MX-claude-high",
        "es_ES-sharvard-medium",
    ]
    narration_calls = [
        command
        for command in calls
        if command[0] == sys.executable and command[1:3] == ("-m", "piper")
    ]
    assert narration_calls
    assert all(
        command[command.index("--sentence-silence") + 1] == "0"
        for command in narration_calls
    )
    ffmpeg_filters = [
        command[command.index("-af") + 1]
        for command in calls
        if command[0] == "ffmpeg" and "-af" in command
    ]
    assert any("afade=t=in:st=0:d=0.08" in value for value in ffmpeg_filters)
    assert any("loudnorm=I=-16:TP=-2:LRA=4" in value for value in ffmpeg_filters)

    stale_catalog = first.catalog.model_dump(mode="json")
    for entry in stale_catalog["entries"]:
        entry["delivery_uri"] = entry["delivery_uri"].split("?", 1)[0]
    first.catalog_path.write_text(
        json.dumps(stale_catalog, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    assert builder._reuse_existing() is None

    first_scene = manifest.scenes[0]
    narration_name = f"narration-{first_scene.sequence:03d}.mp3"
    conformance_transcriber.text_by_filename[narration_name] += " desvidan"
    with pytest.raises(SourceAssetBuildError, match="gate acústico bloqueó"):
        builder.build(force=True)
    rejected = json.loads(first.conformance_report_path.read_text(encoding="utf-8"))
    assert rejected["approved"] is False
    assert rejected["render_performed"] is False
    assert len(rejected["synthesis_attempts"]) == 2
    assert all(not attempt["approved"] for attempt in rejected["synthesis_attempts"])


def test_verify_catalog_delivery_compares_exact_bytes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project, outputs_root, manifest = _planned_manifest(tmp_path)
    assets_root = project / "source_assets"
    assets_root.mkdir()
    scene = manifest.scenes[0]
    local = assets_root / "visual" / "hook.mp4"
    local.parent.mkdir()
    local.write_bytes(b"exact-public-bytes")
    catalog = ApprovedAssetCatalog.model_validate(
        {
            "entries": [
                {
                    "entry_id": "hook",
                    "capability": "stock_video_search",
                    "role": "scene_visual",
                    "relative_path": "visual/hook.mp4",
                    "delivery_uri": "https://cdn.example.test/hook.mp4",
                    "mime_type": "video/mp4",
                    "media_family": "video",
                    "file_extension": ".mp4",
                    "scene_id": scene.scene_id,
                    "source_url": "https://commons.example.test/hook",
                    "license_name": "CC BY 2.0",
                    "attribution": "Example",
                    "actual_cost_usd": 0.0,
                }
            ]
        }
    )

    passed = verify_catalog_delivery(
        catalog,
        assets_root=assets_root,
        fetch_bytes=lambda url: b"exact-public-bytes",
    )
    assert passed.verified_count == 1
    assert passed.total_bytes == len(b"exact-public-bytes")
    assert passed.checks[0]["passed"] is True
    assert passed.checks[0]["delivery_uri_content_sha256"] is None
    assert passed.checks[0]["delivery_uri_version_matches"] is True

    stale_catalog = ApprovedAssetCatalog(
        entries=(
            catalog.entries[0].model_copy(
                update={
                    "delivery_uri": (
                        "https://cdn.example.test/hook.mp4?content_sha256=" + "0" * 64
                    )
                }
            ),
        )
    )
    with pytest.raises(SourceAssetBuildError, match="content_sha256"):
        verify_catalog_delivery(
            stale_catalog,
            assets_root=assets_root,
            fetch_bytes=lambda url: b"exact-public-bytes",
        )

    with pytest.raises(SourceAssetBuildError, match="no coincide"):
        verify_catalog_delivery(
            catalog,
            assets_root=assets_root,
            fetch_bytes=lambda url: b"tampered",
        )


def test_procedural_audio_is_physical(tmp_path: Path) -> None:
    audio = tmp_path / "pulse.wav"
    source_assets._write_procedural_audio(audio, 0.05, kind="pulse")
    with wave.open(str(audio), "rb") as stream:
        assert stream.getframerate() == 48_000
        assert stream.getnchannels() == 1
        assert stream.getnframes() == 2_400


def test_build_reports_missing_piper_without_any_media_call(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project, outputs_root, manifest = _planned_manifest(tmp_path)
    monkeypatch.setattr(source_assets.shutil, "which", lambda name: f"/bin/{name}")
    monkeypatch.setattr(source_assets.importlib.util, "find_spec", lambda name: None)
    builder = PM9SourceAssetBuilder(
        manifest,
        project_path=project,
        assets_root=project / "source_assets",
        model_dir=outputs_root / "models",
        delivery_base_uri="https://cdn.example.test/pm9",
        runner=lambda command: pytest.fail("No debe invocarse ningún comando"),
        fetch_bytes=lambda url: pytest.fail("No debe invocarse la red"),
    )

    with pytest.raises(SourceAssetBuildError, match="piper-tts==1.7.0"):
        builder.build()
