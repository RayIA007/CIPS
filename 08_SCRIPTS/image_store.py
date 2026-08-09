"""
=========================================================
Proyecto : CIPS
Release  : 0.8
Build    : 068-F3.3
Archivo  : image_store.py
Estado   : FASE 3.3
=========================================================

Store especializado para artefactos de imagen binarios.
No genera, decodifica, redimensiona ni crea thumbnails en F3.3.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from artifact_store import ArtifactStore, ArtifactWriteResult, CollisionPolicy
from master_producer_models import SpecialistRole


_IMAGE_MIME_BY_SUFFIX: dict[str, tuple[str, ...]] = {
    ".png": ("image/png",),
    ".jpg": ("image/jpeg",),
    ".jpeg": ("image/jpeg",),
    ".webp": ("image/webp",),
    ".gif": ("image/gif",),
    ".svg": ("image/svg+xml",),
    ".bmp": ("image/bmp",),
    ".tif": ("image/tiff",),
    ".tiff": ("image/tiff",),
    ".avif": ("image/avif",),
}


class ImageStore(ArtifactStore):
    """Persistencia binaria de imágenes con validación MIME/extensión."""

    @property
    def media_type(self) -> str:
        return "image"

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
            raise ValueError("ImageStore no persiste imágenes vacías.")
        resolved_mime = self._resolve_image_mime(relative_path, mime_type)
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

    def persist_image(
        self,
        *,
        workspace_root: str | Path,
        relative_path: str | Path,
        content: bytes | bytearray | memoryview,
        artifact_type: str = "image",
        mime_type: str | None = None,
        metadata: Mapping[str, Any] | None = None,
        artifact_id: str | None = None,
        producer_role: SpecialistRole | str = SpecialistRole.MASTER_PRODUCER,
        created_at: str | None = None,
        collision_policy: CollisionPolicy | str = CollisionPolicy.REUSE_IDENTICAL,
    ) -> ArtifactWriteResult:
        resolved_mime = self._resolve_image_mime(relative_path, mime_type)
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
    def _resolve_image_mime(relative_path: str | Path, mime_type: str | None) -> str:
        suffix = Path(str(relative_path)).suffix.lower()
        allowed = _IMAGE_MIME_BY_SUFFIX.get(suffix)
        if allowed is None:
            raise ValueError(
                f"Extensión de imagen no soportada por ImageStore: {suffix or '<sin extensión>'}"
            )
        resolved = allowed[0] if mime_type is None else str(mime_type).strip().lower()
        if not resolved.startswith("image/"):
            raise ValueError("ImageStore requiere un mime_type de familia image/*.")
        if resolved not in allowed:
            raise ValueError(f"mime_type '{resolved}' incompatible con la extensión {suffix}.")
        return resolved


def get_image_store_info() -> dict[str, object]:
    return {
        "component": "image_store",
        "version": "0.8",
        "build": "068-F3.3",
        "media_type": "image",
        "supported_suffixes": sorted(_IMAGE_MIME_BY_SUFFIX),
    }
