"""Constructor principal y selección metodológica."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from textwrap import dedent
from typing import Any, Iterable, Mapping, Optional, Sequence

try:
    from research_director_models import (
        CitationStyle,
        ClaimStatus,
        ClaimType,
        EvidenceDirection,
        EvidenceStrength,
        EvidenceType,
        FactClaim,
        FindingImportance,
        GapSeverity,
        KnowledgeGap,
        QuestionStatus,
        QuestionType,
        ResearchConfiguration,
        ResearchConstraint,
        ResearchEvidence,
        ResearchFinding,
        ResearchHypothesis,
        ResearchMethod,
        ResearchObjective,
        ResearchPlan,
        ResearchPriority,
        ResearchQuestion,
        ResearchScope,
        ResearchSource,
        ResearchStatus,
        SourceCredibility,
        SourceType,
        VerificationStatus,
        utc_now_iso,
    )
except ImportError:  # pragma: no cover
    from ..research_director_models import (
        CitationStyle,
        ClaimStatus,
        ClaimType,
        EvidenceDirection,
        EvidenceStrength,
        EvidenceType,
        FactClaim,
        FindingImportance,
        GapSeverity,
        KnowledgeGap,
        QuestionStatus,
        QuestionType,
        ResearchConfiguration,
        ResearchConstraint,
        ResearchEvidence,
        ResearchFinding,
        ResearchHypothesis,
        ResearchMethod,
        ResearchObjective,
        ResearchPlan,
        ResearchPriority,
        ResearchQuestion,
        ResearchScope,
        ResearchSource,
        ResearchStatus,
        SourceCredibility,
        SourceType,
        VerificationStatus,
        utc_now_iso,
    )

from .common import (
    DEFAULT_PROMPT_LANGUAGE,
    DEFAULT_SCHEMA_VERSION,
    PromptAudience,
    PromptOutputMode,
    PromptSectionKind,
    PromptStrictness,
    ResearchPromptBuilderError,
    ResearchPromptContractError,
    ResearchPromptValidationError,
    normalize_string_list,
    normalize_text,
    safe_json_dumps,
    stable_hash,
)
from .contracts import ResearchPromptContract, ResearchPromptValidator
from .models import PromptBuildContext, PromptPackage, PromptSection
from .templates import ResearchPromptTemplates

RESEARCH_PROMPT_BUILDER_PART2_VERSION = "1.0.0-refactor-builder"

class ResearchPromptProfile(str, Enum):
    GENERAL = "general"
    FACT_CHECKING = "fact_checking"
    LEGAL = "legal"
    TECHNICAL = "technical"
    SCIENTIFIC = "scientific"
    MARKET = "market"
    COMPETITOR = "competitor"
    TREND = "trend"
    AUDIENCE = "audience"
    MONETIZATION = "monetization"
    CONTENT = "content"


@dataclass(slots=True)
class _SectionPlan:
    title: str
    kind: PromptSectionKind
    audience: PromptAudience
    content: str
    order: int
    required: bool = True
    enabled: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_section(self) -> PromptSection:
        return PromptSection(
            title=self.title,
            content=self.content,
            kind=self.kind,
            audience=self.audience,
            order=self.order,
            required=self.required,
            enabled=self.enabled,
            metadata=dict(self.metadata),
        )


class ResearchMethodSelector:
    """Selecciona métodos de investigación a partir del contexto."""

    PROFILE_METHODS: dict[ResearchPromptProfile, tuple[ResearchMethod, ...]] = {
        ResearchPromptProfile.GENERAL: (
            ResearchMethod.DESK_RESEARCH,
            ResearchMethod.DOCUMENT_ANALYSIS,
            ResearchMethod.FACT_CHECKING,
        ),
        ResearchPromptProfile.FACT_CHECKING: (
            ResearchMethod.FACT_CHECKING,
            ResearchMethod.DOCUMENT_ANALYSIS,
            ResearchMethod.COMPARATIVE_ANALYSIS,
        ),
        ResearchPromptProfile.LEGAL: (
            ResearchMethod.LEGAL_RESEARCH,
            ResearchMethod.DOCUMENT_ANALYSIS,
            ResearchMethod.FACT_CHECKING,
        ),
        ResearchPromptProfile.TECHNICAL: (
            ResearchMethod.TECHNICAL_VALIDATION,
            ResearchMethod.DOCUMENT_ANALYSIS,
            ResearchMethod.COMPARATIVE_ANALYSIS,
        ),
        ResearchPromptProfile.SCIENTIFIC: (
            ResearchMethod.LITERATURE_REVIEW,
            ResearchMethod.SYSTEMATIC_REVIEW,
            ResearchMethod.DATASET_ANALYSIS,
        ),
        ResearchPromptProfile.MARKET: (
            ResearchMethod.MARKET_RESEARCH,
            ResearchMethod.COMPARATIVE_ANALYSIS,
            ResearchMethod.TREND_ANALYSIS,
        ),
        ResearchPromptProfile.COMPETITOR: (
            ResearchMethod.COMPETITOR_RESEARCH,
            ResearchMethod.COMPARATIVE_ANALYSIS,
            ResearchMethod.DESK_RESEARCH,
        ),
        ResearchPromptProfile.TREND: (
            ResearchMethod.TREND_ANALYSIS,
            ResearchMethod.MARKET_RESEARCH,
            ResearchMethod.DESK_RESEARCH,
        ),
        ResearchPromptProfile.AUDIENCE: (
            ResearchMethod.USER_INTERVIEW,
            ResearchMethod.SURVEY,
            ResearchMethod.MARKET_RESEARCH,
        ),
        ResearchPromptProfile.MONETIZATION: (
            ResearchMethod.MARKET_RESEARCH,
            ResearchMethod.COMPETITOR_RESEARCH,
            ResearchMethod.COMPARATIVE_ANALYSIS,
        ),
        ResearchPromptProfile.CONTENT: (
            ResearchMethod.DESK_RESEARCH,
            ResearchMethod.TREND_ANALYSIS,
            ResearchMethod.FACT_CHECKING,
        ),
    }

    @classmethod
    def infer_profile(
        cls,
        context: PromptBuildContext,
    ) -> ResearchPromptProfile:
        corpus = " ".join(
            [
                context.topic,
                context.objective,
                context.audience,
                context.content_format,
                context.platform,
                " ".join(question.question for question in context.questions),
            ]
        ).casefold()

        keyword_groups: list[tuple[ResearchPromptProfile, tuple[str, ...]]] = [
            (
                ResearchPromptProfile.LEGAL,
                (
                    "ley",
                    "legal",
                    "regulación",
                    "reglamento",
                    "juríd",
                    "norma",
                    "compliance",
                    "contrato",
                ),
            ),
            (
                ResearchPromptProfile.SCIENTIFIC,
                (
                    "científic",
                    "estudio",
                    "ensayo",
                    "evidencia clínica",
                    "paper",
                    "meta-análisis",
                    "revisión sistemática",
                ),
            ),
            (
                ResearchPromptProfile.TECHNICAL,
                (
                    "técnic",
                    "software",
                    "arquitectura",
                    "api",
                    "código",
                    "ingeniería",
                    "estándar",
                    "implementación",
                ),
            ),
            (
                ResearchPromptProfile.COMPETITOR,
                (
                    "competidor",
                    "competencia",
                    "benchmark",
                    "comparar marcas",
                    "posicionamiento competitivo",
                ),
            ),
            (
                ResearchPromptProfile.MONETIZATION,
                (
                    "monetización",
                    "ingresos",
                    "rentabilidad",
                    "modelo de negocio",
                    "pricing",
                    "precio",
                    "roi",
                ),
            ),
            (
                ResearchPromptProfile.MARKET,
                (
                    "mercado",
                    "demanda",
                    "industria",
                    "segmento",
                    "tamaño de mercado",
                    "oportunidad comercial",
                ),
            ),
            (
                ResearchPromptProfile.TREND,
                (
                    "tendencia",
                    "viral",
                    "actualidad",
                    "popularidad",
                    "crecimiento",
                ),
            ),
            (
                ResearchPromptProfile.AUDIENCE,
                (
                    "audiencia",
                    "usuario",
                    "cliente ideal",
                    "buyer persona",
                    "comportamiento",
                    "psicología",
                ),
            ),
            (
                ResearchPromptProfile.FACT_CHECKING,
                (
                    "verificar",
                    "comprobar",
                    "fact-check",
                    "confirmar",
                    "verdadero",
                    "falso",
                ),
            ),
            (
                ResearchPromptProfile.CONTENT,
                (
                    "contenido",
                    "youtube",
                    "tiktok",
                    "instagram",
                    "video",
                    "guion",
                    "publicación",
                ),
            ),
        ]

        scores: dict[ResearchPromptProfile, int] = {
            profile: 0 for profile, _ in keyword_groups
        }

        for profile, keywords in keyword_groups:
            for keyword in keywords:
                if keyword in corpus:
                    scores[profile] += 1

        if not any(scores.values()):
            return ResearchPromptProfile.GENERAL

        return max(scores, key=scores.get)

    @classmethod
    def select_methods(
        cls,
        context: PromptBuildContext,
        *,
        profile: Optional[ResearchPromptProfile] = None,
    ) -> list[ResearchMethod]:
        if context.preferred_methods:
            return list(context.preferred_methods)

        if context.plan is not None and context.plan.methods:
            return list(context.plan.methods)

        selected_profile = profile or cls.infer_profile(context)
        methods = list(cls.PROFILE_METHODS[selected_profile])

        if context.configuration.require_fact_check_for_publication:
            if ResearchMethod.FACT_CHECKING not in methods:
                methods.append(ResearchMethod.FACT_CHECKING)

        if context.research_scope is ResearchScope.COMPARATIVE:
            if ResearchMethod.COMPARATIVE_ANALYSIS not in methods:
                methods.append(ResearchMethod.COMPARATIVE_ANALYSIS)

        if context.research_scope is ResearchScope.CONFIRMATORY:
            if ResearchMethod.FACT_CHECKING not in methods:
                methods.append(ResearchMethod.FACT_CHECKING)

        return list(dict.fromkeys(methods))


class ResearchDirectorPromptBuilder:
    """Constructor principal de prompts del Research Director."""

    def __init__(
        self,
        configuration: Optional[ResearchConfiguration] = None,
        *,
        output_mode: PromptOutputMode = PromptOutputMode.JSON_ONLY,
        strictness: PromptStrictness = PromptStrictness.STRICT,
        include_developer_prompt: bool = True,
        include_contract_in_user_prompt: bool = True,
        include_full_supplied_material: bool = True,
    ) -> None:
        self.configuration = configuration or ResearchConfiguration()
        self.output_mode = (
            output_mode
            if isinstance(output_mode, PromptOutputMode)
            else PromptOutputMode(str(output_mode))
        )
        self.strictness = (
            strictness
            if isinstance(strictness, PromptStrictness)
            else PromptStrictness(str(strictness))
        )
        self.include_developer_prompt = bool(include_developer_prompt)
        self.include_contract_in_user_prompt = bool(
            include_contract_in_user_prompt
        )
        self.include_full_supplied_material = bool(
            include_full_supplied_material
        )

    def build(
        self,
        context: PromptBuildContext,
    ) -> PromptPackage:
        ResearchPromptValidator.validate_context(context)

        profile = ResearchMethodSelector.infer_profile(context)
        methods = ResearchMethodSelector.select_methods(
            context,
            profile=profile,
        )
        contract = self.build_output_contract(
            context=context,
            profile=profile,
            methods=methods,
        )

        system_sections = self.build_system_sections(
            context=context,
            profile=profile,
            methods=methods,
        )
        developer_sections = self.build_developer_sections(
            context=context,
            profile=profile,
            methods=methods,
        )
        user_sections = self.build_user_sections(
            context=context,
            profile=profile,
            methods=methods,
            contract=contract,
        )

        all_sections = [
            *system_sections,
            *developer_sections,
            *user_sections,
        ]

        system_prompt = self.render_sections(
            system_sections,
            heading_level=2,
        )
        developer_prompt = (
            self.render_sections(
                developer_sections,
                heading_level=2,
            )
            if self.include_developer_prompt
            else ""
        )
        user_prompt = self.render_sections(
            user_sections,
            heading_level=2,
        )

        package = PromptPackage(
            system_prompt=system_prompt,
            developer_prompt=developer_prompt,
            user_prompt=user_prompt,
            output_contract=contract,
            sections=all_sections,
            language=context.language,
            output_mode=self.output_mode,
            strictness=self.strictness,
            schema_version=DEFAULT_SCHEMA_VERSION,
            builder_version=RESEARCH_PROMPT_BUILDER_PART2_VERSION,
            metadata={
                "project_id": context.project_id,
                "context_id": context.context_id,
                "profile": profile.value,
                "methods": [method.value for method in methods],
                "created_by": self.__class__.__name__,
                "built_at": utc_now_iso(),
                "configuration_hash": stable_hash(
                    self.configuration.to_dict()
                ),
                "context_hash": stable_hash(context.to_dict()),
            },
        )

        ResearchPromptValidator.validate_package(package)
        return package

    def build_system_prompt(
        self,
        context: PromptBuildContext,
    ) -> str:
        profile = ResearchMethodSelector.infer_profile(context)
        methods = ResearchMethodSelector.select_methods(
            context,
            profile=profile,
        )
        return self.render_sections(
            self.build_system_sections(
                context=context,
                profile=profile,
                methods=methods,
            )
        )

    def build_developer_prompt(
        self,
        context: PromptBuildContext,
    ) -> str:
        profile = ResearchMethodSelector.infer_profile(context)
        methods = ResearchMethodSelector.select_methods(
            context,
            profile=profile,
        )
        return self.render_sections(
            self.build_developer_sections(
                context=context,
                profile=profile,
                methods=methods,
            )
        )

    def build_user_prompt(
        self,
        context: PromptBuildContext,
    ) -> str:
        profile = ResearchMethodSelector.infer_profile(context)
        methods = ResearchMethodSelector.select_methods(
            context,
            profile=profile,
        )
        contract = self.build_output_contract(
            context=context,
            profile=profile,
            methods=methods,
        )
        return self.render_sections(
            self.build_user_sections(
                context=context,
                profile=profile,
                methods=methods,
                contract=contract,
            )
        )

    def build_system_sections(
        self,
        *,
        context: PromptBuildContext,
        profile: ResearchPromptProfile,
        methods: Sequence[ResearchMethod],
    ) -> list[PromptSection]:
        plans = [
            _SectionPlan(
                title="Identidad profesional",
                content=ResearchPromptTemplates.SYSTEM_IDENTITY,
                kind=PromptSectionKind.IDENTITY,
                audience=PromptAudience.SYSTEM,
                order=10,
            ),
            _SectionPlan(
                title="Misión central",
                content=ResearchPromptTemplates.CORE_MISSION,
                kind=PromptSectionKind.MISSION,
                audience=PromptAudience.SYSTEM,
                order=20,
            ),
            _SectionPlan(
                title="Reglas no negociables",
                content=ResearchPromptTemplates.NON_NEGOTIABLE_RULES,
                kind=PromptSectionKind.SAFETY_POLICY,
                audience=PromptAudience.SYSTEM,
                order=30,
            ),
            _SectionPlan(
                title="Perfil de investigación",
                content=self._build_profile_instruction(profile),
                kind=PromptSectionKind.METHODOLOGY,
                audience=PromptAudience.SYSTEM,
                order=40,
            ),
            _SectionPlan(
                title="Métodos seleccionados",
                content=self._build_methods_instruction(methods),
                kind=PromptSectionKind.METHODOLOGY,
                audience=PromptAudience.SYSTEM,
                order=50,
            ),
            _SectionPlan(
                title="Política de fuentes",
                content=ResearchPromptTemplates.SOURCE_POLICY,
                kind=PromptSectionKind.SOURCE_POLICY,
                audience=PromptAudience.SYSTEM,
                order=60,
            ),
            _SectionPlan(
                title="Política de evidencia",
                content=ResearchPromptTemplates.EVIDENCE_POLICY,
                kind=PromptSectionKind.EVIDENCE_POLICY,
                audience=PromptAudience.SYSTEM,
                order=70,
            ),
            _SectionPlan(
                title="Política de afirmaciones",
                content=ResearchPromptTemplates.CLAIM_POLICY,
                kind=PromptSectionKind.CLAIM_POLICY,
                audience=PromptAudience.SYSTEM,
                order=80,
            ),
            _SectionPlan(
                title="Política de citas",
                content=ResearchPromptTemplates.CITATION_POLICY,
                kind=PromptSectionKind.CITATION_POLICY,
                audience=PromptAudience.SYSTEM,
                order=90,
            ),
            _SectionPlan(
                title="Puertas de calidad",
                content=self._build_quality_policy(context),
                kind=PromptSectionKind.QUALITY_POLICY,
                audience=PromptAudience.SYSTEM,
                order=100,
            ),
            _SectionPlan(
                title="Disciplina de respuesta",
                content=ResearchPromptTemplates.RESPONSE_DISCIPLINE,
                kind=PromptSectionKind.FINAL_INSTRUCTIONS,
                audience=PromptAudience.SYSTEM,
                order=110,
            ),
            _SectionPlan(
                title="Instrucción final",
                content=ResearchPromptTemplates.FINAL_INSTRUCTION,
                kind=PromptSectionKind.FINAL_INSTRUCTIONS,
                audience=PromptAudience.SYSTEM,
                order=120,
            ),
        ]
        return [plan.to_section() for plan in plans]

    def build_developer_sections(
        self,
        *,
        context: PromptBuildContext,
        profile: ResearchPromptProfile,
        methods: Sequence[ResearchMethod],
    ) -> list[PromptSection]:
        if not self.include_developer_prompt:
            return []

        plans = [
            _SectionPlan(
                title="Prioridad operativa",
                content=self._build_operational_priority(context),
                kind=PromptSectionKind.WORKFLOW,
                audience=PromptAudience.DEVELOPER,
                order=200,
            ),
            _SectionPlan(
                title="Flujo de trabajo",
                content=self._build_workflow_instruction(
                    context=context,
                    methods=methods,
                ),
                kind=PromptSectionKind.WORKFLOW,
                audience=PromptAudience.DEVELOPER,
                order=210,
            ),
            _SectionPlan(
                title="Control de incertidumbre",
                content=self._build_uncertainty_instruction(),
                kind=PromptSectionKind.VERIFICATION_POLICY,
                audience=PromptAudience.DEVELOPER,
                order=220,
            ),
            _SectionPlan(
                title="Política de publicación",
                content=self._build_publication_policy(context),
                kind=PromptSectionKind.QUALITY_POLICY,
                audience=PromptAudience.DEVELOPER,
                order=230,
            ),
            _SectionPlan(
                title="Restricciones de formato",
                content=self._build_format_policy(),
                kind=PromptSectionKind.OUTPUT_CONTRACT,
                audience=PromptAudience.DEVELOPER,
                order=240,
            ),
        ]
        return [plan.to_section() for plan in plans]

    def build_user_sections(
        self,
        *,
        context: PromptBuildContext,
        profile: ResearchPromptProfile,
        methods: Sequence[ResearchMethod],
        contract: Mapping[str, Any],
    ) -> list[PromptSection]:
        sections: list[PromptSection] = [
            PromptSection(
                title="Proyecto",
                content=self._build_project_context(context, profile),
                kind=PromptSectionKind.CONTEXT,
                audience=PromptAudience.USER,
                order=300,
            ),
            PromptSection(
                title="Objetivo de investigación",
                content=context.objective,
                kind=PromptSectionKind.OBJECTIVES,
                audience=PromptAudience.USER,
                order=310,
            ),
        ]

        objectives_content = self._build_objectives_section(context)
        if objectives_content:
            sections.append(
                PromptSection(
                    title="Objetivos específicos",
                    content=objectives_content,
                    kind=PromptSectionKind.OBJECTIVES,
                    audience=PromptAudience.USER,
                    order=320,
                )
            )

        questions_content = self._build_questions_section(context)
        if questions_content:
            sections.append(
                PromptSection(
                    title="Preguntas de investigación",
                    content=questions_content,
                    kind=PromptSectionKind.QUESTIONS,
                    audience=PromptAudience.USER,
                    order=330,
                )
            )

        constraints_content = self._build_constraints_section(context)
        if constraints_content:
            sections.append(
                PromptSection(
                    title="Restricciones",
                    content=constraints_content,
                    kind=PromptSectionKind.CONSTRAINTS,
                    audience=PromptAudience.USER,
                    order=340,
                )
            )

        plan_content = self._build_plan_section(context)
        if plan_content:
            sections.append(
                PromptSection(
                    title="Plan existente",
                    content=plan_content,
                    kind=PromptSectionKind.TASKS,
                    audience=PromptAudience.USER,
                    order=350,
                )
            )

        supplied_material = self._build_supplied_material_section(context)
        if supplied_material:
            sections.append(
                PromptSection(
                    title="Material proporcionado",
                    content=supplied_material,
                    kind=PromptSectionKind.INPUT_DATA,
                    audience=PromptAudience.USER,
                    order=360,
                )
            )

        additional_context = self._build_additional_context_section(context)
        if additional_context:
            sections.append(
                PromptSection(
                    title="Contexto adicional",
                    content=additional_context,
                    kind=PromptSectionKind.CONTEXT,
                    audience=PromptAudience.USER,
                    order=370,
                )
            )

        exclusions = self._build_exclusions_section(context)
        if exclusions:
            sections.append(
                PromptSection(
                    title="Exclusiones",
                    content=exclusions,
                    kind=PromptSectionKind.CONSTRAINTS,
                    audience=PromptAudience.USER,
                    order=380,
                )
            )

        outputs = self._build_outputs_section(context)
        if outputs:
            sections.append(
                PromptSection(
                    title="Entregables obligatorios",
                    content=outputs,
                    kind=PromptSectionKind.OUTPUT_CONTRACT,
                    audience=PromptAudience.USER,
                    order=390,
                )
            )

        sections.append(
            PromptSection(
                title="Métodos aplicables",
                content=self._build_methods_instruction(methods),
                kind=PromptSectionKind.METHODOLOGY,
                audience=PromptAudience.USER,
                order=400,
            )
        )

        if self.include_contract_in_user_prompt:
            sections.append(
                PromptSection(
                    title="Contrato JSON de salida",
                    content=safe_json_dumps(
                        contract,
                        indent=2,
                        ensure_ascii=False,
                    ),
                    kind=PromptSectionKind.OUTPUT_CONTRACT,
                    audience=PromptAudience.USER,
                    order=410,
                )
            )

        sections.append(
            PromptSection(
                title="Instrucción de ejecución",
                content=self._build_execution_instruction(context),
                kind=PromptSectionKind.FINAL_INSTRUCTIONS,
                audience=PromptAudience.USER,
                order=420,
            )
        )

        return sections

    def build_output_contract(
        self,
        *,
        context: PromptBuildContext,
        profile: ResearchPromptProfile,
        methods: Sequence[ResearchMethod],
    ) -> dict[str, Any]:
        contract = ResearchPromptContract.base_contract()
        properties = contract["properties"]

        properties["project_id"]["const"] = context.project_id

        properties["research_plan"] = {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "plan_id",
                "topic",
                "objective",
                "scope",
                "methods",
                "questions",
                "tasks",
                "success_criteria",
            ],
            "properties": {
                "plan_id": {"type": "string", "minLength": 1},
                "topic": {"type": "string", "minLength": 1},
                "objective": {"type": "string", "minLength": 1},
                "scope": {
                    "type": "string",
                    "enum": [item.value for item in ResearchScope],
                },
                "methods": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": [item.value for item in ResearchMethod],
                    },
                    "minItems": 1,
                },
                "questions": {
                    "type": "array",
                    "items": {"type": "object"},
                },
                "tasks": {
                    "type": "array",
                    "items": {"type": "object"},
                },
                "success_criteria": {
                    "type": "array",
                    "items": {"type": "string"},
                },
            },
        }

        properties["sources"] = self._source_schema()
        properties["evidence"] = self._evidence_schema()
        properties["claims"] = self._claim_schema()
        properties["verifications"] = self._verification_schema()
        properties["findings"] = self._finding_schema()
        properties["contradictions"] = self._contradiction_schema()
        properties["knowledge_gaps"] = self._gap_schema()
        properties["hypotheses"] = self._hypothesis_schema()
        properties["metrics"] = self._metrics_schema()
        properties["issues"] = self._issue_schema()
        properties["artifacts"] = self._artifact_schema()

        contract["x-cips"] = {
            "profile": profile.value,
            "selected_methods": [method.value for method in methods],
            "language": context.language,
            "citation_style": (
                context.configuration.default_citation_style.value
            ),
            "strictness": self.strictness.value,
            "output_mode": self.output_mode.value,
        }

        ResearchPromptValidator.validate_contract(contract)
        return contract

    @staticmethod
    def render_sections(
        sections: Sequence[PromptSection],
        *,
        heading_level: int = 2,
    ) -> str:
        ResearchPromptValidator.validate_sections(sections)
        rendered = [
            section.render(
                include_heading=True,
                heading_level=heading_level,
            )
            for section in sorted(
                sections,
                key=lambda item: (item.order, item.section_id),
            )
            if section.enabled
        ]
        return "\n\n".join(item for item in rendered if item).strip()

    def _build_profile_instruction(
        self,
        profile: ResearchPromptProfile,
    ) -> str:
        descriptions = {
            ResearchPromptProfile.GENERAL:
                "Investigación multidisciplinaria general con validación factual.",
            ResearchPromptProfile.FACT_CHECKING:
                "Verificación rigurosa de afirmaciones y detección de errores.",
            ResearchPromptProfile.LEGAL:
                "Investigación jurídica con atención a jurisdicción, vigencia y fuente oficial.",
            ResearchPromptProfile.TECHNICAL:
                "Validación técnica basada en documentación primaria y estándares.",
            ResearchPromptProfile.SCIENTIFIC:
                "Síntesis de evidencia científica con jerarquía metodológica.",
            ResearchPromptProfile.MARKET:
                "Investigación de mercado orientada a demanda, tamaño y oportunidad.",
            ResearchPromptProfile.COMPETITOR:
                "Análisis competitivo documentado y comparable.",
            ResearchPromptProfile.TREND:
                "Análisis de tendencias con control de actualidad y volatilidad.",
            ResearchPromptProfile.AUDIENCE:
                "Investigación de audiencia, necesidades y comportamiento.",
            ResearchPromptProfile.MONETIZATION:
                "Investigación de modelos de ingresos, viabilidad y monetización.",
            ResearchPromptProfile.CONTENT:
                "Investigación editorial para producir contenido confiable y relevante.",
        }
        return (
            f"Perfil seleccionado: {profile.value}\n\n"
            f"{descriptions[profile]}"
        )

    @staticmethod
    def _build_methods_instruction(
        methods: Sequence[ResearchMethod],
    ) -> str:
        if not methods:
            return "No se preseleccionaron métodos; define los mínimos necesarios."

        lines = [
            f"{index}. {method.value}"
            for index, method in enumerate(methods, start=1)
        ]
        return (
            "Aplica los siguientes métodos, ajustándolos al alcance y riesgo:\n\n"
            + "\n".join(lines)
        )

    def _build_quality_policy(
        self,
        context: PromptBuildContext,
    ) -> str:
        config = context.configuration
        return dedent(
            f"""
            {ResearchPromptTemplates.QUALITY_GATES}

            Umbrales configurados:

            - Credibilidad mínima de fuente: {config.minimum_source_credibility_score}/10.
            - Calidad mínima de evidencia: {config.minimum_evidence_quality_score}/10.
            - Confianza factual mínima: {config.minimum_fact_confidence_score}/10.
            - Completitud mínima: {config.minimum_completeness_score}/10.
            - Trazabilidad mínima: {config.minimum_traceability_score}/10.
            - Calidad global mínima: {config.minimum_overall_quality_score}/10.
            - Fuentes autoritativas mínimas: {config.minimum_authoritative_sources}.
            - Fuentes primarias mínimas: {config.minimum_primary_sources}.
            - Fuentes por afirmación crítica: {config.minimum_sources_per_critical_claim}.
            """
        ).strip()

    def _build_operational_priority(
        self,
        context: PromptBuildContext,
    ) -> str:
        return dedent(
            f"""
            Prioridad del proyecto: {context.priority.value}.

            Orden de prioridad:
            1. Exactitud y trazabilidad.
            2. Cumplimiento de restricciones.
            3. Cobertura de preguntas obligatorias.
            4. Actualidad y calidad de fuentes.
            5. Utilidad para producción de contenido.
            6. Eficiencia operativa.
            """
        ).strip()

    def _build_workflow_instruction(
        self,
        *,
        context: PromptBuildContext,
        methods: Sequence[ResearchMethod],
    ) -> str:
        return dedent(
            f"""
            Ejecuta el flujo:

            1. Valida el objetivo, alcance y restricciones.
            2. Normaliza las preguntas existentes.
            3. Agrega preguntas faltantes únicamente cuando sean necesarias.
            4. Diseña tareas y dependencias.
            5. Aplica los métodos: {", ".join(method.value for method in methods)}.
            6. Registra fuentes antes de registrar evidencia.
            7. Registra evidencia antes de verificar afirmaciones.
            8. Analiza contradicciones y vacíos.
            9. Produce hallazgos y métricas.
            10. Determina de forma conservadora el estado de publicación.
            """
        ).strip()

    @staticmethod
    def _build_uncertainty_instruction() -> str:
        return dedent(
            """
            Usa una política explícita de incertidumbre:

            - No confundas ausencia de evidencia con evidencia de ausencia.
            - No extrapoles más allá de población, periodo o jurisdicción.
            - Reduce la confianza cuando la evidencia sea indirecta.
            - Registra contradicciones aunque no puedas resolverlas.
            - Mantén como hipótesis aquello que no pueda verificarse.
            - Usa INCONCLUSIVE cuando la evidencia no permita concluir.
            """
        ).strip()

    def _build_publication_policy(
        self,
        context: PromptBuildContext,
    ) -> str:
        config = context.configuration
        return dedent(
            f"""
            Solo declara publication_safe=true cuando:

            - no existan bloqueos críticos;
            - las afirmaciones materiales estén verificadas;
            - los hallazgos publicables estén fact_checked;
            - la trazabilidad cumpla el umbral;
            - la calidad global cumpla el umbral;
            - se respeten jurisdicción y vigencia;
            - la revisión humana sea completada o no resulte obligatoria.

            Revisión humana requerida: {str(config.require_human_review).lower()}.
            Fact-check para publicación: {str(config.require_fact_check_for_publication).lower()}.
            Detener ante vacío bloqueante: {str(config.stop_on_blocking_gap).lower()}.
            Detener ante contradicción crítica: {str(config.stop_on_critical_contradiction).lower()}.
            """
        ).strip()

    def _build_format_policy(self) -> str:
        if self.output_mode is PromptOutputMode.JSON_ONLY:
            format_instruction = (
                "Devuelve únicamente un objeto JSON válido. "
                "No uses bloques Markdown ni texto fuera del JSON."
            )
        elif self.output_mode is PromptOutputMode.JSON_AND_MARKDOWN:
            format_instruction = (
                "Devuelve primero el objeto JSON y después un resumen Markdown."
            )
        elif self.output_mode is PromptOutputMode.MARKDOWN_ONLY:
            format_instruction = (
                "Devuelve un informe Markdown estructurado."
            )
        else:
            format_instruction = (
                "Devuelve texto estructurado conforme a las secciones solicitadas."
            )

        return dedent(
            f"""
            {format_instruction}

            Usa UTF-8, identificadores consistentes y valores compatibles con
            las enumeraciones del contrato. No agregues comentarios dentro del JSON.
            """
        ).strip()

    def _build_project_context(
        self,
        context: PromptBuildContext,
        profile: ResearchPromptProfile,
    ) -> str:
        items = [
            f"Project ID: {context.project_id}",
            f"Tema: {context.topic}",
            f"Perfil: {profile.value}",
            f"Idioma: {context.language}",
            f"Alcance: {context.research_scope.value}",
            f"Prioridad: {context.priority.value}",
        ]

        if context.audience:
            items.append(f"Audiencia: {context.audience}")
        if context.content_format:
            items.append(f"Formato de contenido: {context.content_format}")
        if context.platform:
            items.append(f"Plataforma: {context.platform}")
        if context.jurisdiction:
            items.append(
                "Jurisdicción: " + ", ".join(context.jurisdiction)
            )
        if context.deadline:
            items.append(f"Fecha límite: {context.deadline}")

        return "\n".join(f"- {item}" for item in items)

    @staticmethod
    def _build_objectives_section(
        context: PromptBuildContext,
    ) -> str:
        objectives = list(context.objectives)
        if not objectives and context.plan is not None:
            objectives = list(context.plan.objectives)

        if not objectives:
            return ""

        lines: list[str] = []
        for index, objective in enumerate(objectives, start=1):
            lines.append(
                f"{index}. [{objective.priority.value}] {objective.statement}"
            )
            if objective.success_criteria:
                for criterion in objective.success_criteria:
                    lines.append(f"   - Criterio: {criterion}")

        return "\n".join(lines)

    @staticmethod
    def _build_questions_section(
        context: PromptBuildContext,
    ) -> str:
        questions = list(context.questions)
        if not questions and context.plan is not None:
            questions = list(context.plan.questions)

        if not questions:
            return ""

        lines: list[str] = []
        for index, question in enumerate(questions, start=1):
            lines.append(
                f"{index}. [{question.priority.value}] "
                f"[{question.question_type.value}] {question.question}"
            )
            if question.rationale:
                lines.append(f"   - Razón: {question.rationale}")
            if question.source_requirements:
                lines.append(
                    "   - Fuentes requeridas: "
                    + "; ".join(question.source_requirements)
                )

        return "\n".join(lines)

    @staticmethod
    def _build_constraints_section(
        context: PromptBuildContext,
    ) -> str:
        constraints = list(context.constraints)
        if not constraints and context.plan is not None:
            constraints = list(context.plan.constraints)

        if not constraints:
            return ""

        lines: list[str] = []
        for index, constraint in enumerate(constraints, start=1):
            qualifier = "OBLIGATORIA" if constraint.mandatory else "PREFERENTE"
            lines.append(
                f"{index}. [{qualifier}] [{constraint.category}] "
                f"{constraint.description}"
            )
            if constraint.impact:
                lines.append(f"   - Impacto: {constraint.impact}")
            if constraint.mitigation:
                lines.append(f"   - Mitigación: {constraint.mitigation}")

        return "\n".join(lines)

    def _build_plan_section(
        self,
        context: PromptBuildContext,
    ) -> str:
        if context.plan is None:
            return ""

        if self.include_full_supplied_material:
            return safe_json_dumps(
                context.plan.to_dict(),
                indent=2,
                ensure_ascii=False,
            )

        return dedent(
            f"""
            Plan ID: {context.plan.plan_id}
            Estado: {context.plan.status.value}
            Métodos: {", ".join(method.value for method in context.plan.methods)}
            Total de tareas: {len(context.plan.tasks)}
            """
        ).strip()

    def _build_supplied_material_section(
        self,
        context: PromptBuildContext,
    ) -> str:
        if not context.has_supplied_material:
            return ""

        payload: dict[str, Any] = {}

        if context.supplied_sources:
            payload["sources"] = [
                item.to_dict() for item in context.supplied_sources
            ]

        if context.supplied_evidence:
            payload["evidence"] = [
                item.to_dict() for item in context.supplied_evidence
            ]

        if context.supplied_claims:
            payload["claims"] = [
                item.to_dict() for item in context.supplied_claims
            ]

        if context.supplied_findings:
            payload["findings"] = [
                item.to_dict() for item in context.supplied_findings
            ]

        if context.supplied_hypotheses:
            payload["hypotheses"] = [
                item.to_dict() for item in context.supplied_hypotheses
            ]

        if context.supplied_gaps:
            payload["knowledge_gaps"] = [
                item.to_dict() for item in context.supplied_gaps
            ]

        if self.include_full_supplied_material:
            return safe_json_dumps(
                payload,
                indent=2,
                ensure_ascii=False,
            )

        summary = {
            key: len(value)
            for key, value in payload.items()
            if isinstance(value, list)
        }
        return safe_json_dumps(
            summary,
            indent=2,
            ensure_ascii=False,
        )

    @staticmethod
    def _build_additional_context_section(
        context: PromptBuildContext,
    ) -> str:
        payload: dict[str, Any] = {}

        if context.additional_context:
            payload["additional_context"] = context.additional_context
        if context.human_notes:
            payload["human_notes"] = context.human_notes

        if not payload:
            return ""

        return safe_json_dumps(
            payload,
            indent=2,
            ensure_ascii=False,
        )

    @staticmethod
    def _build_exclusions_section(
        context: PromptBuildContext,
    ) -> str:
        if not context.exclusions:
            return ""
        return "\n".join(
            f"- {item}" for item in context.exclusions
        )

    @staticmethod
    def _build_outputs_section(
        context: PromptBuildContext,
    ) -> str:
        outputs = [
            *context.configuration.required_artifacts,
            *context.mandatory_outputs,
        ]
        outputs = normalize_string_list(outputs)

        if not outputs:
            return ""

        return "\n".join(
            f"- {item}" for item in outputs
        )

    def _build_execution_instruction(
        self,
        context: PromptBuildContext,
    ) -> str:
        strict_note = {
            PromptStrictness.FLEXIBLE:
                "Puedes adaptar el procedimiento sin romper el contrato.",
            PromptStrictness.STANDARD:
                "Sigue el procedimiento y documenta desviaciones.",
            PromptStrictness.STRICT:
                "No omitas campos ni reglas del contrato.",
            PromptStrictness.AUDIT:
                "Documenta toda decisión relevante para auditoría.",
        }[self.strictness]

        return dedent(
            f"""
            Realiza la investigación del proyecto {context.project_id}.

            {strict_note}

            No inventes datos. Cuando no sea posible verificar una afirmación,
            registra el estado adecuado, explica la limitación y conserva la
            trazabilidad de lo que sí pudo establecerse.
            """
        ).strip()

    @staticmethod
    def _source_schema() -> dict[str, Any]:
        return {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "source_id",
                    "title",
                    "source_type",
                    "credibility",
                    "credibility_score",
                    "relevance_score",
                    "accessed_at",
                    "limitations",
                ],
                "properties": {
                    "source_id": {"type": "string", "minLength": 1},
                    "title": {"type": "string", "minLength": 1},
                    "source_type": {
                        "type": "string",
                        "enum": [item.value for item in SourceType],
                    },
                    "authors": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "organization": {"type": "string"},
                    "publisher": {"type": "string"},
                    "publication_date": {"type": "string"},
                    "accessed_at": {"type": "string"},
                    "url": {"type": "string"},
                    "doi": {"type": "string"},
                    "jurisdiction": {"type": "string"},
                    "credibility": {
                        "type": "string",
                        "enum": [item.value for item in SourceCredibility],
                    },
                    "credibility_score": {
                        "type": ["number", "null"],
                        "minimum": 0,
                        "maximum": 10,
                    },
                    "relevance_score": {
                        "type": ["number", "null"],
                        "minimum": 0,
                        "maximum": 10,
                    },
                    "primary_source": {"type": "boolean"},
                    "peer_reviewed": {"type": "boolean"},
                    "official": {"type": "boolean"},
                    "summary": {"type": "string"},
                    "limitations": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
            },
        }

    @staticmethod
    def _evidence_schema() -> dict[str, Any]:
        return {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "evidence_id",
                    "source_id",
                    "content",
                    "evidence_type",
                    "direction",
                    "strength",
                    "confidence_score",
                    "question_ids",
                    "claim_ids",
                    "limitations",
                ],
                "properties": {
                    "evidence_id": {"type": "string", "minLength": 1},
                    "source_id": {"type": "string", "minLength": 1},
                    "content": {"type": "string", "minLength": 1},
                    "evidence_type": {
                        "type": "string",
                        "enum": [item.value for item in EvidenceType],
                    },
                    "direction": {
                        "type": "string",
                        "enum": [item.value for item in EvidenceDirection],
                    },
                    "strength": {
                        "type": "string",
                        "enum": [item.value for item in EvidenceStrength],
                    },
                    "locator": {"type": "string"},
                    "context": {"type": "string"},
                    "interpretation": {"type": "string"},
                    "confidence_score": {
                        "type": ["number", "null"],
                        "minimum": 0,
                        "maximum": 10,
                    },
                    "question_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "claim_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "limitations": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
            },
        }

    @staticmethod
    def _claim_schema() -> dict[str, Any]:
        return {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "claim_id",
                    "statement",
                    "claim_type",
                    "status",
                    "importance",
                    "evidence_ids",
                    "supporting_source_ids",
                    "contradicting_source_ids",
                    "confidence_score",
                    "publication_safe",
                ],
                "properties": {
                    "claim_id": {"type": "string", "minLength": 1},
                    "statement": {"type": "string", "minLength": 1},
                    "claim_type": {
                        "type": "string",
                        "enum": [item.value for item in ClaimType],
                    },
                    "status": {
                        "type": "string",
                        "enum": [item.value for item in ClaimStatus],
                    },
                    "importance": {
                        "type": "string",
                        "enum": [item.value for item in FindingImportance],
                    },
                    "time_sensitive": {"type": "boolean"},
                    "jurisdiction": {"type": "string"},
                    "evidence_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "supporting_source_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "contradicting_source_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "confidence_score": {
                        "type": ["number", "null"],
                        "minimum": 0,
                        "maximum": 10,
                    },
                    "publication_safe": {"type": "boolean"},
                    "requires_attribution": {"type": "boolean"},
                    "attribution_text": {"type": "string"},
                    "notes": {"type": "string"},
                },
            },
        }

    @staticmethod
    def _verification_schema() -> dict[str, Any]:
        return {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "verification_id",
                    "claim_id",
                    "status",
                    "conclusion",
                    "supporting_evidence_ids",
                    "contradicting_evidence_ids",
                    "source_ids",
                    "confidence_score",
                ],
                "properties": {
                    "verification_id": {"type": "string", "minLength": 1},
                    "claim_id": {"type": "string", "minLength": 1},
                    "status": {
                        "type": "string",
                        "enum": [item.value for item in VerificationStatus],
                    },
                    "conclusion": {"type": "string"},
                    "rationale": {"type": "string"},
                    "supporting_evidence_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "contradicting_evidence_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "source_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "confidence_score": {
                        "type": ["number", "null"],
                        "minimum": 0,
                        "maximum": 10,
                    },
                    "publication_recommendation": {"type": "string"},
                    "correction": {"type": "string"},
                    "limitations": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
            },
        }

    @staticmethod
    def _finding_schema() -> dict[str, Any]:
        return {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "finding_id",
                    "title",
                    "summary",
                    "importance",
                    "evidence_ids",
                    "source_ids",
                    "claim_ids",
                    "confidence_score",
                    "fact_checked",
                    "publication_safe",
                    "limitations",
                ],
                "properties": {
                    "finding_id": {"type": "string", "minLength": 1},
                    "title": {"type": "string", "minLength": 1},
                    "summary": {"type": "string", "minLength": 1},
                    "importance": {
                        "type": "string",
                        "enum": [item.value for item in FindingImportance],
                    },
                    "category": {"type": "string"},
                    "detail": {"type": "string"},
                    "implications": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "recommendations": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "evidence_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "source_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "claim_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "confidence_score": {
                        "type": ["number", "null"],
                        "minimum": 0,
                        "maximum": 10,
                    },
                    "fact_checked": {"type": "boolean"},
                    "publication_safe": {"type": "boolean"},
                    "limitations": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
            },
        }

    @staticmethod
    def _contradiction_schema() -> dict[str, Any]:
        return {
            "type": "array",
            "items": {
                "type": "object",
                "required": [
                    "contradiction_id",
                    "description",
                    "source_ids",
                    "evidence_ids",
                    "claim_ids",
                    "severity",
                    "resolved",
                    "resolution",
                    "blocking",
                ],
                "properties": {
                    "contradiction_id": {"type": "string"},
                    "description": {"type": "string"},
                    "source_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 2,
                    },
                    "evidence_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "claim_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "severity": {
                        "type": "string",
                        "enum": ["low", "medium", "high", "critical"],
                    },
                    "resolved": {"type": "boolean"},
                    "resolution": {"type": "string"},
                    "blocking": {"type": "boolean"},
                },
            },
        }

    @staticmethod
    def _gap_schema() -> dict[str, Any]:
        return {
            "type": "array",
            "items": {
                "type": "object",
                "required": [
                    "gap_id",
                    "description",
                    "severity",
                    "question_ids",
                    "claim_ids",
                    "missing_information",
                    "impact",
                    "resolution_strategy",
                    "resolved",
                    "blocking",
                ],
                "properties": {
                    "gap_id": {"type": "string"},
                    "description": {"type": "string"},
                    "severity": {
                        "type": "string",
                        "enum": [item.value for item in GapSeverity],
                    },
                    "question_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "claim_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "missing_information": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "impact": {"type": "string"},
                    "resolution_strategy": {"type": "string"},
                    "resolved": {"type": "boolean"},
                    "resolution": {"type": "string"},
                    "blocking": {"type": "boolean"},
                },
            },
        }

    @staticmethod
    def _hypothesis_schema() -> dict[str, Any]:
        return {
            "type": "array",
            "items": {
                "type": "object",
                "required": [
                    "hypothesis_id",
                    "statement",
                    "status",
                    "supporting_evidence_ids",
                    "contradicting_evidence_ids",
                    "confidence_score",
                    "publication_allowed",
                    "publication_label",
                ],
                "properties": {
                    "hypothesis_id": {"type": "string"},
                    "statement": {"type": "string"},
                    "status": {
                        "type": "string",
                        "enum": [
                            item.value
                            for item in ResearchHypothesis.__dataclass_fields__[
                                "status"
                            ].default.__class__
                        ],
                    },
                    "supporting_evidence_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "contradicting_evidence_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "confidence_score": {
                        "type": ["number", "null"],
                        "minimum": 0,
                        "maximum": 10,
                    },
                    "publication_allowed": {"type": "boolean"},
                    "publication_label": {"type": "string"},
                },
            },
        }

    @staticmethod
    def _metrics_schema() -> dict[str, Any]:
        return {
            "type": "object",
            "required": [
                "total_questions",
                "answered_questions",
                "total_sources",
                "total_evidence_items",
                "total_claims",
                "verified_claims",
                "total_findings",
                "knowledge_gaps",
                "contradictions",
                "source_quality_score",
                "evidence_quality_score",
                "factual_confidence_score",
                "completeness_score",
                "traceability_score",
                "overall_quality_score",
            ],
            "properties": {
                "total_questions": {"type": "integer", "minimum": 0},
                "answered_questions": {"type": "integer", "minimum": 0},
                "total_sources": {"type": "integer", "minimum": 0},
                "total_evidence_items": {"type": "integer", "minimum": 0},
                "total_claims": {"type": "integer", "minimum": 0},
                "verified_claims": {"type": "integer", "minimum": 0},
                "total_findings": {"type": "integer", "minimum": 0},
                "knowledge_gaps": {"type": "integer", "minimum": 0},
                "contradictions": {"type": "integer", "minimum": 0},
                "source_quality_score": {
                    "type": ["number", "null"],
                    "minimum": 0,
                    "maximum": 10,
                },
                "evidence_quality_score": {
                    "type": ["number", "null"],
                    "minimum": 0,
                    "maximum": 10,
                },
                "factual_confidence_score": {
                    "type": ["number", "null"],
                    "minimum": 0,
                    "maximum": 10,
                },
                "completeness_score": {
                    "type": ["number", "null"],
                    "minimum": 0,
                    "maximum": 10,
                },
                "traceability_score": {
                    "type": ["number", "null"],
                    "minimum": 0,
                    "maximum": 10,
                },
                "overall_quality_score": {
                    "type": ["number", "null"],
                    "minimum": 0,
                    "maximum": 10,
                },
            },
        }

    @staticmethod
    def _issue_schema() -> dict[str, Any]:
        return {
            "type": "array",
            "items": {
                "type": "object",
                "required": [
                    "issue_id",
                    "issue_type",
                    "message",
                    "risk_level",
                    "blocking",
                    "recommended_action",
                    "resolved",
                ],
                "properties": {
                    "issue_id": {"type": "string"},
                    "issue_type": {"type": "string"},
                    "message": {"type": "string"},
                    "risk_level": {
                        "type": "string",
                        "enum": [
                            "informational",
                            "low",
                            "medium",
                            "high",
                            "critical",
                        ],
                    },
                    "blocking": {"type": "boolean"},
                    "recommended_action": {"type": "string"},
                    "resolved": {"type": "boolean"},
                    "resolution": {"type": "string"},
                },
            },
        }

    @staticmethod
    def _artifact_schema() -> dict[str, Any]:
        return {
            "type": "array",
            "items": {
                "type": "object",
                "required": [
                    "artifact_id",
                    "name",
                    "artifact_type",
                    "path",
                    "description",
                    "approved",
                ],
                "properties": {
                    "artifact_id": {"type": "string"},
                    "name": {"type": "string"},
                    "artifact_type": {"type": "string"},
                    "path": {"type": "string"},
                    "description": {"type": "string"},
                    "approved": {"type": "boolean"},
                },
            },
        }


