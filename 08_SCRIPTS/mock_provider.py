"""
=========================================================
Proyecto : CIPS
Release  : 0.5
Build    : 001
Archivo  : mock_provider.py
Estado   : RELEASE
=========================================================

Proveedor LLM simulado para pruebas locales.

Permite validar el pipeline, los adaptadores y el administrador
de proveedores sin realizar llamadas externas ni consumir tokens.
"""

from typing import Any

from llm_provider import LLMProvider, ProviderResult
from runtime_models import LLMResponse


class MockProvider(LLMProvider):
    """
    Proveedor simulado de respuestas LLM.

    Genera una respuesta Markdown determinista a partir del prompt
    recibido y conserva los metadatos de la ejecución.
    """

    provider_name = "mock"
    model_name = "mock-cips-v1"

    supports_streaming = False
    supports_system_prompt = True
    supports_images = False
    supports_tools = False

    def generate(
        self,
        prompt: str,
        metadata: dict[str, Any] | None = None,
    ) -> ProviderResult:
        """
        Genera una respuesta simulada.

        Args:
            prompt:
                Prompt que será procesado de manera local.

            metadata:
                Metadatos opcionales de la ejecución.

        Returns:
            ProviderResult:
                Resultado exitoso o fallido de la simulación.
        """

        errors = self.validate_prompt(prompt)

        if errors:
            return ProviderResult.fail(
                message="El MockProvider rechazó el prompt.",
                errors=errors,
                metadata=self._build_metadata(metadata),
            )

        prepared_prompt = self.prepare_prompt(prompt)

        content = self._build_response(
            prompt=prepared_prompt,
        )

        response_metadata = self._build_metadata(metadata)

        response_metadata.update(
            {
                "prompt_characters": len(prepared_prompt),
                "estimated_prompt_tokens": self.estimate_tokens(
                    prepared_prompt
                ),
                "simulated": True,
            }
        )

        response = LLMResponse(
            content=content,
            model=self.model_name,
            metadata=response_metadata,
        )

        return ProviderResult.ok(
            response=response,
            message="Respuesta simulada generada correctamente.",
            metadata=response_metadata,
        )

    def health_check(self) -> bool:
        """
        Indica que el proveedor simulado está disponible.
        """

        return True

    def _build_response(
        self,
        prompt: str,
    ) -> str:
        """
        Construye una respuesta Markdown determinista.
        """

        return (
            "# Briefing Estratégico\n\n"
            "## Estado\n\n"
            "Contenido generado correctamente por MockProvider.\n\n"
            "## Proveedor\n\n"
            f"{self.provider_name}\n\n"
            "## Modelo\n\n"
            f"{self.model_name}\n\n"
            "## Longitud del prompt\n\n"
            f"{len(prompt)} caracteres.\n\n"
            "## Tokens estimados\n\n"
            f"{self.estimate_tokens(prompt)} tokens.\n\n"
            "## Nota\n\n"
            "Esta respuesta es una simulación local y no fue "
            "generada por un modelo externo.\n"
        )

    def _build_metadata(
        self,
        metadata: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """
        Construye metadatos seguros para el resultado.
        """

        result = dict(metadata or {})

        result.update(
            {
                "provider": self.provider_name,
                "model": self.model_name,
            }
        )

        return result