"""PM8 orchestration: manifest needs -> F4/F5 execution -> F3 artifacts."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from artifact_store import ArtifactStore, CollisionPolicy
from capability_resolver import CapabilityResolver
from media_director import (
    CapabilityProviderExecutor,
    MediaArtifactPersister,
    MediaDirector,
)
from media_director.models import (
    MediaRequest as DirectorMediaRequest,
    MediaResult as DirectorMediaResult,
    MediaType,
)
from media_director.strategy import MediaStrategy
from media_provider import MediaRequest as ProviderMediaRequest
from metadata_store import MetadataStore
from production_manifest import (
    AssetRequest,
    AssetType,
    CostHint,
    ProductionManifest,
    QualityHint,
    SceneSpec,
    serialize_manifest,
)
from workspace_resolver import WorkspaceResolver

from .errors import (
    AssetOutputValidationError,
    AssetProviderExecutionError,
    AssetProviderSelectionError,
    AssetReceiptIntegrityError,
    AssetResolutionError,
)
from .models import (
    ASSET_RESOLUTION_FILENAME,
    AssetBinary,
    AssetResolutionBundle,
    AssetRole,
    CostStatus,
    MediaFamily,
    ResolutionStatus,
    ResolvedAsset,
    deterministic_record_id,
    deterministic_request_sha256,
    deterministic_resolution_id,
)
from .policy import AssetProviderPolicy, ProviderSelection


_VISUAL_CAPABILITIES: dict[AssetType, tuple[str, tuple[MediaFamily, ...]]] = {
    AssetType.AI_VIDEO: ("ai_video_generation", (MediaFamily.VIDEO,)),
    AssetType.AI_IMAGE: ("image_generation", (MediaFamily.IMAGE,)),
    AssetType.STOCK_VIDEO: ("stock_video_search", (MediaFamily.VIDEO,)),
    AssetType.STOCK_IMAGE: ("stock_image_search", (MediaFamily.IMAGE,)),
    AssetType.EXISTING_ASSET: (
        "existing_asset_resolution",
        (MediaFamily.IMAGE, MediaFamily.VIDEO),
    ),
}
_RENDERER_NATIVE_ASSETS = frozenset(
    {AssetType.MOTION_GRAPHIC, AssetType.TEXT_GRAPHIC}
)
_SENSITIVE_METADATA_TOKENS = (
    "api_key",
    "authorization",
    "credential",
    "password",
    "secret",
    "token",
)


@dataclass(frozen=True, slots=True)
class AssetResolutionRun:
    bundle: AssetResolutionBundle
    bundle_relative_path: str
    bundle_sidecar_relative_path: str
    reused_existing: bool
    resolved_count: int
    reused_count: int


class _AssetStrategy(MediaStrategy):
    """F5 strategy configured for one PM8 capability and output family."""

    default_post_process_chain = ()

    def __init__(
        self,
        *,
        strategy_name: str,
        capability: str,
        media_type: MediaType,
        output_format: str,
    ) -> None:
        self.strategy_name = strategy_name
        self.provider_capability = capability
        self.media_type = media_type
        self.output_format = output_format
        super().__init__(input_schema={"prompt": str})


class ManifestAssetResolver:
    """Resolve every manifest visual/audio need before render compilation.

    The class composes existing boundaries instead of replacing them:
    ``CapabilityResolver`` (F4), ``MediaDirector`` and
    ``CapabilityProviderExecutor`` (F5), then specialized stores through
    ``MediaArtifactPersister``/``MetadataStore`` (F3).
    """

    def __init__(
        self,
        *,
        capability_resolver: CapabilityResolver,
        workspace_resolver: WorkspaceResolver,
        allow_paid: bool = False,
        allow_unknown_cost: bool = False,
        preferred_providers: Mapping[str, str] | None = None,
    ) -> None:
        if not isinstance(capability_resolver, CapabilityResolver):
            raise TypeError("capability_resolver debe ser CapabilityResolver.")
        if not isinstance(workspace_resolver, WorkspaceResolver):
            raise TypeError("workspace_resolver debe ser WorkspaceResolver.")
        self._workspace_resolver = workspace_resolver
        self._policy = AssetProviderPolicy(
            capability_resolver,
            allow_paid=allow_paid,
            allow_unknown_cost=allow_unknown_cost,
        )
        self._allow_paid = bool(allow_paid)
        self._preferred_providers = {
            str(capability).strip().lower(): str(provider).strip().lower()
            for capability, provider in dict(preferred_providers or {}).items()
        }
        if any(not key or not value for key, value in self._preferred_providers.items()):
            raise ValueError("preferred_providers no acepta nombres vacíos.")
        self._persister = MediaArtifactPersister(workspace_resolver)
        self._metadata_store = MetadataStore(workspace_resolver)

    @property
    def workspace_resolver(self) -> WorkspaceResolver:
        return self._workspace_resolver

    def resolve(
        self,
        manifest: ProductionManifest,
        *,
        workspace_root: str | Path,
    ) -> AssetResolutionRun:
        if not isinstance(manifest, ProductionManifest):
            raise TypeError("manifest debe ser ProductionManifest.")
        workspace = Path(workspace_root).expanduser().resolve(strict=False)
        self._workspace_resolver.confine_path(workspace, "asset_resolution")
        manifest_sha256 = hashlib.sha256(
            serialize_manifest(manifest).encode("utf-8")
        ).hexdigest()
        base = self._base_path(manifest, manifest_sha256)
        bundle_relative_path = (base / ASSET_RESOLUTION_FILENAME).as_posix()

        existing = self._load_existing_bundle(
            manifest=manifest,
            manifest_sha256=manifest_sha256,
            workspace=workspace,
            relative_path=bundle_relative_path,
        )
        if existing is not None:
            return AssetResolutionRun(
                bundle=existing,
                bundle_relative_path=bundle_relative_path,
                bundle_sidecar_relative_path=self._relative(
                    ArtifactStore.sidecar_path_for(workspace / bundle_relative_path),
                    workspace,
                ),
                reused_existing=True,
                resolved_count=0,
                reused_count=sum(
                    asset.status is ResolutionStatus.PERSISTED
                    for asset in existing.assets
                ),
            )

        records: list[ResolvedAsset] = []
        reused_count = 0
        resolved_count = 0
        for scene in manifest.scenes:
            record, reused = self._resolve_scene_visual(
                manifest,
                scene,
                manifest_sha256=manifest_sha256,
                workspace=workspace,
                base=base,
            )
            records.append(record)
            reused_count += int(reused)
            resolved_count += int(
                record.status is ResolutionStatus.PERSISTED and not reused
            )
            if scene.narration_text is not None:
                record, reused = self._resolve_persisted(
                    manifest=manifest,
                    manifest_sha256=manifest_sha256,
                    workspace=workspace,
                    base=base,
                    role=AssetRole.SCENE_NARRATION,
                    asset_type="narration",
                    scene_id=scene.scene_id,
                    cue_id=None,
                    source_reference_ids=scene.source_reference_ids,
                    capability="voice_synthesis",
                    prompt=scene.narration_text,
                    payload={
                        "scene_id": scene.scene_id,
                        "text": scene.narration_text,
                        "locale": manifest.locale,
                        "voice_characteristics": list(
                            manifest.narration.voice_characteristics
                        ),
                        "pace_words_per_minute": (
                            manifest.narration.pace_words_per_minute
                        ),
                        "duration_seconds": scene.duration_seconds,
                    },
                    expected_families=(MediaFamily.AUDIO,),
                    quality_hint=QualityHint.HIGH,
                    cost_hint=CostHint.FREE,
                    selected_from_alternative=False,
                )
                records.append(record)
                reused_count += int(reused)
                resolved_count += int(not reused)

        music = manifest.audio_design.music
        if music is not None:
            existing_id = music.existing_asset_id
            record, reused = self._resolve_persisted(
                manifest=manifest,
                manifest_sha256=manifest_sha256,
                workspace=workspace,
                base=base,
                role=AssetRole.MUSIC,
                asset_type="music",
                scene_id=None,
                cue_id=None,
                source_reference_ids=(),
                capability=(
                    "existing_asset_resolution"
                    if existing_id is not None
                    else "music_generation"
                ),
                prompt=music.creative_brief or music.mood,
                payload={
                    "mood": music.mood,
                    "energy": music.energy,
                    "instrumental_preferred": music.instrumental_preferred,
                    "duration_seconds": (
                        music.duration_seconds or manifest.output.duration_seconds
                    ),
                    "existing_asset_id": existing_id,
                },
                expected_families=(MediaFamily.AUDIO,),
                quality_hint=QualityHint.HIGH,
                cost_hint=CostHint.FREE,
                selected_from_alternative=False,
            )
            records.append(record)
            reused_count += int(reused)
            resolved_count += int(not reused)

        scene_by_id = {scene.scene_id: scene for scene in manifest.scenes}
        for effect in manifest.audio_design.sound_effects:
            existing_id = effect.existing_asset_id
            record, reused = self._resolve_persisted(
                manifest=manifest,
                manifest_sha256=manifest_sha256,
                workspace=workspace,
                base=base,
                role=AssetRole.SOUND_EFFECT,
                asset_type="sound_effect",
                scene_id=None,
                cue_id=effect.cue_id,
                source_reference_ids=scene_by_id[
                    effect.scene_id
                ].source_reference_ids,
                capability=(
                    "existing_asset_resolution"
                    if existing_id is not None
                    else "sound_effect_generation"
                ),
                prompt=effect.description,
                payload={
                    "cue_id": effect.cue_id,
                    "description": effect.description,
                    "duration_seconds": effect.duration_seconds,
                    "intensity": effect.intensity,
                    "existing_asset_id": existing_id,
                },
                expected_families=(MediaFamily.AUDIO,),
                quality_hint=QualityHint.STANDARD,
                cost_hint=CostHint.FREE,
                selected_from_alternative=False,
            )
            records.append(record)
            reused_count += int(reused)
            resolved_count += int(not reused)

        ordered = tuple(sorted(records, key=lambda item: item.locator))
        estimated_total = round(
            sum(asset.estimated_cost_usd or 0.0 for asset in ordered),
            8,
        )
        actual_total = round(
            sum(asset.actual_cost_usd or 0.0 for asset in ordered),
            8,
        )
        unknown_count = sum(
            asset.cost_status is CostStatus.UNKNOWN for asset in ordered
        )
        bundle = AssetResolutionBundle(
            resolution_id=deterministic_resolution_id(
                manifest_id=manifest.manifest_id,
                manifest_sha256=manifest_sha256,
                assets=ordered,
            ),
            manifest_id=manifest.manifest_id,
            manifest_sha256=manifest_sha256,
            project_id=manifest.project.project_id,
            production_id=manifest.project.production_id,
            assets=ordered,
            total_estimated_cost_usd=estimated_total,
            total_actual_cost_usd=actual_total,
            unknown_cost_count=unknown_count,
            metadata={
                "provider_neutral": True,
                "free_only": not self._allow_paid,
                "f3_persisted_count": sum(
                    asset.status is ResolutionStatus.PERSISTED for asset in ordered
                ),
            },
        )
        written = self._metadata_store.persist_metadata(
            workspace_root=workspace,
            relative_path=bundle_relative_path,
            content=bundle.model_dump(mode="json"),
            artifact_type="asset_resolution_bundle",
            metadata={
                "manifest_id": manifest.manifest_id,
                "manifest_sha256": manifest_sha256,
                "resolution_id": bundle.resolution_id,
            },
            artifact_id=bundle.resolution_id,
            collision_policy=CollisionPolicy.REUSE_IDENTICAL,
        )
        return AssetResolutionRun(
            bundle=bundle,
            bundle_relative_path=self._relative(Path(written.artifact.path), workspace),
            bundle_sidecar_relative_path=self._relative(written.sidecar_path, workspace),
            reused_existing=False,
            resolved_count=resolved_count,
            reused_count=reused_count,
        )

    def _resolve_scene_visual(
        self,
        manifest: ProductionManifest,
        scene: SceneSpec,
        *,
        manifest_sha256: str,
        workspace: Path,
        base: Path,
    ) -> tuple[ResolvedAsset, bool]:
        request = scene.asset_request
        failures: list[str] = []
        choices = (request.asset_type, *request.alternatives)
        for index, asset_type in enumerate(choices):
            selected_from_alternative = index > 0
            if asset_type is AssetType.NONE:
                return (
                    self._non_persisted_record(
                        manifest=manifest,
                        role=AssetRole.SCENE_VISUAL,
                        scene_id=scene.scene_id,
                        cue_id=None,
                        source_reference_ids=scene.source_reference_ids,
                        asset_type=asset_type.value,
                        status=ResolutionStatus.NOT_REQUIRED,
                        selected_from_alternative=selected_from_alternative,
                    ),
                    False,
                )
            if asset_type in _RENDERER_NATIVE_ASSETS:
                return (
                    self._non_persisted_record(
                        manifest=manifest,
                        role=AssetRole.SCENE_VISUAL,
                        scene_id=scene.scene_id,
                        cue_id=None,
                        source_reference_ids=scene.source_reference_ids,
                        asset_type=asset_type.value,
                        status=ResolutionStatus.RENDERER_NATIVE,
                        selected_from_alternative=selected_from_alternative,
                    ),
                    False,
                )
            capability_contract = _VISUAL_CAPABILITIES.get(asset_type)
            if capability_contract is None:
                failures.append(f"{asset_type.value}:sin_mapeo")
                continue
            capability, expected_families = capability_contract
            try:
                return self._resolve_persisted(
                    manifest=manifest,
                    manifest_sha256=manifest_sha256,
                    workspace=workspace,
                    base=base,
                    role=AssetRole.SCENE_VISUAL,
                    asset_type=asset_type.value,
                    scene_id=scene.scene_id,
                    cue_id=None,
                    source_reference_ids=scene.source_reference_ids,
                    capability=capability,
                    prompt=self._visual_prompt(request, asset_type),
                    payload={
                        "scene_id": scene.scene_id,
                        "asset_type": asset_type.value,
                        "creative_brief": request.creative_brief,
                        "image_prompt": request.image_prompt,
                        "video_prompt": request.video_prompt,
                        "stock_query": request.stock_query,
                        "existing_asset_id": request.existing_asset_id,
                        "visual_direction": scene.visual_direction.model_dump(mode="json"),
                        "duration_seconds": scene.duration_seconds,
                        "output": manifest.output.model_dump(mode="json"),
                        "style_profile": manifest.style_profile,
                    },
                    expected_families=expected_families,
                    quality_hint=request.quality_hint,
                    cost_hint=request.cost_hint,
                    selected_from_alternative=selected_from_alternative,
                )
            except AssetProviderSelectionError as error:
                failures.append(f"{asset_type.value}:{error}")
                continue
        raise AssetProviderSelectionError(
            f"La escena '{scene.scene_id}' no pudo resolver ninguna opción: "
            + " | ".join(failures)
        )

    def _resolve_persisted(
        self,
        *,
        manifest: ProductionManifest,
        manifest_sha256: str,
        workspace: Path,
        base: Path,
        role: AssetRole,
        asset_type: str,
        scene_id: str | None,
        cue_id: str | None,
        source_reference_ids: tuple[str, ...],
        capability: str,
        prompt: str,
        payload: Mapping[str, Any],
        expected_families: tuple[MediaFamily, ...],
        quality_hint: QualityHint,
        cost_hint: CostHint,
        selected_from_alternative: bool,
    ) -> tuple[ResolvedAsset, bool]:
        provider_payload = {
            **dict(payload),
            "manifest_id": manifest.manifest_id,
            "manifest_sha256": manifest_sha256,
            "project_id": manifest.project.project_id,
            "production_id": manifest.project.production_id,
            "role": role.value,
            "source_reference_ids": list(source_reference_ids),
            "prompt": prompt,
        }
        selection_request = ProviderMediaRequest(
            capability=capability,
            payload=provider_payload,
            metadata={
                "manifest_id": manifest.manifest_id,
                "scene_id": scene_id,
                "cue_id": cue_id,
                    "role": role.value,
                    "source_reference_ids": list(source_reference_ids),
                },
        )
        selection = self._policy.select(
            selection_request,
            quality_hint=quality_hint,
            cost_hint=cost_hint,
            preferred_provider=self._preferred_providers.get(capability),
        )
        request_sha256 = deterministic_request_sha256(
            {
                "capability": capability,
                "payload": provider_payload,
                "quality_hint": quality_hint.value,
                "cost_hint": cost_hint.value,
            }
        )
        record_id = deterministic_record_id(
            request_sha256,
            selection.provider.provider_name,
        )
        receipt_relative_path = (
            base / "receipts" / f"{record_id}.json"
        ).as_posix()
        existing = self._load_receipt(
            workspace=workspace,
            relative_path=receipt_relative_path,
            request_sha256=request_sha256,
            record_id=record_id,
        )
        if existing is not None:
            return existing, True

        initial_media_type = self._director_media_type(expected_families[0])
        strategy = _AssetStrategy(
            strategy_name=f"asset_{role.value}",
            capability=capability,
            media_type=initial_media_type,
            output_format=expected_families[0].value,
        )
        director = MediaDirector(strategy)

        def provider_invoker(provider: Any, work_package: Any) -> AssetBinary:
            result = provider.generate(
                ProviderMediaRequest(
                    capability=work_package.capability,
                    payload=dict(work_package.provider_payload),
                    metadata=dict(work_package.metadata),
                )
            )
            if not result.success:
                details = "; ".join(str(item) for item in result.errors)
                raise AssetProviderExecutionError(
                    result.message + (f": {details}" if details else "")
                )
            if not isinstance(result.output, AssetBinary):
                raise AssetOutputValidationError(
                    f"El provider '{provider.provider_name}' no devolvió AssetBinary."
                )
            return result.output

        executor = CapabilityProviderExecutor(
            self._policy.resolver,
            provider_invoker=provider_invoker,
        )
        director_result = director.execute(
            DirectorMediaRequest(
                prompt=prompt,
                input_data={
                    key: value
                    for key, value in provider_payload.items()
                    if key != "prompt"
                },
                preferred_provider=selection.provider.provider_name,
                metadata={
                    "manifest_id": manifest.manifest_id,
                    "scene_id": scene_id,
                    "cue_id": cue_id,
                    "role": role.value,
                    "asset_type": asset_type,
                    "provider": selection.provider.provider_name,
                    "capability": capability,
                    "estimated_cost_usd": selection.estimated_cost_usd,
                },
            ),
            provider_executor=executor,
        )
        output = director_result.output
        if not isinstance(output, AssetBinary):
            raise AssetOutputValidationError("F5 no devolvió AssetBinary.")
        if output.media_family not in expected_families:
            expected = ", ".join(item.value for item in expected_families)
            raise AssetOutputValidationError(
                f"El provider devolvió '{output.media_family.value}', se esperaba {expected}."
            )
        if not self._allow_paid and (output.actual_cost_usd or 0.0) > 0.0:
            raise AssetOutputValidationError(
                "El provider reportó costo real positivo sin autorización de pago."
            )

        media_type = self._director_media_type(output.media_family)
        binary_result = DirectorMediaResult(
            request_id=director_result.request_id,
            strategy_name=director_result.strategy_name,
            media_type=media_type,
            capability=director_result.capability,
            output_format=output.file_extension.lstrip("."),
            output=output.content,
            post_process_chain=director_result.post_process_chain,
            metadata={
                **dict(director_result.metadata),
                **self._safe_metadata(output.metadata),
                "provider_quality_tier": selection.quality_tier,
                "provider_cost_tier": selection.cost_tier,
                "request_sha256": request_sha256,
            },
        )
        identity = scene_id or cue_id or role.value
        relative_path = (
            base
            / "artifacts"
            / role.value
            / f"{identity}-{record_id[-8:]}{output.file_extension}"
        ).as_posix()
        written = self._persister.persist(
            binary_result,
            workspace_root=workspace,
            relative_path=relative_path,
            mime_type=output.mime_type,
            metadata={
                "asset_resolution_record_id": record_id,
                "manifest_sha256": manifest_sha256,
                "selected_from_alternative": selected_from_alternative,
            },
            artifact_id=record_id,
            collision_policy=CollisionPolicy.REUSE_IDENTICAL,
        )
        artifact = written.artifact
        actual_cost = output.actual_cost_usd
        known_cost = actual_cost
        if known_cost is None:
            known_cost = selection.estimated_cost_usd
        cost_status = (
            CostStatus.UNKNOWN
            if known_cost is None
            else CostStatus.FREE
            if known_cost == 0.0
            else CostStatus.KNOWN
        )
        record = ResolvedAsset(
            record_id=record_id,
            request_sha256=request_sha256,
            role=role,
            status=ResolutionStatus.PERSISTED,
            asset_type=asset_type,
            scene_id=scene_id,
            cue_id=cue_id,
            source_reference_ids=source_reference_ids,
            selected_from_alternative=selected_from_alternative,
            provider_name=selection.provider.provider_name,
            capability=capability,
            media_family=output.media_family,
            artifact_id=artifact.artifact_id,
            artifact_relative_path=self._relative(Path(artifact.path), workspace),
            sidecar_relative_path=self._relative(written.sidecar_path, workspace),
            content_sha256=artifact.content_hash,
            mime_type=artifact.mime_type,
            size_bytes=artifact.size_bytes,
            delivery_uri=output.delivery_uri,
            estimated_cost_usd=selection.estimated_cost_usd,
            actual_cost_usd=actual_cost,
            cost_status=cost_status,
            created_at=written.created_at,
            metadata={
                **dict(selection.metadata),
                **self._safe_metadata(output.metadata),
                "deduplicated": written.deduplicated,
                "event_created": written.event_created,
            },
        )
        self._metadata_store.persist_metadata(
            workspace_root=workspace,
            relative_path=receipt_relative_path,
            content=record.model_dump(mode="json"),
            artifact_type="asset_resolution_receipt",
            metadata={
                "manifest_id": manifest.manifest_id,
                "record_id": record.record_id,
                "request_sha256": request_sha256,
            },
            artifact_id=f"receipt-{record_id}",
            collision_policy=CollisionPolicy.REUSE_IDENTICAL,
        )
        return record, False

    def _non_persisted_record(
        self,
        *,
        manifest: ProductionManifest,
        role: AssetRole,
        scene_id: str | None,
        cue_id: str | None,
        source_reference_ids: tuple[str, ...],
        asset_type: str,
        status: ResolutionStatus,
        selected_from_alternative: bool,
    ) -> ResolvedAsset:
        request_sha256 = deterministic_request_sha256(
            {
                "manifest_id": manifest.manifest_id,
                "role": role.value,
                "scene_id": scene_id,
                "cue_id": cue_id,
                "source_reference_ids": list(source_reference_ids),
                "asset_type": asset_type,
                "status": status.value,
            }
        )
        return ResolvedAsset(
            record_id=deterministic_record_id(request_sha256, None),
            request_sha256=request_sha256,
            role=role,
            status=status,
            asset_type=asset_type,
            scene_id=scene_id,
            cue_id=cue_id,
            source_reference_ids=source_reference_ids,
            selected_from_alternative=selected_from_alternative,
            actual_cost_usd=0.0,
            cost_status=CostStatus.FREE,
            metadata={"provider_required": False},
        )

    def _load_existing_bundle(
        self,
        *,
        manifest: ProductionManifest,
        manifest_sha256: str,
        workspace: Path,
        relative_path: str,
    ) -> AssetResolutionBundle | None:
        if not self._metadata_store.exists(workspace, relative_path):
            return None
        try:
            self._metadata_store.load_sidecar(workspace, relative_path)
            bundle = AssetResolutionBundle.model_validate_json(
                self._metadata_store.read_bytes(workspace, relative_path)
            )
        except Exception as error:
            raise AssetReceiptIntegrityError(
                f"El bundle PM8 existente es inválido: {type(error).__name__}: {error}"
            ) from error
        if (
            bundle.manifest_id != manifest.manifest_id
            or bundle.manifest_sha256 != manifest_sha256
            or bundle.project_id != manifest.project.project_id
            or bundle.production_id != manifest.project.production_id
        ):
            raise AssetReceiptIntegrityError(
                "El bundle PM8 existente no corresponde al manifest actual."
            )
        for record in bundle.assets:
            self._verify_record(record, workspace)
        return bundle

    def _load_receipt(
        self,
        *,
        workspace: Path,
        relative_path: str,
        request_sha256: str,
        record_id: str,
    ) -> ResolvedAsset | None:
        if not self._metadata_store.exists(workspace, relative_path):
            return None
        try:
            self._metadata_store.load_sidecar(workspace, relative_path)
            record = ResolvedAsset.model_validate_json(
                self._metadata_store.read_bytes(workspace, relative_path)
            )
        except Exception as error:
            raise AssetReceiptIntegrityError(
                f"El recibo PM8 existente es inválido: {type(error).__name__}: {error}"
            ) from error
        if record.record_id != record_id or record.request_sha256 != request_sha256:
            raise AssetReceiptIntegrityError(
                "El recibo PM8 no coincide con la solicitud determinista."
            )
        self._verify_record(record, workspace)
        return record

    @staticmethod
    def _verify_record(record: ResolvedAsset, workspace: Path) -> None:
        if record.status is not ResolutionStatus.PERSISTED:
            return
        assert record.artifact_relative_path is not None
        assert record.sidecar_relative_path is not None
        assert record.content_sha256 is not None
        assert record.artifact_id is not None
        artifact_path = (workspace / record.artifact_relative_path).resolve(strict=False)
        sidecar_path = (workspace / record.sidecar_relative_path).resolve(strict=False)
        try:
            artifact_path.relative_to(workspace)
            sidecar_path.relative_to(workspace)
        except ValueError as error:
            raise AssetReceiptIntegrityError(
                "Un recibo PM8 referencia una ruta fuera del workspace."
            ) from error
        if not artifact_path.is_file() or not sidecar_path.is_file():
            raise AssetReceiptIntegrityError(
                f"Artifact o sidecar PM8 ausente para '{record.record_id}'."
            )
        if ArtifactStore.calculate_file_hash(artifact_path) != record.content_sha256:
            raise AssetReceiptIntegrityError(
                f"Hash físico inválido para '{record.record_id}'."
            )
        try:
            sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise AssetReceiptIntegrityError(
                f"Sidecar F3 inválido para '{record.record_id}'."
            ) from error
        if sidecar.get("content_hash") != record.content_sha256:
            raise AssetReceiptIntegrityError(
                f"Hash de sidecar inválido para '{record.record_id}'."
            )
        events = sidecar.get("events", [])
        if not any(
            isinstance(event, dict)
            and event.get("artifact_id") == record.artifact_id
            for event in events
        ):
            raise AssetReceiptIntegrityError(
                f"Sidecar sin evento para '{record.artifact_id}'."
            )

    @staticmethod
    def _visual_prompt(request: AssetRequest, asset_type: AssetType) -> str:
        if asset_type is AssetType.AI_IMAGE:
            return request.image_prompt or request.creative_brief or "AI image"
        if asset_type is AssetType.AI_VIDEO:
            return request.video_prompt or request.creative_brief or "AI video"
        if asset_type in {AssetType.STOCK_IMAGE, AssetType.STOCK_VIDEO}:
            return request.stock_query or request.creative_brief or "stock asset"
        if asset_type is AssetType.EXISTING_ASSET:
            return request.existing_asset_id or "existing asset"
        return request.creative_brief or asset_type.value

    @staticmethod
    def _director_media_type(family: MediaFamily) -> MediaType:
        if family is MediaFamily.IMAGE:
            return MediaType.IMAGE
        if family is MediaFamily.VIDEO:
            return MediaType.VIDEO
        if family is MediaFamily.AUDIO:
            return MediaType.VOICE
        raise AssetOutputValidationError(
            f"MediaFamily no persistible mediante F5: {family.value}."
        )

    @staticmethod
    def _safe_metadata(metadata: Mapping[str, Any]) -> dict[str, Any]:
        safe: dict[str, Any] = {}
        for raw_key, value in metadata.items():
            key = str(raw_key)
            lowered = key.lower()
            if any(token in lowered for token in _SENSITIVE_METADATA_TOKENS):
                continue
            if value is None or isinstance(value, (str, int, float, bool)):
                safe[key] = value
        return safe

    @staticmethod
    def _base_path(
        manifest: ProductionManifest,
        manifest_sha256: str,
    ) -> Path:
        return Path("asset_resolution") / manifest.manifest_id / manifest_sha256[:16]

    @staticmethod
    def _relative(path: Path, workspace: Path) -> str:
        try:
            return path.resolve(strict=False).relative_to(workspace).as_posix()
        except ValueError as error:
            raise AssetResolutionError(
                f"La ruta resuelta quedó fuera del workspace: {path}"
            ) from error


__all__ = ["AssetResolutionRun", "ManifestAssetResolver"]
