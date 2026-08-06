"""Ensamblado y orquestación avanzada."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from .audit import AuditEventType, PromptAuditTrail
from .builder import ResearchDirectorPromptBuilder, ResearchMethodSelector
from .diagnostics import PromptScore, PromptScorer
from .exporters import PromptExportProvider, PromptExporter
from .models import PromptBuildContext, PromptPackage
from .normalization import (
    ConstraintResolver,
    ContextNormalizer,
    ResearchObjectiveOptimizer,
    ResearchQuestionExpander,
)
from .optimization import PromptOptimizer

RESEARCH_PROMPT_BUILDER_PART3_VERSION = "1.0.0-refactor-engine"

class ResearchPromptAssembler:
    def __init__(self, builder: Optional[ResearchDirectorPromptBuilder] = None, *,
                 expand_questions: bool = True, optimize_objectives: bool = True,
                 resolve_constraints: bool = True) -> None:
        self.builder = builder or ResearchDirectorPromptBuilder()
        self.expand_questions_enabled = expand_questions
        self.optimize_objectives_enabled = optimize_objectives
        self.resolve_constraints_enabled = resolve_constraints

    def assemble(self, value: Any, *, audit_trail: Optional[PromptAuditTrail] = None) -> tuple[PromptBuildContext, PromptPackage]:
        audit = audit_trail or PromptAuditTrail()
        context = ContextNormalizer.normalize(value, configuration=self.builder.configuration)
        audit.add(AuditEventType.NORMALIZED, "Entrada normalizada.", after=context.to_dict())
        if self.optimize_objectives_enabled:
            before = context.to_dict()
            ResearchObjectiveOptimizer.optimize_context(context)
            audit.add(AuditEventType.OBJECTIVE_OPTIMIZED, "Objetivos optimizados.", before=before, after=context.to_dict())
        if self.resolve_constraints_enabled:
            before = context.to_dict()
            ConstraintResolver.resolve_context(context)
            audit.add(AuditEventType.CONSTRAINT_RESOLVED, "Restricciones consolidadas.", before=before, after=context.to_dict())
        if self.expand_questions_enabled:
            before_count = len(context.questions)
            profile = ResearchMethodSelector.infer_profile(context)
            context.questions = ResearchQuestionExpander.expand(context, profile=profile)
            audit.add(AuditEventType.QUESTION_EXPANDED, "Preguntas expandidas.",
                      details={"before": before_count, "after": len(context.questions), "profile": profile.value})
        package = self.builder.build(context)
        package.metadata.update({"audit_id": audit.audit_id, "part3_version": RESEARCH_PROMPT_BUILDER_PART3_VERSION})
        audit.add(AuditEventType.ASSEMBLED, "PromptPackage ensamblado.", after=package.to_dict())
        return context, package



@dataclass(slots=True)
class AdvancedPromptResult:
    context: PromptBuildContext
    package: PromptPackage
    score: PromptScore
    audit_trail: PromptAuditTrail

    def to_dict(self) -> dict[str, Any]:
        return {"context": self.context.to_dict(), "package": self.package.to_dict(),
                "score": self.score.to_dict(), "audit_trail": self.audit_trail.to_dict()}


class AdvancedResearchPromptEngine:
    def __init__(self, builder: Optional[ResearchDirectorPromptBuilder] = None, *,
                 optimize_prompt: bool = True, expand_questions: bool = True,
                 optimize_objectives: bool = True, resolve_constraints: bool = True,
                 token_budget: Optional[int] = None,
                 input_cost_per_million_tokens: float = 0.0) -> None:
        self.builder = builder or ResearchDirectorPromptBuilder()
        self.optimize_prompt = optimize_prompt
        self.token_budget = token_budget
        self.assembler = ResearchPromptAssembler(self.builder, expand_questions=expand_questions,
                                                  optimize_objectives=optimize_objectives,
                                                  resolve_constraints=resolve_constraints)
        self.optimizer = PromptOptimizer()
        self.scorer = PromptScorer(input_cost_per_million_tokens=input_cost_per_million_tokens)

    def build(self, value: Any) -> AdvancedPromptResult:
        audit = PromptAuditTrail(metadata={"engine": self.__class__.__name__, "version": RESEARCH_PROMPT_BUILDER_PART3_VERSION})
        audit.add(AuditEventType.CREATED, "Inicio de construcción avanzada.")
        context, package = self.assembler.assemble(value, audit_trail=audit)
        if self.optimize_prompt:
            self.optimizer.optimize_package(package, audit_trail=audit)
        score = self.scorer.score(context=context, package=package, token_budget=self.token_budget)
        audit.add(AuditEventType.SCORED, "Métricas y diagnósticos calculados.", after=score.to_dict(),
                  details={"overall": score.overall, "diagnostics": len(score.diagnostics)})
        package.metadata["prompt_score"] = {"overall": score.overall, "recommendation": score.recommendation,
                                             "metrics": score.metrics.to_dict()}
        package.metadata["audit_id"] = audit.audit_id
        package.metadata["audit_event_count"] = len(audit.events)
        return AdvancedPromptResult(context, package, score, audit)

    def export(self, result: AdvancedPromptResult, provider: PromptExportProvider, **kwargs: Any) -> dict[str, Any]:
        payload = PromptExporter.export(result.package, provider, **kwargs)
        result.audit_trail.add(AuditEventType.EXPORTED, f"Paquete exportado para {provider.value}.",
                               after=payload, details={"provider": provider.value})
        return payload


