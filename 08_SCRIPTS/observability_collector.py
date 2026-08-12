"""F8 execution-event collection over the existing CIPS MessageBus.

The collector is an observability adapter, not a second event bus. It subscribes
only to established Core execution topics, maps messages into ``TelemetryEvent``
records, applies a small allow-list for metadata, and delegates persistence to
an injected recorder compatible with ``TelemetryEngine.record_event``.

Collection is fail-open by design: telemetry persistence failures are counted
but never propagated back into workflow execution.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Protocol

from cips_core.messages import Message, MessageBus, MessageType
from telemetry_models import TelemetryEvent


class TelemetryRecorder(Protocol):
    """Narrow persistence contract implemented by the existing TelemetryEngine."""

    def record_event(
        self,
        event: TelemetryEvent,
        project_path: str | Path | None = None,
        output_directory: str | Path | None = None,
        update_summary: bool = True,
    ) -> Any: ...


CORE_EXECUTION_TOPICS: tuple[str, ...] = (
    "workflow.started",
    "workflow.finished",
    "task.started",
    "task.succeeded",
    "task.failed",
    "adapter.succeeded",
)

_SAFE_PAYLOAD_METADATA: tuple[str, ...] = (
    "status",
    "agent",
    "capability",
    "attempt",
    "attempts",
    "max_attempts",
    "started_at",
    "finished_at",
    "adapter",
    "result_id",
)


class ObservabilityCollector:
    """Collect Core ``Message`` objects into the existing telemetry contract."""

    def __init__(
        self,
        message_bus: MessageBus,
        recorder: TelemetryRecorder,
        *,
        project_path: str | Path | None = None,
        output_directory: str | Path | None = None,
        update_summary: bool = True,
        auto_subscribe: bool = True,
    ) -> None:
        if not isinstance(message_bus, MessageBus):
            raise TypeError("message_bus debe ser MessageBus.")
        if not callable(getattr(recorder, "record_event", None)):
            raise TypeError("recorder debe exponer record_event().")
        if project_path is None and output_directory is None:
            raise ValueError("Se requiere project_path u output_directory.")

        self._message_bus = message_bus
        self._recorder = recorder
        self._project_path = project_path
        self._output_directory = output_directory
        self._update_summary = bool(update_summary)
        self._subscribed = False
        self.collected_count = 0
        self.failure_count = 0
        self.last_failure_type = ""

        if auto_subscribe:
            self.subscribe()

    def subscribe(self) -> None:
        """Subscribe once to the established Core execution topics."""
        if self._subscribed:
            return
        for topic in CORE_EXECUTION_TOPICS:
            self._message_bus.subscribe(topic, self.collect)
        self._subscribed = True

    def collect(self, message: Message) -> TelemetryEvent | None:
        """Normalize and persist one supported Core message without raising."""
        if not isinstance(message, Message):
            raise TypeError("message debe ser Message.")
        if message.topic not in CORE_EXECUTION_TOPICS:
            return None

        try:
            event = self._to_event(message)
            result = self._recorder.record_event(
                event,
                project_path=self._project_path,
                output_directory=self._output_directory,
                update_summary=self._update_summary,
            )
        except Exception as exc:  # observability must not control execution
            self.failure_count += 1
            self.last_failure_type = exc.__class__.__name__
            return None

        if getattr(result, "success", True) is False:
            self.failure_count += 1
            self.last_failure_type = "record_failed"
            return None

        self.collected_count += 1
        self.last_failure_type = ""
        return event

    @staticmethod
    def _to_event(message: Message) -> TelemetryEvent:
        payload = dict(message.payload or {})
        metadata: dict[str, Any] = {
            "message_type": message.message_type.value,
            "source": str(message.source or ""),
            "target": str(message.target or ""),
            "priority": int(message.priority),
        }
        for key in _SAFE_PAYLOAD_METADATA:
            value = payload.get(key)
            if isinstance(value, (str, int, float, bool)):
                metadata[key] = value

        attempt_count = ObservabilityCollector._non_negative_int(
            payload.get("attempts", payload.get("attempt", 0))
        )
        max_attempts = ObservabilityCollector._non_negative_int(
            payload.get("max_attempts", 0)
        )
        retry_enabled = max_attempts > 1
        task_succeeded = message.topic == "task.succeeded"
        task_failed = message.topic == "task.failed"

        return TelemetryEvent(
            event_id=message.message_id,
            timestamp=message.created_at,
            project_id=str(payload.get("project_id", "") or ""),
            component="workflow_engine",
            operation=message.topic,
            event_type=message.message_type.value,
            success=message.message_type is not MessageType.ERROR,
            duration_seconds=ObservabilityCollector._duration_seconds(payload),
            retry_enabled=retry_enabled,
            retry_attempts=attempt_count,
            retry_count=max(attempt_count - 1, 0),
            retry_exhausted=(
                task_failed
                and retry_enabled
                and attempt_count >= max_attempts
            ),
            succeeded_after_retry=(task_succeeded and attempt_count > 1),
            exception_type=str(payload.get("exception_type", "") or ""),
            metadata=metadata,
            workflow_id=str(payload.get("workflow_id", "") or ""),
            run_id=str(payload.get("run_id", "") or ""),
            task_id=str(payload.get("task_id", "") or ""),
            correlation_id=str(message.correlation_id or ""),
        )

    @staticmethod
    def _duration_seconds(payload: dict[str, Any]) -> float:
        duration_ms = payload.get("duration_ms")
        if isinstance(duration_ms, (int, float)) and not isinstance(duration_ms, bool):
            return max(float(duration_ms), 0.0) / 1000.0

        started_at = str(payload.get("started_at", "") or "").strip()
        finished_at = str(payload.get("finished_at", "") or "").strip()
        if not started_at or not finished_at:
            return 0.0

        try:
            started = datetime.fromisoformat(started_at)
            finished = datetime.fromisoformat(finished_at)
            duration = (finished - started).total_seconds()
        except (TypeError, ValueError):
            return 0.0

        return max(duration, 0.0)

    @staticmethod
    def _non_negative_int(value: Any) -> int:
        try:
            number = int(value)
        except (TypeError, ValueError):
            return 0
        return max(number, 0)
