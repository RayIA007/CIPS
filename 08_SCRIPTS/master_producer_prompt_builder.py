"""
CIPS — Master Producer Prompt Builder
=====================================

Constructor oficial de prompts para el componente Master Producer de CIPS.

Ruta del proyecto:
    08_SCRIPTS/master_producer_prompt_builder.py

Responsabilidades:
- Convertir ProductionBrief y ProductionContext en instrucciones operativas.
- Seleccionar los especialistas necesarios para cada proyecto.
- Definir el contrato de salida estructurada del Master Producer.
- Construir prompts reproducibles, auditables y listos para un LLM.

Este módulo no ejecuta modelos de IA ni escribe archivos de producción.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from typing import Any, Iterable, Mapping, Optional, Sequence

try:
    from master_producer_models import (
        ContentType,
        MasterProducerConfiguration,
        MonetizationObjective,
        PlatformType,
        ProductionBrief,
        ProductionContext,
        QualityLevel,
        SpecialistRole,
    )
except ImportError:  # Permite importarlo como parte de un paquete.
    from .master_producer_models import (
        ContentType,
        MasterProducerConfiguration,
        MonetizationObjective,
        PlatformType,
        ProductionBrief,
        ProductionContext,
        QualityLevel,
        SpecialistRole,
    )


PROMPT_BUILDER_VERSION = "1.0.0"
DEFAULT_MAX_CONTEXT_CHARACTERS = 48_000


__all__ = [
    "PROMPT_BUILDER_VERSION",
    "DEFAULT_MAX_CONTEXT_CHARACTERS",
    "PromptBuildError",
    "PromptSection",
    "PromptPackage",
    "MasterProducerPromptBuilder",
    "build_master_producer_prompt",
]


class PromptBuildError(ValueError):
    """Error de validación o construcción de un prompt."""


@dataclass(slots=True, frozen=True)
class PromptSection:
    """Sección individual de un prompt construido."""

    title: str
    content: str
    required: bool = True

    def render(self) -> str:
        content = self.content.strip()
        if not content and not self.required:
            return ""
        if not content:
            raise PromptBuildError(
                f"La sección obligatoria '{self.title}' está vacía."
            )
        return f"## {self.title}\n\n{content}"


@dataclass(slots=True, frozen=True)
class PromptPackage:
    """Paquete final listo para enviarse a un proveedor de IA."""

    system_prompt: str
    user_prompt: str
    selected_roles: tuple[SpecialistRole, ...]
    response_schema: Mapping[str, Any]
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @property
    def combined_prompt(self) -> str:
        """Devuelve una versión monolítica para clientes de prompt único."""
        return (
            "<SYSTEM_INSTRUCTIONS>\n"
            f"{self.system_prompt.strip()}\n"
            "</SYSTEM_INSTRUCTIONS>\n\n"
            "<PROJECT_REQUEST>\n"
            f"{self.user_prompt.strip()}\n"
            "</PROJECT_REQUEST>"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "system_prompt": self.system_prompt,
            "user_prompt": self.user_prompt,
            "combined_prompt": self.combined_prompt,
            "selected_roles": [role.value for role in self.selected_roles],
            "response_schema": dict(self.response_schema),
            "metadata": dict(self.metadata),
        }

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)


class MasterProducerPromptBuilder:
    """
    Construye el prompt operativo del Master Producer.

    El resultado conserva una separación clara entre:
    - instrucciones permanentes del sistema;
    - información específica del proyecto;
    - contrato estructurado de respuesta.
    """

    ROLE_ORDER: tuple[SpecialistRole, ...] = (
        SpecialistRole.MASTER_PRODUCER,
        SpecialistRole.RESEARCH_DIRECTOR,
        SpecialistRole.FACT_CHECKER,
        SpecialistRole.STRATEGY_DIRECTOR,
        SpecialistRole.CREATIVE_DIRECTOR,
        SpecialistRole.SCREENWRITING_DIRECTOR,
        SpecialistRole.STORYBOARD_DIRECTOR,
        SpecialistRole.GENERATIVE_ART_DIRECTOR,
        SpecialistRole.AUDIO_DIRECTOR,
        SpecialistRole.SEO_DIRECTOR,
        SpecialistRole.PLATFORM_DIRECTOR,
        SpecialistRole.MARKETING_DIRECTOR,
        SpecialistRole.MONETIZATION_DIRECTOR,
        SpecialistRole.LEGAL_REVIEWER,
        SpecialistRole.QUALITY_DIRECTOR,
        SpecialistRole.PUBLISHING_MANAGER,
        SpecialistRole.ANALYTICS_DIRECTOR,
    )

    ROLE_LABELS: Mapping[SpecialistRole, str] = {
        SpecialistRole.MASTER_PRODUCER: "Master Producer",
        SpecialistRole.RESEARCH_DIRECTOR: "Director de Investigación",
        SpecialistRole.FACT_CHECKER: "Verificador de Datos",
        SpecialistRole.STRATEGY_DIRECTOR: "Director Estratégico",
        SpecialistRole.CREATIVE_DIRECTOR: "Director Creativo",
        SpecialistRole.SCREENWRITING_DIRECTOR: "Director de Guion",
        SpecialistRole.STORYBOARD_DIRECTOR: "Director de Storyboard",
        SpecialistRole.GENERATIVE_ART_DIRECTOR: "Director de Arte Generativo",
        SpecialistRole.AUDIO_DIRECTOR: "Director de Audio",
        SpecialistRole.SEO_DIRECTOR: "Director SEO",
        SpecialistRole.PLATFORM_DIRECTOR: "Director de Plataforma",
        SpecialistRole.MARKETING_DIRECTOR: "Director de Marketing",
        SpecialistRole.MONETIZATION_DIRECTOR: "Director de Monetización",
        SpecialistRole.LEGAL_REVIEWER: "Revisor Legal",
        SpecialistRole.QUALITY_DIRECTOR: "Director de Calidad",
        SpecialistRole.PUBLISHING_MANAGER: "Responsable de Publicación",
        SpecialistRole.ANALYTICS_DIRECTOR: "Director de Analítica",
        SpecialistRole.CUSTOM: "Especialista Personalizado",
    }

    ROLE_MISSIONS: Mapping[SpecialistRole, str] = {
        SpecialistRole.MASTER_PRODUCER: (
            "Coordinar el proyecto, validar dependencias, asignar especialistas, "
            "resolver conflictos y consolidar un plan ejecutable."
        ),
        SpecialistRole.RESEARCH_DIRECTOR: (
            "Definir la investigación necesaria, preguntas críticas, fuentes "
            "preferidas y criterios de evidencia."
        ),
        SpecialistRole.FACT_CHECKER: (
            "Verificar afirmaciones relevantes, separar hechos de inferencias y "
            "señalar datos que no deben publicarse sin confirmación."
        ),
        SpecialistRole.STRATEGY_DIRECTOR: (
            "Convertir el objetivo comercial y de audiencia en una estrategia de "
            "contenido medible y diferenciada."
        ),
        SpecialistRole.CREATIVE_DIRECTOR: (
            "Definir concepto, enfoque narrativo, promesa, gancho y dirección creativa."
        ),
        SpecialistRole.SCREENWRITING_DIRECTOR: (
            "Diseñar la arquitectura del guion, progresión narrativa, ritmo y llamada "
            "a la acción."
        ),
        SpecialistRole.STORYBOARD_DIRECTOR: (
            "Traducir el guion a escenas, planos, transiciones y necesidades visuales."
        ),
        SpecialistRole.GENERATIVE_ART_DIRECTOR: (
            "Planificar recursos visuales y prompts de imagen o video con coherencia "
            "estética y continuidad."
        ),
        SpecialistRole.AUDIO_DIRECTOR: (
            "Definir voz, música, efectos, silencios, mezcla y tratamiento sonoro."
        ),
        SpecialistRole.SEO_DIRECTOR: (
            "Diseñar palabras clave, títulos, descripciones, etiquetas y descubribilidad."
        ),
        SpecialistRole.PLATFORM_DIRECTOR: (
            "Adaptar duración, formato, estructura y publicación a la plataforma objetivo."
        ),
        SpecialistRole.MARKETING_DIRECTOR: (
            "Alinear el contenido con posicionamiento, distribución y conversión."
        ),
        SpecialistRole.MONETIZATION_DIRECTOR: (
            "Definir mecanismos de monetización compatibles con el contenido, la "
            "audiencia y la etapa del proyecto."
        ),
        SpecialistRole.LEGAL_REVIEWER: (
            "Detectar riesgos legales, regulatorios, de propiedad intelectual, "
            "publicidad, privacidad o uso de terceros."
        ),
        SpecialistRole.QUALITY_DIRECTOR: (
            "Establecer controles de calidad, criterios de aceptación y causas de rechazo."
        ),
        SpecialistRole.PUBLISHING_MANAGER: (
            "Preparar checklist, activos, metadatos y secuencia operativa de publicación."
        ),
        SpecialistRole.ANALYTICS_DIRECTOR: (
            "Definir KPIs, eventos de medición, hipótesis y reglas de aprendizaje posterior."
        ),
    }

    def __init__(
        self,
        configuration: Optional[MasterProducerConfiguration] = None,
        *,
        max_context_characters: int = DEFAULT_MAX_CONTEXT_CHARACTERS,
    ) -> None:
        self.configuration = configuration or MasterProducerConfiguration()
        if max_context_characters < 4_000:
            raise ValueError(
                "'max_context_characters' debe ser igual o mayor que 4000."
            )
        self.max_context_characters = max_context_characters

    def build(
        self,
        brief: ProductionBrief,
        context: Optional[ProductionContext] = None,
        *,
        additional_instructions: Optional[Iterable[str]] = None,
        forced_roles: Optional[Iterable[SpecialistRole | str]] = None,
        excluded_roles: Optional[Iterable[SpecialistRole | str]] = None,
    ) -> PromptPackage:
        """Construye y valida el paquete completo de prompts."""
        self._validate_inputs(brief, context)

        selected_roles = self.select_roles(
            brief,
            forced_roles=forced_roles,
            excluded_roles=excluded_roles,
        )
        response_schema = self.build_response_schema()
        system_prompt = self.build_system_prompt(selected_roles, response_schema)
        user_prompt = self.build_user_prompt(
            brief,
            context,
            selected_roles=selected_roles,
            additional_instructions=additional_instructions,
        )

        return PromptPackage(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            selected_roles=tuple(selected_roles),
            response_schema=response_schema,
            metadata={
                "builder": self.__class__.__name__,
                "builder_version": PROMPT_BUILDER_VERSION,
                "project_id": brief.project_id,
                "project_name": brief.project_name,
                "platform": brief.platform.value,
                "content_type": brief.content_type.value,
                "quality_level": brief.quality_level.value,
                "selected_role_count": len(selected_roles),
            },
        )

    def build_system_prompt(
        self,
        selected_roles: Sequence[SpecialistRole],
        response_schema: Mapping[str, Any],
    ) -> str:
        """Genera las instrucciones permanentes del Master Producer."""
        role_catalog = self._render_role_catalog(selected_roles)
        schema_json = json.dumps(response_schema, ensure_ascii=False, indent=2)

        sections = [
            PromptSection(
                "Identidad y autoridad",
                """
