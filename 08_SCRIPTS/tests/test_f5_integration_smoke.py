from __future__ import annotations

from pathlib import Path
import sys


SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from cips_core.facade import CIPSOrchestrator
from cips_core.media_runtime import MediaRuntime
from cips_core.tasks import TaskDefinition, TaskStatus
from workspace_resolver import WorkspaceResolver


class FakeCapabilityResolver:
    """Resolver F4-compatible used only by the F5 integration smoke."""

    def __init__(self) -> None:
        self.provider = object()
        self.calls: list[tuple[str, str | None]] = []

    def resolve(self, capability: str, *, preferred_provider: str | None = None):
        self.calls.append((capability, preferred_provider))
        return self.provider


def test_f5_end_to_end_media_runtime_smoke(tmp_path: Path) -> None:
    """Exercise F5.1-F5.5 through the real Core contracts without real providers."""

    resolver = FakeCapabilityResolver()
    provider_calls: list[str] = []
    payload_by_capability = {
        "voice_synthesis": b"f5-smoke-voice",
        "image_generation": b"f5-smoke-image",
        "video_rendering": b"f5-smoke-video",
    }

    def provider_invoker(provider, work_package):
        assert provider is resolver.provider
        provider_calls.append(work_package.capability)
        return payload_by_capability[work_package.capability]

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

    tasks = [
        TaskDefinition(
            name="voice",
            capability="voice_synthesis",
            task_id="01_voice",
            input_data={
                "prompt": "Synthetic F5 voice",
                "preferred_provider": "fake-media",
                "artifact_target": {
                    "platform": "f5-smoke",
                    "relative_path": "voice/voice.wav",
                    "mime_type": "audio/wav",
                },
            },
        ),
        TaskDefinition(
            name="image",
            capability="image_generation",
            task_id="02_image",
            dependencies={"01_voice"},
            input_data={
                "prompt": "Synthetic F5 image",
                "preferred_provider": "fake-media",
                "artifact_target": {
                    "platform": "f5-smoke",
                    "relative_path": "image/frame.png",
                    "mime_type": "image/png",
                },
            },
        ),
        TaskDefinition(
            name="video",
            capability="video_rendering",
            task_id="03_video",
            dependencies={"02_image"},
            input_data={
                "prompt": "Synthetic F5 video",
                "preferred_provider": "fake-media",
                "artifact_target": {
                    "platform": "f5-smoke",
                    "relative_path": "video/render.mp4",
                    "mime_type": "video/mp4",
                },
            },
        ),
    ]
    workflow = orchestrator.create_workflow(name="f5-integration-smoke", tasks=tasks)

    result = orchestrator.run(workflow, project_id="f5-smoke-project")

    assert result.succeeded
    assert list(result.task_results) == ["01_voice", "02_image", "03_video"]
    assert resolver.calls == [
        ("voice_synthesis", "fake-media"),
        ("image_generation", "fake-media"),
        ("video_rendering", "fake-media"),
    ]
    assert provider_calls == [
        "voice_synthesis",
        "image_generation",
        "video_rendering",
    ]

    expected = {
        "01_voice": ("voice_synthesis", "VoiceMediaAdapter", b"f5-smoke-voice"),
        "02_image": ("image_generation", "ImageMediaAdapter", b"f5-smoke-image"),
        "03_video": ("video_rendering", "VideoMediaAdapter", b"f5-smoke-video"),
    }
    workspace_root = tmp_path / "05_OUTPUTS" / "f5-smoke" / result.run_id

    for task_id, (capability, adapter_name, content) in expected.items():
        task_result = result.task_results[task_id]
        assert task_result.status is TaskStatus.SUCCEEDED
        assert task_result.attempts == 1
        assert task_result.adapter_result["adapter_name"] == adapter_name
        assert task_result.adapter_result["capability"] == capability
        assert len(task_result.artifacts) == 1

        artifact = task_result.artifacts[0]
        artifact_path = Path(artifact["path"])
        assert artifact_path.read_bytes() == content
        assert artifact_path.is_relative_to(workspace_root)
        assert Path(artifact["sidecar_path"]).is_file()
        assert artifact["deduplicated"] is False
        assert artifact["event_created"] is True

    adapter_events = [
        message
        for message in orchestrator.message_bus.history()
        if message.topic == "adapter.succeeded"
    ]
    assert len(adapter_events) == 3
    assert all(len(message.payload["artifacts"]) == 1 for message in adapter_events)

    checkpoint = orchestrator.checkpoint_store.load_latest(
        workflow.workflow_id,
        result.run_id,
    )
    assert checkpoint is not None
    assert checkpoint.status.value == "succeeded"
    assert set(checkpoint.task_results) == set(expected)
