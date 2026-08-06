"""
===============================================================================
CIPS - Consejo de Inteligencia para Producción de Soluciones
Knowledge Assets Domain
-------------------------------------------------------------------------------

Archivo:
    mixins.py

Descripción:
    Define capacidades reutilizables para los modelos del dominio
    Knowledge Assets.

Versión:
    1.0.0
===============================================================================
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
import unicodedata
from dataclasses import fields, is_dataclass
from datetime import datetime
from typing import Any, Dict, Iterable, List, Mapping, Optional, Set

from .base import JSONDict, ValidationErrors, parse_datetime, serialize_value, utc_now


def _normalize_optional_text(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError(f"Se esperaba str o None; se recibió {type(value).__name__}.")
    normalized = value.strip()
    return normalized or None


def _normalize_text_list(values: Iterable[str]) -> List[str]:
    normalized: List[str] = []
    seen: Set[str] = set()
    for value in values:
        if not isinstance(value, str):
            raise TypeError(f"Todos los elementos deben ser str; se recibió {type(value).__name__}.")
        item = value.strip()
        if not item:
            continue
        key = item.casefold()
        if key not in seen:
            normalized.append(item)
            seen.add(key)
    return normalized


def _slugify(value: str) -> str:
    if not isinstance(value, str):
        raise TypeError("value debe ser str.")
    normalized = unicodedata.normalize("NFKD", value)
    normalized = normalized.encode("ascii", "ignore").decode("ascii")
    normalized = normalized.lower().strip()
    normalized = re.sub(r"[^a-z0-9]+", "-", normalized)
    normalized = re.sub(r"-+", "-", normalized)
    return normalized.strip("-")


def _public_state(instance: Any) -> JSONDict:
    if is_dataclass(instance):
        return {
            item.name: serialize_value(getattr(instance, item.name))
            for item in fields(instance)
            if not item.name.startswith("_")
        }
    return {
        key: serialize_value(value)
        for key, value in vars(instance).items()
        if not key.startswith("_")
    }


class TimestampMixin:
    created_at: datetime
    updated_at: datetime

    def initialize_timestamps(self) -> None:
        now = utc_now()
        self.created_at = parse_datetime(getattr(self, "created_at", None) or now)
        self.updated_at = parse_datetime(getattr(self, "updated_at", None) or self.created_at)
        if self.updated_at < self.created_at:
            self.updated_at = self.created_at

    def touch(self, timestamp: Optional[datetime] = None) -> datetime:
        new_timestamp = parse_datetime(timestamp or utc_now())
        if new_timestamp < self.created_at:
            raise ValueError("updated_at no puede ser anterior a created_at.")
        self.updated_at = new_timestamp
        return self.updated_at

    def timestamp_validation_errors(self) -> ValidationErrors:
        errors: ValidationErrors = []
        if not isinstance(getattr(self, "created_at", None), datetime):
            errors.append("created_at debe ser datetime.")
        if not isinstance(getattr(self, "updated_at", None), datetime):
            errors.append("updated_at debe ser datetime.")
        if isinstance(getattr(self, "created_at", None), datetime) and isinstance(getattr(self, "updated_at", None), datetime) and self.updated_at < self.created_at:
            errors.append("updated_at no puede ser anterior a created_at.")
        return errors


class VersionMixin:
    version: str
    revision: int

    def initialize_version(self) -> None:
        version = getattr(self, "version", "1.0.0")
        revision = getattr(self, "revision", 1)
        if not isinstance(version, str):
            raise TypeError("version debe ser str.")
        if isinstance(revision, bool) or not isinstance(revision, int):
            raise TypeError("revision debe ser int.")
        self.version = version.strip() or "1.0.0"
        self.revision = max(1, revision)

    def _version_parts(self) -> tuple[int, int, int]:
        match = re.fullmatch(r"(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)", self.version.strip())
        if match is None:
            raise ValueError("version debe cumplir el formato MAJOR.MINOR.PATCH.")
        return int(match.group("major")), int(match.group("minor")), int(match.group("patch"))

    def bump_revision(self) -> int:
        self.revision += 1
        if hasattr(self, "touch"):
            self.touch()
        return self.revision

    def bump_patch(self) -> str:
        major, minor, patch = self._version_parts()
        self.version = f"{major}.{minor}.{patch + 1}"
        self.bump_revision()
        return self.version

    def bump_minor(self) -> str:
        major, minor, _ = self._version_parts()
        self.version = f"{major}.{minor + 1}.0"
        self.bump_revision()
        return self.version

    def bump_major(self) -> str:
        major, _, _ = self._version_parts()
        self.version = f"{major + 1}.0.0"
        self.bump_revision()
        return self.version

    def version_validation_errors(self) -> ValidationErrors:
        errors: ValidationErrors = []
        try:
            self._version_parts()
        except (AttributeError, TypeError, ValueError):
            errors.append("version debe cumplir el formato MAJOR.MINOR.PATCH.")
        revision = getattr(self, "revision", None)
        if isinstance(revision, bool) or not isinstance(revision, int) or revision < 1:
            errors.append("revision debe ser un entero mayor o igual que 1.")
        return errors


class AuditMixin:
    created_by: Optional[str]
    updated_by: Optional[str]

    def initialize_audit(self) -> None:
        self.created_by = _normalize_optional_text(getattr(self, "created_by", None))
        self.updated_by = _normalize_optional_text(getattr(self, "updated_by", None)) or self.created_by

    def mark_updated_by(self, actor: str) -> None:
        normalized = _normalize_optional_text(actor)
        if normalized is None:
            raise ValueError("actor no puede estar vacío.")
        self.updated_by = normalized
        if hasattr(self, "touch"):
            self.touch()

    def audit_validation_errors(self) -> ValidationErrors:
        errors: ValidationErrors = []
        for field_name in ("created_by", "updated_by"):
            value = getattr(self, field_name, None)
            if value is not None and not isinstance(value, str):
                errors.append(f"{field_name} debe ser str o None.")
        return errors


class TagMixin:
    tags: List[str]

    def initialize_tags(self) -> None:
        self.tags = _normalize_text_list(getattr(self, "tags", []))

    def add_tag(self, tag: str) -> bool:
        items = _normalize_text_list([tag])
        if not items:
            return False
        item = items[0]
        if any(current.casefold() == item.casefold() for current in self.tags):
            return False
        self.tags.append(item)
        if hasattr(self, "touch"):
            self.touch()
        return True

    def remove_tag(self, tag: str) -> bool:
        target = tag.strip().casefold()
        for index, current in enumerate(self.tags):
            if current.casefold() == target:
                del self.tags[index]
                if hasattr(self, "touch"):
                    self.touch()
                return True
        return False

    def has_tag(self, tag: str) -> bool:
        if not isinstance(tag, str):
            return False
        target = tag.strip().casefold()
        return any(current.casefold() == target for current in self.tags)

    def tag_validation_errors(self) -> ValidationErrors:
        try:
            normalized = _normalize_text_list(getattr(self, "tags", []))
        except (TypeError, ValueError) as exc:
            return [str(exc)]
        if len(normalized) != len(getattr(self, "tags", [])):
            return ["tags contiene valores vacíos o duplicados."]
        return []


class LabelMixin:
    labels: List[str]

    def initialize_labels(self) -> None:
        self.labels = _normalize_text_list(getattr(self, "labels", []))

    def add_label(self, label: str) -> bool:
        items = _normalize_text_list([label])
        if not items:
            return False
        item = items[0]
        if any(current.casefold() == item.casefold() for current in self.labels):
            return False
        self.labels.append(item)
        return True

    def remove_label(self, label: str) -> bool:
        target = label.strip().casefold()
        for index, current in enumerate(self.labels):
            if current.casefold() == target:
                del self.labels[index]
                return True
        return False


class AliasMixin:
    aliases: List[str]

    def initialize_aliases(self) -> None:
        self.aliases = _normalize_text_list(getattr(self, "aliases", []))

    def add_alias(self, alias: str) -> bool:
        items = _normalize_text_list([alias])
        if not items:
            return False
        item = items[0]
        if any(current.casefold() == item.casefold() for current in self.aliases):
            return False
        self.aliases.append(item)
        return True

    def matches_alias(self, value: str) -> bool:
        if not isinstance(value, str):
            return False
        target = value.strip().casefold()
        return any(alias.casefold() == target for alias in self.aliases)


class SlugMixin:
    slug: Optional[str]

    def initialize_slug(self, source: Optional[str] = None) -> None:
        current = _normalize_optional_text(getattr(self, "slug", None))
        if current:
            self.slug = _slugify(current)
        elif source:
            generated = _slugify(source)
            self.slug = generated or None
        else:
            self.slug = None

    def regenerate_slug(self, source: str) -> str:
        generated = _slugify(source)
        if not generated:
            raise ValueError("No fue posible generar un slug con source.")
        self.slug = generated
        if hasattr(self, "touch"):
            self.touch()
        return generated

    def slug_validation_errors(self) -> ValidationErrors:
        slug = getattr(self, "slug", None)
        if slug is None:
            return []
        if not isinstance(slug, str):
            return ["slug debe ser str o None."]
        if slug != _slugify(slug):
            return ["slug contiene un formato inválido."]
        return []


class DescriptionMixin:
    summary: Optional[str]
    description: Optional[str]

    def initialize_descriptions(self) -> None:
        self.summary = _normalize_optional_text(getattr(self, "summary", None))
        self.description = _normalize_optional_text(getattr(self, "description", None))

    def description_validation_errors(self, *, summary_max_length: int = 500) -> ValidationErrors:
        errors: ValidationErrors = []
        if self.summary is not None and len(self.summary) > summary_max_length:
            errors.append(f"summary supera {summary_max_length} caracteres.")
        return errors


class NotesMixin:
    notes: List[str]

    def initialize_notes(self) -> None:
        self.notes = _normalize_text_list(getattr(self, "notes", []))

    def add_note(self, note: str) -> None:
        normalized = _normalize_optional_text(note)
        if normalized is None:
            raise ValueError("note no puede estar vacía.")
        self.notes.append(normalized)
        if hasattr(self, "touch"):
            self.touch()


class CustomFieldMixin:
    custom_fields: Dict[str, Any]

    def initialize_custom_fields(self) -> None:
        value = getattr(self, "custom_fields", {}) or {}
        if not isinstance(value, Mapping):
            raise TypeError("custom_fields debe ser Mapping.")
        self.custom_fields = {str(key): copy.deepcopy(item) for key, item in value.items()}

    def set_custom_field(self, key: str, value: Any) -> None:
        if not isinstance(key, str) or not key.strip():
            raise ValueError("key debe ser una cadena no vacía.")
        self.custom_fields[key.strip()] = copy.deepcopy(value)
        if hasattr(self, "touch"):
            self.touch()

    def get_custom_field(self, key: str, default: Any = None) -> Any:
        return self.custom_fields.get(key, default)

    def remove_custom_field(self, key: str) -> bool:
        if key not in self.custom_fields:
            return False
        del self.custom_fields[key]
        if hasattr(self, "touch"):
            self.touch()
        return True


class SearchMixin:
    search_fields: tuple[str, ...] = ("title", "name", "summary", "description", "tags", "labels", "aliases")

    def search_document(self) -> str:
        fragments: List[str] = []
        for field_name in self.search_fields:
            value = getattr(self, field_name, None)
            if value is None:
                continue
            if isinstance(value, str):
                fragments.append(value)
            elif isinstance(value, Iterable) and not isinstance(value, (bytes, bytearray, Mapping)):
                fragments.extend(str(item) for item in value)
            else:
                fragments.append(str(value))
        return " ".join(fragments).casefold()

    def matches_query(self, query: str, *, require_all_terms: bool = True) -> bool:
        if not isinstance(query, str):
            raise TypeError("query debe ser str.")
        terms = [term.casefold() for term in query.split() if term.strip()]
        if not terms:
            return True
        document = self.search_document()
        return all(term in document for term in terms) if require_all_terms else any(term in document for term in terms)


class HashMixin:
    hash_algorithm: str = "sha256"
    hash_excluded_fields: Set[str] = {"updated_at", "content_hash"}

    def hash_payload(self) -> JSONDict:
        payload = _public_state(self)
        for field_name in self.hash_excluded_fields:
            payload.pop(field_name, None)
        return payload

    def calculate_hash(self) -> str:
        serialized = json.dumps(self.hash_payload(), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        try:
            hasher = hashlib.new(self.hash_algorithm)
        except ValueError as exc:
            raise ValueError(f"Algoritmo hash no soportado: {self.hash_algorithm!r}.") from exc
        hasher.update(serialized)
        return hasher.hexdigest()

    def verify_hash(self, expected_hash: str) -> bool:
        return isinstance(expected_hash, str) and self.calculate_hash() == expected_hash.strip().lower()


class ChangeTrackingMixin:
    _original_state: Optional[JSONDict] = None

    def capture_state(self) -> JSONDict:
        self._original_state = copy.deepcopy(_public_state(self))
        return copy.deepcopy(self._original_state)

    def current_state(self) -> JSONDict:
        return copy.deepcopy(_public_state(self))

    def is_dirty(self) -> bool:
        return self._original_state is not None and self.current_state() != self._original_state

    def changed_fields(self) -> Dict[str, Dict[str, Any]]:
        if self._original_state is None:
            return {}
        current = self.current_state()
        keys = set(self._original_state) | set(current)
        return {
            key: {"before": self._original_state.get(key), "after": current.get(key)}
            for key in sorted(keys)
            if self._original_state.get(key) != current.get(key)
        }

    def accept_changes(self) -> None:
        self.capture_state()


class MetadataMixin:
    metadata: Any

    def set_metadata(self, metadata: Any) -> None:
        self.metadata = metadata
        if hasattr(self, "touch"):
            self.touch()

    def metadata_dict(self) -> JSONDict:
        value = getattr(self, "metadata", None)
        if value is None:
            return {}
        serialized = serialize_value(value)
        return serialized if isinstance(serialized, dict) else {"value": serialized}


class ReferenceMixin:
    references: Any

    def set_references(self, references: Any) -> None:
        self.references = references
        if hasattr(self, "touch"):
            self.touch()

    def reference_summary(self) -> JSONDict:
        value = getattr(self, "references", None)
        if value is None:
            return {"source_count": 0, "citation_count": 0, "evidence_count": 0}
        summary_method = getattr(value, "summary", None)
        if callable(summary_method):
            return summary_method()
        serialized = serialize_value(value)
        return serialized if isinstance(serialized, dict) else {}


class ExportMixin:
    def export_dict(self, *, exclude_none: bool = False, exclude_fields: Optional[Iterable[str]] = None) -> JSONDict:
        payload = _public_state(self)
        excluded = set(exclude_fields or [])
        return {
            key: value
            for key, value in payload.items()
            if key not in excluded and not (exclude_none and value is None)
        }

    def export_json(self, *, indent: Optional[int] = 2, ensure_ascii: bool = False, sort_keys: bool = False, exclude_none: bool = False, exclude_fields: Optional[Iterable[str]] = None) -> str:
        return json.dumps(self.export_dict(exclude_none=exclude_none, exclude_fields=exclude_fields), indent=indent, ensure_ascii=ensure_ascii, sort_keys=sort_keys)


class CopyMixin:
    def copy_with(self, **changes: Any) -> Any:
        cloned = copy.deepcopy(self)
        for key, value in changes.items():
            if not hasattr(cloned, key):
                raise AttributeError(f"{type(self).__name__} no contiene el atributo {key!r}.")
            setattr(cloned, key, value)
        if hasattr(cloned, "touch"):
            cloned.touch()
        return cloned


class DomainInitializationMixin:
    initialization_methods: tuple[str, ...] = (
        "initialize_timestamps", "initialize_version", "initialize_audit",
        "initialize_tags", "initialize_labels", "initialize_aliases",
        "initialize_descriptions", "initialize_notes", "initialize_custom_fields",
    )

    def initialize_domain_capabilities(self) -> None:
        for method_name in self.initialization_methods:
            method = getattr(self, method_name, None)
            if callable(method):
                method()


class DomainValidationMixin:
    validation_method_names: tuple[str, ...] = (
        "timestamp_validation_errors", "version_validation_errors",
        "audit_validation_errors", "tag_validation_errors",
        "slug_validation_errors", "description_validation_errors",
    )

    def mixin_validation_errors(self) -> ValidationErrors:
        errors: ValidationErrors = []
        for method_name in self.validation_method_names:
            method = getattr(self, method_name, None)
            if callable(method):
                errors.extend(method() or [])
        return errors


class KnowledgeAssetCapabilities(
    DomainInitializationMixin,
    DomainValidationMixin,
    TimestampMixin,
    VersionMixin,
    AuditMixin,
    TagMixin,
    LabelMixin,
    AliasMixin,
    SlugMixin,
    DescriptionMixin,
    NotesMixin,
    CustomFieldMixin,
    SearchMixin,
    HashMixin,
    ChangeTrackingMixin,
    MetadataMixin,
    ReferenceMixin,
    ExportMixin,
    CopyMixin,
):
    """Composición principal de capacidades para KnowledgeAsset."""


__all__ = [
    "AliasMixin", "AuditMixin", "ChangeTrackingMixin", "CopyMixin",
    "CustomFieldMixin", "DescriptionMixin", "DomainInitializationMixin",
    "DomainValidationMixin", "ExportMixin", "HashMixin",
    "KnowledgeAssetCapabilities", "LabelMixin", "MetadataMixin",
    "NotesMixin", "ReferenceMixin", "SearchMixin", "SlugMixin",
    "TagMixin", "TimestampMixin", "VersionMixin",
]