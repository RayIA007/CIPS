from __future__ import annotations

import re
from pathlib import Path

from moviepy import AudioFileClip


_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?¡¿])\s+")
_WHITESPACE_RE = re.compile(r"\s+")
_MARKDOWN_RE = re.compile(r"[#*_`~]+")


def _clean_text(text: str) -> str:
    text = _MARKDOWN_RE.sub("", str(text or ""))
    return _WHITESPACE_RE.sub(" ", text).strip()


def _caption_chunks(text: str, max_chars: int = 84) -> list[str]:
    cleaned = _clean_text(text)
    if not cleaned:
        return []

    sentences = [item.strip() for item in _SENTENCE_SPLIT_RE.split(cleaned) if item.strip()]
    chunks: list[str] = []

    for sentence in sentences or [cleaned]:
        words = sentence.split()
        current: list[str] = []
        current_length = 0
        for word in words:
            projected = current_length + (1 if current else 0) + len(word)
            if current and projected > max_chars:
                chunks.append(" ".join(current))
                current = [word]
                current_length = len(word)
            else:
                current.append(word)
                current_length = projected
        if current:
            chunks.append(" ".join(current))

    return chunks


def _format_srt_timestamp(seconds: float) -> str:
    milliseconds = max(0, int(round(float(seconds) * 1000)))
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def generar_subtitulos_desde_narracion(proyecto_dir: Path) -> Path:
    """Genera SRT determinista usando narración textual y duración real del audio."""

    proyecto_dir = Path(proyecto_dir)
    narration_path = proyecto_dir / "narration" / "narration.txt"
    audio_path = proyecto_dir / "voice" / "audio.mp3"
    output_path = proyecto_dir / "subtitles" / "subtitles.srt"

    if not narration_path.is_file():
        raise FileNotFoundError(f"Narración no encontrada: {narration_path}")
    if not audio_path.is_file():
        raise FileNotFoundError(f"Audio no encontrado: {audio_path}")

    narration = narration_path.read_text(encoding="utf-8").strip()
    chunks = _caption_chunks(narration)
    if not chunks:
        raise ValueError("La narración está vacía y no permite generar subtítulos.")

    audio_clip = AudioFileClip(str(audio_path))
    try:
        duration = float(audio_clip.duration or 0.0)
    finally:
        audio_clip.close()

    if duration <= 0:
        raise ValueError("La duración del audio debe ser mayor que cero.")

    weights = [max(1, len(chunk.split())) for chunk in chunks]
    total_weight = sum(weights)
    elapsed = 0.0
    blocks: list[str] = []

    for index, (chunk, weight) in enumerate(zip(chunks, weights), start=1):
        start = elapsed
        if index == len(chunks):
            end = duration
        else:
            end = min(duration, start + duration * (weight / total_weight))
        if end <= start:
            end = min(duration, start + 0.001)
        blocks.append(
            f"{index}\n"
            f"{_format_srt_timestamp(start)} --> {_format_srt_timestamp(end)}\n"
            f"{chunk}\n"
        )
        elapsed = end

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(blocks).rstrip() + "\n", encoding="utf-8")
    return output_path
