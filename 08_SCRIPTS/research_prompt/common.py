"""Infraestructura común del CIPS Research Prompt Builder."""
from __future__ import annotations

from dataclasses import fields, is_dataclass
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
import re
from typing import Any, Iterable, Mapping, Optional

try:
    from research_director_models import RESEARCH_MODELS_VERSION
except ImportError:  # pragma: no cover
    from ..research_director_models import RESEARCH_MODELS_VERSION

RESEARCH_PROMPT_BUILDER_VERSION = "1.0.0-refactor"
DEFAULT_PROMPT_LANGUAGE = "es-MX"
DEFAULT_SCHEMA_VERSION = "1.0"
DEFAULT_MAX_SECTION_CHARS = 120_000
DEFAULT_MAX_TOTAL_CHARS = 500_000

class ResearchPromptBuilderError(RuntimeError):
    """Error base del constructor de prompts."""


class ResearchPromptValidationError(ResearchPromptBuilderError):
    """El prompt o su contexto incumplen una regla."""


class ResearchPromptSerializationError(ResearchPromptBuilderError):
    """No fue posible serializar el contenido."""


class ResearchPromptContractError(ResearchPromptBuilderError):
    """El contrato de respuesta es inválido."""


class PromptSectionKind(str, Enum):
    IDENTITY = "identity"
    MISSION = "mission"
    CONTEXT = "context"
    OBJECTIVES = "objectives"
    QUESTIONS = "questions"
    CONSTRAINTS = "constraints"
    METHODOLOGY = "methodology"
    SOURCE_POLICY = "source_policy"
    EVIDENCE_POLICY = "evidence_policy"
    CLAIM_POLICY = "claim_policy"
    VERIFICATION_POLICY = "verification_policy"
    CITATION_POLICY = "citation_policy"
    QUALITY_POLICY = "quality_policy"
    SAFETY_POLICY = "safety_policy"
    WORKFLOW = "workflow"
    TASKS = "tasks"
    INPUT_DATA = "input_data"
    OUTPUT_CONTRACT = "output_contract"
    FINAL_INSTRUCTIONS = "final_instructions"
    CUSTOM = "custom"


class PromptAudience(str, Enum):
    SYSTEM = "system"
    USER = "user"
    DEVELOPER = "developer"
    TOOL = "tool"
    INTERNAL = "internal"


class PromptOutputMode(str, Enum):
    JSON_ONLY = "json_only"
    JSON_AND_MARKDOWN = "json_and_markdown"
    MARKDOWN_ONLY = "markdown_only"
    STRUCTURED_TEXT = "structured_text"


class PromptStrictness(str, Enum):
    FLEXIBLE = "flexible"
    STANDARD = "standard"
    STRICT = "strict"
    AUDIT = "audit"


def normalize_text(value: Any, *, field_name: str = "value", required: bool = False) -> str:
    text = "" if value is None else str(value)
    text = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if required and not text:
        raise ResearchPromptValidationError(f"'{field_name}' no puede estar vacío.")
    return text


def normalize_string_list(values: Optional[Iterable[Any]]) -> list[str]:
    if values is None:
        return []
    output: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = normalize_text(value)
        if not text:
            continue
        key = text.casefold()
        if key in seen:
            continue
        seen.add(key)
        output.append(text)
    return output


def _serialize(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat(timespec="seconds")
    if is_dataclass(value):
        return {item.name: _serialize(getattr(value, item.name)) for item in fields(value)}
    if isinstance(value, Mapping):
        return {str(key): _serialize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_serialize(item) for item in value]
    return value


def safe_json_dumps(value: Any, *, indent: Optional[int] = 2, ensure_ascii: bool = False, sort_keys: bool = False) -> str:
    try:
        return json.dumps(_serialize(value), indent=indent, ensure_ascii=ensure_ascii, sort_keys=sort_keys)
    except (TypeError, ValueError) as exc:
        raise ResearchPromptSerializationError(str(exc)) from exc


def stable_hash(value: Any) -> str:
    payload = safe_json_dumps(value, indent=None, sort_keys=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _enum(value: Any, enum_type: type[Enum], field_name: str) -> Enum:
    if isinstance(value, enum_type):
        return value
    try:
        return enum_type(str(value))
    except ValueError as exc:
        allowed = ", ".join(item.value for item in enum_type)
        raise ResearchPromptValidationError(f"'{field_name}' debe ser uno de: {allowed}.") from exc


def _mapping(value: Optional[Mapping[str, Any]], field_name: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ResearchPromptValidationError(f"'{field_name}' debe ser Mapping.")
    return dict(value)
