"""Normalización, expansión y resolución del contexto."""
from __future__ import annotations

from dataclasses import asdict, is_dataclass
import json
import re
from typing import Any, Mapping, Optional, Sequence

try:
    from research_director_models import (
        ResearchConfiguration,
        ResearchConstraint,
        ResearchObjective,
        ResearchPriority,
        ResearchQuestion,
        generate_id,
        utc_now_iso,
    )
except ImportError:  # pragma: no cover
    from ..research_director_models import (
        ResearchConfiguration,
        ResearchConstraint,
        ResearchObjective,
        ResearchPriority,
        ResearchQuestion,
        generate_id,
        utc_now_iso,
    )

from .advanced_common import _constraint, _get, _key, _list, _objective, _question
from .builder import ResearchMethodSelector, ResearchPromptProfile
from .common import DEFAULT_PROMPT_LANGUAGE, ResearchPromptValidationError, normalize_string_list, normalize_text
from .contracts import ResearchPromptValidator
from .models import PromptBuildContext

class ContextNormalizer:
    """Convierte dict, JSON, Markdown, dataclass, lista o texto a PromptBuildContext."""

    ALIASES = {
        "project_id": ("project_id", "project", "proyecto_id", "proyecto", "id"),
        "topic": ("topic", "tema", "subject", "asunto"),
        "objective": ("objective", "objetivo", "goal", "meta", "purpose"),
        "audience": ("audience", "audiencia", "publico", "público"),
        "content_format": ("content_format", "format", "formato"),
        "platform": ("platform", "plataforma", "channel", "canal"),
        "language": ("language", "idioma", "lang"),
        "jurisdiction": ("jurisdiction", "jurisdiccion", "jurisdicción"),
        "deadline": ("deadline", "fecha_limite", "fecha_límite"),
        "questions": ("questions", "preguntas", "research_questions"),
        "objectives": ("objectives", "objetivos", "research_objectives"),
        "constraints": ("constraints", "restricciones", "limitaciones"),
        "exclusions": ("exclusions", "exclusiones", "exclude"),
        "mandatory_outputs": ("mandatory_outputs", "outputs", "entregables"),
        "human_notes": ("human_notes", "notes", "notas"),
        "additional_context": ("additional_context", "context", "contexto"),
    }

    @classmethod
    def normalize(cls, value: Any, *, configuration: Optional[ResearchConfiguration] = None,
                  default_project_id: Optional[str] = None,
                  language: str = DEFAULT_PROMPT_LANGUAGE) -> PromptBuildContext:
        if isinstance(value, PromptBuildContext):
            return value
        if isinstance(value, str):
            data = cls._parse_text(value)
        elif isinstance(value, Mapping):
            data = dict(value)
        elif is_dataclass(value):
            data = asdict(value)
        elif hasattr(value, "to_dict"):
            data = dict(value.to_dict())
        elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
            items = list(value)
            if not items:
                raise ResearchPromptValidationError("La entrada no puede estar vacía.")
            data = {"topic": str(items[0]), "objective": str(items[1] if len(items) > 1 else items[0]),
                    "additional_context": {"remaining_items": items[2:]}}
        else:
            raise ResearchPromptValidationError("Tipo de entrada no compatible.")

        canonical = cls._canonical(data)
        context = PromptBuildContext(
            project_id=normalize_text(canonical.get("project_id") or default_project_id or generate_id("project"), required=True),
            topic=normalize_text(canonical.get("topic"), field_name="topic", required=True),
            objective=normalize_text(canonical.get("objective"), field_name="objective", required=True),
            audience=normalize_text(canonical.get("audience")),
            content_format=normalize_text(canonical.get("content_format")),
            platform=normalize_text(canonical.get("platform")),
            language=normalize_text(canonical.get("language") or language, required=True),
            jurisdiction=normalize_string_list(_list(canonical.get("jurisdiction"))),
            deadline=normalize_text(canonical.get("deadline")),
            objectives=cls._objectives(canonical.get("objectives")),
            questions=cls._questions(canonical.get("questions")),
            constraints=cls._constraints(canonical.get("constraints")),
            exclusions=normalize_string_list(_list(canonical.get("exclusions"))),
            mandatory_outputs=normalize_string_list(_list(canonical.get("mandatory_outputs"))),
            human_notes=normalize_string_list(_list(canonical.get("human_notes"))),
            additional_context=canonical.get("additional_context") if isinstance(canonical.get("additional_context"), Mapping) else {},
            configuration=configuration or ResearchConfiguration(),
            metadata={"normalized_by": cls.__name__, "source_type": type(value).__name__, "normalized_at": utc_now_iso()},
        )
        ResearchPromptValidator.validate_context(context)
        return context

    @classmethod
    def _canonical(cls, data: Mapping[str, Any]) -> dict[str, Any]:
        src = {_key(k).replace(" ", "_"): v for k, v in data.items()}
        out: dict[str, Any] = {}
        all_aliases: set[str] = set()
        for canonical, aliases in cls.ALIASES.items():
            for alias in aliases:
                token = _key(alias).replace(" ", "_")
                all_aliases.add(token)
                if token in src and canonical not in out:
                    out[canonical] = src[token]
        extras = {k: v for k, v in src.items() if k not in all_aliases}
        if extras:
            current = out.get("additional_context")
            merged = dict(current) if isinstance(current, Mapping) else {}
            merged.update(extras)
            out["additional_context"] = merged
        return out

    @staticmethod
    def _parse_text(text: str) -> dict[str, Any]:
        text = normalize_text(text, required=True)
        try:
            parsed = json.loads(text)
            if isinstance(parsed, Mapping):
                return dict(parsed)
        except json.JSONDecodeError:
            pass
        data: dict[str, Any] = {}
        for line in text.splitlines():
            match = re.match(r"^\s*#{0,6}\s*([\wÁÉÍÓÚÜÑáéíóúüñ ]{2,40})\s*:\s*(.+)$", line)
            if match:
                data[match.group(1).strip()] = match.group(2).strip()
        if not data:
            first = re.split(r"(?<=[.!?])\s+", text)[0]
            data = {"topic": first[:250], "objective": text}
        data.setdefault("topic", next(iter(data.values())))
        data.setdefault("objective", text)
        return data

    @staticmethod
    def _questions(value: Any) -> list[ResearchQuestion]:
        result: list[ResearchQuestion] = []
        seen: set[str] = set()
        for item in _list(value):
            if isinstance(item, ResearchQuestion):
                obj = item
            elif isinstance(item, Mapping):
                text = normalize_text(_get(item, "question", "text", "statement", default=""))
                if not text:
                    continue
                obj = _question(text)
            else:
                text = normalize_text(item)
                if not text:
                    continue
                obj = _question(text)
            token = _key(obj.question)
            if token not in seen:
                seen.add(token)
                result.append(obj)
        return result

    @staticmethod
    def _objectives(value: Any) -> list[ResearchObjective]:
        result: list[ResearchObjective] = []
        seen: set[str] = set()
        for item in _list(value):
            if isinstance(item, ResearchObjective):
                obj = item
            elif isinstance(item, Mapping):
                text = normalize_text(_get(item, "statement", "objective", "text", default=""))
                if not text:
                    continue
                obj = _objective(text)
            else:
                text = normalize_text(item)
                if not text:
                    continue
                obj = _objective(text)
            token = _key(obj.statement)
            if token not in seen:
                seen.add(token)
                result.append(obj)
        return result

    @staticmethod
    def _constraints(value: Any) -> list[ResearchConstraint]:
        result: list[ResearchConstraint] = []
        for item in _list(value):
            if isinstance(item, ResearchConstraint):
                result.append(item)
            elif isinstance(item, Mapping):
                text = normalize_text(_get(item, "description", "constraint", "text", default=""))
                if text:
                    result.append(_constraint(text, normalize_text(_get(item, "category", default="general")) or "general", bool(_get(item, "mandatory", default=True))))
            else:
                text = normalize_text(item)
                if text:
                    result.append(_constraint(text))
        return result


