"""Offline JSON2Video compiler for the CIPS render boundary.

The adapter translates a provider-neutral :class:`ProductionManifest` and a
complete PM8 asset bundle into JSON2Video's Movie JSON.  Compilation is fully
offline: it reads no credentials, performs no network request, and never
starts a render.
"""

from __future__ import annotations

import hashlib
import json
import math
import textwrap
from collections.abc import Mapping
from typing import Any
from urllib.parse import urlsplit

from asset_resolution import AssetResolutionBundle, MediaFamily, ResolutionStatus
from production_manifest import (
    AssetType,
    CameraMovement,
    CaptionMode,
    OnScreenTextSpec,
    ProductionManifest,
    SceneSpec,
    TextPlacement,
    TextStyleRole,
    TransitionKind,
    TransitionSpec,
    serialize_manifest,
)
from render_adapter import (
    RenderAdapterContractError,
    RenderCapabilityError,
    RenderCompilationError,
    RenderPlan,
    RenderTargetAdapter,
    RenderTargetCapabilities,
)


JSON2VIDEO_PAYLOAD_FILENAME = "json2video_payload.json"
JSON2VIDEO_FREE_MAX_DURATION_SECONDS = 60.0
JSON2VIDEO_FREE_MAX_WIDTH_PX = 1920
JSON2VIDEO_FREE_MAX_HEIGHT_PX = 1920

_SUPPORTED_TRANSITIONS = (
    TransitionKind.CUT,
    TransitionKind.FADE,
    TransitionKind.DISSOLVE,
    TransitionKind.SLIDE,
    TransitionKind.WIPE,
    TransitionKind.ZOOM,
)
_IMAGE_ASSET_TYPES = {
    AssetType.AI_IMAGE,
    AssetType.STOCK_IMAGE,
    AssetType.MOTION_GRAPHIC,
    AssetType.TEXT_GRAPHIC,
}
_VIDEO_ASSET_TYPES = {AssetType.AI_VIDEO, AssetType.STOCK_VIDEO}
_ALLOWED_ELEMENT_TYPES = {"audio", "image", "subtitles", "text", "video"}
_TIMING_TOLERANCE = 1e-6


def json2video_capabilities() -> RenderTargetCapabilities:
    """Declare the evaluated JSON2Video free-tier compilation boundary."""

    return RenderTargetCapabilities(
        supported_asset_types=tuple(
            asset_type for asset_type in AssetType if asset_type is not AssetType.NONE
        ),
        supported_transition_kinds=_SUPPORTED_TRANSITIONS,
        supports_narration=True,
        supports_motion=True,
        supports_on_screen_text=True,
        supports_captions=True,
        supports_music=True,
        supports_sound_effects=True,
        max_width_px=JSON2VIDEO_FREE_MAX_WIDTH_PX,
        max_height_px=JSON2VIDEO_FREE_MAX_HEIGHT_PX,
        max_fps=60.0,
        max_duration_seconds=JSON2VIDEO_FREE_MAX_DURATION_SECONDS,
    )


