"""Proactive acoustic conformance gate for generated scene narration.

The canonical script remains the editorial authority.  This module listens to
the physical audio produced from that script, compares the observed words with
the canonical words, persists exact differences, and blocks downstream paid
rendering when they diverge.  It never rewrites the script automatically.
"""

from __future__ import annotations

import difflib
import hashlib
import inspect
import json
import os
import re
import tempfile
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol

from artifact_store import CollisionPolicy
from metadata_store import MetadataStore
from production_manifest import ProductionManifest
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

NARRATION_CONFORMANCE_RELATIVE_PATH = Path("acceptance") / "narration_conformance.json"


class NarrationConformanceError(RuntimeError):
    """Narration could not prove acoustic equality with the canonical script."""


class NarrationTranscriberUnavailableError(NarrationConformanceError):
    """The configured local transcription engine cannot run."""


class NarrationConformanceMismatchError(NarrationConformanceError):
    """At least one physical narration clip differs from its canonical text."""


class _ConformanceModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
        validate_default=True,
    )


class NarrationConformancePolicy(_ConformanceModel):
    """Provider-neutral policy for the pre-render acoustic gate."""

    enabled: bool = False
    engine: Literal["faster_whisper"] = "faster_whisper"
    model: str = Field(default="small", min_length=1, max_length=128)
    adjudication_model: str | None = Field(
        default="medium", min_length=1, max_length=128
    )
    language: str = Field(default="es", pattern=r"^[a-z]{2,3}$")
    device: Literal["cpu"] = "cpu"
    compute_type: Literal["int8"] = "int8"
    word_timestamps: Literal[True] = True
    vad_filter: Literal[True] = True
    comparison: Literal["exact_lexical"] = "exact_lexical"
    automatic_script_rewrite: Literal[False] = False


class NarrationTranscription(_ConformanceModel):
    """Observed text returned by a local speech-to-text engine."""

    text: str
    detected_language: str | None = Field(default=None, min_length=1, max_length=32)
    language_probability: float | None = Field(default=None, ge=0.0, le=1.0)


class NarrationTranscriber(Protocol):
    """Minimal injection boundary used by production and deterministic tests."""

    @property
    def network_called(self) -> bool: ...

    def transcribe(self, audio_path: Path) -> NarrationTranscription: ...


class NarrationTokenDifference(_ConformanceModel):
    """One lexical insertion, deletion, or replacement."""

    operation: Literal["insert", "delete", "replace"]
    expected: tuple[str, ...] = ()
    observed: tuple[str, ...] = ()
    expected_index: int = Field(..., ge=0)
    observed_index: int = Field(..., ge=0)

    @model_validator(mode="after")
    def _validate_operation(self) -> NarrationTokenDifference:
        if self.operation == "insert" and (self.expected or not self.observed):
            raise ValueError("insert requiere sólo tokens observados.")
        if self.operation == "delete" and (not self.expected or self.observed):
            raise ValueError("delete requiere sólo tokens esperados.")
        if self.operation == "replace" and (not self.expected or not self.observed):
            raise ValueError("replace requiere tokens esperados y observados.")
        return self


