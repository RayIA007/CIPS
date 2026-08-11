from __future__ import annotations

from pathlib import Path
import sys

import pytest
from pydantic import ValidationError


SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from video_pipeline import VideoPipelineCompiler, VideoPipelineLoader


BASE_YAML = """
pipeline_id: deterministic-video
name: Deterministic video pipeline
version: 1.0.0
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


def test_scene_rejects_duplicate_dependencies() -> None:
    bad_yaml = BASE_YAML.replace(
        "      - scene_a\n    media_refs:",
        "      - scene_a\n      - scene_a\n    media_refs:",
        1,
    )

    with pytest.raises(ValidationError, match="dependencies contiene referencias duplicadas"):
        VideoPipelineLoader.loads(bad_yaml)


def test_scene_rejects_self_dependency_before_core_compilation() -> None:
    bad_yaml = BASE_YAML.replace("      - scene_a\n", "      - scene_b\n", 1)

    with pytest.raises(ValidationError, match="no puede depender de sí misma"):
        VideoPipelineLoader.loads(bad_yaml)


def test_scene_rejects_duplicate_media_refs() -> None:
    bad_yaml = BASE_YAML.replace(
        "      - image:secondary\n",
        "      - image:secondary\n      - image:secondary\n",
        1,
    )

    with pytest.raises(ValidationError, match="media_refs contiene referencias duplicadas"):
        VideoPipelineLoader.loads(bad_yaml)


def test_pipeline_rejects_duplicate_scene_ids() -> None:
    bad_yaml = BASE_YAML.replace("scene_id: scene_a", "scene_id: scene_b", 1)

    with pytest.raises(ValidationError, match="scene_id duplicados: scene_b"):
        VideoPipelineLoader.loads(bad_yaml)


def test_pipeline_rejects_unsupported_schema_version() -> None:
    bad_yaml = BASE_YAML.replace("version: 1.0.0", "version: 2.0.0", 1)

    with pytest.raises(ValidationError, match="Versión de video pipeline no soportada"):
        VideoPipelineLoader.loads(bad_yaml)


def test_dependency_order_reuses_core_without_reordering_declared_scenes() -> None:
    spec = VideoPipelineLoader.loads(BASE_YAML)

    assert [scene.scene_id for scene in spec.scenes] == ["scene_b", "scene_a"]
    assert VideoPipelineCompiler.dependency_order(spec) == ("scene_a", "scene_b")

    workflow = VideoPipelineCompiler.compile(spec)
    assert [task.task_id for task in workflow.tasks] == ["scene_b", "scene_a"]


def test_compiled_identifiers_are_stable_across_repeated_compilation() -> None:
    spec = VideoPipelineLoader.loads(BASE_YAML)

    first = VideoPipelineCompiler.compile(spec)
    second = VideoPipelineCompiler.compile(spec)

    assert first.workflow_id == second.workflow_id == "deterministic-video"
    assert [task.task_id for task in first.tasks] == ["scene_b", "scene_a"]
    assert [task.task_id for task in second.tasks] == ["scene_b", "scene_a"]
    assert VideoPipelineCompiler.dependency_order(spec) == (
        "scene_a",
        "scene_b",
    )
