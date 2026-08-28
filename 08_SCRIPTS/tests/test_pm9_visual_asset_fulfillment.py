from __future__ import annotations

import json
import shutil
import struct
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from asset_resolution import (  # noqa: E402
    AssetBinary,
    BinaryAssetProviderAdapter,
    ExistingAssetProvider,
    ManifestAssetResolver,
    MediaFamily,
    WikimediaCommonsProvider,
    image_dimensions,
)
from capability_resolver import CapabilityResolver  # noqa: E402
from creative_direction_planner import (  # noqa: E402
    CreativeDirectionPlanner,
    CreativeDirectionPlanningError,
)
from media_provider import MediaRequest  # noqa: E402
from media_provider_registry import MediaProviderRegistry  # noqa: E402
from production_acceptance import (  # noqa: E402
    ApprovedAssetCatalog,
    VisualAssetFulfillmentService,
)
import production_acceptance.pipeline as acceptance_pipeline  # noqa: E402
from production_manifest import (  # noqa: E402
    AssetRequest,
    AssetType,
    AudioDesignSpec,
    CostHint,
    ProductionManifest,
    QualityHint,
)
from production_manifest_compiler import ProductionManifestCompiler  # noqa: E402
from workspace_resolver import WorkspaceResolver  # noqa: E402


FIXTURE_PROJECT = Path(__file__).parent / "fixtures" / "pm9" / "editorial_project"
COMMONS_FILE_URL = "https://upload.wikimedia.org/example/test-image.png"
COMMONS_PAGE_URL = "https://commons.wikimedia.org/wiki/File:Test_image.png"


def _png(width: int = 1280, height: int = 720, marker: bytes = b"fixture") -> bytes:
    return (
        b"\x89PNG\r\n\x1a\n"
        + struct.pack(">I", 13)
        + b"IHDR"
        + struct.pack(">II", width, height)
        + b"\x08\x02\x00\x00\x00"
        + marker
    )


def _commons_page(
    *,
    index: int = 1,
    page_id: int = 10,
    title: str = "File:Test image.png",
    license_name: str = "CC BY-SA 4.0",
    artist: str = "Example Creator",
    width: int = 1280,
    height: int = 720,
) -> dict:
    return {
        "pageid": page_id,
        "index": index,
        "title": title,
        "imageinfo": [
            {
                "url": COMMONS_FILE_URL,
                "descriptionurl": COMMONS_PAGE_URL,
                "mime": "image/png",
                "mediatype": "BITMAP",
                "width": width,
                "height": height,
                "size": len(_png(width, height)),
                "extmetadata": {
                    "LicenseShortName": {"value": license_name},
                    "LicenseUrl": {
                        "value": "https://creativecommons.org/licenses/by-sa/4.0/"
                    },
                    "Artist": {"value": f"<b>{artist}</b>"},
                    "Credit": {"value": "Wikimedia Commons"},
                    "UsageTerms": {"value": license_name},
                },
            }
        ],
    }


def _api_payload(*pages: dict) -> dict:
    return {"batchcomplete": True, "query": {"pages": list(pages)}}


def _provider(payload: dict, content: bytes | None = None):
    urls: list[str] = []
    downloads: list[str] = []

    def fetch_json(url: str):
        urls.append(url)
        return payload

    def fetch_bytes(url: str):
        downloads.append(url)
        return content if content is not None else _png()

    provider = WikimediaCommonsProvider(
        fetch_json=fetch_json,
        fetch_bytes=fetch_bytes,
    )
    return provider, urls, downloads


def _request(query: str = "skeletal muscle anatomy") -> MediaRequest:
    return MediaRequest(
        capability="stock_image_search",
        payload={"stock_query": query},
    )


