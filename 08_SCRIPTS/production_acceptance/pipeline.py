"""PM9 orchestration over the already completed PM1-PM8, F3, F7, and F8."""

from __future__ import annotations

import hashlib
import inspect
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from artifact_store import CollisionPolicy
from asset_resolution import (
    AssetResolutionBundle,
    AssetResolutionRun,
    AssetRole,
    ManifestAssetResolver,
    ResolutionStatus,
)
from canonical_subtitles import (
    CANONICAL_SUBTITLE_RELATIVE_PATH,
    CanonicalSubtitleError,
    CanonicalSubtitleResult,
    CanonicalSubtitleService,
    CanonicalSubtitleTrack,
    PhysicalAudioDurationProbe,
)
from creative_direction_planner import CreativeDirectionPlanner
from creatomate_adapter import CreatomateAdapter
from final_review import (
    ManualReviewPolicy,
    ReviewArtifactRef,
    ReviewDecision,
    ReviewExportBoundary,
    ReviewGateway,
    ReviewTarget,
    persist_review_result,
)
from metadata_store import MetadataStore
from observability_query import ObservabilityQuery, RunDiagnosticSnapshot
from production_manifest import AssetType, ProductionManifest
from production_manifest_compiler import ProductionManifestCompiler
from render_adapter import (
    RenderPlan,
    RenderResult,
    RenderStatus,
    RenderSubmission,
    RenderTargetAdapter,
)
from telemetry_engine import TelemetryEngine
from telemetry_models import TelemetryEvent
from video_store import VideoStore
from workspace_resolver import WorkspaceResolver

from .frame_rate import FrameRateProcessingError, FrameRateProcessor
from .media_probe import FFprobeInspector
from .models import (
    FrameRatePolicy,
    ProductionAcceptanceEvidence,
    ProductionPreparationEvidence,
)
from .narration_conformance import (
    NarrationConformanceInspection,
    NarrationConformancePolicy,
    inspect_narration_conformance,
)

PREPARATION_RELATIVE_PATH = Path("acceptance") / "preparation.json"
PAYLOAD_RELATIVE_PATH = Path("render") / "creatomate_payload.json"
QA_RELATIVE_PATH = Path("acceptance") / "qa_report.json"
FRAME_RATE_EVIDENCE_RELATIVE_PATH = Path("acceptance") / "frame_rate_evidence.json"
FINAL_ACCEPTANCE_RELATIVE_PATH = Path("acceptance") / "final_acceptance.json"
FINAL_VIDEO_RELATIVE_PATH = Path("final") / "short.mp4"
NORMALIZED_VIDEO_RELATIVE_DIR = Path("video") / "normalized"
TELEMETRY_RELATIVE_PATH = Path("03_TELEMETRIA") / TelemetryEngine.EVENTS_FILENAME


class ProductionAcceptanceError(RuntimeError):
    """PM9 could not complete a required production-acceptance boundary."""


class ProductionAcceptanceBlockedError(ProductionAcceptanceError):
    """PM9 stopped safely before an unauthorized or unapproved action."""


@dataclass(frozen=True, slots=True)
class PreparedProduction:
    """In-memory PM9 preparation result plus durable evidence paths."""

    project_path: Path
    manifest: ProductionManifest
    asset_run: AssetResolutionRun
    plan: RenderPlan
    submission: RenderSubmission
    evidence: ProductionPreparationEvidence
    preparation_path: Path
    payload_path: Path
    canonical_subtitles: CanonicalSubtitleResult | None
    narration_conformance: NarrationConformanceInspection | None


@dataclass(frozen=True, slots=True)
class FinalizedProduction:
    """Completed PM9 result after physical QA, F7 approval, export, and F8."""

    evidence: ProductionAcceptanceEvidence
    evidence_path: Path
    export_path: Path
    diagnostic_snapshot: RunDiagnosticSnapshot
    reused_existing: bool


