# CHANGELOG — Sprint 2C

## Añadido

- `AdapterAgentBridge`.
- `CIPSOrchestrator.register_adapter()`.
- registro coordinado en `AdapterRegistry` y `AgentRegistry`.
- resolución automática de tareas por `capability`.
- evento `adapter.succeeded` en `MessageBus`.
- métricas, advertencias y artefactos en `TaskResult`.
- conversión recursiva a estructuras serializables para checkpoints.
- smoke test de integración real.

## Compatibilidad

- los agentes tradicionales siguen usando `register_agent()`;
- el smoke test original del Core continúa operativo;
- no se modifica el Research Prompt Builder;
- no se modifica el Research Director Adapter del Sprint 2B.
