"""
===============================================================================
CIPS - Consejo de Inteligencia para Producción de Soluciones
Knowledge Assets Domain
-------------------------------------------------------------------------------

Archivo:
    models.py

Descripción:
    Modelos principales del dominio Knowledge Assets.

    Este módulo representa el núcleo de la librería y define las entidades
    que administran conocimiento estructurado dentro del ecosistema CIPS.

Objetivos:

    • Representar activos de conocimiento.
    • Administrar colecciones.
    • Facilitar búsquedas.
    • Soportar serialización.
    • Mantener integridad referencial.
    • Integrarse con Graph.
    • Integrarse con Factory.
    • Integrarse con Serializer.
    • Integrarse con Validators.

Versión:
    1.0.0
===============================================================================
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field

from datetime import datetime

from typing import Any
from typing import Dict
from typing import Iterable
from typing import Iterator
from typing import List
from typing import Mapping
from typing import Optional
from typing import Sequence
from typing import Set

from .base import (
    BaseEntity,
    JSONDict,
    ValidationErrors,
    utc_now,
)

from .enums import (
    AudienceLevel,
    ContentChannel,
    ContentFormat,
    ContentIntent,
    EvidenceLevel,
    KnowledgeComplexity,
    KnowledgeConfidence,
    KnowledgeFreshness,
    KnowledgeLifecycle,
    KnowledgeScope,
    KnowledgeStatus,
    KnowledgeType,
    LanguageCode,
    Priority,
    PublicationState,
    SourceReliability,
    Visibility,
)

from .identifiers import (
    DomainIdentifier,
    IdentifierPrefix,
)

from .metadata import (
    KnowledgeMetadata,
)

from .references import (
    ReferenceCollection,
)

from .mixins import (
    KnowledgeAssetCapabilities,
)

###############################################################################
# TYPE ALIASES
###############################################################################

KnowledgeAssetID = DomainIdentifier

KnowledgeMap = Dict[str, "KnowledgeAsset"]

KnowledgeList = List["KnowledgeAsset"]

KnowledgeIterable = Iterable["KnowledgeAsset"]

KnowledgeSet = Set[str]

###############################################################################
# DEFAULTS
###############################################################################

DEFAULT_LANGUAGE = LanguageCode.ES

DEFAULT_STATUS = KnowledgeStatus.DRAFT

DEFAULT_VISIBILITY = Visibility.PRIVATE

DEFAULT_PUBLICATION_STATE = PublicationState.NOT_SCHEDULED

DEFAULT_PRIORITY = Priority.NORMAL

DEFAULT_COMPLEXITY = KnowledgeComplexity.INTERMEDIATE

DEFAULT_CONFIDENCE = KnowledgeConfidence.MEDIUM

DEFAULT_SCOPE = KnowledgeScope.ORGANIZATION

DEFAULT_FRESHNESS = KnowledgeFreshness.EVERGREEN

DEFAULT_LIFECYCLE = KnowledgeLifecycle.CREATED

###############################################################################
# INTERNAL HELPERS
###############################################################################


def _now() -> datetime:
    """
    Devuelve un datetime UTC.

    Centralizar este método facilita
    pruebas unitarias futuras.
    """
    return utc_now()


def _empty_metadata() -> KnowledgeMetadata:
    """
    Construye un objeto vacío
    de metadatos.
    """
    return KnowledgeMetadata()


def _empty_references() -> ReferenceCollection:
    """
    Construye una colección vacía
    de referencias.
    """
    return ReferenceCollection()


def _new_identifier() -> DomainIdentifier:
    """
    Genera un identificador para
    KnowledgeAsset.
    """
    return DomainIdentifier.new(
        IdentifierPrefix.KNOWLEDGE_ASSET
    )


###############################################################################
# VALIDATION UTILITIES
###############################################################################


def validate_title(title: str) -> str:
    """
    Normaliza y valida un título.
    """

    if not isinstance(title, str):
        raise TypeError(
            "title debe ser str."
        )

    title = title.strip()

    if not title:
        raise ValueError(
            "title no puede estar vacío."
        )

    if len(title) > 300:
        raise ValueError(
            "title excede 300 caracteres."
        )

    return title


def validate_language(
    language: LanguageCode,
) -> LanguageCode:

    if not isinstance(language, LanguageCode):
        raise TypeError(
            "language debe ser LanguageCode."
        )

    return language


def validate_priority(
    priority: Priority,
) -> Priority:

    if not isinstance(priority, Priority):
        raise TypeError(
            "priority debe ser Priority."
        )

    return priority


def validate_visibility(
    visibility: Visibility,
) -> Visibility:

    if not isinstance(
        visibility,
        Visibility,
    ):
        raise TypeError(
            "visibility debe ser Visibility."
        )

    return visibility


###############################################################################
# ABSTRACT COLLECTION
###############################################################################


class AssetContainer:
    """
    Clase base reutilizable para
    futuras colecciones.

    La usarán:

        KnowledgeCollection
        KnowledgeBundle
        KnowledgeIndex

    evitando repetir cientos
    de líneas de código.
    """

    __slots__ = (
        "_assets",
    )

    def __init__(
        self,
        assets: Optional[
            Iterable["KnowledgeAsset"]
        ] = None,
    ) -> None:

        self._assets: Dict[
            str,
            KnowledgeAsset,
        ] = {}

        if assets:

            for asset in assets:

                self.add(asset)

    ###########################################################################

    def __len__(self) -> int:

        return len(
            self._assets
        )

    ###########################################################################

    def __iter__(
        self,
    ) -> Iterator[
        "KnowledgeAsset"
    ]:

        return iter(
            self._assets.values()
        )

    ###########################################################################

    def __contains__(
        self,
        asset_id: object,
    ) -> bool:

        if isinstance(
            asset_id,
            DomainIdentifier,
        ):
            asset_id = str(asset_id)

        return asset_id in self._assets

    ###########################################################################

    def clear(
        self,
    ) -> None:

        self._assets.clear()

    ###########################################################################

    def values(
        self,
    ) -> List[
        "KnowledgeAsset"
    ]:

        return list(
            self._assets.values()
        )

    ###########################################################################

    def ids(
        self,
    ) -> List[
        str
    ]:

        return list(
            self._assets.keys()
        )

    ###########################################################################

    def get(
        self,
        asset_id: str,
    ) -> Optional[
        "KnowledgeAsset"
    ]:

        return self._assets.get(
            asset_id
        )

    ###########################################################################

    def add(
        self,
        asset: "KnowledgeAsset",
    ) -> None:

        if not isinstance(
            asset,
            KnowledgeAsset,
        ):
            raise TypeError(
                "asset debe ser KnowledgeAsset."
            )

        self._assets[
            str(asset.identifier)
        ] = asset

    ###########################################################################

    def remove(
        self,
        asset_id: str,
    ) -> bool:

        return (
            self._assets.pop(
                asset_id,
                None,
            )
            is not None
        )

    ###########################################################################

    def to_list(
        self,
    ) -> List[
        "KnowledgeAsset"
    ]:

        return self.values()
    ###############################################################################
# KNOWLEDGE ASSET
###############################################################################


@dataclass(slots=True)
class KnowledgeAsset(
    BaseEntity,
    KnowledgeAssetCapabilities,
):
    """
    Entidad principal del dominio.

    Representa cualquier activo de conocimiento administrado por CIPS.

    Ejemplos:

        • Curso
        • Prompt
        • Investigación
        • Documento
        • Estrategia
        • Manual
        • Tutorial
        • Framework
        • Dataset
        • Plantilla
        • Checklist
        • SOP
        • Workflow

    Toda la librería gira alrededor de esta entidad.
    """

    ###########################################################################
    # IDENTIDAD
    ###########################################################################

    identifier: DomainIdentifier = field(
        default_factory=_new_identifier,
    )

    ###########################################################################
    # INFORMACIÓN PRINCIPAL
    ###########################################################################

    title: str = ""

    slug: Optional[str] = None

    summary: Optional[str] = None

    description: Optional[str] = None

    ###########################################################################
    # CLASIFICACIÓN
    ###########################################################################

    knowledge_type: KnowledgeType = (
        KnowledgeType.DOCUMENT
    )

    status: KnowledgeStatus = (
        DEFAULT_STATUS
    )

    lifecycle: KnowledgeLifecycle = (
        DEFAULT_LIFECYCLE
    )

    scope: KnowledgeScope = (
        DEFAULT_SCOPE
    )

    ###########################################################################
    # CALIDAD
    ###########################################################################

    confidence: KnowledgeConfidence = (
        DEFAULT_CONFIDENCE
    )

    freshness: KnowledgeFreshness = (
        DEFAULT_FRESHNESS
    )

    complexity: KnowledgeComplexity = (
        DEFAULT_COMPLEXITY
    )

    ###########################################################################
    # PUBLICACIÓN
    ###########################################################################

    visibility: Visibility = (
        DEFAULT_VISIBILITY
    )

    publication_state: PublicationState = (
        DEFAULT_PUBLICATION_STATE
    )

    priority: Priority = (
        DEFAULT_PRIORITY
    )

    ###########################################################################
    # IDIOMA
    ###########################################################################

    language: LanguageCode = (
        DEFAULT_LANGUAGE
    )

    ###########################################################################
    # AUDIENCIA
    ###########################################################################

    audience: Optional[
        AudienceLevel
    ] = None

    content_intent: Optional[
        ContentIntent
    ] = None

    content_format: Optional[
        ContentFormat
    ] = None

    content_channel: Optional[
        ContentChannel
    ] = None

    ###########################################################################
    # EVIDENCIA
    ###########################################################################

    evidence_level: Optional[
        EvidenceLevel
    ] = None

    source_reliability: Optional[
        SourceReliability
    ] = None

    ###########################################################################
    # METADATOS
    ###########################################################################

    metadata: KnowledgeMetadata = field(
        default_factory=_empty_metadata
    )

    ###########################################################################
    # REFERENCIAS
    ###########################################################################

    references: ReferenceCollection = field(
        default_factory=_empty_references
    )

    ###########################################################################
    # ORGANIZACIÓN
    ###########################################################################

    tags: List[str] = field(
        default_factory=list
    )

    labels: List[str] = field(
        default_factory=list
    )

    aliases: List[str] = field(
        default_factory=list
    )

    notes: List[str] = field(
        default_factory=list
    )

    ###########################################################################
    # EXTENSIBILIDAD
    ###########################################################################

    custom_fields: Dict[
        str,
        Any,
    ] = field(
        default_factory=dict
    )

    ###########################################################################
    # AUDITORÍA
    ###########################################################################

    created_by: Optional[str] = None

    updated_by: Optional[str] = None

    ###########################################################################
    # VERSIONADO
    ###########################################################################

    version: str = "1.0.0"

    revision: int = 1

    ###########################################################################
    # FECHAS
    ###########################################################################

    created_at: datetime = field(
        default_factory=_now
    )

    updated_at: datetime = field(
        default_factory=_now
    )

    ###########################################################################
    # ESTADO INTERNO
    ###########################################################################

    archived: bool = False

    deleted: bool = False

    locked: bool = False

    ###########################################################################
    # POST INIT
    ###########################################################################

    def __post_init__(
        self,
    ) -> None:
        """
        Inicialización central.

        Ejecuta todos los inicializadores
        proporcionados por los mixins.
        """

        self.title = validate_title(
            self.title
        )

        self.language = validate_language(
            self.language
        )

        self.priority = validate_priority(
            self.priority
        )

        self.visibility = validate_visibility(
            self.visibility
        )

        self.initialize_domain_capabilities()

        self.initialize_slug(
            self.title
        )

        self.capture_state()
            ###########################################################################
    # IDENTIDAD
    ###########################################################################

    @property
    def id(self) -> str:
        """
        Alias de solo lectura del identificador.

        Facilita la interoperabilidad con ORMs,
        APIs REST y serializadores.
        """
        return str(self.identifier)

    @property
    def is_active(self) -> bool:
        """
        Indica si el activo puede utilizarse.
        """
        return (
            not self.deleted
            and not self.archived
        )

    @property
    def is_editable(self) -> bool:
        """
        Indica si el activo admite modificaciones.
        """
        return (
            self.is_active
            and not self.locked
        )

    ###########################################################################
    # ESTADO
    ###########################################################################

    def archive(self) -> None:
        """
        Archiva el activo.
        """

        if not self.archived:

            self.archived = True

            self.touch()

    ###########################################################################

    def restore(self) -> None:
        """
        Restaura un activo archivado.
        """

        if self.archived:

            self.archived = False

            self.touch()

    ###########################################################################

    def lock(self) -> None:
        """
        Bloquea modificaciones.
        """

        if not self.locked:

            self.locked = True

            self.touch()

    ###########################################################################

    def unlock(self) -> None:
        """
        Desbloquea modificaciones.
        """

        if self.locked:

            self.locked = False

            self.touch()

    ###########################################################################

    def mark_deleted(self) -> None:
        """
        Eliminación lógica.
        """

        if not self.deleted:

            self.deleted = True

            self.touch()

    ###########################################################################

    def recover(self) -> None:
        """
        Recupera un activo eliminado.
        """

        if self.deleted:

            self.deleted = False

            self.touch()

    ###########################################################################
    # PUBLICACIÓN
    ###########################################################################

    def publish(self) -> None:
        """
        Publica el activo.
        """

        self.publication_state = (
            PublicationState.PUBLISHED
        )

        self.status = (
            KnowledgeStatus.PUBLISHED
        )

        self.touch()

    ###########################################################################

    def unpublish(self) -> None:
        """
        Regresa el activo a borrador.
        """

        self.publication_state = (
            PublicationState.NOT_SCHEDULED
        )

        self.status = (
            KnowledgeStatus.DRAFT
        )

        self.touch()

    ###########################################################################

    def set_visibility(
        self,
        visibility: Visibility,
    ) -> None:

        self.visibility = validate_visibility(
            visibility
        )

        self.touch()

    ###########################################################################

    def set_priority(
        self,
        priority: Priority,
    ) -> None:

        self.priority = validate_priority(
            priority
        )

        self.touch()

    ###########################################################################

    def set_language(
        self,
        language: LanguageCode,
    ) -> None:

        self.language = validate_language(
            language
        )

        self.touch()

    ###########################################################################
    # INFORMACIÓN
    ###########################################################################

    def rename(
        self,
        title: str,
    ) -> None:
        """
        Cambia el título del activo.
        """

        self.title = validate_title(
            title
        )

        self.regenerate_slug(
            self.title
        )

        self.touch()

    ###########################################################################

    def set_summary(
        self,
        summary: Optional[str],
    ) -> None:

        self.summary = summary

        self.touch()

    ###########################################################################

    def set_description(
        self,
        description: Optional[str],
    ) -> None:

        self.description = description

        self.touch()

    ###########################################################################
    # METADATOS
    ###########################################################################

    def replace_metadata(
        self,
        metadata: KnowledgeMetadata,
    ) -> None:

        if not isinstance(
            metadata,
            KnowledgeMetadata,
        ):
            raise TypeError(
                "metadata debe ser KnowledgeMetadata."
            )

        self.metadata = metadata

        self.touch()

    ###########################################################################
    # REFERENCIAS
    ###########################################################################

    def replace_references(
        self,
        references: ReferenceCollection,
    ) -> None:

        if not isinstance(
            references,
            ReferenceCollection,
        ):
            raise TypeError(
                "references debe ser ReferenceCollection."
            )

        self.references = references

        self.touch()

    ###########################################################################
    # VERSIONADO
    ###########################################################################

    def new_revision(self) -> int:
        """
        Incrementa únicamente la revisión.
        """

        return self.bump_revision()

    ###########################################################################

    def new_minor_version(self) -> str:
        """
        Incrementa la versión menor.
        """

        return self.bump_minor()

    ###########################################################################

    def new_major_version(self) -> str:
        """
        Incrementa la versión mayor.
        """

        return self.bump_major()

    ###########################################################################
    # UTILIDADES
    ###########################################################################

    def matches(
        self,
        query: str,
    ) -> bool:
        """
        Alias de búsqueda textual.
        """

        return self.matches_query(
            query
        )

    ###########################################################################

    def content_hash(
        self,
    ) -> str:
        """
        Hash estable del contenido.
        """

        return self.calculate_hash()

    ###########################################################################

    def clone(
        self,
        **changes: Any,
    ) -> "KnowledgeAsset":
        """
        Crea una copia profunda del activo.

        Si no se proporciona un nuevo
        identificador, genera uno nuevo
        automáticamente para evitar
        duplicados.
        """

        if "identifier" not in changes:

            changes[
                "identifier"
            ] = _new_identifier()

        return self.copy_with(
            **changes
        )
            ###########################################################################
    # VALIDACIÓN
    ###########################################################################

    def validation_errors(
        self,
    ) -> ValidationErrors:
        """
        Ejecuta todas las validaciones de la entidad.

        Combina:

            • Validaciones propias.
            • Validaciones heredadas de los mixins.
            • Validaciones de objetos compuestos.
        """

        errors: ValidationErrors = []

        #######################################################################
        # CAMPOS OBLIGATORIOS
        #######################################################################

        try:
            validate_title(self.title)
        except Exception as exc:
            errors.append(str(exc))

        #######################################################################
        # ENUMS
        #######################################################################

        enum_validations = (
            ("knowledge_type", self.knowledge_type, KnowledgeType),
            ("status", self.status, KnowledgeStatus),
            ("lifecycle", self.lifecycle, KnowledgeLifecycle),
            ("scope", self.scope, KnowledgeScope),
            ("confidence", self.confidence, KnowledgeConfidence),
            ("freshness", self.freshness, KnowledgeFreshness),
            ("complexity", self.complexity, KnowledgeComplexity),
            ("visibility", self.visibility, Visibility),
            ("publication_state", self.publication_state, PublicationState),
            ("priority", self.priority, Priority),
            ("language", self.language, LanguageCode),
        )

        for field_name, value, enum_type in enum_validations:

            if not isinstance(
                value,
                enum_type,
            ):
                errors.append(
                    f"{field_name} debe ser {enum_type.__name__}."
                )

        #######################################################################
        # IDENTIFICADOR
        #######################################################################

        if not isinstance(
            self.identifier,
            DomainIdentifier,
        ):
            errors.append(
                "identifier debe ser DomainIdentifier."
            )

        #######################################################################
        # METADATA
        #######################################################################

        if not isinstance(
            self.metadata,
            KnowledgeMetadata,
        ):
            errors.append(
                "metadata debe ser KnowledgeMetadata."
            )
        else:

            method = getattr(
                self.metadata,
                "validation_errors",
                None,
            )

            if callable(method):

                errors.extend(method())

        #######################################################################
        # REFERENCIAS
        #######################################################################

        if not isinstance(
            self.references,
            ReferenceCollection,
        ):
            errors.append(
                "references debe ser ReferenceCollection."
            )
        else:

            method = getattr(
                self.references,
                "validation_errors",
                None,
            )

            if callable(method):

                errors.extend(method())

        #######################################################################
        # MIXINS
        #######################################################################

        errors.extend(
            self.mixin_validation_errors()
        )

        #######################################################################
        # DUPLICADOS
        #######################################################################

        if len(self.tags) != len(set(
            tag.casefold()
            for tag in self.tags
        )):
            errors.append(
                "tags contiene valores duplicados."
            )

        if len(self.labels) != len(set(
            label.casefold()
            for label in self.labels
        )):
            errors.append(
                "labels contiene valores duplicados."
            )

        if len(self.aliases) != len(set(
            alias.casefold()
            for alias in self.aliases
        )):
            errors.append(
                "aliases contiene valores duplicados."
            )

        #######################################################################
        # FECHAS
        #######################################################################

        if self.updated_at < self.created_at:

            errors.append(
                "updated_at no puede ser menor que created_at."
            )

        return errors

    ###########################################################################

    def validate(
        self,
    ) -> None:
        """
        Lanza una excepción si la entidad es inválida.
        """

        errors = self.validation_errors()

        if errors:

            raise ValueError(
                "\n".join(errors)
            )

    ###########################################################################
    # SERIALIZACIÓN
    ###########################################################################

    def to_dict(
        self,
    ) -> JSONDict:
        """
        Serializa completamente el activo.

        Compatible con serializer.py.
        """

        return self.export_dict()

    ###########################################################################

    def to_json(
        self,
        *,
        indent: int = 2,
    ) -> str:
        """
        Exporta la entidad como JSON.
        """

        return self.export_json(
            indent=indent,
            ensure_ascii=False,
        )

    ###########################################################################

    @classmethod
    def from_dict(
        cls,
        data: Mapping[
            str,
            Any,
        ],
    ) -> "KnowledgeAsset":
        """
        Reconstruye un activo desde un diccionario.
        """

        if not isinstance(
            data,
            Mapping,
        ):
            raise TypeError(
                "data debe ser Mapping."
            )

        payload = dict(data)

        if "identifier" in payload:

            if not isinstance(
                payload["identifier"],
                DomainIdentifier,
            ):
                payload["identifier"] = (
                    DomainIdentifier(
                        payload["identifier"]
                    )
                )

        return cls(
            **payload
        )

    ###########################################################################

    @classmethod
    def new(
        cls,
        title: str,
        *,
        knowledge_type: KnowledgeType = (
            KnowledgeType.DOCUMENT
        ),
    ) -> "KnowledgeAsset":
        """
        Constructor de conveniencia.
        """

        return cls(
            title=title,
            knowledge_type=knowledge_type,
        )

    ###########################################################################

    def __hash__(
        self,
    ) -> int:
        """
        Permite utilizar la entidad
        dentro de conjuntos y diccionarios.
        """

        return hash(
            str(self.identifier)
        )

    ###########################################################################

    def __repr__(
        self,
    ) -> str:

        return (
            f"{type(self).__name__}("
            f"id={self.identifier!s}, "
            f"title={self.title!r}, "
            f"type={self.knowledge_type.name}, "
            f"status={self.status.name})"
        )
        ###############################################################################
# KNOWLEDGE COLLECTION
###############################################################################


class KnowledgeCollection(
    AssetContainer,
):
    """
    Colección enriquecida de activos de conocimiento.

    Además de almacenar activos proporciona:

        • búsquedas
        • filtros
        • estadísticas
        • exportación
        • ordenamiento
        • índices rápidos

    Es la colección principal utilizada por
    serializer.py, graph.py y factory.py.
    """

    ###########################################################################
    # CONSTRUCTOR
    ###########################################################################

    def __init__(
        self,
        assets: Optional[
            Iterable[
                KnowledgeAsset
            ]
        ] = None,
        *,
        name: str = "",
        description: str = "",
    ) -> None:

        super().__init__(
            assets
        )

        self.name = (
            name.strip()
        )

        self.description = (
            description.strip()
        )

    ###########################################################################
    # PROPIEDADES
    ###########################################################################

    @property
    def count(
        self,
    ) -> int:

        return len(
            self
        )

    ###########################################################################

    @property
    def empty(
        self,
    ) -> bool:

        return (
            len(self)
            == 0
        )

    ###########################################################################
    # CONSULTAS
    ###########################################################################

    def first(
        self,
    ) -> Optional[
        KnowledgeAsset
    ]:

        for asset in self:

            return asset

        return None

    ###########################################################################

    def last(
        self,
    ) -> Optional[
        KnowledgeAsset
    ]:

        if self.empty:

            return None

        return self.values()[-1]

    ###########################################################################

    def titles(
        self,
    ) -> List[
        str
    ]:

        return [
            asset.title
            for asset in self
        ]

    ###########################################################################

    def identifiers(
        self,
    ) -> List[
        DomainIdentifier
    ]:

        return [
            asset.identifier
            for asset in self
        ]

    ###########################################################################
    # FILTRADO
    ###########################################################################

    def filter(
        self,
        predicate,
    ) -> "KnowledgeCollection":
        """
        Filtra utilizando cualquier función.
        """

        return KnowledgeCollection(

            asset
            for asset in self

            if predicate(
                asset
            )
        )

    ###########################################################################

    def active(
        self,
    ) -> "KnowledgeCollection":

        return self.filter(

            lambda asset:
            asset.is_active

        )

    ###########################################################################

    def published(
        self,
    ) -> "KnowledgeCollection":

        return self.filter(

            lambda asset:
            asset.publication_state
            ==
            PublicationState.PUBLISHED

        )

    ###########################################################################

    def archived(
        self,
    ) -> "KnowledgeCollection":

        return self.filter(

            lambda asset:
            asset.archived

        )

    ###########################################################################

    def deleted(
        self,
    ) -> "KnowledgeCollection":

        return self.filter(

            lambda asset:
            asset.deleted

        )

    ###########################################################################

    def locked(
        self,
    ) -> "KnowledgeCollection":

        return self.filter(

            lambda asset:
            asset.locked

        )

    ###########################################################################
    # BÚSQUEDA
    ###########################################################################

    def search(
        self,
        query: str,
    ) -> "KnowledgeCollection":

        return self.filter(

            lambda asset:
            asset.matches(
                query
            )

        )

    ###########################################################################

    def by_type(
        self,
        knowledge_type: KnowledgeType,
    ) -> "KnowledgeCollection":

        return self.filter(

            lambda asset:
            asset.knowledge_type
            ==
            knowledge_type

        )

    ###########################################################################

    def by_status(
        self,
        status: KnowledgeStatus,
    ) -> "KnowledgeCollection":

        return self.filter(

            lambda asset:
            asset.status
            ==
            status

        )

    ###########################################################################

    def by_language(
        self,
        language: LanguageCode,
    ) -> "KnowledgeCollection":

        return self.filter(

            lambda asset:
            asset.language
            ==
            language

        )

    ###########################################################################

    def by_visibility(
        self,
        visibility: Visibility,
    ) -> "KnowledgeCollection":

        return self.filter(

            lambda asset:
            asset.visibility
            ==
            visibility

        )

    ###########################################################################

    def by_priority(
        self,
        priority: Priority,
    ) -> "KnowledgeCollection":

        return self.filter(

            lambda asset:
            asset.priority
            ==
            priority

        )

    ###########################################################################

    def by_tag(
        self,
        tag: str,
    ) -> "KnowledgeCollection":

        return self.filter(

            lambda asset:
            asset.has_tag(
                tag
            )

        )

    ###########################################################################

    def by_label(
        self,
        label: str,
    ) -> "KnowledgeCollection":

        return self.filter(

            lambda asset:

            any(

                current.casefold()
                ==
                label.casefold()

                for current
                in asset.labels

            )

        )

    ###########################################################################

    def by_alias(
        self,
        alias: str,
    ) -> "KnowledgeCollection":

        return self.filter(

            lambda asset:
            asset.matches_alias(
                alias
            )

        )

    ###########################################################################
    # ORDENAMIENTO
    ###########################################################################

    def sort_by_title(
        self,
        *,
        reverse: bool = False,
    ) -> "KnowledgeCollection":

        return KnowledgeCollection(

            sorted(

                self,

                key=lambda asset:
                asset.title.casefold(),

                reverse=reverse,

            )

        )

    ###########################################################################

    def sort_by_created(
        self,
        *,
        reverse: bool = False,
    ) -> "KnowledgeCollection":

        return KnowledgeCollection(

            sorted(

                self,

                key=lambda asset:
                asset.created_at,

                reverse=reverse,

            )

        )

    ###########################################################################

    def sort_by_updated(
        self,
        *,
        reverse: bool = True,
    ) -> "KnowledgeCollection":

        return KnowledgeCollection(

            sorted(

                self,

                key=lambda asset:
                asset.updated_at,

                reverse=reverse,

            )

        )

    ###########################################################################

    def sort_by_priority(
        self,
    ) -> "KnowledgeCollection":

        return KnowledgeCollection(

            sorted(

                self,

                key=lambda asset:
                asset.priority.value,

            )

        )
            ###########################################################################
    # AGRUPACIONES
    ###########################################################################

    def group_by_type(
        self,
    ) -> Dict[
        KnowledgeType,
        "KnowledgeCollection",
    ]:
        """
        Agrupa los activos por tipo.
        """

        groups: Dict[
            KnowledgeType,
            KnowledgeCollection,
        ] = {}

        for asset in self:

            groups.setdefault(
                asset.knowledge_type,
                KnowledgeCollection(),
            ).add(asset)

        return groups

    ###########################################################################

    def group_by_status(
        self,
    ) -> Dict[
        KnowledgeStatus,
        "KnowledgeCollection",
    ]:

        groups: Dict[
            KnowledgeStatus,
            KnowledgeCollection,
        ] = {}

        for asset in self:

            groups.setdefault(
                asset.status,
                KnowledgeCollection(),
            ).add(asset)

        return groups

    ###########################################################################

    def group_by_language(
        self,
    ) -> Dict[
        LanguageCode,
        "KnowledgeCollection",
    ]:

        groups: Dict[
            LanguageCode,
            KnowledgeCollection,
        ] = {}

        for asset in self:

            groups.setdefault(
                asset.language,
                KnowledgeCollection(),
            ).add(asset)

        return groups

    ###########################################################################

    def group_by_visibility(
        self,
    ) -> Dict[
        Visibility,
        "KnowledgeCollection",
    ]:

        groups: Dict[
            Visibility,
            KnowledgeCollection,
        ] = {}

        for asset in self:

            groups.setdefault(
                asset.visibility,
                KnowledgeCollection(),
            ).add(asset)

        return groups

    ###########################################################################
    # ÍNDICES
    ###########################################################################

    def index_by_identifier(
        self,
    ) -> Dict[
        str,
        KnowledgeAsset,
    ]:

        return {

            str(asset.identifier): asset

            for asset in self

        }

    ###########################################################################

    def index_by_title(
        self,
    ) -> Dict[
        str,
        KnowledgeAsset,
    ]:

        return {

            asset.title.casefold(): asset

            for asset in self

        }

    ###########################################################################

    def index_by_slug(
        self,
    ) -> Dict[
        str,
        KnowledgeAsset,
    ]:

        return {

            asset.slug: asset

            for asset in self

            if asset.slug

        }

    ###########################################################################
    # ESTADÍSTICAS
    ###########################################################################

    def statistics(
        self,
    ) -> JSONDict:
        """
        Devuelve un resumen estadístico de la colección.
        """

        stats: JSONDict = {

            "total_assets": len(self),

            "published": len(
                self.published()
            ),

            "drafts": len(
                self.by_status(
                    KnowledgeStatus.DRAFT
                )
            ),

            "archived": len(
                self.archived()
            ),

            "deleted": len(
                self.deleted()
            ),

            "locked": len(
                self.locked()
            ),

            "active": len(
                self.active()
            ),

        }

        stats["types"] = {

            key.name: len(value)

            for key, value

            in self.group_by_type().items()

        }

        stats["languages"] = {

            key.name: len(value)

            for key, value

            in self.group_by_language().items()

        }

        stats["visibility"] = {

            key.name: len(value)

            for key, value

            in self.group_by_visibility().items()

        }

        return stats

    ###########################################################################
    # EXPORTACIÓN
    ###########################################################################

    def to_list(
        self,
    ) -> List[
        JSONDict,
    ]:

        return [

            asset.to_dict()

            for asset

            in self

        ]

    ###########################################################################

    def to_json(
        self,
        *,
        indent: int = 2,
    ) -> str:

        import json

        return json.dumps(

            self.to_list(),

            indent=indent,

            ensure_ascii=False,

        )

    ###########################################################################
    # VALIDACIÓN
    ###########################################################################

    def validation_errors(
        self,
    ) -> ValidationErrors:
        """
        Valida todos los activos de la colección.
        """

        errors: ValidationErrors = []

        identifiers: Set[
            str
        ] = set()

        slugs: Set[
            str
        ] = set()

        for asset in self:

            ###################################################################
            # VALIDACIÓN DEL ACTIVO
            ###################################################################

            asset_errors = asset.validation_errors()

            if asset_errors:

                for error in asset_errors:

                    errors.append(

                        f"{asset.title}: {error}"

                    )

            ###################################################################
            # IDENTIFICADORES DUPLICADOS
            ###################################################################

            identifier = str(
                asset.identifier
            )

            if identifier in identifiers:

                errors.append(

                    f"Identifier duplicado: {identifier}"

                )

            identifiers.add(
                identifier
            )

            ###################################################################
            # SLUGS DUPLICADOS
            ###################################################################

            if asset.slug:

                slug = asset.slug.casefold()

                if slug in slugs:

                    errors.append(

                        f"Slug duplicado: {asset.slug}"

                    )

                slugs.add(
                    slug
                )

        return errors

    ###########################################################################

    def validate(
        self,
    ) -> None:

        errors = self.validation_errors()

        if errors:

            raise ValueError(

                "\n".join(errors)

            )

    ###########################################################################
    # CONJUNTOS
    ###########################################################################

    def union(
        self,
        other: "KnowledgeCollection",
    ) -> "KnowledgeCollection":
        """
        Une dos colecciones sin duplicar activos.
        """

        result = KnowledgeCollection(
            self.values()
        )

        for asset in other:

            if str(asset.identifier) not in result:

                result.add(asset)

        return result

    ###########################################################################

    def intersection(
        self,
        other: "KnowledgeCollection",
    ) -> "KnowledgeCollection":
        """
        Devuelve los activos presentes en ambas colecciones.
        """

        return KnowledgeCollection(

            asset

            for asset in self

            if str(asset.identifier) in other

        )

    ###########################################################################

    def difference(
        self,
        other: "KnowledgeCollection",
    ) -> "KnowledgeCollection":
        """
        Devuelve los activos exclusivos de esta colección.
        """

        return KnowledgeCollection(

            asset

            for asset in self

            if str(asset.identifier) not in other

        )

    ###########################################################################

    def clone(
        self,
    ) -> "KnowledgeCollection":
        """
        Copia profunda de la colección.
        """

        return KnowledgeCollection(

            asset.clone()

            for asset in self

        )
        ###############################################################################
# KNOWLEDGE BUNDLE
###############################################################################


@dataclass(slots=True)
class KnowledgeBundle:
    """
    Contenedor lógico para transportar conjuntos de activos.

    Un Bundle representa una unidad de intercambio entre módulos
    (Serializer, Factory, Graph, API, Exportadores, etc.).

    Puede contener activos, información descriptiva y metadatos del
    propio paquete.
    """

    ###########################################################################
    # IDENTIDAD
    ###########################################################################

    identifier: DomainIdentifier = field(
        default_factory=lambda: DomainIdentifier.new(
            IdentifierPrefix.CONTENT_ASSET
        )
    )

    ###########################################################################
    # INFORMACIÓN
    ###########################################################################

    name: str = ""

    version: str = "1.0.0"

    description: str = ""

    author: Optional[str] = None

    ###########################################################################
    # CONTENIDO
    ###########################################################################

    assets: KnowledgeCollection = field(
        default_factory=KnowledgeCollection
    )

    ###########################################################################
    # FECHAS
    ###########################################################################

    created_at: datetime = field(
        default_factory=_now
    )

    ###########################################################################
    # OPERACIONES
    ###########################################################################

    def __len__(self) -> int:

        return len(
            self.assets
        )

    ###########################################################################

    def __iter__(
        self,
    ) -> Iterator[
        KnowledgeAsset
    ]:

        return iter(
            self.assets
        )

    ###########################################################################

    def add(
        self,
        asset: KnowledgeAsset,
    ) -> None:

        self.assets.add(
            asset
        )

    ###########################################################################

    def remove(
        self,
        asset_id: str,
    ) -> bool:

        return self.assets.remove(
            asset_id
        )

    ###########################################################################

    def statistics(
        self,
    ) -> JSONDict:

        return self.assets.statistics()

    ###########################################################################

    def validation_errors(
        self,
    ) -> ValidationErrors:

        errors: ValidationErrors = []

        if not self.name.strip():

            errors.append(
                "Bundle sin nombre."
            )

        errors.extend(
            self.assets.validation_errors()
        )

        return errors

    ###########################################################################

    def validate(
        self,
    ) -> None:

        errors = self.validation_errors()

        if errors:

            raise ValueError(
                "\n".join(errors)
            )

    ###########################################################################

    def to_dict(
        self,
    ) -> JSONDict:

        return {

            "identifier": str(
                self.identifier
            ),

            "name": self.name,

            "version": self.version,

            "description": self.description,

            "author": self.author,

            "created_at": self.created_at.isoformat(),

            "assets": self.assets.to_list(),

        }

    ###########################################################################

    def to_json(
        self,
        *,
        indent: int = 2,
    ) -> str:

        import json

        return json.dumps(

            self.to_dict(),

            indent=indent,

            ensure_ascii=False,

        )


###############################################################################
# KNOWLEDGE INDEX
###############################################################################


class KnowledgeIndex:
    """
    Índices rápidos para acelerar búsquedas.

    Esta clase mantiene múltiples estructuras hash evitando recorrer
    miles de activos en búsquedas frecuentes.
    """

    ###########################################################################

    def __init__(
        self,
        assets: Optional[
            Iterable[
                KnowledgeAsset
            ]
        ] = None,
    ) -> None:

        self.clear()

        if assets:

            self.build(
                assets
            )

    ###########################################################################

    def clear(
        self,
    ) -> None:

        self.by_identifier: Dict[
            str,
            KnowledgeAsset,
        ] = {}

        self.by_title: Dict[
            str,
            List[
                KnowledgeAsset
            ],
        ] = {}

        self.by_slug: Dict[
            str,
            KnowledgeAsset,
        ] = {}

        self.by_type: Dict[
            KnowledgeType,
            List[
                KnowledgeAsset
            ],
        ] = {}

        self.by_tag: Dict[
            str,
            List[
                KnowledgeAsset
            ],
        ] = {}

    ###########################################################################

    def build(
        self,
        assets: Iterable[
            KnowledgeAsset
        ],
    ) -> None:

        self.clear()

        for asset in assets:

            self.add(
                asset
            )

    ###########################################################################

    def add(
        self,
        asset: KnowledgeAsset,
    ) -> None:

        #######################################################################
        # IDENTIFIER
        #######################################################################

        self.by_identifier[
            str(asset.identifier)
        ] = asset

        #######################################################################
        # TITLE
        #######################################################################

        key = asset.title.casefold()

        self.by_title.setdefault(

            key,

            [],

        ).append(

            asset

        )

        #######################################################################
        # SLUG
        #######################################################################

        if asset.slug:

            self.by_slug[
                asset.slug
            ] = asset

        #######################################################################
        # TYPE
        #######################################################################

        self.by_type.setdefault(

            asset.knowledge_type,

            [],

        ).append(

            asset

        )

        #######################################################################
        # TAGS
        #######################################################################

        for tag in asset.tags:

            self.by_tag.setdefault(

                tag.casefold(),

                [],

            ).append(

                asset

            )

    ###########################################################################

    def get(
        self,
        identifier: str,
    ) -> Optional[
        KnowledgeAsset
    ]:

        return self.by_identifier.get(
            identifier
        )

    ###########################################################################

    def title(
        self,
        title: str,
    ) -> List[
        KnowledgeAsset
    ]:

        return self.by_title.get(

            title.casefold(),

            [],

        )

    ###########################################################################

    def slug(
        self,
        slug: str,
    ) -> Optional[
        KnowledgeAsset
    ]:

        return self.by_slug.get(
            slug
        )

    ###########################################################################

    def type(
        self,
        knowledge_type: KnowledgeType,
    ) -> KnowledgeCollection:

        return KnowledgeCollection(

            self.by_type.get(

                knowledge_type,

                [],

            )

        )

    ###########################################################################

    def tag(
        self,
        tag: str,
    ) -> KnowledgeCollection:

        return KnowledgeCollection(

            self.by_tag.get(

                tag.casefold(),

                [],

            )

        )
        ###############################################################################
# KNOWLEDGE QUERY
###############################################################################


@dataclass(slots=True)
class KnowledgeQuery:
    """
    Representa una consulta estructurada sobre una colección de
    KnowledgeAssets.

    Esta clase evita pasar decenas de parámetros entre módulos y permite
    serializar consultas, reutilizarlas y almacenarlas.
    """

    ###########################################################################
    # TEXTO
    ###########################################################################

    text: str = ""

    ###########################################################################
    # FILTROS
    ###########################################################################

    knowledge_type: Optional[
        KnowledgeType
    ] = None

    status: Optional[
        KnowledgeStatus
    ] = None

    language: Optional[
        LanguageCode
    ] = None

    visibility: Optional[
        Visibility
    ] = None

    priority: Optional[
        Priority
    ] = None

    tag: Optional[
        str
    ] = None

    label: Optional[
        str
    ] = None

    alias: Optional[
        str
    ] = None

    ###########################################################################
    # OPCIONES
    ###########################################################################

    include_archived: bool = False

    include_deleted: bool = False

    limit: Optional[int] = None

    offset: int = 0

    ###########################################################################

    def apply(
        self,
        collection: KnowledgeCollection,
    ) -> KnowledgeCollection:
        """
        Ejecuta la consulta sobre una colección.
        """

        result = collection

        #######################################################################
        # ESTADOS
        #######################################################################

        if not self.include_archived:

            result = result.filter(

                lambda asset:
                not asset.archived

            )

        if not self.include_deleted:

            result = result.filter(

                lambda asset:
                not asset.deleted

            )

        #######################################################################
        # BÚSQUEDA
        #######################################################################

        if self.text:

            result = result.search(
                self.text
            )

        #######################################################################
        # FILTROS
        #######################################################################

        if self.knowledge_type is not None:

            result = result.by_type(
                self.knowledge_type
            )

        if self.status is not None:

            result = result.by_status(
                self.status
            )

        if self.language is not None:

            result = result.by_language(
                self.language
            )

        if self.visibility is not None:

            result = result.by_visibility(
                self.visibility
            )

        if self.priority is not None:

            result = result.by_priority(
                self.priority
            )

        if self.tag:

            result = result.by_tag(
                self.tag
            )

        if self.label:

            result = result.by_label(
                self.label
            )

        if self.alias:

            result = result.by_alias(
                self.alias
            )

        #######################################################################
        # PAGINACIÓN
        #######################################################################

        assets = result.values()

        if self.offset:

            assets = assets[
                self.offset:
            ]

        if self.limit is not None:

            assets = assets[
                : self.limit
            ]

        return KnowledgeCollection(
            assets
        )

    ###########################################################################

    def to_dict(
        self,
    ) -> JSONDict:

        return {

            "text": self.text,

            "knowledge_type":
            self.knowledge_type.name
            if self.knowledge_type
            else None,

            "status":
            self.status.name
            if self.status
            else None,

            "language":
            self.language.name
            if self.language
            else None,

            "visibility":
            self.visibility.name
            if self.visibility
            else None,

            "priority":
            self.priority.name
            if self.priority
            else None,

            "tag": self.tag,

            "label": self.label,

            "alias": self.alias,

            "include_archived":
            self.include_archived,

            "include_deleted":
            self.include_deleted,

            "limit":
            self.limit,

            "offset":
            self.offset,

        }


###############################################################################
# KNOWLEDGE SEARCH RESULT
###############################################################################


@dataclass(slots=True)
class KnowledgeSearchResult:
    """
    Resultado enriquecido de una búsqueda.

    No solamente devuelve un activo, sino también información útil
    para motores de búsqueda, ranking, IA y Graph.
    """

    ###########################################################################
    # ACTIVO
    ###########################################################################

    asset: KnowledgeAsset

    ###########################################################################
    # SCORE
    ###########################################################################

    score: float = 1.0

    ###########################################################################
    # COINCIDENCIAS
    ###########################################################################

    matched_fields: List[
        str
    ] = field(
        default_factory=list
    )

    matched_terms: List[
        str
    ] = field(
        default_factory=list
    )

    ###########################################################################
    # CONTEXTO
    ###########################################################################

    explanation: Optional[
        str
    ] = None

    ###########################################################################

    @property
    def identifier(
        self,
    ) -> DomainIdentifier:

        return self.asset.identifier

    ###########################################################################

    @property
    def title(
        self,
    ) -> str:

        return self.asset.title

    ###########################################################################

    @property
    def knowledge_type(
        self,
    ) -> KnowledgeType:

        return self.asset.knowledge_type

    ###########################################################################

    def add_match(
        self,
        field_name: str,
        term: str,
    ) -> None:

        if field_name not in self.matched_fields:

            self.matched_fields.append(
                field_name
            )

        if term not in self.matched_terms:

            self.matched_terms.append(
                term
            )

    ###########################################################################

    def to_dict(
        self,
    ) -> JSONDict:

        return {

            "score":
            self.score,

            "identifier":
            str(
                self.asset.identifier
            ),

            "title":
            self.asset.title,

            "knowledge_type":
            self.asset.knowledge_type.name,

            "matched_fields":
            self.matched_fields,

            "matched_terms":
            self.matched_terms,

            "explanation":
            self.explanation,

            "asset":
            self.asset.to_dict(),

        }

    ###########################################################################

    def __lt__(
        self,
        other: "KnowledgeSearchResult",
    ) -> bool:
        """
        Permite ordenar resultados por score.
        """

        return self.score < other.score

    ###########################################################################

    def __repr__(
        self,
    ) -> str:

        return (

            f"{type(self).__name__}("
            f"title={self.asset.title!r}, "
            f"score={self.score:.3f})"

        )
        ###############################################################################
# MODULE UTILITIES
###############################################################################


def collection_from_assets(
    assets: Iterable[
        KnowledgeAsset,
    ],
) -> KnowledgeCollection:
    """
    Construye una colección a partir de un iterable.

    Es el punto de entrada recomendado para crear colecciones desde
    cualquier origen (Factory, Serializer, Graph, API, etc.).
    """

    return KnowledgeCollection(
        assets
    )


###############################################################################


def collection_from_dicts(
    items: Iterable[
        Mapping[
            str,
            Any,
        ]
    ],
) -> KnowledgeCollection:
    """
    Construye una colección a partir de diccionarios.
    """

    return KnowledgeCollection(

        KnowledgeAsset.from_dict(
            item
        )

        for item

        in items

    )


###############################################################################


def collection_from_json(
    payload: str,
) -> KnowledgeCollection:
    """
    Construye una colección desde un documento JSON.
    """

    import json

    data = json.loads(
        payload
    )

    if not isinstance(
        data,
        list,
    ):
        raise TypeError(
            "El JSON debe contener una lista."
        )

    return collection_from_dicts(
        data
    )


###############################################################################


def merge_collections(
    *collections: KnowledgeCollection,
) -> KnowledgeCollection:
    """
    Une cualquier número de colecciones.

    Los activos se deduplican utilizando su identifier.
    """

    merged = KnowledgeCollection()

    for collection in collections:

        for asset in collection:

            if (
                str(asset.identifier)
                not in merged
            ):

                merged.add(
                    asset
                )

    return merged


###############################################################################


def validate_collection(
    collection: KnowledgeCollection,
) -> None:
    """
    Punto de entrada uniforme para validar colecciones.
    """

    collection.validate()


###############################################################################


def build_index(
    collection: KnowledgeCollection,
) -> KnowledgeIndex:
    """
    Construye un índice optimizado.
    """

    return KnowledgeIndex(
        collection
    )


###############################################################################


def execute_query(
    collection: KnowledgeCollection,
    query: KnowledgeQuery,
) -> KnowledgeCollection:
    """
    Ejecuta una consulta estructurada.
    """

    return query.apply(
        collection
    )


###############################################################################


def search_assets(
    collection: KnowledgeCollection,
    query: str,
) -> List[
    KnowledgeSearchResult,
]:
    """
    Motor básico de búsqueda.

    Más adelante podrá sustituirse por BM25,
    embeddings o búsqueda vectorial sin modificar
    la API pública.
    """

    results: List[
        KnowledgeSearchResult
    ] = []

    query_terms = {

        term.casefold()

        for term

        in query.split()

        if term.strip()

    }

    for asset in collection:

        if not asset.matches(
            query
        ):
            continue

        result = KnowledgeSearchResult(
            asset=asset
        )

        score = 0.0

        ###############################################################
        # TITLE
        ###############################################################

        title = asset.title.casefold()

        for term in query_terms:

            if term in title:

                result.add_match(
                    "title",
                    term,
                )

                score += 10

        ###############################################################
        # TAGS
        ###############################################################

        for tag in asset.tags:

            current = tag.casefold()

            for term in query_terms:

                if term == current:

                    result.add_match(
                        "tags",
                        term,
                    )

                    score += 5

        ###############################################################
        # SUMMARY
        ###############################################################

        if asset.summary:

            summary = (
                asset.summary.casefold()
            )

            for term in query_terms:

                if term in summary:

                    result.add_match(
                        "summary",
                        term,
                    )

                    score += 2

        ###############################################################
        # DESCRIPTION
        ###############################################################

        if asset.description:

            description = (
                asset.description.casefold()
            )

            for term in query_terms:

                if term in description:

                    result.add_match(
                        "description",
                        term,
                    )

                    score += 1

        result.score = score

        results.append(
            result
        )

    results.sort(
        reverse=True
    )

    return results


###############################################################################
# MODULE CONSTANTS
###############################################################################

MODEL_VERSION = "1.0.0"

MODULE_NAME = "knowledge_assets.models"

SUPPORTED_EXPORT_FORMATS = (
    "dict",
    "json",
)

SUPPORTED_SEARCH_FIELDS = (
    "title",
    "summary",
    "description",
    "tags",
    "labels",
    "aliases",
)

###############################################################################
# PUBLIC EXPORTS
###############################################################################

__all__ = [

    ###########################################################################
    # ENTIDADES
    ###########################################################################

    "KnowledgeAsset",

    "KnowledgeCollection",

    "KnowledgeBundle",

    "KnowledgeIndex",

    "KnowledgeQuery",

    "KnowledgeSearchResult",

    ###########################################################################
    # UTILIDADES
    ###########################################################################

    "build_index",

    "collection_from_assets",

    "collection_from_dicts",

    "collection_from_json",

    "execute_query",

    "merge_collections",

    "search_assets",

    "validate_collection",

    ###########################################################################
    # ALIAS
    ###########################################################################

    "KnowledgeAssetID",

    "KnowledgeIterable",

    "KnowledgeList",

    "KnowledgeMap",

    "KnowledgeSet",

    ###########################################################################
    # CONSTANTES
    ###########################################################################

    "MODEL_VERSION",

    "MODULE_NAME",

    "SUPPORTED_EXPORT_FORMATS",

    "SUPPORTED_SEARCH_FIELDS",

]