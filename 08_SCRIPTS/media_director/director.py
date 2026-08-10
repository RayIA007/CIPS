from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .models import MediaRequest, MediaResult, MediaWorkPackage
from .strategy import MediaStrategy


ProviderExecutor = Callable[[MediaWorkPackage], Any]


class MediaDirector:
    """
    Algoritmo común de F5 para solicitudes multimedia.

    La selección/ejecución concreta del provider se inyecta como callable para
    mantener esta capa independiente de SDKs y de la implementación F4.
    StageExecutor/PipelineEngine no se invocan aquí; el post-proceso se conserva
    como especificación declarativa para una capa externa posterior.
    """

    def __init__(self, strategy: MediaStrategy) -> None:
        if not isinstance(strategy, MediaStrategy):
            raise TypeError("strategy debe ser MediaStrategy.")
        self.strategy = strategy

    def prepare(self, request: MediaRequest) -> MediaWorkPackage:
        """Valida la entrada y crea el paquete provider-agnostic."""
        return self.strategy.build_work_package(request)

    def execute(
        self,
        request: MediaRequest,
        *,
        provider_executor: ProviderExecutor,
    ) -> MediaResult:
        """
        Ejecuta una única llamada a la frontera provider inyectada.

        No aplica retry, no persiste artifacts y no ejecuta post-proceso.
        Esas responsabilidades permanecen en sus capas propietarias.
        """
        if not callable(provider_executor):
            raise TypeError("provider_executor debe ser invocable.")

        work_package = self.prepare(request)
        raw_output = provider_executor(work_package)
        normalized_output = self.strategy.normalize_provider_result(
            raw_output,
            work_package=work_package,
        )
        self.strategy.validate_result(
            normalized_output,
            work_package=work_package,
        )

        return MediaResult(
            request_id=work_package.request_id,
            strategy_name=work_package.strategy_name,
            media_type=work_package.media_type,
            capability=work_package.capability,
            output_format=work_package.output_format,
            output=normalized_output,
            post_process_chain=work_package.post_process_chain,
            metadata=work_package.metadata,
        )


__all__ = ["ProviderExecutor", "MediaDirector"]
