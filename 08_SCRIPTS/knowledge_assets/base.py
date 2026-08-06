"""
===============================================================================
CIPS - Consejo de Inteligencia para Producción de Soluciones
Knowledge Assets Domain
-------------------------------------------------------------------------------

Archivo:
    base.py

Descripción:
    Define las clases base, utilidades de serialización, identificación,
    control temporal, clonación y validación utilizadas por el dominio
    Knowledge Assets.

Reglas de arquitectura:
    - No importa módulos internos del proyecto.
    - No contiene modelos específicos del negocio.
    - No contiene enumeraciones del dominio.
    - Puede ser reutilizado por cualquier módulo de knowledge_assets.

Versión:
    1.0.0
===============================================================================
"""

from __future__ import annotations

import copy
import json
import uuid
from abc import ABC
from dataclasses import dataclass, field, fields, is_dataclass
from datetime import date, datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, ClassVar, Dict, List, Mapping, Optional, Type, TypeVar


JSONDict = Dict[str, Any]
ValidationErrors = List[str]

T = TypeVar("T")
TSerializable = TypeVar("TSerializable", bound="SerializableMixin")
TBaseEntity = TypeVar("TBaseEntity", bound="BaseEntity")

DEFAULT_ENCODING: str = "utf-8"
DEFAULT_JSON_INDENT: int = 2
DEFAULT_ID_PREFIX: str = "ka"


def utc_now() -> datetime:
    """Devuelve la fecha y hora actual en UTC con zona horaria."""
    return datetime.now(timezone.utc)


