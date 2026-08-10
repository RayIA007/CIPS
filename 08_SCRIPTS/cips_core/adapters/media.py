"""Adaptadores delgados del Media Director para el Core Orchestrator de CIPS.

F5.2 publica las capacidades multimedia ya modeladas por ``media_director`` en
la capa estándar de adaptadores del Core. Este módulo no selecciona providers,
no conoce SDKs externos, no implementa persistencia F3 y no ejecuta post-proceso.
Las fronteras de provider y artifact se inyectan como callables; el adapter solo
traduce contratos y publica el resultado normalizado al Core.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any, Mapping

from media_director import (
    ImageStrategy,
    MediaDirector,
    MediaRequest,
    MediaResult,
    MediaStrategy,
    VideoStrategy,
    VoiceStrategy,
)

from .base import BaseAgentAdapter
from .contracts import AdapterRequest, AdapterResult
from .exceptions import AdapterContractError, AdapterValidationError


ProviderExecutor = Callable[[Any], Any]
MediaArtifactHandler = Callable[[MediaResult, AdapterRequest], tuple[Mapping[str, Any], ...]]
ARTIFACT_TARGET_KEY = "artifact_target"


class MediaDirectorAdapter(BaseAgentAdapter):
    """Base delgada que traduce contratos Core <-> MediaDirector."""

    strategy_factory: type[MediaStrategy] | None = None

    def __init__(
        self,
        *,
        provider_executor: ProviderExecutor,
        director: MediaDirector | None = None,
        artifact_handler: MediaArtifactHandler | None = None,
    ) -> None:
        super().__init__()
        if not callable(provider_executor):
            raise AdapterContractError("provider_executor debe ser invocable.")
        if artifact_handler is not None and not callable(artifact_handler):
            raise AdapterContractError("artifact_handler debe ser invocable o None.")
        self._provider_executor = provider_executor
        self._artifact_handler = artifact_handler
        self._director = director or self._build_director()
        if self._director.strategy.provider_capability != self.capability:
            raise AdapterContractError(
                "La capability del adaptador no coincide con la estrategia multimedia."
            )

    @property
    def director(self) -> MediaDirector:
        return self._director

    def _build_director(self) -> MediaDirector:
        if self.strategy_factory is None:
            raise AdapterContractError(
                f"{type(self).__name__} debe declarar strategy_factory."
            )
        return MediaDirector(self.strategy_factory())

    def validate_request(self, request: AdapterRequest) -> None:
        payload = self._payload(request)
        prompt = payload.get("prompt")
        if prompt is None or not str(prompt).strip():
            raise AdapterValidationError(
                f"{self.adapter_name} requiere input.prompt."
            )
        artifact_target = payload.get(ARTIFACT_TARGET_KEY)
        if artifact_target is not None:
            self._validate_artifact_target(artifact_target)

    def run(self, request: AdapterRequest) -> MediaResult:
        media_request = self._to_media_request(request)
        return self.director.execute(
            media_request,
            provider_executor=self._provider_executor,
        )

    def normalize_result(
        self,
        *,
        raw_output: Any,
        request: AdapterRequest,
        started_at: float,
    ) -> AdapterResult:
        if not isinstance(raw_output, MediaResult):
            raise AdapterContractError(
                "MediaDirector devolvió un resultado incompatible."
            )
        output = raw_output.to_dict()
        artifacts = self._collect_artifacts(raw_output, request)
        return AdapterResult.success(
            adapter_name=self.adapter_name,
            capability=self.capability,
            output=output,
            metrics={
                "media_request_id": raw_output.request_id,
                "strategy_name": raw_output.strategy_name,
                "media_type": raw_output.media_type.value,
                "output_format": raw_output.output_format,
                "post_process_step_count": len(raw_output.post_process_chain),
            },
            artifacts=artifacts,
            started_at=started_at,
        )

    def descriptor_metadata(self) -> dict[str, Any]:
        metadata = super().descriptor_metadata()
        strategy = self.director.strategy
        metadata.update(
            {
                "component": "media_director.MediaDirector",
                "strategy": strategy.strategy_name,
                "media_type": strategy.media_type.value,
                "output_format": strategy.output_format,
                "post_process_mode": "declarative",
                "artifact_persistence": (
                    "runtime_opt_in" if self._artifact_handler is not None else "disabled"
                ),
            }
        )
        return metadata

    @staticmethod
    def _payload(request: AdapterRequest) -> dict[str, Any]:
        merged = dict(request.shared_data)
        merged.update(request.input_data)
        return merged

    def _to_media_request(self, request: AdapterRequest) -> MediaRequest:
        payload = self._payload(request)
        prompt = str(payload.pop("prompt")).strip()
        preferred_provider = payload.pop("preferred_provider", None)
        payload.pop(ARTIFACT_TARGET_KEY, None)

        supplied_metadata = payload.pop("metadata", {})
        if supplied_metadata is None:
            supplied_metadata = {}
        if not isinstance(supplied_metadata, Mapping):
            raise AdapterValidationError("input.metadata debe ser Mapping.")

        metadata = dict(request.context.metadata)
        metadata.update(dict(supplied_metadata))
        metadata.setdefault("project_id", request.context.project_id)
        metadata.setdefault("workflow_id", request.context.workflow_id)
        metadata.setdefault("run_id", request.context.run_id)
        metadata.setdefault("task_id", request.context.task_id)
        metadata.setdefault("correlation_id", request.context.correlation_id)
        if request.task_outputs:
            metadata.setdefault("task_outputs", dict(request.task_outputs))

        return MediaRequest(
            prompt=prompt,
            input_data=payload,
            preferred_provider=preferred_provider,
            metadata=metadata,
        )

    def _collect_artifacts(
        self,
        result: MediaResult,
        request: AdapterRequest,
    ) -> tuple[Mapping[str, Any], ...]:
        if self._artifact_handler is None:
            return ()
        artifacts = self._artifact_handler(result, request)
        if artifacts is None:
            return ()
        try:
            normalized = tuple(artifacts)
        except TypeError as exc:
            raise AdapterContractError(
                "artifact_handler debe devolver una colección de Mapping."
            ) from exc
        if not all(isinstance(item, Mapping) for item in normalized):
            raise AdapterContractError(
                "artifact_handler solo puede devolver elementos Mapping."
            )
        return tuple(dict(item) for item in normalized)

    @staticmethod
    def _validate_artifact_target(value: Any) -> None:
        if not isinstance(value, Mapping):
            raise AdapterValidationError("artifact_target debe ser Mapping.")
        for field_name in ("platform", "relative_path"):
            field_value = value.get(field_name)
            if field_value is None or not str(field_value).strip():
                raise AdapterValidationError(
                    f"artifact_target.{field_name} es obligatorio."
                )
        metadata = value.get("metadata")
        if metadata is not None and not isinstance(metadata, Mapping):
            raise AdapterValidationError(
                "artifact_target.metadata debe ser Mapping o None."
            )



class VoiceMediaAdapter(MediaDirectorAdapter):
    adapter_name = "VoiceMediaAdapter"
    capability = "voice_synthesis"
    version = "1.0.0"
    strategy_factory = VoiceStrategy


class ImageMediaAdapter(MediaDirectorAdapter):
    adapter_name = "ImageMediaAdapter"
    capability = "image_generation"
    version = "1.0.0"
    strategy_factory = ImageStrategy


class VideoMediaAdapter(MediaDirectorAdapter):
    adapter_name = "VideoMediaAdapter"
    capability = "video_rendering"
    version = "1.0.0"
    strategy_factory = VideoStrategy


__all__ = [
    "ARTIFACT_TARGET_KEY",
    "ProviderExecutor",
    "MediaArtifactHandler",
    "MediaDirectorAdapter",
    "VoiceMediaAdapter",
    "ImageMediaAdapter",
    "VideoMediaAdapter",
]
