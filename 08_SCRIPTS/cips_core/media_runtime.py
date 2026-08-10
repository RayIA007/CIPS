"""Composición runtime del flujo multimedia F5 para el Core de CIPS.

F5.5 conecta, sin duplicar responsabilidades:

Core adapter -> MediaDirector -> CapabilityProviderExecutor -> provider
             -> MediaResult -> MediaArtifactPersister -> ArtifactStore F3

Este módulo configura fronteras ya existentes. No implementa selección de
provider, retry, hashing, sidecars, pipelines ni SDKs externos.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from media_director import (
    CapabilityProviderExecutor,
    MediaArtifactPersister,
    MediaResult,
    MediaWorkPackage,
)
from workspace_resolver import WorkspaceResolver

from .adapters.contracts import AdapterRequest
from .adapters.media import (
    ARTIFACT_TARGET_KEY,
    ImageMediaAdapter,
    MediaDirectorAdapter,
    VideoMediaAdapter,
    VoiceMediaAdapter,
)
from .integration import AdapterAgentBridge


ProviderInvoker = Callable[[Any, MediaWorkPackage], Any]


@dataclass(frozen=True, slots=True)
class MediaArtifactTarget:
    """Destino lógico de persistencia solicitado por una ejecución Core."""

    platform: str
    relative_path: str
    execution_id: str | None = None
    mime_type: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
    artifact_id: str | None = None

    def __post_init__(self) -> None:
        platform = str(self.platform).strip()
        relative_path = str(self.relative_path).strip()
        execution_id = self._optional_text(self.execution_id)
        mime_type = self._optional_text(self.mime_type)
        artifact_id = self._optional_text(self.artifact_id)
        if not platform:
            raise ValueError("MediaArtifactTarget.platform es obligatorio.")
        if not relative_path:
            raise ValueError("MediaArtifactTarget.relative_path es obligatorio.")
        if not isinstance(self.metadata, Mapping):
            raise TypeError("MediaArtifactTarget.metadata debe ser Mapping.")
        object.__setattr__(self, "platform", platform)
        object.__setattr__(self, "relative_path", relative_path)
        object.__setattr__(self, "execution_id", execution_id)
        object.__setattr__(self, "mime_type", mime_type)
        object.__setattr__(self, "artifact_id", artifact_id)
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    @classmethod
    def from_value(cls, value: Any) -> "MediaArtifactTarget":
        if not isinstance(value, Mapping):
            raise TypeError("artifact_target debe ser Mapping.")
        return cls(
            platform=value.get("platform", ""),
            relative_path=value.get("relative_path", ""),
            execution_id=value.get("execution_id"),
            mime_type=value.get("mime_type"),
            metadata=value.get("metadata") or {},
            artifact_id=value.get("artifact_id"),
        )

    @staticmethod
    def _optional_text(value: Any) -> str | None:
        if value is None:
            return None
        normalized = str(value).strip()
        return normalized or None


class MediaRuntime:
    """Compone los adapters multimedia con F4 y F3 para ejecución en Core."""

    def __init__(
        self,
        capability_resolver: Any,
        *,
        provider_invoker: ProviderInvoker,
        workspace_resolver: WorkspaceResolver,
    ) -> None:
        self._provider_executor = CapabilityProviderExecutor(
            capability_resolver,
            provider_invoker=provider_invoker,
        )
        self._artifact_persister = MediaArtifactPersister(workspace_resolver)

    @property
    def provider_executor(self) -> CapabilityProviderExecutor:
        return self._provider_executor

    @property
    def artifact_persister(self) -> MediaArtifactPersister:
        return self._artifact_persister

    def create_adapters(self) -> tuple[MediaDirectorAdapter, ...]:
        """Crea los tres adapters F5 configurados con las fronteras runtime."""

        common = {
            "provider_executor": self._provider_executor,
            "artifact_handler": self._persist_artifact,
        }
        return (
            VoiceMediaAdapter(**common),
            ImageMediaAdapter(**common),
            VideoMediaAdapter(**common),
        )

    def register(
        self,
        bridge: AdapterAgentBridge,
        *,
        replace: bool = False,
    ) -> list[Any]:
        """Publica los adapters configurados usando el bridge estándar del Core."""

        if not isinstance(bridge, AdapterAgentBridge):
            raise TypeError("bridge debe ser AdapterAgentBridge.")
        return bridge.register_many(self.create_adapters(), replace=replace)

    def _persist_artifact(
        self,
        result: MediaResult,
        request: AdapterRequest,
    ) -> tuple[Mapping[str, Any], ...]:
        raw_target = self._artifact_target_value(request)
        if raw_target is None:
            return ()

        target = MediaArtifactTarget.from_value(raw_target)
        execution_id = target.execution_id or request.context.run_id
        workspace = self._artifact_persister.workspace_resolver.resolve_execution_workspace(
            target.platform,
            execution_id,
            create=True,
        )
        written = self._artifact_persister.persist(
            result,
            workspace_root=workspace,
            relative_path=target.relative_path,
            mime_type=target.mime_type,
            metadata=target.metadata,
            artifact_id=target.artifact_id,
        )
        artifact = written.artifact
        return (
            {
                "artifact_type": artifact.artifact_type,
                "artifact_id": artifact.artifact_id,
                "path": artifact.path,
                "mime_type": artifact.mime_type,
                "content_hash": artifact.content_hash,
                "size_bytes": artifact.size_bytes,
                "created_at": written.created_at,
                "sidecar_path": str(written.sidecar_path),
                "deduplicated": written.deduplicated,
                "event_created": written.event_created,
            },
        )

    @staticmethod
    def _artifact_target_value(request: AdapterRequest) -> Any:
        if ARTIFACT_TARGET_KEY in request.input_data:
            return request.input_data[ARTIFACT_TARGET_KEY]
        return request.shared_data.get(ARTIFACT_TARGET_KEY)


__all__ = [
    "ProviderInvoker",
    "MediaArtifactTarget",
    "MediaRuntime",
]
