# CHANGELOG

## Sprint 2B — Research Adapter 1.0.0

### Añadido

- `ResearchDirectorAdapter` como primer adaptador real de CIPS.
- `ResearchAdapterConfig` para presupuesto de tokens y optimización.
- traducción de payload del Orchestrator a entrada del Research Builder;
- validación de tema y objetivo;
- ejecución perezosa de `AdvancedResearchPromptEngine`;
- normalización de `PromptPackage` a `AdapterResult`;
- métricas de score, tokens, diagnósticos y auditoría;
- descriptor de artefacto `prompt_package`;
- smoke test contra el Research Prompt Builder real.

### No modificado

- `cips_core/engine.py`;
- `cips_core/agents.py`;
- `cips_core/facade.py`;
- paquete `research_prompt/`.

La conexión automática con `AgentRegistry` y `CIPSOrchestrator` corresponde al
Entregable C.