class ResearchQuestionExpander:
    GENERAL = (
        ("¿Cuáles son los hechos principales verificables sobre {topic}?", "Establecer la base factual."),
        ("¿Qué fuentes primarias y autoritativas existen sobre {topic}?", "Priorizar evidencia confiable."),
        ("¿Qué contradicciones, riesgos y vacíos relevantes existen?", "Controlar incertidumbre."),
    )
    PROFILE = {
        ResearchPromptProfile.LEGAL: (
            ("¿Qué leyes, reglamentos o normas vigentes regulan {topic}?", "Definir el marco jurídico."),
            ("¿Qué jurisdicción, autoridad y fecha de vigencia aplican?", "Controlar alcance legal."),
        ),
        ResearchPromptProfile.TECHNICAL: (
            ("¿Cómo funciona técnicamente {topic} y cuáles son sus dependencias?", "Comprender la arquitectura."),
            ("¿Qué documentación oficial, estándares y riesgos técnicos aplican?", "Validar implementación."),
        ),
        ResearchPromptProfile.SCIENTIFIC: (
            ("¿Cuál es el estado de la evidencia científica sobre {topic}?", "Sintetizar conocimiento."),
            ("¿Qué calidad metodológica y riesgo de sesgo presentan los estudios?", "Jerarquizar evidencia."),
        ),
        ResearchPromptProfile.MARKET: (
            ("¿Cuál es el tamaño, crecimiento y estructura del mercado de {topic}?", "Cuantificar oportunidad."),
            ("¿Qué segmentos, barreras y oportunidades comerciales existen?", "Mapear demanda."),
        ),
        ResearchPromptProfile.COMPETITOR: (
            ("¿Quiénes son los competidores directos e indirectos de {topic}?", "Definir panorama competitivo."),
            ("¿Cómo se comparan en valor, precio, alcance y capacidades?", "Construir benchmark."),
        ),
        ResearchPromptProfile.TREND: (
            ("¿Qué señales verificables indican que {topic} es una tendencia?", "Separar tendencia de ruido."),
            ("¿Cuál es su velocidad, duración probable y distribución geográfica?", "Medir evolución."),
        ),
        ResearchPromptProfile.AUDIENCE: (
            ("¿Qué segmentos de audiencia muestran mayor interés en {topic}?", "Priorizar públicos."),
            ("¿Qué necesidades, motivaciones, objeciones y hábitos presentan?", "Comprender conducta."),
        ),
        ResearchPromptProfile.MONETIZATION: (
            ("¿Qué modelos de monetización son aplicables a {topic}?", "Identificar ingresos."),
            ("¿Qué costos, márgenes, riesgos y requisitos tiene cada modelo?", "Evaluar viabilidad."),
        ),
        ResearchPromptProfile.CONTENT: (
            ("¿Qué ángulos de contenido verificables y relevantes existen sobre {topic}?", "Crear base editorial."),
            ("¿Qué busca la audiencia y qué vacíos de contenido existen?", "Alinear contenido con demanda."),
        ),
    }

    @classmethod
    def expand(cls, context: PromptBuildContext, *, profile: Optional[ResearchPromptProfile] = None,
               maximum_questions: Optional[int] = None) -> list[ResearchQuestion]:
        profile = profile or ResearchMethodSelector.infer_profile(context)
        result = list(context.questions)
        seen = {_key(item.question) for item in result}
        limit = maximum_questions or getattr(context.configuration, "max_questions", 50)
        for template, rationale in (*cls.GENERAL, *cls.PROFILE.get(profile, ())):
            if len(result) >= limit:
                break
            text = template.format(topic=context.topic)
            token = _key(text)
            if token not in seen:
                result.append(_question(text, ResearchPriority.HIGH, rationale))
                seen.add(token)
        return result


