"""
===============================================================================
CIPS - Consejo de Inteligencia para Producción de Soluciones
Knowledge Assets Domain
-------------------------------------------------------------------------------

Archivo:
    references.py

Descripción:
    Define los objetos de valor utilizados para registrar fuentes, citas,
    evidencias y referencias externas asociadas con un Knowledge Asset.

Objetivos:
    - Mantener trazabilidad verificable del conocimiento.
    - Diferenciar fuente, cita y evidencia.
    - Evitar referencias duplicadas.
    - Facilitar serialización y reconstrucción desde JSON.
    - Preparar el dominio para validación, auditoría y cálculo de confianza.

Versión:
    1.0.0
===============================================================================
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Dict, Iterable, List, Mapping, Optional
from urllib.parse import urlparse

from .base import (
    JSONDict,
    ValidationErrors,
    ValueObject,
    deserialize_enum,
    generate_identifier,
    parse_datetime,
    require_non_empty_string,
    utc_now,
)
from .enums import (
    EvidenceLevel,
    SourceReliability,
    SourceType,
    ValidationStatus,
)


# =============================================================================
# CONSTANTS
# =============================================================================

DEFAULT_REFERENCE_PREFIX: str = "ref"
DEFAULT_CITATION_PREFIX: str = "cit"
DEFAULT_EVIDENCE_PREFIX: str = "evd"

MIN_CONFIDENCE_SCORE: float = 0.0
MAX_CONFIDENCE_SCORE: float = 1.0


# =============================================================================
# INTERNAL UTILITIES
# =============================================================================

def _normalize_optional_string(value: Optional[str]) -> Optional[str]:
    """
    Normaliza una cadena opcional.

    Devuelve ``None`` cuando el valor es nulo o queda vacío después de quitar
    espacios laterales.
    """
    if value is None:
        return None

    if not isinstance(value, str):
        raise TypeError(
            "Se esperaba str o None; "
            f"se recibió {type(value).__name__}."
        )

    normalized = value.strip()

    return normalized or None


def _normalize_string_list(values: Iterable[str]) -> List[str]:
    """
    Normaliza una colección de cadenas y elimina duplicados conservando orden.
    """
    normalized: List[str] = []
    seen = set()

    for value in values:
        if not isinstance(value, str):
            raise TypeError(
                "Todos los elementos deben ser str; "
                f"se recibió {type(value).__name__}."
            )

        item = value.strip()

        if item and item.casefold() not in seen:
            normalized.append(item)
            seen.add(item.casefold())

    return normalized


def _normalize_date(value: Any) -> Optional[date]:
    """
    Convierte un valor compatible a ``date``.

    Valores aceptados:
        - None
        - date
        - datetime
        - cadena ISO 8601
    """
    if value is None:
        return None

    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    if isinstance(value, str):
        normalized = value.strip()

        if not normalized:
            return None

        try:
            return date.fromisoformat(normalized)
        except ValueError:
            return parse_datetime(normalized).date()

    raise TypeError(
        "Se esperaba date, datetime, str ISO 8601 o None; "
        f"se recibió {type(value).__name__}."
    )


def _is_valid_url(value: str) -> bool:
    """
    Comprueba si una cadena contiene una URL HTTP o HTTPS válida.
    """
    parsed = urlparse(value)

    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _normalize_confidence_score(value: float) -> float:
    """
    Normaliza y valida una puntuación de confianza entre 0.0 y 1.0.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(
            "confidence_score debe ser int o float."
        )

    normalized = float(value)

    if not MIN_CONFIDENCE_SCORE <= normalized <= MAX_CONFIDENCE_SCORE:
        raise ValueError(
            "confidence_score debe estar entre "
            f"{MIN_CONFIDENCE_SCORE} y {MAX_CONFIDENCE_SCORE}."
        )

    return normalized


# =============================================================================
# SOURCE LOCATION
# =============================================================================

