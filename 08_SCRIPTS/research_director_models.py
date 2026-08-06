"""
CIPS — Research Director Models
===============================

Modelos de dominio para el Director de Investigación del Estudio Profesional
de Producción de Contenido CIPS.

Ruta recomendada:
    08_SCRIPTS/research_director_models.py

Principios:
- Trazabilidad completa entre preguntas, fuentes, evidencia, afirmaciones,
  verificaciones y hallazgos.
- Separación explícita entre hechos, inferencias, opiniones e hipótesis.
- Evaluación reproducible de credibilidad, relevancia, actualidad y fuerza.
- Serialización JSON estable.
- Validación estricta y modelos independientes de proveedores externos.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields, is_dataclass
from datetime import datetime, timezone
from enum import Enum
import json
import math
import re
from typing import Any, Iterable, Mapping, Optional, Sequence
from uuid import uuid4


RESEARCH_MODELS_VERSION = "1.0.0"


__all__ = [
    "RESEARCH_MODELS_VERSION",
    "utc_now_iso",
    "generate_id",
    "ResearchModelError",
    "ResearchValidationError",
    "ResearchPriority",
    "ResearchStatus",
    "ResearchMethod",
    "ResearchScope",
    "QuestionType",
    "QuestionStatus",
    "SourceType",
    "SourceOrigin",
    "SourceAccessStatus",
    "SourceCredibility",
    "EvidenceType",
    "EvidenceStrength",
    "EvidenceDirection",
    "ClaimType",
    "ClaimStatus",
    "VerificationStatus",
    "ContradictionSeverity",
    "GapSeverity",
    "HypothesisStatus",
    "FindingImportance",
    "RiskLevel",
    "IssueType",
    "TaskStatus",
    "CitationStyle",
    "ArtifactType",
    "ResearchObjective",
    "ResearchQuestion",
    "ResearchConstraint",
    "ResearchSource",
    "ResearchCitation",
    "ResearchEvidence",
    "FactClaim",
    "FactVerification",
    "ResearchContradiction",
    "KnowledgeGap",
    "ResearchHypothesis",
    "ResearchFinding",
    "ResearchRisk",
    "ResearchIssue",
    "ResearchTask",
    "ResearchPlan",
    "ResearchMetrics",
    "ResearchArtifact",
    "ResearchReport",
    "ResearchResult",
    "ResearchConfiguration",
]


# =============================================================================
# Excepciones y utilidades
# =============================================================================


class ResearchModelError(ValueError):
    """Error base de los modelos del Director de Investigación."""


class ResearchValidationError(ResearchModelError):
    """El contenido de un modelo incumple una regla de validación."""


def utc_now_iso() -> str:
    """Devuelve la fecha y hora UTC actual en ISO 8601."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def generate_id(prefix: str) -> str:
    """Genera un identificador legible y suficientemente único."""
    clean = re.sub(r"[^a-z0-9]+", "_", str(prefix).strip().lower()).strip("_")
    return f"{clean or 'id'}_{uuid4().hex[:16]}"


def _clean_text(value: Any, *, field_name: str = "value") -> str:
    text = str(value or "").strip()
    if not text:
        raise ResearchValidationError(f"'{field_name}' no puede estar vacío.")
    return text


def _optional_text(value: Any) -> str:
    return str(value or "").strip()


def _clean_string_list(values: Optional[Iterable[Any]]) -> list[str]:
    if values is None:
        return []

    output: list[str] = []
    seen: set[str] = set()

    for value in values:
        text = str(value or "").strip()
        if not text:
            continue
        key = text.casefold()
        if key in seen:
            continue
        seen.add(key)
        output.append(text)

    return output


def _clean_id_list(values: Optional[Iterable[Any]]) -> list[str]:
    return _clean_string_list(values)


def _clean_mapping(value: Optional[Mapping[str, Any]]) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ResearchValidationError("Se esperaba un Mapping.")
    return dict(value)


def _validate_score(
    value: Optional[float],
    *,
    field_name: str,
    minimum: float = 0.0,
    maximum: float = 10.0,
    allow_none: bool = True,
) -> Optional[float]:
    if value is None:
        if allow_none:
            return None
        raise ResearchValidationError(f"'{field_name}' es obligatorio.")

    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ResearchValidationError(
            f"'{field_name}' debe ser numérico."
        ) from exc

    if not math.isfinite(number):
        raise ResearchValidationError(
            f"'{field_name}' debe ser un número finito."
        )
    if not minimum <= number <= maximum:
        raise ResearchValidationError(
            f"'{field_name}' debe estar entre {minimum} y {maximum}."
        )
    return number


def _validate_non_negative(
    value: float | int,
    *,
    field_name: str,
) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ResearchValidationError(
            f"'{field_name}' debe ser numérico."
        ) from exc

    if not math.isfinite(number) or number < 0:
        raise ResearchValidationError(
            f"'{field_name}' debe ser un número no negativo."
        )
    return number


def _validate_probability(
    value: Optional[float],
    *,
    field_name: str,
) -> Optional[float]:
    return _validate_score(
        value,
        field_name=field_name,
        minimum=0.0,
        maximum=1.0,
        allow_none=True,
    )


def _validate_iso(value: Optional[str], *, field_name: str) -> str:
    text = _optional_text(value)
    if not text:
        return ""

    normalized = text.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ResearchValidationError(
            f"'{field_name}' no contiene una fecha ISO 8601 válida."
        ) from exc

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed.astimezone(timezone.utc).isoformat(timespec="seconds")


def _normalize_url(value: Optional[str]) -> str:
    text = _optional_text(value)
    if not text:
        return ""
    if not re.match(r"^(https?://|doi:|urn:|file:)", text, re.IGNORECASE):
        raise ResearchValidationError(
            "La URL o identificador debe comenzar con http://, https://, "
            "doi:, urn: o file:."
        )
    return text


def _coerce_enum(value: Any, enum_type: type[Enum], field_name: str) -> Enum:
    if isinstance(value, enum_type):
        return value
    try:
        return enum_type(str(value))
    except ValueError as exc:
        allowed = ", ".join(item.value for item in enum_type)
        raise ResearchValidationError(
            f"'{field_name}' debe ser uno de: {allowed}."
        ) from exc


