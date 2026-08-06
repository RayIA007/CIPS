"""
=========================================================
Proyecto : CIPS
Release  : 0.5
Build    : 021
Archivo  : knowledge_resolver.py
Estado   : RELEASE
=========================================================

Selecciona los Knowledge Modules relevantes para el
Stage actual del proyecto.

Compatibilidad:
- PipelineEngine mediante execute(Project, modules).
- PipelineRunner mediante execute(RuntimeContext).
"""

from runtime_component import RuntimeComponent
from runtime_context import RuntimeContext
from runtime_models import (
    EngineResult,
    KnowledgeModule,
    Project,
)
from utils import ROOT, read_yaml
from dataclasses import dataclass, field
from typing import Any
from collections import Counter
import math
import re
import unicodedata

KNOWLEDGE_RULES_PATH = (
    ROOT
    / "01_CONFIG"
    / "knowledge_rules.yaml"
)


###############################################################################
# Resolver Build 021
###############################################################################

KNOWLEDGE_RESOLVER_VERSION = "2.1.0"

WORD_PATTERN = re.compile(
    r"[a-zA-ZáéíóúÁÉÍÓÚüÜñÑ0-9]+"
)

DEFAULT_STOPWORDS = frozenset({
    "de","la","el","los","las","un","una",
    "para","con","por","en","y","o",
    "que","como","del","al"
})


@dataclass(slots=True)
class ResolverWeights:

    name: float = 0.25
    category: float = 0.10
    tags: float = 0.15
    keywords: float = 0.15
    content: float = 0.20
    priority: float = 0.15

    @property
    def total(self):

        return (
            self.name
            + self.category
            + self.tags
            + self.keywords
            + self.content
            + self.priority
        )


@dataclass(slots=True)
class ModuleScore:

    module: KnowledgeModule

    score: float

    matched_terms: list[str] = field(
        default_factory=list
    )

    reasons: list[str] = field(
        default_factory=list
    )

    metadata: dict[str,Any] = field(
        default_factory=dict
    )
    
    
    
@dataclass(slots=True)
class ResolverRuleSet:
    """
    Reglas normalizadas para una etapa concreta del pipeline.

    Mantiene compatibilidad con el esquema histórico que únicamente
    declaraba módulos obligatorios mediante ``required``.
    """

    required: list[str] = field(default_factory=list)
    optional: list[str] = field(default_factory=list)
    priority: dict[str, float] = field(default_factory=dict)

    maximum_modules: int | None = None
    minimum_score: float = 0.0


