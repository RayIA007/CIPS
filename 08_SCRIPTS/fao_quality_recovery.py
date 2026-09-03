"""FAO.6 quality, recovery and operator-diagnostic boundary.

This module consumes the durable FAO.5 preparation and stops before render.
It performs physical source and delivery checks, reuses the existing acoustic
gate evidence, verifies editorial/visual/technical quality, and persists a
single fail-closed report with recovery guidance suitable for a non-expert
operator.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
import hashlib
import ipaddress
import json
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import socket
from typing import Any
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from artifact_store import CollisionPolicy
from asset_resolution import MediaFamily
from asset_resolution.wikimedia_commons import image_dimensions
from editorial_contract import EDITORIAL_STAGES, canonical_editorial_path
from editorial_validator import EditorialValidatorEngine
from metadata_store import MetadataStore
from production_acceptance import (
    ApprovedAssetCatalog,
    ProductionPreparationEvidence,
    SourceAssetBuildError,
    inspect_narration_conformance,
    verify_catalog_delivery,
)
from production_manifest import AssetType, ProductionManifest, deserialize_manifest
from run_pm9_full_production_acceptance import _load_project_config
from telemetry_engine import TelemetryEngine
from telemetry_models import TelemetryEvent
from workspace_resolver import WorkspaceResolver


QUALITY_REPORT_RELATIVE_PATH = Path("state") / "fao_quality_recovery.json"
_SCHEMA_NAME = "cips.fao.quality_recovery"
_SCHEMA_VERSION = "1.0"
_UNIFICATION_RELATIVE_PATH = Path("state") / "fao_pm9_unification.json"
_RENDER_OUTPUTS = (
    Path("render") / "creatomate_result.json",
    Path("render") / "json2video_result.json",
    Path("acceptance") / "final_acceptance.json",
    Path("final") / "short.mp4",
)
_PHYSICAL_VISUAL_TYPES = frozenset(
    {AssetType.STOCK_IMAGE, AssetType.STOCK_VIDEO, AssetType.EXISTING_ASSET}
)
_RENDERER_NATIVE_TYPES = frozenset(
    {AssetType.MOTION_GRAPHIC, AssetType.TEXT_GRAPHIC}
)
_WORD_RE = re.compile(r"[a-záéíóúüñ0-9]+", re.IGNORECASE)
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")
_SOURCE_LINE_RE = re.compile(
    r"^.*\[(F\d+)\].*?(https?://[^\s)>\]]+).*$",
    re.IGNORECASE | re.MULTILINE,
)
_MAX_SOURCE_BYTES = 2 * 1024 * 1024
_MAX_ASSET_BYTES = 64 * 1024 * 1024

_STOPWORDS = frozenset(
    {
        "a", "al", "como", "con", "de", "del", "el", "en", "es",
        "esta", "este", "la", "las", "lo", "los", "o", "para", "por",
        "que", "se", "sin", "su", "un", "una", "y", "the", "of", "to",
        "in", "and", "is", "for", "on", "with", "from", "this", "that",
    }
)

SourceFetcher = Callable[[str], "SourceFetchResult"]
AssetFetcher = Callable[[str], bytes]
Clock = Callable[[], datetime]


class FAOQualityRecoveryError(RuntimeError):
    """FAO.6 could not build trustworthy quality evidence."""


class FAOQualityRecoveryBlockedError(FAOQualityRecoveryError):
    """FAO.6 stopped safely and exposes durable operator guidance."""

    def __init__(self, result: "FAOQualityRecoveryResult") -> None:
        self.result = result
        self.operator_message = result.operator_message
        self.recovery_steps = result.recovery_steps
        super().__init__(result.operator_message)


@dataclass(frozen=True, slots=True)
class SourceFetchResult:
    """Bounded textual response observed for one declared editorial source."""

    requested_url: str
    final_url: str
    status_code: int
    content_type: str
    content: bytes
    etag: str | None = None
    last_modified: str | None = None


@dataclass(frozen=True, slots=True)
class FAOQualityRecoveryResult:
    """Durable FAO.6 decision returned to the official menu."""

    project_path: Path
    evidence_path: Path
    approved: bool
    input_fingerprint: str
    passed_gates: tuple[str, ...]
    blocking_codes: tuple[str, ...]
    operator_message: str
    recovery_steps: tuple[str, ...]
    retryable: bool
    source_network_calls: int
    delivery_network_calls: int
    reused_existing: bool

    def metadata(self) -> dict[str, Any]:
        return {
            "fao_quality_recovery_complete": self.approved,
            "fao_quality_recovery_path": _relative(
                self.evidence_path,
                self.project_path,
            ),
            "quality_approved": self.approved,
            "quality_passed_gates": list(self.passed_gates),
            "quality_blocking_codes": list(self.blocking_codes),
            "operator_message": self.operator_message,
            "recovery_steps": list(self.recovery_steps),
            "retryable": self.retryable,
            "quality_source_network_calls": self.source_network_calls,
            "quality_delivery_network_calls": self.delivery_network_calls,
            "quality_evidence_reused": self.reused_existing,
            "paid_provider_called": False,
            "render_performed": False,
            "f7_review_performed": False,
            "publication_performed": False,
        }


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._ignored_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        if tag.casefold() in {"script", "style", "noscript", "svg"}:
            self._ignored_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() in {"script", "style", "noscript", "svg"}:
            self._ignored_depth = max(0, self._ignored_depth - 1)

    def handle_data(self, data: str) -> None:
        if not self._ignored_depth and data.strip():
            self.parts.append(data)


class FAOQualityRecoveryEngine:
    """Validate FAO quality and persist idempotent operator diagnostics."""

    component_name = "fao_quality_recovery_engine"
    engine_version = "1.0"
    schema_name = _SCHEMA_NAME
    schema_version = _SCHEMA_VERSION

    def __init__(
        self,
        *,
        source_fetcher: SourceFetcher | None = None,
        asset_fetcher: AssetFetcher | None = None,
        clock: Clock | None = None,
        evidence_max_age_hours: int = 24,
    ) -> None:
        if evidence_max_age_hours < 1:
            raise ValueError("evidence_max_age_hours debe ser al menos 1.")
        self.source_fetcher = source_fetcher or _fetch_textual_source
        self.asset_fetcher = asset_fetcher or _fetch_public_asset
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.evidence_max_age = timedelta(hours=evidence_max_age_hours)

    def evaluate(self, project_path: str | Path) -> FAOQualityRecoveryResult:
        """Evaluate all FAO.6 gates and stop before render on any blocker."""

        project = Path(project_path).expanduser().resolve(strict=False)
        workspace = _workspace_for(project)
        metadata_store = MetadataStore(workspace)
        context = self._load_context(project)
        input_fingerprint = self._input_fingerprint(context)

        existing = self._reuse_existing(
            project,
            input_fingerprint=input_fingerprint,
        )
        if existing is not None:
            if existing.approved:
                return existing
            raise FAOQualityRecoveryBlockedError(existing)

        source_calls = [0]
        delivery_calls = [0]
        gates = [
            self._factual_gate(context, source_calls),
            self._editorial_gate(context),
            self._visual_gate(context),
            self._acoustic_gate(context),
            self._technical_gate(context, delivery_calls),
        ]
        blocking_codes = tuple(
            dict.fromkeys(
                code
                for gate in gates
                for code in gate["blocking_codes"]
            )
        )
        approved = not blocking_codes and all(
            gate["status"] == "passed" for gate in gates
        )
        diagnostic = _operator_diagnostic(blocking_codes)
        checked_at = _as_utc(self.clock())
        telemetry_path = project / "03_TELEMETRIA" / TelemetryEngine.EVENTS_FILENAME
        self._record_telemetry(
            project,
            project_id=context["manifest"].project.project_id,
            input_fingerprint=input_fingerprint,
            approved=approved,
            blocking_codes=blocking_codes,
        )
        report = {
            "schema_name": self.schema_name,
            "schema_version": self.schema_version,
            "status": (
                "quality_approved_for_render_authorization"
                if approved
                else "quality_blocked"
            ),
            "project_id": context["manifest"].project.project_id,
            "input_fingerprint": input_fingerprint,
            "engine": self.component_name,
            "engine_version": self.engine_version,
            "checked_at": checked_at.isoformat(),
            "evidence_valid_until": (checked_at + self.evidence_max_age).isoformat(),
            "approved": approved,
            "gates": gates,
            "passed_gates": [
                gate["gate"] for gate in gates if gate["status"] == "passed"
            ],
            "blocking_codes": list(blocking_codes),
            "operator_diagnostic": diagnostic,
            "source_network_calls": source_calls[0],
            "delivery_network_calls": delivery_calls[0],
            "f8_quality_telemetry_persisted": True,
            "f8_telemetry_path": _relative(telemetry_path, project),
            "free_tier_default": True,
            "total_actual_cost_usd": 0.0,
            "unknown_cost_count": 0,
            "paid_provider_called": False,
            "render_authorization_required": True,
            "render_performed": False,
            "f7_review_state": "not_started",
            "f7_review_performed": False,
            "publication_performed": False,
        }
        path = project / QUALITY_REPORT_RELATIVE_PATH
        write = metadata_store.persist_metadata(
            workspace_root=project,
            relative_path=QUALITY_REPORT_RELATIVE_PATH,
            content=report,
            artifact_type="fao_quality_recovery_evidence",
            artifact_id=f"fao6-quality-{_mapping_sha256(report)[:24]}",
            metadata={
                "project_id": report["project_id"],
                "approved": approved,
                "blocking_codes": list(blocking_codes),
                "render_performed": False,
                "publication_performed": False,
            },
            collision_policy=CollisionPolicy.REPLACE,
        )
        if Path(write.artifact.path).resolve(strict=False) != path:
            raise FAOQualityRecoveryError(
                "F3 no persistió la evidencia FAO.6 en la ruta canónica."
            )
        result = self._result_from_report(
            project,
            report,
            reused_existing=False,
        )
        if not result.approved:
            raise FAOQualityRecoveryBlockedError(result)
        return result

    @staticmethod
    def _record_telemetry(
        project: Path,
        *,
        project_id: str,
        input_fingerprint: str,
        approved: bool,
        blocking_codes: Sequence[str],
    ) -> None:
        telemetry = TelemetryEngine()
        event_id = (
            f"fao6-{input_fingerprint[:24]}-"
            f"{'approved' if approved else 'blocked'}"
        )
        existing = telemetry.read_events(project_path=project)
        if existing.success and any(
            isinstance(event, TelemetryEvent) and event.event_id == event_id
            for event in (existing.data or [])
        ):
            return
        recorded = telemetry.record_event(
            TelemetryEvent(
                event_id=event_id,
                timestamp="",
                project_id=project_id,
                component="fao_quality_recovery",
                operation="task.succeeded" if approved else "task.failed",
                stage="quality_assurance",
                event_type="execution",
                success=approved,
                validation_score=100.0 if approved else 0.0,
                validation_passing_score=100.0,
                validation_approved=approved,
                estimated_cost=0.0,
                metadata={
                    "task_id": "fao6_quality_gate",
                    "status": "approved" if approved else "blocked",
                    "blocking_codes": list(blocking_codes),
                    "render_performed": False,
                    "publication_performed": False,
                },
                workflow_id="fao-operational-end-to-end",
                run_id=f"fao6-{input_fingerprint[:24]}",
                task_id="fao6_quality_gate",
                correlation_id=f"fao6-{input_fingerprint[:24]}",
            ),
            project_path=project,
            update_summary=True,
        )
        if not recorded.success:
            raise FAOQualityRecoveryError(
                "F8 no pudo persistir el diagnóstico de calidad FAO.6: "
                + "; ".join(recorded.errors)
            )

    def _load_context(self, project: Path) -> dict[str, Any]:
        unification_path = project / _UNIFICATION_RELATIVE_PATH
        unification = _read_json_object(unification_path, "evidencia FAO.5")
        if (
            unification.get("schema_name") != "cips.fao.pm9_unification"
            or unification.get("schema_version") != "1.0"
            or unification.get("status") != "ready_for_render_authorization"
            or unification.get("ready_for_real_render") is not True
        ):
            raise FAOQualityRecoveryError(
                "FAO.6 requiere una preparación FAO.5 válida y lista para autorización."
            )
        outputs = unification.get("outputs")
        if not isinstance(outputs, Mapping):
            raise FAOQualityRecoveryError("La evidencia FAO.5 no declara sus salidas.")
        output_paths: dict[str, Path] = {}
        for name, raw_ref in outputs.items():
            if not isinstance(raw_ref, Mapping):
                raise FAOQualityRecoveryError(
                    f"La referencia FAO.5 '{name}' es inválida."
                )
            path = _project_file(project, raw_ref.get("path"))
            if (
                not path.is_file()
                or _file_sha256(path) != raw_ref.get("sha256")
                or path.stat().st_size != raw_ref.get("size_bytes")
            ):
                raise FAOQualityRecoveryError(
                    f"La salida FAO.5 '{name}' no coincide con su evidencia física."
                )
            output_paths[str(name)] = path

        manifest_path = project / "production_manifest.json"
        manifest = deserialize_manifest(manifest_path.read_bytes())
        config_path = project / "production_acceptance_config.json"
        config = _load_project_config(project)
        catalog_path = output_paths["fulfilled_asset_catalog"]
        catalog = ApprovedAssetCatalog.load(catalog_path)
        fulfillment = _read_json_object(
            output_paths["visual_fulfillment_report"],
            "reporte de fulfillment visual",
        )
        preparation_path = output_paths["pm9_preparation"]
        preparation = ProductionPreparationEvidence.model_validate_json(
            preparation_path.read_bytes()
        )
        request_path = project / "operational_request.json"
        request = _read_json_object(request_path, "solicitud operativa")
        editorial = {
            stage: canonical_editorial_path(project, stage).read_text(
                encoding="utf-8"
            ).strip()
            for stage in EDITORIAL_STAGES
        }
        assets_root = (project / config["assets_root_relative_path"]).resolve(
            strict=False
        )
        assets_root.relative_to(project)

        tracked_paths = {
            unification_path,
            request_path,
            manifest_path,
            config_path,
            *output_paths.values(),
            *(canonical_editorial_path(project, stage) for stage in EDITORIAL_STAGES),
        }
        for entry in catalog.entries:
            path = (assets_root / entry.relative_path).resolve(strict=False)
            path.relative_to(assets_root)
            tracked_paths.add(path)
        conformance_relative = preparation.narration_conformance_relative_path
        if conformance_relative:
            tracked_paths.add(_project_file(project, conformance_relative))
        missing = [path for path in tracked_paths if not path.is_file()]
        if missing:
            raise FAOQualityRecoveryError(
                "Faltan entradas físicas para FAO.6: "
                + ", ".join(_relative(path, project) for path in sorted(missing))
            )
        return {
            "project": project,
            "unification": unification,
            "output_paths": output_paths,
            "manifest": manifest,
            "manifest_path": manifest_path,
            "config": config,
            "config_path": config_path,
            "catalog": catalog,
            "catalog_path": catalog_path,
            "fulfillment": fulfillment,
            "preparation": preparation,
            "preparation_path": preparation_path,
            "request": request,
            "request_path": request_path,
            "editorial": editorial,
            "assets_root": assets_root,
            "tracked_paths": tuple(sorted(tracked_paths)),
        }

    def _input_fingerprint(self, context: Mapping[str, Any]) -> str:
        project = context["project"]
        return _mapping_sha256(
            {
                "engine": self.component_name,
                "engine_version": self.engine_version,
                "files": [
                    {
                        "path": _relative(path, project),
                        "sha256": _file_sha256(path),
                        "size_bytes": path.stat().st_size,
                    }
                    for path in context["tracked_paths"]
                ],
            }
        )

    def _reuse_existing(
        self,
        project: Path,
        *,
        input_fingerprint: str,
    ) -> FAOQualityRecoveryResult | None:
        path = project / QUALITY_REPORT_RELATIVE_PATH
        if not path.is_file():
            return None
        try:
            report = _read_json_object(path, "evidencia FAO.6")
            if (
                report.get("schema_name") != self.schema_name
                or report.get("schema_version") != self.schema_version
                or report.get("input_fingerprint") != input_fingerprint
                or report.get("render_performed") is not False
                or report.get("publication_performed") is not False
            ):
                return None
            valid_until = datetime.fromisoformat(
                str(report["evidence_valid_until"]).replace("Z", "+00:00")
            )
            if _as_utc(self.clock()) > _as_utc(valid_until):
                return None
            result = self._result_from_report(
                project,
                report,
                reused_existing=True,
            )
            if not result.approved and result.retryable:
                return None
            return result
        except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError):
            return None

    def _factual_gate(
        self,
        context: Mapping[str, Any],
        calls: list[int],
    ) -> dict[str, Any]:
        research = context["editorial"]["investigacion"]
        verification = context["editorial"]["verificacion"]
        declared = EditorialValidatorEngine._source_declarations(research)
        relations = EditorialValidatorEngine._claim_source_relations(research)
        decisions = EditorialValidatorEngine._verification_decisions(verification)
        approved_claims = {
            claim: decision
            for claim, decision in decisions.items()
            if decision["status"] == "APROBADA"
        }
        source_labels = {
            source_id.upper(): " ".join(
                line.replace(url, " ").split()
            )
            for source_id, url, line in _source_lines(research)
        }
        checks: list[dict[str, Any]] = []
        blockers: list[str] = []
        fetched_text: dict[str, str] = {}
        fetched_ok: set[str] = set()
        hosts: set[str] = set()
        topic_tokens = _tokens(str(context["request"].get("topic", "")))

        for source_id, url in sorted(declared.items()):
            check: dict[str, Any] = {
                "check_id": f"source:{source_id}",
                "source_id": source_id,
                "requested_url": url,
                "passed": False,
            }
            parsed = urlsplit(url)
            if parsed.scheme.casefold() != "https":
                blockers.append("factual_source_not_https")
                check["failure"] = "La fuente no usa HTTPS."
                checks.append(check)
                continue
            try:
                calls[0] += 1
                response = self.source_fetcher(url)
                text = _response_text(response)
                label_tokens = _tokens(source_labels.get(source_id, ""))
                body_tokens = _tokens(text)
                relevance_tokens = (label_tokens | topic_tokens) & body_tokens
                passed = (
                    200 <= response.status_code < 300
                    and len(text) >= 250
                    and bool(relevance_tokens)
                    and urlsplit(response.final_url).scheme.casefold() == "https"
                )
                check.update(
                    {
                        "final_url": response.final_url,
                        "status_code": response.status_code,
                        "content_type": response.content_type,
                        "size_bytes": len(response.content),
                        "content_sha256": hashlib.sha256(response.content).hexdigest(),
                        "text_characters": len(text),
                        "relevance_token_count": len(relevance_tokens),
                        "etag": response.etag,
                        "last_modified": response.last_modified,
                        "passed": passed,
                    }
                )
                if passed:
                    fetched_text[source_id] = text
                    fetched_ok.add(source_id)
                    hosts.add((urlsplit(response.final_url).hostname or "").casefold())
                else:
                    blockers.append("factual_source_not_concordant")
                    check["failure"] = (
                        "La fuente respondió, pero no aportó texto suficiente y "
                        "reconocible para el tema declarado."
                    )
            except Exception as error:  # noqa: BLE001 - external source boundary
                blockers.append("factual_source_unavailable")
                check["failure"] = f"{type(error).__name__}: {error}"
            checks.append(check)

        if len(hosts) < 2:
            blockers.append("factual_sources_not_independent")
        for claim_id, decision in sorted(approved_claims.items()):
            cited = set(decision["sources"]) or relations.get(claim_id, set())
            claim_text = _claim_context(research, claim_id)
            claim_tokens = _tokens(claim_text)
            available = cited & fetched_ok
            overlap = set()
            available_body_tokens: set[str] = set()
            for source_id in available:
                body_tokens = _tokens(fetched_text[source_id])
                available_body_tokens.update(body_tokens)
                overlap.update(claim_tokens & body_tokens)
            topic_overlap = topic_tokens & available_body_tokens
            passed = (
                bool(cited)
                and cited <= fetched_ok
                and bool(overlap or topic_overlap)
            )
            if not passed:
                blockers.append("factual_claim_not_physically_supported")
            checks.append(
                {
                    "check_id": f"claim:{claim_id}",
                    "claim_id": claim_id,
                    "declared_sources": sorted(cited),
                    "available_sources": sorted(available),
                    "overlap_token_count": len(overlap),
                    "topic_overlap_token_count": len(topic_overlap),
                    "passed": passed,
                }
            )
        if len(declared) < 2 or not approved_claims:
            blockers.append("factual_evidence_incomplete")
        return _gate("factual", checks, blockers)

    @staticmethod
    def _editorial_gate(context: Mapping[str, Any]) -> dict[str, Any]:
        request = context["request"]
        editorial = context["editorial"]
        manifest: ProductionManifest = context["manifest"]
        topic_tokens = _tokens(str(request.get("topic", "")))
        research_tokens = _tokens(editorial["investigacion"])
        narration_tokens = _tokens(editorial["narracion"])
        research_topic_overlap = _stems(topic_tokens) & _stems(research_tokens)
        narration_topic_overlap = _stems(topic_tokens) & _stems(narration_tokens)
        verification = EditorialValidatorEngine._verification_decisions(
            editorial["verificacion"]
        )
        approved = {
            claim for claim, item in verification.items()
            if item["status"] == "APROBADA"
        }
        used_claims = (
            EditorialValidatorEngine._claim_ids(editorial["guion"])
            | EditorialValidatorEngine._claim_ids(editorial["storyboard"])
        )
        word_count = len(_WORD_RE.findall(editorial["narracion"]))
        duration = float(request.get("duration_seconds") or 0)
        words_per_minute = 0.0 if duration <= 0 else word_count * 60.0 / duration
        sentences = [
            " ".join(item.casefold().split())
            for item in _SENTENCE_RE.split(editorial["narracion"])
            if item.strip()
        ]
        unique_sentence_ratio = (
            1.0 if not sentences else len(set(sentences)) / len(sentences)
        )
        visual_token_counts = [
            len(_tokens(scene.visual_direction.intent)) for scene in manifest.scenes
        ]
        checks = [
            {
                "check_id": "topic_alignment",
                "research_overlap": len(research_topic_overlap),
                "narration_overlap": len(narration_topic_overlap),
                "passed": bool(research_topic_overlap)
                and bool(narration_topic_overlap),
            },
            {
                "check_id": "approved_claim_usage",
                "approved_claims": sorted(approved),
                "used_claims": sorted(used_claims),
                "passed": bool(approved) and bool(used_claims) and used_claims <= approved,
            },
            {
                "check_id": "spoken_duration",
                "word_count": word_count,
                "words_per_minute": round(words_per_minute, 2),
                "accepted_range": [75.0, 210.0],
                "passed": 75.0 <= words_per_minute <= 210.0,
            },
            {
                "check_id": "narrative_repetition",
                "sentence_count": len(sentences),
                "unique_sentence_ratio": round(unique_sentence_ratio, 4),
                "passed": unique_sentence_ratio >= 0.8,
            },
            {
                "check_id": "scene_visual_specificity",
                "scene_token_counts": visual_token_counts,
                "passed": bool(visual_token_counts)
                and all(count >= 3 for count in visual_token_counts),
            },
            {
                "check_id": "request_manifest_duration",
                "requested_seconds": duration,
                "manifest_seconds": manifest.output.duration_seconds,
                "passed": (
                    duration > 0
                    and abs(manifest.output.duration_seconds - duration) / duration <= 0.15
                ),
            },
        ]
        code_by_check = {
            "topic_alignment": "editorial_topic_drift",
            "approved_claim_usage": "editorial_unapproved_claim",
            "spoken_duration": "editorial_spoken_duration_out_of_range",
            "narrative_repetition": "editorial_repetition",
            "scene_visual_specificity": "editorial_visual_brief_too_generic",
            "request_manifest_duration": "editorial_duration_mismatch",
        }
        blockers = [
            code_by_check[check["check_id"]]
            for check in checks
            if not check["passed"]
        ]
        return _gate("editorial", checks, blockers)

    @staticmethod
    def _visual_gate(context: Mapping[str, Any]) -> dict[str, Any]:
        manifest: ProductionManifest = context["manifest"]
        catalog: ApprovedAssetCatalog = context["catalog"]
        assets_root: Path = context["assets_root"]
        report_assets = {
            str(item.get("entry_id")): item
            for item in context["fulfillment"].get("assets", [])
            if isinstance(item, Mapping)
        }
        by_scene = {
            entry.scene_id: entry
            for entry in catalog.entries
            if entry.role == "scene_visual" and entry.scene_id is not None
        }
        checks: list[dict[str, Any]] = []
        blockers: list[str] = []
        for scene in manifest.scenes:
            asset_type = scene.asset_request.asset_type
            if asset_type in _RENDERER_NATIVE_TYPES:
                passed = len(_tokens(scene.asset_request.creative_brief or "")) >= 3
                checks.append(
                    {
                        "check_id": f"renderer_native:{scene.scene_id}",
                        "scene_id": scene.scene_id,
                        "asset_type": asset_type.value,
                        "passed": passed,
                    }
                )
                if not passed:
                    blockers.append("visual_renderer_native_brief_incomplete")
                continue
            if asset_type not in _PHYSICAL_VISUAL_TYPES:
                blockers.append("visual_asset_type_not_supported")
                checks.append(
                    {
                        "check_id": f"visual:{scene.scene_id}",
                        "scene_id": scene.scene_id,
                        "passed": False,
                    }
                )
                continue
            entry = by_scene.get(scene.scene_id)
            report = None if entry is None else report_assets.get(entry.entry_id)
            passed = entry is not None and report is not None
            detail: dict[str, Any] = {
                "check_id": f"visual:{scene.scene_id}",
                "scene_id": scene.scene_id,
                "asset_type": asset_type.value,
                "passed": False,
            }
            if passed and entry is not None and report is not None:
                path = (assets_root / entry.relative_path).resolve(strict=False)
                try:
                    path.relative_to(assets_root)
                    content = path.read_bytes()
                    physical_sha = hashlib.sha256(content).hexdigest()
                    expected_sha = str(report.get("content_sha256") or "")
                    width = report.get("width_px")
                    height = report.get("height_px")
                    if entry.media_family is MediaFamily.IMAGE:
                        width, height = image_dimensions(content, entry.mime_type)
                    query = scene.asset_request.stock_query or ""
                    selected = " ".join(
                        str(value or "")
                        for value in (
                            report.get("selected_title"),
                            entry.source_url,
                            entry.attribution,
                        )
                    )
                    relevance = _tokens(
                        " ".join(
                            filter(
                                None,
                                (
                                    query,
                                    scene.asset_request.creative_brief,
                                    scene.visual_direction.intent,
                                ),
                            )
                        )
                    ) & _tokens(selected)
                    query_bound = (
                        not query
                        or _tokens(query)
                        == _tokens(str(report.get("prompt_permitted") or ""))
                    )
                    passed = (
                        bool(content)
                        and physical_sha == expected_sha
                        and entry.mime_type == report.get("mime_type")
                        and (
                            entry.media_family is not MediaFamily.IMAGE
                            or (
                                isinstance(width, int)
                                and isinstance(height, int)
                                and width >= 640
                                and height >= 360
                            )
                        )
                        and query_bound
                        and bool(relevance)
                    )
                    detail.update(
                        {
                            "entry_id": entry.entry_id,
                            "relative_path": entry.relative_path,
                            "content_sha256": physical_sha,
                            "width_px": width,
                            "height_px": height,
                            "query_bound": query_bound,
                            "relevance_token_count": len(relevance),
                            "passed": passed,
                        }
                    )
                except Exception as error:  # noqa: BLE001 - physical asset boundary
                    detail["failure"] = f"{type(error).__name__}: {error}"
                    passed = False
            if not passed:
                blockers.append("visual_asset_quality_failed")
            checks.append(detail)
        return _gate("visual", checks, blockers)

    @staticmethod
    def _acoustic_gate(context: Mapping[str, Any]) -> dict[str, Any]:
        manifest: ProductionManifest = context["manifest"]
        catalog: ApprovedAssetCatalog = context["catalog"]
        assets_root: Path = context["assets_root"]
        policy = context["config"]["narration_conformance_policy"]
        audio_hashes = {
            entry.scene_id: _file_sha256(assets_root / entry.relative_path)
            for entry in catalog.entries
            if entry.role == "scene_narration" and entry.scene_id is not None
        }
        inspection = inspect_narration_conformance(
            manifest,
            project_path=context["project"],
            audio_sha256_by_scene_id=audio_hashes,
            policy=policy,
        )
        evidence = context["unification"]
        blockers = list(inspection.blockers)
        if policy.enabled and (
            evidence.get("narration_conformance_required") is not True
            or evidence.get("narration_conformance_approved") is not True
            or inspection.report is None
            or inspection.report.approved is not True
        ):
            blockers.append("acoustic_evidence_missing_or_rejected")
        checks = [
            {
                "check_id": "narration_conformance",
                "policy_enabled": policy.enabled,
                "scene_count": len(audio_hashes),
                "report_path": _relative(inspection.report_path, context["project"]),
                "report_sha256": inspection.report_sha256,
                "persisted_approved": (
                    None if inspection.report is None else inspection.report.approved
                ),
                "passed": not blockers,
            }
        ]
        return _gate("acoustic", checks, blockers)

    def _technical_gate(
        self,
        context: Mapping[str, Any],
        calls: list[int],
    ) -> dict[str, Any]:
        manifest: ProductionManifest = context["manifest"]
        preparation: ProductionPreparationEvidence = context["preparation"]
        evidence = context["unification"]
        request = context["request"]
        payload_path = context["output_paths"]["render_payload"]
        try:
            payload = json.loads(payload_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            payload = None
        checks = [
            {
                "check_id": "preparation_ready",
                "passed": preparation.ready_for_real_render and not preparation.blockers,
                "blockers": list(preparation.blockers),
            },
            {
                "check_id": "provider_neutral_output_contract",
                "width_px": manifest.output.width_px,
                "height_px": manifest.output.height_px,
                "aspect_ratio": manifest.output.aspect_ratio,
                "fps": manifest.output.fps,
                "duration_seconds": manifest.output.duration_seconds,
                "passed": (
                    manifest.output.width_px == 1080
                    and manifest.output.height_px == 1920
                    and manifest.output.aspect_ratio == "9:16"
                    and abs(manifest.output.fps - 30.0) <= 0.01
                    and float(request.get("duration_seconds") or 0) > 0
                    and abs(
                        manifest.output.duration_seconds
                        - float(request.get("duration_seconds") or 0)
                    )
                    / float(request.get("duration_seconds") or 1)
                    <= 0.15
                ),
            },
            {
                "check_id": "render_payload",
                "provider": evidence.get("render_provider"),
                "size_bytes": payload_path.stat().st_size,
                "passed": isinstance(payload, Mapping) and bool(payload),
            },
            {
                "check_id": "zero_cost_and_no_side_effects",
                "passed": (
                    evidence.get("total_actual_cost_usd") == 0.0
                    and evidence.get("unknown_cost_count") == 0
                    and evidence.get("paid_provider_called") is False
                    and evidence.get("render_performed") is False
                    and evidence.get("f7_review_performed") is False
                    and evidence.get("publication_performed") is False
                    and not any(
                        (context["project"] / relative).exists()
                        for relative in _RENDER_OUTPUTS
                    )
                ),
            },
        ]
        blockers = [
            {
                "preparation_ready": "technical_preparation_not_ready",
                "provider_neutral_output_contract": "technical_output_contract_invalid",
                "render_payload": "technical_payload_invalid",
                "zero_cost_and_no_side_effects": "technical_safety_boundary_breached",
            }[check["check_id"]]
            for check in checks
            if not check["passed"]
        ]
        delivery_check: dict[str, Any] = {
            "check_id": "public_asset_delivery",
            "passed": False,
        }

        def counted_fetch(url: str) -> bytes:
            calls[0] += 1
            return self.asset_fetcher(url)

        try:
            verification = verify_catalog_delivery(
                context["catalog"],
                assets_root=context["assets_root"],
                fetch_bytes=counted_fetch,
            )
            delivery_check.update(
                {
                    "verified_count": verification.verified_count,
                    "total_bytes": verification.total_bytes,
                    "checks": list(verification.checks),
                    "passed": True,
                }
            )
        except (OSError, TypeError, ValueError, SourceAssetBuildError) as error:
            blockers.append("technical_public_delivery_unavailable")
            delivery_check["failure"] = f"{type(error).__name__}: {error}"
        checks.append(delivery_check)
        return _gate("technical", checks, blockers)

    @staticmethod
    def _result_from_report(
        project: Path,
        report: Mapping[str, Any],
        *,
        reused_existing: bool,
    ) -> FAOQualityRecoveryResult:
        diagnostic = report.get("operator_diagnostic")
        if not isinstance(diagnostic, Mapping):
            raise ValueError("La evidencia FAO.6 no contiene diagnóstico de operador.")
        return FAOQualityRecoveryResult(
            project_path=project,
            evidence_path=project / QUALITY_REPORT_RELATIVE_PATH,
            approved=bool(report.get("approved")),
            input_fingerprint=str(report["input_fingerprint"]),
            passed_gates=tuple(str(item) for item in report.get("passed_gates", [])),
            blocking_codes=tuple(
                str(item) for item in report.get("blocking_codes", [])
            ),
            operator_message=str(diagnostic.get("message") or ""),
            recovery_steps=tuple(
                str(item) for item in diagnostic.get("recovery_steps", [])
            ),
            retryable=bool(diagnostic.get("retryable")),
            source_network_calls=int(report.get("source_network_calls", 0)),
            delivery_network_calls=int(report.get("delivery_network_calls", 0)),
            reused_existing=reused_existing,
        )


def _gate(
    name: str,
    checks: Sequence[Mapping[str, Any]],
    blockers: Sequence[str],
) -> dict[str, Any]:
    unique = list(dict.fromkeys(str(item) for item in blockers))
    return {
        "gate": name,
        "status": "passed" if not unique else "blocked",
        "checks": [dict(item) for item in checks],
        "blocking_codes": unique,
    }


def _operator_diagnostic(blockers: Sequence[str]) -> dict[str, Any]:
    if not blockers:
        return {
            "message": (
                "FAO.6 aprobó las fuentes, el contenido editorial, los visuales, "
                "la narración y la preparación técnica. El render continúa sujeto "
                "a una autorización humana nueva y cuantificada."
            ),
            "retryable": False,
            "recovery_steps": [],
        }
    retryable_codes = {
        "factual_source_unavailable",
        "technical_public_delivery_unavailable",
    }
    if "factual_source_unavailable" in blockers:
        retryable_codes.update(
            {
                "factual_sources_not_independent",
                "factual_claim_not_physically_supported",
            }
        )
    retryable = all(code in retryable_codes for code in blockers)
    steps: list[str] = []
    if any(code.startswith("factual_") for code in blockers):
        steps.append(
            "Comprueba la conexión a Internet y vuelve a usar 'Continuar Proyecto'. "
            "Si la fuente sigue fallando, crea un proyecto nuevo para que CIPS "
            "regenere la investigación con referencias accesibles."
        )
    if any(code.startswith("editorial_") for code in blockers):
        steps.append(
            "El paquete editorial no alcanza la calidad requerida. Conserva esta "
            "evidencia y crea un proyecto nuevo con un tema, audiencia o estilo más "
            "precisos; CIPS no renderizará el contenido defectuoso."
        )
    if any(code.startswith("visual_") for code in blockers):
        steps.append(
            "Un visual no coincide física o semánticamente con su escena. Vuelve a "
            "intentar desde 'Continuar Proyecto'; si no cambia, inicia un proyecto "
            "nuevo para adquirir otra selección Free Tier."
        )
    if any(code.startswith("acoustic_") or code.startswith("narration_") for code in blockers):
        steps.append(
            "La narración no conserva evidencia acústica válida. No autorices un "
            "render; vuelve a intentar para que CIPS verifique o regenere la voz local."
        )
    if any(code.startswith("technical_") for code in blockers):
        steps.append(
            "Verifica que los assets estén disponibles en sus URLs públicas y usa "
            "'Continuar Proyecto'. CIPS volverá a comprobarlos sin renderizar ni publicar."
        )
    return {
        "message": (
            "FAO.6 bloqueó el render de forma segura. Motivos: "
            + ", ".join(blockers)
            + "."
        ),
        "retryable": retryable,
        "recovery_steps": list(dict.fromkeys(steps)),
    }


def _source_lines(content: str) -> tuple[tuple[str, str, str], ...]:
    return tuple(
        (match.group(1).upper(), match.group(2).rstrip(".,;:"), match.group(0))
        for match in _SOURCE_LINE_RE.finditer(content)
    )


def _claim_context(content: str, claim_id: str) -> str:
    marker = f"[{claim_id.upper()}]"
    for line in content.splitlines():
        if marker in line.upper():
            return line.replace(marker, " ")
    return ""


def _tokens(value: str) -> set[str]:
    return {
        token.casefold()
        for token in _WORD_RE.findall(str(value))
        if len(token) >= 3 and token.casefold() not in _STOPWORDS
    }


def _stems(values: set[str]) -> set[str]:
    """Normalize a conservative plural suffix for cross-artifact matching."""

    return {
        value[:-1] if len(value) > 4 and value.endswith("s") else value
        for value in values
    }


def _response_text(response: SourceFetchResult) -> str:
    content_type = response.content_type.casefold().split(";", 1)[0].strip()
    if content_type not in {"text/html", "text/plain", "application/xhtml+xml"}:
        raise ValueError(
            "La fuente no entrega contenido textual HTML/plain verificable."
        )
    decoded = response.content.decode("utf-8", errors="replace")
    if content_type in {"text/html", "application/xhtml+xml"}:
        parser = _TextExtractor()
        parser.feed(decoded)
        decoded = " ".join(parser.parts)
    return " ".join(decoded.split())


def _fetch_textual_source(url: str) -> SourceFetchResult:
    _validate_public_https(url)
    request = Request(
        url,
        headers={
            "User-Agent": "CIPS-FAO6/1.0 (+quality-source-verification)",
            "Accept": "text/html,text/plain,application/xhtml+xml;q=0.9",
        },
    )
    with urlopen(request, timeout=20) as response:  # noqa: S310 - validated public HTTPS
        final_url = str(response.geturl())
        _validate_public_https(final_url)
        content = response.read(_MAX_SOURCE_BYTES + 1)
        if len(content) > _MAX_SOURCE_BYTES:
            raise ValueError("La fuente excede el límite de 2 MiB.")
        return SourceFetchResult(
            requested_url=url,
            final_url=final_url,
            status_code=int(getattr(response, "status", 200)),
            content_type=str(response.headers.get("Content-Type", "")),
            content=content,
            etag=response.headers.get("ETag"),
            last_modified=response.headers.get("Last-Modified"),
        )


def _fetch_public_asset(url: str) -> bytes:
    _validate_public_https(url)
    request = Request(
        url,
        headers={"User-Agent": "CIPS-FAO6/1.0 (+asset-delivery-verification)"},
    )
    with urlopen(request, timeout=45) as response:  # noqa: S310 - validated public HTTPS
        final_url = str(response.geturl())
        _validate_public_https(final_url)
        content = response.read(_MAX_ASSET_BYTES + 1)
        if len(content) > _MAX_ASSET_BYTES:
            raise ValueError("El asset remoto excede el límite de 64 MiB.")
        if not content:
            raise ValueError("El asset remoto está vacío.")
        return content


def _validate_public_https(url: str) -> None:
    parsed = urlsplit(str(url).strip())
    if (
        parsed.scheme.casefold() != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise ValueError("La URL debe ser HTTPS pública y no incluir credenciales.")
    host = parsed.hostname.casefold().rstrip(".")
    if host == "localhost" or host.endswith(".localhost"):
        raise ValueError("La URL no puede apuntar a localhost.")
    try:
        addresses = socket.getaddrinfo(host, parsed.port or 443, type=socket.SOCK_STREAM)
    except socket.gaierror as error:
        raise ValueError(f"No se pudo resolver el host público: {host}") from error
    if not addresses:
        raise ValueError(f"El host no resolvió direcciones: {host}")
    for address in addresses:
        ip = ipaddress.ip_address(address[4][0])
        if not ip.is_global:
            raise ValueError("La URL resolvió una dirección no pública.")


def _workspace_for(project: Path) -> WorkspaceResolver:
    if not project.is_dir() or project.parent.name != "04_PROYECTOS":
        raise FAOQualityRecoveryError(
            "El proyecto FAO.6 debe existir directamente dentro de 04_PROYECTOS."
        )
    return WorkspaceResolver(
        projects_root=project.parent,
        outputs_root=project.parent.parent / "05_OUTPUTS",
    )


def _read_json_object(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise FAOQualityRecoveryError(
            f"No fue posible leer {label}: {error}"
        ) from error
    if not isinstance(value, dict):
        raise FAOQualityRecoveryError(f"{label} debe contener un objeto JSON.")
    return value


def _project_file(project: Path, value: Any) -> Path:
    text = str(value or "").strip().replace("\\", "/")
    if (
        not text
        or PurePosixPath(text).is_absolute()
        or PureWindowsPath(text).is_absolute()
        or any(part in {"", ".", ".."} for part in PurePosixPath(text).parts)
    ):
        raise FAOQualityRecoveryError(
            "La evidencia FAO contiene una ruta no confinada."
        )
    path = (project / Path(text)).resolve(strict=False)
    try:
        path.relative_to(project)
    except ValueError as error:
        raise FAOQualityRecoveryError(
            "La evidencia FAO contiene una ruta fuera del proyecto."
        ) from error
    return path


def _relative(path: Path, project: Path) -> str:
    return path.resolve(strict=False).relative_to(
        project.resolve(strict=False)
    ).as_posix()


def _mapping_sha256(value: Mapping[str, Any]) -> str:
    payload = json.dumps(
        dict(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


__all__ = [
    "FAOQualityRecoveryBlockedError",
    "FAOQualityRecoveryEngine",
    "FAOQualityRecoveryError",
    "FAOQualityRecoveryResult",
    "QUALITY_REPORT_RELATIVE_PATH",
    "SourceFetchResult",
]
