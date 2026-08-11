from __future__ import annotations

from pathlib import Path

import pytest

from artifact_store import ArtifactNotFoundError
from cips_core.messages import MessageBus, MessageType
from final_review import (
    ManualReviewPolicy,
    REVIEW_AUDIT_SCHEMA_VERSION,
    REVIEW_AUDIT_TOPIC,
    ReviewAction,
    ReviewArtifactRef,
    ReviewAuditRecord,
    ReviewAuditRecorder,
    ReviewDecision,
    ReviewGateway,
    ReviewPersistenceError,
    ReviewState,
    ReviewTarget,
    persist_review_result,
)
from metadata_store import MetadataStore
from workspace_resolver import WorkspaceResolver


def _review_result(
    action: ReviewAction = ReviewAction.APPROVE,
    *,
    decision_id: str = "decision:manual/001",
    comments: str | None = "Reviewed and accepted.",
    redo_target: str | None = None,
):
    target = ReviewTarget(
        project_id="project-01",
        workflow_id="workflow:video/01",
        run_id="run:2026/08/11",
        artifacts=(
            ReviewArtifactRef(
                artifact_id="artifact-video-01",
                content_hash="a" * 64,
                task_id="render-final",
                role="video",
                metadata={
                    "codec": "h264",
                    "path": r"C:\\should-not-be-persisted\\video.mp4",
                    "sidecar_path": r"C:\\should-not-be-persisted\\video.mp4.meta.json",
                    "api_token": "must-not-be-copied",
                },
            ),
        ),
        metadata={"workspace_root": r"C:\\should-not-be-persisted", "render_profile": "final"},
    )
    decision = ReviewDecision(
        decision_id=decision_id,
        action=action,
        actor="reviewer-01",
        decided_at="2026-08-11T16:00:00+00:00",
        comments=comments,
        redo_target=redo_target,
        metadata={
            "decision_origin": "manual",
            "authorization": "must-not-be-persisted",
        },
    )
    return ReviewGateway().present(
        target,
        policy=ManualReviewPolicy(),
        decision=decision,
    )


def _store(tmp_path: Path):
    resolver = WorkspaceResolver(
        projects_root=tmp_path / "projects",
        outputs_root=tmp_path / "outputs",
    )
    workspace = resolver.resolve_project_workspace("project-01", create=True)
    return MetadataStore(resolver), workspace


def test_build_record_is_minimal_logical_audit_snapshot():
    record = ReviewAuditRecorder.build_record(_review_result())

    assert record.schema_version == REVIEW_AUDIT_SCHEMA_VERSION
    assert record.state is ReviewState.APPROVED
    assert record.previous_state is ReviewState.READY_FOR_REVIEW
    assert record.artifacts[0].artifact_id == "artifact-video-01"
    payload = record.model_dump(mode="json")
    text = str(payload)
    assert "should-not-be-persisted" not in text
    assert "api_token" not in text
    assert "authorization" not in text
    assert "codec" not in text


def test_record_persists_json_through_metadata_store(tmp_path: Path):
    store, workspace = _store(tmp_path)
    result = ReviewAuditRecorder(store).record(_review_result(), workspace_root=workspace)

    assert result.artifact_id == result.record.record_id
    assert len(result.content_hash) == 64
    assert result.event_created is True
    assert result.audit_event_published is False
    persisted = [p for p in workspace.rglob("*.json") if not str(p).endswith(".meta.json")]
    assert len(persisted) == 1
    assert persisted[0].is_file()


def test_load_round_trips_validated_audit_record(tmp_path: Path):
    store, workspace = _store(tmp_path)
    recorder = ReviewAuditRecorder(store)
    written = recorder.record(_review_result(), workspace_root=workspace)

    loaded = recorder.load(workspace_root=workspace, record_id=written.record.record_id)

    assert loaded == written.record
    assert isinstance(loaded, ReviewAuditRecord)


def test_replaying_same_decision_is_idempotent_and_does_not_duplicate_audit_event(tmp_path: Path):
    store, workspace = _store(tmp_path)
    bus = MessageBus()
    recorder = ReviewAuditRecorder(store, message_bus=bus)
    review_result = _review_result()

    first = recorder.record(review_result, workspace_root=workspace)
    second = recorder.record(review_result, workspace_root=workspace)

    assert first.artifact_id == second.artifact_id
    assert first.content_hash == second.content_hash
    assert first.created_at == second.created_at
    assert first.event_created is True
    assert second.event_created is False
    assert second.deduplicated is True
    assert first.audit_event_published is True
    assert second.audit_event_published is False
    assert len(bus.history()) == 1