Eres el MASTER PRODUCER de CIPS, un Estudio Profesional de Producción de
Contenido impulsado por IA. Eres la máxima autoridad operativa del proyecto.
Tu función no es producir todavía cada pieza final, sino convertir una solicitud
en un plan profesional, ordenado, verificable, monetizable y listo para ser
ejecutado por especialistas.

Piensa como productor ejecutivo, director de operaciones editoriales, estratega
de contenido y responsable final de calidad. Debes proteger el objetivo del
proyecto, evitar trabajo innecesario y asegurar que cada fase genere una salida
utilizable por la siguiente.
""".strip(),
            ),
            PromptSection(
                "Misión",
                """
Analiza el brief y el contexto. Después:

1. Determina el alcance real del proyecto.
2. Detecta información faltante, riesgos, supuestos y dependencias.
3. Selecciona y coordina únicamente a los especialistas necesarios.
4. Diseña una secuencia de tareas sin ciclos ni saltos críticos.
5. Define entregables, criterios de aceptación y puntos de control.
6. Integra calidad, plataforma, publicación y monetización desde el inicio.
7. Entrega un plan listo para ejecución, no una explicación genérica.
""".strip(),
            ),
            PromptSection("Especialistas autorizados", role_catalog),
            PromptSection(
                "Principios obligatorios",
                """
