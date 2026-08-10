from __future__ import annotations

from dataclasses import dataclass, field, fields, is_dataclass
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping
from uuid import uuid4


MODEL_VERSION = "1.0.0"


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:16]}"


def _freeze_mapping(value: Mapping[str, Any] | None) -> Mapping[str, Any]:
    if value is None:
        return MappingProxyType({})
    if not isinstance(value, Mapping):
        raise TypeError("Se esperaba un objeto Mapping.")
    return MappingProxyType(dict(value))


def _to_primitive(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return {item.name: _to_primitive(getattr(value, item.name)) for item in fields(value)}
    if isinstance(value, Mapping):
        return {str(key): _to_primitive(item) for key, item in value.items()}
    if isinstance(value, (tuple, list, set, frozenset)):
        return [_to_primitive(item) for item in value]
    return value


class SerializableModel:
    schema_version = MODEL_VERSION

    def to_dict(self) -> dict[str, Any]:
        return _to_primitive(self)


class MediaType(str, Enum):
    VOICE = "voice"
    IMAGE = "image"
    VIDEO = "video"


@dataclass(frozen=True, slots=True)
class PostProcessStep(SerializableModel):
    """Paso declarativo; F5 no lo ejecuta internamente."""

    name: str
    required: bool = True
    parameters: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        name = str(self.name).strip()
        if not name:
            raise ValueError("PostProcessStep.name es obligatorio.")
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "parameters", _freeze_mapping(self.parameters))


@dataclass(frozen=True, slots=True)
class MediaRequest(SerializableModel):
    """Solicitud de dominio independiente de SDKs, filesystem y providers."""

    prompt: str
    input_data: Mapping[str, Any] = field(default_factory=dict)
    preferred_provider: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
    request_id: str = field(default_factory=lambda: _new_id("media_req"))

    def __post_init__(self) -> None:
        prompt = str(self.prompt).strip()
        if not prompt:
            raise ValueError("MediaRequest.prompt es obligatorio.")
        request_id = str(self.request_id).strip()
        if not request_id:
            raise ValueError("MediaRequest.request_id es obligatorio.")
        preferred = None
        if self.preferred_provider is not None:
            preferred = str(self.preferred_provider).strip().lower() or None
        object.__setattr__(self, "prompt", prompt)
        object.__setattr__(self, "request_id", request_id)
        object.__setattr__(self, "preferred_provider", preferred)
        object.__setattr__(self, "input_data", _freeze_mapping(self.input_data))
        object.__setattr__(self, "metadata", _freeze_mapping(self.metadata))


@dataclass(frozen=True, slots=True)
class MediaWorkPackage(SerializableModel):
    """Paquete normalizado que una capa de integración puede enviar a F4."""

    request_id: str
    strategy_name: str
    media_type: MediaType
    capability: str
    provider_payload: Mapping[str, Any]
    output_format: str
    preferred_provider: str | None = None
    post_process_chain: tuple[PostProcessStep, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("request_id", "strategy_name", "capability", "output_format"):
            value = str(getattr(self, field_name)).strip()
            if not value:
                raise ValueError(f"MediaWorkPackage.{field_name} es obligatorio.")
            object.__setattr__(self, field_name, value)
        object.__setattr__(self, "media_type", MediaType(self.media_type))
        object.__setattr__(self, "provider_payload", _freeze_mapping(self.provider_payload))
        object.__setattr__(self, "metadata", _freeze_mapping(self.metadata))
        object.__setattr__(self, "post_process_chain", tuple(self.post_process_chain))


@dataclass(frozen=True, slots=True)
class MediaResult(SerializableModel):
    """Resultado de dominio; no representa un artifact persistido de F3."""

    request_id: str
    strategy_name: str
    media_type: MediaType
    capability: str
    output_format: str
    output: Any
    post_process_chain: tuple[PostProcessStep, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("request_id", "strategy_name", "capability", "output_format"):
            value = str(getattr(self, field_name)).strip()
            if not value:
                raise ValueError(f"MediaResult.{field_name} es obligatorio.")
            object.__setattr__(self, field_name, value)
        object.__setattr__(self, "media_type", MediaType(self.media_type))
        object.__setattr__(self, "post_process_chain", tuple(self.post_process_chain))
        object.__setattr__(self, "metadata", _freeze_mapping(self.metadata))


__all__ = [
    "MODEL_VERSION",
    "MediaType",
    "PostProcessStep",
    "MediaRequest",
    "MediaWorkPackage",
    "MediaResult",
]
