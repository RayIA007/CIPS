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
    AdapterExecutionError,
    AdapterRegistry,
    AdapterRequest,
    AdapterValidationError,
)
from cips_core.agents import AgentRegistry
from cips_core.engine import WorkflowEngine
from cips_core.integration import AdapterAgentBridge
from cips_core.media_runtime import MediaArtifactTarget, MediaRuntime
from cips_core.tasks import TaskDefinition, WorkflowDefinition
import cips_core.adapters.media as media_adapter_module
import cips_core.media_runtime as runtime_module
from workspace_resolver import WorkspaceResolver


class RecordingResolver:
    def __init__(self) -> None:
        self.provider = object()
        self.calls: list[tuple[str, str | None]] = []

    def resolve(self, capability: str, *, preferred_provider: str | None = None):
        self.calls.append((capability, preferred_provider))
        return self.provider


def make_workspace_resolver(tmp_path: Path) -> WorkspaceResolver:
    return WorkspaceResolver(
        projects_root=tmp_path / "04_PROYECTOS",
        outputs_root=tmp_path / "05_OUTPUTS",
    )


def make_request(capability: str, input_data: dict) -> AdapterRequest:
    return AdapterRequest(
        capability=capability,
        context=AdapterContext(
            project_id="project-1",
            workflow_id="workflow-1",
            run_id="run-1",
            task_id="task-1",
            correlation_id="corr-1",
            metadata={"source": "f5.5-test"},
        ),
        input_data=input_data,
    )


def make_runtime(tmp_path: Path, invoker):
    resolver = RecordingResolver()
    runtime = MediaRuntime(
        resolver,
        provider_invoker=invoker,
        workspace_resolver=make_workspace_resolver(tmp_path),
    )
    return runtime, resolver


def test_f5_5_runtime_creates_three_core_media_adapters(tmp_path: Path) -> None:
    runtime, _ = make_runtime(tmp_path, lambda provider, package: b"synthetic")

    adapters = runtime.create_adapters()

    assert [adapter.capability for adapter in adapters] == [
        "voice_synthesis",
        "image_generation",
        "video_rendering",
    ]
    assert all(
        adapter.descriptor_metadata()["artifact_persistence"] == "runtime_opt_in"
        for adapter in adapters
    )


def test_f5_5_generates_and_persists_artifact_through_runtime(tmp_path: Path) -> None:
    observed_packages = []

    def invoker(provider, package):
        observed_packages.append(package)
        return b"synthetic-image-bytes"

    runtime, resolver = make_runtime(tmp_path, invoker)
    image_adapter = runtime.create_adapters()[1]
    result = image_adapter.execute(
        make_request(
            "image_generation",
            {
                "prompt": "Create a synthetic image",
                "preferred_provider": " Fake-Media ",
                "artifact_target": {
                    "platform": "tiktok",
                    "relative_path": "images/frame.png",
                    "mime_type": "image/png",
                    "metadata": {"campaign": "f5.5"},
                },
            },
        )
    )

    assert result.succeeded
    assert resolver.calls == [("image_generation", "fake-media")]
    assert len(observed_packages) == 1
    assert "artifact_target" not in observed_packages[0].provider_payload
    assert len(result.artifacts) == 1
    artifact = dict(result.artifacts[0])
    artifact_path = Path(artifact["path"])
    assert artifact_path.read_bytes() == b"synthetic-image-bytes"
    assert artifact["mime_type"] == "image/png"
    assert artifact["artifact_type"] == "image"
    assert Path(artifact["sidecar_path"]).is_file()
    assert artifact_path.is_relative_to(tmp_path / "05_OUTPUTS" / "tiktok" / "run-1")


def test_f5_5_artifact_persistence_is_opt_in(tmp_path: Path) -> None:
    runtime, resolver = make_runtime(
        tmp_path,
        lambda provider, package: b"synthetic-audio",
    )
    voice_adapter = runtime.create_adapters()[0]

    result = voice_adapter.execute(
        make_request("voice_synthesis", {"prompt": "Synthetic voice"})
    )

    assert result.succeeded
    assert resolver.calls == [("voice_synthesis", None)]
    assert result.artifacts == ()
    assert not (tmp_path / "05_OUTPUTS").exists()


def test_f5_5_explicit_execution_id_controls_workspace_scope(tmp_path: Path) -> None:
    runtime, _ = make_runtime(tmp_path, lambda provider, package: b"video")
    video_adapter = runtime.create_adapters()[2]

    result = video_adapter.execute(
        make_request(
            "video_rendering",
            {
                "prompt": "Synthetic video",
                "artifact_target": {
                    "platform": "youtube",
                    "execution_id": "publish-001",
                    "relative_path": "video/render.mp4",
                },
            },
        )
    )

    artifact_path = Path(result.artifacts[0]["path"])
    assert artifact_path.is_relative_to(
        tmp_path / "05_OUTPUTS" / "youtube" / "publish-001"
    )
    assert artifact_path.read_bytes() == b"video"


