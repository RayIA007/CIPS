"""Compile CIPS editorial artifacts into a universal production manifest.

This PM2 boundary reads the existing CIPS project layout, maps editorial
content to the provider-neutral PM1 domain, and persists the canonical JSON
through the F3 ``MetadataStore``.  It does not plan or resolve media assets,
render output, or contact external services.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import hashlib
import math
from pathlib import Path
import re
from typing import Any

from artifact_store import ArtifactWriteResult
from final_project_builder import FinalProjectBuilder
from metadata_store import MetadataStore
from production_manifest import (
    PRODUCTION_MANIFEST_FILENAME,
    AssetRequest,
    AssetType,
    AudioDesignSpec,
    CaptionSpec,
    NarrationSpec,
    OutputSpec,
    ProductionManifest,
    ProjectIdentity,
    PublicationSpec,
    QualityCategory,
    QualityRequirement,
    RequirementLevel,
    SceneSpec,
    SourceReference,
    SourceType,
    TargetPlatform,
    VisualDirection,
    deserialize_manifest,
    serialize_manifest,
)
from runtime_constants import STAGE_FILES
from runtime_models import FinalProjectObject, Project
from workspace_resolver import WorkspaceResolver


_EDITORIAL_STAGES = (
    "investigacion",
    "verificacion",
    "guion",
    "storyboard",
    "narracion",
    "seo",
    "publicacion",
)
_SOURCE_TYPES = {
    "investigacion": SourceType.RESEARCH,
    "verificacion": SourceType.VERIFICATION,
    "guion": SourceType.SCRIPT,
    "storyboard": SourceType.STORYBOARD,
    "narracion": SourceType.NARRATION,
    "seo": SourceType.SEO,
    # PM1 has one neutral SEO/publication provenance category.
    "publicacion": SourceType.SEO,
}
_SOURCE_TITLES = {
    "investigacion": "Investigación editorial",
    "verificacion": "Verificación editorial",
    "guion": "Guion editorial",
    "storyboard": "Storyboard editorial",
    "narracion": "Narración editorial",
    "seo": "Metadata SEO",
    "publicacion": "Instrucciones de publicación",
}
_VERTICAL_PLATFORMS = {
    TargetPlatform.YOUTUBE_SHORTS,
    TargetPlatform.TIKTOK,
    TargetPlatform.INSTAGRAM_REELS,
    TargetPlatform.FACEBOOK_REELS,
}
_PLATFORM_ALIASES = {
    "youtube": TargetPlatform.YOUTUBE_SHORTS,
    "youtube_short": TargetPlatform.YOUTUBE_SHORTS,
    "youtube_shorts": TargetPlatform.YOUTUBE_SHORTS,
    "shorts": TargetPlatform.YOUTUBE_SHORTS,
    "tiktok": TargetPlatform.TIKTOK,
    "instagram": TargetPlatform.INSTAGRAM_REELS,
    "instagram_reels": TargetPlatform.INSTAGRAM_REELS,
    "reels": TargetPlatform.INSTAGRAM_REELS,
    "facebook": TargetPlatform.FACEBOOK_REELS,
    "facebook_reels": TargetPlatform.FACEBOOK_REELS,
    "generic": TargetPlatform.GENERIC,
}
_LOCALE_ALIASES = {
    "es": "es-MX",
    "espanol": "es-MX",
    "español": "es-MX",
    "spanish": "es-MX",
    "en": "en-US",
    "english": "en-US",
    "ingles": "en-US",
    "inglés": "en-US",
}
_PENDING_MARKERS = {
    "pendiente",
    "por completar",
    "contenido pendiente",
    "sin contenido",
    "todo",
}
_WORD_PATTERN = re.compile(r"\b[\wÁÉÍÓÚÜÑáéíóúüñ'-]+\b", re.UNICODE)
_SCENE_HEADING_PATTERN = re.compile(
    r"(?im)^\s{0,3}#{1,6}\s*(?:escena|scene|shot|toma)\s*(\d+)?\s*[:.-]?\s*(.*?)\s*$"
)
_TIME_RANGE_PATTERN = re.compile(
    r"(?P<start>\d{1,2}:(?:\d{2})(?::\d{2})?(?:[.,]\d+)?)\s*[-–—>]\s*"
    r"(?P<end>\d{1,2}:(?:\d{2})(?::\d{2})?(?:[.,]\d+)?)"
)


class ProductionManifestCompilationError(ValueError):
    """Base error for invalid or incomplete editorial compilation input."""


class MissingEditorialArtifactError(ProductionManifestCompilationError):
    """One or more mandatory PM2 editorial artifacts are absent or pending."""


class EditorialFormatError(ProductionManifestCompilationError):
    """An editorial artifact cannot be mapped deterministically."""


@dataclass(frozen=True, slots=True)
class ManifestPersistenceResult:
    """Validated manifest plus its physical F3 persistence evidence."""

    manifest: ProductionManifest
    artifact_write: ArtifactWriteResult
    manifest_path: Path


@dataclass(frozen=True, slots=True)
class _SceneDraft:
    label: str
    visual_intent: str
    timing_label: str | None = None


class ProductionManifestCompiler:
    """Compile the current CIPS editorial project contract into PM1 models."""

    compiler_name = "cips.production_manifest_compiler"
    compiler_version = "1.0"

    def __init__(
        self,
        *,
        workspace_resolver: WorkspaceResolver | None = None,
        metadata_store: MetadataStore | None = None,
        final_project_builder: FinalProjectBuilder | None = None,
    ) -> None:
        if metadata_store is not None and workspace_resolver is not None:
            if metadata_store.workspace_resolver is not workspace_resolver:
                raise ValueError(
                    "metadata_store y workspace_resolver deben compartir la misma instancia."
                )
        if metadata_store is None:
            resolver = workspace_resolver or WorkspaceResolver()
            metadata_store = MetadataStore(resolver)
        self._metadata_store = metadata_store
        self._final_project_builder = final_project_builder or FinalProjectBuilder()

    @property
    def metadata_store(self) -> MetadataStore:
        return self._metadata_store

    def compile(
        self,
        project_input: FinalProjectObject | Project | str | Path,
        *,
        configuration: Mapping[str, Any] | None = None,
    ) -> ProductionManifest:
        """Build and validate a deterministic manifest without writing files."""

        final_project = self._resolve_final_project(project_input)
        contents = self._require_editorial_contents(final_project)
        settings = self._build_settings(final_project, configuration)

        narration_text = self._normalize_narration(contents["narracion"])
        scene_drafts = self._parse_storyboard(contents["storyboard"])
        narration_chunks = self._partition_narration(
            narration_text,
            len(scene_drafts),
        )
        source_references = self._build_source_references(final_project, contents)
        source_ids = tuple(reference.source_id for reference in source_references)

        pace = self._positive_int(
            settings.get("narration_pace_words_per_minute", 150),
            "narration_pace_words_per_minute",
            minimum=60,
            maximum=260,
        )
        estimated_duration = self._estimated_duration_seconds(narration_text, pace)
        requested_duration = self._duration_setting(settings, contents)
        output_duration = round(max(estimated_duration, requested_duration or 0.0), 6)
        scene_durations = self._allocate_scene_durations(
            narration_chunks,
            output_duration,
        )

        platform = self._target_platform(settings, contents)
        width, height, aspect_ratio = self._output_geometry(platform, settings)
        fps = self._positive_float(settings.get("fps", 30.0), "fps")
        if fps > 240.0:
            raise EditorialFormatError("fps no puede exceder 240.")

        scenes: list[SceneSpec] = []
        start_seconds = 0.0
        for sequence, (draft, narration, duration) in enumerate(
            zip(scene_drafts, narration_chunks, scene_durations),
            start=1,
        ):
            metadata: dict[str, str | int] = {
                "editorial_scene_label": draft.label,
                "editorial_scene_sequence": sequence,
                "timing_basis": "narration_word_weighted",
            }
            if draft.timing_label is not None:
                metadata["editorial_timing_label"] = draft.timing_label
            scenes.append(
                SceneSpec(
                    sequence=sequence,
                    start_seconds=float(round(start_seconds, 6)),
                    duration_seconds=float(duration),
                    narration_text=narration,
                    asset_request=AssetRequest(asset_type=AssetType.NONE),
                    visual_direction=VisualDirection(
                        intent=draft.visual_intent,
                        composition=(
                            "Composición pendiente de dirección creativa; "
                            "se conserva la intención del storyboard."
                        ),
                    ),
                    captions=CaptionSpec(),
                    source_reference_ids=source_ids,
                    metadata=metadata,
                )
            )
            start_seconds = round(start_seconds + duration, 6)

        publication = self._publication_spec(
            final_project=final_project,
            script=contents["guion"],
            seo=contents["seo"],
            publication=contents["publicacion"],
            narration=narration_text,
        )
        hook = self._extract_section(contents["guion"], ("hook", "gancho"))
        if not hook:
            hook = self._first_sentence(narration_text)

        project_id = self._identifier(final_project.project.project_id, "project_id")
        production_id = self._identifier(
            str(settings.get("production_id") or f"{project_id}-production"),
            "production_id",
        )
        revision = self._positive_int(settings.get("revision", 1), "revision")
        campaign_value = settings.get("campaign_id")
        campaign_id = (
            None
            if campaign_value in (None, "")
            else self._identifier(str(campaign_value), "campaign_id")
        )
        title = str(settings.get("title") or final_project.project.tema or publication.title).strip()
        if not title:
            title = publication.title

        manifest = ProductionManifest(
            project=ProjectIdentity(
                project_id=project_id,
                production_id=production_id,
                title=title,
                revision=revision,
                campaign_id=campaign_id,
            ),
            locale=self._locale(settings, contents),
            style_profile=self._identifier(
                str(settings.get("style_profile") or "editorial-default-v1"),
                "style_profile",
            ),
            output=OutputSpec(
                platform=platform,
                width_px=width,
                height_px=height,
                aspect_ratio=aspect_ratio,
                fps=float(fps),
                duration_seconds=float(output_duration),
            ),
            narration=NarrationSpec(
                full_text=narration_text,
                hook=hook,
                call_to_action=publication.call_to_action,
                voice_characteristics=self._text_tuple(
                    settings.get("voice_characteristics", ("clara", "natural"))
                ),
                pace_words_per_minute=pace,
                estimated_duration_seconds=float(estimated_duration),
                delivery_notes=self._optional_text(settings.get("delivery_notes")),
            ),
            scenes=tuple(scenes),
            audio_design=AudioDesignSpec(
                target_loudness_lufs=float(
                    self._bounded_float(
                        settings.get("target_loudness_lufs", -14.0),
                        "target_loudness_lufs",
                        -36.0,
                        -5.0,
                    )
                ),
                true_peak_dbfs=float(
                    self._bounded_float(
                        settings.get("true_peak_dbfs", -1.0),
                        "true_peak_dbfs",
                        -12.0,
                        0.0,
                    )
                ),
            ),
            publication=publication,
            quality_requirements=self._quality_requirements(
                width=width,
                height=height,
                duration=output_duration,
            ),
            source_references=source_references,
            metadata={
                "compiler": self.compiler_name,
                "compiler_version": self.compiler_version,
                "editorial_source_count": len(source_references),
                "timing_strategy": "narration_word_weighted",
            },
        )
        # Exercise the public PM1 serialization boundary before returning.
        return deserialize_manifest(serialize_manifest(manifest))

    def compile_and_persist(
        self,
        project_input: FinalProjectObject | Project | str | Path,
        *,
        configuration: Mapping[str, Any] | None = None,
        relative_path: str | Path = PRODUCTION_MANIFEST_FILENAME,
    ) -> ManifestPersistenceResult:
        """Compile and persist canonical ``production_manifest.json`` through F3."""

        final_project = self._resolve_final_project(project_input)
        manifest = self.compile(final_project, configuration=configuration)
        serialized = serialize_manifest(manifest).encode("utf-8")
        artifact_write = self._metadata_store.persist_bytes(
            workspace_root=final_project.project.path,
            relative_path=relative_path,
            content=serialized,
            artifact_type="production_manifest",
            mime_type="application/json",
            artifact_id=f"artifact-{manifest.manifest_id}",
            metadata={
                "schema_name": manifest.schema_name,
                "schema_version": manifest.schema_version.value,
                "manifest_id": manifest.manifest_id,
                "compiler": self.compiler_name,
                "compiler_version": self.compiler_version,
            },
        )
        manifest_path = Path(artifact_write.artifact.path)
        persisted = deserialize_manifest(manifest_path.read_bytes())
        if persisted != manifest:
            raise ProductionManifestCompilationError(
                "El manifest persistido por F3 no coincide con el manifest compilado."
            )
        return ManifestPersistenceResult(
            manifest=manifest,
            artifact_write=artifact_write,
            manifest_path=manifest_path,
        )

    def _resolve_final_project(
        self,
        project_input: FinalProjectObject | Project | str | Path,
    ) -> FinalProjectObject:
        if isinstance(project_input, FinalProjectObject):
            return project_input
        if not isinstance(project_input, (Project, str, Path)):
            raise TypeError(
                "project_input debe ser FinalProjectObject, Project, str o Path."
            )
        result = self._final_project_builder.execute(
            project_input=project_input,
            require_complete=False,
        )
        if not result.success or not isinstance(result.data, FinalProjectObject):
            details = "; ".join(result.errors)
            raise ProductionManifestCompilationError(
                "No fue posible leer el proyecto editorial."
                + (f" {details}" if details else "")
            )
        return result.data

    @staticmethod
    def _require_editorial_contents(final_project: FinalProjectObject) -> dict[str, str]:
        contents: dict[str, str] = {}
        missing: list[str] = []
        for stage in _EDITORIAL_STAGES:
            content = final_project.get_stage_content(stage).lstrip("\ufeff").strip()
            if not content:
                configured_path = final_project.source_files.get(stage)
                path = (
                    Path(configured_path)
                    if configured_path
                    else final_project.project.path / STAGE_FILES[stage]
                )
                if path.is_file():
                    content = path.read_text(encoding="utf-8").lstrip("\ufeff").strip()
            if not content or ProductionManifestCompiler._is_pending_content(content):
                missing.append(stage)
            else:
                contents[stage] = content
        if missing:
            raise MissingEditorialArtifactError(
                "Faltan artifacts editoriales completos: " + ", ".join(missing) + "."
            )
        return contents

    @staticmethod
    def _is_pending_content(content: str) -> bool:
        if len(_WORD_PATTERN.findall(content)) > 20:
            return False
        normalized = ProductionManifestCompiler._fold(content)
        return any(
            re.search(rf"\b{re.escape(marker)}\b", normalized)
            for marker in _PENDING_MARKERS
        )

    @staticmethod
    def _build_settings(
        final_project: FinalProjectObject,
        overrides: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        if overrides is not None and not isinstance(overrides, Mapping):
            raise TypeError("configuration debe ser Mapping.")
        merged: dict[str, Any] = {}
        sources: list[Mapping[str, Any]] = []
        project_data = final_project.metadata.get("project_data")
        if isinstance(project_data, Mapping):
            sources.append(project_data)
        if isinstance(final_project.project.metadata, Mapping):
            sources.append(final_project.project.metadata)
        if isinstance(final_project.project.config, Mapping):
            sources.append(final_project.project.config)

        for source in sources:
            for key, value in source.items():
                if key not in {"production_manifest", "manifest", "output"}:
                    merged.setdefault(str(key), value)
            for section_name in ("output", "manifest", "production_manifest"):
                section = source.get(section_name)
                if isinstance(section, Mapping):
                    merged.update(section)
        if overrides:
            merged.update(overrides)
        return merged

    def _build_source_references(
        self,
        final_project: FinalProjectObject,
        contents: Mapping[str, str],
    ) -> tuple[SourceReference, ...]:
        references: list[SourceReference] = []
        project_root = final_project.project.path.resolve(strict=False)
        for stage in _EDITORIAL_STAGES:
            configured_path = final_project.source_files.get(stage)
            path = (
                Path(configured_path)
                if configured_path
                else project_root / STAGE_FILES[stage]
            )
            resolved = path.expanduser().resolve(strict=False)
            try:
                uri = resolved.relative_to(project_root).as_posix()
            except ValueError:
                uri = path.as_posix()
            payload = (
                resolved.read_bytes()
                if resolved.is_file()
                else contents[stage].encode("utf-8")
            )
            references.append(
                SourceReference(
                    source_id=f"source-{stage}",
                    source_type=_SOURCE_TYPES[stage],
                    title=_SOURCE_TITLES[stage],
                    uri=uri,
                    locator="Documento completo",
                    content_hash=hashlib.sha256(payload).hexdigest(),
                )
            )
        return tuple(references)

    def _parse_storyboard(self, content: str) -> tuple[_SceneDraft, ...]:
        normalized = content.lstrip("\ufeff").strip()
        heading_matches = list(_SCENE_HEADING_PATTERN.finditer(normalized))
        drafts: list[_SceneDraft] = []
        if heading_matches:
            for index, match in enumerate(heading_matches):
                body_start = match.end()
                body_end = (
                    heading_matches[index + 1].start()
                    if index + 1 < len(heading_matches)
                    else len(normalized)
                )
                heading_suffix = match.group(2).strip()
                body = normalized[body_start:body_end].strip()
                combined = "\n".join(part for part in (heading_suffix, body) if part)
                intent = self._storyboard_intent(combined)
                timing = self._time_range_label(match.group(0) + "\n" + body)
                drafts.append(
                    _SceneDraft(
                        label=f"Escena {index + 1}",
                        visual_intent=intent,
                        timing_label=timing,
                    )
                )
        else:
            drafts.extend(self._parse_storyboard_table(normalized))
        if not drafts:
            raise EditorialFormatError(
                "El storyboard no contiene escenas reconocibles por encabezados o tabla Markdown."
            )
        return tuple(drafts)

    def _parse_storyboard_table(self, content: str) -> tuple[_SceneDraft, ...]:
        rows: list[list[str]] = []
        for line in content.splitlines():
            stripped = line.strip()
            if not stripped.startswith("|") or stripped.count("|") < 3:
                continue
            cells = [cell.strip() for cell in stripped.strip("|").split("|")]
            if all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells):
                continue
            rows.append(cells)
        if len(rows) < 2:
            return ()
        header = [self._fold(cell) for cell in rows[0]]
        scene_index = next(
            (
                index
                for index, value in enumerate(header)
                if any(token in value for token in ("escena", "scene", "visual", "shot"))
            ),
            1 if len(header) > 1 else 0,
        )
        time_index = next(
            (
                index
                for index, value in enumerate(header)
                if any(token in value for token in ("segundo", "tiempo", "time"))
            ),
            None,
        )
        drafts: list[_SceneDraft] = []
        for cells in rows[1:]:
            if scene_index >= len(cells):
                continue
            intent = self._clean_markdown(cells[scene_index])
            if not intent:
                continue
            timing = (
                self._time_range_label(cells[time_index])
                if time_index is not None and time_index < len(cells)
                else None
            )
            drafts.append(
                _SceneDraft(
                    label=f"Escena {len(drafts) + 1}",
                    visual_intent=intent,
                    timing_label=timing,
                )
            )
        return tuple(drafts)

    def _storyboard_intent(self, text: str) -> str:
        for labels in (
            ("intención visual", "intencion visual", "visual"),
            ("descripción", "descripcion", "escena"),
        ):
            value = self._extract_labeled_value(text, labels)
            if value:
                return self._clean_markdown(value)
        cleaned = self._clean_markdown(text)
        if not cleaned:
            raise EditorialFormatError("Una escena del storyboard no contiene intención visual.")
        return cleaned

    @staticmethod
    def _normalize_narration(content: str) -> str:
        lines = []
        for line in content.lstrip("\ufeff").splitlines():
            stripped = line.strip()
            if not stripped or re.fullmatch(r"#{1,6}\s*(narraci[oó]n|narration)\s*", stripped, re.I):
                continue
            lines.append(stripped)
        narration = re.sub(r"\s+", " ", " ".join(lines)).strip()
        if not narration or not _WORD_PATTERN.search(narration):
            raise EditorialFormatError("La narración no contiene texto utilizable.")
        return narration

    @staticmethod
    def _partition_narration(text: str, scene_count: int) -> tuple[str, ...]:
        if scene_count < 1:
            raise EditorialFormatError("scene_count debe ser positivo.")
        tokens = re.findall(r"\S+", text)
        if len(tokens) < scene_count:
            raise EditorialFormatError(
                "La narración no contiene suficientes palabras para mapear todas las escenas."
            )
        base, remainder = divmod(len(tokens), scene_count)
        chunks: list[str] = []
        cursor = 0
        for index in range(scene_count):
            size = base + (1 if index < remainder else 0)
            chunks.append(" ".join(tokens[cursor : cursor + size]))
            cursor += size
        return tuple(chunks)

    @staticmethod
    def _estimated_duration_seconds(text: str, pace: int) -> float:
        word_count = len(_WORD_PATTERN.findall(text))
        if word_count < 1:
            raise EditorialFormatError("No es posible estimar una narración sin palabras.")
        return float(round(max(0.001, word_count * 60.0 / pace), 6))

    @staticmethod
    def _allocate_scene_durations(
        narration_chunks: tuple[str, ...],
        total_duration: float,
    ) -> tuple[float, ...]:
        weights = [max(1, len(_WORD_PATTERN.findall(chunk))) for chunk in narration_chunks]
        weight_sum = sum(weights)
        durations: list[float] = []
        accumulated = 0.0
        for index, weight in enumerate(weights):
            if index == len(weights) - 1:
                duration = round(total_duration - accumulated, 6)
            else:
                duration = round(total_duration * weight / weight_sum, 6)
            if duration <= 0.0:
                raise EditorialFormatError("El cálculo de timings produjo una duración no positiva.")
            durations.append(float(duration))
            accumulated = round(accumulated + duration, 6)
        return tuple(durations)

    def _duration_setting(
        self,
        settings: Mapping[str, Any],
        contents: Mapping[str, str],
    ) -> float | None:
        configured = settings.get("target_duration_seconds", settings.get("duration_seconds"))
        if configured not in (None, ""):
            return self._positive_float(configured, "target_duration_seconds")
        for text in (contents["guion"], contents["storyboard"]):
            value = self._extract_labeled_value(
                text,
                ("duración", "duracion", "duración estimada", "duration"),
            )
            if value:
                match = re.search(r"\d+(?:[.,]\d+)?", value)
                if match:
                    return self._positive_float(
                        match.group(0).replace(",", "."),
                        "duration_seconds",
                    )
        return None

    def _publication_spec(
        self,
        *,
        final_project: FinalProjectObject,
        script: str,
        seo: str,
        publication: str,
        narration: str,
    ) -> PublicationSpec:
        combined = publication + "\n\n" + seo
        title = self._extract_labeled_value(combined, ("título", "titulo", "title"))
        title = title or final_project.project.tema or self._first_sentence(narration)
        description = self._extract_labeled_value(
            combined,
            ("descripción", "descripcion", "description"),
        )
        if not description:
            description = self._first_content_paragraph(publication)
        if not description:
            description = self._first_sentence(narration)
        hashtags_value = self._extract_labeled_value(combined, ("hashtags", "etiquetas")) or ""
        hashtags = tuple(
            match.group(1)
            for match in re.finditer(r"#([\wÁÉÍÓÚÜÑáéíóúüñ-]+)", hashtags_value)
        )
        keywords_value = self._extract_labeled_value(
            combined,
            ("palabras clave", "keywords"),
        )
        keywords = self._split_list(keywords_value)
        call_to_action = self._extract_labeled_value(
            combined,
            ("llamado a la acción", "llamada a la acción", "cta", "call to action"),
        )
        call_to_action = call_to_action or self._extract_section(
            script,
            ("llamado a la acción", "llamada a la acción", "cta", "conclusión"),
        )
        return PublicationSpec(
            title=self._clean_markdown(title),
            description=self._clean_markdown(description),
            hashtags=hashtags,
            keywords=keywords,
            call_to_action=(
                self._clean_markdown(call_to_action) if call_to_action else None
            ),
        )

    @staticmethod
    def _quality_requirements(
        *,
        width: int,
        height: int,
        duration: float,
    ) -> tuple[QualityRequirement, ...]:
        return (
            QualityRequirement(
                requirement_id="qa-resolution",
                category=QualityCategory.TECHNICAL,
                level=RequirementLevel.MUST,
                description="La salida debe conservar la resolución declarada.",
                metric="resolution",
                expected=f"{width}x{height}",
            ),
            QualityRequirement(
                requirement_id="qa-duration",
                category=QualityCategory.TECHNICAL,
                level=RequirementLevel.MUST,
                description="La salida debe conservar la duración de la timeline.",
                metric="duration_seconds",
                expected=float(duration),
            ),
            QualityRequirement(
                requirement_id="qa-caption-narration",
                category=QualityCategory.CAPTIONS,
                level=RequirementLevel.MUST,
                description="Los captions deben corresponder a la narración editorial.",
                metric="caption_narration_alignment",
                expected=True,
            ),
        )

    def _target_platform(
        self,
        settings: Mapping[str, Any],
        contents: Mapping[str, str],
    ) -> TargetPlatform:
        raw = settings.get("platform")
        if raw in (None, ""):
            raw = self._extract_labeled_value(
                contents["seo"] + "\n" + contents["guion"],
                ("plataforma", "platform"),
            )
        normalized = self._fold(str(raw or "youtube_shorts")).replace(" ", "_")
        if normalized in _PLATFORM_ALIASES:
            return _PLATFORM_ALIASES[normalized]
        try:
            return TargetPlatform(normalized)
        except ValueError as exc:
            raise EditorialFormatError(f"Plataforma no soportada: {raw!r}.") from exc

    def _output_geometry(
        self,
        platform: TargetPlatform,
        settings: Mapping[str, Any],
    ) -> tuple[int, int, str]:
        default_width, default_height = (
            (1080, 1920) if platform in _VERTICAL_PLATFORMS else (1920, 1080)
        )
        width = self._positive_int(settings.get("width_px", default_width), "width_px")
        height = self._positive_int(settings.get("height_px", default_height), "height_px")
        aspect_ratio = str(settings.get("aspect_ratio") or "").strip()
        if not aspect_ratio:
            divisor = math.gcd(width, height)
            aspect_ratio = f"{width // divisor}:{height // divisor}"
        return width, height, aspect_ratio

    def _locale(
        self,
        settings: Mapping[str, Any],
        contents: Mapping[str, str],
    ) -> str:
        raw = settings.get("locale") or settings.get("language")
        if raw in (None, ""):
            raw = self._extract_labeled_value(
                contents["investigacion"] + "\n" + contents["guion"],
                ("idioma", "locale", "language"),
            )
        value = str(raw or "es-MX").strip()
        return _LOCALE_ALIASES.get(self._fold(value), value)

    @staticmethod
    def _extract_labeled_value(text: str, labels: tuple[str, ...]) -> str | None:
        for label in labels:
            escaped = re.escape(label)
            inline = re.search(
                rf"(?im)^\s*(?:[-*]\s*)?(?:\*\*)?{escaped}(?:\*\*)?\s*:\s*(.+?)\s*$",
                text,
            )
            if inline:
                return inline.group(1).strip()
            heading = re.search(
                rf"(?ims)^\s{{0,3}}#{{1,6}}\s*{escaped}\s*$\s*(.+?)(?=^\s{{0,3}}#{{1,6}}\s|\Z)",
                text,
            )
            if heading:
                value = heading.group(1).strip()
                if value:
                    return value
        return None

    @classmethod
    def _extract_section(cls, text: str, labels: tuple[str, ...]) -> str | None:
        value = cls._extract_labeled_value(text, labels)
        return cls._clean_markdown(value) if value else None

    @staticmethod
    def _first_sentence(text: str) -> str:
        normalized = re.sub(r"\s+", " ", text).strip()
        match = re.match(r".+?[.!?…](?:\s|$)", normalized)
        return (match.group(0) if match else normalized).strip()

    @classmethod
    def _first_content_paragraph(cls, text: str) -> str | None:
        for paragraph in re.split(r"\n\s*\n", text):
            cleaned = cls._clean_markdown(paragraph)
            if cleaned and not cleaned.casefold().startswith(("seo", "publicación", "publicacion")):
                return cleaned
        return None

    @staticmethod
    def _clean_markdown(text: str | None) -> str:
        if text is None:
            return ""
        value = re.sub(r"(?m)^\s{0,3}#{1,6}\s*", "", text)
        value = re.sub(r"[*_`]+", "", value)
        value = re.sub(r"(?m)^\s*[-+]\s+", "", value)
        value = re.sub(r"\s+", " ", value).strip(" \t\r\n|:-")
        return value

    @staticmethod
    def _time_range_label(text: str) -> str | None:
        match = _TIME_RANGE_PATTERN.search(text)
        return match.group(0).strip() if match else None

    @staticmethod
    def _split_list(value: str | None) -> tuple[str, ...]:
        if not value:
            return ()
        items = [
            item.strip().lstrip("#")
            for item in re.split(r"[,;|\n]", value)
            if item.strip().lstrip("#")
        ]
        unique: list[str] = []
        seen: set[str] = set()
        for item in items:
            key = item.casefold()
            if key not in seen:
                seen.add(key)
                unique.append(item)
        return tuple(unique)

    @classmethod
    def _text_tuple(cls, value: Any) -> tuple[str, ...]:
        if isinstance(value, str):
            return cls._split_list(value)
        if isinstance(value, (list, tuple, set)):
            return tuple(str(item).strip() for item in value if str(item).strip())
        raise EditorialFormatError("voice_characteristics debe ser texto o colección.")

    @staticmethod
    def _optional_text(value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @staticmethod
    def _identifier(value: str, label: str) -> str:
        normalized = re.sub(r"\s+", "-", value.strip())
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", normalized):
            raise EditorialFormatError(
                f"{label} debe contener solo letras ASCII, números, punto, guion o guion bajo."
            )
        return normalized

    @staticmethod
    def _positive_float(value: Any, label: str) -> float:
        if isinstance(value, bool):
            raise EditorialFormatError(f"{label} debe ser numérico.")
        try:
            number = float(value)
        except (TypeError, ValueError) as exc:
            raise EditorialFormatError(f"{label} debe ser numérico.") from exc
        if not math.isfinite(number) or number <= 0.0:
            raise EditorialFormatError(f"{label} debe ser positivo y finito.")
        return number

    @classmethod
    def _bounded_float(
        cls,
        value: Any,
        label: str,
        minimum: float,
        maximum: float,
    ) -> float:
        if isinstance(value, bool):
            raise EditorialFormatError(f"{label} debe ser numérico.")
        try:
            number = float(value)
        except (TypeError, ValueError) as exc:
            raise EditorialFormatError(f"{label} debe ser numérico.") from exc
        if not math.isfinite(number) or not minimum <= number <= maximum:
            raise EditorialFormatError(
                f"{label} debe estar entre {minimum} y {maximum}."
            )
        return number

    @staticmethod
    def _positive_int(
        value: Any,
        label: str,
        *,
        minimum: int = 1,
        maximum: int | None = None,
    ) -> int:
        if isinstance(value, bool):
            raise EditorialFormatError(f"{label} debe ser entero.")
        try:
            number = int(value)
        except (TypeError, ValueError) as exc:
            raise EditorialFormatError(f"{label} debe ser entero.") from exc
        if str(value).strip() not in {str(number), f"{number}.0"} and not isinstance(value, int):
            raise EditorialFormatError(f"{label} debe ser entero.")
        if number < minimum or (maximum is not None and number > maximum):
            suffix = f" entre {minimum} y {maximum}" if maximum is not None else " positivo"
            raise EditorialFormatError(f"{label} debe ser{suffix}.")
        return number

    @staticmethod
    def _fold(value: str) -> str:
        translation = str.maketrans("áéíóúüñ", "aeiouun")
        return value.strip().casefold().translate(translation)


__all__ = [
    "EditorialFormatError",
    "ManifestPersistenceResult",
    "MissingEditorialArtifactError",
    "ProductionManifestCompilationError",
    "ProductionManifestCompiler",
]
