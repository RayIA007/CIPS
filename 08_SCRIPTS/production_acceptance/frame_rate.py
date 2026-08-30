"""Provider-neutral PM9 frame-rate policy and local FFmpeg normalization."""

from __future__ import annotations

import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

from artifact_store import CollisionPolicy
from video_store import VideoStore
from workspace_resolver import WorkspaceResolver

from .media_probe import FFprobeInspector
from .models import (
    FrameRateAction,
    FrameRateEvidence,
    FrameRateMode,
    FrameRatePolicy,
    FrameRateTransformationEvidence,
    MediaProbeReport,
)


class FrameRateProcessingError(RuntimeError):
    """The physical FPS boundary could not produce trustworthy evidence."""


FFmpegRunner = Callable[[Sequence[str]], subprocess.CompletedProcess[str]]


@dataclass(frozen=True, slots=True)
class FrameRateProcessingResult:
    """Effective MP4 plus its durable provider-neutral FPS evidence."""

    output_path: Path
    output_probe: MediaProbeReport
    evidence: FrameRateEvidence


class FrameRateProcessor:
    """Apply strict, accepted-source, or normalize-to-manifest FPS policy."""

    def __init__(
        self,
        workspace_resolver: WorkspaceResolver,
        *,
        inspector: FFprobeInspector | None = None,
        video_store: VideoStore | None = None,
        executable: str = "ffmpeg",
        runner: FFmpegRunner | None = None,
    ) -> None:
        if not isinstance(workspace_resolver, WorkspaceResolver):
            raise TypeError("workspace_resolver debe ser WorkspaceResolver.")
        resolved_executable = str(executable).strip()
        if not resolved_executable:
            raise ValueError("executable no puede estar vacío.")
        self.workspace_resolver = workspace_resolver
        self.inspector = inspector or FFprobeInspector()
        self.video_store = video_store or VideoStore(workspace_resolver)
        if self.video_store.workspace_resolver is not workspace_resolver:
            raise ValueError("video_store debe compartir WorkspaceResolver.")
        self._executable = resolved_executable
        self._runner = runner or self._run_ffmpeg

    def process(
        self,
        input_path: str | Path,
        *,
        workspace_root: str | Path,
        input_artifact_id: str,
        normalized_relative_path: str | Path,
        policy: FrameRatePolicy,
        target_fps: float,
        expected_width: int,
        expected_height: int,
        expected_duration_seconds: float,
    ) -> FrameRateProcessingResult:
        if not isinstance(policy, FrameRatePolicy):
            raise TypeError("policy debe ser FrameRatePolicy.")
        source = Path(input_path).expanduser().resolve(strict=False)
        workspace = Path(workspace_root).expanduser().resolve(strict=False)
        source_probe = self.inspector.inspect(
            source,
            expected_width=expected_width,
            expected_height=expected_height,
            expected_fps=target_fps,
            acceptable_fps=policy.accepted_fps(target_fps),
            fps_tolerance=policy.tolerance_fps,
            expected_duration_seconds=expected_duration_seconds,
        )
        source_locator = _locator(source, workspace)
        if not source_probe.approved:
            evidence = _unchanged_evidence(
                policy=policy,
                action=FrameRateAction.BLOCKED,
                target_fps=target_fps,
                artifact_id=input_artifact_id,
                locator=source_locator,
                probe=source_probe,
            )
            return FrameRateProcessingResult(source, source_probe, evidence)

        at_target = _within_tolerance(
            source_probe.fps,
            target_fps,
            policy.tolerance_fps,
        )
        if at_target or policy.mode is FrameRateMode.STRICT:
            evidence = _unchanged_evidence(
                policy=policy,
                action=FrameRateAction.PASSTHROUGH,
                target_fps=target_fps,
                artifact_id=input_artifact_id,
                locator=source_locator,
                probe=source_probe,
            )
            return FrameRateProcessingResult(source, source_probe, evidence)
        if policy.mode is FrameRateMode.ACCEPT_SOURCE:
            evidence = _unchanged_evidence(
                policy=policy,
                action=FrameRateAction.ACCEPTED_SOURCE,
                target_fps=target_fps,
                artifact_id=input_artifact_id,
                locator=source_locator,
                probe=source_probe,
            )
            return FrameRateProcessingResult(source, source_probe, evidence)

        filter_value = f"fps=fps={_fps_text(target_fps)}:round=near"
        with TemporaryDirectory(prefix="cips-pm9-fps-") as temporary:
            candidate = Path(temporary) / "normalized.mp4"
            command = (
                self._executable,
                "-v",
                "error",
                "-nostdin",
                "-i",
                str(source),
                "-map",
                "0:v:0",
                "-map",
                "0:a:0?",
                "-vf",
                filter_value,
                "-c:v",
                "libx264",
                "-preset",
                "medium",
                "-crf",
                "18",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "copy",
                "-map_metadata",
                "-1",
                "-map_chapters",
                "-1",
                "-movflags",
                "+faststart",
                "-y",
                str(candidate),
            )
            completed = self._runner(command)
            if completed.returncode != 0 or not candidate.is_file():
                detail = str(completed.stderr or "").strip() or "sin detalle"
                raise FrameRateProcessingError(
                    f"FFmpeg no pudo normalizar el FPS: {detail}"
                )
            output_probe = self.inspector.inspect(
                candidate,
                expected_width=expected_width,
                expected_height=expected_height,
                expected_fps=target_fps,
                fps_tolerance=policy.tolerance_fps,
                expected_duration_seconds=expected_duration_seconds,
            )
            if not output_probe.approved:
                failures = ", ".join(
                    check.check_id
                    for check in output_probe.checks
                    if not check.passed
                )
                raise FrameRateProcessingError(
                    "La salida normalizada no superó validación física: " + failures
                )
            tool_version = self._tool_version()
            write = self.video_store.persist_video(
                workspace_root=workspace,
                relative_path=normalized_relative_path,
                content=candidate.read_bytes(),
                artifact_type="frame_rate_normalized_video",
                mime_type="video/mp4",
                artifact_id=f"fps-normalized-{output_probe.file_sha256[:24]}",
                metadata={
                    "source_artifact_id": input_artifact_id,
                    "source_content_sha256": source_probe.file_sha256,
                    "source_fps": source_probe.fps,
                    "target_fps": float(target_fps),
                    "video_filter": filter_value,
                    "video_codec": "libx264",
                    "audio_strategy": "copy",
                    "temporal_strategy": "duplicate_drop_nearest",
                    "pixel_format": "yuv420p",
                    "quality_profile": "crf18-medium",
                    "tool": "ffmpeg",
                    "tool_version": tool_version,
                    "actual_cost_usd": 0.0,
                    "network_called": False,
                    "publication_performed": False,
                },
                collision_policy=CollisionPolicy.REUSE_IDENTICAL,
            )

        output_path = Path(write.artifact.path).resolve(strict=False)
        evidence = FrameRateEvidence(
            policy=policy,
            action=FrameRateAction.NORMALIZED,
            target_fps=float(target_fps),
            input_artifact_id=input_artifact_id,
            output_artifact_id=write.artifact.artifact_id,
            input_locator=source_locator,
            output_locator=_locator(output_path, workspace),
            input_probe=source_probe,
            output_probe=output_probe,
            transformation=FrameRateTransformationEvidence(
                tool_version=tool_version,
                video_filter=filter_value,
            ),
        )
        return FrameRateProcessingResult(output_path, output_probe, evidence)

    def _tool_version(self) -> str:
        completed = self._runner((self._executable, "-version"))
        first_line = str(completed.stdout or "").splitlines()
        if completed.returncode != 0 or not first_line or not first_line[0].strip():
            raise FrameRateProcessingError("FFmpeg no devolvió una versión auditable.")
        return first_line[0].strip()

    @staticmethod
    def _run_ffmpeg(command: Sequence[str]) -> subprocess.CompletedProcess[str]:
        try:
            return subprocess.run(
                list(command),
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=1800,
            )
        except (OSError, subprocess.SubprocessError) as error:
            raise FrameRateProcessingError(
                f"No fue posible ejecutar FFmpeg: {type(error).__name__}: {error}"
            ) from error


def _unchanged_evidence(
    *,
    policy: FrameRatePolicy,
    action: FrameRateAction,
    target_fps: float,
    artifact_id: str,
    locator: str,
    probe: MediaProbeReport,
) -> FrameRateEvidence:
    return FrameRateEvidence(
        policy=policy,
        action=action,
        target_fps=float(target_fps),
        input_artifact_id=artifact_id,
        output_artifact_id=artifact_id,
        input_locator=locator,
        output_locator=locator,
        input_probe=probe,
        output_probe=probe,
    )


def _within_tolerance(observed: float, expected: float, tolerance: float) -> bool:
    return abs(float(observed) - float(expected)) <= float(tolerance)


def _fps_text(value: float) -> str:
    number = float(value)
    return str(int(number)) if number.is_integer() else f"{number:.6f}".rstrip("0")


def _locator(path: Path, workspace: Path) -> str:
    try:
        return path.relative_to(workspace).as_posix()
    except ValueError:
        return f"external/{path.name}"


__all__ = [
    "FFmpegRunner",
    "FrameRateProcessingError",
    "FrameRateProcessingResult",
    "FrameRateProcessor",
]