def test_f5_5_core_workflow_receives_persisted_artifact(tmp_path: Path) -> None:
    runtime, resolver = make_runtime(
        tmp_path,
        lambda provider, package: b"workflow-image",
    )
    agent_registry = AgentRegistry()
    adapter_registry = AdapterRegistry()
    bridge = AdapterAgentBridge(agent_registry, adapter_registry)
    runtime.register(bridge)
    workflow = WorkflowDefinition(
        name="f5.5-runtime",
        tasks=[
            TaskDefinition(
                name="image",
                capability="image_generation",
                input_data={
                    "prompt": "Workflow image",
                    "artifact_target": {
                        "platform": "instagram",
                        "relative_path": "images/workflow.png",
                    },
                },
            )
        ],
    )

    workflow_result = WorkflowEngine(agent_registry).run(
        workflow,
        project_id="project-runtime",
    )

    assert workflow_result.succeeded
    task_result = next(iter(workflow_result.task_results.values()))
    assert task_result.attempts == 1
    assert task_result.adapter_result["adapter_name"] == "ImageMediaAdapter"
    assert len(task_result.artifacts) == 1
    artifact = task_result.artifacts[0]
    artifact_path = Path(artifact["path"])
    assert artifact_path.read_bytes() == b"workflow-image"
    assert artifact_path.is_relative_to(
        tmp_path / "05_OUTPUTS" / "instagram" / workflow_result.run_id
    )
    assert resolver.calls == [("image_generation", None)]


def test_f5_5_invalid_artifact_target_is_rejected_before_provider_call(
    tmp_path: Path,
) -> None:
    provider_calls = 0

    def invoker(provider, package):
        nonlocal provider_calls
        provider_calls += 1
        return b"should-not-run"

    runtime, resolver = make_runtime(tmp_path, invoker)
    image_adapter = runtime.create_adapters()[1]

    with pytest.raises(AdapterValidationError, match="relative_path"):
        image_adapter.execute(
            make_request(
                "image_generation",
                {
                    "prompt": "Invalid target",
                    "artifact_target": {"platform": "tiktok"},
                },
            )
        )

    assert provider_calls == 0
    assert resolver.calls == []


def test_f5_5_provider_failure_has_no_internal_retry_or_artifact(
    tmp_path: Path,
) -> None:
    provider_calls = 0

    def invoker(provider, package):
        nonlocal provider_calls
        provider_calls += 1
        raise RuntimeError("synthetic provider failure")

    runtime, resolver = make_runtime(tmp_path, invoker)
    adapter = runtime.create_adapters()[2]

    with pytest.raises(AdapterExecutionError, match="synthetic provider failure"):
        adapter.execute(
            make_request(
                "video_rendering",
                {
                    "prompt": "Fail once",
                    "artifact_target": {
                        "platform": "youtube",
                        "relative_path": "video/fail.mp4",
                    },
                },
            )
        )

    assert provider_calls == 1
    assert resolver.calls == [("video_rendering", None)]
    assert not (tmp_path / "05_OUTPUTS").exists()


def test_f5_5_target_model_validates_runtime_configuration() -> None:
    target = MediaArtifactTarget(
        platform=" tiktok ",
        relative_path=" images/a.png ",
        metadata={"source": "test"},
    )
    assert target.platform == "tiktok"
    assert target.relative_path == "images/a.png"
    assert dict(target.metadata) == {"source": "test"}

    with pytest.raises(ValueError, match="platform"):
        MediaArtifactTarget(platform="", relative_path="images/a.png")
    with pytest.raises(TypeError, match="metadata"):
        MediaArtifactTarget(
            platform="tiktok",
            relative_path="images/a.png",
            metadata=[],  # type: ignore[arg-type]
        )


def test_f5_5_runtime_does_not_reimplement_pipeline_retry_hash_or_provider_sdks() -> None:
    runtime_source = Path(runtime_module.__file__).read_text(encoding="utf-8")
    media_source = Path(media_adapter_module.__file__).read_text(encoding="utf-8")

    imported = set()
    for source in (runtime_source, media_source):
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)

    forbidden = {
        "stage_executor",
        "pipeline_engine",
        "retry_engine",
        "hashlib",
        "openai",
        "anthropic",
        "elevenlabs",
        "google.generativeai",
        "google.genai",
    }
    assert imported.isdisjoint(forbidden)
    assert "while " not in runtime_source
    assert "sha256" not in runtime_source.lower()
    assert "sidecar_path_for" not in runtime_source

    media_imports = set()
    media_tree = ast.parse(media_source)
    for node in ast.walk(media_tree):
        if isinstance(node, ast.Import):
            media_imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            media_imports.add(node.module)
    assert "artifact_store" not in media_imports
    assert "workspace_resolver" not in media_imports
