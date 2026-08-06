# CIPS Sprint 2 — Entregable B: Research Adapter

Este entregable añade el primer adaptador de producción de CIPS:
`ResearchDirectorAdapter`.

## Flujo implementado

```text
Payload del Core Orchestrator
        ↓
AdapterRequest
        ↓
ResearchDirectorAdapter
        ↓
AdvancedResearchPromptEngine
        ↓
AdvancedPromptResult / PromptPackage
        ↓
AdapterResult
```

## Archivos instalados

```text
cips_core/adapters/__init__.py      (actualizado)
cips_core/adapters/research.py      (nuevo)
tests/test_research_adapter_smoke.py
```

## Requisitos previos

Deben estar instalados y validados:

1. Research Prompt Builder refactorizado.
2. Core Orchestrator Sprint 1.
3. Adapter Framework Sprint 2A.

## Instalación

Extrae el contenido interno del ZIP directamente en:

```text
C:\ConsejoIA_V5\08_SCRIPTS
```

Autoriza combinar carpetas y reemplaza `cips_core\adapters\__init__.py`.
No se reemplazan `engine.py`, `agents.py` ni el paquete `research_prompt`.

## Validación

```bat
python -m tests.test_research_adapter_smoke
```

El test usa el Research Prompt Builder real; no emplea un agente simulado.
