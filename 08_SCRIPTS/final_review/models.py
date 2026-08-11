"""Pure domain models for CIPS F7 final review.

The models in this module describe a review target and a review decision. They
intentionally do not execute workflows, mutate ``ProductionState``, persist
files, export deliverables, select providers, or publish content.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


FINAL_REVIEW_SCHEMA_VERSION = "1.0.0"


class ReviewState(str, Enum):
    """Lifecycle state of the final-review domain, independent of workflow state."""

    READY_FOR_REVIEW = "ready_for_review"
    APPROVED = "approved"
    CHANGES_REQUESTED = "changes_requested"
    CANCELLED = "cancelled"


class ReviewAction(str, Enum):
    """Decision emitted by a reviewer or an explicit automated review policy."""

    APPROVE = "approve"
    REQUEST_CHANGES = "request_changes"
    CANCEL = "cancel"


class ReviewArtifactRef(BaseModel):
    """Logical artifact identity for review, never a filesystem path."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    artifact_id: str = Field(..., min_length=1)
    content_hash: str | None = None
    task_id: str | None = None
    role: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("artifact_id")
    @classmethod
    def _normalize_artifact_id(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("artifact_id es obligatorio.")
        return normalized

    @field_validator("task_id", "role")
    @classmethod
    def _normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("Los identificadores opcionales no pueden estar vacíos.")
        return normalized

    @field_validator("content_hash")
    @classmethod
    def _validate_content_hash(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower()
        if len(normalized) != 64 or any(char not in "0123456789abcdef" for char in normalized):
            raise ValueError("content_hash debe ser un SHA-256 hexadecimal de 64 caracteres.")
        return normalized


class ReviewTarget(BaseModel):
    """Stable logical unit submitted to final review."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    project_id: str = Field(..., min_length=1)
    workflow_id: str = Field(..., min_length=1)
    run_id: str = Field(..., min_length=1)
    artifacts: tuple[ReviewArtifactRef, ...] = Field(..., min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("project_id", "workflow_id", "run_id")
    @classmethod
    def _normalize_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("project_id, workflow_id y run_id son obligatorios.")
        return normalized

    @model_validator(mode="after")
    def _reject_duplicate_artifacts(self) -> "ReviewTarget":
        artifact_ids = [artifact.artifact_id for artifact in self.artifacts]
        duplicates = sorted({item for item in artifact_ids if artifact_ids.count(item) > 1})
        if duplicates:
            raise ValueError(
                "ReviewTarget contiene artifact_id duplicados: "
                f"{', '.join(duplicates)}."
            )
        return self


class ReviewDecision(BaseModel):
    """Serializable review decision without execution or persistence behavior."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    decision_id: str = Field(..., min_length=1)
    action: ReviewAction
    actor: str = Field(..., min_length=1)
    decided_at: str = Field(..., min_length=1)
    comments: str | None = None
    redo_target: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("decision_id", "actor")
    @classmethod
    def _normalize_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("decision_id y actor son obligatorios.")
        return normalized

    @field_validator("decided_at")
    @classmethod
    def _normalize_decided_at(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("decided_at es obligatorio.")
        try:
            datetime.fromisoformat(normalized.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("decided_at debe usar formato ISO-8601.") from exc
        return normalized

    @field_validator("comments", "redo_target")
    @classmethod
    def _normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("comments y redo_target no pueden ser texto vacío.")
        return normalized

    @model_validator(mode="after")
    def _validate_action_payload(self) -> "ReviewDecision":
        if self.action is ReviewAction.REQUEST_CHANGES and self.redo_target is None:
            raise ValueError("REQUEST_CHANGES requiere redo_target.")
        if self.action is not ReviewAction.REQUEST_CHANGES and self.redo_target is not None:
            raise ValueError("redo_target solo es válido para REQUEST_CHANGES.")
        return self


__all__ = [
    "FINAL_REVIEW_SCHEMA_VERSION",
    "ReviewAction",
    "ReviewArtifactRef",
    "ReviewDecision",
    "ReviewState",
    "ReviewTarget",
]