class ResearchObjectiveOptimizer:
    @staticmethod
    def optimize_statement(statement: str, *, topic: str, audience: str = "", platform: str = "", deadline: str = "") -> str:
        statement = normalize_text(statement, required=True)
        if len(statement.split()) >= 15:
            return statement
        qualifiers = []
        if audience:
            qualifiers.append(f"para {audience}")
        if platform:
            qualifiers.append(f"en {platform}")
        if deadline:
            qualifiers.append(f"antes de {deadline}")
        suffix = ", " + ", ".join(qualifiers) if qualifiers else ""
        return (
            f"Determinar, mediante investigación documentada y trazable, los hechos verificables, "
            f"fuentes autoritativas, riesgos, oportunidades, limitaciones y recomendaciones accionables "
            f"relacionados con {topic}{suffix}, para permitir decisiones y contenido publicable sin exceder la evidencia."
        )

    @classmethod
    def optimize_context(cls, context: PromptBuildContext) -> PromptBuildContext:
        context.objective = cls.optimize_statement(context.objective, topic=context.topic,
                                                   audience=context.audience, platform=context.platform,
                                                   deadline=context.deadline)
        context.objectives = [
            _objective(cls.optimize_statement(item.statement, topic=context.topic,
                                               audience=context.audience, platform=context.platform,
                                               deadline=context.deadline), item.priority)
            for item in context.objectives
        ]
        return context


class ConstraintResolver:
    FACTUALITY_MASTER = (
        "No inventar ni fabricar fuentes, datos, estadísticas, citas, evidencia, identificadores o conclusiones; "
        "toda afirmación material debe ser trazable y cualquier incertidumbre debe declararse."
    )

    @classmethod
    def resolve(cls, constraints: Sequence[ResearchConstraint]) -> list[ResearchConstraint]:
        if not constraints:
            return []
        factual_terms = ("invent", "fabric", "falso", "estadística", "evidencia", "fuente")
        factual: list[ResearchConstraint] = []
        others: list[ResearchConstraint] = []
        seen: set[str] = set()
        for item in constraints:
            token = _key(item.description)
            if token in seen:
                continue
            seen.add(token)
            if any(term in token for term in factual_terms):
                factual.append(item)
            else:
                others.append(item)
        if factual:
            others.insert(0, _constraint(cls.FACTUALITY_MASTER, "factuality", any(getattr(x, "mandatory", True) for x in factual)))
        return others

    @classmethod
    def resolve_context(cls, context: PromptBuildContext) -> PromptBuildContext:
        context.constraints = cls.resolve(context.constraints)
        return context


