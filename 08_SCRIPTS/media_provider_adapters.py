"""
=========================================================
Proyecto : CIPS
Release  : 0.5
Build    : 001
Archivo  : media_provider_adapters.py
Estado   : RELEASE
=========================================================

Adaptadores mínimos para conectar funciones multimedia existentes con el
contrato ``MediaProvider`` de CIPS.

F4.5 mantiene estos adaptadores deliberadamente pequeños: reciben un backend
inyectable, no importan SDKs multimedia, no hacen retry/failover y no conocen
WorkspaceResolver ni ArtifactStore. La integración con ``11_MEDIA_PRODUCTION``
se realiza en una capa posterior (F4.6).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from copy import deepcopy
from os import PathLike
from pathlib import Path
from typing import Any

from media_provider import MediaProvider, MediaRequest, MediaResult, normalize_capability


MediaBackend = Callable[..., Any]


class MediaProviderAdapterError(RuntimeError):
    """Error base para adaptadores multimedia basados en callables."""


class CallableMediaProviderAdapter(MediaProvider):
    """Adapta un callable local al contrato :class:`MediaProvider`.

    El payload normalizado para F4.5 es una ruta de proyecto (``Path`` o
    ``os.PathLike``). ``request.options`` se reenvía como argumentos nombrados
    al backend. Esta forma coincide con las funciones multimedia existentes de
    CIPS y permite probar el adaptador con fakes sin cargar dependencias reales.
    """

    provider_name = "callable_media"
    capability_name = "media_generation"

    def __init__(
        self,
        backend: MediaBackend,
        *,
        provider_name: str | None = None,
        capability_metadata: Mapping[str, Any] | None = None,
    ) -> None:
        if not callable(backend):
            raise TypeError("backend debe ser callable.")

        resolved_name = self.provider_name if provider_name is None else provider_name
        self.provider_name = self._normalize_provider_name(resolved_name)
        self._backend = backend
        self._capability_metadata = deepcopy(dict(capability_metadata or {}))

    @property
    def backend(self) -> MediaBackend:
        """Callable adaptado; útil para inspección y composición controlada."""

        return self._backend

    def capabilities(self) -> dict[str, dict[str, Any]]:
        """Declara una única capacidad con metadata copiada defensivamente."""

        return {
            normalize_capability(self.capability_name): deepcopy(
                self._capability_metadata
            )
        }

    def validate_input(self, request: MediaRequest) -> list[str]:
        """Valida contrato base, ruta de proyecto y opciones serializables como mapping."""

        errors = super().validate_input(request)
        if errors:
            return errors

        if not isinstance(request.payload, (str, PathLike, Path)):
            errors.append(
                "payload debe ser una ruta de proyecto (str o os.PathLike)."
            )
        elif not str(request.payload).strip():
            errors.append("payload no puede ser una ruta vacía.")

        if not isinstance(request.options, dict):
            errors.append("options debe ser un diccionario.")

        return errors

    def generate(self, request: MediaRequest) -> MediaResult:
        """Ejecuta exactamente una vez el backend inyectado, sin retry ni failover."""

        errors = self.validate_input(request)
        if errors:
            return MediaResult.fail(
                errors=errors,
                metadata=self._result_metadata(),
            )

        project_dir = Path(request.payload)
        try:
            output = self._backend(project_dir, **dict(request.options))
        except Exception as error:  # La frontera normaliza el fallo del backend.
            return MediaResult.fail(
                message=(
                    f"El proveedor multimedia '{self.provider_name}' "
                    "no pudo completar la solicitud."
                ),
                errors=[f"{type(error).__name__}: {error}"],
                metadata={
                    **self._result_metadata(),
                    "backend_error_type": type(error).__name__,
                },
            )

        return MediaResult.ok(
            output,
            metadata=self._result_metadata(),
        )

    def _result_metadata(self) -> dict[str, Any]:
        return {
            "provider": self.provider_name,
            "capability": normalize_capability(self.capability_name),
            "adapter": self.__class__.__name__,
        }

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


class VoiceSynthesisAdapter(CallableMediaProviderAdapter):
    """Adaptador mínimo para síntesis de voz basada en un proyecto."""

    provider_name = "voice_adapter"
    capability_name = "voice_synthesis"


class ImageGenerationAdapter(CallableMediaProviderAdapter):
    """Adaptador mínimo para generación de imágenes/storyboard."""

    provider_name = "image_adapter"
    capability_name = "image_generation"


class VideoRenderingAdapter(CallableMediaProviderAdapter):
    """Adaptador mínimo para render/ensamblado de video."""

    provider_name = "video_adapter"
    capability_name = "video_rendering"


__all__ = [
    "CallableMediaProviderAdapter",
    "ImageGenerationAdapter",
    "MediaBackend",
    "MediaProviderAdapterError",
    "VideoRenderingAdapter",
    "VoiceSynthesisAdapter",
]
