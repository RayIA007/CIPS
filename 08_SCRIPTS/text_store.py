"""
=========================================================
Proyecto : CIPS
Release  : 0.8
Build    : 067-F3.3
Archivo  : text_store.py
Estado   : FASE 3.3
=========================================================

Store especializado para artefactos textuales.

Reglas F3.3:
- UTF-8 sin BOM por defecto para conservar el comportamiento actual de CIPS.
- No procesa ni transforma semánticamente el texto.
- Valida que MIME y extensión pertenezcan a la familia textual soportada.
- Delega hashing, sidecar, deduplicación, idempotencia y colisiones a ArtifactStore.
"""

from __future__ import annotations

import codecs
from pathlib import Path
from typing import Any, Mapping

from artifact_store import ArtifactStore, ArtifactWriteResult, CollisionPolicy
from master_producer_models import SpecialistRole


_TEXT_MIME_BY_SUFFIX: dict[str, str] = {
    ".md": "text/markdown",
    ".txt": "text/plain",
    ".html": "text/html",
    ".htm": "text/html",
    ".csv": "text/csv",
    ".css": "text/css",
    ".xml": "text/xml",
    ".yaml": "text/yaml",
    ".yml": "text/yaml",
    ".srt": "text/plain",
    ".vtt": "text/vtt",
}


class TextStore(ArtifactStore):
    """Persistencia de contenido textual sin imponer procesamiento adicional."""

    @property
    def media_type(self) -> str:
        return "text"

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
        resolved_mime = self._resolve_text_mime(relative_path, mime_type)
        return super().persist_bytes(
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

    def persist_text(
        self,
        *,
        workspace_root: str | Path,
        relative_path: str | Path,
        content: str,
        artifact_type: str = "text",
        mime_type: str | None = None,
        encoding: str = "utf-8",
        metadata: Mapping[str, Any] | None = None,
        artifact_id: str | None = None,
        producer_role: SpecialistRole | str = SpecialistRole.MASTER_PRODUCER,
        created_at: str | None = None,
        collision_policy: CollisionPolicy | str = CollisionPolicy.REUSE_IDENTICAL,
    ) -> ArtifactWriteResult:
        if not isinstance(content, str):
            raise TypeError("content debe ser str para TextStore.persist_text().")

        normalized_encoding = codecs.lookup(str(encoding or "").strip()).name
        resolved_mime = self._resolve_text_mime(relative_path, mime_type)
        event_metadata = dict(metadata or {})
        event_metadata.setdefault("encoding", normalized_encoding)

        return self.persist_bytes(
            workspace_root=workspace_root,
            relative_path=relative_path,
            content=content.encode(normalized_encoding),
            artifact_type=artifact_type,
            mime_type=resolved_mime,
            metadata=event_metadata,
            artifact_id=artifact_id,
            producer_role=producer_role,
            created_at=created_at,
            collision_policy=collision_policy,
        )

    @staticmethod
    def _resolve_text_mime(relative_path: str | Path, mime_type: str | None) -> str:
        suffix = Path(str(relative_path)).suffix.lower()
        expected = _TEXT_MIME_BY_SUFFIX.get(suffix)
        if expected is None:
            raise ValueError(f"Extensión textual no soportada por TextStore: {suffix or '<sin extensión>'}")

        resolved = expected if mime_type is None else str(mime_type).strip().lower()
        if not resolved.startswith("text/"):
            raise ValueError("TextStore requiere un mime_type de familia text/*.")
        if resolved != expected:
            raise ValueError(
                f"mime_type incompatible con {suffix}: se esperaba '{expected}' y se recibió '{resolved}'."
            )
        return resolved


def get_text_store_info() -> dict[str, object]:
    return {
        "component": "text_store",
        "version": "0.8",
        "build": "067-F3.3",
        "media_type": "text",
        "default_encoding": "utf-8",
        "supported_suffixes": sorted(_TEXT_MIME_BY_SUFFIX),
    }
