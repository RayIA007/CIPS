"""Deterministic, charge-safe provider selection for PM8."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Mapping

from capability_resolver import (
    CapabilityNotAvailableError,
    CapabilityResolver,
    PreferredProviderUnavailableError,
)
from media_provider import MediaProvider, MediaRequest, normalize_capability
from production_manifest import CostHint, QualityHint

from .errors import AssetProviderSelectionError


_QUALITY_RANK = {
    QualityHint.DRAFT.value: 0,
    QualityHint.STANDARD.value: 1,
    QualityHint.HIGH.value: 2,
}
_COST_RANK = {
    CostHint.FREE.value: 0,
    CostHint.LOW.value: 1,
    CostHint.BALANCED.value: 2,
    CostHint.PREMIUM.value: 3,
}
_SAFE_METADATA_KEYS = frozenset(
    {
        "available",
        "cost_tier",
        "free_tier",
        "license",
        "local",
        "priority",
        "quality_tier",
        "source",
    }
)


@dataclass(frozen=True, slots=True)
class ProviderSelection:
    provider: MediaProvider
    capability: str
    estimated_cost_usd: float | None
    cost_tier: str
    quality_tier: str
    metadata: Mapping[str, Any]


class AssetProviderPolicy:
    """Rank F4 candidates by declared availability, cost and quality.

    Paid or unknown-cost execution is disabled by default.  This is an
    operational guardrail: a manifest may request premium quality, but it can
    never authorize billing by itself.
    """

    def __init__(
        self,
        resolver: CapabilityResolver,
        *,
        allow_paid: bool = False,
        allow_unknown_cost: bool = False,
    ) -> None:
        if not isinstance(resolver, CapabilityResolver):
            raise TypeError("resolver debe ser CapabilityResolver.")
        self._resolver = resolver
        self.allow_paid = bool(allow_paid)
        self.allow_unknown_cost = bool(allow_unknown_cost)

    @property
    def resolver(self) -> CapabilityResolver:
        return self._resolver

    def select(
        self,
        request: MediaRequest,
        *,
        quality_hint: QualityHint,
        cost_hint: CostHint,
        preferred_provider: str | None = None,
    ) -> ProviderSelection:
        if not isinstance(request, MediaRequest):
            raise TypeError("request debe ser media_provider.MediaRequest.")
        capability = normalize_capability(request.capability)
        quality = QualityHint(quality_hint)
        cost = CostHint(cost_hint)

        try:
            if preferred_provider is not None:
                candidates = [
                    self._resolver.resolve(
                        capability,
                        preferred_provider=preferred_provider,
                    )
                ]
            else:
                candidates = self._resolver.candidates(capability)
        except (
            CapabilityNotAvailableError,
            PreferredProviderUnavailableError,
        ) as error:
            raise AssetProviderSelectionError(str(error)) from error
        if not candidates:
            raise AssetProviderSelectionError(
                f"No hay providers habilitados para '{capability}'."
            )

        accepted: list[tuple[tuple[Any, ...], ProviderSelection]] = []
        rejected: list[str] = []
        for provider in candidates:
            selection, reason = self._evaluate(
                provider,
                request=request,
                capability=capability,
                quality_hint=quality,
                cost_hint=cost,
            )
            if selection is None:
                rejected.append(f"{provider.provider_name}:{reason}")
                continue
            accepted.append((self._rank(selection, quality, cost), selection))

        if not accepted:
            details = ", ".join(sorted(rejected)) or "sin candidatos"
            raise AssetProviderSelectionError(
                f"Ningún provider satisface la política para '{capability}': {details}."
            )
        accepted.sort(key=lambda item: item[0])
        return accepted[0][1]

    def _evaluate(
        self,
        provider: MediaProvider,
        *,
        request: MediaRequest,
        capability: str,
        quality_hint: QualityHint,
        cost_hint: CostHint,
    ) -> tuple[ProviderSelection | None, str]:
        declared = {
            normalize_capability(name): metadata
            for name, metadata in provider.capabilities().items()
        }
        raw_metadata = declared.get(capability, {})
        if raw_metadata is None:
            raw_metadata = {}
        if not isinstance(raw_metadata, Mapping):
            return None, "metadata_invalida"
        metadata = dict(raw_metadata)
        if metadata.get("available", True) is not True:
            return None, "no_disponible"

        quality_tier = str(metadata.get("quality_tier", "draft")).strip().lower()
        cost_tier = str(metadata.get("cost_tier", "unknown")).strip().lower()
        if quality_tier not in _QUALITY_RANK:
            return None, "quality_tier_desconocido"
        if cost_tier not in _COST_RANK and cost_tier != "unknown":
            return None, "cost_tier_desconocido"
        if _QUALITY_RANK[quality_tier] < _QUALITY_RANK[quality_hint.value]:
            return None, "calidad_insuficiente"
        if cost_tier in _COST_RANK and _COST_RANK[cost_tier] > _COST_RANK[cost_hint.value]:
            return None, "costo_fuera_de_hint"

        estimated = provider.estimate_cost(request)
        if estimated is not None:
            if isinstance(estimated, bool) or not isinstance(estimated, (int, float)):
                return None, "estimacion_invalida"
            estimated = float(estimated)
            if estimated < 0.0:
                return None, "estimacion_negativa"

        explicitly_free = (
            cost_tier == CostHint.FREE.value
            or metadata.get("free_tier") is True
            or estimated == 0.0
        )
        if not self.allow_paid and not explicitly_free:
            return None, "pago_no_autorizado"
        if estimated is None and not explicitly_free and not self.allow_unknown_cost:
            return None, "costo_desconocido"

        safe_metadata = {
            str(key): value
            for key, value in metadata.items()
            if str(key) in _SAFE_METADATA_KEYS
            and (value is None or isinstance(value, (str, int, float, bool)))
        }
        if explicitly_free and cost_tier == "unknown":
            cost_tier = CostHint.FREE.value
        return (
            ProviderSelection(
                provider=provider,
                capability=capability,
                estimated_cost_usd=estimated,
                cost_tier=cost_tier,
                quality_tier=quality_tier,
                metadata=safe_metadata,
            ),
            "",
        )

    @staticmethod
    def _rank(
        selection: ProviderSelection,
        quality_hint: QualityHint,
        cost_hint: CostHint,
    ) -> tuple[Any, ...]:
        quality_rank = _QUALITY_RANK[selection.quality_tier]
        cost_rank = _COST_RANK.get(selection.cost_tier, 99)
        estimate = (
            selection.estimated_cost_usd
            if selection.estimated_cost_usd is not None
            else float("inf")
        )
        priority = selection.metadata.get("priority", 100)
        if (
            isinstance(priority, bool)
            or not isinstance(priority, (int, float))
            or not math.isfinite(float(priority))
        ):
            priority = 100
        if quality_hint is QualityHint.HIGH or cost_hint in {
            CostHint.BALANCED,
            CostHint.PREMIUM,
        }:
            return (-quality_rank, cost_rank, estimate, float(priority), selection.provider.provider_name)
        return (cost_rank, -quality_rank, estimate, float(priority), selection.provider.provider_name)


__all__ = ["AssetProviderPolicy", "ProviderSelection"]