class NarrationClipConformance(_ConformanceModel):
    """Acoustic evidence for one narration-bearing scene."""

    scene_id: str = Field(..., min_length=1, max_length=128)
    sequence: int = Field(..., gt=0)
    audio_relative_path: str = Field(..., min_length=1)
    audio_sha256: str
    canonical_text: str = Field(..., min_length=1)
    canonical_text_sha256: str
    observed_text: str = ""
    expected_tokens: tuple[str, ...] = ()
    observed_tokens: tuple[str, ...] = ()
    differences: tuple[NarrationTokenDifference, ...] = ()
    detected_language: str | None = Field(default=None, min_length=1, max_length=32)
    language_probability: float | None = Field(default=None, ge=0.0, le=1.0)
    transcription_error: str | None = Field(default=None, min_length=1)
    adjudication_model: str | None = Field(default=None, min_length=1, max_length=128)
    adjudication_observed_text: str | None = None
    adjudication_tokens: tuple[str, ...] | None = None
    adjudication_differences: tuple[NarrationTokenDifference, ...] | None = None
    adjudication_error: str | None = Field(default=None, min_length=1)
    adjudication_approved: bool | None = None
    approved: bool

    @field_validator("audio_sha256", "canonical_text_sha256")
    @classmethod
    def _validate_hash(cls, value: str) -> str:
        normalized = value.casefold()
        if len(normalized) != 64 or any(
            character not in "0123456789abcdef" for character in normalized
        ):
            raise ValueError("Se esperaba un SHA-256 hexadecimal.")
        return normalized

    @model_validator(mode="after")
    def _validate_decision(self) -> NarrationClipConformance:
        adjudication_fields = (
            self.adjudication_model,
            self.adjudication_observed_text,
            self.adjudication_tokens,
            self.adjudication_differences,
            self.adjudication_error,
            self.adjudication_approved,
        )
        if any(value is not None for value in adjudication_fields):
            if self.adjudication_model is None or self.adjudication_approved is None:
                raise ValueError(
                    "La adjudicación acústica debe identificar modelo y decisión."
                )
            if self.adjudication_error is None:
                if any(
                    value is None
                    for value in (
                        self.adjudication_observed_text,
                        self.adjudication_tokens,
                        self.adjudication_differences,
                    )
                ):
                    raise ValueError(
                        "La adjudicación acústica exitosa está incompleta."
                    )
                if self.adjudication_approved != (not self.adjudication_differences):
                    raise ValueError(
                        "La decisión adjudicada no coincide con sus diferencias."
                    )
            elif self.adjudication_approved:
                raise ValueError("Una adjudicación con error no puede aprobar.")
        primary_approved = not self.differences and self.transcription_error is None
        expected_approval = primary_approved or self.adjudication_approved is True
        if self.approved != expected_approval:
            raise ValueError("approved no coincide con la evidencia acústica.")
        return self


class NarrationSynthesisAttempt(_ConformanceModel):
    """One complete voice candidate evaluated against the canonical script."""

    attempt: int = Field(..., gt=0)
    voice_id: str = Field(..., min_length=1, max_length=128)
    clips: tuple[NarrationClipConformance, ...]
    blockers: tuple[str, ...] = ()
    approved: bool

    @model_validator(mode="after")
    def _validate_decision(self) -> NarrationSynthesisAttempt:
        expected_approval = (
            bool(self.clips)
            and all(clip.approved for clip in self.clips)
            and not self.blockers
        )
        if self.approved != expected_approval:
            raise ValueError("approved no coincide con el intento de voz.")
        return self


class NarrationConformanceReport(_ConformanceModel):
    """Durable all-scenes decision consumed by the render-preparation gate."""

    schema_name: Literal["cips.production_acceptance.narration_conformance"] = (
        "cips.production_acceptance.narration_conformance"
    )
    schema_version: Literal["1.1"] = "1.1"
    manifest_id: str = Field(..., min_length=1, max_length=128)
    project_id: str = Field(..., min_length=1, max_length=128)
    policy: NarrationConformancePolicy
    normalization: Literal["unicode_case_punctuation_diacritic_insensitive_v1"] = (
        "unicode_case_punctuation_diacritic_insensitive_v1"
    )
    clips: tuple[NarrationClipConformance, ...] = ()
    blockers: tuple[str, ...] = ()
    approved: bool
    synthesis_voice_id: str | None = Field(default=None, min_length=1, max_length=128)
    synthesis_attempts: tuple[NarrationSynthesisAttempt, ...] = ()
    failure_action: Literal["block_render_and_require_authorized_regeneration"] = (
        "block_render_and_require_authorized_regeneration"
    )
    canonical_script_mutated: Literal[False] = False
    actual_cost_usd: Literal[0.0] = 0.0
    paid_provider_called: Literal[False] = False
    render_performed: Literal[False] = False
    publication_performed: Literal[False] = False
    network_called: bool = False

    @model_validator(mode="after")
    def _validate_decision(self) -> NarrationConformanceReport:
        expected_approval = (
            bool(self.clips)
            and all(clip.approved for clip in self.clips)
            and not self.blockers
        )
        if self.approved != expected_approval:
            raise ValueError("approved no coincide con las escenas acústicas.")
        if self.approved == bool(self.blockers):
            raise ValueError("blockers debe estar vacío sólo cuando approved=true.")
        if self.synthesis_attempts:
            expected_attempts = tuple(range(1, len(self.synthesis_attempts) + 1))
            if (
                tuple(item.attempt for item in self.synthesis_attempts)
                != expected_attempts
            ):
                raise ValueError("Los intentos de voz deben ser consecutivos.")
            latest = self.synthesis_attempts[-1]
            if (
                self.synthesis_voice_id != latest.voice_id
                or self.clips != latest.clips
                or self.blockers != latest.blockers
                or self.approved != latest.approved
            ):
                raise ValueError("El reporte no coincide con su último intento de voz.")
        elif self.synthesis_voice_id is not None:
            raise ValueError("synthesis_voice_id requiere evidencia de intentos.")
        return self


