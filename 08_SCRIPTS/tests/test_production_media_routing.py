from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

from production_media_router import ProductionMediaRouter
from workspace_resolver import WorkspaceResolver


def _project(tmp_path: Path):
    projects_root = tmp_path / "04_PROYECTOS"
    outputs_root = tmp_path / "05_OUTPUTS"
    project_path = projects_root / "PROYECTO_TEST"
    project_path.mkdir(parents=True)
    return (
        SimpleNamespace(project_id="PROYECTO_TEST", path=project_path),
        WorkspaceResolver(projects_root=projects_root, outputs_root=outputs_root),
    )


def _mp3_bytes() -> bytes:
    return b"ID3\x04\x00\x00\x00\x00\x00\x10" + b"CIPS-AUDIO" * 32


def _png_bytes() -> bytes:
    return b"\x89PNG\r\n\x1a\n" + b"CIPS-IMAGE" * 32


def _mp4_bytes() -> bytes:
    return b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom" + b"CIPS-VIDEO" * 32


def _assert_sidecar(path: Path) -> None:
    sidecar = Path(f"{path}.meta.json")
    assert sidecar.is_file()
    data = json.loads(sidecar.read_text(encoding="utf-8"))
    assert data["content_hash"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert data["size_bytes"] == path.stat().st_size


def test_routes_real_media_and_persists_f3_sidecars(tmp_path: Path) -> None:
    project, resolver = _project(tmp_path)

    def voice_backend(project_path: Path) -> Path:
        path = project_path / "voice" / "audio.mp3"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(_mp3_bytes())
        return path

    def image_backend(project_path: Path) -> list[Path]:
        path = project_path / "images" / "escena_01.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(_png_bytes())
        return [path]

    def video_backend(project_path: Path) -> Path:
        path = project_path / "final" / "short.mp4"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(_mp4_bytes())
        return path

    router = ProductionMediaRouter(
        workspace_resolver=resolver,
        backend_overrides={
            "voz": voice_backend,
            "imagenes": image_backend,
            "ensamblado": video_backend,
        },
    )

    voice = router.execute(project, "voz")
    images = router.execute(project, "imagenes")
    video = router.execute(project, "ensamblado")

    assert voice.success is True
    assert images.success is True
    assert video.success is True

    audio_path = project.path / "voice" / "audio.mp3"
    image_path = project.path / "images" / "escena_01.png"
    raw_video = project.path / "video" / "raw_video.mp4"
    final_video = project.path / "final" / "short.mp4"

    assert audio_path.read_bytes().startswith(b"ID3")
    assert image_path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    assert b"ftyp" in raw_video.read_bytes()[:32]
    assert b"ftyp" in final_video.read_bytes()[:32]

    for path in (audio_path, image_path, raw_video, final_video):
        _assert_sidecar(path)

    subtitles = project.path / "subtitles" / "subtitles.srt"
    subtitles.parent.mkdir(parents=True, exist_ok=True)
    subtitles.write_text("1\n00:00:00,000 --> 00:00:01,000\nCIPS\n", encoding="utf-8")

    quality = router.validate_quality_gate(project)
    assert quality.success is True
    assert quality.metadata["validation_score"] == 100


def test_rejects_text_masquerading_as_mp3(tmp_path: Path) -> None:
    project, resolver = _project(tmp_path)

    def bad_voice_backend(project_path: Path) -> Path:
        path = project_path / "voice" / "audio.mp3"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# RESULTADO\n## Guion de voz", encoding="utf-8")
        return path

    router = ProductionMediaRouter(
        workspace_resolver=resolver,
        backend_overrides={"voz": bad_voice_backend},
    )
    result = router.execute(project, "voz")

    assert result.success is False
    assert any("firma binaria" in error for error in result.errors)
    assert not Path(f"{project.path / 'voice' / 'audio.mp3'}.meta.json").exists()


def test_reuses_valid_media_without_recalling_backend(tmp_path: Path) -> None:
    project, resolver = _project(tmp_path)
    calls = {"voice": 0}

    def voice_backend(project_path: Path) -> Path:
        calls["voice"] += 1
        path = project_path / "voice" / "audio.mp3"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(_mp3_bytes())
        return path

    router = ProductionMediaRouter(
        workspace_resolver=resolver,
        backend_overrides={"voz": voice_backend},
    )

    first = router.execute(project, "voz")
    second = router.execute(project, "voz")

    assert first.success is True
    assert second.success is True
    assert second.reused_existing is True
    assert calls["voice"] == 1


def test_video_stage_blocks_invalid_prerequisites(tmp_path: Path) -> None:
    project, resolver = _project(tmp_path)
    router = ProductionMediaRouter(
        workspace_resolver=resolver,
        backend_overrides={"ensamblado": lambda project_path: project_path / "final" / "short.mp4"},
    )

    result = router.execute(project, "ensamblado")

    assert result.success is False
    assert any("audio" in error.lower() for error in result.errors)
    assert any("imágenes" in error.lower() for error in result.errors)


def test_rejects_text_masquerading_as_mp4(tmp_path: Path) -> None:
    project, resolver = _project(tmp_path)
    audio = project.path / "voice" / "audio.mp3"
    image = project.path / "images" / "escena_01.png"
    audio.parent.mkdir(parents=True, exist_ok=True)
    image.parent.mkdir(parents=True, exist_ok=True)
    audio.write_bytes(_mp3_bytes())
    image.write_bytes(_png_bytes())

    def bad_video_backend(project_path: Path) -> Path:
        path = project_path / "final" / "short.mp4"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# RESULTADO\n## Video final", encoding="utf-8")
        return path

    router = ProductionMediaRouter(
        workspace_resolver=resolver,
        backend_overrides={"ensamblado": bad_video_backend},
    )
    result = router.execute(project, "ensamblado")

    assert result.success is False
    assert any("firma binaria" in error for error in result.errors)
    assert not (project.path / "video" / "raw_video.mp4").exists()


def test_quality_gate_rejects_valid_media_without_f3_sidecars(tmp_path: Path) -> None:
    project, resolver = _project(tmp_path)
    audio = project.path / "voice" / "audio.mp3"
    image = project.path / "images" / "escena_01.png"
    raw_video = project.path / "video" / "raw_video.mp4"
    final_video = project.path / "final" / "short.mp4"
    subtitles = project.path / "subtitles" / "subtitles.srt"

    for path, payload in (
        (audio, _mp3_bytes()),
        (image, _png_bytes()),
        (raw_video, _mp4_bytes()),
        (final_video, _mp4_bytes()),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
    subtitles.parent.mkdir(parents=True, exist_ok=True)
    subtitles.write_text("1\n00:00:00,000 --> 00:00:01,000\nCIPS\n", encoding="utf-8")

    router = ProductionMediaRouter(workspace_resolver=resolver)
    result = router.validate_quality_gate(project)

    assert result.success is False
    assert any("Falta sidecar F3" in error for error in result.errors)

def test_recovers_legacy_text_file_named_images(tmp_path: Path) -> None:
    project, resolver = _project(tmp_path)
    legacy_images = project.path / "images"
    legacy_images.write_text(
        "# RESULTADO\n## Respuesta de imágenes generada por LLM",
        encoding="utf-8",
    )

    def image_backend(project_path: Path) -> list[Path]:
        path = project_path / "images" / "escena_01.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(_png_bytes())
        return [path]

    router = ProductionMediaRouter(
        workspace_resolver=resolver,
        backend_overrides={"imagenes": image_backend},
    )
    result = router.execute(project, "imagenes")

    assert result.success is True
    assert (project.path / "images").is_dir()
    assert (project.path / "images" / "escena_01.png").is_file()
    preserved = list(project.path.glob("images.invalid_legacy_response*.txt"))
    assert len(preserved) == 1
    assert "# RESULTADO" in preserved[0].read_text(encoding="utf-8")




def test_subtitles_are_generated_deterministically_and_invalid_legacy_is_preserved(tmp_path: Path) -> None:
    project, resolver = _project(tmp_path)
    subtitles = project.path / "subtitles" / "subtitles.srt"
    narration = project.path / "narration" / "narration.txt"
    subtitles.parent.mkdir(parents=True, exist_ok=True)
    narration.parent.mkdir(parents=True, exist_ok=True)
    subtitles.write_text("# RESULTADO\nSubtitulos sin timestamps", encoding="utf-8")
    narration.write_text("Una narración válida para la prueba.", encoding="utf-8")

    calls = {"subtitles": 0}

    def subtitle_backend(project_path: Path) -> Path:
        calls["subtitles"] += 1
        path = project_path / "subtitles" / "subtitles.srt"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "1\n00:00:00,000 --> 00:00:02,000\nUna narración válida para la prueba.\n",
            encoding="utf-8",
        )
        return path

    router = ProductionMediaRouter(
        workspace_resolver=resolver,
        backend_overrides={"subtitulos": subtitle_backend},
    )
    result = router.execute(project, "subtitulos")

    assert result.success is True
    assert result.metadata["validation_mode"] == "timed_text"
    assert result.metadata["deterministic_stage"] is True
    assert "-->" in subtitles.read_text(encoding="utf-8")
    assert calls["subtitles"] == 1
    preserved = list((project.path / "subtitles").glob("subtitles.invalid_legacy_response*.txt"))
    assert len(preserved) == 1
    assert "# RESULTADO" in preserved[0].read_text(encoding="utf-8")

    second = router.execute(project, "subtitulos")
    assert second.success is True
    assert second.reused_existing is True
    assert calls["subtitles"] == 1


def test_quality_gate_rejects_malformed_srt_even_if_arrow_is_present(tmp_path: Path) -> None:
    project, resolver = _project(tmp_path)
    subtitles = project.path / "subtitles" / "subtitles.srt"
    subtitles.parent.mkdir(parents=True, exist_ok=True)
    subtitles.write_text("texto --> texto\n", encoding="utf-8")

    router = ProductionMediaRouter(workspace_resolver=resolver)
    errors = router._subtitle_validation_errors(subtitles)

    assert errors
    assert "marcas temporales válidas" in errors[0]
