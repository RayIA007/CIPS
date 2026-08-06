"""Integración entre AdapterRegistry y AgentRegistry."""
from __future__ import annotations

from typing import Iterable

from .agents import AgentDescriptor, AgentRegistry
from .adapters import AdapterRegistry, BaseAgentAdapter


class AdapterAgentBridge:
    """Publica adaptadores como agentes ejecutables del Core Orchestrator."""

    def __init__(self, agent_registry: AgentRegistry, adapter_registry: AdapterRegistry):
        self.agent_registry = agent_registry
        self.adapter_registry = adapter_registry

    def register(
        self,
        adapter: BaseAgentAdapter,
        *,
        replace: bool = False,
    ) -> AgentDescriptor:
        """Registra el adaptador y crea su descriptor compatible con el Core."""
        self.adapter_registry.register(adapter, replace=replace)

        descriptor = AgentDescriptor(
            name=adapter.adapter_name,
            handler=adapter,
            capabilities={adapter.capability},
            version=adapter.version,
            enabled=adapter.enabled,
            metadata=adapter.descriptor_metadata(),
        )
        self.agent_registry.register(descriptor, replace=replace)
        return descriptor

    def register_many(
        self,
        adapters: Iterable[BaseAgentAdapter],
        *,
        replace: bool = False,
    ) -> list[AgentDescriptor]:
        return [self.register(adapter, replace=replace) for adapter in adapters]

    def resolve_adapter(self, *, capability: str) -> BaseAgentAdapter:
        return self.adapter_registry.resolve(capability=capability)
