from __future__ import annotations

import json
from pathlib import Path, PureWindowsPath
import sys
from tempfile import TemporaryDirectory

import pytest

SCRIPT_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from artifact_store import ArtifactStore, CollisionPolicy  # noqa: E402
from audio_store import AudioStore  # noqa: E402
from image_store import ImageStore  # noqa: E402
from master_producer_models import ProductionArtifact  # noqa: E402
from metadata_store import MetadataStore  # noqa: E402
from text_store import TextStore  # noqa: E402
from video_store import VideoStore  # noqa: E402
from workspace_resolver import WorkspaceResolver, WorkspaceSecurityError  # noqa: E402


CREATED_AT = "2026-08-09T15:30:00+00:00"


@pytest.fixture()
def stores_env():
    with TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        projects = root / "04_PROYECTOS"
        outputs = root / "05_OUTPUTS"
        projects.mkdir()
        outputs.mkdir()
        resolver = WorkspaceResolver(projects_root=projects, outputs_root=outputs)
        workspace = resolver.resolve_project_workspace("PROJECT_MEDIA", create=True)
        yield {
            "resolver": resolver,
            "workspace": workspace,
            "text": TextStore(resolver),
            "image": ImageStore(resolver),
            "audio": AudioStore(resolver),
            "video": VideoStore(resolver),
            "metadata": MetadataStore(resolver),
        }


def test_all_specialized_stores_extend_artifact_store(stores_env):
    for name in ("text", "image", "audio", "video", "metadata"):
        assert isinstance(stores_env[name], ArtifactStore)


def test_media_type_contracts(stores_env):
    assert stores_env["text"].media_type == "text"
    assert stores_env["image"].media_type == "image"
    assert stores_env["audio"].media_type == "audio"
    assert stores_env["video"].media_type == "video"
    assert stores_env["metadata"].media_type == "metadata"


def test_text_store_persists_utf8_without_bom(stores_env):
    store = stores_env["text"]
    workspace = stores_env["workspace"]
    result = store.persist_text(
        workspace_root=workspace,
        relative_path="text/guion.md",
        content="CIPS ágil",
        created_at=CREATED_AT,
    )
    path = Path(result.artifact.path)
    assert path.read_bytes() == "CIPS ágil".encode("utf-8")
    assert not path.read_bytes().startswith(b"\xef\xbb\xbf")
    assert result.artifact.mime_type == "text/markdown"
    assert result.artifact.metadata["encoding"] == "utf-8"


def test_text_store_infers_mime_from_extension(stores_env):
    result = stores_env["text"].persist_text(
        workspace_root=stores_env["workspace"],
        relative_path="notes/readme.txt",
        content="hola",
        created_at=CREATED_AT,
    )
    assert result.artifact.mime_type == "text/plain"


def test_text_store_rejects_mime_extension_mismatch(stores_env):
    with pytest.raises(ValueError):
        stores_env["text"].persist_text(
            workspace_root=stores_env["workspace"],
            relative_path="notes/readme.md",
            content="hola",
            mime_type="text/plain",
            created_at=CREATED_AT,
        )


def test_text_store_direct_bytes_cannot_bypass_family_rules(stores_env):
    with pytest.raises(ValueError):
        stores_env["text"].persist_bytes(
            workspace_root=stores_env["workspace"],
            relative_path="notes/readme.md",
            content=b"hola",
            artifact_type="text",
            mime_type="image/png",
            created_at=CREATED_AT,
        )


def test_text_store_rejects_unsupported_extension(stores_env):
    with pytest.raises(ValueError):
        stores_env["text"].persist_text(
            workspace_root=stores_env["workspace"],
            relative_path="notes/readme.bin",
            content="hola",
            created_at=CREATED_AT,
        )


def test_text_store_preserves_core_deduplication(stores_env):
    store = stores_env["text"]
    workspace = stores_env["workspace"]
    first = store.persist_text(
        workspace_root=workspace,
        relative_path="text/a.md",
        content="mismo",
        artifact_id="text_a",
        created_at=CREATED_AT,
    )
    second = store.persist_text(
        workspace_root=workspace,
        relative_path="text/b.md",
        content="mismo",
        artifact_id="text_b",
        created_at="2026-08-09T15:31:00+00:00",
    )
    assert Path(first.artifact.path) == Path(second.artifact.path)
    assert second.deduplicated is True
    sidecar = json.loads(first.sidecar_path.read_text(encoding="utf-8"))
    assert {event["artifact_id"] for event in sidecar["events"]} == {"text_a", "text_b"}


def test_image_store_persists_bytes_and_sidecar_metadata(stores_env):
    payload = b"\x89PNG\r\n\x1a\nCIPS"
    result = stores_env["image"].persist_image(
        workspace_root=stores_env["workspace"],
        relative_path="images/frame.png",
        content=payload,
        metadata={"width": 1080, "height": 1920, "source": "test"},
        created_at=CREATED_AT,
    )
    assert Path(result.artifact.path).read_bytes() == payload
    assert isinstance(result.artifact, ProductionArtifact)
    assert result.artifact.mime_type == "image/png"
    data = json.loads(result.sidecar_path.read_text(encoding="utf-8"))
    assert data["media_type"] == "image"
    assert data["events"][0]["metadata"]["width"] == 1080


