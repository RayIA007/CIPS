from __future__ import annotations

from pathlib import Path
import sys

import pytest


SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from cips_core.facade import CIPSOrchestrator
from cips_core.tasks import TaskStatus, WorkflowStatus
from video_pipeline import (
    VIDEO_RENDERING_CAPABILITY,
    VideoPipelineLoader,
    VideoPipelineRunner,
)


EXECUTABLE_YAML = """
pipeline_id: f6-core-execution
name: F6 Core declarative execution
version: 1.0.0
metadata:
  phase: F6.3
scenes:
  - scene_id: scene_b
    prompt: Render the dependent synthetic scene.
    duration: 4
    dependencies:
      - scene_a
    media_refs:
      - image:secondary
  - scene_id: scene_a
    prompt: Render the prerequisite synthetic scene.
    duration: 3
    media_refs:
      - image:primary
"""


class SpyOrchestrator:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def run(self, workflow, *, project_id, initial_data=None, metadata=None):
        call = {
            "workflow": workflow,
            "project_id": project_id,
            "initial_data": initial_data,
            "metadata": metadata,
        }
        self.calls.append(call)
        return call


def test_runner_compiles_and_delegates_to_supplied_core_contract() -> None:
    spec = VideoPipelineLoader.loads(EXECUTABLE_YAML)
    orchestrator = SpyOrchestrator()
    runner = VideoPipelineRunner(orchestrator)

    result = runner.run(
        spec,
        project_id="project-f63",
        initial_data={"seed": "synthetic"},
        metadata={"source": "f6.3-test"},
    )

    assert result is orchestrator.calls[0]
    assert result["project_id"] == "project-f63"
    assert result["initial_data"] == {"seed": "synthetic"}
    assert result["metadata"] == {"source": "f6.3-test"}
    workflow = result["workflow"]
    assert workflow.workflow_id == "f6-core-execution"
    assert [task.task_id for task in workflow.tasks] == ["scene_b", "scene_a"]
    assert all(task.capability == VIDEO_RENDERING_CAPABILITY for task in workflow.tasks)


def test_runner_executes_via_real_core_workflow_engine_without_media_provider() -> None:
    spec = VideoPipelineLoader.loads(EXECUTABLE_YAML)
    orchestrator = CIPSOrchestrator()
    calls: list[dict[str, object]] = []

    def fake_video_handler(payload):
        calls.append(payload)
        return {
            "task_id": payload["task_id"],
            "seen_outputs": sorted(payload["task_outputs"]),
            "prompt": payload["input"]["prompt"],
        }

    orchestrator.register_agent(
        name="SyntheticVideoAgent",
        handler=fake_video_handler,
        capabilities={VIDEO_RENDERING_CAPABILITY},
    )

    result = VideoPipelineRunner(orchestrator).run(
        spec,
        project_id="project-f63",
        initial_data={"seed": "synthetic"},
        metadata={"execution": "core-only"},
    )

    assert result.succeeded
    assert result.status is WorkflowStatus.SUCCEEDED
    assert list(result.task_results) == ["scene_a", "scene_b"]
    assert [call["task_id"] for call in calls] == ["scene_a", "scene_b"]
    assert calls[0]["task_outputs"] == {}
    assert list(calls[1]["task_outputs"]) == ["scene_a"]
    assert calls[0]["shared_data"] == {"seed": "synthetic"}
    assert calls[1]["metadata"] == {"execution": "core-only"}
    assert result.task_results["scene_a"].status is TaskStatus.SUCCEEDED
    assert result.task_results["scene_b"].status is TaskStatus.SUCCEEDED
    assert result.context.task_outputs["scene_a"]["seen_outputs"] == []
    assert result.context.task_outputs["scene_b"]["seen_outputs"] == ["scene_a"]


def test_runner_preserves_core_messages_and_checkpoint_lifecycle() -> None:
    spec = VideoPipelineLoader.loads(EXECUTABLE_YAML)
    orchestrator = CIPSOrchestrator()
    orchestrator.register_agent(
        name="SyntheticVideoAgent",
        handler=lambda payload: {"task_id": payload["task_id"]},
        capabilities={VIDEO_RENDERING_CAPABILITY},
    )

    result = VideoPipelineRunner(orchestrator).run(spec, project_id="project-f63")

    topics = [message.topic for message in orchestrator.message_bus.history()]
    assert topics == [
        "workflow.started",
        "task.started",
        "task.succeeded",
        "task.started",
        "task.succeeded",
        "workflow.finished",
    ]
    checkpoint = orchestrator.checkpoint_store.load_latest(
        result.workflow_id,
        result.run_id,
    )
    assert checkpoint is not None
    assert checkpoint.status is WorkflowStatus.SUCCEEDED
    assert set(checkpoint.task_results) == {"scene_a", "scene_b"}


def test_runner_does_not_execute_dependency_after_core_failure() -> None:
    spec = VideoPipelineLoader.loads(EXECUTABLE_YAML)
    orchestrator = CIPSOrchestrator()
    calls: list[str] = []

    def failing_handler(payload):
        task_id = payload["task_id"]
        calls.append(task_id)
        if task_id == "scene_a":
            raise RuntimeError("synthetic failure")
        return {"task_id": task_id}

    orchestrator.register_agent(
        name="SyntheticVideoAgent",
        handler=failing_handler,
        capabilities={VIDEO_RENDERING_CAPABILITY},
    )

    result = VideoPipelineRunner(orchestrator).run(spec, project_id="project-f63")

    assert result.status is WorkflowStatus.FAILED
    assert calls == ["scene_a"]
    assert result.task_results["scene_a"].status is TaskStatus.FAILED
    assert "synthetic failure" in result.task_results["scene_a"].error
    assert "scene_b" not in result.task_results


def test_runner_rejects_non_video_pipeline_spec() -> None:
    runner = VideoPipelineRunner(SpyOrchestrator())
    with pytest.raises(TypeError, match="spec debe ser VideoPipelineSpec"):
        runner.run(object(), project_id="project-f63")
