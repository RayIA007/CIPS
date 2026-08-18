from __future__ import annotations

from pathlib import Path

import yaml

from final_project_builder import FinalProjectBuilder
from runtime_constants import STAGE_FILES
from runtime_models import FinalProjectObject, Project


class _ProjectManagerStub:
    def load_project(self, *_args, **_kwargs):
        raise AssertionError("No debe cargarse otro proyecto en esta prueba.")


def _write_text(path: Path, label: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = (f"# {label}\n\nContenido válido del Stage {label}. " * 20).strip()
    path.write_text(body, encoding="utf-8")


def _build_complete_project(root: Path) -> Project:
    (root / "proyecto.yaml").write_text(
        yaml.safe_dump(
            {
                "id": "PROYECTO_TEST",
                "tema": "Tema de prueba",
                "estado": "control_calidad",
                "stage_actual": "control_calidad",
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (root / "memoria.yaml").write_text(
        yaml.safe_dump({"historial": []}, sort_keys=False),
        encoding="utf-8",
    )

    textual_stages = {
        "investigacion",
        "verificacion",
        "guion",
        "storyboard",
        "seo",
        "publicacion",
        "narracion",
        "subtitulos",
        "control_calidad",
    }
    for stage in textual_stages:
        _write_text(root / STAGE_FILES[stage], stage)

    audio = root / STAGE_FILES["voz"]
    audio.parent.mkdir(parents=True, exist_ok=True)
    audio.write_bytes(b"\xff\xfb\x90\x64" + b"A" * 512)

    images = root / STAGE_FILES["imagenes"]
    images.mkdir(parents=True, exist_ok=True)
    (images / "escena_01.png").write_bytes(
        b"\x89PNG\r\n\x1a\n" + b"B" * 256
    )

    video = root / STAGE_FILES["ensamblado"]
    video.parent.mkdir(parents=True, exist_ok=True)
    video.write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"C" * 512)

    return Project(
        project_id="PROYECTO_TEST",
        path=root,
        tema="Tema de prueba",
        estado="control_calidad",
        stage_actual="control_calidad",
    )


def test_builder_does_not_decode_binary_media_as_utf8(tmp_path: Path) -> None:
    project = _build_complete_project(tmp_path)
    builder = FinalProjectBuilder(project_manager=_ProjectManagerStub())

    result = builder.execute(project, require_complete=True)

    assert result.success, result.errors
    assert isinstance(result.data, FinalProjectObject)
    assert result.metadata["missing_stages"] == []

    artifact_outputs = result.data.metadata["artifact_stage_outputs"]
    assert artifact_outputs["voz"]["present"] is True
    assert artifact_outputs["imagenes"]["present"] is True
    assert artifact_outputs["ensamblado"]["present"] is True
    assert result.data.get_stage_content("voz") == ""
    assert result.data.get_stage_content("ensamblado") == ""


def test_builder_reports_missing_media_artifact_without_decoding(tmp_path: Path) -> None:
    project = _build_complete_project(tmp_path)
    (tmp_path / STAGE_FILES["voz"]).unlink()
    builder = FinalProjectBuilder(project_manager=_ProjectManagerStub())

    result = builder.execute(project, require_complete=True)

    assert result.success is False
    assert "voz" in result.metadata["missing_stages"]
    assert any("voz" in error for error in result.errors)
