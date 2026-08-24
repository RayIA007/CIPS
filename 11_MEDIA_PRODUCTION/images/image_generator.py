from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from typing import Iterable

from PIL import Image

DEFAULT_OUTPUT_SIZE = (1080, 1920)
DEFAULT_SAMPLE_SIZE = (384, 640)
DEFAULT_STEPS = 8
DEFAULT_CFG_SCALE = 7.0
DEFAULT_SAMPLING_METHOD = "euler_a"
DEFAULT_NEGATIVE_PROMPT = (
    "blurry, deformed, duplicated person, extra limbs, unreadable text, low quality"
)


def generar_imagenes_storyboard(proyecto_dir: Path, num_escenas: int = 3) -> list[Path]:
    """Generate storyboard-linked scene images through local stable-diffusion.cpp."""

    proyecto_dir = Path(proyecto_dir)
    storyboard_path = proyecto_dir / "storyboard" / "04_STORYBOARD.md"
    if not storyboard_path.is_file():
        raise FileNotFoundError(
            f"Storyboard no encontrado para generación de imágenes: {storyboard_path}"
        )

    scenes = _extract_storyboard_scenes(storyboard_path.read_text(encoding="utf-8"))
    if not scenes:
        raise ValueError("El storyboard no contiene escenas utilizables para generar imágenes.")

    selected_scenes = scenes[: max(1, int(num_escenas or 1))]
    images_dir = proyecto_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    cli_path = _resolve_sd_cli_path()
    model_path = _resolve_model_path()
    backend = os.getenv("CIPS_SDCPP_BACKEND", "cpu").strip() or "cpu"
    threads = int(os.getenv("CIPS_SDCPP_THREADS", "4"))
    sample_width = int(os.getenv("CIPS_SDCPP_WIDTH", str(DEFAULT_SAMPLE_SIZE[0])))
    sample_height = int(os.getenv("CIPS_SDCPP_HEIGHT", str(DEFAULT_SAMPLE_SIZE[1])))
    steps = int(os.getenv("CIPS_SDCPP_STEPS", str(DEFAULT_STEPS)))
    cfg_scale = float(os.getenv("CIPS_SDCPP_CFG_SCALE", str(DEFAULT_CFG_SCALE)))
    sampling_method = (
        os.getenv("CIPS_SDCPP_SAMPLING_METHOD", DEFAULT_SAMPLING_METHOD).strip()
        or DEFAULT_SAMPLING_METHOD
    )
    negative_prompt = os.getenv("CIPS_SDCPP_NEGATIVE_PROMPT", DEFAULT_NEGATIVE_PROMPT).strip()
    prompt_prefix = os.getenv(
        "CIPS_SDCPP_PROMPT_PREFIX",
        "Vertical short-video scene, cinematic framing, coherent subject, detailed, publishable quality.",
    ).strip()
    seed_base = int(os.getenv("CIPS_SDCPP_SEED_BASE", "42"))

    generated_paths: list[Path] = []
    for index, scene_text in enumerate(selected_scenes, start=1):
        raw_output_path = images_dir / f"escena_{index:02d}_raw.png"
        final_output_path = images_dir / f"escena_{index:02d}.png"
        prompt = _compose_prompt(scene_text, prompt_prefix=prompt_prefix)
        command = [
            str(cli_path),
            "--model",
            str(model_path),
            "--backend",
            backend,
            "--threads",
            str(threads),
            "--width",
            str(sample_width),
            "--height",
            str(sample_height),
            "--steps",
            str(steps),
            "--sampling-method",
            sampling_method,
            "--cfg-scale",
            str(cfg_scale),
            "--seed",
            str(seed_base + index - 1),
            "--prompt",
            prompt,
            "--output",
            str(raw_output_path),
        ]
        if negative_prompt:
            command.extend(["--negative-prompt", negative_prompt])

        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode != 0:
            error_text = (completed.stderr or completed.stdout or "").strip()
            raise RuntimeError(
                "stable-diffusion.cpp falló durante la generación de imágenes"
                + (f": {error_text}" if error_text else ".")
            )
        if not raw_output_path.is_file():
            raise RuntimeError(
                f"stable-diffusion.cpp terminó sin producir la imagen esperada: {raw_output_path}"
            )

        _normalize_vertical_image(raw_output_path, final_output_path)
        raw_output_path.unlink(missing_ok=True)
        generated_paths.append(final_output_path)

    return generated_paths


