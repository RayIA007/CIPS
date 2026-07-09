"""
=========================================================
Proyecto : CIPS
Release  : 0.3
Build    : 005
Archivo  : runtime_models.py
Estado   : RELEASE
=========================================================
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class EngineResult:
    """
    Resultado estándar devuelto por todos los Engines.
    """

    success: bool
    data: Any = None
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    message: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def ok(
        cls,
        data: Any = None,
        message: str = "Operación completada correctamente.",
        warnings: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> "EngineResult":
        return cls(
            success=True,
            data=data,
            warnings=warnings or [],
            errors=[],
            message=message,
            metadata=metadata or {},
        )

    @classmethod
    def fail(
        cls,
        message: str = "La operación falló.",
        errors: list[str] | None = None,
        warnings: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> "EngineResult":
        return cls(
            success=False,
            data=None,
            warnings=warnings or [],
            errors=errors or [],
            message=message,
            metadata=metadata or {},
        )


@dataclass
class Project:
    """
    Representa un proyecto CIPS durante la ejecución del Runtime.
    """

    project_id: str
    path: Path
    tema: str = ""
    estado: str = "CREATED"
    stage_actual: str = "investigacion"
    ultimo_stage_validado: str = ""
    config: dict[str, Any] = field(default_factory=dict)
    memory: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class KnowledgeModule:
    """
    Representa un módulo de conocimiento cargado desde 09_KNOWLEDGE.
    """

    module_id: str
    name: str
    path: Path
    category: str
    content: str
    dependencies: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ContextObject:
    """
    Representa el contexto construido a partir de Knowledge Modules.
    """

    project: Project
    modules: list[KnowledgeModule]
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class PromptObject:
    """
    Representa un prompt estructurado antes de renderizarse a Markdown.
    """

    project: Project
    objective: str
    context: ContextObject
    output_format: str = "Markdown"
    restrictions: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class LLMResponse:
    """
    Representa una respuesta producida por un modelo de IA.
    """

    content: str
    model: str = "manual"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationResult:
    """
    Representa el resultado de validar una respuesta IA.
    """

    approved: bool
    observations: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class MemoryRecord:
    """
    Representa un registro de memoria del proyecto.
    """

    stage: str
    status: str
    summary: str = ""
    next_stage: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)