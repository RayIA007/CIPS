from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from artifact_store import ArtifactWriteResult, CollisionPolicy
from audio_store import AudioStore
from image_store import ImageStore
from master_producer_models import SpecialistRole
from video_store import VideoStore
from workspace_resolver import WorkspaceResolver

from .models import MediaResult, MediaType


class MediaArtifactPersister:
    """
    Puente F5.4 entre ``MediaResult`` y los stores especializados de F3.

    Responsabilidades:
    - seleccionar el store F3 correspondiente al tipo de medio;
    - validar que ``MediaResult.output`` sea contenido binario persistible;
    - transferir correlación y metadata F5 al sidecar mediante F3;
    - delegar completamente rutas, hashing, deduplicación, colisiones y sidecars.

    No genera medios, no resuelve providers, no aplica retry y no ejecuta
    post-proceso ni pipelines.
    """

    def __init__(self, workspace_resolver: WorkspaceResolver) -> None:
        if not isinstance(workspace_resolver, WorkspaceResolver):
            raise TypeError("workspace_resolver debe ser WorkspaceResolver.")
        self._workspace_resolver = workspace_resolver
        self._image_store = ImageStore(workspace_resolver)
        self._audio_store = AudioStore(workspace_resolver)
        self._video_store = VideoStore(workspace_resolver)

    @property
    def workspace_resolver(self) -> WorkspaceResolver:
        return self._workspace_resolver

    def persist(
        self,
        result: MediaResult,
        *,
        workspace_root: str | Path,
        relative_path: str | Path,
        mime_type: str | None = None,
        metadata: Mapping[str, Any] | None = None,
        artifact_id: str | None = None,
        producer_role: SpecialistRole | str = SpecialistRole.MASTER_PRODUCER,
        created_at: str | None = None,
        collision_policy: CollisionPolicy | str = CollisionPolicy.REUSE_IDENTICAL,
    ) -> ArtifactWriteResult:
        """Persiste un ``MediaResult`` binario usando exclusivamente F3."""

        if not isinstance(result, MediaResult):
            raise TypeError("result debe ser MediaResult.")

        content = self._binary_output(result.output)
        artifact_metadata = self._build_metadata(result, metadata)

        common = {
            "workspace_root": workspace_root,
            "relative_path": relative_path,
            "content": content,
            "metadata": artifact_metadata,
            "artifact_id": artifact_id,
            "producer_role": producer_role,
            "created_at": created_at,
            "collision_policy": collision_policy,
        }

        if result.media_type is MediaType.VOICE:
            return self._audio_store.persist_audio(
                **common,
                artifact_type="audio",
                mime_type=mime_type,
            )
        if result.media_type is MediaType.IMAGE:
            return self._image_store.persist_image(
                **common,
                artifact_type="image",
                mime_type=mime_type,
            )
        if result.media_type is MediaType.VIDEO:
            return self._video_store.persist_video(
                **common,
                artifact_type="video",
                mime_type=mime_type,
            )

        raise ValueError(f"MediaType no soportado para persistencia: {result.media_type!r}")

    @staticmethod
    def _binary_output(output: Any) -> bytes:
        if isinstance(output, bytes):
            return output
        if isinstance(output, (bytearray, memoryview)):
            return bytes(output)
        raise TypeError(
            "MediaResult.output debe ser bytes, bytearray o memoryview antes de persistir."
        )

    @staticmethod
    def _build_metadata(
        result: MediaResult,
        metadata: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        if metadata is not None and not isinstance(metadata, Mapping):
            raise TypeError("metadata debe ser Mapping o None.")

        merged = dict(result.metadata)
        merged.update(dict(metadata or {}))
        merged.update(
            {
                "media_request_id": result.request_id,
                "media_strategy": result.strategy_name,
                "media_capability": result.capability,
                "media_output_format": result.output_format,
                "media_result_type": result.media_type.value,
                "post_process_chain": [
                    step.to_dict() for step in result.post_process_chain
                ],
            }
        )
        return merged


__all__ = ["MediaArtifactPersister"]
