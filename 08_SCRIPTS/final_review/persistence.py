"""F3-backed persistence and audit adapter for CIPS F7 final review.

This module records immutable review decisions through the existing F3
``MetadataStore``. It does not implement a second artifact subsystem, mutate
workflow/checkpoint state, rerun pipeline work, export, publish content, or
provide observability beyond one minimal ``MessageType.AUDIT`` event.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal
from urllib.parse import quote

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from artifact_store import ArtifactStoreError
from cips_core.messages import Message, MessageBus, MessageType
from metadata_store import MetadataStore

from .errors import InvalidReviewTransitionError, ReviewPersistenceError
from .gateway import ReviewGatewayResult
from .models import ReviewAction, ReviewArtifactRef, ReviewDecision, ReviewState
from .transitions import apply_review_decision


REVIEW_AUDIT_SCHEMA_VERSION = "1.0.0"
REVIEW_AUDIT_TOPIC = "review.decision_recorded"


class ReviewAuditArtifactRef(BaseModel):
    """Minimal logical artifact identity captured by the review audit record."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    artifact_id: str = Field(..., min_length=1)
    content_hash: str | None = None
    task_id: str | None = None
    role: str | None = None


class ReviewAuditRecord(BaseModel):
    """Immutable, JSON-serializable snapshot of one final-review decision."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0.0"] = REVIEW_AUDIT_SCHEMA_VERSION
    record_id: str = Field(..., min_length=1)
    project_id: str = Field(..., min_length=1)
    workflow_id: str = Field(..., min_length=1)
    run_id: str = Field(..., min_length=1)
    previous_state: ReviewState
    state: ReviewState
    policy_name: str = Field(..., min_length=1)
    decision_id: str = Field(..., min_length=1)
    action: ReviewAction
    actor: str = Field(..., min_length=1)
    decided_at: str = Field(..., min_length=1)
    comments: str | None = None
    redo_target: str | None = None
    artifacts: tuple[ReviewAuditArtifactRef, ...] = Field(..., min_length=1)

    @model_validator(mode="after")
    def _validate_audit_snapshot(self) -> "ReviewAuditRecord":
        decision = ReviewDecision(
            decision_id=self.decision_id,
            action=self.action,
            actor=self.actor,
            decided_at=self.decided_at,
            comments=self.comments,
            redo_target=self.redo_target,
            metadata={},
        )
        try:
            expected_state = apply_review_decision(self.previous_state, decision)
        except InvalidReviewTransitionError as exc:
            raise ValueError("La transición contenida en el registro auditado no es válida.") from exc
        if expected_state is not self.state:
            raise ValueError(
                "El estado auditado no coincide con la transición de ReviewDecision."
            )
        for artifact in self.artifacts:
            ReviewArtifactRef(
                artifact_id=artifact.artifact_id,
                content_hash=artifact.content_hash,
                task_id=artifact.task_id,
                role=artifact.role,
                metadata={},
            )
        return self


class ReviewPersistenceResult(BaseModel):
    """Logical result of recording one review decision through F3."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    record: ReviewAuditRecord
    artifact_id: str = Field(..., min_length=1)
    content_hash: str = Field(..., min_length=1)
    created_at: str = Field(..., min_length=1)
    deduplicated: bool
    event_created: bool
    audit_event_published: bool


