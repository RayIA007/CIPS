from __future__ import annotations

from pathlib import Path
import sys

import pytest
from pydantic import ValidationError


SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from cips_core.errors import CircularDependencyError, TaskDependencyError
from cips_core.tasks import TaskGraph, WorkflowDefinition
from video_pipeline import (
    VIDEO_RENDERING_CAPABILITY,
    VideoPipelineCompiler,
    VideoPipelineLoader,
    VideoPipelineSpec,
)


VALID_YAML = """
pipeline_id: video-demo
name: Demo declarative video
version: 1.0.0
metadata:
  project: synthetic-test
scenes:
  - scene_id: 01_intro
    name: Intro
    prompt: Establishing shot for a synthetic demo.
    duration: 5
    media_refs:
      - image:hero
    transitions:
      - kind: fade
        duration: 0.5
  - scene_id: 02_outro
    prompt: Closing shot for a synthetic demo.
    duration: 4.25
    dependencies:
      - 01_intro
    audio_track: audio:narration
    subtitle_track: subtitles:main
"""


def test_loader_builds_valid_video_pipeline_spec(tmp_path: Path) -> None:
    path = tmp_path / "video_pipeline.yaml"
    path.write_text(VALID_YAML, encoding="utf-8")

    spec = VideoPipelineLoader.load(path)

    assert isinstance(spec, VideoPipelineSpec)
    assert spec.pipeline_id == "video-demo"
    assert spec.name == "Demo declarative video"
    assert [scene.scene_id for scene in spec.scenes] == ["01_intro", "02_outro"]
    assert spec.scenes[0].duration == 5.0
    assert spec.scenes[0].transitions[0].kind == "fade"


def test_loader_rejects_text_duration_before_runtime() -> None:
    bad_yaml = VALID_YAML.replace("duration: 5\n", "duration: 5s\n", 1)

    with pytest.raises(ValidationError, match="scene.duration debe ser numérico"):
        VideoPipelineLoader.loads(bad_yaml)


def test_loader_forbids_unknown_fields() -> None:
    bad_yaml = VALID_YAML.replace("    duration: 5\n", "    duration: 5\n    duraton: 5\n", 1)

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        VideoPipelineLoader.loads(bad_yaml)


def test_compiler_maps_spec_to_existing_core_workflow_contracts() -> None:
    spec = VideoPipelineLoader.loads(VALID_YAML)

    workflow = VideoPipelineCompiler.compile(spec)

    assert isinstance(workflow, WorkflowDefinition)
    assert workflow.workflow_id == "video-demo"
    assert workflow.name == "Demo declarative video"
    assert workflow.version == "1.0.0"
    assert workflow.metadata == {"project": "synthetic-test"}
    assert [task.task_id for task in workflow.tasks] == ["01_intro", "02_outro"]
    assert all(task.capability == VIDEO_RENDERING_CAPABILITY for task in workflow.tasks)

    intro, outro = workflow.tasks
    assert intro.name == "Intro"
    assert intro.dependencies == set()
    assert intro.input_data == {
        "prompt": "Establishing shot for a synthetic demo.",
        "duration": 5.0,
        "media_refs": ["image:hero"],
        "transitions": [
            {"kind": "fade", "duration": 0.5, "parameters": {}}
        ],
    }
    assert outro.dependencies == {"01_intro"}
    assert outro.input_data["audio_track"] == "audio:narration"
    assert outro.input_data["subtitle_track"] == "subtitles:main"
    assert TaskGraph(workflow).topological_order() == ["01_intro", "02_outro"]


def test_compiler_reuses_core_validation_for_missing_dependencies() -> None:
    bad_yaml = VALID_YAML.replace("      - 01_intro\n", "      - missing_scene\n", 1)
    spec = VideoPipelineLoader.loads(bad_yaml)

    with pytest.raises(TaskDependencyError, match="missing_scene"):
        VideoPipelineCompiler.compile(spec)


def test_compiler_reuses_core_validation_for_cycles() -> None:
    cyclic_yaml = VALID_YAML.replace(
        "    media_refs:\n",
        "    dependencies:\n      - 02_outro\n    media_refs:\n",
        1,
    )
    spec = VideoPipelineLoader.loads(cyclic_yaml)

    with pytest.raises(CircularDependencyError, match="Ciclo detectado"):
        VideoPipelineCompiler.compile(spec)
