"""
=========================================================
Proyecto : CIPS
Release  : 0.5
Build    : 032A
Archivo  : llm_config.py
Estado   : RELEASE
=========================================================

Carga y valida la configuración del LLM Provider Framework.

Responsabilidades:
- leer 01_CONFIG/llm.yaml;
- normalizar la configuración;
- seleccionar el proveedor activo;
- construir el proveedor mediante LLMProviderFactory;
- conservar el modo manual como respaldo seguro.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from llm_provider import LLMProvider
from llm_provider_factory import LLMProviderFactory
from utils import ROOT, read_yaml


LLM_CONFIG_PATH = ROOT / "01_CONFIG" / "llm.yaml"


@dataclass
class LLMSettings:
    """
    Configuración normalizada del proveedor LLM activo.
    """

    mode: str = "manual"
    provider: str = "manual"
    model: str = "external_manual"
    enabled: bool = True
    timeout_seconds: int = 60
    temperature: float = 0.2
    max_output_tokens: int | None = None
    provider_options: dict[str, Any] = field(
        default_factory=dict
    )
    metadata: dict[str, Any] = field(
        default_factory=dict
    )


class LLMConfigManager:
    """
    Administra la configuración de proveedores LLM.

    Si llm.yaml no existe, está incompleto o el proveedor
    solicitado no está disponible, utiliza el proveedor
    manual como respaldo seguro.
    """

    def __init__(
        self,
        config_path: Path = LLM_CONFIG_PATH,
    ) -> None:
        self.config_path = config_path

    def load(self) -> LLMSettings:
        """
        Lee y normaliza la configuración del proveedor activo.
        """

        raw_config = read_yaml(
            self.config_path
        )

        if not isinstance(raw_config, dict):
            raw_config = {}

        runtime_config = self._get_runtime_config(
            raw_config
        )

        provider_name = self._normalize_identifier(
            runtime_config.get(
                "provider",
                runtime_config.get(
                    "default_provider",
                    "manual",
                ),
            ),
            default="manual",
        )

        mode = self._normalize_identifier(
            runtime_config.get(
                "mode",
                provider_name,
            ),
            default="manual",
        )

        enabled = self._normalize_bool(
            runtime_config.get(
                "enabled",
                True,
            )
        )

        model = self._normalize_model_name(
            runtime_config.get(
                "model",
                "external_manual",
            ),
            default="external_manual",
        )

        timeout_seconds = self._normalize_positive_int(
            runtime_config.get(
                "timeout_seconds",
                60,
            ),
            default=60,
        )

        temperature = self._normalize_temperature(
            runtime_config.get(
                "temperature",
                0.2,
            )
        )

        max_output_tokens = self._normalize_optional_int(
            runtime_config.get(
                "max_output_tokens"
            )
        )

        provider_options = self._get_provider_options(
            raw_config=raw_config,
            provider_name=provider_name,
            runtime_config=runtime_config,
        )

        return LLMSettings(
            mode=mode,
            provider=provider_name,
            model=model,
            enabled=enabled,
            timeout_seconds=timeout_seconds,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            provider_options=provider_options,
            metadata={
                "config_path": str(self.config_path),
                "config_exists": self.config_path.exists(),
            },
        )

    def create_provider(
        self,
        settings: LLMSettings | None = None,
    ) -> LLMProvider:
        """
        Construye el proveedor activo.

        Cuando debe utilizarse el respaldo manual, elimina
        las opciones del proveedor original para no enviar
        argumentos incompatibles a ManualLLMProvider.
        """

        active_settings = settings or self.load()

        resolved_provider = self._resolve_provider_name(
            active_settings
        )

        if resolved_provider == active_settings.provider:
            provider_options = dict(
                active_settings.provider_options
            )
        else:
            provider_options = {}

        return LLMProviderFactory.create(
            resolved_provider,
            **provider_options,
        )

    def get_runtime_summary(self) -> dict[str, Any]:
        """
        Devuelve un resumen seguro de la configuración activa.

        Nunca expone credenciales.
        """

        settings = self.load()

        active_provider = self._resolve_provider_name(
            settings
        )

        return {
            "mode": settings.mode,
            "configured_provider": settings.provider,
            "active_provider": active_provider,
            "model": settings.model,
            "enabled": settings.enabled,
            "timeout_seconds": settings.timeout_seconds,
            "temperature": settings.temperature,
            "max_output_tokens": settings.max_output_tokens,
            "config_path": settings.metadata.get(
                "config_path"
            ),
            "available_providers": (
                LLMProviderFactory.available_providers()
            ),
        }

    def _resolve_provider_name(
        self,
        settings: LLMSettings,
    ) -> str:
        """
        Determina el proveedor que realmente debe utilizarse.
        """

        if not settings.enabled:
            return "manual"

        if not LLMProviderFactory.is_registered(
            settings.provider
        ):
            return "manual"

        return settings.provider

    def _get_runtime_config(
        self,
        raw_config: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Admite distintas estructuras durante la migración.
        """

        for section_name in (
            "runtime",
            "llm",
            "active",
        ):
            section = raw_config.get(
                section_name
            )

            if isinstance(section, dict):
                return section

        return raw_config

    def _get_provider_options(
        self,
        raw_config: dict[str, Any],
        provider_name: str,
        runtime_config: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Obtiene opciones específicas del proveedor configurado.
        """

        options: dict[str, Any] = {}

        runtime_options = runtime_config.get(
            "provider_options",
            {},
        )

        if isinstance(runtime_options, dict):
            options.update(runtime_options)

        providers = raw_config.get(
            "providers",
            {},
        )

        if isinstance(providers, dict):
            provider_config = providers.get(
                provider_name,
                {},
            )

            if isinstance(provider_config, dict):
                constructor_options = provider_config.get(
                    "options",
                    {},
                )

                if isinstance(
                    constructor_options,
                    dict,
                ):
                    options.update(
                        constructor_options
                    )

        return options

    def _normalize_identifier(
        self,
        value: Any,
        default: str,
    ) -> str:
        """
        Normaliza identificadores como provider y mode.
        """

        if not isinstance(value, str):
            return default

        normalized = (
            value.strip()
            .lower()
            .replace("-", "_")
            .replace(" ", "_")
        )

        return normalized or default

    def _normalize_model_name(
        self,
        value: Any,
        default: str,
    ) -> str:
        """
        Normaliza un nombre de modelo sin alterar guiones,
        puntos, barras u otros caracteres válidos.
        """

        if not isinstance(value, str):
            return default

        normalized = value.strip()

        return normalized or default

    def _normalize_bool(
        self,
        value: Any,
    ) -> bool:
        """
        Normaliza valores booleanos.
        """

        if isinstance(value, bool):
            return value

        if isinstance(value, str):
            return value.strip().lower() in {
                "true",
                "yes",
                "si",
                "sí",
                "1",
                "enabled",
            }

        return bool(value)

    def _normalize_positive_int(
        self,
        value: Any,
        default: int,
    ) -> int:
        """
        Convierte un valor a entero positivo.
        """

        try:
            number = int(value)
        except (TypeError, ValueError):
            return default

        if number <= 0:
            return default

        return number

    def _normalize_optional_int(
        self,
        value: Any,
    ) -> int | None:
        """
        Convierte un valor opcional a entero positivo.
        """

        if value in (
            None,
            "",
        ):
            return None

        try:
            number = int(value)
        except (TypeError, ValueError):
            return None

        if number <= 0:
            return None

        return number

    def _normalize_temperature(
        self,
        value: Any,
    ) -> float:
        """
        Normaliza la temperatura dentro del rango 0–2.
        """

        try:
            temperature = float(value)
        except (TypeError, ValueError):
            return 0.2

        return min(
            max(
                temperature,
                0.0,
            ),
            2.0,
        )