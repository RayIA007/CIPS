from __future__ import annotations

import json
from pathlib import Path
import sys


SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from telemetry_engine import TelemetryEngine
from telemetry_models import TelemetryEvent, TelemetrySummary


def _event(**overrides: object) -> TelemetryEvent:
    values: dict[str, object] = {
        "event_id": "event-demo",
        "timestamp": "2026-08-11T23:30:00+00:00",
        "project_id": "project-demo",
        "component": "workflow_engine",
        "operation": "task.succeeded",
        "success": True,
    }
    values.update(overrides)
    return TelemetryEvent(**values)


def test_legacy_positional_constructor_contract_is_preserved() -> None:
    event = TelemetryEvent(
        "event-legacy",
        "2026-08-11T23:30:00+00:00",
        "project-legacy",
        "legacy-component",
        "legacy-operation",
        "Guion",
    )

    assert event.stage == "guion"
    assert event.workflow_id == ""
    assert event.run_id == ""
    assert event.task_id == ""
    assert event.correlation_id == ""


def test_execution_correlation_ids_are_normalized_without_inference() -> None:
    event = _event(
        workflow_id=" workflow-demo ",
        run_id=" run-demo ",
        task_id=" task-demo ",
        correlation_id=" correlation-demo ",
    )

    assert event.workflow_id == "workflow-demo"
    assert event.run_id == "run-demo"
    assert event.task_id == "task-demo"
    assert event.correlation_id == "correlation-demo"

    uncorrelated = _event()
    assert uncorrelated.correlation_id == ""


def test_execution_correlation_ids_are_serializable() -> None:
    event = _event(
        workflow_id="workflow-demo",
        run_id="run-demo",
        task_id="task-demo",
        correlation_id="run-demo",
    )

    payload = event.to_dict()
    encoded = json.dumps(payload, sort_keys=True)

    assert payload["workflow_id"] == "workflow-demo"
    assert payload["run_id"] == "run-demo"
    assert payload["task_id"] == "task-demo"
    assert payload["correlation_id"] == "run-demo"
    assert '"run_id": "run-demo"' in encoded


def test_telemetry_event_dict_round_trip_preserves_correlation() -> None:
    event = _event(
        workflow_id="workflow-demo",
        run_id="run-demo",
        task_id="task-demo",
        correlation_id="run-demo",
        metadata={"safe": True},
    )

    restored = TelemetryEvent(**event.to_dict())

    assert restored.to_dict() == event.to_dict()


def test_existing_summary_aggregation_is_unchanged_by_correlation() -> None:
    event = _event(
        workflow_id="workflow-demo",
        run_id="run-demo",
        task_id="task-demo",
        correlation_id="run-demo",
        duration_seconds=1.25,
        prompt_tokens=10,
        response_tokens=20,
        estimated_cost=0.125,
    )
    summary = TelemetrySummary(scope="project", scope_id="project-demo")

    summary.register_event(event)

    assert summary.events_total == 1
    assert summary.successful_events == 1
    assert summary.failed_events == 0
    assert summary.duration_seconds == 1.25
    assert summary.total_tokens == 30
    assert summary.estimated_cost == 0.125


def test_existing_telemetry_engine_round_trip_preserves_correlation(tmp_path: Path) -> None:
    engine = TelemetryEngine()
    event = _event(
        workflow_id="workflow-demo",
        run_id="run-demo",
        task_id="task-demo",
        correlation_id="run-demo",
    )

    recorded = engine.record_event(
        event,
        output_directory=tmp_path,
        update_summary=False,
    )
    loaded = engine.read_events(output_directory=tmp_path)

    assert recorded.success is True
    assert loaded.success is True
    assert len(loaded.data) == 1
    restored = loaded.data[0]
    assert restored.workflow_id == "workflow-demo"
    assert restored.run_id == "run-demo"
    assert restored.task_id == "task-demo"
    assert restored.correlation_id == "run-demo"
