from __future__ import annotations

import hashlib
import shutil
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from asset_resolution import (  # noqa: E402
    AssetBinary,
    AssetOutputValidationError,
    AssetProviderExecutionError,
    AssetProviderPolicy,
    AssetProviderSelectionError,
    AssetReceiptIntegrityError,
    BinaryAssetProviderAdapter,
    ExistingAssetProvider,
    ManifestAssetResolver,
    MediaFamily,
    ResolutionStatus,
    asset_resolution_json_schema,
    deserialize_asset_resolution,
    serialize_asset_resolution,
)
from capability_resolver import CapabilityResolver  # noqa: E402
from creative_direction_planner import CreativeDirectionPlanner  # noqa: E402
from creatomate_adapter import CreatomateAdapter  # noqa: E402
from media_provider import MediaRequest  # noqa: E402
from media_provider_registry import MediaProviderRegistry  # noqa: E402
from production_manifest import (  # noqa: E402
    AssetRequest,
    AssetType,
    CostHint,
    ProductionManifest,
    QualityHint,
    serialize_manifest,
)
from production_manifest_compiler import ProductionManifestCompiler  # noqa: E402
from render_adapter import RenderCompilationError  # noqa: E402
from workspace_resolver import WorkspaceResolver  # noqa: E402


FIXTURE_PROJECT = Path(__file__).parent / "fixtures" / "pm2" / "editorial_project"


@pytest.fixture()
def planned_manifest(tmp_path: Path) -> tuple[ProductionManifest, Path, WorkspaceResolver]:
    projects_root = tmp_path / "04_PROYECTOS"
    outputs_root = tmp_path / "05_OUTPUTS"
    projects_root.mkdir()
    outputs_root.mkdir()
    project_path = projects_root / "PROYECTO_PM8_0001"
    shutil.copytree(FIXTURE_PROJECT, project_path)
    workspace_resolver = WorkspaceResolver(
        projects_root=projects_root,
        outputs_root=outputs_root,
    )
    source = ProductionManifestCompiler(
        workspace_resolver=workspace_resolver
    ).compile(project_path)
    manifest = CreativeDirectionPlanner(
        workspace_resolver=workspace_resolver
    ).plan(source)
    return manifest, project_path, workspace_resolver


@pytest.fixture()
def mixed_manifest(
    planned_manifest: tuple[ProductionManifest, Path, WorkspaceResolver],
) -> tuple[ProductionManifest, Path, WorkspaceResolver]:
    manifest, project_path, workspace_resolver = planned_manifest
    requests = (
        AssetRequest(
            asset_type=AssetType.AI_IMAGE,
            creative_brief="Macro biomedical scene",
            image_prompt="Detailed cellular repair in cyan and amber",
            quality_hint=QualityHint.HIGH,
            cost_hint=CostHint.FREE,
        ),
        AssetRequest(
            asset_type=AssetType.STOCK_VIDEO,
            creative_brief="Verification workflow",
            stock_query="researcher verifying two independent sources",
            quality_hint=QualityHint.HIGH,
            cost_hint=CostHint.FREE,
        ),
        AssetRequest(
            asset_type=AssetType.EXISTING_ASSET,
            creative_brief="Approved closing visual",
            existing_asset_id="existing-scene-3",
            quality_hint=QualityHint.HIGH,
            cost_hint=CostHint.FREE,
        ),
    )
    scenes = tuple(
        scene.model_copy(update={"asset_request": request})
        for scene, request in zip(manifest.scenes, requests)
    )
    return manifest.model_copy(update={"scenes": scenes}), project_path, workspace_resolver


