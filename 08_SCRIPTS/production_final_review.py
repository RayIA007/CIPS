"""Production bridge from the legacy PipelineEngine finalization path to F7.

This adapter does not reimplement the F7 state machine, persistence layer, or
export boundary. It converts the already validated production final video into
a ReviewTarget, obtains an explicit approval through ReviewGateway, records the
decision through the F3-backed ReviewAuditRecorder, and exposes the existing
ReviewExportBoundary for the caller that owns export execution.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, TypeVar

from final_review.export_boundary import ReviewExportAuthorization, ReviewExportBoundary
from final_review.gateway import ReviewGateway, ReviewGatewayResult
from final_review.models import (
    ReviewAction,
    ReviewArtifactRef,
    ReviewDecision,
    ReviewState,
    ReviewTarget,
)
from final_review.persistence import ReviewAuditRecorder, ReviewPersistenceResult
from final_review.policies import ManualReviewPolicy
from metadata_store import MetadataStore
from runtime_models import Project
from workspace_resolver import WorkspaceResolver


T = TypeVar("T")


class ProductionFinalReviewError(RuntimeError):
    """Raised when production final-review evidence cannot be built safely."""


class ProductionFinalReviewBridge:
    """Connect production acceptance with the already completed F7 domain."""

    FINAL_VIDEO_RELATIVE_PATH = Path("final") / "short.mp4"
    REVIEW_ACTOR = "pipeline_control_calidad"

    def __init__(
        self,
        *,
        gateway: ReviewGateway | None = None,
        export_boundary: ReviewExportBoundary | None = None,
    ) -> None:
        self.gateway = gateway or ReviewGateway()
        self.export_boundary = export_boundary or ReviewExportBoundary()

    def review_and_persist(
        self,
        project: Project,
    ) -> tuple[ReviewGatewayResult, ReviewPersistenceResult]:
        """Create, approve, and durably persist the review for the final video."""

        target = self._build_target(project)
        artifact = target.artifacts[0]
        identity = (artifact.content_hash or artifact.artifact_id).replace(":", "-")
        stable_suffix = identity[:24]
        decided_at = datetime.now(timezone.utc).isoformat()
        decision = ReviewDecision(
            decision_id=f"production-approval-{stable_suffix}",
            action=ReviewAction.APPROVE,
            actor=self.REVIEW_ACTOR,
            decided_at=decided_at,
            comments=(
                "Aprobación automática posterior a control_calidad validado; "
                "el artifact final ya superó el quality gate multimedia."
            ),
            redo_target=None,
            metadata={
                "source": "pipeline_engine",
                "stage": "control_calidad",
                "artifact_role": "final_video",
            },
        )
        review_result = self.gateway.present(
            target,
            policy=ManualReviewPolicy(),
            current_state=ReviewState.READY_FOR_REVIEW,
            decision=decision,
        )
        if not review_result.approved:
            raise ProductionFinalReviewError(
                "Final Review no terminó en ReviewState.APPROVED."
            )

        resolver = WorkspaceResolver(
            projects_root=project.path.parent,
            outputs_root=project.path.parent / "_review_outputs",
        )
        recorder = ReviewAuditRecorder(MetadataStore(resolver))
        persistence_result = recorder.record(
            review_result,
            workspace_root=project.path,
        )
        return review_result, persistence_result

    def authorize(self, review_result: ReviewGatewayResult) -> ReviewExportAuthorization:
        """Return the F7 export authorization for an approved review result."""

        return self.export_boundary.authorize(review_result)

    def execute_export(
        self,
        review_result: ReviewGatewayResult,
        export_operation: Callable[[], T],
    ) -> T:
        """Execute export only through the F7 ReviewExportBoundary."""

        return self.export_boundary.execute(review_result, export_operation)

    def _build_target(self, project: Project) -> ReviewTarget:
        if not isinstance(project, Project):
            raise TypeError("project debe ser Project.")

        final_video = project.path / self.FINAL_VIDEO_RELATIVE_PATH
        sidecar = Path(f"{final_video}.meta.json")
        if not final_video.is_file() or final_video.stat().st_size <= 0:
            raise ProductionFinalReviewError(
                f"No existe final video revisable: {final_video}"
            )
        sidecar_data = self._read_sidecar(sidecar)
        artifact_id, content_hash = self._sidecar_identity(sidecar_data)

        artifact = ReviewArtifactRef(
            artifact_id=artifact_id,
            content_hash=content_hash,
            task_id="ensamblado",
            role="final_video",
            metadata={
                "artifact_type": sidecar_data.get(
                    "artifact_type",
                    sidecar_data.get("media_type", "video"),
                ),
                "mime_type": sidecar_data.get("mime_type", "video/mp4"),
                "size_bytes": final_video.stat().st_size,
            },
        )
        return ReviewTarget(
            project_id=project.project_id,
            workflow_id=f"production-{project.project_id}",
            run_id=f"production-{content_hash[:24]}",
            artifacts=(artifact,),
            metadata={
                "source": "legacy_production_pipeline",
                "stage": "control_calidad",
                "quality_gate": "passed",
            },
        )

    @staticmethod
    def _read_sidecar(sidecar: Path) -> dict[str, Any]:
        try:
            data = json.loads(sidecar.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ProductionFinalReviewError(
                f"No se pudo leer sidecar F3 válido: {sidecar}"
            ) from exc
        if not isinstance(data, dict):
            raise ProductionFinalReviewError(
                f"Sidecar F3 inválido: {sidecar}"
            )
        return data


    @staticmethod
    def _sidecar_identity(sidecar_data: dict[str, Any]) -> tuple[str, str]:
        """Return the F3 artifact identity from current or legacy sidecar layouts.

        Current F3 media sidecars keep ``content_hash`` at the document root and
        place ``artifact_id`` inside the durable ``events`` entries. Older test
        fixtures and compatibility data may expose ``artifact_id`` at the root.
        """

        content_hash = str(sidecar_data.get("content_hash", "")).strip().lower()
        artifact_id = str(sidecar_data.get("artifact_id", "")).strip()

        if not artifact_id:
            events = sidecar_data.get("events", [])
            if isinstance(events, list):
                relative_path = str(sidecar_data.get("relative_path", "")).strip()
                candidates = [item for item in events if isinstance(item, dict)]
                if relative_path:
                    matching = [
                        item
                        for item in candidates
                        if str(item.get("requested_relative_path", "")).strip()
                        == relative_path
                    ]
                    if matching:
                        candidates = matching
                for event in reversed(candidates):
                    candidate = str(event.get("artifact_id", "")).strip()
                    if candidate:
                        artifact_id = candidate
                        break

        if not artifact_id or not content_hash:
            raise ProductionFinalReviewError(
                "El sidecar F3 de final/short.mp4 no contiene "
                "artifact_id/content_hash utilizables."
            )
        return artifact_id, content_hash

    @classmethod
    def has_approved_review(cls, project_path: Path) -> bool:
        """Validate durable approval against the current final-video identity."""

        project_path = Path(project_path)
        final_video = project_path / cls.FINAL_VIDEO_RELATIVE_PATH
        sidecar = Path(f"{final_video}.meta.json")
        if not final_video.is_file() or not sidecar.is_file():
            return False
        try:
            sidecar_data = cls._read_sidecar(sidecar)
        except ProductionFinalReviewError:
            return False

        try:
            artifact_id, content_hash = cls._sidecar_identity(sidecar_data)
        except ProductionFinalReviewError:
            return False

        decisions_dir = project_path / "final_review" / "decisions"
        if not decisions_dir.is_dir():
            return False

        for record_path in decisions_dir.glob("*.json"):
            if record_path.name.endswith(".meta.json"):
                continue
            try:
                record = json.loads(record_path.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError):
                continue
            if not isinstance(record, dict):
                continue
            if str(record.get("state", "")).lower() != "approved":
                continue
            if str(record.get("action", "")).lower() != "approve":
                continue
            artifacts = record.get("artifacts", [])
            if not isinstance(artifacts, list):
                continue
            if any(
                isinstance(item, dict)
                and str(item.get("artifact_id", "")).strip() == artifact_id
                and str(item.get("content_hash", "")).strip().lower() == content_hash
                for item in artifacts
            ):
                return True
        return False


__all__ = [
    "ProductionFinalReviewBridge",
    "ProductionFinalReviewError",
]