- Prioriza producción, calidad y monetización.
- No inventes datos, fuentes, resultados, métricas ni capacidades.
- Marca claramente cualquier supuesto o información no verificada.
- No presentes como hecho aquello que requiera investigación.
- No omitas dependencias indispensables.
- No crees especialistas o tareas sin utilidad concreta.
- No dupliques responsabilidades entre especialistas.
- No generes ciclos de dependencia.
- La investigación precede a las afirmaciones verificables.
- La estrategia precede al concepto creativo.
- El concepto precede al guion.
- El guion precede al storyboard y a la producción visual.
- El control de calidad precede a la publicación.
- La monetización debe ser coherente con la audiencia y la propuesta de valor.
- Conserva el idioma solicitado por el proyecto.
- Respeta restricciones, puntos obligatorios y afirmaciones prohibidas.
""".strip(),
            ),
            PromptSection(
                "Criterios de decisión",
                """
Cada tarea propuesta debe cumplir al menos una condición:

- reduce tiempo de producción;
- incrementa calidad;
- reduce un riesgo real;
- mejora publicación o distribución;
- incrementa la capacidad de monetización;
- es indispensable para completar una dependencia.

Cuando una tarea no cumpla ninguna, elimínala del plan.
""".strip(),
            ),
            PromptSection(
                "Protocolo de incertidumbre",
                """
