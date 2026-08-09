"""
=========================================================
Proyecto : CIPS
Release  : 0.8
Build    : 066-F3.2
Archivo  : artifact_store.py
Estado   : FASE 3.2
=========================================================

Contrato común de persistencia segura para artefactos CIPS.

Responsabilidades:
- Persistir bytes dentro de un workspace autorizado.
- Calcular identidad de contenido mediante SHA-256.
- Crear y actualizar sidecars ``<artifact>.<ext>.meta.json``.
- Deduplicar contenido idéntico de forma determinista.
- Preservar idempotencia cuando se reutiliza ``artifact_id``.
- Aplicar políticas explícitas de colisión.
- Reutilizar ``ProductionArtifact`` como referencia lógica pública.

Este módulo NO procesa medios, NO genera contenido y NO sustituye
``ManifestEngine`` ni ``ProjectManifest``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, is_dataclass
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
import os
from pathlib import Path, PurePath
from typing import Any, Mapping
from uuid import uuid4

from master_producer_models import ProductionArtifact, SpecialistRole
from workspace_resolver import WorkspaceResolver


SIDECAR_SCHEMA_VERSION = "1.0"
SIDECAR_SUFFIX = ".meta.json"
_HASH_CHUNK_SIZE = 1024 * 1024


class ArtifactStoreError(RuntimeError):
    """Error base de almacenamiento de artefactos F3."""


class ArtifactCollisionError(ArtifactStoreError):
    """La ruta destino ya contiene contenido incompatible."""


class ArtifactIdentityConflictError(ArtifactStoreError):
    """Un ``artifact_id`` existente apunta a contenido diferente."""


class ArtifactIntegrityError(ArtifactStoreError):
    """La integridad del archivo o del sidecar no puede validarse."""


class ArtifactNotFoundError(ArtifactStoreError):
    """No existe el artefacto solicitado."""


class CollisionPolicy(str, Enum):
    """Política explícita ante una ruta física ya ocupada."""

    REUSE_IDENTICAL = "reuse_identical"
    REJECT = "reject"
    REPLACE = "replace"


@dataclass(frozen=True, slots=True)
class ArtifactWriteResult:
    """Resultado operacional de una persistencia F3."""

    artifact: ProductionArtifact
    created_at: str
    sidecar_path: Path
    deduplicated: bool
    event_created: bool


@dataclass(frozen=True, slots=True)
class _ExistingEvent:
    artifact_path: Path
    sidecar_path: Path
    content_hash: str
    created_at: str
    artifact_type: str
    media_type: str
    mime_type: str
    producer_role: str
    requested_relative_path: str
    metadata: dict[str, Any]


@dataclass(frozen=True, slots=True)
class _PhysicalSelection:
    path: Path
    deduplicated: bool
    created: bool
    rollback_path: Path | None = None


class ArtifactStore(ABC):
    """
    Clase base abstracta para los stores especializados de F3.

    Los stores de texto, imagen, audio, video y metadata convertirán su
    contenido a bytes y delegarán aquí la persistencia física común.
    """

    def __init__(self, workspace_resolver: WorkspaceResolver) -> None:
        if not isinstance(workspace_resolver, WorkspaceResolver):
            raise TypeError("workspace_resolver debe ser WorkspaceResolver.")
        self._workspace_resolver = workspace_resolver

    @property
    def workspace_resolver(self) -> WorkspaceResolver:
        return self._workspace_resolver

    @property
    @abstractmethod
    def media_type(self) -> str:
        """Identificador estable del medio gestionado por el store."""

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
        """Persiste bytes y registra un evento lógico en el sidecar."""

        payload = self._normalize_bytes(content)
        logical_type = self._require_text(artifact_type, "artifact_type")
        resolved_mime = self._require_text(mime_type, "mime_type")
        policy = CollisionPolicy(collision_policy)
        event_time = self._normalize_created_at(created_at)
        event_metadata = dict(metadata or {})
        media_type = self._require_text(self.media_type, "media_type")
        normalized_producer_role = SpecialistRole(producer_role)

        destination = self._workspace_resolver.confine_path(
            workspace_root,
            relative_path,
        )
        workspace = Path(workspace_root).expanduser().resolve(strict=False)
        requested_relative = self._relative_to_workspace(destination, workspace)
        content_hash = self.calculate_content_hash(payload)

        if artifact_id is not None:
            normalized_artifact_id = self._require_text(artifact_id, "artifact_id")
            existing_event = self._find_event_by_artifact_id(
                workspace,
                normalized_artifact_id,
            )
            if existing_event is not None:
                if (
                    existing_event.content_hash != content_hash
                    or existing_event.artifact_type != logical_type
                    or existing_event.media_type != media_type
                    or existing_event.mime_type != resolved_mime
                    or existing_event.producer_role != str(normalized_producer_role)
                ):
                    raise ArtifactIdentityConflictError(
                        "artifact_id ya existe con una identidad lógica o de contenido diferente."
                    )
                return self._result_for_existing_event(
                    existing_event=existing_event,
                    artifact_id=normalized_artifact_id,
                )
        else:
            normalized_artifact_id = None

        selection = self._select_physical_path(
            workspace=workspace,
            destination=destination,
            content_hash=content_hash,
            payload=payload,
            media_type=media_type,
            mime_type=resolved_mime,
            collision_policy=policy,
        )
        physical_path = selection.path

        sidecar_path = self.sidecar_path_for(physical_path)
        physical_relative = self._relative_to_workspace(physical_path, workspace)

        artifact_metadata = dict(event_metadata)
        artifact_metadata.update(
            {
                "created_at": event_time,
                "media_type": media_type,
                "relative_path": physical_relative,
                "requested_relative_path": requested_relative,
                "sidecar_path": str(sidecar_path),
            }
        )

        artifact_kwargs: dict[str, Any] = {
            "name": physical_path.name,
            "artifact_type": logical_type,
            "path": str(physical_path),
            "producer_role": normalized_producer_role,
            "content_hash": content_hash,
            "mime_type": resolved_mime,
            "size_bytes": len(payload),
            "metadata": artifact_metadata,
        }
        if normalized_artifact_id is not None:
            artifact_kwargs["artifact_id"] = normalized_artifact_id
        artifact = ProductionArtifact(**artifact_kwargs)

        try:
            event_created, effective_created_at = self._register_sidecar_event(
                sidecar_path=sidecar_path,
                artifact_path=physical_path,
                workspace=workspace,
                content_hash=content_hash,
                media_type=media_type,
                mime_type=resolved_mime,
                size_bytes=len(payload),
                artifact=artifact,
                created_at=event_time,
                requested_relative=requested_relative,
                metadata=event_metadata,
            )
        except Exception:
            self._rollback_physical_selection(selection)
            raise
        else:
            if selection.rollback_path is not None:
                self._safe_unlink(selection.rollback_path)

        if effective_created_at != event_time:
            artifact.metadata["created_at"] = effective_created_at

        return ArtifactWriteResult(
            artifact=artifact,
            created_at=effective_created_at,
            sidecar_path=sidecar_path,
            deduplicated=selection.deduplicated,
            event_created=event_created,
        )

    def resolve_path(
        self,
        workspace_root: str | Path,
        relative_path: str | Path,
    ) -> Path:
        """Resuelve un destino sin escribirlo."""

        return self._workspace_resolver.confine_path(workspace_root, relative_path)

    def exists(self, workspace_root: str | Path, relative_path: str | Path) -> bool:
        """Indica si existe un archivo regular en la ruta confinada."""

        return self.resolve_path(workspace_root, relative_path).is_file()

    def read_bytes(self, workspace_root: str | Path, relative_path: str | Path) -> bytes:
        """Lee bytes únicamente desde una ruta confinada."""

        path = self.resolve_path(workspace_root, relative_path)
        if not path.is_file():
            raise ArtifactNotFoundError(f"No existe el artefacto: {path}")
        return path.read_bytes()

    def load_sidecar(
        self,
        workspace_root: str | Path,
        relative_path: str | Path,
    ) -> dict[str, Any]:
        """Carga el sidecar de un artefacto ubicado en la ruta indicada."""

        path = self.resolve_path(workspace_root, relative_path)
        return self._load_sidecar_path(self.sidecar_path_for(path), required=True)

    def verify_hash(
        self,
        workspace_root: str | Path,
        relative_path: str | Path,
        expected_hash: str,
    ) -> bool:
        """Verifica la identidad SHA-256 de un archivo confinado."""

        path = self.resolve_path(workspace_root, relative_path)
        if not path.is_file():
            raise ArtifactNotFoundError(f"No existe el artefacto: {path}")
        return self.calculate_file_hash(path) == self._require_text(
            expected_hash,
            "expected_hash",
        ).lower()

    @staticmethod
    def sidecar_path_for(artifact_path: str | Path) -> Path:
        path = Path(artifact_path)
        return Path(f"{path}{SIDECAR_SUFFIX}")

    @staticmethod
    def calculate_content_hash(content: bytes | bytearray | memoryview) -> str:
        payload = ArtifactStore._normalize_bytes(content)
        return hashlib.sha256(payload).hexdigest()

    @staticmethod
    def calculate_file_hash(file_path: str | Path) -> str:
        path = Path(file_path)
        hasher = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(_HASH_CHUNK_SIZE), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    def _select_physical_path(
        self,
        *,
        workspace: Path,
        destination: Path,
        content_hash: str,
        payload: bytes,
        media_type: str,
        mime_type: str,
        collision_policy: CollisionPolicy,
    ) -> _PhysicalSelection:
        if destination.exists():
            if not destination.is_file():
                raise ArtifactCollisionError(
                    "La ruta destino existe pero no es un archivo regular."
                )
            existing_hash = self.calculate_file_hash(destination)
            if collision_policy is CollisionPolicy.REJECT:
                raise ArtifactCollisionError("La ruta destino ya existe.")
            if existing_hash == content_hash:
                return _PhysicalSelection(destination, True, False)
            if collision_policy is not CollisionPolicy.REPLACE:
                raise ArtifactCollisionError(
                    "La ruta destino contiene bytes diferentes; reemplazo no autorizado."
                )
            rollback_path = destination.with_name(
                f".{destination.name}.{uuid4().hex}.bak"
            )
            os.replace(destination, rollback_path)
            try:
                self._atomic_write_bytes(destination, payload)
            except Exception:
                self._safe_unlink(destination)
                os.replace(rollback_path, destination)
                raise
            return _PhysicalSelection(
                destination,
                False,
                False,
                rollback_path=rollback_path,
            )

        if collision_policy is CollisionPolicy.REUSE_IDENTICAL:
            duplicate = self._find_duplicate_content(
                workspace=workspace,
                content_hash=content_hash,
                media_type=media_type,
                mime_type=mime_type,
            )
            if duplicate is not None:
                return _PhysicalSelection(duplicate, True, False)

        self._atomic_write_bytes(destination, payload)
        return _PhysicalSelection(destination, False, True)

    def _find_duplicate_content(
        self,
        *,
        workspace: Path,
        content_hash: str,
        media_type: str,
        mime_type: str,
    ) -> Path | None:
        if not workspace.exists():
            return None
        for sidecar in sorted(workspace.rglob(f"*{SIDECAR_SUFFIX}")):
            data = self._load_sidecar_path(sidecar, required=False)
            if not data:
                continue
            if data.get("content_hash") != content_hash:
                continue
            if data.get("media_type") != media_type or data.get("mime_type") != mime_type:
                continue
            artifact_path = self._artifact_path_from_sidecar(sidecar)
            if not artifact_path.is_file():
                continue
            if self.calculate_file_hash(artifact_path) == content_hash:
                return artifact_path
        return None

    def _find_event_by_artifact_id(
        self,
        workspace: Path,
        artifact_id: str,
    ) -> _ExistingEvent | None:
        if not workspace.exists():
            return None
        for sidecar in sorted(workspace.rglob(f"*{SIDECAR_SUFFIX}")):
            data = self._load_sidecar_path(sidecar, required=False)
            if not data:
                continue
            for event in data.get("events", []):
                if isinstance(event, dict) and event.get("artifact_id") == artifact_id:
                    artifact_path = self._artifact_path_from_sidecar(sidecar)
                    content_hash = str(data.get("content_hash", ""))
                    created_at = str(event.get("created_at", ""))
                    artifact_type = str(event.get("artifact_type", ""))
                    media_type = str(data.get("media_type", ""))
                    mime_type = str(data.get("mime_type", ""))
                    producer_role = str(event.get("producer_role", ""))
                    requested_relative_path = str(
                        event.get("requested_relative_path", "")
                    )
                    event_metadata = event.get("metadata", {})
                    if (
                        not artifact_path.is_file()
                        or not content_hash
                        or not created_at
                        or not artifact_type
                        or not media_type
                        or not mime_type
                        or not producer_role
                        or not requested_relative_path
                        or not isinstance(event_metadata, dict)
                    ):
                        raise ArtifactIntegrityError(
                            "El sidecar contiene un evento incompleto o huérfano."
                        )
                    if self.calculate_file_hash(artifact_path) != content_hash:
                        raise ArtifactIntegrityError(
                            "El archivo físico no coincide con el content_hash del sidecar."
                        )
                    return _ExistingEvent(
                        artifact_path=artifact_path,
                        sidecar_path=sidecar,
                        content_hash=content_hash,
                        created_at=created_at,
                        artifact_type=artifact_type,
                        media_type=media_type,
                        mime_type=mime_type,
                        producer_role=producer_role,
                        requested_relative_path=requested_relative_path,
                        metadata=dict(event_metadata),
                    )
        return None

    def _result_for_existing_event(
        self,
        *,
        existing_event: _ExistingEvent,
        artifact_id: str,
    ) -> ArtifactWriteResult:
        artifact_metadata = dict(existing_event.metadata)
        artifact_metadata.update(
            {
                "created_at": existing_event.created_at,
                "media_type": existing_event.media_type,
                "requested_relative_path": existing_event.requested_relative_path,
                "sidecar_path": str(existing_event.sidecar_path),
            }
        )
        artifact = ProductionArtifact(
            name=existing_event.artifact_path.name,
            artifact_type=existing_event.artifact_type,
            path=str(existing_event.artifact_path),
            artifact_id=artifact_id,
            producer_role=existing_event.producer_role,
            content_hash=existing_event.content_hash,
            mime_type=existing_event.mime_type,
            size_bytes=existing_event.artifact_path.stat().st_size,
            metadata=artifact_metadata,
        )
        return ArtifactWriteResult(
            artifact=artifact,
            created_at=existing_event.created_at,
            sidecar_path=existing_event.sidecar_path,
            deduplicated=True,
            event_created=False,
        )

    def _register_sidecar_event(
        self,
        *,
        sidecar_path: Path,
        artifact_path: Path,
        workspace: Path,
        content_hash: str,
        media_type: str,
        mime_type: str,
        size_bytes: int,
        artifact: ProductionArtifact,
        created_at: str,
        requested_relative: str,
        metadata: Mapping[str, Any],
    ) -> tuple[bool, str]:
        existing = self._load_sidecar_path(sidecar_path, required=False)
        if existing and existing.get("content_hash") == content_hash:
            sidecar = existing
        else:
            sidecar = {
                "schema_version": SIDECAR_SCHEMA_VERSION,
                "content_hash": content_hash,
                "media_type": media_type,
                "relative_path": self._relative_to_workspace(artifact_path, workspace),
                "filename": artifact_path.name,
                "mime_type": mime_type,
                "size_bytes": size_bytes,
                "events": [],
            }

        events = sidecar.setdefault("events", [])
        if not isinstance(events, list):
            raise ArtifactIntegrityError("El campo 'events' del sidecar no es una lista.")
        for event in events:
            if isinstance(event, dict) and event.get("artifact_id") == artifact.artifact_id:
                existing_created_at = str(event.get("created_at", ""))
                if not existing_created_at:
                    raise ArtifactIntegrityError(
                        "El evento existente no contiene created_at."
                    )
                return False, existing_created_at

        events.append(
            {
                "artifact_id": artifact.artifact_id,
                "artifact_type": artifact.artifact_type,
                "created_at": created_at,
                "producer_role": str(artifact.producer_role),
                "requested_relative_path": requested_relative,
                "metadata": self._json_safe(metadata),
            }
        )
        self._atomic_write_json(sidecar_path, sidecar)
        return True, created_at


    @staticmethod
    def _rollback_physical_selection(selection: _PhysicalSelection) -> None:
        if selection.rollback_path is not None:
            ArtifactStore._safe_unlink(selection.path)
            os.replace(selection.rollback_path, selection.path)
            return
        if selection.created:
            ArtifactStore._safe_unlink(selection.path)

    @staticmethod
    def _normalize_bytes(content: bytes | bytearray | memoryview) -> bytes:
        if isinstance(content, bytes):
            return content
        if isinstance(content, (bytearray, memoryview)):
            return bytes(content)
        raise TypeError("content debe ser bytes, bytearray o memoryview.")

    @staticmethod
    def _require_text(value: Any, label: str) -> str:
        text = "" if value is None else str(value).strip()
        if not text:
            raise ValueError(f"{label} no puede estar vacío.")
        return text

    @staticmethod
    def _normalize_created_at(value: str | None) -> str:
        if value is None:
            return datetime.now(timezone.utc).isoformat()
        return ArtifactStore._require_text(value, "created_at")

    @staticmethod
    def _relative_to_workspace(path: Path, workspace: Path) -> str:
        try:
            return path.resolve(strict=False).relative_to(
                workspace.resolve(strict=False)
            ).as_posix()
        except ValueError as exc:
            raise ArtifactIntegrityError(
                "El artefacto resuelto quedó fuera del workspace esperado."
            ) from exc

    @staticmethod
    def _artifact_path_from_sidecar(sidecar_path: Path) -> Path:
        text = str(sidecar_path)
        if not text.endswith(SIDECAR_SUFFIX):
            raise ArtifactIntegrityError("Ruta sidecar inválida.")
        return Path(text[: -len(SIDECAR_SUFFIX)])

    @staticmethod
    def _load_sidecar_path(sidecar_path: Path, *, required: bool) -> dict[str, Any]:
        if not sidecar_path.is_file():
            if required:
                raise ArtifactNotFoundError(f"No existe el sidecar: {sidecar_path}")
            return {}
        try:
            data = json.loads(sidecar_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            if required:
                raise ArtifactIntegrityError(
                    f"No se pudo leer el sidecar: {sidecar_path}"
                ) from exc
            return {}
        if not isinstance(data, dict):
            if required:
                raise ArtifactIntegrityError("El sidecar no contiene un objeto JSON.")
            return {}
        return data

    @staticmethod
    def _atomic_write_bytes(path: Path, content: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
        try:
            with temp_path.open("xb") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_path, path)
        except Exception:
            ArtifactStore._safe_unlink(temp_path)
            raise

    @staticmethod
    def _atomic_write_json(path: Path, data: Mapping[str, Any]) -> None:
        encoded = json.dumps(
            ArtifactStore._json_safe(data),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ).encode("utf-8")
        ArtifactStore._atomic_write_bytes(path, encoded)

    @staticmethod
    def _json_safe(value: Any) -> Any:
        if isinstance(value, Enum):
            return value.value
        if isinstance(value, PurePath):
            return value.as_posix()
        if is_dataclass(value):
            return ArtifactStore._json_safe(asdict(value))
        if isinstance(value, Mapping):
            return {
                str(key): ArtifactStore._json_safe(item)
                for key, item in value.items()
            }
        if isinstance(value, (list, tuple, set, frozenset)):
            return [ArtifactStore._json_safe(item) for item in value]
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        return str(value)

    @staticmethod
    def _safe_unlink(path: Path) -> None:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass


def get_artifact_store_info() -> dict[str, object]:
    """Devuelve información pública del componente F3.2."""

    return {
        "component": "artifact_store",
        "version": "0.8",
        "build": "066-F3.2",
        "hash_algorithm": "sha256",
        "sidecar_suffix": SIDECAR_SUFFIX,
        "collision_policies": [policy.value for policy in CollisionPolicy],
    }
