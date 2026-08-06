"""
===============================================================================
CIPS - Consejo de Inteligencia para Producción de Soluciones
Knowledge Assets Domain
-------------------------------------------------------------------------------

Archivo:
    identifiers.py

Descripción:
    Define políticas, validadores y objetos de valor para la generación,
    normalización, análisis y administración de identificadores dentro del
    dominio Knowledge Assets.

Versión:
    1.0.0
===============================================================================
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from typing import Any, ClassVar, Dict, Iterable, List, Mapping, Optional, Set

from .base import (
    JSONDict,
    ValidationErrors,
    ValueObject,
    generate_identifier,
    require_non_empty_string,
)

DEFAULT_SEPARATOR: str = "_"
DEFAULT_RANDOM_LENGTH: int = 32
MIN_RANDOM_LENGTH: int = 8
MAX_RANDOM_LENGTH: int = 64
DEFAULT_NAMESPACE: str = "cips"

IDENTIFIER_PATTERN = re.compile(
    r"^(?P<prefix>[a-z][a-z0-9]*(?:_[a-z0-9]+)*)_"
    r"(?P<value>[a-f0-9]{8,64})$"
)
PREFIX_PATTERN = re.compile(r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$")
NAMESPACE_PATTERN = re.compile(r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$")


class IdentifierPrefix:
    """Catálogo central de prefijos utilizados por CIPS."""

    KNOWLEDGE_ASSET: ClassVar[str] = "ka"
    KNOWLEDGE_REFERENCE: ClassVar[str] = "ref"
    CITATION: ClassVar[str] = "cit"
    EVIDENCE: ClassVar[str] = "evd"
    RELATIONSHIP: ClassVar[str] = "rel"
    GRAPH: ClassVar[str] = "graph"
    GRAPH_NODE: ClassVar[str] = "node"
    GRAPH_EDGE: ClassVar[str] = "edge"
    METADATA: ClassVar[str] = "meta"
    CONTENT_ASSET: ClassVar[str] = "content"
    RESEARCH_PACKAGE: ClassVar[str] = "research"
    STRATEGY_PACKAGE: ClassVar[str] = "strategy"
    CONTENT_PLAN: ClassVar[str] = "plan"
    PLANNING_SESSION: ClassVar[str] = "session"
    VALIDATION_REPORT: ClassVar[str] = "validation"
    SERIALIZATION_PACKAGE: ClassVar[str] = "serialization"
    FACTORY_REQUEST: ClassVar[str] = "factory"

    @classmethod
    def values(cls) -> List[str]:
        return [
            value
            for name, value in vars(cls).items()
            if name.isupper() and isinstance(value, str) and not name.startswith("_")
        ]

    @classmethod
    def contains(cls, prefix: str) -> bool:
        try:
            normalized = normalize_prefix(prefix)
        except (TypeError, ValueError):
            return False
        return normalized in cls.values()


def normalize_prefix(prefix: str) -> str:
    if not isinstance(prefix, str):
        raise TypeError(
            "prefix debe ser str; "
            f"se recibió {type(prefix).__name__}."
        )
    normalized = prefix.strip().lower()
    normalized = re.sub(r"[\s-]+", DEFAULT_SEPARATOR, normalized)
    normalized = re.sub(r"_+", DEFAULT_SEPARATOR, normalized)
    normalized = normalized.strip(DEFAULT_SEPARATOR)
    if not normalized:
        raise ValueError("prefix no puede estar vacío.")
    if not PREFIX_PATTERN.fullmatch(normalized):
        raise ValueError(
            "prefix debe comenzar con una letra y contener únicamente "
            "letras minúsculas, números y guiones bajos."
        )
    return normalized


def normalize_namespace(namespace: str) -> str:
    if not isinstance(namespace, str):
        raise TypeError(
            "namespace debe ser str; "
            f"se recibió {type(namespace).__name__}."
        )
    normalized = namespace.strip().lower()
    normalized = re.sub(r"\s+", "-", normalized)
    normalized = re.sub(r"[-_.]+", "-", normalized)
    normalized = normalized.strip("-")
    if not normalized:
        raise ValueError("namespace no puede estar vacío.")
    if not NAMESPACE_PATTERN.fullmatch(normalized):
        raise ValueError("namespace contiene caracteres no permitidos.")
    return normalized


def normalize_identifier(identifier: str) -> str:
    normalized = require_non_empty_string(identifier, "identifier").lower()
    if not IDENTIFIER_PATTERN.fullmatch(normalized):
        raise ValueError(
            "identifier no cumple el formato '<prefix>_<hexadecimal>'."
        )
    return normalized


def is_valid_prefix(prefix: Any) -> bool:
    try:
        normalize_prefix(prefix)
    except (TypeError, ValueError):
        return False
    return True


def is_valid_identifier(identifier: Any) -> bool:
    if not isinstance(identifier, str):
        return False
    return IDENTIFIER_PATTERN.fullmatch(identifier.strip().lower()) is not None


def identifier_has_prefix(identifier: str, prefix: str) -> bool:
    return parse_identifier(identifier).prefix == normalize_prefix(prefix)


def generate_hex_value(length: int = DEFAULT_RANDOM_LENGTH) -> str:
    if isinstance(length, bool) or not isinstance(length, int):
        raise TypeError("length debe ser int.")
    if not MIN_RANDOM_LENGTH <= length <= MAX_RANDOM_LENGTH:
        raise ValueError(
            f"length debe estar entre {MIN_RANDOM_LENGTH} y {MAX_RANDOM_LENGTH}."
        )
    generated = ""
    while len(generated) < length:
        generated += uuid.uuid4().hex
    return generated[:length]


def create_identifier(prefix: str, *, random_length: int = DEFAULT_RANDOM_LENGTH) -> str:
    normalized_prefix = normalize_prefix(prefix)
    if random_length == DEFAULT_RANDOM_LENGTH:
        return generate_identifier(normalized_prefix)
    return f"{normalized_prefix}{DEFAULT_SEPARATOR}{generate_hex_value(random_length)}"


def create_namespaced_identifier(
    prefix: str,
    namespace: str,
    *,
    random_length: int = DEFAULT_RANDOM_LENGTH,
) -> str:
    normalized_namespace = normalize_namespace(namespace).replace("-", "_")
    normalized_prefix = normalize_prefix(prefix)
    return create_identifier(
        f"{normalized_namespace}_{normalized_prefix}",
        random_length=random_length,
    )


def create_deterministic_identifier(
    prefix: str,
    value: str,
    *,
    namespace: uuid.UUID = uuid.NAMESPACE_URL,
    random_length: int = DEFAULT_RANDOM_LENGTH,
) -> str:
    normalized_prefix = normalize_prefix(prefix)
    normalized_value = require_non_empty_string(value, "value")
    if not isinstance(namespace, uuid.UUID):
        raise TypeError("namespace debe ser uuid.UUID.")
    if isinstance(random_length, bool) or not isinstance(random_length, int):
        raise TypeError("random_length debe ser int.")
    if not MIN_RANDOM_LENGTH <= random_length <= DEFAULT_RANDOM_LENGTH:
        raise ValueError(
            f"random_length determinista debe estar entre {MIN_RANDOM_LENGTH} "
            f"y {DEFAULT_RANDOM_LENGTH}."
        )
    deterministic_value = uuid.uuid5(namespace, normalized_value).hex[:random_length]
    return f"{normalized_prefix}{DEFAULT_SEPARATOR}{deterministic_value}"


@dataclass(frozen=True)
class ParsedIdentifier(ValueObject):
    raw: str
    prefix: str
    value: str

    def __post_init__(self) -> None:
        normalized_raw = normalize_identifier(self.raw)
        normalized_prefix = normalize_prefix(self.prefix)
        normalized_value = require_non_empty_string(self.value, "value").lower()
        if not re.fullmatch(r"[a-f0-9]{8,64}", normalized_value):
            raise ValueError(
                "value debe ser una cadena hexadecimal de 8 a 64 caracteres."
            )
        expected = f"{normalized_prefix}{DEFAULT_SEPARATOR}{normalized_value}"
        if normalized_raw != expected:
            raise ValueError("raw no coincide con prefix y value.")
        object.__setattr__(self, "raw", normalized_raw)
        object.__setattr__(self, "prefix", normalized_prefix)
        object.__setattr__(self, "value", normalized_value)

    @property
    def random_length(self) -> int:
        return len(self.value)

    def validation_errors(self) -> ValidationErrors:
        errors: ValidationErrors = []
        if not is_valid_identifier(self.raw):
            errors.append("raw no es un identificador válido.")
        if not is_valid_prefix(self.prefix):
            errors.append("prefix no es válido.")
        if not re.fullmatch(r"[a-f0-9]{8,64}", self.value):
            errors.append(
                "value debe ser hexadecimal y tener entre 8 y 64 caracteres."
            )
        return errors

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ParsedIdentifier":
        if not isinstance(data, Mapping):
            raise TypeError("ParsedIdentifier.from_dict esperaba Mapping.")
        return cls(**dict(data))


def parse_identifier(identifier: str) -> ParsedIdentifier:
    normalized = normalize_identifier(identifier)
    match = IDENTIFIER_PATTERN.fullmatch(normalized)
    if match is None:
        raise ValueError("No fue posible analizar identifier.")
    return ParsedIdentifier(
        raw=normalized,
        prefix=match.group("prefix"),
        value=match.group("value"),
    )


def extract_prefix(identifier: str) -> str:
    return parse_identifier(identifier).prefix


def extract_value(identifier: str) -> str:
    return parse_identifier(identifier).value


@dataclass(frozen=True)
class DomainIdentifier(ValueObject):
    value: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", normalize_identifier(self.value))

    @property
    def prefix(self) -> str:
        return extract_prefix(self.value)

    @property
    def random_value(self) -> str:
        return extract_value(self.value)

    def has_prefix(self, prefix: str) -> bool:
        return self.prefix == normalize_prefix(prefix)

    def __str__(self) -> str:
        return self.value

    def validation_errors(self) -> ValidationErrors:
        return [] if is_valid_identifier(self.value) else [
            "value no es un identificador válido."
        ]

    @classmethod
    def new(
        cls,
        prefix: str,
        *,
        random_length: int = DEFAULT_RANDOM_LENGTH,
    ) -> "DomainIdentifier":
        return cls(create_identifier(prefix, random_length=random_length))

    @classmethod
    def deterministic(
        cls,
        prefix: str,
        source_value: str,
        *,
        namespace: uuid.UUID = uuid.NAMESPACE_URL,
        random_length: int = DEFAULT_RANDOM_LENGTH,
    ) -> "DomainIdentifier":
        return cls(
            create_deterministic_identifier(
                prefix,
                source_value,
                namespace=namespace,
                random_length=random_length,
            )
        )

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "DomainIdentifier":
        if not isinstance(data, Mapping):
            raise TypeError("DomainIdentifier.from_dict esperaba Mapping.")
        return cls(value=data["value"])


@dataclass
class IdentifierPolicy(ValueObject):
    allowed_prefixes: List[str]
    random_length: int = DEFAULT_RANDOM_LENGTH
    require_registered_prefix: bool = False

    def __post_init__(self) -> None:
        self.allowed_prefixes = normalize_prefixes(self.allowed_prefixes)
        if isinstance(self.random_length, bool) or not isinstance(self.random_length, int):
            raise TypeError("random_length debe ser int.")
        if not MIN_RANDOM_LENGTH <= self.random_length <= MAX_RANDOM_LENGTH:
            raise ValueError(
                f"random_length debe estar entre {MIN_RANDOM_LENGTH} "
                f"y {MAX_RANDOM_LENGTH}."
            )
        if not isinstance(self.require_registered_prefix, bool):
            raise TypeError("require_registered_prefix debe ser bool.")
        if self.require_registered_prefix:
            unregistered = [
                prefix
                for prefix in self.allowed_prefixes
                if not IdentifierPrefix.contains(prefix)
            ]
            if unregistered:
                raise ValueError(
                    "Prefijos no registrados: " + ", ".join(unregistered)
                )

    def permits_prefix(self, prefix: str) -> bool:
        return normalize_prefix(prefix) in self.allowed_prefixes

    def create(self, prefix: str) -> DomainIdentifier:
        normalized = normalize_prefix(prefix)
        if not self.permits_prefix(normalized):
            raise ValueError(f"El prefijo {normalized!r} no está permitido.")
        return DomainIdentifier.new(normalized, random_length=self.random_length)

    def validate_identifier(self, identifier: str) -> ValidationErrors:
        if not is_valid_identifier(identifier):
            return ["identifier no cumple el formato CIPS."]
        errors: ValidationErrors = []
        parsed = parse_identifier(identifier)
        if not self.permits_prefix(parsed.prefix):
            errors.append(f"El prefijo {parsed.prefix!r} no está permitido.")
        if parsed.random_length != self.random_length:
            errors.append(
                "La longitud hexadecimal no coincide con la política: "
                f"esperada={self.random_length}, recibida={parsed.random_length}."
            )
        return errors

    def validation_errors(self) -> ValidationErrors:
        errors: ValidationErrors = []
        if not self.allowed_prefixes:
            errors.append("allowed_prefixes debe contener al menos un prefijo.")
        if len(self.allowed_prefixes) != len(set(self.allowed_prefixes)):
            errors.append("allowed_prefixes contiene valores duplicados.")
        return errors

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "IdentifierPolicy":
        if not isinstance(data, Mapping):
            raise TypeError("IdentifierPolicy.from_dict esperaba Mapping.")
        return cls(**dict(data))


class IdentifierRegistry:
    """Registro en memoria para detectar identificadores duplicados."""

    def __init__(self, identifiers: Optional[Iterable[str]] = None) -> None:
        self._identifiers: Set[str] = set()
        if identifiers is not None:
            self.register_many(identifiers)

    def __contains__(self, identifier: object) -> bool:
        if not isinstance(identifier, str):
            return False
        try:
            normalized = normalize_identifier(identifier)
        except (TypeError, ValueError):
            return False
        return normalized in self._identifiers

    def __len__(self) -> int:
        return len(self._identifiers)

    def register(self, identifier: str) -> str:
        normalized = normalize_identifier(identifier)
        if normalized in self._identifiers:
            raise ValueError(
                f"El identificador {normalized!r} ya está registrado."
            )
        self._identifiers.add(normalized)
        return normalized

    def register_many(self, identifiers: Iterable[str]) -> List[str]:
        normalized_values = [normalize_identifier(item) for item in identifiers]
        incoming_duplicates = _find_duplicates(normalized_values)
        if incoming_duplicates:
            raise ValueError(
                "La colección contiene identificadores duplicados: "
                + ", ".join(sorted(incoming_duplicates))
            )
        existing = [
            item for item in normalized_values if item in self._identifiers
        ]
        if existing:
            raise ValueError(
                "Los siguientes identificadores ya están registrados: "
                + ", ".join(existing)
            )
        self._identifiers.update(normalized_values)
        return normalized_values

    def unregister(self, identifier: str) -> bool:
        normalized = normalize_identifier(identifier)
        if normalized not in self._identifiers:
            return False
        self._identifiers.remove(normalized)
        return True

    def clear(self) -> None:
        self._identifiers.clear()

    def values(self) -> List[str]:
        return sorted(self._identifiers)

    def by_prefix(self, prefix: str) -> List[str]:
        normalized_prefix = normalize_prefix(prefix)
        return [
            item
            for item in self.values()
            if extract_prefix(item) == normalized_prefix
        ]

    def counts_by_prefix(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for identifier in self._identifiers:
            prefix = extract_prefix(identifier)
            counts[prefix] = counts.get(prefix, 0) + 1
        return dict(sorted(counts.items()))

    def to_dict(self) -> JSONDict:
        return {
            "identifiers": self.values(),
            "count": len(self),
            "counts_by_prefix": self.counts_by_prefix(),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "IdentifierRegistry":
        if not isinstance(data, Mapping):
            raise TypeError("IdentifierRegistry.from_dict esperaba Mapping.")
        return cls(data.get("identifiers", []))


def normalize_prefixes(prefixes: Iterable[str]) -> List[str]:
    normalized: List[str] = []
    seen: Set[str] = set()
    for prefix in prefixes:
        current = normalize_prefix(prefix)
        if current not in seen:
            normalized.append(current)
            seen.add(current)
    return normalized


def _find_duplicates(values: Iterable[str]) -> Set[str]:
    seen: Set[str] = set()
    duplicates: Set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        else:
            seen.add(value)
    return duplicates


def find_duplicate_identifiers(identifiers: Iterable[str]) -> List[str]:
    normalized = [normalize_identifier(item) for item in identifiers]
    return sorted(_find_duplicates(normalized))


def group_identifiers_by_prefix(
    identifiers: Iterable[str],
) -> Dict[str, List[str]]:
    grouped: Dict[str, List[str]] = {}
    for identifier in identifiers:
        normalized = normalize_identifier(identifier)
        prefix = extract_prefix(normalized)
        grouped.setdefault(prefix, []).append(normalized)
    return {
        prefix: sorted(values)
        for prefix, values in sorted(grouped.items())
    }


__all__ = [
    "DEFAULT_NAMESPACE",
    "DEFAULT_RANDOM_LENGTH",
    "DEFAULT_SEPARATOR",
    "DomainIdentifier",
    "IDENTIFIER_PATTERN",
    "IdentifierPolicy",
    "IdentifierPrefix",
    "IdentifierRegistry",
    "MAX_RANDOM_LENGTH",
    "MIN_RANDOM_LENGTH",
    "NAMESPACE_PATTERN",
    "PREFIX_PATTERN",
    "ParsedIdentifier",
    "create_deterministic_identifier",
    "create_identifier",
    "create_namespaced_identifier",
    "extract_prefix",
    "extract_value",
    "find_duplicate_identifiers",
    "generate_hex_value",
    "group_identifiers_by_prefix",
    "identifier_has_prefix",
    "is_valid_identifier",
    "is_valid_prefix",
    "normalize_identifier",
    "normalize_namespace",
    "normalize_prefix",
    "normalize_prefixes",
    "parse_identifier",
]