@dataclass(frozen=True, slots=True)
class NarrationConformanceInspection:
    """Read-only result used by preparation without re-running ASR."""

    report: NarrationConformanceReport | None
    report_path: Path
    report_sha256: str | None
    blockers: tuple[str, ...]


class FasterWhisperTranscriber:
    """Lazy local CPU/int8 transcription backed by faster-whisper."""

    def __init__(
        self,
        policy: NarrationConformancePolicy,
        *,
        model_dir: str | Path,
        allow_model_download: bool,
    ) -> None:
        if not isinstance(policy, NarrationConformancePolicy):
            raise TypeError("policy debe ser NarrationConformancePolicy.")
        if not policy.enabled:
            raise ValueError("La transcripción requiere policy.enabled=true.")
        self.policy = policy
        self.model_dir = Path(model_dir).expanduser().resolve(strict=False)
        self.allow_model_download = bool(allow_model_download)
        self._model = None
        self._network_called = False

    @property
    def network_called(self) -> bool:
        return self._network_called

    def transcribe(self, audio_path: Path) -> NarrationTranscription:
        model = self._load_model()
        try:
            segments, info = model.transcribe(
                str(audio_path),
                language=self.policy.language,
                beam_size=5,
                word_timestamps=self.policy.word_timestamps,
                vad_filter=self.policy.vad_filter,
                condition_on_previous_text=False,
            )
            text = " ".join(segment.text.strip() for segment in segments).strip()
        except Exception as error:  # pragma: no cover - dependency boundary
            raise NarrationTranscriberUnavailableError(
                f"Faster-Whisper no pudo transcribir {audio_path.name}: {error}"
            ) from error
        return NarrationTranscription(
            text=text,
            detected_language=str(getattr(info, "language", "") or "") or None,
            language_probability=_optional_probability(
                getattr(info, "language_probability", None)
            ),
        )

    def _load_model(self):
        if self._model is not None:
            return self._model
        physical_model_dir = self._physical_model_dir()
        cached = _physical_model_is_ready(physical_model_dir)
        if not cached and not self.allow_model_download:
            raise NarrationTranscriberUnavailableError(
                "El modelo local Faster-Whisper no está en caché. Ejecuta primero "
                "build-assets para descargarlo sin usar un proveedor de pago."
            )
        self._network_called = bool(not cached and self.allow_model_download)
        if not cached:
            self._download_physical_model(physical_model_dir)
        try:
            from faster_whisper import WhisperModel
        except ImportError as error:  # pragma: no cover - dependency boundary
            raise NarrationTranscriberUnavailableError(
                "Falta faster-whisper. Instala las dependencias del repositorio."
            ) from error
        try:
            self._model = WhisperModel(
                str(physical_model_dir),
                device=self.policy.device,
                compute_type=self.policy.compute_type,
                local_files_only=True,
            )
        except Exception as error:  # pragma: no cover - dependency boundary
            raise NarrationTranscriberUnavailableError(
                f"No se pudo cargar el modelo local '{self.policy.model}': {error}"
            ) from error
        return self._model

    def _physical_model_dir(self) -> Path:
        model_name = re.sub(
            r"[^a-zA-Z0-9._-]+",
            "--",
            self.policy.model,
        ).strip(".-")
        if not model_name:
            raise NarrationTranscriberUnavailableError(
                "El nombre del modelo Faster-Whisper no es seguro."
            )
        return self.model_dir / "physical" / model_name

    def _download_physical_model(self, destination: Path) -> None:
        """Download regular files, never cache-snapshot symlinks on Windows."""

        try:
            from huggingface_hub import snapshot_download
        except ImportError as error:  # pragma: no cover - dependency boundary
            raise NarrationTranscriberUnavailableError(
                "Falta huggingface-hub para preparar el modelo local."
            ) from error
        repository_id = (
            self.policy.model
            if "/" in self.policy.model
            else f"Systran/faster-whisper-{self.policy.model}"
        )
        destination.mkdir(parents=True, exist_ok=True)
        arguments = {
            "repo_id": repository_id,
            "local_dir": str(destination),
            "allow_patterns": [
                "config.json",
                "preprocessor_config.json",
                "model.bin",
                "tokenizer.json",
                "vocabulary.*",
            ],
            "local_files_only": False,
        }
        if "local_dir_use_symlinks" in inspect.signature(snapshot_download).parameters:
            arguments["local_dir_use_symlinks"] = False
        try:
            snapshot_download(**arguments)
        except Exception as error:  # pragma: no cover - dependency boundary
            raise NarrationTranscriberUnavailableError(
                "No se pudo descargar el modelo como archivos físicos sin enlaces "
                f"simbólicos: {error}"
            ) from error
        if not _physical_model_is_ready(destination):
            raise NarrationTranscriberUnavailableError(
                "La descarga del modelo terminó incompleta; faltan archivos físicos."
            )


