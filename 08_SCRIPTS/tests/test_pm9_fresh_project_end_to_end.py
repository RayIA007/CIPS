from __future__ import annotations

import json
import shutil
import struct
import subprocess
import sys
import wave
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = SCRIPTS_DIR.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from asset_resolution import (  # noqa: E402
    ManifestAssetResolver,
    WikimediaCommonsProvider,
)
from capability_resolver import CapabilityResolver  # noqa: E402
from json2video_adapter import JSON2VideoAdapter  # noqa: E402
from media_provider_registry import MediaProviderRegistry  # noqa: E402
from production_acceptance import (  # noqa: E402
    ApprovedAssetCatalogProvider,
    FullProductionAcceptance,
    PM9SourceAssetBuilder,
    VisualAssetFulfillmentService,
)
import production_acceptance.source_assets as source_assets  # noqa: E402
from production_manifest import AssetType, serialize_manifest  # noqa: E402
from production_manifest_compiler import ProductionManifestCompiler  # noqa: E402
import run_pm9_full_production_acceptance as pm9_cli  # noqa: E402
from workspace_resolver import WorkspaceResolver  # noqa: E402


FRESH_PROJECT = (
    REPOSITORY_ROOT / "04_PROYECTOS" / "PROYECTO_PM9_CIELO_0001"
)


def _fresh_environment(tmp_path: Path):
    projects_root = tmp_path / "04_PROYECTOS"
    outputs_root = tmp_path / "05_OUTPUTS"
    projects_root.mkdir()
    outputs_root.mkdir()
    project = projects_root / FRESH_PROJECT.name
    shutil.copytree(FRESH_PROJECT, project)
    workspace = WorkspaceResolver(projects_root, outputs_root)
    config = pm9_cli._load_project_config(project)
    compiled = ProductionManifestCompiler(workspace_resolver=workspace).compile(project)
    planned = pm9_cli._planned_manifest(compiled, config)
    return project, outputs_root, workspace, config, planned


def _write_wav(path: Path, *, seconds: float = 0.1) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(8_000)
        stream.writeframes(b"\x00\x00" * max(1, round(seconds * 8_000)))