def _serialize(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat(timespec="seconds")
    if is_dataclass(value):
        return {
            item.name: _serialize(getattr(value, item.name))
            for item in fields(value)
        }
    if isinstance(value, Mapping):
        return {str(key): _serialize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_serialize(item) for item in value]
    return value


class SerializableModel:
    """Mixin de serialización común para todos los modelos."""

    def to_dict(self) -> dict[str, Any]:
        return _serialize(self)

    def to_json(
        self,
        *,
        indent: Optional[int] = 2,
        ensure_ascii: bool = False,
    ) -> str:
        return json.dumps(
            self.to_dict(),
            ensure_ascii=ensure_ascii,
            indent=indent,
            sort_keys=False,
        )


# =============================================================================
# Enumeraciones
# =============================================================================


class ResearchPriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class ResearchStatus(str, Enum):
    DRAFT = "draft"
    PLANNING = "planning"
    READY = "ready"
    IN_PROGRESS = "in_progress"
    PAUSED = "paused"
    IN_REVIEW = "in_review"
    COMPLETED = "completed"
    PARTIAL = "partial"
    BLOCKED = "blocked"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ResearchMethod(str, Enum):
    DESK_RESEARCH = "desk_research"
    LITERATURE_REVIEW = "literature_review"
    SYSTEMATIC_REVIEW = "systematic_review"
    RAPID_REVIEW = "rapid_review"
    DOCUMENT_ANALYSIS = "document_analysis"
    DATASET_ANALYSIS = "dataset_analysis"
    EXPERT_INTERVIEW = "expert_interview"
    USER_INTERVIEW = "user_interview"
    SURVEY = "survey"
    OBSERVATION = "observation"
    CASE_STUDY = "case_study"
    COMPARATIVE_ANALYSIS = "comparative_analysis"
    MARKET_RESEARCH = "market_research"
    COMPETITOR_RESEARCH = "competitor_research"
    TREND_ANALYSIS = "trend_analysis"
    TECHNICAL_VALIDATION = "technical_validation"
    LEGAL_RESEARCH = "legal_research"
    FACT_CHECKING = "fact_checking"
    MIXED_METHODS = "mixed_methods"
    OTHER = "other"


class ResearchScope(str, Enum):
    EXPLORATORY = "exploratory"
    DESCRIPTIVE = "descriptive"
    EXPLANATORY = "explanatory"
    EVALUATIVE = "evaluative"
    COMPARATIVE = "comparative"
    PREDICTIVE = "predictive"
    CONFIRMATORY = "confirmatory"


class QuestionType(str, Enum):
    PRIMARY = "primary"
    SECONDARY = "secondary"
    FACTUAL = "factual"
    DEFINITONAL = "definitional"
    CAUSAL = "causal"
    COMPARATIVE = "comparative"
    TEMPORAL = "temporal"
    QUANTITATIVE = "quantitative"
    QUALITATIVE = "qualitative"
    LEGAL = "legal"
    TECHNICAL = "technical"
    MARKET = "market"
    RISK = "risk"
    AUDIENCE = "audience"
    MONETIZATION = "monetization"
    OTHER = "other"


class QuestionStatus(str, Enum):
    OPEN = "open"
    IN_RESEARCH = "in_research"
    ANSWERED = "answered"
    PARTIALLY_ANSWERED = "partially_answered"
    UNANSWERED = "unanswered"
    BLOCKED = "blocked"
    DEFERRED = "deferred"
    REJECTED = "rejected"


class SourceType(str, Enum):
    PRIMARY_RESEARCH = "primary_research"
    PEER_REVIEWED_ARTICLE = "peer_reviewed_article"
    SYSTEMATIC_REVIEW = "systematic_review"
    META_ANALYSIS = "meta_analysis"
    GOVERNMENT_DOCUMENT = "government_document"
    OFFICIAL_STATISTICS = "official_statistics"
    LAW_OR_REGULATION = "law_or_regulation"
    COURT_DECISION = "court_decision"
    TECHNICAL_STANDARD = "technical_standard"
    OFFICIAL_DOCUMENTATION = "official_documentation"
    COMPANY_REPORT = "company_report"
    FINANCIAL_FILING = "financial_filing"
    INDUSTRY_REPORT = "industry_report"
    BOOK = "book"
    CONFERENCE_PAPER = "conference_paper"
    THESIS = "thesis"
    DATASET = "dataset"
    EXPERT_INTERVIEW = "expert_interview"
    NEWS_ARTICLE = "news_article"
    PROFESSIONAL_PUBLICATION = "professional_publication"
    EDUCATIONAL_RESOURCE = "educational_resource"
    BLOG = "blog"
    FORUM = "forum"
    SOCIAL_MEDIA = "social_media"
    VIDEO = "video"
    PODCAST = "podcast"
    WIKI = "wiki"
    ARCHIVE = "archive"
    INTERNAL_DOCUMENT = "internal_document"
    USER_PROVIDED = "user_provided"
    OTHER = "other"


class SourceOrigin(str, Enum):
    EXTERNAL_PUBLIC = "external_public"
    EXTERNAL_PRIVATE = "external_private"
    INTERNAL = "internal"
    USER_PROVIDED = "user_provided"
    GENERATED = "generated"


class SourceAccessStatus(str, Enum):
    AVAILABLE = "available"
    PARTIAL = "partial"
    PAYWALLED = "paywalled"
    RESTRICTED = "restricted"
    UNAVAILABLE = "unavailable"
    ARCHIVED = "archived"
    UNKNOWN = "unknown"


class SourceCredibility(str, Enum):
    UNKNOWN = "unknown"
    VERY_LOW = "very_low"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"
    AUTHORITATIVE = "authoritative"


class EvidenceType(str, Enum):
    DIRECT_QUOTE = "direct_quote"
    PARAPHRASE = "paraphrase"
    STATISTIC = "statistic"
    EXPERIMENTAL_RESULT = "experimental_result"
    OBSERVATION = "observation"
    EXPERT_OPINION = "expert_opinion"
    LEGAL_TEXT = "legal_text"
    DEFINITION = "definition"
    TECHNICAL_SPECIFICATION = "technical_specification"
    CASE_EXAMPLE = "case_example"
    HISTORICAL_RECORD = "historical_record"
    DATA_POINT = "data_point"
    INFERENCE = "inference"
    COUNTEREVIDENCE = "counterevidence"
    OTHER = "other"


class EvidenceStrength(str, Enum):
    UNASSESSED = "unassessed"
    ANECDOTAL = "anecdotal"
    WEAK = "weak"
    MODERATE = "moderate"
    STRONG = "strong"
    VERY_STRONG = "very_strong"
    CONCLUSIVE = "conclusive"


class EvidenceDirection(str, Enum):
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    MIXED = "mixed"
    NEUTRAL = "neutral"
    CONTEXTUAL = "contextual"


class ClaimType(str, Enum):
    FACT = "fact"
    DEFINITION = "definition"
    STATISTIC = "statistic"
    CAUSAL = "causal"
    COMPARATIVE = "comparative"
    FORECAST = "forecast"
    LEGAL = "legal"
    TECHNICAL = "technical"
    HISTORICAL = "historical"
    ATTRIBUTION = "attribution"
    OPINION = "opinion"
    INFERENCE = "inference"
    HYPOTHESIS = "hypothesis"
    RECOMMENDATION = "recommendation"
    MARKETING = "marketing"
    OTHER = "other"


class ClaimStatus(str, Enum):
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    VERIFIED = "verified"
    PARTIALLY_VERIFIED = "partially_verified"
    DISPUTED = "disputed"
    UNVERIFIED = "unverified"
    FALSE = "false"
    OUTDATED = "outdated"
    NOT_APPLICABLE = "not_applicable"
    WITHDRAWN = "withdrawn"


class VerificationStatus(str, Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    VERIFIED = "verified"
    PARTIALLY_VERIFIED = "partially_verified"
    UNVERIFIED = "unverified"
    CONTRADICTED = "contradicted"
    INCONCLUSIVE = "inconclusive"
    NOT_VERIFIABLE = "not_verifiable"


class ContradictionSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class GapSeverity(str, Enum):
    INFORMATIONAL = "informational"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    BLOCKING = "blocking"


class HypothesisStatus(str, Enum):
    PROPOSED = "proposed"
    UNDER_REVIEW = "under_review"
    SUPPORTED = "supported"
    PARTIALLY_SUPPORTED = "partially_supported"
    REJECTED = "rejected"
    INCONCLUSIVE = "inconclusive"
    DEFERRED = "deferred"


class FindingImportance(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RiskLevel(str, Enum):
    INFORMATIONAL = "informational"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class IssueType(str, Enum):
    MISSING_SOURCE = "missing_source"
    LOW_CREDIBILITY = "low_credibility"
    OUTDATED_SOURCE = "outdated_source"
    CONTRADICTION = "contradiction"
    UNSUPPORTED_CLAIM = "unsupported_claim"
    BIAS = "bias"
    CONFLICT_OF_INTEREST = "conflict_of_interest"
    ACCESS_LIMITATION = "access_limitation"
    DATA_QUALITY = "data_quality"
    PRIVACY = "privacy"
    COPYRIGHT = "copyright"
    LEGAL = "legal"
    ETHICAL = "ethical"
    SCOPE = "scope"
    TIME = "time"
    COST = "cost"
    OTHER = "other"


class TaskStatus(str, Enum):
    PENDING = "pending"
    READY = "ready"
    IN_PROGRESS = "in_progress"
    IN_REVIEW = "in_review"
    COMPLETED = "completed"
    PARTIAL = "partial"
    BLOCKED = "blocked"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


class CitationStyle(str, Enum):
    APA = "apa"
    MLA = "mla"
    CHICAGO = "chicago"
    IEEE = "ieee"
    HARVARD = "harvard"
    VANCOUVER = "vancouver"
    OSCOLA = "oscola"
    INLINE_URL = "inline_url"
    CUSTOM = "custom"


class ArtifactType(str, Enum):
    RESEARCH_BRIEF = "research_brief"
    SOURCE_REGISTER = "source_register"
    EVIDENCE_MATRIX = "evidence_matrix"
    CLAIM_REGISTER = "claim_register"
    VERIFICATION_REPORT = "verification_report"
    RESEARCH_REPORT = "research_report"
    EXECUTIVE_SUMMARY = "executive_summary"
    BIBLIOGRAPHY = "bibliography"
    DATASET = "dataset"
    NOTES = "notes"
    JSON = "json"
    MARKDOWN = "markdown"
    OTHER = "other"


# =============================================================================
# Modelos fundamentales
# =============================================================================


@dataclass(slots=True)
class ResearchObjective(SerializableModel):
    statement: str
    objective_id: str = field(default_factory=lambda: generate_id("robj"))
    rationale: str = ""
    priority: ResearchPriority = ResearchPriority.NORMAL
    success_criteria: list[str] = field(default_factory=list)
    related_question_ids: list[str] = field(default_factory=list)
    required: bool = True
    completed: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)

    def __post_init__(self) -> None:
        self.statement = _clean_text(self.statement, field_name="statement")
        self.objective_id = _clean_text(
            self.objective_id, field_name="objective_id"
        )
        self.rationale = _optional_text(self.rationale)
        self.priority = _coerce_enum(
            self.priority, ResearchPriority, "priority"
        )
        self.success_criteria = _clean_string_list(self.success_criteria)
        self.related_question_ids = _clean_id_list(
            self.related_question_ids
        )
        self.metadata = _clean_mapping(self.metadata)
        self.created_at = _validate_iso(
            self.created_at, field_name="created_at"
        )
        self.updated_at = _validate_iso(
            self.updated_at, field_name="updated_at"
        )

    def mark_completed(self) -> None:
        self.completed = True
        self.updated_at = utc_now_iso()


@dataclass(slots=True)
class ResearchQuestion(SerializableModel):
    question: str
    question_id: str = field(default_factory=lambda: generate_id("rq"))
    question_type: QuestionType = QuestionType.FACTUAL
    status: QuestionStatus = QuestionStatus.OPEN
    priority: ResearchPriority = ResearchPriority.NORMAL
    rationale: str = ""
    expected_answer: str = ""
    answer: str = ""
    parent_question_id: str = ""
    dependent_question_ids: list[str] = field(default_factory=list)
    source_requirements: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    search_queries: list[str] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)
    finding_ids: list[str] = field(default_factory=list)
    gap_ids: list[str] = field(default_factory=list)
    confidence_score: Optional[float] = None
    required: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)
    answered_at: str = ""

    def __post_init__(self) -> None:
        self.question = _clean_text(
            self.question, field_name="question"
        )
        if not self.question.endswith("?"):
            self.question += "?"
        self.question_id = _clean_text(
            self.question_id, field_name="question_id"
        )
        self.question_type = _coerce_enum(
            self.question_type, QuestionType, "question_type"
        )
        self.status = _coerce_enum(
            self.status, QuestionStatus, "status"
        )
        self.priority = _coerce_enum(
            self.priority, ResearchPriority, "priority"
        )
        self.rationale = _optional_text(self.rationale)
        self.expected_answer = _optional_text(self.expected_answer)
        self.answer = _optional_text(self.answer)
        self.parent_question_id = _optional_text(
            self.parent_question_id
        )
        self.dependent_question_ids = _clean_id_list(
            self.dependent_question_ids
        )
        self.source_requirements = _clean_string_list(
            self.source_requirements
        )
        self.keywords = _clean_string_list(self.keywords)
        self.search_queries = _clean_string_list(self.search_queries)
        self.evidence_ids = _clean_id_list(self.evidence_ids)
        self.finding_ids = _clean_id_list(self.finding_ids)
        self.gap_ids = _clean_id_list(self.gap_ids)
        self.confidence_score = _validate_score(
            self.confidence_score,
            field_name="confidence_score",
        )
        self.metadata = _clean_mapping(self.metadata)
        self.created_at = _validate_iso(
            self.created_at, field_name="created_at"
        )
        self.updated_at = _validate_iso(
            self.updated_at, field_name="updated_at"
        )
        self.answered_at = _validate_iso(
            self.answered_at, field_name="answered_at"
        )

        if self.status is QuestionStatus.ANSWERED and not self.answer:
            raise ResearchValidationError(
                "Una pregunta ANSWERED debe contener 'answer'."
            )

    def set_answer(
        self,
        answer: str,
        *,
        confidence_score: Optional[float] = None,
        partial: bool = False,
    ) -> None:
        self.answer = _clean_text(answer, field_name="answer")
        self.confidence_score = _validate_score(
            confidence_score,
            field_name="confidence_score",
        )
        self.status = (
            QuestionStatus.PARTIALLY_ANSWERED
            if partial
            else QuestionStatus.ANSWERED
        )
        self.answered_at = utc_now_iso()
        self.updated_at = self.answered_at


