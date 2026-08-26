"""Physical MP4 validation for PM9 using the installed FFprobe binary."""

from __future__ import annotations

import hashlib
import json
import subprocess
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from .models import MediaCheck, MediaProbeReport


class MediaProbeError(RuntimeError):
    """FFprobe could not produce trustworthy technical evidence."""


ProbeRunner = Callable[[Sequence[str]], Mapping[str, Any]]


class FFprobeInspector:
    """Inspect a physical render and evaluate the PM9 technical gate."""

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

    def inspect(
        self,
        path: str | Path,
        *,
        expected_width: int,
        expected_height: int,
        expected_fps: float,
        expected_duration_seconds: float,
        duration_tolerance_seconds: float = 1.0,
        fps_tolerance: float = 0.15,
    ) -> MediaProbeReport:
        media_path = Path(path).expanduser().resolve(strict=False)
        if not media_path.is_file() or media_path.stat().st_size <= 0:
            raise MediaProbeError(f"No existe un MP4 físico utilizable: {media_path}")
        if media_path.suffix.lower() != ".mp4":
            raise MediaProbeError("PM9 requiere una salida física con extensión .mp4.")

        command = (
            self._executable,
            "-v",
            "error",
            "-show_format",
            "-show_streams",
            "-of",
            "json",
            str(media_path),
        )
        try:
            raw = self._runner(command)
        except MediaProbeError:
            raise
        except Exception as error:
            raise MediaProbeError(
                f"FFprobe falló: {type(error).__name__}: {error}"
            ) from error
        if not isinstance(raw, Mapping):
            raise MediaProbeError("FFprobe no devolvió un objeto JSON.")

        streams = raw.get("streams")
        format_data = raw.get("format")
        if not isinstance(streams, list) or not isinstance(format_data, Mapping):
            raise MediaProbeError("FFprobe no devolvió streams/format válidos.")
        video_streams = [
            item
            for item in streams
            if isinstance(item, Mapping) and item.get("codec_type") == "video"
        ]
        audio_streams = [
            item
            for item in streams
            if isinstance(item, Mapping) and item.get("codec_type") == "audio"
        ]
        if len(video_streams) != 1:
            raise MediaProbeError("PM9 requiere exactamente un stream de video.")
        if not audio_streams:
            raise MediaProbeError("PM9 requiere al menos un stream de audio.")

        video = video_streams[0]
        audio = audio_streams[0]
        width = _positive_int(video.get("width"), "width")
        height = _positive_int(video.get("height"), "height")
        fps = _frame_rate(video.get("avg_frame_rate") or video.get("r_frame_rate"))
        duration = _positive_float(
            format_data.get("duration") or video.get("duration"),
            "duration",
        )
        sample_rate = _positive_int(audio.get("sample_rate"), "sample_rate")
        video_codec = _required_text(video.get("codec_name"), "video codec")
        audio_codec = _required_text(audio.get("codec_name"), "audio codec")
        formats = tuple(
            sorted(
                {
                    item.strip().lower()
                    for item in str(format_data.get("format_name", "")).split(",")
                    if item.strip()
                }
            )
        )
        if not formats:
            raise MediaProbeError("FFprobe no identificó el contenedor multimedia.")

        checks = (
            MediaCheck(
                check_id="container-mp4",
                passed=bool({"mp4", "mov"} & set(formats)),
                expected="mp4/mov",
                actual=",".join(formats),
            ),
            MediaCheck(
                check_id="vertical-resolution",
                passed=width == int(expected_width) and height == int(expected_height),
                expected=f"{int(expected_width)}x{int(expected_height)}",
                actual=f"{width}x{height}",
            ),
            MediaCheck(
                check_id="frame-rate",
                passed=abs(fps - float(expected_fps)) <= float(fps_tolerance),
                expected=f"{float(expected_fps):.3f} fps ± {float(fps_tolerance):.3f}",
                actual=f"{fps:.3f} fps",
            ),
            MediaCheck(
                check_id="duration",
                passed=(
                    abs(duration - float(expected_duration_seconds))
                    <= float(duration_tolerance_seconds)
                ),
                expected=(
                    f"{float(expected_duration_seconds):.3f} s "
                    f"± {float(duration_tolerance_seconds):.3f}"
                ),
                actual=f"{duration:.3f} s",
            ),
            MediaCheck(
                check_id="video-stream",
                passed=bool(video_codec),
                expected="codec de video identificable",
                actual=video_codec,
            ),
            MediaCheck(
                check_id="audio-stream",
                passed=bool(audio_codec and sample_rate > 0),
                expected="audio con codec y sample rate",
                actual=f"{audio_codec} @ {sample_rate} Hz",
            ),
        )
        return MediaProbeReport(
            file_sha256=_sha256(media_path),
            size_bytes=media_path.stat().st_size,
            format_names=formats,
            duration_seconds=duration,
            width_px=width,
            height_px=height,
            fps=fps,
            video_codec=video_codec,
            audio_codec=audio_codec,
            audio_sample_rate_hz=sample_rate,
            checks=checks,
        )

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
            raise MediaProbeError(
                f"No fue posible ejecutar FFprobe: {type(error).__name__}: {error}"
            ) from error
        if completed.returncode != 0:
            details = completed.stderr.strip() or "sin detalle"
            raise MediaProbeError(
                f"FFprobe terminó con código {completed.returncode}: {details}"
            )
        try:
            parsed = json.loads(completed.stdout)
        except json.JSONDecodeError as error:
            raise MediaProbeError("FFprobe devolvió JSON inválido.") from error
        if not isinstance(parsed, Mapping):
            raise MediaProbeError("FFprobe devolvió una raíz JSON inválida.")
        return parsed


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _required_text(value: Any, label: str) -> str:
    normalized = str(value or "").strip().lower()
    if not normalized:
        raise MediaProbeError(f"FFprobe no devolvió {label}.")
    return normalized


def _positive_int(value: Any, label: str) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError) as error:
        raise MediaProbeError(f"FFprobe devolvió {label} inválido.") from error
    if number <= 0:
        raise MediaProbeError(f"FFprobe devolvió {label} no positivo.")
    return number


def _positive_float(value: Any, label: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as error:
        raise MediaProbeError(f"FFprobe devolvió {label} inválido.") from error
    if number <= 0.0:
        raise MediaProbeError(f"FFprobe devolvió {label} no positivo.")
    return round(number, 6)


def _frame_rate(value: Any) -> float:
    text = str(value or "").strip()
    if not text:
        raise MediaProbeError("FFprobe no devolvió frame rate.")
    if "/" in text:
        numerator, denominator = text.split("/", 1)
        try:
            denominator_value = float(denominator)
            if denominator_value == 0.0:
                raise ValueError("denominador cero")
            value = float(numerator) / denominator_value
        except ValueError as error:
            raise MediaProbeError("FFprobe devolvió frame rate inválido.") from error
    else:
        value = _positive_float(text, "frame rate")
    if value <= 0.0:
        raise MediaProbeError("FFprobe devolvió frame rate no positivo.")
    return round(value, 6)


__all__ = ["FFprobeInspector", "MediaProbeError", "ProbeRunner"]
