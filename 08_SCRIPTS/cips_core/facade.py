from __future__ import annotations
from .agents import AgentDescriptor, AgentRegistry
from .adapters import AdapterRegistry, BaseAgentAdapter
from .checkpoints import InMemoryCheckpointStore
from .engine import WorkflowEngine
from .integration import AdapterAgentBridge
from .messages import MessageBus
from .tasks import WorkflowDefinition

class CIPSOrchestrator:
    def __init__(self,*,registry=None,adapter_registry=None,message_bus=None,checkpoint_store=None):
        self.registry=registry or AgentRegistry()
        self.adapter_registry=adapter_registry or AdapterRegistry()
        self.message_bus=message_bus or MessageBus()
        self.checkpoint_store=checkpoint_store or InMemoryCheckpointStore()
        self.adapter_bridge=AdapterAgentBridge(self.registry,self.adapter_registry)
        self.engine=WorkflowEngine(self.registry,message_bus=self.message_bus,checkpoint_store=self.checkpoint_store)

    def register_agent(self,*,name,handler,capabilities,version="1.0.0",metadata=None,replace=False):
        return self.registry.register(AgentDescriptor(name,handler,set(capabilities),version=version,metadata=dict(metadata or {})),replace=replace)

    def register_adapter(self,adapter:BaseAgentAdapter,*,replace=False):
        """Registra un adaptador como agente ejecutable del Orchestrator."""
        return self.adapter_bridge.register(adapter,replace=replace)

    def create_workflow(self,*,name,tasks,version="1.0.0",metadata=None):
        return WorkflowDefinition(name,tasks,version=version,metadata=dict(metadata or {}))

    def run(self,workflow,*,project_id,initial_data=None,metadata=None):
        return self.engine.run(workflow,project_id=project_id,initial_data=initial_data,metadata=metadata)
