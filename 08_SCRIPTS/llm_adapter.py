"""
=========================================================
Proyecto : CIPS
Release  : 0.5
Build    : 033
Archivo  : llm_adapter.py
Estado   : RELEASE
=========================================================

Conecta RuntimeContext con el proveedor LLM configurado.

Responsabilidades:
- cargar la configuración activa de llm.yaml;
- crear el proveedor mediante LLMProviderFactory;
- obtener el prompt desde RuntimeContext;
- solicitar una respuesta al proveedor;
- guardar LLMResponse dentro de RuntimeContext;
- comunicar estados pendientes, errores y advertencias.
"""

from typing import Any

from llm_config import LLMConfigManager, LLMSettings
from llm_provider import LLMProvider, ProviderResult
from runtime_component import RuntimeComponent
from runtime_context import RuntimeContext
from runtime_models import EngineResult


class LLMAdapter(RuntimeComponent):
    """
    Adaptador entre RuntimeContext y cualquier proveedor LLM.

    El proveedor puede configurarse de dos maneras:

    1. Mediante 01_CONFIG/llm.yaml.
    2. Mediante una instancia explícita recibida en __init__.

    Si no existe un proveedor real disponible, la configuración
    utilizará ManualLLMProvider como respaldo seguro.
    """

    component_name = "llm_adapter"

    def __init__(
        self,
        provider: LLMProvider | None = None,
        config_manager: LLMConfigManager | None = None,
    ) -> None:
        """
        Inicializa el Adapter y resuelve el proveedor activo.
        """

        self.config_manager = (
            config_manager
            or LLMConfigManager()
        )

        self.settings = self.config_manager.load()

        if provider is not None:
            self._validate_provider(provider)
            self.provider = provider
            self.provider_source = "explicit"
        else:
            self.provider = (
                self.config_manager.create_provider(
                    self.settings
                )
            )
            self.provider_source = "configuration"

    def execute(
        self,
        runtime_context: RuntimeContext,
    ) -> EngineResult:
        """
        Solicita una respuesta al proveedor activo.
        """

        try:
            if not isinstance(
                runtime_context,
                RuntimeContext,
            ):
                return EngineResult.fail(
                    message=(
                        "LLMAdapter requiere un "
                        "RuntimeContext válido."
                    ),
                    errors=[
                        "Entrada incompatible con RuntimeContext."
                    ],
                    metadata={
                        "component": self.component_name,
                    },
                )

            prompt = self._get_prompt(
                runtime_context
            )

            if not prompt:
                return EngineResult.fail(
                    message=(
                        "No existe un prompt disponible "
                        "para enviar al proveedor LLM."
                    ),
                    errors=[
                        "RuntimeContext.prompt_markdown vacío."
                    ],
                    metadata=self._build_metadata(
                        runtime_context
                    ),
                )

            provider_metadata = (
                self._build_provider_metadata(
                    runtime_context
                )
            )

            provider_result = self.provider.generate(
                prompt=prompt,
                metadata=provider_metadata,
            )

            return self._process_provider_result(
                runtime_context=runtime_context,
                provider_result=provider_result,
                prompt=prompt,
            )

        except Exception as error:
            return EngineResult.fail(
                message="Error inesperado en LLMAdapter.",
                errors=[str(error)],
                metadata={
                    "component": self.component_name,
                    **self.provider.get_provider_info(),
                },
            )

    def reload_configuration(self) -> LLMSettings:
        """
        Recarga llm.yaml y reconstruye el proveedor activo.
        """

        self.settings = self.config_manager.load()

        self.provider = (
            self.config_manager.create_provider(
                self.settings
            )
        )

        self.provider_source = "configuration"

        return self.settings

    def set_provider(
        self,
        provider: LLMProvider,
    ) -> None:
        """
        Cambia el proveedor manualmente durante la ejecución.
        """

        self._validate_provider(provider)

        self.provider = provider
        self.provider_source = "explicit"

    def get_provider(
        self,
    ) -> LLMProvider:
        """
        Devuelve el proveedor actualmente configurado.
        """

        return self.provider

    def get_configuration_summary(
        self,
    ) -> dict[str, Any]:
        """
        Devuelve un resumen seguro de la configuración activa.
        """

        summary = (
            self.config_manager.get_runtime_summary()
        )

        summary.update(
            {
                "provider_source": self.provider_source,
                "resolved_provider": (
                    self.provider.provider_name
                ),
                "resolved_model": (
                    self.provider.model_name
                ),
            }
        )

        return summary

    def _validate_provider(
        self,
        provider: LLMProvider,
    ) -> None:
        """
        Verifica que el proveedor implemente LLMProvider.
        """

        if not isinstance(
            provider,
            LLMProvider,
        ):
            raise TypeError(
                "provider debe implementar LLMProvider."
            )

    def _get_prompt(
        self,
        runtime_context: RuntimeContext,
    ) -> str:
        """
        Obtiene el prompt Markdown activo.
        """

        return (
            runtime_context.prompt_markdown
            or ""
        ).strip()

    def _build_provider_metadata(
        self,
        runtime_context: RuntimeContext,
    ) -> dict[str, Any]:
        """
        Construye los metadatos enviados al proveedor.
        """

        project = runtime_context.project

        metadata: dict[str, Any] = {
            "project_id": project.project_id,
            "stage": project.stage_actual,
            "tema": project.tema,
            "prompt_path": runtime_context.prompt_path,
            "configured_provider": (
                self.settings.provider
            ),
            "configured_model": (
                self.settings.model
            ),
            "timeout_seconds": (
                self.settings.timeout_seconds
            ),
            "temperature": (
                self.settings.temperature
            ),
            "max_output_tokens": (
                self.settings.max_output_tokens
            ),
        }

        manual_response = (
            runtime_context.metadata.get(
                "manual_response"
            )
        )

        if manual_response is not None:
            metadata["manual_response"] = (
                manual_response
            )

        return metadata

    def _process_provider_result(
        self,
        runtime_context: RuntimeContext,
        provider_result: ProviderResult,
        prompt: str,
    ) -> EngineResult:
        """
        Convierte ProviderResult en EngineResult.
        """

        metadata = {
            **self._build_metadata(
                runtime_context
            ),
            **provider_result.metadata,
            "prompt_characters": len(prompt),
        }

        if not provider_result.success:
            self._register_provider_state(
                runtime_context=runtime_context,
                provider_result=provider_result,
            )

            return EngineResult.fail(
                message=provider_result.message,
                errors=list(
                    provider_result.errors
                ),
                warnings=list(
                    provider_result.warnings
                ),
                metadata=metadata,
            )

        if provider_result.response is None:
            return EngineResult.fail(
                message=(
                    "El proveedor informó éxito, pero no "
                    "devolvió una LLMResponse."
                ),
                errors=[
                    "ProviderResult.response es None."
                ],
                warnings=list(
                    provider_result.warnings
                ),
                metadata=metadata,
            )

        runtime_context.llm_response = (
            provider_result.response
        )

        runtime_context.metadata["llm_provider"] = {
            "provider": self.provider.provider_name,
            "model": self.provider.model_name,
            "source": self.provider_source,
            "success": True,
            "response_characters": len(
                provider_result.response.content
            ),
        }

        return EngineResult.ok(
            data=runtime_context,
            message=provider_result.message,
            warnings=list(
                provider_result.warnings
            ),
            metadata={
                **metadata,
                "response_characters": len(
                    provider_result.response.content
                ),
                "llm_response_available": True,
            },
        )

    def _register_provider_state(
        self,
        runtime_context: RuntimeContext,
        provider_result: ProviderResult,
    ) -> None:
        """
        Registra estados pendientes o fallidos del proveedor.
        """

        runtime_context.metadata["llm_provider"] = {
            "provider": self.provider.provider_name,
            "model": self.provider.model_name,
            "source": self.provider_source,
            "success": provider_result.success,
            "requires_user_action": (
                provider_result.metadata.get(
                    "requires_user_action",
                    False,
                )
            ),
            "message": provider_result.message,
        }

    def _build_metadata(
        self,
        runtime_context: RuntimeContext,
    ) -> dict[str, Any]:
        """
        Construye metadatos comunes del Adapter.
        """

        project = runtime_context.project

        return {
            "component": self.component_name,
            "project_id": project.project_id,
            "stage": project.stage_actual,
            "provider_source": self.provider_source,
            "configured_provider": (
                self.settings.provider
            ),
            "configured_model": (
                self.settings.model
            ),
            **self.provider.get_provider_info(),
        }