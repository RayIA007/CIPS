"""Adapter del Strategy Director para el Core Orchestrator de CIPS."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional

from .base import BaseAgentAdapter
from .contracts import AdapterRequest, AdapterResult
from .exceptions import AdapterContractError, AdapterValidationError


@dataclass(frozen=True, slots=True)
class StrategyAdapterConfig:
    require_evidence: bool = True
    include_full_result: bool = True


class StrategyDirectorAdapter(BaseAgentAdapter):
    adapter_name = "StrategyDirectorAdapter"
    capability = "strategy"
    version = "1.0.0"

    def __init__(self, config: Optional[StrategyAdapterConfig] = None, *, engine: Any = None) -> None:
        super().__init__()
        self.config = config or StrategyAdapterConfig()
        self._engine = engine

    @property
    def engine(self) -> Any:
        if self._engine is None:
            try:
                from strategy_director import StrategyDirectorEngine
            except ImportError as exc:
                raise AdapterContractError("No está instalado el paquete 'strategy_director'.") from exc
            self._engine = StrategyDirectorEngine()
        return self._engine

    def validate_request(self, request: AdapterRequest) -> None:
        payload = self._payload(request)
        missing = []
        if not self._first_text(payload, "tema", "topic", "project_name"):
            missing.append("tema/topic")
        if not self._first_text(payload, "objetivo", "business_objective", "objective"):
            missing.append("objetivo/business_objective")
        if missing:
            raise AdapterValidationError("StrategyDirectorAdapter requiere: " + ", ".join(missing))
        if self.config.require_evidence and not self._has_evidence(payload):
            raise AdapterValidationError(
                "StrategyDirectorAdapter requiere evidencia real en research_findings, evidence, insights o hallazgos. "
                "Un PromptPackage del Research Director es una referencia, no un hallazgo confirmado."
            )

    def run(self, request: AdapterRequest) -> Any:
        return self.engine.build(self._payload(request))

    def normalize_result(self, *, raw_output: Any, request: AdapterRequest, started_at: float) -> AdapterResult:
        if not hasattr(raw_output, "package") or not hasattr(raw_output, "score"):
            raise AdapterContractError("StrategyDirectorEngine devolvió un resultado incompatible.")
        package = raw_output.package
        score = raw_output.score
        output = {
            "package_id": package.package_id,
            "strategy_package": package.to_dict(),
            "executive_summary": package.executive_summary,
            "value_proposition": package.value_proposition,
            "positioning": package.positioning,
        }
        if self.config.include_full_result:
            output["strategy_result"] = raw_output.to_dict()
        metrics = {
            "package_id": package.package_id,
            "score": score.overall,
            "completeness": score.completeness,
            "evidence_coverage": score.evidence_coverage,
            "measurability": score.measurability,
            "objective_count": len(package.objectives),
            "audience_count": len(package.audiences),
            "pillar_count": len(package.content_pillars),
            "kpi_count": len(package.kpis),
            "roadmap_phase_count": len(package.roadmap),
            "evidence_count": len(package.evidence),
            "source_reference_count": len(package.source_references),
        }
        return AdapterResult.success(
            adapter_name=self.adapter_name,
            capability=self.capability,
            output=output,
            warnings=tuple(score.warnings),
            metrics=metrics,
            artifacts=({
                "artifact_type": "strategy_package",
                "artifact_id": package.package_id,
                "schema_version": package.schema_version,
            },),
            started_at=started_at,
        )

    def descriptor_metadata(self) -> dict[str, Any]:
        metadata = super().descriptor_metadata()
        metadata.update({"component": "strategy_director.StrategyDirectorEngine", "require_evidence": self.config.require_evidence})
        return metadata

    @staticmethod
    def _payload(request: AdapterRequest) -> dict[str, Any]:
        merged = dict(request.shared_data)
        merged.update(request.input_data)
        merged.setdefault("project_id", request.context.project_id)
        merged.setdefault("workflow_id", request.context.workflow_id)
        merged.setdefault("run_id", request.context.run_id)
        merged.setdefault("task_id", request.context.task_id)
        merged.setdefault("task_outputs", dict(request.task_outputs))
        return merged

    @staticmethod
    def _first_text(payload: Mapping[str, Any], *keys: str) -> str:
        for key in keys:
            value = payload.get(key)
            if value is not None and str(value).strip():
                return str(value).strip()
        return ""

    @staticmethod
    def _has_evidence(payload: Mapping[str, Any]) -> bool:
        for key in ("research_findings", "evidence", "insights", "hallazgos"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return True
            if value and not isinstance(value, str):
                return True
        return False