class NarrationConformanceGate:
    """Validate generated audio and persist a fail-closed acoustic decision."""

    def __init__(
        self,
        policy: NarrationConformancePolicy,
        transcriber: NarrationTranscriber,
        *,
        report_relative_path: str | Path = NARRATION_CONFORMANCE_RELATIVE_PATH,
        metadata_store: MetadataStore | None = None,
        adjudicator: NarrationTranscriber | None = None,
    ) -> None:
        if not isinstance(policy, NarrationConformancePolicy):
            raise TypeError("policy debe ser NarrationConformancePolicy.")
        if not policy.enabled:
            raise ValueError("NarrationConformanceGate requiere enabled=true.")
        self.policy = policy
        self.transcriber = transcriber
        self.adjudicator = adjudicator
        self.report_relative_path = _safe_relative(report_relative_path)
        if metadata_store is not None and not isinstance(metadata_store, MetadataStore):
            raise TypeError("metadata_store debe ser MetadataStore.")
        self.metadata_store = metadata_store
        self._synthesis_attempts: list[NarrationSynthesisAttempt] = []
        self._last_report: NarrationConformanceReport | None = None

    @property
    def network_called(self) -> bool:
        return bool(
            getattr(self.transcriber, "network_called", False)
            or (
                self.adjudicator is not None
                and getattr(self.adjudicator, "network_called", False)
            )
        )

    @property
    def last_report(self) -> NarrationConformanceReport | None:
        """Most recent durable decision from this gate instance."""

        return self._last_report

    def reset_attempt_history(self) -> None:
        """Start a new build without carrying attempts from an earlier build."""

        self._synthesis_attempts.clear()
        self._last_report = None

    def validate_and_persist(
        self,
        manifest: ProductionManifest,
        audio_paths_by_scene_id: dict[str, Path],
        *,
        project_path: str | Path,
        synthesis_voice_id: str | None = None,
    ) -> NarrationConformanceReport:
        """Listen to every clip, persist evidence, and raise on any divergence."""

        if not isinstance(manifest, ProductionManifest):
            raise TypeError("manifest debe ser ProductionManifest.")
        project = Path(project_path).expanduser().resolve(strict=False)
        clips: list[NarrationClipConformance] = []
        blockers: list[str] = []
        for scene in manifest.scenes:
            if scene.narration_text is None:
                continue
            path = audio_paths_by_scene_id.get(scene.scene_id)
            if path is None:
                blockers.append(f"missing_narration_audio:{scene.scene_id}")
                continue
            audio_path = Path(path).expanduser().resolve(strict=False)
            try:
                relative_path = audio_path.relative_to(project).as_posix()
                audio_sha256 = _sha256_path(audio_path)
                transcription = self.transcriber.transcribe(audio_path)
                expected_tokens = acoustic_tokens(scene.narration_text)
                observed_tokens = acoustic_tokens(transcription.text)
                differences = token_differences(expected_tokens, observed_tokens)
                adjudication_model: str | None = None
                adjudication_observed_text: str | None = None
                adjudication_tokens: tuple[str, ...] | None = None
                adjudication_differences: (
                    tuple[NarrationTokenDifference, ...] | None
                ) = None
                adjudication_error: str | None = None
                adjudication_approved: bool | None = None
                if differences and self.adjudicator is not None:
                    adjudication_model = self.policy.adjudication_model or str(
                        getattr(
                            getattr(self.adjudicator, "policy", None),
                            "model",
                            "secondary",
                        )
                    )
                    try:
                        adjudication = self.adjudicator.transcribe(audio_path)
                        adjudication_observed_text = adjudication.text
                        adjudication_tokens = acoustic_tokens(adjudication.text)
                        adjudication_differences = token_differences(
                            expected_tokens,
                            adjudication_tokens,
                        )
                        adjudication_approved = not adjudication_differences
                    except Exception as error:  # noqa: BLE001 - external engine boundary
                        adjudication_error = f"{type(error).__name__}: {error}"
                        adjudication_approved = False
                clip = NarrationClipConformance(
                    scene_id=scene.scene_id,
                    sequence=scene.sequence,
                    audio_relative_path=relative_path,
                    audio_sha256=audio_sha256,
                    canonical_text=scene.narration_text,
                    canonical_text_sha256=_sha256_text(scene.narration_text),
                    observed_text=transcription.text,
                    expected_tokens=expected_tokens,
                    observed_tokens=observed_tokens,
                    differences=differences,
                    detected_language=transcription.detected_language,
                    language_probability=transcription.language_probability,
                    adjudication_model=adjudication_model,
                    adjudication_observed_text=adjudication_observed_text,
                    adjudication_tokens=adjudication_tokens,
                    adjudication_differences=adjudication_differences,
                    adjudication_error=adjudication_error,
                    adjudication_approved=adjudication_approved,
                    approved=not differences or adjudication_approved is True,
                )
            # Fail closed for any injected ASR/runtime failure and preserve the
            # exception class in durable evidence instead of losing the gate.
            except Exception as error:  # noqa: BLE001 - external engine boundary
                message = f"{type(error).__name__}: {error}"
                try:
                    relative_path = audio_path.relative_to(project).as_posix()
                    audio_sha256 = _sha256_path(audio_path)
                except (OSError, ValueError):
                    relative_path = str(audio_path)
                    audio_sha256 = "0" * 64
                clip = NarrationClipConformance(
                    scene_id=scene.scene_id,
                    sequence=scene.sequence,
                    audio_relative_path=relative_path,
                    audio_sha256=audio_sha256,
                    canonical_text=scene.narration_text,
                    canonical_text_sha256=_sha256_text(scene.narration_text),
                    transcription_error=message,
                    approved=False,
                )
            clips.append(clip)
            if not clip.approved:
                blocker = (
                    "narration_transcription_unavailable"
                    if (
                        clip.transcription_error is not None
                        or clip.adjudication_error is not None
                    )
                    else "narration_acoustic_mismatch"
                )
                blockers.append(f"{blocker}:{scene.scene_id}")

        expected_count = sum(
            scene.narration_text is not None for scene in manifest.scenes
        )
        if len(clips) != expected_count and not blockers:
            blockers.append("narration_scene_count_mismatch")
        approved = not blockers and len(clips) == expected_count
        if synthesis_voice_id is not None:
            attempt = NarrationSynthesisAttempt(
                attempt=len(self._synthesis_attempts) + 1,
                voice_id=synthesis_voice_id,
                clips=tuple(clips),
                blockers=tuple(blockers),
                approved=approved,
            )
            self._synthesis_attempts.append(attempt)
        report = NarrationConformanceReport(
            manifest_id=manifest.manifest_id,
            project_id=manifest.project.project_id,
            policy=self.policy,
            clips=tuple(clips),
            blockers=tuple(blockers),
            approved=approved,
            synthesis_voice_id=synthesis_voice_id,
            synthesis_attempts=tuple(self._synthesis_attempts),
            network_called=self.network_called,
        )
        self._last_report = report
        report_path = project / self.report_relative_path
        payload = report.model_dump(mode="json")
        if self.metadata_store is None:
            _write_json_atomic(report_path, payload)
        else:
            report_hash = _sha256_text(
                json.dumps(
                    payload,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                    allow_nan=False,
                )
            )
            self.metadata_store.persist_metadata(
                workspace_root=project,
                relative_path=self.report_relative_path,
                content=payload,
                artifact_type="narration_acoustic_conformance",
                artifact_id=f"narration-conformance-{report_hash[:24]}",
                metadata={
                    "manifest_id": report.manifest_id,
                    "approved": report.approved,
                    "engine": report.policy.engine,
                    "model": report.policy.model,
                    "adjudication_model": report.policy.adjudication_model,
                    "synthesis_voice_id": report.synthesis_voice_id,
                    "synthesis_attempt_count": len(report.synthesis_attempts),
                    "render_performed": False,
                    "publication_performed": False,
                },
                collision_policy=CollisionPolicy.REPLACE,
            )
        if not report.approved:
            detail = _first_difference_detail(report)
            raise NarrationConformanceMismatchError(
                "El gate acústico bloqueó la narración antes del render"
                + (f": {detail}" if detail else ".")
            )
        return report