class FullProductionAcceptance:
    """Run the new production model without reimplementing completed phases."""

    workflow_id = "pm9-full-production-acceptance"

    def __init__(
        self,
        *,
        workspace_resolver: WorkspaceResolver,
        asset_resolver: ManifestAssetResolver,
        ffprobe_inspector: FFprobeInspector | None = None,
        frame_rate_policy: FrameRatePolicy | None = None,
        frame_rate_processor: FrameRateProcessor | None = None,
        subtitle_duration_probe: PhysicalAudioDurationProbe | None = None,
        telemetry_engine: TelemetryEngine | None = None,
        narration_conformance_policy: NarrationConformancePolicy | None = None,
    ) -> None:
        if not isinstance(workspace_resolver, WorkspaceResolver):
            raise TypeError("workspace_resolver debe ser WorkspaceResolver.")
        if not isinstance(asset_resolver, ManifestAssetResolver):
            raise TypeError("asset_resolver debe ser ManifestAssetResolver.")
        if asset_resolver.workspace_resolver is not workspace_resolver:
            raise ValueError("asset_resolver debe compartir WorkspaceResolver.")
        self.workspace_resolver = workspace_resolver
        self.asset_resolver = asset_resolver
        self.ffprobe_inspector = ffprobe_inspector or FFprobeInspector()
        self.frame_rate_policy = frame_rate_policy or FrameRatePolicy()
        if not isinstance(self.frame_rate_policy, FrameRatePolicy):
            raise TypeError("frame_rate_policy debe ser FrameRatePolicy.")
        self.frame_rate_processor = frame_rate_processor or FrameRateProcessor(
            workspace_resolver,
            inspector=self.ffprobe_inspector,
        )
        if not isinstance(self.frame_rate_processor, FrameRateProcessor):
            raise TypeError("frame_rate_processor debe ser FrameRateProcessor.")
        if self.frame_rate_processor.workspace_resolver is not workspace_resolver:
            raise ValueError("frame_rate_processor debe compartir WorkspaceResolver.")
        self.canonical_subtitle_service = CanonicalSubtitleService(
            workspace_resolver,
            duration_probe=subtitle_duration_probe,
        )
        self.telemetry_engine = telemetry_engine or TelemetryEngine()
        self.narration_conformance_policy = (
            narration_conformance_policy or NarrationConformancePolicy()
        )
        if not isinstance(
            self.narration_conformance_policy, NarrationConformancePolicy
        ):
            raise TypeError(
                "narration_conformance_policy debe ser NarrationConformancePolicy."
            )
        self.metadata_store = MetadataStore(workspace_resolver)
        self.video_store = VideoStore(workspace_resolver)

    def prepare(
        self,
        project_path: str | Path,
        *,
        asset_types_by_sequence: Mapping[int, AssetType | str] | None = None,
        existing_asset_ids_by_sequence: Mapping[int, str] | None = None,
        stock_queries_by_sequence: Mapping[int, str] | None = None,
        on_screen_text_mode: str = "auto",
        adapter_factory: (Callable[..., RenderTargetAdapter] | None) = None,
        payload_relative_path: str | Path = PAYLOAD_RELATIVE_PATH,
        canonical_subtitles: bool = False,
        canonical_subtitle_relative_path: (
            str | Path
        ) = CANONICAL_SUBTITLE_RELATIVE_PATH,
    ) -> PreparedProduction:
        """Compile, plan, resolve, and persist a real-render submission."""

        project = Path(project_path).expanduser().resolve(strict=False)
        self.workspace_resolver.confine_path(project, "acceptance")
        compiler = ProductionManifestCompiler(
            workspace_resolver=self.workspace_resolver,
            metadata_store=self.metadata_store,
        )
        # PM3 persists the enriched canonical manifest below.  Persisting the
        # bare PM2 manifest first would make a second preparation collide with
        # the already enriched document at the same canonical path.
        compiled_manifest = compiler.compile(project)
        asset_overrides = _scene_overrides(
            compiled_manifest,
            asset_types_by_sequence,
            label="asset_types_by_sequence",
        )
        existing_overrides = _scene_overrides(
            compiled_manifest,
            existing_asset_ids_by_sequence,
            label="existing_asset_ids_by_sequence",
        )
        stock_query_overrides = _scene_overrides(
            compiled_manifest,
            stock_queries_by_sequence,
            label="stock_queries_by_sequence",
        )
        planner = CreativeDirectionPlanner(
            workspace_resolver=self.workspace_resolver,
            metadata_store=self.metadata_store,
        )
        planned = planner.plan_and_persist(
            compiled_manifest,
            workspace_root=project,
            asset_types=asset_overrides,
            existing_asset_ids=existing_overrides,
            stock_queries=stock_query_overrides,
            on_screen_text_mode=on_screen_text_mode,
        )
        asset_run = self.asset_resolver.resolve(
            planned.manifest,
            workspace_root=project,
        )
        narration_inspection: NarrationConformanceInspection | None = None
        if self.narration_conformance_policy.enabled:
            narration_inspection = inspect_narration_conformance(
                planned.manifest,
                project_path=project,
                audio_sha256_by_scene_id={
                    asset.scene_id: asset.content_sha256
                    for asset in asset_run.bundle.assets
                    if asset.role is AssetRole.SCENE_NARRATION
                    and asset.scene_id is not None
                    and asset.content_sha256 is not None
                },
                policy=self.narration_conformance_policy,
            )
        canonical_subtitle_result: CanonicalSubtitleResult | None = None
        if canonical_subtitles:
            try:
                canonical_subtitle_result = (
                    self.canonical_subtitle_service.build_and_persist(
                        planned.manifest,
                        asset_run.bundle,
                        workspace_root=project,
                        relative_path=canonical_subtitle_relative_path,
                    )
                )
            except CanonicalSubtitleError as error:
                raise ProductionAcceptanceBlockedError(
                    f"El gate editorial de subtítulos canónicos bloqueó PM9: {error}"
                ) from error
        adapter = (
            CreatomateAdapter(resolved_assets=asset_run.bundle)
            if adapter_factory is None
            else _invoke_adapter_factory(
                adapter_factory,
                asset_run.bundle,
                (
                    None
                    if canonical_subtitle_result is None
                    else canonical_subtitle_result.track
                ),
            )
        )
        if not isinstance(adapter, RenderTargetAdapter):
            raise TypeError(
                "adapter_factory debe devolver una instancia RenderTargetAdapter."
            )
        plan = adapter.compile(planned.manifest)
        submission = adapter.prepare_submission(plan)
        payload_write = self.metadata_store.persist_metadata(
            workspace_root=project,
            relative_path=payload_relative_path,
            content=plan.target_payload,
            artifact_type=f"{_provider_name(plan)}_payload",
            artifact_id=f"payload-{submission.submission_id}",
            metadata={
                "adapter_name": plan.adapter_name,
                "adapter_version": plan.adapter_version,
                "manifest_id": plan.manifest_id,
                "plan_id": plan.plan_id,
                "submission_id": submission.submission_id,
                "provider_neutral_source": True,
            },
            collision_policy=CollisionPolicy.REPLACE,
        )
        run_id = f"pm9-{submission.submission_id[-24:]}"
        blockers = _preparation_blockers(
            planned.manifest,
            asset_run,
            narration_blockers=(
                () if narration_inspection is None else narration_inspection.blockers
            ),
        )
        evidence = ProductionPreparationEvidence(
            project_id=planned.manifest.project.project_id,
            production_id=planned.manifest.project.production_id,
            manifest_id=planned.manifest.manifest_id,
            manifest_sha256=plan.manifest_sha256,
            resolution_id=asset_run.bundle.resolution_id,
            plan_id=plan.plan_id,
            submission_id=submission.submission_id,
            idempotency_key=submission.idempotency_key,
            workflow_id=self.workflow_id,
            run_id=run_id,
            scene_count=len(planned.manifest.scenes),
            persisted_asset_count=sum(
                asset.status is ResolutionStatus.PERSISTED
                for asset in asset_run.bundle.assets
            ),
            renderer_native_asset_count=sum(
                asset.status is ResolutionStatus.RENDERER_NATIVE
                for asset in asset_run.bundle.assets
            ),
            total_estimated_cost_usd=asset_run.bundle.total_estimated_cost_usd,
            total_actual_cost_usd=asset_run.bundle.total_actual_cost_usd,
            unknown_cost_count=asset_run.bundle.unknown_cost_count,
            manifest_relative_path=_relative(planned.manifest_path, project),
            asset_bundle_relative_path=asset_run.bundle_relative_path,
            payload_relative_path=_relative(Path(payload_write.artifact.path), project),
            canonical_subtitles_relative_path=(
                None
                if canonical_subtitle_result is None
                else _relative(canonical_subtitle_result.artifact_path, project)
            ),
            canonical_subtitles_sha256=(
                None
                if canonical_subtitle_result is None
                else canonical_subtitle_result.content_sha256
            ),
            canonical_subtitles_lexical_source=(
                None
                if canonical_subtitle_result is None
                else canonical_subtitle_result.track.lexical_source
            ),
            canonical_subtitles_timing_source=(
                None
                if canonical_subtitle_result is None
                else canonical_subtitle_result.track.timing_source
            ),
            narration_conformance_required=(self.narration_conformance_policy.enabled),
            narration_conformance_relative_path=(
                None
                if narration_inspection is None
                else _relative(narration_inspection.report_path, project)
            ),
            narration_conformance_sha256=(
                None
                if narration_inspection is None
                else narration_inspection.report_sha256
            ),
            narration_conformance_approved=(
                None
                if narration_inspection is None
                else bool(
                    narration_inspection.report is not None
                    and narration_inspection.report.approved
                    and not narration_inspection.blockers
                )
            ),
            ready_for_real_render=not blockers,
            blockers=blockers,
        )
        preparation_write = self.metadata_store.persist_metadata(
            workspace_root=project,
            relative_path=PREPARATION_RELATIVE_PATH,
            content=evidence.model_dump(mode="json"),
            artifact_type="production_acceptance_preparation",
            artifact_id=f"pm9-preparation-{submission.submission_id}",
            metadata={
                "project_id": evidence.project_id,
                "run_id": evidence.run_id,
                "ready_for_real_render": evidence.ready_for_real_render,
            },
            collision_policy=CollisionPolicy.REPLACE,
        )
        self._record_once(
            project,
            evidence,
            operation="workflow.started",
            stage="production_acceptance",
            success=True,
            metadata={"status": "running"},
        )
        self._record_once(
            project,
            evidence,
            operation="task.succeeded",
            stage="preparation",
            success=evidence.ready_for_real_render,
            validation_approved=evidence.ready_for_real_render,
            metadata={
                "status": (
                    "succeeded" if evidence.ready_for_real_render else "blocked"
                ),
                "task_id": "prepare",
                "manifest_id": evidence.manifest_id,
                "resolution_id": evidence.resolution_id,
                "plan_id": evidence.plan_id,
                "submission_id": evidence.submission_id,
            },
        )
        return PreparedProduction(
            project_path=project,
            manifest=planned.manifest,
            asset_run=asset_run,
            plan=plan,
            submission=submission,
            evidence=evidence,
            preparation_path=Path(preparation_write.artifact.path),
            payload_path=Path(payload_write.artifact.path),
            canonical_subtitles=canonical_subtitle_result,
            narration_conformance=narration_inspection,
        )

    def finalize(
        self,
        prepared: PreparedProduction,
        *,
        render_result: RenderResult,
        render_path: str | Path,
        review_decision: ReviewDecision | None,
    ) -> FinalizedProduction:
        """Validate a real render, require human approval, then export through F7."""

        if not isinstance(prepared, PreparedProduction):
            raise TypeError("prepared debe ser PreparedProduction.")
        if not isinstance(render_result, RenderResult):
            raise TypeError("render_result debe ser RenderResult.")
        self._validate_render_result(prepared, render_result)
        raw_media_path = Path(render_path).expanduser().resolve(strict=False)
        existing = self._reuse_existing(prepared, raw_media_path)
        if existing is not None:
            return existing

        raw_render_artifact_id = render_result.output_artifact_ids[0]
        try:
            frame_rate_result = self.frame_rate_processor.process(
                raw_media_path,
                workspace_root=prepared.project_path,
                input_artifact_id=raw_render_artifact_id,
                normalized_relative_path=(
                    NORMALIZED_VIDEO_RELATIVE_DIR
                    / f"{prepared.submission.submission_id}.mp4"
                ),
                policy=self.frame_rate_policy,
                target_fps=prepared.manifest.output.fps,
                expected_width=prepared.manifest.output.width_px,
                expected_height=prepared.manifest.output.height_px,
                expected_duration_seconds=prepared.manifest.output.duration_seconds,
            )
        except FrameRateProcessingError as error:
            raise ProductionAcceptanceBlockedError(
                f"La política física de FPS bloqueó PM9: {error}"
            ) from error
        frame_rate = frame_rate_result.evidence
        media_path = frame_rate_result.output_path
        probe = frame_rate_result.output_probe
        frame_rate_write = self.metadata_store.persist_metadata(
            workspace_root=prepared.project_path,
            relative_path=FRAME_RATE_EVIDENCE_RELATIVE_PATH,
            content=frame_rate.model_dump(mode="json"),
            artifact_type="production_acceptance_frame_rate_evidence",
            artifact_id=(
                f"pm9-fps-{frame_rate.input_probe.file_sha256[:12]}-"
                f"{frame_rate.output_probe.file_sha256[:12]}-"
                f"{frame_rate.action.value}"
            ),
            metadata={
                "manifest_id": prepared.manifest.manifest_id,
                "run_id": prepared.evidence.run_id,
                "policy_mode": frame_rate.policy.mode.value,
                "action": frame_rate.action.value,
                "target_fps": frame_rate.target_fps,
                "input_fps": frame_rate.input_probe.fps,
                "output_fps": frame_rate.output_probe.fps,
                "actual_cost_usd": frame_rate.actual_cost_usd,
                "network_called": False,
                "publication_performed": False,
            },
            collision_policy=CollisionPolicy.REPLACE,
        )
        qa_write = self.metadata_store.persist_metadata(
            workspace_root=prepared.project_path,
            relative_path=QA_RELATIVE_PATH,
            content=probe.model_dump(mode="json"),
            artifact_type="production_acceptance_qa",
            artifact_id=f"pm9-qa-{probe.file_sha256[:24]}",
            metadata={
                "manifest_id": prepared.manifest.manifest_id,
                "run_id": prepared.evidence.run_id,
                "qa_approved": probe.approved,
                "frame_rate_evidence_artifact_id": (
                    frame_rate_write.artifact.artifact_id
                ),
            },
            collision_policy=CollisionPolicy.REPLACE,
        )
        self._record_once(
            prepared.project_path,
            prepared.evidence,
            operation="task.succeeded" if probe.approved else "task.failed",
            stage="quality_gate",
            success=probe.approved,
            validation_approved=probe.approved,
            validation_score=100.0 if probe.approved else 0.0,
            validation_passing_score=100.0,
            metadata={
                "status": "succeeded" if probe.approved else "failed",
                "task_id": "quality_gate",
                "artifact_id": qa_write.artifact.artifact_id,
                "content_hash": qa_write.artifact.content_hash,
            },
        )
        if not probe.approved:
            failures = ", ".join(
                check.check_id for check in probe.checks if not check.passed
            )
            raise ProductionAcceptanceBlockedError(
                f"El MP4 no superó el gate técnico PM9: {failures}."
            )
        if review_decision is None:
            raise ProductionAcceptanceBlockedError(
                "El MP4 superó QA técnico, pero falta una ReviewDecision humana explícita."
            )
        if not isinstance(review_decision, ReviewDecision):
            raise TypeError("review_decision debe ser ReviewDecision o None.")

        review_artifact_id = frame_rate.output_artifact_id
        target = ReviewTarget(
            project_id=prepared.manifest.project.project_id,
            workflow_id=prepared.evidence.workflow_id,
            run_id=prepared.evidence.run_id,
            artifacts=(
                ReviewArtifactRef(
                    artifact_id=review_artifact_id,
                    content_hash=probe.file_sha256,
                    task_id=f"{_provider_name(prepared.plan)}-render",
                    role="final_video_candidate",
                    metadata={
                        "mime_type": "video/mp4",
                        "width_px": probe.width_px,
                        "height_px": probe.height_px,
                        "fps": probe.fps,
                        "duration_seconds": probe.duration_seconds,
                        "qa_artifact_id": qa_write.artifact.artifact_id,
                        "frame_rate_action": frame_rate.action.value,
                        "source_artifact_id": raw_render_artifact_id,
                    },
                ),
            ),
            metadata={
                "source": "pm9_full_production_acceptance",
                "quality_gate": "passed",
                "human_quality_required": True,
            },
        )
        review_result = ReviewGateway().present(
            target,
            policy=ManualReviewPolicy(),
            decision=review_decision,
        )
        persisted_review = persist_review_result(
            review_result,
            metadata_store=self.metadata_store,
            workspace_root=prepared.project_path,
        )
        self._record_once(
            prepared.project_path,
            prepared.evidence,
            operation="review.decision_recorded",
            stage="final_review",
            success=review_result.approved,
            metadata={
                "schema_version": persisted_review.record.schema_version,
                "record_id": persisted_review.record.record_id,
                "decision_id": persisted_review.record.decision_id,
                "action": persisted_review.record.action.value,
                "state": persisted_review.record.state.value,
                "policy_name": persisted_review.record.policy_name,
                "artifact_id": review_artifact_id,
                "content_hash": probe.file_sha256,
            },
        )
        if not review_result.approved:
            raise ProductionAcceptanceBlockedError(
                "F7 registró la decisión humana "
                f"'{review_result.state.value}'; la exportación permanece bloqueada."
            )

        def export_operation():
            return self.video_store.persist_video(
                workspace_root=prepared.project_path,
                relative_path=FINAL_VIDEO_RELATIVE_PATH,
                content=media_path.read_bytes(),
                artifact_type="final_video",
                mime_type="video/mp4",
                artifact_id=f"pm9-export-{probe.file_sha256[:24]}",
                metadata={
                    "manifest_id": prepared.manifest.manifest_id,
                    "resolution_id": prepared.asset_run.bundle.resolution_id,
                    "plan_id": prepared.plan.plan_id,
                    "submission_id": prepared.submission.submission_id,
                    "render_job_id": render_result.job_id,
                    "source_render_artifact_id": raw_render_artifact_id,
                    "review_artifact_id": review_artifact_id,
                    "review_decision_id": review_decision.decision_id,
                    "qa_approved": True,
                    "human_approved": True,
                    "publication_performed": False,
                    "render_provider": _provider_name(prepared.plan),
                    "frame_rate_action": frame_rate.action.value,
                    "source_fps": frame_rate.input_probe.fps,
                    "output_fps": frame_rate.output_probe.fps,
                },
                collision_policy=CollisionPolicy.REPLACE,
            )

        export_write = ReviewExportBoundary().execute(
            review_result,
            export_operation,
        )
        export_path = Path(export_write.artifact.path)
        external_job_id = _optional_text(render_result.metadata.get("external_job_id"))
        estimated_cost = round(
            prepared.asset_run.bundle.total_estimated_cost_usd
            + _non_negative_float(render_result.metadata.get("estimated_cost_usd")),
            8,
        )
        credits = _optional_non_negative_float(
            render_result.metadata.get("credits_used")
            if render_result.metadata.get("credits_used") is not None
            else render_result.metadata.get("estimated_credits")
        )
        self._record_once(
            prepared.project_path,
            prepared.evidence,
            operation="adapter.succeeded",
            stage="export",
            success=True,
            provider=_provider_name(prepared.plan),
            estimated_cost=estimated_cost,
            metadata={
                "status": "succeeded",
                "task_id": "export",
                "capability": "video_rendering",
                "adapter": prepared.plan.adapter_name,
                "result_id": render_result.job_id,
                "artifact_refs": [
                    {
                        "artifact_id": export_write.artifact.artifact_id,
                        "content_hash": export_write.artifact.content_hash,
                        "artifact_type": "final_video",
                    }
                ],
            },
        )
        self._record_once(
            prepared.project_path,
            prepared.evidence,
            operation="workflow.finished",
            stage="production_acceptance",
            success=True,
            estimated_cost=estimated_cost,
            metadata={"status": "succeeded"},
        )
        snapshot = self._snapshot(prepared)
        evidence = ProductionAcceptanceEvidence(
            project_id=prepared.manifest.project.project_id,
            production_id=prepared.manifest.project.production_id,
            manifest_id=prepared.manifest.manifest_id,
            resolution_id=prepared.asset_run.bundle.resolution_id,
            plan_id=prepared.plan.plan_id,
            submission_id=prepared.submission.submission_id,
            workflow_id=prepared.evidence.workflow_id,
            run_id=prepared.evidence.run_id,
            render_job_id=render_result.job_id,
            render_artifact_id=raw_render_artifact_id,
            render_external_job_id=external_job_id,
            frame_rate=frame_rate,
            media_probe=probe,
            qa_approved=True,
            human_approved=True,
            review_record_id=persisted_review.record.record_id,
            review_decision_id=review_decision.decision_id,
            review_state="approved",
            export_artifact_id=export_write.artifact.artifact_id,
            export_content_sha256=export_write.artifact.content_hash,
            export_relative_path=_relative(export_path, prepared.project_path),
            telemetry_relative_path=TELEMETRY_RELATIVE_PATH.as_posix(),
            observed_estimated_cost_usd=estimated_cost,
            observed_credits=credits,
            publication_performed=False,
            metadata={
                "diagnostic_status": snapshot.status,
                "diagnostic_events_total": snapshot.events_total,
                "manifest_source_reference_count": len(
                    prepared.manifest.source_references
                ),
                "asset_count": len(prepared.asset_run.bundle.assets),
                "payload_element_count": _payload_element_count(
                    prepared.plan.target_payload
                ),
                "frame_rate_action": frame_rate.action.value,
                "frame_rate_evidence_artifact_id": (
                    frame_rate_write.artifact.artifact_id
                ),
            },
        )
        evidence_write = self.metadata_store.persist_metadata(
            workspace_root=prepared.project_path,
            relative_path=FINAL_ACCEPTANCE_RELATIVE_PATH,
            content=evidence.model_dump(mode="json"),
            artifact_type="production_acceptance_evidence",
            artifact_id=f"pm9-acceptance-{prepared.submission.submission_id}",
            metadata={
                "project_id": evidence.project_id,
                "run_id": evidence.run_id,
                "qa_approved": evidence.qa_approved,
                "human_approved": evidence.human_approved,
                "review_state": evidence.review_state,
            },
            collision_policy=CollisionPolicy.REPLACE,
        )
        return FinalizedProduction(
            evidence=evidence,
            evidence_path=Path(evidence_write.artifact.path),
            export_path=export_path,
            diagnostic_snapshot=snapshot,
            reused_existing=False,
        )

    @staticmethod
    def _validate_render_result(
        prepared: PreparedProduction,
        render_result: RenderResult,
    ) -> None:
        if render_result.status is not RenderStatus.SUCCEEDED:
            raise ProductionAcceptanceBlockedError(
                f"El render no terminó en succeeded: {render_result.status.value}."
            )
        if render_result.manifest_id != prepared.manifest.manifest_id:
            raise ProductionAcceptanceError(
                "RenderResult pertenece a otro ProductionManifest."
            )
        if render_result.plan_id != prepared.plan.plan_id:
            raise ProductionAcceptanceError("RenderResult pertenece a otro RenderPlan.")
        if render_result.target_id != prepared.plan.target_id:
            raise ProductionAcceptanceError(
                "RenderResult pertenece a otro render target."
            )

    def _record_once(
        self,
        project_path: Path,
        preparation: ProductionPreparationEvidence,
        *,
        operation: str,
        stage: str,
        success: bool,
        provider: str = "",
        estimated_cost: float = 0.0,
        validation_score: float | None = None,
        validation_passing_score: float | None = None,
        validation_approved: bool | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> None:
        event_id = f"pm9-{preparation.run_id}-{operation}-{stage}"
        existing = self.telemetry_engine.read_events(
            project_path=project_path,
            run_id=preparation.run_id,
        )
        if existing.success and any(
            isinstance(event, TelemetryEvent) and event.event_id == event_id
            for event in (existing.data or [])
        ):
            return
        recorded = self.telemetry_engine.record_event(
            TelemetryEvent(
                event_id=event_id,
                timestamp="",
                project_id=preparation.project_id,
                component="production_acceptance",
                operation=operation,
                stage=stage,
                event_type=(
                    "review" if operation == "review.decision_recorded" else "execution"
                ),
                success=success,
                provider=provider,
                validation_score=validation_score,
                validation_passing_score=validation_passing_score,
                validation_approved=validation_approved,
                estimated_cost=estimated_cost,
                metadata=dict(metadata or {}),
                workflow_id=preparation.workflow_id,
                run_id=preparation.run_id,
                task_id=str((metadata or {}).get("task_id", "")),
                correlation_id=preparation.run_id,
            ),
            project_path=project_path,
            update_summary=True,
        )
        if not recorded.success:
            raise ProductionAcceptanceError(
                "F8 no pudo persistir un evento PM9: " + "; ".join(recorded.errors)
            )

    def _snapshot(self, prepared: PreparedProduction) -> RunDiagnosticSnapshot:
        result = ObservabilityQuery(self.telemetry_engine).get_run(
            prepared.evidence.run_id,
            project_path=prepared.project_path,
            project_id=prepared.evidence.project_id,
        )
        if not result.success or not isinstance(result.data, RunDiagnosticSnapshot):
            raise ProductionAcceptanceError(
                "F8 no pudo construir el snapshot diagnóstico PM9."
            )
        return result.data

    def _reuse_existing(
        self,
        prepared: PreparedProduction,
        render_path: Path,
    ) -> FinalizedProduction | None:
        if not self.metadata_store.exists(
            prepared.project_path,
            FINAL_ACCEPTANCE_RELATIVE_PATH,
        ):
            return None
        try:
            payload = self.metadata_store.read_bytes(
                prepared.project_path,
                FINAL_ACCEPTANCE_RELATIVE_PATH,
            )
            evidence = ProductionAcceptanceEvidence.model_validate_json(payload)
        except Exception as error:
            raise ProductionAcceptanceError(
                "La evidencia PM9 existente es inválida y no puede reutilizarse."
            ) from error
        if (
            evidence.manifest_id != prepared.manifest.manifest_id
            or evidence.submission_id != prepared.submission.submission_id
        ):
            raise ProductionAcceptanceError(
                "La evidencia PM9 existente pertenece a otra revisión."
            )
        if (
            not render_path.is_file()
            or _sha256(render_path) != evidence.frame_rate.input_probe.file_sha256
        ):
            raise ProductionAcceptanceError(
                "El render físico no coincide con la evidencia PM9 persistida."
            )
        export_path = prepared.project_path / evidence.export_relative_path
        if (
            not export_path.is_file()
            or _sha256(export_path) != evidence.export_content_sha256
        ):
            raise ProductionAcceptanceError(
                "La exportación física no coincide con la evidencia PM9 persistida."
            )
        return FinalizedProduction(
            evidence=evidence,
            evidence_path=prepared.project_path / FINAL_ACCEPTANCE_RELATIVE_PATH,
            export_path=export_path,
            diagnostic_snapshot=self._snapshot(prepared),
            reused_existing=True,
        )


def _scene_overrides(
    manifest: ProductionManifest,
    values: Mapping[int, Any] | None,
    *,
    label: str,
) -> dict[str, Any]:
    if values is None:
        return {}
    if not isinstance(values, Mapping):
        raise TypeError(f"{label} debe ser Mapping por sequence.")
    by_sequence = {scene.sequence: scene.scene_id for scene in manifest.scenes}
    unknown = sorted(set(values) - set(by_sequence))
    if unknown:
        raise ProductionAcceptanceError(
            f"{label} contiene secuencias inexistentes: "
            + ", ".join(str(item) for item in unknown)
        )
    return {by_sequence[int(sequence)]: value for sequence, value in values.items()}


def _invoke_adapter_factory(
    factory: Callable[..., RenderTargetAdapter],
    bundle: AssetResolutionBundle,
    canonical_track: CanonicalSubtitleTrack | None,
) -> RenderTargetAdapter:
    """Preserve legacy one-argument factories outside canonical subtitle mode."""

    try:
        signature = inspect.signature(factory)
    except (TypeError, ValueError):
        if canonical_track is None:
            return factory(bundle)
        return factory(bundle, canonical_track)
    try:
        signature.bind(bundle, canonical_track)
    except TypeError as two_argument_error:
        if canonical_track is not None:
            raise TypeError(
                "adapter_factory debe aceptar (bundle, canonical_track) cuando "
                "canonical_subtitles=True."
            ) from two_argument_error
        try:
            signature.bind(bundle)
        except TypeError as one_argument_error:
            raise TypeError(
                "adapter_factory debe aceptar bundle o (bundle, canonical_track)."
            ) from one_argument_error
        return factory(bundle)
    return factory(bundle, canonical_track)


def _provider_name(plan: RenderPlan) -> str:
    """Derive a stable telemetry/provider label from the render target."""

    provider = str(plan.target_id).split(".", 1)[0].strip().lower()
    if not provider:
        raise ProductionAcceptanceError("RenderPlan.target_id no identifica proveedor.")
    return provider


def _payload_element_count(payload: Mapping[str, Any]) -> int:
    """Count both movie-level and scene-level elements across render targets."""

    count = 0
    elements = payload.get("elements", [])
    if isinstance(elements, list):
        count += len(elements)
    scenes = payload.get("scenes", [])
    if isinstance(scenes, list):
        for scene in scenes:
            if not isinstance(scene, Mapping):
                continue
            scene_elements = scene.get("elements", [])
            if isinstance(scene_elements, list):
                count += len(scene_elements)
    return count


def _preparation_blockers(
    manifest: ProductionManifest,
    asset_run: AssetResolutionRun,
    *,
    narration_blockers: tuple[str, ...] = (),
) -> tuple[str, ...]:
    blockers: list[str] = list(narration_blockers)
    if manifest.output.width_px != 1080 or manifest.output.height_px != 1920:
        blockers.append("output_not_1080x1920")
    if manifest.output.aspect_ratio != "9:16":
        blockers.append("output_not_9_16")
    if asset_run.bundle.unknown_cost_count:
        blockers.append("unknown_asset_cost")
    if any(
        asset.status is ResolutionStatus.PERSISTED and asset.delivery_uri is None
        for asset in asset_run.bundle.assets
    ):
        blockers.append("persisted_asset_without_https_delivery")
    if any(
        asset.status is ResolutionStatus.PERSISTED and asset.selected_from_alternative
        for asset in asset_run.bundle.assets
    ):
        blockers.append("fallback_asset_requires_human_review")
    return tuple(blockers)


def _relative(path: Path, root: Path) -> str:
    return path.resolve(strict=False).relative_to(root.resolve(strict=False)).as_posix()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _optional_text(value: Any) -> str | None:
    normalized = str(value or "").strip()
    return normalized or None


def _non_negative_float(value: Any) -> float:
    try:
        number = float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0
    return max(number, 0.0)


def _optional_non_negative_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return max(number, 0.0)


__all__ = [
    "FINAL_ACCEPTANCE_RELATIVE_PATH",
    "FINAL_VIDEO_RELATIVE_PATH",
    "PAYLOAD_RELATIVE_PATH",
    "PREPARATION_RELATIVE_PATH",
    "QA_RELATIVE_PATH",
    "FinalizedProduction",
    "FullProductionAcceptance",
    "PreparedProduction",
    "ProductionAcceptanceBlockedError",
    "ProductionAcceptanceError",
]