@dataclass(slots=True)
class ResearchConstraint(SerializableModel):
    description: str
    constraint_id: str = field(default_factory=lambda: generate_id("rcon"))
    category: str = "general"
    mandatory: bool = True
    rationale: str = ""
    impact: str = ""
    mitigation: str = ""
    source: str = ""
    active: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now_iso)

    def __post_init__(self) -> None:
        self.description = _clean_text(
            self.description, field_name="description"
        )
        self.constraint_id = _clean_text(
            self.constraint_id, field_name="constraint_id"
        )
        self.category = _clean_text(
            self.category, field_name="category"
        )
        self.rationale = _optional_text(self.rationale)
        self.impact = _optional_text(self.impact)
        self.mitigation = _optional_text(self.mitigation)
        self.source = _optional_text(self.source)
        self.metadata = _clean_mapping(self.metadata)
        self.created_at = _validate_iso(
            self.created_at, field_name="created_at"
        )


# =============================================================================
# Fuentes, citas y evidencia
# =============================================================================


@dataclass(slots=True)
class ResearchSource(SerializableModel):
    title: str
    source_type: SourceType
    source_id: str = field(default_factory=lambda: generate_id("src"))
    authors: list[str] = field(default_factory=list)
    organization: str = ""
    publisher: str = ""
    publication_date: str = ""
    accessed_at: str = field(default_factory=utc_now_iso)
    url: str = ""
    doi: str = ""
    isbn: str = ""
    language: str = ""
    jurisdiction: str = ""
    origin: SourceOrigin = SourceOrigin.EXTERNAL_PUBLIC
    access_status: SourceAccessStatus = SourceAccessStatus.AVAILABLE
    credibility: SourceCredibility = SourceCredibility.UNKNOWN
    credibility_score: Optional[float] = None
    relevance_score: Optional[float] = None
    authority_score: Optional[float] = None
    accuracy_score: Optional[float] = None
    currency_score: Optional[float] = None
    transparency_score: Optional[float] = None
    bias_risk_score: Optional[float] = None
    primary_source: bool = False
    peer_reviewed: bool = False
    official: bool = False
    archived: bool = False
    paywalled: bool = False
    summary: str = ""
    notes: str = ""
    limitations: list[str] = field(default_factory=list)
    conflicts_of_interest: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    question_ids: list[str] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)

    def __post_init__(self) -> None:
        self.title = _clean_text(self.title, field_name="title")
        self.source_type = _coerce_enum(
            self.source_type, SourceType, "source_type"
        )
        self.source_id = _clean_text(
            self.source_id, field_name="source_id"
        )
        self.authors = _clean_string_list(self.authors)
        self.organization = _optional_text(self.organization)
        self.publisher = _optional_text(self.publisher)
        self.publication_date = _validate_iso(
            self.publication_date,
            field_name="publication_date",
        )
        self.accessed_at = _validate_iso(
            self.accessed_at, field_name="accessed_at"
        )
        self.url = _normalize_url(self.url)
        self.doi = _optional_text(self.doi)
        self.isbn = _optional_text(self.isbn)
        self.language = _optional_text(self.language)
        self.jurisdiction = _optional_text(self.jurisdiction)
        self.origin = _coerce_enum(
            self.origin, SourceOrigin, "origin"
        )
        self.access_status = _coerce_enum(
            self.access_status,
            SourceAccessStatus,
            "access_status",
        )
        self.credibility = _coerce_enum(
            self.credibility,
            SourceCredibility,
            "credibility",
        )

        for score_name in (
            "credibility_score",
            "relevance_score",
            "authority_score",
            "accuracy_score",
            "currency_score",
            "transparency_score",
            "bias_risk_score",
        ):
            setattr(
                self,
                score_name,
                _validate_score(
                    getattr(self, score_name),
                    field_name=score_name,
                ),
            )

        self.summary = _optional_text(self.summary)
        self.notes = _optional_text(self.notes)
        self.limitations = _clean_string_list(self.limitations)
        self.conflicts_of_interest = _clean_string_list(
            self.conflicts_of_interest
        )
        self.tags = _clean_string_list(self.tags)
        self.question_ids = _clean_id_list(self.question_ids)
        self.evidence_ids = _clean_id_list(self.evidence_ids)
        self.metadata = _clean_mapping(self.metadata)
        self.created_at = _validate_iso(
            self.created_at, field_name="created_at"
        )
        self.updated_at = _validate_iso(
            self.updated_at, field_name="updated_at"
        )

        if not any(
            (
                self.url,
                self.doi,
                self.isbn,
                self.organization,
                self.authors,
                self.publisher,
            )
        ):
            self.limitations = _clean_string_list(
                [
                    *self.limitations,
                    "La fuente no contiene identificadores ni autoría suficiente.",
                ]
            )

    @property
    def composite_score(self) -> Optional[float]:
        values = [
            self.authority_score,
            self.accuracy_score,
            self.currency_score,
            self.transparency_score,
            self.relevance_score,
        ]
        present = [value for value in values if value is not None]
        if not present:
            return self.credibility_score

        positive = sum(present) / len(present)
        penalty = (self.bias_risk_score or 0.0) * 0.2
        return round(max(0.0, min(10.0, positive - penalty)), 2)

    def touch(self) -> None:
        self.updated_at = utc_now_iso()


@dataclass(slots=True)
class ResearchCitation(SerializableModel):
    source_id: str
    citation_text: str
    citation_id: str = field(default_factory=lambda: generate_id("cit"))
    style: CitationStyle = CitationStyle.APA
    locator: str = ""
    quote: str = ""
    paraphrase: str = ""
    context: str = ""
    direct_quote: bool = False
    verified_against_source: bool = False
    evidence_ids: list[str] = field(default_factory=list)
    claim_ids: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now_iso)

    def __post_init__(self) -> None:
        self.source_id = _clean_text(
            self.source_id, field_name="source_id"
        )
        self.citation_text = _clean_text(
            self.citation_text, field_name="citation_text"
        )
        self.citation_id = _clean_text(
            self.citation_id, field_name="citation_id"
        )
        self.style = _coerce_enum(
            self.style, CitationStyle, "style"
        )
        self.locator = _optional_text(self.locator)
        self.quote = _optional_text(self.quote)
        self.paraphrase = _optional_text(self.paraphrase)
        self.context = _optional_text(self.context)
        self.evidence_ids = _clean_id_list(self.evidence_ids)
        self.claim_ids = _clean_id_list(self.claim_ids)
        self.metadata = _clean_mapping(self.metadata)
        self.created_at = _validate_iso(
            self.created_at, field_name="created_at"
        )

        if self.direct_quote and not self.quote:
            raise ResearchValidationError(
                "Una cita directa debe incluir 'quote'."
            )


@dataclass(slots=True)
class ResearchEvidence(SerializableModel):
    source_id: str
    content: str
    evidence_type: EvidenceType
    evidence_id: str = field(default_factory=lambda: generate_id("ev"))
    direction: EvidenceDirection = EvidenceDirection.SUPPORTS
    strength: EvidenceStrength = EvidenceStrength.UNASSESSED
    locator: str = ""
    context: str = ""
    interpretation: str = ""
    methodology_notes: str = ""
    relevance_score: Optional[float] = None
    reliability_score: Optional[float] = None
    confidence_score: Optional[float] = None
    extracted_at: str = field(default_factory=utc_now_iso)
    extracted_by: str = "research_director"
    verbatim: bool = False
    independently_confirmed: bool = False
    duplicate_of_evidence_id: str = ""
    question_ids: list[str] = field(default_factory=list)
    claim_ids: list[str] = field(default_factory=list)
    finding_ids: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.source_id = _clean_text(
            self.source_id, field_name="source_id"
        )
        self.content = _clean_text(
            self.content, field_name="content"
        )
        self.evidence_type = _coerce_enum(
            self.evidence_type,
            EvidenceType,
            "evidence_type",
        )
        self.evidence_id = _clean_text(
            self.evidence_id, field_name="evidence_id"
        )
        self.direction = _coerce_enum(
            self.direction,
            EvidenceDirection,
            "direction",
        )
        self.strength = _coerce_enum(
            self.strength,
            EvidenceStrength,
            "strength",
        )
        self.locator = _optional_text(self.locator)
        self.context = _optional_text(self.context)
        self.interpretation = _optional_text(self.interpretation)
        self.methodology_notes = _optional_text(
            self.methodology_notes
        )

        for score_name in (
            "relevance_score",
            "reliability_score",
            "confidence_score",
        ):
            setattr(
                self,
                score_name,
                _validate_score(
                    getattr(self, score_name),
                    field_name=score_name,
                ),
            )

        self.extracted_at = _validate_iso(
            self.extracted_at, field_name="extracted_at"
        )
        self.extracted_by = _clean_text(
            self.extracted_by, field_name="extracted_by"
        )
        self.duplicate_of_evidence_id = _optional_text(
            self.duplicate_of_evidence_id
        )
        self.question_ids = _clean_id_list(self.question_ids)
        self.claim_ids = _clean_id_list(self.claim_ids)
        self.finding_ids = _clean_id_list(self.finding_ids)
        self.limitations = _clean_string_list(self.limitations)
        self.tags = _clean_string_list(self.tags)
        self.metadata = _clean_mapping(self.metadata)

        if self.verbatim and self.evidence_type is not EvidenceType.DIRECT_QUOTE:
            raise ResearchValidationError(
                "La evidencia 'verbatim' debe usar DIRECT_QUOTE."
            )


