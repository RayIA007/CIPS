"""
=========================================================
Proyecto : CIPS
Release  : 0.8
Build    : 071-F3.3
Archivo  : metadata_store.py
Estado   : FASE 3.3
=========================================================

Store especializado para documentos JSON de metadata.
No sustituye sidecars *.meta.json ni MANIFEST.json.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from artifact_store import ArtifactStore, ArtifactWriteResult, CollisionPolicy
from master_producer_models import SpecialistRole


class MetadataStore(ArtifactStore):
    """Persistencia determinista de metadata JSON como artefacto independiente."""

    @property
    def media_type(self) -> str:
        return "metadata"

    def persist_metadata(
        self,
        *,
        workspace_root: str | Path,
        relative_path: str | Path,
        content: Mapping[str, Any],
        artifact_type: str = "metadata",
        metadata: Mapping[str, Any] | None = None,
        artifact_id: str | None = None,
        producer_role: SpecialistRole | str = SpecialistRole.MASTER_PRODUCER,
        created_at: str | None = None,
        collision_policy: CollisionPolicy | str = CollisionPolicy.REUSE_IDENTICAL,
    ) -> ArtifactWriteResult:
        if not isinstance(content, Mapping):
            raise TypeError("content debe ser Mapping para MetadataStore.persist_metadata().")
        self._validate_metadata_path(relative_path)
        safe_content = self._json_safe(dict(content))
        encoded = json.dumps(
            safe_content,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ).encode("utf-8")
        event_metadata = dict(metadata or {})
        event_metadata.setdefault("encoding", "utf-8")
        event_metadata.setdefault("format", "json")
        return super().persist_bytes(
            workspace_root=workspace_root,
            relative_path=relative_path,
            content=encoded,
            artifact_type=artifact_type,
            mime_type="application/json",
            metadata=event_metadata,
            artifact_id=artifact_id,
            producer_role=producer_role,
            created_at=created_at,
            collision_policy=collision_policy,
        )

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
        self._validate_metadata_path(relative_path)
        if str(mime_type).strip().lower() != "application/json":
            raise ValueError("MetadataStore requiere mime_type='application/json'.")
        payload = self._normalize_bytes(content)
        try:
            decoded = payload.decode("utf-8")
            parsed = json.loads(decoded)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("MetadataStore requiere JSON UTF-8 válido.") from exc
        if not isinstance(parsed, dict):
            raise ValueError("MetadataStore requiere un objeto JSON en la raíz.")
        return super().persist_bytes(
            workspace_root=workspace_root,
            relative_path=relative_path,
            content=payload,
            artifact_type=artifact_type,
            mime_type="application/json",
            metadata=metadata,
            artifact_id=artifact_id,
            producer_role=producer_role,
            created_at=created_at,
            collision_policy=collision_policy,
        )

    @staticmethod
    def _validate_metadata_path(relative_path: str | Path) -> None:
        text = str(relative_path).replace("\\", "/").lower()
        if not text.endswith(".json"):
            raise ValueError("MetadataStore requiere extensión .json.")
        if text.endswith(".meta.json"):
            raise ValueError("La terminación .meta.json está reservada para sidecars de ArtifactStore.")


def get_metadata_store_info() -> dict[str, object]:
    return {
        "component": "metadata_store",
        "version": "0.8",
        "build": "071-F3.3",
        "media_type": "metadata",
        "mime_type": "application/json",
        "reserved_suffix": ".meta.json",
    }
