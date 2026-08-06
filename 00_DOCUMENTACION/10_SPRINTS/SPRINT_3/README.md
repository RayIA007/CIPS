# CIPS Sprint 3 — Strategy Director

Primer Director estratégico integrado al Core Orchestrator mediante la Adapter Layer.

## Componentes

- `strategy_director.models`: contrato `StrategyPackage` y modelos asociados.
- `strategy_director.engine`: motor determinista que convierte evidencia en estrategia.
- `cips_core.adapters.strategy`: `StrategyDirectorAdapter`.
- pruebas independientes y de integración Research → Strategy → Core.

## Principio de credibilidad

El Strategy Director **no confunde un prompt de investigación con resultados de investigación**. El Research Director actual produce un `PromptPackage`; por ello, Strategy requiere hallazgos reales en `research_findings`, `evidence`, `insights` o `hallazgos`. El `package_id` del Research Director se conserva como referencia de trazabilidad.

## Salida principal

`StrategyPackage` incluye resumen ejecutivo, objetivos, audiencias, propuesta de valor, posicionamiento, pilares, canales, KPI, roadmap, riesgos, supuestos, evidencia y referencias.

## Pruebas

```bat
python -m tests.test_strategy_adapter_smoke
python -m tests.test_core_strategy_integration_smoke
```
