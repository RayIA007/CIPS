"""Derive reproducible production inputs from a verified FAO editorial package.

FAO.4 reuses the provider-neutral PM2 compiler and PM3 creative planner.  This
boundary validates the complete FAO.3 package, derives a planned
``ProductionManifest`` plus the PM9-compatible project configuration, and
persists deterministic evidence without contacting providers, rendering, or
publishing.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

from artifact_store import CollisionPolicy
from creative_direction_planner import CreativeDirectionPlanner
from editorial_contract import EDITORIAL_STAGES
from metadata_store import MetadataStore
from production_acceptance.models import FrameRatePolicy
from production_acceptance.narration_conformance import NarrationConformancePolicy
from production_manifest import (
    AssetType,
    ProductionManifest,
    deserialize_manifest,
    serialize_manifest,
)
from production_manifest_compiler import ProductionManifestCompiler
from style_profiles import IMMERSIVE_PROCESS_EXPLAINER_ID
from workspace_resolver import WorkspaceResolver


PRODUCTION_MANIFEST_PATH = Path("production_manifest.json")
PRODUCTION_CONFIG_PATH = Path("production_acceptance_config.json")
PRODUCTION_DERIVATION_PATH = Path("state") / "production_derivation.json"

_CONFIG_SCHEMA = "cips.production_acceptance.project_config"
_DERIVATION_SCHEMA = "cips.fao.production_derivation"
_OPERATIONAL_REQUEST_SCHEMA = "cips.fao.operational_request"
_EDITORIAL_PACKAGE_SCHEMA = "cips.fao.editorial_package"
_STOCK_ASSET_TYPES = frozenset({AssetType.STOCK_IMAGE, AssetType.STOCK_VIDEO})
_FREE_TIER_FALLBACK_TYPES = frozenset(
    {AssetType.AI_IMAGE, AssetType.AI_VIDEO, AssetType.STOCK_VIDEO}
)
_CONFIG_ALLOWED_KEYS = frozenset(
    {
        "schema_name",
        "schema_version",
        "asset_types_by_sequence",
        "existing_asset_ids_by_sequence",
        "stock_queries_by_sequence",
        "catalog_relative_path",
        "assets_root_relative_path",
        "fulfillment_report_relative_path",
        "on_screen_text_mode",
        "frame_rate_policy",
        "narration_conformance_policy",
    }
)


class ProductionDerivationError(ValueError):
    """Base error for an invalid or non-reproducible FAO.4 derivation."""


class EditorialPackageValidationError(ProductionDerivationError):
    """The FAO.3 package or one of its physical inputs is inconsistent."""


class ProductionConfigurationValidationError(ProductionDerivationError):
    """The generated PM9-compatible configuration is internally inconsistent."""


@dataclass(frozen=True, slots=True)
class ProductionDerivationResult:
    """Validated FAO.4 outputs and their deterministic physical evidence."""

    manifest: ProductionManifest
    manifest_path: Path
    config_path: Path
    evidence_path: Path
    manifest_sha256: str
    config_sha256: str
    evidence_sha256: str
    input_fingerprint: str
    reused_existing: bool

    def metadata(self) -> dict[str, Any]:
        return {
            "manifest_id": self.manifest.manifest_id,
            "production_manifest_path": str(self.manifest_path),
            "production_manifest_sha256": self.manifest_sha256,
            "production_config_path": str(self.config_path),
            "production_config_sha256": self.config_sha256,
            "production_derivation_path": str(self.evidence_path),
            "production_derivation_sha256": self.evidence_sha256,
            "production_input_fingerprint": self.input_fingerprint,
            "production_derivation_reused": self.reused_existing,
            "network_called": False,
            "paid_provider_called": False,
            "render_performed": False,
            "publication_performed": False,
        }


class ProductionDerivationEngine:
    """Produce all FAO.4 inputs from the verified FAO.3 editorial package."""

    component_name = "production_derivation_engine"
    schema_name = _DERIVATION_SCHEMA
    schema_version = "1.0"
    engine_version = "1.0"
    free_tier_policy = "free-tier-stock-and-renderer-native-v1"

    def __init__(
        self,
        *,
        workspace_resolver: WorkspaceResolver | None = None,
        metadata_store: MetadataStore | None = None,
        compiler: ProductionManifestCompiler | None = None,
        planner: CreativeDirectionPlanner | None = None,
    ) -> None:
        if metadata_store is not None and workspace_resolver is not None:
            if metadata_store.workspace_resolver is not workspace_resolver:
                raise ValueError(
                    "metadata_store y workspace_resolver deben compartir la misma instancia."
                )
        self._dynamic_workspace = all(
            value is None
            for value in (workspace_resolver, metadata_store, compiler, planner)
        )
        if self._dynamic_workspace:
            self._metadata_store: MetadataStore | None = None
            self._compiler: ProductionManifestCompiler | None = None
            self._planner: CreativeDirectionPlanner | None = None
        else:
            resolver = workspace_resolver or WorkspaceResolver()
            store = metadata_store or MetadataStore(resolver)
            self._metadata_store = store
            self._compiler = compiler or ProductionManifestCompiler(
                metadata_store=store,
            )
            self._planner = planner or CreativeDirectionPlanner(
                metadata_store=store,
            )

    def derive_and_persist(self, project_path: str | Path) -> ProductionDerivationResult:
        """Validate, derive, persist, and verify the complete FAO.4 output set."""

        project = Path(project_path).expanduser().resolve(strict=False)
        self._ensure_components(project)
        assert self._compiler is not None
        assert self._planner is not None
        request_path = project / "operational_request.json"
        package_path = project / "state" / "editorial_package.json"
        request = self._read_json_object(request_path, "solicitud operativa")
        package = self._read_json_object(package_path, "paquete editorial")
        artifact_inputs = self._validate_editorial_inputs(
            project=project,
            request_path=request_path,
            request=request,
            package_path=package_path,
            package=package,
        )

        compiler_configuration = {
            "title": str(request["topic"]),
            "platform": str(request["platform"]),
            "target_duration_seconds": int(request["duration_seconds"]),
            "style_profile": IMMERSIVE_PROCESS_EXPLAINER_ID,
        }
        base_manifest = self._compiler.compile(
            project,
            configuration=compiler_configuration,
        )
        auto_planned = self._planner.plan(
            base_manifest,
            on_screen_text_mode="captions_only",
        )
        asset_types = self._asset_types_for_policy(
            auto_planned,
            free_tier_default=bool(request.get("free_tier_default", True)),
        )
        planned = self._planner.plan(
            base_manifest,
            asset_types=asset_types,
            on_screen_text_mode="captions_only",
        )
        manifest_bytes = serialize_manifest(planned).encode("utf-8")
        manifest_sha256 = self._sha256(manifest_bytes)

        config = self._build_production_config(planned)
        self.validate_production_config(config, planned)
        config_bytes = self._json_bytes(config)
        config_sha256 = self._sha256(config_bytes)

        input_fingerprint = self._input_fingerprint(
            request_path=request_path,
            package_path=package_path,
            artifact_inputs=artifact_inputs,
            request=request,
        )
        evidence = self._build_evidence(
            project=project,
            request=request,
            package_path=package_path,
            artifact_inputs=artifact_inputs,
            planned=planned,
            manifest_sha256=manifest_sha256,
            config=config,
            config_sha256=config_sha256,
            input_fingerprint=input_fingerprint,
        )
        evidence_bytes = self._json_bytes(evidence)
        evidence_sha256 = self._sha256(evidence_bytes)

        manifest_path = project / PRODUCTION_MANIFEST_PATH
        config_path = project / PRODUCTION_CONFIG_PATH
        evidence_path = project / PRODUCTION_DERIVATION_PATH
        reused_existing = self._outputs_are_identical(
            manifest_path=manifest_path,
            manifest_bytes=manifest_bytes,
            config_path=config_path,
            config_bytes=config_bytes,
            evidence_path=evidence_path,
            evidence_bytes=evidence_bytes,
        )

        if not reused_existing:
            self._persist_json(
                project=project,
                relative_path=PRODUCTION_MANIFEST_PATH,
                content=manifest_bytes,
                artifact_type="production_manifest",
                artifact_id=f"fao4-manifest-{manifest_sha256[:32]}",
                metadata={
                    "manifest_id": planned.manifest_id,
                    "derivation_engine": self.component_name,
                    "input_fingerprint": input_fingerprint,
                },
            )
            self._persist_json(
                project=project,
                relative_path=PRODUCTION_CONFIG_PATH,
                content=config_bytes,
                artifact_type="production_acceptance_config",
                artifact_id=f"fao4-config-{config_sha256[:32]}",
                metadata={
                    "schema_name": _CONFIG_SCHEMA,
                    "manifest_id": planned.manifest_id,
                    "input_fingerprint": input_fingerprint,
                },
            )
            self._persist_json(
                project=project,
                relative_path=PRODUCTION_DERIVATION_PATH,
                content=evidence_bytes,
                artifact_type="production_derivation_evidence",
                artifact_id=f"fao4-evidence-{evidence_sha256[:32]}",
                metadata={
                    "schema_name": self.schema_name,
                    "manifest_id": planned.manifest_id,
                    "input_fingerprint": input_fingerprint,
                },
            )

        self._verify_readback(
            manifest_path=manifest_path,
            expected_manifest=planned,
            expected_manifest_bytes=manifest_bytes,
            config_path=config_path,
            expected_config=config,
            evidence_path=evidence_path,
            expected_evidence=evidence,
        )
        return ProductionDerivationResult(
            manifest=planned,
            manifest_path=manifest_path,
            config_path=config_path,
            evidence_path=evidence_path,
            manifest_sha256=manifest_sha256,
            config_sha256=config_sha256,
            evidence_sha256=evidence_sha256,
            input_fingerprint=input_fingerprint,
            reused_existing=reused_existing,
        )

    def _ensure_components(self, project: Path) -> None:
        if not self._dynamic_workspace or self._metadata_store is not None:
            return
        resolver = WorkspaceResolver(
            projects_root=project.parent,
            outputs_root=project.parent.parent / "05_OUTPUTS",
        )
        store = MetadataStore(resolver)
        self._metadata_store = store
        self._compiler = ProductionManifestCompiler(metadata_store=store)
        self._planner = CreativeDirectionPlanner(metadata_store=store)

    @classmethod
    def validate_production_config(
        cls,
        config: Mapping[str, Any],
        manifest: ProductionManifest,
    ) -> None:
        """Validate the generated project config against its planned manifest."""

        if not isinstance(config, Mapping):
            raise ProductionConfigurationValidationError(
                "La configuración de producción debe ser un objeto JSON."
            )
        unknown = sorted(set(config) - _CONFIG_ALLOWED_KEYS)
        if unknown:
            raise ProductionConfigurationValidationError(
                "Campos de configuración no soportados: " + ", ".join(unknown) + "."
            )
        if config.get("schema_name") != _CONFIG_SCHEMA:
            raise ProductionConfigurationValidationError(
                "schema_name de configuración de producción inválido."
            )
        if config.get("schema_version") != "1.0":
            raise ProductionConfigurationValidationError(
                "schema_version de configuración de producción no soportado."
            )

        expected_sequences = {scene.sequence for scene in manifest.scenes}
        asset_types = cls._sequence_mapping(
            config.get("asset_types_by_sequence"),
            label="asset_types_by_sequence",
            value_type=AssetType,
        )
        if set(asset_types) != expected_sequences:
            raise ProductionConfigurationValidationError(
                "asset_types_by_sequence debe cubrir exactamente todas las escenas."
            )
        expected_types = {
            scene.sequence: scene.asset_request.asset_type for scene in manifest.scenes
        }
        if asset_types != expected_types:
            raise ProductionConfigurationValidationError(
                "Los tipos de activos no coinciden con el ProductionManifest."
            )

        existing_ids = cls._sequence_mapping(
            config.get("existing_asset_ids_by_sequence", {}),
            label="existing_asset_ids_by_sequence",
            value_type=str,
        )
        stock_queries = cls._sequence_mapping(
            config.get("stock_queries_by_sequence", {}),
            label="stock_queries_by_sequence",
            value_type=str,
        )
        expected_existing = {
            scene.sequence: str(scene.asset_request.existing_asset_id)
            for scene in manifest.scenes
            if scene.asset_request.asset_type is AssetType.EXISTING_ASSET
        }
        expected_stock = {
            scene.sequence: str(scene.asset_request.stock_query)
            for scene in manifest.scenes
            if scene.asset_request.asset_type in _STOCK_ASSET_TYPES
        }
        if existing_ids != expected_existing:
            raise ProductionConfigurationValidationError(
                "Las referencias de activos existentes no coinciden con el manifest."
            )
        if stock_queries != expected_stock:
            raise ProductionConfigurationValidationError(
                "Las consultas stock no coinciden con el manifest creativo."
            )
        if config.get("on_screen_text_mode") != "captions_only":
            raise ProductionConfigurationValidationError(
                "FAO.4 requiere on_screen_text_mode='captions_only'."
            )

        for field in (
            "catalog_relative_path",
            "assets_root_relative_path",
            "fulfillment_report_relative_path",
        ):
            cls._safe_relative(config.get(field), field)
        try:
            FrameRatePolicy.model_validate(config.get("frame_rate_policy", {}))
            NarrationConformancePolicy.model_validate(
                config.get("narration_conformance_policy", {})
            )
        except ValueError as error:
            raise ProductionConfigurationValidationError(str(error)) from error

    def _validate_editorial_inputs(
        self,
        *,
        project: Path,
        request_path: Path,
        request: dict[str, Any],
        package_path: Path,
        package: dict[str, Any],
    ) -> tuple[dict[str, Any], ...]:
        if request.get("schema_name") != _OPERATIONAL_REQUEST_SCHEMA:
            raise EditorialPackageValidationError(
                "La solicitud operativa no usa el schema FAO esperado."
            )
        if request.get("schema_version") != "1.0":
            raise EditorialPackageValidationError(
                "La solicitud operativa usa una versión no soportada."
            )
        if request.get("publication_performed") is not False:
            raise EditorialPackageValidationError(
                "publication_performed debe permanecer en false."
            )
        required_request = (
            "project_id",
            "topic",
            "platform",
            "duration_seconds",
            "audience",
            "creative_style",
        )
        missing_request = [field for field in required_request if request.get(field) in (None, "")]
        if missing_request:
            raise EditorialPackageValidationError(
                "La solicitud operativa está incompleta: " + ", ".join(missing_request) + "."
            )

        if package.get("schema_name") != _EDITORIAL_PACKAGE_SCHEMA:
            raise EditorialPackageValidationError(
                "El paquete editorial no usa el schema FAO.3 esperado."
            )
        if package.get("schema_version") != "1.0" or package.get("status") != "editorial_complete":
            raise EditorialPackageValidationError(
                "El paquete editorial no está completo o usa una versión no soportada."
            )
        if package.get("project_id") != request.get("project_id"):
            raise EditorialPackageValidationError(
                "El paquete editorial no pertenece a la solicitud operativa."
            )
        if package.get("publication_performed") is not False:
            raise EditorialPackageValidationError(
                "El paquete editorial no conserva publication_performed=false."
            )
        if not package.get("semantic_validation") or not package.get(
            "factual_traceability_validation"
        ):
            raise EditorialPackageValidationError(
                "El paquete editorial no acredita las validaciones FAO.3."
            )
        if package.get("placeholder_files") != []:
            raise EditorialPackageValidationError(
                "El paquete editorial contiene archivos pendientes."
            )

        evidence_relative = self._safe_relative(package.get("evidence_path"), "evidence_path")
        evidence_path = (project / evidence_relative).resolve(strict=False)
        if not evidence_path.is_file() or self._file_sha256(evidence_path) != package.get(
            "evidence_sha256"
        ):
            raise EditorialPackageValidationError(
                "La evidencia editorial física no coincide con el paquete FAO.3."
            )

        raw_artifacts = package.get("artifacts")
        if not isinstance(raw_artifacts, list):
            raise EditorialPackageValidationError(
                "El paquete editorial no contiene una lista de artefactos."
            )
        if package.get("artifact_count") != len(raw_artifacts):
            raise EditorialPackageValidationError(
                "artifact_count no coincide con los artefactos editoriales."
            )
        expected_stages = list(EDITORIAL_STAGES)
        actual_stages = [item.get("stage") for item in raw_artifacts if isinstance(item, Mapping)]
        if actual_stages != expected_stages:
            raise EditorialPackageValidationError(
                "Los artefactos del paquete no cubren los Stages editoriales en orden."
            )

        artifacts: list[dict[str, Any]] = []
        for item in raw_artifacts:
            if not isinstance(item, Mapping):
                raise EditorialPackageValidationError(
                    "El paquete editorial contiene una entrada de artefacto inválida."
                )
            relative = self._safe_relative(item.get("path"), "artifact.path")
            path = (project / relative).resolve(strict=False)
            if not path.is_file():
                raise EditorialPackageValidationError(
                    f"No existe el artefacto editorial '{relative}'."
                )
            actual_hash = self._file_sha256(path)
            if actual_hash != item.get("sha256"):
                raise EditorialPackageValidationError(
                    f"El hash físico de '{item.get('stage')}' no coincide con FAO.3."
                )
            artifacts.append(
                {
                    "stage": str(item["stage"]),
                    "path": relative.as_posix(),
                    "sha256": actual_hash,
                }
            )

        package_topics = (
            "topic",
            "platform",
            "duration_seconds",
            "audience",
            "creative_style",
        )
        if any(package.get(field) != request.get(field) for field in package_topics):
            raise EditorialPackageValidationError(
                "El paquete editorial no conserva la solicitud operativa autoritativa."
            )
        if not request_path.is_file() or not package_path.is_file():
            raise EditorialPackageValidationError(
                "Faltan las entradas físicas de la derivación FAO.4."
            )
        return tuple(artifacts)

    @staticmethod
    def _asset_types_for_policy(
        manifest: ProductionManifest,
        *,
        free_tier_default: bool,
    ) -> dict[str, AssetType]:
        selected: dict[str, AssetType] = {}
        for scene in manifest.scenes:
            asset_type = scene.asset_request.asset_type
            if free_tier_default and asset_type in _FREE_TIER_FALLBACK_TYPES:
                asset_type = AssetType.STOCK_IMAGE
            selected[scene.scene_id] = asset_type
        return selected

    @staticmethod
    def _build_production_config(manifest: ProductionManifest) -> dict[str, Any]:
        asset_types = {
            str(scene.sequence): scene.asset_request.asset_type.value
            for scene in manifest.scenes
        }
        existing_ids = {
            str(scene.sequence): scene.asset_request.existing_asset_id
            for scene in manifest.scenes
            if scene.asset_request.asset_type is AssetType.EXISTING_ASSET
        }
        stock_queries = {
            str(scene.sequence): scene.asset_request.stock_query
            for scene in manifest.scenes
            if scene.asset_request.asset_type in _STOCK_ASSET_TYPES
        }
        language = manifest.locale.split("-", 1)[0].casefold()
        if len(language) not in {2, 3} or not language.isalpha():
            language = "es"
        return {
            "schema_name": _CONFIG_SCHEMA,
            "schema_version": "1.0",
            "asset_types_by_sequence": asset_types,
            "existing_asset_ids_by_sequence": existing_ids,
            "stock_queries_by_sequence": stock_queries,
            "catalog_relative_path": "source_assets/automated_asset_catalog.json",
            "assets_root_relative_path": "source_assets",
            "fulfillment_report_relative_path": (
                "acceptance/visual_asset_fulfillment.json"
            ),
            "on_screen_text_mode": "captions_only",
            "frame_rate_policy": {
                "mode": "normalize_to_manifest",
                "accepted_source_fps": [25.0],
                "tolerance_fps": 0.15,
            },
            "narration_conformance_policy": {
                "enabled": True,
                "engine": "faster_whisper",
                "model": "small",
                "adjudication_model": "medium",
                "language": language,
                "device": "cpu",
                "compute_type": "int8",
                "word_timestamps": True,
                "vad_filter": True,
                "comparison": "exact_lexical",
                "automatic_script_rewrite": False,
            },
        }

    def _input_fingerprint(
        self,
        *,
        request_path: Path,
        package_path: Path,
        artifact_inputs: tuple[dict[str, Any], ...],
        request: Mapping[str, Any],
    ) -> str:
        assert self._compiler is not None
        assert self._planner is not None
        payload = {
            "engine": self.component_name,
            "engine_version": self.engine_version,
            "compiler_version": self._compiler.compiler_version,
            "planner_version": self._planner.planner_version,
            "free_tier_policy": self.free_tier_policy,
            "free_tier_default": bool(request.get("free_tier_default", True)),
            "operational_request_sha256": self._file_sha256(request_path),
            "editorial_package_sha256": self._file_sha256(package_path),
            "editorial_artifacts": list(artifact_inputs),
        }
        return self._sha256(self._canonical_bytes(payload))

    def _build_evidence(
        self,
        *,
        project: Path,
        request: Mapping[str, Any],
        package_path: Path,
        artifact_inputs: tuple[dict[str, Any], ...],
        planned: ProductionManifest,
        manifest_sha256: str,
        config: Mapping[str, Any],
        config_sha256: str,
        input_fingerprint: str,
    ) -> dict[str, Any]:
        assert self._compiler is not None
        assert self._planner is not None
        return {
            "schema_name": self.schema_name,
            "schema_version": self.schema_version,
            "status": "production_inputs_ready",
            "project_id": str(request["project_id"]),
            "input_fingerprint": input_fingerprint,
            "operational_request_path": "operational_request.json",
            "operational_request_sha256": self._file_sha256(
                project / "operational_request.json"
            ),
            "editorial_package_path": package_path.relative_to(project).as_posix(),
            "editorial_package_sha256": self._file_sha256(package_path),
            "editorial_artifacts": list(artifact_inputs),
            "production_manifest_path": PRODUCTION_MANIFEST_PATH.as_posix(),
            "production_manifest_sha256": manifest_sha256,
            "manifest_id": planned.manifest_id,
            "style_profile": planned.style_profile,
            "scene_count": len(planned.scenes),
            "production_config_path": PRODUCTION_CONFIG_PATH.as_posix(),
            "production_config_sha256": config_sha256,
            "asset_types_by_sequence": dict(config["asset_types_by_sequence"]),
            "stock_queries_by_sequence": dict(config["stock_queries_by_sequence"]),
            "compiler": self._compiler.compiler_name,
            "compiler_version": self._compiler.compiler_version,
            "planner": self._planner.planner_name,
            "planner_version": self._planner.planner_version,
            "derivation_engine": self.component_name,
            "derivation_engine_version": self.engine_version,
            "free_tier_default": bool(request.get("free_tier_default", True)),
            "free_tier_policy": self.free_tier_policy,
            "configuration_validated": True,
            "manifest_validated": True,
            "network_called": False,
            "paid_provider_called": False,
            "render_performed": False,
            "publication_performed": False,
        }

    def _persist_json(
        self,
        *,
        project: Path,
        relative_path: Path,
        content: bytes,
        artifact_type: str,
        artifact_id: str,
        metadata: Mapping[str, Any],
    ) -> None:
        assert self._metadata_store is not None
        result = self._metadata_store.persist_bytes(
            workspace_root=project,
            relative_path=relative_path,
            content=content,
            artifact_type=artifact_type,
            mime_type="application/json",
            artifact_id=artifact_id,
            metadata=metadata,
            collision_policy=CollisionPolicy.REPLACE,
        )
        expected_path = (project / relative_path).resolve(strict=False)
        if Path(result.artifact.path).resolve(strict=False) != expected_path:
            raise ProductionDerivationError(
                f"F3 no persistió '{relative_path}' en la ruta canónica esperada."
            )

    def _verify_readback(
        self,
        *,
        manifest_path: Path,
        expected_manifest: ProductionManifest,
        expected_manifest_bytes: bytes,
        config_path: Path,
        expected_config: Mapping[str, Any],
        evidence_path: Path,
        expected_evidence: Mapping[str, Any],
    ) -> None:
        if manifest_path.read_bytes() != expected_manifest_bytes:
            raise ProductionDerivationError(
                "El ProductionManifest persistido no conserva los bytes derivados."
            )
        if deserialize_manifest(manifest_path.read_bytes()) != expected_manifest:
            raise ProductionDerivationError(
                "El ProductionManifest persistido no supera la validación PM1."
            )
        config = self._read_json_object(config_path, "configuración de producción")
        self.validate_production_config(config, expected_manifest)
        if config != dict(expected_config):
            raise ProductionDerivationError(
                "La configuración persistida no coincide con la configuración derivada."
            )
        evidence = self._read_json_object(evidence_path, "evidencia de derivación")
        if evidence != dict(expected_evidence):
            raise ProductionDerivationError(
                "La evidencia persistida no coincide con la derivación FAO.4."
            )

    @staticmethod
    def _outputs_are_identical(
        *,
        manifest_path: Path,
        manifest_bytes: bytes,
        config_path: Path,
        config_bytes: bytes,
        evidence_path: Path,
        evidence_bytes: bytes,
    ) -> bool:
        expected = (
            (manifest_path, manifest_bytes),
            (config_path, config_bytes),
            (evidence_path, evidence_bytes),
        )
        return all(path.is_file() and path.read_bytes() == content for path, content in expected)

    @staticmethod
    def _sequence_mapping(
        value: Any,
        *,
        label: str,
        value_type: type[AssetType] | type[str],
    ) -> dict[int, Any]:
        if not isinstance(value, Mapping):
            raise ProductionConfigurationValidationError(f"{label} debe ser un objeto JSON.")
        normalized: dict[int, Any] = {}
        for raw_sequence, raw_value in value.items():
            try:
                sequence = int(raw_sequence)
            except (TypeError, ValueError) as error:
                raise ProductionConfigurationValidationError(
                    f"{label} contiene una secuencia no numérica."
                ) from error
            if sequence < 1 or str(sequence) != str(raw_sequence):
                raise ProductionConfigurationValidationError(
                    f"{label} contiene una secuencia inválida: {raw_sequence!r}."
                )
            try:
                converted = value_type(raw_value)
            except (TypeError, ValueError) as error:
                raise ProductionConfigurationValidationError(
                    f"{label} contiene un valor inválido para la escena {sequence}."
                ) from error
            if value_type is str:
                converted = str(converted).strip()
                if not converted:
                    raise ProductionConfigurationValidationError(
                        f"{label} contiene texto vacío para la escena {sequence}."
                    )
            normalized[sequence] = converted
        return normalized

    @staticmethod
    def _safe_relative(value: Any, label: str) -> Path:
        text = str(value or "").strip().replace("\\", "/")
        if not text:
            raise ProductionConfigurationValidationError(f"{label} no puede estar vacío.")
        if PurePosixPath(text).is_absolute() or PureWindowsPath(text).is_absolute():
            raise ProductionConfigurationValidationError(f"{label} debe ser una ruta relativa.")
        path = Path(text)
        if any(part in {"", ".", ".."} for part in PurePosixPath(text).parts):
            raise ProductionConfigurationValidationError(
                f"{label} contiene un segmento de ruta no permitido."
            )
        return path

    @staticmethod
    def _read_json_object(path: Path, label: str) -> dict[str, Any]:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError as error:
            raise EditorialPackageValidationError(f"Falta {label}: {path}") from error
        except (OSError, json.JSONDecodeError) as error:
            raise EditorialPackageValidationError(f"No fue posible leer {label}: {error}") from error
        if not isinstance(data, dict):
            raise EditorialPackageValidationError(f"{label} debe tener una raíz JSON object.")
        return data

    @staticmethod
    def _canonical_bytes(value: Mapping[str, Any]) -> bytes:
        return json.dumps(
            dict(value),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")

    @staticmethod
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

    @staticmethod
    def _sha256(content: bytes) -> str:
        return hashlib.sha256(content).hexdigest()

    @classmethod
    def _file_sha256(cls, path: Path) -> str:
        return cls._sha256(path.read_bytes())


__all__ = [
    "EditorialPackageValidationError",
    "PRODUCTION_CONFIG_PATH",
    "PRODUCTION_DERIVATION_PATH",
    "PRODUCTION_MANIFEST_PATH",
    "ProductionConfigurationValidationError",
    "ProductionDerivationEngine",
    "ProductionDerivationError",
    "ProductionDerivationResult",
]
