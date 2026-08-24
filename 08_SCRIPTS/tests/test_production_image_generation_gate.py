from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image


MODULE_PATH = Path(__file__).resolve().parents[2] / "11_MEDIA_PRODUCTION" / "images" / "image_generator.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("cips_image_generator", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def image_generator_module():
    return _load_module()


def _install_fake_subprocess(
    monkeypatch: pytest.MonkeyPatch,
    image_generator_module,
    log_path: Path,
) -> None:
    def fake_run(command, capture_output, text, check):
        args = list(command)
        out = Path(args[args.index("--output") + 1])
        prompt = args[args.index("--prompt") + 1]
        backend = args[args.index("--backend") + 1]
        seed = args[args.index("--seed") + 1]
        width = int(args[args.index("--width") + 1])
        height = int(args[args.index("--height") + 1])

        entries = []
        if log_path.exists():
            entries = json.loads(log_path.read_text(encoding="utf-8"))
        entries.append(
            {
                "prompt": prompt,
                "backend": backend,
                "seed": seed,
                "width": width,
                "height": height,
            }
        )
        log_path.write_text(json.dumps(entries, ensure_ascii=False), encoding="utf-8")
        out.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (width, height), color=(120, 160, 200)).save(out, format="PNG")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(image_generator_module.subprocess, "run", fake_run)


def _write_fake_backend_files(cli_path: Path, model_path: Path) -> None:
    cli_path.parent.mkdir(parents=True, exist_ok=True)
    cli_path.write_bytes(b"fake executable placeholder")
    model_path.parent.mkdir(parents=True, exist_ok=True)
    model_path.write_bytes(b"fake model")


def test_generates_scene_images_from_storyboard(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    image_generator_module,
):
    project_dir = tmp_path / "PROYECTO_0002"
    storyboard_dir = project_dir / "storyboard"
    storyboard_dir.mkdir(parents=True)
    storyboard_dir.joinpath("04_STORYBOARD.md").write_text(
        "# Escena 1\nUna estudiante leyendo en un escritorio moderno.\n\n"
        "# Escena 2\nLa misma estudiante subraya el libro con luz cálida.",
        encoding="utf-8",
    )

    cli_path = tmp_path / "sd-cli.exe"
    model_path = tmp_path / "model.safetensors"
    log_path = tmp_path / "sd_cli_calls.json"
    _write_fake_backend_files(cli_path, model_path)
    _install_fake_subprocess(monkeypatch, image_generator_module, log_path)

    monkeypatch.setenv("CIPS_SDCPP_CLI_PATH", str(cli_path))
    monkeypatch.setenv("CIPS_SDCPP_MODEL_PATH", str(model_path))

    generated = image_generator_module.generar_imagenes_storyboard(project_dir, num_escenas=2)

    assert [path.name for path in generated] == ["escena_01.png", "escena_02.png"]
    for path in generated:
        assert path.is_file()
        with Image.open(path) as image:
            assert image.size == (1080, 1920)
    assert not any(project_dir.joinpath("images").glob("*_raw.png"))

    calls = json.loads(log_path.read_text(encoding="utf-8"))
    assert len(calls) == 2
    assert "Una estudiante leyendo" in calls[0]["prompt"]
    assert "La misma estudiante subraya" in calls[1]["prompt"]
    assert calls[0]["backend"] == "cpu"


def test_preserves_first_scene_when_storyboard_has_utf8_bom(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    image_generator_module,
):
    project_dir = tmp_path / "PROYECTO_0002_BOM"
    storyboard_dir = project_dir / "storyboard"
    storyboard_dir.mkdir(parents=True)
    storyboard_dir.joinpath("04_STORYBOARD.md").write_text(
        "\ufeff# Escena 1\nUna astronauta caminando sobre Marte.\n\n"
        "# Escena 2\nUn submarino amarillo entre corales.\n\n"
        "# Escena 3\nUna ciudad futurista bajo la lluvia.",
        encoding="utf-8",
    )

    cli_path = tmp_path / "sd-cli-bom.exe"
    model_path = tmp_path / "model-bom.safetensors"
    log_path = tmp_path / "sd_cli_bom_calls.json"
    _write_fake_backend_files(cli_path, model_path)
    _install_fake_subprocess(monkeypatch, image_generator_module, log_path)

    monkeypatch.setenv("CIPS_SDCPP_CLI_PATH", str(cli_path))
    monkeypatch.setenv("CIPS_SDCPP_MODEL_PATH", str(model_path))

    generated = image_generator_module.generar_imagenes_storyboard(project_dir, num_escenas=3)

    assert [path.name for path in generated] == [
        "escena_01.png",
        "escena_02.png",
        "escena_03.png",
    ]
    calls = json.loads(log_path.read_text(encoding="utf-8"))
    assert len(calls) == 3
    assert "Una astronauta caminando sobre Marte" in calls[0]["prompt"]
    assert "Un submarino amarillo entre corales" in calls[1]["prompt"]
    assert "Una ciudad futurista bajo la lluvia" in calls[2]["prompt"]


def test_uses_default_repo_locations_when_env_is_absent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    image_generator_module,
):
    project_dir = tmp_path / "repo" / "04_PROYECTOS" / "PROYECTO_0003"
    storyboard_dir = project_dir / "storyboard"
    storyboard_dir.mkdir(parents=True)
    storyboard_dir.joinpath("04_STORYBOARD.md").write_text(
        "Escena 1\nUn escritor frente a una laptop.", encoding="utf-8"
    )

    repo_root = tmp_path / "repo"
    cli_path = repo_root / "stable-diffusion-cpp-win-cpu-x64" / "sd-cli.exe"
    model_path = repo_root / "stable-diffusion-models" / "v1-5-pruned-emaonly.safetensors"
    log_path = tmp_path / "default_calls.json"
    _write_fake_backend_files(cli_path, model_path)
    _install_fake_subprocess(monkeypatch, image_generator_module, log_path)

    monkeypatch.delenv("CIPS_SDCPP_CLI_PATH", raising=False)
    monkeypatch.delenv("CIPS_SDCPP_MODEL_PATH", raising=False)
    monkeypatch.setattr(image_generator_module, "_repo_root", lambda: repo_root)

    generated = image_generator_module.generar_imagenes_storyboard(project_dir, num_escenas=1)

    assert len(generated) == 1
    assert generated[0].is_file()
    calls = json.loads(log_path.read_text(encoding="utf-8"))
    assert calls[0]["width"] == 384
    assert calls[0]["height"] == 640


def test_raises_clear_error_when_cli_is_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    image_generator_module,
):
    project_dir = tmp_path / "PROYECTO_0004"
    storyboard_dir = project_dir / "storyboard"
    storyboard_dir.mkdir(parents=True)
    storyboard_dir.joinpath("04_STORYBOARD.md").write_text(
        "Escena 1\nUn profesor explicando una lección.", encoding="utf-8"
    )
    model_path = tmp_path / "model.safetensors"
    model_path.write_bytes(b"fake model")

    monkeypatch.setenv("CIPS_SDCPP_CLI_PATH", str(tmp_path / "missing-sd-cli.exe"))
    monkeypatch.setenv("CIPS_SDCPP_MODEL_PATH", str(model_path))

    with pytest.raises(FileNotFoundError) as error:
        image_generator_module.generar_imagenes_storyboard(project_dir, num_escenas=1)

    assert "sd-cli.exe" in str(error.value)
