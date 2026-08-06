"""Fachada de compatibilidad pública.

Uso recomendado:
    from research_director_prompt_builder import AdvancedResearchPromptEngine
o:
    from research_prompt import AdvancedResearchPromptEngine
"""
from research_prompt import *  # noqa: F401,F403
from research_prompt import __all__, __version__