Cuando falte información:

- registra la pregunta en `open_questions`;
- formula un supuesto mínimo en `assumptions` solo cuando sea seguro continuar;
- agrega una tarea de investigación cuando la respuesta afecte precisión,
  cumplimiento, reputación, costo, monetización o publicación;
- marca `human_approval_required` cuando la decisión no deba automatizarse.

Nunca rellenes silenciosamente un dato crítico.
""".strip(),
            ),
            PromptSection(
                "Contrato de salida",
                f"""
Devuelve exclusivamente un objeto JSON válido que cumpla exactamente el
siguiente esquema lógico. No uses Markdown, comentarios, texto previo ni texto
posterior al JSON.

{schema_json}

Reglas adicionales del JSON:

- Usa cadenas vacías únicamente cuando el esquema las permita y no exista dato.
- Usa listas vacías cuando no haya elementos aplicables.
- Todos los identificadores deben ser únicos dentro de la respuesta.
- `dependency_task_ids` solo puede referenciar tareas existentes.
- `sequence` debe reflejar el orden de ejecución.
- Los puntajes deben usar una escala de 0 a 10.
- `selected_roles` debe contener únicamente los roles autorizados indicados.
- `final_recommendation` debe ser operativa y específica.
""".strip(),
            ),
        ]

        return self._render_sections(sections)

    def build_user_prompt(
        self,
        brief: ProductionBrief,
        context: Optional[ProductionContext],
        *,
        selected_roles: Sequence[SpecialistRole],
        additional_instructions: Optional[Iterable[str]] = None,
    ) -> str:
        """Genera la solicitud específica del proyecto."""
        brief_json = self._bounded_json(brief.to_dict(), "brief")
        context_json = self._bounded_json(
            context.to_dict() if context is not None else {},
            "context",
        )
        instructions = self._normalize_strings(additional_instructions)

        selected = "\n".join(
            f"- {role.value}: {self.ROLE_LABELS.get(role, role.value)}"
            for role in selected_roles
        )

        sections = [
            PromptSection(
                "Orden de producción",
                """
Construye el plan maestro del proyecto descrito a continuación. Debe quedar
listo para que un orquestador convierta cada tarea en una ejecución real.
No redactes todavía todos los entregables finales: define con precisión cómo se
producirán, qué información requieren, quién los realizará y cómo se aprobarán.
""".strip(),
            ),
            PromptSection("ProductionBrief", brief_json),
            PromptSection("ProductionContext", context_json),
            PromptSection("Roles seleccionados", selected),
            PromptSection(
                "Instrucciones adicionales",
                self._render_bullets(instructions),
                required=False,
            ),
            PromptSection(
                "Resultado esperado",
                """