def test_new_record_emits_minimal_message_bus_audit_event(tmp_path: Path):
    store, workspace = _store(tmp_path)
    bus = MessageBus()
    written = ReviewAuditRecorder(store, message_bus=bus).record(
        _review_result(), workspace_root=workspace
    )

    [message] = bus.history()
    assert message.topic == REVIEW_AUDIT_TOPIC
    assert message.message_type is MessageType.AUDIT
    assert message.source == "final_review.persistence"
    assert message.correlation_id == written.record.run_id
    assert message.payload["record_id"] == written.record.record_id
    assert message.payload["decision_id"] == written.record.decision_id
    assert "comments" not in message.payload
    assert "path" not in message.payload
    assert "sidecar_path" not in message.payload


def test_changes_requested_persists_redo_target_without_rerun(tmp_path: Path):
    store, workspace = _store(tmp_path)
    review_result = _review_result(
        ReviewAction.REQUEST_CHANGES,
        decision_id="redo:guion/01",
        comments="Revise opening.",
        redo_target="guion",
    )

    written = ReviewAuditRecorder(store).record(review_result, workspace_root=workspace)

    assert written.record.state is ReviewState.CHANGES_REQUESTED
    assert written.record.redo_target == "guion"
    assert written.record.action is ReviewAction.REQUEST_CHANGES


def test_cancelled_decision_is_persisted_as_terminal_review_truth(tmp_path: Path):
    store, workspace = _store(tmp_path)
    review_result = _review_result(
        ReviewAction.CANCEL,
        decision_id="cancel:01",
        comments="Cancelled by reviewer.",
    )

    written = ReviewAuditRecorder(store).record(review_result, workspace_root=workspace)

    assert written.record.state is ReviewState.CANCELLED
    assert written.record.action is ReviewAction.CANCEL
    assert written.record.redo_target is None


def test_unsafe_logical_identifiers_are_encoded_only_inside_persistence_path(tmp_path: Path):
    store, workspace = _store(tmp_path)
    review_result = _review_result(decision_id="approve:final/01?x=1")

    written = ReviewAuditRecorder(store).record(review_result, workspace_root=workspace)

    assert "approve:final/01?x=1" in written.record.record_id
    physical = [p for p in workspace.rglob("*.json") if not str(p).endswith(".meta.json")]
    assert len(physical) == 1
    assert ":" not in physical[0].name
    assert "/" not in physical[0].name
    assert "?" not in physical[0].name
    assert "%" in physical[0].name


def test_functional_facade_uses_same_f3_persistence_contract(tmp_path: Path):
    store, workspace = _store(tmp_path)
    review_result = _review_result(decision_id="facade-01")

    written = persist_review_result(
        review_result,
        metadata_store=store,
        workspace_root=workspace,
    )

    assert written.record.decision_id == "facade-01"
    assert written.artifact_id == written.record.record_id


def test_recorder_rejects_non_metadata_store():
    with pytest.raises(TypeError, match="MetadataStore"):
        ReviewAuditRecorder(object())  # type: ignore[arg-type]


def test_recorder_rejects_non_message_bus(tmp_path: Path):
    store, _ = _store(tmp_path)
    with pytest.raises(TypeError, match="MessageBus"):
        ReviewAuditRecorder(store, message_bus=object())  # type: ignore[arg-type]


def test_build_record_rejects_non_gateway_result():
    with pytest.raises(TypeError, match="ReviewGatewayResult"):
        ReviewAuditRecorder.build_record(object())  # type: ignore[arg-type]


def test_load_unknown_record_raises_review_persistence_error(tmp_path: Path):
    store, workspace = _store(tmp_path)
    recorder = ReviewAuditRecorder(store)

    with pytest.raises(ReviewPersistenceError, match="No se pudo cargar"):
        recorder.load(workspace_root=workspace, record_id="missing-record")


def test_audit_record_rejects_state_decision_inconsistency():
    valid = ReviewAuditRecorder.build_record(_review_result())
    payload = valid.model_dump(mode="json")
    payload["state"] = ReviewState.CANCELLED.value

    with pytest.raises(ValueError, match="estado auditado"):
        ReviewAuditRecord.model_validate(payload)


def test_same_record_identity_rejects_conflicting_payload(tmp_path: Path):
    store, workspace = _store(tmp_path)
    recorder = ReviewAuditRecorder(store)
    recorder.record(_review_result(comments="first"), workspace_root=workspace)

    with pytest.raises(ReviewPersistenceError, match="No se pudo persistir"):
        recorder.record(_review_result(comments="changed"), workspace_root=workspace)