@dataclass
class SourceLocation(ValueObject):
    """
    Ubicación precisa dentro de una fuente.

    Permite señalar página, capítulo, sección, párrafo, marca temporal o rango
    de líneas sin depender del formato original del documento.
    """

    page: Optional[int] = None
    page_end: Optional[int] = None
    chapter: Optional[str] = None
    section: Optional[str] = None
    paragraph: Optional[str] = None
    line_start: Optional[int] = None
    line_end: Optional[int] = None
    timestamp_start: Optional[str] = None
    timestamp_end: Optional[str] = None
    locator: Optional[str] = None

    def __post_init__(self) -> None:
        self.chapter = _normalize_optional_string(self.chapter)
        self.section = _normalize_optional_string(self.section)
        self.paragraph = _normalize_optional_string(self.paragraph)
        self.timestamp_start = _normalize_optional_string(self.timestamp_start)
        self.timestamp_end = _normalize_optional_string(self.timestamp_end)
        self.locator = _normalize_optional_string(self.locator)

    def validation_errors(self) -> ValidationErrors:
        errors: ValidationErrors = []

        for name in ("page", "page_end", "line_start", "line_end"):
            value = getattr(self, name)

            if value is not None:
                if isinstance(value, bool) or not isinstance(value, int):
                    errors.append(f"{name} debe ser int o None.")
                elif value < 1:
                    errors.append(f"{name} debe ser mayor o igual que 1.")

        if (
            self.page is not None
            and self.page_end is not None
            and self.page_end < self.page
        ):
            errors.append("page_end no puede ser menor que page.")

        if (
            self.line_start is not None
            and self.line_end is not None
            and self.line_end < self.line_start
        ):
            errors.append("line_end no puede ser menor que line_start.")

        return errors

    def is_empty(self) -> bool:
        """
        Indica si no se ha definido ninguna ubicación.
        """
        return not any(
            (
                self.page,
                self.page_end,
                self.chapter,
                self.section,
                self.paragraph,
                self.line_start,
                self.line_end,
                self.timestamp_start,
                self.timestamp_end,
                self.locator,
            )
        )

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "SourceLocation":
        if not isinstance(data, Mapping):
            raise TypeError("SourceLocation.from_dict esperaba Mapping.")

        return cls(**dict(data))


# =============================================================================
# SOURCE REFERENCE
# =============================================================================

@dataclass
class SourceReference(ValueObject):
    """
    Representa una fuente documental, humana, institucional o digital.

    Una fuente puede existir sin una cita textual. Su propósito es registrar
    el origen general de una afirmación o activo de conocimiento.
    """

    id: str = field(
        default_factory=lambda: generate_identifier(DEFAULT_REFERENCE_PREFIX)
    )
    source_type: SourceType = SourceType.RESEARCH
    reliability: SourceReliability = SourceReliability.UNKNOWN
    validation_status: ValidationStatus = ValidationStatus.PENDING

    title: str = ""
    authors: List[str] = field(default_factory=list)
    organization: Optional[str] = None
    publisher: Optional[str] = None

    publication_date: Optional[date] = None
    accessed_at: Optional[datetime] = None

    url: Optional[str] = None
    doi: Optional[str] = None
    isbn: Optional[str] = None

    language: Optional[str] = None
    edition: Optional[str] = None
    volume: Optional[str] = None
    issue: Optional[str] = None

    location: SourceLocation = field(default_factory=SourceLocation)
    notes: Optional[str] = None
    tags: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.id = require_non_empty_string(self.id, "id")
        self.title = require_non_empty_string(self.title, "title")

        self.source_type = deserialize_enum(SourceType, self.source_type)
        self.reliability = deserialize_enum(
            SourceReliability,
            self.reliability,
        )
        self.validation_status = deserialize_enum(
            ValidationStatus,
            self.validation_status,
        )

        self.authors = _normalize_string_list(self.authors)
        self.tags = _normalize_string_list(self.tags)

        self.organization = _normalize_optional_string(self.organization)
        self.publisher = _normalize_optional_string(self.publisher)
        self.url = _normalize_optional_string(self.url)
        self.doi = _normalize_optional_string(self.doi)
        self.isbn = _normalize_optional_string(self.isbn)
        self.language = _normalize_optional_string(self.language)
        self.edition = _normalize_optional_string(self.edition)
        self.volume = _normalize_optional_string(self.volume)
        self.issue = _normalize_optional_string(self.issue)
        self.notes = _normalize_optional_string(self.notes)

        self.publication_date = _normalize_date(self.publication_date)

        if self.accessed_at is not None:
            self.accessed_at = parse_datetime(self.accessed_at)

        if isinstance(self.location, Mapping):
            self.location = SourceLocation.from_dict(self.location)
        elif not isinstance(self.location, SourceLocation):
            raise TypeError(
                "location debe ser SourceLocation o Mapping."
            )

    def validation_errors(self) -> ValidationErrors:
        errors = super().validation_errors()

        if not self.title:
            errors.append("title es obligatorio.")

        if self.url is not None and not _is_valid_url(self.url):
            errors.append("url debe usar el esquema http o https.")

        errors.extend(
            f"location.{error}"
            for error in self.location.validation_errors()
        )

        return errors

    def canonical_key(self) -> str:
        """
        Devuelve una clave estable para detectar fuentes duplicadas.
        """
        if self.doi:
            return f"doi:{self.doi.casefold()}"

        if self.isbn:
            return f"isbn:{self.isbn.casefold()}"

        if self.url:
            return f"url:{self.url.rstrip('/').casefold()}"

        author_key = "|".join(author.casefold() for author in self.authors)
        date_key = (
            self.publication_date.isoformat()
            if self.publication_date
            else ""
        )

        return (
            f"title:{self.title.casefold()}|"
            f"authors:{author_key}|"
            f"date:{date_key}"
        )

    def is_verified(self) -> bool:
        """
        Indica si la fuente fue validada y tiene confiabilidad alta.
        """
        return (
            self.validation_status == ValidationStatus.VALID
            and self.reliability
            in {
                SourceReliability.HIGH,
                SourceReliability.VERIFIED,
            }
        )

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "SourceReference":
        if not isinstance(data, Mapping):
            raise TypeError("SourceReference.from_dict esperaba Mapping.")

        normalized = dict(data)

        if "source_type" in normalized:
            normalized["source_type"] = deserialize_enum(
                SourceType,
                normalized["source_type"],
            )

        if "reliability" in normalized:
            normalized["reliability"] = deserialize_enum(
                SourceReliability,
                normalized["reliability"],
            )

        if "validation_status" in normalized:
            normalized["validation_status"] = deserialize_enum(
                ValidationStatus,
                normalized["validation_status"],
            )

        if "publication_date" in normalized:
            normalized["publication_date"] = _normalize_date(
                normalized["publication_date"]
            )

        if (
            normalized.get("accessed_at") is not None
            and not isinstance(normalized["accessed_at"], datetime)
        ):
            normalized["accessed_at"] = parse_datetime(
                normalized["accessed_at"]
            )

        if isinstance(normalized.get("location"), Mapping):
            normalized["location"] = SourceLocation.from_dict(
                normalized["location"]
            )

        return cls(**normalized)


