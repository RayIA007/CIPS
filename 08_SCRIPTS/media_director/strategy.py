from __future__ import annotations

from abc import ABC
from types import MappingProxyType
from typing import Any, Mapping

from .exceptions import MediaRequestValidationError, MediaResultValidationError
from .models import MediaRequest, MediaType, MediaWorkPackage, PostProcessStep


class MediaStrategy(ABC):
    """Variación por medio sin selección de provider ni ejecución de pipeline."""

    strategy_name = "media"
    media_type = MediaType.IMAGE
    provider_capability = ""
    output_format = "binary"
    default_post_process_chain: tuple[PostProcessStep, ...] = ()

    def __init__(
        self,
        *,
        input_schema: Mapping[str, type | tuple[type, ...]] | None = None,
        post_process_chain: tuple[PostProcessStep, ...] | None = None,
    ) -> None:
        schema = dict(input_schema or {"prompt": str})
        if "prompt" not in schema:
            schema = {"prompt": str, **schema}
        self._input_schema = MappingProxyType(schema)
        self._post_process_chain = tuple(
            self.default_post_process_chain
            if post_process_chain is None
            else post_process_chain
        )
        self._validate_contract()

    @property
    def input_schema(self) -> Mapping[str, type | tuple[type, ...]]:
        return self._input_schema

    @property
    def post_process_chain(self) -> tuple[PostProcessStep, ...]:
        return self._post_process_chain

    def _validate_contract(self) -> None:
        if not str(self.strategy_name).strip():
            raise TypeError("MediaStrategy.strategy_name es obligatorio.")
        if not str(self.provider_capability).strip():
            raise TypeError("MediaStrategy.provider_capability es obligatorio.")
        if not str(self.output_format).strip():
            raise TypeError("MediaStrategy.output_format es obligatorio.")
        MediaType(self.media_type)
        for field_name, expected_type in self._input_schema.items():
            if not str(field_name).strip():
                raise TypeError("input_schema contiene un nombre de campo vacío.")
            if not isinstance(expected_type, type) and not (
                isinstance(expected_type, tuple)
                and expected_type
                and all(isinstance(item, type) for item in expected_type)
            ):
                raise TypeError("input_schema debe mapear nombres a tipos válidos.")
        if not all(isinstance(step, PostProcessStep) for step in self._post_process_chain):
            raise TypeError("post_process_chain solo puede contener PostProcessStep.")

    def validate_request(self, request: MediaRequest) -> None:
        if not isinstance(request, MediaRequest):
            raise TypeError("request debe ser MediaRequest.")
        for field_name, expected_type in self._input_schema.items():
            if field_name == "prompt":
                value = request.prompt
            else:
                if field_name not in request.input_data:
                    raise MediaRequestValidationError(
                        f"Falta input_data['{field_name}'] para '{self.strategy_name}'."
                    )
                value = request.input_data[field_name]
            if not isinstance(value, expected_type):
                raise MediaRequestValidationError(
                    f"'{field_name}' tiene un tipo incompatible con '{self.strategy_name}'."
                )

    def build_provider_request(self, request: MediaRequest) -> Mapping[str, Any]:
        self.validate_request(request)
        payload = dict(request.input_data)
        payload["prompt"] = request.prompt
        return payload

    def build_work_package(self, request: MediaRequest) -> MediaWorkPackage:
        return MediaWorkPackage(
            request_id=request.request_id,
            strategy_name=self.strategy_name,
            media_type=self.media_type,
            capability=self.provider_capability,
            provider_payload=self.build_provider_request(request),
            output_format=self.output_format,
            preferred_provider=request.preferred_provider,
            post_process_chain=self.post_process_chain,
            metadata=request.metadata,
        )

    def normalize_provider_result(
        self,
        raw_output: Any,
        *,
        work_package: MediaWorkPackage,
    ) -> Any:
        return raw_output

    def validate_result(
        self,
        normalized_output: Any,
        *,
        work_package: MediaWorkPackage,
    ) -> None:
        if normalized_output is None:
            raise MediaResultValidationError(
                f"'{self.strategy_name}' recibió un resultado vacío."
            )


class VoiceStrategy(MediaStrategy):
    strategy_name = "voice"
    media_type = MediaType.VOICE
    provider_capability = "voice_synthesis"
    output_format = "audio"
    default_post_process_chain = (
        PostProcessStep("package"),
    )


class ImageStrategy(MediaStrategy):
    strategy_name = "image"
    media_type = MediaType.IMAGE
    provider_capability = "image_generation"
    output_format = "image"
    default_post_process_chain = (
        PostProcessStep("optimize"),
        PostProcessStep("resize"),
        PostProcessStep("package"),
    )


class VideoStrategy(MediaStrategy):
    strategy_name = "video"
    media_type = MediaType.VIDEO
    provider_capability = "video_rendering"
    output_format = "video"
    default_post_process_chain = (
        PostProcessStep("compress"),
        PostProcessStep("subtitle"),
        PostProcessStep("package"),
    )


__all__ = [
    "MediaStrategy",
    "VoiceStrategy",
    "ImageStrategy",
    "VideoStrategy",
]
