"""Operate PM9 without conflating preparation, paid render, and human review.

The default ``inventory`` and ``prepare`` commands are offline.  ``render`` is
guarded by both an environment confirmation and an explicit credit ceiling.
``accept`` never publishes; it records F7 and exports only an approved MP4.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from asset_resolution import ManifestAssetResolver, WikimediaCommonsProvider
from artifact_store import CollisionPolicy
from capability_resolver import CapabilityResolver
from creative_direction_planner import CreativeDirectionPlanner
from creatomate_adapter import CreatomateAdapter
from creatomate_api import (
    CREATOMATE_API_KEY_ENV,
    CreatomateApiClient,
    CreatomateApiConfig,
    CreatomateApiError,
    CreatomateExecutionContext,
    CreatomateRenderService,
    estimate_render_credits,
)
from json2video_adapter import (
    JSON2VIDEO_PAYLOAD_FILENAME,
    JSON2VideoAdapter,
    estimate_json2video_credits,
)
from json2video_api import (
    JSON2VIDEO_API_KEY_ENV,
    JSON2VideoApiClient,
    JSON2VideoApiConfig,
    JSON2VideoApiError,
    JSON2VideoRenderService,
)
from final_review import ReviewAction, ReviewDecision
from media_provider_registry import MediaProviderRegistry
from metadata_store import MetadataStore
from production_acceptance import (
    ApprovedAssetCatalog,
    ApprovedAssetCatalogProvider,
    FrameRatePolicy,
    FullProductionAcceptance,
    PM9SourceAssetBuilder,
    ProductionAcceptanceBlockedError,
    ProductionAcceptanceError,
    SourceAssetBuildError,
    VisualAssetFulfillmentError,
    VisualAssetFulfillmentService,
    VERIFY_REPORT_RELATIVE_PATH,
    derive_github_raw_base,
    verify_catalog_delivery,
)
from production_manifest import AssetType, ProductionManifest
from production_manifest_compiler import ProductionManifestCompiler
from render_adapter import RenderResult, RenderStatus
from workspace_resolver import WorkspaceResolver


CONFIRMATION_ENV = "CIPS_PM9_REAL_RENDER_CONFIRM"
CONFIRMATION_VALUE = "I_AUTHORIZE_REAL_RENDER"
ASSET_CONFIRMATION_ENV = "CIPS_PM9_REAL_ASSET_CONFIRM"
ASSET_CONFIRMATION_VALUE = "I_AUTHORIZE_FREE_VISUAL_ACQUISITION"
PROJECT_CONFIG_FILENAME = "production_acceptance_config.json"
INVENTORY_RELATIVE_PATH = Path("acceptance") / "asset_requirements.json"
RENDER_RESULT_RELATIVE_PATH = Path("render") / "creatomate_result.json"
JSON2VIDEO_RENDER_RESULT_RELATIVE_PATH = (
    Path("render") / "json2video_result.json"
)
JSON2VIDEO_PAYLOAD_RELATIVE_PATH = Path("render") / JSON2VIDEO_PAYLOAD_FILENAME
_PROVIDERS = ("creatomate", "json2video")

_VISUAL_CAPABILITIES: dict[AssetType, tuple[str, str]] = {
    AssetType.AI_VIDEO: ("ai_video_generation", "video"),
    AssetType.AI_IMAGE: ("image_generation", "image"),
    AssetType.STOCK_VIDEO: ("stock_video_search", "video"),
    AssetType.STOCK_IMAGE: ("stock_image_search", "image"),
    AssetType.EXISTING_ASSET: ("existing_asset_resolution", "image_or_video"),
}
_RENDERER_NATIVE = {AssetType.MOTION_GRAPHIC, AssetType.TEXT_GRAPHIC}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "PM9: inventario, assets gratuitos, preparación, render autorizado y F7."
        ),
    )
    parser.add_argument(
        "command",
        choices=(
            "inventory",
            "build-assets",
            "fulfill-assets",
            "verify-assets",
            "prepare",
            "render",
            "accept",
        ),
    )
    parser.add_argument(
        "--project",
        type=Path,
        default=Path("04_PROYECTOS") / "PROYECTO_PM9_PLANCHA_0001",
        help="Ruta del proyecto editorial PM9.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        help=(
            "Configuración PM9 confinada al proyecto; por defecto usa "
            "production_acceptance_config.json."
        ),
    )
    parser.add_argument(
        "--catalog",
        type=Path,
        help="Catálogo aprobado; por defecto se usa el indicado por el proyecto.",
    )
    parser.add_argument(
        "--assets-root",
        type=Path,
        help="Raíz de archivos del catálogo; por defecto se usa la del proyecto.",
    )
    parser.add_argument(
        "--delivery-base",
        help=(
            "Base HTTPS pública estable para los assets; por defecto se deriva "
            "de origin, rama actual y ruta del proyecto."
        ),
    )
    parser.add_argument(
        "--model-dir",
        type=Path,
        help="Caché local del modelo Piper; por defecto vive bajo 05_OUTPUTS.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Regenera assets existentes que ya coincidan con el manifiesto.",
    )
    parser.add_argument(
        "--provider",
        choices=_PROVIDERS,
        default="creatomate",
        help="Proveedor de render; Creatomate permanece como valor compatible.",
    )
    parser.add_argument(
        "--max-credits",
        type=int,
        default=0,
        help="Límite explícito para el comando render.",
    )
    parser.add_argument(
        "--max-visual-assets",
        type=int,
        default=0,
        help="Límite explícito de descargas visuales para fulfill-assets.",
    )
    parser.add_argument(
        "--action",
        choices=("approve", "request_changes", "cancel"),
        help="Decisión humana F7 para accept.",
    )
    parser.add_argument("--actor", help="Identidad auditable del revisor humano.")
    parser.add_argument("--comments", help="Evaluación humana del MP4.")
    parser.add_argument(
        "--redo-target",
        help="Stage al que regresar cuando action=request_changes.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    project = args.project.expanduser().resolve(strict=False)
    try:
        workspace = _workspace_for(project)
        config = _load_project_config(project, args.config)
        if args.command == "inventory":
            return _inventory_command(project, workspace, config)
        if args.command == "build-assets":
            return _build_assets_command(project, workspace, config, args)
        if args.command == "fulfill-assets":
            return _fulfill_assets_command(project, workspace, config, args)
        if args.command == "verify-assets":
            return _verify_assets_command(project, workspace, config, args)

        acceptance = _acceptance_for(
            project,
            workspace,
            config,
            catalog_path=args.catalog,
            assets_root=args.assets_root,
        )
        prepared = acceptance.prepare(
            project,
            asset_types_by_sequence=config["asset_types_by_sequence"],
            existing_asset_ids_by_sequence=config[
                "existing_asset_ids_by_sequence"
            ],
            stock_queries_by_sequence=config["stock_queries_by_sequence"],
            on_screen_text_mode=config["on_screen_text_mode"],
            adapter_factory=_adapter_factory(args.provider, config=config),
            payload_relative_path=_payload_relative_path(args.provider),
            canonical_subtitles=(
                args.provider == "json2video"
                and config["json2video_subtitle_mode"] == "canonical_srt"
            ),
        )
        if args.command == "prepare":
            estimated = _estimated_credits(prepared.plan, args.provider)
            prepared_output = {
                "success": prepared.evidence.ready_for_real_render,
                "command": "prepare",
                "provider": args.provider,
                "evidence": prepared.evidence.model_dump(mode="json"),
                "estimated_render_credits": estimated,
                "network_called": False,
                "publication_performed": False,
            }
            if args.provider == "creatomate":
                prepared_output["estimated_creatomate_credits"] = estimated
            _print_json(
                prepared_output
            )
            return 0 if prepared.evidence.ready_for_real_render else 2
        if args.command == "render":
            return _render_command(
                prepared,
                acceptance,
                max_credits=args.max_credits,
                provider=args.provider,
                config=config,
            )
        return _accept_command(prepared, acceptance, args, provider=args.provider)
    except (
        ProductionAcceptanceBlockedError,
        ProductionAcceptanceError,
        SourceAssetBuildError,
        VisualAssetFulfillmentError,
    ) as error:
        _print_json({"success": False, "blocked": True, "error": str(error)})
        return 2
    except CreatomateApiError as error:
        _print_json(
            {
                "success": False,
                "category": error.category.value,
                "operation": error.operation,
                "retryable": error.retryable,
                "ambiguous_submission": error.ambiguous_submission,
                "status_code": error.status_code,
                "error": str(error),
            }
        )
        return 1
    except JSON2VideoApiError as error:
        _print_json(
            {
                "success": False,
                "category": error.category,
                "operation": error.operation,
                "retryable": error.retryable,
                "ambiguous_submission": error.ambiguous_submission,
                "status_code": error.status_code,
                "error": str(error),
            }
        )
        return 1
    except (OSError, UnicodeError, ValueError, TypeError, json.JSONDecodeError) as error:
        _print_json(
            {
                "success": False,
                "category": "configuration_or_validation",
                "error": f"{type(error).__name__}: {error}",
            }
        )
        return 1


def _workspace_for(project: Path) -> WorkspaceResolver:
    projects_root = _find_parent_named(project, "04_PROYECTOS")
    repository_root = projects_root.parent
    outputs_root = repository_root / "05_OUTPUTS"
    outputs_root.mkdir(parents=True, exist_ok=True)
    return WorkspaceResolver(
        projects_root=projects_root,
        outputs_root=outputs_root,
    )


def _find_parent_named(path: Path, name: str) -> Path:
    for candidate in (path, *path.parents):
        if candidate.name == name:
            return candidate
    raise ValueError(f"La ruta del proyecto debe estar dentro de {name}.")


def _load_project_config(
    project: Path,
    override: Path | None = None,
) -> dict[str, Any]:
    path = (
        project / PROJECT_CONFIG_FILENAME
        if override is None
        else (
            override
            if override.is_absolute()
            else project / override
        )
    ).expanduser().resolve(strict=False)
    try:
        path.relative_to(project)
    except ValueError as error:
        raise ValueError("--config debe permanecer dentro del proyecto.") from error
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise ValueError(f"{PROJECT_CONFIG_FILENAME} requiere una raíz JSON object.")
    allowed = {
        "schema_name",
        "schema_version",
        "asset_types_by_sequence",
        "existing_asset_ids_by_sequence",
        "stock_queries_by_sequence",
        "catalog_relative_path",
        "assets_root_relative_path",
        "seed_catalog_relative_path",
        "fulfillment_report_relative_path",
        "on_screen_text_mode",
        "json2video_music_volume",
        "json2video_sound_effect_gain",
        "json2video_subtitle_mode",
        "json2video_ambient_diagram_background",
        "frame_rate_policy",
    }
    unknown = sorted(set(raw) - allowed)
    if unknown:
        raise ValueError("Campos no soportados en configuración: " + ", ".join(unknown))
    if raw.get("schema_name") != "cips.production_acceptance.project_config":
        raise ValueError("schema_name PM9 inválido.")
    if raw.get("schema_version") != "1.0":
        raise ValueError("schema_version PM9 no soportado.")
    asset_types = _sequence_mapping(raw.get("asset_types_by_sequence"), AssetType)
    existing_ids = _sequence_mapping(
        raw.get("existing_asset_ids_by_sequence", {}), str
    )
    stock_queries = _sequence_mapping(
        raw.get("stock_queries_by_sequence", {}), str
    )
    catalog_relative = _safe_relative(raw.get("catalog_relative_path"), "catalog")
    assets_relative = _safe_relative(
        raw.get("assets_root_relative_path"), "assets_root"
    )
    seed_catalog_raw = raw.get("seed_catalog_relative_path")
    seed_catalog_relative = (
        None
        if seed_catalog_raw is None
        else _safe_relative(seed_catalog_raw, "seed_catalog")
    )
    fulfillment_report_relative = _safe_relative(
        raw.get(
            "fulfillment_report_relative_path",
            "acceptance/visual_asset_fulfillment.json",
        ),
        "fulfillment_report",
    )
    on_screen_text_mode = str(raw.get("on_screen_text_mode", "auto")).strip().casefold()
    if on_screen_text_mode not in {"auto", "captions_only"}:
        raise ValueError(
            "on_screen_text_mode debe ser auto o captions_only."
        )
    json2video_music_volume = _bounded_config_float(
        raw.get("json2video_music_volume", 0.2),
        label="json2video_music_volume",
        minimum=0.0,
        maximum=1.0,
    )
    json2video_sound_effect_gain = _bounded_config_float(
        raw.get("json2video_sound_effect_gain", 1.0),
        label="json2video_sound_effect_gain",
        minimum=0.0,
        maximum=4.0,
    )
    json2video_subtitle_mode = str(
        raw.get("json2video_subtitle_mode", "inline_srt")
    ).strip().casefold()
    if json2video_subtitle_mode not in {
        "inline_srt",
        "canonical_srt",
        "automatic_whisper",
    }:
        raise ValueError(
            "json2video_subtitle_mode debe ser inline_srt, canonical_srt o "
            "automatic_whisper."
        )
    json2video_ambient_diagram_background = raw.get(
        "json2video_ambient_diagram_background", False
    )
    if not isinstance(json2video_ambient_diagram_background, bool):
        raise ValueError(
            "json2video_ambient_diagram_background debe ser booleano."
        )
    frame_rate_policy = FrameRatePolicy.model_validate(
        raw.get("frame_rate_policy", {})
    )
    return {
        "asset_types_by_sequence": asset_types,
        "existing_asset_ids_by_sequence": existing_ids,
        "stock_queries_by_sequence": stock_queries,
        "catalog_relative_path": catalog_relative,
        "assets_root_relative_path": assets_relative,
        "seed_catalog_relative_path": seed_catalog_relative,
        "fulfillment_report_relative_path": fulfillment_report_relative,
        "on_screen_text_mode": on_screen_text_mode,
        "json2video_music_volume": json2video_music_volume,
        "json2video_sound_effect_gain": json2video_sound_effect_gain,
        "json2video_subtitle_mode": json2video_subtitle_mode,
        "json2video_ambient_diagram_background": (
            json2video_ambient_diagram_background
        ),
        "frame_rate_policy": frame_rate_policy,
    }


def _sequence_mapping(value: Any, converter: Any) -> dict[int, Any]:
    if not isinstance(value, Mapping):
        raise ValueError("Los overrides por escena deben ser un JSON object.")
    result: dict[int, Any] = {}
    for raw_sequence, raw_value in value.items():
        try:
            sequence = int(raw_sequence)
        except (TypeError, ValueError) as error:
            raise ValueError("Las secuencias de escena deben ser enteros.") from error
        if sequence < 1 or isinstance(raw_sequence, bool):
            raise ValueError("Las secuencias de escena deben ser positivas.")
        converted = converter(raw_value)
        if converter is str:
            converted = converted.strip()
            if not converted:
                raise ValueError("existing_asset_id no puede estar vacío.")
        result[sequence] = converted
    return result


def _safe_relative(value: Any, label: str) -> Path:
    path = Path(str(value or "").replace("\\", "/"))
    if not path.parts or path.is_absolute() or ".." in path.parts:
        raise ValueError(f"{label} debe ser una ruta relativa confinada.")
    return path


def _bounded_config_float(
    value: Any,
    *,
    label: str,
    minimum: float,
    maximum: float,
) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} debe ser numérico.")
    normalized = float(value)
    if not math.isfinite(normalized) or not minimum <= normalized <= maximum:
        raise ValueError(
            f"{label} debe estar entre {minimum:.1f} y {maximum:.1f}."
        )
    return normalized


def _acceptance_for(
    project: Path,
    workspace: WorkspaceResolver,
    config: Mapping[str, Any],
    *,
    catalog_path: Path | None,
    assets_root: Path | None,
) -> FullProductionAcceptance:
    catalog_location = _resolve_override(
        project,
        catalog_path,
        config["catalog_relative_path"],
    )
    assets_location = _resolve_override(
        project,
        assets_root,
        config["assets_root_relative_path"],
    )
    catalog = ApprovedAssetCatalog.load(catalog_location)
    provider = ApprovedAssetCatalogProvider(catalog, assets_root=assets_location)
    resolver = ManifestAssetResolver(
        capability_resolver=CapabilityResolver(MediaProviderRegistry([provider])),
        workspace_resolver=workspace,
        cache_namespace=f"catalog-{_catalog_content_sha256(catalog)[:16]}",
    )
    return FullProductionAcceptance(
        workspace_resolver=workspace,
        asset_resolver=resolver,
        frame_rate_policy=config["frame_rate_policy"],
    )


def _resolve_override(project: Path, override: Path | None, default: Path) -> Path:
    if override is not None:
        return override.expanduser().resolve(strict=False)
    return (project / default).resolve(strict=False)


def _catalog_content_sha256(catalog: ApprovedAssetCatalog) -> str:
    canonical = json.dumps(
        catalog.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _refresh_fulfilled_catalog_from_seed(
    project: Path,
    workspace: WorkspaceResolver,
    config: Mapping[str, Any],
    manifest: ProductionManifest,
    seed_catalog: ApprovedAssetCatalog,
    *,
    assets_root: Path,
) -> Path | None:
    """Replace stale nonvisual entries while preserving approved visuals."""

    configured_assets_root = (
        project / config["assets_root_relative_path"]
    ).resolve(strict=False)
    if assets_root.resolve(strict=False) != configured_assets_root:
        return None
    fulfilled_path = (
        project / config["catalog_relative_path"]
    ).resolve(strict=False)
    seed_path = (assets_root / "asset_catalog.json").resolve(strict=False)
    if fulfilled_path == seed_path or not fulfilled_path.is_file():
        return None
    if any(entry.role == "scene_visual" for entry in seed_catalog.entries):
        return None

    fulfilled = ApprovedAssetCatalog.load(fulfilled_path)
    visuals = tuple(
        entry for entry in fulfilled.entries if entry.role == "scene_visual"
    )
    expected_scene_ids = {scene.scene_id for scene in manifest.scenes}
    visual_scene_ids = {entry.scene_id for entry in visuals}
    if (
        len(visuals) != len(expected_scene_ids)
        or visual_scene_ids != expected_scene_ids
    ):
        return None

    refreshed = ApprovedAssetCatalog(entries=(*visuals, *seed_catalog.entries))
    digest = _catalog_content_sha256(refreshed)
    relative_path = fulfilled_path.relative_to(project)
    write = MetadataStore(workspace).persist_metadata(
        workspace_root=project,
        relative_path=relative_path,
        content=refreshed.model_dump(mode="json"),
        artifact_type="fulfilled_asset_catalog",
        artifact_id=f"refreshed-fulfilled-catalog-{digest[:24]}",
        metadata={
            "manifest_id": manifest.manifest_id,
            "entry_count": len(refreshed.entries),
            "seed_catalog_sha256": _catalog_content_sha256(seed_catalog),
        },
        collision_policy=CollisionPolicy.REPLACE,
    )
    return Path(write.artifact.path).resolve(strict=False)


def _inventory_command(
    project: Path,
    workspace: WorkspaceResolver,
    config: Mapping[str, Any],
) -> int:
    compiled = ProductionManifestCompiler(workspace_resolver=workspace).compile(project)
    planned = _planned_manifest(compiled, config)
    payload = _asset_inventory(planned)
    inventory_digest = hashlib.sha256(
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()[:16]
    write = MetadataStore(workspace).persist_metadata(
        workspace_root=project,
        relative_path=INVENTORY_RELATIVE_PATH,
        content=payload,
        artifact_type="production_asset_requirements",
        artifact_id=f"pm9-inventory-{planned.manifest_id}-{inventory_digest}",
        metadata={
            "manifest_id": planned.manifest_id,
            "required_catalog_entries": payload["required_catalog_entries"],
        },
        collision_policy=CollisionPolicy.REPLACE,
    )
    _print_json(
        {
            "success": True,
            "command": "inventory",
            "artifact_path": str(Path(write.artifact.path).resolve()),
            **payload,
            "network_called": False,
            "publication_performed": False,
        }
    )
    return 0


def _build_assets_command(
    project: Path,
    workspace: WorkspaceResolver,
    config: Mapping[str, Any],
    args: argparse.Namespace,
) -> int:
    compiled = ProductionManifestCompiler(workspace_resolver=workspace).compile(project)
    planned = _planned_manifest(compiled, config)
    assets_root = _resolve_override(
        project,
        args.assets_root,
        config["assets_root_relative_path"],
    )
    delivery_base = (
        str(args.delivery_base).strip()
        if args.delivery_base
        else derive_github_raw_base(project, assets_root)
    )
    model_dir = (
        args.model_dir.expanduser().resolve(strict=False)
        if args.model_dir is not None
        else workspace.outputs_root / "pm9_models" / "piper"
    )
    builder = PM9SourceAssetBuilder(
        planned,
        project_path=project,
        assets_root=assets_root,
        model_dir=model_dir,
        delivery_base_uri=delivery_base,
    )
    result = builder.build(force=args.force)
    refreshed_catalog_path = _refresh_fulfilled_catalog_from_seed(
        project,
        workspace,
        config,
        planned,
        result.catalog,
        assets_root=result.assets_root,
    )
    _print_json(
        {
            "success": True,
            "command": "build-assets",
            "project_id": planned.project.project_id,
            "manifest_id": planned.manifest_id,
            "catalog_path": str(result.catalog_path.resolve()),
            "report_path": str(result.report_path.resolve()),
            "assets_root": str(result.assets_root.resolve()),
            "delivery_base_uri": result.delivery_base_uri,
            "catalog_entries": len(result.catalog.entries),
            "generated_count": result.generated_count,
            "reused_existing": result.reused_existing,
            "fulfilled_catalog_refreshed": refreshed_catalog_path is not None,
            "fulfilled_catalog_path": (
                str(refreshed_catalog_path)
                if refreshed_catalog_path is not None
                else None
            ),
            "actual_cost_usd": 0.0,
            "network_called": result.network_called,
            "paid_provider_called": False,
            "render_performed": False,
            "publication_performed": False,
            "next_gate": "commit_and_push_source_assets_before_verify-assets",
        }
    )
    return 0


def _fulfill_assets_command(
    project: Path,
    workspace: WorkspaceResolver,
    config: Mapping[str, Any],
    args: argparse.Namespace,
) -> int:
    compiled = ProductionManifestCompiler(workspace_resolver=workspace).compile(project)
    planned = _planned_manifest(compiled, config)
    requested_downloads = sum(
        scene.asset_request.asset_type is AssetType.STOCK_IMAGE
        for scene in planned.scenes
    )
    if requested_downloads < 1:
        raise ProductionAcceptanceBlockedError(
            "fulfill-assets requiere al menos una escena stock_image."
        )
    if os.environ.get(ASSET_CONFIRMATION_ENV) != ASSET_CONFIRMATION_VALUE:
        raise ProductionAcceptanceBlockedError(
            f"Falta {ASSET_CONFIRMATION_ENV}={ASSET_CONFIRMATION_VALUE}."
        )
    if args.max_visual_assets < requested_downloads:
        raise ProductionAcceptanceBlockedError(
            "--max-visual-assets debe cubrir el máximo autorizado "
            f"({requested_downloads} requeridos)."
        )

    seed_relative = config.get("seed_catalog_relative_path")
    if seed_relative is None:
        raise ProductionAcceptanceBlockedError(
            "fulfill-assets requiere seed_catalog_relative_path."
        )
    seed_path = (project / seed_relative).resolve(strict=False)
    seed_catalog = ApprovedAssetCatalog.load(seed_path)
    assets_root = (project / config["assets_root_relative_path"]).resolve(
        strict=False
    )
    delivery_base = (
        str(args.delivery_base).strip()
        if args.delivery_base
        else derive_github_raw_base(project, assets_root)
    )
    catalog_provider = ApprovedAssetCatalogProvider(
        seed_catalog,
        assets_root=assets_root,
    )
    wikimedia_provider = WikimediaCommonsProvider()
    resolver = ManifestAssetResolver(
        capability_resolver=CapabilityResolver(
            MediaProviderRegistry([catalog_provider, wikimedia_provider])
        ),
        workspace_resolver=workspace,
        preferred_providers={
            "stock_image_search": wikimedia_provider.provider_name,
        },
        cache_namespace=f"catalog-{_catalog_content_sha256(seed_catalog)[:16]}",
    )
    service = VisualAssetFulfillmentService(
        asset_resolver=resolver,
        workspace_resolver=workspace,
    )
    result = service.fulfill(
        planned,
        workspace_root=project,
        assets_root=assets_root,
        catalog_relative_path=config["catalog_relative_path"],
        report_relative_path=config["fulfillment_report_relative_path"],
        delivery_base_uri=delivery_base,
    )
    _print_json(
        {
            "success": True,
            "command": "fulfill-assets",
            "project_id": planned.project.project_id,
            "manifest_id": planned.manifest_id,
            "resolution_id": result.resolution.bundle.resolution_id,
            "catalog_path": str(result.catalog_path.resolve()),
            "report_path": str(result.report_path.resolve()),
            "catalog_entries": len(result.catalog.entries),
            "delivery_base_uri": delivery_base,
            "requested_visual_assets": requested_downloads,
            "wikimedia_calls": len(wikimedia_provider.calls),
            "resolved_count": result.resolution.resolved_count,
            "reused_resolution_count": result.resolution.reused_count,
            "reused_existing_bundle": result.resolution.reused_existing,
            "staged_count": result.staged_count,
            "reused_staged_count": result.reused_staged_count,
            "actual_cost_usd": result.resolution.bundle.total_actual_cost_usd,
            "unknown_cost_count": result.resolution.bundle.unknown_cost_count,
            "network_called": bool(wikimedia_provider.calls),
            "paid_provider_called": False,
            "render_performed": False,
            "publication_performed": False,
            "next_gate": "commit_and_push_fulfilled_assets_before_verify-assets",
        }
    )
    return 0


def _verify_assets_command(
    project: Path,
    workspace: WorkspaceResolver,
    config: Mapping[str, Any],
    args: argparse.Namespace,
) -> int:
    catalog_path = _resolve_override(
        project,
        args.catalog,
        config["catalog_relative_path"],
    )
    assets_root = _resolve_override(
        project,
        args.assets_root,
        config["assets_root_relative_path"],
    )
    catalog = ApprovedAssetCatalog.load(catalog_path)
    verification = verify_catalog_delivery(catalog, assets_root=assets_root)
    content = {
        "schema_name": "cips.production_acceptance.asset_delivery_verification",
        "schema_version": "1.0",
        "project_id": project.name,
        "verified_count": verification.verified_count,
        "total_bytes": verification.total_bytes,
        "all_passed": True,
        "checks": list(verification.checks),
        "actual_cost_usd": 0.0,
        "paid_provider_called": False,
        "render_performed": False,
        "publication_performed": False,
    }
    write = MetadataStore(workspace).persist_metadata(
        workspace_root=project,
        relative_path=VERIFY_REPORT_RELATIVE_PATH,
        content=content,
        artifact_type="production_asset_delivery_verification",
        artifact_id=f"pm9-delivery-{_verification_digest(verification.checks)}",
        metadata={
            "verified_count": verification.verified_count,
            "all_passed": True,
        },
        collision_policy=CollisionPolicy.REPLACE,
    )
    _print_json(
        {
            "success": True,
            "command": "verify-assets",
            "artifact_path": str(Path(write.artifact.path).resolve()),
            **content,
            "network_called": True,
        }
    )
    return 0


def _verification_digest(checks: Sequence[Mapping[str, Any]]) -> str:
    canonical = json.dumps(
        list(checks),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:24]


def _planned_manifest(
    manifest: ProductionManifest,
    config: Mapping[str, Any],
) -> ProductionManifest:
    by_sequence = {scene.sequence: scene.scene_id for scene in manifest.scenes}
    asset_types = {
        by_sequence[sequence]: asset_type
        for sequence, asset_type in config["asset_types_by_sequence"].items()
    }
    existing = {
        by_sequence[sequence]: asset_id
        for sequence, asset_id in config[
            "existing_asset_ids_by_sequence"
        ].items()
    }
    return CreativeDirectionPlanner().plan(
        manifest,
        asset_types=asset_types,
        existing_asset_ids=existing,
        stock_queries={
            by_sequence[sequence]: query
            for sequence, query in config["stock_queries_by_sequence"].items()
        },
        on_screen_text_mode=config["on_screen_text_mode"],
    )


def _asset_inventory(manifest: ProductionManifest) -> dict[str, Any]:
    requirements: list[dict[str, Any]] = []
    for scene in manifest.scenes:
        asset = scene.asset_request
        if asset.asset_type in _VISUAL_CAPABILITIES:
            capability, family = _VISUAL_CAPABILITIES[asset.asset_type]
            requirements.append(
                {
                    "role": "scene_visual",
                    "scene_id": scene.scene_id,
                    "sequence": scene.sequence,
                    "capability": capability,
                    "media_family": family,
                    "existing_asset_id": asset.existing_asset_id,
                    "requires_catalog_entry": True,
                    "brief": asset.creative_brief,
                }
            )
        elif asset.asset_type in _RENDERER_NATIVE:
            requirements.append(
                {
                    "role": "scene_visual",
                    "scene_id": scene.scene_id,
                    "sequence": scene.sequence,
                    "capability": "renderer_native",
                    "media_family": "metadata",
                    "existing_asset_id": None,
                    "requires_catalog_entry": False,
                    "brief": asset.creative_brief,
                }
            )
        else:
            raise ValueError(
                f"PM9 no inventaría asset_type={asset.asset_type.value}."
            )
        if scene.narration_text:
            requirements.append(
                {
                    "role": "scene_narration",
                    "scene_id": scene.scene_id,
                    "sequence": scene.sequence,
                    "capability": "voice_synthesis",
                    "media_family": "audio",
                    "requires_catalog_entry": True,
                    "brief": scene.narration_text,
                }
            )
    if manifest.audio_design.music is not None:
        requirements.append(
            {
                "role": "music",
                "capability": "music_generation",
                "media_family": "audio",
                "requires_catalog_entry": True,
                "brief": manifest.audio_design.music.creative_brief,
            }
        )
    for effect in manifest.audio_design.sound_effects:
        requirements.append(
            {
                "role": "sound_effect",
                "cue_id": effect.cue_id,
                "capability": "sound_effect_generation",
                "media_family": "audio",
                "requires_catalog_entry": True,
                "brief": effect.description,
            }
        )
    required = sum(item["requires_catalog_entry"] for item in requirements)
    return {
        "schema_name": "cips.production_acceptance.asset_requirements",
        "schema_version": "1.0",
        "manifest_id": manifest.manifest_id,
        "project_id": manifest.project.project_id,
        "style_profile": manifest.style_profile,
        "output": manifest.output.model_dump(mode="json"),
        "required_catalog_entries": required,
        "renderer_native_entries": len(requirements) - required,
        "requirements": requirements,
    }


def _adapter_factory(provider: str, *, config: Mapping[str, Any] | None = None):
    project_config = config or {}
    if provider == "creatomate":
        return lambda bundle, canonical_track=None: CreatomateAdapter(
            resolved_assets=bundle
        )
    if provider == "json2video":
        return lambda bundle, canonical_track=None: JSON2VideoAdapter(
            resolved_assets=bundle,
            music_volume_ceiling=float(
                project_config.get("json2video_music_volume", 0.2)
            ),
            sound_effect_gain=float(
                project_config.get("json2video_sound_effect_gain", 1.0)
            ),
            subtitle_mode=str(
                project_config.get("json2video_subtitle_mode", "inline_srt")
            ),
            canonical_subtitle_track=canonical_track,
            ambient_diagram_background=bool(
                project_config.get(
                    "json2video_ambient_diagram_background", False
                )
            ),
        )
    raise ValueError(f"Proveedor no soportado: {provider}.")


def _payload_relative_path(provider: str) -> Path:
    return (
        RENDER_RESULT_RELATIVE_PATH.with_name("creatomate_payload.json")
        if provider == "creatomate"
        else JSON2VIDEO_PAYLOAD_RELATIVE_PATH
    )


def _result_relative_path(provider: str) -> Path:
    return (
        RENDER_RESULT_RELATIVE_PATH
        if provider == "creatomate"
        else JSON2VIDEO_RENDER_RESULT_RELATIVE_PATH
    )


def _estimated_credits(plan: Any, provider: str) -> int:
    if provider == "creatomate":
        return estimate_render_credits(plan)
    if provider == "json2video":
        return estimate_json2video_credits(plan.output.duration_seconds)
    raise ValueError(f"Proveedor no soportado: {provider}.")


def _render_command(
    prepared: Any,
    acceptance: FullProductionAcceptance,
    *,
    max_credits: int,
    provider: str = "creatomate",
    config: Mapping[str, Any] | None = None,
) -> int:
    estimated = _estimated_credits(prepared.plan, provider)
    if os.environ.get(CONFIRMATION_ENV, "").strip() != CONFIRMATION_VALUE:
        raise ProductionAcceptanceBlockedError(
            f"Define {CONFIRMATION_ENV}={CONFIRMATION_VALUE} sólo tras autorizar "
            f"el render real de {provider} estimado en {estimated} créditos."
        )
    if isinstance(max_credits, bool) or max_credits < estimated:
        raise ProductionAcceptanceBlockedError(
            f"--max-credits debe autorizar al menos {estimated}; recibido {max_credits}."
        )
    if not prepared.evidence.ready_for_real_render:
        raise ProductionAcceptanceBlockedError(
            f"La preparación contiene blockers y no puede enviarse a {provider}."
        )
    if provider == "creatomate":
        api_config = CreatomateApiConfig.from_environment()
        service = CreatomateRenderService(
            client=CreatomateApiClient(api_config),
            workspace_resolver=acceptance.workspace_resolver,
            adapter=CreatomateAdapter(resolved_assets=prepared.asset_run.bundle),
            telemetry_recorder=acceptance.telemetry_engine,
        )
        result = service.execute(
            prepared.manifest,
            workspace_root=prepared.project_path,
            context=CreatomateExecutionContext(
                workflow_id=prepared.evidence.workflow_id,
                run_id=prepared.evidence.run_id,
                task_id="creatomate-render",
                correlation_id=prepared.evidence.run_id,
            ),
        )
        credential_source = CREATOMATE_API_KEY_ENV
    elif provider == "json2video":
        api_config = JSON2VideoApiConfig.from_environment()
        render_adapter = _adapter_factory(
            "json2video", config=config
        )(
            prepared.asset_run.bundle,
            (
                None
                if prepared.canonical_subtitles is None
                else prepared.canonical_subtitles.track
            ),
        )
        if not isinstance(render_adapter, JSON2VideoAdapter):
            raise TypeError("La fábrica JSON2Video devolvió un adapter inválido.")
        service = JSON2VideoRenderService(
            client=JSON2VideoApiClient(api_config),
            workspace_resolver=acceptance.workspace_resolver,
            adapter=render_adapter,
        )
        result = service.execute(
            prepared.manifest,
            workspace_root=prepared.project_path,
        )
        credential_source = JSON2VIDEO_API_KEY_ENV
    else:
        raise ValueError(f"Proveedor no soportado: {provider}.")
    write = MetadataStore(acceptance.workspace_resolver).persist_metadata(
        workspace_root=prepared.project_path,
        relative_path=_result_relative_path(provider),
        content=result.model_dump(mode="json"),
        artifact_type="render_result",
        artifact_id=f"pm9-render-result-{prepared.submission.submission_id}",
        metadata={
            "submission_id": prepared.submission.submission_id,
            "estimated_credits": estimated,
            "provider": provider,
        },
        collision_policy=CollisionPolicy.REPLACE,
    )
    render_path = _render_path(
        prepared.project_path, prepared.submission.submission_id, provider
    )
    _print_json(
        {
            "success": result.status is RenderStatus.SUCCEEDED,
            "command": "render",
            "provider": provider,
            "status": result.status.value,
            "result_path": str(Path(write.artifact.path).resolve()),
            "render_path": str(render_path.resolve()),
            "estimated_credits": estimated,
            "credits_used": result.metadata.get("credits_used"),
            "credential_source": credential_source,
            "publication_performed": False,
        }
    )
    return 0 if result.status is RenderStatus.SUCCEEDED else 1


def _accept_command(
    prepared: Any,
    acceptance: FullProductionAcceptance,
    args: argparse.Namespace,
    *,
    provider: str,
) -> int:
    if not args.action or not args.actor or not args.comments:
        raise ProductionAcceptanceBlockedError(
            "accept requiere --action, --actor y --comments como decisión humana F7."
        )
    action = ReviewAction(args.action)
    if action is ReviewAction.REQUEST_CHANGES and not args.redo_target:
        raise ProductionAcceptanceBlockedError(
            "request_changes requiere --redo-target."
        )
    if action is not ReviewAction.REQUEST_CHANGES and args.redo_target:
        raise ProductionAcceptanceBlockedError(
            "--redo-target sólo corresponde a request_changes."
        )
    result_path = prepared.project_path / _result_relative_path(provider)
    result = RenderResult.model_validate_json(result_path.read_bytes())
    render_path = _render_path(
        prepared.project_path,
        prepared.submission.submission_id,
        provider,
    )
    timestamp = datetime.now(timezone.utc).isoformat()
    decision_basis = "\x1f".join(
        (prepared.evidence.run_id, args.action, args.actor, timestamp)
    )
    decision = ReviewDecision(
        decision_id="human-pm9-" + hashlib.sha256(
            decision_basis.encode("utf-8")
        ).hexdigest()[:24],
        action=action,
        actor=args.actor,
        decided_at=timestamp,
        comments=args.comments,
        redo_target=args.redo_target,
        metadata={
            "quality_dimension": "human_publishability",
            "source": "run_pm9_full_production_acceptance",
        },
    )
    finalized = acceptance.finalize(
        prepared,
        render_result=result,
        render_path=render_path,
        review_decision=decision,
    )
    _print_json(
        {
            "success": True,
            "command": "accept",
            "export_path": str(finalized.export_path.resolve()),
            "evidence_path": str(finalized.evidence_path.resolve()),
            "qa_approved": finalized.evidence.qa_approved,
            "human_approved": finalized.evidence.human_approved,
            "review_state": finalized.evidence.review_state,
            "reused_existing": finalized.reused_existing,
            "publication_performed": finalized.evidence.publication_performed,
        }
    )
    return 0


def _render_path(
    project: Path,
    submission_id: str,
    provider: str = "creatomate",
) -> Path:
    if provider not in _PROVIDERS:
        raise ValueError(f"Proveedor no soportado: {provider}.")
    return project / "video" / provider / f"{submission_id}.mp4"


def _print_json(payload: Mapping[str, Any]) -> None:
    print(
        json.dumps(
            dict(payload),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
    )


if __name__ == "__main__":
    sys.exit(main())
