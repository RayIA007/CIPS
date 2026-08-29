"""PM9.1 bridge from PM8/F3 resolution receipts to an approved render catalog."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlsplit

from artifact_store import CollisionPolicy
from asset_resolution import (
    AssetResolutionRun,
    AssetRole,
    ManifestAssetResolver,
    ResolutionStatus,
    ResolvedAsset,
    WIKIMEDIA_PROVIDER_NAME,
)
from metadata_store import MetadataStore
from production_manifest import ProductionManifest
from workspace_resolver import WorkspaceResolver

from .catalog import ApprovedAssetCatalog, CatalogEntry


FULFILLMENT_REPORT_RELATIVE_PATH = (
    Path("acceptance") / "visual_asset_fulfillment.json"
)


class VisualAssetFulfillmentError(RuntimeError):
    """A resolved asset cannot become a safe, traceable catalog entry."""


@dataclass(frozen=True, slots=True)
class VisualAssetFulfillmentResult:
    resolution: AssetResolutionRun
    catalog: ApprovedAssetCatalog
    catalog_path: Path
    catalog_sidecar_path: Path
    report_path: Path
    report_sidecar_path: Path
    staged_count: int
    reused_staged_count: int


class VisualAssetFulfillmentService:
    """Resolve a manifest through PM8/F3 and refresh its approved catalog.

    F3 remains the source of truth.  Catalog files are deterministic delivery
    copies that preserve the F3 hash and source provenance.  Wikimedia assets
    can be mirrored under a caller-provided public base so render providers do
    not depend on Commons hotlinking behavior.
    """

    def __init__(
        self,
        *,
        asset_resolver: ManifestAssetResolver,
        workspace_resolver: WorkspaceResolver,
    ) -> None:
        if not isinstance(asset_resolver, ManifestAssetResolver):
            raise TypeError("asset_resolver debe ser ManifestAssetResolver.")
        if not isinstance(workspace_resolver, WorkspaceResolver):
            raise TypeError("workspace_resolver debe ser WorkspaceResolver.")
        if asset_resolver.workspace_resolver is not workspace_resolver:
            raise ValueError("asset_resolver y workspace_resolver deben coincidir.")
        self.asset_resolver = asset_resolver
        self.workspace_resolver = workspace_resolver
        self.metadata_store = MetadataStore(workspace_resolver)

    def fulfill(
        self,
        manifest: ProductionManifest,
        *,
        workspace_root: str | Path,
        assets_root: str | Path,
        catalog_relative_path: str | Path,
        report_relative_path: str | Path = FULFILLMENT_REPORT_RELATIVE_PATH,
        delivery_base_uri: str | None = None,
    ) -> VisualAssetFulfillmentResult:
        if not isinstance(manifest, ProductionManifest):
            raise TypeError("manifest debe ser ProductionManifest.")
        workspace = Path(workspace_root).expanduser().resolve(strict=False)
        assets = Path(assets_root).expanduser().resolve(strict=False)
        self.workspace_resolver.confine_path(workspace, "asset_resolution")
        try:
            assets.relative_to(workspace)
        except ValueError as error:
            raise ValueError("assets_root debe permanecer dentro del proyecto.") from error
        catalog_path = self.workspace_resolver.confine_path(
            workspace,
            catalog_relative_path,
        )
        report_path = self.workspace_resolver.confine_path(
            workspace,
            report_relative_path,
        )
        try:
            catalog_path.relative_to(assets)
        except ValueError as error:
            raise ValueError(
                "El catálogo fulfillment debe estar dentro de assets_root."
            ) from error
        delivery_base = _public_base_uri(delivery_base_uri)

        resolution = self.asset_resolver.resolve(
            manifest,
            workspace_root=workspace,
        )
        entries: list[CatalogEntry] = []
        staged_count = 0
        reused_staged_count = 0
        for record in resolution.bundle.assets:
            if record.status is not ResolutionStatus.PERSISTED:
                continue
            entry, reused = self._stage_record(
                manifest,
                record,
                workspace=workspace,
                assets_root=assets,
                delivery_base_uri=delivery_base,
            )
            entries.append(entry)
            staged_count += int(not reused)
            reused_staged_count += int(reused)
        if not entries:
            raise VisualAssetFulfillmentError(
                "El manifest no produjo assets físicos para el catálogo."
            )

        resolution = self._persist_delivery_overrides(
            manifest,
            resolution,
            entries=entries,
            workspace=workspace,
        )

        catalog = ApprovedAssetCatalog(entries=tuple(entries))
        catalog_payload = catalog.model_dump(mode="json")
        catalog_digest = _mapping_digest(catalog_payload)[:12]
        catalog_relative = catalog_path.relative_to(workspace)
        catalog_write = self.metadata_store.persist_metadata(
            workspace_root=workspace,
            relative_path=catalog_relative,
            content=catalog_payload,
            artifact_type="fulfilled_asset_catalog",
            artifact_id=(
                f"fulfilled-catalog-{resolution.bundle.resolution_id}-"
                f"{catalog_digest}"
            ),
            metadata={
                "manifest_id": manifest.manifest_id,
                "resolution_id": resolution.bundle.resolution_id,
                "entry_count": len(entries),
            },
            collision_policy=CollisionPolicy.REPLACE,
        )

        report = {
            "schema_name": "cips.visual_asset_fulfillment",
            "schema_version": "1.0",
            "manifest_id": manifest.manifest_id,
            "manifest_sha256": resolution.bundle.manifest_sha256,
            "resolution_id": resolution.bundle.resolution_id,
            "resolver_reused_existing": resolution.reused_existing,
            "resolved_count": resolution.resolved_count,
            "reused_resolution_count": resolution.reused_count,
            "catalog_entry_count": len(entries),
            "staged_count": staged_count,
            "reused_staged_count": reused_staged_count,
            "total_estimated_cost_usd": (
                resolution.bundle.total_estimated_cost_usd
            ),
            "total_actual_cost_usd": resolution.bundle.total_actual_cost_usd,
            "actual_cost_usd": resolution.bundle.total_actual_cost_usd,
            "unknown_cost_count": resolution.bundle.unknown_cost_count,
            "delivery_base_uri": delivery_base,
            "mirrored_delivery_count": sum(
                record.provider_name == WIKIMEDIA_PROVIDER_NAME
                for record in resolution.bundle.assets
            ),
            "publication_performed": False,
            "render_performed": False,
            "assets": [
                {
                    "entry_id": entry.entry_id,
                    "role": entry.role,
                    "scene_id": entry.scene_id,
                    "cue_id": entry.cue_id,
                    "provider": record.provider_name,
                    "capability": entry.capability,
                    "relative_path": entry.relative_path,
                    "delivery_uri": entry.delivery_uri,
                    "source_url": entry.source_url,
                    "license_name": entry.license_name,
                    "attribution": entry.attribution,
                    "content_sha256": record.content_sha256,
                    "mime_type": entry.mime_type,
                    "size_bytes": record.size_bytes,
                    "width_px": record.metadata.get("width_px"),
                    "height_px": record.metadata.get("height_px"),
                    "aspect_ratio": record.metadata.get("aspect_ratio"),
                    "prompt_permitted": record.metadata.get("prompt_permitted"),
                    "actual_cost_usd": entry.actual_cost_usd,
                    "selected_from_alternative": (
                        record.selected_from_alternative
                    ),
                }
                for entry, record in zip(entries, self._persisted(resolution))
            ],
        }
        report_relative = report_path.relative_to(workspace)
        report_write = self.metadata_store.persist_metadata(
            workspace_root=workspace,
            relative_path=report_relative,
            content=report,
            artifact_type="visual_asset_fulfillment_report",
            artifact_id=(
                f"fulfillment-report-{resolution.bundle.resolution_id}-"
                f"{_mapping_digest(report)[:12]}"
            ),
            metadata={
                "manifest_id": manifest.manifest_id,
                "resolution_id": resolution.bundle.resolution_id,
                "catalog_entry_count": len(entries),
            },
            collision_policy=CollisionPolicy.REPLACE,
        )
        return VisualAssetFulfillmentResult(
            resolution=resolution,
            catalog=catalog,
            catalog_path=Path(catalog_write.artifact.path),
            catalog_sidecar_path=catalog_write.sidecar_path,
            report_path=Path(report_write.artifact.path),
            report_sidecar_path=report_write.sidecar_path,
            staged_count=staged_count,
            reused_staged_count=reused_staged_count,
        )

    def _stage_record(
        self,
        manifest: ProductionManifest,
        record: ResolvedAsset,
        *,
        workspace: Path,
        assets_root: Path,
        delivery_base_uri: str | None,
    ) -> tuple[CatalogEntry, bool]:
        required = (
            record.provider_name,
            record.capability,
            record.media_family,
            record.artifact_relative_path,
            record.content_sha256,
            record.mime_type,
            record.delivery_uri,
        )
        if any(value is None for value in required):
            raise VisualAssetFulfillmentError(
                f"El record '{record.record_id}' no contiene contrato físico completo."
            )
        if record.cost_status.value == "unknown":
            raise VisualAssetFulfillmentError(
                f"El record '{record.record_id}' conserva costo desconocido."
            )
        source = self.workspace_resolver.confine_path(
            workspace,
            record.artifact_relative_path,
        )
        if not source.is_file():
            raise VisualAssetFulfillmentError(
                f"No existe el artefacto F3 '{record.artifact_relative_path}'."
            )
        if _sha256(source) != record.content_sha256:
            raise VisualAssetFulfillmentError(
                f"El artefacto F3 '{record.record_id}' no coincide con su hash."
            )
        extension = source.suffix.lower()
        relative = (
            Path("fulfilled")
            / record.media_family.value
            / record.role.value
            / f"{record.record_id}{extension}"
        )
        destination = (assets_root / relative).resolve(strict=False)
        try:
            destination.relative_to(assets_root)
        except ValueError as error:
            raise VisualAssetFulfillmentError(
                "La ruta de staging escapó de assets_root."
            ) from error
        reused = _copy_verified(
            source,
            destination,
            expected_sha256=record.content_sha256,
        )

        metadata = record.metadata
        source_url = _text(metadata.get("source_url")) or record.delivery_uri
        license_name = _text(metadata.get("license_name")) or _text(
            metadata.get("license")
        )
        if not source_url or not license_name:
            raise VisualAssetFulfillmentError(
                f"El record '{record.record_id}' no acredita fuente y licencia."
            )
        attribution = _text(metadata.get("attribution"))
        existing_asset_id = _existing_asset_id(manifest, record)
        known_cost = record.actual_cost_usd
        if known_cost is None:
            known_cost = record.estimated_cost_usd
        if known_cost is None:
            raise VisualAssetFulfillmentError(
                f"El record '{record.record_id}' no declara costo."
            )
        delivery_uri = record.delivery_uri
        if (
            delivery_base_uri is not None
            and record.provider_name == WIKIMEDIA_PROVIDER_NAME
        ):
            delivery_uri = _join_public_uri(delivery_base_uri, relative)
        return (
            CatalogEntry(
                entry_id=record.record_id,
                capability=record.capability,
                role=record.role.value,
                relative_path=relative.as_posix(),
                delivery_uri=delivery_uri,
                mime_type=record.mime_type,
                media_family=record.media_family,
                file_extension=extension,
                scene_id=record.scene_id,
                cue_id=record.cue_id,
                existing_asset_id=existing_asset_id,
                source_url=source_url,
                license_name=license_name[:256],
                attribution=attribution[:512] if attribution else None,
                actual_cost_usd=float(known_cost),
            ),
            reused,
        )

    def _persist_delivery_overrides(
        self,
        manifest: ProductionManifest,
        resolution: AssetResolutionRun,
        *,
        entries: list[CatalogEntry],
        workspace: Path,
    ) -> AssetResolutionRun:
        delivery_by_record = {entry.entry_id: entry.delivery_uri for entry in entries}
        records: list[ResolvedAsset] = []
        changed: list[ResolvedAsset] = []
        for record in resolution.bundle.assets:
            delivery_uri = delivery_by_record.get(record.record_id)
            if delivery_uri is None or delivery_uri == record.delivery_uri:
                records.append(record)
                continue
            updated = record.model_copy(update={"delivery_uri": delivery_uri})
            records.append(updated)
            changed.append(updated)
        if not changed:
            return resolution

        base = Path(resolution.bundle_relative_path).parent
        for record in changed:
            receipt_relative = base / "receipts" / f"{record.record_id}.json"
            self.metadata_store.persist_metadata(
                workspace_root=workspace,
                relative_path=receipt_relative,
                content=record.model_dump(mode="json"),
                artifact_type="asset_resolution_receipt",
                metadata={
                    "manifest_id": manifest.manifest_id,
                    "record_id": record.record_id,
                    "request_sha256": record.request_sha256,
                    "delivery_mirrored": True,
                },
                artifact_id=f"delivery-receipt-{record.record_id}",
                collision_policy=CollisionPolicy.REPLACE,
            )

        bundle_payload = resolution.bundle.model_dump(mode="json")
        bundle_payload["assets"] = [
            record.model_dump(mode="json") for record in records
        ]
        metadata = dict(bundle_payload.get("metadata") or {})
        metadata["mirrored_delivery_count"] = len(changed)
        bundle_payload["metadata"] = metadata
        bundle = type(resolution.bundle).model_validate(bundle_payload)
        bundle_write = self.metadata_store.persist_metadata(
            workspace_root=workspace,
            relative_path=resolution.bundle_relative_path,
            content=bundle.model_dump(mode="json"),
            artifact_type="asset_resolution_bundle",
            metadata={
                "manifest_id": manifest.manifest_id,
                "manifest_sha256": bundle.manifest_sha256,
                "resolution_id": bundle.resolution_id,
                "mirrored_delivery_count": len(changed),
            },
            artifact_id=f"delivery-{bundle.resolution_id}",
            collision_policy=CollisionPolicy.REPLACE,
        )
        return AssetResolutionRun(
            bundle=bundle,
            bundle_relative_path=Path(bundle_write.artifact.path)
            .resolve(strict=False)
            .relative_to(workspace)
            .as_posix(),
            bundle_sidecar_relative_path=bundle_write.sidecar_path
            .resolve(strict=False)
            .relative_to(workspace)
            .as_posix(),
            reused_existing=resolution.reused_existing,
            resolved_count=resolution.resolved_count,
            reused_count=resolution.reused_count,
        )

    @staticmethod
    def _persisted(resolution: AssetResolutionRun) -> tuple[ResolvedAsset, ...]:
        return tuple(
            record
            for record in resolution.bundle.assets
            if record.status is ResolutionStatus.PERSISTED
        )


def _existing_asset_id(
    manifest: ProductionManifest,
    record: ResolvedAsset,
) -> str | None:
    if record.capability != "existing_asset_resolution":
        return None
    if record.role is AssetRole.SCENE_VISUAL:
        for scene in manifest.scenes:
            if scene.scene_id == record.scene_id:
                return scene.asset_request.existing_asset_id
    if record.role is AssetRole.MUSIC and manifest.audio_design.music is not None:
        return manifest.audio_design.music.existing_asset_id
    if record.role is AssetRole.SOUND_EFFECT:
        for effect in manifest.audio_design.sound_effects:
            if effect.cue_id == record.cue_id:
                return effect.existing_asset_id
    raise VisualAssetFulfillmentError(
        f"No se encontró existing_asset_id para '{record.record_id}'."
    )


def _public_base_uri(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip().rstrip("/")
    parsed = urlsplit(normalized)
    if (
        parsed.scheme.lower() != "https"
        or not parsed.netloc
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(
            "delivery_base_uri debe ser una URL HTTPS pública sin query ni fragment."
        )
    return normalized


def _join_public_uri(base: str, relative: Path) -> str:
    return f"{base}/{quote(relative.as_posix(), safe='/')}"


def _copy_verified(source: Path, destination: Path, *, expected_sha256: str) -> bool:
    if destination.is_file():
        if _sha256(destination) != expected_sha256:
            raise VisualAssetFulfillmentError(
                f"El staging existente '{destination}' tiene contenido incompatible."
            )
        return True
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary_name: str | None = None
    try:
        with source.open("rb") as source_stream, tempfile.NamedTemporaryFile(
            mode="wb",
            dir=destination.parent,
            prefix=f".{destination.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary_name = temporary.name
            for block in iter(lambda: source_stream.read(1024 * 1024), b""):
                temporary.write(block)
            temporary.flush()
            os.fsync(temporary.fileno())
        temporary_path = Path(temporary_name)
        if _sha256(temporary_path) != expected_sha256:
            raise VisualAssetFulfillmentError(
                f"La copia temporal de '{source.name}' no conserva el hash F3."
            )
        os.replace(temporary_path, destination)
        temporary_name = None
    finally:
        if temporary_name is not None:
            Path(temporary_name).unlink(missing_ok=True)
    return False


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _text(value: Any) -> str:
    return " ".join(str(value or "").split())


def _mapping_digest(value: dict[str, Any]) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


__all__ = [
    "FULFILLMENT_REPORT_RELATIVE_PATH",
    "VisualAssetFulfillmentError",
    "VisualAssetFulfillmentResult",
    "VisualAssetFulfillmentService",
]