def _binary_backend(*, delivery: bool = True, fail: bool = False):
    def backend(request: MediaRequest) -> AssetBinary:
        if fail:
            raise RuntimeError("requested provider failure")
        capability = request.capability
        identity = str(request.payload.get("scene_id") or request.payload.get("cue_id") or capability)
        if capability == "image_generation":
            return AssetBinary(
                content=b"\x89PNG\r\n\x1a\nPM8-image",
                mime_type="image/png",
                file_extension=".png",
                media_family=MediaFamily.IMAGE,
                delivery_uri=(f"https://cdn.example.test/{identity}.png" if delivery else None),
                actual_cost_usd=0.0,
                metadata={"source": "offline_test", "api_key": "must-not-persist"},
            )
        if capability in {"stock_video_search", "ai_video_generation"}:
            return AssetBinary(
                content=b"\x00\x00\x00\x18ftypmp42PM8-video",
                mime_type="video/mp4",
                file_extension=".mp4",
                media_family=MediaFamily.VIDEO,
                delivery_uri=(f"https://cdn.example.test/{identity}.mp4" if delivery else None),
                actual_cost_usd=0.0,
                metadata={"license": "test-fixture", "token": "must-not-persist"},
            )
        return AssetBinary(
            content=b"RIFF\x10\x00\x00\x00WAVEfmt PM8-audio-" + identity.encode("utf-8"),
            mime_type="audio/wav",
            file_extension=".wav",
            media_family=MediaFamily.AUDIO,
            delivery_uri=(f"https://cdn.example.test/{identity}.wav" if delivery else None),
            actual_cost_usd=0.0,
            metadata={"source": "offline_test", "secret": "must-not-persist"},
        )

    return backend


def _provider(
    name: str,
    capabilities: tuple[str, ...],
    *,
    quality: str = "high",
    cost: str = "free",
    delivery: bool = True,
    fail: bool = False,
    estimate: float | None = 0.0,
) -> BinaryAssetProviderAdapter:
    return BinaryAssetProviderAdapter(
        _binary_backend(delivery=delivery, fail=fail),
        provider_name=name,
        capabilities={
            capability: {
                "available": True,
                "cost_tier": cost,
                "free_tier": cost == "free",
                "quality_tier": quality,
                "priority": 10,
            }
            for capability in capabilities
        },
        cost_estimator=lambda request: estimate,
    )


def _resolver_stack(
    manifest: ProductionManifest,
    project_path: Path,
    workspace_resolver: WorkspaceResolver,
    *,
    image_delivery: bool = True,
) -> tuple[ManifestAssetResolver, tuple[object, ...]]:
    existing_path = project_path / "source_existing.png"
    existing_path.write_bytes(b"\x89PNG\r\n\x1a\nexisting")
    image = _provider("free_ai_image", ("image_generation",), delivery=image_delivery)
    stock = _provider("free_stock", ("stock_video_search",))
    audio = _provider(
        "free_audio",
        ("voice_synthesis", "music_generation", "sound_effect_generation"),
    )
    existing = ExistingAssetProvider(
        {"existing-scene-3": existing_path},
        delivery_uris={
            "existing-scene-3": "https://cdn.example.test/existing-scene-3.png"
        },
    )
    registry = MediaProviderRegistry([image, stock, audio, existing])
    resolver = ManifestAssetResolver(
        capability_resolver=CapabilityResolver(registry),
        workspace_resolver=workspace_resolver,
    )
    return resolver, (image, stock, audio, existing)


def test_resolves_mixed_manifest_through_f4_f5_and_specialized_f3_stores(
    mixed_manifest: tuple[ProductionManifest, Path, WorkspaceResolver],
) -> None:
    manifest, project_path, workspace_resolver = mixed_manifest
    original = serialize_manifest(manifest)
    resolver, _ = _resolver_stack(manifest, project_path, workspace_resolver)

    run = resolver.resolve(manifest, workspace_root=project_path)

    assert len(run.bundle.assets) == 10
    assert run.resolved_count == 10
    assert run.reused_count == 0
    assert run.bundle.unknown_cost_count == 0
    assert run.bundle.total_estimated_cost_usd == 0.0
    assert run.bundle.total_actual_cost_usd == 0.0
    assert {asset.provider_name for asset in run.bundle.assets} == {
        "free_ai_image",
        "free_stock",
        "free_audio",
        "local_existing_assets",
    }
    assert run.bundle.scene_visual(
        manifest.scenes[0].scene_id
    ).source_reference_ids == manifest.scenes[0].source_reference_ids
    for asset in run.bundle.assets:
        assert asset.status is ResolutionStatus.PERSISTED
        assert (project_path / asset.artifact_relative_path).is_file()
        assert (project_path / asset.sidecar_relative_path).is_file()
        assert hashlib.sha256(
            (project_path / asset.artifact_relative_path).read_bytes()
        ).hexdigest() == asset.content_sha256
    assert (project_path / run.bundle_relative_path).is_file()
    assert (project_path / run.bundle_sidecar_relative_path).is_file()
    assert serialize_manifest(manifest) == original