# =============================================================================
# CITATION
# =============================================================================

@dataclass
class Citation(ValueObject):
    """
    Registra una cita vinculada con una fuente.

    ``quoted_text`` puede contener una cita textual breve. ``paraphrase``
    permite registrar la interpretación utilizada por CIPS sin confundirla
    con el texto original.
    """

    id: str = field(
        default_factory=lambda: generate_identifier(DEFAULT_CITATION_PREFIX)
    )
    source_id: str = ""

    quoted_text: Optional[str] = None
    paraphrase: Optional[str] = None
    context: Optional[str] = None

    location: SourceLocation = field(default_factory=SourceLocation)
    citation_style: Optional[str] = None
    formatted_citation: Optional[str] = None

    verified: bool = False
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.id = require_non_empty_string(self.id, "id")
        self.source_id = require_non_empty_string(
            self.source_id,
            "source_id",
        )

        self.quoted_text = _normalize_optional_string(self.quoted_text)
        self.paraphrase = _normalize_optional_string(self.paraphrase)
        self.context = _normalize_optional_string(self.context)
        self.citation_style = _normalize_optional_string(
            self.citation_style
        )
        self.formatted_citation = _normalize_optional_string(
            self.formatted_citation
        )

        self.created_at = parse_datetime(self.created_at)

        if isinstance(self.location, Mapping):
            self.location = SourceLocation.from_dict(self.location)
        elif not isinstance(self.location, SourceLocation):
            raise TypeError(
                "location debe ser SourceLocation o Mapping."
            )

        if not isinstance(self.verified, bool):
            raise TypeError("verified debe ser bool.")

    def validation_errors(self) -> ValidationErrors:
        errors = super().validation_errors()

        if not self.source_id:
            errors.append("source_id es obligatorio.")

        if not self.quoted_text and not self.paraphrase:
            errors.append(
                "Debe existir quoted_text o paraphrase."
            )

        errors.extend(
            f"location.{error}"
            for error in self.location.validation_errors()
        )

        return errors

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Citation":
        if not isinstance(data, Mapping):
            raise TypeError("Citation.from_dict esperaba Mapping.")

        normalized = dict(data)

        if isinstance(normalized.get("location"), Mapping):
            normalized["location"] = SourceLocation.from_dict(
                normalized["location"]
            )

        if "created_at" in normalized:
            normalized["created_at"] = parse_datetime(
                normalized["created_at"]
            )

        return cls(**normalized)


