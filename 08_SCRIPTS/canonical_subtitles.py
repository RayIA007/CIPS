"""Provider-neutral canonical subtitle alignment and editorial validation.

Words always come from the approved :class:`ProductionManifest`.  Physical
narration audio contributes duration only.  The resulting SRT is deterministic,
locally reviewable, and persisted through F3 with a content hash and provenance
sidecar before any render provider receives it.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import subprocess
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from artifact_store import ArtifactStore, CollisionPolicy
from asset_resolution import AssetResolutionBundle, ResolutionStatus
from production_manifest import ProductionManifest, SceneSpec
from text_store import TextStore
from workspace_resolver import WorkspaceResolver


CANONICAL_SUBTITLE_RELATIVE_PATH = Path("subtitles") / "canonical_subtitles.srt"
CANONICAL_SUBTITLE_SCHEMA_NAME = "cips.canonical_subtitles"
CANONICAL_SUBTITLE_SCHEMA_VERSION = "1.0"
LEXICAL_SOURCE = "production_manifest.scene.narration_text"
TIMING_SOURCE = "ffprobe.physical_scene_narration+deterministic_weighting_v1"
_SRT_TIMECODE = re.compile(r"^(\d{2}):(\d{2}):(\d{2}),(\d{3})$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_MINIMUM_READABLE_CUE_MS = 650


class CanonicalSubtitleError(RuntimeError):
    """Canonical subtitle generation or validation failed safely."""


class CanonicalSubtitleAlignmentError(CanonicalSubtitleError):
    """Final subtitle words or timing diverge from the approved narration."""


class CanonicalSubtitleProbeError(CanonicalSubtitleError):
    """A physical narration asset could not be measured reliably."""


class CanonicalSubtitleCue(BaseModel):
    """One immutable canonical caption cue expressed in integer milliseconds."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    index: int = Field(..., gt=0)
    scene_id: str = Field(..., min_length=1)
    start_ms: int = Field(..., ge=0)
    end_ms: int = Field(..., gt=0)
    text: str = Field(..., min_length=1)

    @model_validator(mode="after")
    def _validate_interval(self) -> "CanonicalSubtitleCue":
        if self.end_ms <= self.start_ms:
            raise ValueError("Cada cue requiere end_ms mayor que start_ms.")
        return self


