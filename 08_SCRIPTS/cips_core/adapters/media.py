"""Adaptadores delgados del Media Director para el Core Orchestrator de CIPS.

F5.2 publica las capacidades multimedia ya modeladas por ``media_director`` en
la capa estándar de adaptadores del Core. Este módulo no selecciona providers,
no conoce SDKs externos, no persiste artifacts y no ejecuta post-proceso.
La frontera de ejecución del provider se inyecta como callable y será conectada
con F4 en F5.3.
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


class MediaDirectorAdapter(BaseAgentAdapter):
    """Base delgada que traduce contratos Core <-> MediaDirector."""

    strategy_factory: type[MediaStrategy] | None = None

    def __init__(
        self,
        *,
        provider_executor: ProviderExecutor,
        director: MediaDirector | None = None,
    ) -> None:
        super().__init__()
        if not callable(provider_executor):
            raise AdapterContractError("provider_executor debe ser invocable.")
        self._provider_executor = provider_executor
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
    "ProviderExecutor",
    "MediaDirectorAdapter",
    "VoiceMediaAdapter",
    "ImageMediaAdapter",
    "VideoMediaAdapter",
]
