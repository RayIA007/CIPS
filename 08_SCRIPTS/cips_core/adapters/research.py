"""Adaptador real del Research Director para CIPS.

Este módulo traduce el payload estándar del Core Orchestrator al formato del
Research Prompt Builder y normaliza el resultado como ``AdapterResult``.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional

from .base import BaseAgentAdapter
from .contracts import AdapterRequest, AdapterResult
from .exceptions import AdapterContractError, AdapterValidationError


@dataclass(frozen=True, slots=True)
class ResearchAdapterConfig:
    """Configuración estable del adaptador de investigación."""

    token_budget: Optional[int] = 50_000
    optimize_prompt: bool = True
    expand_questions: bool = True
    optimize_objectives: bool = True
    resolve_constraints: bool = True
    input_cost_per_million_tokens: float = 0.0
    include_full_result: bool = True

    def __post_init__(self) -> None:
        if self.token_budget is not None and self.token_budget < 1:
            raise ValueError("token_budget debe ser positivo o None.")
        if self.input_cost_per_million_tokens < 0:
            raise ValueError("input_cost_per_million_tokens no puede ser negativo.")


class ResearchDirectorAdapter(BaseAgentAdapter):
    """Conecta el Core Orchestrator con ``AdvancedResearchPromptEngine``."""

    adapter_name = "ResearchDirectorAdapter"
    capability = "research"
    version = "1.0.0"

    def __init__(
        self,
        config: Optional[ResearchAdapterConfig] = None,
        *,
        engine: Any = None,
    ) -> None:
        super().__init__()
        self.config = config or ResearchAdapterConfig()
        self._engine = engine

    @property
    def engine(self) -> Any:
        """Crea el motor de forma perezosa para mantener imports desacoplados."""
        if self._engine is None:
            try:
                from research_prompt import AdvancedResearchPromptEngine
            except ImportError as exc:  # pragma: no cover - depende de instalación
                raise AdapterContractError(
                    "No está instalado el paquete 'research_prompt'. "
                    "Instala primero el Research Prompt Builder refactorizado."
                ) from exc

            self._engine = AdvancedResearchPromptEngine(
                optimize_prompt=self.config.optimize_prompt,
                expand_questions=self.config.expand_questions,
                optimize_objectives=self.config.optimize_objectives,
                resolve_constraints=self.config.resolve_constraints,
                token_budget=self.config.token_budget,
                input_cost_per_million_tokens=(
                    self.config.input_cost_per_million_tokens
                ),
            )
        return self._engine

    def validate_request(self, request: AdapterRequest) -> None:
        research_input = self._build_research_input(request)
        topic = self._first_text(research_input, "tema", "topic")
        objective = self._first_text(research_input, "objetivo", "objective")
        missing = []
        if not topic:
            missing.append("tema/topic")
        if not objective:
            missing.append("objetivo/objective")
        if missing:
            raise AdapterValidationError(
                "ResearchDirectorAdapter requiere: " + ", ".join(missing)
            )

    def run(self, request: AdapterRequest) -> Any:
        research_input = self._build_research_input(request)
        return self.engine.build(research_input)

    def normalize_result(
        self,
        *,
        raw_output: Any,
        request: AdapterRequest,
        started_at: float,
    ) -> AdapterResult:
        required = ("package", "score", "context", "audit_trail")
        missing = [name for name in required if not hasattr(raw_output, name)]
        if missing:
            raise AdapterContractError(
                "El Research Prompt Builder devolvió un resultado incompatible; "
                "faltan: " + ", ".join(missing)
            )

        package = raw_output.package
        score = raw_output.score
        diagnostics = list(getattr(score, "diagnostics", []) or [])
        warning_messages = tuple(
            str(getattr(item, "message", item))
            for item in diagnostics
            if self._severity_value(item) in {"medium", "high", "critical"}
        )

        output: dict[str, Any] = {
            "package_id": package.package_id,
            "system_prompt": package.system_prompt,
            "developer_prompt": package.developer_prompt,
            "user_prompt": package.user_prompt,
            "output_contract": package.output_contract,
            "language": package.language,
            "output_mode": self._enum_value(package.output_mode),
            "strictness": self._enum_value(package.strictness),
            "builder_version": package.builder_version,
            "model_version": package.model_version,
            "metadata": dict(package.metadata),
        }
        if self.config.include_full_result:
            output["research_result"] = raw_output.to_dict()

        metrics = {
            "package_id": package.package_id,
            "score": score.overall,
            "recommendation": score.recommendation,
            "token_estimate": score.metrics.token_estimate,
            "total_characters": score.metrics.total_characters,
            "section_count": score.metrics.section_count,
            "diagnostic_count": len(diagnostics),
            "blocking_diagnostic_count": score.metrics.blocking_diagnostic_count,
            "audit_id": raw_output.audit_trail.audit_id,
            "audit_event_count": len(raw_output.audit_trail.events),
        }
        artifacts = (
            {
                "artifact_type": "prompt_package",
                "artifact_id": package.package_id,
                "schema_version": package.schema_version,
                "builder_version": package.builder_version,
            },
        )

        return AdapterResult.success(
            adapter_name=self.adapter_name,
            capability=self.capability,
            output=output,
            warnings=warning_messages,
            metrics=metrics,
            artifacts=artifacts,
            started_at=started_at,
        )

    def descriptor_metadata(self) -> dict[str, Any]:
        metadata = super().descriptor_metadata()
        metadata.update(
            {
                "component": "research_prompt.AdvancedResearchPromptEngine",
                "token_budget": self.config.token_budget,
                "optimize_prompt": self.config.optimize_prompt,
            }
        )
        return metadata

    @staticmethod
    def _build_research_input(request: AdapterRequest) -> dict[str, Any]:
        """Fusiona datos compartidos y entrada de tarea con precedencia local."""
        merged = dict(request.shared_data)
        merged.update(request.input_data)
        merged.setdefault("project_id", request.context.project_id)
        merged.setdefault("workflow_id", request.context.workflow_id)
        merged.setdefault("run_id", request.context.run_id)
        merged.setdefault("task_id", request.context.task_id)
        merged.setdefault("correlation_id", request.context.correlation_id)
        if request.task_outputs:
            merged.setdefault("task_outputs", dict(request.task_outputs))
        return merged

    @staticmethod
    def _first_text(value: Mapping[str, Any], *keys: str) -> str:
        for key in keys:
            candidate = value.get(key)
            if candidate is not None and str(candidate).strip():
                return str(candidate).strip()
        return ""

    @staticmethod
    def _enum_value(value: Any) -> Any:
        return getattr(value, "value", value)

    @staticmethod
    def _severity_value(diagnostic: Any) -> str:
        severity = getattr(diagnostic, "severity", "")
        return str(getattr(severity, "value", severity)).casefold()
