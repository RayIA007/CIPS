"""Unify fresh FAO projects with the already validated PM9 preparation chain.

FAO.5 deliberately stops at the real-render authorization boundary.  It reuses
FAO.4, PM8/PM9 asset resolution, F3 persistence, canonical subtitles and the
PM9 preparation/F8 telemetry surface without submitting a render or recording
a human F7 decision.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

from artifact_store import CollisionPolicy
from asset_resolution import ManifestAssetResolver, WikimediaCommonsProvider
from capability_resolver import CapabilityResolver
from media_provider_registry import MediaProviderRegistry
from metadata_store import MetadataStore
from production_acceptance import (
    ApprovedAssetCatalog,
    ApprovedAssetCatalogProvider,
    FasterWhisperTranscriber,
    FullProductionAcceptance,
    NarrationConformanceGate,
    NarrationConformancePolicy,
    PM9SourceAssetBuilder,
    PreparedProduction,
    SourceAssetBuildResult,
    VisualAssetFulfillmentResult,
    VisualAssetFulfillmentService,
    derive_github_raw_base,
)
from production_derivation import (
    ProductionDerivationEngine,
    ProductionDerivationResult,
)
from production_manifest import ProductionManifest
from production_manifest_compiler import ProductionManifestCompiler
from run_pm9_full_production_acceptance import (
    INVENTORY_RELATIVE_PATH,
    _adapter_factory,
    _asset_inventory,
    _estimated_credits,
    _load_project_config,
    _payload_relative_path,
    _planned_manifest,
)
from telemetry_engine import TelemetryEngine
from workspace_resolver import WorkspaceResolver


UNIFICATION_RELATIVE_PATH = Path("state") / "fao_pm9_unification.json"
_SCHEMA_NAME = "cips.fao.pm9_unification"
_SCHEMA_VERSION = "1.0"
_SUPPORTED_RENDER_PROVIDERS = {"creatomate", "json2video"}
_RENDER_OUTPUTS = (
    Path("render") / "creatomate_result.json",
    Path("render") / "json2video_result.json",
    Path("acceptance") / "final_acceptance.json",
    Path("final") / "short.mp4",
)

SourceAssetBuilderFactory = Callable[..., PM9SourceAssetBuilder]
WikimediaProviderFactory = Callable[[], WikimediaCommonsProvider]
AcceptanceFactory = Callable[..., FullProductionAcceptance]


class FAOPM9UnificationError(RuntimeError):
    """FAO.5 could not complete a safe PM9 preparation."""


class FAOPM9UnificationBlockedError(FAOPM9UnificationError):
    """FAO.5 stopped before an unsafe, paid, rendered or published action."""


@dataclass(frozen=True, slots=True)
class FAOPM9UnificationResult:
    """Durable FAO.5 result returned to the official CIPS entry point."""

    project_path: Path
    evidence_path: Path
    provider: str
    ready_for_real_render: bool
    estimated_render_credits: int
    total_actual_cost_usd: float
    persisted_asset_count: int
    inventory_path: Path
    catalog_path: Path
    preparation_path: Path
    payload_path: Path
    canonical_subtitles_path: Path | None
    network_called: bool
    reused_existing: bool

    def metadata(self) -> dict[str, Any]:
        """Return checkpoint-safe, portable metadata for MenuController."""

        return {
            "fao_pm9_unification_complete": True,
            "fao_pm9_unification_path": _relative(
                self.evidence_path,
                self.project_path,
            ),
            "render_provider": self.provider,
            "ready_for_real_render": self.ready_for_real_render,
            "estimated_render_credits": self.estimated_render_credits,
            "total_actual_cost_usd": self.total_actual_cost_usd,
            "persisted_asset_count": self.persisted_asset_count,
            "inventory_path": _relative(self.inventory_path, self.project_path),
            "catalog_path": _relative(self.catalog_path, self.project_path),
            "preparation_path": _relative(
                self.preparation_path,
                self.project_path,
            ),
            "payload_path": _relative(self.payload_path, self.project_path),
            "canonical_subtitles_path": (
                None
                if self.canonical_subtitles_path is None
                else _relative(self.canonical_subtitles_path, self.project_path)
            ),
            "network_called": self.network_called,
            "paid_provider_called": False,
            "render_performed": False,
            "f7_review_performed": False,
            "publication_performed": False,
            "reused_existing": self.reused_existing,
        }


class FAOPM9UnificationEngine:
    """Connect a verified FAO.4 project to the PM9 preparation boundary."""

    component_name = "fao_pm9_unification_engine"
    schema_name = _SCHEMA_NAME
    schema_version = _SCHEMA_VERSION
    engine_version = "1.0"

    def __init__(
        self,
        *,
        render_provider: str = "creatomate",
        delivery_base_uri: str | None = None,
        source_asset_builder_factory: SourceAssetBuilderFactory | None = None,
        wikimedia_provider_factory: WikimediaProviderFactory | None = None,
        acceptance_factory: AcceptanceFactory | None = None,
    ) -> None:
        provider = str(render_provider).strip().casefold()
        if provider not in _SUPPORTED_RENDER_PROVIDERS:
            raise ValueError(
                "render_provider debe ser creatomate o json2video."
            )
        self.render_provider = provider
        self.delivery_base_uri = (
            None
            if delivery_base_uri is None
            else str(delivery_base_uri).strip().rstrip("/")
        )
        if self.delivery_base_uri == "":
            raise ValueError("delivery_base_uri no puede estar vacío.")
        self.source_asset_builder_factory = source_asset_builder_factory
        self.wikimedia_provider_factory = (
            wikimedia_provider_factory or WikimediaCommonsProvider
        )
        self.acceptance_factory = acceptance_factory

    def prepare(self, project_path: str | Path) -> FAOPM9UnificationResult:
        """Prepare all zero-cost PM9 inputs and stop before a real render."""

        project = Path(project_path).expanduser().resolve(strict=False)
        workspace = _workspace_for(project)
        metadata_store = MetadataStore(workspace)
        request = _read_json_object(
            project / "operational_request.json",
            "solicitud operativa FAO",
        )
        self._validate_request(request, project)
        self._guard_no_render_outputs(project)

        derivation = ProductionDerivationEngine(
            workspace_resolver=workspace,
            metadata_store=metadata_store,
        ).derive_and_persist(project)
        config = _load_project_config(project)
        planned = self._planned_manifest(project, workspace, config, derivation)
        assets_root = (project / config["assets_root_relative_path"]).resolve(
            strict=False
        )
        delivery_base = self.delivery_base_uri or derive_github_raw_base(
            project,
            assets_root,
        )
        input_fingerprint = self._input_fingerprint(
            derivation,
            provider=self.render_provider,
            delivery_base_uri=delivery_base,
        )

        reused = self._reuse_existing(
            project,
            input_fingerprint=input_fingerprint,
            provider=self.render_provider,
        )
        if reused is not None:
            return reused

        inventory, inventory_path = self._persist_inventory(
            project=project,
            workspace=workspace,
            metadata_store=metadata_store,
            manifest=planned,
        )
        source_assets = self._build_source_assets(
            project=project,
            workspace=workspace,
            metadata_store=metadata_store,
            manifest=planned,
            config=config,
            assets_root=assets_root,
            delivery_base_uri=delivery_base,
        )
        fulfillment, wikimedia_calls = self._fulfill_visuals(
            project=project,
            workspace=workspace,
            manifest=planned,
            config=config,
            source_assets=source_assets,
            assets_root=assets_root,
            delivery_base_uri=delivery_base,
        )
        prepared = self._prepare_render_submission(
            project=project,
            workspace=workspace,
            config=config,
            fulfillment=fulfillment,
            assets_root=assets_root,
        )
        estimated_render_credits = _estimated_credits(
            prepared.plan,
            self.render_provider,
        )
        self._validate_zero_cost_ready(
            prepared,
            fulfillment=fulfillment,
        )

        telemetry_path = project / "03_TELEMETRIA" / TelemetryEngine.EVENTS_FILENAME
        if not telemetry_path.is_file() or telemetry_path.stat().st_size <= 0:
            raise FAOPM9UnificationError(
                "F8 no persistió la telemetría de preparación PM9."
            )
        self._guard_no_render_outputs(project)

        network_called = bool(source_assets.network_called or wikimedia_calls)
        evidence = self._build_evidence(
            project=project,
            request=request,
            derivation=derivation,
            manifest=planned,
            inventory=inventory,
            inventory_path=inventory_path,
            source_assets=source_assets,
            fulfillment=fulfillment,
            prepared=prepared,
            telemetry_path=telemetry_path,
            input_fingerprint=input_fingerprint,
            delivery_base_uri=delivery_base,
            estimated_render_credits=estimated_render_credits,
            network_called=network_called,
        )
        evidence_path = project / UNIFICATION_RELATIVE_PATH
        evidence_bytes = _json_bytes(evidence)
        write = metadata_store.persist_bytes(
            workspace_root=project,
            relative_path=UNIFICATION_RELATIVE_PATH,
            content=evidence_bytes,
            artifact_type="fao_pm9_unification_evidence",
            mime_type="application/json",
            artifact_id=f"fao5-unification-{_sha256(evidence_bytes)[:32]}",
            metadata={
                "project_id": planned.project.project_id,
                "manifest_id": planned.manifest_id,
                "provider": self.render_provider,
                "ready_for_real_render": True,
                "publication_performed": False,
            },
            collision_policy=CollisionPolicy.REPLACE,
        )
        if Path(write.artifact.path).resolve(strict=False) != evidence_path:
            raise FAOPM9UnificationError(
                "F3 no persistió la evidencia FAO.5 en la ruta canónica."
            )
        if evidence_path.read_bytes() != evidence_bytes:
            raise FAOPM9UnificationError(
                "La evidencia FAO.5 no superó la verificación de lectura."
            )
        return self._result_from_evidence(
            project,
            evidence,
            reused_existing=False,
        )

    @staticmethod
    def _validate_request(request: Mapping[str, Any], project: Path) -> None:
        if request.get("schema_name") != "cips.fao.operational_request":
            raise FAOPM9UnificationBlockedError(
                "FAO.5 requiere una solicitud operativa creada por CIPS/run.py."
            )
        if request.get("schema_version") != "1.0":
            raise FAOPM9UnificationBlockedError(
                "La versión de operational_request.json no es compatible."
            )
        if request.get("project_id") != project.name:
            raise FAOPM9UnificationBlockedError(
                "La solicitud operativa pertenece a otro proyecto."
            )
        if request.get("free_tier_default") is not True:
            raise FAOPM9UnificationBlockedError(
                "FAO.5 sólo admite la política Free Tier predeterminada."
            )
        if request.get("publication_performed") is not False:
            raise FAOPM9UnificationBlockedError(
                "FAO.5 exige publication_performed=false."
            )

    @staticmethod
    def _guard_no_render_outputs(project: Path) -> None:
        existing = [path.as_posix() for path in _RENDER_OUTPUTS if (project / path).is_file()]
        if existing:
            raise FAOPM9UnificationBlockedError(
                "FAO.5 sólo prepara y no puede operar sobre un proyecto que ya "
                "contiene render o aceptación final: " + ", ".join(existing) + "."
            )

    @staticmethod
    def _planned_manifest(
        project: Path,
        workspace: WorkspaceResolver,
        config: Mapping[str, Any],
        derivation: ProductionDerivationResult,
    ) -> ProductionManifest:
        compiled = ProductionManifestCompiler(
            workspace_resolver=workspace,
        ).compile(project)
        planned = _planned_manifest(compiled, config)
        if planned.manifest_id != derivation.manifest.manifest_id:
            raise FAOPM9UnificationError(
                "La compilación PM9 no coincide con la derivación FAO.4."
            )
        return planned

    def _persist_inventory(
        self,
        *,
        project: Path,
        workspace: WorkspaceResolver,
        metadata_store: MetadataStore,
        manifest: ProductionManifest,
    ) -> tuple[dict[str, Any], Path]:
        del workspace
        inventory = _asset_inventory(manifest)
        digest = _mapping_sha256(inventory)
        write = metadata_store.persist_metadata(
            workspace_root=project,
            relative_path=INVENTORY_RELATIVE_PATH,
            content=inventory,
            artifact_type="production_asset_requirements",
            artifact_id=f"fao5-inventory-{manifest.manifest_id}-{digest[:16]}",
            metadata={
                "manifest_id": manifest.manifest_id,
                "required_catalog_entries": inventory[
                    "required_catalog_entries"
                ],
                "publication_performed": False,
            },
            collision_policy=CollisionPolicy.REPLACE,
        )
        return inventory, Path(write.artifact.path)

    def _build_source_assets(
        self,
        *,
        project: Path,
        workspace: WorkspaceResolver,
        metadata_store: MetadataStore,
        manifest: ProductionManifest,
        config: Mapping[str, Any],
        assets_root: Path,
        delivery_base_uri: str,
    ) -> SourceAssetBuildResult:
        model_dir = workspace.outputs_root / "pm9_models" / "piper"
        factory = self.source_asset_builder_factory
        if factory is None:
            builder = self._default_source_asset_builder(
                project=project,
                workspace=workspace,
                metadata_store=metadata_store,
                manifest=manifest,
                config=config,
                assets_root=assets_root,
                model_dir=model_dir,
                delivery_base_uri=delivery_base_uri,
            )
        else:
            builder = factory(
                manifest=manifest,
                project_path=project,
                workspace_resolver=workspace,
                metadata_store=metadata_store,
                config=config,
                assets_root=assets_root,
                model_dir=model_dir,
                delivery_base_uri=delivery_base_uri,
            )
        if not isinstance(builder, PM9SourceAssetBuilder):
            raise TypeError(
                "source_asset_builder_factory debe devolver PM9SourceAssetBuilder."
            )
        return builder.build()

    @staticmethod
    def _default_source_asset_builder(
        *,
        project: Path,
        workspace: WorkspaceResolver,
        metadata_store: MetadataStore,
        manifest: ProductionManifest,
        config: Mapping[str, Any],
        assets_root: Path,
        model_dir: Path,
        delivery_base_uri: str,
    ) -> PM9SourceAssetBuilder:
        policy = config["narration_conformance_policy"]
        conformance_gate = None
        if policy.enabled:
            asr_model_dir = workspace.outputs_root / "pm9_models" / "faster_whisper"
            adjudicator = None
            if policy.adjudication_model is not None:
                adjudication_policy = policy.model_copy(
                    update={
                        "model": policy.adjudication_model,
                        "adjudication_model": None,
                    }
                )
                adjudicator = FasterWhisperTranscriber(
                    adjudication_policy,
                    model_dir=asr_model_dir,
                    allow_model_download=True,
                )
            conformance_gate = NarrationConformanceGate(
                policy,
                FasterWhisperTranscriber(
                    policy,
                    model_dir=asr_model_dir,
                    allow_model_download=True,
                ),
                metadata_store=metadata_store,
                adjudicator=adjudicator,
            )
        return PM9SourceAssetBuilder(
            manifest,
            project_path=project,
            assets_root=assets_root,
            model_dir=model_dir,
            delivery_base_uri=delivery_base_uri,
            narration_conformance_gate=conformance_gate,
            narration_voice_candidates=config["narration_voice_candidates"],
        )

    def _fulfill_visuals(
        self,
        *,
        project: Path,
        workspace: WorkspaceResolver,
        manifest: ProductionManifest,
        config: Mapping[str, Any],
        source_assets: SourceAssetBuildResult,
        assets_root: Path,
        delivery_base_uri: str,
    ) -> tuple[VisualAssetFulfillmentResult, int]:
        seed_provider = ApprovedAssetCatalogProvider(
            source_assets.catalog,
            assets_root=source_assets.assets_root,
        )
        wikimedia = self.wikimedia_provider_factory()
        if not isinstance(wikimedia, WikimediaCommonsProvider):
            raise TypeError(
                "wikimedia_provider_factory debe devolver WikimediaCommonsProvider."
            )
        resolver = ManifestAssetResolver(
            capability_resolver=CapabilityResolver(
                MediaProviderRegistry([seed_provider, wikimedia])
            ),
            workspace_resolver=workspace,
            preferred_providers={
                "stock_image_search": wikimedia.provider_name,
            },
            cache_namespace=f"fao5-seed-{_catalog_sha256(source_assets.catalog)[:16]}",
        )
        result = VisualAssetFulfillmentService(
            asset_resolver=resolver,
            workspace_resolver=workspace,
        ).fulfill(
            manifest,
            workspace_root=project,
            assets_root=assets_root,
            catalog_relative_path=config["catalog_relative_path"],
            report_relative_path=config["fulfillment_report_relative_path"],
            delivery_base_uri=delivery_base_uri,
        )
        return result, len(wikimedia.calls)

    def _prepare_render_submission(
        self,
        *,
        project: Path,
        workspace: WorkspaceResolver,
        config: Mapping[str, Any],
        fulfillment: VisualAssetFulfillmentResult,
        assets_root: Path,
    ) -> PreparedProduction:
        catalog = ApprovedAssetCatalog.load(fulfillment.catalog_path)
        provider = ApprovedAssetCatalogProvider(catalog, assets_root=assets_root)
        resolver = ManifestAssetResolver(
            capability_resolver=CapabilityResolver(
                MediaProviderRegistry([provider])
            ),
            workspace_resolver=workspace,
            cache_namespace=f"fao5-final-{_catalog_sha256(catalog)[:16]}",
        )
        if self.acceptance_factory is None:
            acceptance = FullProductionAcceptance(
                workspace_resolver=workspace,
                asset_resolver=resolver,
                frame_rate_policy=config["frame_rate_policy"],
                narration_conformance_policy=config[
                    "narration_conformance_policy"
                ],
            )
        else:
            acceptance = self.acceptance_factory(
                workspace_resolver=workspace,
                asset_resolver=resolver,
                config=config,
            )
        if not isinstance(acceptance, FullProductionAcceptance):
            raise TypeError(
                "acceptance_factory debe devolver FullProductionAcceptance."
            )

        adapter_config = dict(config)
        canonical_subtitles = True
        if self.render_provider == "json2video":
            adapter_config["json2video_subtitle_mode"] = "canonical_srt"
        return acceptance.prepare(
            project,
            asset_types_by_sequence=config["asset_types_by_sequence"],
            existing_asset_ids_by_sequence=config[
                "existing_asset_ids_by_sequence"
            ],
            stock_queries_by_sequence=config["stock_queries_by_sequence"],
            on_screen_text_mode=config["on_screen_text_mode"],
            adapter_factory=_adapter_factory(
                self.render_provider,
                config=adapter_config,
            ),
            payload_relative_path=_payload_relative_path(self.render_provider),
            canonical_subtitles=canonical_subtitles,
        )

    @staticmethod
    def _validate_zero_cost_ready(
        prepared: PreparedProduction,
        *,
        fulfillment: VisualAssetFulfillmentResult,
    ) -> None:
        evidence = prepared.evidence
        costs = (
            evidence.total_estimated_cost_usd,
            evidence.total_actual_cost_usd,
            fulfillment.resolution.bundle.total_estimated_cost_usd,
            fulfillment.resolution.bundle.total_actual_cost_usd,
        )
        if any(float(cost) != 0.0 for cost in costs):
            raise FAOPM9UnificationBlockedError(
                "FAO.5 detectó costo de assets distinto de cero y se detuvo."
            )
        if (
            evidence.unknown_cost_count
            or fulfillment.resolution.bundle.unknown_cost_count
        ):
            raise FAOPM9UnificationBlockedError(
                "FAO.5 detectó costos desconocidos y se detuvo."
            )
        if not evidence.ready_for_real_render or evidence.blockers:
            blockers = ", ".join(evidence.blockers) or "preparación no aprobada"
            raise FAOPM9UnificationBlockedError(
                "La preparación PM9 no quedó lista para render: " + blockers + "."
            )

    def _build_evidence(
        self,
        *,
        project: Path,
        request: Mapping[str, Any],
        derivation: ProductionDerivationResult,
        manifest: ProductionManifest,
        inventory: Mapping[str, Any],
        inventory_path: Path,
        source_assets: SourceAssetBuildResult,
        fulfillment: VisualAssetFulfillmentResult,
        prepared: PreparedProduction,
        telemetry_path: Path,
        input_fingerprint: str,
        delivery_base_uri: str,
        estimated_render_credits: int,
        network_called: bool,
    ) -> dict[str, Any]:
        canonical_path = (
            None
            if prepared.canonical_subtitles is None
            else prepared.canonical_subtitles.artifact_path
        )
        outputs = {
            "production_derivation": _file_ref(
                derivation.evidence_path,
                project,
            ),
            "asset_inventory": _file_ref(inventory_path, project),
            "source_asset_catalog": _file_ref(
                source_assets.catalog_path,
                project,
            ),
            "source_asset_report": _file_ref(
                source_assets.report_path,
                project,
            ),
            "fulfilled_asset_catalog": _file_ref(
                fulfillment.catalog_path,
                project,
            ),
            "visual_fulfillment_report": _file_ref(
                fulfillment.report_path,
                project,
            ),
            "pm9_preparation": _file_ref(prepared.preparation_path, project),
            "render_payload": _file_ref(prepared.payload_path, project),
        }
        if canonical_path is not None:
            outputs["canonical_subtitles"] = _file_ref(canonical_path, project)
        return {
            "schema_name": self.schema_name,
            "schema_version": self.schema_version,
            "status": "ready_for_render_authorization",
            "project_id": manifest.project.project_id,
            "topic": str(request["topic"]),
            "production_input_fingerprint": input_fingerprint,
            "engine": self.component_name,
            "engine_version": self.engine_version,
            "render_provider": self.render_provider,
            "delivery_base_uri": delivery_base_uri,
            "manifest_id": manifest.manifest_id,
            "manifest_sha256": prepared.evidence.manifest_sha256,
            "scene_count": len(manifest.scenes),
            "inventory_required_entries": inventory[
                "required_catalog_entries"
            ],
            "source_catalog_entries": len(source_assets.catalog.entries),
            "fulfilled_catalog_entries": len(fulfillment.catalog.entries),
            "persisted_asset_count": prepared.evidence.persisted_asset_count,
            "renderer_native_asset_count": (
                prepared.evidence.renderer_native_asset_count
            ),
            "resolution_id": prepared.evidence.resolution_id,
            "plan_id": prepared.evidence.plan_id,
            "submission_id": prepared.evidence.submission_id,
            "idempotency_key": prepared.evidence.idempotency_key,
            "canonical_subtitles_generated": canonical_path is not None,
            "narration_conformance_required": (
                prepared.evidence.narration_conformance_required
            ),
            "narration_conformance_approved": (
                prepared.evidence.narration_conformance_approved
            ),
            "ready_for_real_render": True,
            "estimated_render_credits": estimated_render_credits,
            "render_authorization_required": True,
            "total_estimated_asset_cost_usd": 0.0,
            "total_actual_cost_usd": 0.0,
            "unknown_cost_count": 0,
            "free_tier_default": True,
            "f3_artifacts_persisted": True,
            "f7_review_state": "not_started",
            "f7_review_performed": False,
            "f8_preparation_telemetry_persisted": True,
            "f8_telemetry_path": _relative(telemetry_path, project),
            "outputs": outputs,
            "network_called": network_called,
            "paid_provider_called": False,
            "render_performed": False,
            "publication_performed": False,
        }

    def _reuse_existing(
        self,
        project: Path,
        *,
        input_fingerprint: str,
        provider: str,
    ) -> FAOPM9UnificationResult | None:
        path = project / UNIFICATION_RELATIVE_PATH
        if not path.is_file():
            return None
        try:
            evidence = _read_json_object(path, "evidencia FAO.5")
            if (
                evidence.get("schema_name") != self.schema_name
                or evidence.get("schema_version") != self.schema_version
                or evidence.get("status") != "ready_for_render_authorization"
                or evidence.get("production_input_fingerprint")
                != input_fingerprint
                or evidence.get("render_provider") != provider
                or evidence.get("ready_for_real_render") is not True
                or evidence.get("total_actual_cost_usd") != 0.0
                or evidence.get("unknown_cost_count") != 0
                or evidence.get("paid_provider_called") is not False
                or evidence.get("render_performed") is not False
                or evidence.get("f7_review_performed") is not False
                or evidence.get("publication_performed") is not False
            ):
                return None
            outputs = evidence.get("outputs")
            if not isinstance(outputs, Mapping):
                return None
            for raw_ref in outputs.values():
                if not isinstance(raw_ref, Mapping):
                    return None
                output = _project_file(project, raw_ref.get("path"))
                if (
                    not output.is_file()
                    or _file_sha256(output) != raw_ref.get("sha256")
                ):
                    return None
            telemetry = _project_file(
                project,
                evidence.get("f8_telemetry_path"),
            )
            if not telemetry.is_file() or telemetry.stat().st_size <= 0:
                return None
            self._guard_no_render_outputs(project)
            return self._result_from_evidence(
                project,
                evidence,
                reused_existing=True,
            )
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            return None

    @staticmethod
    def _input_fingerprint(
        derivation: ProductionDerivationResult,
        *,
        provider: str,
        delivery_base_uri: str,
    ) -> str:
        return _mapping_sha256(
            {
                "engine": "fao_pm9_unification_engine",
                "engine_version": "1.0",
                "provider": provider,
                "delivery_base_uri": delivery_base_uri,
                "production_input_fingerprint": derivation.input_fingerprint,
                "production_manifest_sha256": derivation.manifest_sha256,
                "production_config_sha256": derivation.config_sha256,
                "production_derivation_sha256": derivation.evidence_sha256,
            }
        )

    @staticmethod
    def _result_from_evidence(
        project: Path,
        evidence: Mapping[str, Any],
        *,
        reused_existing: bool,
    ) -> FAOPM9UnificationResult:
        outputs = evidence["outputs"]
        canonical = outputs.get("canonical_subtitles")
        return FAOPM9UnificationResult(
            project_path=project,
            evidence_path=project / UNIFICATION_RELATIVE_PATH,
            provider=str(evidence["render_provider"]),
            ready_for_real_render=bool(evidence["ready_for_real_render"]),
            estimated_render_credits=int(evidence["estimated_render_credits"]),
            total_actual_cost_usd=float(evidence["total_actual_cost_usd"]),
            persisted_asset_count=int(evidence["persisted_asset_count"]),
            inventory_path=_project_file(
                project,
                outputs["asset_inventory"]["path"],
            ),
            catalog_path=_project_file(
                project,
                outputs["fulfilled_asset_catalog"]["path"],
            ),
            preparation_path=_project_file(
                project,
                outputs["pm9_preparation"]["path"],
            ),
            payload_path=_project_file(
                project,
                outputs["render_payload"]["path"],
            ),
            canonical_subtitles_path=(
                None
                if canonical is None
                else _project_file(project, canonical["path"])
            ),
            network_called=bool(evidence["network_called"]),
            reused_existing=reused_existing,
        )


def _workspace_for(project: Path) -> WorkspaceResolver:
    if not project.is_dir():
        raise FAOPM9UnificationBlockedError(
            f"No existe el proyecto FAO: {project}"
        )
    projects_root = project.parent
    if projects_root.name != "04_PROYECTOS":
        raise FAOPM9UnificationBlockedError(
            "El proyecto FAO debe estar dentro de 04_PROYECTOS."
        )
    return WorkspaceResolver(
        projects_root=projects_root,
        outputs_root=projects_root.parent / "05_OUTPUTS",
    )


def _file_ref(path: Path, project: Path) -> dict[str, Any]:
    resolved = path.resolve(strict=False)
    if not resolved.is_file() or resolved.stat().st_size <= 0:
        raise FAOPM9UnificationError(f"Falta el artefacto FAO.5: {resolved}")
    return {
        "path": _relative(resolved, project),
        "sha256": _file_sha256(resolved),
        "size_bytes": resolved.stat().st_size,
    }


def _project_file(project: Path, value: Any) -> Path:
    text = str(value or "").strip().replace("\\", "/")
    if (
        not text
        or PurePosixPath(text).is_absolute()
        or PureWindowsPath(text).is_absolute()
        or any(part in {"", ".", ".."} for part in PurePosixPath(text).parts)
    ):
        raise ValueError("La evidencia FAO.5 contiene una ruta no confinada.")
    path = (project / Path(text)).resolve(strict=False)
    path.relative_to(project.resolve(strict=False))
    return path


def _relative(path: Path, project: Path) -> str:
    return path.resolve(strict=False).relative_to(
        project.resolve(strict=False)
    ).as_posix()


def _read_json_object(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise FAOPM9UnificationBlockedError(
            f"No fue posible leer {label}: {error}"
        ) from error
    if not isinstance(value, dict):
        raise FAOPM9UnificationBlockedError(
            f"{label} debe contener un objeto JSON."
        )
    return value


def _json_bytes(value: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(
            dict(value),
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _mapping_sha256(value: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        dict(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return _sha256(encoded)


def _catalog_sha256(catalog: ApprovedAssetCatalog) -> str:
    return _mapping_sha256(catalog.model_dump(mode="json"))


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


__all__ = [
    "FAOPM9UnificationBlockedError",
    "FAOPM9UnificationEngine",
    "FAOPM9UnificationError",
    "FAOPM9UnificationResult",
    "UNIFICATION_RELATIVE_PATH",
]
