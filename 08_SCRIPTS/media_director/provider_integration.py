from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol

from .models import MediaWorkPackage


class CapabilityResolverLike(Protocol):
    """Contrato mínimo que F5 consume de ``CapabilityResolver`` de F4."""

    def resolve(
        self,
        capability: str,
        *,
        preferred_provider: str | None = None,
    ) -> Any:
        """Devuelve el provider seleccionado para una capability."""


ProviderInvoker = Callable[[Any, MediaWorkPackage], Any]


class CapabilityProviderExecutor:
    """
    Conecta el ``MediaDirector`` de F5 con la selección de providers de F4.

    Responsabilidades:
    - pedir al resolver exactamente un provider para la capability solicitada;
    - respetar ``preferred_provider`` cuando venga declarado;
    - delegar exactamente una invocación al callable ``provider_invoker``.

    No implementa retry, failover, persistencia, post-proceso ni llamadas a SDKs.
    La forma concreta de invocar al provider se mantiene fuera de esta clase para
    reutilizar los adapters/fakes existentes de F4 sin duplicar sus contratos.
    """

    def __init__(
        self,
        resolver: CapabilityResolverLike,
        *,
        provider_invoker: ProviderInvoker,
    ) -> None:
        resolve = getattr(resolver, "resolve", None)
        if not callable(resolve):
            raise TypeError("resolver debe exponer resolve(...).")
        if not callable(provider_invoker):
            raise TypeError("provider_invoker debe ser invocable.")

        self._resolver = resolver
        self._provider_invoker = provider_invoker

    @property
    def resolver(self) -> CapabilityResolverLike:
        return self._resolver

    @property
    def provider_invoker(self) -> ProviderInvoker:
        return self._provider_invoker

    def __call__(self, work_package: MediaWorkPackage) -> Any:
        if not isinstance(work_package, MediaWorkPackage):
            raise TypeError("work_package debe ser MediaWorkPackage.")

        provider = self._resolver.resolve(
            work_package.capability,
            preferred_provider=work_package.preferred_provider,
        )
        return self._provider_invoker(provider, work_package)


__all__ = [
    "CapabilityResolverLike",
    "ProviderInvoker",
    "CapabilityProviderExecutor",
]