# =============================================================================
# Afirmaciones, verificación y contradicciones
# =============================================================================


@dataclass(slots=True)
class FactClaim(SerializableModel):
    statement: str
    claim_type: ClaimType = ClaimType.FACT
    claim_id: str = field(default_factory=lambda: generate_id("claim"))
    status: ClaimStatus = ClaimStatus.DRAFT
    importance: FindingImportance = FindingImportance.MEDIUM
    context: str = ""
    scope: str = ""
    jurisdiction: str = ""
    time_sensitive: bool = False
    valid_from: str = ""
    valid_until: str = ""
    evidence_ids: list[str] = field(default_factory=list)
    supporting_source_ids: list[str] = field(default_factory=list)
    contradicting_source_ids: list[str] = field(default_factory=list)
    verification_ids: list[str] = field(default_factory=list)
    confidence_score: Optional[float] = None
    publication_safe: bool = False
    requires_attribution: bool = False
    attribution_text: str = ""
    notes: str = ""
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)

    def __post_init__(self) -> None:
        self.statement = _clean_text(
            self.statement, field_name="statement"
        )
        self.claim_type = _coerce_enum(
            self.claim_type, ClaimType, "claim_type"
        )
        self.claim_id = _clean_text(
            self.claim_id, field_name="claim_id"
        )
        self.status = _coerce_enum(
            self.status, ClaimStatus, "status"
        )
        self.importance = _coerce_enum(
            self.importance,
            FindingImportance,
            "importance",
        )
        self.context = _optional_text(self.context)
        self.scope = _optional_text(self.scope)
        self.jurisdiction = _optional_text(self.jurisdiction)
        self.valid_from = _validate_iso(
            self.valid_from, field_name="valid_from"
        )
        self.valid_until = _validate_iso(
            self.valid_until, field_name="valid_until"
        )
        self.evidence_ids = _clean_id_list(self.evidence_ids)
        self.supporting_source_ids = _clean_id_list(
            self.supporting_source_ids
        )
        self.contradicting_source_ids = _clean_id_list(
            self.contradicting_source_ids
        )
        self.verification_ids = _clean_id_list(
            self.verification_ids
        )
        self.confidence_score = _validate_score(
            self.confidence_score,
            field_name="confidence_score",
        )
        self.attribution_text = _optional_text(
            self.attribution_text
        )
        self.notes = _optional_text(self.notes)
        self.tags = _clean_string_list(self.tags)
        self.metadata = _clean_mapping(self.metadata)
        self.created_at = _validate_iso(
            self.created_at, field_name="created_at"
        )
        self.updated_at = _validate_iso(
            self.updated_at, field_name="updated_at"
        )

        if self.requires_attribution and not self.attribution_text:
            raise ResearchValidationError(
                "La afirmación requiere 'attribution_text'."
            )
        if self.publication_safe and self.status not in {
            ClaimStatus.VERIFIED,
            ClaimStatus.PARTIALLY_VERIFIED,
        }:
            raise ResearchValidationError(
                "Una afirmación publication_safe debe estar verificada."
            )

    def touch(self) -> None:
        self.updated_at = utc_now_iso()


@dataclass(slots=True)
class FactVerification(SerializableModel):
    claim_id: str
    status: VerificationStatus
    verification_id: str = field(
        default_factory=lambda: generate_id("verify")
    )
    verifier: str = "research_director"
    method: ResearchMethod = ResearchMethod.FACT_CHECKING
    conclusion: str = ""
    rationale: str = ""
    supporting_evidence_ids: list[str] = field(default_factory=list)
    contradicting_evidence_ids: list[str] = field(default_factory=list)
    source_ids: list[str] = field(default_factory=list)
    confidence_score: Optional[float] = None
    publication_recommendation: str = ""
    correction: str = ""
    limitations: list[str] = field(default_factory=list)
    reviewed_at: str = field(default_factory=utc_now_iso)
    expires_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.claim_id = _clean_text(
            self.claim_id, field_name="claim_id"
        )
        self.status = _coerce_enum(
            self.status,
            VerificationStatus,
            "status",
        )
        self.verification_id = _clean_text(
            self.verification_id,
            field_name="verification_id",
        )
        self.verifier = _clean_text(
            self.verifier, field_name="verifier"
        )
        self.method = _coerce_enum(
            self.method, ResearchMethod, "method"
        )
        self.conclusion = _optional_text(self.conclusion)
        self.rationale = _optional_text(self.rationale)
        self.supporting_evidence_ids = _clean_id_list(
            self.supporting_evidence_ids
        )
        self.contradicting_evidence_ids = _clean_id_list(
            self.contradicting_evidence_ids
        )
        self.source_ids = _clean_id_list(self.source_ids)
        self.confidence_score = _validate_score(
            self.confidence_score,
            field_name="confidence_score",
        )
        self.publication_recommendation = _optional_text(
            self.publication_recommendation
        )
        self.correction = _optional_text(self.correction)
        self.limitations = _clean_string_list(self.limitations)
        self.reviewed_at = _validate_iso(
            self.reviewed_at, field_name="reviewed_at"
        )
        self.expires_at = _validate_iso(
            self.expires_at, field_name="expires_at"
        )
        self.metadata = _clean_mapping(self.metadata)

        if self.status in {
            VerificationStatus.VERIFIED,
            VerificationStatus.PARTIALLY_VERIFIED,
            VerificationStatus.CONTRADICTED,
            VerificationStatus.INCONCLUSIVE,
        } and not self.conclusion:
            raise ResearchValidationError(
                "La verificación finalizada debe contener 'conclusion'."
            )


@dataclass(slots=True)
class ResearchContradiction(SerializableModel):
    description: str
    source_ids: list[str]
    contradiction_id: str = field(
        default_factory=lambda: generate_id("contra")
    )
    evidence_ids: list[str] = field(default_factory=list)
    claim_ids: list[str] = field(default_factory=list)
    severity: ContradictionSeverity = ContradictionSeverity.MEDIUM
    nature: str = ""
    possible_explanations: list[str] = field(default_factory=list)
    resolution: str = ""
    resolved: bool = False
    preferred_source_id: str = ""
    impact: str = ""
    blocking: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now_iso)
    resolved_at: str = ""

    def __post_init__(self) -> None:
        self.description = _clean_text(
            self.description, field_name="description"
        )
        self.source_ids = _clean_id_list(self.source_ids)
        if len(self.source_ids) < 2:
            raise ResearchValidationError(
                "Una contradicción requiere al menos dos fuentes."
            )
        self.contradiction_id = _clean_text(
            self.contradiction_id,
            field_name="contradiction_id",
        )
        self.evidence_ids = _clean_id_list(self.evidence_ids)
        self.claim_ids = _clean_id_list(self.claim_ids)
        self.severity = _coerce_enum(
            self.severity,
            ContradictionSeverity,
            "severity",
        )
        self.nature = _optional_text(self.nature)
        self.possible_explanations = _clean_string_list(
            self.possible_explanations
        )
        self.resolution = _optional_text(self.resolution)
        self.preferred_source_id = _optional_text(
            self.preferred_source_id
        )
        self.impact = _optional_text(self.impact)
        self.metadata = _clean_mapping(self.metadata)
        self.created_at = _validate_iso(
            self.created_at, field_name="created_at"
        )
        self.resolved_at = _validate_iso(
            self.resolved_at, field_name="resolved_at"
        )

        if self.resolved and not self.resolution:
            raise ResearchValidationError(
                "Una contradicción resuelta debe explicar su resolución."
            )

    def resolve(
        self,
        resolution: str,
        *,
        preferred_source_id: str = "",
    ) -> None:
        self.resolution = _clean_text(
            resolution, field_name="resolution"
        )
        self.preferred_source_id = _optional_text(
            preferred_source_id
        )
        self.resolved = True
        self.resolved_at = utc_now_iso()


# =============================================================================
# Vacíos, hipótesis y hallazgos
# =============================================================================


