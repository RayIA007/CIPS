# CIPS Sprint 4A — Dominio del Content Director

Este entregable define el contrato de datos del Content Director sin introducir todavía motor, adaptador ni cambios al Core Orchestrator.

## Objetos principales

- `ContentBrief`
- `ContentObjective`
- `AudienceSegment`
- `ContentPillar`
- `ChannelPlan`
- `ContentPiece`
- `EditorialCalendar` y `EditorialSlot`
- `CallToAction`, `SEOBrief` y `ContentMetricsTarget`
- `ContentPackage`
- `ContentQualityScore` y `ContentBuildResult`

## Garantías

- Modelos inmutables mediante `dataclass(frozen=True, slots=True)`.
- IDs únicos y prefijados para trazabilidad.
- Enumeraciones estables para formato, intención, estado, CTA y cadencia.
- Serialización a estructuras compatibles con JSON.
- Validación de referencias cruzadas entre objetivos, audiencias, pilares, canales, piezas y calendario.
- Validación de fechas, estados y consistencia editorial.
- Conversión inicial desde un `StrategyPackage` serializado mediante `ContentBrief.from_strategy_dict()`.

## Alcance deliberado

Sprint 4A no genera contenido. El motor de generación y scoring se implementará en Sprint 4B usando estos contratos.
