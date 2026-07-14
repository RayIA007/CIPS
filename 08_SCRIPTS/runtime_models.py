"""
=========================================================
Proyecto : CIPS
Release  : 0.7
Build    : 045
Archivo  : runtime_models.py
Estado   : RELEASE
=========================================================

Define los modelos de datos compartidos por el Runtime,
los Engines, el sistema de finalización y los exportadores.

Compatibilidad:
- Runtime Framework existente.
- LLM Provider Framework.
- ValidatorEngine.
- MemoryEngine.
- Sprint 020: Finalization & Export Framework.
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
    warnings: list[str] = field(
        default_factory=list
    )
    errors: list[str] = field(
        default_factory=list
    )
    message: str = ""
    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    @classmethod
    def ok(
        cls,
        data: Any = None,
        message: str = "Operación completada correctamente.",
        warnings: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> "EngineResult":
        """
        Construye un resultado exitoso.
        """

        return cls(
            success=True,
            data=data,
            warnings=list(
                warnings or []
            ),
            errors=[],
            message=message,
            metadata=dict(
                metadata or {}
            ),
        )

    @classmethod
    def fail(
        cls,
        message: str = "La operación falló.",
        errors: list[str] | None = None,
        warnings: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> "EngineResult":
        """
        Construye un resultado fallido.
        """

        return cls(
            success=False,
            data=None,
            warnings=list(
                warnings or []
            ),
            errors=list(
                errors or []
            ),
            message=message,
            metadata=dict(
                metadata or {}
            ),
        )


@dataclass
class Project:
    """
    Representa un proyecto CIPS durante la ejecución.
    """

    project_id: str
    path: Path
    tema: str = ""
    estado: str = "CREATED"
    stage_actual: str = "investigacion"
    ultimo_stage_validado: str = ""
    config: dict[str, Any] = field(
        default_factory=dict
    )
    memory: dict[str, Any] = field(
        default_factory=dict
    )
    metadata: dict[str, Any] = field(
        default_factory=dict
    )


@dataclass
class KnowledgeModule:
    """
    Representa un módulo cargado desde 09_KNOWLEDGE.
    """

    module_id: str
    name: str
    path: Path
    category: str
    content: str
    dependencies: list[str] = field(
        default_factory=list
    )
    metadata: dict[str, Any] = field(
        default_factory=dict
    )


@dataclass
class ContextObject:
    """
    Representa el contexto construido con Knowledge Modules.
    """

    project: Project
    modules: list[KnowledgeModule]
    content: str
    metadata: dict[str, Any] = field(
        default_factory=dict
    )


@dataclass
class PromptObject:
    """
    Representa un prompt estructurado antes de renderizarse.
    """

    project: Project
    objective: str
    context: ContextObject
    output_format: str = "Markdown"
    restrictions: list[str] = field(
        default_factory=list
    )
    metadata: dict[str, Any] = field(
        default_factory=dict
    )


@dataclass
class LLMResponse:
    """
    Representa una respuesta producida por un modelo IA.
    """

    content: str
    model: str = "manual"
    metadata: dict[str, Any] = field(
        default_factory=dict
    )


@dataclass
class ValidationResult:
    """
    Representa el resultado de validar una respuesta IA.
    """

    approved: bool
    observations: list[str] = field(
        default_factory=list
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


@dataclass
class MemoryRecord:
    """
    Representa un registro de memoria del proyecto.
    """

    stage: str
    status: str
    summary: str = ""
    next_stage: str = ""
    metadata: dict[str, Any] = field(
        default_factory=dict
    )


@dataclass
class ProjectMetrics:
    """
    Métricas consolidadas de un proyecto finalizado.

    Este modelo contiene datos medibles del proyecto, no
    contenido editorial ni decisiones de publicación.
    """

    stages_total: int = 0
    stages_completed: int = 0
    completion_percent: float = 0.0

    files_total: int = 0
    prompts_total: int = 0
    responses_total: int = 0
    memory_records: int = 0

    total_characters: int = 0
    total_words: int = 0
    total_lines: int = 0

    prompt_characters: int = 0
    response_characters: int = 0

    prompt_tokens: int = 0
    response_tokens: int = 0
    thinking_tokens: int = 0
    total_tokens: int = 0

    duration_seconds: float = 0.0
    estimated_cost: float = 0.0
    currency: str = "USD"

    validation_scores: dict[str, float] = field(
        default_factory=dict
    )

    average_validation_score: float = 0.0
    minimum_validation_score: float = 0.0
    maximum_validation_score: float = 0.0

    providers_used: list[str] = field(
        default_factory=list
    )

    models_used: list[str] = field(
        default_factory=list
    )

    knowledge_modules_used: list[str] = field(
        default_factory=list
    )

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    def is_complete(self) -> bool:
        """
        Indica si todos los Stages registrados fueron completados.
        """

        return (
            self.stages_total > 0
            and self.stages_completed >= self.stages_total
        )


@dataclass
class ProjectManifest:
    """
    Manifiesto técnico y auditable del proyecto.

    Describe los archivos, sus hashes, versiones, fechas,
    modelos y datos de trazabilidad necesarios para revisar
    o reproducir una exportación.
    """

    project_id: str
    generated_at: str

    manifest_version: str = "1.0"
    cips_release: str = ""
    cips_build: str = ""

    project_path: str = ""
    project_stage: str = ""
    project_status: str = ""

    files: list[dict[str, Any]] = field(
        default_factory=list
    )

    file_count: int = 0
    total_size_bytes: int = 0

    algorithms: dict[str, str] = field(
        default_factory=lambda: {
            "file_hash": "sha256",
        }
    )

    providers: list[str] = field(
        default_factory=list
    )

    models: list[str] = field(
        default_factory=list
    )

    history: list[dict[str, Any]] = field(
        default_factory=list
    )

    metrics_summary: dict[str, Any] = field(
        default_factory=dict
    )

    exports: list[dict[str, Any]] = field(
        default_factory=list
    )

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    def has_files(self) -> bool:
        """
        Indica si el manifiesto contiene archivos registrados.
        """

        return bool(self.files)

    def register_file(
        self,
        file_data: dict[str, Any],
    ) -> None:
        """
        Agrega un archivo al manifiesto.

        El cálculo de hash y tamaño corresponde a ManifestEngine.
        """

        self.files.append(
            dict(file_data)
        )

        self.file_count = len(
            self.files
        )

        size_bytes = file_data.get(
            "size_bytes",
            0,
        )

        try:
            self.total_size_bytes += int(
                size_bytes
            )
        except (TypeError, ValueError):
            pass


@dataclass
class FinalProjectObject:
    """
    Representación consolidada de un proyecto finalizado.

    Este objeto será la fuente única para:

    - FinalizationEngine;
    - ManifestEngine;
    - MetricsEngine;
    - ExportEngine;
    - exportadores Markdown, JSON, DOCX, PDF y ZIP;
    - futuros conectores MCP y plataformas externas.
    """

    project: Project

    investigation: str = ""
    verification: str = ""
    script: str = ""
    storyboard: str = ""
    seo: str = ""
    publication: str = ""
    final_content: str = ""

    stage_contents: dict[str, str] = field(
        default_factory=dict
    )

    source_files: dict[str, str] = field(
        default_factory=dict
    )

    prompt_files: dict[str, str] = field(
        default_factory=dict
    )

    metrics: ProjectMetrics | None = None
    manifest: ProjectManifest | None = None

    exports: dict[str, str] = field(
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

    def get_stage_content(
        self,
        stage: str,
    ) -> str:
        """
        Devuelve el contenido de un Stage consolidado.
        """

        normalized_stage = str(
            stage
        ).strip().lower()

        explicit_fields = {
            "investigacion": self.investigation,
            "verificacion": self.verification,
            "guion": self.script,
            "storyboard": self.storyboard,
            "seo": self.seo,
            "publicacion": self.publication,
            "final": self.final_content,
        }

        explicit_content = explicit_fields.get(
            normalized_stage,
            "",
        )

        if explicit_content:
            return explicit_content

        return self.stage_contents.get(
            normalized_stage,
            "",
        )

    def set_stage_content(
        self,
        stage: str,
        content: str,
    ) -> None:
        """
        Registra contenido y sincroniza los campos principales.
        """

        normalized_stage = str(
            stage
        ).strip().lower()

        normalized_content = str(
            content or ""
        ).strip()

        self.stage_contents[
            normalized_stage
        ] = normalized_content

        if normalized_stage == "investigacion":
            self.investigation = normalized_content

        elif normalized_stage == "verificacion":
            self.verification = normalized_content

        elif normalized_stage == "guion":
            self.script = normalized_content

        elif normalized_stage == "storyboard":
            self.storyboard = normalized_content

        elif normalized_stage == "seo":
            self.seo = normalized_content

        elif normalized_stage == "publicacion":
            self.publication = normalized_content

        elif normalized_stage == "final":
            self.final_content = normalized_content

    def completed_stages(self) -> list[str]:
        """
        Devuelve los Stages que contienen información.
        """

        stage_order = [
            "investigacion",
            "verificacion",
            "guion",
            "storyboard",
            "seo",
            "publicacion",
            "final",
        ]

        return [
            stage
            for stage in stage_order
            if self.get_stage_content(stage)
        ]

    def missing_stages(
        self,
        required_stages: list[str] | None = None,
    ) -> list[str]:
        """
        Devuelve los Stages requeridos que no tienen contenido.
        """

        stages = required_stages or [
            "investigacion",
            "verificacion",
            "guion",
            "storyboard",
            "seo",
            "publicacion",
        ]

        return [
            stage
            for stage in stages
            if not self.get_stage_content(stage)
        ]

    def is_complete(self) -> bool:
        """
        Comprueba si existen todos los entregables de producción.
        """

        return not self.missing_stages()

    def register_export(
        self,
        export_format: str,
        export_path: str | Path,
    ) -> None:
        """
        Registra una exportación producida.
        """

        normalized_format = str(
            export_format
        ).strip().lower()

        if not normalized_format:
            raise ValueError(
                "export_format no puede estar vacío."
            )

        self.exports[
            normalized_format
        ] = str(export_path)