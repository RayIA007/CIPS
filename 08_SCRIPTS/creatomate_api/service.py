"""PM6 render lifecycle integration over PM4, F3, and F8."""

from __future__ import annotations

import hashlib
import json
import math
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol
from uuid import uuid4

from artifact_store import CollisionPolicy
from creatomate_adapter import CreatomateAdapter
from metadata_store import MetadataStore
from production_manifest import ProductionManifest
from render_adapter import (
    RenderJob,
    RenderPlan,
    RenderResult,
    RenderStatus,
    RenderSubmission,
)
from telemetry_engine import TelemetryEngine
from telemetry_models import TelemetryAttempt, TelemetryEvent
from video_store import VideoStore
from workspace_resolver import WorkspaceResolver

from .client import (
    CreatomateApiCall,
    CreatomateApiClient,
    CreatomateBinaryCall,
    CreatomateRenderSnapshot,
)
from .errors import (
    CreatomateAmbiguousSubmissionError,
    CreatomateApiError,
    CreatomateFailureCategory,
    CreatomateInvalidResponseError,
    CreatomatePollingTimeoutError,
    CreatomateTerminalError,
)

CREATOMATE_STATE_SCHEMA = "cips.creatomate_submission_state"
CREATOMATE_STATE_VERSION = "1.0"


class TelemetryRecorder(Protocol):
    def record_event(
        self,
        event: TelemetryEvent,
        project_path: str | Path | None = None,
        output_directory: str | Path | None = None,
        update_summary: bool = True,
    ) -> Any: ...


@dataclass(frozen=True, slots=True)
class CreatomateExecutionContext:
    """Provider-neutral correlation supplied to F8."""

    workflow_id: str = "pm6-creatomate-render"
    run_id: str = ""
    task_id: str = "creatomate-render"
    correlation_id: str = ""

    def resolved(self, submission_id: str) -> CreatomateExecutionContext:
        run_id = str(self.run_id or submission_id).strip()
        return CreatomateExecutionContext(
            workflow_id=str(self.workflow_id).strip(),
            run_id=run_id,
            task_id=str(self.task_id).strip(),
            correlation_id=str(self.correlation_id or run_id).strip(),
        )


