from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from .models import (
    AudienceProfile,
    ContentPillar,
    KPI,
    RoadmapPhase,
    StrategicObjective,
    StrategyBuildResult,
    StrategyPackage,
    StrategyQualityScore,
)


class StrategyDirectorEngine:
    """Motor determinista para convertir evidencia validada en StrategyPackage.

    No inventa investigación. La evidencia debe llegar mediante ``research_findings``,
    ``evidence`` o ``insights``. Si únicamente existe un PromptPackage del Research
    Director, se conserva como referencia, pero no se trata como hallazgo confirmado.
    """

    version = "1.0.0"

    def build(self, payload: Mapping[str, Any]) -> StrategyBuildResult:
        topic = self._text(payload, "tema", "topic", "project_name")
        objective = self._text(payload, "objetivo", "business_objective", "objective")
        project_id = str(payload.get("project_id") or "project_unknown")
        evidence = self._evidence(payload)
        references = self._references(payload)
        audiences = self._audiences(payload)
        channels = self._strings(payload.get("channels")) or ("owned_media", "social_media")

        objectives = self._objectives(payload, objective)
        pillars = self._pillars(payload, topic, evidence)
        kpis = self._kpis(payload)
        roadmap = self._roadmap(payload)
        risks = self._strings(payload.get("risks")) or (
            "Decisiones basadas en evidencia insuficiente o desactualizada.",
            "Desalineación entre propuesta de valor, audiencia y canal.",
            "Métricas de vanidad sin relación con el objetivo de negocio.",
        )
        assumptions = self._strings(payload.get("assumptions")) or (
            "La evidencia suministrada fue revisada por el responsable del proyecto.",
            "Los objetivos y metas serán ajustados con datos operativos reales.",
        )

        value_proposition = self._text(payload, "value_proposition", "propuesta_valor") or (
            f"Ayudar a la audiencia prioritaria a avanzar en {topic} mediante una "
            "propuesta clara, verificable y orientada a resultados."
        )
        positioning = self._text(payload, "positioning", "posicionamiento") or (
            "Posicionamiento basado en utilidad práctica, credibilidad de las fuentes "
            "y consistencia de ejecución."
        )
        summary = (
            f"Estrategia para {topic}. Objetivo principal: {objective}. "
            f"Se estructura en {len(objectives)} objetivos, {len(pillars)} pilares, "
            f"{len(kpis)} KPI y un roadmap de {len(roadmap)} fases."
        )

        package = StrategyPackage(
            project_id=project_id,
            topic=topic,
            business_objective=objective,
            executive_summary=summary,
            objectives=objectives,
            audiences=audiences,
            value_proposition=value_proposition,
            positioning=positioning,
            content_pillars=pillars,
            channels=channels,
            kpis=kpis,
            roadmap=roadmap,
            risks=risks,
            assumptions=assumptions,
            evidence=evidence,
            source_references=references,
        )
        return StrategyBuildResult(package=package, score=self._score(package))

    def _score(self, package: StrategyPackage) -> StrategyQualityScore:
        completeness_items = [
            package.topic,
            package.business_objective,
            package.objectives,
            package.audiences,
            package.value_proposition,
            package.content_pillars,
            package.kpis,
            package.roadmap,
        ]
        completeness = 10.0 * sum(bool(item) for item in completeness_items) / len(completeness_items)
        evidence_coverage = min(10.0, len(package.evidence) * 2.0 + len(package.source_references))
        measurable = sum(bool(kpi.target.strip()) for kpi in package.kpis)
        measurability = 10.0 * measurable / max(1, len(package.kpis))
        warnings = []
        if not package.evidence:
            warnings.append("No se proporcionaron hallazgos de investigación; la estrategia es provisional.")
        if not package.source_references:
            warnings.append("No se proporcionaron referencias de fuentes para trazabilidad.")
        overall = round(completeness * 0.45 + evidence_coverage * 0.30 + measurability * 0.25, 2)
        return StrategyQualityScore(
            overall=overall,
            completeness=round(completeness, 2),
            evidence_coverage=round(evidence_coverage, 2),
            measurability=round(measurability, 2),
            warnings=tuple(warnings),
        )

    def _objectives(self, payload: Mapping[str, Any], objective: str) -> tuple[StrategicObjective, ...]:
        raw = payload.get("strategic_objectives") or payload.get("objectives")
        if isinstance(raw, Iterable) and not isinstance(raw, (str, bytes, Mapping)):
            parsed = []
            for index, item in enumerate(raw, 1):
                if isinstance(item, Mapping):
                    parsed.append(StrategicObjective(
                        name=str(item.get("name") or f"Objetivo {index}"),
                        outcome=str(item.get("outcome") or item.get("resultado") or objective),
                        metric=str(item.get("metric") or item.get("metrica") or "Indicador principal"),
                        target=str(item.get("target") or item.get("meta") or "Definir línea base y meta"),
                        horizon=str(item.get("horizon") or item.get("horizonte") or "90 días"),
                    ))
            if parsed:
                return tuple(parsed)
        return (
            StrategicObjective("Validar propuesta", objective, "Señales de validación", "3 señales verificables", "30 días"),
            StrategicObjective("Construir tracción", "Generar respuesta medible de la audiencia", "Conversión prioritaria", "Mejora contra línea base", "60 días"),
            StrategicObjective("Escalar ejecución", "Estandarizar lo que demuestre resultados", "Eficiencia por entrega", "Reducir retrabajo", "90 días"),
        )

    def _audiences(self, payload: Mapping[str, Any]) -> tuple[AudienceProfile, ...]:
        raw = payload.get("audiences") or payload.get("buyer_personas") or payload.get("audience")
        if isinstance(raw, str) and raw.strip():
            return (AudienceProfile(raw.strip(), f"Audiencia prioritaria para {raw.strip()}"),)
        if isinstance(raw, Iterable) and not isinstance(raw, (str, bytes, Mapping)):
            parsed = []
            for index, item in enumerate(raw, 1):
                if isinstance(item, Mapping):
                    parsed.append(AudienceProfile(
                        name=str(item.get("name") or f"Audiencia {index}"),
                        description=str(item.get("description") or item.get("descripcion") or ""),
                        needs=self._strings(item.get("needs") or item.get("necesidades")),
                        barriers=self._strings(item.get("barriers") or item.get("barreras")),
                        triggers=self._strings(item.get("triggers") or item.get("disparadores")),
                    ))
                elif str(item).strip():
                    parsed.append(AudienceProfile(str(item).strip(), "Segmento priorizado"))
            if parsed:
                return tuple(parsed)
        return (AudienceProfile("Audiencia prioritaria", "Segmento por validar con investigación de campo"),)

    def _pillars(self, payload: Mapping[str, Any], topic: str, evidence: tuple[str, ...]) -> tuple[ContentPillar, ...]:
        raw = payload.get("content_pillars") or payload.get("pilares")
        if isinstance(raw, Iterable) and not isinstance(raw, (str, bytes, Mapping)):
            parsed = []
            for index, item in enumerate(raw, 1):
                if isinstance(item, Mapping):
                    parsed.append(ContentPillar(
                        name=str(item.get("name") or f"Pilar {index}"),
                        purpose=str(item.get("purpose") or item.get("proposito") or ""),
                        themes=self._strings(item.get("themes") or item.get("temas")),
                        formats=self._strings(item.get("formats") or item.get("formatos")),
                    ))
            if parsed:
                return tuple(parsed)
        evidence_themes = evidence[:3] or (topic,)
        return (
            ContentPillar("Educación", "Resolver dudas y construir autoridad", evidence_themes, ("guía", "explicador", "caso")),
            ContentPillar("Confianza", "Demostrar evidencia, proceso y límites", ("fuentes", "metodología", "resultados"), ("comparativa", "checklist", "prueba")),
            ContentPillar("Conversión", "Conectar necesidad con siguiente acción", ("beneficio", "objeción", "llamada a la acción"), ("oferta", "demo", "testimonio")),
        )

    def _kpis(self, payload: Mapping[str, Any]) -> tuple[KPI, ...]:
        raw = payload.get("kpis")
        if isinstance(raw, Iterable) and not isinstance(raw, (str, bytes, Mapping)):
            parsed = []
            for index, item in enumerate(raw, 1):
                if isinstance(item, Mapping):
                    parsed.append(KPI(
                        name=str(item.get("name") or f"KPI {index}"),
                        definition=str(item.get("definition") or item.get("definicion") or ""),
                        cadence=str(item.get("cadence") or item.get("cadencia") or "semanal"),
                        target=str(item.get("target") or item.get("meta") or "Definir tras línea base"),
                    ))
            if parsed:
                return tuple(parsed)
        return (
            KPI("Conversión prioritaria", "Acciones objetivo / oportunidades calificadas", "semanal", "Mejorar contra línea base"),
            KPI("Retención de atención", "Consumo útil del contenido o experiencia", "semanal", "Tendencia positiva sostenida"),
            KPI("Eficiencia de producción", "Entregables aprobados / horas invertidas", "quincenal", "Reducir retrabajo"),
        )

    @staticmethod
    def _roadmap(payload: Mapping[str, Any]) -> tuple[RoadmapPhase, ...]:
        return (
            RoadmapPhase("Descubrimiento", "Días 1-30", ("Validar audiencia", "Confirmar problemas y lenguaje"), ("brief", "matriz de evidencia", "línea base")),
            RoadmapPhase("Validación", "Días 31-60", ("Probar propuesta y pilares", "Medir respuesta"), ("experimentos", "tablero KPI", "revisión de aprendizajes")),
            RoadmapPhase("Escalamiento", "Días 61-90", ("Estandarizar tácticas ganadoras", "Automatizar seguimiento"), ("playbook", "calendario", "criterios de optimización")),
        )

    def _evidence(self, payload: Mapping[str, Any]) -> tuple[str, ...]:
        values = []
        for key in ("research_findings", "evidence", "insights", "hallazgos"):
            values.extend(self._strings(payload.get(key)))
        return tuple(dict.fromkeys(values))

    def _references(self, payload: Mapping[str, Any]) -> tuple[str, ...]:
        values = list(self._strings(payload.get("source_references") or payload.get("sources") or payload.get("fuentes")))
        task_outputs = payload.get("task_outputs")
        if isinstance(task_outputs, Mapping):
            for output in task_outputs.values():
                if isinstance(output, Mapping) and output.get("package_id"):
                    values.append(f"upstream_package:{output['package_id']}")
        return tuple(dict.fromkeys(values))

    @staticmethod
    def _text(payload: Mapping[str, Any], *keys: str) -> str:
        for key in keys:
            value = payload.get(key)
            if value is not None and str(value).strip():
                return str(value).strip()
        return ""

    @staticmethod
    def _strings(value: Any) -> tuple[str, ...]:
        if value is None:
            return ()
        if isinstance(value, str):
            return (value.strip(),) if value.strip() else ()
        if isinstance(value, Mapping):
            return tuple(str(v).strip() for v in value.values() if str(v).strip())
        if isinstance(value, Iterable):
            return tuple(str(v).strip() for v in value if str(v).strip())
        text = str(value).strip()
        return (text,) if text else ()