@dataclass(slots=True)
class KnowledgeGap(SerializableModel):
    description: str
    gap_id: str = field(default_factory=lambda: generate_id("gap"))
    severity: GapSeverity = GapSeverity.MEDIUM
    question_ids: list[str] = field(default_factory=list)
    claim_ids: list[str] = field(default_factory=list)
    missing_information: list[str] = field(default_factory=list)
    reason: str = ""
    impact: str = ""
    resolution_strategy: str = ""
    required_sources: list[str] = field(default_factory=list)
    resolvable: bool = True
    resolved: bool = False
    resolution: str = ""
    blocking: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now_iso)
    resolved_at: str = ""

    def __post_init__(self) -> None:
        self.description = _clean_text(
            self.description, field_name="description"
        )
        self.gap_id = _clean_text(
            self.gap_id, field_name="gap_id"
        )
        self.severity = _coerce_enum(
            self.severity, GapSeverity, "severity"
        )
        self.question_ids = _clean_id_list(self.question_ids)
        self.claim_ids = _clean_id_list(self.claim_ids)
        self.missing_information = _clean_string_list(
            self.missing_information
        )
        self.reason = _optional_text(self.reason)
        self.impact = _optional_text(self.impact)
        self.resolution_strategy = _optional_text(
            self.resolution_strategy
        )
        self.required_sources = _clean_string_list(
            self.required_sources
        )
        self.resolution = _optional_text(self.resolution)
        self.metadata = _clean_mapping(self.metadata)
        self.created_at = _validate_iso(
            self.created_at, field_name="created_at"
        )
        self.resolved_at = _validate_iso(
            self.resolved_at, field_name="resolved_at"
        )

        if self.severity is GapSeverity.BLOCKING:
            self.blocking = True
        if self.resolved and not self.resolution:
            raise ResearchValidationError(
                "Un vacío resuelto debe contener 'resolution'."
            )

    def resolve(self, resolution: str) -> None:
        self.resolution = _clean_text(
            resolution, field_name="resolution"
        )
        self.resolved = True
        self.blocking = False
        self.resolved_at = utc_now_iso()


@dataclass(slots=True)
class ResearchHypothesis(SerializableModel):
    statement: str
    hypothesis_id: str = field(
        default_factory=lambda: generate_id("hyp")
    )
    status: HypothesisStatus = HypothesisStatus.PROPOSED
    rationale: str = ""
    assumptions: list[str] = field(default_factory=list)
    supporting_evidence_ids: list[str] = field(default_factory=list)
    contradicting_evidence_ids: list[str] = field(default_factory=list)
    test_method: str = ""
    test_result: str = ""
    confidence_score: Optional[float] = None
    publication_allowed: bool = False
    publication_label: str = "Hipótesis"
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)

    def __post_init__(self) -> None:
        self.statement = _clean_text(
            self.statement, field_name="statement"
        )
        self.hypothesis_id = _clean_text(
            self.hypothesis_id,
            field_name="hypothesis_id",
        )
        self.status = _coerce_enum(
            self.status,
            HypothesisStatus,
            "status",
        )
        self.rationale = _optional_text(self.rationale)
        self.assumptions = _clean_string_list(self.assumptions)
        self.supporting_evidence_ids = _clean_id_list(
            self.supporting_evidence_ids
        )
        self.contradicting_evidence_ids = _clean_id_list(
            self.contradicting_evidence_ids
        )
        self.test_method = _optional_text(self.test_method)
        self.test_result = _optional_text(self.test_result)
        self.confidence_score = _validate_score(
            self.confidence_score,
            field_name="confidence_score",
        )
        self.publication_label = _clean_text(
            self.publication_label,
            field_name="publication_label",
        )
        self.metadata = _clean_mapping(self.metadata)
        self.created_at = _validate_iso(
            self.created_at, field_name="created_at"
        )
        self.updated_at = _validate_iso(
            self.updated_at, field_name="updated_at"
        )

        if self.publication_allowed and not self.publication_label:
            raise ResearchValidationError(
                "Una hipótesis publicable debe estar etiquetada."
            )


@dataclass(slots=True)
class ResearchFinding(SerializableModel):
    title: str
    summary: str
    finding_id: str = field(
        default_factory=lambda: generate_id("finding")
    )
    importance: FindingImportance = FindingImportance.MEDIUM
    category: str = "general"
    detail: str = ""
    implications: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)
    source_ids: list[str] = field(default_factory=list)
    claim_ids: list[str] = field(default_factory=list)
    question_ids: list[str] = field(default_factory=list)
    confidence_score: Optional[float] = None
    fact_checked: bool = False
    publication_safe: bool = False
    limitations: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)

    def __post_init__(self) -> None:
        self.title = _clean_text(self.title, field_name="title")
        self.summary = _clean_text(
            self.summary, field_name="summary"
        )
        self.finding_id = _clean_text(
            self.finding_id, field_name="finding_id"
        )
        self.importance = _coerce_enum(
            self.importance,
            FindingImportance,
            "importance",
        )
        self.category = _clean_text(
            self.category, field_name="category"
        )
        self.detail = _optional_text(self.detail)
        self.implications = _clean_string_list(self.implications)
        self.recommendations = _clean_string_list(
            self.recommendations
        )
        self.evidence_ids = _clean_id_list(self.evidence_ids)
        self.source_ids = _clean_id_list(self.source_ids)
        self.claim_ids = _clean_id_list(self.claim_ids)
        self.question_ids = _clean_id_list(self.question_ids)
        self.confidence_score = _validate_score(
            self.confidence_score,
            field_name="confidence_score",
        )
        self.limitations = _clean_string_list(self.limitations)
        self.metadata = _clean_mapping(self.metadata)
        self.created_at = _validate_iso(
            self.created_at, field_name="created_at"
        )
        self.updated_at = _validate_iso(
            self.updated_at, field_name="updated_at"
        )

        if self.publication_safe and not self.fact_checked:
            raise ResearchValidationError(
                "Un hallazgo publication_safe debe estar fact_checked."
            )


# =============================================================================
# Riesgos, incidencias y tareas
# =============================================================================


@dataclass(slots=True)
class ResearchRisk(SerializableModel):
    description: str
    risk_id: str = field(default_factory=lambda: generate_id("risk"))
    level: RiskLevel = RiskLevel.MEDIUM
    category: str = "research"
    probability: Optional[float] = None
    impact_score: Optional[float] = None
    mitigation: str = ""
    contingency: str = ""
    owner: str = "research_director"
    active: bool = True
    blocking: bool = False
    related_source_ids: list[str] = field(default_factory=list)
    related_question_ids: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)

    def __post_init__(self) -> None:
        self.description = _clean_text(
            self.description, field_name="description"
        )
        self.risk_id = _clean_text(
            self.risk_id, field_name="risk_id"
        )
        self.level = _coerce_enum(
            self.level, RiskLevel, "level"
        )
        self.category = _clean_text(
            self.category, field_name="category"
        )
        self.probability = _validate_probability(
            self.probability,
            field_name="probability",
        )
        self.impact_score = _validate_score(
            self.impact_score,
            field_name="impact_score",
        )
        self.mitigation = _optional_text(self.mitigation)
        self.contingency = _optional_text(self.contingency)
        self.owner = _clean_text(self.owner, field_name="owner")
        self.related_source_ids = _clean_id_list(
            self.related_source_ids
        )
        self.related_question_ids = _clean_id_list(
            self.related_question_ids
        )
        self.metadata = _clean_mapping(self.metadata)
        self.created_at = _validate_iso(
            self.created_at, field_name="created_at"
        )
        self.updated_at = _validate_iso(
            self.updated_at, field_name="updated_at"
        )


@dataclass(slots=True)
class ResearchIssue(SerializableModel):
    message: str
    issue_type: IssueType
    issue_id: str = field(default_factory=lambda: generate_id("issue"))
    risk_level: RiskLevel = RiskLevel.MEDIUM
    blocking: bool = False
    source_id: str = ""
    evidence_id: str = ""
    claim_id: str = ""
    question_id: str = ""
    task_id: str = ""
    recommended_action: str = ""
    resolution: str = ""
    resolved: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now_iso)
    resolved_at: str = ""

    def __post_init__(self) -> None:
        self.message = _clean_text(
            self.message, field_name="message"
        )
        self.issue_type = _coerce_enum(
            self.issue_type, IssueType, "issue_type"
        )
        self.issue_id = _clean_text(
            self.issue_id, field_name="issue_id"
        )
        self.risk_level = _coerce_enum(
            self.risk_level, RiskLevel, "risk_level"
        )
        self.source_id = _optional_text(self.source_id)
        self.evidence_id = _optional_text(self.evidence_id)
        self.claim_id = _optional_text(self.claim_id)
        self.question_id = _optional_text(self.question_id)
        self.task_id = _optional_text(self.task_id)
        self.recommended_action = _optional_text(
            self.recommended_action
        )
        self.resolution = _optional_text(self.resolution)
        self.metadata = _clean_mapping(self.metadata)
        self.created_at = _validate_iso(
            self.created_at, field_name="created_at"
        )
        self.resolved_at = _validate_iso(
            self.resolved_at, field_name="resolved_at"
        )

        if self.risk_level is RiskLevel.CRITICAL:
            self.blocking = True
        if self.resolved and not self.resolution:
            raise ResearchValidationError(
                "Una incidencia resuelta debe explicar la resolución."
            )