def test_image_store_rejects_wrong_family(stores_env):
    with pytest.raises(ValueError):
        stores_env["image"].persist_image(
            workspace_root=stores_env["workspace"],
            relative_path="images/frame.png",
            content=b"png",
            mime_type="audio/mpeg",
            created_at=CREATED_AT,
        )


def test_image_store_rejects_extension_mismatch(stores_env):
    with pytest.raises(ValueError):
        stores_env["image"].persist_image(
            workspace_root=stores_env["workspace"],
            relative_path="images/frame.jpg",
            content=b"jpeg",
            mime_type="image/png",
            created_at=CREATED_AT,
        )


def test_image_store_direct_bytes_cannot_bypass_rules(stores_env):
    with pytest.raises(ValueError):
        stores_env["image"].persist_bytes(
            workspace_root=stores_env["workspace"],
            relative_path="images/frame.png",
            content=b"png",
            artifact_type="image",
            mime_type="video/mp4",
            created_at=CREATED_AT,
        )


def test_audio_store_persists_wav_alias(stores_env):
    result = stores_env["audio"].persist_audio(
        workspace_root=stores_env["workspace"],
        relative_path="audio/voice.wav",
        content=b"RIFFCIPS-WAVE",
        mime_type="audio/x-wav",
        metadata={"duration": 3.5, "codec": "pcm_s16le"},
        created_at=CREATED_AT,
    )
    assert result.artifact.mime_type == "audio/x-wav"
    assert result.artifact.metadata["duration"] == 3.5


def test_audio_store_infers_mp3_mime(stores_env):
    result = stores_env["audio"].persist_audio(
        workspace_root=stores_env["workspace"],
        relative_path="audio/music.mp3",
        content=b"ID3CIPS",
        created_at=CREATED_AT,
    )
    assert result.artifact.mime_type == "audio/mpeg"


def test_audio_store_direct_bytes_cannot_bypass_rules(stores_env):
    with pytest.raises(ValueError):
        stores_env["audio"].persist_bytes(
            workspace_root=stores_env["workspace"],
            relative_path="audio/music.mp3",
            content=b"ID3",
            artifact_type="audio",
            mime_type="image/jpeg",
            created_at=CREATED_AT,
        )


def test_video_store_persists_metadata_without_processing(stores_env):
    result = stores_env["video"].persist_video(
        workspace_root=stores_env["workspace"],
        relative_path="video/final.mp4",
        content=b"ftypCIPS-video",
        metadata={"duration": 12.25, "codec": "h264", "source": "test"},
        created_at=CREATED_AT,
    )
    assert result.artifact.mime_type == "video/mp4"
    assert result.artifact.metadata["codec"] == "h264"
    assert result.artifact.metadata["duration"] == 12.25


def test_video_store_rejects_mime_extension_mismatch(stores_env):
    with pytest.raises(ValueError):
        stores_env["video"].persist_video(
            workspace_root=stores_env["workspace"],
            relative_path="video/final.mov",
            content=b"video",
            mime_type="video/mp4",
            created_at=CREATED_AT,
        )


def test_video_store_direct_bytes_cannot_bypass_rules(stores_env):
    with pytest.raises(ValueError):
        stores_env["video"].persist_bytes(
            workspace_root=stores_env["workspace"],
            relative_path="video/final.mp4",
            content=b"video",
            artifact_type="video",
            mime_type="audio/mp4",
            created_at=CREATED_AT,
        )


@pytest.mark.parametrize(
    ("store_name", "method_name", "relative_path"),
    [
        ("image", "persist_image", "images/empty.png"),
        ("audio", "persist_audio", "audio/empty.mp3"),
        ("video", "persist_video", "video/empty.mp4"),
    ],
)
def test_binary_media_stores_reject_empty_payloads(
    stores_env, store_name, method_name, relative_path
):
    store = stores_env[store_name]
    method = getattr(store, method_name)
    with pytest.raises(ValueError):
        method(
            workspace_root=stores_env["workspace"],
            relative_path=relative_path,
            content=b"",
            created_at=CREATED_AT,
        )


def test_metadata_store_writes_deterministic_json(stores_env):
    result = stores_env["metadata"].persist_metadata(
        workspace_root=stores_env["workspace"],
        relative_path="metadata/item.json",
        content={"z": 1, "a": {"path": Path("x/y")}},
        created_at=CREATED_AT,
    )
    raw = Path(result.artifact.path).read_text(encoding="utf-8")
    assert raw.index('"a"') < raw.index('"z"')
    assert json.loads(raw) == {"a": {"path": "x/y"}, "z": 1}
    assert result.artifact.mime_type == "application/json"
    assert result.artifact.metadata["format"] == "json"


