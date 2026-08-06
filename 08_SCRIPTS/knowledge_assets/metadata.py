"""
===============================================================================
CIPS - Consejo de Inteligencia para Producción de Soluciones
Knowledge Assets Domain
-------------------------------------------------------------------------------

Archivo:
    metadata.py

Descripción:
    Objetos de valor que contienen los metadatos de un Knowledge Asset.

Estos objetos NO contienen lógica de negocio.
Únicamente representan información estructurada reutilizable.

===============================================================================
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict
from typing import List
from typing import Optional

from .base import ValueObject
from .base import utc_now


# =============================================================================
# AUTHOR
# =============================================================================

@dataclass(slots=True)
class AuthorMetadata(ValueObject):
    """
    Información del autor del activo.
    """

    name: str = ""

    organization: str = ""

    role: str = ""

    email: Optional[str] = None

    website: Optional[str] = None


# =============================================================================
# VERSION
# =============================================================================

@dataclass(slots=True)
class VersionMetadata(ValueObject):
    """
    Control de versiones.
    """

    version: str = "1.0.0"

    revision: int = 1

    change_log: List[str] = field(default_factory=list)


# =============================================================================
# SEO
# =============================================================================

@dataclass(slots=True)
class SEOMetadata(ValueObject):
    """
    Información SEO.
    """

    title: str = ""

    description: str = ""

    keywords: List[str] = field(default_factory=list)

    canonical_url: Optional[str] = None

    slug: Optional[str] = None


# =============================================================================
# TAGS
# =============================================================================

@dataclass(slots=True)
class TagMetadata(ValueObject):
    """
    Clasificación rápida.
    """

    tags: List[str] = field(default_factory=list)

    categories: List[str] = field(default_factory=list)

    labels: List[str] = field(default_factory=list)


# =============================================================================
# STATISTICS
# =============================================================================

@dataclass(slots=True)
class StatisticsMetadata(ValueObject):
    """
    Métricas calculadas.
    """

    word_count: int = 0

    reading_minutes: float = 0.0

    estimated_video_minutes: float = 0.0

    complexity_score: float = 0.0

    quality_score: float = 0.0


# =============================================================================
# AUDIENCE
# =============================================================================

@dataclass(slots=True)
class AudienceMetadata(ValueObject):
    """
    Público objetivo.
    """

    personas: List[str] = field(default_factory=list)

    industries: List[str] = field(default_factory=list)

    countries: List[str] = field(default_factory=list)

    languages: List[str] = field(default_factory=lambda: ["es"])


# =============================================================================
# SOURCE TRACEABILITY
# =============================================================================

@dataclass(slots=True)
class TraceabilityMetadata(ValueObject):
    """
    Permite conocer de dónde nació el activo.
    """

    research_package_id: Optional[str] = None

    strategy_package_id: Optional[str] = None

    content_plan_id: Optional[str] = None

    planning_session_id: Optional[str] = None

    created_by: str = "CIPS"

    created_at: str = field(default_factory=lambda: utc_now().isoformat())


# =============================================================================
# CUSTOM
# =============================================================================

@dataclass(slots=True)
class CustomMetadata(ValueObject):
    """
    Información libre.
    """

    values: Dict[str, str] = field(default_factory=dict)


# =============================================================================
# ROOT METADATA
# =============================================================================

@dataclass(slots=True)
class KnowledgeMetadata(ValueObject):
    """
    Metadatos completos de un Knowledge Asset.
    """

    author: AuthorMetadata = field(default_factory=AuthorMetadata)

    version: VersionMetadata = field(default_factory=VersionMetadata)

    seo: SEOMetadata = field(default_factory=SEOMetadata)

    tags: TagMetadata = field(default_factory=TagMetadata)

    statistics: StatisticsMetadata = field(default_factory=StatisticsMetadata)

    audience: AudienceMetadata = field(default_factory=AudienceMetadata)

    traceability: TraceabilityMetadata = field(default_factory=TraceabilityMetadata)

    custom: CustomMetadata = field(default_factory=CustomMetadata)