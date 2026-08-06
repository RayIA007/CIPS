"""
Fachada de compatibilidad de CIPS.

Este archivo reemplaza al futuro archivo monolítico. Mantiene el nombre
histórico de importación, pero delega toda la funcionalidad al paquete
research_prompt.
"""

from research_prompt import (
    AdvancedPromptResult,
    AdvancedResearchPromptEngine,
    PromptBuildContext,
    PromptExportProvider,
    PromptPackage,
    ResearchDirectorPromptBuilder,
    ResearchPromptFacade,
)

__all__ = [
    "AdvancedPromptResult",
    "AdvancedResearchPromptEngine",
    "PromptBuildContext",
    "PromptExportProvider",
    "PromptPackage",
    "ResearchDirectorPromptBuilder",
    "ResearchPromptFacade",
]
