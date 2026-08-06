"""
===============================================================================
CIPS - Consejo de Inteligencia para Producción de Soluciones
Knowledge Assets Domain
-------------------------------------------------------------------------------

Archivo:
    enums.py

Descripción:
    Contrato semántico del dominio Knowledge Assets.

    Este archivo centraliza todas las enumeraciones utilizadas por el
    dominio de conocimiento de CIPS.

IMPORTANTE

    • Este archivo NO debe importar módulos internos.
    • Todos los demás módulos deberán importar desde aquí.
    • Evita dependencias circulares.
    • Mantiene un vocabulario uniforme en todo el proyecto.

Arquitectura

    Research Director
            │
            ▼
    Strategy Director
            │
            ▼
    Content Planning
            │
            ▼
    Knowledge Assets
            │
            ▼
    Image Director
    Video Director
    Voice Director
    Publisher Director
    Analytics Director

Versión:
    1.0.0

===============================================================================
"""

from __future__ import annotations

from enum import Enum


# =============================================================================
# BASE ENUM
# =============================================================================

class StringEnum(str, Enum):
    """
    Clase base para todas las enumeraciones del dominio.

    Proporciona una representación uniforme,
    facilita la serialización JSON
    y agrega métodos de utilidad comunes.
    """

    def __str__(self) -> str:
        return self.value

    @classmethod
    def values(cls):
        """Devuelve únicamente los valores."""
        return [item.value for item in cls]

    @classmethod
    def names(cls):
        """Devuelve únicamente los nombres."""
        return [item.name for item in cls]

    @classmethod
    def has_value(cls, value: str) -> bool:
        """Indica si el valor pertenece al Enum."""
        return value in cls.values()


# =============================================================================
# KNOWLEDGE
# =============================================================================

class KnowledgeType(StringEnum):
    """
    Tipo principal de conocimiento.
    """

    CONCEPT = "concept"

    PROCESS = "process"

    METHOD = "method"

    FRAMEWORK = "framework"

    PROCEDURE = "procedure"

    TEMPLATE = "template"

    CHECKLIST = "checklist"

    STRATEGY = "strategy"

    PRINCIPLE = "principle"

    THEORY = "theory"

    GUIDE = "guide"

    DOCUMENT = "document"

    FAQ = "faq"

    STORY = "story"

    LESSON = "lesson"

    CASE_STUDY = "case_study"

    COMPARISON = "comparison"

    BEST_PRACTICE = "best_practice"

    WORKFLOW = "workflow"

    DECISION_TREE = "decision_tree"


class KnowledgeStatus(StringEnum):
    """
    Estado del activo.
    """

    DRAFT = "draft"

    REVIEW = "review"

    VALIDATED = "validated"

    APPROVED = "approved"

    PUBLISHED = "published"

    ARCHIVED = "archived"


class KnowledgeLifecycle(StringEnum):
    """
    Ciclo de vida.
    """

    CREATED = "created"

    CURATED = "curated"

    ENRICHED = "enriched"

    REUSED = "reused"

    UPDATED = "updated"

    DEPRECATED = "deprecated"


class KnowledgeScope(StringEnum):
    """
    Alcance del conocimiento.
    """

    LOCAL = "local"

    PROJECT = "project"

    ORGANIZATION = "organization"

    GLOBAL = "global"


class KnowledgeComplexity(StringEnum):
    """
    Complejidad técnica.
    """

    BASIC = "basic"

    INTERMEDIATE = "intermediate"

    ADVANCED = "advanced"

    EXPERT = "expert"


class KnowledgeFreshness(StringEnum):
    """
    Vigencia del conocimiento.
    """

    EVERGREEN = "evergreen"

    SEASONAL = "seasonal"

    TRENDING = "trending"

    TIME_SENSITIVE = "time_sensitive"

    OBSOLETE = "obsolete"


class KnowledgeConfidence(StringEnum):
    """
    Nivel de confianza.
    """

    LOW = "low"

    MEDIUM = "medium"

    HIGH = "high"

    VERIFIED = "verified"


# =============================================================================
# AUDIENCE
# =============================================================================

class AudienceLevel(StringEnum):
    """
    Nivel de experiencia del público.
    """

    BEGINNER = "beginner"

    INTERMEDIATE = "intermediate"

    ADVANCED = "advanced"

    EXPERT = "expert"


class BuyerJourney(StringEnum):
    """
    Etapa del embudo.
    """

    AWARENESS = "awareness"

    INTEREST = "interest"

    CONSIDERATION = "consideration"

    DECISION = "decision"

    RETENTION = "retention"

    ADVOCACY = "advocacy"


class PainPointLevel(StringEnum):
    """
    Intensidad del problema.
    """

    LOW = "low"

    MEDIUM = "medium"

    HIGH = "high"

    CRITICAL = "critical"


# =============================================================================
# CONTENT
# =============================================================================

class ContentIntent(StringEnum):
    """
    Objetivo del contenido.
    """

    EDUCATE = "educate"

    INFORM = "inform"

    ENTERTAIN = "entertain"

    INSPIRE = "inspire"

    ENGAGE = "engage"

    CONVERT = "convert"

    SELL = "sell"

    RETAIN = "retain"


