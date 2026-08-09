from __future__ import annotations

import hashlib
import json
from pathlib import Path, PureWindowsPath
import sys
from tempfile import TemporaryDirectory

import pytest

SCRIPT_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from artifact_store import (  # noqa: E402
    ArtifactCollisionError,
    ArtifactIdentityConflictError,
    ArtifactNotFoundError,
    ArtifactStore,
    CollisionPolicy,
    SIDECAR_SUFFIX,
)
from master_producer_models import ProductionArtifact  # noqa: E402
from workspace_resolver import WorkspaceResolver, WorkspaceSecurityError  # noqa: E402


class BinaryStore(ArtifactStore):
    @property
    def media_type(self) -> str:
        return "binary-test"


@pytest.fixture()
def store_env():
    with TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        projects = root / "04_PROYECTOS"
        outputs = root / "05_OUTPUTS"
        projects.mkdir()
        outputs.mkdir()
        resolver = WorkspaceResolver(projects_root=projects, outputs_root=outputs)
        workspace = resolver.resolve_project_workspace("PROJECT_A", create=True)
        yield BinaryStore(resolver), workspace, root


def persist(store: BinaryStore, workspace: Path, **kwargs):
    base = {
        "workspace_root": workspace,
        "relative_path": "artifacts/example.bin",
        "content": b"CIPS-F3.2",
        "artifact_type": "test_binary",
        "mime_type": "application/octet-stream",
        "created_at": "2026-08-09T14:00:00+00:00",
    }
    base.update(kwargs)
    return store.persist_bytes(**base)


def test_artifact_store_is_abstract():
    resolver = object()
    with pytest.raises(TypeError):
        ArtifactStore(resolver)  # type: ignore[abstract]


def test_persist_creates_artifact_and_sidecar(store_env):
    store, workspace, _ = store_env
    result = persist(store, workspace)
    artifact_path = Path(result.artifact.path)
    assert artifact_path.read_bytes() == b"CIPS-F3.2"
    assert result.sidecar_path == Path(f"{artifact_path}{SIDECAR_SUFFIX}")
    assert result.sidecar_path.is_file()
    assert result.deduplicated is False
    assert result.event_created is True


def test_reuses_existing_production_artifact_contract(store_env):
    store, workspace, _ = store_env
    result = persist(store, workspace)
    assert isinstance(result.artifact, ProductionArtifact)
    assert result.artifact.content_hash == hashlib.sha256(b"CIPS-F3.2").hexdigest()
    assert result.artifact.size_bytes == len(b"CIPS-F3.2")


def test_sidecar_separates_content_identity_from_event(store_env):
    store, workspace, _ = store_env
    first = persist(store, workspace, artifact_id="artifact_event_1")
    data = json.loads(first.sidecar_path.read_text(encoding="utf-8"))
    assert data["content_hash"] == first.artifact.content_hash
    assert "created_at" not in {key for key in data if key != "events"}
    assert data["events"][0]["artifact_id"] == "artifact_event_1"
    assert data["events"][0]["created_at"] == "2026-08-09T14:00:00+00:00"


def test_same_bytes_same_hash(store_env):
    store, workspace, _ = store_env
    a = persist(store, workspace, relative_path="a.bin")
    b = persist(store, workspace, relative_path="b.bin")
    assert a.artifact.content_hash == b.artifact.content_hash


def test_global_dedup_reuses_one_physical_copy(store_env):
    store, workspace, _ = store_env
    first = persist(store, workspace, relative_path="a.bin", artifact_id="artifact_a")
    second = persist(
        store,
        workspace,
        relative_path="nested/b.bin",
        artifact_id="artifact_b",
        created_at="2026-08-09T14:01:00+00:00",
    )
    assert Path(first.artifact.path) == Path(second.artifact.path)
    assert second.deduplicated is True
    physical = [p for p in workspace.rglob("*.bin") if not p.name.startswith(".")]
    assert len(physical) == 1


def test_duplicate_content_preserves_distinct_generation_events(store_env):
    store, workspace, _ = store_env
    first = persist(store, workspace, artifact_id="artifact_a")
    second = persist(
        store,
        workspace,
        relative_path="other.bin",
        artifact_id="artifact_b",
        created_at="2026-08-09T15:00:00+00:00",
    )
    data = json.loads(first.sidecar_path.read_text(encoding="utf-8"))
    assert len(data["events"]) == 2
    assert {event["artifact_id"] for event in data["events"]} == {
        "artifact_a",
        "artifact_b",
    }
    assert first.artifact.content_hash == second.artifact.content_hash
    assert first.created_at != second.created_at