def _minimal_manifest(tmp_path: Path) -> tuple[ProductionManifest, Path, WorkspaceResolver]:
    projects_root = tmp_path / "04_PROYECTOS"
    outputs_root = tmp_path / "05_OUTPUTS"
    project = projects_root / "PM9_AUTOMATED_VISUAL_FIXTURE"
    projects_root.mkdir()
    outputs_root.mkdir()
    shutil.copytree(FIXTURE_PROJECT, project)
    workspace = WorkspaceResolver(projects_root, outputs_root)
    source = ProductionManifestCompiler(workspace_resolver=workspace).compile(project)
    payload = source.model_dump(mode="json")
    scene = payload["scenes"][0]
    scene["sequence"] = 1
    scene["start_seconds"] = 0.0
    scene["narration_text"] = None
    scene["captions"] = None
    scene["on_screen_text"] = []
    scene["asset_request"] = {
        "asset_type": "stock_image",
        "creative_brief": "Una imagen editorial verificable.",
        "stock_query": "skeletal muscle anatomy",
        "alternatives": [],
        "quality_hint": "standard",
        "cost_hint": "free",
    }
    payload["scenes"] = [scene]
    payload["output"]["duration_seconds"] = scene["duration_seconds"]
    payload["narration"]["estimated_duration_seconds"] = min(
        1.0,
        scene["duration_seconds"],
    )
    payload["audio_design"] = AudioDesignSpec().model_dump(mode="json")
    return ProductionManifest.model_validate(payload), project, workspace


def test_wikimedia_provider_declares_free_standard_capability() -> None:
    provider, _, _ = _provider(_api_payload(_commons_page()))

    metadata = provider.capabilities()["stock_image_search"]

    assert metadata["free_tier"] is True
    assert metadata["cost_tier"] == "free"
    assert metadata["quality_tier"] == "standard"
    assert provider.estimate_cost(_request()) == 0.0


def test_wikimedia_provider_returns_validated_bytes_and_provenance() -> None:
    provider, search_urls, downloads = _provider(
        _api_payload(_commons_page()),
        _png(),
    )

    result = provider.generate(_request())

    assert result.success is True
    assert isinstance(result.output, AssetBinary)
    assert result.output.media_family is MediaFamily.IMAGE
    assert result.output.actual_cost_usd == 0.0
    assert result.output.metadata["license_name"] == "CC BY-SA 4.0"
    assert result.output.metadata["attribution"] == "Example Creator"
    assert result.output.metadata["width_px"] == 1280
    assert result.output.metadata["height_px"] == 720
    assert result.output.metadata["aspect_ratio"] == 1.77777778
    assert result.output.metadata["downloaded_size_bytes"] == len(_png())
    assert result.output.metadata["stock_query"] == "skeletal muscle anatomy"
    assert result.output.delivery_uri == COMMONS_FILE_URL
    assert len(search_urls) == 1
    assert "generator=search" in search_urls[0]
    assert downloads == [COMMONS_FILE_URL]
    assert provider.calls == [_request()]


def test_wikimedia_provider_rejects_noncommercial_license_before_download() -> None:
    provider, _, downloads = _provider(
        _api_payload(_commons_page(license_name="CC BY-NC 4.0")),
    )

    result = provider.generate(_request())

    assert result.success is False
    assert any("licencia_rechazada" in error for error in result.errors)
    assert downloads == []
    assert provider.calls == []


def test_image_dimensions_reads_physical_png_and_jpeg() -> None:
    assert image_dimensions(_png(1080, 1920), "image/png") == (1080, 1920)
    jpeg = (
        b"\xff\xd8"
        + b"\xff\xe0\x00\x04AB"
        + b"\xff\xc0\x00\x11\x08"
        + struct.pack(">HH", 720, 1280)
        + b"\x03" + (b"\x01\x11\x00" * 3)
        + b"\xff\xd9"
    )
    assert image_dimensions(jpeg, "image/jpeg") == (1280, 720)


