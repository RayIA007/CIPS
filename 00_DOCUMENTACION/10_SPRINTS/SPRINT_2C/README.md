# CIPS Sprint 2 — Entregable C: Integración con el Core Orchestrator

Este entregable conecta el `AdapterRegistry` con el `AgentRegistry` y permite que un workflow ejecute automáticamente el `ResearchDirectorAdapter` mediante su capacidad `research`.

## Flujo operativo

```text
CIPSOrchestrator
    ↓ register_adapter(...)
AdapterAgentBridge
    ├─ AdapterRegistry
    └─ AgentRegistry
           ↓
WorkflowEngine
           ↓ capability="research"
ResearchDirectorAdapter
           ↓
AdvancedResearchPromptEngine
           ↓
AdapterResult
           ↓
TaskResult + ExecutionContext + MessageBus + Checkpoint
```

## Archivos

```text
cips_core/__init__.py
cips_core/agents.py
cips_core/engine.py
cips_core/facade.py
cips_core/integration.py
cips_core/tasks.py
tests/test_core_research_integration_smoke.py
```

## API añadida

```python
orchestrator.register_adapter(ResearchDirectorAdapter())
```

El adaptador queda registrado simultáneamente por nombre y por capacidad. Una tarea con `capability="research"` puede omitir `agent_name`.

## Resultados enriquecidos

`TaskResult` incorpora:

- `adapter_result`: resumen serializable de la ejecución;
- `metrics`;
- `warnings`;
- `artifacts`;
- `output`: salida normalizada del adaptador.

Los resultados se guardan en `ExecutionContext`, se publican en `MessageBus` y son compatibles con `InMemoryCheckpointStore`.