def inspect_narration_conformance(
    manifest: ProductionManifest,
    *,
    project_path: str | Path,
    audio_sha256_by_scene_id: dict[str, str],
    policy: NarrationConformancePolicy,
    report_relative_path: str | Path = NARRATION_CONFORMANCE_RELATIVE_PATH,
) -> NarrationConformanceInspection:
    """Verify durable evidence without invoking ASR during paid-render preparation."""

    project = Path(project_path).expanduser().resolve(strict=False)
    report_path = project / _safe_relative(report_relative_path)
    if not policy.enabled:
        return NarrationConformanceInspection(None, report_path, None, ())
    if not report_path.is_file():
        return NarrationConformanceInspection(
            None,
            report_path,
            None,
            ("narration_conformance_missing_or_stale",),
        )
    try:
        report = NarrationConformanceReport.model_validate_json(
            report_path.read_bytes()
        )
    except (OSError, UnicodeError, ValueError):
        return NarrationConformanceInspection(
            None,
            report_path,
            None,
            ("narration_conformance_missing_or_stale",),
        )
    stale = report.manifest_id != manifest.manifest_id or report.policy != policy
    expected_scenes = {
        scene.scene_id: scene
        for scene in manifest.scenes
        if scene.narration_text is not None
    }
    clips = {clip.scene_id: clip for clip in report.clips}
    stale = stale or set(clips) != set(expected_scenes)
    for scene_id, scene in expected_scenes.items():
        clip = clips.get(scene_id)
        if clip is None:
            stale = True
            continue
        stale = stale or clip.sequence != scene.sequence
        stale = stale or clip.canonical_text != scene.narration_text
        stale = stale or clip.canonical_text_sha256 != _sha256_text(
            scene.narration_text or ""
        )
        stale = stale or clip.audio_sha256 != audio_sha256_by_scene_id.get(scene_id)
    blockers: list[str] = []
    if stale:
        blockers.append("narration_conformance_missing_or_stale")
    rejected_clips = tuple(clip for clip in report.clips if not clip.approved)
    if any(
        clip.transcription_error is not None or clip.adjudication_error is not None
        for clip in rejected_clips
    ):
        blockers.append("narration_transcription_unavailable")
    if any(
        clip.differences or clip.adjudication_differences for clip in rejected_clips
    ):
        blockers.append("narration_acoustic_mismatch")
    return NarrationConformanceInspection(
        report=report,
        report_path=report_path,
        report_sha256=_sha256_path(report_path),
        blockers=tuple(blockers),
    )