# =============================================================================
# EVIDENCE
# =============================================================================

@dataclass
class Evidence(ValueObject):
    """
    Representa evidencia que respalda o cuestiona una afirmación.

    Puede vincularse con una fuente completa, una cita concreta o ambas.
    """

    id: str = field(
        default_factory=lambda: generate_identifier(DEFAULT_EVIDENCE_PREFIX)
    )
    claim: str = ""

    evidence_level: EvidenceLevel = EvidenceLevel.LOW
    validation_status: ValidationStatus = ValidationStatus.PENDING
    confidence_score: float = 0.0

    source_ids: List[str] = field(default_factory=list)
    citation_ids: List[str] = field(default_factory=list)

    summary: Optional[str] = None
    limitations: List[str] = field(default_factory=list)
    methodology: Optional[str] = None

    supports_claim: bool = True
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        self.id = require_non_empty_string(self.id, "id")
        self.claim = require_non_empty_string(self.claim, "claim")

        self.evidence_level = deserialize_enum(
            EvidenceLevel,
            self.evidence_level,
        )
        self.validation_status = deserialize_enum(
            ValidationStatus,
            self.validation_status,
        )
        self.confidence_score = _normalize_confidence_score(
            self.confidence_score
        )

        self.source_ids = _normalize_string_list(self.source_ids)
        self.citation_ids = _normalize_string_list(self.citation_ids)
        self.limitations = _normalize_string_list(self.limitations)

        self.summary = _normalize_optional_string(self.summary)
        self.methodology = _normalize_optional_string(self.methodology)
        self.reviewed_by = _normalize_optional_string(self.reviewed_by)

        if self.reviewed_at is not None:
            self.reviewed_at = parse_datetime(self.reviewed_at)

        if not isinstance(self.supports_claim, bool):
            raise TypeError("supports_claim debe ser bool.")

    def validation_errors(self) -> ValidationErrors:
        errors = super().validation_errors()

        if not self.claim:
            errors.append("claim es obligatorio.")

        if not self.source_ids and not self.citation_ids:
            errors.append(
                "La evidencia debe vincular al menos una fuente o cita."
            )

        if self.reviewed_at is not None and not self.reviewed_by:
            errors.append(
                "reviewed_by es obligatorio cuando existe reviewed_at."
            )

        return errors

    def is_verified(self) -> bool:
        """
        Indica si la evidencia está validada y tiene confianza suficiente.
        """
        return (
            self.validation_status == ValidationStatus.VALID
            and self.confidence_score >= 0.75
            and self.evidence_level
            in {
                EvidenceLevel.HIGH,
                EvidenceLevel.VERIFIED,
                EvidenceLevel.SCIENTIFIC,
            }
        )

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Evidence":
        if not isinstance(data, Mapping):
            raise TypeError("Evidence.from_dict esperaba Mapping.")

        normalized = dict(data)

        if "evidence_level" in normalized:
            normalized["evidence_level"] = deserialize_enum(
                EvidenceLevel,
                normalized["evidence_level"],
            )

        if "validation_status" in normalized:
            normalized["validation_status"] = deserialize_enum(
                ValidationStatus,
                normalized["validation_status"],
            )

        if normalized.get("reviewed_at") is not None:
            normalized["reviewed_at"] = parse_datetime(
                normalized["reviewed_at"]
            )

        return cls(**normalized)


# =============================================================================
# REFERENCE COLLECTION
# =============================================================================