def test_second_identical_resolution_reuses_bundle_without_provider_calls(
    mixed_manifest: tuple[ProductionManifest, Path, WorkspaceResolver],
) -> None:
    manifest, project_path, workspace_resolver = mixed_manifest
    resolver, providers = _resolver_stack(manifest, project_path, workspace_resolver)
    first = resolver.resolve(manifest, workspace_root=project_path)
    call_counts = [len(provider.calls) for provider in providers]

    second = resolver.resolve(manifest, workspace_root=project_path)

    assert second.reused_existing is True
    assert second.resolved_count == 0
    assert second.reused_count == 10
    assert second.bundle == first.bundle
    assert [len(provider.calls) for provider in providers] == call_counts


def test_creatomate_consumes_resolved_https_sources_without_provider_metadata(
    mixed_manifest: tuple[ProductionManifest, Path, WorkspaceResolver],
) -> None:
    manifest, project_path, workspace_resolver = mixed_manifest
    resolver, _ = _resolver_stack(manifest, project_path, workspace_resolver)
    bundle = resolver.resolve(manifest, workspace_root=project_path).bundle

    plan = CreatomateAdapter(resolved_assets=bundle).compile(manifest)
    media = [
        item
        for item in plan.target_payload["elements"]
        if item["type"] in {"audio", "image", "video"}
    ]

    assert CreatomateAdapter.adapter_version == "1.2"
    assert media
    assert all(item["source"].startswith("https://cdn.example.test/") for item in media)
    assert all("assets.invalid" not in item["source"] for item in media)
    assert all("provider" not in item for item in media)


def test_creatomate_rejects_resolved_asset_without_https_delivery_uri(
    mixed_manifest: tuple[ProductionManifest, Path, WorkspaceResolver],
) -> None:
    manifest, project_path, workspace_resolver = mixed_manifest
    resolver, _ = _resolver_stack(
        manifest,
        project_path,
        workspace_resolver,
        image_delivery=False,
    )
    bundle = resolver.resolve(manifest, workspace_root=project_path).bundle

    with pytest.raises(RenderCompilationError, match="delivery_uri HTTPS"):
        CreatomateAdapter(resolved_assets=bundle).compile(manifest)


def test_creatomate_rejects_bundle_from_different_manifest_revision(
    mixed_manifest: tuple[ProductionManifest, Path, WorkspaceResolver],
) -> None:
    manifest, project_path, workspace_resolver = mixed_manifest
    resolver, _ = _resolver_stack(manifest, project_path, workspace_resolver)
    bundle = resolver.resolve(manifest, workspace_root=project_path).bundle
    changed = manifest.model_copy(update={"style_profile": "another-style-v1"})

    with pytest.raises(RenderCompilationError, match="no corresponde"):
        CreatomateAdapter(resolved_assets=bundle).compile(changed)


def test_policy_selects_high_quality_free_provider_and_blocks_paid_candidate() -> None:
    standard = _provider(
        "standard_free",
        ("image_generation",),
        quality="standard",
    )
    high = _provider("high_free", ("image_generation",), quality="high")
    paid = _provider(
        "premium_paid",
        ("image_generation",),
        quality="high",
        cost="premium",
        estimate=1.25,
    )
    policy = AssetProviderPolicy(
        CapabilityResolver(MediaProviderRegistry([paid, standard, high]))
    )
    request = MediaRequest("image_generation", {"prompt": "cell"})

    selection = policy.select(
        request,
        quality_hint=QualityHint.HIGH,
        cost_hint=CostHint.PREMIUM,
    )

    assert selection.provider is high
    assert selection.estimated_cost_usd == 0.0
    assert paid.calls == []


def test_unknown_cost_provider_is_rejected_before_execution() -> None:
    unknown = _provider(
        "unknown_cost",
        ("image_generation",),
        cost="balanced",
        estimate=None,
    )
    policy = AssetProviderPolicy(
        CapabilityResolver(MediaProviderRegistry([unknown]))
    )

    with pytest.raises(AssetProviderSelectionError, match="pago_no_autorizado"):
        policy.select(
            MediaRequest("image_generation", {"prompt": "cell"}),
            quality_hint=QualityHint.HIGH,
            cost_hint=CostHint.BALANCED,
        )
    assert unknown.calls == []


