"""Contratos JSON y validadores del Research Prompt Builder."""
from __future__ import annotations

from typing import Any, Mapping

try:
    from research_director_models import ResearchStatus
except ImportError:  # pragma: no cover
    from ..research_director_models import ResearchStatus

from .common import (
    DEFAULT_SCHEMA_VERSION,
    ResearchPromptContractError,
    ResearchPromptValidationError,
)
from .models import PromptBuildContext, PromptPackage

class ResearchPromptContract:
    @staticmethod
    def base_contract() -> dict[str, Any]:
        return {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "title": "CIPS Research Director Response",
            "type": "object",
            "additionalProperties": False,
            "required": [
                "schema_version", "project_id", "status", "summary",
                "research_plan", "sources", "evidence", "claims",
                "verifications", "findings", "contradictions",
                "knowledge_gaps", "hypotheses", "metrics",
                "publication_assessment", "issues", "artifacts",
            ],
            "properties": {
                "schema_version": {"type": "string", "const": DEFAULT_SCHEMA_VERSION},
                "project_id": {"type": "string", "minLength": 1},
                "status": {"type": "string", "enum": [item.value for item in ResearchStatus]},
                "summary": {"type": "string", "minLength": 1},
                "research_plan": {"type": "object"},
                "sources": {"type": "array", "items": {"type": "object"}},
                "evidence": {"type": "array", "items": {"type": "object"}},
                "claims": {"type": "array", "items": {"type": "object"}},
                "verifications": {"type": "array", "items": {"type": "object"}},
                "findings": {"type": "array", "items": {"type": "object"}},
                "contradictions": {"type": "array", "items": {"type": "object"}},
                "knowledge_gaps": {"type": "array", "items": {"type": "object"}},
                "hypotheses": {"type": "array", "items": {"type": "object"}},
                "metrics": {"type": "object"},
                "publication_assessment": {
                    "type": "object",
                    "required": ["publication_safe", "ready_for_fact_checker", "ready_for_strategy", "human_review_required", "blocking_reasons"],
                    "properties": {
                        "publication_safe": {"type": "boolean"},
                        "ready_for_fact_checker": {"type": "boolean"},
                        "ready_for_strategy": {"type": "boolean"},
                        "human_review_required": {"type": "boolean"},
                        "blocking_reasons": {"type": "array", "items": {"type": "string"}},
                    },
                },
                "issues": {"type": "array", "items": {"type": "object"}},
                "artifacts": {"type": "array", "items": {"type": "object"}},
            },
        }


class ResearchPromptValidator:
    @staticmethod
    def validate_contract(contract: Mapping[str, Any]) -> None:
        if not isinstance(contract, Mapping):
            raise ResearchPromptContractError("El contrato debe ser Mapping.")
        if contract.get("type") != "object":
            raise ResearchPromptContractError("El contrato raíz debe ser object.")
        required = contract.get("required", [])
        properties = contract.get("properties", {})
        if not isinstance(required, list) or not isinstance(properties, Mapping):
            raise ResearchPromptContractError("Estructura de contrato inválida.")
        missing = [name for name in required if name not in properties]
        if missing:
            raise ResearchPromptContractError("Campos sin definición: " + ", ".join(missing))

    @staticmethod
    def validate_context(context: PromptBuildContext) -> None:
        if len(context.questions) > context.configuration.max_questions:
            raise ResearchPromptValidationError("El contexto excede max_questions.")
        if len(context.supplied_sources) > context.configuration.max_sources:
            raise ResearchPromptValidationError("El contexto excede max_sources.")
        if len(context.supplied_evidence) > context.configuration.max_evidence_items:
            raise ResearchPromptValidationError("El contexto excede max_evidence_items.")
        if len(context.supplied_claims) > context.configuration.max_claims:
            raise ResearchPromptValidationError("El contexto excede max_claims.")

    @staticmethod
    def validate_sections(sections: Any) -> None:
        if not isinstance(sections, (list, tuple)):
            raise ResearchPromptValidationError("'sections' debe ser una secuencia.")
        ids = []
        for item in sections:
            if not hasattr(item, "section_id") or not hasattr(item, "render"):
                raise ResearchPromptValidationError("Cada sección debe ser PromptSection.")
            ids.append(item.section_id)
        if len(ids) != len(set(ids)):
            raise ResearchPromptValidationError("Existen section_id duplicados.")

    @staticmethod
    def validate_package(package: PromptPackage) -> None:
        ResearchPromptValidator.validate_contract(package.output_contract)
        ids = [item.section_id for item in package.sections]
        if len(ids) != len(set(ids)):
            raise ResearchPromptValidationError("Existen section_id duplicados.")