Entrega un plan que incluya:

- resumen ejecutivo del proyecto;
- evaluación de viabilidad;
- preguntas abiertas y supuestos;
- riesgos y acciones de mitigación;
- especialistas seleccionados y justificación;
- tareas ordenadas con dependencias;
- entregables esperados;
- criterios de aceptación;
- checkpoints de revisión humana y automática;
- estrategia preliminar de monetización;
- métricas y señales de éxito;
- recomendación final para iniciar, pausar o solicitar información.

La respuesta debe ser directamente utilizable por `master_producer.py`.
""".strip(),
            ),
        ]

        return self._render_sections(sections)

    def select_roles(
        self,
        brief: ProductionBrief,
        *,
        forced_roles: Optional[Iterable[SpecialistRole | str]] = None,
        excluded_roles: Optional[Iterable[SpecialistRole | str]] = None,
    ) -> list[SpecialistRole]:
        """Selecciona especialistas mediante reglas explícitas y reproducibles."""
        selected: set[SpecialistRole] = {
            SpecialistRole.MASTER_PRODUCER,
            SpecialistRole.STRATEGY_DIRECTOR,
            SpecialistRole.CREATIVE_DIRECTOR,
            SpecialistRole.QUALITY_DIRECTOR,
        }

        if brief.requires_research and self.configuration.enable_research:
            selected.add(SpecialistRole.RESEARCH_DIRECTOR)

        if brief.requires_fact_check and self.configuration.enable_fact_check:
            selected.add(SpecialistRole.FACT_CHECKER)

        if brief.requires_legal_review and self.configuration.enable_legal_review_when_required:
            selected.add(SpecialistRole.LEGAL_REVIEWER)

        if brief.content_type in {
            ContentType.SHORT_VIDEO,
            ContentType.LONG_VIDEO,
            ContentType.PODCAST_EPISODE,
            ContentType.SCRIPT,
            ContentType.CAMPAIGN,
            ContentType.MULTIFORMAT_PACKAGE,
        }:
            selected.add(SpecialistRole.SCREENWRITING_DIRECTOR)

        if brief.content_type in {
            ContentType.SHORT_VIDEO,
            ContentType.LONG_VIDEO,
            ContentType.IMAGE_SET,
            ContentType.CAROUSEL,
            ContentType.CAMPAIGN,
            ContentType.MULTIFORMAT_PACKAGE,
        }:
            selected.add(SpecialistRole.GENERATIVE_ART_DIRECTOR)

        if brief.content_type in {
            ContentType.SHORT_VIDEO,
            ContentType.LONG_VIDEO,
            ContentType.PODCAST_EPISODE,
            ContentType.MULTIFORMAT_PACKAGE,
        }:
            selected.add(SpecialistRole.AUDIO_DIRECTOR)

        if brief.content_type in {
            ContentType.SHORT_VIDEO,
            ContentType.LONG_VIDEO,
            ContentType.CAROUSEL,
            ContentType.CAMPAIGN,
            ContentType.MULTIFORMAT_PACKAGE,
        }:
            selected.add(SpecialistRole.STORYBOARD_DIRECTOR)

        if brief.platform in {
            PlatformType.TIKTOK,
            PlatformType.YOUTUBE_SHORTS,
            PlatformType.YOUTUBE_LONG,
            PlatformType.INSTAGRAM_REELS,
            PlatformType.INSTAGRAM_POST,
            PlatformType.INSTAGRAM_CAROUSEL,
            PlatformType.FACEBOOK_REELS,
            PlatformType.FACEBOOK_POST,
            PlatformType.LINKEDIN,
            PlatformType.X,
            PlatformType.THREADS,
            PlatformType.PINTEREST,
            PlatformType.BLOG,
            PlatformType.PODCAST,
            PlatformType.NEWSLETTER,
            PlatformType.MULTIPLATFORM,
        }:
            selected.add(SpecialistRole.PLATFORM_DIRECTOR)
            selected.add(SpecialistRole.PUBLISHING_MANAGER)

        if brief.platform in {
            PlatformType.YOUTUBE_SHORTS,
            PlatformType.YOUTUBE_LONG,
            PlatformType.BLOG,
            PlatformType.PINTEREST,
            PlatformType.PODCAST,
            PlatformType.NEWSLETTER,
            PlatformType.MULTIPLATFORM,
        } or bool(brief.target_keywords):
            selected.add(SpecialistRole.SEO_DIRECTOR)

        if brief.monetization_objective is not MonetizationObjective.NONE:
            if self.configuration.enable_monetization_review:
                selected.add(SpecialistRole.MONETIZATION_DIRECTOR)
            selected.add(SpecialistRole.MARKETING_DIRECTOR)
            selected.add(SpecialistRole.ANALYTICS_DIRECTOR)

        if brief.quality_level in {
            QualityLevel.PREMIUM,
            QualityLevel.PUBLICATION_READY,
        }:
            selected.add(SpecialistRole.FACT_CHECKER)
            selected.add(SpecialistRole.ANALYTICS_DIRECTOR)

        forced = self._normalize_roles(forced_roles)
        excluded = self._normalize_roles(excluded_roles)

        selected.update(forced)
        selected.difference_update(excluded)
        selected.add(SpecialistRole.MASTER_PRODUCER)

        if (
            SpecialistRole.QUALITY_DIRECTOR in excluded
            and self.configuration.enable_quality_review
        ):
            raise PromptBuildError(
                "No puede excluirse QUALITY_DIRECTOR mientras "
                "enable_quality_review=True."
            )

        if self.configuration.enable_quality_review:
            selected.add(SpecialistRole.QUALITY_DIRECTOR)

        return [role for role in self.ROLE_ORDER if role in selected]

    def build_response_schema(self) -> dict[str, Any]:
        """Devuelve el contrato lógico esperado del LLM."""
        return {
            "project_id": "string",
            "plan_version": 1,
            "status": "planning|ready|paused|rejected",
            "executive_summary": "string",
            "feasibility": {
                "score": "number 0-10",
                "decision": "proceed|proceed_with_conditions|request_information|stop",
                "reason": "string",
            },
            "open_questions": ["string"],
            "assumptions": ["string"],
            "risks": [
                {
                    "risk_id": "string",
                    "level": "none|low|medium|high|critical",
                    "description": "string",
                    "blocking": "boolean",
                    "mitigation": "string",
                    "owner_role": "specialist_role",
                }
            ],
            "selected_roles": [
                {
                    "role": "specialist_role",
                    "reason": "string",
                    "mission": "string",
                    "required": "boolean",
                    "execution_order": "integer >= 0",
                    "depends_on_roles": ["specialist_role"],
                    "expected_outputs": ["string"],
                }
            ],
            "tasks": [
                {
                    "task_id": "string",
                    "sequence": "integer >= 0",
                    "title": "string",
                    "role": "specialist_role",
                    "objective": "string",
                    "dependency_task_ids": ["string"],
                    "input_artifacts": ["string"],
                    "output_artifacts": ["string"],
                    "instructions": ["string"],
                    "acceptance_criteria": ["string"],
                    "estimated_minutes": "number >= 0",
                    "required": "boolean",
                    "human_approval_required": "boolean",
                }
            ],
            "checkpoints": [
                {
                    "checkpoint_id": "string",
                    "stage": "string",
                    "name": "string",
                    "reviewer_role": "specialist_role",
                    "criteria": ["string"],
                    "minimum_score": "number 0-10",
                    "blocking": "boolean",
                }
            ],
            "expected_artifacts": [
                {
                    "name": "string",
                    "artifact_type": "string",
                    "producer_role": "specialist_role",
                    "required": "boolean",
                    "description": "string",
                }
            ],
            "monetization_plan": {
                "objective": "string",
                "primary_mechanism": "string",
                "supporting_mechanisms": ["string"],
                "audience_action": "string",
                "requirements": ["string"],
                "risks": ["string"],
            },
            "success_metrics": [
                {
                    "metric": "string",
                    "purpose": "string",
                    "target": "string",
                    "measurement_stage": "string",
                }
            ],
            "quality_requirements": {
                "minimum_quality_score": "number 0-10",
                "minimum_publication_readiness_score": "number 0-10",
                "minimum_fact_confidence_score": "number 0-10",
                "rejection_conditions": ["string"],
            },
            "final_recommendation": "string",
            "next_action": "start_production|request_information|human_review|stop",
        }

    def get_component_info(self) -> dict[str, Any]:
        return {
            "component": self.__class__.__name__,
            "version": PROMPT_BUILDER_VERSION,
            "max_context_characters": self.max_context_characters,
            "default_language": self.configuration.default_language,
            "strict_validation": self.configuration.strict_validation,
            "supported_roles": len(self.ROLE_ORDER),
        }

    def _validate_inputs(
        self,
        brief: ProductionBrief,
        context: Optional[ProductionContext],
    ) -> None:
        if not isinstance(brief, ProductionBrief):
            raise TypeError("'brief' debe ser ProductionBrief.")
        if context is not None and not isinstance(context, ProductionContext):
            raise TypeError("'context' debe ser ProductionContext o None.")
        if context is not None and context.brief.project_id != brief.project_id:
            raise PromptBuildError(
                "El ProductionContext pertenece a un project_id diferente."
            )

        issues = brief.validate_for_production()
        if issues and self.configuration.strict_validation:
            raise PromptBuildError(" ".join(issues))

    def _render_role_catalog(
        self,
        selected_roles: Sequence[SpecialistRole],
    ) -> str:
        lines: list[str] = []
        for index, role in enumerate(selected_roles, start=1):
            label = self.ROLE_LABELS.get(role, role.value)
            mission = self.ROLE_MISSIONS.get(
                role,
                "Cumplir la misión específica definida por el proyecto.",
            )
            lines.append(f"{index}. `{role.value}` — **{label}**: {mission}")
        return "\n".join(lines)

    def _bounded_json(self, value: Any, label: str) -> str:
        rendered = json.dumps(value, ensure_ascii=False, indent=2)
        if len(rendered) <= self.max_context_characters:
            return rendered

        if self.configuration.strict_validation:
            raise PromptBuildError(
                f"El bloque '{label}' excede el límite de "
                f"{self.max_context_characters} caracteres."
            )

        marker = (
            "\n... CONTENIDO TRUNCADO POR LÍMITE DEL PROMPT ...\n"
        )
        available = self.max_context_characters - len(marker)
        return rendered[:available] + marker

    @staticmethod
    def _normalize_strings(
        values: Optional[Iterable[str]],
    ) -> list[str]:
        if values is None:
            return []
        result: list[str] = []
        seen: set[str] = set()
        for value in values:
            text = str(value).strip()
            if not text:
                continue
            key = text.casefold()
            if key in seen:
                continue
            seen.add(key)
            result.append(text)
        return result

    @staticmethod
    def _normalize_roles(
        values: Optional[Iterable[SpecialistRole | str]],
    ) -> set[SpecialistRole]:
        if values is None:
            return set()
        result: set[SpecialistRole] = set()
        for value in values:
            try:
                result.add(SpecialistRole(value))
            except ValueError as exc:
                raise PromptBuildError(
                    f"Rol de especialista no válido: {value!r}."
                ) from exc
        return result

    @staticmethod
    def _render_bullets(values: Sequence[str]) -> str:
        return "\n".join(f"- {value}" for value in values)

    @staticmethod
    def _render_sections(sections: Sequence[PromptSection]) -> str:
        rendered = [section.render() for section in sections]
        return "\n\n".join(section for section in rendered if section).strip()


def build_master_producer_prompt(
    brief: ProductionBrief,
    context: Optional[ProductionContext] = None,
    *,
    configuration: Optional[MasterProducerConfiguration] = None,
    additional_instructions: Optional[Iterable[str]] = None,
    forced_roles: Optional[Iterable[SpecialistRole | str]] = None,
    excluded_roles: Optional[Iterable[SpecialistRole | str]] = None,
) -> PromptPackage:
    """Función de conveniencia para construir un PromptPackage completo."""
    builder = MasterProducerPromptBuilder(configuration=configuration)
    return builder.build(
        brief,
        context,
        additional_instructions=additional_instructions,
        forced_roles=forced_roles,
        excluded_roles=excluded_roles,
    )