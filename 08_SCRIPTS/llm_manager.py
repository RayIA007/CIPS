"""
=========================================================
Proyecto : CIPS
Release  : 0.5
Build    : 001
Archivo  : llm_manager.py
Estado   : RELEASE
=========================================================

Administrador de proveedores LLM.
"""

from typing import Dict

from llm_provider import LLMProvider, ProviderResult


class LLMManager:
    """
    Administra los proveedores de modelos de lenguaje.
    """

    def __init__(self) -> None:

        self._providers: Dict[str, LLMProvider] = {}

        self._default_provider: str | None = None

    def register(
        self,
        provider: LLMProvider,
    ) -> None:
        """
        Registra un proveedor.
        """

        self._providers[
            provider.provider_name
        ] = provider

        if self._default_provider is None:
            self._default_provider = provider.provider_name

    def providers(self) -> list[str]:

        return sorted(
            self._providers.keys()
        )

    def has_provider(
        self,
        name: str,
    ) -> bool:

        return name in self._providers

    def set_default(
        self,
        name: str,
    ) -> None:

        if name not in self._providers:

            raise ValueError(
                f"Proveedor '{name}' no registrado."
            )

        self._default_provider = name

    def get_default(self) -> LLMProvider:

        if self._default_provider is None:

            raise RuntimeError(
                "No existe un proveedor registrado."
            )

        return self._providers[
            self._default_provider
        ]

    def generate(
        self,
        prompt: str,
        provider_name: str | None = None,
    ) -> ProviderResult:
        """
        Genera una respuesta utilizando
        el proveedor seleccionado.
        """

        if provider_name is None:

            provider = self.get_default()

        else:

            if provider_name not in self._providers:

                raise ValueError(
                    f"Proveedor '{provider_name}' no registrado."
                )

            provider = self._providers[
                provider_name
            ]

        return provider.generate(
            prompt
        )