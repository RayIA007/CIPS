from __future__ import annotations

from pathlib import Path
import sys

import pytest
from pydantic import ValidationError

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from cips_core.adapters.contracts import TASK_ARTIFACT_REF_KEY
from cips_core.adapters.media import VideoMediaAdapter
from cips_core.facade import CIPSOrchestrator
from video_pipeline import VideoPipelineCompiler, VideoPipelineLoader, VideoPipelineRunner


ARTIFACT_YAML = """
pipeline_id: f6-artifact-inputs
name: Artifact-aware declarative video
version: 1.0.0
scenes:
  - scene_id: source
    prompt: Render the source scene.
    duration: 2
    artifact_target:
      platform: f6-test
      relative_path: video/source.mp4
      mime_type: video/mp4
  - scene_id: consumer
    prompt: Render using the previous artifact.
    duration: 3
    dependencies:
      - source
    media_refs:
      - scene_id: source
        artifact_index: 0
        role: source_video
      - image:external
    artifact_target:
      platform: f6-test
      relative_path: video/consumer.mp4
      mime_type: video/mp4
"""


def test_compiler_emits_logical_artifact_target_and_core_reference_marker() -> None:
    spec = VideoPipelineLoader.loads(ARTIFACT_YAML)
    workflow = VideoPipelineCompiler.compile(spec)
    source, consumer = workflow.tasks

    assert source.input_data["artifact_target"] == {
        "platform": "f6-test",
        "relative_path": "video/source.mp4",
        "mime_type": "video/mp4",
        "metadata": {},
    }
    assert consumer.input_data["media_refs"][0] == {
        TASK_ARTIFACT_REF_KEY: {
            "task_id": "source",
            "artifact_index": 0,
            "role": "source_video",
        }
    }
    assert consumer.input_data["media_refs"][1] == "image:external"


def test_artifact_reference_requires_dependency_and_persisted_source() -> None:
    without_dependency = ARTIFACT_YAML.replace(
        "    dependencies:\n      - source\n",
        "",
        1,
    )
    with pytest.raises(ValidationError, match="requiere declarar esa escena en dependencies"):
        VideoPipelineLoader.loads(without_dependency)

    without_target = ARTIFACT_YAML.replace(
        "    artifact_target:\n      platform: f6-test\n      relative_path: video/source.mp4\n      mime_type: video/mp4\n",
        "",
        1,
    )
    with pytest.raises(ValidationError, match="debe declarar artifact_target"):
        VideoPipelineLoader.loads(without_target)


def test_core_keeps_artifacts_separate_from_task_outputs_and_exposes_them_downstream() -> None:
    spec = VideoPipelineLoader.loads(ARTIFACT_YAML)
    observed_packages = []

    def provider_executor(package):
        observed_packages.append(package)
        return f"bytes-{len(observed_packages)}".encode()

    def artifact_handler(result, request):
        return (
            {
                "artifact_type": "video",
                "artifact_id": f"artifact-{request.context.task_id}",
                "path": f"/synthetic/{request.context.task_id}.mp4",
                "mime_type": "video/mp4",
                "content_hash": f"hash-{request.context.task_id}",
            },
        )

    adapter = VideoMediaAdapter(
        provider_executor=provider_executor,
        artifact_handler=artifact_handler,
    )
    orchestrator = CIPSOrchestrator()
    orchestrator.register_agent(
        name="VideoMediaAdapter",
        handler=adapter,
        capabilities={"video_rendering"},
    )

    result = VideoPipelineRunner(orchestrator).run(spec, project_id="project-f64")

    assert result.succeeded
    assert set(result.context.task_outputs) == {"source", "consumer"}
    assert set(result.context.task_artifacts) == {"source", "consumer"}
    assert "artifacts" not in result.context.task_outputs["source"]

    resolved_refs = observed_packages[1].provider_payload["media_refs"]
    assert resolved_refs[0]["artifact_id"] == "artifact-source"
    assert resolved_refs[0]["source_task_id"] == "source"
    assert resolved_refs[0]["artifact_index"] == 0
    assert resolved_refs[0]["role"] == "source_video"
    assert resolved_refs[1] == "image:external"


def test_runtime_rejects_reference_when_requested_artifact_index_does_not_exist() -> None:
    bad_yaml = ARTIFACT_YAML.replace("artifact_index: 0", "artifact_index: 1", 1)
    spec = VideoPipelineLoader.loads(bad_yaml)

    adapter = VideoMediaAdapter(
        provider_executor=lambda package: b"synthetic",
        artifact_handler=lambda result, request: ({"artifact_id": "only-one"},),
    )
    orchestrator = CIPSOrchestrator()
    orchestrator.register_agent(
        name="VideoMediaAdapter",
        handler=adapter,
        capabilities={"video_rendering"},
    )

    result = VideoPipelineRunner(orchestrator).run(spec, project_id="project-f64")
    assert not result.succeeded
    assert "solicita índice 1" in result.error
