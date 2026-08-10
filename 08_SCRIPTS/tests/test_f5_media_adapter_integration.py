from __future__ import annotations

import ast
from pathlib import Path
import sys

import pytest


SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from cips_core.adapters import (
    AdapterContext,
    AdapterContractError,
    AdapterRegistry,
    AdapterRequest,
    AdapterValidationError,
    ImageMediaAdapter,
    VideoMediaAdapter,
    VoiceMediaAdapter,
)
from cips_core.agents import AgentRegistry
from cips_core.integration import AdapterAgentBridge
import cips_core.adapters.media as media_adapter_module


def _request(capability: str, *, input_data=None, shared_data=None, task_outputs=None):
    return AdapterRequest(
        capability=capability,
        context=AdapterContext(
            project_id="project-1",
            workflow_id="workflow-1",
            run_id="run-1",
            task_id="task-1",
            correlation_id="corr-1",
            metadata={"source": "unit-test"},
        ),
        input_data=input_data or {},
        shared_data=shared_data or {},
        task_outputs=task_outputs or {},
    )


def test_f5_2_concrete_adapters_publish_one_media_capability_each() -> None:
    fake = lambda package: {"asset": "synthetic"}
    voice = VoiceMediaAdapter(provider_executor=fake)
    image = ImageMediaAdapter(provider_executor=fake)
    video = VideoMediaAdapter(provider_executor=fake)

    assert (voice.adapter_name, voice.capability) == (
        "VoiceMediaAdapter",
        "voice_synthesis",
    )
    assert (image.adapter_name, image.capability) == (
        "ImageMediaAdapter",
        "image_generation",
    )
    assert (video.adapter_name, video.capability) == (
        "VideoMediaAdapter",
        "video_rendering",
    )
    assert type(voice.director).__name__ == "MediaDirector"
    assert type(image.director).__name__ == "MediaDirector"
    assert type(video.director).__name__ == "MediaDirector"


def test_f5_2_adapter_translates_core_request_and_calls_boundary_once() -> None:
    calls = []

    def fake_executor(package):
        calls.append(package)
        return {"asset": "synthetic-image"}

    adapter = ImageMediaAdapter(provider_executor=fake_executor)
    result = adapter.execute(
        _request(
            "image_generation",
            shared_data={"aspect_ratio": "16:9", "style": "shared"},
            input_data={
                "prompt": "Create a synthetic image",
                "style": "local",
                "preferred_provider": " Fake-One ",
                "metadata": {"campaign": "demo"},
            },
            task_outputs={"strategy": {"id": "s-1"}},
        )
    )

    assert len(calls) == 1
    package = calls[0]
    assert package.capability == "image_generation"
    assert package.preferred_provider == "fake-one"
    assert package.provider_payload == {
        "prompt": "Create a synthetic image",
        "aspect_ratio": "16:9",
        "style": "local",
    }
    assert result.succeeded
    assert result.output["output"] == {"asset": "synthetic-image"}
    assert result.output["metadata"]["project_id"] == "project-1"
    assert result.output["metadata"]["campaign"] == "demo"
    assert result.output["metadata"]["task_outputs"] == {"strategy": {"id": "s-1"}}


def test_f5_2_post_process_chain_remains_declarative() -> None:
    observed = []

    def fake_executor(package):
        observed.extend(step.name for step in package.post_process_chain)
        return b"synthetic-video"

    result = VideoMediaAdapter(provider_executor=fake_executor).execute(
        _request("video_rendering", input_data={"prompt": "Synthetic video"})
    )

    assert observed == ["compress", "subtitle", "package"]
    assert [step["name"] for step in result.output["post_process_chain"]] == [
        "compress",
        "subtitle",
        "package",
    ]


def test_f5_2_bridge_registers_media_adapters_without_registry_changes() -> None:
    fake = lambda package: {"asset": "synthetic"}
    adapters = [
        VoiceMediaAdapter(provider_executor=fake),
        ImageMediaAdapter(provider_executor=fake),
        VideoMediaAdapter(provider_executor=fake),
    ]
    adapter_registry = AdapterRegistry()
    agent_registry = AgentRegistry()
    bridge = AdapterAgentBridge(agent_registry, adapter_registry)

    descriptors = bridge.register_many(adapters)

    assert [descriptor.name for descriptor in descriptors] == [
        "VoiceMediaAdapter",
        "ImageMediaAdapter",
        "VideoMediaAdapter",
    ]
    for adapter in adapters:
        assert bridge.resolve_adapter(capability=adapter.capability) is adapter
        descriptor = agent_registry.resolve(capability=adapter.capability)
        assert descriptor.handler is adapter
        assert descriptor.capabilities == {adapter.capability}
        assert descriptor.metadata["component"] == "media_director.MediaDirector"
        assert descriptor.metadata["post_process_mode"] == "declarative"


def test_f5_2_requires_prompt() -> None:
    adapter = VoiceMediaAdapter(provider_executor=lambda package: b"audio")

    with pytest.raises(AdapterValidationError, match="input.prompt"):
        adapter.execute(_request("voice_synthesis", input_data={}))


def test_f5_2_rejects_non_callable_provider_boundary() -> None:
    with pytest.raises(AdapterContractError, match="provider_executor"):
        ImageMediaAdapter(provider_executor=None)  # type: ignore[arg-type]


def test_f5_2_does_not_import_pipeline_artifacts_or_provider_sdks() -> None:
    source_path = Path(media_adapter_module.__file__).resolve()
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)

    forbidden = (
        "stage_executor",
        "pipeline_engine",
        "artifact_store",
        "workspace_resolver",
        "openai",
        "anthropic",
        "elevenlabs",
        "google.generativeai",
        "google.genai",
    )
    assert not any(
        name == prefix or name.startswith(prefix + ".")
        for name in imported
        for prefix in forbidden
    )
