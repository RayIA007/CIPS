"""Auditoría del ciclo de construcción y exportación."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable, Mapping, Optional

try:
    from research_director_models import generate_id, utc_now_iso
except ImportError:  # pragma: no cover
    from ..research_director_models import generate_id, utc_now_iso

from .advanced_common import _serialize
from .common import normalize_text, safe_json_dumps, stable_hash

class AuditEventType(str, Enum):
    CREATED = "created"
    NORMALIZED = "normalized"
    QUESTION_EXPANDED = "question_expanded"
    OBJECTIVE_OPTIMIZED = "objective_optimized"
    CONSTRAINT_RESOLVED = "constraint_resolved"
    ASSEMBLED = "assembled"
    OPTIMIZED = "optimized"
    VALIDATED = "validated"
    SCORED = "scored"
    EXPORTED = "exported"
    WARNING = "warning"
    ERROR = "error"



@dataclass(slots=True)
class PromptAuditEvent:
    event_type: AuditEventType
    message: str
    event_id: str = field(default_factory=lambda: generate_id("pae"))
    timestamp: str = field(default_factory=utc_now_iso)
    actor: str = "system"
    before_hash: str = ""
    after_hash: str = ""
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return _serialize(self)


@dataclass(slots=True)
class PromptAuditTrail:
    audit_id: str = field(default_factory=lambda: generate_id("pat"))
    events: list[PromptAuditEvent] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now_iso)

    def add(self, event_type: AuditEventType, message: str, *, before: Any = None,
            after: Any = None, details: Optional[Mapping[str, Any]] = None,
            actor: str = "system") -> PromptAuditEvent:
        event = PromptAuditEvent(
            event_type=event_type,
            message=normalize_text(message, required=True),
            actor=actor,
            before_hash=stable_hash(before) if before is not None else "",
            after_hash=stable_hash(after) if after is not None else "",
            details=dict(details or {}),
        )
        self.events.append(event)
        return event

    def to_dict(self) -> dict[str, Any]:
        return _serialize(self)