class ContentFormat(StringEnum):
    """
    Formato recomendado.
    """

    ARTICLE = "article"

    BLOG = "blog"

    VIDEO = "video"

    SHORT = "short"

    REEL = "reel"

    TIKTOK = "tiktok"

    PODCAST = "podcast"

    NEWSLETTER = "newsletter"

    EMAIL = "email"

    EBOOK = "ebook"

    WEBINAR = "webinar"

    COURSE = "course"

    INFOGRAPHIC = "infographic"

    CAROUSEL = "carousel"

    THREAD = "thread"

    LIVESTREAM = "livestream"


class ContentChannel(StringEnum):
    """
    Canal de distribución.
    """

    WEBSITE = "website"

    YOUTUBE = "youtube"

    FACEBOOK = "facebook"

    INSTAGRAM = "instagram"

    TIKTOK = "tiktok"

    LINKEDIN = "linkedin"

    X = "x"

    EMAIL = "email"

    WHATSAPP = "whatsapp"

    TELEGRAM = "telegram"
    # =============================================================================
# RESEARCH & VALIDATION
# =============================================================================

class EvidenceLevel(StringEnum):
    """
    Nivel de evidencia que respalda un Knowledge Asset.
    """

    LOW = "low"

    MEDIUM = "medium"

    HIGH = "high"

    VERIFIED = "verified"

    SCIENTIFIC = "scientific"


class SourceType(StringEnum):
    """
    Origen de la información.
    """

    RESEARCH = "research"

    BOOK = "book"

    SCIENTIFIC_PAPER = "scientific_paper"

    STANDARD = "standard"

    GOVERNMENT = "government"

    INTERVIEW = "interview"

    USER = "user"

    EXPERT = "expert"

    AI_GENERATED = "ai_generated"

    INTERNAL = "internal"


class SourceReliability(StringEnum):
    """
    Nivel de confiabilidad de la fuente.
    """

    UNKNOWN = "unknown"

    LOW = "low"

    MEDIUM = "medium"

    HIGH = "high"

    VERIFIED = "verified"


class ValidationStatus(StringEnum):
    """
    Resultado del proceso de validación.
    """

    PENDING = "pending"

    VALID = "valid"

    INVALID = "invalid"

    WARNING = "warning"

    ERROR = "error"


# =============================================================================
# KNOWLEDGE GRAPH
# =============================================================================

class RelationshipType(StringEnum):
    """
    Tipo de relación entre dos Knowledge Assets.
    """

    RELATED_TO = "related_to"

    DEPENDS_ON = "depends_on"

    EXPANDS = "expands"

    SUMMARIZES = "summarizes"

    SUPPORTS = "supports"

    CONTRADICTS = "contradicts"

    REFERENCES = "references"

    CHILD_OF = "child_of"

    PARENT_OF = "parent_of"

    PREVIOUS = "previous"

    NEXT = "next"

    ALTERNATIVE_TO = "alternative_to"

    REQUIRES = "requires"

    SIMILAR_TO = "similar_to"


class GraphNodeType(StringEnum):
    """
    Tipo de nodo del grafo.
    """

    KNOWLEDGE = "knowledge"

    TOPIC = "topic"

    CATEGORY = "category"

    AUDIENCE = "audience"

    CONTENT = "content"

    STRATEGY = "strategy"

    RESEARCH = "research"


class GraphEdgeType(StringEnum):
    """
    Tipo de conexión del Knowledge Graph.
    """

    DIRECTED = "directed"

    UNDIRECTED = "undirected"

    WEIGHTED = "weighted"

    HIERARCHICAL = "hierarchical"


# =============================================================================
# PRIORITY
# =============================================================================

class Priority(StringEnum):
    """
    Prioridad de ejecución.
    """

    LOW = "low"

    NORMAL = "normal"

    HIGH = "high"

    CRITICAL = "critical"


class RiskLevel(StringEnum):
    """
    Riesgo asociado al activo.
    """

    LOW = "low"

    MEDIUM = "medium"

    HIGH = "high"

    CRITICAL = "critical"


class DifficultyLevel(StringEnum):
    """
    Dificultad de comprensión.
    """

    VERY_EASY = "very_easy"

    EASY = "easy"

    INTERMEDIATE = "intermediate"

    ADVANCED = "advanced"

    EXPERT = "expert"


# =============================================================================
# PUBLICATION
# =============================================================================

class PublicationState(StringEnum):
    """
    Estado de publicación.
    """

    NOT_SCHEDULED = "not_scheduled"

    SCHEDULED = "scheduled"

    PUBLISHED = "published"

    PAUSED = "paused"

    ARCHIVED = "archived"


class Visibility(StringEnum):
    """
    Visibilidad del activo.
    """

    PRIVATE = "private"

    INTERNAL = "internal"

    PUBLIC = "public"


class LanguageCode(StringEnum):
    """
    Idiomas soportados inicialmente.
    """

    ES = "es"

    EN = "en"

    PT = "pt"

    FR = "fr"

    DE = "de"

    IT = "it"


# =============================================================================
# KNOWLEDGE ASSET
# =============================================================================

class AssetPriority(StringEnum):
    """
    Prioridad estratégica del activo.
    """

    LOW = "low"

    NORMAL = "normal"

    HIGH = "high"

    CRITICAL = "critical"


class AssetVisibility(StringEnum):
    """
    Nivel de acceso al activo.
    """

    PRIVATE = "private"

    TEAM = "team"

    ORGANIZATION = "organization"

    PUBLIC = "public"


class AssetState(StringEnum):
    """
    Estado interno del Knowledge Asset.
    """

    CREATED = "created"

    CURATED = "curated"

    REVIEWED = "reviewed"

    APPROVED = "approved"

    PUBLISHED = "published"

    RETIRED = "retired"