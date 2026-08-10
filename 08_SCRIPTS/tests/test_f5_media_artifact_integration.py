from __future__ import annotations

import ast
import json
from pathlib import Path
import sys

import pytest


SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from media_director import (
    MediaArtifactPersister,
    MediaResult,
    MediaType,
    PostProcessStep,
)
import media_director.artifact_integration as integration_module
from workspace_resolver import WorkspaceResolver, WorkspaceSecurityError


def make_resolver(tmp_path: Path) -> WorkspaceResolver:
    return WorkspaceResolver(
        projects_root=tmp_path / "04_PROYECTOS",
        outputs_root=tmp_path / "05_OUTPUTS",
    )


def make_result(
    media_type: MediaType,
    output: bytes | bytearray | memoryview,
) -> MediaResult:
    capability = {
        MediaType.VOICE: "voice_synthesis",
        MediaType.IMAGE: "image_generation",
        MediaType.VIDEO: "video_rendering",
    }[media_type]
    output_format = {
        MediaType.VOICE: "audio",
        MediaType.IMAGE: "image",
        MediaType.VIDEO: "video",
    }[media_type]
    return MediaResult(
        request_id=f"req-{media_type.value}",
        strategy_name=media_type.value,
        media_type=media_type,
        capability=capability,
        output_format=output_format,
        output=output,
        post_process_chain=(PostProcessStep("package"),),
        metadata={"provider": "fake-media", "cost": 0.0},
    )


@pytest.mark.parametrize(
    ("media_type", "relative_path", "mime_type", "artifact_type", "store_media_type"),
    [
        (MediaType.VOICE, "audio/voice.wav", "audio/wav", "audio", "audio"),
        (MediaType.IMAGE, "images/frame.png", "image/png", "image", "image"),
        (MediaType.VIDEO, "video/render.mp4", "video/mp4", "video", "video"),
    ],
)
def test_f5_4_persists_media_result_through_specialized_f3_store(
    tmp_path: Path,
    media_type: MediaType,
    relative_path: str,
    mime_type: str,
    artifact_type: str,
    store_media_type: str,
) -> None:
    resolver = make_resolver(tmp_path)
    workspace = resolver.resolve_execution_workspace("tiktok", "exec_001", create=True)
    payload = f"synthetic-{media_type.value}".encode()
    result = make_result(media_type, payload)

    written = MediaArtifactPersister(resolver).persist(
        result,
        workspace_root=workspace,
        relative_path=relative_path,
        mime_type=mime_type,
        metadata={"duration": 1.25},
    )

    artifact_path = Path(written.artifact.path)
    assert artifact_path.read_bytes() == payload
    assert written.artifact.artifact_type == artifact_type
    assert written.artifact.mime_type == mime_type
    assert written.artifact.metadata["media_type"] == store_media_type
    assert written.artifact.metadata["media_request_id"] == result.request_id
    assert written.artifact.metadata["media_capability"] == result.capability
    assert written.artifact.metadata["provider"] == "fake-media"
    assert written.artifact.metadata["duration"] == 1.25
    assert written.sidecar_path.is_file()

    sidecar = json.loads(written.sidecar_path.read_text(encoding="utf-8"))
    assert sidecar["media_type"] == store_media_type
    assert sidecar["content_hash"] == written.artifact.content_hash
    event_metadata = sidecar["events"][0]["metadata"]
    assert event_metadata["media_request_id"] == result.request_id
    assert event_metadata["post_process_chain"][0]["name"] == "package"


def test_f5_4_reuses_f3_idempotency_and_deduplication(tmp_path: Path) -> None:
    resolver = make_resolver(tmp_path)
    workspace = resolver.resolve_execution_workspace("youtube", "exec_002", create=True)
    persister = MediaArtifactPersister(resolver)
    result = make_result(MediaType.IMAGE, b"same-image")

    first = persister.persist(
        result,
        workspace_root=workspace,
        relative_path="images/same.png",
        mime_type="image/png",
        artifact_id="artifact-fixed",
    )
    second = persister.persist(
        result,
        workspace_root=workspace,
        relative_path="images/ignored.png",
        mime_type="image/png",
        artifact_id="artifact-fixed",
    )

    assert first.artifact.path == second.artifact.path
    assert first.artifact.content_hash == second.artifact.content_hash
    assert second.deduplicated is True
    assert second.event_created is False


def test_f5_4_rejects_non_binary_media_output_before_store_call(tmp_path: Path) -> None:
    resolver = make_resolver(tmp_path)
    workspace = resolver.resolve_execution_workspace("tiktok", "exec_003", create=True)
    result = MediaResult(
        request_id="req-invalid",
        strategy_name="image",
        media_type=MediaType.IMAGE,
        capability="image_generation",
        output_format="image",
        output={"asset": "not-normalized-bytes"},
    )

    with pytest.raises(TypeError, match="debe ser bytes"):
        MediaArtifactPersister(resolver).persist(
            result,
            workspace_root=workspace,
            relative_path="images/invalid.png",
        )

    assert list(workspace.rglob("*")) == []


def test_f5_4_delegates_path_confinement_to_workspace_resolver(tmp_path: Path) -> None:
    resolver = make_resolver(tmp_path)
    workspace = resolver.resolve_execution_workspace("tiktok", "exec_004", create=True)

    with pytest.raises(WorkspaceSecurityError):
        MediaArtifactPersister(resolver).persist(
            make_result(MediaType.VIDEO, b"video"),
            workspace_root=workspace,
            relative_path="../escape.mp4",
            mime_type="video/mp4",
        )


def test_f5_4_boundary_validation(tmp_path: Path) -> None:
    resolver = make_resolver(tmp_path)
    persister = MediaArtifactPersister(resolver)

    with pytest.raises(TypeError, match="WorkspaceResolver"):
        MediaArtifactPersister(object())

    workspace = resolver.resolve_execution_workspace("tiktok", "exec_005", create=True)
    with pytest.raises(TypeError, match="MediaResult"):
        persister.persist(
            object(),
            workspace_root=workspace,
            relative_path="images/x.png",
        )

    with pytest.raises(TypeError, match="metadata"):
        persister.persist(
            make_result(MediaType.IMAGE, b"image"),
            workspace_root=workspace,
            relative_path="images/x.png",
            metadata=[("bad", "mapping")],
        )


def test_f5_4_integration_layer_does_not_reimplement_pipeline_provider_or_hashing() -> None:
    source = Path(integration_module.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)

    forbidden_imports = {
        "stage_executor",
        "pipeline_engine",
        "capability_resolver",
        "retry_engine",
        "openai",
        "google.generativeai",
        "google.genai",
        "anthropic",
        "elevenlabs",
        "hashlib",
        "json",
    }
    assert imported_modules.isdisjoint(forbidden_imports)
    assert "sha256" not in source.lower()
    assert "sidecar_path_for" not in source
    assert "StageExecutor" not in source
    assert "PipelineEngine" not in source
