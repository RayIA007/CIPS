"""
CIPS — Master Producer
======================

Orquestador principal del Estudio Profesional de Producción de Contenido CIPS.

Ruta recomendada:
    08_SCRIPTS/master_producer.py

Responsabilidades:
- Validar solicitudes de producción.
- Crear y enriquecer el contexto operativo.
- Seleccionar especialistas.
- Construir asignaciones y tareas.
- Definir dependencias.
- Generar planes de producción.
- Preparar prompts para el Master Producer.
- Ejecutar tareas mediante adaptadores externos opcionales.
- Consolidar artefactos, métricas, incidencias y resultados.
- Exportar planes, resúmenes y manifiestos de proyecto.

Este módulo no depende de un proveedor específico de IA.
La ejecución real se inyecta mediante un callable compatible con TaskExecutor.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import logging
from pathlib import Path
import time
from typing import Any, Callable, Iterable, Mapping, Optional, Protocol, Sequence

try:
    from master_producer_models import (
        CheckpointStatus,
        ContentType,
        MasterProducerConfiguration,
        MonetizationObjective,
        PlatformType,
        ProductionArtifact,
        ProductionBrief,
        ProductionCheckpoint,
        ProductionContext,
        ProductionIssue,
        ProductionMetrics,
        ProductionPlan,
        ProductionPriority,
        ProductionResult,
        ProductionTask,
        ProjectStatus,
        QualityLevel,
        RiskLevel,
        SpecialistAssignment,
        SpecialistRole,
        TaskStatus,
        utc_now_iso,
    )
    from master_producer_prompt_builder import (
        MasterProducerPromptBuilder,
        PromptBuildError,
        PromptPackage,
    )
    from artifact_store import ArtifactCollisionError, CollisionPolicy
    from metadata_store import MetadataStore
    from text_store import TextStore
    from workspace_models import WorkspaceIdentity
    from workspace_resolver import WorkspaceResolver
except ImportError:  # Permite uso como parte de un paquete.
    from .master_producer_models import (
        CheckpointStatus,
        ContentType,
        MasterProducerConfiguration,
        MonetizationObjective,
        PlatformType,
        ProductionArtifact,
        ProductionBrief,
        ProductionCheckpoint,
        ProductionContext,
        ProductionIssue,
        ProductionMetrics,
        ProductionPlan,
        ProductionPriority,
        ProductionResult,
        ProductionTask,
        ProjectStatus,
        QualityLevel,
        RiskLevel,
        SpecialistAssignment,
        SpecialistRole,
        TaskStatus,
        utc_now_iso,
    )
    from .master_producer_prompt_builder import (
        MasterProducerPromptBuilder,
        PromptBuildError,
        PromptPackage,
    )
    from .artifact_store import ArtifactCollisionError, CollisionPolicy
    from .metadata_store import MetadataStore
    from .text_store import TextStore
    from .workspace_models import WorkspaceIdentity
    from .workspace_resolver import WorkspaceResolver


MASTER_PRODUCER_VERSION = "1.0.0"


__all__ = [
    "MASTER_PRODUCER_VERSION",
    "MasterProducerError",
    "BriefValidationError",
    "PlanValidationError",
    "TaskExecutionError",
    "TaskExecutionOutput",
    "TaskExecutor",
    "MasterProducer",
    "create_master_producer",
]


LOGGER = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Excepciones
# ---------------------------------------------------------------------------


class MasterProducerError(RuntimeError):
    """Error base del componente Master Producer."""


class BriefValidationError(MasterProducerError):
    """La solicitud no cumple las condiciones mínimas de producción."""


class PlanValidationError(MasterProducerError):
    """El plan contiene una estructura, dependencia o regla inválida."""


class TaskExecutionError(MasterProducerError):
    """Una tarea no pudo ejecutarse correctamente."""


# ---------------------------------------------------------------------------
# Contrato de ejecución externa
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class TaskExecutionOutput:
    """
    Resultado normalizado de un ejecutor externo.

    Un adaptador de IA, agente, script o servicio puede devolver esta estructura.
    """

    success: bool
    content: str = ""
    artifacts: list[ProductionArtifact] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    data: dict[str, Any] = field(default_factory=dict)
    input_tokens: int = 0
    output_tokens: int = 0
    cost: float = 0.0
    quality_score: Optional[float] = None
    fact_confidence_score: Optional[float] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.content = str(self.content or "").strip()
        self.warnings = _normalize_strings(self.warnings)
        self.errors = _normalize_strings(self.errors)
        self.data = dict(self.data or {})
        self.metadata = dict(self.metadata or {})

        if not all(isinstance(item, ProductionArtifact) for item in self.artifacts):
            raise TypeError("'artifacts' debe contener ProductionArtifact.")

        if self.input_tokens < 0 or self.output_tokens < 0:
            raise ValueError("Los tokens no pueden ser negativos.")
        if self.cost < 0:
            raise ValueError("'cost' no puede ser negativo.")

        for name in ("quality_score", "fact_confidence_score"):
            value = getattr(self, name)
            if value is None:
                continue
            value = float(value)
            if not 0.0 <= value <= 10.0:
                raise ValueError(f"'{name}' debe estar entre 0 y 10.")
            setattr(self, name, value)

        if self.success and self.errors:
            raise ValueError(
                "TaskExecutionOutput exitoso no puede contener errores."
            )


class TaskExecutor(Protocol):
    """Firma esperada para un ejecutor de tareas."""

    def __call__(
        self,
        task: ProductionTask,
        context: ProductionContext,
        plan: ProductionPlan,
    ) -> TaskExecutionOutput:
        ...


# ---------------------------------------------------------------------------
# Utilidades internas
# ---------------------------------------------------------------------------


def _normalize_strings(values: Optional[Iterable[Any]]) -> list[str]:
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


def _safe_slug(value: str) -> str:
    raw = str(value or "").strip().lower()
    result: list[str] = []
    previous_dash = False

    for char in raw:
        if char.isalnum():
            result.append(char)
            previous_dash = False
        elif not previous_dash:
            result.append("-")
            previous_dash = True

    slug = "".join(result).strip("-")
    return slug or "project"


def _content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _parse_iso(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


# ---------------------------------------------------------------------------
# Master Producer
# ---------------------------------------------------------------------------


class MasterProducer:
    """
    Coordina la planeación y ejecución del pipeline profesional de CIPS.

    El objeto puede operar en dos modalidades:

    1. Planeación:
       crea contexto, prompt, asignaciones, tareas y ProductionPlan.

    2. Ejecución:
       recibe un TaskExecutor y ejecuta tareas respetando dependencias.
    """

    ROLE_ORDER: tuple[SpecialistRole, ...] = (
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

    ROLE_OUTPUTS: Mapping[SpecialistRole, tuple[str, ...]] = {
        SpecialistRole.RESEARCH_DIRECTOR: ("02_Investigacion.md",),
        SpecialistRole.FACT_CHECKER: ("02B_Verificacion_Datos.md",),
        SpecialistRole.STRATEGY_DIRECTOR: ("03_Estrategia.md",),
        SpecialistRole.CREATIVE_DIRECTOR: ("04_Concepto_Creativo.md",),
        SpecialistRole.SCREENWRITING_DIRECTOR: ("05_Guion.md",),
        SpecialistRole.STORYBOARD_DIRECTOR: ("06_Storyboard.md",),
        SpecialistRole.GENERATIVE_ART_DIRECTOR: (
            "07_Prompts_Imagen.md",
            "08_Prompts_Video.md",
        ),
        SpecialistRole.AUDIO_DIRECTOR: ("09_Audio.md",),
        SpecialistRole.SEO_DIRECTOR: ("10_SEO.md",),
        SpecialistRole.PLATFORM_DIRECTOR: ("11_Publicacion.md",),
        SpecialistRole.MARKETING_DIRECTOR: ("11B_Distribucion.md",),
        SpecialistRole.MONETIZATION_DIRECTOR: ("12_Monetizacion.md",),
        SpecialistRole.LEGAL_REVIEWER: ("12B_Revision_Legal.md",),
        SpecialistRole.QUALITY_DIRECTOR: ("13_QA.md",),
        SpecialistRole.PUBLISHING_MANAGER: ("14_Checklist.md",),
        SpecialistRole.ANALYTICS_DIRECTOR: ("15_Analitica.md",),
    }

    ROLE_TITLES: Mapping[SpecialistRole, str] = {
        SpecialistRole.RESEARCH_DIRECTOR: "Investigación y evidencia",
        SpecialistRole.FACT_CHECKER: "Verificación de datos",
        SpecialistRole.STRATEGY_DIRECTOR: "Estrategia de contenido",
        SpecialistRole.CREATIVE_DIRECTOR: "Concepto creativo",
        SpecialistRole.SCREENWRITING_DIRECTOR: "Guion",
        SpecialistRole.STORYBOARD_DIRECTOR: "Storyboard",
        SpecialistRole.GENERATIVE_ART_DIRECTOR: "Dirección de arte generativo",
        SpecialistRole.AUDIO_DIRECTOR: "Diseño de audio",
        SpecialistRole.SEO_DIRECTOR: "Optimización SEO",
        SpecialistRole.PLATFORM_DIRECTOR: "Adaptación y publicación",
        SpecialistRole.MARKETING_DIRECTOR: "Distribución y marketing",
        SpecialistRole.MONETIZATION_DIRECTOR: "Monetización",
        SpecialistRole.LEGAL_REVIEWER: "Revisión legal",
        SpecialistRole.QUALITY_DIRECTOR: "Control de calidad",
        SpecialistRole.PUBLISHING_MANAGER: "Checklist de publicación",
        SpecialistRole.ANALYTICS_DIRECTOR: "Plan de analítica",
    }

    ROLE_MISSIONS: Mapping[SpecialistRole, str] = {
        SpecialistRole.RESEARCH_DIRECTOR: (
            "Investigar el tema, identificar evidencia confiable, separar hechos "
            "de hipótesis y documentar fuentes."
        ),
        SpecialistRole.FACT_CHECKER: (
            "Verificar afirmaciones críticas, detectar datos dudosos y establecer "
            "el nivel de confianza factual."
        ),
        SpecialistRole.STRATEGY_DIRECTOR: (
            "Convertir el objetivo comercial en una estrategia de contenido "
            "medible, diferenciada y adecuada para la audiencia."
        ),
        SpecialistRole.CREATIVE_DIRECTOR: (
            "Definir el concepto creativo, gancho, promesa, tono y dirección narrativa."
        ),
        SpecialistRole.SCREENWRITING_DIRECTOR: (
            "Crear el guion completo con estructura, ritmo, claridad y llamada a la acción."
        ),
        SpecialistRole.STORYBOARD_DIRECTOR: (
            "Traducir el guion a escenas, planos, transiciones y necesidades visuales."
        ),
        SpecialistRole.GENERATIVE_ART_DIRECTOR: (
            "Diseñar prompts visuales consistentes para imagen y video."
        ),
        SpecialistRole.AUDIO_DIRECTOR: (
            "Definir voz, música, efectos, pausas y mezcla del contenido."
        ),
        SpecialistRole.SEO_DIRECTOR: (
            "Optimizar títulos, descripciones, palabras clave, etiquetas y descubribilidad."
        ),
        SpecialistRole.PLATFORM_DIRECTOR: (
            "Adaptar el contenido al formato, duración, normas y comportamiento "
            "de la plataforma objetivo."
        ),
        SpecialistRole.MARKETING_DIRECTOR: (
            "Diseñar la distribución, promoción y reutilización del contenido."
        ),
        SpecialistRole.MONETIZATION_DIRECTOR: (
            "Definir mecanismos de monetización y conversión alineados con el proyecto."
        ),
        SpecialistRole.LEGAL_REVIEWER: (
            "Detectar riesgos de propiedad intelectual, privacidad, publicidad "
            "y cumplimiento aplicable."
        ),
        SpecialistRole.QUALITY_DIRECTOR: (
            "Evaluar precisión, claridad, coherencia, valor, originalidad y "
            "preparación para publicación."
        ),
        SpecialistRole.PUBLISHING_MANAGER: (
            "Consolidar activos, metadatos, checklist y condiciones de publicación."
        ),
        SpecialistRole.ANALYTICS_DIRECTOR: (
            "Definir KPIs, hipótesis, eventos de medición y reglas de aprendizaje."
        ),
    }

    ROLE_ACCEPTANCE: Mapping[SpecialistRole, tuple[str, ...]] = {
        SpecialistRole.RESEARCH_DIRECTOR: (
            "Incluye preguntas de investigación.",
            "Distingue hechos, inferencias y vacíos.",
            "Documenta fuentes o requisitos de fuente.",
        ),
        SpecialistRole.FACT_CHECKER: (
            "Clasifica afirmaciones verificadas y no verificadas.",
            "Señala riesgos de publicación.",
            "Asigna nivel de confianza.",
        ),
        SpecialistRole.STRATEGY_DIRECTOR: (
            "Define objetivo, audiencia y propuesta de valor.",
            "Incluye KPIs.",
            "Alinea estrategia y monetización.",
        ),
        SpecialistRole.CREATIVE_DIRECTOR: (
            "Incluye gancho y promesa.",
            "Define tono y dirección creativa.",
            "Evita conceptos genéricos.",
        ),
        SpecialistRole.SCREENWRITING_DIRECTOR: (
            "El guion tiene apertura, desarrollo y cierre.",
            "La llamada a la acción es coherente.",
            "Respeta duración y plataforma.",
        ),
        SpecialistRole.STORYBOARD_DIRECTOR: (
            "Cada escena tiene objetivo visual.",
            "Existe continuidad entre escenas.",
            "Las transiciones son ejecutables.",
        ),
        SpecialistRole.GENERATIVE_ART_DIRECTOR: (
            "Los prompts son reproducibles.",
            "Mantienen continuidad estética.",
            "Incluyen restricciones visuales.",
        ),
        SpecialistRole.AUDIO_DIRECTOR: (
            "Define voz y ritmo.",
            "Especifica música y efectos.",
            "Respeta la intención narrativa.",
        ),
        SpecialistRole.SEO_DIRECTOR: (
            "Incluye títulos y descripciones.",
            "Incluye palabras clave relevantes.",
            "Evita sobreoptimización.",
        ),
        SpecialistRole.PLATFORM_DIRECTOR: (
            "Respeta formato y duración.",
            "Incluye metadatos de publicación.",
            "Define adaptación específica.",
        ),
        SpecialistRole.MARKETING_DIRECTOR: (
            "Incluye distribución y reutilización.",
            "Define canales y mensajes.",
            "Incluye hipótesis de conversión.",
        ),
        SpecialistRole.MONETIZATION_DIRECTOR: (
            "La monetización es compatible con la audiencia.",
            "Incluye acciones concretas.",
            "Define métricas económicas.",
        ),
        SpecialistRole.LEGAL_REVIEWER: (
            "Identifica riesgos legales.",
            "Propone mitigaciones.",
            "Señala bloqueos cuando corresponda.",
        ),
        SpecialistRole.QUALITY_DIRECTOR: (
            "Evalúa todos los criterios oficiales.",
            "Emite aprobación o rechazo.",
            "Documenta correcciones obligatorias.",
        ),
        SpecialistRole.PUBLISHING_MANAGER: (
            "Todos los activos están identificados.",
            "El checklist es accionable.",
            "La publicación tiene responsable y secuencia.",
        ),
        SpecialistRole.ANALYTICS_DIRECTOR: (
            "Define KPIs y eventos.",
            "Incluye línea base o hipótesis.",
            "Establece reglas de aprendizaje.",
        ),
    }

    def __init__(
        self,
        configuration: Optional[MasterProducerConfiguration] = None,
        *,
        prompt_builder: Optional[MasterProducerPromptBuilder] = None,
        executor: Optional[TaskExecutor] = None,
        logger: Optional[logging.Logger] = None,
        workspace_resolver: Optional[WorkspaceResolver] = None,
        text_store: Optional[TextStore] = None,
        metadata_store: Optional[MetadataStore] = None,
    ) -> None:
        self.configuration = configuration or MasterProducerConfiguration()
        self.prompt_builder = prompt_builder or MasterProducerPromptBuilder(
            configuration=self.configuration
        )
        self.executor = executor
        self.logger = logger or LOGGER

        resolved_workspace = workspace_resolver
        for store, expected_type, label in (
            (text_store, TextStore, "text_store"),
            (metadata_store, MetadataStore, "metadata_store"),
        ):
            if store is None:
                continue
            if not isinstance(store, expected_type):
                raise TypeError(f"{label} no implementa el store F3 esperado.")
            if resolved_workspace is None:
                resolved_workspace = store.workspace_resolver
            elif store.workspace_resolver is not resolved_workspace:
                raise ValueError(
                    f"{label} debe utilizar la misma instancia WorkspaceResolver."
                )

        if resolved_workspace is not None and not isinstance(
            resolved_workspace, WorkspaceResolver
        ):
            raise TypeError("workspace_resolver debe ser WorkspaceResolver o None.")

        self.workspace_resolver = resolved_workspace
        self.text_store = text_store or (
            TextStore(resolved_workspace) if resolved_workspace is not None else None
        )
        self.metadata_store = metadata_store or (
            MetadataStore(resolved_workspace)
            if resolved_workspace is not None
            else None
        )

        self._last_context: Optional[ProductionContext] = None
        self._last_prompt_package: Optional[PromptPackage] = None
        self._last_plan: Optional[ProductionPlan] = None
        self._last_result: Optional[ProductionResult] = None

    # ------------------------------------------------------------------
    # Validación y preparación
    # ------------------------------------------------------------------

    def validate_brief(self, brief: ProductionBrief) -> list[str]:
        """
        Valida la solicitud.

        Devuelve advertencias no bloqueantes.
        Lanza BriefValidationError para fallos bloqueantes.
        """
        if not isinstance(brief, ProductionBrief):
            raise BriefValidationError("'brief' debe ser ProductionBrief.")

        errors: list[str] = []
        warnings: list[str] = []

        errors.extend(brief.validate_for_production())

        if brief.deadline_iso:
            try:
                deadline = _parse_iso(brief.deadline_iso)
            except (TypeError, ValueError) as exc:
                errors.append(f"deadline_iso no es válido: {exc}")
            else:
                if deadline and deadline <= datetime.now(timezone.utc):
                    warnings.append("La fecha límite ya venció o es inmediata.")

        if (
            brief.quality_level
            in {QualityLevel.PREMIUM, QualityLevel.PUBLICATION_READY}
            and not brief.requires_fact_check
        ):
            warnings.append(
                "El nivel de calidad solicitado es alto y fact-check está desactivado."
            )

        if (
            brief.monetization_objective is not MonetizationObjective.NONE
            and not brief.desired_action
            and not brief.call_to_action
        ):
            warnings.append(
                "Existe objetivo de monetización sin acción deseada ni llamada a la acción."
            )

        if brief.requires_sources and not brief.reference_materials:
            warnings.append(
                "No se proporcionaron referencias; el Director de Investigación "
                "deberá localizar fuentes."
            )

        if errors and self.configuration.strict_validation:
            raise BriefValidationError(" ".join(errors))

        warnings.extend(errors)
        return _normalize_strings(warnings)

    def create_context(
        self,
        brief: ProductionBrief,
        *,
        output_root: Optional[str] = None,
        working_data: Optional[Mapping[str, Any]] = None,
        known_risks: Optional[Iterable[str]] = None,
        assumptions: Optional[Iterable[str]] = None,
        open_questions: Optional[Iterable[str]] = None,
    ) -> ProductionContext:
        self.validate_brief(brief)

        context = ProductionContext(
            brief=brief,
            current_status=ProjectStatus.PLANNING,
            known_risks=_normalize_strings(known_risks),
            assumptions=_normalize_strings(assumptions),
            open_questions=_normalize_strings(open_questions),
            output_root="",
            working_data=dict(working_data or {}),
        )

        if self.workspace_resolver is None:
            context.output_root = output_root or self._project_output_directory(brief)
        else:
            if output_root is None:
                identity = WorkspaceIdentity(
                    project_id=brief.project_id,
                    platform=brief.platform.value,
                    execution_id=context.context_id,
                )
                paths = self.workspace_resolver.resolve(identity, create=True)
                if paths.execution_root is None:
                    raise MasterProducerError(
                        "WorkspaceResolver no devolvió execution_root para el contexto."
                    )
                project_root = paths.project_root
                execution_root = paths.execution_root
            else:
                self.workspace_resolver.confine_path(
                    output_root,
                    "__cips_workspace_validation__",
                )
                execution_root = Path(output_root).expanduser().resolve(strict=False)
                project_root = self.workspace_resolver.resolve_project_workspace(
                    brief.project_id,
                    create=True,
                )

            context.output_root = str(execution_root)
            context.working_data["f3_workspace"] = {
                "managed": True,
                "project_id": brief.project_id,
                "platform": brief.platform.value,
                "execution_id": context.context_id,
                "project_root": str(project_root),
                "execution_root": str(execution_root),
            }

        context.working_data.setdefault(
            "master_producer_version",
            MASTER_PRODUCER_VERSION,
        )
        context.working_data.setdefault(
            "created_by",
            "CIPS Master Producer",
        )
        context.touch()
        self._last_context = context
        return context

    def build_prompt(
        self,
        brief: ProductionBrief,
        context: Optional[ProductionContext] = None,
        *,
        additional_instructions: Optional[Iterable[str]] = None,
        forced_roles: Optional[Iterable[SpecialistRole | str]] = None,
        excluded_roles: Optional[Iterable[SpecialistRole | str]] = None,
    ) -> PromptPackage:
        try:
            package = self.prompt_builder.build(
                brief,
                context,
                additional_instructions=additional_instructions,
                forced_roles=forced_roles,
                excluded_roles=excluded_roles,
            )
        except PromptBuildError as exc:
            raise MasterProducerError(
                f"No fue posible construir el prompt: {exc}"
            ) from exc

        self._last_prompt_package = package
        return package

    # ------------------------------------------------------------------
    # Selección de especialistas
    # ------------------------------------------------------------------

    def select_specialists(
        self,
        brief: ProductionBrief,
        context: Optional[ProductionContext] = None,
        *,
        forced_roles: Optional[Iterable[SpecialistRole | str]] = None,
        excluded_roles: Optional[Iterable[SpecialistRole | str]] = None,
    ) -> list[SpecialistRole]:
        package = self.build_prompt(
            brief,
            context,
            forced_roles=forced_roles,
            excluded_roles=excluded_roles,
        )

        roles = [
            role
            for role in package.selected_roles
            if role is not SpecialistRole.MASTER_PRODUCER
        ]

        # La revisión de calidad es obligatoria cuando está habilitada.
        if (
            self.configuration.enable_quality_review
            and SpecialistRole.QUALITY_DIRECTOR not in roles
        ):
            roles.append(SpecialistRole.QUALITY_DIRECTOR)

        # El orden oficial garantiza dependencias previsibles.
        order = {role: index for index, role in enumerate(self.ROLE_ORDER)}
        roles = sorted(
            set(roles),
            key=lambda role: order.get(role, len(order)),
        )

        return roles

    def create_assignments(
        self,
        brief: ProductionBrief,
        context: Optional[ProductionContext] = None,
        *,
        roles: Optional[Sequence[SpecialistRole]] = None,
        forced_roles: Optional[Iterable[SpecialistRole | str]] = None,
        excluded_roles: Optional[Iterable[SpecialistRole | str]] = None,
    ) -> list[SpecialistAssignment]:
        selected = list(
            roles
            if roles is not None
            else self.select_specialists(
                brief,
                context,
                forced_roles=forced_roles,
                excluded_roles=excluded_roles,
            )
        )

        assignments: list[SpecialistAssignment] = []

        for index, role in enumerate(selected, start=1):
            dependencies = self._role_dependencies(role, selected)
            outputs = list(self.ROLE_OUTPUTS.get(role, ()))
            assignment = SpecialistAssignment(
                role=role,
                mission=self.ROLE_MISSIONS.get(
                    role,
                    "Cumplir la misión definida por el Master Producer.",
                ),
                expected_output=", ".join(outputs) or "Entregable especializado",
                execution_order=index,
                depends_on_roles=dependencies,
                input_artifacts=self._input_artifacts_for_role(
                    role,
                    selected,
                ),
                output_artifacts=outputs,
                quality_threshold=self._quality_threshold(brief),
                max_revisions=self.configuration.max_revisions_per_task,
                instructions=self._assignment_instructions(brief, role),
                required=self._is_role_required(brief, role),
                metadata={
                    "project_id": brief.project_id,
                    "platform": brief.platform.value,
                    "content_type": brief.content_type.value,
                },
            )
            assignments.append(assignment)

        return assignments

    # ------------------------------------------------------------------
    # Construcción del plan
    # ------------------------------------------------------------------

    def build_tasks(
        self,
        brief: ProductionBrief,
        assignments: Sequence[SpecialistAssignment],
    ) -> list[ProductionTask]:
        task_by_role: dict[SpecialistRole, ProductionTask] = {}
        tasks: list[ProductionTask] = []

        for assignment in sorted(
            assignments,
            key=lambda item: item.execution_order,
        ):
            dependency_ids = [
                task_by_role[role].task_id
                for role in assignment.depends_on_roles
                if role in task_by_role
            ]

            task = ProductionTask(
                title=self.ROLE_TITLES.get(
                    assignment.role,
                    assignment.specialist_name,
                ),
                role=assignment.role,
                objective=assignment.mission,
                expected_output=assignment.expected_output,
                status=TaskStatus.PENDING,
                sequence=assignment.execution_order,
                required=assignment.required,
                dependency_task_ids=dependency_ids,
                input_artifacts=list(assignment.input_artifacts),
                output_artifacts=list(assignment.output_artifacts),
                instructions=list(assignment.instructions),
                acceptance_criteria=list(
                    self.ROLE_ACCEPTANCE.get(
                        assignment.role,
                        ("Cumple el objetivo asignado.",),
                    )
                ),
                estimated_minutes=self._estimate_minutes(
                    brief,
                    assignment.role,
                ),
                estimated_cost=self._estimate_cost(
                    brief,
                    assignment.role,
                ),
                max_attempts=max(1, assignment.max_revisions + 1),
                metadata={
                    "assignment_id": assignment.assignment_id,
                    "quality_threshold": assignment.quality_threshold,
                },
            )
            tasks.append(task)
            task_by_role[assignment.role] = task

        return tasks

    def build_production_plan(
        self,
        brief: ProductionBrief,
        context: Optional[ProductionContext] = None,
        *,
        forced_roles: Optional[Iterable[SpecialistRole | str]] = None,
        excluded_roles: Optional[Iterable[SpecialistRole | str]] = None,
        additional_success_criteria: Optional[Iterable[str]] = None,
    ) -> ProductionPlan:
        self.validate_brief(brief)

        if context is None:
            context = self.create_context(brief)

        assignments = self.create_assignments(
            brief,
            context,
            forced_roles=forced_roles,
            excluded_roles=excluded_roles,
        )
        tasks = self.build_tasks(brief, assignments)

        if len(tasks) > self.configuration.max_total_tasks:
            raise PlanValidationError(
                f"El plan contiene {len(tasks)} tareas y excede el máximo "
                f"configurado de {self.configuration.max_total_tasks}."
            )

        expected_artifacts = ["README.md", "01_Brief.md"]
        for assignment in assignments:
            expected_artifacts.extend(assignment.output_artifacts)
        expected_artifacts.extend(self.configuration.required_final_artifacts)
        expected_artifacts = _normalize_strings(expected_artifacts)

        success_criteria = [
            "Todas las tareas obligatorias finalizaron correctamente.",
            "No existen incidencias bloqueantes.",
            (
                "La calidad final es igual o superior a "
                f"{self.configuration.minimum_quality_score:.1f}/10."
            ),
            "El proyecto conserva trazabilidad entre brief, plan y entregables.",
            "La salida está lista para revisión humana.",
        ]
        success_criteria.extend(_normalize_strings(additional_success_criteria))

        plan = ProductionPlan(
            project_id=brief.project_id,
            strategy_summary=self._strategy_summary(brief, assignments),
            tasks=tasks,
            status=ProjectStatus.READY,
            assignments=list(assignments),
            expected_artifacts=expected_artifacts,
            success_criteria=_normalize_strings(success_criteria),
            metadata={
                "master_producer_version": MASTER_PRODUCER_VERSION,
                "platform": brief.platform.value,
                "content_type": brief.content_type.value,
                "quality_level": brief.quality_level.value,
                "monetization_objective": brief.monetization_objective.value,
            },
        )

        self.validate_pipeline(plan)
        context.current_status = ProjectStatus.READY
        context.working_data["plan_id"] = plan.plan_id
        context.touch()

        self._last_context = context
        self._last_plan = plan
        return plan

    def validate_pipeline(self, plan: ProductionPlan) -> list[str]:
        if not isinstance(plan, ProductionPlan):
            raise PlanValidationError("'plan' debe ser ProductionPlan.")

        warnings: list[str] = []

        try:
            plan.validate_dependencies()
        except ValueError as exc:
            raise PlanValidationError(str(exc)) from exc

        sequences = [task.sequence for task in plan.tasks]
        if len(sequences) != len(set(sequences)):
            warnings.append(
                "Existen tareas con la misma secuencia; se ordenarán por task_id."
            )

        roles = [task.role for task in plan.tasks]
        duplicates = [
            role.value
            for role, count in Counter(roles).items()
            if count > 1
        ]
        if duplicates:
            warnings.append(
                "Existen roles duplicados en el plan: "
                + ", ".join(sorted(duplicates))
            )

        if (
            self.configuration.enable_quality_review
            and SpecialistRole.QUALITY_DIRECTOR not in roles
        ):
            raise PlanValidationError(
                "El plan no contiene Director de Calidad."
            )

        role_position = {
            task.role: index
            for index, task in enumerate(plan.ordered_tasks())
        }

        canonical_pairs = (
            (
                SpecialistRole.RESEARCH_DIRECTOR,
                SpecialistRole.STRATEGY_DIRECTOR,
            ),
            (
                SpecialistRole.STRATEGY_DIRECTOR,
                SpecialistRole.CREATIVE_DIRECTOR,
            ),
            (
                SpecialistRole.CREATIVE_DIRECTOR,
                SpecialistRole.SCREENWRITING_DIRECTOR,
            ),
            (
                SpecialistRole.SCREENWRITING_DIRECTOR,
                SpecialistRole.STORYBOARD_DIRECTOR,
            ),
            (
                SpecialistRole.STORYBOARD_DIRECTOR,
                SpecialistRole.GENERATIVE_ART_DIRECTOR,
            ),
            (
                SpecialistRole.MONETIZATION_DIRECTOR,
                SpecialistRole.QUALITY_DIRECTOR,
            ),
        )

        for previous, following in canonical_pairs:
            if previous in role_position and following in role_position:
                if role_position[previous] >= role_position[following]:
                    raise PlanValidationError(
                        f"Orden inválido: {previous.value} debe preceder a "
                        f"{following.value}."
                    )

        return warnings

    # ------------------------------------------------------------------
    # Ejecución
    # ------------------------------------------------------------------

    def execute(
        self,
        brief: ProductionBrief,
        *,
        context: Optional[ProductionContext] = None,
        plan: Optional[ProductionPlan] = None,
        executor: Optional[TaskExecutor] = None,
        forced_roles: Optional[Iterable[SpecialistRole | str]] = None,
        excluded_roles: Optional[Iterable[SpecialistRole | str]] = None,
        persist: Optional[bool] = None,
    ) -> ProductionResult:
        started_at = utc_now_iso()
        started_clock = time.perf_counter()

        warnings: list[str] = []
        errors: list[str] = []
        issues: list[ProductionIssue] = []
        artifacts: list[ProductionArtifact] = []
        checkpoints: list[ProductionCheckpoint] = []
        execution_data: dict[str, Any] = {}
        input_tokens = 0
        output_tokens = 0
        actual_cost = 0.0
        revision_count = 0

        try:
            warnings.extend(self.validate_brief(brief))

            if context is None:
                context = self.create_context(brief)
            if plan is None:
                plan = self.build_production_plan(
                    brief,
                    context,
                    forced_roles=forced_roles,
                    excluded_roles=excluded_roles,
                )

            self.validate_pipeline(plan)
            context.current_status = ProjectStatus.IN_PRODUCTION
            plan.status = ProjectStatus.IN_PRODUCTION
            context.touch()

            brief_artifact = self._create_brief_artifact(brief, context)
            artifacts.append(brief_artifact)

            active_executor = executor or self.executor

            if active_executor is None:
                warnings.append(
                    "No se configuró TaskExecutor; se generó el plan sin ejecutar especialistas."
                )
                result = self._build_planning_result(
                    brief=brief,
                    context=context,
                    plan=plan,
                    artifacts=artifacts,
                    warnings=warnings,
                    started_at=started_at,
                    elapsed_seconds=time.perf_counter() - started_clock,
                )
                if self._should_persist(persist):
                    self._persist_bundle(brief, context, plan, result)
                self._last_result = result
                return result

            while True:
                ready = plan.ready_tasks()
                if not ready:
                    break

                for task in ready:
                    task.status = TaskStatus.READY

                for task in ready:
                    output = self._execute_task(
                        task,
                        context,
                        plan,
                        active_executor,
                    )

                    input_tokens += output.input_tokens
                    output_tokens += output.output_tokens
                    actual_cost += output.cost
                    warnings.extend(output.warnings)
                    errors.extend(output.errors)
                    artifacts.extend(output.artifacts)
                    execution_data[task.task_id] = output.data

                    if task.attempt_count > 1:
                        revision_count += task.attempt_count - 1

                    if output.quality_score is not None:
                        task.metadata["quality_score"] = output.quality_score
                    if output.fact_confidence_score is not None:
                        task.metadata[
                            "fact_confidence_score"
                        ] = output.fact_confidence_score

                    if not output.success:
                        issue = ProductionIssue(
                            message=(
                                output.errors[0]
                                if output.errors
                                else f"La tarea '{task.title}' falló."
                            ),
                            source=task.role.value,
                            risk_level=(
                                RiskLevel.HIGH
                                if task.required
                                else RiskLevel.MEDIUM
                            ),
                            blocking=task.required,
                            recommended_action=(
                                "Corregir la tarea y volver a ejecutar."
                            ),
                            related_task_id=task.task_id,
                            metadata={"attempt_count": task.attempt_count},
                        )
                        issues.append(issue)

                        if (
                            task.required
                            and self.configuration.stop_on_blocking_error
                        ):
                            self._block_remaining_tasks(plan, task)
                            break

                if (
                    self.configuration.stop_on_blocking_error
                    and any(issue.blocking for issue in issues)
                ):
                    break

            self._resolve_unreachable_tasks(plan)
            checkpoints.extend(
                self._create_checkpoints(brief, plan, artifacts, issues)
            )

            result = self.generate_result(
                brief=brief,
                context=context,
                plan=plan,
                artifacts=artifacts,
                checkpoints=checkpoints,
                issues=issues,
                warnings=warnings,
                errors=errors,
                data=execution_data,
                started_at=started_at,
                elapsed_seconds=time.perf_counter() - started_clock,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                actual_cost=actual_cost,
                revision_count=revision_count,
            )

            if self._should_persist(persist):
                self._persist_bundle(brief, context, plan, result)

            self._last_context = context
            self._last_plan = plan
            self._last_result = result
            return result

        except MasterProducerError:
            raise
        except Exception as exc:
            raise MasterProducerError(
                f"Fallo inesperado durante la producción: {exc}"
            ) from exc

    def _execute_task(
        self,
        task: ProductionTask,
        context: ProductionContext,
        plan: ProductionPlan,
        executor: TaskExecutor,
    ) -> TaskExecutionOutput:
        last_error = ""

        while task.attempt_count < task.max_attempts:
            task.attempt_count += 1
            task.status = TaskStatus.RUNNING
            task.started_at = task.started_at or utc_now_iso()

            try:
                output = executor(task, context, plan)
                if not isinstance(output, TaskExecutionOutput):
                    raise TypeError(
                        "El ejecutor debe devolver TaskExecutionOutput."
                    )
            except Exception as exc:
                last_error = str(exc)
                task.error_message = last_error

                if task.attempt_count >= task.max_attempts:
                    task.status = TaskStatus.FAILED
                    task.completed_at = utc_now_iso()
                    return TaskExecutionOutput(
                        success=False,
                        errors=[last_error],
                        metadata={
                            "exception_type": type(exc).__name__,
                            "attempt_count": task.attempt_count,
                        },
                    )

                continue

            if output.success:
                task.status = TaskStatus.COMPLETED
                task.completed_at = utc_now_iso()
                task.error_message = ""
                context.working_data[task.role.value] = output.data
                context.touch()
                return output

            last_error = (
                output.errors[0]
                if output.errors
                else f"La tarea '{task.title}' no fue aprobada."
            )
            task.error_message = last_error

            if task.attempt_count >= task.max_attempts:
                task.status = TaskStatus.FAILED
                task.completed_at = utc_now_iso()
                return output

        task.status = TaskStatus.FAILED
        task.completed_at = utc_now_iso()
        return TaskExecutionOutput(
            success=False,
            errors=[last_error or "La tarea agotó sus intentos."],
        )

    def collect_results(
        self,
        plan: ProductionPlan,
        outputs: Mapping[str, TaskExecutionOutput],
    ) -> dict[str, Any]:
        """
        Consolida resultados ya ejecutados externamente.

        Este método es útil cuando los agentes se ejecutan fuera de este proceso.
        """
        task_ids = {task.task_id for task in plan.tasks}
        unknown = set(outputs) - task_ids
        if unknown:
            raise PlanValidationError(
                "Se recibieron resultados para tareas inexistentes: "
                + ", ".join(sorted(unknown))
            )

        artifacts: list[ProductionArtifact] = []
        warnings: list[str] = []
        errors: list[str] = []
        data: dict[str, Any] = {}
        input_tokens = 0
        output_tokens = 0
        actual_cost = 0.0

        for task in plan.tasks:
            output = outputs.get(task.task_id)
            if output is None:
                continue
            if not isinstance(output, TaskExecutionOutput):
                raise TypeError(
                    f"El resultado de '{task.task_id}' no es TaskExecutionOutput."
                )

            task.attempt_count = max(task.attempt_count, 1)
            task.completed_at = utc_now_iso()
            task.status = (
                TaskStatus.COMPLETED if output.success else TaskStatus.FAILED
            )
            task.error_message = (
                ""
                if output.success
                else (output.errors[0] if output.errors else "Tarea fallida.")
            )

            artifacts.extend(output.artifacts)
            warnings.extend(output.warnings)
            errors.extend(output.errors)
            data[task.task_id] = output.data
            input_tokens += output.input_tokens
            output_tokens += output.output_tokens
            actual_cost += output.cost

        return {
            "artifacts": artifacts,
            "warnings": _normalize_strings(warnings),
            "errors": _normalize_strings(errors),
            "data": data,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "actual_cost": round(actual_cost, 6),
        }

    def generate_result(
        self,
        *,
        brief: ProductionBrief,
        context: ProductionContext,
        plan: ProductionPlan,
        artifacts: Sequence[ProductionArtifact],
        checkpoints: Sequence[ProductionCheckpoint],
        issues: Sequence[ProductionIssue],
        warnings: Optional[Iterable[str]] = None,
        errors: Optional[Iterable[str]] = None,
        data: Optional[Mapping[str, Any]] = None,
        started_at: Optional[str] = None,
        elapsed_seconds: float = 0.0,
        input_tokens: int = 0,
        output_tokens: int = 0,
        actual_cost: float = 0.0,
        revision_count: int = 0,
    ) -> ProductionResult:
        completed = sum(
            task.status is TaskStatus.COMPLETED for task in plan.tasks
        )
        failed = sum(task.status is TaskStatus.FAILED for task in plan.tasks)
        skipped = sum(
            task.status in {TaskStatus.SKIPPED, TaskStatus.CANCELLED}
            for task in plan.tasks
        )

        required_failed = [
            task
            for task in plan.tasks
            if task.required and task.status is not TaskStatus.COMPLETED
        ]
        blocking_issues = [issue for issue in issues if issue.blocking]
        checkpoint_failed = [
            checkpoint
            for checkpoint in checkpoints
            if checkpoint.status is CheckpointStatus.FAILED
        ]

        quality_scores = [
            float(task.metadata["quality_score"])
            for task in plan.tasks
            if task.metadata.get("quality_score") is not None
        ]
        fact_scores = [
            float(task.metadata["fact_confidence_score"])
            for task in plan.tasks
            if task.metadata.get("fact_confidence_score") is not None
        ]

        quality_score = (
            round(sum(quality_scores) / len(quality_scores), 2)
            if quality_scores
            else None
        )
        fact_score = (
            round(sum(fact_scores) / len(fact_scores), 2)
            if fact_scores
            else None
        )

        artifact_names = {artifact.name for artifact in artifacts}
        required_names = set(self.configuration.required_final_artifacts)
        artifact_coverage = (
            len(required_names & artifact_names) / len(required_names)
            if required_names
            else 1.0
        )
        readiness_score = round(artifact_coverage * 10.0, 2)

        monetization_score = self._derive_monetization_score(
            brief,
            plan,
            artifacts,
        )

        normalized_errors = _normalize_strings(errors)
        normalized_warnings = _normalize_strings(warnings)

        success = not (
            required_failed
            or blocking_issues
            or checkpoint_failed
            or normalized_errors
        )

        quality_ok = (
            quality_score is None
            or quality_score >= self.configuration.minimum_quality_score
        )
        readiness_ok = (
            readiness_score
            >= self.configuration.minimum_publication_readiness_score
        )
        fact_ok = (
            fact_score is None
            or fact_score
            >= self.configuration.minimum_fact_confidence_score
        )

        publication_ready = bool(
            success
            and quality_ok
            and readiness_ok
            and fact_ok
            and all(
                checkpoint.status
                in {CheckpointStatus.PASSED, CheckpointStatus.WAIVED}
                for checkpoint in checkpoints
            )
        )

        if publication_ready:
            status = ProjectStatus.COMPLETED
            summary = (
                "La producción finalizó correctamente y está lista para "
                "revisión humana previa a publicación."
            )
            recommendation = (
                "Realizar la aprobación humana final y proceder con la publicación."
            )
        elif success:
            status = ProjectStatus.IN_REVIEW
            summary = (
                "La ejecución terminó sin fallos bloqueantes, pero aún requiere "
                "revisión o entregables adicionales."
            )
            recommendation = (
                "Completar los criterios pendientes antes de publicar."
            )
        else:
            status = ProjectStatus.FAILED
            summary = (
                "La producción no pudo completar todos los requisitos obligatorios."
            )
            recommendation = (
                "Corregir incidencias bloqueantes y reanudar desde las fases afectadas."
            )

        plan.status = status
        context.current_status = status
        context.touch()

        metrics = ProductionMetrics(
            total_tasks=len(plan.tasks),
            completed_tasks=completed,
            failed_tasks=failed,
            skipped_tasks=skipped,
            revision_count=revision_count,
            elapsed_seconds=max(0.0, float(elapsed_seconds)),
            estimated_cost=plan.estimated_total_cost,
            actual_cost=max(0.0, float(actual_cost)),
            input_tokens=max(0, int(input_tokens)),
            output_tokens=max(0, int(output_tokens)),
            quality_score=quality_score,
            publication_readiness_score=readiness_score,
            monetization_score=monetization_score,
            fact_confidence_score=fact_score,
            generated_artifacts=len(artifacts),
            warnings_count=len(normalized_warnings),
            errors_count=len(normalized_errors),
            metadata={
                "artifact_coverage": round(artifact_coverage, 4),
                "required_failed_tasks": [
                    task.task_id for task in required_failed
                ],
            },
        )

        result = ProductionResult(
            project_id=brief.project_id,
            plan_id=plan.plan_id,
            status=status,
            success=success,
            summary=summary,
            recommendation=recommendation,
            publication_ready=publication_ready,
            artifacts=list(artifacts),
            checkpoints=list(checkpoints),
            issues=list(issues),
            warnings=normalized_warnings,
            errors=normalized_errors,
            metrics=metrics,
            data=dict(data or {}),
            output_paths={
                artifact.name: artifact.path for artifact in artifacts
            },
            metadata={
                "master_producer_version": MASTER_PRODUCER_VERSION,
                "quality_ok": quality_ok,
                "readiness_ok": readiness_ok,
                "fact_ok": fact_ok,
            },
            started_at=started_at,
        )
        self._last_result = result
        return result

    # ------------------------------------------------------------------
    # Exportación y diagnóstico
    # ------------------------------------------------------------------

    def export_plan(
        self,
        plan: ProductionPlan,
        destination: str | Path,
    ) -> Path:
        path = Path(destination)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(plan.to_json(indent=2), encoding="utf-8")
        return path

    def export_summary(
        self,
        brief: ProductionBrief,
        plan: ProductionPlan,
        destination: str | Path,
        *,
        result: Optional[ProductionResult] = None,
    ) -> Path:
        path = Path(destination)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            self._render_summary(brief, plan, result=result),
            encoding="utf-8",
        )
        return path

    def _render_summary(
        self,
        brief: ProductionBrief,
        plan: ProductionPlan,
        *,
        result: Optional[ProductionResult] = None,
    ) -> str:
        lines = [
            f"# {brief.project_name}",
            "",
            "## Resumen del proyecto",
            "",
            f"- ID: `{brief.project_id}`",
            f"- Tema: {brief.topic}",
            f"- Objetivo: {brief.objective}",
            f"- Audiencia: {brief.audience}",
            f"- Plataforma: `{brief.platform.value}`",
            f"- Tipo de contenido: `{brief.content_type.value}`",
            f"- Calidad: `{brief.quality_level.value}`",
            f"- Monetización: `{brief.monetization_objective.value}`",
            "",
            "## Estrategia del Master Producer",
            "",
            plan.strategy_summary,
            "",
            "## Pipeline",
            "",
        ]

        for task in plan.ordered_tasks():
            dependencies = ", ".join(task.dependency_task_ids) or "Ninguna"
            lines.extend(
                [
                    f"### {task.sequence}. {task.title}",
                    "",
                    f"- Rol: `{task.role.value}`",
                    f"- Estado: `{task.status.value}`",
                    f"- Dependencias: {dependencies}",
                    f"- Salida: {task.expected_output}",
                    "",
                ]
            )

        if result is not None:
            lines.extend(
                [
                    "## Resultado",
                    "",
                    f"- Estado: `{result.status.value}`",
                    f"- Éxito: `{result.success}`",
                    f"- Listo para publicación: `{result.publication_ready}`",
                    f"- Calidad: `{result.metrics.quality_score}`",
                    (
                        "- Preparación para publicación: "
                        f"`{result.metrics.publication_readiness_score}`"
                    ),
                    "",
                    result.summary,
                    "",
                ]
            )

        return "\n".join(lines).rstrip() + "\n"

    def get_statistics(
        self,
        plan: Optional[ProductionPlan] = None,
        result: Optional[ProductionResult] = None,
    ) -> dict[str, Any]:
        active_plan = plan or self._last_plan
        active_result = result or self._last_result

        stats: dict[str, Any] = {
            "component": "MasterProducer",
            "version": MASTER_PRODUCER_VERSION,
            "has_context": self._last_context is not None,
            "has_prompt": self._last_prompt_package is not None,
            "has_plan": active_plan is not None,
            "has_result": active_result is not None,
        }

        if active_plan is not None:
            status_counts = Counter(task.status.value for task in active_plan.tasks)
            stats["plan"] = {
                "plan_id": active_plan.plan_id,
                "status": active_plan.status.value,
                "tasks": len(active_plan.tasks),
                "status_counts": dict(status_counts),
                "estimated_minutes": active_plan.estimated_total_minutes,
                "estimated_cost": active_plan.estimated_total_cost,
                "expected_artifacts": len(active_plan.expected_artifacts),
            }

        if active_result is not None:
            stats["result"] = {
                "result_id": active_result.result_id,
                "status": active_result.status.value,
                "success": active_result.success,
                "publication_ready": active_result.publication_ready,
                "completion_rate": active_result.metrics.completion_rate,
                "quality_score": active_result.metrics.quality_score,
                "actual_cost": active_result.metrics.actual_cost,
                "artifacts": len(active_result.artifacts),
                "blocking_issues": len(active_result.blocking_issues),
            }

        return stats

    def health_check(self) -> dict[str, Any]:
        checks: dict[str, Any] = {
            "models": True,
            "prompt_builder": isinstance(
                self.prompt_builder,
                MasterProducerPromptBuilder,
            ),
            "configuration": isinstance(
                self.configuration,
                MasterProducerConfiguration,
            ),
            "output_root_writable": None,
            "executor_configured": self.executor is not None,
        }

        try:
            root = Path(self.configuration.output_root)
            candidate = root if root.exists() else root.parent
            while not candidate.exists() and candidate != candidate.parent:
                candidate = candidate.parent
            checks["output_root_writable"] = candidate.exists()
        except OSError:
            checks["output_root_writable"] = False

        healthy = all(
            value is True
            for key, value in checks.items()
            if key not in {"executor_configured"}
        )

        return {
            "component": "MasterProducer",
            "version": MASTER_PRODUCER_VERSION,
            "healthy": healthy,
            "checks": checks,
            "configuration": self.configuration.get_component_info(),
        }

    def get_component_info(self) -> dict[str, Any]:
        return {
            "component": "MasterProducer",
            "version": MASTER_PRODUCER_VERSION,
            "responsibility": "Planificación y orquestación de producción",
            "executor_configured": self.executor is not None,
            "supported_roles": [role.value for role in self.ROLE_ORDER],
            "configuration": self.configuration.get_component_info(),
        }

    # ------------------------------------------------------------------
    # Helpers de arquitectura
    # ------------------------------------------------------------------

    def _role_dependencies(
        self,
        role: SpecialistRole,
        selected: Sequence[SpecialistRole],
    ) -> list[SpecialistRole]:
        selected_set = set(selected)

        candidates: Mapping[SpecialistRole, tuple[SpecialistRole, ...]] = {
            SpecialistRole.FACT_CHECKER: (
                SpecialistRole.RESEARCH_DIRECTOR,
            ),
            SpecialistRole.STRATEGY_DIRECTOR: (
                SpecialistRole.FACT_CHECKER,
                SpecialistRole.RESEARCH_DIRECTOR,
            ),
            SpecialistRole.CREATIVE_DIRECTOR: (
                SpecialistRole.STRATEGY_DIRECTOR,
            ),
            SpecialistRole.SCREENWRITING_DIRECTOR: (
                SpecialistRole.CREATIVE_DIRECTOR,
            ),
            SpecialistRole.STORYBOARD_DIRECTOR: (
                SpecialistRole.SCREENWRITING_DIRECTOR,
            ),
            SpecialistRole.GENERATIVE_ART_DIRECTOR: (
                SpecialistRole.STORYBOARD_DIRECTOR,
                SpecialistRole.SCREENWRITING_DIRECTOR,
            ),
            SpecialistRole.AUDIO_DIRECTOR: (
                SpecialistRole.SCREENWRITING_DIRECTOR,
            ),
            SpecialistRole.SEO_DIRECTOR: (
                SpecialistRole.SCREENWRITING_DIRECTOR,
            ),
            SpecialistRole.PLATFORM_DIRECTOR: (
                SpecialistRole.SEO_DIRECTOR,
                SpecialistRole.SCREENWRITING_DIRECTOR,
            ),
            SpecialistRole.MARKETING_DIRECTOR: (
                SpecialistRole.PLATFORM_DIRECTOR,
                SpecialistRole.STRATEGY_DIRECTOR,
            ),
            SpecialistRole.MONETIZATION_DIRECTOR: (
                SpecialistRole.STRATEGY_DIRECTOR,
                SpecialistRole.PLATFORM_DIRECTOR,
            ),
            SpecialistRole.LEGAL_REVIEWER: (
                SpecialistRole.SCREENWRITING_DIRECTOR,
            ),
            SpecialistRole.QUALITY_DIRECTOR: (
                SpecialistRole.MONETIZATION_DIRECTOR,
                SpecialistRole.PLATFORM_DIRECTOR,
                SpecialistRole.LEGAL_REVIEWER,
                SpecialistRole.GENERATIVE_ART_DIRECTOR,
                SpecialistRole.AUDIO_DIRECTOR,
            ),
            SpecialistRole.PUBLISHING_MANAGER: (
                SpecialistRole.QUALITY_DIRECTOR,
            ),
            SpecialistRole.ANALYTICS_DIRECTOR: (
                SpecialistRole.STRATEGY_DIRECTOR,
                SpecialistRole.PUBLISHING_MANAGER,
            ),
        }

        possible = candidates.get(role, ())
        available = [item for item in possible if item in selected_set]

        # Algunas dependencias son alternativas. Se conserva la más cercana
        # al rol cuando la dependencia preferida no fue seleccionada.
        if role is SpecialistRole.STRATEGY_DIRECTOR:
            if SpecialistRole.FACT_CHECKER in available:
                return [SpecialistRole.FACT_CHECKER]
            if SpecialistRole.RESEARCH_DIRECTOR in available:
                return [SpecialistRole.RESEARCH_DIRECTOR]

        if role is SpecialistRole.GENERATIVE_ART_DIRECTOR:
            if SpecialistRole.STORYBOARD_DIRECTOR in available:
                return [SpecialistRole.STORYBOARD_DIRECTOR]
            if SpecialistRole.SCREENWRITING_DIRECTOR in available:
                return [SpecialistRole.SCREENWRITING_DIRECTOR]

        return available

    def _input_artifacts_for_role(
        self,
        role: SpecialistRole,
        selected: Sequence[SpecialistRole],
    ) -> list[str]:
        inputs = ["01_Brief.md"]
        for dependency in self._role_dependencies(role, selected):
            inputs.extend(self.ROLE_OUTPUTS.get(dependency, ()))
        return _normalize_strings(inputs)

    def _assignment_instructions(
        self,
        brief: ProductionBrief,
        role: SpecialistRole,
    ) -> list[str]:
        instructions = [
            f"Trabajar en idioma {brief.language}.",
            f"Respetar el nivel de calidad {brief.quality_level.value}.",
            f"Optimizar para {brief.platform.value}.",
            "No inventar datos ni fuentes.",
            "Documentar supuestos y riesgos.",
            "Entregar contenido accionable y listo para la siguiente fase.",
        ]

        if brief.tone:
            instructions.append(f"Aplicar el tono: {brief.tone}.")
        if brief.brand_voice:
            instructions.append(
                f"Respetar la voz de marca: {brief.brand_voice}."
            )
        if brief.restrictions:
            instructions.append(
                "Cumplir las restricciones del brief sin excepciones."
            )
        if role is SpecialistRole.MONETIZATION_DIRECTOR:
            instructions.append(
                f"Priorizar el objetivo: {brief.monetization_objective.value}."
            )

        return instructions

    def _is_role_required(
        self,
        brief: ProductionBrief,
        role: SpecialistRole,
    ) -> bool:
        if role is SpecialistRole.RESEARCH_DIRECTOR:
            return brief.requires_research and self.configuration.enable_research
        if role is SpecialistRole.FACT_CHECKER:
            return brief.requires_fact_check and self.configuration.enable_fact_check
        if role is SpecialistRole.LEGAL_REVIEWER:
            return (
                brief.requires_legal_review
                and self.configuration.enable_legal_review_when_required
            )
        if role is SpecialistRole.MONETIZATION_DIRECTOR:
            return (
                brief.monetization_objective is not MonetizationObjective.NONE
                and self.configuration.enable_monetization_review
            )
        if role is SpecialistRole.QUALITY_DIRECTOR:
            return self.configuration.enable_quality_review
        return True

    def _quality_threshold(self, brief: ProductionBrief) -> float:
        levels = {
            QualityLevel.DRAFT: 6.0,
            QualityLevel.STANDARD: 7.0,
            QualityLevel.PROFESSIONAL: 8.0,
            QualityLevel.PREMIUM: 9.0,
            QualityLevel.PUBLICATION_READY: 9.0,
        }
        return max(
            levels[brief.quality_level],
            self.configuration.minimum_quality_score,
        )

    def _estimate_minutes(
        self,
        brief: ProductionBrief,
        role: SpecialistRole,
    ) -> float:
        base = {
            SpecialistRole.RESEARCH_DIRECTOR: 30.0,
            SpecialistRole.FACT_CHECKER: 20.0,
            SpecialistRole.STRATEGY_DIRECTOR: 20.0,
            SpecialistRole.CREATIVE_DIRECTOR: 20.0,
            SpecialistRole.SCREENWRITING_DIRECTOR: 35.0,
            SpecialistRole.STORYBOARD_DIRECTOR: 30.0,
            SpecialistRole.GENERATIVE_ART_DIRECTOR: 35.0,
            SpecialistRole.AUDIO_DIRECTOR: 20.0,
            SpecialistRole.SEO_DIRECTOR: 15.0,
            SpecialistRole.PLATFORM_DIRECTOR: 15.0,
            SpecialistRole.MARKETING_DIRECTOR: 20.0,
            SpecialistRole.MONETIZATION_DIRECTOR: 20.0,
            SpecialistRole.LEGAL_REVIEWER: 20.0,
            SpecialistRole.QUALITY_DIRECTOR: 25.0,
            SpecialistRole.PUBLISHING_MANAGER: 15.0,
            SpecialistRole.ANALYTICS_DIRECTOR: 15.0,
        }.get(role, 20.0)

        quality_multiplier = {
            QualityLevel.DRAFT: 0.6,
            QualityLevel.STANDARD: 0.8,
            QualityLevel.PROFESSIONAL: 1.0,
            QualityLevel.PREMIUM: 1.25,
            QualityLevel.PUBLICATION_READY: 1.4,
        }[brief.quality_level]

        duration_multiplier = 1.0
        if brief.duration_seconds:
            duration_multiplier += min(1.5, brief.duration_seconds / 1800.0)

        return round(base * quality_multiplier * duration_multiplier, 2)

    def _estimate_cost(
        self,
        brief: ProductionBrief,
        role: SpecialistRole,
    ) -> float:
        # Estimación neutral; el proveedor real podrá reemplazarla.
        minute_estimate = self._estimate_minutes(brief, role)
        return round(minute_estimate * 0.0025, 4)

    def _strategy_summary(
        self,
        brief: ProductionBrief,
        assignments: Sequence[SpecialistAssignment],
    ) -> str:
        roles = ", ".join(item.role.value for item in assignments)
        return (
            f"Producir '{brief.project_name}' para {brief.audience}, "
            f"optimizado para {brief.platform.value}, con formato "
            f"{brief.content_type.value}, calidad {brief.quality_level.value} "
            f"y objetivo de monetización "
            f"{brief.monetization_objective.value}. "
            f"Especialistas seleccionados: {roles}."
        )

    def _create_brief_artifact(
        self,
        brief: ProductionBrief,
        context: ProductionContext,
    ) -> ProductionArtifact:
        content = brief.to_json(indent=2)
        path = str(Path(context.output_root) / "01_Brief.json")
        return ProductionArtifact(
            name="01_Brief.md",
            artifact_type="brief",
            path=path,
            producer_role=SpecialistRole.MASTER_PRODUCER,
            version=1,
            status="generated",
            content_hash=_content_hash(content),
            mime_type="application/json",
            size_bytes=len(content.encode("utf-8")),
            approved=True,
            metadata={"serialized_content": content},
        )

    def _create_checkpoints(
        self,
        brief: ProductionBrief,
        plan: ProductionPlan,
        artifacts: Sequence[ProductionArtifact],
        issues: Sequence[ProductionIssue],
    ) -> list[ProductionCheckpoint]:
        artifact_names = {artifact.name for artifact in artifacts}
        required_names = set(self.configuration.required_final_artifacts)
        missing = sorted(required_names - artifact_names)

        pipeline_passed = all(
            task.status is TaskStatus.COMPLETED
            for task in plan.tasks
            if task.required
        )
        pipeline_checkpoint = ProductionCheckpoint(
            name="Pipeline obligatorio",
            criteria=[
                "Todas las tareas obligatorias fueron completadas.",
                "No existen tareas bloqueadas.",
            ],
            status=(
                CheckpointStatus.PASSED
                if pipeline_passed
                else CheckpointStatus.FAILED
            ),
            stage="production",
            reviewer_role=SpecialistRole.MASTER_PRODUCER,
            score=10.0 if pipeline_passed else 0.0,
            findings=(
                []
                if pipeline_passed
                else ["Existen tareas obligatorias incompletas."]
            ),
            required_actions=(
                []
                if pipeline_passed
                else ["Completar o corregir las tareas obligatorias."]
            ),
            reviewed_at=utc_now_iso(),
        )

        artifacts_passed = not missing
        artifacts_checkpoint = ProductionCheckpoint(
            name="Cobertura de entregables",
            criteria=[
                "Todos los entregables finales requeridos están presentes."
            ],
            status=(
                CheckpointStatus.PASSED
                if artifacts_passed
                else CheckpointStatus.NEEDS_REVIEW
            ),
            stage="packaging",
            reviewer_role=SpecialistRole.PUBLISHING_MANAGER,
            score=(
                10.0
                if artifacts_passed
                else round(
                    10.0
                    * (
                        len(required_names & artifact_names)
                        / max(1, len(required_names))
                    ),
                    2,
                )
            ),
            findings=(
                []
                if artifacts_passed
                else [f"Faltan entregables: {', '.join(missing)}"]
            ),
            required_actions=(
                []
                if artifacts_passed
                else ["Generar los entregables faltantes."]
            ),
            reviewed_at=utc_now_iso(),
        )

        no_blockers = not any(issue.blocking for issue in issues)
        risk_checkpoint = ProductionCheckpoint(
            name="Riesgos bloqueantes",
            criteria=["No existen incidencias bloqueantes sin resolver."],
            status=(
                CheckpointStatus.PASSED
                if no_blockers
                else CheckpointStatus.FAILED
            ),
            stage="quality",
            reviewer_role=SpecialistRole.QUALITY_DIRECTOR,
            score=10.0 if no_blockers else 0.0,
            findings=(
                []
                if no_blockers
                else ["Existen incidencias bloqueantes."]
            ),
            required_actions=(
                []
                if no_blockers
                else ["Resolver incidencias antes de publicar."]
            ),
            reviewed_at=utc_now_iso(),
        )

        return [
            pipeline_checkpoint,
            artifacts_checkpoint,
            risk_checkpoint,
        ]

    def _block_remaining_tasks(
        self,
        plan: ProductionPlan,
        failed_task: ProductionTask,
    ) -> None:
        dependents: dict[str, set[str]] = defaultdict(set)
        for task in plan.tasks:
            for dependency_id in task.dependency_task_ids:
                dependents[dependency_id].add(task.task_id)

        blocked_ids: set[str] = set()
        queue = list(dependents.get(failed_task.task_id, set()))

        while queue:
            task_id = queue.pop(0)
            if task_id in blocked_ids:
                continue
            blocked_ids.add(task_id)
            queue.extend(dependents.get(task_id, set()))

        for task in plan.tasks:
            if task.task_id in blocked_ids and not task.is_terminal:
                task.status = TaskStatus.BLOCKED
                task.error_message = (
                    f"Bloqueada por fallo en '{failed_task.task_id}'."
                )

    def _resolve_unreachable_tasks(self, plan: ProductionPlan) -> None:
        terminal_ids = {
            task.task_id
            for task in plan.tasks
            if task.status in {
                TaskStatus.COMPLETED,
                TaskStatus.FAILED,
                TaskStatus.SKIPPED,
                TaskStatus.CANCELLED,
            }
        }

        for task in plan.tasks:
            if task.status in {TaskStatus.PENDING, TaskStatus.READY}:
                unmet = set(task.dependency_task_ids) - terminal_ids
                failed_dependency = any(
                    dependency.status
                    in {
                        TaskStatus.FAILED,
                        TaskStatus.BLOCKED,
                        TaskStatus.CANCELLED,
                    }
                    for dependency in plan.tasks
                    if dependency.task_id in task.dependency_task_ids
                )
                if unmet or failed_dependency:
                    task.status = TaskStatus.BLOCKED
                    task.error_message = "Dependencias incompletas o fallidas."

    def _derive_monetization_score(
        self,
        brief: ProductionBrief,
        plan: ProductionPlan,
        artifacts: Sequence[ProductionArtifact],
    ) -> Optional[float]:
        if brief.monetization_objective is MonetizationObjective.NONE:
            return None

        has_role = any(
            task.role is SpecialistRole.MONETIZATION_DIRECTOR
            and task.status is TaskStatus.COMPLETED
            for task in plan.tasks
        )
        has_artifact = any(
            artifact.name == "12_Monetizacion.md"
            for artifact in artifacts
        )

        if has_role and has_artifact:
            return 10.0
        if has_role or has_artifact:
            return 6.0
        return 0.0

    def _build_planning_result(
        self,
        *,
        brief: ProductionBrief,
        context: ProductionContext,
        plan: ProductionPlan,
        artifacts: Sequence[ProductionArtifact],
        warnings: Sequence[str],
        started_at: str,
        elapsed_seconds: float,
    ) -> ProductionResult:
        metrics = ProductionMetrics(
            total_tasks=len(plan.tasks),
            completed_tasks=0,
            failed_tasks=0,
            skipped_tasks=0,
            elapsed_seconds=elapsed_seconds,
            estimated_cost=plan.estimated_total_cost,
            generated_artifacts=len(artifacts),
            warnings_count=len(warnings),
            metadata={"planning_only": True},
        )

        plan.status = ProjectStatus.READY
        context.current_status = ProjectStatus.READY
        context.touch()

        return ProductionResult(
            project_id=brief.project_id,
            plan_id=plan.plan_id,
            status=ProjectStatus.READY,
            success=True,
            summary=(
                "El plan de producción fue generado correctamente. "
                "La ejecución de especialistas está pendiente."
            ),
            recommendation=(
                "Configurar un TaskExecutor y ejecutar el plan."
            ),
            publication_ready=False,
            artifacts=list(artifacts),
            warnings=list(warnings),
            metrics=metrics,
            data={
                "planning_only": True,
                "task_count": len(plan.tasks),
            },
            output_paths={
                artifact.name: artifact.path for artifact in artifacts
            },
            metadata={
                "master_producer_version": MASTER_PRODUCER_VERSION,
            },
            started_at=started_at,
        )

    def _project_output_directory(self, brief: ProductionBrief) -> str:
        root = Path(self.configuration.output_root)
        if not self.configuration.create_project_directory:
            return str(root)
        folder = f"{_safe_slug(brief.project_name)}-{brief.project_id[-8:]}"
        return str(root / folder)

    def _should_persist(self, persist: Optional[bool]) -> bool:
        if persist is None:
            return self.configuration.persist_outputs
        return bool(persist)

    def _persist_bundle(
        self,
        brief: ProductionBrief,
        context: ProductionContext,
        plan: ProductionPlan,
        result: ProductionResult,
    ) -> None:
        if self._is_f3_workspace_context(context):
            self._persist_bundle_f3(brief, context, plan, result)
            return

        root = Path(context.output_root)
        root.mkdir(parents=True, exist_ok=True)

        files = {
            "brief.json": brief.to_json(indent=2),
            "context.json": context.to_json(indent=2),
            "plan.json": plan.to_json(indent=2),
            "result.json": result.to_json(indent=2),
        }

        if self._last_prompt_package is not None:
            files["prompt_package.json"] = self._last_prompt_package.to_json(
                indent=2
            )

        for filename, content in files.items():
            path = root / filename
            if path.exists() and not self.configuration.overwrite_existing:
                timestamp = datetime.now(timezone.utc).strftime(
                    "%Y%m%dT%H%M%SZ"
                )
                path = root / f"{path.stem}_{timestamp}{path.suffix}"
            path.write_text(content, encoding="utf-8")

        self.export_summary(
            brief,
            plan,
            root / "README.md",
            result=result,
        )

    def _is_f3_workspace_context(self, context: ProductionContext) -> bool:
        workspace = context.working_data.get("f3_workspace", {})
        return (
            self.workspace_resolver is not None
            and self.text_store is not None
            and self.metadata_store is not None
            and isinstance(workspace, Mapping)
            and workspace.get("managed") is True
        )

    def _persist_bundle_f3(
        self,
        brief: ProductionBrief,
        context: ProductionContext,
        plan: ProductionPlan,
        result: ProductionResult,
    ) -> None:
        if self.text_store is None or self.metadata_store is None:
            raise MasterProducerError("Stores F3 no disponibles para persistencia runtime.")

        root = Path(context.output_root)
        common_metadata = {
            "source": "CIPS Master Producer",
            "project_id": brief.project_id,
            "platform": brief.platform.value,
            "execution_id": context.context_id,
            "stage": "runtime_bundle",
        }
        files = {
            "brief.json": brief.to_json(indent=2),
            "context.json": context.to_json(indent=2),
            "plan.json": plan.to_json(indent=2),
            "result.json": result.to_json(indent=2),
        }
        if self._last_prompt_package is not None:
            files["prompt_package.json"] = self._last_prompt_package.to_json(
                indent=2
            )

        for filename, content in files.items():
            self._persist_f3_document(
                store=self.metadata_store,
                workspace_root=root,
                relative_path=filename,
                content=content,
                artifact_type="runtime_metadata",
                mime_type="application/json",
                metadata={**common_metadata, "logical_name": filename},
            )

        self._persist_f3_document(
            store=self.text_store,
            workspace_root=root,
            relative_path="README.md",
            content=self._render_summary(brief, plan, result=result),
            artifact_type="runtime_summary",
            mime_type="text/markdown",
            metadata={**common_metadata, "logical_name": "README.md"},
        )

    def _persist_f3_document(
        self,
        *,
        store: MetadataStore | TextStore,
        workspace_root: Path,
        relative_path: str,
        content: str,
        artifact_type: str,
        mime_type: str,
        metadata: Mapping[str, Any],
    ) -> None:
        payload = content.encode("utf-8")
        policy = (
            CollisionPolicy.REPLACE
            if self.configuration.overwrite_existing
            else CollisionPolicy.REUSE_IDENTICAL
        )
        try:
            store.persist_bytes(
                workspace_root=workspace_root,
                relative_path=relative_path,
                content=payload,
                artifact_type=artifact_type,
                mime_type=mime_type,
                metadata=metadata,
                producer_role=SpecialistRole.MASTER_PRODUCER,
                collision_policy=policy,
            )
        except ArtifactCollisionError:
            if self.configuration.overwrite_existing:
                raise
            versioned_path = self._versioned_artifact_path(relative_path, payload)
            store.persist_bytes(
                workspace_root=workspace_root,
                relative_path=versioned_path,
                content=payload,
                artifact_type=artifact_type,
                mime_type=mime_type,
                metadata={**dict(metadata), "versioned_from": relative_path},
                producer_role=SpecialistRole.MASTER_PRODUCER,
                collision_policy=CollisionPolicy.REUSE_IDENTICAL,
            )

    @staticmethod
    def _versioned_artifact_path(relative_path: str, payload: bytes) -> str:
        path = Path(relative_path)
        content_hash = hashlib.sha256(payload).hexdigest()
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        return str(
            path.with_name(
                f"{path.stem}.{content_hash[:12]}.{timestamp}{path.suffix}"
            )
        )


def create_master_producer(
    configuration: Optional[MasterProducerConfiguration] = None,
    *,
    executor: Optional[TaskExecutor] = None,
    workspace_resolver: Optional[WorkspaceResolver] = None,
    text_store: Optional[TextStore] = None,
    metadata_store: Optional[MetadataStore] = None,
) -> MasterProducer:
    """Factory oficial del componente."""
    return MasterProducer(
        configuration=configuration,
        executor=executor,
        workspace_resolver=workspace_resolver,
        text_store=text_store,
        metadata_store=metadata_store,
    )
