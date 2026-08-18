from __future__ import annotations

import hashlib
import json
from pathlib import Path

from production_final_review import ProductionFinalReviewBridge
from runtime_models import Project


def _write_final_artifact(project_path: Path) -> tuple[str, str]:
    final_dir = project_path / "final"
    final_dir.mkdir(parents=True, exist_ok=True)
    video = final_dir / "short.mp4"
    video.write_bytes(b"\x00\x00\x00\x18ftypmp42production-video")
    content_hash = hashlib.sha256(video.read_bytes()).hexdigest()
    artifact_id = "artifact-final-video"
    Path(f"{video}.meta.json").write_text(
        json.dumps(
            {
                "content_hash": content_hash,
                "events": [
                    {
                        "artifact_id": artifact_id,
                        "artifact_type": "video",
                        "requested_relative_path": "final/short.mp4",
                    }
                ],
                "media_type": "video",
                "mime_type": "video/mp4",
                "relative_path": "final/short.mp4",
                "schema_version": "1.0",
            }
        ),
        encoding="utf-8",
    )
    return artifact_id, content_hash


def test_approved_review_evidence_must_match_current_final_artifact(tmp_path: Path) -> None:
    artifact_id, content_hash = _write_final_artifact(tmp_path)
    decisions = tmp_path / "final_review" / "decisions"
    decisions.mkdir(parents=True)
    (decisions / "decision.json").write_text(
        json.dumps(
            {
                "project_id": "PROYECTO_TEST",
                "state": "approved",
                "action": "approve",
                "artifacts": [
                    {
                        "artifact_id": artifact_id,
                        "content_hash": content_hash,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    assert ProductionFinalReviewBridge.has_approved_review(tmp_path) is True

    sidecar = Path(f"{tmp_path / 'final' / 'short.mp4'}.meta.json")
    payload = json.loads(sidecar.read_text(encoding="utf-8"))
    payload["content_hash"] = "f" * 64
    sidecar.write_text(json.dumps(payload), encoding="utf-8")

    assert ProductionFinalReviewBridge.has_approved_review(tmp_path) is False


def test_review_and_persist_creates_f7_approval_record(tmp_path: Path) -> None:
    artifact_id, content_hash = _write_final_artifact(tmp_path)
    project = Project(
        project_id="PROYECTO_TEST",
        path=tmp_path,
        tema="Tema",
        estado="final",
        stage_actual="final",
    )

    bridge = ProductionFinalReviewBridge()
    review_result, persistence = bridge.review_and_persist(project)

    assert review_result.approved is True
    assert review_result.state.value == "approved"
    assert review_result.decision.action.value == "approve"
    assert review_result.target.artifacts[0].artifact_id == artifact_id
    assert review_result.target.artifacts[0].content_hash == content_hash
    assert persistence.record.state.value == "approved"
    assert persistence.record.action.value == "approve"
    assert persistence.record.artifacts[0].artifact_id == artifact_id

    assert ProductionFinalReviewBridge.has_approved_review(tmp_path) is True


def test_pipeline_finalization_routes_export_through_f7_boundary() -> None:
    source = (
        Path(__file__).resolve().parents[1] / "pipeline_engine.py"
    ).read_text(encoding="utf-8")
    start = source.index("    def _finalize_and_export(")
    end = source.index("    def _build_finalization_failure(", start)
    block = source[start:end]

    assert "review_and_persist" in block
    assert "production_final_review.authorize" in block
    assert "production_final_review.execute_export" in block
    assert '"export_authorized": True' in block
    assert '"review_persisted": True' in block
    assert "project.estado = FINAL_STAGE" in block


def test_smoke_reopens_final_project_when_f7_approval_is_missing() -> None:
    source = (
        Path(__file__).resolve().parents[1] / "full_pipeline_smoke_test.py"
    ).read_text(encoding="utf-8")
    assert "ProductionFinalReviewBridge.has_approved_review(project_path)" in source
    assert 'return "control_calidad"' in source


def test_sidecar_identity_keeps_legacy_flat_artifact_id_compatibility() -> None:
    artifact_id, content_hash = ProductionFinalReviewBridge._sidecar_identity(
        {
            "artifact_id": "artifact-legacy",
            "content_hash": "a" * 64,
        }
    )

    assert artifact_id == "artifact-legacy"
    assert content_hash == "a" * 64
