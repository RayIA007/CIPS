from __future__ import annotations

from pathlib import Path
import sys


SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from cips_core.facade import CIPSOrchestrator
from cips_core.media_runtime import MediaRuntime
from cips_core.tasks import TaskStatus
from video_pipeline import VideoPipelineLoader, VideoPipelineRunner
from workspace_resolver import WorkspaceResolver


PIPELINE_YAML = """
pipeline_id: f6-integration-smoke
name: F6 declarative video integration smoke
version: 1.0.0
metadata:
  phase: F6.6
scenes:
  - scene_id: preview
    prompt: Render a synthetic preview.
    duration: 2
    render_profile: preview
    transitions:
      - kind: fade
        duration: 0.25
    post_process_chain:
      - name: compress
        parameters:
          quality: draft
      - name: package
        parameters:
          container: mp4
    artifact_target:
      platform: f6-smoke
      relative_path: video/preview.mp4
      mime_type: video/mp4

  - scene_id: final
    prompt: Render the synthetic final using the preview artifact.
    duration: 4
    dependencies:
      - preview
    media_refs:
      - scene_id: preview
        artifact_index: 0
        role: preview_video
      - image:external-reference
    transitions:
      - kind: dissolve
        duration: 0.5
    audio_track: audio:synthetic-narration
    subtitle_track: subtitles:synthetic-main
    render_profile:
      name: final
      max_height: 1080
      parameters:
        quality: high
    post_process_chain:
      - name: compress
        parameters:
          quality: final
      - name: subtitle
        required: true
      - name: package
        parameters:
          container: mp4
    artifact_target:
      platform: f6-smoke
      relative_path: video/final.mp4
      mime_type: video/mp4
"""


class FakeCapabilityResolver:
    """F4-compatible resolver used only by the F6 integration smoke."""

    def __init__(self) -> None:
        self.provider = object()
        self.calls: list[tuple[str, str | None]] = []

    def resolve(self, capability: str, *, preferred_provider: str | None = None):
        self.calls.append((capability, preferred_provider))
        return self.provider


def test_f6_declarative_video_pipeline_end_to_end_without_real_providers(
    tmp_path: Path,
) -> None:
    """Exercise F6.1-F6.5 through Core/F5/F3 without real providers."""

    resolver = FakeCapabilityResolver()
    provider_packages = []

    def provider_invoker(provider, work_package):
        assert provider is resolver.provider
        provider_packages.append(work_package)
        if work_package.provider_payload["render_profile"]["name"] == "preview":
            return b"f6-smoke-preview-video"
        return b"f6-smoke-final-video"

    workspace_resolver = WorkspaceResolver(
        projects_root=tmp_path / "04_PROYECTOS",
        outputs_root=tmp_path / "05_OUTPUTS",
    )
    runtime = MediaRuntime(
        resolver,
        provider_invoker=provider_invoker,
        workspace_resolver=workspace_resolver,
    )
    orchestrator = CIPSOrchestrator()
    runtime.register(orchestrator.adapter_bridge)

    spec = VideoPipelineLoader.loads(PIPELINE_YAML)
    result = VideoPipelineRunner(orchestrator).run(
        spec,
        project_id="f6-smoke-project",
        metadata={"source": "f6.6-integration-smoke"},
    )

    assert result.succeeded
    assert list(result.task_results) == ["preview", "final"]
    assert resolver.calls == [
        ("video_rendering", None),
        ("video_rendering", None),
    ]
    assert len(provider_packages) == 2

    preview_package, final_package = provider_packages
    assert preview_package.provider_payload["render_profile"] == {
        "name": "preview",
        "max_height": 360,
        "parameters": {},
    }
    assert [step.name for step in preview_package.post_process_chain] == [
        "compress",
        "package",
    ]
    assert "post_process_chain" not in preview_package.provider_payload

    assert final_package.provider_payload["render_profile"] == {
        "name": "final",
        "max_height": 1080,
        "parameters": {"quality": "high"},
    }
    assert final_package.provider_payload["audio_track"] == "audio:synthetic-narration"
    assert final_package.provider_payload["subtitle_track"] == "subtitles:synthetic-main"
    assert final_package.provider_payload["transitions"] == [
        {"kind": "dissolve", "duration": 0.5, "parameters": {}}
    ]
    assert [step.name for step in final_package.post_process_chain] == [
        "compress",
        "subtitle",
        "package",
    ]
    assert "post_process_chain" not in final_package.provider_payload

    resolved_refs = final_package.provider_payload["media_refs"]
    assert len(resolved_refs) == 2
    assert resolved_refs[0]["source_task_id"] == "preview"
    assert resolved_refs[0]["artifact_index"] == 0
    assert resolved_refs[0]["role"] == "preview_video"
    assert resolved_refs[1] == "image:external-reference"

    workspace_root = tmp_path / "05_OUTPUTS" / "f6-smoke" / result.run_id
    expected_content = {
        "preview": b"f6-smoke-preview-video",
        "final": b"f6-smoke-final-video",
    }
    for task_id, content in expected_content.items():
        task_result = result.task_results[task_id]
        assert task_result.status is TaskStatus.SUCCEEDED
        assert task_result.attempts == 1
        assert task_result.adapter_result["adapter_name"] == "VideoMediaAdapter"
        assert task_result.adapter_result["capability"] == "video_rendering"
        assert len(task_result.artifacts) == 1

        artifact = task_result.artifacts[0]
        artifact_path = Path(artifact["path"])
        assert artifact_path.read_bytes() == content
        assert artifact_path.is_relative_to(workspace_root)
        assert Path(artifact["sidecar_path"]).is_file()
        assert artifact["deduplicated"] is False
        assert artifact["event_created"] is True

    preview_artifact = result.task_results["preview"].artifacts[0]
    assert Path(resolved_refs[0]["path"]) == Path(preview_artifact["path"])
    assert resolved_refs[0]["content_hash"] == preview_artifact["content_hash"]
    assert set(result.context.task_outputs) == {"preview", "final"}
    assert set(result.context.task_artifacts) == {"preview", "final"}
    assert result.context.metadata["source"] == "f6.6-integration-smoke"

    adapter_events = [
        message
        for message in orchestrator.message_bus.history()
        if message.topic == "adapter.succeeded"
    ]
    assert len(adapter_events) == 2
    assert all(len(message.payload["artifacts"]) == 1 for message in adapter_events)

    checkpoint = orchestrator.checkpoint_store.load_latest(
        spec.pipeline_id,
        result.run_id,
    )
    assert checkpoint is not None
    assert checkpoint.status.value == "succeeded"
    assert set(checkpoint.task_results) == {"preview", "final"}