class JSON2VideoAdapter(RenderTargetAdapter):
    """Compile a CIPS manifest to a directly submittable Movie JSON body."""

    adapter_name = "JSON2VideoAdapter"
    adapter_version = "1.2"
    target_id = "json2video.movie"

    def __init__(
        self,
        *,
        resolved_assets: AssetResolutionBundle,
        capabilities: RenderTargetCapabilities | None = None,
        music_volume_ceiling: float = 0.2,
        sound_effect_gain: float = 1.0,
    ) -> None:
        if not isinstance(resolved_assets, AssetResolutionBundle):
            raise TypeError("resolved_assets debe ser AssetResolutionBundle.")
        self._resolved_assets = resolved_assets
        self._music_volume_ceiling = _bounded_mix_value(
            music_volume_ceiling,
            label="music_volume_ceiling",
            maximum=1.0,
        )
        self._sound_effect_gain = _bounded_mix_value(
            sound_effect_gain,
            label="sound_effect_gain",
            maximum=4.0,
        )
        super().__init__(capabilities=capabilities or json2video_capabilities())

    @property
    def resolved_assets(self) -> AssetResolutionBundle:
        return self._resolved_assets

    def validate_capabilities(self, manifest: ProductionManifest) -> None:
        super().validate_capabilities(manifest)
        unsupported: set[str] = set()
        for scene in manifest.scenes:
            if scene.asset_request.asset_type is AssetType.NONE:
                unsupported.add("asset_type:none")
            if scene.motion.camera_movement is CameraMovement.CUSTOM:
                unsupported.add("camera_movement:custom")
        if unsupported:
            raise RenderCapabilityError(self.target_id, tuple(unsupported))

    def compile_payload(self, manifest: ProductionManifest) -> Mapping[str, Any]:
        self._validate_resolution_bundle(manifest)
        scenes = [self._compile_scene(manifest, scene) for scene in manifest.scenes]
        global_elements: list[dict[str, Any]] = []
        music = self._compile_music(manifest)
        if music is not None:
            global_elements.append(music)
        subtitles = self._compile_subtitles(manifest)
        if subtitles is not None:
            global_elements.append(subtitles)

        payload: dict[str, Any] = {
            "resolution": "custom",
            "width": manifest.output.width_px,
            "height": manifest.output.height_px,
            "fps": int(round(manifest.output.fps)),
            "quality": "high",
            "cache": True,
            "comment": "CIPS PM9 internal production acceptance; no publication",
            "client-data": {
                "manifest_id": manifest.manifest_id,
                "project_id": manifest.project.project_id,
                "production_id": manifest.project.production_id,
                "publication_performed": False,
                "expected_duration_seconds": _json_number(
                    manifest.output.duration_seconds
                ),
            },
            "scenes": scenes,
        }
        if global_elements:
            payload["elements"] = global_elements
        validate_json2video_payload(
            payload,
            expected_duration_seconds=manifest.output.duration_seconds,
        )
        return payload

    def validate_plan(
        self,
        plan: RenderPlan,
        *,
        manifest: ProductionManifest,
    ) -> None:
        super().validate_plan(plan, manifest=manifest)
        try:
            validate_json2video_payload(
                plan.target_payload,
                expected_duration_seconds=manifest.output.duration_seconds,
            )
        except RenderCompilationError as error:
            raise RenderAdapterContractError(
                f"Movie JSON inválido después de compilar: {error}"
            ) from error

    def _compile_scene(
        self,
        manifest: ProductionManifest,
        scene: SceneSpec,
    ) -> dict[str, Any]:
        elements = [self._compile_visual(scene)]
        elements.extend(self._compile_on_screen_text(manifest, scene))
        narration = self._compile_narration(manifest, scene)
        if narration is not None:
            elements.append(narration)
        elements.extend(self._compile_scene_sound_effects(manifest, scene))

        rendered: dict[str, Any] = {
            "id": scene.scene_id,
            "comment": f"CIPS scene {scene.sequence}",
            "duration": _json_number(scene.duration_seconds),
            "background-color": _background_color(scene),
            "elements": elements,
        }
        return rendered

    def _compile_visual(self, scene: SceneSpec) -> dict[str, Any]:
        asset = self._persisted_asset("scene_visual", scene.scene_id)
        media_family = asset.media_family
        asset_type = scene.asset_request.asset_type
        if media_family is MediaFamily.IMAGE:
            element_type = "image"
        elif media_family is MediaFamily.VIDEO:
            element_type = "video"
        else:
            raise RenderCompilationError(
                f"scene_visual:{scene.scene_id} debe ser image o video, no "
                f"'{media_family.value if media_family else 'none'}'."
            )
        if asset_type in _IMAGE_ASSET_TYPES and element_type != "image":
            raise RenderCompilationError(
                f"scene_visual:{scene.scene_id} no coincide con {asset_type.value}."
            )
        if asset_type in _VIDEO_ASSET_TYPES and element_type != "video":
            raise RenderCompilationError(
                f"scene_visual:{scene.scene_id} no coincide con {asset_type.value}."
            )

        element: dict[str, Any] = {
            "id": f"visual-{scene.sequence:03d}",
            "type": element_type,
            "src": asset.delivery_uri,
            "duration": -2,
            "resize": _visual_resize(asset.metadata),
            "position": "center-center",
        }
        if element_type == "video":
            element["muted"] = True
        keyframes = _compile_motion(scene)
        if keyframes:
            element["keyframes"] = keyframes
        fade_in = _element_fade(scene.transition_in)
        fade_out = _element_fade(scene.transition_out)
        if fade_in:
            element["fade-in"] = fade_in
        if fade_out:
            element["fade-out"] = fade_out
        return element

    def _compile_on_screen_text(
        self,
        manifest: ProductionManifest,
        scene: SceneSpec,
    ) -> list[dict[str, Any]]:
        return [
            {
                "id": item.text_id,
                "type": "text",
                "text": item.text,
                "start": _json_number(item.start_offset_seconds),
                "duration": _json_number(item.duration_seconds),
                "position": "center-center",
                "width": "90%",
                "height": "90%",
                "settings": _text_settings(manifest, item),
            }
            for item in scene.on_screen_text
        ]

    def _compile_narration(
        self,
        manifest: ProductionManifest,
        scene: SceneSpec,
    ) -> dict[str, Any] | None:
        if scene.narration_text is None:
            return None
        asset = self._persisted_asset("scene_narration", scene.scene_id)
        return {
            "id": f"narration-{scene.sequence:03d}",
            "type": "audio",
            "src": asset.delivery_uri,
            "start": 0,
            "duration": -2,
            "volume": _db_to_multiplier(manifest.audio_design.voice_gain_db),
        }

    def _compile_scene_sound_effects(
        self,
        manifest: ProductionManifest,
        scene: SceneSpec,
    ) -> list[dict[str, Any]]:
        elements: list[dict[str, Any]] = []
        for effect in manifest.audio_design.sound_effects:
            if effect.scene_id != scene.scene_id:
                continue
            asset = self._persisted_asset("sound_effect", effect.cue_id)
            element: dict[str, Any] = {
                "id": effect.cue_id,
                "type": "audio",
                "src": asset.delivery_uri,
                "start": _json_number(effect.start_offset_seconds),
                "volume": _json_number(
                    max(
                        0.0,
                        min(effect.intensity * self._sound_effect_gain, 1.0),
                    )
                ),
            }
            if effect.duration_seconds is not None:
                element["duration"] = _json_number(effect.duration_seconds)
            elements.append(element)
        return elements

    def _compile_music(self, manifest: ProductionManifest) -> dict[str, Any] | None:
        music = manifest.audio_design.music
        if music is None:
            return None
        asset = self._persisted_asset("music", "music")
        duration = music.duration_seconds
        if duration is None or math.isclose(
            duration,
            manifest.output.duration_seconds - music.start_seconds,
            abs_tol=_TIMING_TOLERANCE,
        ):
            rendered_duration: int | float = -2
        else:
            rendered_duration = _json_number(duration)
        return {
            "id": "background-music",
            "type": "audio",
            "src": asset.delivery_uri,
            "start": _json_number(music.start_seconds),
            "duration": rendered_duration,
            "loop": -1,
            "volume": _json_number(
                min(
                    self._music_volume_ceiling,
                    _db_to_multiplier(music.ducking_db),
                )
            ),
        }

    def _compile_subtitles(
        self,
        manifest: ProductionManifest,
    ) -> dict[str, Any] | None:
        if not any(scene.captions is not None for scene in manifest.scenes):
            return None
        captions = _render_srt(manifest)
        if not captions:
            return None
        safe_bottom = int(
            round(manifest.output.height_px * (1.0 - manifest.output.safe_area.bottom))
        )
        return {
            "type": "subtitles",
            "captions": captions,
            "language": "es-419",
            "comment": "Deterministic inline SRT from the approved CIPS narration",
            "settings": {
                "style": "classic",
                "font-family": "Montserrat",
                "font-size": 88,
                "font-weight": "700",
                "word-color": "#FFFFFF",
                "line-color": "#FFFFFF",
                "outline-color": "#000000",
                "outline-width": 5,
                "shadow-color": "#000000",
                "shadow-offset": 2,
                "max-words-per-line": 6,
                "position": "custom",
                "x": manifest.output.width_px // 2,
                "y": safe_bottom - 120,
            },
        }

    def _persisted_asset(self, role: str, identity: str):
        try:
            if role == "scene_visual":
                asset = self._resolved_assets.scene_visual(identity)
            elif role == "scene_narration":
                asset = self._resolved_assets.scene_narration(identity)
            elif role == "music":
                asset = self._resolved_assets.music()
            elif role == "sound_effect":
                asset = self._resolved_assets.sound_effect(identity)
            else:
                raise KeyError(role)
        except KeyError as error:
            raise RenderCompilationError(
                f"PM8 no resolvió '{role}:{identity}' para JSON2Video."
            ) from error
        if asset.status is not ResolutionStatus.PERSISTED:
            raise RenderCompilationError(
                f"'{role}:{identity}' no contiene un artifact F3 persistido."
            )
        if asset.delivery_uri is None or not _is_public_https(asset.delivery_uri):
            raise RenderCompilationError(
                f"'{role}:{identity}' no tiene delivery_uri HTTPS público."
            )
        return asset

    def _validate_resolution_bundle(self, manifest: ProductionManifest) -> None:
        manifest_sha256 = hashlib.sha256(
            serialize_manifest(manifest).encode("utf-8")
        ).hexdigest()
        bundle = self._resolved_assets
        if (
            bundle.manifest_id != manifest.manifest_id
            or bundle.manifest_sha256 != manifest_sha256
            or bundle.project_id != manifest.project.project_id
            or bundle.production_id != manifest.project.production_id
        ):
            raise RenderCompilationError(
                "AssetResolutionBundle no corresponde al ProductionManifest compilado."
            )


