"""
CIPS — Master Producer Models
=============================

Modelos de datos oficiales para el componente Master Producer de CIPS.

Ruta del proyecto:
    08_SCRIPTS/master_producer_models.py

Este módulo contiene únicamente enumeraciones, estructuras de datos,
validaciones y serialización. No contiene llamadas a IA, persistencia ni
lógica de orquestación.
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields, is_dataclass
from datetime import datetime, timezone
from enum import Enum
import json
from pathlib import Path
from typing import Any, ClassVar, Iterable, Mapping, Optional
from uuid import uuid4


MODEL_VERSION = "1.0.0"


__all__ = [
    "MODEL_VERSION",
    "ProductionPriority",
    "ProjectStatus",
    "PlatformType",
    "ContentType",
    "QualityLevel",
    "MonetizationObjective",
    "SpecialistRole",
    "TaskStatus",
    "CheckpointStatus",
    "RiskLevel",
    "ProductionBrief",
    "ProductionContext",
    "SpecialistAssignment",
    "ProductionTask",
    "ProductionPlan",
    "ProductionCheckpoint",
    "ProductionMetrics",
    "ProductionArtifact",
    "ProductionIssue",
    "ProductionResult",
    "MasterProducerConfiguration",
    "utc_now_iso",
]


def utc_now_iso() -> str:
    """Devuelve la fecha y hora actual en UTC con formato ISO 8601."""
    return datetime.now(timezone.utc).isoformat()


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:16]}"


def _clean_text(value: Any, *, field_name: str, required: bool = False) -> str:
    text = "" if value is None else str(value).strip()
    if required and not text:
        raise ValueError(f"'{field_name}' es obligatorio.")
    return text


def _clean_string_list(values: Optional[Iterable[Any]]) -> list[str]:
    if values is None:
        return []
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value).strip()
        if not text:
            continue
        key = text.casefold()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(text)
    return normalized


def _ensure_mapping(value: Optional[Mapping[str, Any]]) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise TypeError("Se esperaba un objeto de tipo Mapping.")
    return dict(value)


def _to_primitive(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Path):
        return str(value)
    if is_dataclass(value):
        return {item.name: _to_primitive(getattr(value, item.name)) for item in fields(value)}
    if isinstance(value, Mapping):
        return {str(key): _to_primitive(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_to_primitive(item) for item in value]
    return value


class SerializableModel:
    """Mixin común de serialización para todos los modelos."""

    schema_version: ClassVar[str] = MODEL_VERSION

    def to_dict(self) -> dict[str, Any]:
        return _to_primitive(self)

    def to_json(self, *, indent: int = 2, ensure_ascii: bool = False) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=ensure_ascii)


class StrEnum(str, Enum):
    def __str__(self) -> str:
        return self.value


class ProductionPriority(StrEnum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"
    CRITICAL = "critical"


class ProjectStatus(StrEnum):
    DRAFT = "draft"
    PLANNING = "planning"
    READY = "ready"
    IN_PRODUCTION = "in_production"
    PAUSED = "paused"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    COMPLETED = "completed"
    PUBLISHED = "published"
    ARCHIVED = "archived"
    FAILED = "failed"


class PlatformType(StrEnum):
    TIKTOK = "tiktok"
    YOUTUBE_SHORTS = "youtube_shorts"
    YOUTUBE_LONG = "youtube_long"
    INSTAGRAM_REELS = "instagram_reels"
    INSTAGRAM_POST = "instagram_post"
    INSTAGRAM_CAROUSEL = "instagram_carousel"
    FACEBOOK_REELS = "facebook_reels"
    FACEBOOK_POST = "facebook_post"
    LINKEDIN = "linkedin"
    X = "x"
    THREADS = "threads"
    PINTEREST = "pinterest"
    BLOG = "blog"
    PODCAST = "podcast"
    NEWSLETTER = "newsletter"
    MULTIPLATFORM = "multiplatform"
    OTHER = "other"


class ContentType(StrEnum):
    SHORT_VIDEO = "short_video"
    LONG_VIDEO = "long_video"
    ARTICLE = "article"
    SOCIAL_POST = "social_post"
    CAROUSEL = "carousel"
    PODCAST_EPISODE = "podcast_episode"
    EMAIL = "email"
    SCRIPT = "script"
    IMAGE_SET = "image_set"
    CAMPAIGN = "campaign"
    MULTIFORMAT_PACKAGE = "multiformat_package"
    OTHER = "other"


class QualityLevel(StrEnum):
    DRAFT = "draft"
    STANDARD = "standard"
    PROFESSIONAL = "professional"
    PREMIUM = "premium"
    PUBLICATION_READY = "publication_ready"


class MonetizationObjective(StrEnum):
    NONE = "none"
    AUDIENCE_GROWTH = "audience_growth"
    PLATFORM_REVENUE = "platform_revenue"
    LEAD_GENERATION = "lead_generation"
    AFFILIATE_MARKETING = "affiliate_marketing"
    PRODUCT_SALES = "product_sales"
    SERVICE_SALES = "service_sales"
    SPONSORSHIP = "sponsorship"
    BRAND_AWARENESS = "brand_awareness"
    COMMUNITY_GROWTH = "community_growth"
    NEWSLETTER_GROWTH = "newsletter_growth"
    COURSE_SALES = "course_sales"
    DIGITAL_PRODUCT_SALES = "digital_product_sales"
    MULTIPLE = "multiple"
    OTHER = "other"


class SpecialistRole(StrEnum):
    MASTER_PRODUCER = "master_producer"
    RESEARCH_DIRECTOR = "research_director"
    STRATEGY_DIRECTOR = "strategy_director"
    CREATIVE_DIRECTOR = "creative_director"
    SCREENWRITING_DIRECTOR = "screenwriting_director"
    STORYBOARD_DIRECTOR = "storyboard_director"
    GENERATIVE_ART_DIRECTOR = "generative_art_director"
    AUDIO_DIRECTOR = "audio_director"
    SEO_DIRECTOR = "seo_director"
    PLATFORM_DIRECTOR = "platform_director"
    MARKETING_DIRECTOR = "marketing_director"
    MONETIZATION_DIRECTOR = "monetization_director"
    FACT_CHECKER = "fact_checker"
    LEGAL_REVIEWER = "legal_reviewer"
    QUALITY_DIRECTOR = "quality_director"
    PUBLISHING_MANAGER = "publishing_manager"
    ANALYTICS_DIRECTOR = "analytics_director"
    CUSTOM = "custom"


class TaskStatus(StrEnum):
    PENDING = "pending"
    BLOCKED = "blocked"
    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


class CheckpointStatus(StrEnum):
    PENDING = "pending"
    PASSED = "passed"
    FAILED = "failed"
    WAIVED = "waived"
    NEEDS_REVIEW = "needs_review"


class RiskLevel(StrEnum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(slots=True)
class ProductionBrief(SerializableModel):
    """Solicitud inicial normalizada para un proyecto de contenido."""

    topic: str
    objective: str
    audience: str
    platform: PlatformType
    content_type: ContentType
    project_name: str = ""
    project_id: str = field(default_factory=lambda: _new_id("project"))
    language: str = "es-MX"
    duration_seconds: Optional[int] = None
    quality_level: QualityLevel = QualityLevel.PROFESSIONAL
    monetization_objective: MonetizationObjective = MonetizationObjective.AUDIENCE_GROWTH
    priority: ProductionPriority = ProductionPriority.NORMAL
    desired_action: str = ""
    brand_name: str = ""
    brand_voice: str = ""
    tone: str = ""
    call_to_action: str = ""
    key_messages: list[str] = field(default_factory=list)
    mandatory_points: list[str] = field(default_factory=list)
    restrictions: list[str] = field(default_factory=list)
    prohibited_claims: list[str] = field(default_factory=list)
    reference_materials: list[str] = field(default_factory=list)
    target_keywords: list[str] = field(default_factory=list)
    requires_research: bool = True
    requires_fact_check: bool = True
    requires_legal_review: bool = False
    requires_sources: bool = True
    deadline_iso: Optional[str] = None
    created_at: str = field(default_factory=utc_now_iso)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.topic = _clean_text(self.topic, field_name="topic", required=True)
        self.objective = _clean_text(self.objective, field_name="objective", required=True)
        self.audience = _clean_text(self.audience, field_name="audience", required=True)
        self.project_name = _clean_text(self.project_name or self.topic, field_name="project_name", required=True)
        self.project_id = _clean_text(self.project_id, field_name="project_id", required=True)
        self.language = _clean_text(self.language, field_name="language", required=True)
        self.platform = PlatformType(self.platform)
        self.content_type = ContentType(self.content_type)
        self.quality_level = QualityLevel(self.quality_level)
        self.monetization_objective = MonetizationObjective(self.monetization_objective)
        self.priority = ProductionPriority(self.priority)
        if self.duration_seconds is not None:
            if not isinstance(self.duration_seconds, int):
                raise TypeError("'duration_seconds' debe ser entero o None.")
            if self.duration_seconds <= 0:
                raise ValueError("'duration_seconds' debe ser mayor que cero.")
        self.desired_action = _clean_text(self.desired_action, field_name="desired_action")
        self.brand_name = _clean_text(self.brand_name, field_name="brand_name")
        self.brand_voice = _clean_text(self.brand_voice, field_name="brand_voice")
        self.tone = _clean_text(self.tone, field_name="tone")
        self.call_to_action = _clean_text(self.call_to_action, field_name="call_to_action")
        self.key_messages = _clean_string_list(self.key_messages)
        self.mandatory_points = _clean_string_list(self.mandatory_points)
        self.restrictions = _clean_string_list(self.restrictions)
        self.prohibited_claims = _clean_string_list(self.prohibited_claims)
        self.reference_materials = _clean_string_list(self.reference_materials)
        self.target_keywords = _clean_string_list(self.target_keywords)
        self.metadata = _ensure_mapping(self.metadata)

    def validate_for_production(self) -> list[str]:
        issues: list[str] = []
        if self.platform is PlatformType.OTHER and not self.metadata.get("platform_name"):
            issues.append("La plataforma es 'other' pero metadata.platform_name no fue definido.")
        if self.content_type is ContentType.OTHER and not self.metadata.get("content_type_name"):
            issues.append("El tipo de contenido es 'other' pero metadata.content_type_name no fue definido.")
        if self.requires_sources and not self.requires_research:
            issues.append("requires_sources=True requiere normalmente requires_research=True.")
        return issues


@dataclass(slots=True)
class ProductionContext(SerializableModel):
    """Contexto enriquecido que acompaña al proyecto durante su producción."""

    brief: ProductionBrief
    context_id: str = field(default_factory=lambda: _new_id("context"))
    current_status: ProjectStatus = ProjectStatus.DRAFT
    research_summary: str = ""
    strategic_summary: str = ""
    creative_direction: str = ""
    approved_script_summary: str = ""
    verified_facts: list[str] = field(default_factory=list)
    source_references: list[str] = field(default_factory=list)
    known_risks: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)
    prior_decisions: list[str] = field(default_factory=list)
    available_assets: list[str] = field(default_factory=list)
    output_root: str = ""
    working_data: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)

    def __post_init__(self) -> None:
        if not isinstance(self.brief, ProductionBrief):
            raise TypeError("'brief' debe ser ProductionBrief.")
        self.context_id = _clean_text(self.context_id, field_name="context_id", required=True)
        self.current_status = ProjectStatus(self.current_status)
        self.research_summary = _clean_text(self.research_summary, field_name="research_summary")
        self.strategic_summary = _clean_text(self.strategic_summary, field_name="strategic_summary")
        self.creative_direction = _clean_text(self.creative_direction, field_name="creative_direction")
        self.approved_script_summary = _clean_text(self.approved_script_summary, field_name="approved_script_summary")
        self.verified_facts = _clean_string_list(self.verified_facts)
        self.source_references = _clean_string_list(self.source_references)
        self.known_risks = _clean_string_list(self.known_risks)
        self.assumptions = _clean_string_list(self.assumptions)
        self.open_questions = _clean_string_list(self.open_questions)
        self.prior_decisions = _clean_string_list(self.prior_decisions)
        self.available_assets = _clean_string_list(self.available_assets)
        self.output_root = _clean_text(self.output_root, field_name="output_root")
        self.working_data = _ensure_mapping(self.working_data)

    def touch(self) -> None:
        self.updated_at = utc_now_iso()


@dataclass(slots=True)
class SpecialistAssignment(SerializableModel):
    """Asignación formal de un especialista a un proyecto."""

    role: SpecialistRole
    mission: str
    expected_output: str
    assignment_id: str = field(default_factory=lambda: _new_id("assignment"))
    specialist_name: str = ""
    required: bool = True
    execution_order: int = 0
    depends_on_roles: list[SpecialistRole] = field(default_factory=list)
    input_artifacts: list[str] = field(default_factory=list)
    output_artifacts: list[str] = field(default_factory=list)
    quality_threshold: float = 8.0
    max_revisions: int = 2
    instructions: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.role = SpecialistRole(self.role)
        self.mission = _clean_text(self.mission, field_name="mission", required=True)
        self.expected_output = _clean_text(self.expected_output, field_name="expected_output", required=True)
        self.assignment_id = _clean_text(self.assignment_id, field_name="assignment_id", required=True)
        self.specialist_name = _clean_text(self.specialist_name or self.role.value, field_name="specialist_name", required=True)
        if self.execution_order < 0:
            raise ValueError("'execution_order' no puede ser negativo.")
        self.quality_threshold = float(self.quality_threshold)
        if not 0.0 <= self.quality_threshold <= 10.0:
            raise ValueError("'quality_threshold' debe estar entre 0 y 10.")
        if self.max_revisions < 0:
            raise ValueError("'max_revisions' no puede ser negativo.")
        self.depends_on_roles = [SpecialistRole(item) for item in self.depends_on_roles]
        self.input_artifacts = _clean_string_list(self.input_artifacts)
        self.output_artifacts = _clean_string_list(self.output_artifacts)
        self.instructions = _clean_string_list(self.instructions)
        self.metadata = _ensure_mapping(self.metadata)


@dataclass(slots=True)
class ProductionTask(SerializableModel):
    """Unidad ejecutable dentro de un plan de producción."""

    title: str
    role: SpecialistRole
    objective: str
    expected_output: str
    task_id: str = field(default_factory=lambda: _new_id("task"))
    status: TaskStatus = TaskStatus.PENDING
    sequence: int = 0
    required: bool = True
    dependency_task_ids: list[str] = field(default_factory=list)
    input_artifacts: list[str] = field(default_factory=list)
    output_artifacts: list[str] = field(default_factory=list)
    instructions: list[str] = field(default_factory=list)
    acceptance_criteria: list[str] = field(default_factory=list)
    estimated_minutes: float = 0.0
    estimated_cost: float = 0.0
    max_attempts: int = 2
    attempt_count: int = 0
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error_message: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.title = _clean_text(self.title, field_name="title", required=True)
        self.role = SpecialistRole(self.role)
        self.objective = _clean_text(self.objective, field_name="objective", required=True)
        self.expected_output = _clean_text(self.expected_output, field_name="expected_output", required=True)
        self.task_id = _clean_text(self.task_id, field_name="task_id", required=True)
        self.status = TaskStatus(self.status)
        if self.sequence < 0:
            raise ValueError("'sequence' no puede ser negativo.")
        if self.estimated_minutes < 0 or self.estimated_cost < 0:
            raise ValueError("Las estimaciones no pueden ser negativas.")
        if self.max_attempts <= 0:
            raise ValueError("'max_attempts' debe ser mayor que cero.")
        if self.attempt_count < 0:
            raise ValueError("'attempt_count' no puede ser negativo.")
        self.dependency_task_ids = _clean_string_list(self.dependency_task_ids)
        self.input_artifacts = _clean_string_list(self.input_artifacts)
        self.output_artifacts = _clean_string_list(self.output_artifacts)
        self.instructions = _clean_string_list(self.instructions)
        self.acceptance_criteria = _clean_string_list(self.acceptance_criteria)
        self.error_message = _clean_text(self.error_message, field_name="error_message")
        self.metadata = _ensure_mapping(self.metadata)

    @property
    def is_terminal(self) -> bool:
        return self.status in {TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.SKIPPED, TaskStatus.CANCELLED}

    @property
    def can_retry(self) -> bool:
        return self.status is TaskStatus.FAILED and self.attempt_count < self.max_attempts


@dataclass(slots=True)
class ProductionPlan(SerializableModel):
    """Plan de ejecución generado por el Master Producer."""

    project_id: str
    strategy_summary: str
    tasks: list[ProductionTask]
    plan_id: str = field(default_factory=lambda: _new_id("plan"))
    plan_version: int = 1
    status: ProjectStatus = ProjectStatus.PLANNING
    assignments: list[SpecialistAssignment] = field(default_factory=list)
    expected_artifacts: list[str] = field(default_factory=list)
    success_criteria: list[str] = field(default_factory=list)
    estimated_total_minutes: float = 0.0
    estimated_total_cost: float = 0.0
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.project_id = _clean_text(self.project_id, field_name="project_id", required=True)
        self.strategy_summary = _clean_text(self.strategy_summary, field_name="strategy_summary", required=True)
        self.plan_id = _clean_text(self.plan_id, field_name="plan_id", required=True)
        self.status = ProjectStatus(self.status)
        if self.plan_version <= 0:
            raise ValueError("'plan_version' debe ser mayor que cero.")
        if not isinstance(self.tasks, list):
            self.tasks = list(self.tasks)
        if not all(isinstance(task, ProductionTask) for task in self.tasks):
            raise TypeError("'tasks' solo puede contener ProductionTask.")
        if not isinstance(self.assignments, list):
            self.assignments = list(self.assignments)
        if not all(isinstance(item, SpecialistAssignment) for item in self.assignments):
            raise TypeError("'assignments' solo puede contener SpecialistAssignment.")
        self.expected_artifacts = _clean_string_list(self.expected_artifacts)
        self.success_criteria = _clean_string_list(self.success_criteria)
        self.metadata = _ensure_mapping(self.metadata)
        self.recalculate_estimates()
        self.validate_dependencies()

    def recalculate_estimates(self) -> None:
        self.estimated_total_minutes = round(sum(task.estimated_minutes for task in self.tasks), 4)
        self.estimated_total_cost = round(sum(task.estimated_cost for task in self.tasks), 6)
        self.updated_at = utc_now_iso()

    def validate_dependencies(self) -> None:
        task_ids = [task.task_id for task in self.tasks]
        duplicate_ids = {task_id for task_id in task_ids if task_ids.count(task_id) > 1}
        if duplicate_ids:
            raise ValueError("Existen task_id duplicados: " + ", ".join(sorted(duplicate_ids)))
        known_ids = set(task_ids)
        for task in self.tasks:
            missing = set(task.dependency_task_ids) - known_ids
            if missing:
                raise ValueError(f"La tarea '{task.task_id}' depende de tareas inexistentes: " + ", ".join(sorted(missing)))
            if task.task_id in task.dependency_task_ids:
                raise ValueError(f"La tarea '{task.task_id}' no puede depender de sí misma.")
        graph = {task.task_id: list(task.dependency_task_ids) for task in self.tasks}
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(task_id: str) -> None:
            if task_id in visited:
                return
            if task_id in visiting:
                raise ValueError(f"Se detectó un ciclo de dependencias en '{task_id}'.")
            visiting.add(task_id)
            for dependency_id in graph.get(task_id, []):
                visit(dependency_id)
            visiting.remove(task_id)
            visited.add(task_id)

        for task_id in graph:
            visit(task_id)

    def ordered_tasks(self) -> list[ProductionTask]:
        return sorted(self.tasks, key=lambda task: (task.sequence, task.task_id))

    def ready_tasks(self) -> list[ProductionTask]:
        completed_ids = {task.task_id for task in self.tasks if task.status is TaskStatus.COMPLETED}
        return [
            task
            for task in self.ordered_tasks()
            if task.status in {TaskStatus.PENDING, TaskStatus.READY}
            and set(task.dependency_task_ids).issubset(completed_ids)
        ]


@dataclass(slots=True)
class ProductionCheckpoint(SerializableModel):
    name: str
    criteria: list[str]
    checkpoint_id: str = field(default_factory=lambda: _new_id("checkpoint"))
    status: CheckpointStatus = CheckpointStatus.PENDING
    stage: str = ""
    reviewer_role: SpecialistRole = SpecialistRole.QUALITY_DIRECTOR
    score: Optional[float] = None
    findings: list[str] = field(default_factory=list)
    required_actions: list[str] = field(default_factory=list)
    reviewed_at: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.name = _clean_text(self.name, field_name="name", required=True)
        self.criteria = _clean_string_list(self.criteria)
        if not self.criteria:
            raise ValueError("'criteria' debe contener al menos un criterio.")
        self.checkpoint_id = _clean_text(self.checkpoint_id, field_name="checkpoint_id", required=True)
        self.status = CheckpointStatus(self.status)
        self.stage = _clean_text(self.stage, field_name="stage")
        self.reviewer_role = SpecialistRole(self.reviewer_role)
        if self.score is not None:
            self.score = float(self.score)
            if not 0.0 <= self.score <= 10.0:
                raise ValueError("'score' debe estar entre 0 y 10.")
        self.findings = _clean_string_list(self.findings)
        self.required_actions = _clean_string_list(self.required_actions)
        self.metadata = _ensure_mapping(self.metadata)


@dataclass(slots=True)
class ProductionMetrics(SerializableModel):
    total_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    skipped_tasks: int = 0
    revision_count: int = 0
    elapsed_seconds: float = 0.0
    estimated_cost: float = 0.0
    actual_cost: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    quality_score: Optional[float] = None
    publication_readiness_score: Optional[float] = None
    monetization_score: Optional[float] = None
    fact_confidence_score: Optional[float] = None
    generated_artifacts: int = 0
    warnings_count: int = 0
    errors_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        integer_fields = (
            "total_tasks", "completed_tasks", "failed_tasks", "skipped_tasks",
            "revision_count", "input_tokens", "output_tokens",
            "generated_artifacts", "warnings_count", "errors_count",
        )
        for field_name in integer_fields:
            value = getattr(self, field_name)
            if not isinstance(value, int):
                raise TypeError(f"'{field_name}' debe ser entero.")
            if value < 0:
                raise ValueError(f"'{field_name}' no puede ser negativo.")
        for field_name in ("elapsed_seconds", "estimated_cost", "actual_cost"):
            value = float(getattr(self, field_name))
            if value < 0:
                raise ValueError(f"'{field_name}' no puede ser negativo.")
            setattr(self, field_name, value)
        for field_name in ("quality_score", "publication_readiness_score", "monetization_score", "fact_confidence_score"):
            value = getattr(self, field_name)
            if value is None:
                continue
            value = float(value)
            if not 0.0 <= value <= 10.0:
                raise ValueError(f"'{field_name}' debe estar entre 0 y 10.")
            setattr(self, field_name, value)
        self.metadata = _ensure_mapping(self.metadata)

    @property
    def completion_rate(self) -> float:
        return 0.0 if self.total_tasks == 0 else round(self.completed_tasks / self.total_tasks, 4)

    @property
    def success_rate(self) -> float:
        attempted = self.completed_tasks + self.failed_tasks
        return 0.0 if attempted == 0 else round(self.completed_tasks / attempted, 4)


@dataclass(slots=True)
class ProductionArtifact(SerializableModel):
    name: str
    artifact_type: str
    path: str
    artifact_id: str = field(default_factory=lambda: _new_id("artifact"))
    producer_role: SpecialistRole = SpecialistRole.MASTER_PRODUCER
    version: int = 1
    status: str = "generated"
    content_hash: str = ""
    mime_type: str = "text/markdown"
    size_bytes: Optional[int] = None
    approved: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.name = _clean_text(self.name, field_name="name", required=True)
        self.artifact_type = _clean_text(self.artifact_type, field_name="artifact_type", required=True)
        self.path = _clean_text(self.path, field_name="path", required=True)
        self.artifact_id = _clean_text(self.artifact_id, field_name="artifact_id", required=True)
        self.producer_role = SpecialistRole(self.producer_role)
        if self.version <= 0:
            raise ValueError("'version' debe ser mayor que cero.")
        if self.size_bytes is not None and self.size_bytes < 0:
            raise ValueError("'size_bytes' no puede ser negativo.")
        self.status = _clean_text(self.status, field_name="status", required=True)
        self.content_hash = _clean_text(self.content_hash, field_name="content_hash")
        self.mime_type = _clean_text(self.mime_type, field_name="mime_type", required=True)
        self.metadata = _ensure_mapping(self.metadata)


@dataclass(slots=True)
class ProductionIssue(SerializableModel):
    message: str
    source: str
    issue_id: str = field(default_factory=lambda: _new_id("issue"))
    risk_level: RiskLevel = RiskLevel.MEDIUM
    code: str = ""
    blocking: bool = False
    recommended_action: str = ""
    related_task_id: str = ""
    created_at: str = field(default_factory=utc_now_iso)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.message = _clean_text(self.message, field_name="message", required=True)
        self.source = _clean_text(self.source, field_name="source", required=True)
        self.issue_id = _clean_text(self.issue_id, field_name="issue_id", required=True)
        self.risk_level = RiskLevel(self.risk_level)
        self.code = _clean_text(self.code, field_name="code")
        self.recommended_action = _clean_text(self.recommended_action, field_name="recommended_action")
        self.related_task_id = _clean_text(self.related_task_id, field_name="related_task_id")
        self.metadata = _ensure_mapping(self.metadata)


@dataclass(slots=True)
class ProductionResult(SerializableModel):
    project_id: str
    status: ProjectStatus
    success: bool
    result_id: str = field(default_factory=lambda: _new_id("result"))
    plan_id: str = ""
    summary: str = ""
    recommendation: str = ""
    publication_ready: bool = False
    artifacts: list[ProductionArtifact] = field(default_factory=list)
    checkpoints: list[ProductionCheckpoint] = field(default_factory=list)
    issues: list[ProductionIssue] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    metrics: ProductionMetrics = field(default_factory=ProductionMetrics)
    data: dict[str, Any] = field(default_factory=dict)
    output_paths: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    started_at: Optional[str] = None
    completed_at: str = field(default_factory=utc_now_iso)

    def __post_init__(self) -> None:
        self.project_id = _clean_text(self.project_id, field_name="project_id", required=True)
        self.status = ProjectStatus(self.status)
        self.result_id = _clean_text(self.result_id, field_name="result_id", required=True)
        self.plan_id = _clean_text(self.plan_id, field_name="plan_id")
        self.summary = _clean_text(self.summary, field_name="summary")
        self.recommendation = _clean_text(self.recommendation, field_name="recommendation")
        if not all(isinstance(item, ProductionArtifact) for item in self.artifacts):
            raise TypeError("'artifacts' solo puede contener ProductionArtifact.")
        if not all(isinstance(item, ProductionCheckpoint) for item in self.checkpoints):
            raise TypeError("'checkpoints' solo puede contener ProductionCheckpoint.")
        if not all(isinstance(item, ProductionIssue) for item in self.issues):
            raise TypeError("'issues' solo puede contener ProductionIssue.")
        if not isinstance(self.metrics, ProductionMetrics):
            raise TypeError("'metrics' debe ser ProductionMetrics.")
        self.warnings = _clean_string_list(self.warnings)
        self.errors = _clean_string_list(self.errors)
        self.data = _ensure_mapping(self.data)
        self.output_paths = {str(key): str(value) for key, value in _ensure_mapping(self.output_paths).items()}
        self.metadata = _ensure_mapping(self.metadata)
        if self.success and self.errors:
            raise ValueError("Un ProductionResult exitoso no puede contener errores.")
        if self.publication_ready and not self.success:
            raise ValueError("publication_ready=True requiere success=True.")

    @property
    def blocking_issues(self) -> list[ProductionIssue]:
        return [issue for issue in self.issues if issue.blocking]

    @property
    def approved_checkpoints(self) -> int:
        return sum(checkpoint.status is CheckpointStatus.PASSED for checkpoint in self.checkpoints)


@dataclass(slots=True)
class MasterProducerConfiguration(SerializableModel):
    """Configuración operativa del Master Producer."""

    enabled: bool = True
    default_language: str = "es-MX"
    default_quality_level: QualityLevel = QualityLevel.PROFESSIONAL
    default_priority: ProductionPriority = ProductionPriority.NORMAL
    persist_outputs: bool = True
    output_root: str = "10_OUTPUT/production"
    create_project_directory: bool = True
    overwrite_existing: bool = False
    enable_research: bool = True
    enable_fact_check: bool = True
    enable_legal_review_when_required: bool = True
    enable_quality_review: bool = True
    enable_monetization_review: bool = True
    stop_on_blocking_error: bool = True
    continue_on_optional_failure: bool = True
    max_revisions_per_task: int = 2
    max_total_tasks: int = 50
    minimum_quality_score: float = 8.0
    minimum_publication_readiness_score: float = 8.0
    minimum_fact_confidence_score: float = 8.0
    include_debug_metadata: bool = False
    include_intermediate_artifacts: bool = True
    strict_validation: bool = True
    required_final_artifacts: list[str] = field(default_factory=lambda: [
        "README.md",
        "01_Brief.md",
        "02_Investigacion.md",
        "03_Estrategia.md",
        "04_Concepto_Creativo.md",
        "05_Guion.md",
        "06_Storyboard.md",
        "07_Prompts_Imagen.md",
        "08_Prompts_Video.md",
        "09_Audio.md",
        "10_SEO.md",
        "11_Publicacion.md",
        "12_Monetizacion.md",
        "13_QA.md",
        "14_Checklist.md",
    ])
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.default_language = _clean_text(self.default_language, field_name="default_language", required=True)
        self.default_quality_level = QualityLevel(self.default_quality_level)
        self.default_priority = ProductionPriority(self.default_priority)
        self.output_root = _clean_text(self.output_root, field_name="output_root", required=True)
        if self.max_revisions_per_task < 0:
            raise ValueError("'max_revisions_per_task' no puede ser negativo.")
        if self.max_total_tasks <= 0:
            raise ValueError("'max_total_tasks' debe ser mayor que cero.")
        for field_name in ("minimum_quality_score", "minimum_publication_readiness_score", "minimum_fact_confidence_score"):
            value = float(getattr(self, field_name))
            if not 0.0 <= value <= 10.0:
                raise ValueError(f"'{field_name}' debe estar entre 0 y 10.")
            setattr(self, field_name, value)
        self.required_final_artifacts = _clean_string_list(self.required_final_artifacts)
        self.metadata = _ensure_mapping(self.metadata)

    def get_component_info(self) -> dict[str, Any]:
        return {
            "component": "MasterProducerModels",
            "model_version": MODEL_VERSION,
            "enabled": self.enabled,
            "persist_outputs": self.persist_outputs,
            "output_root": self.output_root,
            "strict_validation": self.strict_validation,
            "maximum_tasks": self.max_total_tasks,
            "minimum_quality_score": self.minimum_quality_score,
            "required_final_artifacts": len(self.required_final_artifacts),
        }