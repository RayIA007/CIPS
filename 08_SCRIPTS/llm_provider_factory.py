"""
=========================================================
Proyecto : CIPS
Release  : 0.5
Build    : 036
Archivo  : llm_provider_factory.py
Estado   : RELEASE
=========================================================

Crea proveedores LLM a partir de nombres configurables.

Proveedores registrados:
- manual
- gemini

Los proveedores futuros podrán agregarse sin modificar
LLMAdapter ni PipelineRunner.
"""

from collections.abc import Callable
from typing import Any

from gemini_llm_provider import GeminiLLMProvider
from llm_provider import LLMProvider
from manual_llm_provider import ManualLLMProvider


ProviderBuilder = Callable[..., LLMProvider]


class LLMProviderFactory:
    """
    Fábrica oficial de proveedores LLM de CIPS.

    Ejemplos:

        LLMProviderFactory.create("manual")

        LLMProviderFactory.create(
            "gemini",
            model="gemini-3.5-flash",
            temperature=0.2,
        )
    """

    _providers: dict[str, ProviderBuilder] = {
        "manual": ManualLLMProvider,
        "gemini": GeminiLLMProvider,
    }

    @classmethod
    def create(
        cls,
        provider_name: str,
        **provider_options: Any,
    ) -> LLMProvider:
        """
        Crea una instancia del proveedor solicitado.

        Raises:
            ValueError:
                Si el proveedor no está registrado.

            TypeError:
                Si la instancia no implementa LLMProvider.
        """

        normalized_name = cls._normalize_name(
            provider_name
        )

        provider_builder = cls._providers.get(
            normalized_name
        )

        if provider_builder is None:
            available = ", ".join(
                cls.available_providers()
            )

            raise ValueError(
                "Proveedor LLM no registrado: "
                f"{provider_name}. "
                f"Proveedores disponibles: {available}"
            )

        try:
            provider = provider_builder(
                **provider_options
            )

        except TypeError as error:
            raise TypeError(
                "No fue posible construir el proveedor "
                f"'{normalized_name}' con las opciones recibidas: "
                f"{error}"
            ) from error

        if not isinstance(
            provider,
            LLMProvider,
        ):
            raise TypeError(
                "El proveedor creado no implementa "
                "la interfaz LLMProvider."
            )

        return provider

    @classmethod
    def register(
        cls,
        provider_name: str,
        provider_builder: ProviderBuilder,
        replace: bool = False,
    ) -> None:
        """
        Registra dinámicamente un proveedor.

        Args:
            provider_name:
                Nombre utilizado por la configuración.

            provider_builder:
                Clase o función constructora del proveedor.

            replace:
                Permite sustituir un registro existente.
        """

        normalized_name = cls._normalize_name(
            provider_name
        )

        if not callable(provider_builder):
            raise TypeError(
                "provider_builder debe ser invocable."
            )

        if (
            normalized_name in cls._providers
            and not replace
        ):
            raise ValueError(
                "El proveedor ya está registrado: "
                f"{normalized_name}"
            )

        cls._providers[normalized_name] = (
            provider_builder
        )

    @classmethod
    def unregister(
        cls,
        provider_name: str,
    ) -> None:
        """
        Elimina un proveedor del registro.

        El proveedor manual permanece como respaldo obligatorio.
        """

        normalized_name = cls._normalize_name(
            provider_name
        )

        if normalized_name == "manual":
            raise ValueError(
                "El proveedor manual no puede eliminarse."
            )

        cls._providers.pop(
            normalized_name,
            None,
        )

    @classmethod
    def is_registered(
        cls,
        provider_name: str,
    ) -> bool:
        """
        Indica si el proveedor está registrado.
        """

        normalized_name = cls._normalize_name(
            provider_name
        )

        return normalized_name in cls._providers

    @classmethod
    def available_providers(
        cls,
    ) -> list[str]:
        """
        Devuelve los nombres de proveedores registrados.
        """

        return sorted(
            cls._providers.keys()
        )

    @classmethod
    def provider_info(
        cls,
        provider_name: str,
        **provider_options: Any,
    ) -> dict[str, str]:
        """
        Construye temporalmente el proveedor y devuelve
        su información pública.
        """

        provider = cls.create(
            provider_name,
            **provider_options,
        )

        return provider.get_provider_info()

    @classmethod
    def registered_provider_classes(
        cls,
    ) -> dict[str, str]:
        """
        Devuelve los nombres de las clases registradas.
        """

        return {
            provider_name: getattr(
                provider_builder,
                "__name__",
                provider_builder.__class__.__name__,
            )
            for provider_name, provider_builder
            in sorted(cls._providers.items())
        }

    @staticmethod
    def _normalize_name(
        provider_name: str,
    ) -> str:
        """
        Normaliza el nombre recibido.
        """

        if not isinstance(
            provider_name,
            str,
        ):
            raise TypeError(
                "provider_name debe ser una cadena."
            )

        normalized_name = (
            provider_name
            .strip()
            .lower()
            .replace("-", "_")
            .replace(" ", "_")
        )

        if not normalized_name:
            raise ValueError(
                "provider_name no puede estar vacío."
            )

        return normalized_name