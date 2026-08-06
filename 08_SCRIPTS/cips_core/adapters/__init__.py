"""Capa estándar de adaptadores de CIPS."""

from .base import BaseAgentAdapter
from .contracts import AdapterContext, AdapterRequest, AdapterResult, AdapterStatus
from .exceptions import (
    AdapterAlreadyRegisteredError,
    AdapterContractError,
    AdapterDisabledError,
    AdapterError,
    AdapterExecutionError,
    AdapterNotFoundError,
    AdapterValidationError,
)
from .registry import AdapterRegistry
from .research import ResearchAdapterConfig, ResearchDirectorAdapter
from .strategy import StrategyAdapterConfig, StrategyDirectorAdapter

__all__ = [
    "BaseAgentAdapter",
    "AdapterContext",
    "AdapterRequest",
    "AdapterResult",
    "AdapterStatus",
    "AdapterRegistry",
    "ResearchAdapterConfig",
    "ResearchDirectorAdapter",
    "StrategyAdapterConfig",
    "StrategyDirectorAdapter",
    "AdapterError",
    "AdapterContractError",
    "AdapterValidationError",
    "AdapterExecutionError",
    "AdapterNotFoundError",
    "AdapterAlreadyRegisteredError",
    "AdapterDisabledError",
]