class CanonicalSubtitleTrack(BaseModel):
    """Provider-neutral canonical subtitle track ready for persistence/rendering."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    schema_name: Literal["cips.canonical_subtitles"] = CANONICAL_SUBTITLE_SCHEMA_NAME
    schema_version: Literal["1.0"] = CANONICAL_SUBTITLE_SCHEMA_VERSION
    manifest_id: str = Field(..., min_length=1)
    output_duration_ms: int = Field(..., gt=0)
    lexical_source: Literal["production_manifest.scene.narration_text"] = LEXICAL_SOURCE
    timing_source: Literal[
        "ffprobe.physical_scene_narration+deterministic_weighting_v1"
    ] = TIMING_SOURCE
    canonical_text_sha256: str
    audio_sha256_by_scene: dict[str, str] = Field(..., min_length=1)
    audio_duration_ms_by_scene: dict[str, int] = Field(..., min_length=1)
    cues: tuple[CanonicalSubtitleCue, ...] = Field(..., min_length=1)

    @field_validator("canonical_text_sha256")
    @classmethod
    def _validate_text_hash(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not _SHA256.fullmatch(normalized):
            raise ValueError("canonical_text_sha256 debe ser SHA-256 hexadecimal.")
        return normalized

    @field_validator("audio_sha256_by_scene")
    @classmethod
    def _validate_audio_hashes(cls, values: dict[str, str]) -> dict[str, str]:
        normalized: dict[str, str] = {}
        for scene_id, value in values.items():
            digest = str(value).strip().lower()
            if not scene_id.strip() or not _SHA256.fullmatch(digest):
                raise ValueError("audio_sha256_by_scene contiene una entrada inválida.")
            normalized[scene_id.strip()] = digest
        return normalized

    @field_validator("audio_duration_ms_by_scene")
    @classmethod
    def _validate_audio_durations(cls, values: dict[str, int]) -> dict[str, int]:
        if any(
            not scene_id.strip() or duration <= 0
            for scene_id, duration in values.items()
        ):
            raise ValueError("Las duraciones físicas de narración deben ser positivas.")
        return dict(values)

    @model_validator(mode="after")
    def _validate_timeline(self) -> "CanonicalSubtitleTrack":
        expected_indexes = tuple(range(1, len(self.cues) + 1))
        if tuple(cue.index for cue in self.cues) != expected_indexes:
            raise ValueError("Los índices de cues deben ser consecutivos desde 1.")
        previous_end = 0
        for cue in self.cues:
            if cue.start_ms < previous_end:
                raise ValueError("Los cues canónicos no pueden solaparse.")
            if cue.end_ms > self.output_duration_ms:
                raise ValueError("Un cue excede la duración final solicitada.")
            previous_end = cue.end_ms
        scene_ids = {cue.scene_id for cue in self.cues}
        if scene_ids != set(self.audio_sha256_by_scene):
            raise ValueError("Los hashes de audio no cubren exactamente los cues.")
        if scene_ids != set(self.audio_duration_ms_by_scene):
            raise ValueError("Las duraciones de audio no cubren exactamente los cues.")
        return self

    def to_srt(self) -> str:
        """Render a stable UTF-8 SRT from the validated track."""

        return "\n\n".join(
            (
                f"{cue.index}\n"
                f"{_format_srt_time(cue.start_ms)} --> {_format_srt_time(cue.end_ms)}\n"
                f"{cue.text}"
            )
            for cue in self.cues
        )


ProbeRunner = Callable[[Sequence[str]], Mapping[str, Any]]


class PhysicalAudioDurationProbe:
    """Read physical audio duration locally with FFprobe and no network access."""

    def __init__(
        self,
        *,
        executable: str = "ffprobe",
        runner: ProbeRunner | None = None,
    ) -> None:
        normalized = str(executable).strip()
        if not normalized:
            raise ValueError("executable no puede estar vacío.")
        self._executable = normalized
        self._runner = runner or self._run_ffprobe

    def inspect(self, path: str | Path) -> float:
        audio_path = Path(path).expanduser().resolve(strict=False)
        if not audio_path.is_file() or audio_path.stat().st_size <= 0:
            raise CanonicalSubtitleProbeError(
                f"No existe una narración física utilizable: {audio_path}"
            )
        command = (
            self._executable,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            str(audio_path),
        )
        try:
            payload = self._runner(command)
        except CanonicalSubtitleProbeError:
            raise
        except Exception as error:
            raise CanonicalSubtitleProbeError(
                f"FFprobe falló para {audio_path.name}: {type(error).__name__}: {error}"
            ) from error
        if not isinstance(payload, Mapping):
            raise CanonicalSubtitleProbeError("FFprobe no devolvió un objeto JSON.")
        format_data = payload.get("format")
        if not isinstance(format_data, Mapping):
            raise CanonicalSubtitleProbeError("FFprobe no devolvió format.duration.")
        try:
            duration = float(format_data.get("duration"))
        except (TypeError, ValueError) as error:
            raise CanonicalSubtitleProbeError(
                f"FFprobe no midió una duración válida para {audio_path.name}."
            ) from error
        if not math.isfinite(duration) or duration <= 0:
            raise CanonicalSubtitleProbeError(
                f"Duración física inválida para {audio_path.name}."
            )
        return duration

    @staticmethod
    def _run_ffprobe(command: Sequence[str]) -> Mapping[str, Any]:
        try:
            completed = subprocess.run(
                list(command),
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=60,
            )
        except (OSError, subprocess.SubprocessError) as error:
            raise CanonicalSubtitleProbeError(
                f"No fue posible ejecutar FFprobe: {type(error).__name__}: {error}"
            ) from error
        if completed.returncode != 0:
            detail = completed.stderr.strip() or "sin detalle"
            raise CanonicalSubtitleProbeError(
                f"FFprobe terminó con código {completed.returncode}: {detail}"
            )
        try:
            parsed = json.loads(completed.stdout)
        except json.JSONDecodeError as error:
            raise CanonicalSubtitleProbeError(
                "FFprobe devolvió JSON inválido."
            ) from error
        if not isinstance(parsed, Mapping):
            raise CanonicalSubtitleProbeError(
                "FFprobe devolvió una raíz JSON inválida."
            )
        return parsed


@dataclass(frozen=True, slots=True)
class CanonicalSubtitleResult:
    """Validated track plus its persisted F3 artifact evidence."""

    track: CanonicalSubtitleTrack
    srt_text: str
    artifact_path: Path
    sidecar_path: Path
    content_sha256: str


class CanonicalSubtitleService:
    """Build, validate, and persist a canonical SRT before provider compilation."""

    def __init__(
        self,
        workspace_resolver: WorkspaceResolver,
        *,
        duration_probe: PhysicalAudioDurationProbe | None = None,
        text_store: TextStore | None = None,
    ) -> None:
        if not isinstance(workspace_resolver, WorkspaceResolver):
            raise TypeError("workspace_resolver debe ser WorkspaceResolver.")
        self.workspace_resolver = workspace_resolver
        self.duration_probe = duration_probe or PhysicalAudioDurationProbe()
        self.text_store = text_store or TextStore(workspace_resolver)

    def build_and_persist(
        self,
        manifest: ProductionManifest,
        bundle: AssetResolutionBundle,
        *,
        workspace_root: str | Path,
        relative_path: str | Path = CANONICAL_SUBTITLE_RELATIVE_PATH,
    ) -> CanonicalSubtitleResult:
        if not isinstance(manifest, ProductionManifest):
            raise TypeError("manifest debe ser ProductionManifest.")
        if not isinstance(bundle, AssetResolutionBundle):
            raise TypeError("bundle debe ser AssetResolutionBundle.")
        if bundle.manifest_id != manifest.manifest_id:
            raise CanonicalSubtitleAlignmentError(
                "El bundle de narración no corresponde al manifest canónico."
            )
        project = Path(workspace_root).expanduser().resolve(strict=False)
        self.workspace_resolver.confine_path(project, "canonical_subtitles")

        cues: list[CanonicalSubtitleCue] = []
        audio_hashes: dict[str, str] = {}
        audio_durations: dict[str, int] = {}
        captioned_scenes = [
            scene for scene in manifest.scenes if scene.captions is not None
        ]
        if not captioned_scenes:
            raise CanonicalSubtitleAlignmentError(
                "El manifest no contiene escenas con captions para alinear."
            )
        for scene in captioned_scenes:
            narration = _canonical_scene_text(scene)
            try:
                asset = bundle.scene_narration(scene.scene_id)
            except KeyError as error:
                raise CanonicalSubtitleAlignmentError(
                    f"Falta la narración física de la escena '{scene.scene_id}'."
                ) from error
            if asset.status is not ResolutionStatus.PERSISTED:
                raise CanonicalSubtitleAlignmentError(
                    f"La narración de '{scene.scene_id}' no está persistida en F3."
                )
            if asset.artifact_relative_path is None or asset.content_sha256 is None:
                raise CanonicalSubtitleAlignmentError(
                    f"La narración de '{scene.scene_id}' no tiene referencia F3 completa."
                )
            audio_path = (project / asset.artifact_relative_path).resolve(strict=False)
            self.workspace_resolver.confine_path(
                audio_path, "canonical_subtitles audio"
            )
            if not audio_path.is_file():
                raise CanonicalSubtitleProbeError(
                    f"No existe el audio F3 de '{scene.scene_id}': {audio_path}"
                )
            physical_hash = ArtifactStore.calculate_file_hash(audio_path)
            if physical_hash != asset.content_sha256:
                raise CanonicalSubtitleAlignmentError(
                    f"El hash físico de la narración '{scene.scene_id}' no coincide con F3."
                )
            measured_ms = int(round(self.duration_probe.inspect(audio_path) * 1000.0))
            scene_duration_ms = int(round(scene.duration_seconds * 1000.0))
            if measured_ms > scene_duration_ms + 250:
                raise CanonicalSubtitleAlignmentError(
                    f"La narración de '{scene.scene_id}' excede su escena: "
                    f"{measured_ms} ms > {scene_duration_ms} ms."
                )
            usable_ms = min(measured_ms, scene_duration_ms)
            if usable_ms < 250:
                raise CanonicalSubtitleAlignmentError(
                    f"La narración de '{scene.scene_id}' es demasiado corta para alinear."
                )
            scene_cues = _align_scene(
                scene,
                narration,
                audio_duration_ms=usable_ms,
                first_index=len(cues) + 1,
            )
            cues.extend(scene_cues)
            audio_hashes[scene.scene_id] = physical_hash
            audio_durations[scene.scene_id] = measured_ms

        canonical_text_sha256 = _canonical_text_sha256(captioned_scenes)
        track = CanonicalSubtitleTrack(
            manifest_id=manifest.manifest_id,
            output_duration_ms=int(round(manifest.output.duration_seconds * 1000.0)),
            canonical_text_sha256=canonical_text_sha256,
            audio_sha256_by_scene=audio_hashes,
            audio_duration_ms_by_scene=audio_durations,
            cues=tuple(cues),
        )
        validate_canonical_subtitle_track(track, manifest)
        srt_text = track.to_srt()
        validate_srt_against_manifest(srt_text, manifest, expected_track=track)
        srt_sha256 = ArtifactStore.calculate_content_hash(srt_text.encode("utf-8"))

        write = self.text_store.persist_text(
            workspace_root=project,
            relative_path=relative_path,
            content=srt_text,
            artifact_type="canonical_subtitles",
            mime_type="text/plain",
            artifact_id=(
                f"canonical-subtitles-{manifest.manifest_id}-{srt_sha256}"
            ),
            metadata={
                "schema_name": track.schema_name,
                "schema_version": track.schema_version,
                "manifest_id": manifest.manifest_id,
                "lexical_source": track.lexical_source,
                "timing_source": track.timing_source,
                "canonical_text_sha256": track.canonical_text_sha256,
                "audio_sha256_by_scene": track.audio_sha256_by_scene,
                "audio_duration_ms_by_scene": track.audio_duration_ms_by_scene,
                "lexical_congruence": True,
                "publication_performed": False,
            },
            collision_policy=CollisionPolicy.REPLACE,
        )
        return CanonicalSubtitleResult(
            track=track,
            srt_text=srt_text,
            artifact_path=Path(write.artifact.path),
            sidecar_path=write.sidecar_path,
            content_sha256=write.artifact.content_hash,
        )


def validate_canonical_subtitle_track(
    track: CanonicalSubtitleTrack,
    manifest: ProductionManifest,
) -> None:
    """Block any lexical, scene, accent, punctuation, or timing discrepancy."""

    if not isinstance(track, CanonicalSubtitleTrack):
        raise TypeError("track debe ser CanonicalSubtitleTrack.")
    if not isinstance(manifest, ProductionManifest):
        raise TypeError("manifest debe ser ProductionManifest.")
    if track.manifest_id != manifest.manifest_id:
        raise CanonicalSubtitleAlignmentError(
            "El track canónico pertenece a otro ProductionManifest."
        )
    captioned_scenes = [
        scene for scene in manifest.scenes if scene.captions is not None
    ]
    expected_scene_ids = {scene.scene_id for scene in captioned_scenes}
    actual_scene_ids = {cue.scene_id for cue in track.cues}
    if actual_scene_ids != expected_scene_ids:
        raise CanonicalSubtitleAlignmentError(
            "Los cues no cubren exactamente las escenas con captions."
        )
    if track.canonical_text_sha256 != _canonical_text_sha256(captioned_scenes):
        raise CanonicalSubtitleAlignmentError(
            "El hash del texto canónico no coincide con la narración aprobada."
        )
    for scene in captioned_scenes:
        scene_cues = [cue for cue in track.cues if cue.scene_id == scene.scene_id]
        reconstructed = _normalize_text(" ".join(cue.text for cue in scene_cues))
        canonical = _canonical_scene_text(scene)
        if reconstructed != canonical:
            raise CanonicalSubtitleAlignmentError(
                f"Congruencia léxica fallida en '{scene.scene_id}': "
                "hay palabras, acentos o signos añadidos, eliminados o sustituidos."
            )
        scene_start_ms = int(round(scene.start_seconds * 1000.0))
        scene_end_ms = int(round(scene.end_seconds * 1000.0))
        scene_duration_ms = scene_end_ms - scene_start_ms
        measured_ms = track.audio_duration_ms_by_scene[scene.scene_id]
        if measured_ms > scene_duration_ms + 250:
            raise CanonicalSubtitleAlignmentError(
                f"La duración física de '{scene.scene_id}' excede su escena."
            )
        audio_end_ms = scene_start_ms + min(measured_ms, scene_duration_ms)
        if any(
            cue.start_ms < scene_start_ms or cue.end_ms > audio_end_ms
            for cue in scene_cues
        ):
            raise CanonicalSubtitleAlignmentError(
                f"Los cues de '{scene.scene_id}' exceden su narración física."
            )
        if scene_cues[0].start_ms != scene_start_ms:
            raise CanonicalSubtitleAlignmentError(
                f"Los cues de '{scene.scene_id}' no empiezan con la narración."
            )
        if scene_cues[-1].end_ms != audio_end_ms:
            raise CanonicalSubtitleAlignmentError(
                f"Los cues de '{scene.scene_id}' no terminan con la narración."
            )
        if any(
            previous.end_ms != following.start_ms
            for previous, following in zip(scene_cues, scene_cues[1:])
        ):
            raise CanonicalSubtitleAlignmentError(
                f"Los cues de '{scene.scene_id}' contienen huecos temporales."
            )
        if len(scene_cues) > 1 and any(
            cue.end_ms - cue.start_ms < _MINIMUM_READABLE_CUE_MS for cue in scene_cues
        ):
            raise CanonicalSubtitleAlignmentError(
                f"Los cues de '{scene.scene_id}' incluyen un destello menor a "
                f"{_MINIMUM_READABLE_CUE_MS} ms."
            )


def validate_srt_against_manifest(
    srt_text: str,
    manifest: ProductionManifest,
    *,
    expected_track: CanonicalSubtitleTrack | None = None,
) -> None:
    """Parse a final SRT and compare it literally with approved narration."""

    parsed = _parse_srt(srt_text)
    if expected_track is not None:
        expected = tuple(
            (cue.index, cue.start_ms, cue.end_ms, cue.text)
            for cue in expected_track.cues
        )
        if parsed != expected:
            raise CanonicalSubtitleAlignmentError(
                "El SRT final no coincide exactamente con el track canónico validado."
            )
        validate_canonical_subtitle_track(expected_track, manifest)
        return

    captioned_scenes = [
        scene for scene in manifest.scenes if scene.captions is not None
    ]
    parsed_by_scene: dict[str, list[str]] = {
        scene.scene_id: [] for scene in captioned_scenes
    }
    for _, cue_start, cue_end, text in parsed:
        matching_scenes = [
            scene
            for scene in captioned_scenes
            if cue_start >= int(round(scene.start_seconds * 1000.0))
            and cue_end <= int(round(scene.end_seconds * 1000.0))
        ]
        if len(matching_scenes) != 1:
            raise CanonicalSubtitleAlignmentError(
                "Un cue SRT está fuera de escena o cruza un límite editorial."
            )
        parsed_by_scene[matching_scenes[0].scene_id].append(text)
    for scene in captioned_scenes:
        scene_text = " ".join(parsed_by_scene[scene.scene_id])
        if _normalize_text(scene_text) != _canonical_scene_text(scene):
            raise CanonicalSubtitleAlignmentError(
                f"Congruencia léxica fallida en '{scene.scene_id}'."
            )


def _align_scene(
    scene: SceneSpec,
    narration: str,
    *,
    audio_duration_ms: int,
    first_index: int,
) -> list[CanonicalSubtitleCue]:
    caption = scene.captions
    if caption is None:
        return []
    chunks = _caption_chunks(
        narration.split(),
        max_characters=caption.max_characters_per_line,
        max_words=6,
        audio_duration_ms=audio_duration_ms,
    )
    if not chunks:
        raise CanonicalSubtitleAlignmentError(
            f"La escena '{scene.scene_id}' no produjo chunks canónicos."
        )
    weights = [_spoken_weight(chunk) for chunk in chunks]
    total_weight = sum(weights)
    scene_start_ms = int(round(scene.start_seconds * 1000.0))
    cues: list[CanonicalSubtitleCue] = []
    elapsed_weight = 0
    cursor = scene_start_ms
    for offset, (chunk, weight) in enumerate(zip(chunks, weights)):
        elapsed_weight += weight
        end_ms = (
            scene_start_ms + audio_duration_ms
            if offset == len(chunks) - 1
            else scene_start_ms
            + int(round(audio_duration_ms * elapsed_weight / total_weight))
        )
        end_ms = max(cursor + 1, end_ms)
        cues.append(
            CanonicalSubtitleCue(
                index=first_index + offset,
                scene_id=scene.scene_id,
                start_ms=cursor,
                end_ms=end_ms,
                text=chunk,
            )
        )
        cursor = end_ms
    return cues


def _caption_chunks(
    words: list[str],
    *,
    max_characters: int,
    max_words: int,
    audio_duration_ms: int,
) -> list[str]:
    if not words:
        return []
    if max_characters < 1 or max_words < 1 or audio_duration_ms < 1:
        raise CanonicalSubtitleAlignmentError(
            "Los límites de segmentación canónica deben ser positivos."
        )

    word_count = len(words)

    def candidates(start: int):
        for end in range(start + 1, min(word_count, start + max_words) + 1):
            chunk = " ".join(words[start:end])
            if len(chunk) > max_characters and end > start + 1:
                break
            yield end, chunk

    @lru_cache(maxsize=None)
    def minimum_chunks(start: int) -> int:
        if start == word_count:
            return 0
        counts = [1 + minimum_chunks(end) for end, _ in candidates(start)]
        return min(counts) if counts else word_count + 1

    required_chunks = minimum_chunks(0)
    if required_chunks > word_count:
        raise CanonicalSubtitleAlignmentError(
            "No existe una segmentación canónica compatible con los límites."
        )
    total_weight = _spoken_weight(" ".join(words))
    target_weight = total_weight / required_chunks

    @lru_cache(maxsize=None)
    def best_partition(
        start: int,
        remaining: int,
    ) -> tuple[int, tuple[str, ...]] | None:
        if start == word_count:
            return (0, ()) if remaining == 0 else None
        if remaining <= 0:
            return None
        best: tuple[int, tuple[str, ...]] | None = None
        for end, chunk in candidates(start):
            words_left = word_count - end
            if words_left < remaining - 1:
                continue
            tail = best_partition(end, remaining - 1)
            if tail is None:
                continue
            chunk_word_count = end - start
            weight = _spoken_weight(chunk)
            predicted_ms = round(audio_duration_ms * weight / total_weight)
            duration_deficit = max(0, _MINIMUM_READABLE_CUE_MS - predicted_ms)
            orphan_penalty = 10**12 if chunk_word_count == 1 and word_count > 1 else 0
            short_phrase_penalty = 10**7 if chunk_word_count == 2 else 0
            readability_penalty = duration_deficit * duration_deficit * 10_000
            balance_penalty = round((weight - target_weight) ** 2 * 100)
            boundary_penalty = 0 if chunk[-1] in ".?!;:" else 5_000
            cost = (
                orphan_penalty
                + short_phrase_penalty
                + readability_penalty
                + balance_penalty
                + boundary_penalty
                + tail[0]
            )
            candidate = (cost, (chunk, *tail[1]))
            if best is None or candidate < best:
                best = candidate
        return best

    partition = best_partition(0, required_chunks)
    if partition is None:
        raise CanonicalSubtitleAlignmentError(
            "No fue posible equilibrar los chunks canónicos."
        )
    return list(partition[1])


def _spoken_weight(text: str) -> int:
    letters = sum(character.isalnum() for character in text)
    short_pauses = sum(text.count(mark) for mark in ",;:") * 2
    long_pauses = sum(text.count(mark) for mark in ".?!") * 4
    return max(1, letters + short_pauses + long_pauses)


def _canonical_scene_text(scene: SceneSpec) -> str:
    narration = _normalize_text(scene.narration_text or "")
    if not narration:
        raise CanonicalSubtitleAlignmentError(
            f"La escena '{scene.scene_id}' tiene captions sin narración canónica."
        )
    return narration


def _canonical_text_sha256(scenes: Sequence[SceneSpec]) -> str:
    payload = [
        {"scene_id": scene.scene_id, "text": _canonical_scene_text(scene)}
        for scene in scenes
    ]
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _normalize_text(value: str) -> str:
    return " ".join(str(value).split())


def _format_srt_time(milliseconds: int) -> str:
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"


def _parse_srt(srt_text: str) -> tuple[tuple[int, int, int, str], ...]:
    normalized = str(srt_text).replace("\r\n", "\n").strip()
    if not normalized:
        raise CanonicalSubtitleAlignmentError("El SRT canónico está vacío.")
    parsed: list[tuple[int, int, int, str]] = []
    previous_end = 0
    for expected_index, block in enumerate(re.split(r"\n{2,}", normalized), start=1):
        lines = block.splitlines()
        if len(lines) < 3:
            raise CanonicalSubtitleAlignmentError(
                "El SRT contiene un bloque incompleto."
            )
        try:
            index = int(lines[0])
        except ValueError as error:
            raise CanonicalSubtitleAlignmentError(
                "El SRT contiene un índice inválido."
            ) from error
        if index != expected_index:
            raise CanonicalSubtitleAlignmentError(
                "Los índices SRT deben ser consecutivos desde 1."
            )
        timing = lines[1].split(" --> ")
        if len(timing) != 2:
            raise CanonicalSubtitleAlignmentError(
                "El SRT contiene timestamps inválidos."
            )
        start_ms = _parse_srt_time(timing[0])
        end_ms = _parse_srt_time(timing[1])
        if end_ms <= start_ms or start_ms < previous_end:
            raise CanonicalSubtitleAlignmentError(
                "El SRT contiene tiempos vacíos, invertidos o solapados."
            )
        text = _normalize_text(" ".join(lines[2:]))
        if not text:
            raise CanonicalSubtitleAlignmentError("El SRT contiene un cue sin texto.")
        parsed.append((index, start_ms, end_ms, text))
        previous_end = end_ms
    return tuple(parsed)


def _parse_srt_time(value: str) -> int:
    match = _SRT_TIMECODE.fullmatch(value.strip())
    if match is None:
        raise CanonicalSubtitleAlignmentError(f"Timestamp SRT inválido: {value}")
    hours, minutes, seconds, milliseconds = (int(item) for item in match.groups())
    if minutes >= 60 or seconds >= 60:
        raise CanonicalSubtitleAlignmentError(f"Timestamp SRT fuera de rango: {value}")
    return ((hours * 60 + minutes) * 60 + seconds) * 1000 + milliseconds


__all__ = [
    "CANONICAL_SUBTITLE_RELATIVE_PATH",
    "CANONICAL_SUBTITLE_SCHEMA_NAME",
    "CANONICAL_SUBTITLE_SCHEMA_VERSION",
    "CanonicalSubtitleAlignmentError",
    "CanonicalSubtitleCue",
    "CanonicalSubtitleError",
    "CanonicalSubtitleProbeError",
    "CanonicalSubtitleResult",
    "CanonicalSubtitleService",
    "CanonicalSubtitleTrack",
    "PhysicalAudioDurationProbe",
    "ProbeRunner",
    "validate_canonical_subtitle_track",
    "validate_srt_against_manifest",
]