def test_same_artifact_id_is_event_idempotent(store_env):
    store, workspace, _ = store_env
    first = persist(store, workspace, artifact_id="artifact_same")
    second = persist(
        store,
        workspace,
        relative_path="different-request.bin",
        artifact_id="artifact_same",
        created_at="2026-08-09T18:00:00+00:00",
    )
    data = json.loads(first.sidecar_path.read_text(encoding="utf-8"))
    assert len(data["events"]) == 1
    assert second.event_created is False
    assert second.created_at == first.created_at
    assert Path(second.artifact.path) == Path(first.artifact.path)


def test_same_artifact_id_with_different_content_is_rejected(store_env):
    store, workspace, _ = store_env
    persist(store, workspace, artifact_id="artifact_same")
    with pytest.raises(ArtifactIdentityConflictError):
        persist(
            store,
            workspace,
            relative_path="different.bin",
            content=b"different",
            artifact_id="artifact_same",
        )


def test_existing_same_path_same_content_is_reused(store_env):
    store, workspace, _ = store_env
    first = persist(store, workspace)
    second = persist(store, workspace)
    assert second.deduplicated is True
    assert Path(second.artifact.path) == Path(first.artifact.path)


def test_reject_policy_rejects_even_identical_destination(store_env):
    store, workspace, _ = store_env
    persist(store, workspace)
    with pytest.raises(ArtifactCollisionError):
        persist(store, workspace, collision_policy=CollisionPolicy.REJECT)


def test_different_content_collision_is_rejected_by_default(store_env):
    store, workspace, _ = store_env
    persist(store, workspace)
    with pytest.raises(ArtifactCollisionError):
        persist(store, workspace, content=b"different")


def test_replace_requires_explicit_policy(store_env):
    store, workspace, _ = store_env
    first = persist(store, workspace)
    second = persist(
        store,
        workspace,
        content=b"replacement",
        collision_policy=CollisionPolicy.REPLACE,
        artifact_id="artifact_replacement",
    )
    assert Path(second.artifact.path).read_bytes() == b"replacement"
    assert second.artifact.content_hash != first.artifact.content_hash


def test_replace_resets_sidecar_to_new_content_identity(store_env):
    store, workspace, _ = store_env
    first = persist(store, workspace, artifact_id="artifact_old")
    second = persist(
        store,
        workspace,
        content=b"replacement",
        collision_policy="replace",
        artifact_id="artifact_new",
    )
    data = json.loads(second.sidecar_path.read_text(encoding="utf-8"))
    assert data["content_hash"] == second.artifact.content_hash
    assert data["content_hash"] != first.artifact.content_hash
    assert [event["artifact_id"] for event in data["events"]] == ["artifact_new"]


def test_path_traversal_is_blocked(store_env):
    store, workspace, _ = store_env
    with pytest.raises(WorkspaceSecurityError):
        persist(store, workspace, relative_path="../../outside.bin")


def test_windows_path_traversal_is_blocked_on_non_windows_too(store_env):
    store, workspace, _ = store_env
    with pytest.raises(WorkspaceSecurityError):
        persist(store, workspace, relative_path=r"..\..\outside.bin")


def test_absolute_path_is_blocked(store_env):
    store, workspace, root = store_env
    with pytest.raises(WorkspaceSecurityError):
        persist(store, workspace, relative_path=root / "outside.bin")


def test_workspace_outside_authorized_roots_is_blocked(store_env):
    store, _, root = store_env
    outside = root / "outside"
    outside.mkdir()
    with pytest.raises(WorkspaceSecurityError):
        persist(store, outside)


def test_read_exists_and_verify_hash(store_env):
    store, workspace, _ = store_env
    result = persist(store, workspace)
    assert store.exists(workspace, "artifacts/example.bin") is True
    assert store.read_bytes(workspace, "artifacts/example.bin") == b"CIPS-F3.2"
    assert store.verify_hash(
        workspace,
        "artifacts/example.bin",
        result.artifact.content_hash,
    ) is True


def test_read_missing_artifact_raises(store_env):
    store, workspace, _ = store_env
    with pytest.raises(ArtifactNotFoundError):
        store.read_bytes(workspace, "missing.bin")


