"""Crash-safe JSON2Video render lifecycle for PM9 acceptance."""

from __future__ import annotations

import hashlib
import json
import math
import time
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from artifact_store import CollisionPolicy
from json2video_adapter import JSON2VideoAdapter, estimate_json2video_credits
from metadata_store import MetadataStore
from production_manifest import ProductionManifest
from render_adapter import RenderResult, RenderStatus
from video_store import VideoStore
from workspace_resolver import WorkspaceResolver

from .client import JSON2VideoApiClient, JSON2VideoMovieSnapshot
from .errors import (
    JSON2VideoAmbiguousSubmissionError,
    JSON2VideoApiError,
    JSON2VideoInvalidResponseError,
    JSON2VideoPollingTimeoutError,
)


class JSON2VideoRenderService:
    """Submit once, resume safely, poll, download and persist one MP4."""

    def __init__(
        self,
        *,
        client: JSON2VideoApiClient,
        workspace_resolver: WorkspaceResolver,
        adapter: JSON2VideoAdapter,
        metadata_store: MetadataStore | None = None,
        video_store: VideoStore | None = None,
        sleep_function: Callable[[float], None] | None = None,
        clock_function: Callable[[], float] | None = None,
    ) -> None:
        if not isinstance(client, JSON2VideoApiClient):
            raise TypeError("client debe ser JSON2VideoApiClient.")
        if not isinstance(workspace_resolver, WorkspaceResolver):
            raise TypeError("workspace_resolver debe ser WorkspaceResolver.")
        if not isinstance(adapter, JSON2VideoAdapter):
            raise TypeError("adapter debe ser JSON2VideoAdapter.")
        self.client = client
        self.workspace_resolver = workspace_resolver
        self.adapter = adapter
        self.metadata_store = metadata_store or MetadataStore(workspace_resolver)
        self.video_store = video_store or VideoStore(workspace_resolver)
        self.sleep_function = sleep_function or time.sleep
        self.clock_function = clock_function or time.monotonic

    def execute(
        self,
        manifest: ProductionManifest,
        *,
        workspace_root: str | Path,
    ) -> RenderResult:
        if not isinstance(manifest, ProductionManifest):
            raise TypeError("manifest debe ser ProductionManifest.")
        workspace = Path(workspace_root).expanduser().resolve(strict=False)
        self.workspace_resolver.confine_path(workspace, "metadata")
        plan = self.adapter.compile(manifest)
        submission = self.adapter.prepare_submission(plan)
        estimated_credits = estimate_json2video_credits(
            plan.output.duration_seconds
        )
        state_path = Path("render") / f"json2video_state_{submission.submission_id}.json"
        state = self._load_state(workspace, state_path)
        restored = self._restore_result(workspace, plan, submission, state)
        if restored is not None:
            return restored

        project_id = self._resume_or_submit(
            workspace,
            state_path,
            plan,
            submission,
            state,
            estimated_credits,
        )
        snapshot = self._poll(project_id)
        if snapshot.status is RenderStatus.FAILED:
            result = RenderResult(
                job_id=_job_id(submission.submission_id),
                plan_id=plan.plan_id,
                manifest_id=plan.manifest_id,
                target_id=plan.target_id,
                status=RenderStatus.FAILED,
                error=snapshot.message or "JSON2Video indicó que el render falló.",
                metadata={
                    **snapshot.safe_metadata(),
                    "external_job_id": project_id,
                    "estimated_credits": estimated_credits,
                },
            )
            self._persist_state(
                workspace,
                state_path,
                submission.submission_id,
                {
                    **self._base_state(plan, submission, estimated_credits),
                    "state": "terminal_failed",
                    "external_job_id": project_id,
                    "error": result.error,
                    **snapshot.safe_metadata(),
                },
            )
            return result

        if snapshot.output_url is None:
            raise JSON2VideoInvalidResponseError(
                "JSON2Video terminó sin URL de descarga.",
                operation="render.download",
                category="invalid_response",
                retryable=False,
            )
        content = self.client.download_movie(snapshot.output_url)
        relative_path = Path("video") / "json2video" / f"{submission.submission_id}.mp4"
        artifact_id = "render-" + hashlib.sha256(
            f"json2video|{submission.submission_id}".encode("utf-8")
        ).hexdigest()[:24]
        write = self.video_store.persist_video(
            workspace_root=workspace,
            relative_path=relative_path,
            content=content,
            artifact_type="rendered_video",
            mime_type="video/mp4",
            artifact_id=artifact_id,
            metadata={
                "provider": "json2video",
                "source": "json2video_api",
                "external_job_id": project_id,
                "submission_id": submission.submission_id,
                "plan_id": plan.plan_id,
                "manifest_id": plan.manifest_id,
                "estimated_credits": estimated_credits,
                **snapshot.safe_metadata(),
            },
            collision_policy=CollisionPolicy.REUSE_IDENTICAL,
        )
        result_metadata: dict[str, Any] = {
            **snapshot.safe_metadata(),
            "external_job_id": project_id,
            "estimated_credits": estimated_credits,
            "content_hash": write.artifact.content_hash,
            "size_bytes": write.artifact.size_bytes,
            "deduplicated": write.deduplicated,
        }
        if snapshot.consumed_credits is not None:
            result_metadata["credits_used"] = snapshot.consumed_credits
        result = RenderResult(
            job_id=_job_id(submission.submission_id),
            plan_id=plan.plan_id,
            manifest_id=plan.manifest_id,
            target_id=plan.target_id,
            status=RenderStatus.SUCCEEDED,
            output_artifact_ids=(write.artifact.artifact_id,),
            metadata=result_metadata,
        )
        self._persist_state(
            workspace,
            state_path,
            submission.submission_id,
            {
                **self._base_state(plan, submission, estimated_credits),
                "state": "succeeded",
                "external_job_id": project_id,
                "output_artifact_id": write.artifact.artifact_id,
                "output_relative_path": relative_path.as_posix(),
                "output_content_hash": write.artifact.content_hash,
                "output_size_bytes": write.artifact.size_bytes,
                **snapshot.safe_metadata(),
            },
        )
        return result

    def _resume_or_submit(
        self,
        workspace: Path,
        state_path: Path,
        plan: Any,
        submission: Any,
        state: Mapping[str, Any] | None,
        estimated_credits: int,
    ) -> str:
        if state is not None:
            project_id = str(state.get("external_job_id", "") or "").strip()
            if project_id:
                return project_id
            if state.get("state") in {"dispatching", "ambiguous"}:
                raise JSON2VideoAmbiguousSubmissionError(
                    "Existe un envío sin project id confirmado; se bloqueó el reenvío "
                    "para evitar consumo duplicado.",
                    operation="render.submit",
                    category="provider_external",
                    retryable=False,
                    ambiguous_submission=True,
                )
        dispatching = {
            **self._base_state(plan, submission, estimated_credits),
            "state": "dispatching",
        }
        self._persist_state(
            workspace, state_path, submission.submission_id, dispatching
        )
        try:
            snapshot = self.client.create_movie(submission.payload)
        except JSON2VideoApiError as error:
            self._persist_state(
                workspace,
                state_path,
                submission.submission_id,
                {
                    **dispatching,
                    "state": "ambiguous" if error.ambiguous_submission else "failed",
                    "error": str(error),
                    "retryable": error.retryable,
                },
            )
            raise
        self._persist_state(
            workspace,
            state_path,
            submission.submission_id,
            {
                **dispatching,
                "state": "submitted",
                "external_job_id": snapshot.project_id,
                "provider_status": snapshot.provider_status,
            },
        )
        return snapshot.project_id

    def _poll(self, project_id: str) -> JSON2VideoMovieSnapshot:
        started = self.clock_function()
        while True:
            snapshot = self.client.get_movie(project_id)
            if snapshot.status in {RenderStatus.SUCCEEDED, RenderStatus.FAILED}:
                return snapshot
            if self.clock_function() - started >= self.client.config.poll_timeout_seconds:
                raise JSON2VideoPollingTimeoutError(
                    "El render no llegó a estado terminal dentro del plazo configurado.",
                    operation="render.status",
                    category="provider_external",
                    retryable=True,
                )
            self.sleep_function(self.client.config.poll_interval_seconds)

    def _load_state(
        self, workspace: Path, relative_path: Path
    ) -> Mapping[str, Any] | None:
        if not self.metadata_store.exists(workspace, relative_path):
            return None
        try:
            data = json.loads(
                self.metadata_store.read_bytes(workspace, relative_path).decode("utf-8")
            )
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise JSON2VideoInvalidResponseError(
                "El estado local de JSON2Video está dañado.",
                operation="render.idempotency",
                category="data_validation",
                retryable=False,
            ) from error
        if not isinstance(data, Mapping):
            raise JSON2VideoInvalidResponseError(
                "El estado local de JSON2Video no es un objeto.",
                operation="render.idempotency",
                category="data_validation",
                retryable=False,
            )
        return data

    def _restore_result(
        self,
        workspace: Path,
        plan: Any,
        submission: Any,
        state: Mapping[str, Any] | None,
    ) -> RenderResult | None:
        if state is None or state.get("state") != "succeeded":
            return None
        if (
            state.get("submission_id") != submission.submission_id
            or state.get("plan_id") != plan.plan_id
        ):
            raise JSON2VideoInvalidResponseError(
                "El estado local pertenece a otra preparación.",
                operation="render.idempotency",
                category="data_validation",
                retryable=False,
            )
        relative_path = str(state.get("output_relative_path", "") or "")
        content_hash = str(state.get("output_content_hash", "") or "")
        artifact_id = str(state.get("output_artifact_id", "") or "")
        if not relative_path or not content_hash or not artifact_id:
            return None
        if not self.video_store.exists(workspace, relative_path):
            return None
        if not self.video_store.verify_hash(workspace, relative_path, content_hash):
            return None
        metadata = {
            "external_job_id": str(state.get("external_job_id", "")),
            "provider_status": "done",
            "estimated_credits": state.get("estimated_credits", 0),
            "content_hash": content_hash,
            "size_bytes": state.get("output_size_bytes", 0),
            "idempotency_reused": True,
        }
        for key in ("width", "height", "duration", "consumed_credits"):
            if state.get(key) is not None:
                metadata[key] = state[key]
        if state.get("consumed_credits") is not None:
            metadata["credits_used"] = state["consumed_credits"]
        return RenderResult(
            job_id=_job_id(submission.submission_id),
            plan_id=plan.plan_id,
            manifest_id=plan.manifest_id,
            target_id=plan.target_id,
            status=RenderStatus.SUCCEEDED,
            output_artifact_ids=(artifact_id,),
            metadata=metadata,
        )

    def _persist_state(
        self,
        workspace: Path,
        relative_path: Path,
        submission_id: str,
        content: Mapping[str, Any],
    ) -> None:
        self.metadata_store.persist_metadata(
            workspace_root=workspace,
            relative_path=relative_path,
            content=dict(content),
            artifact_type="json2video_submission_state",
            metadata={"submission_id": submission_id, "provider": "json2video"},
            collision_policy=CollisionPolicy.REPLACE,
        )

    @staticmethod
    def _base_state(plan: Any, submission: Any, credits: int) -> dict[str, Any]:
        return {
            "schema_name": "cips.json2video_submission_state",
            "schema_version": "1.0",
            "provider": "json2video",
            "manifest_id": plan.manifest_id,
            "plan_id": plan.plan_id,
            "submission_id": submission.submission_id,
            "idempotency_key": submission.idempotency_key,
            "estimated_credits": credits,
        }


def _job_id(submission_id: str) -> str:
    return "rj-" + hashlib.sha256(
        f"json2video|{submission_id}".encode("utf-8")
    ).hexdigest()[:24]


__all__ = ["JSON2VideoRenderService"]