@dataclass(slots=True)
class ResearchTask(SerializableModel):
    title: str
    objective: str
    task_id: str = field(default_factory=lambda: generate_id("rtask"))
    status: TaskStatus = TaskStatus.PENDING
    priority: ResearchPriority = ResearchPriority.NORMAL
    method: ResearchMethod = ResearchMethod.DESK_RESEARCH
    sequence: int = 0
    required: bool = True
    dependency_task_ids: list[str] = field(default_factory=list)
    question_ids: list[str] = field(default_factory=list)
    source_ids: list[str] = field(default_factory=list)
    output_artifacts: list[str] = field(default_factory=list)
    instructions: list[str] = field(default_factory=list)
    acceptance_criteria: list[str] = field(default_factory=list)
    estimated_minutes: float = 0.0
    estimated_cost: float = 0.0
    actual_minutes: float = 0.0
    actual_cost: float = 0.0
    attempt_count: int = 0
    max_attempts: int = 2
    assigned_to: str = "research_director"
    error_message: str = ""
    result_summary: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now_iso)
    started_at: str = ""
    completed_at: str = ""

    def __post_init__(self) -> None:
        self.title = _clean_text(self.title, field_name="title")
        self.objective = _clean_text(
            self.objective, field_name="objective"
        )
        self.task_id = _clean_text(
            self.task_id, field_name="task_id"
        )
        self.status = _coerce_enum(
            self.status, TaskStatus, "status"
        )
        self.priority = _coerce_enum(
            self.priority, ResearchPriority, "priority"
        )
        self.method = _coerce_enum(
            self.method, ResearchMethod, "method"
        )
        if int(self.sequence) < 0:
            raise ResearchValidationError(
                "'sequence' no puede ser negativo."
            )
        self.sequence = int(self.sequence)
        self.dependency_task_ids = _clean_id_list(
            self.dependency_task_ids
        )
        if self.task_id in self.dependency_task_ids:
            raise ResearchValidationError(
                "Una tarea no puede depender de sí misma."
            )
        self.question_ids = _clean_id_list(self.question_ids)
        self.source_ids = _clean_id_list(self.source_ids)
        self.output_artifacts = _clean_string_list(
            self.output_artifacts
        )
        self.instructions = _clean_string_list(self.instructions)
        self.acceptance_criteria = _clean_string_list(
            self.acceptance_criteria
        )
        self.estimated_minutes = _validate_non_negative(
            self.estimated_minutes,
            field_name="estimated_minutes",
        )
        self.estimated_cost = _validate_non_negative(
            self.estimated_cost,
            field_name="estimated_cost",
        )
        self.actual_minutes = _validate_non_negative(
            self.actual_minutes,
            field_name="actual_minutes",
        )
        self.actual_cost = _validate_non_negative(
            self.actual_cost,
            field_name="actual_cost",
        )
        if int(self.attempt_count) < 0:
            raise ResearchValidationError(
                "'attempt_count' no puede ser negativo."
            )
        if int(self.max_attempts) < 1:
            raise ResearchValidationError(
                "'max_attempts' debe ser al menos 1."
            )
        self.attempt_count = int(self.attempt_count)
        self.max_attempts = int(self.max_attempts)
        self.assigned_to = _clean_text(
            self.assigned_to, field_name="assigned_to"
        )
        self.error_message = _optional_text(self.error_message)
        self.result_summary = _optional_text(self.result_summary)
        self.metadata = _clean_mapping(self.metadata)
        self.created_at = _validate_iso(
            self.created_at, field_name="created_at"
        )
        self.started_at = _validate_iso(
            self.started_at, field_name="started_at"
        )
        self.completed_at = _validate_iso(
            self.completed_at, field_name="completed_at"
        )

    @property
    def is_terminal(self) -> bool:
        return self.status in {
            TaskStatus.COMPLETED,
            TaskStatus.PARTIAL,
            TaskStatus.FAILED,
            TaskStatus.SKIPPED,
            TaskStatus.CANCELLED,
        }


# =============================================================================
# Plan, métricas, artefactos, informe y resultado
# =============================================================================


@dataclass(slots=True)
class ResearchPlan(SerializableModel):
    project_id: str
    topic: str
    objective: str
    plan_id: str = field(default_factory=lambda: generate_id("rplan"))
    status: ResearchStatus = ResearchStatus.DRAFT
    priority: ResearchPriority = ResearchPriority.NORMAL
    scope: ResearchScope = ResearchScope.EXPLORATORY
    methods: list[ResearchMethod] = field(default_factory=list)
    objectives: list[ResearchObjective] = field(default_factory=list)
    questions: list[ResearchQuestion] = field(default_factory=list)
    constraints: list[ResearchConstraint] = field(default_factory=list)
    tasks: list[ResearchTask] = field(default_factory=list)
    expected_artifacts: list[str] = field(default_factory=list)
    source_requirements: list[str] = field(default_factory=list)
    inclusion_criteria: list[str] = field(default_factory=list)
    exclusion_criteria: list[str] = field(default_factory=list)
    search_strategy: list[str] = field(default_factory=list)
    success_criteria: list[str] = field(default_factory=list)
    deadline_iso: str = ""
    language: str = "es"
    jurisdictions: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)

    def __post_init__(self) -> None:
        self.project_id = _clean_text(
            self.project_id, field_name="project_id"
        )
        self.topic = _clean_text(self.topic, field_name="topic")
        self.objective = _clean_text(
            self.objective, field_name="objective"
        )
        self.plan_id = _clean_text(
            self.plan_id, field_name="plan_id"
        )
        self.status = _coerce_enum(
            self.status, ResearchStatus, "status"
        )
        self.priority = _coerce_enum(
            self.priority, ResearchPriority, "priority"
        )
        self.scope = _coerce_enum(
            self.scope, ResearchScope, "scope"
        )
        self.methods = [
            _coerce_enum(item, ResearchMethod, "methods")
            for item in self.methods
        ]
        self.methods = list(dict.fromkeys(self.methods))
        self.objectives = self._validate_models(
            self.objectives,
            ResearchObjective,
            "objectives",
        )
        self.questions = self._validate_models(
            self.questions,
            ResearchQuestion,
            "questions",
        )
        self.constraints = self._validate_models(
            self.constraints,
            ResearchConstraint,
            "constraints",
        )
        self.tasks = self._validate_models(
            self.tasks,
            ResearchTask,
            "tasks",
        )
        self.expected_artifacts = _clean_string_list(
            self.expected_artifacts
        )
        self.source_requirements = _clean_string_list(
            self.source_requirements
        )
        self.inclusion_criteria = _clean_string_list(
            self.inclusion_criteria
        )
        self.exclusion_criteria = _clean_string_list(
            self.exclusion_criteria
        )
        self.search_strategy = _clean_string_list(
            self.search_strategy
        )
        self.success_criteria = _clean_string_list(
            self.success_criteria
        )
        self.deadline_iso = _validate_iso(
            self.deadline_iso, field_name="deadline_iso"
        )
        self.language = _clean_text(
            self.language, field_name="language"
        )
        self.jurisdictions = _clean_string_list(
            self.jurisdictions
        )
        self.metadata = _clean_mapping(self.metadata)
        self.created_at = _validate_iso(
            self.created_at, field_name="created_at"
        )
        self.updated_at = _validate_iso(
            self.updated_at, field_name="updated_at"
        )

        self.validate_unique_ids()
        self.validate_dependencies()

    @staticmethod
    def _validate_models(
        values: Sequence[Any],
        expected_type: type,
        field_name: str,
    ) -> list[Any]:
        output = list(values or [])
        if not all(isinstance(item, expected_type) for item in output):
            raise ResearchValidationError(
                f"'{field_name}' debe contener {expected_type.__name__}."
            )
        return output

    def validate_unique_ids(self) -> None:
        collections = (
            ("objectives", [item.objective_id for item in self.objectives]),
            ("questions", [item.question_id for item in self.questions]),
            ("constraints", [item.constraint_id for item in self.constraints]),
            ("tasks", [item.task_id for item in self.tasks]),
        )
        for name, identifiers in collections:
            if len(identifiers) != len(set(identifiers)):
                raise ResearchValidationError(
                    f"Existen identificadores duplicados en '{name}'."
                )

    def validate_dependencies(self) -> None:
        task_ids = {task.task_id for task in self.tasks}
        for task in self.tasks:
            unknown = set(task.dependency_task_ids) - task_ids
            if unknown:
                raise ResearchValidationError(
                    f"La tarea '{task.task_id}' depende de tareas inexistentes: "
                    + ", ".join(sorted(unknown))
                )

        graph = {
            task.task_id: set(task.dependency_task_ids)
            for task in self.tasks
        }
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(task_id: str) -> None:
            if task_id in visiting:
                raise ResearchValidationError(
                    "El plan contiene un ciclo de dependencias."
                )
            if task_id in visited:
                return
            visiting.add(task_id)
            for dependency in graph[task_id]:
                visit(dependency)
            visiting.remove(task_id)
            visited.add(task_id)

        for task_id in graph:
            visit(task_id)

    def ordered_tasks(self) -> list[ResearchTask]:
        return sorted(
            self.tasks,
            key=lambda item: (item.sequence, item.task_id),
        )

    def ready_tasks(self) -> list[ResearchTask]:
        completed = {
            task.task_id
            for task in self.tasks
            if task.status in {
                TaskStatus.COMPLETED,
                TaskStatus.SKIPPED,
            }
        }
        return [
            task
            for task in self.ordered_tasks()
            if task.status in {TaskStatus.PENDING, TaskStatus.READY}
            and set(task.dependency_task_ids).issubset(completed)
        ]

    @property
    def estimated_total_minutes(self) -> float:
        return round(
            sum(task.estimated_minutes for task in self.tasks),
            2,
        )

    @property
    def estimated_total_cost(self) -> float:
        return round(
            sum(task.estimated_cost for task in self.tasks),
            6,
        )

    def touch(self) -> None:
        self.updated_at = utc_now_iso()