def test_paid_provider_becomes_selectable_only_with_explicit_runtime_authorization() -> None:
    paid = _provider(
        "premium_paid",
        ("image_generation",),
        quality="high",
        cost="premium",
        estimate=1.25,
    )
    policy = AssetProviderPolicy(
        CapabilityResolver(MediaProviderRegistry([paid])),
        allow_paid=True,
    )

    selection = policy.select(
        MediaRequest("image_generation", {"prompt": "cell"}),
        quality_hint=QualityHint.HIGH,
        cost_hint=CostHint.PREMIUM,
    )

    assert selection.provider is paid
    assert selection.estimated_cost_usd == 1.25
    assert paid.calls == []


def test_visual_alternative_is_used_when_primary_capability_is_unavailable(
    planned_manifest: tuple[ProductionManifest, Path, WorkspaceResolver],
) -> None:
    manifest, project_path, workspace_resolver = planned_manifest
    first_request = AssetRequest(
        asset_type=AssetType.AI_VIDEO,
        video_prompt="cell division cinematic video",
        stock_query="cell division microscopy",
        alternatives=(AssetType.STOCK_VIDEO,),
        quality_hint=QualityHint.HIGH,
        cost_hint=CostHint.FREE,
    )
    scenes = list(manifest.scenes)
    scenes[0] = scenes[0].model_copy(update={"asset_request": first_request})
    candidate = manifest.model_copy(update={"scenes": tuple(scenes)})
    stock = _provider("free_stock", ("stock_video_search",))
    audio = _provider(
        "free_audio",
        ("voice_synthesis", "music_generation", "sound_effect_generation"),
    )
    resolver = ManifestAssetResolver(
        capability_resolver=CapabilityResolver(MediaProviderRegistry([stock, audio])),
        workspace_resolver=workspace_resolver,
    )

    bundle = resolver.resolve(candidate, workspace_root=project_path).bundle
    visual = bundle.scene_visual(candidate.scenes[0].scene_id)

    assert visual.asset_type == "stock_video"
    assert visual.selected_from_alternative is True
    assert visual.provider_name == "free_stock"


def test_renderer_native_and_none_visuals_do_not_call_visual_provider(
    planned_manifest: tuple[ProductionManifest, Path, WorkspaceResolver],
) -> None:
    manifest, project_path, workspace_resolver = planned_manifest
    scenes = list(manifest.scenes)
    scenes[1] = scenes[1].model_copy(
        update={"asset_request": AssetRequest(asset_type=AssetType.NONE)}
    )
    candidate = manifest.model_copy(update={"scenes": tuple(scenes)})
    audio = _provider(
        "free_audio",
        ("voice_synthesis", "music_generation", "sound_effect_generation"),
    )
    resolver = ManifestAssetResolver(
        capability_resolver=CapabilityResolver(MediaProviderRegistry([audio])),
        workspace_resolver=workspace_resolver,
    )

    bundle = resolver.resolve(candidate, workspace_root=project_path).bundle

    assert [bundle.scene_visual(scene.scene_id).status for scene in candidate.scenes] == [
        ResolutionStatus.RENDERER_NATIVE,
        ResolutionStatus.NOT_REQUIRED,
        ResolutionStatus.RENDERER_NATIVE,
    ]
    assert all(call.capability != "image_generation" for call in audio.calls)


def test_provider_execution_failure_is_explicit_and_not_silently_retried(
    mixed_manifest: tuple[ProductionManifest, Path, WorkspaceResolver],
) -> None:
    manifest, project_path, workspace_resolver = mixed_manifest
    failing = _provider(
        "failing_image",
        ("image_generation",),
        fail=True,
    )
    resolver = ManifestAssetResolver(
        capability_resolver=CapabilityResolver(MediaProviderRegistry([failing])),
        workspace_resolver=workspace_resolver,
    )

    with pytest.raises(AssetProviderExecutionError, match="requested provider failure"):
        resolver.resolve(manifest, workspace_root=project_path)
    assert len(failing.calls) == 1