class KnowledgeResolver(RuntimeComponent):
    """
    Filtra los Knowledge Modules según el Stage actual.

    Admite dos formas de ejecución:

    1. execute(Project, knowledge_modules)
       Mantiene compatibilidad con PipelineEngine.

    2. execute(RuntimeContext)
       Implementa el contrato del Runtime Framework.
    """
    weights = ResolverWeights()

    minimum_score = 0

    
    maximum_modules = None
    
    component_name = "knowledge_resolver"


    ####################################################################
    # API Pública
    ####################################################################


    def execute(
        self,
        runtime_input: Project | RuntimeContext,
        knowledge_modules: list[KnowledgeModule] | None = None,
    ) -> EngineResult:
        """
        Selecciona los módulos requeridos para el Stage actual.
        """

        try:
            runtime_context = self._get_runtime_context(
                runtime_input
            )

            project = self._get_project(
                runtime_input
            )

            available_modules = self._get_available_modules(
                runtime_input=runtime_input,
                knowledge_modules=knowledge_modules,
            )

            if not available_modules:
                return EngineResult.fail(
                    message=(
                        "No se recibieron Knowledge Modules "
                        "para resolver."
                    ),
                    errors=[
                        "knowledge_modules vacío"
                    ],
                    metadata={
                        "component": self.component_name,
                        "project_id": project.project_id,
                        "stage": project.stage_actual,
                    },
                )

            rule_set = self._get_stage_rules(project)
            required_ids = list(rule_set.required)

            if not required_ids:
                return EngineResult.fail(
                    message=(
                        "No existen reglas de conocimiento "
                        "para el Stage actual."
                    ),
                    errors=[
                        f"Stage actual: {project.stage_actual}",
                        f"Archivo: {KNOWLEDGE_RULES_PATH}",
                    ],
                    metadata={
                        "component": self.component_name,
                        "project_id": project.project_id,
                        "stage": project.stage_actual,
                    },
                )

            selected_modules = self._select_modules_by_rules(
                available_modules=available_modules,
                rule_set=rule_set,
            )

            missing_ids = [
                module_id
                for module_id in required_ids
                if module_id not in {
                    module.module_id
                    for module in selected_modules
                }
            ]

            if not selected_modules:
                return EngineResult.fail(
                    message=(
                        "KnowledgeResolver no encontró "
                        "módulos relevantes."
                    ),
                    errors=[
                        f"Stage actual: {project.stage_actual}",
                        f"IDs requeridos: {required_ids}",
                    ],
                    metadata={
                        "component": self.component_name,
                        "project_id": project.project_id,
                        "stage": project.stage_actual,
                    },
                )

            warnings = []

            if missing_ids:
                warnings.append(
                    "No se encontraron algunos módulos "
                    f"requeridos: {missing_ids}"
                )

            metadata = {
                "component": self.component_name,
                "project_id": project.project_id,
                "stage": project.stage_actual,
                "received_modules": len(
                    available_modules
                ),
                "selected_modules": len(
                    selected_modules
                ),
                "required_ids": required_ids,
                "selected_ids": [
                    module.module_id
                    for module in selected_modules
                ],
                "missing_ids": missing_ids,
                "rules_path": str(
                    KNOWLEDGE_RULES_PATH
                ),
            }

            if runtime_context is not None:
                runtime_context.resolved_modules = (
                    selected_modules
                )

                return EngineResult.ok(
                    data=runtime_context,
                    message=(
                        "Knowledge Modules seleccionados "
                        "en RuntimeContext."
                    ),
                    warnings=warnings,
                    metadata=metadata,
                )

            return EngineResult.ok(
                data=selected_modules,
                message=(
                    "Knowledge Modules seleccionados "
                    "correctamente."
                ),
                warnings=warnings,
                metadata=metadata,
            )

        except Exception as error:
            return EngineResult.fail(
                message=(
                    "Error inesperado en "
                    "KnowledgeResolver."
                ),
                errors=[str(error)],
                metadata={
                    "component": self.component_name,
                },
            )


    ####################################################################
    # Runtime
    ####################################################################


    def _get_runtime_context(
        self,
        runtime_input: Project | RuntimeContext,
    ) -> RuntimeContext | None:
        """
        Devuelve RuntimeContext cuando se utiliza
        el nuevo Runtime Framework.
        """

        if isinstance(
            runtime_input,
            RuntimeContext,
        ):
            return runtime_input

        return None

    def _get_project(
        self,
        runtime_input: Project | RuntimeContext,
    ) -> Project:
        """
        Obtiene Project desde cualquiera
        de las interfaces compatibles.
        """

        if isinstance(
            runtime_input,
            RuntimeContext,
        ):
            return runtime_input.project

        if isinstance(
            runtime_input,
            Project,
        ):
            return runtime_input

        raise TypeError(
            "KnowledgeResolver requiere "
            "Project o RuntimeContext."
        )

    def _get_available_modules(
        self,
        runtime_input: Project | RuntimeContext,
        knowledge_modules: list[KnowledgeModule] | None,
    ) -> list[KnowledgeModule]:
        """
        Obtiene los módulos desde el argumento legado
        o desde RuntimeContext.
        """

        if isinstance(
            runtime_input,
            RuntimeContext,
        ):
            return runtime_input.knowledge_modules

        return knowledge_modules or []

    def _get_required_module_ids(
        self,
        project_or_stage: Project | str,
    ) -> list[str]:
        """Conserva la interfaz histórica del Build 020."""

        rule_set = self._get_stage_rules(project_or_stage)
        return list(rule_set.required)

    def _get_stage_rules(
        self,
        project_or_stage: Project | str,
    ) -> ResolverRuleSet:
        """Obtiene y normaliza las reglas de la etapa actual."""

        rules_data = self._load_knowledge_rules()
        stage_name = self._get_project_stage(project_or_stage)

        default_stage = str(
            rules_data.get("default_stage", "investigacion")
        ).strip()

        stages = rules_data.get("stages", {})
        if not isinstance(stages, dict):
            stages = {}

        raw_stage_rules = (
            stages.get(stage_name)
            or stages.get(default_stage)
            or {}
        )

        if isinstance(raw_stage_rules, list):
            raw_stage_rules = {"required": raw_stage_rules}

        if not isinstance(raw_stage_rules, dict):
            raw_stage_rules = {}

        required = self._normalize_module_ids(
            raw_stage_rules.get("required", [])
        )
        optional = self._normalize_module_ids(
            raw_stage_rules.get("optional", [])
        )
        optional = [
            module_id
            for module_id in optional
            if module_id not in required
        ]

        return ResolverRuleSet(
            required=required,
            optional=optional,
            priority=self._normalize_priority_map(
                raw_stage_rules.get("priority", {})
            ),
            maximum_modules=self._normalize_maximum_modules(
                raw_stage_rules.get("maximum_modules")
            ),
            minimum_score=self._normalize_minimum_score(
                raw_stage_rules.get("minimum_score", 0.0)
            ),
        )

    def _load_knowledge_rules(self) -> dict[str, Any]:
        """Carga y valida knowledge_rules.yaml."""

        loaded_rules = read_yaml(KNOWLEDGE_RULES_PATH)

        if loaded_rules is None:
            return {}

        if not isinstance(loaded_rules, dict):
            raise ValueError(
                "knowledge_rules.yaml debe contener un objeto YAML "
                "en su nivel raíz."
            )

        return loaded_rules

    def _get_project_stage(
        self,
        project_or_stage: Project | str,
    ) -> str:
        """Obtiene el identificador normalizado de la etapa."""

        if isinstance(project_or_stage, str):
            return project_or_stage.strip() or "default"

        candidate_attributes = (
            "stage_actual",
            "stage",
            "current_stage",
            "pipeline_stage",
            "project_stage",
        )

        for attribute_name in candidate_attributes:
            value = getattr(project_or_stage, attribute_name, None)
            if value is not None and str(value).strip():
                return str(value).strip()

        return "default"

    def _normalize_module_ids(self, module_ids: Any) -> list[str]:
        """Normaliza IDs, elimina vacíos y conserva el orden."""

        if module_ids is None:
            return []
        if isinstance(module_ids, str):
            module_ids = [module_ids]
        if not isinstance(module_ids, (list, tuple, set)):
            return []

        normalized_ids: list[str] = []
        for module_id in module_ids:
            normalized_id = str(module_id).strip().upper()
            if normalized_id and normalized_id not in normalized_ids:
                normalized_ids.append(normalized_id)

        return normalized_ids

    def _normalize_priority_map(
        self,
        priority_data: Any,
    ) -> dict[str, float]:
        """Normaliza prioridades por módulo."""

        if priority_data is None:
            return {}

        if isinstance(priority_data, dict):
            normalized_priority: dict[str, float] = {}
            for module_id, raw_priority in priority_data.items():
                normalized_id = str(module_id).strip().upper()
                if normalized_id:
                    normalized_priority[normalized_id] = (
                        self._priority_value(raw_priority)
                    )
            return normalized_priority

        if isinstance(priority_data, (list, tuple)):
            normalized_ids = self._normalize_module_ids(priority_data)
            total_items = len(normalized_ids)
            return {
                module_id: float(total_items - index)
                for index, module_id in enumerate(normalized_ids)
            }

        return {}

    def _normalize_maximum_modules(self, value: Any) -> int | None:
        """Normaliza el límite máximo de módulos."""

        if value is None:
            return None
        try:
            normalized_value = int(value)
        except (TypeError, ValueError):
            return None
        return normalized_value if normalized_value > 0 else None

    def _normalize_minimum_score(self, value: Any) -> float:
        """Normaliza el puntaje mínimo permitido."""

        try:
            normalized_value = float(value)
        except (TypeError, ValueError):
            return 0.0
        return max(0.0, normalized_value)

    def _select_modules_by_rules(
        self,
        available_modules: list[KnowledgeModule],
        rule_set: ResolverRuleSet,
    ) -> list[KnowledgeModule]:
        """Selecciona obligatorios y opcionales por prioridad."""

        modules_by_id: dict[str, KnowledgeModule] = {}
        for module in available_modules:
            module_id = self._get_module_id(module)
            if module_id and module_id not in modules_by_id:
                modules_by_id[module_id] = module

        selected_modules = [
            modules_by_id[module_id]
            for module_id in rule_set.required
            if module_id in modules_by_id
        ]

        optional_modules = [
            modules_by_id[module_id]
            for module_id in rule_set.optional
            if module_id in modules_by_id
            and modules_by_id[module_id] not in selected_modules
        ]
        optional_modules.sort(
            key=lambda module: (
                -rule_set.priority.get(self._get_module_id(module), 0.0),
                self._get_module_id(module),
            )
        )
        selected_modules.extend(optional_modules)

        if rule_set.maximum_modules is not None:
            required_count = sum(
                self._get_module_id(module) in rule_set.required
                for module in selected_modules
            )
            effective_limit = max(
                rule_set.maximum_modules,
                required_count,
            )
            selected_modules = selected_modules[:effective_limit]

        return selected_modules

    def _get_module_id(self, module: KnowledgeModule) -> str:
        """Obtiene el identificador normalizado del módulo."""

        return str(getattr(module, "module_id", "")).strip().upper()

    ####################################################################
    # Utilidades internas
    ####################################################################

    def _normalize_text(self, text: str) -> str:
        text = unicodedata.normalize("NFKD", str(text))
        text = "".join(
            character
            for character in text
            if not unicodedata.combining(character)
        )
        text = text.lower()
        text = re.sub(r"[^a-z0-9]+", " ", text)
        return " ".join(text.split())

    def _tokenize(self, text: str) -> list[str]:
        normalized = self._normalize_text(text)
        return [
            word
            for word in WORD_PATTERN.findall(normalized)
            if word not in DEFAULT_STOPWORDS
        ]

    def _priority_value(self, value: Any) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0
