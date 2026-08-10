"""
=========================================================
Proyecto : CIPS
Release  : 0.5
Build    : 001
Archivo  : fake_media_provider.py
Estado   : RELEASE
=========================================================

Fake multimedia determinista para pruebas de infraestructura CIPS.
No realiza IO, red, llamadas a SDKs ni persistencia.
"""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from media_provider import MediaProvider, MediaRequest, MediaResult, normalize_capability


class FakeMediaProvider(MediaProvider):
    """Provider configurable, determinista y libre de efectos externos."""

    provider_name = "fake_media"

    def __init__(
        self,
        *,
        provider_name: str,
        capabilities: Mapping[str, Mapping[str, Any] | None],
        outputs: Mapping[str, Any] | None = None,
        fail_capabilities: set[str] | None = None,
    ) -> None:
        self.provider_name = self._normalize_provider_name(provider_name)
        self._capabilities = self._normalize_capabilities(capabilities)
        self._outputs = {
            normalize_capability(name): deepcopy(value)
            for name, value in dict(outputs or {}).items()
        }
        self._fail_capabilities = {
            normalize_capability(name) for name in (fail_capabilities or set())
        }
        self.calls: list[MediaRequest] = []

    def capabilities(self) -> dict[str, dict[str, Any]]:
        return deepcopy(self._capabilities)

    def generate(self, request: MediaRequest) -> MediaResult:
        errors = self.validate_input(request)
        if errors:
            return MediaResult.fail(errors=errors)

        capability = normalize_capability(request.capability)
        self.calls.append(
            MediaRequest(
                capability=capability,
                payload=deepcopy(request.payload),
                options=deepcopy(request.options),
                metadata=deepcopy(request.metadata),
            )
        )

        metadata = {
            "provider": self.provider_name,
            "capability": capability,
            "fake": True,
        }
        if capability in self._fail_capabilities:
            return MediaResult.fail(
                message="Fallo determinista solicitado al fake multimedia.",
                errors=[f"fake_failure:{capability}"],
                metadata=metadata,
            )

        output = deepcopy(
            self._outputs.get(
                capability,
                {
                    "provider": self.provider_name,
                    "capability": capability,
                    "payload": request.payload,
                },
            )
        )
        return MediaResult.ok(output, metadata=metadata)

    @staticmethod
    def _normalize_provider_name(name: str) -> str:
        if not isinstance(name, str):
            raise TypeError("El nombre del proveedor debe ser una cadena de texto.")
        normalized = name.strip().lower()
        if not normalized:
            raise ValueError("El nombre del proveedor no puede estar vacío.")
        if normalized == "base":
            raise ValueError("'base' es un nombre reservado para MediaProvider.")
        return normalized

    @staticmethod
    def _normalize_capabilities(
        capabilities: Mapping[str, Mapping[str, Any] | None],
    ) -> dict[str, dict[str, Any]]:
        if not isinstance(capabilities, Mapping):
            raise TypeError("capabilities debe ser un mapping.")

        normalized: dict[str, dict[str, Any]] = {}
        for raw_name, raw_metadata in capabilities.items():
            capability = normalize_capability(raw_name)
            if raw_metadata is None:
                metadata: dict[str, Any] = {}
            elif isinstance(raw_metadata, Mapping):
                metadata = deepcopy(dict(raw_metadata))
            else:
                raise TypeError(
                    "Los metadatos de una capacidad deben ser un mapping o None."
                )
            normalized[capability] = metadata

        if not normalized:
            raise ValueError("El fake debe declarar al menos una capacidad.")
        return normalized


__all__ = ["FakeMediaProvider"]