class CreatomateRenderService:
    """Execute one manifest through Creatomate with crash-safe local idempotency."""

    def __init__(
        self,
        *,
        client: CreatomateApiClient,
        workspace_resolver: WorkspaceResolver,
        adapter: CreatomateAdapter | None = None,
        metadata_store: MetadataStore | None = None,
        video_store: VideoStore | None = None,
        telemetry_recorder: TelemetryRecorder | None = None,
        telemetry_output_directory: str | Path | None = None,
        sleep_function: Callable[[float], None] | None = None,
        clock_function: Callable[[], float] | None = None,
    ) -> None:
        if not isinstance(client, CreatomateApiClient):
            raise TypeError("client debe ser CreatomateApiClient.")
        if not isinstance(workspace_resolver, WorkspaceResolver):
            raise TypeError("workspace_resolver debe ser WorkspaceResolver.")
        self.client = client
        self.workspace_resolver = workspace_resolver
        self.adapter = adapter or CreatomateAdapter()
        self.metadata_store = metadata_store or MetadataStore(workspace_resolver)
        self.video_store = video_store or VideoStore(workspace_resolver)
        if self.metadata_store.workspace_resolver is not workspace_resolver:
            raise ValueError("MetadataStore debe compartir WorkspaceResolver.")
        if self.video_store.workspace_resolver is not workspace_resolver:
            raise ValueError("VideoStore debe compartir WorkspaceResolver.")
        self.telemetry_recorder = telemetry_recorder or TelemetryEngine()
        self.telemetry_output_directory = (
            Path(telemetry_output_directory)
            if telemetry_output_directory is not None
            else None
        )
        self.sleep_function = sleep_function or time.sleep
        self.clock_function = clock_function or time.monotonic

    def execute(
        self,
        manifest: ProductionManifest,
        *,
        workspace_root: str | Path,
        context: CreatomateExecutionContext | None = None,
    ) -> RenderResult:
        """Compile, submit, poll, download, persist, and return a PM4 result."""

        if not isinstance(manifest, ProductionManifest):
            raise TypeError("manifest debe ser ProductionManifest.")
        workspace = Path(workspace_root).expanduser().resolve(strict=False)
        self.workspace_resolver.confine_path(workspace, "metadata")
        plan = self.adapter.compile(manifest)
        submission = self.adapter.prepare_submission(plan)
        correlation = (context or CreatomateExecutionContext()).resolved(
            submission.submission_id
        )
        estimated_credits = estimate_render_credits(plan)

        state = self._load_state(workspace, submission)
        restored = self._restore_result(
            state=state,
            plan=plan,
            submission=submission,
            workspace=workspace,
        )
        if restored is not None:
            self._record_event(
                operation="render.idempotency_reuse",
                success=True,
                project_id=plan.project_id,
                context=correlation,
                workspace=workspace,
                metadata={
                    "submission_id": submission.submission_id,
                    "artifact_count": len(restored.output_artifact_ids),
                    "estimated_credits": estimated_credits,
                },
            )
            return restored

        job, snapshot = self._resume_or_submit(
            state=state,
            plan=plan,
            submission=submission,
            workspace=workspace,
            context=correlation,
            estimated_credits=estimated_credits,
        )
        job, snapshot = self._wait_for_terminal(
            job=job,
            snapshot=snapshot,
            plan=plan,
            submission=submission,
            workspace=workspace,
            context=correlation,
            estimated_credits=estimated_credits,
        )

        if job.status is RenderStatus.FAILED:
            result = RenderResult(
                job_id=job.job_id,
                plan_id=plan.plan_id,
                manifest_id=plan.manifest_id,
                target_id=plan.target_id,
                status=RenderStatus.FAILED,
                error=snapshot.error_message
                or "Creatomate indicó que el render falló.",
                metadata={
                    **snapshot.safe_metadata(),
                    "external_job_id": job.external_job_id,
                    "estimated_credits": estimated_credits,
                },
            )
            self._persist_state(
                workspace,
                submission,
                self._state_payload(
                    plan=plan,
                    submission=submission,
                    state="terminal_failed",
                    job=job,
                    snapshot=snapshot,
                    error=result.error,
                    estimated_credits=estimated_credits,
                ),
            )
            self._record_event(
                operation="render.result",
                success=False,
                project_id=plan.project_id,
                context=correlation,
                workspace=workspace,
                error=result.error,
                metadata={
                    "submission_id": submission.submission_id,
                    "external_job_id": job.external_job_id,
                    "provider_status": snapshot.provider_status,
                    "estimated_credits": estimated_credits,
                },
            )
            return result

        return self._download_and_persist(
            job=job,
            snapshot=snapshot,
            plan=plan,
            submission=submission,
            workspace=workspace,
            context=correlation,
            estimated_credits=estimated_credits,
        )

    def _resume_or_submit(
        self,
        *,
        state: Mapping[str, Any] | None,
        plan: RenderPlan,
        submission: RenderSubmission,
        workspace: Path,
        context: CreatomateExecutionContext,
        estimated_credits: int,
    ) -> tuple[RenderJob, CreatomateRenderSnapshot]:
        if state is not None:
            state_name = str(state.get("state", ""))
            external_job_id = str(state.get("external_job_id", "") or "").strip()
            if external_job_id:
                call = self._call_status(
                    external_job_id=external_job_id,
                    plan=plan,
                    workspace=workspace,
                    context=context,
                )
                snapshot = self.client.parse_snapshot(
                    call.data,
                    expected_external_job_id=external_job_id,
                )
                return self._job(submission, plan, snapshot, estimated_credits), snapshot
            if state_name in {"dispatching", "ambiguous"}:
                raise CreatomateAmbiguousSubmissionError(
                    "Existe un envío anterior sin id externo confirmado; PM6 bloqueó el reenvío para evitar consumo duplicado.",
                    operation="render.submit",
                    category=CreatomateFailureCategory.PROVIDER_EXTERNAL,
                    retryable=False,
                    ambiguous_submission=True,
                )
            if state_name == "terminal_failed":
                raise CreatomateTerminalError(
                    str(state.get("error", "El envío anterior falló de forma terminal.")),
                    operation="render.submit",
                    category=_state_category(state),
                    retryable=False,
                    status_code=_optional_status_code(state.get("status_code")),
                )

        dispatching = self._state_payload(
            plan=plan,
            submission=submission,
            state="dispatching",
            estimated_credits=estimated_credits,
        )
        self._persist_state(workspace, submission, dispatching)
        try:
            call = self.client.create_render(submission)
            snapshot = self.client.parse_snapshot(call.data)
        except CreatomateApiError as error:
            failure_state = "ambiguous" if error.ambiguous_submission else (
                "retryable_failed" if error.retryable else "terminal_failed"
            )
            self._persist_state(
                workspace,
                submission,
                {
                    **dispatching,
                    "state": failure_state,
                    "error": str(error),
                    "error_category": error.category.value,
                    "retryable": error.retryable,
                    "status_code": error.status_code,
                    "updated_at": _utc_now(),
                },
            )
            self._record_event(
                operation="render.submit",
                success=False,
                project_id=plan.project_id,
                context=context,
                workspace=workspace,
                attempts=error.attempts,
                status_code=error.status_code,
                error=str(error),
                metadata={
                    "submission_id": submission.submission_id,
                    "error_category": error.category.value,
                    "ambiguous_submission": error.ambiguous_submission,
                    "estimated_credits": estimated_credits,
                },
            )
            raise

        job = self._job(submission, plan, snapshot, estimated_credits)
        self._persist_state(
            workspace,
            submission,
            self._state_payload(
                plan=plan,
                submission=submission,
                state="submitted",
                job=job,
                snapshot=snapshot,
                estimated_credits=estimated_credits,
            ),
        )
        self._record_call(
            operation="render.submit",
            call=call,
            success=True,
            project_id=plan.project_id,
            context=context,
            workspace=workspace,
            metadata={
                "submission_id": submission.submission_id,
                "external_job_id": snapshot.external_job_id,
                "provider_status": snapshot.provider_status,
                "estimated_credits": estimated_credits,
                **_credit_metadata(snapshot),
            },
        )
        return job, snapshot

    def _wait_for_terminal(
        self,
        *,
        job: RenderJob,
        snapshot: CreatomateRenderSnapshot,
        plan: RenderPlan,
        submission: RenderSubmission,
        workspace: Path,
        context: CreatomateExecutionContext,
        estimated_credits: int,
    ) -> tuple[RenderJob, CreatomateRenderSnapshot]:
        if job.status in {RenderStatus.SUCCEEDED, RenderStatus.FAILED}:
            return job, snapshot
        started = self.clock_function()
        while job.status not in {RenderStatus.SUCCEEDED, RenderStatus.FAILED}:
            elapsed = self.clock_function() - started
            if elapsed >= self.client.config.poll_timeout_seconds:
                error = CreatomatePollingTimeoutError(
                    "El render no alcanzó un estado terminal dentro del tiempo configurado.",
                    operation="render.status",
                    category=CreatomateFailureCategory.PROVIDER_EXTERNAL,
                    retryable=True,
                )
                self._persist_state(
                    workspace,
                    submission,
                    self._state_payload(
                        plan=plan,
                        submission=submission,
                        state="submitted",
                        job=job,
                        snapshot=snapshot,
                        error=str(error),
                        estimated_credits=estimated_credits,
                    ),
                )
                self._record_event(
                    operation="render.status",
                    success=False,
                    project_id=plan.project_id,
                    context=context,
                    workspace=workspace,
                    error=str(error),
                    metadata={
                        "submission_id": submission.submission_id,
                        "external_job_id": job.external_job_id,
                        "provider_status": snapshot.provider_status,
                        "timed_out": True,
                    },
                )
                raise error

            self.sleep_function(self.client.config.poll_interval_seconds)
            call = self._call_status(
                external_job_id=job.external_job_id or "",
                plan=plan,
                workspace=workspace,
                context=context,
            )
            snapshot = self.client.parse_snapshot(
                call.data,
                expected_external_job_id=job.external_job_id,
            )
            job = self._job(submission, plan, snapshot, estimated_credits)
            self._persist_state(
                workspace,
                submission,
                self._state_payload(
                    plan=plan,
                    submission=submission,
                    state="submitted",
                    job=job,
                    snapshot=snapshot,
                    estimated_credits=estimated_credits,
                ),
            )
            self._record_call(
                operation="render.status",
                call=call,
                success=True,
                project_id=plan.project_id,
                context=context,
                workspace=workspace,
                metadata={
                    "submission_id": submission.submission_id,
                    "external_job_id": snapshot.external_job_id,
                    "provider_status": snapshot.provider_status,
                    **_credit_metadata(snapshot),
                },
            )
        return job, snapshot

    def _call_status(
        self,
        *,
        external_job_id: str,
        plan: RenderPlan,
        workspace: Path,
        context: CreatomateExecutionContext,
    ) -> CreatomateApiCall:
        try:
            return self.client.get_render(external_job_id)
        except CreatomateApiError as error:
            self._record_event(
                operation="render.status",
                success=False,
                project_id=plan.project_id,
                context=context,
                workspace=workspace,
                attempts=error.attempts,
                status_code=error.status_code,
                error=str(error),
                metadata={
                    "external_job_id": external_job_id,
                    "error_category": error.category.value,
                },
            )
            raise

    def _download_and_persist(
        self,
        *,
        job: RenderJob,
        snapshot: CreatomateRenderSnapshot,
        plan: RenderPlan,
        submission: RenderSubmission,
        workspace: Path,
        context: CreatomateExecutionContext,
        estimated_credits: int,
    ) -> RenderResult:
        if snapshot.output_url is None:
            raise CreatomateInvalidResponseError(
                "El render exitoso no contiene URL de descarga.",
                operation="render.download",
                category=CreatomateFailureCategory.PROVIDER_EXTERNAL,
                retryable=False,
            )
        try:
            download = self.client.download_render(snapshot.output_url)
            _validate_mp4(download, snapshot)
        except CreatomateApiError as error:
            self._record_event(
                operation="render.download",
                success=False,
                project_id=plan.project_id,
                context=context,
                workspace=workspace,
                attempts=error.attempts,
                status_code=error.status_code,
                error=str(error),
                metadata={
                    "submission_id": submission.submission_id,
                    "external_job_id": job.external_job_id,
                    "error_category": error.category.value,
                },
            )
            raise

        self._record_binary_call(
            call=download,
            project_id=plan.project_id,
            context=context,
            workspace=workspace,
            metadata={
                "submission_id": submission.submission_id,
                "external_job_id": job.external_job_id,
                "download_size_bytes": len(download.content),
                "content_type": download.content_type,
            },
        )

        artifact_id = _artifact_id(job.job_id)
        relative_path = f"video/creatomate/{submission.submission_id}.mp4"
        artifact_metadata: dict[str, Any] = {
            "provider": "creatomate",
            "source": "creatomate_api",
            "external_job_id": job.external_job_id,
            "submission_id": submission.submission_id,
            "plan_id": plan.plan_id,
            "manifest_id": plan.manifest_id,
            "container": "mp4",
            "estimated_credits": estimated_credits,
        }
        artifact_metadata.update(snapshot.safe_metadata())
        write = self.video_store.persist_video(
            workspace_root=workspace,
            relative_path=relative_path,
            content=download.content,
            artifact_type="rendered_video",
            mime_type="video/mp4",
            metadata=artifact_metadata,
            artifact_id=artifact_id,
            collision_policy=CollisionPolicy.REUSE_IDENTICAL,
        )
        result = RenderResult(
            job_id=job.job_id,
            plan_id=plan.plan_id,
            manifest_id=plan.manifest_id,
            target_id=plan.target_id,
            status=RenderStatus.SUCCEEDED,
            output_artifact_ids=(write.artifact.artifact_id,),
            metadata={
                **snapshot.safe_metadata(),
                "external_job_id": job.external_job_id,
                "estimated_credits": estimated_credits,
                "content_hash": write.artifact.content_hash,
                "size_bytes": write.artifact.size_bytes,
                "deduplicated": write.deduplicated,
            },
        )
        self._persist_state(
            workspace,
            submission,
            {
                **self._state_payload(
                    plan=plan,
                    submission=submission,
                    state="succeeded",
                    job=job,
                    snapshot=snapshot,
                    estimated_credits=estimated_credits,
                ),
                "output_artifact_id": write.artifact.artifact_id,
                "output_relative_path": relative_path,
                "output_content_hash": write.artifact.content_hash,
                "output_size_bytes": write.artifact.size_bytes,
            },
        )
        self._record_event(
            operation="render.persist",
            success=True,
            project_id=plan.project_id,
            context=context,
            workspace=workspace,
            metadata={
                "submission_id": submission.submission_id,
                "external_job_id": job.external_job_id,
                "artifact_count": 1,
                "artifact_refs": [
                    {
                        "artifact_id": write.artifact.artifact_id,
                        "content_hash": write.artifact.content_hash,
                        "artifact_type": write.artifact.artifact_type,
                    }
                ],
                "deduplicated": write.deduplicated,
                "estimated_credits": estimated_credits,
                **_credit_metadata(snapshot),
            },
        )
        self._record_event(
            operation="render.result",
            success=True,
            project_id=plan.project_id,
            context=context,
            workspace=workspace,
            metadata={
                "submission_id": submission.submission_id,
                "external_job_id": job.external_job_id,
                "provider_status": snapshot.provider_status,
                "artifact_count": 1,
                "estimated_credits": estimated_credits,
                **_credit_metadata(snapshot),
            },
        )
        return result

    def _restore_result(
        self,
        *,
        state: Mapping[str, Any] | None,
        plan: RenderPlan,
        submission: RenderSubmission,
        workspace: Path,
    ) -> RenderResult | None:
        if state is None:
            return None
        state_name = str(state.get("state", ""))
        if state_name == "terminal_failed":
            external_job_id = str(state.get("external_job_id", "") or "").strip()
            if not external_job_id:
                return None
            return RenderResult(
                job_id=_job_id(submission),
                plan_id=plan.plan_id,
                manifest_id=plan.manifest_id,
                target_id=plan.target_id,
                status=RenderStatus.FAILED,
                error=str(state.get("error", "Creatomate indicó que el render falló.")),
                metadata={
                    "external_job_id": external_job_id,
                    "provider_status": str(state.get("provider_status", "failed")),
                },
            )
        if state_name != "succeeded":
            return None
        artifact_id = str(state.get("output_artifact_id", "") or "").strip()
        relative_path = str(state.get("output_relative_path", "") or "").strip()
        content_hash = str(state.get("output_content_hash", "") or "").strip()
        if not artifact_id or not relative_path or not content_hash:
            return None
        if not self.video_store.exists(workspace, relative_path):
            return None
        if not self.video_store.verify_hash(workspace, relative_path, content_hash):
            return None
        metadata = {
            "external_job_id": str(state.get("external_job_id", "")),
            "provider_status": "succeeded",
            "content_hash": content_hash,
            "size_bytes": state.get("output_size_bytes", 0),
            "idempotency_reused": True,
        }
        if state.get("estimated_credits") is not None:
            metadata["estimated_credits"] = state["estimated_credits"]
        if state.get("credits_used") is not None:
            metadata["credits_used"] = state["credits_used"]
        return RenderResult(
            job_id=_job_id(submission),
            plan_id=plan.plan_id,
            manifest_id=plan.manifest_id,
            target_id=plan.target_id,
            status=RenderStatus.SUCCEEDED,
            output_artifact_ids=(artifact_id,),
            metadata=metadata,
        )

    def _job(
        self,
        submission: RenderSubmission,
        plan: RenderPlan,
        snapshot: CreatomateRenderSnapshot,
        estimated_credits: int,
    ) -> RenderJob:
        return RenderJob(
            job_id=_job_id(submission),
            submission_id=submission.submission_id,
            target_id=submission.target_id,
            status=snapshot.status,
            external_job_id=snapshot.external_job_id,
            metadata={
                "provider": "creatomate",
                "plan_id": plan.plan_id,
                "manifest_id": plan.manifest_id,
                "provider_status": snapshot.provider_status,
                "estimated_credits": estimated_credits,
                **_credit_metadata(snapshot),
            },
        )

    def _load_state(
        self,
        workspace: Path,
        submission: RenderSubmission,
    ) -> Mapping[str, Any] | None:
        relative_path = _state_relative_path(submission)
        if not self.metadata_store.exists(workspace, relative_path):
            return None
        try:
            decoded = json.loads(
                self.metadata_store.read_bytes(workspace, relative_path).decode("utf-8")
            )
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise CreatomateInvalidResponseError(
                "El registro local de idempotencia está dañado.",
                operation="render.idempotency",
                category=CreatomateFailureCategory.DATA_VALIDATION,
                retryable=False,
            ) from error
        if not isinstance(decoded, Mapping):
            raise CreatomateInvalidResponseError(
                "El registro local de idempotencia no es un objeto JSON.",
                operation="render.idempotency",
                category=CreatomateFailureCategory.DATA_VALIDATION,
                retryable=False,
            )
        expected = {
            "schema_name": CREATOMATE_STATE_SCHEMA,
            "schema_version": CREATOMATE_STATE_VERSION,
            "submission_id": submission.submission_id,
            "idempotency_key": submission.idempotency_key,
            "plan_id": submission.plan_id,
            "manifest_id": submission.manifest_id,
            "target_id": submission.target_id,
        }
        if any(decoded.get(key) != value for key, value in expected.items()):
            raise CreatomateInvalidResponseError(
                "El registro local no coincide con la identidad de la submission.",
                operation="render.idempotency",
                category=CreatomateFailureCategory.DATA_VALIDATION,
                retryable=False,
            )
        return dict(decoded)

    def _persist_state(
        self,
        workspace: Path,
        submission: RenderSubmission,
        state: Mapping[str, Any],
    ) -> None:
        serialized = json.dumps(dict(state), ensure_ascii=False, sort_keys=True)
        if self.client.config.api_key in serialized:
            raise RuntimeError("El estado de Creatomate intentó persistir una credencial.")
        self.metadata_store.persist_metadata(
            workspace_root=workspace,
            relative_path=_state_relative_path(submission),
            content=dict(state),
            artifact_type="creatomate_submission_state",
            metadata={
                "provider": "creatomate",
                "state": str(state.get("state", "")),
            },
            collision_policy=CollisionPolicy.REPLACE,
        )

    @staticmethod
    def _state_payload(
        *,
        plan: RenderPlan,
        submission: RenderSubmission,
        state: str,
        job: RenderJob | None = None,
        snapshot: CreatomateRenderSnapshot | None = None,
        error: str | None = None,
        estimated_credits: int,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema_name": CREATOMATE_STATE_SCHEMA,
            "schema_version": CREATOMATE_STATE_VERSION,
            "submission_id": submission.submission_id,
            "idempotency_key": submission.idempotency_key,
            "plan_id": plan.plan_id,
            "manifest_id": plan.manifest_id,
            "target_id": submission.target_id,
            "state": str(state),
            "estimated_credits": estimated_credits,
            "updated_at": _utc_now(),
        }
        if job is not None:
            payload["job_id"] = job.job_id
            payload["external_job_id"] = job.external_job_id
            payload["render_status"] = job.status.value
        if snapshot is not None:
            payload.update(snapshot.safe_metadata())
        if error:
            payload["error"] = str(error)
        return payload

    def _record_call(
        self,
        *,
        operation: str,
        call: CreatomateApiCall,
        success: bool,
        project_id: str,
        context: CreatomateExecutionContext,
        workspace: Path,
        metadata: Mapping[str, Any],
    ) -> None:
        self._record_event(
            operation=operation,
            success=success,
            project_id=project_id,
            context=context,
            workspace=workspace,
            attempts=call.attempts,
            status_code=call.status_code,
            duration_seconds=call.duration_seconds,
            metadata=metadata,
        )

    def _record_binary_call(
        self,
        *,
        call: CreatomateBinaryCall,
        project_id: str,
        context: CreatomateExecutionContext,
        workspace: Path,
        metadata: Mapping[str, Any],
    ) -> None:
        self._record_event(
            operation="render.download",
            success=True,
            project_id=project_id,
            context=context,
            workspace=workspace,
            attempts=call.attempts,
            status_code=call.status_code,
            duration_seconds=call.duration_seconds,
            metadata=metadata,
        )

    def _record_event(
        self,
        *,
        operation: str,
        success: bool,
        project_id: str,
        context: CreatomateExecutionContext,
        workspace: Path,
        attempts: tuple[Any, ...] = (),
        status_code: int | None = None,
        duration_seconds: float = 0.0,
        error: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> None:
        safe_metadata = _safe_telemetry_metadata(metadata or {})
        serialized = json.dumps(safe_metadata, ensure_ascii=False, sort_keys=True)
        if self.client.config.api_key in serialized:
            return
        normalized_attempts = [_telemetry_attempt(item) for item in attempts]
        event = TelemetryEvent(
            event_id=f"cm-{uuid4().hex}",
            timestamp=_utc_now(),
            project_id=project_id,
            component="creatomate_api",
            operation=operation,
            event_type="render",
            success=success,
            provider="creatomate",
            duration_seconds=duration_seconds,
            retry_enabled=self.client.config.max_attempts > 1,
            retry_attempts=len(normalized_attempts),
            retry_count=max(len(normalized_attempts) - 1, 0),
            retry_exhausted=(
                bool(normalized_attempts)
                and not success
                and len(normalized_attempts) >= self.client.config.max_attempts
            ),
            succeeded_after_retry=success and len(normalized_attempts) > 1,
            status_code=status_code,
            exception_type=("CreatomateApiError" if error else ""),
            attempts=normalized_attempts,
            errors=[self.client.config.redact(error)] if error else [],
            metadata=safe_metadata,
            workflow_id=context.workflow_id,
            run_id=context.run_id,
            task_id=context.task_id,
            correlation_id=context.correlation_id,
        )
        output_directory = self.telemetry_output_directory or (workspace / "telemetry")
        try:
            self.telemetry_recorder.record_event(
                event,
                output_directory=output_directory,
                update_summary=True,
            )
        except Exception:
            return


def estimate_render_credits(plan: RenderPlan) -> int:
    """Estimate credits using Creatomate's documented 100M-pixel formula."""

    if not isinstance(plan, RenderPlan):
        raise TypeError("plan debe ser RenderPlan.")
    pixels = (
        plan.output.width_px
        * plan.output.height_px
        * plan.output.fps
        * plan.output.duration_seconds
    )
    return max(1, math.ceil(pixels / 100_000_000.0))


def _validate_mp4(
    download: CreatomateBinaryCall,
    snapshot: CreatomateRenderSnapshot,
) -> None:
    if download.content_type not in {"", "application/octet-stream", "video/mp4"}:
        raise CreatomateInvalidResponseError(
            f"Content-Type inesperado para MP4: {download.content_type}.",
            operation="render.download",
            category=CreatomateFailureCategory.DATA_VALIDATION,
            retryable=False,
        )
    if len(download.content) < 12 or download.content[4:8] != b"ftyp":
        raise CreatomateInvalidResponseError(
            "La descarga no contiene una cabecera MP4/ISO-BMFF válida.",
            operation="render.download",
            category=CreatomateFailureCategory.DATA_VALIDATION,
            retryable=False,
        )
    if snapshot.output_format not in {None, "mp4"}:
        raise CreatomateInvalidResponseError(
            f"Creatomate declaró output_format={snapshot.output_format}, no mp4.",
            operation="render.download",
            category=CreatomateFailureCategory.DATA_VALIDATION,
            retryable=False,
        )
    if snapshot.file_size is not None and snapshot.file_size != len(download.content):
        raise CreatomateInvalidResponseError(
            "El tamaño descargado no coincide con file_size de Creatomate.",
            operation="render.download",
            category=CreatomateFailureCategory.DATA_VALIDATION,
            retryable=False,
        )


def _state_relative_path(submission: RenderSubmission) -> str:
    return f"metadata/creatomate/{submission.submission_id}.json"


def _job_id(submission: RenderSubmission) -> str:
    digest = hashlib.sha256(
        f"{submission.target_id}\x1f{submission.submission_id}".encode()
    ).hexdigest()
    return f"rj-{digest[:24]}"


def _artifact_id(job_id: str) -> str:
    return f"render-{job_id}"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _credit_metadata(snapshot: CreatomateRenderSnapshot) -> dict[str, float]:
    return (
        {"credits_used": snapshot.credits_used}
        if snapshot.credits_used is not None
        else {}
    )


def _optional_status_code(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        code = int(value)
    except (TypeError, ValueError):
        return None
    return code if 100 <= code <= 599 else None


def _state_category(state: Mapping[str, Any]) -> CreatomateFailureCategory:
    try:
        return CreatomateFailureCategory(str(state.get("error_category", "")))
    except ValueError:
        return CreatomateFailureCategory.PROVIDER_EXTERNAL


def _telemetry_attempt(value: Any) -> TelemetryAttempt:
    metadata = getattr(value, "metadata", {})
    safe_metadata = _safe_telemetry_metadata(
        metadata if isinstance(metadata, Mapping) else {}
    )
    return TelemetryAttempt(
        attempt_number=getattr(value, "attempt_number", 1),
        success=getattr(value, "success", False),
        duration_seconds=getattr(value, "duration_seconds", 0.0),
        delay_seconds=getattr(value, "delay_seconds", 0.0),
        retryable=getattr(value, "retryable", False),
        status_code=getattr(value, "status_code", None),
        exception_type=getattr(value, "exception_type", ""),
        matched_rule=getattr(value, "matched_rule", ""),
        message="",
        metadata=safe_metadata,
    )


def _safe_telemetry_metadata(values: Mapping[str, Any]) -> dict[str, Any]:
    allowed_scalars = {
        "submission_id",
        "external_job_id",
        "provider_status",
        "estimated_credits",
        "credits_used",
        "download_size_bytes",
        "content_type",
        "artifact_count",
        "deduplicated",
        "error_category",
        "ambiguous_submission",
        "timed_out",
        "category",
        "retryable",
        "status_code",
        "retry_after_seconds",
        "policy_delay_seconds",
        "provider_retry_after_seconds",
        "delay_source",
        "decision_reason",
        "retries_remaining",
    }
    result: dict[str, Any] = {}
    for key in allowed_scalars:
        value = values.get(key)
        if isinstance(value, (str, int, float, bool)) and not (
            isinstance(value, float) and not math.isfinite(value)
        ):
            result[key] = value
    refs = values.get("artifact_refs")
    if isinstance(refs, list):
        safe_refs: list[dict[str, str]] = []
        for item in refs:
            if not isinstance(item, Mapping):
                continue
            ref = {
                key: str(item[key])
                for key in ("artifact_id", "content_hash", "artifact_type")
                if item.get(key)
            }
            if ref:
                safe_refs.append(ref)
        if safe_refs:
            result["artifact_refs"] = safe_refs
    return result


__all__ = [
    "CREATOMATE_STATE_SCHEMA",
    "CREATOMATE_STATE_VERSION",
    "CreatomateExecutionContext",
    "CreatomateRenderService",
    "estimate_render_credits",
]