def test_load_sidecar(store_env):
    store, workspace, _ = store_env
    result = persist(store, workspace)
    sidecar = store.load_sidecar(workspace, "artifacts/example.bin")
    assert sidecar["content_hash"] == result.artifact.content_hash
    assert sidecar["media_type"] == "binary-test"


def test_metadata_is_json_safe(store_env):
    store, workspace, _ = store_env
    result = persist(store, workspace, metadata={"path": Path("a/b"), "values": {1, 2}})
    data = json.loads(result.sidecar_path.read_text(encoding="utf-8"))
    event_metadata = data["events"][0]["metadata"]
    assert event_metadata["path"] == "a/b"
    assert sorted(event_metadata["values"]) == [1, 2]


def test_windows_path_metadata_is_normalized_to_posix(store_env):
    store, workspace, _ = store_env
    result = persist(
        store,
        workspace,
        metadata={"path": PureWindowsPath(r"a\b\c.txt")},
    )
    data = json.loads(result.sidecar_path.read_text(encoding="utf-8"))
    assert data["events"][0]["metadata"]["path"] == "a/b/c.txt"


def test_empty_bytes_are_valid_content(store_env):
    store, workspace, _ = store_env
    result = persist(store, workspace, content=b"")
    assert result.artifact.content_hash == hashlib.sha256(b"").hexdigest()
    assert result.artifact.size_bytes == 0


def test_non_bytes_content_rejected(store_env):
    store, workspace, _ = store_env
    with pytest.raises(TypeError):
        persist(store, workspace, content="not-bytes")  # type: ignore[arg-type]


def test_sidecar_suffix_exact(store_env):
    store, workspace, _ = store_env
    result = persist(store, workspace, relative_path="video.mp4")
    assert result.sidecar_path.name == "video.mp4.meta.json"


def test_sidecar_does_not_replace_manifest(store_env):
    store, workspace, _ = store_env
    persist(store, workspace)
    assert not (workspace / "MANIFEST.json").exists()


def test_no_temporary_files_remain_after_success(store_env):
    store, workspace, _ = store_env
    persist(store, workspace)
    leftovers = [path for path in workspace.rglob("*.tmp")]
    assert leftovers == []


def test_artifact_id_cannot_change_logical_type(store_env):
    store, workspace, _ = store_env
    persist(store, workspace, artifact_id="artifact_same")
    with pytest.raises(ArtifactIdentityConflictError):
        persist(
            store,
            workspace,
            relative_path="other.bin",
            artifact_id="artifact_same",
            artifact_type="another_type",
        )


def test_replace_rolls_back_file_if_sidecar_registration_fails(store_env, monkeypatch):
    store, workspace, _ = store_env
    first = persist(store, workspace, artifact_id="artifact_old")
    original_sidecar = first.sidecar_path.read_bytes()

    def fail_sidecar(**kwargs):
        raise OSError("forced sidecar failure")

    monkeypatch.setattr(store, "_register_sidecar_event", fail_sidecar)
    with pytest.raises(OSError, match="forced sidecar failure"):
        persist(
            store,
            workspace,
            content=b"replacement",
            artifact_id="artifact_new",
            collision_policy=CollisionPolicy.REPLACE,
        )

    assert Path(first.artifact.path).read_bytes() == b"CIPS-F3.2"
    assert first.sidecar_path.read_bytes() == original_sidecar
    assert list(workspace.rglob("*.bak")) == []


def test_same_artifact_id_returns_original_event_metadata(store_env):
    store, workspace, _ = store_env
    first = persist(
        store,
        workspace,
        artifact_id="artifact_same",
        metadata={"source": "original"},
    )
    second = persist(
        store,
        workspace,
        relative_path="new-request.bin",
        artifact_id="artifact_same",
        metadata={"source": "changed"},
        created_at="2026-08-09T20:00:00+00:00",
    )
    assert second.event_created is False
    assert second.created_at == first.created_at
    assert second.artifact.metadata["source"] == "original"
    assert second.artifact.metadata["requested_relative_path"] == "artifacts/example.bin"


def test_new_artifact_is_removed_if_sidecar_registration_fails(store_env, monkeypatch):
    store, workspace, _ = store_env

    def fail_sidecar(**kwargs):
        raise OSError("forced sidecar failure")

    monkeypatch.setattr(store, "_register_sidecar_event", fail_sidecar)
    with pytest.raises(OSError, match="forced sidecar failure"):
        persist(store, workspace)

    assert not (workspace / "artifacts" / "example.bin").exists()
    assert list(workspace.rglob("*.tmp")) == []
