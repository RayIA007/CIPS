"""Semantic and factual-traceability gate for FAO.3 editorial artifacts."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from editorial_contract import (
    EDITORIAL_PREREQUISITES,
    EDITORIAL_STAGES,
    canonical_editorial_path,
    contains_placeholder,
    legacy_editorial_path,
)
from runtime_component import RuntimeComponent
from runtime_context import RuntimeContext
from runtime_models import EngineResult, ValidationResult


SOURCE_RE = re.compile(
    r"\[(F\d+)\][^\n]*(https?://[^\s)>\]]+)",
    re.IGNORECASE,
)
CLAIM_RE = re.compile(r"\[(A\d+)\]", re.IGNORECASE)
SOURCE_REFERENCE_RE = re.compile(r"\[(F\d+)\]", re.IGNORECASE)
STATUS_RE = re.compile(r"\b(APROBADA|RECHAZADA|INCIERTA)\b", re.IGNORECASE)
SCENE_RE = re.compile(r"^#{1,6}\s+ESCENA\s+\d+\b", re.IGNORECASE | re.MULTILINE)
DURATION_RE = re.compile(
    r"(?:\*\*)?duraci[oó]n(?:\*\*)?\s*:\s*(\d+)\s*(?:s|segundos?)\b",
    re.IGNORECASE,
)
WORD_RE = re.compile(r"[a-záéíóúüñ0-9]+", re.IGNORECASE)

STOPWORDS = frozenset(
    {
        "a",
        "al",
        "como",
        "con",
        "de",
        "del",
        "el",
        "en",
        "es",
        "esta",
        "este",
        "la",
        "las",
        "lo",
        "los",
        "o",
        "para",
        "por",
        "que",
        "se",
        "su",
        "un",
        "una",
        "y",
    }
)


class EditorialValidatorEngine(RuntimeComponent):
    """Enforce traceable claims, approved evidence and cross-stage coherence."""

    component_name = "editorial_validator"
    LEDGER_SCHEMA = "cips.fao.editorial_evidence"
    PACKAGE_SCHEMA = "cips.fao.editorial_package"

    def execute(self, runtime_context: RuntimeContext) -> EngineResult:
        project = runtime_context.project
        stage = project.stage_actual

        if stage not in EDITORIAL_STAGES:
            return EngineResult.ok(
                data=runtime_context,
                message="El Stage no requiere validación editorial FAO.3.",
                metadata={
                    "component": self.component_name,
                    "project_id": project.project_id,
                    "stage": stage,
                    "applied": False,
                },
            )

        response = runtime_context.llm_response
        if response is None or not str(response.content or "").strip():
            return EngineResult.fail(
                message="No existe contenido editorial para validar.",
                errors=["RuntimeContext.llm_response vacío."],
                metadata=self._base_metadata(runtime_context),
            )

        previous = runtime_context.validation_result
        if previous is None or not previous.approved:
            return EngineResult.fail(
                message="La validación estructural debe aprobar antes del gate FAO.3.",
                errors=["ValidationResult estructural no aprobado."],
                metadata=self._base_metadata(runtime_context),
            )

        if not (project.path / "operational_request.json").is_file():
            return EngineResult.ok(
                data=runtime_context,
                message=(
                    "Proyecto heredado sin solicitud FAO; se conserva la "
                    "validación estructural anterior."
                ),
                warnings=[
                    "El gate verificable FAO.3 no se aplica a este proyecto heredado."
                ],
                metadata={
                    **self._base_metadata(runtime_context),
                    "applied": False,
                    "legacy_project": True,
                },
            )

        content = response.content.strip()
        errors: list[str] = []
        warnings: list[str] = []
        observations: list[str] = []

        try:
            request = self._load_request(project.path)
            analysis = self._validate_stage(
                project_path=project.path,
                stage=stage,
                content=content,
                request=request,
                errors=errors,
                warnings=warnings,
                observations=observations,
            )
        except (OSError, ValueError, json.JSONDecodeError) as error:
            errors.append(str(error))
            analysis = {}

        metadata = {
            **self._base_metadata(runtime_context),
            "applied": True,
            "semantic_approved": not errors,
            "factual_traceability_approved": not errors,
            "publication_performed": False,
            **analysis,
        }

        combined = ValidationResult(
            approved=not errors,
            observations=[*previous.observations, *observations],
            warnings=[*previous.warnings, *warnings],
            errors=errors,
            metadata={
                **previous.metadata,
                "editorial_validation": metadata,
            },
        )
        runtime_context.validation_result = combined

        if errors:
            return EngineResult.fail(
                message="El entregable no superó la validación editorial verificable.",
                errors=errors,
                warnings=warnings,
                metadata=metadata,
            )

        try:
            legacy_path = self._persist_legacy_mirror(
                project_path=project.path,
                stage=stage,
                content=content,
            )
            ledger_path = self._persist_ledger(
                runtime_context=runtime_context,
                request=request,
                content=content,
                analysis=analysis,
            )
            package_path = self._persist_package_if_complete(
                project_path=project.path,
                project_id=project.project_id,
                request=request,
                ledger_path=ledger_path,
            )
        except (OSError, ValueError, json.JSONDecodeError) as error:
            combined.approved = False
            combined.errors.append(str(error))
            return EngineResult.fail(
                message="El contenido fue validado, pero falló la evidencia editorial.",
                errors=[str(error)],
                warnings=warnings,
                metadata=metadata,
            )

        metadata.update(
            {
                "evidence_ledger_path": str(ledger_path),
                "editorial_package_path": str(package_path) if package_path else "",
                "editorial_package_complete": package_path is not None,
                "legacy_mirror_path": str(legacy_path) if legacy_path else "",
            }
        )
        combined.metadata["editorial_validation"] = dict(metadata)

        return EngineResult.ok(
            data=runtime_context,
            message="Trazabilidad factual y coherencia editorial aprobadas.",
            warnings=warnings,
            metadata=metadata,
        )

    def _validate_stage(
        self,
        *,
        project_path: Path,
        stage: str,
        content: str,
        request: dict[str, Any],
        errors: list[str],
        warnings: list[str],
        observations: list[str],
    ) -> dict[str, Any]:
        if contains_placeholder(content):
            errors.append("El entregable contiene un marcador editorial sin resolver.")

        topic_tokens = self._tokens(str(request["topic"]))
        content_tokens = self._tokens(content)
        topic_overlap = self._overlap(topic_tokens, content_tokens)
        if stage == "investigacion" and topic_tokens and topic_overlap <= 0:
            errors.append("La investigación no conserva términos reconocibles del tema.")

        prerequisites = self._load_prerequisite_contents(project_path, stage)
        semantic_overlap = self._semantic_overlap(content, prerequisites.values())
        if prerequisites and semantic_overlap < 0.06:
            errors.append(
                "El entregable no conserva suficiente relación semántica con sus "
                f"entradas aprobadas ({semantic_overlap:.3f} < 0.060)."
            )

        source_ids: set[str] = set()
        source_urls: dict[str, str] = {}
        claim_ids = self._claim_ids(content)
        approved_claim_ids: set[str] = set()
        referenced_claim_ids: set[str] = set()
        decision_statuses: dict[str, str] = {}

        research = prerequisites.get("investigacion", "")
        verification = prerequisites.get("verificacion", "")
        research_claims = self._claim_ids(research)
        research_sources = self._source_declarations(research)
        approved_from_verification = self._approved_claims(verification)

        if stage == "investigacion":
            source_urls = self._source_declarations(content)
            source_ids = set(source_urls)
            if len(source_ids) < 2:
                errors.append("La investigación debe declarar al menos dos fuentes con URL.")
            if len(claim_ids) < 2:
                errors.append("La investigación debe identificar al menos dos afirmaciones [A#].")
            relations = self._claim_source_relations(content)
            unsupported = sorted(claim_ids - set(relations))
            if unsupported:
                errors.append(
                    "Afirmaciones sin relación explícita con fuentes: "
                    + ", ".join(unsupported)
                    + "."
                )
            unknown_sources = {
                source
                for sources in relations.values()
                for source in sources
                if source not in source_ids
            }
            if unknown_sources:
                errors.append(
                    "La evidencia cita fuentes no declaradas: "
                    + ", ".join(sorted(unknown_sources))
                    + "."
                )

        elif stage == "verificacion":
            source_ids = set(research_sources)
            referenced_claim_ids = self._claim_ids(content)
            decisions = self._verification_decisions(content)
            decision_statuses = {
                claim_id: decision["status"] for claim_id, decision in decisions.items()
            }
            missing_decisions = sorted(research_claims - set(decisions))
            if missing_decisions:
                errors.append(
                    "La verificación no decide todas las afirmaciones: "
                    + ", ".join(missing_decisions)
                    + "."
                )
            unknown_claims = sorted(set(decisions) - research_claims)
            if unknown_claims:
                errors.append(
                    "La verificación introduce afirmaciones no investigadas: "
                    + ", ".join(unknown_claims)
                    + "."
                )
            for claim_id, decision in decisions.items():
                if not decision["sources"]:
                    errors.append(f"{claim_id} no cita una fuente en la verificación.")
                unknown = decision["sources"] - source_ids
                if unknown:
                    errors.append(
                        f"{claim_id} cita fuentes inexistentes: "
                        + ", ".join(sorted(unknown))
                        + "."
                    )
            approved_claim_ids = {
                claim_id
                for claim_id, status in decision_statuses.items()
                if status == "APROBADA"
            }
            if not approved_claim_ids:
                errors.append("La verificación no aprobó ninguna afirmación utilizable.")

        elif stage in {"guion", "storyboard"}:
            referenced_claim_ids = self._claim_ids(content)
            approved_claim_ids = set(approved_from_verification)
            if not referenced_claim_ids:
                errors.append(f"El Stage '{stage}' no cita afirmaciones aprobadas [A#].")
            rejected_refs = sorted(referenced_claim_ids - approved_claim_ids)
            if rejected_refs:
                errors.append(
                    "El entregable usa afirmaciones no aprobadas: "
                    + ", ".join(rejected_refs)
                    + "."
                )

        if stage == "storyboard":
            scene_count = len(SCENE_RE.findall(content))
            durations = [int(value) for value in DURATION_RE.findall(content)]
            duration_total = sum(durations)
            target = int(request["duration_seconds"])
            if scene_count < 2:
                errors.append("El storyboard debe contener al menos dos escenas numeradas.")
            if len(durations) != scene_count:
                errors.append("Cada escena del storyboard debe declarar una duración entera.")
            if duration_total != target:
                errors.append(
                    f"Las escenas suman {duration_total} s y la solicitud exige {target} s."
                )
        else:
            scene_count = 0
            durations = []
            duration_total = 0

        if stage == "publicacion":
            lowered = content.casefold()
            if "publication_performed: false" not in lowered:
                errors.append("El paquete debe declarar publication_performed: false.")
            if "authorization_required: true" not in lowered:
                errors.append("El paquete debe declarar authorization_required: true.")

        narration_min_words = 0
        narration_max_words = 0
        if stage == "narracion":
            word_count = len(WORD_RE.findall(content))
            duration = int(request["duration_seconds"])
            narration_min_words = max(3, round(duration * 1.25))
            narration_max_words = max(narration_min_words, round(duration * 3.2))
            if not narration_min_words <= word_count <= narration_max_words:
                errors.append(
                    "La narración no cabe de forma razonable en la duración: "
                    f"{word_count} palabras; rango {narration_min_words}-"
                    f"{narration_max_words}."
                )
            if (
                re.search(r"^\s*#", content, re.MULTILINE)
                or CLAIM_RE.search(content)
                or SOURCE_REFERENCE_RE.search(content)
                or re.search(r"https?://", content, re.IGNORECASE)
            ):
                errors.append(
                    "La narración debe ser texto pronunciable sin Markdown, IDs ni URL."
                )
            approved_claim_ids = set(approved_from_verification)

        if not errors:
            observations.append(
                f"Stage '{stage}' alineado con solicitud y evidencia editorial previa."
            )

        return {
            "topic_overlap": round(topic_overlap, 4),
            "semantic_overlap": round(semantic_overlap, 4),
            "source_ids": sorted(source_ids),
            "source_urls": dict(sorted(source_urls.items())),
            "claim_ids": sorted(claim_ids),
            "approved_claim_ids": sorted(approved_claim_ids),
            "referenced_claim_ids": sorted(referenced_claim_ids),
            "decision_statuses": dict(sorted(decision_statuses.items())),
            "scene_count": scene_count,
            "scene_durations_seconds": durations,
            "scene_duration_total_seconds": duration_total,
            "narration_min_words": narration_min_words,
            "narration_max_words": narration_max_words,
            "placeholder_free": not contains_placeholder(content),
        }

    def _persist_ledger(
        self,
        *,
        runtime_context: RuntimeContext,
        request: dict[str, Any],
        content: str,
        analysis: dict[str, Any],
    ) -> Path:
        project = runtime_context.project
        stage = project.stage_actual
        artifact_path = canonical_editorial_path(project.path, stage)
        if not artifact_path.is_file():
            raise ValueError(f"No existe el artefacto físico validado: {artifact_path}")

        ledger_path = project.path / "state" / "editorial_evidence.json"
        ledger = self._read_json_object(ledger_path)
        if ledger and ledger.get("schema_name") != self.LEDGER_SCHEMA:
            raise ValueError("El ledger editorial existente usa un schema incompatible.")

        request_path = project.path / "operational_request.json"
        prompt_path = Path(runtime_context.prompt_path) if runtime_context.prompt_path else None
        artifact_hash = self._file_sha256(artifact_path)
        existing_stage = dict(ledger.get("stages", {}).get(stage, {})) if ledger else {}
        validated_at = existing_stage.get("validated_at")
        if existing_stage.get("artifact_sha256") != artifact_hash or not validated_at:
            validated_at = datetime.now(timezone.utc).isoformat()

        response = runtime_context.llm_response
        provider = ""
        model = ""
        if response is not None:
            provider = str(response.metadata.get("provider", ""))
            model = str(response.model or "")

        stages = dict(ledger.get("stages", {})) if ledger else {}
        stages[stage] = {
            "status": "validated",
            "artifact_path": artifact_path.relative_to(project.path).as_posix(),
            "artifact_sha256": artifact_hash,
            "artifact_characters": len(content),
            "prompt_path": (
                prompt_path.relative_to(project.path).as_posix()
                if prompt_path is not None and prompt_path.is_relative_to(project.path)
                else str(prompt_path or "")
            ),
            "prompt_sha256": (
                self._file_sha256(prompt_path)
                if prompt_path is not None and prompt_path.is_file()
                else ""
            ),
            "provider": provider,
            "model": model,
            "manual_fallback": provider == "manual" or model == "external_manual",
            "input_artifacts": list(runtime_context.metadata.get("editorial_inputs", [])),
            "semantic_overlap": analysis.get("semantic_overlap", 0.0),
            "source_ids": analysis.get("source_ids", []),
            "source_urls": analysis.get("source_urls", {}),
            "claim_ids": analysis.get("claim_ids", []),
            "approved_claim_ids": analysis.get("approved_claim_ids", []),
            "referenced_claim_ids": analysis.get("referenced_claim_ids", []),
            "decision_statuses": analysis.get("decision_statuses", {}),
            "placeholder_free": analysis.get("placeholder_free", False),
            "semantic_validation": True,
            "factual_traceability_validation": True,
            "validated_at": validated_at,
            "publication_performed": False,
        }

        payload = {
            "schema_name": self.LEDGER_SCHEMA,
            "schema_version": "1.0",
            "project_id": project.project_id,
            "operational_request_path": "operational_request.json",
            "operational_request_sha256": self._file_sha256(request_path),
            "free_tier_default": bool(request.get("free_tier_default", True)),
            "publication_performed": False,
            "stages": stages,
        }
        self._write_json_atomic(ledger_path, payload)
        return ledger_path

    def _persist_legacy_mirror(
        self,
        *,
        project_path: Path,
        stage: str,
        content: str,
    ) -> Path | None:
        """Keep the legacy root artifact synchronized after validation."""

        path = legacy_editorial_path(project_path, stage)
        if path is None:
            return None
        self._write_text_atomic(path, content.rstrip() + "\n")
        return path

    def _persist_package_if_complete(
        self,
        *,
        project_path: Path,
        project_id: str,
        request: dict[str, Any],
        ledger_path: Path,
    ) -> Path | None:
        ledger = self._read_json_object(ledger_path)
        stages = ledger.get("stages", {})
        if not all(stage in stages for stage in EDITORIAL_STAGES):
            return None

        artifacts: list[dict[str, Any]] = []
        for stage in EDITORIAL_STAGES:
            path = canonical_editorial_path(project_path, stage)
            if not path.is_file():
                return None
            content = path.read_text(encoding="utf-8").strip()
            if not content or contains_placeholder(content):
                raise ValueError(
                    f"El paquete editorial conserva contenido pendiente en '{stage}'."
                )
            artifact_hash = self._file_sha256(path)
            if stages[stage].get("artifact_sha256") != artifact_hash:
                raise ValueError(
                    f"El hash físico de '{stage}' no coincide con su evidencia."
                )
            artifacts.append(
                {
                    "stage": stage,
                    "path": path.relative_to(project_path).as_posix(),
                    "sha256": artifact_hash,
                    "characters": len(content),
                }
            )

        package_path = project_path / "state" / "editorial_package.json"
        payload = {
            "schema_name": self.PACKAGE_SCHEMA,
            "schema_version": "1.0",
            "project_id": project_id,
            "topic": request["topic"],
            "platform": request["platform"],
            "duration_seconds": request["duration_seconds"],
            "audience": request["audience"],
            "creative_style": request["creative_style"],
            "status": "editorial_complete",
            "artifact_count": len(artifacts),
            "artifacts": artifacts,
            "evidence_path": ledger_path.relative_to(project_path).as_posix(),
            "evidence_sha256": self._file_sha256(ledger_path),
            "placeholder_files": [],
            "semantic_validation": True,
            "factual_traceability_validation": True,
            "free_tier_default": bool(request.get("free_tier_default", True)),
            "publication_performed": False,
        }
        self._write_json_atomic(package_path, payload)
        return package_path

    def _load_request(self, project_path: Path) -> dict[str, Any]:
        path = project_path / "operational_request.json"
        data = self._read_json_object(path)
        if data.get("schema_name") != "cips.fao.operational_request":
            raise ValueError("La solicitud operativa no usa el schema FAO esperado.")
        if data.get("publication_performed") is not False:
            raise ValueError("publication_performed debe permanecer en false.")
        return data

    def _load_prerequisite_contents(
        self,
        project_path: Path,
        stage: str,
    ) -> dict[str, str]:
        contents: dict[str, str] = {}
        for prerequisite in EDITORIAL_PREREQUISITES[stage]:
            path = canonical_editorial_path(project_path, prerequisite)
            if not path.is_file():
                raise ValueError(f"Falta el prerequisito editorial: {prerequisite}")
            contents[prerequisite] = path.read_text(encoding="utf-8").strip()
        return contents

    @staticmethod
    def _source_declarations(content: str) -> dict[str, str]:
        sources: dict[str, str] = {}
        for source_id, url in SOURCE_RE.findall(content):
            sources[source_id.upper()] = url.rstrip(".,;:")
        return sources

    @staticmethod
    def _claim_ids(content: str) -> set[str]:
        return {value.upper() for value in CLAIM_RE.findall(content)}

    @staticmethod
    def _claim_source_relations(content: str) -> dict[str, set[str]]:
        relations: dict[str, set[str]] = {}
        for line in content.splitlines():
            claims = {value.upper() for value in CLAIM_RE.findall(line)}
            sources = {value.upper() for value in SOURCE_REFERENCE_RE.findall(line)}
            if not claims or not sources:
                continue
            for claim in claims:
                relations.setdefault(claim, set()).update(sources)
        return relations

    @staticmethod
    def _verification_decisions(content: str) -> dict[str, dict[str, Any]]:
        decisions: dict[str, dict[str, Any]] = {}
        for line in content.splitlines():
            claim_match = CLAIM_RE.search(line)
            status_match = STATUS_RE.search(line)
            if claim_match is None or status_match is None:
                continue
            claim_id = claim_match.group(1).upper()
            decisions[claim_id] = {
                "status": status_match.group(1).upper(),
                "sources": {
                    value.upper() for value in SOURCE_REFERENCE_RE.findall(line)
                },
            }
        return decisions

    def _approved_claims(self, verification: str) -> set[str]:
        return {
            claim_id
            for claim_id, decision in self._verification_decisions(verification).items()
            if decision["status"] == "APROBADA"
        }

    @classmethod
    def _semantic_overlap(cls, content: str, sources: Iterable[str]) -> float:
        source_tokens: set[str] = set()
        for source in sources:
            source_tokens.update(cls._tokens(source))
        return cls._overlap(cls._tokens(content), source_tokens)

    @staticmethod
    def _overlap(left: set[str], right: set[str]) -> float:
        if not left or not right:
            return 0.0
        return len(left & right) / min(len(left), len(right))

    @staticmethod
    def _tokens(content: str) -> set[str]:
        normalized = unicodedata.normalize("NFKD", content.casefold())
        normalized = "".join(char for char in normalized if not unicodedata.combining(char))
        return {
            token
            for token in WORD_RE.findall(normalized)
            if len(token) >= 3 and token not in STOPWORDS
        }

    @staticmethod
    def _file_sha256(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    @staticmethod
    def _read_json_object(path: Path) -> dict[str, Any]:
        if not path.is_file():
            return {}
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"El archivo JSON debe contener un objeto: {path}")
        return data

    @staticmethod
    def _write_json_atomic(path: Path, data: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(f"{path.suffix}.tmp")
        try:
            temporary.write_text(
                json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            temporary.replace(path)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise

    @staticmethod
    def _write_text_atomic(path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(f"{path.suffix}.tmp")
        try:
            temporary.write_text(content, encoding="utf-8")
            temporary.replace(path)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise

    def _base_metadata(self, runtime_context: RuntimeContext) -> dict[str, Any]:
        project = runtime_context.project
        return {
            "component": self.component_name,
            "project_id": project.project_id,
            "stage": project.stage_actual,
        }


__all__ = ["EditorialValidatorEngine"]