def acoustic_tokens(text: str) -> tuple[str, ...]:
    """Normalize non-acoustic spelling details while preserving lexical identity."""

    decomposed = unicodedata.normalize("NFKD", str(text).casefold())
    without_marks = "".join(
        character for character in decomposed if not unicodedata.combining(character)
    )
    return tuple(re.findall(r"[^\W_]+", without_marks, flags=re.UNICODE))


def token_differences(
    expected: tuple[str, ...],
    observed: tuple[str, ...],
) -> tuple[NarrationTokenDifference, ...]:
    """Return deterministic word-level differences between two token streams."""

    matcher = difflib.SequenceMatcher(a=expected, b=observed, autojunk=False)
    differences: list[NarrationTokenDifference] = []
    for tag, first_start, first_end, second_start, second_end in matcher.get_opcodes():
        if tag == "equal":
            continue
        operation = {"insert": "insert", "delete": "delete", "replace": "replace"}[tag]
        differences.append(
            NarrationTokenDifference(
                operation=operation,
                expected=expected[first_start:first_end],
                observed=observed[second_start:second_end],
                expected_index=first_start,
                observed_index=second_start,
            )
        )
    return tuple(differences)


def _first_difference_detail(report: NarrationConformanceReport) -> str | None:
    for clip in report.clips:
        if clip.approved:
            continue
        if clip.transcription_error:
            return f"escena {clip.sequence}, {clip.transcription_error}"
        if clip.adjudication_error:
            return (
                f"escena {clip.sequence}, adjudicación "
                f"{clip.adjudication_model}: {clip.adjudication_error}"
            )
        decisive_differences = clip.adjudication_differences or clip.differences
        if decisive_differences:
            difference = decisive_differences[0]
            expected = " ".join(difference.expected) or "∅"
            observed = " ".join(difference.observed) or "∅"
            stage = (
                f"adjudicación {clip.adjudication_model}, "
                if clip.adjudication_differences is not None
                else ""
            )
            return (
                f"escena {clip.sequence}, {stage}{difference.operation}: "
                f"'{expected}' → '{observed}'"
            )
    return None


