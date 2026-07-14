"""
=========================================================
Proyecto : CIPS
Release  : 0.5
Build    : 029
Archivo  : manual_llm_provider.py
Estado   : RELEASE
=========================================================

Implementa el proveedor manual de CIPS.

Este proveedor no llama a una API externa. Conserva el flujo
actual en el que el usuario copia el prompt, obtiene la respuesta
en una herramienta de IA y la guarda dentro del proyecto.
"""

from typing import Any

from llm_provider import LLMProvider, ProviderResult
from runtime_models import LLMResponse


class ManualLLMProvider(LLMProvider):
    """
    Proveedor manual del Runtime.

    Su responsabilidad es representar formalmente el modo manual
    dentro del LLM Provider Framework.

    No genera contenido por sí mismo.

    Cuando no recibe una respuesta manual, devuelve un resultado
    pendiente y conserva el prompt listo para ser utilizado fuera
    de CIPS.
    """

    provider_name = "manual"
    model_name = "external_manual"

    def generate(
        self,
        prompt: str,
        metadata: dict[str, Any] | None = None,
    ) -> ProviderResult:
        """
        Prepara una ejecución manual.

        El contenido opcional de la respuesta puede recibirse
        mediante:

            metadata["manual_response"]

        Cuando no existe respuesta, el resultado no se considera
        un error técnico. Se informa que la ejecución requiere
        intervención del usuario.
        """

        prompt_errors = self.validate_prompt(prompt)

        if prompt_errors:
            return ProviderResult.fail(
                message="El prompt manual no es válido.",
                errors=prompt_errors,
                metadata={
                    "provider": self.provider_name,
                    "model": self.model_name,
                },
            )

        execution_metadata = dict(metadata or {})

        manual_response = execution_metadata.get(
            "manual_response"
        )

        if manual_response is None:
            return ProviderResult.fail(
                message=(
                    "La ejecución manual requiere que el usuario "
                    "copie el prompt, obtenga una respuesta externa "
                    "y la guarde en el archivo del Stage actual."
                ),
                warnings=[
                    "Proveedor manual pendiente de respuesta."
                ],
                errors=[],
                metadata={
                    **execution_metadata,
                    "provider": self.provider_name,
                    "model": self.model_name,
                    "requires_user_action": True,
                    "prompt_characters": len(prompt),
                },
            )

        response_content = str(
            manual_response
        ).strip()

        if not response_content:
            return ProviderResult.fail(
                message="La respuesta manual está vacía.",
                errors=[
                    "metadata['manual_response'] no contiene texto."
                ],
                metadata={
                    **execution_metadata,
                    "provider": self.provider_name,
                    "model": self.model_name,
                    "requires_user_action": True,
                    "prompt_characters": len(prompt),
                },
            )

        response = LLMResponse(
            content=response_content,
            model=self.model_name,
            metadata={
                **execution_metadata,
                "provider": self.provider_name,
                "mode": "manual",
                "prompt_characters": len(prompt),
                "response_characters": len(response_content),
            },
        )

        return ProviderResult.ok(
            response=response,
            message="Respuesta manual recibida correctamente.",
            metadata={
                **execution_metadata,
                "provider": self.provider_name,
                "model": self.model_name,
                "requires_user_action": False,
                "prompt_characters": len(prompt),
                "response_characters": len(response_content),
            },
        )