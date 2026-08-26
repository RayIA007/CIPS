"""Offline Creatomate RenderScript compiler for the PM4 render boundary.

The adapter translates one provider-neutral ``ProductionManifest`` into a
deterministic, inspectable RenderScript payload.  It deliberately performs no
network I/O, uses no credentials, and starts no render.  PM8 may inject a
provider-neutral ``AssetResolutionBundle``; without it, the historical
``assets.invalid`` placeholders remain byte-for-byte compatible.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from typing import Any

from asset_resolution.models import (
    AssetResolutionBundle,
    MediaFamily,
    ResolutionStatus,
)
from production_manifest import (
    AssetType,
    CameraMovement,
    CaptionMode,
    MotionSpec,
    MotionSpeed,
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
from style_profiles import (
    CaptionTiming,
    LayoutPolicy,
    StyleProfile,
    TransitionCharacter,
    VisualDensity,
    classify_output_layout,
    get_style_profile,
)

CREATOMATE_PAYLOAD_FILENAME = "creatomate_payload.json"
CREATOMATE_PLACEHOLDER_ORIGIN = "https://assets.invalid/cips"

_SUPPORTED_TRANSITIONS = (
    TransitionKind.CUT,
    TransitionKind.FADE,
    TransitionKind.DISSOLVE,
    TransitionKind.SLIDE,
    TransitionKind.ZOOM,
)
_IMAGE_ASSET_TYPES = {
    AssetType.AI_IMAGE,
    AssetType.STOCK_IMAGE,
    AssetType.EXISTING_ASSET,
}
_VIDEO_ASSET_TYPES = {
    AssetType.AI_VIDEO,
    AssetType.STOCK_VIDEO,
}
_GRAPHIC_ASSET_TYPES = {
    AssetType.MOTION_GRAPHIC,
    AssetType.TEXT_GRAPHIC,
}
_ALLOWED_ELEMENT_TYPES = {"audio", "image", "shape", "text", "video"}
_RECTANGLE_PATH = "M 0% 0% L 100% 0% L 100% 100% L 0% 100% Z"
_TIMING_TOLERANCE = 1e-6


def creatomate_capabilities() -> RenderTargetCapabilities:
    """Declare the compile-only subset supported by this adapter."""

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
    )


class CreatomateAdapter(RenderTargetAdapter):
    """Compile manifests to multi-format direct RenderScript without executing it."""

    adapter_name = "CreatomateAdapter"
    adapter_version = "1.4"
    target_id = "creatomate.renderscript"

    def __init__(
        self,
        *,
        capabilities: RenderTargetCapabilities | None = None,
        resolved_assets: AssetResolutionBundle | None = None,
    ) -> None:
        if resolved_assets is not None and not isinstance(
            resolved_assets, AssetResolutionBundle
        ):
            raise TypeError("resolved_assets debe ser AssetResolutionBundle o None.")
        self._resolved_assets = resolved_assets
        super().__init__(capabilities=capabilities or creatomate_capabilities())

    @property
    def resolved_assets(self) -> AssetResolutionBundle | None:
        return self._resolved_assets

    def validate_capabilities(self, manifest: ProductionManifest) -> None:
        """Apply PM4 validation without coupling output to one aspect ratio."""

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
        """Build one direct RenderScript payload with deterministic layers."""

        self._validate_resolution_bundle(manifest)
        style = get_style_profile(manifest.style_profile)
        elements: list[dict[str, Any]] = []
        for scene in manifest.scenes:
            elements.append(self._compile_visual(manifest, scene, style=style))
            elements.extend(self._compile_on_screen_text(manifest, scene, style=style))
            caption = self._compile_caption(manifest, scene, style=style)
            if caption is not None:
                elements.append(caption)
            narration = self._compile_narration(manifest, scene)
            if narration is not None:
                elements.append(narration)

        music = self._compile_music(manifest, style=style)
        if music is not None:
            elements.append(music)
        elements.extend(self._compile_sound_effects(manifest, style=style))

        payload = {
            "output_format": "mp4",
            # Creatomate may otherwise choose a reduced preview scale.  PM9
            # requires the physical output dimensions declared below.
            "render_scale": 1.0,
            "width": manifest.output.width_px,
            "height": manifest.output.height_px,
            "frame_rate": _json_number(manifest.output.fps),
            "duration": _json_number(manifest.output.duration_seconds),
            "elements": elements,
        }
        validate_creatomate_payload(payload)
        return payload

    def validate_plan(
        self,
        plan: RenderPlan,
        *,
        manifest: ProductionManifest,
    ) -> None:
        """Preserve PM4 invariants and validate the derived RenderScript."""

        super().validate_plan(plan, manifest=manifest)
        try:
            validate_creatomate_payload(plan.target_payload)
        except RenderCompilationError as error:
            raise RenderAdapterContractError(
                f"RenderScript inválido después de compilar: {error}"
            ) from error

    def _compile_visual(
        self,
        manifest: ProductionManifest,
        scene: SceneSpec,
        *,
        style: StyleProfile | None,
    ) -> dict[str, Any]:
        asset_type = scene.asset_request.asset_type
        base: dict[str, Any] = {
            "name": f"Scene:{scene.scene_id}:visual:{asset_type.value}",
            "track": 1,
            "time": _json_number(scene.start_seconds),
            "duration": _json_number(scene.duration_seconds),
            "x": "50%",
            "y": "50%",
            "width": "100%",
            "height": "100%",
        }
        resolved_visual = (
            self._resolved_assets.scene_visual(scene.scene_id)
            if self._resolved_assets is not None
            else None
        )
        existing_video = (
            asset_type is AssetType.EXISTING_ASSET
            and resolved_visual is not None
            and resolved_visual.media_family is MediaFamily.VIDEO
        )
        if asset_type in _IMAGE_ASSET_TYPES and not existing_video:
            base.update(
                {
                    "type": "image",
                    "source": self._scene_asset_source(
                        manifest,
                        scene,
                        extension="jpg",
                    ),
                    "fit": (style.composition.visual_fit.value if style else "cover"),
                    "clip": True,
                }
            )
        elif asset_type in _VIDEO_ASSET_TYPES or existing_video:
            base.update(
                {
                    "type": "video",
                    "source": self._scene_asset_source(
                        manifest,
                        scene,
                        extension="mp4",
                    ),
                    "fit": (style.composition.visual_fit.value if style else "cover"),
                    "clip": True,
                    "volume": "0%",
                }
            )
        elif asset_type in _GRAPHIC_ASSET_TYPES:
            palette = scene.visual_direction.color_palette
            base.update(
                {
                    "type": "shape",
                    "path": _RECTANGLE_PATH,
                    "fill_color": (
                        style.composition.canvas_color
                        if style
                        else (palette[0] if palette else "#111827")
                    ),
                    "clip": True,
                }
            )
        else:
            raise RenderCompilationError(
                f"asset_type no compilable para '{scene.scene_id}': {asset_type.value}."
            )

        animations = self._compile_animations(scene, style=style)
        if animations:
            base["animations"] = animations
        return base

    def _compile_animations(
        self,
        scene: SceneSpec,
        *,
        style: StyleProfile | None,
    ) -> list[dict[str, Any]]:
        animations: list[dict[str, Any]] = []
        incoming = _transition_animation(
            scene.transition_in,
            phase="in",
            element_duration=scene.duration_seconds,
            style=style,
        )
        if incoming is not None:
            animations.append(incoming)
        motion = _motion_animation(
            scene.motion,
            scene.duration_seconds,
            style=style,
        )
        if motion is not None:
            animations.append(motion)
        outgoing = _transition_animation(
            scene.transition_out,
            phase="out",
            element_duration=scene.duration_seconds,
            style=style,
        )
        if outgoing is not None:
            animations.append(outgoing)
        return animations

    def _compile_on_screen_text(
        self,
        manifest: ProductionManifest,
        scene: SceneSpec,
        *,
        style: StyleProfile | None,
    ) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for text in scene.on_screen_text:
            placement = _text_geometry(text.placement, manifest)
            rendered_style = _text_style(text.style_role, style=style)
            items.append(
                {
                    "name": f"Scene:{scene.scene_id}:text:{text.text_id}",
                    "type": "text",
                    "track": 2,
                    "time": _json_number(
                        scene.start_seconds + text.start_offset_seconds
                    ),
                    "duration": _json_number(text.duration_seconds),
                    "text": text.text,
                    **placement,
                    **rendered_style,
                }
            )
        return items

    def _compile_caption(
        self,
        manifest: ProductionManifest,
        scene: SceneSpec,
        *,
        style: StyleProfile | None,
    ) -> dict[str, Any] | None:
        caption = scene.captions
        if caption is None:
            return None
        text = (
            caption.custom_text
            if caption.mode is CaptionMode.CUSTOM
            else scene.narration_text
        )
        if not text:
            raise RenderCompilationError(
                f"La escena '{scene.scene_id}' requiere texto para captions."
            )
        if style is None:
            return {
                "name": f"Scene:{scene.scene_id}:captions:{caption.mode.value}",
                "type": "text",
                "track": 3,
                "time": _json_number(scene.start_seconds),
                "duration": _json_number(scene.duration_seconds),
                "text": text,
                **_text_geometry(caption.placement, manifest),
                "fill_color": "#FFFFFF",
                "font_family": "Montserrat",
                "font_weight": 700,
                "font_size": "5 vmin",
                "line_height": "115%",
                "text_wrap": True,
                "x_alignment": "50%",
                "y_alignment": "50%",
                "background_color": "rgba(0,0,0,0.62)",
                "background_x_padding": "18%",
                "background_y_padding": "14%",
                "background_border_radius": "10%",
            }

        layout = style.composition.layout_for(
            classify_output_layout(
                manifest.output.width_px,
                manifest.output.height_px,
            )
        )
        caption_policy = style.captions
        if not caption_policy.visible:
            return None
        rendered: dict[str, Any] = {
            "name": f"Scene:{scene.scene_id}:captions:{caption.mode.value}",
            "type": "text",
            "track": 3,
            "time": _json_number(scene.start_seconds),
            "duration": _json_number(scene.duration_seconds),
            **_profile_caption_geometry(layout, manifest),
            "fill_color": caption_policy.fill_color,
            "font_family": caption_policy.font_family,
            "font_weight": caption_policy.font_weight,
            "font_size": _vmin(
                caption_policy.font_size_fraction * layout.caption_font_scale
            ),
            "line_height": _ratio_percent(caption_policy.line_height),
            "text_wrap": True,
            "x_alignment": "50%",
            "y_alignment": "50%",
            "text_transform": "uppercase" if caption_policy.uppercase else "none",
            "background_color": caption_policy.background_color,
            "background_x_padding": _percent(caption_policy.background_x_padding),
            "background_y_padding": _percent(caption_policy.background_y_padding),
            "background_border_radius": _percent(
                caption_policy.background_border_radius
            ),
        }
        if caption_policy.stroke_color is not None:
            rendered["stroke_color"] = caption_policy.stroke_color
            rendered["stroke_width"] = _vmin(caption_policy.stroke_width_fraction)
        if (
            caption_policy.timing is CaptionTiming.SYNCHRONIZED_WORDS
            and caption.mode is not CaptionMode.CUSTOM
            and scene.narration_text is not None
        ):
            rendered.update(
                {
                    "transcript_source": f"Scene:{scene.scene_id}:narration",
                    "transcript_effect": "highlight",
                    "transcript_split": "word",
                    "transcript_placement": "animate",
                    "transcript_color": caption_policy.emphasis_color,
                    "transcript_maximum_length": min(
                        caption.max_characters_per_line,
                        caption_policy.maximum_characters,
                    ),
                }
            )
        else:
            rendered["text"] = text
        return rendered

    def _compile_narration(
        self,
        manifest: ProductionManifest,
        scene: SceneSpec,
    ) -> dict[str, Any] | None:
        if scene.narration_text is None:
            return None
        return {
            "name": f"Scene:{scene.scene_id}:narration",
            "type": "audio",
            "track": 4,
            "time": _json_number(scene.start_seconds),
            "duration": _json_number(scene.duration_seconds),
            "source": self._resolved_source(
                role="scene_narration",
                identity=scene.scene_id,
                placeholder=_placeholder_url(
                    manifest.manifest_id,
                    "narration",
                    f"{scene.scene_id}.wav",
                ),
            ),
            "volume": _db_to_percentage(manifest.audio_design.voice_gain_db),
        }

    def _compile_music(
        self,
        manifest: ProductionManifest,
        *,
        style: StyleProfile | None,
    ) -> dict[str, Any] | None:
        music = manifest.audio_design.music
        if music is None:
            return None
        identity = music.existing_asset_id or "background-music"
        duration = music.duration_seconds or (
            manifest.output.duration_seconds - music.start_seconds
        )
        return {
            "name": "Audio:music",
            "type": "audio",
            "track": 5,
            "time": _json_number(music.start_seconds),
            "duration": _json_number(duration),
            "source": self._resolved_source(
                role="music",
                identity="music",
                placeholder=_placeholder_url(
                    manifest.manifest_id,
                    "music",
                    f"{identity}.mp3",
                ),
            ),
            "loop": True,
            "volume": _db_to_percentage(
                style.audio.ducking_db if style else music.ducking_db
            ),
        }

    def _compile_sound_effects(
        self,
        manifest: ProductionManifest,
        *,
        style: StyleProfile | None,
    ) -> list[dict[str, Any]]:
        scenes = {scene.scene_id: scene for scene in manifest.scenes}
        elements: list[dict[str, Any]] = []
        for effect in manifest.audio_design.sound_effects:
            scene = scenes[effect.scene_id]
            identity = effect.existing_asset_id or effect.cue_id
            elements.append(
                {
                    "name": f"Audio:sfx:{effect.cue_id}",
                    "type": "audio",
                    "track": 6,
                    "time": _json_number(
                        scene.start_seconds + effect.start_offset_seconds
                    ),
                    "duration": _json_number(effect.duration_seconds or 0.5),
                    "source": self._resolved_source(
                        role="sound_effect",
                        identity=effect.cue_id,
                        placeholder=_placeholder_url(
                            manifest.manifest_id,
                            "sfx",
                            f"{identity}.wav",
                        ),
                    ),
                    "volume": _unit_to_percentage(
                        effect.intensity * _sound_effect_multiplier(style)
                    ),
                }
            )
        return elements

    def _scene_asset_source(
        self,
        manifest: ProductionManifest,
        scene: SceneSpec,
        *,
        extension: str,
    ) -> str:
        identity = scene.asset_request.existing_asset_id or scene.scene_id
        return self._resolved_source(
            role="scene_visual",
            identity=scene.scene_id,
            placeholder=_placeholder_url(
                manifest.manifest_id,
                "visual",
                f"{identity}.{extension}",
            ),
        )

    def _resolved_source(
        self,
        *,
        role: str,
        identity: str,
        placeholder: str,
    ) -> str:
        bundle = self._resolved_assets
        if bundle is None:
            return placeholder
        try:
            if role == "scene_visual":
                record = bundle.scene_visual(identity)
            elif role == "scene_narration":
                record = bundle.scene_narration(identity)
            elif role == "music":
                record = bundle.music()
            elif role == "sound_effect":
                record = bundle.sound_effect(identity)
            else:  # Defensive guard for adapter-owned call sites.
                raise KeyError(role)
        except KeyError as error:
            raise RenderCompilationError(
                f"PM8 no resolvió '{role}:{identity}' para Creatomate."
            ) from error
        if record.status is not ResolutionStatus.PERSISTED:
            raise RenderCompilationError(
                f"'{role}:{identity}' no contiene un artifact F3 persistido."
            )
        if record.delivery_uri is None:
            raise RenderCompilationError(
                f"'{role}:{identity}' no tiene delivery_uri HTTPS para Creatomate."
            )
        return record.delivery_uri

    def _validate_resolution_bundle(self, manifest: ProductionManifest) -> None:
        bundle = self._resolved_assets
        if bundle is None:
            return
        manifest_sha256 = hashlib.sha256(
            serialize_manifest(manifest).encode("utf-8")
        ).hexdigest()
        if (
            bundle.manifest_id != manifest.manifest_id
            or bundle.manifest_sha256 != manifest_sha256
            or bundle.project_id != manifest.project.project_id
            or bundle.production_id != manifest.project.production_id
        ):
            raise RenderCompilationError(
                "AssetResolutionBundle no corresponde al ProductionManifest compilado."
            )


def serialize_creatomate_payload(
    payload: Mapping[str, Any],
    *,
    indent: int = 2,
) -> str:
    """Validate and canonically serialize one RenderScript mapping."""

    if isinstance(indent, bool) or not isinstance(indent, int) or indent < 0:
        raise ValueError("indent debe ser un entero no negativo.")
    normalized = validate_creatomate_payload(payload)
    return (
        json.dumps(
            normalized,
            ensure_ascii=False,
            indent=indent,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n"
    )


def deserialize_creatomate_payload(
    payload: str | bytes | bytearray,
) -> dict[str, Any]:
    """Decode and structurally validate one RenderScript document."""

    if not isinstance(payload, (str, bytes, bytearray)):
        raise TypeError("payload debe ser JSON en str, bytes o bytearray.")
    try:
        decoded = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RenderCompilationError(
            f"JSON de Creatomate inválido: {error}."
        ) from error
    return validate_creatomate_payload(decoded)


def validate_creatomate_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Validate the direct-RenderScript subset emitted by the CIPS adapter."""

    if not isinstance(payload, Mapping):
        raise TypeError("payload debe ser un Mapping.")
    normalized = dict(payload)
    if normalized.get("output_format") != "mp4":
        raise RenderCompilationError("output_format debe ser 'mp4'.")
    render_scale = normalized.get("render_scale")
    if (
        isinstance(render_scale, bool)
        or not isinstance(render_scale, (int, float))
        or float(render_scale) != 1.0
    ):
        raise RenderCompilationError(
            "render_scale debe ser 1.0 para conservar la resolución física."
        )
    for field in ("width", "height"):
        value = normalized.get(field)
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise RenderCompilationError(f"{field} debe ser un entero positivo.")
    for field in ("frame_rate", "duration"):
        _require_positive_number(normalized.get(field), field)
    elements = normalized.get("elements")
    if not isinstance(elements, list) or not elements:
        raise RenderCompilationError("elements debe ser una lista no vacía.")

    output_duration = float(normalized["duration"])
    names: set[str] = set()
    for index, element in enumerate(elements):
        if not isinstance(element, Mapping):
            raise RenderCompilationError(f"elements[{index}] debe ser un Mapping.")
        name = element.get("name")
        if not isinstance(name, str) or not name.strip():
            raise RenderCompilationError(f"elements[{index}].name es obligatorio.")
        if name in names:
            raise RenderCompilationError(f"Nombre de elemento duplicado: {name}.")
        names.add(name)
        element_type = element.get("type")
        if element_type not in _ALLOWED_ELEMENT_TYPES:
            raise RenderCompilationError(
                f"Tipo de elemento no soportado en '{name}': {element_type}."
            )
        track = element.get("track")
        if isinstance(track, bool) or not isinstance(track, int) or track < 1:
            raise RenderCompilationError(f"track inválido en '{name}'.")
        start = _require_non_negative_number(element.get("time"), f"{name}.time")
        duration = _require_positive_number(
            element.get("duration"),
            f"{name}.duration",
        )
        if start + duration > output_duration + _TIMING_TOLERANCE:
            raise RenderCompilationError(
                f"El elemento '{name}' excede la duración de salida."
            )
        if element_type in {"audio", "image", "video"}:
            source = element.get("source")
            if not isinstance(source, str) or not source.startswith("https://"):
                raise RenderCompilationError(f"source HTTPS obligatorio en '{name}'.")
        elif element_type == "text":
            text = element.get("text")
            transcript_source = element.get("transcript_source")
            has_text = isinstance(text, str) and bool(text.strip())
            if not has_text and transcript_source is None:
                raise RenderCompilationError(
                    f"text o transcript_source es obligatorio en '{name}'."
                )
            if transcript_source is not None:
                _validate_transcript_source(transcript_source, name)
        elif element_type == "shape":
            path = element.get("path")
            if not isinstance(path, str) or not path.strip():
                raise RenderCompilationError(f"path es obligatorio en '{name}'.")

    element_by_name = {
        str(element["name"]): element
        for element in elements
        if isinstance(element, Mapping)
    }
    for element in elements:
        if not isinstance(element, Mapping) or element.get("type") != "text":
            continue
        transcript_source = element.get("transcript_source")
        if not isinstance(transcript_source, str):
            continue
        source_element = element_by_name.get(transcript_source)
        if source_element is None:
            raise RenderCompilationError(
                f"transcript_source inexistente en '{element['name']}': "
                f"{transcript_source}."
            )
        if source_element.get("type") not in {"audio", "video"}:
            raise RenderCompilationError(
                f"transcript_source debe referir audio o video en '{element['name']}'."
            )

    try:
        json.dumps(normalized, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as error:
        raise RenderCompilationError(
            f"El payload contiene valores no compatibles con JSON: {error}."
        ) from error
    return normalized


def _transition_animation(
    transition: TransitionSpec,
    *,
    phase: str,
    element_duration: float,
    style: StyleProfile | None,
) -> dict[str, Any] | None:
    if transition.kind is TransitionKind.CUT:
        return None
    if transition.kind not in _SUPPORTED_TRANSITIONS:
        raise RenderCompilationError(
            f"Transición Creatomate no soportada: {transition.kind.value}."
        )
    duration = min(
        (
            style.transitions.preferred_duration_seconds
            if style and style.transitions.preferred_duration_seconds > 0.0
            else transition.duration_seconds
        ),
        element_duration,
    )
    rendered_kind = transition.kind
    if transition.kind is TransitionKind.DISSOLVE or (
        style
        and style.transitions.character
        in {
            TransitionCharacter.SOFT,
            TransitionCharacter.DISSOLVE,
        }
    ):
        rendered_kind = TransitionKind.FADE
    animation: dict[str, Any] = {
        "time": _json_number(0.0 if phase == "in" else element_duration - duration),
        "duration": _json_number(duration),
        "easing": style.motion.preferred_easing if style else "cubic-in-out",
        "transition": True,
        "enable": "second-only" if phase == "in" else "first-only",
    }
    if rendered_kind is TransitionKind.FADE:
        animation["type"] = "fade"
    elif rendered_kind is TransitionKind.SLIDE:
        animation.update(
            {
                "type": "slide",
                "fade": False,
                "direction": _direction_degrees(transition.direction),
            }
        )
    elif rendered_kind is TransitionKind.ZOOM:
        animation.update(
            {
                "type": "scale",
                "scope": "element",
                "fade": False,
                "start_scale": "115%" if phase == "in" else "100%",
                "end_scale": "100%" if phase == "in" else "115%",
            }
        )
    return animation


def _motion_animation(
    motion: MotionSpec,
    duration: float,
    *,
    style: StyleProfile | None,
) -> dict[str, Any] | None:
    movement = motion.camera_movement
    if movement is CameraMovement.STATIC:
        return None
    if movement is CameraMovement.CUSTOM:
        raise RenderCompilationError("camera_movement='custom' no está soportado.")
    easing = (
        style.motion.preferred_easing
        if style
        else ("linear" if motion.speed is MotionSpeed.SLOW else "quadratic-in-out")
    )
    intensity = min(
        1.0,
        motion.intensity * (style.motion.intensity_multiplier if style else 1.0),
    )
    if movement in {
        CameraMovement.DOLLY,
        CameraMovement.ORBIT,
        CameraMovement.ZOOM,
    }:
        scale_delta = max(2 if style else 3, round(20 * intensity))
        return {
            "time": 0,
            "duration": _json_number(duration),
            "easing": easing,
            "type": "scale",
            "scope": "element",
            "start_scale": "100%",
            "end_scale": f"{100 + scale_delta}%",
            "fade": False,
        }
    return {
        "time": 0,
        "duration": _json_number(duration),
        "easing": easing,
        "type": "slide",
        "fade": False,
        "direction": _direction_degrees(motion.direction),
    }


def _text_geometry(
    placement: TextPlacement,
    manifest: ProductionManifest,
) -> dict[str, Any]:
    safe = manifest.output.safe_area
    left = _percent(safe.left)
    width = _percent(1.0 - safe.left - safe.right)
    positions = {
        TextPlacement.TOP: (_percent(safe.top), "0%"),
        TextPlacement.UPPER_THIRD: ("32%", "50%"),
        TextPlacement.CENTER: ("50%", "50%"),
        TextPlacement.LOWER_THIRD: ("70%", "50%"),
        TextPlacement.BOTTOM: (_percent(1.0 - safe.bottom), "100%"),
        TextPlacement.CUSTOM: ("50%", "50%"),
    }
    y, y_anchor = positions[placement]
    return {
        "x": left,
        "y": y,
        "width": width,
        "height": "18%",
        "x_anchor": "0%",
        "y_anchor": y_anchor,
    }


def _text_style(
    role: TextStyleRole,
    *,
    style: StyleProfile | None,
) -> dict[str, Any]:
    large_roles = {TextStyleRole.HOOK, TextStyleRole.TITLE, TextStyleRole.CTA}
    if style is not None:
        caption = style.captions
        role_scale = 1.25 if role in large_roles else 1.0
        rendered = {
            "fill_color": caption.fill_color,
            "font_family": caption.font_family,
            "font_weight": max(caption.font_weight, 700)
            if role in large_roles
            else caption.font_weight,
            "font_size": _vmin(caption.font_size_fraction * role_scale),
            "line_height": _ratio_percent(caption.line_height),
            "text_wrap": True,
            "x_alignment": "50%",
            "y_alignment": "50%",
            "text_transform": "uppercase" if caption.uppercase else "none",
            "background_color": caption.background_color,
            "background_x_padding": _percent(caption.background_x_padding),
            "background_y_padding": _percent(caption.background_y_padding),
            "background_border_radius": _percent(caption.background_border_radius),
        }
        if caption.stroke_color is not None:
            rendered["stroke_color"] = caption.stroke_color
            rendered["stroke_width"] = _vmin(caption.stroke_width_fraction)
        return rendered
    return {
        "fill_color": "#FFFFFF",
        "font_family": "Montserrat",
        "font_weight": 800 if role in large_roles else 700,
        "font_size": "7 vmin" if role in large_roles else "5.5 vmin",
        "line_height": "110%",
        "text_wrap": True,
        "x_alignment": "50%",
        "y_alignment": "50%",
        "background_color": "rgba(0,0,0,0.48)",
        "background_x_padding": "20%",
        "background_y_padding": "16%",
        "background_border_radius": "10%",
    }


def _profile_caption_geometry(
    layout: LayoutPolicy,
    manifest: ProductionManifest,
) -> dict[str, Any]:
    """Clamp a profile layout inside the manifest's normalized safe area."""

    safe = manifest.output.safe_area
    available_width = 1.0 - safe.left - safe.right
    available_height = 1.0 - safe.top - safe.bottom
    width = min(layout.caption_width, available_width)
    height = min(layout.caption_height, available_height)
    x = min(
        1.0 - safe.right - width / 2.0,
        max(safe.left + width / 2.0, layout.caption_x),
    )
    y = min(
        1.0 - safe.bottom - height / 2.0,
        max(safe.top + height / 2.0, layout.caption_y),
    )
    return {
        "x": _percent(x),
        "y": _percent(y),
        "width": _percent(width),
        "height": _percent(height),
        "x_anchor": "50%",
        "y_anchor": "50%",
    }


def _validate_transcript_source(source: Any, element_name: str) -> None:
    if isinstance(source, str):
        if not source.strip():
            raise RenderCompilationError(
                f"transcript_source vacío en '{element_name}'."
            )
        return
    if not isinstance(source, list) or not source:
        raise RenderCompilationError(f"transcript_source inválido en '{element_name}'.")
    for index, keyframe in enumerate(source):
        if not isinstance(keyframe, Mapping):
            raise RenderCompilationError(
                f"transcript_source[{index}] inválido en '{element_name}'."
            )
        _require_non_negative_number(
            keyframe.get("time"),
            f"{element_name}.transcript_source[{index}].time",
        )
        _require_positive_number(
            keyframe.get("duration"),
            f"{element_name}.transcript_source[{index}].duration",
        )
        value = keyframe.get("value")
        if not isinstance(value, str) or not value.strip():
            raise RenderCompilationError(
                f"value obligatorio en transcript_source[{index}] de '{element_name}'."
            )


def _sound_effect_multiplier(style: StyleProfile | None) -> float:
    if style is None:
        return 1.0
    return {
        VisualDensity.LOW: 0.55,
        VisualDensity.MEDIUM: 0.8,
        VisualDensity.HIGH: 1.0,
    }[style.audio.sound_effect_density]


def _vmin(fraction: float) -> str:
    return f"{round(fraction * 100.0, 3):g} vmin"


def _ratio_percent(value: float) -> str:
    return f"{round(value * 100.0, 3):g}%"


def _placeholder_url(manifest_id: str, category: str, filename: str) -> str:
    return f"{CREATOMATE_PLACEHOLDER_ORIGIN}/{manifest_id}/{category}/{filename}"


def _direction_degrees(direction: str | None) -> str:
    normalized = (direction or "left").strip().casefold()
    if "right" in normalized or "derecha" in normalized:
        return "0°"
    if "up" in normalized or "arriba" in normalized:
        return "-90°"
    if "down" in normalized or "abajo" in normalized:
        return "90°"
    return "180°"


def _db_to_percentage(db: float) -> str:
    ratio = min(1.0, max(0.0, math.pow(10.0, db / 20.0)))
    return _unit_to_percentage(ratio)


def _unit_to_percentage(value: float) -> str:
    return f"{round(min(1.0, max(0.0, value)) * 100.0, 2):g}%"


def _percent(value: float) -> str:
    return f"{round(value * 100.0, 4):g}%"


def _json_number(value: float) -> int | float:
    number = round(float(value), 6)
    return int(number) if number.is_integer() else number


def _require_non_negative_number(value: Any, field_name: str) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
        or float(value) < 0.0
    ):
        raise RenderCompilationError(f"{field_name} debe ser un número no negativo.")
    return float(value)


def _require_positive_number(value: Any, field_name: str) -> float:
    number = _require_non_negative_number(value, field_name)
    if number <= 0.0:
        raise RenderCompilationError(f"{field_name} debe ser un número positivo.")
    return number


__all__ = [
    "CREATOMATE_PAYLOAD_FILENAME",
    "CREATOMATE_PLACEHOLDER_ORIGIN",
    "CreatomateAdapter",
    "creatomate_capabilities",
    "deserialize_creatomate_payload",
    "serialize_creatomate_payload",
    "validate_creatomate_payload",
]