def test_positive_actual_cost_is_rejected_without_paid_authorization(
    mixed_manifest: tuple[ProductionManifest, Path, WorkspaceResolver],
) -> None:
    manifest, project_path, workspace_resolver = mixed_manifest

    def backend(request: MediaRequest) -> AssetBinary:
        return AssetBinary(
            content=b"\x89PNG\r\n\x1a\ncharged",
            mime_type="image/png",
            file_extension=".png",
            media_family=MediaFamily.IMAGE,
            delivery_uri="https://cdn.example.test/charged.png",
            actual_cost_usd=0.01,
        )

    deceptive = BinaryAssetProviderAdapter(
        backend,
        provider_name="deceptive_free",
        capabilities={
            "image_generation": {
                "cost_tier": "free",
                "free_tier": True,
                "quality_tier": "high",
            }
        },
        cost_estimator=lambda request: 0.0,
    )
    resolver = ManifestAssetResolver(
        capability_resolver=CapabilityResolver(MediaProviderRegistry([deceptive])),
        workspace_resolver=workspace_resolver,
    )

    with pytest.raises(AssetOutputValidationError, match="costo real positivo"):
        resolver.resolve(manifest, workspace_root=project_path)


def test_partial_failure_resumes_from_receipt_without_repeating_completed_provider(
    mixed_manifest: tuple[ProductionManifest, Path, WorkspaceResolver],
) -> None:
    manifest, project_path, workspace_resolver = mixed_manifest
    image = _provider("free_ai_image", ("image_generation",))
    failing_stock = _provider("free_stock", ("stock_video_search",), fail=True)
    audio = _provider(
        "free_audio",
        ("voice_synthesis", "music_generation", "sound_effect_generation"),
    )
    existing_path = project_path / "source_existing.png"
    existing_path.write_bytes(b"\x89PNG\r\n\x1a\nexisting")
    existing = ExistingAssetProvider(
        {"existing-scene-3": existing_path},
        delivery_uris={
            "existing-scene-3": "https://cdn.example.test/existing-scene-3.png"
        },
    )
    first_registry = MediaProviderRegistry([image, failing_stock, audio, existing])
    first = ManifestAssetResolver(
        capability_resolver=CapabilityResolver(first_registry),
        workspace_resolver=workspace_resolver,
    )

    with pytest.raises(AssetProviderExecutionError):
        first.resolve(manifest, workspace_root=project_path)
    assert len(image.calls) == 1

    working_stock = _provider("free_stock", ("stock_video_search",))
    second_registry = MediaProviderRegistry([image, working_stock, audio, existing])
    second = ManifestAssetResolver(
        capability_resolver=CapabilityResolver(second_registry),
        workspace_resolver=workspace_resolver,
    )
    run = second.resolve(manifest, workspace_root=project_path)

    assert len(image.calls) == 1
    assert run.reused_count >= 1
    assert run.bundle.scene_visual(manifest.scenes[0].scene_id).provider_name == "free_ai_image"


def test_identical_audio_bytes_are_deduplicated_by_f3_with_distinct_logical_records(
    planned_manifest: tuple[ProductionManifest, Path, WorkspaceResolver],
) -> None:
    manifest, project_path, workspace_resolver = planned_manifest

    def same_audio(request: MediaRequest) -> AssetBinary:
        return AssetBinary(
            content=b"RIFF\x10\x00\x00\x00WAVEidentical-audio",
            mime_type="audio/wav",
            file_extension=".wav",
            media_family=MediaFamily.AUDIO,
            delivery_uri="https://cdn.example.test/shared.wav",
            actual_cost_usd=0.0,
        )

    audio = BinaryAssetProviderAdapter(
        same_audio,
        provider_name="shared_free_audio",
        capabilities={
            capability: {
                "cost_tier": "free",
                "free_tier": True,
                "quality_tier": "high",
            }
            for capability in (
                "voice_synthesis",
                "music_generation",
                "sound_effect_generation",
            )
        },
        cost_estimator=lambda request: 0.0,
    )
    stock = _provider("free_stock", ("stock_video_search",))
    resolver = ManifestAssetResolver(
        capability_resolver=CapabilityResolver(
            MediaProviderRegistry([audio, stock])
        ),
        workspace_resolver=workspace_resolver,
    )

    bundle = resolver.resolve(manifest, workspace_root=project_path).bundle
    audio_records = [
        asset for asset in bundle.assets if asset.media_family is MediaFamily.AUDIO
    ]

    assert len(audio_records) == 7
    assert len({asset.artifact_relative_path for asset in audio_records}) == 1
    assert len({asset.artifact_id for asset in audio_records}) == 7
    shared_sidecar = project_path / audio_records[0].sidecar_relative_path
    sidecar_text = shared_sidecar.read_text(encoding="utf-8")
    assert all(asset.artifact_id in sidecar_text for asset in audio_records)


