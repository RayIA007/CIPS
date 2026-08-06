from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Callable, Optional
from .errors import AgentNotFoundError, DuplicateAgentError
from .utils import generate_id, utc_now_iso

AgentHandler = Callable[[dict[str, Any]], Any]

@dataclass(slots=True)
class AgentDescriptor:
    name: str
    handler: AgentHandler
    capabilities: set[str]
    agent_id: str = field(default_factory=lambda: generate_id("agent"))
    version: str = "1.0.0"
    enabled: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)
    registered_at: str = field(default_factory=utc_now_iso)

    def __post_init__(self):
        self.name = self.name.strip()
        self.capabilities = {x.strip() for x in self.capabilities if x.strip()}
        if not self.name:
            raise ValueError("El nombre del agente es obligatorio.")
        if not callable(self.handler):
            raise TypeError("handler debe ser invocable.")
        if not self.capabilities:
            raise ValueError("El agente requiere al menos una capacidad.")

class AgentRegistry:
    def __init__(self):
        self._agents: dict[str, AgentDescriptor] = {}

    def register(self, descriptor: AgentDescriptor, *, replace: bool = False):
        if descriptor.name in self._agents and not replace:
            raise DuplicateAgentError(descriptor.name)
        if replace:
            for name, current in list(self._agents.items()):
                if name == descriptor.name:
                    del self._agents[name]
        self._agents[descriptor.name] = descriptor
        return descriptor

    def unregister(self, name: str) -> AgentDescriptor:
        if name not in self._agents:
            raise AgentNotFoundError(name)
        return self._agents.pop(name)

    def get(self, name):
        if name not in self._agents:
            raise AgentNotFoundError(name)
        return self._agents[name]

    def resolve(self, *, agent_name: Optional[str] = None, capability: Optional[str] = None):
        if agent_name:
            agent = self.get(agent_name)
            if not agent.enabled or (capability and capability not in agent.capabilities):
                raise AgentNotFoundError(agent_name)
            return agent
        if capability:
            for agent in self._agents.values():
                if agent.enabled and capability in agent.capabilities:
                    return agent
        raise AgentNotFoundError(capability or agent_name or "agente")

    def list_agents(self):
        return sorted(self._agents.values(), key=lambda x: x.name)
