"""F8 query and diagnostic snapshot surface over persisted CIPS telemetry.

This module is read-only. It does not create another telemetry store, event bus,
dashboard, or policy engine. It queries ``TelemetryEngine`` through its public
``read_events`` contract and projects correlated events into a safe run-level
snapshot suitable for diagnostics and tests.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Protocol

from runtime_models import EngineResult
from telemetry_models import TelemetryEvent


class TelemetryReader(Protocol):
    """Narrow query contract implemented by ``TelemetryEngine``."""

    def read_events(
        self,
        project_path: str | Path | None = None,
        output_directory: str | Path | None = None,
        project_id: str | None = None,
        stage: str | None = None,
        component: str | None = None,
        event_type: str | None = None,
        success: bool | None = None,
        limit: int | None = None,
        newest_first: bool = False,
        workflow_id: str | None = None,
        run_id: str | None = None,
        task_id: str | None = None,
        correlation_id: str | None = None,
    ) -> EngineResult: ...


@dataclass(slots=True)
class RunDiagnosticSnapshot:
    """Safe, deterministic run-level projection of correlated telemetry."""

    run_id: str
    project_id: str = ""
    workflow_id: str = ""
    status: str = "unknown"
    started_at: str = ""
    finished_at: str = ""
    duration_seconds: float = 0.0

    events_total: int = 0
    successful_events: int = 0
    failed_events: int = 0
    retry_count: int = 0
    recovered_tasks: int = 0
    exhausted_tasks: int = 0

    total_tokens: int = 0
    estimated_cost: float = 0.0
    currencies: list[str] = field(default_factory=list)
    providers: list[str] = field(default_factory=list)
    capabilities: list[str] = field(default_factory=list)

    artifacts: list[dict[str, str]] = field(default_factory=list)
    review: dict[str, Any] = field(default_factory=dict)
    failures: list[dict[str, Any]] = field(default_factory=list)
    timeline: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ObservabilityQuery:
    """Read-only query facade for F8 correlated telemetry diagnostics."""

    COMPONENT_NAME = "observability_query"
    VERSION = "0.1"

    _TIMELINE_METADATA: tuple[str, ...] = (
        "status",
        "agent",
        "capability",
        "attempt",
        "attempts",
        "max_attempts",
        "adapter",
        "result_id",
    )
    _REVIEW_METADATA: tuple[str, ...] = (
        "schema_version",
        "record_id",
        "decision_id",
        "action",
        "state",
        "policy_name",
        "artifact_id",
        "content_hash",
    )
    _ARTIFACT_FIELDS: tuple[str, ...] = (
        "artifact_id",
        "content_hash",
        "artifact_type",
    )

    def __init__(self, reader: TelemetryReader) -> None:
        if not callable(getattr(reader, "read_events", None)):
            raise TypeError("reader debe exponer read_events().")
        self._reader = reader

    def get_run(
        self,
        run_id: str,
        *,
        project_path: str | Path | None = None,
        output_directory: str | Path | None = None,
        project_id: str | None = None,
    ) -> EngineResult:
        """Return one diagnostic snapshot for ``run_id``."""
        normalized_run_id = str(run_id or "").strip()
        if not normalized_run_id:
            return EngineResult.fail(
                message="run_id es obligatorio para consultar observabilidad.",
                errors=["run_id vacío."],
                metadata={"component": self.COMPONENT_NAME},
            )

        result = self._reader.read_events(
            project_path=project_path,
            output_directory=output_directory,
            project_id=project_id,
            run_id=normalized_run_id,
        )
        if not result.success:
            return EngineResult.fail(
                message="No fue posible consultar la telemetría del run.",
                errors=list(result.errors),
                warnings=list(result.warnings),
                metadata={
                    "component": self.COMPONENT_NAME,
                    "run_id": normalized_run_id,
                },
            )

        events = [
            event
            for event in (result.data or [])
            if isinstance(event, TelemetryEvent)
            and event.run_id == normalized_run_id
        ]
        if not events:
            return EngineResult.fail(
                message="No existen eventos de telemetría para el run solicitado.",
                errors=["run_id no encontrado."],
                warnings=list(result.warnings),
                metadata={
                    "component": self.COMPONENT_NAME,
                    "run_id": normalized_run_id,
                    "events_returned": 0,
                },
            )

        snapshot = self._build_snapshot(normalized_run_id, events)
        return EngineResult.ok(
            data=snapshot,
            message="Snapshot de diagnóstico construido correctamente.",
            warnings=[*list(result.warnings), *snapshot.warnings],
            metadata={
                "component": self.COMPONENT_NAME,
                "version": self.VERSION,
                "run_id": normalized_run_id,
                "events_returned": len(events),
            },
        )

    def snapshot(self, run_id: str, **kwargs: Any) -> EngineResult:
        return self.get_run(run_id, **kwargs)

    def timeline(self, run_id: str, **kwargs: Any) -> EngineResult:
        return self._view(run_id, "timeline", **kwargs)

    def failures(self, run_id: str, **kwargs: Any) -> EngineResult:
        return self._view(run_id, "failures", **kwargs)

    def artifacts(self, run_id: str, **kwargs: Any) -> EngineResult:
        return self._view(run_id, "artifacts", **kwargs)

    def review(self, run_id: str, **kwargs: Any) -> EngineResult:
        return self._view(run_id, "review", **kwargs)

    def cost(self, run_id: str, **kwargs: Any) -> EngineResult:
        result = self.get_run(run_id, **kwargs)
        if not result.success:
            return result
        snapshot: RunDiagnosticSnapshot = result.data
        return EngineResult.ok(
            data={
                "run_id": snapshot.run_id,
                "total_tokens": snapshot.total_tokens,
                "estimated_cost": snapshot.estimated_cost,
                "currencies": list(snapshot.currencies),
            },
            message="Vista de costo observado construida correctamente.",
            warnings=list(result.warnings),
            metadata=dict(result.metadata),
        )

    def _view(self, run_id: str, field_name: str, **kwargs: Any) -> EngineResult:
        result = self.get_run(run_id, **kwargs)
        if not result.success:
            return result
        snapshot: RunDiagnosticSnapshot = result.data
        return EngineResult.ok(
            data=getattr(snapshot, field_name),
            message=f"Vista {field_name} construida correctamente.",
            warnings=list(result.warnings),
            metadata=dict(result.metadata),
        )

    def _build_snapshot(
        self,
        run_id: str,
        events: list[TelemetryEvent],
    ) -> RunDiagnosticSnapshot:
        project_ids = self._unique(event.project_id for event in events)
        workflow_ids = self._unique(event.workflow_id for event in events)
        warnings: list[str] = []
        if len(project_ids) > 1:
            warnings.append("El run contiene múltiples project_id; no se infirió uno canónico.")
        if len(workflow_ids) > 1:
            warnings.append("El run contiene múltiples workflow_id; no se infirió uno canónico.")

        timeline = [self._timeline_entry(event) for event in events]
        failures = [entry for entry in timeline if not entry["success"]]
        artifacts = self._collect_artifacts(events)
        review = self._latest_review(events)
        workflow_started = next(
            (event for event in events if event.operation == "workflow.started"),
            None,
        )
        workflow_finished = next(
            (event for event in reversed(events) if event.operation == "workflow.finished"),
            None,
        )

        status = "unknown"
        started_at = ""
        finished_at = ""
        duration_seconds = 0.0
        if workflow_started is not None:
            status = "running"
            started_at = self._safe_string(
                workflow_started.metadata.get("started_at")
            ) or workflow_started.timestamp
        if workflow_finished is not None:
            status = self._safe_string(
                workflow_finished.metadata.get("status")
            ) or status
            finished_at = self._safe_string(
                workflow_finished.metadata.get("finished_at")
            ) or workflow_finished.timestamp
            duration_seconds = max(float(workflow_finished.duration_seconds), 0.0)

        providers = self._unique(event.provider for event in events)
        capabilities = self._unique(
            self._safe_string(event.metadata.get("capability")) for event in events
        )
        currencies = self._unique(event.currency for event in events if event.currency)

        return RunDiagnosticSnapshot(
            run_id=run_id,
            project_id=project_ids[0] if len(project_ids) == 1 else "",
            workflow_id=workflow_ids[0] if len(workflow_ids) == 1 else "",
            status=status,
            started_at=started_at,
            finished_at=finished_at,
            duration_seconds=round(duration_seconds, 6),
            events_total=len(events),
            successful_events=sum(1 for event in events if event.success),
            failed_events=sum(1 for event in events if not event.success),
            retry_count=sum(max(int(event.retry_count), 0) for event in events),
            recovered_tasks=sum(1 for event in events if event.succeeded_after_retry),
            exhausted_tasks=sum(1 for event in events if event.retry_exhausted),
            total_tokens=sum(max(int(event.total_tokens), 0) for event in events),
            estimated_cost=round(
                sum(max(float(event.estimated_cost), 0.0) for event in events),
                6,
            ),
            currencies=currencies,
            providers=providers,
            capabilities=capabilities,
            artifacts=artifacts,
            review=review,
            failures=failures,
            timeline=timeline,
            warnings=warnings,
        )

    def _timeline_entry(self, event: TelemetryEvent) -> dict[str, Any]:
        entry: dict[str, Any] = {
            "event_id": event.event_id,
            "timestamp": event.timestamp,
            "component": event.component,
            "operation": event.operation,
            "event_type": event.event_type,
            "success": event.success,
            "task_id": event.task_id,
            "provider": event.provider,
            "duration_seconds": event.duration_seconds,
            "exception_type": event.exception_type,
        }
        for key in self._TIMELINE_METADATA:
            value = event.metadata.get(key)
            if isinstance(value, (str, int, float, bool)):
                entry[key] = value
        return entry

    def _collect_artifacts(self, events: list[TelemetryEvent]) -> list[dict[str, str]]:
        artifacts: list[dict[str, str]] = []
        seen: set[tuple[tuple[str, str], ...]] = set()
        for event in events:
            raw_refs = event.metadata.get("artifact_refs")
            if not isinstance(raw_refs, list):
                continue
            for raw_ref in raw_refs:
                if not isinstance(raw_ref, dict):
                    continue
                ref = {
                    key: self._safe_string(raw_ref.get(key))
                    for key in self._ARTIFACT_FIELDS
                    if self._safe_string(raw_ref.get(key))
                }
                if not (ref.get("artifact_id") or ref.get("content_hash")):
                    continue
                identity = tuple(sorted(ref.items()))
                if identity in seen:
                    continue
                seen.add(identity)
                artifacts.append(ref)
        return artifacts

    def _latest_review(self, events: list[TelemetryEvent]) -> dict[str, Any]:
        review_event = next(
            (
                event
                for event in reversed(events)
                if event.operation == "review.decision_recorded"
            ),
            None,
        )
        if review_event is None:
            return {}
        review: dict[str, Any] = {
            "timestamp": review_event.timestamp,
            "success": review_event.success,
        }
        for key in self._REVIEW_METADATA:
            value = review_event.metadata.get(key)
            if isinstance(value, (str, int, float, bool)):
                review[key] = value
        return review

    @staticmethod
    def _unique(values: Any) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()
        for value in values:
            normalized = str(value or "").strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            result.append(normalized)
        return result

    @staticmethod
    def _safe_string(value: Any) -> str:
        return str(value or "").strip()
