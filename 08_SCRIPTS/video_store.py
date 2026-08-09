"""
=========================================================
Proyecto : CIPS
Release  : 0.8
Build    : 070-F3.3
Archivo  : video_store.py
Estado   : FASE 3.3
=========================================================

Store especializado para artefactos de video binarios.
No transcodifica, extrae frames ni inspecciona codecs en F3.3.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from artifact_store import ArtifactStore, ArtifactWriteResult, CollisionPolicy
from master_producer_models import SpecialistRole


_VIDEO_MIME_BY_SUFFIX: dict[str, tuple[str, ...]] = {
    ".mp4": ("video/mp4",),
    ".m4v": ("video/mp4", "video/x-m4v"),
    ".mov": ("video/quicktime",),
    ".webm": ("video/webm",),
    ".mkv": ("video/x-matroska",),
    ".avi": ("video/x-msvideo",),
    ".mpeg": ("video/mpeg",),
    ".mpg": ("video/mpeg",),
}


class VideoStore(ArtifactStore):
    """Persistencia binaria de video con validación MIME/extensión."""

    @property
    def media_type(self) -> str:
        return "video"

    def persist_bytes(
        self,
        *,
        workspace_root: str | Path,
        relative_path: str | Path,
        content: bytes | bytearray | memoryview,
        artifact_type: str,
        mime_type: str,
        metadata: Mapping[str, Any] | None = None,
        artifact_id: str | None = None,
        producer_role: SpecialistRole | str = SpecialistRole.MASTER_PRODUCER,
        created_at: str | None = None,
        collision_policy: CollisionPolicy | str = CollisionPolicy.REUSE_IDENTICAL,
    ) -> ArtifactWriteResult:
        payload = self._normalize_bytes(content)
        if not payload:
            raise ValueError("VideoStore no persiste video vacío.")
        resolved_mime = self._resolve_video_mime(relative_path, mime_type)
        return super().persist_bytes(
            workspace_root=workspace_root,
            relative_path=relative_path,
            content=payload,
            artifact_type=artifact_type,
            mime_type=resolved_mime,
            metadata=metadata,
            artifact_id=artifact_id,
            producer_role=producer_role,
            created_at=created_at,
            collision_policy=collision_policy,
        )

    def persist_video(
        self,
        *,
        workspace_root: str | Path,
        relative_path: str | Path,
        content: bytes | bytearray | memoryview,
        artifact_type: str = "video",
        mime_type: str | None = None,
        metadata: Mapping[str, Any] | None = None,
        artifact_id: str | None = None,
        producer_role: SpecialistRole | str = SpecialistRole.MASTER_PRODUCER,
        created_at: str | None = None,
        collision_policy: CollisionPolicy | str = CollisionPolicy.REUSE_IDENTICAL,
    ) -> ArtifactWriteResult:
        resolved_mime = self._resolve_video_mime(relative_path, mime_type)
        return self.persist_bytes(
            workspace_root=workspace_root,
            relative_path=relative_path,
            content=content,
            artifact_type=artifact_type,
            mime_type=resolved_mime,
            metadata=metadata,
            artifact_id=artifact_id,
            producer_role=producer_role,
            created_at=created_at,
            collision_policy=collision_policy,
        )

    @staticmethod
    def _resolve_video_mime(relative_path: str | Path, mime_type: str | None) -> str:
        suffix = Path(str(relative_path)).suffix.lower()
        allowed = _VIDEO_MIME_BY_SUFFIX.get(suffix)
        if allowed is None:
            raise ValueError(
                f"Extensión de video no soportada por VideoStore: {suffix or '<sin extensión>'}"
            )
        resolved = allowed[0] if mime_type is None else str(mime_type).strip().lower()
        if not resolved.startswith("video/"):
            raise ValueError("VideoStore requiere un mime_type de familia video/*.")
        if resolved not in allowed:
            raise ValueError(f"mime_type '{resolved}' incompatible con la extensión {suffix}.")
        return resolved


def get_video_store_info() -> dict[str, object]:
    return {
        "component": "video_store",
        "version": "0.8",
        "build": "070-F3.3",
        "media_type": "video",
        "supported_suffixes": sorted(_VIDEO_MIME_BY_SUFFIX),
    }
