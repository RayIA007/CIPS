###############################################################################
# relationships.py
#
# Knowledge Assets Library
#
# Sistema de relaciones semánticas entre activos de conocimiento.
#
# Este módulo define:
#
#     • Relaciones dirigidas
#     • Metadata de relaciones
#     • Validación
#     • Helpers
#     • Índices
#     • Consultas
#
# Es la base utilizada posteriormente por graph.py para construir
# Knowledge Graphs completos.
###############################################################################

from __future__ import annotations

###############################################################################
# STANDARD LIBRARY
###############################################################################

from dataclasses import dataclass
from dataclasses import field

from datetime import datetime

from typing import Any
from typing import Dict
from typing import Iterable
from typing import Iterator
from typing import List
from typing import Mapping
from typing import MutableMapping
from typing import Optional
from typing import Sequence
from typing import Set
from typing import Tuple
from typing import TypeAlias

import uuid

###############################################################################
# LOCAL IMPORTS
###############################################################################

from .base import BaseEntity

from .identifiers import DomainIdentifier

from .metadata import Metadata

from .references import ReferenceCollection

from .models import KnowledgeAsset

from .enums import RelationshipType
from .enums import ConfidenceLevel

###############################################################################
# TYPE ALIASES
###############################################################################

RelationshipID: TypeAlias = DomainIdentifier

RelationshipList: TypeAlias = List["Relationship"]

RelationshipMap: TypeAlias = Dict[
    str,
    "Relationship",
]

RelationshipSet: TypeAlias = Set[
    "Relationship",
]

RelationshipIterator: TypeAlias = Iterator[
    "Relationship",
]

RelationshipErrors: TypeAlias = List[
    str,
]

JSONDict: TypeAlias = Dict[
    str,
    Any,
]

###############################################################################
# DEFAULTS
###############################################################################

DEFAULT_WEIGHT = 1.0

DEFAULT_CONFIDENCE = ConfidenceLevel.MEDIUM

###############################################################################
# HELPERS
###############################################################################

def _now() -> datetime:
    """
    Fecha UTC actual.
    """

    return datetime.utcnow()


###############################################################################

def _empty_metadata() -> Metadata:
    """
    Metadata vacía.
    """

    return Metadata()


###############################################################################

def _empty_references() -> ReferenceCollection:
    """
    Colección vacía de referencias.
    """

    return ReferenceCollection()


###############################################################################

def _normalize_text(
    value: str,
) -> str:
    """
    Normaliza texto para comparaciones.
    """

    return value.strip()


###############################################################################

def _normalize_key(
    value: str,
) -> str:
    """
    Clave normalizada para índices.
    """

    return value.strip().casefold()


###############################################################################

def _relationship_uuid() -> str:
    """
    UUID interno.
    """

    return uuid.uuid4().hex


###############################################################################
# VALIDADORES
###############################################################################

def validate_asset(
    asset: KnowledgeAsset,
) -> None:

    if not isinstance(
        asset,
        KnowledgeAsset,
    ):
        raise TypeError(
            "KnowledgeAsset esperado."
        )


###############################################################################

def validate_weight(
    weight: float,
) -> None:

    if weight < 0:

        raise ValueError(
            "El peso no puede ser negativo."
        )


###############################################################################

def validate_confidence(
    confidence: ConfidenceLevel,
) -> None:

    if not isinstance(
        confidence,
        ConfidenceLevel,
    ):
        raise TypeError(
            "ConfidenceLevel esperado."
        )


###############################################################################

def validate_relationship_type(
    relationship_type: RelationshipType,
) -> None:

    if not isinstance(
        relationship_type,
        RelationshipType,
    ):
        raise TypeError(
            "RelationshipType esperado."
        )


###############################################################################
# RELATIONSHIP METADATA
###############################################################################

