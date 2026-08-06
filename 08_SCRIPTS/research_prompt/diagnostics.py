"""Diagnósticos, métricas y scoring de prompts."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional, Sequence

try:
    from research_director_models import (
        FactClaim,
        ResearchConstraint,
        ResearchEvidence,
        ResearchFinding,
        ResearchQuestion,
        ResearchSource,
        generate_id,
        utc_now_iso,
    )
except ImportError:  # pragma: no cover
    from ..research_director_models import (
        FactClaim,
        ResearchConstraint,
        ResearchEvidence,
        ResearchFinding,
        ResearchQuestion,
        ResearchSource,
        generate_id,
        utc_now_iso,
    )

from .advanced_common import _clamp, _get, _key, _list, _serialize, _tokens
from .common import normalize_string_list, normalize_text
from .models import PromptBuildContext, PromptPackage

class DiagnosticSeverity(str, Enum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class DiagnosticCode(str, Enum):
    EMPTY_SYSTEM_PROMPT = "empty_system_prompt"
    EMPTY_USER_PROMPT = "empty_user_prompt"
    EMPTY_OBJECTIVE = "empty_objective"
    EMPTY_TOPIC = "empty_topic"
    DUPLICATE_SECTION = "duplicate_section"
    DUPLICATE_QUESTION = "duplicate_question"
    DUPLICATE_CONSTRAINT = "duplicate_constraint"
    DUPLICATE_SOURCE = "duplicate_source"
    ORPHAN_EVIDENCE = "orphan_evidence"
    ORPHAN_CLAIM = "orphan_claim"
    ORPHAN_FINDING = "orphan_finding"
    CLAIM_WITHOUT_EVIDENCE = "claim_without_evidence"
    FINDING_WITHOUT_SUPPORT = "finding_without_support"
    CONTRADICTORY_INSTRUCTIONS = "contradictory_instructions"
    MISSING_OUTPUT_CONTRACT = "missing_output_contract"
    TOKEN_BUDGET_EXCEEDED = "token_budget_exceeded"
    LOW_QUESTION_COVERAGE = "low_question_coverage"
    HIGH_AMBIGUITY = "high_ambiguity"
    INVALID_REFERENCE = "invalid_reference"



@dataclass(slots=True)
class PromptDiagnostic:
    code: DiagnosticCode
    message: str
    severity: DiagnosticSeverity = DiagnosticSeverity.MEDIUM
    diagnostic_id: str = field(default_factory=lambda: generate_id("pdiag"))
    location: str = ""
    recommendation: str = ""
    blocking: bool = False
    details: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.severity is DiagnosticSeverity.CRITICAL:
            self.blocking = True

    def to_dict(self) -> dict[str, Any]:
        return _serialize(self)


@dataclass(slots=True)
class PromptMetrics:
    total_characters: int = 0
    token_estimate: int = 0
    section_count: int = 0
    objective_count: int = 0
    question_count: int = 0
    constraint_count: int = 0
    source_count: int = 0
    evidence_count: int = 0
    claim_count: int = 0
    finding_count: int = 0
    diagnostic_count: int = 0
    blocking_diagnostic_count: int = 0
    coverage_score: float = 0.0
    clarity_score: float = 0.0
    completeness_score: float = 0.0
    traceability_score: float = 0.0
    ambiguity_score: float = 0.0
    complexity_score: float = 0.0
    optimization_score: float = 0.0
    quality_score: float = 0.0
    estimated_runtime_seconds: float = 0.0
    estimated_input_cost: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return _serialize(self)


@dataclass(slots=True)
class PromptScore:
    overall: float
    recommendation: str
    metrics: PromptMetrics
    diagnostics: list[PromptDiagnostic] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return _serialize(self)



class PromptDiagnostics:
    def analyze(self, *, context: Optional[PromptBuildContext] = None,
                package: Optional[PromptPackage] = None,
                token_budget: Optional[int] = None) -> list[PromptDiagnostic]:
        out: list[PromptDiagnostic] = []
        if context:
            out.extend(self._context(context))
        if package:
            out.extend(self._package(package, token_budget))
        return out

    def _context(self, context: PromptBuildContext) -> list[PromptDiagnostic]:
        out: list[PromptDiagnostic] = []
        if not context.topic:
            out.append(PromptDiagnostic(DiagnosticCode.EMPTY_TOPIC, "El tema está vacío.", DiagnosticSeverity.CRITICAL))
        if not context.objective:
            out.append(PromptDiagnostic(DiagnosticCode.EMPTY_OBJECTIVE, "El objetivo está vacío.", DiagnosticSeverity.CRITICAL))
        if len(context.questions) < 2:
            out.append(PromptDiagnostic(DiagnosticCode.LOW_QUESTION_COVERAGE,
                                        "Hay menos de dos preguntas de investigación.", DiagnosticSeverity.MEDIUM,
                                        recommendation="Expandir preguntas."))
        out.extend(self._duplicates(context.questions, "question", DiagnosticCode.DUPLICATE_QUESTION))
        out.extend(self._duplicates(context.constraints, "description", DiagnosticCode.DUPLICATE_CONSTRAINT))
        source_ids = {normalize_text(_get(x, "source_id", default="")) for x in context.supplied_sources}
        evidence_ids = {normalize_text(_get(x, "evidence_id", default="")) for x in context.supplied_evidence}
        claim_ids = {normalize_text(_get(x, "claim_id", default="")) for x in context.supplied_claims}
        for ev in context.supplied_evidence:
            sid = normalize_text(_get(ev, "source_id", default=""))
            if sid and sid not in source_ids:
                out.append(PromptDiagnostic(DiagnosticCode.ORPHAN_EVIDENCE,
                                            f"Evidencia referencia fuente inexistente: {sid}.", DiagnosticSeverity.HIGH))
        for claim in context.supplied_claims:
            cid = normalize_text(_get(claim, "claim_id", default=""))
            refs = normalize_string_list(_list(_get(claim, "evidence_ids", default=[])))
            if not refs:
                out.append(PromptDiagnostic(DiagnosticCode.CLAIM_WITHOUT_EVIDENCE,
                                            f"Claim {cid or '<sin id>'} sin evidencia.", DiagnosticSeverity.HIGH))
            invalid = [ref for ref in refs if ref not in evidence_ids]
            if invalid:
                out.append(PromptDiagnostic(DiagnosticCode.ORPHAN_CLAIM,
                                            f"Claim {cid or '<sin id>'} contiene referencias inválidas.",
                                            DiagnosticSeverity.HIGH, details={"invalid_evidence_ids": invalid}))
        for finding in context.supplied_findings:
            fid = normalize_text(_get(finding, "finding_id", default=""))
            eids = normalize_string_list(_list(_get(finding, "evidence_ids", default=[])))
            cids = normalize_string_list(_list(_get(finding, "claim_ids", default=[])))
            sids = normalize_string_list(_list(_get(finding, "source_ids", default=[])))
            if not (eids or cids or sids):
                out.append(PromptDiagnostic(DiagnosticCode.FINDING_WITHOUT_SUPPORT,
                                            f"Hallazgo {fid or '<sin id>'} sin respaldo.", DiagnosticSeverity.HIGH))
            invalid = {"evidence": [x for x in eids if x not in evidence_ids],
                       "claims": [x for x in cids if x not in claim_ids],
                       "sources": [x for x in sids if x not in source_ids]}
            invalid = {k: v for k, v in invalid.items() if v}
            if invalid:
                out.append(PromptDiagnostic(DiagnosticCode.ORPHAN_FINDING,
                                            f"Hallazgo {fid or '<sin id>'} contiene referencias inválidas.",
                                            DiagnosticSeverity.HIGH, details=invalid))
        ambiguity = 0.0
        if len(context.topic.split()) < 3: ambiguity += 2
        if len(context.objective.split()) < 12: ambiguity += 2.5
        if not context.audience: ambiguity += 1
        if not context.mandatory_outputs: ambiguity += 1
        if not context.questions: ambiguity += 3
        if ambiguity >= 6:
            out.append(PromptDiagnostic(DiagnosticCode.HIGH_AMBIGUITY,
                                        "El contexto presenta alta ambigüedad.", DiagnosticSeverity.HIGH,
                                        details={"ambiguity_score": ambiguity}))
        return out

    @staticmethod
    def _duplicates(items: Sequence[Any], attr: str, code: DiagnosticCode) -> list[PromptDiagnostic]:
        counts: dict[str, int] = {}
        for item in items:
            token = _key(_get(item, attr, default=""))
            counts[token] = counts.get(token, 0) + 1
        return [PromptDiagnostic(code, f"Elemento duplicado: {token}", DiagnosticSeverity.LOW)
                for token, count in counts.items() if token and count > 1]

    def _package(self, package: PromptPackage, token_budget: Optional[int]) -> list[PromptDiagnostic]:
        out: list[PromptDiagnostic] = []
        if not package.system_prompt:
            out.append(PromptDiagnostic(DiagnosticCode.EMPTY_SYSTEM_PROMPT, "System prompt vacío.", DiagnosticSeverity.CRITICAL))
        if not package.user_prompt:
            out.append(PromptDiagnostic(DiagnosticCode.EMPTY_USER_PROMPT, "User prompt vacío.", DiagnosticSeverity.CRITICAL))
        if not package.output_contract:
            out.append(PromptDiagnostic(DiagnosticCode.MISSING_OUTPUT_CONTRACT, "Contrato de salida ausente.", DiagnosticSeverity.HIGH))
        titles: dict[str, int] = {}
        for section in package.sections:
            token = _key(section.title)
            titles[token] = titles.get(token, 0) + 1
        for token, count in titles.items():
            if count > 1:
                out.append(PromptDiagnostic(DiagnosticCode.DUPLICATE_SECTION,
                                            f"Sección repetida {count} veces: {token}.", DiagnosticSeverity.LOW))
        estimate = _tokens(package.system_prompt + package.developer_prompt + package.user_prompt)
        if token_budget is not None and estimate > token_budget:
            out.append(PromptDiagnostic(DiagnosticCode.TOKEN_BUDGET_EXCEEDED,
                                        f"Estimación de {estimate} tokens supera {token_budget}.", DiagnosticSeverity.HIGH))
        corpus = (package.system_prompt + package.developer_prompt + package.user_prompt).casefold()
        conflicts = (("únicamente un objeto json", "informe markdown"),
                     ("no agregues texto fuera", "después un resumen markdown"))
        for left, right in conflicts:
            if left in corpus and right in corpus:
                out.append(PromptDiagnostic(DiagnosticCode.CONTRADICTORY_INSTRUCTIONS,
                                            f"Conflicto entre '{left}' y '{right}'.", DiagnosticSeverity.HIGH))
        return out


class PromptScorer:
    def __init__(self, *, input_cost_per_million_tokens: float = 0.0) -> None:
        self.rate = max(0.0, float(input_cost_per_million_tokens))
        self.diagnostics = PromptDiagnostics()

    def score(self, *, context: PromptBuildContext, package: PromptPackage,
              token_budget: Optional[int] = None) -> PromptScore:
        diagnostics = self.diagnostics.analyze(context=context, package=package, token_budget=token_budget)
        metrics = self.calculate_metrics(context, package, diagnostics)
        overall = _clamp(
            metrics.clarity_score * .18 + metrics.coverage_score * .18 +
            metrics.completeness_score * .18 + metrics.traceability_score * .20 +
            (10 - metrics.ambiguity_score) * .10 + metrics.optimization_score * .08 +
            (10 - metrics.complexity_score) * .08 -
            sum(2.5 if x.severity is DiagnosticSeverity.CRITICAL else .6 if x.severity is DiagnosticSeverity.HIGH else 0 for x in diagnostics)
        )
        metrics.quality_score = overall
        recommendation = (
            "No ejecutar todavía; resuelve diagnósticos bloqueantes." if any(x.blocking for x in diagnostics) else
            "Prompt listo para ejecución profesional." if overall >= 9 else
            "Prompt apto; revisa diagnósticos medios." if overall >= 7.5 else
            "Prompt utilizable con revisión previa." if overall >= 6 else
            "Prompt insuficiente; requiere corrección."
        )
        return PromptScore(overall, recommendation, metrics, diagnostics)

    def calculate_metrics(self, context: PromptBuildContext, package: PromptPackage,
                          diagnostics: Sequence[PromptDiagnostic]) -> PromptMetrics:
        text = package.system_prompt + package.developer_prompt + package.user_prompt
        token_estimate = _tokens(text)
        coverage = _clamp((1 if context.topic else 0) + (1.5 if context.objective else 0) +
                          min(3, len(context.questions) * .6) + min(1, len(context.constraints) * .25) +
                          (.7 if context.audience else 0) + (.8 if context.mandatory_outputs else 0) +
                          (.5 if context.additional_context else 0))
        clarity = _clamp(5 + (.8 if len(context.topic.split()) >= 3 else 0) +
                         (1.2 if len(context.objective.split()) >= 18 else 0) +
                         (1 if package.output_contract else 0) + (.6 if package.sections else 0) +
                         (.7 if context.mandatory_outputs else 0))
        complete = _clamp(sum([bool(context.project_id), bool(context.topic), bool(context.objective),
                               bool(context.questions), bool(package.system_prompt), bool(package.user_prompt),
                               bool(package.output_contract), bool(package.metadata)]) / 8 * 10)
        source_ids = {normalize_text(_get(x, "source_id", default="")) for x in context.supplied_sources}
        evidence_ids = {normalize_text(_get(x, "evidence_id", default="")) for x in context.supplied_evidence}
        total_links = valid_links = 0
        for ev in context.supplied_evidence:
            sid = normalize_text(_get(ev, "source_id", default=""))
            if sid:
                total_links += 1; valid_links += int(sid in source_ids)
        for claim in context.supplied_claims:
            for eid in normalize_string_list(_list(_get(claim, "evidence_ids", default=[]))):
                total_links += 1; valid_links += int(eid in evidence_ids)
        traceability = 7.0 if not (context.supplied_claims or context.supplied_evidence) else (2.0 if total_links == 0 else _clamp(valid_links / total_links * 10))
        ambiguity = _clamp((2 if len(context.topic.split()) < 3 else 0) +
                           (2.5 if len(context.objective.split()) < 12 else 0) +
                           (1 if not context.audience else 0) +
                           (1 if not context.mandatory_outputs else 0) +
                           (3 if not context.questions else 0))
        complexity = _clamp(min(7, token_estimate / 2500) + min(2, len(package.sections) / 15) + 1)
        saved_percent = float(package.metadata.get("optimization", {}).get("saved_percent", 0.0))
        duplicate_count = sum(1 for x in diagnostics if x.code in {DiagnosticCode.DUPLICATE_SECTION, DiagnosticCode.DUPLICATE_QUESTION, DiagnosticCode.DUPLICATE_CONSTRAINT, DiagnosticCode.DUPLICATE_SOURCE})
        optimization = _clamp(7 + min(2, saved_percent / 10) - duplicate_count * .8)
        return PromptMetrics(
            total_characters=len(text), token_estimate=token_estimate, section_count=len(package.sections),
            objective_count=max(1, len(context.objectives)), question_count=len(context.questions),
            constraint_count=len(context.constraints), source_count=len(context.supplied_sources),
            evidence_count=len(context.supplied_evidence), claim_count=len(context.supplied_claims),
            finding_count=len(context.supplied_findings), diagnostic_count=len(diagnostics),
            blocking_diagnostic_count=sum(1 for x in diagnostics if x.blocking),
            coverage_score=coverage, clarity_score=clarity, completeness_score=complete,
            traceability_score=traceability, ambiguity_score=ambiguity,
            complexity_score=complexity, optimization_score=optimization,
            estimated_runtime_seconds=round(2 + token_estimate / 35, 2) if token_estimate else 0,
            estimated_input_cost=round(token_estimate / 1_000_000 * self.rate, 8),
            metadata={"generated_at": utc_now_iso(), "input_cost_rate": self.rate},
        )


