"""Build and verify zero-cost physical source assets used by PM9.

The builder deliberately keeps media acquisition separate from render
providers.  Local Piper speech and procedural audio work for any compatible
manifest.  The original plank-project visual recipe remains available only for
that legacy acceptance fixture; fresh projects leave ``stock_image`` requests
to the PM8 visual-fulfillment boundary instead of depending on curated files.
The generated catalog contains stable public HTTPS delivery locations but
never uploads or publishes anything itself.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import shutil
import struct
import subprocess
import sys
import tempfile
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen

from production_manifest import AssetType, ProductionManifest

from .catalog import ApprovedAssetCatalog, CatalogEntry


PIPER_PACKAGE_VERSION = "1.7.0"
PIPER_VOICE_ID = "es_MX-claude-high"
PIPER_SENTENCE_SILENCE_SECONDS = 0.0
PIPER_MODEL_CARD_URL = (
    "https://huggingface.co/rhasspy/piper-voices/blob/main/"
    "es/es_MX/claude/high/MODEL_CARD"
)
WIKIMEDIA_FILE_PAGE = (
    "https://commons.wikimedia.org/wiki/"
    "File:Fitness_enthusiast_performs_plank_exercise_at_home_on_yoga_mat.jpg"
)
WIKIMEDIA_PHOTO_URL = (
    "https://upload.wikimedia.org/wikipedia/commons/thumb/f/fc/"
    "Fitness_enthusiast_performs_plank_exercise_at_home_on_yoga_mat.jpg/"
    "1280px-Fitness_enthusiast_performs_plank_exercise_at_home_on_yoga_mat.jpg"
)
WIKIMEDIA_LICENSE_URL = "https://creativecommons.org/licenses/by/2.0/"
CATALOG_FILENAME = "asset_catalog.json"
BUILD_REPORT_FILENAME = "asset_build_report.json"
VERIFY_REPORT_RELATIVE_PATH = Path("acceptance") / "asset_delivery_verification.json"


class SourceAssetBuildError(RuntimeError):
    """A prerequisite or physical source-asset build step failed."""


@dataclass(frozen=True, slots=True)
class SourceAssetBuildResult:
    """Durable output of one local source-asset build."""

    catalog: ApprovedAssetCatalog
    catalog_path: Path
    report_path: Path
    assets_root: Path
    delivery_base_uri: str
    generated_count: int
    reused_existing: bool
    network_called: bool


@dataclass(frozen=True, slots=True)
class DeliveryVerificationResult:
    """Byte-for-byte comparison of public URLs with local catalog assets."""

    verified_count: int
    total_bytes: int
    checks: tuple[dict[str, Any], ...]


CommandRunner = Callable[[Sequence[str]], subprocess.CompletedProcess[str]]
ByteFetcher = Callable[[str], bytes]


class PM9SourceAssetBuilder:
    """Create local zero-cost assets without paid provider calls.

    A fresh project whose visuals are all ``stock_image`` receives an
    audio-only seed catalog.  PM9.1 then fulfills the missing scene visuals
    through provider-neutral PM8 resolution.  The exact historical plank
    profile is retained so its already-closed acceptance path remains stable.
    """

    def __init__(
        self,
        manifest: ProductionManifest,
        *,
        project_path: str | Path,
        assets_root: str | Path,
        model_dir: str | Path,
        delivery_base_uri: str,
        runner: CommandRunner | None = None,
        fetch_bytes: ByteFetcher | None = None,
        python_executable: str | Path | None = None,
    ) -> None:
        if not isinstance(manifest, ProductionManifest):
            raise TypeError("manifest debe ser ProductionManifest.")
        self.manifest = manifest
        self.project_path = Path(project_path).expanduser().resolve(strict=False)
        self.assets_root = Path(assets_root).expanduser().resolve(strict=False)
        self.model_dir = Path(model_dir).expanduser().resolve(strict=False)
        self.delivery_base_uri = _public_base_uri(delivery_base_uri)
        self.runner = runner or _run_command
        self.fetch_bytes = fetch_bytes or _fetch_public_bytes
        self.python_executable = str(python_executable or sys.executable)
        try:
            self.assets_root.relative_to(self.project_path)
        except ValueError as error:
            raise ValueError("assets_root debe permanecer dentro del proyecto.") from error

    def build(self, *, force: bool = False) -> SourceAssetBuildResult:
        """Build all media and write a strict catalog plus provenance report."""

        existing = self._reuse_existing()
        if existing is not None and not force:
            return existing
        legacy_visuals = self._uses_legacy_plank_visuals()
        self._preflight()
        self.assets_root.mkdir(parents=True, exist_ok=True)
        self.model_dir.mkdir(parents=True, exist_ok=True)

        with tempfile.TemporaryDirectory(prefix="cips-pm9-assets-") as temp_name:
            temp = Path(temp_name)
            files: dict[str, Path] = {}
            photo_bytes: bytes | None = None
            if legacy_visuals:
                photo_path = temp / "plank-source.jpg"
                photo_bytes = self.fetch_bytes(WIKIMEDIA_PHOTO_URL)
                if len(photo_bytes) < 100_000 or not photo_bytes.startswith(
                    b"\xff\xd8"
                ):
                    raise SourceAssetBuildError(
                        "Wikimedia no devolvió la fotografía JPEG PM9 esperada."
                    )
                photo_path.write_bytes(photo_bytes)
                files["scene_visual_1"] = self._build_hook_video(photo_path)
                files["scene_visual_2"] = self._curated_visual(
                    "visual/scene-002-biomedical-v2.png",
                )
                files["scene_visual_3"] = self._curated_visual(
                    "visual/scene-003-motor-units-v2.png",
                )
                files["scene_visual_4"] = self._curated_visual(
                    "visual/scene-004-aligned-plank-v2.png",
                )

            voice_model_cached = self._voice_model_is_cached()
            model_path = self._ensure_voice_model()
            for scene in self.manifest.scenes:
                if scene.narration_text is None:
                    continue
                files[f"narration_{scene.sequence}"] = self._build_narration(
                    scene.narration_text,
                    scene.duration_seconds,
                    model_path=model_path,
                    temporary_root=temp,
                    sequence=scene.sequence,
                )

            if self.manifest.audio_design.music is not None:
                files["music"] = self._build_music(temp)
            for index, effect in enumerate(self.manifest.audio_design.sound_effects):
                files[f"sfx_{effect.cue_id}"] = self._build_sound_effect(
                    effect.cue_id,
                    effect.duration_seconds or 0.5,
                    kind=(
                        "whoosh"
                        if index == 0
                        else "impact"
                        if index == len(self.manifest.audio_design.sound_effects) - 1
                        else "pulse"
                    ),
                    temporary_root=temp,
                )

        catalog = self._catalog(files, include_legacy_visuals=legacy_visuals)
        catalog_path = self.assets_root / CATALOG_FILENAME
        _write_json_atomic(
            catalog_path,
            catalog.model_dump(mode="json"),
        )
        report_path = self.assets_root / BUILD_REPORT_FILENAME
        report = self._build_report(
            catalog,
            files,
            photo_bytes,
            include_legacy_visuals=legacy_visuals,
        )
        _write_json_atomic(report_path, report)
        return SourceAssetBuildResult(
            catalog=catalog,
            catalog_path=catalog_path,
            report_path=report_path,
            assets_root=self.assets_root,
            delivery_base_uri=self.delivery_base_uri,
            generated_count=len(catalog.entries),
            reused_existing=False,
            network_called=legacy_visuals or not voice_model_cached,
        )

    def _preflight(self) -> None:
        missing = [name for name in ("ffmpeg", "ffprobe") if shutil.which(name) is None]
        if missing:
            raise SourceAssetBuildError(
                "Faltan ejecutables multimedia requeridos: " + ", ".join(missing) + "."
            )
        if importlib.util.find_spec("piper") is None:
            raise SourceAssetBuildError(
                "Falta Piper TTS. Instala la dependencia local aprobada con: "
                f"python -m pip install piper-tts=={PIPER_PACKAGE_VERSION}"
            )

    def _reuse_existing(self) -> SourceAssetBuildResult | None:
        catalog_path = self.assets_root / CATALOG_FILENAME
        report_path = self.assets_root / BUILD_REPORT_FILENAME
        if not catalog_path.is_file() or not report_path.is_file():
            return None
        try:
            catalog = ApprovedAssetCatalog.load(catalog_path)
            report = json.loads(report_path.read_text(encoding="utf-8"))
            if (
                report.get("manifest_id") != self.manifest.manifest_id
                or report.get("delivery_base_uri") != self.delivery_base_uri
                or len(catalog.entries) != self._expected_local_entry_count()
                or not isinstance(report.get("voice"), Mapping)
                or report["voice"].get("sentence_silence_seconds")
                != PIPER_SENTENCE_SILENCE_SECONDS
            ):
                return None
            for entry in catalog.entries:
                path = (self.assets_root / entry.relative_path).resolve(strict=False)
                path.relative_to(self.assets_root)
                if not path.is_file() or path.stat().st_size <= 0:
                    return None
                expected = report["files"][entry.entry_id]["sha256"]
                if _sha256_path(path) != expected:
                    return None
        except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError):
            return None
        return SourceAssetBuildResult(
            catalog=catalog,
            catalog_path=catalog_path,
            report_path=report_path,
            assets_root=self.assets_root,
            delivery_base_uri=self.delivery_base_uri,
            generated_count=0,
            reused_existing=True,
            network_called=False,
        )

    def _build_hook_video(self, photo_path: Path) -> Path:
        destination = self.assets_root / "visual" / "scene-001-plank-hook.mp4"
        destination.parent.mkdir(parents=True, exist_ok=True)
        duration = self.manifest.scenes[0].duration_seconds
        filter_graph = (
            "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,"
            "crop=1080:1920,gblur=sigma=38,eq=brightness=-0.22:saturation=0.85[bg];"
            "[0:v]scale=1080:-2[fg];"
            "[bg][fg]overlay=x='(W-w)/2+2*sin(19*t)':"
            "y='(H-h)/2+2*sin(23*t)',format=yuv420p[outv]"
        )
        self.runner(
            (
                "ffmpeg",
                "-nostdin",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-loop",
                "1",
                "-framerate",
                str(int(self.manifest.output.fps)),
                "-i",
                str(photo_path),
                "-filter_complex",
                filter_graph,
                "-map",
                "[outv]",
                "-t",
                _decimal(duration),
                "-an",
                "-c:v",
                "libx264",
                "-preset",
                "medium",
                "-crf",
                "21",
                "-movflags",
                "+faststart",
                str(destination),
            )
        )
        _require_nonempty(destination, "video de hook")
        return destination

    def _uses_legacy_plank_visuals(self) -> bool:
        """Identify only the historical PM9 plank recipe.

        Other visual mixes are rejected rather than silently receiving assets
        whose content, provenance, or scene identity does not match.
        """

        types = tuple(scene.asset_request.asset_type for scene in self.manifest.scenes)
        if all(asset_type is AssetType.STOCK_IMAGE for asset_type in types):
            return False
        legacy = (
            AssetType.STOCK_VIDEO,
            AssetType.AI_IMAGE,
            AssetType.AI_IMAGE,
            AssetType.EXISTING_ASSET,
        )
        if (
            self.manifest.project.project_id == "PROYECTO_PM9_PLANCHA_0001"
            and types == legacy
        ):
            return True
        raise SourceAssetBuildError(
            "El builder local sólo admite visuales stock_image para proyectos "
            "nuevos; otros visuales deben resolverse mediante PM8."
        )

    def _expected_local_entry_count(self) -> int:
        legacy_visual_count = 4 if self._uses_legacy_plank_visuals() else 0
        narration_count = sum(
            scene.narration_text is not None for scene in self.manifest.scenes
        )
        music_count = int(self.manifest.audio_design.music is not None)
        return (
            legacy_visual_count
            + narration_count
            + music_count
            + len(self.manifest.audio_design.sound_effects)
        )

    def _curated_visual(self, relative_path: str) -> Path:
        destination = (self.assets_root / relative_path).resolve(strict=False)
        try:
            destination.relative_to(self.assets_root)
        except ValueError as error:
            raise SourceAssetBuildError(
                "La ruta del visual curado escapa de assets_root."
            ) from error
        _require_nonempty(destination, "visual científico curado PM9")
        if destination.suffix.lower() != ".png":
            raise SourceAssetBuildError(
                f"El visual curado debe ser PNG: {destination.name}."
            )
        return destination

    def _ensure_voice_model(self) -> Path:
        model_path = self.model_dir / f"{PIPER_VOICE_ID}.onnx"
        config_path = self.model_dir / f"{PIPER_VOICE_ID}.onnx.json"
        if model_path.is_file() and config_path.is_file():
            return model_path
        self.runner(
            (
                self.python_executable,
                "-m",
                "piper.download_voices",
                PIPER_VOICE_ID,
                "--data-dir",
                str(self.model_dir),
            )
        )
        _require_nonempty(model_path, "modelo de voz Piper")
        _require_nonempty(config_path, "configuración de voz Piper")
        return model_path

    def _voice_model_is_cached(self) -> bool:
        return (
            (self.model_dir / f"{PIPER_VOICE_ID}.onnx").is_file()
            and (self.model_dir / f"{PIPER_VOICE_ID}.onnx.json").is_file()
        )

    def _build_narration(
        self,
        text: str,
        duration_seconds: float,
        *,
        model_path: Path,
        temporary_root: Path,
        sequence: int,
    ) -> Path:
        raw_path = temporary_root / f"narration-{sequence:03d}-raw.wav"
        destination = self.assets_root / "audio" / f"narration-{sequence:03d}.mp3"
        destination.parent.mkdir(parents=True, exist_ok=True)
        self.runner(
            (
                self.python_executable,
                "-m",
                "piper",
                "-m",
                str(model_path),
                "-f",
                str(raw_path),
                "--sentence-silence",
                _decimal(PIPER_SENTENCE_SILENCE_SECONDS),
                "--",
                text,
            )
        )
        _require_nonempty(raw_path, f"narración {sequence}")
        raw_duration = _probe_duration(raw_path, runner=self.runner)
        target = max(0.5, duration_seconds - 0.18)
        tempo = raw_duration / target
        if tempo > 1.38:
            raise SourceAssetBuildError(
                f"La narración {sequence} requeriría una aceleración excesiva "
                f"({tempo:.2f}x); ajusta el guion o la duración."
            )
        filters = ["highpass=f=75", "lowpass=f=11500"]
        if tempo > 1.0:
            filters.extend(_atempo_filters(tempo))
        filters.extend(
            (
                "loudnorm=I=-16:TP=-1.5:LRA=7",
                "apad",
                f"atrim=duration={_decimal(target)}",
            )
        )
        self._encode_mp3(raw_path, destination, filters=filters)
        return destination

    def _build_music(self, temporary_root: Path) -> Path:
        duration = self.manifest.output.duration_seconds
        raw_path = temporary_root / "background-music.wav"
        _write_procedural_audio(raw_path, duration, kind="music")
        destination = self.assets_root / "audio" / "background-music.mp3"
        destination.parent.mkdir(parents=True, exist_ok=True)
        self._encode_mp3(
            raw_path,
            destination,
            filters=(
                "highpass=f=45",
                "lowpass=f=9000",
                "loudnorm=I=-16.5:TP=-2:LRA=5",
                "afade=t=in:st=0:d=0.08",
                f"afade=t=out:st={_decimal(max(0.0, duration - 0.7))}:d=0.7",
            ),
        )
        return destination

    def _build_sound_effect(
        self,
        cue_id: str,
        duration_seconds: float,
        *,
        kind: str,
        temporary_root: Path,
    ) -> Path:
        raw_path = temporary_root / f"{cue_id}.wav"
        _write_procedural_audio(raw_path, duration_seconds, kind=kind)
        destination = self.assets_root / "audio" / f"{cue_id}.mp3"
        destination.parent.mkdir(parents=True, exist_ok=True)
        self._encode_mp3(
            raw_path,
            destination,
            filters=("highpass=f=45", "loudnorm=I=-16:TP=-2:LRA=4"),
        )
        return destination

    def _encode_mp3(
        self,
        source: Path,
        destination: Path,
        *,
        filters: Iterable[str],
    ) -> None:
        self.runner(
            (
                "ffmpeg",
                "-nostdin",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-i",
                str(source),
                "-af",
                ",".join(filters),
                "-ar",
                "48000",
                "-ac",
                "1",
                "-c:a",
                "libmp3lame",
                "-b:a",
                "128k",
                str(destination),
            )
        )
        _require_nonempty(destination, destination.name)

    def _catalog(
        self,
        files: Mapping[str, Path],
        *,
        include_legacy_visuals: bool,
    ) -> ApprovedAssetCatalog:
        scenes = {scene.sequence: scene for scene in self.manifest.scenes}
        entries: list[CatalogEntry] = []
        if include_legacy_visuals:
            entries.extend(
                [
                    self._entry(
                        entry_id="scene-001-plank-hook",
                        capability="stock_video_search",
                        role="scene_visual",
                        path=files["scene_visual_1"],
                        mime_type="video/mp4",
                        media_family="video",
                        scene_id=scenes[1].scene_id,
                        source_url=WIKIMEDIA_FILE_PAGE,
                        license_name=(
                            "Creative Commons Attribution 2.0 Generic (CC BY 2.0)"
                        ),
                        attribution=(
                            "Fotografía: Shixart1985, Wikimedia Commons, CC BY 2.0; "
                            "adaptada a video vertical con fondo, recorte y movimiento. "
                            f"Licencia: {WIKIMEDIA_LICENSE_URL}"
                        ),
                    ),
                    self._entry(
                        entry_id="scene-002-biomedical",
                        capability="image_generation",
                        role="scene_visual",
                        path=files["scene_visual_2"],
                        mime_type="image/png",
                        media_family="image",
                        scene_id=scenes[2].scene_id,
                        source_url=self._project_source_url(files["scene_visual_2"]),
                        license_name="Original CIPS commissioned AI artwork",
                        attribution=(
                            "Visual científico original generado para CIPS con OpenAI "
                            "ImageGen; sin texto, logotipos ni marcas de agua."
                        ),
                    ),
                    self._entry(
                        entry_id="scene-003-motor-units",
                        capability="image_generation",
                        role="scene_visual",
                        path=files["scene_visual_3"],
                        mime_type="image/png",
                        media_family="image",
                        scene_id=scenes[3].scene_id,
                        source_url=self._project_source_url(files["scene_visual_3"]),
                        license_name="Original CIPS commissioned AI artwork",
                        attribution=(
                            "Visual científico original generado para CIPS con OpenAI "
                            "ImageGen; sin texto, logotipos ni marcas de agua."
                        ),
                    ),
                    self._entry(
                        entry_id="scene-004-aligned-plank",
                        capability="existing_asset_resolution",
                        role="scene_visual",
                        path=files["scene_visual_4"],
                        mime_type="image/png",
                        media_family="image",
                        scene_id=scenes[4].scene_id,
                        existing_asset_id="aligned-plank",
                        source_url=self._project_source_url(files["scene_visual_4"]),
                        license_name="Original CIPS commissioned AI artwork",
                        attribution=(
                            "Fotografía deportiva sintética original generada para CIPS "
                            "con OpenAI ImageGen; sin texto, logotipos ni marcas de agua."
                        ),
                    ),
                ]
            )
        for scene in self.manifest.scenes:
            if scene.narration_text is None:
                continue
            entries.append(
                self._entry(
                    entry_id=f"narration-{scene.sequence:03d}",
                    capability="voice_synthesis",
                    role="scene_narration",
                    path=files[f"narration_{scene.sequence}"],
                    mime_type="audio/mpeg",
                    media_family="audio",
                    scene_id=scene.scene_id,
                    source_url=PIPER_MODEL_CARD_URL,
                    license_name=(
                        "Piper es_MX-claude-high generated speech "
                        "(dataset Apache-2.0)"
                    ),
                    attribution=(
                        "Voz sintetizada localmente con Piper y el modelo "
                        "es_MX-claude-high (español de México)."
                    ),
                )
            )
        if self.manifest.audio_design.music is not None:
            entries.append(
                self._entry(
                    entry_id="background-music",
                    capability="music_generation",
                    role="music",
                    path=files["music"],
                    mime_type="audio/mpeg",
                    media_family="audio",
                    source_url=self._project_source_url(files["music"]),
                    license_name="Original CIPS procedural audio",
                    attribution=(
                        "Música instrumental original sintetizada localmente por CIPS."
                    ),
                )
            )
        for effect in self.manifest.audio_design.sound_effects:
            entries.append(
                self._entry(
                    entry_id=effect.cue_id,
                    capability="sound_effect_generation",
                    role="sound_effect",
                    path=files[f"sfx_{effect.cue_id}"],
                    mime_type="audio/mpeg",
                    media_family="audio",
                    cue_id=effect.cue_id,
                    source_url=self._project_source_url(files[f"sfx_{effect.cue_id}"]),
                    license_name="Original CIPS procedural audio",
                    attribution="Efecto sonoro original sintetizado localmente por CIPS.",
                )
            )
        expected = self._expected_local_entry_count()
        if len(entries) != expected:
            raise SourceAssetBuildError(
                "El catálogo local no coincide con el manifest: "
                f"se esperaban {expected} entradas y se obtuvieron {len(entries)}."
            )
        return ApprovedAssetCatalog(entries=tuple(entries))

    def _entry(
        self,
        *,
        entry_id: str,
        capability: str,
        role: str,
        path: Path,
        mime_type: str,
        media_family: str,
        source_url: str,
        license_name: str,
        attribution: str,
        scene_id: str | None = None,
        cue_id: str | None = None,
        existing_asset_id: str | None = None,
    ) -> CatalogEntry:
        relative = path.resolve(strict=False).relative_to(self.assets_root).as_posix()
        return CatalogEntry(
            entry_id=entry_id,
            capability=capability,
            role=role,
            relative_path=relative,
            delivery_uri=f"{self.delivery_base_uri}/{_quote_path(relative)}",
            mime_type=mime_type,
            media_family=media_family,
            file_extension=path.suffix.lower(),
            scene_id=scene_id,
            cue_id=cue_id,
            existing_asset_id=existing_asset_id,
            source_url=source_url,
            license_name=license_name,
            attribution=attribution,
            actual_cost_usd=0.0,
        )

    def _project_source_url(self, path: Path) -> str:
        relative = path.resolve(strict=False).relative_to(self.assets_root).as_posix()
        return f"{self.delivery_base_uri}/{_quote_path(relative)}"

    def _build_report(
        self,
        catalog: ApprovedAssetCatalog,
        files: Mapping[str, Path],
        photo_bytes: bytes | None,
        *,
        include_legacy_visuals: bool,
    ) -> dict[str, Any]:
        del files
        report: dict[str, Any] = {
            "schema_name": "cips.production_acceptance.asset_build_report",
            "schema_version": "1.0",
            "manifest_id": self.manifest.manifest_id,
            "project_id": self.manifest.project.project_id,
            "build_profile": (
                "legacy_plank_complete"
                if include_legacy_visuals
                else "generic_audio_seed"
            ),
            "catalog_entry_count": len(catalog.entries),
            "delivery_base_uri": self.delivery_base_uri,
            "actual_cost_usd": 0.0,
            "paid_provider_called": False,
            "publication_performed": False,
            "network_sources": (
                [WIKIMEDIA_PHOTO_URL, PIPER_MODEL_CARD_URL]
                if include_legacy_visuals
                else [PIPER_MODEL_CARD_URL]
            ),
            "voice": {
                "engine": "Piper",
                "package_version": PIPER_PACKAGE_VERSION,
                "model": PIPER_VOICE_ID,
                "locale": "es-MX",
                "sentence_silence_seconds": PIPER_SENTENCE_SILENCE_SECONDS,
                "model_card_url": PIPER_MODEL_CARD_URL,
                "dataset_license": "Apache-2.0",
            },
            "files": {
                entry.entry_id: {
                    "relative_path": entry.relative_path,
                    "sha256": _sha256_path(self.assets_root / entry.relative_path),
                    "size_bytes": (self.assets_root / entry.relative_path).stat().st_size,
                    "delivery_uri": entry.delivery_uri,
                    "license_name": entry.license_name,
                    "attribution": entry.attribution,
                }
                for entry in catalog.entries
            },
        }
        if photo_bytes is not None:
            report["source_photo_sha256"] = hashlib.sha256(photo_bytes).hexdigest()
        return report


def verify_catalog_delivery(
    catalog: ApprovedAssetCatalog,
    *,
    assets_root: str | Path,
    fetch_bytes: ByteFetcher | None = None,
) -> DeliveryVerificationResult:
    """Fetch every public delivery URI and compare it with its local bytes."""

    if not isinstance(catalog, ApprovedAssetCatalog):
        raise TypeError("catalog debe ser ApprovedAssetCatalog.")
    root = Path(assets_root).expanduser().resolve(strict=False)
    fetch = fetch_bytes or _fetch_public_bytes
    checks: list[dict[str, Any]] = []
    total_bytes = 0
    for entry in catalog.entries:
        local_path = (root / entry.relative_path).resolve(strict=False)
        try:
            local_path.relative_to(root)
        except ValueError as error:
            raise SourceAssetBuildError(
                f"La entrada {entry.entry_id} escapa de assets_root."
            ) from error
        local = local_path.read_bytes()
        remote = fetch(entry.delivery_uri)
        local_sha = hashlib.sha256(local).hexdigest()
        remote_sha = hashlib.sha256(remote).hexdigest()
        passed = bool(local) and local_sha == remote_sha
        checks.append(
            {
                "entry_id": entry.entry_id,
                "delivery_uri": entry.delivery_uri,
                "size_bytes": len(remote),
                "local_sha256": local_sha,
                "remote_sha256": remote_sha,
                "passed": passed,
            }
        )
        if not passed:
            raise SourceAssetBuildError(
                f"El asset público {entry.entry_id} no coincide con el archivo local."
            )
        total_bytes += len(remote)
    return DeliveryVerificationResult(
        verified_count=len(checks),
        total_bytes=total_bytes,
        checks=tuple(checks),
    )


def derive_github_raw_base(
    project_path: str | Path,
    assets_root: str | Path,
    *,
    runner: CommandRunner | None = None,
) -> str:
    """Derive a raw.githubusercontent.com base from the checked-out origin."""

    project = Path(project_path).expanduser().resolve(strict=False)
    assets = Path(assets_root).expanduser().resolve(strict=False)
    repository = _repository_root(project)
    run = runner or _run_command
    remote = run(
        ("git", "-C", str(repository), "remote", "get-url", "origin")
    ).stdout.strip()
    branch = run(
        ("git", "-C", str(repository), "branch", "--show-current")
    ).stdout.strip()
    owner_repo = _github_owner_repo(remote)
    if not branch:
        raise SourceAssetBuildError(
            "No se pudo derivar la rama Git; usa --delivery-base explícitamente."
        )
    try:
        relative = assets.relative_to(repository).as_posix()
    except ValueError as error:
        raise SourceAssetBuildError(
            "assets_root debe estar dentro del repositorio para derivar su URL pública."
        ) from error
    return _public_base_uri(
        f"https://raw.githubusercontent.com/{owner_repo}/"
        f"{quote(branch, safe='')}/{_quote_path(relative)}"
    )


def _github_owner_repo(remote: str) -> str:
    normalized = remote.strip()
    if normalized.startswith("git@github.com:"):
        path = normalized.removeprefix("git@github.com:")
    else:
        parsed = urlsplit(normalized)
        if parsed.hostname not in {"github.com", "www.github.com"}:
            raise SourceAssetBuildError(
                "origin no apunta a GitHub; usa --delivery-base explícitamente."
            )
        path = parsed.path.lstrip("/")
    path = path.removesuffix(".git").strip("/")
    parts = path.split("/")
    if len(parts) != 2 or not all(parts):
        raise SourceAssetBuildError(
            "No se pudo interpretar owner/repository desde origin."
        )
    return "/".join(quote(part, safe="") for part in parts)


def _repository_root(path: Path) -> Path:
    for candidate in (path, *path.parents):
        if (candidate / ".git").exists():
            return candidate
    raise SourceAssetBuildError("No se encontró la raíz Git del proyecto.")


def _public_base_uri(value: str) -> str:
    normalized = str(value).strip().rstrip("/")
    parsed = urlsplit(normalized)
    if (
        parsed.scheme.lower() != "https"
        or not parsed.netloc
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("delivery_base_uri debe ser HTTPS pública, estable y sin query.")
    return normalized


def _quote_path(value: str) -> str:
    return "/".join(quote(part, safe="") for part in Path(value).as_posix().split("/"))


def _fetch_public_bytes(url: str) -> bytes:
    request = Request(
        url,
        headers={"User-Agent": "CIPS-PM9-Production-Acceptance/1.0"},
    )
    with urlopen(request, timeout=45) as response:  # noqa: S310 - fixed/validated HTTPS
        final = urlsplit(response.geturl())
        if final.scheme.lower() != "https" or not final.netloc:
            raise SourceAssetBuildError("La descarga pública redirigió fuera de HTTPS.")
        return response.read()


def _run_command(command: Sequence[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            list(command),
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except FileNotFoundError as error:
        raise SourceAssetBuildError(
            f"No se encontró el ejecutable requerido: {command[0]}."
        ) from error
    except subprocess.CalledProcessError as error:
        detail = (error.stderr or error.stdout or "sin detalle").strip()
        raise SourceAssetBuildError(
            f"Falló {command[0]} (código {error.returncode}): {detail[-1200:]}"
        ) from error


def _probe_duration(path: Path, *, runner: CommandRunner) -> float:
    completed = runner(
        (
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        )
    )
    try:
        duration = float(completed.stdout.strip())
    except (TypeError, ValueError) as error:
        raise SourceAssetBuildError(f"ffprobe no pudo medir {path.name}.") from error
    if not math.isfinite(duration) or duration <= 0:
        raise SourceAssetBuildError(f"Duración inválida para {path.name}.")
    return duration


def _atempo_filters(value: float) -> tuple[str, ...]:
    if not math.isfinite(value) or value <= 0:
        raise ValueError("atempo requiere un factor positivo y finito.")
    factors: list[float] = []
    remaining = value
    while remaining > 2.0:
        factors.append(2.0)
        remaining /= 2.0
    while remaining < 0.5:
        factors.append(0.5)
        remaining /= 0.5
    factors.append(remaining)
    return tuple(f"atempo={factor:.8f}" for factor in factors)


def _write_procedural_audio(path: Path, duration_seconds: float, *, kind: str) -> None:
    sample_rate = 48_000
    frame_count = max(1, round(duration_seconds * sample_rate))
    path.parent.mkdir(parents=True, exist_ok=True)
    state = 0xC1F5A9
    with wave.open(str(path), "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(sample_rate)
        buffer = bytearray()
        for index in range(frame_count):
            time = index / sample_rate
            state = (1664525 * state + 1013904223) & 0xFFFFFFFF
            noise = ((state / 0xFFFFFFFF) * 2.0) - 1.0
            if kind == "music":
                beat = time % 0.5
                kick = math.sin(2 * math.pi * (72 - 38 * min(beat, 0.18)) * time)
                kick *= math.exp(-18 * beat)
                hat_phase = time % 0.25
                hat = noise * math.exp(-65 * hat_phase)
                bass_note = (55.0, 65.41, 73.42, 49.0)[int(time / 2) % 4]
                bass = math.sin(2 * math.pi * bass_note * time) * 0.22
                pulse = math.sin(2 * math.pi * 220 * time) * (0.05 if beat < 0.08 else 0)
                value = 0.34 * kick + 0.07 * hat + bass + pulse
            elif kind == "whoosh":
                position = index / max(1, frame_count - 1)
                envelope = math.sin(math.pi * position) ** 1.4
                value = noise * envelope * (0.22 + 0.3 * position)
            elif kind == "impact":
                value = (
                    0.68 * math.sin(2 * math.pi * 78 * time) * math.exp(-10 * time)
                    + 0.13 * noise * math.exp(-24 * time)
                )
            else:
                value = (
                    0.45 * math.sin(2 * math.pi * 330 * time) * math.exp(-13 * time)
                    + 0.16 * math.sin(2 * math.pi * 165 * time) * math.exp(-9 * time)
                )
            sample = max(-32767, min(32767, round(value * 32767 * 0.72)))
            buffer.extend(struct.pack("<h", sample))
            if len(buffer) >= 131_072:
                stream.writeframesraw(buffer)
                buffer.clear()
        if buffer:
            stream.writeframesraw(buffer)


def _require_nonempty(path: Path, label: str) -> None:
    if not path.is_file() or path.stat().st_size <= 0:
        raise SourceAssetBuildError(f"No se produjo un {label} físico válido: {path}")


def _sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json_atomic(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    temporary.replace(path)


def _decimal(value: float) -> str:
    return format(float(value), ".6f").rstrip("0").rstrip(".")


__all__ = [
    "BUILD_REPORT_FILENAME",
    "CATALOG_FILENAME",
    "DeliveryVerificationResult",
    "PIPER_PACKAGE_VERSION",
    "PIPER_SENTENCE_SILENCE_SECONDS",
    "PIPER_VOICE_ID",
    "PM9SourceAssetBuilder",
    "SourceAssetBuildError",
    "SourceAssetBuildResult",
    "VERIFY_REPORT_RELATIVE_PATH",
    "derive_github_raw_base",
    "verify_catalog_delivery",
]