def _extract_storyboard_scenes(storyboard_text: str) -> list[str]:
    lines = [line.rstrip() for line in storyboard_text.splitlines()]
    blocks: list[list[str]] = []
    current: list[str] = []
    heading_pattern = re.compile(r"^\s{0,3}#{1,6}\s*(escena|scene)\b", re.IGNORECASE)
    label_pattern = re.compile(r"^\s*(escena|scene)\s*\d+\b", re.IGNORECASE)

    for line in lines:
        stripped = _strip_bom(line.strip())
        if not stripped:
            if current:
                current.append("")
            continue
        if heading_pattern.match(stripped) or label_pattern.match(stripped):
            if current:
                blocks.append(current)
                current = []
            current.append(stripped)
            continue
        if current:
            current.append(stripped)

    if current:
        blocks.append(current)

    if blocks:
        normalized = [
            _clean_scene_text("\n".join(chunk))
            for chunk in blocks
            if _clean_scene_text("\n".join(chunk))
        ]
        if normalized:
            return normalized

    fallback = _clean_scene_text(storyboard_text)
    return [fallback] if fallback else []


def _clean_scene_text(scene_text: str) -> str:
    cleaned_lines = []
    for line in scene_text.splitlines():
        stripped = _strip_bom(line.strip())
        if not stripped:
            continue
        stripped = re.sub(r"^[#\-*\d.\)\s]+", "", stripped)
        cleaned_lines.append(stripped)
    return " ".join(cleaned_lines).strip()


def _strip_bom(text: str) -> str:
    return text.lstrip("\ufeff")


def _compose_prompt(scene_text: str, *, prompt_prefix: str) -> str:
    parts = [prompt_prefix.strip(), scene_text.strip(), "Vertical 9:16 composition."]
    return " ".join(part for part in parts if part)


def _normalize_vertical_image(source_path: Path, target_path: Path) -> None:
    with Image.open(source_path) as image:
        normalized = image.convert("RGB").resize(DEFAULT_OUTPUT_SIZE, Image.LANCZOS)
        normalized.save(target_path, format="PNG")


def _resolve_sd_cli_path() -> Path:
    candidate = os.getenv("CIPS_SDCPP_CLI_PATH", "").strip()
    if candidate:
        explicit = Path(candidate)
        if not explicit.is_file():
            raise FileNotFoundError(
                f"No se encontró sd-cli.exe de stable-diffusion.cpp: {explicit}"
            )
        return explicit

    repo_root = _repo_root()
    return _first_existing_file(
        [
            repo_root / "stable-diffusion-cpp-win-cpu-x64" / "sd-cli.exe",
            repo_root / "stable-diffusion-cpp-win-vulkan-x64" / "sd-cli.exe",
            repo_root / "stable-diffusion-cpp" / "sd-cli.exe",
        ],
        "sd-cli.exe de stable-diffusion.cpp",
    )


def _resolve_model_path() -> Path:
    candidate = os.getenv("CIPS_SDCPP_MODEL_PATH", "").strip()
    if candidate:
        explicit = Path(candidate)
        if not explicit.is_file():
            raise FileNotFoundError(
                f"No se encontró modelo local de stable-diffusion.cpp: {explicit}"
            )
        return explicit

    repo_root = _repo_root()
    return _first_existing_file(
        [
            repo_root / "stable-diffusion-models" / "v1-5-pruned-emaonly.safetensors",
            repo_root / "stable-diffusion-models" / "model.safetensors",
            repo_root / "stable-diffusion-models" / "model.gguf",
        ],
        "modelo local de stable-diffusion.cpp",
    )


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _first_existing_file(candidates: Iterable[Path], label: str) -> Path:
    for candidate in candidates:
        candidate = Path(candidate)
        if candidate.is_file():
            return candidate
    searched = "\n".join(f"- {Path(path)}" for path in candidates)
    raise FileNotFoundError(f"No se encontró {label}. Rutas revisadas:\n{searched}")