def validate_json2video_payload(
    payload: Mapping[str, Any],
    *,
    expected_duration_seconds: float | None = None,
) -> dict[str, Any]:
    """Validate the strict Movie JSON subset emitted by CIPS."""

    if not isinstance(payload, Mapping):
        raise TypeError("payload debe ser un Mapping.")
    normalized = dict(payload)
    if normalized.get("resolution") != "custom":
        raise RenderCompilationError("resolution debe ser 'custom'.")
    for field in ("width", "height", "fps"):
        value = normalized.get(field)
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise RenderCompilationError(f"{field} debe ser un entero positivo.")
    if normalized.get("quality") != "high":
        raise RenderCompilationError("quality debe ser 'high'.")
    if normalized.get("cache") is not True:
        raise RenderCompilationError("cache debe estar habilitado.")
    client_data = normalized.get("client-data")
    if not isinstance(client_data, Mapping):
        raise RenderCompilationError("client-data es obligatorio.")
    if client_data.get("publication_performed") is not False:
        raise RenderCompilationError(
            "client-data debe registrar publication_performed=false."
        )

    scenes = normalized.get("scenes")
    if not isinstance(scenes, list) or not scenes:
        raise RenderCompilationError("scenes debe ser una lista no vacía.")
    scene_ids: set[str] = set()
    total_duration = 0.0
    for scene_index, scene in enumerate(scenes):
        if not isinstance(scene, Mapping):
            raise RenderCompilationError(f"scenes[{scene_index}] debe ser un objeto.")
        scene_id = scene.get("id")
        if not isinstance(scene_id, str) or not scene_id:
            raise RenderCompilationError(f"scenes[{scene_index}].id es obligatorio.")
        if scene_id in scene_ids:
            raise RenderCompilationError(f"id de escena duplicado: {scene_id}.")
        scene_ids.add(scene_id)
        duration = _require_positive_number(
            scene.get("duration"), f"scenes[{scene_index}].duration"
        )
        total_duration += duration
        elements = scene.get("elements")
        if not isinstance(elements, list) or not elements:
            raise RenderCompilationError(
                f"scenes[{scene_index}].elements debe ser una lista no vacía."
            )
        _validate_elements(elements, container=f"scenes[{scene_index}]")
        if not any(
            isinstance(element, Mapping)
            and element.get("type") in {"image", "video"}
            for element in elements
        ):
            raise RenderCompilationError(
                f"scenes[{scene_index}] no contiene un visual físico."
            )
    if expected_duration_seconds is not None and not math.isclose(
        total_duration,
        float(expected_duration_seconds),
        abs_tol=_TIMING_TOLERANCE,
    ):
        raise RenderCompilationError(
            "La suma de escenas no coincide con la duración de salida."
        )

    global_elements = normalized.get("elements", [])
    if not isinstance(global_elements, list):
        raise RenderCompilationError("elements global debe ser una lista.")
    _validate_elements(global_elements, container="movie")
    subtitles = [
        element
        for element in global_elements
        if isinstance(element, Mapping) and element.get("type") == "subtitles"
    ]
    if len(subtitles) > 1:
        raise RenderCompilationError("JSON2Video acepta un solo elemento subtitles.")
    if subtitles:
        captions = subtitles[0].get("captions")
        if not isinstance(captions, str) or " --> " not in captions:
            raise RenderCompilationError("subtitles.captions debe contener SRT inline.")
    try:
        json.dumps(normalized, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as error:
        raise RenderCompilationError(
            f"El payload no es compatible con JSON: {error}."
        ) from error
    return normalized


def serialize_json2video_payload(
    payload: Mapping[str, Any],
    *,
    indent: int = 2,
) -> str:
    if isinstance(indent, bool) or not isinstance(indent, int) or indent < 0:
        raise ValueError("indent debe ser un entero no negativo.")
    normalized = validate_json2video_payload(payload)
    return json.dumps(
        normalized,
        ensure_ascii=False,
        sort_keys=True,
        indent=indent,
        allow_nan=False,
    ) + "\n"


def estimate_json2video_credits(duration_seconds: float) -> int:
    """Estimate free-plan credits for a 1080p render (one per second)."""

    if isinstance(duration_seconds, bool) or not isinstance(
        duration_seconds, (int, float)
    ):
        raise TypeError("duration_seconds debe ser numérico.")
    if not math.isfinite(float(duration_seconds)) or duration_seconds <= 0:
        raise ValueError("duration_seconds debe ser positivo y finito.")
    return int(math.ceil(float(duration_seconds)))


def _validate_elements(elements: list[Any], *, container: str) -> None:
    ids: set[str] = set()
    for index, element in enumerate(elements):
        if not isinstance(element, Mapping):
            raise RenderCompilationError(
                f"{container}.elements[{index}] debe ser un objeto."
            )
        element_type = element.get("type")
        if element_type not in _ALLOWED_ELEMENT_TYPES:
            raise RenderCompilationError(
                f"Tipo no soportado en {container}.elements[{index}]: {element_type}."
            )
        element_id = element.get("id")
        if element_id is not None:
            if not isinstance(element_id, str) or not element_id:
                raise RenderCompilationError("El id de elemento no puede estar vacío.")
            if element_id in ids:
                raise RenderCompilationError(f"id de elemento duplicado: {element_id}.")
            ids.add(element_id)
        if element_type in {"audio", "image", "video"}:
            src = element.get("src")
            if not isinstance(src, str) or not _is_public_https(src):
                raise RenderCompilationError(
                    f"src HTTPS público obligatorio en {container}.elements[{index}]."
                )
        if element_type == "text":
            if not isinstance(element.get("text"), str) or not element["text"].strip():
                raise RenderCompilationError("Los elementos text requieren texto.")
            if not isinstance(element.get("settings"), Mapping):
                raise RenderCompilationError("Los elementos text requieren settings.")


def _element_fade(transition: TransitionSpec) -> int | float:
    # JSON2Video currently accepts scene.transition but its renderer fails when
    # the field is present in a multi-scene movie.  Preserve every non-cut
    # boundary as an element-level fade instead; these use the same approved
    # duration and render reliably without changing the scene timeline.
    if transition.kind is TransitionKind.CUT:
        return 0
    return _json_number(transition.duration_seconds)


def _visual_resize(metadata: Mapping[str, Any]) -> str:
    requested = str(metadata.get("recommended_resize") or "").strip().casefold()
    if requested == "contain":
        return "contain"
    return "cover"


def _bounded_mix_value(value: float, *, label: str, maximum: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{label} debe ser numérico.")
    normalized = float(value)
    if not math.isfinite(normalized) or normalized < 0.0 or normalized > maximum:
        raise ValueError(f"{label} debe estar entre 0.0 y {maximum:.1f}.")
    return normalized


def _compile_motion(scene: SceneSpec) -> list[dict[str, Any]]:
    motion = scene.motion
    if motion.camera_movement is CameraMovement.STATIC or motion.intensity <= 0:
        return []
    intensity = min(float(motion.intensity), 1.0)
    duration = _json_number(scene.duration_seconds)
    if motion.camera_movement is CameraMovement.ZOOM:
        return [
            {"time": 0, "zoom": 0},
            {"time": duration, "zoom": _json_number(0.7 * intensity)},
        ]
    offsets = {
        CameraMovement.PAN: ("x", f"{50.0 + 3.0 * intensity:.2f}%"),
        CameraMovement.TRACKING: ("x", f"{50.0 + 2.0 * intensity:.2f}%"),
        CameraMovement.TILT: ("y", f"{50.0 + 3.0 * intensity:.2f}%"),
        CameraMovement.DOLLY: ("zoom", _json_number(0.5 * intensity)),
        CameraMovement.ORBIT: ("x", f"{50.0 + 2.0 * intensity:.2f}%"),
        CameraMovement.HANDHELD: ("zoom", _json_number(0.15 * intensity)),
    }
    property_name, final_value = offsets.get(
        motion.camera_movement, ("zoom", _json_number(0.2 * intensity))
    )
    initial_value: str | int = "50%" if property_name in {"x", "y"} else 0
    return [
        {"time": 0, property_name: initial_value},
        {"time": duration, property_name: final_value, "easing": "ease-in-out-sine"},
    ]


def _text_settings(
    manifest: ProductionManifest,
    item: OnScreenTextSpec,
) -> dict[str, str]:
    vertical = {
        TextPlacement.TOP: "top",
        TextPlacement.UPPER_THIRD: "top",
        TextPlacement.CENTER: "center",
        TextPlacement.LOWER_THIRD: "bottom",
        TextPlacement.BOTTOM: "bottom",
        TextPlacement.CUSTOM: "center",
    }[item.placement]
    font_size = {
        TextStyleRole.HOOK: "82px",
        TextStyleRole.TITLE: "76px",
        TextStyleRole.EMPHASIS: "72px",
        TextStyleRole.CTA: "68px",
        TextStyleRole.BODY: "58px",
        TextStyleRole.LABEL: "52px",
        TextStyleRole.CREDIT: "38px",
    }[item.style_role]
    padding_top = int(round(manifest.output.safe_area.top * 100))
    padding_bottom = int(round(manifest.output.safe_area.bottom * 100))
    return {
        "font-family": "Montserrat",
        "font-size": font_size,
        "font-weight": "800",
        "line-height": "1.05",
        "color": "#FFFFFF",
        "text-shadow": "0 3px 8px rgba(0,0,0,0.95)",
        "text-align": "center",
        "horizontal-position": "center",
        "vertical-position": vertical,
        "padding-top": f"{padding_top}%",
        "padding-right": "5%",
        "padding-bottom": f"{padding_bottom}%",
        "padding-left": "5%",
    }


def _render_srt(manifest: ProductionManifest) -> str:
    entries: list[tuple[float, float, str]] = []
    for scene in manifest.scenes:
        caption = scene.captions
        if caption is None:
            continue
        if caption.mode is CaptionMode.CUSTOM:
            text = caption.custom_text or ""
        else:
            text = scene.narration_text or ""
        words = text.split()
        if not words:
            continue
        chunks = _caption_chunks(
            words,
            max_characters=caption.max_characters_per_line,
            max_words=6,
        )
        word_total = sum(len(chunk.split()) for chunk in chunks)
        cursor = scene.start_seconds
        for index, chunk in enumerate(chunks):
            chunk_words = len(chunk.split())
            if index == len(chunks) - 1:
                end = scene.end_seconds
            else:
                end = cursor + scene.duration_seconds * chunk_words / word_total
            entries.append((cursor, end, chunk))
            cursor = end
    return "\n\n".join(
        f"{index}\n{_srt_time(start)} --> {_srt_time(end)}\n{text}"
        for index, (start, end, text) in enumerate(entries, start=1)
    )


def _caption_chunks(
    words: list[str],
    *,
    max_characters: int,
    max_words: int,
) -> list[str]:
    wrapped = textwrap.wrap(
        " ".join(words),
        width=max_characters,
        break_long_words=False,
        break_on_hyphens=False,
    )
    chunks: list[str] = []
    for line in wrapped:
        line_words = line.split()
        chunks.extend(
            " ".join(line_words[index : index + max_words])
            for index in range(0, len(line_words), max_words)
        )
    return chunks


def _srt_time(seconds: float) -> str:
    milliseconds = int(round(float(seconds) * 1000))
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def _background_color(scene: SceneSpec) -> str:
    palette = scene.visual_direction.color_palette
    return palette[0] if palette else "#0B1020"


def _db_to_multiplier(db: float) -> int | float:
    return _json_number(max(0.0, min(10.0, math.pow(10.0, float(db) / 20.0))))


def _json_number(value: float) -> int | float:
    rendered = round(float(value), 6)
    return int(rendered) if rendered.is_integer() else rendered


def _require_positive_number(value: Any, label: str) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
        or float(value) <= 0
    ):
        raise RenderCompilationError(f"{label} debe ser un número positivo.")
    return float(value)


def _is_public_https(value: str) -> bool:
    parsed = urlsplit(str(value))
    return (
        parsed.scheme.lower() == "https"
        and bool(parsed.netloc)
        and parsed.username is None
        and parsed.password is None
    )


__all__ = [
    "JSON2VIDEO_FREE_MAX_DURATION_SECONDS",
    "JSON2VIDEO_FREE_MAX_HEIGHT_PX",
    "JSON2VIDEO_FREE_MAX_WIDTH_PX",
    "JSON2VIDEO_PAYLOAD_FILENAME",
    "JSON2VideoAdapter",
    "estimate_json2video_credits",
    "json2video_capabilities",
    "serialize_json2video_payload",
    "validate_json2video_payload",
]