def test_existing_asset_provider_reads_only_allowlisted_physical_asset(tmp_path: Path) -> None:
    asset = tmp_path / "approved.png"
    asset.write_bytes(b"\x89PNG\r\n\x1a\napproved")
    provider = ExistingAssetProvider({"approved-1": asset})

    ok = provider.generate(
        MediaRequest(
            "existing_asset_resolution",
            {"existing_asset_id": "approved-1"},
        )
    )
    missing = provider.generate(
        MediaRequest(
            "existing_asset_resolution",
            {"existing_asset_id": "not-allowlisted"},
        )
    )

    assert ok.success is True
    assert ok.output.content == asset.read_bytes()
    assert ok.output.media_family is MediaFamily.IMAGE
    assert missing.success is False
    assert "existing_asset_not_found" in missing.errors[0]


def test_asset_binary_rejects_mime_with_invalid_physical_signature() -> None:
    with pytest.raises(ValueError, match="firma esperada"):
        AssetBinary(
            content=b"this-is-not-a-png",
            mime_type="image/png",
            file_extension=".png",
            media_family=MediaFamily.IMAGE,
        )


def test_tampered_physical_asset_blocks_resume_instead_of_regenerating(
    mixed_manifest: tuple[ProductionManifest, Path, WorkspaceResolver],
) -> None:
    manifest, project_path, workspace_resolver = mixed_manifest
    resolver, providers = _resolver_stack(manifest, project_path, workspace_resolver)
    first = resolver.resolve(manifest, workspace_root=project_path)
    visual = first.bundle.scene_visual(manifest.scenes[0].scene_id)
    path = project_path / visual.artifact_relative_path
    path.write_bytes(b"tampered")
    call_counts = [len(provider.calls) for provider in providers]

    with pytest.raises(AssetReceiptIntegrityError, match="Hash físico inválido"):
        resolver.resolve(manifest, workspace_root=project_path)
    assert [len(provider.calls) for provider in providers] == call_counts


def test_bundle_serialization_round_trip_schema_and_secret_redaction(
    mixed_manifest: tuple[ProductionManifest, Path, WorkspaceResolver],
) -> None:
    manifest, project_path, workspace_resolver = mixed_manifest
    resolver, _ = _resolver_stack(manifest, project_path, workspace_resolver)
    bundle = resolver.resolve(manifest, workspace_root=project_path).bundle

    serialized = serialize_asset_resolution(bundle)
    rebuilt = deserialize_asset_resolution(serialized)
    schema = asset_resolution_json_schema()

    assert rebuilt == bundle
    assert schema["title"] == "AssetResolutionBundle"
    assert "must-not-persist" not in serialized
    assert "api_key" not in serialized
    assert "secret" not in serialized
    assert "token" not in serialized


def test_pm8_modules_do_not_contaminate_production_manifest_or_import_provider_sdks() -> None:
    manifest_text = (SCRIPTS_DIR / "production_manifest" / "models.py").read_text(
        encoding="utf-8"
    ).lower()
    pm8_text = "\n".join(
        path.read_text(encoding="utf-8").lower()
        for path in sorted((SCRIPTS_DIR / "asset_resolution").glob("*.py"))
    )

    assert "provider_name" not in manifest_text
    assert "delivery_uri" not in manifest_text
    assert "api_key" not in manifest_text
    forbidden = (
        "import google",
        "import openai",
        "import requests",
        "import edge_tts",
        "import creatomate",
    )
    assert all(token not in pm8_text for token in forbidden)
