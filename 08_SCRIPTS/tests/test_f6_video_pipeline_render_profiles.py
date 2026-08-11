from __future__ import annotations

from pathlib import Path
import sys

import pytest
from pydantic import ValidationError


SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from cips_core.adapters.contracts import AdapterContext, AdapterRequest
from cips_core.adapters.media import VideoMediaAdapter
from video_pipeline import VideoPipelineCompiler, VideoPipelineLoader


PROFILE_YAML = """
pipeline_id: f6-render-profile
name: Render profile and post-process integration
version: 1.0.0
scenes:
  - scene_id: preview_scene
    prompt: Render a synthetic preview scene.
    duration: 4
    media_refs:
      - image:hero
    transitions:
      - kind: fade
        duration: 0.4
    audio_track: audio:narration
    subtitle_track: subtitles:main
    render_profile: preview
    post_process_chain:
      - name: compress
        parameters:
          quality: draft
      - name: subtitle
        required: true
      - name: package
        parameters:
          container: mp4
"""


def _request(input_data):
    return AdapterRequest(
        capability="video_rendering",
        context=AdapterContext(
            project_id="project-f65",
            workflow_id="f6-render-profile",
            run_id="run-f65",
            task_id="preview_scene",
        ),
        input_data=input_data,
    )


def test_preview_profile_defaults_to_360p_without_hardcoding_renderer() -> None:
    spec = VideoPipelineLoader.loads(PROFILE_YAML)
    profile = spec.scenes[0].render_profile

    assert profile is not None
    assert profile.name == "preview"
    assert profile.max_height == 360
    assert profile.parameters == {}


def test_compiler_keeps_render_intent_and_post_process_declarative() -> None:
    task = VideoPipelineCompiler.compile(VideoPipelineLoader.loads(PROFILE_YAML)).tasks[0]

    assert task.input_data["render_profile"] == {
        "name": "preview",
        "max_height": 360,
        "parameters": {},
    }
    assert task.input_data["transitions"] == [
        {"kind": "fade", "duration": 0.4, "parameters": {}}
    ]
    assert task.input_data["audio_track"] == "audio:narration"
    assert task.input_data["subtitle_track"] == "subtitles:main"
    assert task.input_data["post_process_chain"] == [
        {"name": "compress", "required": True, "parameters": {"quality": "draft"}},
        {"name": "subtitle", "required": True, "parameters": {}},
        {"name": "package", "required": True, "parameters": {"container": "mp4"}},
    ]


def test_scene_rejects_duplicate_post_process_steps() -> None:
    bad_yaml = PROFILE_YAML.replace(
        "      - name: subtitle\n        required: true\n",
        "      - name: compress\n        required: true\n",
        1,
    )

    with pytest.raises(ValidationError, match="post_process_chain contiene pasos duplicados"):
        VideoPipelineLoader.loads(bad_yaml)


def test_media_adapter_routes_profile_to_provider_and_chain_to_f5_contract() -> None:
    task = VideoPipelineCompiler.compile(VideoPipelineLoader.loads(PROFILE_YAML)).tasks[0]
    observed_packages = []

    def provider_executor(package):
        observed_packages.append(package)
        return b"synthetic-preview"

    result = VideoMediaAdapter(provider_executor=provider_executor).execute(
        _request(task.input_data)
    )

    assert result.succeeded
    package = observed_packages[0]
    assert package.provider_payload["render_profile"] == {
        "name": "preview",
        "max_height": 360,
        "parameters": {},
    }
    assert package.provider_payload["audio_track"] == "audio:narration"
    assert package.provider_payload["subtitle_track"] == "subtitles:main"
    assert package.provider_payload["transitions"][0]["kind"] == "fade"
    assert "post_process_chain" not in package.provider_payload
    assert [step.name for step in package.post_process_chain] == [
        "compress",
        "subtitle",
        "package",
    ]
    assert package.post_process_chain[0].parameters["quality"] == "draft"
    assert result.metrics["post_process_step_count"] == 3


def test_absent_post_process_override_preserves_f5_video_defaults() -> None:
    observed_packages = []
    adapter = VideoMediaAdapter(
        provider_executor=lambda package: observed_packages.append(package) or b"video"
    )

    result = adapter.execute(
        _request({"prompt": "Synthetic final", "duration": 2, "media_refs": [], "transitions": []})
    )

    assert result.succeeded
    assert [step.name for step in observed_packages[0].post_process_chain] == [
        "compress",
        "subtitle",
        "package",
    ]


def test_explicit_empty_post_process_chain_does_not_reapply_f5_defaults() -> None:
    yaml_text = PROFILE_YAML.replace(
        "    post_process_chain:\n"
        "      - name: compress\n"
        "        parameters:\n"
        "          quality: draft\n"
        "      - name: subtitle\n"
        "        required: true\n"
        "      - name: package\n"
        "        parameters:\n"
        "          container: mp4\n",
        "    post_process_chain: []\n",
    )
    task = VideoPipelineCompiler.compile(VideoPipelineLoader.loads(yaml_text)).tasks[0]
    observed_packages = []
    adapter = VideoMediaAdapter(
        provider_executor=lambda package: observed_packages.append(package) or b"video"
    )

    result = adapter.execute(_request(task.input_data))

    assert result.succeeded
    assert observed_packages[0].post_process_chain == ()
    assert result.metrics["post_process_step_count"] == 0