def _physical_model_is_ready(path: Path) -> bool:
    required = ("config.json", "model.bin", "tokenizer.json")
    return all((path / filename).is_file() for filename in required) and any(
        path.glob("vocabulary.*")
    )


def _safe_relative(value: str | Path) -> Path:
    path = Path(str(value).replace("\\", "/"))
    if path.is_absolute() or not path.parts or ".." in path.parts:
        raise ValueError("La ruta de evidencia acústica debe ser relativa y confinada.")
    return path


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_json_atomic(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _optional_probability(value: object) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        probability = float(value)
    except (TypeError, ValueError):
        return None
    return probability if 0.0 <= probability <= 1.0 else None


__all__ = [
    "NARRATION_CONFORMANCE_RELATIVE_PATH",
    "FasterWhisperTranscriber",
    "NarrationClipConformance",
    "NarrationConformanceError",
    "NarrationConformanceGate",
    "NarrationConformanceInspection",
    "NarrationConformanceMismatchError",
    "NarrationConformancePolicy",
    "NarrationConformanceReport",
    "NarrationSynthesisAttempt",
    "NarrationTokenDifference",
    "NarrationTranscriber",
    "NarrationTranscriberUnavailableError",
    "NarrationTranscription",
    "acoustic_tokens",
    "inspect_narration_conformance",
    "token_differences",
]
