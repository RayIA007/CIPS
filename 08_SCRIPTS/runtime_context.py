"""
=========================================================
Proyecto : CIPS
Release  : 0.4
Build    : 017
Archivo  : runtime_context.py
Estado   : RELEASE
=========================================================

Define el objeto compartido que circula entre los
componentes del Runtime.
"""

from dataclasses import dataclass, field
from typing import Any

from runtime_models import (
    ContextObject,
    EngineResult,
    KnowledgeModule,
    LLMResponse,
    Project,
    PromptObject,
    ValidationResult,
)


@dataclass
class RuntimeContext:
    """
    Estado compartido de una ejecución del Runtime.

    Cada componente recibe este objeto, utiliza únicamente
    los campos relacionados con su responsabilidad y guarda
    su resultado en el campo correspondiente.
    """

    project: Project

    knowledge_modules: list[KnowledgeModule] = field(
        default_factory=list
    )

    resolved_modules: list[KnowledgeModule] = field(
        default_factory=list
    )

    compressed_modules: list[KnowledgeModule] = field(
        default_factory=list
    )

    context_object: ContextObject | None = None

    prompt_object: PromptObject | None = None

    prompt_markdown: str = ""

    prompt_path: str = ""

    llm_response: LLMResponse | None = None

    validation_result: ValidationResult | None = None

    memory_data: dict[str, Any] = field(
        default_factory=dict
    )

    warnings: list[str] = field(
        default_factory=list
    )

    errors: list[str] = field(
        default_factory=list
    )

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    component_results: dict[str, EngineResult] = field(
        default_factory=dict
    )

    def register_result(
        self,
        component_name: str,
        result: EngineResult,
    ) -> None:
        """
        Registra el resultado producido por un componente.
        """

        self.component_results[component_name] = result

        self.warnings.extend(result.warnings)
        self.errors.extend(result.errors)

        if result.metadata:
            self.metadata[component_name] = result.metadata

    def has_errors(self) -> bool:
        """
        Indica si la ejecución contiene errores.
        """

        return bool(self.errors)

    def is_ready_for_context(self) -> bool:
        """
        Verifica si existen módulos disponibles para construir contexto.
        """

        return bool(
            self.compressed_modules
            or self.resolved_modules
            or self.knowledge_modules
        )

    def is_ready_for_prompt(self) -> bool:
        """
        Verifica si existe un ContextObject válido.
        """

        return self.context_object is not None

    def is_ready_for_validation(self) -> bool:
        """
        Verifica si existe una respuesta LLM disponible.
        """

        return self.llm_response is not None

    def get_active_modules(self) -> list[KnowledgeModule]:
        """
        Devuelve el conjunto de módulos más procesado disponible.

        Prioridad:

        1. compressed_modules
        2. resolved_modules
        3. knowledge_modules
        """

        if self.compressed_modules:
            return self.compressed_modules

        if self.resolved_modules:
            return self.resolved_modules

        return self.knowledge_modules