def test_metadata_store_is_order_independent_for_hashing(stores_env):
    store = stores_env["metadata"]
    workspace = stores_env["workspace"]
    first = store.persist_metadata(
        workspace_root=workspace,
        relative_path="metadata/a.json",
        content={"b": 2, "a": 1},
        artifact_id="meta_a",
        created_at=CREATED_AT,
    )
    second = store.persist_metadata(
        workspace_root=workspace,
        relative_path="metadata/b.json",
        content={"a": 1, "b": 2},
        artifact_id="meta_b",
        created_at="2026-08-09T15:32:00+00:00",
    )
    assert first.artifact.content_hash == second.artifact.content_hash
    assert Path(first.artifact.path) == Path(second.artifact.path)
    assert second.deduplicated is True


def test_metadata_store_rejects_reserved_sidecar_suffix(stores_env):
    with pytest.raises(ValueError):
        stores_env["metadata"].persist_metadata(
            workspace_root=stores_env["workspace"],
            relative_path="metadata/custom.meta.json",
            content={"x": 1},
            created_at=CREATED_AT,
        )


def test_metadata_store_rejects_non_json_extension(stores_env):
    with pytest.raises(ValueError):
        stores_env["metadata"].persist_metadata(
            workspace_root=stores_env["workspace"],
            relative_path="metadata/custom.yaml",
            content={"x": 1},
            created_at=CREATED_AT,
        )


def test_metadata_store_direct_bytes_requires_valid_utf8_json_object(stores_env):
    with pytest.raises(ValueError):
        stores_env["metadata"].persist_bytes(
            workspace_root=stores_env["workspace"],
            relative_path="metadata/raw.json",
            content=b"not-json",
            artifact_type="metadata",
            mime_type="application/json",
            created_at=CREATED_AT,
        )


def test_metadata_store_rejects_json_array_root(stores_env):
    with pytest.raises(ValueError):
        stores_env["metadata"].persist_bytes(
            workspace_root=stores_env["workspace"],
            relative_path="metadata/raw.json",
            content=b"[1, 2]",
            artifact_type="metadata",
            mime_type="application/json",
            created_at=CREATED_AT,
        )


def test_metadata_store_rejects_wrong_mime(stores_env):
    with pytest.raises(ValueError):
        stores_env["metadata"].persist_bytes(
            workspace_root=stores_env["workspace"],
            relative_path="metadata/raw.json",
            content=b'{"ok": true}',
            artifact_type="metadata",
            mime_type="text/plain",
            created_at=CREATED_AT,
        )


def test_windows_style_path_metadata_is_portable(stores_env):
    result = stores_env["metadata"].persist_metadata(
        workspace_root=stores_env["workspace"],
        relative_path="metadata/portable.json",
        content={"path": PureWindowsPath("assets\\frame.png")},
        created_at=CREATED_AT,
    )
    assert json.loads(Path(result.artifact.path).read_text(encoding="utf-8"))["path"] == "assets/frame.png"


def test_media_stores_inherit_path_confinement(stores_env):
    with pytest.raises(WorkspaceSecurityError):
        stores_env["image"].persist_image(
            workspace_root=stores_env["workspace"],
            relative_path="../escape.png",
            content=b"png",
            created_at=CREATED_AT,
        )


def test_media_stores_block_windows_style_traversal(stores_env):
    with pytest.raises(WorkspaceSecurityError):
        stores_env["audio"].persist_audio(
            workspace_root=stores_env["workspace"],
            relative_path="..\\escape.mp3",
            content=b"mp3",
            created_at=CREATED_AT,
        )


def test_explicit_collision_policy_still_comes_from_artifact_store(stores_env):
    store = stores_env["video"]
    workspace = stores_env["workspace"]
    first = store.persist_video(
        workspace_root=workspace,
        relative_path="video/collision.mp4",
        content=b"first",
        created_at=CREATED_AT,
    )
    second = store.persist_video(
        workspace_root=workspace,
        relative_path="video/collision.mp4",
        content=b"second",
        artifact_id="replacement_video",
        collision_policy=CollisionPolicy.REPLACE,
        created_at="2026-08-09T15:33:00+00:00",
    )
    assert Path(second.artifact.path).read_bytes() == b"second"
    assert first.artifact.content_hash != second.artifact.content_hash


def test_no_store_creates_global_manifest(stores_env):
    workspace = stores_env["workspace"]
    stores_env["text"].persist_text(
        workspace_root=workspace,
        relative_path="text/a.md",
        content="a",
        created_at=CREATED_AT,
    )
    stores_env["metadata"].persist_metadata(
        workspace_root=workspace,
        relative_path="metadata/a.json",
        content={"a": 1},
        created_at=CREATED_AT,
    )
    assert not (workspace / "MANIFEST.json").exists()