def datetime_to_iso(value: datetime) -> str:
    """Convierte un datetime a ISO 8601."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def parse_datetime(value: Any) -> datetime:
    """Convierte datetime o cadena ISO 8601 a datetime con zona horaria."""
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        normalized = value.strip()
        if normalized.endswith("Z"):
            normalized = normalized[:-1] + "+00:00"
        parsed = datetime.fromisoformat(normalized)
    else:
        raise TypeError(
            "Se esperaba datetime o str ISO 8601; "
            f"se recibió {type(value).__name__}."
        )

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def generate_identifier(prefix: str = DEFAULT_ID_PREFIX) -> str:
    """Genera un identificador único legible."""
    clean_prefix = str(prefix).strip().lower().replace(" ", "_")
    if not clean_prefix:
        clean_prefix = DEFAULT_ID_PREFIX
    return f"{clean_prefix}_{uuid.uuid4().hex}"


def require_non_empty_string(value: Any, field_name: str) -> str:
    """Valida y normaliza una cadena obligatoria."""
    if not isinstance(value, str):
        raise TypeError(
            f"{field_name} debe ser str; se recibió {type(value).__name__}."
        )
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} no puede estar vacío.")
    return normalized


def serialize_value(value: Any) -> Any:
    """Convierte recursivamente un valor a una estructura compatible con JSON."""
    if isinstance(value, SerializableMixin):
        return value.to_dict()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return datetime_to_iso(value)
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if is_dataclass(value) and not isinstance(value, type):
        return {
            item.name: serialize_value(getattr(value, item.name))
            for item in fields(value)
        }
    if isinstance(value, Mapping):
        return {
            str(key): serialize_value(item_value)
            for key, item_value in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [serialize_value(item) for item in value]
    if isinstance(value, (set, frozenset)):
        serialized_items = [serialize_value(item) for item in value]
        try:
            return sorted(serialized_items)
        except TypeError:
            return serialized_items
    return value


def deserialize_enum(enum_type: Type[Enum], value: Any) -> Enum:
    """Convierte un valor o nombre al Enum indicado."""
    if isinstance(value, enum_type):
        return value
    try:
        return enum_type(value)
    except (TypeError, ValueError):
        pass
    if isinstance(value, str):
        normalized = value.strip().upper()
        try:
            return enum_type[normalized]
        except KeyError:
            pass
    valid_values = ", ".join(str(item.value) for item in enum_type)
    raise ValueError(
        f"Valor inválido para {enum_type.__name__}: {value!r}. "
        f"Valores permitidos: {valid_values}."
    )


class SerializableMixin:
    """Proporciona serialización consistente a diccionario y JSON."""

    def to_dict(self) -> JSONDict:
        if is_dataclass(self):
            return {
                item.name: serialize_value(getattr(self, item.name))
                for item in fields(self)
            }
        return {
            key: serialize_value(value)
            for key, value in vars(self).items()
            if not key.startswith("_")
        }

    def to_json(
        self,
        *,
        indent: Optional[int] = DEFAULT_JSON_INDENT,
        ensure_ascii: bool = False,
        sort_keys: bool = False,
    ) -> str:
        return json.dumps(
            self.to_dict(),
            indent=indent,
            ensure_ascii=ensure_ascii,
            sort_keys=sort_keys,
        )

    def write_json(
        self,
        path: str | Path,
        *,
        indent: Optional[int] = DEFAULT_JSON_INDENT,
        ensure_ascii: bool = False,
        sort_keys: bool = False,
        create_parents: bool = True,
    ) -> Path:
        output_path = Path(path)
        if create_parents:
            output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            self.to_json(
                indent=indent,
                ensure_ascii=ensure_ascii,
                sort_keys=sort_keys,
            ),
            encoding=DEFAULT_ENCODING,
        )
        return output_path

    @classmethod
    def from_dict(cls: Type[TSerializable], data: Mapping[str, Any]) -> TSerializable:
        if not isinstance(data, Mapping):
            raise TypeError(
                f"{cls.__name__}.from_dict esperaba Mapping; "
                f"se recibió {type(data).__name__}."
            )
        return cls(**dict(data))  # type: ignore[arg-type]

    @classmethod
    def from_json(cls: Type[TSerializable], payload: str) -> TSerializable:
        if not isinstance(payload, str):
            raise TypeError(
                f"{cls.__name__}.from_json esperaba str; "
                f"se recibió {type(payload).__name__}."
            )
        decoded = json.loads(payload)
        if not isinstance(decoded, dict):
            raise ValueError(
                f"El JSON de {cls.__name__} debe representar un objeto."
            )
        return cls.from_dict(decoded)

    @classmethod
    def read_json(cls: Type[TSerializable], path: str | Path) -> TSerializable:
        payload = Path(path).read_text(encoding=DEFAULT_ENCODING)
        return cls.from_json(payload)


class CloneMixin:
    """Proporciona clonación profunda de instancias."""

    def clone(self: T, **changes: Any) -> T:
        cloned = copy.deepcopy(self)
        for attribute_name, value in changes.items():
            if not hasattr(cloned, attribute_name):
                raise AttributeError(
                    f"{type(self).__name__} no contiene el atributo "
                    f"{attribute_name!r}."
                )
            setattr(cloned, attribute_name, value)
        return cloned


class ValidationMixin:
    """Contrato base para validación de modelos del dominio."""

    def validation_errors(self) -> ValidationErrors:
        return []

    def is_valid(self) -> bool:
        return not self.validation_errors()

    def validate(self) -> None:
        errors = self.validation_errors()
        if errors:
            formatted_errors = "\n".join(f"- {error}" for error in errors)
            raise ValueError(
                f"{type(self).__name__} inválido:\n{formatted_errors}"
            )


@dataclass
class BaseEntity(SerializableMixin, CloneMixin, ValidationMixin, ABC):
    """Entidad base con identidad, marcas temporales y validación."""

    id_prefix: ClassVar[str] = DEFAULT_ID_PREFIX

    id: str = field(default_factory=lambda: generate_identifier(DEFAULT_ID_PREFIX))
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.id = require_non_empty_string(self.id, "id")
        self.created_at = parse_datetime(self.created_at)
        self.updated_at = parse_datetime(self.updated_at)
        if self.updated_at < self.created_at:
            self.updated_at = self.created_at

    @classmethod
    def new_id(cls) -> str:
        return generate_identifier(cls.id_prefix)

    def touch(self, timestamp: Optional[datetime] = None) -> datetime:
        new_timestamp = parse_datetime(timestamp or utc_now())
        if new_timestamp < self.created_at:
            raise ValueError("updated_at no puede ser anterior a created_at.")
        self.updated_at = new_timestamp
        return self.updated_at

    def validation_errors(self) -> ValidationErrors:
        errors: ValidationErrors = []
        if not isinstance(self.id, str) or not self.id.strip():
            errors.append("id es obligatorio.")
        if not isinstance(self.created_at, datetime):
            errors.append("created_at debe ser datetime.")
        if not isinstance(self.updated_at, datetime):
            errors.append("updated_at debe ser datetime.")
        if (
            isinstance(self.created_at, datetime)
            and isinstance(self.updated_at, datetime)
            and self.updated_at < self.created_at
        ):
            errors.append("updated_at no puede ser anterior a created_at.")
        return errors

    @classmethod
    def from_dict(
        cls: Type[TBaseEntity],
        data: Mapping[str, Any],
    ) -> TBaseEntity:
        if not isinstance(data, Mapping):
            raise TypeError(
                f"{cls.__name__}.from_dict esperaba Mapping; "
                f"se recibió {type(data).__name__}."
            )
        normalized = dict(data)
        if "created_at" in normalized:
            normalized["created_at"] = parse_datetime(normalized["created_at"])
        if "updated_at" in normalized:
            normalized["updated_at"] = parse_datetime(normalized["updated_at"])
        return cls(**normalized)  # type: ignore[arg-type]


class ValueObject(SerializableMixin, CloneMixin, ValidationMixin, ABC):
    """
    Clase base para objetos de valor.

    No es una dataclass porque no define campos propios.
    Su función es proporcionar comportamiento común a los
    Value Objects del dominio, independientemente de que las
    clases derivadas sean mutables o inmutables.
    """
    
    def __post_init__(self) -> None:
        pass


__all__ = [
    "BaseEntity",
    "CloneMixin",
    "DEFAULT_ENCODING",
    "DEFAULT_ID_PREFIX",
    "DEFAULT_JSON_INDENT",
    "JSONDict",
    "SerializableMixin",
    "ValidationErrors",
    "ValidationMixin",
    "ValueObject",
    "datetime_to_iso",
    "deserialize_enum",
    "generate_identifier",
    "parse_datetime",
    "require_non_empty_string",
    "serialize_value",
    "utc_now",
]