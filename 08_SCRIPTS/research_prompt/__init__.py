"""API pública estable del CIPS Research Prompt Builder."""
from .common import (
    DEFAULT_PROMPT_LANGUAGE,
    DEFAULT_SCHEMA_VERSION,
    PromptAudience,
    PromptOutputMode,
    PromptSectionKind,
    PromptStrictness,
    ResearchPromptBuilderError,
    ResearchPromptContractError,
    ResearchPromptSerializationError,
    ResearchPromptValidationError,
    normalize_string_list,
    normalize_text,
    safe_json_dumps,
    stable_hash,
)
from .models import PromptBuildContext, PromptPackage, PromptSection
from .templates import ResearchPromptTemplates
from .contracts import ResearchPromptContract, ResearchPromptValidator
from .builder import (
    ResearchDirectorPromptBuilder,
    ResearchMethodSelector,
    ResearchPromptProfile,
)
from .audit import AuditEventType, PromptAuditEvent, PromptAuditTrail
from .normalization import (
    ConstraintResolver,
    ContextNormalizer,
    ResearchObjectiveOptimizer,
    ResearchQuestionExpander,
)
from .optimization import PromptOptimizer
from .diagnostics import (
    DiagnosticCode,
    DiagnosticSeverity,
    PromptDiagnostic,
    PromptDiagnostics,
    PromptMetrics,
    PromptScore,
    PromptScorer,
)
from .exporters import PromptExportProvider, PromptExporter
from .engine import (
    AdvancedPromptResult,
    AdvancedResearchPromptEngine,
    ResearchPromptAssembler,
)

__version__ = "1.0.0-refactor"

__all__ = [name for name in globals() if not name.startswith("_")]