class ReviewAuditRecorder:
    """Persist review audit records using the existing F3 ``MetadataStore``."""

    def __init__(
        self,
        metadata_store: MetadataStore,
        *,
        message_bus: MessageBus | None = None,
    ) -> None:
        if not isinstance(metadata_store, MetadataStore):
            raise TypeError("metadata_store debe ser una instancia de MetadataStore.")
        if message_bus is not None and not isinstance(message_bus, MessageBus):
            raise TypeError("message_bus debe ser MessageBus o None.")
        self._metadata_store = metadata_store
        self._message_bus = message_bus

    def record(
        self,
        review_result: ReviewGatewayResult,
        *,
        workspace_root: str | Path,
    ) -> ReviewPersistenceResult:
        """Persist one immutable review decision and emit one audit event if new."""

        record = self.build_record(review_result)
        relative_path = self._relative_path(record.record_id)
        try:
            write_result = self._metadata_store.persist_metadata(
                workspace_root=workspace_root,
                relative_path=relative_path,
                content=record.model_dump(mode="json"),
                artifact_type="final_review_decision",
                metadata={
                    "schema_version": record.schema_version,
                    "record_id": record.record_id,
                    "project_id": record.project_id,
                    "workflow_id": record.workflow_id,
                    "run_id": record.run_id,
                    "decision_id": record.decision_id,
                    "review_state": record.state.value,
                    "review_action": record.action.value,
                    "policy_name": record.policy_name,
                },
                artifact_id=record.record_id,
                producer_role="custom",
            )
        except Exception as exc:
            raise ReviewPersistenceError(
                f"No se pudo persistir la decisión de final review '{record.decision_id}'."
            ) from exc

        artifact = write_result.artifact
        if artifact.artifact_id != record.record_id:
            raise ReviewPersistenceError(
                "MetadataStore devolvió un artifact_id distinto del record_id esperado."
            )

        audit_event_published = False
        if self._message_bus is not None and write_result.event_created:
            self._message_bus.publish(
                Message(
                    topic=REVIEW_AUDIT_TOPIC,
                    message_type=MessageType.AUDIT,
                    source="final_review.persistence",
                    correlation_id=record.run_id,
                    payload={
                        "schema_version": record.schema_version,
                        "record_id": record.record_id,
                        "project_id": record.project_id,
                        "workflow_id": record.workflow_id,
                        "run_id": record.run_id,
                        "decision_id": record.decision_id,
                        "action": record.action.value,
                        "state": record.state.value,
                        "actor": record.actor,
                        "policy_name": record.policy_name,
                        "artifact_id": artifact.artifact_id,
                        "content_hash": artifact.content_hash,
                    },
                )
            )
            audit_event_published = True

        return ReviewPersistenceResult(
            record=record,
            artifact_id=artifact.artifact_id,
            content_hash=artifact.content_hash,
            created_at=write_result.created_at,
            deduplicated=write_result.deduplicated,
            event_created=write_result.event_created,
            audit_event_published=audit_event_published,
        )

    def load(
        self,
        *,
        workspace_root: str | Path,
        record_id: str,
    ) -> ReviewAuditRecord:
        """Load and validate one known immutable review record from F3."""

        normalized_id = str(record_id).strip()
        if not normalized_id:
            raise ReviewPersistenceError("record_id no puede estar vacío.")
        try:
            payload = self._metadata_store.read_bytes(
                workspace_root,
                self._relative_path(normalized_id),
            )
            data = json.loads(payload.decode("utf-8"))
            return ReviewAuditRecord.model_validate(data)
        except (ArtifactStoreError, OSError, UnicodeError, json.JSONDecodeError, ValidationError, ValueError) as exc:
            raise ReviewPersistenceError(
                f"No se pudo cargar un registro de final review válido: '{normalized_id}'."
            ) from exc

    @classmethod
    def build_record(cls, review_result: ReviewGatewayResult) -> ReviewAuditRecord:
        """Build the durable audit snapshot without copying artifact metadata or paths."""

        if not isinstance(review_result, ReviewGatewayResult):
            raise TypeError("review_result debe ser una instancia de ReviewGatewayResult.")

        target = review_result.target
        decision = review_result.decision
        record_id = cls._record_id(
            project_id=target.project_id,
            workflow_id=target.workflow_id,
            run_id=target.run_id,
            decision_id=decision.decision_id,
        )
        artifacts = tuple(
            ReviewAuditArtifactRef(
                artifact_id=artifact.artifact_id,
                content_hash=artifact.content_hash,
                task_id=artifact.task_id,
                role=artifact.role,
            )
            for artifact in target.artifacts
        )
        return ReviewAuditRecord(
            record_id=record_id,
            project_id=target.project_id,
            workflow_id=target.workflow_id,
            run_id=target.run_id,
            previous_state=review_result.previous_state,
            state=review_result.state,
            policy_name=review_result.policy_name,
            decision_id=decision.decision_id,
            action=decision.action,
            actor=decision.actor,
            decided_at=decision.decided_at,
            comments=decision.comments,
            redo_target=decision.redo_target,
            artifacts=artifacts,
        )

    @staticmethod
    def _record_id(
        *,
        project_id: str,
        workflow_id: str,
        run_id: str,
        decision_id: str,
    ) -> str:
        return (
            "final-review:"
            f"{project_id}:{workflow_id}:{run_id}:{decision_id}"
        )

    @staticmethod
    def _relative_path(record_id: str) -> Path:
        # Percent-encoding keeps logical identifiers deterministic while avoiding
        # Windows-reserved path characters. No content hashing is reimplemented.
        filename = f"{quote(record_id, safe='-_.~')}.json"
        return Path("final_review") / "decisions" / filename


def persist_review_result(
    review_result: ReviewGatewayResult,
    *,
    metadata_store: MetadataStore,
    workspace_root: str | Path,
    message_bus: MessageBus | None = None,
) -> ReviewPersistenceResult:
    """Functional facade for one-shot F3-backed review persistence."""

    return ReviewAuditRecorder(metadata_store, message_bus=message_bus).record(
        review_result,
        workspace_root=workspace_root,
    )


__all__ = [
    "REVIEW_AUDIT_SCHEMA_VERSION",
    "REVIEW_AUDIT_TOPIC",
    "ReviewAuditArtifactRef",
    "ReviewAuditRecord",
    "ReviewAuditRecorder",
    "ReviewPersistenceResult",
    "persist_review_result",
]