def _completed(stdout: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess([], 0, stdout=stdout, stderr="")


def _build_audio_seed(
    project: Path,
    outputs_root: Path,
    manifest,
    monkeypatch: pytest.MonkeyPatch,
):
    assets_root = project / "source_assets"
    model_dir = outputs_root / "pm9_models" / "piper"
    model_dir.mkdir(parents=True)
    (model_dir / "es_MX-claude-high.onnx").write_bytes(b"offline-model")
    (model_dir / "es_MX-claude-high.onnx.json").write_text(
        "{}", encoding="utf-8"
    )
    monkeypatch.setattr(source_assets.shutil, "which", lambda name: f"/bin/{name}")
    monkeypatch.setattr(
        source_assets.importlib.util,
        "find_spec",
        lambda name: object(),
    )
    monkeypatch.setattr(
        source_assets,
        "_write_procedural_audio",
        lambda path, duration_seconds, kind: _write_wav(path),
    )

    def runner(command):
        command = tuple(str(item) for item in command)
        if command[0] == sys.executable and command[1:3] == ("-m", "piper"):
            _write_wav(Path(command[command.index("-f") + 1]), seconds=1.0)
        elif command[0] == "ffprobe":
            return _completed("1.000000\n")
        elif command[0] == "ffmpeg":
            destination = Path(command[-1])
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(b"ID3\x04\x00\x00PM9.2-" + destination.name.encode())
        return _completed()

    builder = PM9SourceAssetBuilder(
        manifest,
        project_path=project,
        assets_root=assets_root,
        model_dir=model_dir,
        delivery_base_uri=(
            "https://raw.githubusercontent.com/RayIA007/CIPS/main/"
            f"04_PROYECTOS/{project.name}/source_assets"
        ),
        runner=runner,
        fetch_bytes=lambda url: pytest.fail(
            "El builder genérico no debe descargar visuales."
        ),
    )
    return builder, builder.build()


def _png(width: int, height: int, marker: bytes) -> bytes:
    return (
        b"\x89PNG\r\n\x1a\n"
        + struct.pack(">I", 13)
        + b"IHDR"
        + struct.pack(">II", width, height)
        + b"\x08\x02\x00\x00\x00"
        + marker
    )


def _wikimedia_provider() -> WikimediaCommonsProvider:
    call_index = 0
    content_by_url: dict[str, bytes] = {}

    def fetch_json(url: str):
        nonlocal call_index
        call_index += 1
        width = 1280 + call_index
        height = 720 + call_index
        file_url = (
            "https://upload.wikimedia.org/wikipedia/commons/"
            f"pm9-fresh-{call_index}.png"
        )
        content_by_url[file_url] = _png(
            width,
            height,
            f"fresh-{call_index}".encode(),
        )
        return {
            "batchcomplete": True,
            "query": {
                "pages": [
                    {
                        "pageid": 9000 + call_index,
                        "index": 1,
                        "title": f"File:PM9 fresh {call_index}.png",
                        "imageinfo": [
                            {
                                "url": file_url,
                                "descriptionurl": (
                                    "https://commons.wikimedia.org/wiki/"
                                    f"File:PM9_fresh_{call_index}.png"
                                ),
                                "mime": "image/png",
                                "mediatype": "BITMAP",
                                "width": width,
                                "height": height,
                                "size": len(content_by_url[file_url]),
                                "extmetadata": {
                                    "LicenseShortName": {"value": "CC BY-SA 4.0"},
                                    "LicenseUrl": {
                                        "value": (
                                            "https://creativecommons.org/"
                                            "licenses/by-sa/4.0/"
                                        )
                                    },
                                    "Artist": {"value": "PM9 offline fixture"},
                                    "Credit": {"value": "Wikimedia Commons"},
                                    "UsageTerms": {"value": "CC BY-SA 4.0"},
                                },
                            }
                        ],
                    }
                ]
            },
        }

    return WikimediaCommonsProvider(
        fetch_json=fetch_json,
        fetch_bytes=lambda url: content_by_url[url],
    )


def test_fresh_project_compiles_short_distinct_provider_neutral_plan(
    tmp_path: Path,
) -> None:
    project, _, _, config, planned = _fresh_environment(tmp_path)

    assert planned.project.project_id == "PROYECTO_PM9_CIELO_0001"
    assert "plancha" not in planned.project.title.casefold()
    assert planned.output.duration_seconds == 26.0
    assert (planned.output.width_px, planned.output.height_px) == (1080, 1920)
    assert len(planned.scenes) == 3
    assert all(
        scene.asset_request.asset_type is AssetType.STOCK_IMAGE
        for scene in planned.scenes
    )
    assert config["stock_queries_by_sequence"] == {
        1: "blue sky daylight",
        2: "Rayleigh scattering diagram",
        3: "red sunset horizon",
    }
    assert len(planned.source_references) == 7
    assert all(
        len(reference.content_hash or "") == 64
        for reference in planned.source_references
    )
    serialized = serialize_manifest(planned).casefold()
    assert "wikimedia" not in serialized
    assert "json2video" not in serialized
    assert "creatomate" not in serialized
    research = (project / "research" / "01_INVESTIGACION.md").read_text(
        encoding="utf-8"
    )
    assert "https://spaceplace.nasa.gov/blue-sky/" in research
    assert "https://www.nesdis.noaa.gov/" in research


def test_generic_builder_creates_idempotent_audio_seed_without_curated_visuals(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project, outputs_root, _, _, planned = _fresh_environment(tmp_path)
    builder, first = _build_audio_seed(
        project,
        outputs_root,
        planned,
        monkeypatch,
    )
    second = builder.build()

    assert len(first.catalog.entries) == 7
    assert not any(entry.role == "scene_visual" for entry in first.catalog.entries)
    assert first.network_called is False
    assert first.generated_count == 7
    assert second.reused_existing is True
    assert second.generated_count == 0
    assert second.network_called is False
    report = json.loads(first.report_path.read_text(encoding="utf-8"))
    assert report["build_profile"] == "generic_audio_seed"
    assert report["catalog_entry_count"] == 7
    assert report["actual_cost_usd"] == 0.0
    assert report["paid_provider_called"] is False
    assert report["publication_performed"] is False
    assert "source_photo_sha256" not in report


def test_offline_fresh_chain_reaches_json2video_preparation_without_publication(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project, outputs_root, workspace, config, planned = _fresh_environment(tmp_path)
    _, seed = _build_audio_seed(
        project,
        outputs_root,
        planned,
        monkeypatch,
    )
    seed_provider = ApprovedAssetCatalogProvider(
        seed.catalog,
        assets_root=seed.assets_root,
    )
    wikimedia = _wikimedia_provider()
    fulfillment_resolver = ManifestAssetResolver(
        capability_resolver=CapabilityResolver(
            MediaProviderRegistry([seed_provider, wikimedia])
        ),
        workspace_resolver=workspace,
        preferred_providers={"stock_image_search": wikimedia.provider_name},
    )
    fulfillment = VisualAssetFulfillmentService(
        asset_resolver=fulfillment_resolver,
        workspace_resolver=workspace,
    ).fulfill(
        planned,
        workspace_root=project,
        assets_root=seed.assets_root,
        catalog_relative_path=config["catalog_relative_path"],
        report_relative_path=config["fulfillment_report_relative_path"],
    )

    assert len(wikimedia.calls) == 3
    assert len(fulfillment.catalog.entries) == 10
    assert fulfillment.resolution.bundle.total_actual_cost_usd == 0.0
    assert fulfillment.resolution.bundle.unknown_cost_count == 0
    assert all(
        entry.actual_cost_usd == 0.0 for entry in fulfillment.catalog.entries
    )

    final_provider = ApprovedAssetCatalogProvider(
        fulfillment.catalog,
        assets_root=seed.assets_root,
    )
    acceptance = FullProductionAcceptance(
        workspace_resolver=workspace,
        asset_resolver=ManifestAssetResolver(
            capability_resolver=CapabilityResolver(
                MediaProviderRegistry([final_provider])
            ),
            workspace_resolver=workspace,
        ),
    )
    prepared = acceptance.prepare(
        project,
        asset_types_by_sequence=config["asset_types_by_sequence"],
        existing_asset_ids_by_sequence=config["existing_asset_ids_by_sequence"],
        stock_queries_by_sequence=config["stock_queries_by_sequence"],
        adapter_factory=lambda bundle: JSON2VideoAdapter(resolved_assets=bundle),
        payload_relative_path=Path("video/json2video/json2video_payload.json"),
    )

    assert prepared.evidence.ready_for_real_render is True
    assert prepared.evidence.persisted_asset_count == 10
    assert prepared.evidence.total_actual_cost_usd == 0.0
    assert prepared.evidence.unknown_cost_count == 0
    assert len(prepared.plan.target_payload["scenes"]) == 3
    assert prepared.plan.target_payload["fps"] == 30
    assert prepared.plan.target_payload["client-data"]["publication_performed"] is False
    assert not (project / "final").exists()
    report = json.loads(fulfillment.report_path.read_text(encoding="utf-8"))
    assert report["actual_cost_usd"] == 0.0
    assert report["render_performed"] is False
    assert report["publication_performed"] is False
