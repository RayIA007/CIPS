"""
=========================================================
Proyecto : CIPS
Release  : 0.9
Build    : 073
Archivo  : cost_analyzer.py
Estado   : RELEASE
=========================================================

Calcula costos estimados de tokens a partir de:
- provider_pricing.yaml;
- TelemetryEvent;
- proveedor;
- modelo;
- tier;
- modo de facturación.

Responsabilidades:
- cargar y validar configuración de precios;
- resolver proveedor, modelo, alias, tier y modo;
- calcular costos de entrada, salida, pensamiento y caché;
- analizar un TelemetryEvent;
- analizar múltiples eventos;
- generar StageCostAnalysis;
- generar ProjectCostReport;
- advertir sobre precios desconocidos o incompletos.

Este componente NO:
- llama proveedores;
- ejecuta el Pipeline;
- modifica telemetría;
- escribe reportes;
- modifica provider_pricing.yaml;
- sustituye TelemetryEngine.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from uuid import uuid4

import yaml

from cost_models import (
    CostBreakdown,
    CostStatus,
    ProjectCostReport,
    StageCostAnalysis,
    TokenUsageBreakdown,
)
from telemetry_models import TelemetryEvent
from utils import ROOT


class CostAnalyzer:
    """
    Analizador de costos y consumo de tokens.
    """

    COMPONENT_NAME = "cost_analyzer"
    VERSION = "0.9"

    DEFAULT_CONFIG_PATH = (
        ROOT
        / "01_CONFIG"
        / "provider_pricing.yaml"
    )

    def __init__(
        self,
        config_path: Path | str | None = None,
    ) -> None:
        """
        Inicializa y carga la configuración de precios.
        """

        self.config_path = Path(
            config_path
            or self.DEFAULT_CONFIG_PATH
        ).expanduser().resolve()

        self.config: dict[str, Any] = {}
        self.schema: dict[str, Any] = {}
        self.defaults: dict[str, Any] = {}
        self.providers: dict[str, Any] = {}
        self.calculation_config: dict[str, Any] = {}

        self.reload_configuration()

    # --------------------------------------------------
    # API pública
    # --------------------------------------------------

    def reload_configuration(
        self,
    ) -> dict[str, Any]:
        """
        Recarga provider_pricing.yaml.
        """

        if not self.config_path.exists():
            raise FileNotFoundError(
                f"No existe la configuración de precios: "
                f"{self.config_path}"
            )

        raw = yaml.safe_load(
            self.config_path.read_text(
                encoding="utf-8"
            )
        )

        if not isinstance(
            raw,
            dict,
        ):
            raise ValueError(
                "provider_pricing.yaml debe contener "
                "un objeto YAML."
            )

        self.config = raw

        self.schema = self._dict_value(
            raw.get(
                "schema"
            )
        )

        self.defaults = self._dict_value(
            raw.get(
                "defaults"
            )
        )

        self.providers = self._dict_value(
            raw.get(
                "providers"
            )
        )

        self.calculation_config = self._dict_value(
            raw.get(
                "calculation"
            )
        )

        if not self.providers:
            raise ValueError(
                "provider_pricing.yaml no contiene "
                "proveedores."
            )

        return dict(
            self.config
        )

    def analyze_usage(
        self,
        *,
        project_id: str,
        stage: str,
        provider: str,
        model: str,
        prompt_tokens: int = 0,
        response_tokens: int = 0,
        thinking_tokens: int = 0,
        cached_input_tokens: int = 0,
        cache_write_tokens: int = 0,
        total_tokens: int = 0,
        duration_seconds: float = 0.0,
        retry_count: int = 0,
        retry_exhausted: bool = False,
        succeeded_after_retry: bool = False,
        billing_tier: str | None = None,
        billing_mode: str | None = None,
        tool_cost: float = 0.0,
        other_cost: float = 0.0,
        metadata: dict[str, Any] | None = None,
    ) -> StageCostAnalysis:
        """
        Calcula costo estimado de una ejecución.
        """

        resolved_provider = self._normalize_name(
            provider
            or self.defaults.get(
                "provider",
                "",
            )
        )

        resolved_model = str(
            model
            or self.defaults.get(
                "model",
                "",
            )
        ).strip()

        resolved_tier = self._normalize_name(
            billing_tier
            or self.defaults.get(
                "billing_tier",
                "paid",
            )
        )

        resolved_mode = self._normalize_name(
            billing_mode
            or self.defaults.get(
                "billing_mode",
                "standard",
            )
        )

        token_usage = TokenUsageBreakdown(
            prompt_tokens=prompt_tokens,
            response_tokens=response_tokens,
            thinking_tokens=thinking_tokens,
            cached_input_tokens=cached_input_tokens,
            cache_write_tokens=cache_write_tokens,
            total_tokens=total_tokens,
            metadata={
                "source": self.COMPONENT_NAME,
            },
        )

        pricing = self.resolve_pricing(
            provider=resolved_provider,
            model=resolved_model,
            billing_tier=resolved_tier,
            billing_mode=resolved_mode,
        )

        status = pricing["status"]

        warnings = list(
            pricing["warnings"]
        )

        errors = list(
            pricing["errors"]
        )

        rates = dict(
            pricing["rates"]
        )

        token_unit = self._positive_int(
            self.schema.get(
                "token_unit",
                1_000_000,
            ),
            1_000_000,
        )

        currency = str(
            self.schema.get(
                "currency",
                self.defaults.get(
                    "currency",
                    "USD",
                ),
            )
            or "USD"
        ).upper()

        billable_input_tokens = (
            token_usage.billable_input_tokens()
        )

        input_rate = self._rate_value(
            rates,
            "input",
        )

        output_rate = self._rate_value(
            rates,
            "output",
        )

        thinking_rate = self._rate_value(
            rates,
            "thinking",
            fallback=output_rate,
        )

        cached_input_rate = self._rate_value(
            rates,
            "cached_input",
        )

        cache_write_rate = self._rate_value(
            rates,
            "cache_write",
        )

        if resolved_tier == "free_tier":
            status = CostStatus.FREE_TIER

            input_rate = 0.0
            output_rate = 0.0
            thinking_rate = 0.0
            cached_input_rate = 0.0
            cache_write_rate = 0.0

        input_cost = self._token_cost(
            billable_input_tokens,
            input_rate,
            token_unit,
        )

        output_cost = self._token_cost(
            token_usage.response_tokens,
            output_rate,
            token_unit,
        )

        thinking_cost = self._token_cost(
            token_usage.thinking_tokens,
            thinking_rate,
            token_unit,
        )

        cached_input_cost = self._token_cost(
            token_usage.cached_input_tokens,
            cached_input_rate,
            token_unit,
        )

        cache_write_cost = self._token_cost(
            token_usage.cache_write_tokens,
            cache_write_rate,
            token_unit,
        )

        tool_cost = self._non_negative_float(
            tool_cost
        )

        other_cost = self._non_negative_float(
            other_cost
        )

        if (
            status == CostStatus.CALCULATED
            and self._missing_required_rates(
                token_usage=token_usage,
                rates=rates,
                billing_tier=resolved_tier,
            )
        ):
            status = CostStatus.PARTIAL

            warnings.append(
                "El cálculo es parcial porque faltan "
                "una o más tarifas necesarias."
            )

        cost = CostBreakdown(
            status=status,
            currency=currency,
            token_unit=token_unit,
            input_rate=input_rate,
            output_rate=output_rate,
            thinking_rate=thinking_rate,
            cached_input_rate=cached_input_rate,
            cache_write_rate=cache_write_rate,
            input_cost=input_cost,
            output_cost=output_cost,
            thinking_cost=thinking_cost,
            cached_input_cost=cached_input_cost,
            cache_write_cost=cache_write_cost,
            tool_cost=tool_cost,
            other_cost=other_cost,
            billing_tier=resolved_tier,
            billing_mode=resolved_mode,
            pricing_source=str(
                pricing.get(
                    "pricing_source",
                    "",
                )
            ),
            pricing_last_verified=str(
                self.schema.get(
                    "last_verified",
                    "",
                )
            ),
            pricing_is_estimate=bool(
                self.schema.get(
                    "pricing_is_estimate",
                    True,
                )
            ),
            metadata={
                "resolved_provider": (
                    pricing.get(
                        "resolved_provider",
                        resolved_provider,
                    )
                ),
                "resolved_model": (
                    pricing.get(
                        "resolved_model",
                        resolved_model,
                    )
                ),
                "pricing_mode": (
                    pricing.get(
                        "resolved_mode",
                        resolved_mode,
                    )
                ),
                "pricing_tier": (
                    pricing.get(
                        "resolved_tier",
                        resolved_tier,
                    )
                ),
                "rate_keys": sorted(
                    rates
                ),
            },
        )

        analysis = StageCostAnalysis(
            analysis_id=self._new_analysis_id(),
            project_id=project_id,
            stage=stage,
            provider=resolved_provider,
            model=resolved_model,
            status=status,
            token_usage=token_usage,
            cost=cost,
            duration_seconds=duration_seconds,
            retry_count=retry_count,
            retry_exhausted=retry_exhausted,
            succeeded_after_retry=(
                succeeded_after_retry
            ),
            warnings=self._unique_strings(
                warnings
            ),
            errors=self._unique_strings(
                errors
            ),
            metadata={
                **dict(
                    metadata or {}
                ),
                "component": self.COMPONENT_NAME,
                "version": self.VERSION,
                "config_path": str(
                    self.config_path
                ),
                "billable_input_tokens": (
                    billable_input_tokens
                ),
                "pricing_enabled": bool(
                    pricing.get(
                        "pricing_enabled",
                        False,
                    )
                ),
            },
        )

        return analysis

    def analyze_event(
        self,
        event: TelemetryEvent,
        *,
        billing_tier: str | None = None,
        billing_mode: str | None = None,
    ) -> StageCostAnalysis:
        """
        Calcula costo desde TelemetryEvent.
        """

        if not isinstance(
            event,
            TelemetryEvent,
        ):
            raise TypeError(
                "event debe ser TelemetryEvent."
            )

        metadata = dict(
            event.metadata or {}
        )

        cached_input_tokens = self._first_int(
            metadata,
            (
                "cached_input_tokens",
                "cache_read_tokens",
            ),
        )

        cache_write_tokens = self._first_int(
            metadata,
            (
                "cache_write_tokens",
                "cached_write_tokens",
            ),
        )

        tool_cost = self._first_float(
            metadata,
            (
                "tool_cost",
                "grounding_cost",
            ),
        )

        other_cost = self._first_float(
            metadata,
            (
                "other_cost",
                "additional_cost",
            ),
        )

        return self.analyze_usage(
            project_id=event.project_id,
            stage=event.stage,
            provider=event.provider,
            model=event.model,
            prompt_tokens=event.prompt_tokens,
            response_tokens=event.response_tokens,
            thinking_tokens=event.thinking_tokens,
            cached_input_tokens=cached_input_tokens,
            cache_write_tokens=cache_write_tokens,
            total_tokens=event.total_tokens,
            duration_seconds=event.duration_seconds,
            retry_count=event.retry_count,
            retry_exhausted=event.retry_exhausted,
            succeeded_after_retry=(
                event.succeeded_after_retry
            ),
            billing_tier=(
                billing_tier
                or metadata.get(
                    "billing_tier"
                )
            ),
            billing_mode=(
                billing_mode
                or metadata.get(
                    "billing_mode"
                )
            ),
            tool_cost=tool_cost,
            other_cost=other_cost,
            metadata={
                "event_id": event.event_id,
                "event_success": event.success,
                "status_code": event.status_code,
            },
        )

    def analyze_events(
        self,
        events: Iterable[
            TelemetryEvent | dict[str, Any]
        ],
        *,
        project_id: str = "",
        scope: str = "project",
        billing_tier: str | None = None,
        billing_mode: str | None = None,
    ) -> ProjectCostReport:
        """
        Calcula costos de múltiples eventos.
        """

        normalized_events = self._normalize_events(
            events
        )

        resolved_project_id = str(
            project_id
            or self._infer_project_id(
                normalized_events
            )
            or ""
        ).strip()

        report = ProjectCostReport(
            report_id=self._new_report_id(),
            generated_at=self._utc_now(),
            project_id=resolved_project_id,
            status=CostStatus.INVALID,
            scope=scope,
            currency=str(
                self.schema.get(
                    "currency",
                    "USD",
                )
                or "USD"
            ).upper(),
            metadata={
                "component": self.COMPONENT_NAME,
                "version": self.VERSION,
                "config_path": str(
                    self.config_path
                ),
                "events_received": len(
                    normalized_events
                ),
                "billing_tier_override": (
                    billing_tier or ""
                ),
                "billing_mode_override": (
                    billing_mode or ""
                ),
            },
        )

        for event in normalized_events:
            report.add_analysis(
                self.analyze_event(
                    event,
                    billing_tier=billing_tier,
                    billing_mode=billing_mode,
                )
            )

        if not normalized_events:
            report.warnings.append(
                "No existen eventos para calcular costos."
            )

        report.warnings = self._unique_strings(
            report.warnings
        )

        report.errors = self._unique_strings(
            report.errors
        )

        return report

    def resolve_pricing(
        self,
        *,
        provider: str,
        model: str,
        billing_tier: str,
        billing_mode: str,
        effective_date: date | datetime | str | None = None,
    ) -> dict[str, Any]:
        """
        Resuelve un bloque de tarifas.
        """

        resolved_provider = self._normalize_name(
            provider
        )

        resolved_model = str(
            model or ""
        ).strip()

        resolved_tier = self._normalize_name(
            billing_tier
        )

        resolved_mode = self._normalize_name(
            billing_mode
        )

        warnings: list[str] = []
        errors: list[str] = []

        provider_config = self._dict_value(
            self.providers.get(
                resolved_provider
            )
        )

        if not provider_config:
            return {
                "status": CostStatus.UNKNOWN_PRICING,
                "rates": {},
                "warnings": [
                    (
                        "Proveedor sin configuración de "
                        f"precios: {resolved_provider or '(vacío)'}."
                    )
                ],
                "errors": [],
                "resolved_provider": resolved_provider,
                "resolved_model": resolved_model,
                "resolved_tier": resolved_tier,
                "resolved_mode": resolved_mode,
                "pricing_enabled": False,
                "pricing_source": "",
            }

        models = self._dict_value(
            provider_config.get(
                "models"
            )
        )

        resolved_model_key = self._resolve_model_key(
            models=models,
            requested_model=resolved_model,
        )

        if not resolved_model_key:
            return {
                "status": CostStatus.UNKNOWN_PRICING,
                "rates": {},
                "warnings": [
                    (
                        "Modelo sin configuración de precios: "
                        f"{resolved_provider}/{resolved_model}."
                    )
                ],
                "errors": [],
                "resolved_provider": resolved_provider,
                "resolved_model": resolved_model,
                "resolved_tier": resolved_tier,
                "resolved_mode": resolved_mode,
                "pricing_enabled": bool(
                    provider_config.get(
                        "enabled",
                        False,
                    )
                ),
                "pricing_source": str(
                    provider_config.get(
                        "pricing_source",
                        "",
                    )
                ),
            }

        model_config = self._dict_value(
            models.get(
                resolved_model_key
            )
        )

        pricing_enabled = bool(
            provider_config.get(
                "enabled",
                False,
            )
            and model_config.get(
                "enabled",
                False,
            )
        )

        if not pricing_enabled:
            warnings.append(
                (
                    "La entrada de precios está deshabilitada "
                    f"para {resolved_provider}/"
                    f"{resolved_model_key}."
                )
            )

        tier_config = model_config.get(
            resolved_tier
        )

        if tier_config is None:
            return {
                "status": CostStatus.UNKNOWN_PRICING,
                "rates": {},
                "warnings": [
                    *warnings,
                    (
                        "Tier sin configuración de precios: "
                        f"{resolved_tier}."
                    ),
                ],
                "errors": [],
                "resolved_provider": resolved_provider,
                "resolved_model": resolved_model_key,
                "resolved_tier": resolved_tier,
                "resolved_mode": resolved_mode,
                "pricing_enabled": pricing_enabled,
                "pricing_source": str(
                    provider_config.get(
                        "pricing_source",
                        "",
                    )
                ),
            }

        if resolved_tier == "free_tier":
            rates = self._select_effective_rates(
                tier_config,
                effective_date=effective_date,
            )

            return {
                "status": CostStatus.FREE_TIER,
                "rates": rates,
                "warnings": warnings,
                "errors": errors,
                "resolved_provider": resolved_provider,
                "resolved_model": resolved_model_key,
                "resolved_tier": resolved_tier,
                "resolved_mode": resolved_mode,
                "pricing_enabled": pricing_enabled,
                "pricing_source": str(
                    provider_config.get(
                        "pricing_source",
                        "",
                    )
                ),
            }

        tier_dict = self._dict_value(
            tier_config
        )

        mode_config = tier_dict.get(
            resolved_mode
        )

        if mode_config is None:
            if self._looks_like_rate_block(
                tier_dict
            ):
                mode_config = tier_dict

            else:
                return {
                    "status": CostStatus.UNKNOWN_PRICING,
                    "rates": {},
                    "warnings": [
                        *warnings,
                        (
                            "Modo de facturación sin precios: "
                            f"{resolved_mode}."
                        ),
                    ],
                    "errors": errors,
                    "resolved_provider": resolved_provider,
                    "resolved_model": resolved_model_key,
                    "resolved_tier": resolved_tier,
                    "resolved_mode": resolved_mode,
                    "pricing_enabled": pricing_enabled,
                    "pricing_source": str(
                        provider_config.get(
                            "pricing_source",
                            "",
                        )
                    ),
                }

        rates = self._select_effective_rates(
            mode_config,
            effective_date=effective_date,
        )

        if not rates:
            return {
                "status": CostStatus.UNKNOWN_PRICING,
                "rates": {},
                "warnings": [
                    *warnings,
                    "No se encontró un bloque de tarifas vigente.",
                ],
                "errors": errors,
                "resolved_provider": resolved_provider,
                "resolved_model": resolved_model_key,
                "resolved_tier": resolved_tier,
                "resolved_mode": resolved_mode,
                "pricing_enabled": pricing_enabled,
                "pricing_source": str(
                    provider_config.get(
                        "pricing_source",
                        "",
                    )
                ),
            }

        return {
            "status": CostStatus.CALCULATED,
            "rates": rates,
            "warnings": warnings,
            "errors": errors,
            "resolved_provider": resolved_provider,
            "resolved_model": resolved_model_key,
            "resolved_tier": resolved_tier,
            "resolved_mode": resolved_mode,
            "pricing_enabled": pricing_enabled,
            "pricing_source": str(
                provider_config.get(
                    "pricing_source",
                    "",
                )
            ),
        }

    def get_component_info(
        self,
    ) -> dict[str, Any]:
        """
        Devuelve información pública.
        """

        return {
            "component": self.COMPONENT_NAME,
            "version": self.VERSION,
            "config_path": str(
                self.config_path
            ),
            "schema_version": str(
                self.schema.get(
                    "version",
                    "",
                )
            ),
            "currency": str(
                self.schema.get(
                    "currency",
                    "USD",
                )
            ),
            "token_unit": self._positive_int(
                self.schema.get(
                    "token_unit",
                    1_000_000,
                ),
                1_000_000,
            ),
            "providers": sorted(
                self.providers
            ),
            "reads_files": True,
            "writes_files": False,
            "uses_telemetry": True,
            "next_component": (
                "cost_analytics_smoke_test"
            ),
        }

    # --------------------------------------------------
    # Resolución de tarifas
    # --------------------------------------------------

    def _resolve_model_key(
        self,
        *,
        models: dict[str, Any],
        requested_model: str,
    ) -> str:
        """
        Resuelve nombre exacto o alias.
        """

        if requested_model in models:
            return requested_model

        normalized_requested = self._normalize_name(
            requested_model
        )

        for model_key, raw_config in models.items():
            if (
                self._normalize_name(
                    model_key
                )
                == normalized_requested
            ):
                return model_key

            model_config = self._dict_value(
                raw_config
            )

            aliases = model_config.get(
                "aliases",
                [],
            )

            if not isinstance(
                aliases,
                list,
            ):
                aliases = []

            if normalized_requested in {
                self._normalize_name(
                    alias
                )
                for alias in aliases
            }:
                return model_key

        return ""

    def _select_effective_rates(
        self,
        raw_rates: Any,
        *,
        effective_date: date | datetime | str | None,
    ) -> dict[str, Any]:
        """
        Selecciona tarifas simples o vigentes por fecha.
        """

        if isinstance(
            raw_rates,
            dict,
        ):
            return dict(
                raw_rates
            )

        if not isinstance(
            raw_rates,
            list,
        ):
            return {}

        target_date = self._resolve_date(
            effective_date
        )

        candidates: list[
            dict[str, Any]
        ] = []

        for item in raw_rates:
            if not isinstance(
                item,
                dict,
            ):
                continue

            start = self._parse_date(
                item.get(
                    "effective_from"
                )
            )

            end = self._parse_date(
                item.get(
                    "effective_until"
                )
            )

            if (
                start is not None
                and target_date < start
            ):
                continue

            if (
                end is not None
                and target_date > end
            ):
                continue

            candidates.append(
                item
            )

        if not candidates:
            return {}

        selected = max(
            candidates,
            key=lambda item: (
                self._parse_date(
                    item.get(
                        "effective_from"
                    )
                )
                or date.min
            ),
        )

        return {
            key: value
            for key, value in selected.items()
            if key not in {
                "effective_from",
                "effective_until",
            }
        }

    def _looks_like_rate_block(
        self,
        value: dict[str, Any],
    ) -> bool:
        """
        Detecta si el diccionario ya contiene tasas.
        """

        return any(
            key in value
            for key in {
                "input",
                "output",
                "thinking",
                "cached_input",
                "cache_write",
            }
        )

    def _missing_required_rates(
        self,
        *,
        token_usage: TokenUsageBreakdown,
        rates: dict[str, Any],
        billing_tier: str,
    ) -> bool:
        """
        Detecta tarifas faltantes para tokens usados.
        """

        if billing_tier == "free_tier":
            return False

        checks = (
            (
                token_usage.billable_input_tokens(),
                "input",
            ),
            (
                token_usage.response_tokens,
                "output",
            ),
            (
                token_usage.thinking_tokens,
                "thinking",
            ),
            (
                token_usage.cached_input_tokens,
                "cached_input",
            ),
            (
                token_usage.cache_write_tokens,
                "cache_write",
            ),
        )

        return any(
            tokens > 0
            and key not in rates
            for tokens, key in checks
        )

    # --------------------------------------------------
    # Normalización
    # --------------------------------------------------

    def _normalize_events(
        self,
        events: Iterable[
            TelemetryEvent | dict[str, Any]
        ],
    ) -> list[TelemetryEvent]:
        """
        Convierte diccionarios a TelemetryEvent.
        """

        normalized: list[TelemetryEvent] = []

        for event in events or []:
            if isinstance(
                event,
                TelemetryEvent,
            ):
                normalized.append(
                    event
                )

            elif isinstance(
                event,
                dict,
            ):
                data = {
                    key: value
                    for key, value in event.items()
                    if key
                    in TelemetryEvent.__dataclass_fields__
                }

                normalized.append(
                    TelemetryEvent(
                        **data
                    )
                )

        return normalized

    def _infer_project_id(
        self,
        events: list[TelemetryEvent],
    ) -> str:
        """
        Infiere el proyecto cuando todos coinciden.
        """

        project_ids = {
            event.project_id
            for event in events
            if event.project_id
        }

        if len(project_ids) == 1:
            return next(
                iter(
                    project_ids
                )
            )

        return ""

    def _token_cost(
        self,
        tokens: int,
        rate: float,
        token_unit: int,
    ) -> float:
        """
        Calcula costo por tokens.
        """

        if (
            tokens <= 0
            or rate <= 0
            or token_unit <= 0
        ):
            return 0.0

        return round(
            (
                tokens
                / token_unit
            )
            * rate,
            self._rounding_places(),
        )

    def _rate_value(
        self,
        rates: dict[str, Any],
        key: str,
        fallback: float = 0.0,
    ) -> float:
        """
        Obtiene una tasa segura.
        """

        if key not in rates:
            return self._non_negative_float(
                fallback
            )

        return self._non_negative_float(
            rates.get(
                key
            )
        )

    def _rounding_places(
        self,
    ) -> int:
        """
        Devuelve precisión configurada.
        """

        value = self._positive_int(
            self.defaults.get(
                "rounding_decimal_places",
                8,
            ),
            8,
        )

        return min(
            max(
                value,
                1,
            ),
            12,
        )

    def _first_int(
        self,
        metadata: dict[str, Any],
        keys: tuple[str, ...],
    ) -> int:
        """
        Devuelve el primer entero disponible.
        """

        for key in keys:
            if key in metadata:
                return self._non_negative_int(
                    metadata.get(
                        key
                    )
                )

        return 0

    def _first_float(
        self,
        metadata: dict[str, Any],
        keys: tuple[str, ...],
    ) -> float:
        """
        Devuelve el primer flotante disponible.
        """

        for key in keys:
            if key in metadata:
                return self._non_negative_float(
                    metadata.get(
                        key
                    )
                )

        return 0.0

    def _resolve_date(
        self,
        value: date | datetime | str | None,
    ) -> date:
        """
        Resuelve fecha efectiva.
        """

        if isinstance(
            value,
            datetime,
        ):
            return value.date()

        if isinstance(
            value,
            date,
        ):
            return value

        parsed = self._parse_date(
            value
        )

        return (
            parsed
            if parsed is not None
            else datetime.now(
                timezone.utc
            ).date()
        )

    def _parse_date(
        self,
        value: Any,
    ) -> date | None:
        """
        Convierte texto ISO a date.
        """

        text = str(
            value or ""
        ).strip()

        if not text:
            return None

        try:
            return date.fromisoformat(
                text
            )
        except ValueError:
            return None

    def _normalize_name(
        self,
        value: Any,
    ) -> str:
        """
        Normaliza nombres técnicos.
        """

        return str(
            value or ""
        ).strip().lower()

    def _dict_value(
        self,
        value: Any,
    ) -> dict[str, Any]:
        """
        Devuelve dict seguro.
        """

        return (
            dict(
                value
            )
            if isinstance(
                value,
                dict,
            )
            else {}
        )

    def _positive_int(
        self,
        value: Any,
        default: int,
    ) -> int:
        try:
            number = int(
                value
            )
        except (TypeError, ValueError):
            return default

        return (
            number
            if number > 0
            else default
        )

    def _non_negative_int(
        self,
        value: Any,
    ) -> int:
        try:
            number = int(
                value
            )
        except (TypeError, ValueError):
            return 0

        return max(
            number,
            0,
        )

    def _non_negative_float(
        self,
        value: Any,
    ) -> float:
        try:
            number = float(
                value
            )
        except (TypeError, ValueError):
            return 0.0

        return round(
            max(
                number,
                0.0,
            ),
            self._rounding_places(),
        )

    def _unique_strings(
        self,
        values: list[Any] | None,
    ) -> list[str]:
        """
        Elimina duplicados conservando orden.
        """

        result: list[str] = []

        for value in values or []:
            item = str(
                value or ""
            ).strip()

            if (
                item
                and item not in result
            ):
                result.append(
                    item
                )

        return result

    def _new_analysis_id(
        self,
    ) -> str:
        """
        Genera ID de análisis.
        """

        return (
            "COST-"
            + uuid4().hex.upper()
        )

    def _new_report_id(
        self,
    ) -> str:
        """
        Genera ID de reporte.
        """

        return (
            "COST-REPORT-"
            + uuid4().hex.upper()
        )

    def _utc_now(
        self,
    ) -> str:
        """
        Devuelve fecha UTC ISO-8601.
        """

        return (
            datetime.now(
                timezone.utc
            )
            .isoformat(
                timespec="milliseconds"
            )
            .replace(
                "+00:00",
                "Z",
            )
        )