@dataclass
class ReferenceCollection(ValueObject):
    """
    Contenedor raíz de fuentes, citas y evidencias.

    Mantiene integridad referencial básica y proporciona operaciones de
    búsqueda, incorporación y eliminación.
    """

    sources: List[SourceReference] = field(default_factory=list)
    citations: List[Citation] = field(default_factory=list)
    evidence: List[Evidence] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.sources = [
            item
            if isinstance(item, SourceReference)
            else SourceReference.from_dict(item)
            for item in self.sources
        ]

        self.citations = [
            item
            if isinstance(item, Citation)
            else Citation.from_dict(item)
            for item in self.citations
        ]

        self.evidence = [
            item
            if isinstance(item, Evidence)
            else Evidence.from_dict(item)
            for item in self.evidence
        ]

    def add_source(
        self,
        source: SourceReference,
        *,
        reject_duplicate: bool = True,
    ) -> SourceReference:
        """
        Agrega una fuente y opcionalmente rechaza duplicados semánticos.
        """
        if not isinstance(source, SourceReference):
            raise TypeError("source debe ser SourceReference.")

        if self.get_source(source.id) is not None:
            raise ValueError(
                f"Ya existe una fuente con id {source.id!r}."
            )

        if reject_duplicate:
            canonical_key = source.canonical_key()

            for current in self.sources:
                if current.canonical_key() == canonical_key:
                    raise ValueError(
                        "Ya existe una fuente equivalente en la colección."
                    )

        self.sources.append(source)

        return source

    def add_citation(self, citation: Citation) -> Citation:
        """
        Agrega una cita si su fuente existe.
        """
        if not isinstance(citation, Citation):
            raise TypeError("citation debe ser Citation.")

        if self.get_citation(citation.id) is not None:
            raise ValueError(
                f"Ya existe una cita con id {citation.id!r}."
            )

        if self.get_source(citation.source_id) is None:
            raise ValueError(
                "No existe la fuente indicada por citation.source_id."
            )

        self.citations.append(citation)

        return citation

    def add_evidence(self, item: Evidence) -> Evidence:
        """
        Agrega evidencia si todas sus referencias existen.
        """
        if not isinstance(item, Evidence):
            raise TypeError("item debe ser Evidence.")

        if self.get_evidence(item.id) is not None:
            raise ValueError(
                f"Ya existe evidencia con id {item.id!r}."
            )

        missing_sources = [
            source_id
            for source_id in item.source_ids
            if self.get_source(source_id) is None
        ]
        missing_citations = [
            citation_id
            for citation_id in item.citation_ids
            if self.get_citation(citation_id) is None
        ]

        if missing_sources:
            raise ValueError(
                "Fuentes inexistentes: "
                + ", ".join(missing_sources)
            )

        if missing_citations:
            raise ValueError(
                "Citas inexistentes: "
                + ", ".join(missing_citations)
            )

        self.evidence.append(item)

        return item

    def get_source(self, source_id: str) -> Optional[SourceReference]:
        """
        Busca una fuente por identificador.
        """
        return next(
            (
                source
                for source in self.sources
                if source.id == source_id
            ),
            None,
        )

    def get_citation(self, citation_id: str) -> Optional[Citation]:
        """
        Busca una cita por identificador.
        """
        return next(
            (
                citation
                for citation in self.citations
                if citation.id == citation_id
            ),
            None,
        )

    def get_evidence(self, evidence_id: str) -> Optional[Evidence]:
        """
        Busca evidencia por identificador.
        """
        return next(
            (
                item
                for item in self.evidence
                if item.id == evidence_id
            ),
            None,
        )

    def sources_for_evidence(
        self,
        evidence_id: str,
    ) -> List[SourceReference]:
        """
        Devuelve las fuentes directas e indirectas asociadas con evidencia.
        """
        item = self.get_evidence(evidence_id)

        if item is None:
            return []

        source_ids = list(item.source_ids)

        for citation_id in item.citation_ids:
            citation = self.get_citation(citation_id)

            if citation and citation.source_id not in source_ids:
                source_ids.append(citation.source_id)

        return [
            source
            for source_id in source_ids
            if (source := self.get_source(source_id)) is not None
        ]

    def remove_source(
        self,
        source_id: str,
        *,
        cascade: bool = False,
    ) -> bool:
        """
        Elimina una fuente.

        Cuando ``cascade`` es falso, la operación se rechaza si existen citas
        o evidencias dependientes. Cuando es verdadero, elimina las citas
        asociadas y limpia las relaciones de evidencia.
        """
        source = self.get_source(source_id)

        if source is None:
            return False

        dependent_citations = [
            citation
            for citation in self.citations
            if citation.source_id == source_id
        ]
        dependent_citation_ids = {
            citation.id
            for citation in dependent_citations
        }
        direct_evidence = [
            item
            for item in self.evidence
            if (
                source_id in item.source_ids
                or any(
                    citation_id in dependent_citation_ids
                    for citation_id in item.citation_ids
                )
            )
        ]

        if (
            dependent_citations or direct_evidence
        ) and not cascade:
            raise ValueError(
                "La fuente tiene citas o evidencias dependientes."
            )

        self.sources = [
            item
            for item in self.sources
            if item.id != source_id
        ]

        if cascade:
            self.citations = [
                citation
                for citation in self.citations
                if citation.id not in dependent_citation_ids
            ]

            retained_evidence: List[Evidence] = []

            for item in self.evidence:
                item.source_ids = [
                    current_id
                    for current_id in item.source_ids
                    if current_id != source_id
                ]
                item.citation_ids = [
                    current_id
                    for current_id in item.citation_ids
                    if current_id not in dependent_citation_ids
                ]

                if item.source_ids or item.citation_ids:
                    retained_evidence.append(item)

            self.evidence = retained_evidence

        return True

    def validation_errors(self) -> ValidationErrors:
        errors = super().validation_errors()

        source_ids = [source.id for source in self.sources]
        citation_ids = [citation.id for citation in self.citations]
        evidence_ids = [item.id for item in self.evidence]

        if len(source_ids) != len(set(source_ids)):
            errors.append("Existen identificadores de fuente duplicados.")

        if len(citation_ids) != len(set(citation_ids)):
            errors.append("Existen identificadores de cita duplicados.")

        if len(evidence_ids) != len(set(evidence_ids)):
            errors.append("Existen identificadores de evidencia duplicados.")

        canonical_keys = [
            source.canonical_key()
            for source in self.sources
        ]

        if len(canonical_keys) != len(set(canonical_keys)):
            errors.append("Existen fuentes semánticamente duplicadas.")

        source_id_set = set(source_ids)
        citation_id_set = set(citation_ids)

        for source in self.sources:
            errors.extend(
                f"sources[{source.id}].{error}"
                for error in source.validation_errors()
            )

        for citation in self.citations:
            errors.extend(
                f"citations[{citation.id}].{error}"
                for error in citation.validation_errors()
            )

            if citation.source_id not in source_id_set:
                errors.append(
                    f"citations[{citation.id}].source_id no existe."
                )

        for item in self.evidence:
            errors.extend(
                f"evidence[{item.id}].{error}"
                for error in item.validation_errors()
            )

            for source_id in item.source_ids:
                if source_id not in source_id_set:
                    errors.append(
                        f"evidence[{item.id}] referencia la fuente "
                        f"inexistente {source_id!r}."
                    )

            for citation_id in item.citation_ids:
                if citation_id not in citation_id_set:
                    errors.append(
                        f"evidence[{item.id}] referencia la cita "
                        f"inexistente {citation_id!r}."
                    )

        return errors

    def summary(self) -> JSONDict:
        """
        Devuelve métricas básicas de trazabilidad.
        """
        verified_sources = sum(
            1
            for source in self.sources
            if source.is_verified()
        )
        verified_evidence = sum(
            1
            for item in self.evidence
            if item.is_verified()
        )

        return {
            "source_count": len(self.sources),
            "citation_count": len(self.citations),
            "evidence_count": len(self.evidence),
            "verified_source_count": verified_sources,
            "verified_evidence_count": verified_evidence,
        }

    @classmethod
    def from_dict(
        cls,
        data: Mapping[str, Any],
    ) -> "ReferenceCollection":
        if not isinstance(data, Mapping):
            raise TypeError(
                "ReferenceCollection.from_dict esperaba Mapping."
            )

        return cls(
            sources=[
                SourceReference.from_dict(item)
                for item in data.get("sources", [])
            ],
            citations=[
                Citation.from_dict(item)
                for item in data.get("citations", [])
            ],
            evidence=[
                Evidence.from_dict(item)
                for item in data.get("evidence", [])
            ],
        )


# =============================================================================
# PUBLIC EXPORTS
# =============================================================================

__all__ = [
    "Citation",
    "DEFAULT_CITATION_PREFIX",
    "DEFAULT_EVIDENCE_PREFIX",
    "DEFAULT_REFERENCE_PREFIX",
    "Evidence",
    "MAX_CONFIDENCE_SCORE",
    "MIN_CONFIDENCE_SCORE",
    "ReferenceCollection",
    "SourceLocation",
    "SourceReference",
]