@dataclass(slots=True)
class ResearchMetrics(SerializableModel):
    total_questions: int = 0
    answered_questions: int = 0
    partially_answered_questions: int = 0
    unresolved_questions: int = 0
    total_sources: int = 0
    authoritative_sources: int = 0
    primary_sources: int = 0
    peer_reviewed_sources: int = 0
    current_sources: int = 0
    total_evidence_items: int = 0
    strong_evidence_items: int = 0
    total_claims: int = 0
    verified_claims: int = 0
    disputed_claims: int = 0
    unsupported_claims: int = 0
    total_findings: int = 0
    publication_safe_findings: int = 0
    knowledge_gaps: int = 0
    blocking_gaps: int = 0
    contradictions: int = 0
    unresolved_contradictions: int = 0
    total_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    elapsed_seconds: float = 0.0
    estimated_cost: float = 0.0
    actual_cost: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    source_quality_score: Optional[float] = None
    evidence_quality_score: Optional[float] = None
    factual_confidence_score: Optional[float] = None
    completeness_score: Optional[float] = None
    recency_score: Optional[float] = None
    traceability_score: Optional[float] = None
    bias_control_score: Optional[float] = None
    overall_quality_score: Optional[float] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        integer_fields = (
            "total_questions",
            "answered_questions",
            "partially_answered_questions",
            "unresolved_questions",
            "total_sources",
            "authoritative_sources",
            "primary_sources",
            "peer_reviewed_sources",
            "current_sources",
            "total_evidence_items",
            "strong_evidence_items",
            "total_claims",
            "verified_claims",
            "disputed_claims",
            "unsupported_claims",
            "total_findings",
            "publication_safe_findings",
            "knowledge_gaps",
            "blocking_gaps",
            "contradictions",
            "unresolved_contradictions",
            "total_tasks",
            "completed_tasks",
            "failed_tasks",
            "input_tokens",
            "output_tokens",
        )
        for field_name in integer_fields:
            value = int(getattr(self, field_name))
            if value < 0:
                raise ResearchValidationError(
                    f"'{field_name}' no puede ser negativo."
                )
            setattr(self, field_name, value)

        for field_name in (
            "elapsed_seconds",
            "estimated_cost",
            "actual_cost",
        ):
            setattr(
                self,
                field_name,
                _validate_non_negative(
                    getattr(self, field_name),
                    field_name=field_name,
                ),
            )

        for field_name in (
            "source_quality_score",
            "evidence_quality_score",
            "factual_confidence_score",
            "completeness_score",
            "recency_score",
            "traceability_score",
            "bias_control_score",
            "overall_quality_score",
        ):
            setattr(
                self,
                field_name,
                _validate_score(
                    getattr(self, field_name),
                    field_name=field_name,
                ),
            )

        self.metadata = _clean_mapping(self.metadata)

    @property
    def question_completion_rate(self) -> float:
        if self.total_questions == 0:
            return 0.0
        completed = (
            self.answered_questions
            + 0.5 * self.partially_answered_questions
        )
        return round(completed / self.total_questions, 4)

    @property
    def claim_verification_rate(self) -> float:
        if self.total_claims == 0:
            return 0.0
        return round(self.verified_claims / self.total_claims, 4)

    @property
    def task_completion_rate(self) -> float:
        if self.total_tasks == 0:
            return 0.0
        return round(self.completed_tasks / self.total_tasks, 4)

    @property
    def source_authority_rate(self) -> float:
        if self.total_sources == 0:
            return 0.0
        return round(
            self.authoritative_sources / self.total_sources,
            4,
        )


@dataclass(slots=True)
class ResearchArtifact(SerializableModel):
    name: str
    artifact_type: ArtifactType
    path: str
    artifact_id: str = field(
        default_factory=lambda: generate_id("rartifact")
    )
    description: str = ""
    mime_type: str = "text/markdown"
    version: int = 1
    content_hash: str = ""
    size_bytes: int = 0
    approved: bool = False
    producer: str = "research_director"
    source_ids: list[str] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)
    claim_ids: list[str] = field(default_factory=list)
    finding_ids: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)

    def __post_init__(self) -> None:
        self.name = _clean_text(self.name, field_name="name")
        self.artifact_type = _coerce_enum(
            self.artifact_type,
            ArtifactType,
            "artifact_type",
        )
        self.path = _clean_text(self.path, field_name="path")
        self.artifact_id = _clean_text(
            self.artifact_id, field_name="artifact_id"
        )
        self.description = _optional_text(self.description)
        self.mime_type = _clean_text(
            self.mime_type, field_name="mime_type"
        )
        if int(self.version) < 1:
            raise ResearchValidationError(
                "'version' debe ser al menos 1."
            )
        self.version = int(self.version)
        self.content_hash = _optional_text(self.content_hash)
        if int(self.size_bytes) < 0:
            raise ResearchValidationError(
                "'size_bytes' no puede ser negativo."
            )
        self.size_bytes = int(self.size_bytes)
        self.producer = _clean_text(
            self.producer, field_name="producer"
        )
        self.source_ids = _clean_id_list(self.source_ids)
        self.evidence_ids = _clean_id_list(self.evidence_ids)
        self.claim_ids = _clean_id_list(self.claim_ids)
        self.finding_ids = _clean_id_list(self.finding_ids)
        self.metadata = _clean_mapping(self.metadata)
        self.created_at = _validate_iso(
            self.created_at, field_name="created_at"
        )
        self.updated_at = _validate_iso(
            self.updated_at, field_name="updated_at"
        )


@dataclass(slots=True)
class ResearchReport(SerializableModel):
    project_id: str
    title: str
    executive_summary: str
    report_id: str = field(
        default_factory=lambda: generate_id("rreport")
    )
    status: ResearchStatus = ResearchStatus.IN_REVIEW
    methodology: str = ""
    scope: str = ""
    background: str = ""
    key_findings: list[ResearchFinding] = field(default_factory=list)
    questions: list[ResearchQuestion] = field(default_factory=list)
    sources: list[ResearchSource] = field(default_factory=list)
    citations: list[ResearchCitation] = field(default_factory=list)
    evidence: list[ResearchEvidence] = field(default_factory=list)
    claims: list[FactClaim] = field(default_factory=list)
    verifications: list[FactVerification] = field(default_factory=list)
    contradictions: list[ResearchContradiction] = field(default_factory=list)
    knowledge_gaps: list[KnowledgeGap] = field(default_factory=list)
    hypotheses: list[ResearchHypothesis] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    conclusions: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    bibliography: list[str] = field(default_factory=list)
    metrics: ResearchMetrics = field(default_factory=ResearchMetrics)
    publication_safe: bool = False
    fact_checked: bool = False
    human_review_required: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)

    def __post_init__(self) -> None:
        self.project_id = _clean_text(
            self.project_id, field_name="project_id"
        )
        self.title = _clean_text(self.title, field_name="title")
        self.executive_summary = _clean_text(
            self.executive_summary,
            field_name="executive_summary",
        )
        self.report_id = _clean_text(
            self.report_id, field_name="report_id"
        )
        self.status = _coerce_enum(
            self.status, ResearchStatus, "status"
        )
        self.methodology = _optional_text(self.methodology)
        self.scope = _optional_text(self.scope)
        self.background = _optional_text(self.background)

        self.key_findings = self._validate_collection(
            self.key_findings, ResearchFinding, "key_findings"
        )
        self.questions = self._validate_collection(
            self.questions, ResearchQuestion, "questions"
        )
        self.sources = self._validate_collection(
            self.sources, ResearchSource, "sources"
        )
        self.citations = self._validate_collection(
            self.citations, ResearchCitation, "citations"
        )
        self.evidence = self._validate_collection(
            self.evidence, ResearchEvidence, "evidence"
        )
        self.claims = self._validate_collection(
            self.claims, FactClaim, "claims"
        )
        self.verifications = self._validate_collection(
            self.verifications,
            FactVerification,
            "verifications",
        )
        self.contradictions = self._validate_collection(
            self.contradictions,
            ResearchContradiction,
            "contradictions",
        )
        self.knowledge_gaps = self._validate_collection(
            self.knowledge_gaps,
            KnowledgeGap,
            "knowledge_gaps",
        )
        self.hypotheses = self._validate_collection(
            self.hypotheses,
            ResearchHypothesis,
            "hypotheses",
        )

        self.limitations = _clean_string_list(self.limitations)
        self.conclusions = _clean_string_list(self.conclusions)
        self.recommendations = _clean_string_list(
            self.recommendations
        )
        self.bibliography = _clean_string_list(self.bibliography)
        if not isinstance(self.metrics, ResearchMetrics):
            raise ResearchValidationError(
                "'metrics' debe ser ResearchMetrics."
            )
        self.metadata = _clean_mapping(self.metadata)
        self.created_at = _validate_iso(
            self.created_at, field_name="created_at"
        )
        self.updated_at = _validate_iso(
            self.updated_at, field_name="updated_at"
        )

        if self.publication_safe and not self.fact_checked:
            raise ResearchValidationError(
                "Un informe publication_safe debe estar fact_checked."
            )
        self.validate_references()

    @staticmethod
    def _validate_collection(
        values: Sequence[Any],
        expected_type: type,
        field_name: str,
    ) -> list[Any]:
        output = list(values or [])
        if not all(isinstance(item, expected_type) for item in output):
            raise ResearchValidationError(
                f"'{field_name}' debe contener {expected_type.__name__}."
            )
        return output

    def validate_references(self) -> None:
        source_ids = {item.source_id for item in self.sources}
        evidence_ids = {item.evidence_id for item in self.evidence}
        claim_ids = {item.claim_id for item in self.claims}
        question_ids = {item.question_id for item in self.questions}

        for citation in self.citations:
            if citation.source_id not in source_ids:
                raise ResearchValidationError(
                    f"La cita '{citation.citation_id}' referencia "
                    "una fuente inexistente."
                )

        for item in self.evidence:
            if item.source_id not in source_ids:
                raise ResearchValidationError(
                    f"La evidencia '{item.evidence_id}' referencia "
                    "una fuente inexistente."
                )
            unknown_questions = set(item.question_ids) - question_ids
            if unknown_questions:
                raise ResearchValidationError(
                    f"La evidencia '{item.evidence_id}' referencia "
                    "preguntas inexistentes."
                )

        for claim in self.claims:
            unknown_evidence = set(claim.evidence_ids) - evidence_ids
            if unknown_evidence:
                raise ResearchValidationError(
                    f"La afirmación '{claim.claim_id}' referencia "
                    "evidencia inexistente."
                )

        for verification in self.verifications:
            if verification.claim_id not in claim_ids:
                raise ResearchValidationError(
                    f"La verificación '{verification.verification_id}' "
                    "referencia una afirmación inexistente."
                )

    @property
    def blocking_gaps(self) -> list[KnowledgeGap]:
        return [
            item
            for item in self.knowledge_gaps
            if item.blocking and not item.resolved
        ]

    @property
    def unresolved_contradictions(self) -> list[ResearchContradiction]:
        return [
            item for item in self.contradictions if not item.resolved
        ]


