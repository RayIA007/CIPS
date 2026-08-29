"""Plan provider-neutral creative direction for a production manifest.

This PM3 boundary enriches the deterministic PM2 manifest with audiovisual
decisions that a later render boundary can consume.  It selects no concrete
service, resolves no physical asset, performs no network I/O, and renders no
media.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from artifact_store import ArtifactWriteResult, CollisionPolicy
from metadata_store import MetadataStore
from production_manifest import (
    PRODUCTION_MANIFEST_FILENAME,
    AssetRequest,
    AssetType,
    AudioDesignSpec,
    CameraMovement,
    CaptionSpec,
    CostHint,
    MotionSpec,
    MotionSpeed,
    MusicSpec,
    OnScreenTextSpec,
    ProductionManifest,
    QualityHint,
    SceneSpec,
    SoundEffectSpec,
    TextPlacement,
    TextStyleRole,
    TransitionKind,
    TransitionSpec,
    VisualDirection,
    deserialize_manifest,
    serialize_manifest,
)
from style_profiles import OutputLayoutFamily, classify_output_layout
from workspace_resolver import WorkspaceResolver

_WORD_PATTERN = re.compile(r"[\wÁÉÍÓÚÜÑáéíóúüñ'-]+", re.UNICODE)
_STOP_WORDS = {
    "a",
    "al",
    "and",
    "ante",
    "antes",
    "como",
    "con",
    "cuando",
    "de",
    "del",
    "despues",
    "el",
    "en",
    "es",
    "ese",
    "esta",
    "este",
    "for",
    "from",
    "hacia",
    "la",
    "las",
    "lo",
    "los",
    "mas",
    "no",
    "of",
    "on",
    "o",
    "para",
    "por",
    "que",
    "se",
    "sin",
    "su",
    "sus",
    "the",
    "to",
    "tu",
    "un",
    "una",
    "y",
}
_TEXT_CUES = {
    "afirmacion",
    "cifra",
    "frase",
    "hook",
    "mensaje",
    "pantalla",
    "pregunta",
    "texto",
    "titulo",
}
_MOTION_GRAPHIC_CUES = {
    "comparacion",
    "dato",
    "diagrama",
    "grafica",
    "hipotesis",
    "interfaz",
    "paso",
    "proceso",
    "secuencia",
    "sello",
    "timeline",
}
_STOCK_VIDEO_CUES = {
    "actividad",
    "ciudad",
    "equipo",
    "escenario",
    "fecha",
    "fuente",
    "lugar",
    "persona",
    "producto",
    "referencia",
}
_STOCK_IMAGE_CUES = {
    "archivo",
    "documento",
    "fotografia",
    "mapa",
    "retrato",
}
_AI_VIDEO_CUES = {
    "cinematico",
    "evolucion",
    "fantasia",
    "metamorfosis",
    "transformacion",
    "viaje",
}
_AI_IMAGE_CUES = {
    "abstracto",
    "concepto",
    "ilustracion",
    "imaginario",
    "metafora",
    "surrealista",
}


class CreativeDirectionPlanningError(ValueError):
    """The manifest or explicit PM3 planning inputs are inconsistent."""


@dataclass(frozen=True, slots=True)
class CreativeManifestPersistenceResult:
    """Enriched manifest plus its physical F3 persistence evidence."""

    manifest: ProductionManifest
    artifact_write: ArtifactWriteResult
    manifest_path: Path


class CreativeDirectionPlanner:
    """Deterministically enrich PM2 scenes with universal creative intent."""

    planner_name = "cips.creative_direction_planner"
    planner_version = "1.1"
    planning_strategy = "deterministic-editorial-heuristics"
    supported_on_screen_text_modes = frozenset({"auto", "captions_only"})

    def __init__(
        self,
        *,
        workspace_resolver: WorkspaceResolver | None = None,
        metadata_store: MetadataStore | None = None,
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

    @property
    def metadata_store(self) -> MetadataStore:
        return self._metadata_store

    def plan(
        self,
        manifest: ProductionManifest,
        *,
        asset_types: Mapping[str, AssetType | str] | None = None,
        existing_asset_ids: Mapping[str, str] | None = None,
        stock_queries: Mapping[str, str] | None = None,
        on_screen_text_mode: str = "auto",
    ) -> ProductionManifest:
        """Return a validated, enriched manifest without writing files.

        ``asset_types`` is an optional scene-id keyed editorial override.  It
        states only the universal asset need.  ``existing_asset_ids`` is
        required for scenes explicitly assigned ``existing_asset``.
        """

        if not isinstance(manifest, ProductionManifest):
            raise TypeError("manifest debe ser ProductionManifest.")
        text_mode = self._normalize_on_screen_text_mode(on_screen_text_mode)

        known_scene_ids = {scene.scene_id for scene in manifest.scenes}
        type_overrides = self._normalize_asset_type_overrides(
            asset_types,
            known_scene_ids,
        )
        asset_id_overrides = self._normalize_existing_asset_ids(
            existing_asset_ids,
            known_scene_ids,
        )
        stock_query_overrides = self._normalize_stock_queries(
            stock_queries,
            known_scene_ids,
        )
        unused_asset_ids = set(asset_id_overrides) - {
            scene_id
            for scene_id, asset_type in type_overrides.items()
            if asset_type is AssetType.EXISTING_ASSET
        }
        for scene in manifest.scenes:
            if (
                scene.asset_request.asset_type is AssetType.EXISTING_ASSET
                and scene.scene_id in asset_id_overrides
            ):
                unused_asset_ids.discard(scene.scene_id)
        if unused_asset_ids:
            raise CreativeDirectionPlanningError(
                "existing_asset_ids solo acepta escenas planificadas como existing_asset: "
                + ", ".join(sorted(unused_asset_ids))
                + "."
            )

        scenes: list[SceneSpec] = []
        generated_effects: list[SoundEffectSpec] = []
        scene_count = len(manifest.scenes)
        for index, scene in enumerate(manifest.scenes):
            narrative_role = self._narrative_role(index, scene_count)
            asset_type = type_overrides.get(scene.scene_id)
            if asset_type is None:
                asset_type = (
                    scene.asset_request.asset_type
                    if scene.asset_request.asset_type is not AssetType.NONE
                    else self._select_asset_type(scene, narrative_role)
                )

            existing_asset_id = asset_id_overrides.get(
                scene.scene_id,
                scene.asset_request.existing_asset_id,
            )
            if asset_type is AssetType.EXISTING_ASSET and existing_asset_id is None:
                raise CreativeDirectionPlanningError(
                    f"La escena '{scene.scene_id}' requiere existing_asset_id."
                )

            preserve_existing = (
                scene.metadata.get("creative_planner") == self.planner_name
                or scene.asset_request.asset_type is not AssetType.NONE
            ) and scene.scene_id not in type_overrides
            visual_direction = self._visual_direction(
                manifest,
                scene,
                asset_type,
                narrative_role,
                preserve_existing=preserve_existing,
            )
            motion = self._motion(
                scene,
                asset_type,
                narrative_role,
                preserve_existing=preserve_existing,
            )
            asset_request = (
                scene.asset_request
                if (
                    scene.asset_request.asset_type is not AssetType.NONE
                    and scene.scene_id not in type_overrides
                )
                else self._asset_request(
                    manifest,
                    scene,
                    asset_type,
                    existing_asset_id,
                    visual_direction,
                    motion,
                )
            )
            stock_query_override = stock_query_overrides.get(scene.scene_id)
            if stock_query_override is not None:
                if asset_request.asset_type not in {
                    AssetType.STOCK_IMAGE,
                    AssetType.STOCK_VIDEO,
                }:
                    raise CreativeDirectionPlanningError(
                        "stock_queries solo acepta escenas stock_image/stock_video: "
                        f"{scene.scene_id}."
                    )
                asset_request = asset_request.model_copy(
                    update={"stock_query": stock_query_override},
                )
            on_screen_text = self._on_screen_text(
                scene,
                narrative_role,
                mode=text_mode,
            )
            captions = self._captions(scene)
            transition_in, transition_out = self._transitions(
                scene,
                index,
                scene_count,
                preserve_existing=preserve_existing,
            )
            metadata = dict(scene.metadata)
            metadata.update(
                {
                    "creative_planner": self.planner_name,
                    "creative_planner_version": self.planner_version,
                    "music_energy": self._scene_music_energy(narrative_role),
                    "music_mood": self._scene_music_mood(narrative_role),
                    "narrative_role": narrative_role,
                    "on_screen_text_mode": text_mode,
                    "planned_asset_type": asset_type.value,
                }
            )
            planned_scene = SceneSpec(
                scene_id=scene.scene_id,
                sequence=scene.sequence,
                start_seconds=scene.start_seconds,
                duration_seconds=scene.duration_seconds,
                narration_text=scene.narration_text,
                asset_request=asset_request,
                visual_direction=visual_direction,
                motion=motion,
                on_screen_text=on_screen_text,
                captions=captions,
                transition_in=transition_in,
                transition_out=transition_out,
                source_reference_ids=scene.source_reference_ids,
                metadata=metadata,
            )
            scenes.append(planned_scene)
            generated_effects.append(self._sound_effect(planned_scene, narrative_role))

        source_hash = self._source_manifest_hash(manifest)
        root_metadata = dict(manifest.metadata)
        root_metadata.update(
            {
                "creative_planner": self.planner_name,
                "creative_planner_version": self.planner_version,
                "creative_planning_strategy": self.planning_strategy,
                "creative_source_manifest_sha256": source_hash,
                "on_screen_text_mode": text_mode,
            }
        )
        audio_design = AudioDesignSpec(
            target_loudness_lufs=manifest.audio_design.target_loudness_lufs,
            true_peak_dbfs=manifest.audio_design.true_peak_dbfs,
            voice_gain_db=manifest.audio_design.voice_gain_db,
            music=(
                manifest.audio_design.music
                if manifest.audio_design.music is not None
                else self._music(manifest)
            ),
            sound_effects=(
                manifest.audio_design.sound_effects
                if manifest.audio_design.sound_effects
                else tuple(generated_effects)
            ),
        )
        planned = ProductionManifest(
            schema_name=manifest.schema_name,
            schema_version=manifest.schema_version,
            manifest_id=manifest.manifest_id,
            project=manifest.project,
            locale=manifest.locale,
            style_profile=manifest.style_profile,
            output=manifest.output,
            narration=manifest.narration,
            scenes=tuple(scenes),
            audio_design=audio_design,
            publication=manifest.publication,
            quality_requirements=manifest.quality_requirements,
            source_references=manifest.source_references,
            metadata=root_metadata,
        )
        return deserialize_manifest(serialize_manifest(planned))

    def plan_and_persist(
        self,
        manifest: ProductionManifest,
        *,
        workspace_root: str | Path,
        relative_path: str | Path = PRODUCTION_MANIFEST_FILENAME,
        asset_types: Mapping[str, AssetType | str] | None = None,
        existing_asset_ids: Mapping[str, str] | None = None,
        stock_queries: Mapping[str, str] | None = None,
        on_screen_text_mode: str = "auto",
    ) -> CreativeManifestPersistenceResult:
        """Plan and persist the canonical enriched manifest through F3."""

        planned = self.plan(
            manifest,
            asset_types=asset_types,
            existing_asset_ids=existing_asset_ids,
            stock_queries=stock_queries,
            on_screen_text_mode=on_screen_text_mode,
        )
        serialized = serialize_manifest(planned).encode("utf-8")
        source_hash = str(planned.metadata["creative_source_manifest_sha256"])
        artifact_write = self._metadata_store.persist_bytes(
            workspace_root=workspace_root,
            relative_path=relative_path,
            content=serialized,
            artifact_type="production_manifest",
            mime_type="application/json",
            artifact_id=(
                f"artifact-{planned.manifest_id}-creative-"
                f"{self.planner_version.replace('.', '-')}"
            ),
            metadata={
                "schema_name": planned.schema_name,
                "schema_version": planned.schema_version.value,
                "manifest_id": planned.manifest_id,
                "planner": self.planner_name,
                "planner_version": self.planner_version,
                "source_manifest_sha256": source_hash,
            },
            collision_policy=CollisionPolicy.REPLACE,
        )
        manifest_path = Path(artifact_write.artifact.path)
        persisted = deserialize_manifest(manifest_path.read_bytes())
        if persisted != planned:
            raise CreativeDirectionPlanningError(
                "El manifest creativo persistido por F3 no coincide con el planificado."
            )
        return CreativeManifestPersistenceResult(
            manifest=planned,
            artifact_write=artifact_write,
            manifest_path=manifest_path,
        )

    @staticmethod
    def _normalize_asset_type_overrides(
        values: Mapping[str, AssetType | str] | None,
        known_scene_ids: set[str],
    ) -> dict[str, AssetType]:
        if values is None:
            return {}
        if not isinstance(values, Mapping):
            raise TypeError("asset_types debe ser Mapping por scene_id.")
        unknown = sorted(set(values) - known_scene_ids)
        if unknown:
            raise CreativeDirectionPlanningError(
                "asset_types contiene scene_id desconocidos: "
                + ", ".join(unknown)
                + "."
            )
        normalized: dict[str, AssetType] = {}
        for scene_id, value in values.items():
            try:
                normalized[scene_id] = AssetType(value)
            except (TypeError, ValueError) as exc:
                raise CreativeDirectionPlanningError(
                    f"asset_type inválido para la escena '{scene_id}': {value!r}."
                ) from exc
        return normalized

    @staticmethod
    def _normalize_existing_asset_ids(
        values: Mapping[str, str] | None,
        known_scene_ids: set[str],
    ) -> dict[str, str]:
        if values is None:
            return {}
        if not isinstance(values, Mapping):
            raise TypeError("existing_asset_ids debe ser Mapping por scene_id.")
        unknown = sorted(set(values) - known_scene_ids)
        if unknown:
            raise CreativeDirectionPlanningError(
                "existing_asset_ids contiene scene_id desconocidos: "
                + ", ".join(unknown)
                + "."
            )
        normalized: dict[str, str] = {}
        for scene_id, value in values.items():
            text = str(value).strip()
            if not text:
                raise CreativeDirectionPlanningError(
                    f"existing_asset_id vacío para la escena '{scene_id}'."
                )
            normalized[scene_id] = text
        return normalized

    @staticmethod
    def _normalize_stock_queries(
        values: Mapping[str, str] | None,
        known_scene_ids: set[str],
    ) -> dict[str, str]:
        if values is None:
            return {}
        if not isinstance(values, Mapping):
            raise TypeError("stock_queries debe ser Mapping por scene_id.")
        unknown = sorted(set(values) - known_scene_ids)
        if unknown:
            raise CreativeDirectionPlanningError(
                "stock_queries contiene scene_id desconocidos: "
                + ", ".join(unknown)
                + "."
            )
        normalized: dict[str, str] = {}
        for scene_id, value in values.items():
            text = " ".join(str(value).split())
            if not text:
                raise CreativeDirectionPlanningError(
                    f"stock_query vacío para la escena '{scene_id}'."
                )
            normalized[scene_id] = text
        return normalized

    @classmethod
    def _select_asset_type(cls, scene: SceneSpec, narrative_role: str) -> AssetType:
        search_text = cls._fold(
            " ".join(
                (
                    str(scene.metadata.get("editorial_scene_label", "")),
                    scene.visual_direction.intent,
                    scene.narration_text or "",
                )
            )
        )
        tokens = set(_WORD_PATTERN.findall(search_text))
        scored = (
            (AssetType.TEXT_GRAPHIC, len(tokens & _TEXT_CUES)),
            (AssetType.MOTION_GRAPHIC, len(tokens & _MOTION_GRAPHIC_CUES)),
            (AssetType.STOCK_VIDEO, len(tokens & _STOCK_VIDEO_CUES)),
            (AssetType.STOCK_IMAGE, len(tokens & _STOCK_IMAGE_CUES)),
            (AssetType.AI_VIDEO, len(tokens & _AI_VIDEO_CUES)),
            (AssetType.AI_IMAGE, len(tokens & _AI_IMAGE_CUES)),
        )
        best_type, best_score = max(scored, key=lambda item: item[1])
        if best_score > 0:
            return best_type
        if narrative_role == "hook":
            return AssetType.AI_VIDEO
        if narrative_role == "resolution":
            return AssetType.MOTION_GRAPHIC
        return AssetType.STOCK_VIDEO

    @classmethod
    def _visual_direction(
        cls,
        manifest: ProductionManifest,
        scene: SceneSpec,
        asset_type: AssetType,
        narrative_role: str,
        *,
        preserve_existing: bool,
    ) -> VisualDirection:
        existing = scene.visual_direction
        placeholder = "pendiente de direccion creativa" in cls._fold(
            existing.composition
        )
        if preserve_existing and not placeholder:
            return existing

        layout_family = classify_output_layout(
            manifest.output.width_px,
            manifest.output.height_px,
        )
        format_label = cls._format_label(layout_family)
        if layout_family is OutputLayoutFamily.VERTICAL:
            compositions = {
                "hook": (
                    "Elemento focal de alto contraste en el centro del encuadre vertical, "
                    "con espacio inferior limpio para captions."
                ),
                "explanation": (
                    "Progresión visual en profundidad y lectura de arriba hacia abajo, "
                    "con acciones claramente separadas dentro del encuadre vertical."
                ),
                "resolution": (
                    "Resultado visual dominante en el centro y cierre ascendente hacia el CTA, "
                    "manteniendo libre la zona inferior de captions."
                ),
            }
        else:
            compositions = {
                "hook": (
                    f"Elemento focal de alto contraste en el centro del encuadre {format_label}, "
                    "con una zona segura limpia para captions."
                ),
                "explanation": (
                    f"Progresión visual en profundidad adaptada al encuadre {format_label}, "
                    "con acciones claramente separadas y lectura natural."
                ),
                "resolution": (
                    f"Resultado visual dominante y cierre hacia el CTA en encuadre {format_label}, "
                    "manteniendo libre la zona segura de captions."
                ),
            }
        palettes = {
            "hook": ("#111827", "#F59E0B", "#F8FAFC"),
            "explanation": ("#111827", "#22D3EE", "#F8FAFC"),
            "resolution": ("#111827", "#10B981", "#F8FAFC"),
        }
        subjects = cls._keywords(
            f"{existing.intent} {scene.narration_text or ''}",
            limit=4,
        )
        asset_label = asset_type.value.replace("_", " ")
        return VisualDirection(
            intent=existing.intent,
            composition=compositions[narrative_role],
            subjects=subjects or ("concepto editorial principal",),
            environment=(
                f"Escena {format_label} coherente con el perfil {manifest.style_profile} "
                f"y resuelta como {asset_label}."
            ),
            lighting=(
                "Alto contraste legible en pantalla móvil, con profundidad controlada."
                if layout_family is OutputLayoutFamily.VERTICAL
                else "Contraste legible en el formato de salida, con profundidad controlada."
            ),
            color_palette=palettes[narrative_role],
            negative_constraints=(
                "sin logotipos de proveedores",
                "sin marcas de agua",
                "sin texto ilegible",
                "sin elementos fuera del área segura",
            ),
            continuity_notes=(
                f"Conservar tipografía, contraste y continuidad cromática de "
                f"{manifest.style_profile}."
            ),
        )

    @staticmethod
    def _motion(
        scene: SceneSpec,
        asset_type: AssetType,
        narrative_role: str,
        *,
        preserve_existing: bool,
    ) -> MotionSpec:
        if preserve_existing:
            return scene.motion
        if asset_type is AssetType.NONE:
            return MotionSpec()
        if asset_type in {AssetType.AI_IMAGE, AssetType.STOCK_IMAGE}:
            return MotionSpec(
                camera_movement=CameraMovement.ZOOM,
                speed=MotionSpeed.SLOW,
                intensity=0.3,
                direction="acercamiento gradual al sujeto principal",
                subject_movement="Parallax sutil entre primer plano y fondo.",
            )
        if narrative_role == "hook":
            return MotionSpec(
                camera_movement=CameraMovement.ZOOM,
                speed=MotionSpeed.FAST,
                intensity=0.65,
                direction="hacia el elemento focal",
                subject_movement="Entrada escalonada de los elementos principales.",
            )
        if narrative_role == "resolution":
            return MotionSpec(
                camera_movement=CameraMovement.DOLLY,
                speed=MotionSpeed.SLOW,
                intensity=0.35,
                direction="alejamiento breve para revelar el resultado",
                subject_movement="Convergencia de elementos hacia el cierre visual.",
            )
        return MotionSpec(
            camera_movement=CameraMovement.TRACKING,
            speed=MotionSpeed.MEDIUM,
            intensity=0.45,
            direction="de izquierda a derecha siguiendo la progresión narrativa",
            subject_movement="Los elementos aparecen en el orden explicado por la narración.",
        )

    @classmethod
    def _asset_request(
        cls,
        manifest: ProductionManifest,
        scene: SceneSpec,
        asset_type: AssetType,
        existing_asset_id: str | None,
        visual: VisualDirection,
        motion: MotionSpec,
    ) -> AssetRequest:
        if asset_type is AssetType.NONE:
            return AssetRequest(
                asset_type=AssetType.NONE,
                quality_hint=QualityHint.STANDARD,
                cost_hint=CostHint.FREE,
            )

        brief = (
            f"Escena {scene.sequence}: {visual.intent} Debe funcionar en "
            f"{manifest.output.aspect_ratio}, respetar el área segura y sostener "
            f"la narración durante {scene.duration_seconds:.2f} segundos."
        )
        common: dict[str, Any] = {
            "asset_type": asset_type,
            "creative_brief": brief,
            "quality_hint": (
                QualityHint.HIGH
                if asset_type
                in {AssetType.AI_VIDEO, AssetType.STOCK_VIDEO, AssetType.MOTION_GRAPHIC}
                else QualityHint.STANDARD
            ),
            "cost_hint": cls._cost_hint(asset_type),
        }
        if asset_type is AssetType.AI_IMAGE:
            common["image_prompt"] = cls._image_prompt(manifest, visual)
        elif asset_type is AssetType.AI_VIDEO:
            common["video_prompt"] = cls._video_prompt(manifest, visual, motion)
        elif asset_type in {AssetType.STOCK_IMAGE, AssetType.STOCK_VIDEO}:
            common["stock_query"] = cls._stock_query(
                manifest,
                scene,
                visual,
                asset_type,
            )
        elif asset_type is AssetType.EXISTING_ASSET:
            common["existing_asset_id"] = existing_asset_id
        return AssetRequest(**common)

    @staticmethod
    def _cost_hint(asset_type: AssetType) -> CostHint:
        if asset_type in {AssetType.EXISTING_ASSET, AssetType.NONE}:
            return CostHint.FREE
        if asset_type in {
            AssetType.STOCK_IMAGE,
            AssetType.STOCK_VIDEO,
            AssetType.MOTION_GRAPHIC,
            AssetType.TEXT_GRAPHIC,
        }:
            return CostHint.LOW
        return CostHint.BALANCED

    @staticmethod
    def _image_prompt(manifest: ProductionManifest, visual: VisualDirection) -> str:
        family = classify_output_layout(
            manifest.output.width_px,
            manifest.output.height_px,
        )
        format_label = CreativeDirectionPlanner._format_label(family)
        return (
            f"Imagen {format_label} {manifest.output.aspect_ratio}. {visual.intent} "
            f"Composición: {visual.composition} Sujetos: {', '.join(visual.subjects)}. "
            f"Ambiente: {visual.environment} Iluminación: {visual.lighting} "
            f"Paleta: {', '.join(visual.color_palette)}. "
            f"Restricciones: {', '.join(visual.negative_constraints)}."
        )

    @classmethod
    def _video_prompt(
        cls,
        manifest: ProductionManifest,
        visual: VisualDirection,
        motion: MotionSpec,
    ) -> str:
        image_basis = cls._image_prompt(manifest, visual)
        return (
            f"{image_basis} Cámara: {motion.camera_movement.value}, "
            f"velocidad {motion.speed.value}, intensidad {motion.intensity:.2f}. "
            f"Dirección: {motion.direction or 'centrada'}. "
            f"Movimiento del sujeto: {motion.subject_movement or 'natural y controlado'}."
        )

    @classmethod
    def _stock_query(
        cls,
        manifest: ProductionManifest,
        scene: SceneSpec,
        visual: VisualDirection,
        asset_type: AssetType,
    ) -> str:
        keywords = cls._keywords(
            " ".join(
                (
                    visual.intent,
                    " ".join(visual.subjects),
                    scene.narration_text or "",
                )
            ),
            limit=8,
        )
        medium = "video" if asset_type is AssetType.STOCK_VIDEO else "fotografía"
        family = classify_output_layout(
            manifest.output.width_px,
            manifest.output.height_px,
        )
        return " ".join((*keywords, cls._format_label(family), medium))

    @staticmethod
    def _format_label(family: OutputLayoutFamily) -> str:
        return {
            OutputLayoutFamily.VERTICAL: "vertical",
            OutputLayoutFamily.HORIZONTAL: "horizontal",
            OutputLayoutFamily.SQUARE: "cuadrado",
        }[family]

    @classmethod
    def _on_screen_text(
        cls,
        scene: SceneSpec,
        narrative_role: str,
        *,
        mode: str,
    ) -> tuple[OnScreenTextSpec, ...]:
        if mode == "captions_only":
            return ()
        if scene.on_screen_text:
            return scene.on_screen_text
        source = scene.narration_text or scene.visual_direction.intent
        words = source.split()
        text = " ".join(words[:7]).rstrip(".,;:!?¡¿")
        if len(words) > 7:
            text += "…"
        start = 0.0 if scene.duration_seconds <= 0.5 else 0.2
        duration = min(4.5, scene.duration_seconds - start)
        roles = {
            "hook": TextStyleRole.HOOK,
            "explanation": TextStyleRole.EMPHASIS,
            "resolution": TextStyleRole.CTA,
        }
        placements = {
            "hook": TextPlacement.CENTER,
            "explanation": TextPlacement.UPPER_THIRD,
            "resolution": TextPlacement.CENTER,
        }
        return (
            OnScreenTextSpec(
                text_id=f"text-{scene.sequence:03d}-primary",
                text=text,
                start_offset_seconds=float(start),
                duration_seconds=float(duration),
                placement=placements[narrative_role],
                style_role=roles[narrative_role],
                accessibility_label=f"Texto principal de la escena {scene.sequence}: {text}",
            ),
        )

    @classmethod
    def _normalize_on_screen_text_mode(cls, value: str) -> str:
        if not isinstance(value, str):
            raise TypeError("on_screen_text_mode debe ser texto.")
        normalized = value.strip().casefold()
        if normalized not in cls.supported_on_screen_text_modes:
            raise CreativeDirectionPlanningError(
                "on_screen_text_mode no soportado: "
                f"{value!r}; usa auto o captions_only."
            )
        return normalized

    @classmethod
    def _captions(cls, scene: SceneSpec) -> CaptionSpec | None:
        if scene.narration_text is None:
            return scene.captions
        if scene.captions is not None and scene.captions.emphasis_words:
            return scene.captions
        existing = scene.captions or CaptionSpec()
        return CaptionSpec(
            mode=existing.mode,
            custom_text=existing.custom_text,
            emphasis_words=cls._keywords(scene.narration_text, limit=3),
            max_characters_per_line=existing.max_characters_per_line,
            max_lines=existing.max_lines,
            placement=existing.placement,
            respect_safe_area=existing.respect_safe_area,
        )

    @classmethod
    def _transitions(
        cls,
        scene: SceneSpec,
        index: int,
        scene_count: int,
        *,
        preserve_existing: bool,
    ) -> tuple[TransitionSpec, TransitionSpec]:
        if preserve_existing:
            return scene.transition_in, scene.transition_out
        duration = float(min(0.3, scene.duration_seconds * 0.15))
        transition_in = (
            TransitionSpec()
            if index == 0
            else cls._boundary_transition(index - 1, duration)
        )
        transition_out = (
            TransitionSpec(kind=TransitionKind.FADE, duration_seconds=duration)
            if index == scene_count - 1
            else cls._boundary_transition(index, duration)
        )
        return transition_in, transition_out

    @staticmethod
    def _boundary_transition(boundary_index: int, duration: float) -> TransitionSpec:
        kinds = (
            TransitionKind.SLIDE,
            TransitionKind.ZOOM,
            TransitionKind.DISSOLVE,
        )
        kind = kinds[boundary_index % len(kinds)]
        return TransitionSpec(
            kind=kind,
            duration_seconds=duration,
            direction="left" if kind is TransitionKind.SLIDE else None,
        )

    @staticmethod
    def _sound_effect(scene: SceneSpec, narrative_role: str) -> SoundEffectSpec:
        descriptions = {
            "hook": "Whoosh breve al entrar el elemento focal.",
            "explanation": "Pulso suave al avanzar al siguiente punto visual.",
            "resolution": "Impacto suave al aparecer el resultado o CTA.",
        }
        start = float(min(0.6, scene.duration_seconds * 0.12))
        duration = float(min(0.5, scene.duration_seconds * 0.12))
        return SoundEffectSpec(
            cue_id=f"sfx-{scene.sequence:03d}-{narrative_role}",
            scene_id=scene.scene_id,
            description=descriptions[narrative_role],
            start_offset_seconds=start,
            duration_seconds=duration,
            intensity={"hook": 0.55, "explanation": 0.35, "resolution": 0.45}[
                narrative_role
            ],
        )

    @classmethod
    def _music(cls, manifest: ProductionManifest) -> MusicSpec:
        folded = cls._fold(
            f"{manifest.project.title} {manifest.narration.full_text} {manifest.style_profile}"
        )
        if any(token in folded for token in ("verific", "fuente", "dato", "noticia")):
            mood = "analítico, moderno y confiable"
            energy = 0.62
        elif any(token in folded for token in ("motiv", "logro", "cambio", "crece")):
            mood = "optimista, ascendente y motivador"
            energy = 0.72
        else:
            mood = "dinámico, contemporáneo y claro"
            energy = 0.66
        return MusicSpec(
            mood=mood,
            energy=float(energy),
            ducking_db=-9.0,
            instrumental_preferred=True,
            creative_brief=(
                "Base instrumental con pulso definido, apertura inmediata para el hook, "
                "desarrollo estable bajo la voz y cierre breve sin melodía invasiva."
            ),
            start_seconds=0.0,
            duration_seconds=manifest.output.duration_seconds,
        )

    @staticmethod
    def _scene_music_energy(narrative_role: str) -> float:
        return {"hook": 0.72, "explanation": 0.58, "resolution": 0.68}[narrative_role]

    @staticmethod
    def _scene_music_mood(narrative_role: str) -> str:
        return {
            "hook": "inmediato y expectante",
            "explanation": "estable y concentrado",
            "resolution": "conclusivo y ascendente",
        }[narrative_role]

    @classmethod
    def _keywords(cls, text: str, *, limit: int) -> tuple[str, ...]:
        selected: list[str] = []
        seen: set[str] = set()
        for token in _WORD_PATTERN.findall(text):
            normalized = cls._fold(token).strip("'-")
            if len(normalized) < 3 or normalized in _STOP_WORDS or normalized in seen:
                continue
            seen.add(normalized)
            selected.append(token.strip("'-").casefold())
            if len(selected) == limit:
                break
        return tuple(selected)

    @staticmethod
    def _narrative_role(index: int, scene_count: int) -> str:
        if index == 0:
            return "hook"
        if index == scene_count - 1:
            return "resolution"
        return "explanation"

    @classmethod
    def _source_manifest_hash(cls, manifest: ProductionManifest) -> str:
        existing = manifest.metadata.get("creative_source_manifest_sha256")
        if isinstance(existing, str) and re.fullmatch(r"[0-9a-f]{64}", existing):
            return existing
        payload = serialize_manifest(manifest).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    @staticmethod
    def _fold(value: str) -> str:
        normalized = unicodedata.normalize("NFKD", value.casefold())
        return "".join(char for char in normalized if not unicodedata.combining(char))


__all__ = [
    "CreativeDirectionPlanner",
    "CreativeDirectionPlanningError",
    "CreativeManifestPersistenceResult",
]
