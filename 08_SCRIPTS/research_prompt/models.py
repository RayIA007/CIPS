"""Modelos internos de prompts y contexto."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

try:
    from research_director_models import (
        RESEARCH_MODELS_VERSION,
        FactClaim,
        KnowledgeGap,
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
        generate_id,
        utc_now_iso,
    )
except ImportError:  # pragma: no cover
    from ..research_director_models import (
        RESEARCH_MODELS_VERSION,
        FactClaim,
        KnowledgeGap,
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
        generate_id,
        utc_now_iso,
    )

from .common import (
    DEFAULT_MAX_SECTION_CHARS,
    DEFAULT_MAX_TOTAL_CHARS,
    DEFAULT_PROMPT_LANGUAGE,
    DEFAULT_SCHEMA_VERSION,
    RESEARCH_PROMPT_BUILDER_VERSION,
    PromptAudience,
    PromptOutputMode,
    PromptSectionKind,
    PromptStrictness,
    ResearchPromptValidationError,
    _enum,
    _mapping,
    _serialize,
    normalize_string_list,
    normalize_text,
    stable_hash,
)

@dataclass(slots=True)
class PromptSection:
    title: str
    content: str
    kind: PromptSectionKind = PromptSectionKind.CUSTOM
    audience: PromptAudience = PromptAudience.SYSTEM
    section_id: str = field(default_factory=lambda: generate_id("psec"))
    order: int = 0
    required: bool = True
    enabled: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.title = normalize_text(self.title, field_name="title", required=True)
        self.content = normalize_text(self.content, field_name="content", required=self.required)
        self.kind = _enum(self.kind, PromptSectionKind, "kind")
        self.audience = _enum(self.audience, PromptAudience, "audience")
        self.section_id = normalize_text(self.section_id, field_name="section_id", required=True)
        self.order = int(self.order)
        if self.order < 0:
            raise ResearchPromptValidationError("'order' no puede ser negativo.")
        self.metadata = _mapping(self.metadata, "metadata")
        if len(self.content) > DEFAULT_MAX_SECTION_CHARS:
            raise ResearchPromptValidationError(f"La sección '{self.title}' excede el límite.")

    def render(self, *, heading_level: int = 2, include_heading: bool = True) -> str:
        if not self.enabled:
            return ""
        if not include_heading:
            return self.content.strip()
        level = max(1, min(int(heading_level), 6))
        return f"{'#' * level} {self.title}\n\n{self.content}".strip()

    def to_dict(self) -> dict[str, Any]:
        return _serialize(self)


@dataclass(slots=True)
class PromptPackage:
    system_prompt: str
    user_prompt: str
    package_id: str = field(default_factory=lambda: generate_id("ppkg"))
    developer_prompt: str = ""
    output_contract: dict[str, Any] = field(default_factory=dict)
    sections: list[PromptSection] = field(default_factory=list)
    language: str = DEFAULT_PROMPT_LANGUAGE
    output_mode: PromptOutputMode = PromptOutputMode.JSON_ONLY
    strictness: PromptStrictness = PromptStrictness.STRICT
    schema_version: str = DEFAULT_SCHEMA_VERSION
    builder_version: str = RESEARCH_PROMPT_BUILDER_VERSION
    model_version: str = RESEARCH_MODELS_VERSION
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now_iso)

    def __post_init__(self) -> None:
        self.system_prompt = normalize_text(self.system_prompt, field_name="system_prompt", required=True)
        self.user_prompt = normalize_text(self.user_prompt, field_name="user_prompt", required=True)
        self.developer_prompt = normalize_text(self.developer_prompt)
        self.package_id = normalize_text(self.package_id, field_name="package_id", required=True)
        self.output_contract = _mapping(self.output_contract, "output_contract")
        self.sections = list(self.sections or [])
        if not all(isinstance(item, PromptSection) for item in self.sections):
            raise ResearchPromptValidationError("'sections' debe contener PromptSection.")
        self.language = normalize_text(self.language, field_name="language", required=True)
        self.output_mode = _enum(self.output_mode, PromptOutputMode, "output_mode")
        self.strictness = _enum(self.strictness, PromptStrictness, "strictness")
        self.metadata = _mapping(self.metadata, "metadata")
        if self.total_characters > DEFAULT_MAX_TOTAL_CHARS:
            raise ResearchPromptValidationError("El paquete excede el límite total.")
        ids = [item.section_id for item in self.sections]
        if len(ids) != len(set(ids)):
            raise ResearchPromptValidationError("Existen section_id duplicados.")

    @property
    def total_characters(self) -> int:
        return len(self.system_prompt) + len(self.developer_prompt) + len(self.user_prompt)

    @property
    def fingerprint(self) -> str:
        return stable_hash({
            "system_prompt": self.system_prompt,
            "developer_prompt": self.developer_prompt,
            "user_prompt": self.user_prompt,
            "output_contract": self.output_contract,
            "language": self.language,
            "output_mode": self.output_mode.value,
            "strictness": self.strictness.value,
        })

    def to_messages(self) -> list[dict[str, str]]:
        messages = [{"role": "system", "content": self.system_prompt}]
        if self.developer_prompt:
            messages.append({"role": "developer", "content": self.developer_prompt})
        messages.append({"role": "user", "content": self.user_prompt})
        return messages

    def to_dict(self) -> dict[str, Any]:
        payload = _serialize(self)
        payload["fingerprint"] = self.fingerprint
        payload["total_characters"] = self.total_characters
        return payload


@dataclass(slots=True)
class PromptBuildContext:
    project_id: str
    topic: str
    objective: str
    context_id: str = field(default_factory=lambda: generate_id("pctx"))
    audience: str = ""
    content_format: str = ""
    platform: str = ""
    language: str = DEFAULT_PROMPT_LANGUAGE
    jurisdiction: list[str] = field(default_factory=list)
    deadline: str = ""
    priority: ResearchPriority = ResearchPriority.NORMAL
    research_scope: ResearchScope = ResearchScope.EXPLORATORY
    preferred_methods: list[ResearchMethod] = field(default_factory=list)
    objectives: list[ResearchObjective] = field(default_factory=list)
    questions: list[ResearchQuestion] = field(default_factory=list)
    constraints: list[ResearchConstraint] = field(default_factory=list)
    plan: Optional[ResearchPlan] = None
    configuration: ResearchConfiguration = field(default_factory=ResearchConfiguration)
    supplied_sources: list[ResearchSource] = field(default_factory=list)
    supplied_evidence: list[ResearchEvidence] = field(default_factory=list)
    supplied_claims: list[FactClaim] = field(default_factory=list)
    supplied_findings: list[ResearchFinding] = field(default_factory=list)
    supplied_hypotheses: list[ResearchHypothesis] = field(default_factory=list)
    supplied_gaps: list[KnowledgeGap] = field(default_factory=list)
    additional_context: dict[str, Any] = field(default_factory=dict)
    exclusions: list[str] = field(default_factory=list)
    mandatory_outputs: list[str] = field(default_factory=list)
    human_notes: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now_iso)

    def __post_init__(self) -> None:
        self.project_id = normalize_text(self.project_id, field_name="project_id", required=True)
        self.topic = normalize_text(self.topic, field_name="topic", required=True)
        self.objective = normalize_text(self.objective, field_name="objective", required=True)
        self.context_id = normalize_text(self.context_id, field_name="context_id", required=True)
        self.language = normalize_text(self.language, field_name="language", required=True)
        self.jurisdiction = normalize_string_list(self.jurisdiction)
        self.deadline = normalize_text(self.deadline)
        self.priority = _enum(self.priority, ResearchPriority, "priority")
        self.research_scope = _enum(self.research_scope, ResearchScope, "research_scope")
        self.preferred_methods = list(dict.fromkeys(_enum(item, ResearchMethod, "preferred_methods") for item in self.preferred_methods))
        checks = [
            (self.objectives, ResearchObjective, "objectives"),
            (self.questions, ResearchQuestion, "questions"),
            (self.constraints, ResearchConstraint, "constraints"),
            (self.supplied_sources, ResearchSource, "supplied_sources"),
            (self.supplied_evidence, ResearchEvidence, "supplied_evidence"),
            (self.supplied_claims, FactClaim, "supplied_claims"),
            (self.supplied_findings, ResearchFinding, "supplied_findings"),
            (self.supplied_hypotheses, ResearchHypothesis, "supplied_hypotheses"),
            (self.supplied_gaps, KnowledgeGap, "supplied_gaps"),
        ]
        for values, expected, name in checks:
            if not all(isinstance(item, expected) for item in values):
                raise ResearchPromptValidationError(f"'{name}' debe contener {expected.__name__}.")
        if self.plan is not None and not isinstance(self.plan, ResearchPlan):
            raise ResearchPromptValidationError("'plan' debe ser ResearchPlan o None.")
        if self.plan is not None and self.plan.project_id != self.project_id:
            raise ResearchPromptValidationError("El plan pertenece a otro proyecto.")
        if not isinstance(self.configuration, ResearchConfiguration):
            raise ResearchPromptValidationError("'configuration' debe ser ResearchConfiguration.")
        self.additional_context = _mapping(self.additional_context, "additional_context")
        self.exclusions = normalize_string_list(self.exclusions)
        self.mandatory_outputs = normalize_string_list(self.mandatory_outputs)
        self.human_notes = normalize_string_list(self.human_notes)
        self.metadata = _mapping(self.metadata, "metadata")

    @property
    def has_supplied_material(self) -> bool:
        return any((
            self.supplied_sources,
            self.supplied_evidence,
            self.supplied_claims,
            self.supplied_findings,
            self.supplied_hypotheses,
            self.supplied_gaps,
        ))

    def to_dict(self) -> dict[str, Any]:
        return _serialize(self)