@dataclass(slots=True)
class ResearchResult(SerializableModel):
    project_id: str
    plan_id: str
    status: ResearchStatus
    success: bool
    summary: str
    result_id: str = field(
        default_factory=lambda: generate_id("rresult")
    )
    recommendation: str = ""
    report: Optional[ResearchReport] = None
    artifacts: list[ResearchArtifact] = field(default_factory=list)
    issues: list[ResearchIssue] = field(default_factory=list)
    risks: list[ResearchRisk] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    metrics: ResearchMetrics = field(default_factory=ResearchMetrics)
    publication_safe: bool = False
    ready_for_fact_checker: bool = False
    ready_for_strategy: bool = False
    data: dict[str, Any] = field(default_factory=dict)
    output_paths: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    started_at: str = ""
    completed_at: str = field(default_factory=utc_now_iso)

    def __post_init__(self) -> None:
        self.project_id = _clean_text(
            self.project_id, field_name="project_id"
        )
        self.plan_id = _clean_text(
            self.plan_id, field_name="plan_id"
        )
        self.status = _coerce_enum(
            self.status, ResearchStatus, "status"
        )
        self.summary = _clean_text(
            self.summary, field_name="summary"
        )
        self.result_id = _clean_text(
            self.result_id, field_name="result_id"
        )
        self.recommendation = _optional_text(
            self.recommendation
        )
        if self.report is not None and not isinstance(
            self.report, ResearchReport
        ):
            raise ResearchValidationError(
                "'report' debe ser ResearchReport o None."
            )
        if not all(
            isinstance(item, ResearchArtifact)
            for item in self.artifacts
        ):
            raise ResearchValidationError(
                "'artifacts' debe contener ResearchArtifact."
            )
        if not all(
            isinstance(item, ResearchIssue)
            for item in self.issues
        ):
            raise ResearchValidationError(
                "'issues' debe contener ResearchIssue."
            )
        if not all(
            isinstance(item, ResearchRisk)
            for item in self.risks
        ):
            raise ResearchValidationError(
                "'risks' debe contener ResearchRisk."
            )
        self.warnings = _clean_string_list(self.warnings)
        self.errors = _clean_string_list(self.errors)
        if not isinstance(self.metrics, ResearchMetrics):
            raise ResearchValidationError(
                "'metrics' debe ser ResearchMetrics."
            )
        self.data = _clean_mapping(self.data)
        self.output_paths = {
            str(key): str(value)
            for key, value in _clean_mapping(
                self.output_paths
            ).items()
        }
        self.metadata = _clean_mapping(self.metadata)
        self.started_at = _validate_iso(
            self.started_at, field_name="started_at"
        )
        self.completed_at = _validate_iso(
            self.completed_at, field_name="completed_at"
        )

        if self.success and self.errors:
            raise ResearchValidationError(
                "Un ResearchResult exitoso no puede contener errores."
            )
        if self.publication_safe and (
            self.report is None or not self.report.publication_safe
        ):
            raise ResearchValidationError(
                "publication_safe requiere un informe aprobado."
            )

    @property
    def blocking_issues(self) -> list[ResearchIssue]:
        return [
            item
            for item in self.issues
            if item.blocking and not item.resolved
        ]


# =============================================================================
# Configuración
# =============================================================================


@dataclass(slots=True)
class ResearchConfiguration(SerializableModel):
    enabled: bool = True
    strict_validation: bool = True
    output_root: str = "10_OUTPUT/research"
    persist_outputs: bool = True
    overwrite_existing: bool = False
    create_project_directory: bool = True
    default_language: str = "es-MX"
    default_citation_style: CitationStyle = CitationStyle.APA
    default_method: ResearchMethod = ResearchMethod.DESK_RESEARCH
    default_scope: ResearchScope = ResearchScope.EXPLORATORY
    max_questions: int = 40
    max_sources: int = 100
    max_evidence_items: int = 300
    max_claims: int = 200
    max_tasks: int = 50
    max_revisions_per_task: int = 2
    max_source_age_days: int = 1095
    minimum_sources_per_critical_claim: int = 2
    minimum_authoritative_sources: int = 2
    minimum_primary_sources: int = 1
    minimum_source_credibility_score: float = 7.0
    minimum_evidence_quality_score: float = 7.0
    minimum_fact_confidence_score: float = 8.0
    minimum_completeness_score: float = 8.0
    minimum_traceability_score: float = 9.0
    minimum_overall_quality_score: float = 8.0
    require_primary_sources: bool = True
    require_authoritative_sources: bool = True
    require_source_dates: bool = True
    require_access_dates: bool = True
    require_claim_traceability: bool = True
    require_independent_confirmation: bool = True
    require_fact_check_for_publication: bool = True
    require_human_review: bool = True
    allow_anonymous_sources: bool = False
    allow_generated_sources: bool = False
    allow_unverified_claims_in_draft: bool = True
    stop_on_blocking_gap: bool = True
    stop_on_critical_contradiction: bool = True
    detect_duplicate_sources: bool = True
    detect_duplicate_evidence: bool = True
    calculate_bias_risk: bool = True
    calculate_recency: bool = True
    required_artifacts: list[str] = field(
        default_factory=lambda: [
            "02_Investigacion.md",
            "02A_Registro_Fuentes.json",
            "02B_Matriz_Evidencia.json",
            "02C_Registro_Afirmaciones.json",
        ]
    )
    trusted_domains: list[str] = field(default_factory=list)
    blocked_domains: list[str] = field(default_factory=list)
    preferred_source_types: list[SourceType] = field(
        default_factory=lambda: [
            SourceType.PEER_REVIEWED_ARTICLE,
            SourceType.SYSTEMATIC_REVIEW,
            SourceType.GOVERNMENT_DOCUMENT,
            SourceType.OFFICIAL_STATISTICS,
            SourceType.LAW_OR_REGULATION,
            SourceType.TECHNICAL_STANDARD,
            SourceType.OFFICIAL_DOCUMENTATION,
        ]
    )
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.output_root = _clean_text(
            self.output_root, field_name="output_root"
        )
        self.default_language = _clean_text(
            self.default_language,
            field_name="default_language",
        )
        self.default_citation_style = _coerce_enum(
            self.default_citation_style,
            CitationStyle,
            "default_citation_style",
        )
        self.default_method = _coerce_enum(
            self.default_method,
            ResearchMethod,
            "default_method",
        )
        self.default_scope = _coerce_enum(
            self.default_scope,
            ResearchScope,
            "default_scope",
        )

        integer_rules = {
            "max_questions": 1,
            "max_sources": 1,
            "max_evidence_items": 1,
            "max_claims": 1,
            "max_tasks": 1,
            "max_revisions_per_task": 0,
            "max_source_age_days": 0,
            "minimum_sources_per_critical_claim": 1,
            "minimum_authoritative_sources": 0,
            "minimum_primary_sources": 0,
        }
        for field_name, minimum in integer_rules.items():
            value = int(getattr(self, field_name))
            if value < minimum:
                raise ResearchValidationError(
                    f"'{field_name}' debe ser >= {minimum}."
                )
            setattr(self, field_name, value)

        for field_name in (
            "minimum_source_credibility_score",
            "minimum_evidence_quality_score",
            "minimum_fact_confidence_score",
            "minimum_completeness_score",
            "minimum_traceability_score",
            "minimum_overall_quality_score",
        ):
            setattr(
                self,
                field_name,
                _validate_score(
                    getattr(self, field_name),
                    field_name=field_name,
                    allow_none=False,
                ),
            )

        self.required_artifacts = _clean_string_list(
            self.required_artifacts
        )
        self.trusted_domains = _clean_string_list(
            self.trusted_domains
        )
        self.blocked_domains = _clean_string_list(
            self.blocked_domains
        )
        self.preferred_source_types = [
            _coerce_enum(
                item,
                SourceType,
                "preferred_source_types",
            )
            for item in self.preferred_source_types
        ]
        self.preferred_source_types = list(
            dict.fromkeys(self.preferred_source_types)
        )
        self.metadata = _clean_mapping(self.metadata)

        overlap = {
            item.casefold() for item in self.trusted_domains
        } & {
            item.casefold() for item in self.blocked_domains
        }
        if overlap:
            raise ResearchValidationError(
                "Un dominio no puede estar simultáneamente en trusted_domains "
                "y blocked_domains."
            )

    def get_component_info(self) -> dict[str, Any]:
        return {
            "component": "ResearchDirectorModels",
            "version": RESEARCH_MODELS_VERSION,
            "enabled": self.enabled,
            "strict_validation": self.strict_validation,
            "default_method": self.default_method.value,
            "default_scope": self.default_scope.value,
            "default_citation_style": self.default_citation_style.value,
            "limits": {
                "questions": self.max_questions,
                "sources": self.max_sources,
                "evidence_items": self.max_evidence_items,
                "claims": self.max_claims,
                "tasks": self.max_tasks,
            },
            "quality_thresholds": {
                "source_credibility": self.minimum_source_credibility_score,
                "evidence_quality": self.minimum_evidence_quality_score,
                "fact_confidence": self.minimum_fact_confidence_score,
                "completeness": self.minimum_completeness_score,
                "traceability": self.minimum_traceability_score,
                "overall_quality": self.minimum_overall_quality_score,
            },
        }