def test_fulfillment_resolves_persists_updates_catalog_and_reuses_without_call(
    tmp_path: Path,
) -> None:
    manifest, project, workspace = _minimal_manifest(tmp_path)
    provider, search_urls, downloads = _provider(
        _api_payload(_commons_page()),
        _png(),
    )
    resolver = ManifestAssetResolver(
        capability_resolver=CapabilityResolver(
            MediaProviderRegistry([provider])
        ),
        workspace_resolver=workspace,
    )
    service = VisualAssetFulfillmentService(
        asset_resolver=resolver,
        workspace_resolver=workspace,
    )

    first = service.fulfill(
        manifest,
        workspace_root=project,
        assets_root=project / "source_assets",
        catalog_relative_path="source_assets/automated_catalog.json",
    )
    second = service.fulfill(
        manifest,
        workspace_root=project,
        assets_root=project / "source_assets",
        catalog_relative_path="source_assets/automated_catalog.json",
    )

    assert first.resolution.resolved_count == 1
    assert first.resolution.reused_existing is False
    assert second.resolution.reused_existing is True
    assert second.resolution.resolved_count == 0
    assert len(provider.calls) == 1
    assert len(search_urls) == 1
    assert len(downloads) == 1
    assert first.staged_count == 1
    assert second.reused_staged_count == 1
    assert first.catalog == second.catalog
    loaded = ApprovedAssetCatalog.load(first.catalog_path)
    entry = loaded.entries[0]
    assert entry.delivery_uri == COMMONS_FILE_URL
    assert entry.source_url == COMMONS_PAGE_URL
    assert entry.license_name == "CC BY-SA 4.0"
    assert entry.actual_cost_usd == 0.0
    assert (project / "source_assets" / entry.relative_path).is_file()
    record = first.resolution.bundle.assets[0]
    assert record.metadata["prompt_permitted"] == "skeletal muscle anatomy"
    assert record.metadata["width_px"] == 1280
    assert Path(first.catalog_sidecar_path).is_file()
    assert Path(first.report_sidecar_path).is_file()
    report = json.loads(first.report_path.read_text(encoding="utf-8"))
    assert report["catalog_entry_count"] == 1
    assert report["actual_cost_usd"] == 0.0
    assert report["publication_performed"] is False


def test_free_execution_failure_can_use_explicit_curated_fallback_and_blocks_gate(
    tmp_path: Path,
) -> None:
    manifest, project, workspace = _minimal_manifest(tmp_path)
    scene = manifest.scenes[0]
    request = AssetRequest(
        asset_type=AssetType.STOCK_IMAGE,
        creative_brief=scene.asset_request.creative_brief,
        stock_query=scene.asset_request.stock_query,
        existing_asset_id="curated-safe",
        alternatives=(AssetType.EXISTING_ASSET,),
        quality_hint=QualityHint.STANDARD,
        cost_hint=CostHint.FREE,
    )
    fallback_manifest = manifest.model_copy(
        update={
            "scenes": (
                scene.model_copy(update={"asset_request": request}),
            )
        }
    )
    failing = BinaryAssetProviderAdapter(
        lambda request: (_ for _ in ()).throw(RuntimeError("offline failure")),
        provider_name="free_stock_failure",
        capabilities={
            "stock_image_search": {
                "available": True,
                "cost_tier": "free",
                "free_tier": True,
                "quality_tier": "standard",
            }
        },
    )
    curated_path = project / "curated.png"
    curated_path.write_bytes(_png())
    curated = ExistingAssetProvider(
        {"curated-safe": curated_path},
        delivery_uris={
            "curated-safe": "https://cdn.example.test/curated-safe.png"
        },
    )
    resolver = ManifestAssetResolver(
        capability_resolver=CapabilityResolver(
            MediaProviderRegistry([failing, curated])
        ),
        workspace_resolver=workspace,
    )

    run = resolver.resolve(fallback_manifest, workspace_root=project)

    record = run.bundle.scene_visual(scene.scene_id)
    assert record.provider_name == curated.provider_name
    assert record.selected_from_alternative is True
    assert "fallback_asset_requires_human_review" in (
        acceptance_pipeline._preparation_blockers(fallback_manifest, run)
    )


def test_stock_query_override_is_provider_neutral_and_validated(tmp_path: Path) -> None:
    manifest, _, _ = _minimal_manifest(tmp_path)
    scene = manifest.scenes[0]
    planned = CreativeDirectionPlanner().plan(
        manifest,
        stock_queries={scene.scene_id: "plank exercise proper form"},
    )

    assert planned.scenes[0].asset_request.stock_query == (
        "plank exercise proper form"
    )
    non_stock = manifest.model_copy(
        update={
            "scenes": (
                scene.model_copy(
                    update={
                        "asset_request": AssetRequest(
                            asset_type=AssetType.AI_IMAGE,
                            image_prompt="A safe diagram",
                        )
                    }
                ),
            )
        }
    )
    with pytest.raises(CreativeDirectionPlanningError, match="stock_queries"):
        CreativeDirectionPlanner().plan(
            non_stock,
            stock_queries={scene.scene_id: "not applicable"},
        )