@dataclass(slots=True)
class RelationshipMetadata:
    """
    Información descriptiva asociada a una relación.

    Una relación posee su propia metadata independiente
    de los activos que conecta.
    """

    ###########################################################################
    # IDENTIDAD
    ###########################################################################

    uuid: str = field(
        default_factory=_relationship_uuid
    )

    ###########################################################################
    # PESO
    ###########################################################################

    weight: float = DEFAULT_WEIGHT

    confidence: ConfidenceLevel = DEFAULT_CONFIDENCE

    ###########################################################################
    # DOCUMENTACIÓN
    ###########################################################################

    summary: str = ""

    description: str = ""

    notes: List[str] = field(
        default_factory=list
    )

    ###########################################################################
    # METADATA GENERAL
    ###########################################################################

    metadata: Metadata = field(
        default_factory=_empty_metadata
    )

    references: ReferenceCollection = field(
        default_factory=_empty_references
    )

    custom_fields: MutableMapping[
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

    created_at: datetime = field(
        default_factory=_now
    )

    updated_at: datetime = field(
        default_factory=_now
    )

    ###########################################################################
    # VALIDACIÓN
    ###########################################################################

    def __post_init__(
        self,
    ) -> None:

        validate_weight(
            self.weight
        )

        validate_confidence(
            self.confidence
        )

        self.summary = _normalize_text(
            self.summary
        )

        self.description = _normalize_text(
            self.description
        )

    ###########################################################################

    def touch(
        self,
    ) -> None:
        """
        Actualiza la fecha de modificación.
        """

        self.updated_at = _now()

    ###########################################################################

    def add_note(
        self,
        note: str,
    ) -> None:

        note = _normalize_text(
            note
        )

        if note:

            self.notes.append(
                note
            )

            self.touch()

    ###########################################################################

    def set_weight(
        self,
        value: float,
    ) -> None:

        validate_weight(
            value
        )

        self.weight = value

        self.touch()

    ###########################################################################

    def set_confidence(
        self,
        confidence: ConfidenceLevel,
    ) -> None:

        validate_confidence(
            confidence
        )

        self.confidence = confidence

        self.touch()

    ###########################################################################

    def to_dict(
        self,
    ) -> JSONDict:

        return {

            "uuid": self.uuid,

            "weight": self.weight,

            "confidence": self.confidence.name,

            "summary": self.summary,

            "description": self.description,

            "notes": list(self.notes),

            "metadata": self.metadata.to_dict(),

            "references": self.references.to_dict(),

            "custom_fields": dict(
                self.custom_fields
            ),

            "created_by": self.created_by,

            "updated_by": self.updated_by,

            "created_at": self.created_at.isoformat(),

            "updated_at": self.updated_at.isoformat(),

        }

    ###########################################################################

    def clone(
        self,
    ) -> "RelationshipMetadata":

        return RelationshipMetadata(

            weight=self.weight,

            confidence=self.confidence,

            summary=self.summary,

            description=self.description,

            notes=list(
                self.notes
            ),

            metadata=self.metadata,

            references=self.references,

            custom_fields=dict(
                self.custom_fields
            ),

            created_by=self.created_by,

            updated_by=self.updated_by,

        )
        ###############################################################################
# RELATIONSHIP
###############################################################################

@dataclass(slots=True)
class Relationship(
    BaseEntity,
):
    """
    Relación dirigida entre dos activos de conocimiento.

    Representa una arista del Knowledge Graph.

        source -------- relationship_type --------> target

    Ejemplo:

        Curso Python ----requires----> Variables

    Las relaciones son entidades de primer nivel y poseen identidad,
    auditoría, metadata y ciclo de vida propios.
    """

    ###########################################################################
    # IDENTIDAD
    ###########################################################################

    identifier: RelationshipID

    ###########################################################################
    # NODOS
    ###########################################################################

    source: KnowledgeAsset

    target: KnowledgeAsset

    ###########################################################################
    # TIPO
    ###########################################################################

    relationship_type: RelationshipType

    ###########################################################################
    # METADATA
    ###########################################################################

    metadata: RelationshipMetadata = field(
        default_factory=RelationshipMetadata
    )

    ###########################################################################
    # ESTADO
    ###########################################################################

    active: bool = True

    deleted: bool = False

    locked: bool = False

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
    # VALIDACIÓN
    ###########################################################################

    def __post_init__(
        self,
    ) -> None:

        validate_asset(
            self.source
        )

        validate_asset(
            self.target
        )

        validate_relationship_type(
            self.relationship_type
        )

        if (
            self.source.identifier
            ==
            self.target.identifier
        ):
            raise ValueError(
                "Una relación no puede apuntar al mismo activo."
            )

    ###########################################################################
    # PROPIEDADES
    ###########################################################################

    @property
    def id(
        self,
    ) -> str:

        return str(
            self.identifier
        )

    ###########################################################################

    @property
    def weight(
        self,
    ) -> float:

        return self.metadata.weight

    ###########################################################################

    @property
    def confidence(
        self,
    ) -> ConfidenceLevel:

        return self.metadata.confidence

    ###########################################################################
    # ESTADO
    ###########################################################################

    def touch(
        self,
    ) -> None:

        self.updated_at = _now()

        self.metadata.touch()

    ###########################################################################

    def activate(
        self,
    ) -> None:

        self.active = True

        self.touch()

    ###########################################################################

    def deactivate(
        self,
    ) -> None:

        self.active = False

        self.touch()

    ###########################################################################

    def delete(
        self,
    ) -> None:

        self.deleted = True

        self.touch()

    ###########################################################################

    def restore(
        self,
    ) -> None:

        self.deleted = False

        self.touch()

    ###########################################################################

    def lock(
        self,
    ) -> None:

        self.locked = True

        self.touch()

    ###########################################################################

    def unlock(
        self,
    ) -> None:

        self.locked = False

        self.touch()

    ###########################################################################
    # VERSIONADO
    ###########################################################################

    def new_revision(
        self,
    ) -> None:

        self.revision += 1

        self.touch()

    ###########################################################################

    def new_minor_version(
        self,
    ) -> None:

        major, minor, patch = map(
            int,
            self.version.split("."),
        )

        minor += 1

        patch = 0

        self.version = (
            f"{major}.{minor}.{patch}"
        )

        self.new_revision()

    ###########################################################################

    def new_major_version(
        self,
    ) -> None:

        major, minor, patch = map(
            int,
            self.version.split("."),
        )

        major += 1

        minor = 0

        patch = 0

        self.version = (
            f"{major}.{minor}.{patch}"
        )

        self.new_revision()

    ###########################################################################
    # CONSULTAS
    ###########################################################################

    def involves(
        self,
        asset: KnowledgeAsset,
    ) -> bool:

        return (

            asset.identifier
            ==
            self.source.identifier

            or

            asset.identifier
            ==
            self.target.identifier

        )

    ###########################################################################

    def is_between(
        self,
        source: KnowledgeAsset,
        target: KnowledgeAsset,
    ) -> bool:

        return (

            self.source.identifier
            ==
            source.identifier

            and

            self.target.identifier
            ==
            target.identifier

        )

    ###########################################################################

    def other(
        self,
        asset: KnowledgeAsset,
    ) -> KnowledgeAsset:

        if (
            asset.identifier
            ==
            self.source.identifier
        ):
            return self.target

        if (
            asset.identifier
            ==
            self.target.identifier
        ):
            return self.source

        raise ValueError(
            "El activo no pertenece a esta relación."
        )

    ###########################################################################
    # SERIALIZACIÓN
    ###########################################################################

    def to_dict(
        self,
    ) -> JSONDict:

        return {

            "identifier":
            str(
                self.identifier
            ),

            "relationship_type":
            self.relationship_type.name,

            "source":
            str(
                self.source.identifier
            ),

            "target":
            str(
                self.target.identifier
            ),

            "active":
            self.active,

            "deleted":
            self.deleted,

            "locked":
            self.locked,

            "version":
            self.version,

            "revision":
            self.revision,

            "metadata":
            self.metadata.to_dict(),

            "created_at":
            self.created_at.isoformat(),

            "updated_at":
            self.updated_at.isoformat(),

        }

    ###########################################################################

    def __hash__(
        self,
    ) -> int:

        return hash(
            self.identifier
        )

    ###########################################################################

    def __repr__(
        self,
    ) -> str:

        return (

            f"{type(self).__name__}("
            f"{self.source.title!r} "
            f"-[{self.relationship_type.name}]-> "
            f"{self.target.title!r})"

        )
        ###############################################################################
# RELATIONSHIP COLLECTION
###############################################################################


class RelationshipCollection:
    """
    Colección enriquecida de relaciones.

    Proporciona:

        • almacenamiento
        • consultas
        • filtros
        • estadísticas
        • agrupaciones
        • exportación

    Es la estructura utilizada posteriormente por graph.py.
    """

    ###########################################################################
    # CONSTRUCTOR
    ###########################################################################

    def __init__(
        self,
        relationships: Optional[
            Iterable[
                Relationship
            ]
        ] = None,
    ) -> None:

        self._relationships: Dict[
            str,
            Relationship,
        ] = {}

        if relationships:

            for relationship in relationships:

                self.add(
                    relationship
                )

    ###########################################################################
    # ITERACIÓN
    ###########################################################################

    def __iter__(
        self,
    ) -> RelationshipIterator:

        return iter(
            self._relationships.values()
        )

    ###########################################################################

    def __len__(
        self,
    ) -> int:

        return len(
            self._relationships
        )

    ###########################################################################

    def __contains__(
        self,
        identifier: str,
    ) -> bool:

        return (
            identifier
            in self._relationships
        )

    ###########################################################################
    # CRUD
    ###########################################################################

    def add(
        self,
        relationship: Relationship,
    ) -> None:

        self._relationships[
            str(
                relationship.identifier
            )
        ] = relationship

    ###########################################################################

    def remove(
        self,
        identifier: str,
    ) -> bool:

        if identifier not in self:

            return False

        del self._relationships[
            identifier
        ]

        return True

    ###########################################################################

    def clear(
        self,
    ) -> None:

        self._relationships.clear()

    ###########################################################################

    def get(
        self,
        identifier: str,
    ) -> Optional[
        Relationship
    ]:

        return self._relationships.get(
            identifier
        )

    ###########################################################################
    # EXPORTACIÓN
    ###########################################################################

    def values(
        self,
    ) -> RelationshipList:

        return list(
            self._relationships.values()
        )

    ###########################################################################

    def identifiers(
        self,
    ) -> List[
        str
    ]:

        return list(
            self._relationships.keys()
        )

    ###########################################################################

    def to_list(
        self,
    ) -> List[
        JSONDict
    ]:

        return [

            relationship.to_dict()

            for relationship

            in self

        ]

    ###########################################################################
    # CONSULTAS
    ###########################################################################

    def active(
        self,
    ) -> "RelationshipCollection":

        return self.filter(

            lambda relationship:
            relationship.active

        )

    ###########################################################################

    def deleted(
        self,
    ) -> "RelationshipCollection":

        return self.filter(

            lambda relationship:
            relationship.deleted

        )

    ###########################################################################

    def locked(
        self,
    ) -> "RelationshipCollection":

        return self.filter(

            lambda relationship:
            relationship.locked

        )

    ###########################################################################

    def by_type(
        self,
        relationship_type: RelationshipType,
    ) -> "RelationshipCollection":

        return self.filter(

            lambda relationship:

            relationship.relationship_type

            ==

            relationship_type

        )

    ###########################################################################

    def from_asset(
        self,
        asset: KnowledgeAsset,
    ) -> "RelationshipCollection":

        return self.filter(

            lambda relationship:

            relationship.source.identifier

            ==

            asset.identifier

        )

    ###########################################################################

    def to_asset(
        self,
        asset: KnowledgeAsset,
    ) -> "RelationshipCollection":

        return self.filter(

            lambda relationship:

            relationship.target.identifier

            ==

            asset.identifier

        )

    ###########################################################################

    def involving(
        self,
        asset: KnowledgeAsset,
    ) -> "RelationshipCollection":

        return self.filter(

            lambda relationship:

            relationship.involves(
                asset
            )

        )

    ###########################################################################
    # FILTRADO
    ###########################################################################

    def filter(
        self,
        predicate,
    ) -> "RelationshipCollection":

        return RelationshipCollection(

            relationship

            for relationship

            in self

            if predicate(
                relationship
            )

        )

    ###########################################################################
    # AGRUPACIONES
    ###########################################################################

    def group_by_type(
        self,
    ) -> Dict[
        RelationshipType,
        "RelationshipCollection",
    ]:

        groups = {}

        for relationship in self:

            groups.setdefault(

                relationship.relationship_type,

                RelationshipCollection(),

            ).add(

                relationship

            )

        return groups

    ###########################################################################
    # ESTADÍSTICAS
    ###########################################################################

    def statistics(
        self,
    ) -> JSONDict:

        return {

            "total_relationships": len(
                self
            ),

            "active": len(
                self.active()
            ),

            "deleted": len(
                self.deleted()
            ),

            "locked": len(
                self.locked()
            ),

            "types": {

                relationship_type.name: len(
                    collection
                )

                for relationship_type, collection

                in self.group_by_type().items()

            },

        }

    ###########################################################################
    # VALIDACIÓN
    ###########################################################################

    def validation_errors(
        self,
    ) -> RelationshipErrors:

        errors: RelationshipErrors = []

        identifiers = set()

        for relationship in self:

            identifier = str(
                relationship.identifier
            )

            if identifier in identifiers:

                errors.append(

                    f"Relationship duplicada: {identifier}"

                )

            identifiers.add(
                identifier
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
        other: "RelationshipCollection",
    ) -> "RelationshipCollection":

        result = RelationshipCollection(
            self
        )

        for relationship in other:

            if (
                str(
                    relationship.identifier
                )
                not in result
            ):

                result.add(
                    relationship
                )

        return result

    ###########################################################################

    def intersection(
        self,
        other: "RelationshipCollection",
    ) -> "RelationshipCollection":

        return RelationshipCollection(

            relationship

            for relationship

            in self

            if (
                str(
                    relationship.identifier
                )
                in other
            )

        )

    ###########################################################################

    def difference(
        self,
        other: "RelationshipCollection",
    ) -> "RelationshipCollection":

        return RelationshipCollection(

            relationship

            for relationship

            in self

            if (
                str(
                    relationship.identifier
                )
                not in other
            )

        )

    ###########################################################################

    def clone(
        self,
    ) -> "RelationshipCollection":

        return RelationshipCollection(

            self.values()

        )
        ###############################################################################
# RELATIONSHIP INDEX
###############################################################################


class RelationshipIndex:
    """
    Índices hash para acelerar consultas sobre relaciones.

    Mantiene múltiples estructuras O(1) evitando recorrer toda la
    colección para búsquedas frecuentes.

    Esta clase constituye la base de graph.py.
    """

    ###########################################################################
    # CONSTRUCTOR
    ###########################################################################

    def __init__(
        self,
        relationships: Optional[
            Iterable[
                Relationship
            ]
        ] = None,
    ) -> None:

        self.clear()

        if relationships:

            self.build(
                relationships
            )

    ###########################################################################
    # LIMPIEZA
    ###########################################################################

    def clear(
        self,
    ) -> None:

        #######################################################################
        # IDENTIFICADOR
        #######################################################################

        self.by_identifier: Dict[
            str,
            Relationship,
        ] = {}

        #######################################################################
        # ORIGEN
        #######################################################################

        self.by_source: Dict[
            str,
            RelationshipCollection,
        ] = {}

        #######################################################################
        # DESTINO
        #######################################################################

        self.by_target: Dict[
            str,
            RelationshipCollection,
        ] = {}

        #######################################################################
        # TIPO
        #######################################################################

        self.by_type: Dict[
            RelationshipType,
            RelationshipCollection,
        ] = {}

        #######################################################################
        # ADYACENCIA
        #######################################################################

        self.outgoing: Dict[
            str,
            RelationshipCollection,
        ] = {}

        self.incoming: Dict[
            str,
            RelationshipCollection,
        ] = {}

    ###########################################################################
    # BUILD
    ###########################################################################

    def build(
        self,
        relationships: Iterable[
            Relationship
        ],
    ) -> None:

        self.clear()

        for relationship in relationships:

            self.add(
                relationship
            )

    ###########################################################################
    # INSERCIÓN
    ###########################################################################

    def add(
        self,
        relationship: Relationship,
    ) -> None:

        rid = str(
            relationship.identifier
        )

        source = str(
            relationship.source.identifier
        )

        target = str(
            relationship.target.identifier
        )

        #######################################################################
        # IDENTIFIER
        #######################################################################

        self.by_identifier[
            rid
        ] = relationship

        #######################################################################
        # SOURCE
        #######################################################################

        self.by_source.setdefault(

            source,

            RelationshipCollection(),

        ).add(

            relationship

        )

        #######################################################################
        # TARGET
        #######################################################################

        self.by_target.setdefault(

            target,

            RelationshipCollection(),

        ).add(

            relationship

        )

        #######################################################################
        # TYPE
        #######################################################################

        self.by_type.setdefault(

            relationship.relationship_type,

            RelationshipCollection(),

        ).add(

            relationship

        )

        #######################################################################
        # ADJACENCY
        #######################################################################

        self.outgoing.setdefault(

            source,

            RelationshipCollection(),

        ).add(

            relationship

        )

        self.incoming.setdefault(

            target,

            RelationshipCollection(),

        ).add(

            relationship

        )

    ###########################################################################
    # IDENTIFIER
    ###########################################################################

    def get(
        self,
        identifier: str,
    ) -> Optional[
        Relationship
    ]:

        return self.by_identifier.get(
            identifier
        )

    ###########################################################################
    # SOURCE
    ###########################################################################

    def source(
        self,
        asset: KnowledgeAsset,
    ) -> RelationshipCollection:

        return self.by_source.get(

            str(
                asset.identifier
            ),

            RelationshipCollection(),

        )

    ###########################################################################
    # TARGET
    ###########################################################################

    def target(
        self,
        asset: KnowledgeAsset,
    ) -> RelationshipCollection:

        return self.by_target.get(

            str(
                asset.identifier
            ),

            RelationshipCollection(),

        )

    ###########################################################################
    # TYPE
    ###########################################################################

    def relationship_type(
        self,
        relationship_type: RelationshipType,
    ) -> RelationshipCollection:

        return self.by_type.get(

            relationship_type,

            RelationshipCollection(),

        )

    ###########################################################################
    # OUTGOING
    ###########################################################################

    def outgoing_edges(
        self,
        asset: KnowledgeAsset,
    ) -> RelationshipCollection:

        return self.outgoing.get(

            str(
                asset.identifier
            ),

            RelationshipCollection(),

        )

    ###########################################################################
    # INCOMING
    ###########################################################################

    def incoming_edges(
        self,
        asset: KnowledgeAsset,
    ) -> RelationshipCollection:

        return self.incoming.get(

            str(
                asset.identifier
            ),

            RelationshipCollection(),

        )

    ###########################################################################
    # NEIGHBORS
    ###########################################################################

    def successors(
        self,
        asset: KnowledgeAsset,
    ) -> KnowledgeCollection:
        """
        Nodos alcanzables desde este activo.
        """

        nodes = KnowledgeCollection()

        for relationship in self.outgoing_edges(
            asset
        ):

            nodes.add(
                relationship.target
            )

        return nodes

    ###########################################################################

    def predecessors(
        self,
        asset: KnowledgeAsset,
    ) -> KnowledgeCollection:
        """
        Nodos que llegan hasta este activo.
        """

        nodes = KnowledgeCollection()

        for relationship in self.incoming_edges(
            asset
        ):

            nodes.add(
                relationship.source
            )

        return nodes

    ###########################################################################
    # GRADO
    ###########################################################################

    def out_degree(
        self,
        asset: KnowledgeAsset,
    ) -> int:

        return len(
            self.outgoing_edges(
                asset
            )
        )

    ###########################################################################

    def in_degree(
        self,
        asset: KnowledgeAsset,
    ) -> int:

        return len(
            self.incoming_edges(
                asset
            )
        )

    ###########################################################################

    def degree(
        self,
        asset: KnowledgeAsset,
    ) -> int:

        return (

            self.out_degree(
                asset
            )

            +

            self.in_degree(
                asset
            )

        )

    ###########################################################################
    # EXPORTACIÓN
    ###########################################################################

    def statistics(
        self,
    ) -> JSONDict:

        return {

            "relationships":
                len(
                    self.by_identifier
                ),

            "source_nodes":
                len(
                    self.by_source
                ),

            "target_nodes":
                len(
                    self.by_target
                ),

            "relationship_types":
                len(
                    self.by_type
                ),

        }
        ###############################################################################
# RELATIONSHIP QUERY
###############################################################################


@dataclass(slots=True)
class RelationshipQuery:
    """
    Consulta estructurada sobre RelationshipCollection.

    Esta clase encapsula todos los filtros disponibles y permite
    construir consultas reutilizables, serializables y fácilmente
    extensibles.
    """

    ###########################################################################
    # FILTROS PRINCIPALES
    ###########################################################################

    source: Optional[
        KnowledgeAsset
    ] = None

    target: Optional[
        KnowledgeAsset
    ] = None

    relationship_type: Optional[
        RelationshipType
    ] = None

    ###########################################################################
    # METADATA
    ###########################################################################

    minimum_weight: Optional[
        float
    ] = None

    maximum_weight: Optional[
        float
    ] = None

    confidence: Optional[
        ConfidenceLevel
    ] = None

    ###########################################################################
    # ESTADO
    ###########################################################################

    active_only: bool = True

    include_deleted: bool = False

    include_locked: bool = True

    ###########################################################################
    # PAGINACIÓN
    ###########################################################################

    offset: int = 0

    limit: Optional[
        int
    ] = None

    ###########################################################################
    # EJECUCIÓN
    ###########################################################################

    def apply(
        self,
        relationships: RelationshipCollection,
    ) -> RelationshipCollection:
        """
        Ejecuta la consulta sobre una colección.
        """

        result = relationships

        #######################################################################
        # SOURCE
        #######################################################################

        if self.source is not None:

            result = result.from_asset(
                self.source
            )

        #######################################################################
        # TARGET
        #######################################################################

        if self.target is not None:

            result = result.to_asset(
                self.target
            )

        #######################################################################
        # TYPE
        #######################################################################

        if self.relationship_type is not None:

            result = result.by_type(
                self.relationship_type
            )

        #######################################################################
        # ACTIVE
        #######################################################################

        if self.active_only:

            result = result.active()

        #######################################################################
        # DELETED
        #######################################################################

        if not self.include_deleted:

            result = result.filter(

                lambda relationship:

                not relationship.deleted

            )

        #######################################################################
        # LOCKED
        #######################################################################

        if not self.include_locked:

            result = result.filter(

                lambda relationship:

                not relationship.locked

            )

        #######################################################################
        # WEIGHT
        #######################################################################

        if self.minimum_weight is not None:

            result = result.filter(

                lambda relationship:

                relationship.weight

                >=

                self.minimum_weight

            )

        if self.maximum_weight is not None:

            result = result.filter(

                lambda relationship:

                relationship.weight

                <=

                self.maximum_weight

            )

        #######################################################################
        # CONFIDENCE
        #######################################################################

        if self.confidence is not None:

            result = result.filter(

                lambda relationship:

                relationship.confidence

                ==

                self.confidence

            )

        #######################################################################
        # PAGINACIÓN
        #######################################################################

        relationships_list = result.values()

        if self.offset:

            relationships_list = relationships_list[
                self.offset:
            ]

        if self.limit is not None:

            relationships_list = relationships_list[
                :self.limit
            ]

        return RelationshipCollection(
            relationships_list
        )

    ###########################################################################
    # SERIALIZACIÓN
    ###########################################################################

    def to_dict(
        self,
    ) -> JSONDict:

        return {

            "source":

                str(self.source.identifier)

                if self.source

                else None,

            "target":

                str(self.target.identifier)

                if self.target

                else None,

            "relationship_type":

                self.relationship_type.name

                if self.relationship_type

                else None,

            "minimum_weight":

                self.minimum_weight,

            "maximum_weight":

                self.maximum_weight,

            "confidence":

                self.confidence.name

                if self.confidence

                else None,

            "active_only":

                self.active_only,

            "include_deleted":

                self.include_deleted,

            "include_locked":

                self.include_locked,

            "offset":

                self.offset,

            "limit":

                self.limit,

        }

    ###########################################################################

    def clone(
        self,
    ) -> "RelationshipQuery":

        return RelationshipQuery(

            source=self.source,

            target=self.target,

            relationship_type=self.relationship_type,

            minimum_weight=self.minimum_weight,

            maximum_weight=self.maximum_weight,

            confidence=self.confidence,

            active_only=self.active_only,

            include_deleted=self.include_deleted,

            include_locked=self.include_locked,

            offset=self.offset,

            limit=self.limit,

        )

    ###########################################################################

    def __repr__(
        self,
    ) -> str:

        return (

            f"{type(self).__name__}("

            f"type={self.relationship_type}, "

            f"active_only={self.active_only}, "

            f"limit={self.limit})"

        )
        ###############################################################################
# RELATIONSHIP SEARCH RESULT
###############################################################################


@dataclass(slots=True)
class RelationshipSearchResult:
    """
    Resultado enriquecido de una búsqueda de relaciones.

    Además de la relación encontrada almacena información útil para
    motores de búsqueda, ranking y Graph.
    """

    ###########################################################################
    # RELACIÓN
    ###########################################################################

    relationship: Relationship

    ###########################################################################
    # SCORE
    ###########################################################################

    score: float = 1.0

    ###########################################################################
    # INFORMACIÓN DE COINCIDENCIA
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
    # PROPIEDADES
    ###########################################################################

    @property
    def source(
        self,
    ) -> KnowledgeAsset:

        return self.relationship.source

    ###########################################################################

    @property
    def target(
        self,
    ) -> KnowledgeAsset:

        return self.relationship.target

    ###########################################################################

    @property
    def relationship_type(
        self,
    ) -> RelationshipType:

        return self.relationship.relationship_type

    ###########################################################################

    @property
    def weight(
        self,
    ) -> float:

        return self.relationship.weight

    ###########################################################################

    @property
    def confidence(
        self,
    ) -> ConfidenceLevel:

        return self.relationship.confidence

    ###########################################################################
    # MATCHES
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
    # SERIALIZACIÓN
    ###########################################################################

    def to_dict(
        self,
    ) -> JSONDict:

        return {

            "score":
                self.score,

            "relationship":
                self.relationship.to_dict(),

            "source":
                self.source.title,

            "target":
                self.target.title,

            "relationship_type":
                self.relationship_type.name,

            "weight":
                self.weight,

            "confidence":
                self.confidence.name,

            "matched_fields":
                list(self.matched_fields),

            "matched_terms":
                list(self.matched_terms),

            "explanation":
                self.explanation,

        }

    ###########################################################################

    def clone(
        self,
    ) -> "RelationshipSearchResult":

        return RelationshipSearchResult(

            relationship=self.relationship,

            score=self.score,

            matched_fields=list(
                self.matched_fields
            ),

            matched_terms=list(
                self.matched_terms
            ),

            explanation=self.explanation,

        )

    ###########################################################################

    def __lt__(
        self,
        other: "RelationshipSearchResult",
    ) -> bool:

        return self.score < other.score

    ###########################################################################

    def __repr__(
        self,
    ) -> str:

        return (

            f"{type(self).__name__}("

            f"{self.source.title!r}"

            f" -> "

            f"{self.target.title!r}, "

            f"score={self.score:.3f})"

        )
        ###############################################################################
# MODULE UTILITIES
###############################################################################


def relationship_from_dict(
    data: Mapping[
        str,
        Any,
    ],
    *,
    asset_lookup: Mapping[
        str,
        KnowledgeAsset,
    ],
) -> Relationship:
    """
    Construye una Relationship a partir de un diccionario.

    asset_lookup:
        Diccionario identifier -> KnowledgeAsset
        utilizado para reconstruir los extremos de la relación.
    """

    source_id = data["source"]
    target_id = data["target"]

    try:

        source = asset_lookup[source_id]
        target = asset_lookup[target_id]

    except KeyError as exc:

        raise KeyError(

            f"KnowledgeAsset no encontrado: {exc}"

        ) from exc

    metadata = RelationshipMetadata()

    metadata.weight = data.get(
        "metadata",
        {},
    ).get(
        "weight",
        DEFAULT_WEIGHT,
    )

    metadata.summary = data.get(
        "metadata",
        {},
    ).get(
        "summary",
        "",
    )

    metadata.description = data.get(
        "metadata",
        {},
    ).get(
        "description",
        "",
    )

    relationship = Relationship(

        identifier=DomainIdentifier.parse(
            data["identifier"]
        ),

        source=source,

        target=target,

        relationship_type=RelationshipType[
            data["relationship_type"]
        ],

        metadata=metadata,

        active=data.get(
            "active",
            True,
        ),

        deleted=data.get(
            "deleted",
            False,
        ),

        locked=data.get(
            "locked",
            False,
        ),

        version=data.get(
            "version",
            "1.0.0",
        ),

        revision=data.get(
            "revision",
            1,
        ),

    )

    return relationship


###############################################################################


def relationship_collection_from_relationships(
    relationships: Iterable[
        Relationship,
    ],
) -> RelationshipCollection:
    """
    Construye una colección desde un iterable.
    """

    return RelationshipCollection(
        relationships
    )


###############################################################################


def relationship_collection_from_dicts(
    items: Iterable[
        Mapping[
            str,
            Any,
        ]
    ],
    *,
    asset_lookup: Mapping[
        str,
        KnowledgeAsset,
    ],
) -> RelationshipCollection:
    """
    Construye una colección desde diccionarios.
    """

    collection = RelationshipCollection()

    for item in items:

        collection.add(

            relationship_from_dict(

                item,

                asset_lookup=asset_lookup,

            )

        )

    return collection


###############################################################################


def merge_relationships(
    *collections: RelationshipCollection,
) -> RelationshipCollection:
    """
    Une múltiples colecciones eliminando duplicados.
    """

    merged = RelationshipCollection()

    for collection in collections:

        for relationship in collection:

            identifier = str(
                relationship.identifier
            )

            if identifier not in merged:

                merged.add(
                    relationship
                )

    return merged


###############################################################################


def validate_relationships(
    relationships: RelationshipCollection,
) -> None:
    """
    Punto de entrada uniforme para validar colecciones.
    """

    relationships.validate()


###############################################################################


def build_relationship_index(
    relationships: RelationshipCollection,
) -> RelationshipIndex:
    """
    Construye un índice optimizado.
    """

    return RelationshipIndex(
        relationships
    )


###############################################################################


def execute_relationship_query(
    relationships: RelationshipCollection,
    query: RelationshipQuery,
) -> RelationshipCollection:
    """
    Ejecuta una consulta estructurada.
    """

    return query.apply(
        relationships
    )


###############################################################################


def search_relationships(
    relationships: RelationshipCollection,
    query: str,
) -> List[
    RelationshipSearchResult,
]:
    """
    Motor básico de búsqueda textual.

    Diseñado para ser reemplazado posteriormente por
    BM25, embeddings, búsqueda híbrida o GraphRAG.
    """

    query = query.casefold().strip()

    results: List[
        RelationshipSearchResult
    ] = []

    for relationship in relationships:

        score = 0.0

        result = RelationshipSearchResult(
            relationship=relationship
        )

        ###############################################################
        # TYPE
        ###############################################################

        relation_name = (

            relationship.relationship_type.name

            .casefold()

        )

        if query in relation_name:

            score += 10

            result.add_match(

                "relationship_type",

                query,

            )

        ###############################################################
        # SOURCE
        ###############################################################

        if query in relationship.source.title.casefold():

            score += 5

            result.add_match(

                "source",

                query,

            )

        ###############################################################
        # TARGET
        ###############################################################

        if query in relationship.target.title.casefold():

            score += 5

            result.add_match(

                "target",

                query,

            )

        ###############################################################
        # SUMMARY
        ###############################################################

        if (

            relationship.metadata.summary

            and

            query

            in

            relationship.metadata.summary.casefold()

        ):

            score += 2

            result.add_match(

                "summary",

                query,

            )

        ###############################################################
        # DESCRIPTION
        ###############################################################

        if (

            relationship.metadata.description

            and

            query

            in

            relationship.metadata.description.casefold()

        ):

            score += 1

            result.add_match(

                "description",

                query,

            )

        if score > 0:

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

MODULE_NAME = "knowledge_assets.relationships"

MODULE_VERSION = "1.0.0"

###############################################################################

SUPPORTED_EXPORT_FORMATS = (

    "dict",

    "json",

)

###############################################################################

SUPPORTED_SEARCH_FIELDS = (

    "relationship_type",

    "source",

    "target",

    "summary",

    "description",

)

###############################################################################

DEFAULT_SEARCH_LIMIT = 100

###############################################################################

MAX_RELATIONSHIP_WEIGHT = float("inf")

MIN_RELATIONSHIP_WEIGHT = 0.0

###############################################################################

GRAPH_READY = True

###############################################################################
# MODULE HELPERS
###############################################################################

def empty_relationship_collection(
) -> RelationshipCollection:
    """
    Devuelve una colección vacía.

    Se expone como API pública para mantener
    consistencia con otros módulos.
    """

    return RelationshipCollection()


###############################################################################

def empty_relationship_index(
) -> RelationshipIndex:
    """
    Devuelve un índice vacío.
    """

    return RelationshipIndex()


###############################################################################

def empty_relationship_query(
) -> RelationshipQuery:
    """
    Consulta vacía.
    """

    return RelationshipQuery()


###############################################################################

def relationship_statistics(
    relationships: RelationshipCollection,
) -> JSONDict:
    """
    Alias público de statistics().
    """

    return relationships.statistics()


###############################################################################

def relationship_count(
    relationships: RelationshipCollection,
) -> int:

    return len(
        relationships
    )


###############################################################################

def active_relationship_count(
    relationships: RelationshipCollection,
) -> int:

    return len(

        relationships.active()

    )


###############################################################################

def deleted_relationship_count(
    relationships: RelationshipCollection,
) -> int:

    return len(

        relationships.deleted()

    )


###############################################################################

def locked_relationship_count(
    relationships: RelationshipCollection,
) -> int:

    return len(

        relationships.locked()

    )


###############################################################################

def relationship_types(
    relationships: RelationshipCollection,
) -> Set[
    RelationshipType,
]:
    """
    Devuelve todos los tipos de relación presentes.
    """

    return {

        relationship.relationship_type

        for relationship

        in relationships

    }


###############################################################################

def relationship_nodes(
    relationships: RelationshipCollection,
) -> KnowledgeCollection:
    """
    Devuelve todos los KnowledgeAssets involucrados.
    """

    nodes = KnowledgeCollection()

    for relationship in relationships:

        nodes.add(
            relationship.source
        )

        nodes.add(
            relationship.target
        )

    return nodes


###############################################################################
# PUBLIC EXPORTS
###############################################################################

__all__ = [

    ###########################################################################
    # METADATA
    ###########################################################################

    "RelationshipMetadata",

    ###########################################################################
    # DOMAIN
    ###########################################################################

    "Relationship",

    "RelationshipCollection",

    "RelationshipIndex",

    "RelationshipQuery",

    "RelationshipSearchResult",

    ###########################################################################
    # BUILDERS
    ###########################################################################

    "relationship_from_dict",

    "relationship_collection_from_relationships",

    "relationship_collection_from_dicts",

    ###########################################################################
    # HELPERS
    ###########################################################################

    "build_relationship_index",

    "execute_relationship_query",

    "merge_relationships",

    "search_relationships",

    "validate_relationships",

    "relationship_statistics",

    "relationship_nodes",

    "relationship_count",

    "active_relationship_count",

    "deleted_relationship_count",

    "locked_relationship_count",

    "relationship_types",

    "empty_relationship_collection",

    "empty_relationship_index",

    "empty_relationship_query",

    ###########################################################################
    # TYPE ALIASES
    ###########################################################################

    "RelationshipID",

    "RelationshipList",

    "RelationshipMap",

    "RelationshipSet",

    "RelationshipIterator",

    "RelationshipErrors",

    ###########################################################################
    # CONSTANTS
    ###########################################################################

    "MODULE_NAME",

    "MODULE_VERSION",

    "SUPPORTED_EXPORT_FORMATS",

    "SUPPORTED_SEARCH_FIELDS",

    "DEFAULT_SEARCH_LIMIT",

    "MAX_RELATIONSHIP_WEIGHT",

    "MIN_RELATIONSHIP_WEIGHT",

    "GRAPH_READY",

]