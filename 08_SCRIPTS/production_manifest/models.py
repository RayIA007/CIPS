"""Provider-neutral domain models for the CIPS production manifest.

The models in this module describe *what* must be produced. They deliberately
do not select providers, resolve assets, render media, persist artifacts, or
contain renderer-specific template/payload fields.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import Enum
import hashlib
import re
from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    StrictBool,
    field_validator,
    model_validator,
)


PRODUCTION_MANIFEST_SCHEMA_NAME = "cips.production_manifest"
PRODUCTION_MANIFEST_SCHEMA_VERSION = "1.0"
PRODUCTION_MANIFEST_FILENAME = "production_manifest.json"

_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_LOCALE_PATTERN = re.compile(r"^[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*$")
_HEX_COLOR_PATTERN = re.compile(r"^#[0-9A-Fa-f]{6}$")
_TIMING_TOLERANCE = 1e-6

StrictPositiveSeconds = Annotated[
    float,
    Field(strict=True, gt=0.0, allow_inf_nan=False),
]
StrictNonNegativeSeconds = Annotated[
    float,
    Field(strict=True, ge=0.0, allow_inf_nan=False),
]
StrictUnitInterval = Annotated[
    float,
    Field(strict=True, ge=0.0, le=1.0, allow_inf_nan=False),
]
StrictPositiveInt = Annotated[int, Field(strict=True, gt=0)]


class ManifestModel(BaseModel):
    """Strict structural base shared by every manifest domain model."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
        validate_default=True,
    )


class ManifestVersion(str, Enum):
    """Supported versions of the universal manifest contract."""

    V1_0 = PRODUCTION_MANIFEST_SCHEMA_VERSION


class TargetPlatform(str, Enum):
    YOUTUBE_SHORTS = "youtube_shorts"
    TIKTOK = "tiktok"
    INSTAGRAM_REELS = "instagram_reels"
    FACEBOOK_REELS = "facebook_reels"
    GENERIC = "generic"


class AssetType(str, Enum):
    AI_VIDEO = "ai_video"
    AI_IMAGE = "ai_image"
    STOCK_VIDEO = "stock_video"
    STOCK_IMAGE = "stock_image"
    MOTION_GRAPHIC = "motion_graphic"
    TEXT_GRAPHIC = "text_graphic"
    EXISTING_ASSET = "existing_asset"
    NONE = "none"


class QualityHint(str, Enum):
    DRAFT = "draft"
    STANDARD = "standard"
    HIGH = "high"


class CostHint(str, Enum):
    FREE = "free"
    LOW = "low"
    BALANCED = "balanced"
    PREMIUM = "premium"


class CameraMovement(str, Enum):
    STATIC = "static"
    PAN = "pan"
    TILT = "tilt"
    DOLLY = "dolly"
    ZOOM = "zoom"
    ORBIT = "orbit"
    TRACKING = "tracking"
    HANDHELD = "handheld"
    CUSTOM = "custom"


class MotionSpeed(str, Enum):
    SLOW = "slow"
    MEDIUM = "medium"
    FAST = "fast"


class TextPlacement(str, Enum):
    TOP = "top"
    UPPER_THIRD = "upper_third"
    CENTER = "center"
    LOWER_THIRD = "lower_third"
    BOTTOM = "bottom"
    CUSTOM = "custom"


class TextStyleRole(str, Enum):
    HOOK = "hook"
    TITLE = "title"
    BODY = "body"
    LABEL = "label"
    EMPHASIS = "emphasis"
    CTA = "cta"
    CREDIT = "credit"


class CaptionMode(str, Enum):
    VERBATIM = "verbatim"
    CONDENSED = "condensed"
    KEYWORDS = "keywords"
    CUSTOM = "custom"


class TransitionKind(str, Enum):
    CUT = "cut"
    FADE = "fade"
    DISSOLVE = "dissolve"
    SLIDE = "slide"
    WIPE = "wipe"
    ZOOM = "zoom"
    CUSTOM = "custom"


class SourceType(str, Enum):
    RESEARCH = "research"
    VERIFICATION = "verification"
    SCRIPT = "script"
    STORYBOARD = "storyboard"
    NARRATION = "narration"
    SEO = "seo"
    EXTERNAL = "external"


class QualityCategory(str, Enum):
    TECHNICAL = "technical"
    VISUAL = "visual"
    AUDIO = "audio"
    CAPTIONS = "captions"
    EDITORIAL = "editorial"
    ACCESSIBILITY = "accessibility"
    SAFETY = "safety"


class RequirementLevel(str, Enum):
    MUST = "must"
    SHOULD = "should"


def deterministic_manifest_id(
    project_id: str,
    production_id: str,
    revision: int,
    schema_version: ManifestVersion | str = ManifestVersion.V1_0,
) -> str:
    """Build a stable manifest identity from immutable logical identity data."""

    if isinstance(revision, bool) or not isinstance(revision, int) or revision < 1:
        raise ValueError("revision debe ser un entero positivo.")
    version = schema_version.value if isinstance(schema_version, ManifestVersion) else str(schema_version)
    basis = "\x1f".join(
        (
            _normalize_identity_part(project_id, "project_id"),
            _normalize_identity_part(production_id, "production_id"),
            str(revision),
            _normalize_identity_part(version, "schema_version"),
        )
    )
    return f"pm-{hashlib.sha256(basis.encode('utf-8')).hexdigest()[:24]}"


def deterministic_scene_id(
    sequence: int,
    narration_text: str | None = None,
    visual_intent: str | None = None,
) -> str:
    """Build a stable scene identity without relying on a renderer or provider."""

    if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 1:
        raise ValueError("sequence debe ser un entero positivo.")
    basis_text = narration_text or visual_intent
    if basis_text is None or not _collapse_whitespace(basis_text):
        raise ValueError(
            "Se requiere narration_text o visual_intent para derivar scene_id."
        )
    basis = f"{sequence}\x1f{_collapse_whitespace(basis_text).casefold()}"
    digest = hashlib.sha256(basis.encode("utf-8")).hexdigest()[:16]
    return f"scene-{sequence:03d}-{digest}"


class ProjectIdentity(ManifestModel):
    """Logical identity of one production revision."""

    project_id: str = Field(..., min_length=1, max_length=128)
    production_id: str = Field(..., min_length=1, max_length=128)
    title: str = Field(..., min_length=1)
    revision: StrictPositiveInt = 1
    campaign_id: str | None = Field(default=None, min_length=1, max_length=128)

    @field_validator("project_id", "production_id", "campaign_id")
    @classmethod
    def _validate_identifiers(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_identifier(value, "project identity")


class SafeAreaSpec(ManifestModel):
    """Normalized safe-area margins expressed as fractions of the canvas."""

    top: StrictUnitInterval = 0.05
    right: StrictUnitInterval = 0.05
    bottom: StrictUnitInterval = 0.12
    left: StrictUnitInterval = 0.05

    @model_validator(mode="after")
    def _validate_visible_area(self) -> "SafeAreaSpec":
        if self.left + self.right >= 1.0 or self.top + self.bottom >= 1.0:
            raise ValueError("safe_area debe conservar un área visible positiva.")
        return self


class OutputSpec(ManifestModel):
    """Provider-neutral technical target for the rendered output."""

    platform: TargetPlatform
    width_px: Annotated[int, Field(strict=True, gt=0, le=16384)]
    height_px: Annotated[int, Field(strict=True, gt=0, le=16384)]
    aspect_ratio: str = Field(..., pattern=r"^[1-9][0-9]*:[1-9][0-9]*$")
    fps: Annotated[float, Field(strict=True, ge=1.0, le=240.0, allow_inf_nan=False)]
    duration_seconds: StrictPositiveSeconds
    safe_area: SafeAreaSpec = Field(default_factory=SafeAreaSpec)

    @model_validator(mode="after")
    def _validate_aspect_ratio(self) -> "OutputSpec":
        numerator_text, denominator_text = self.aspect_ratio.split(":", 1)
        declared = int(numerator_text) / int(denominator_text)
        actual = self.width_px / self.height_px
        relative_error = abs(actual - declared) / declared
        if relative_error > 0.01:
            raise ValueError(
                "aspect_ratio no coincide con width_px/height_px dentro de 1%."
            )
        return self


class NarrationSpec(ManifestModel):
    """Narration intent independent of any voice provider or voice identifier."""

    full_text: str = Field(..., min_length=1)
    hook: str = Field(..., min_length=1)
    call_to_action: str | None = Field(default=None, min_length=1)
    voice_characteristics: tuple[str, ...] = Field(default_factory=tuple)
    pace_words_per_minute: Annotated[int, Field(strict=True, ge=60, le=260)] = 150
    estimated_duration_seconds: StrictPositiveSeconds
    delivery_notes: str | None = Field(default=None, min_length=1)

    @field_validator("voice_characteristics")
    @classmethod
    def _validate_voice_characteristics(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return _normalize_unique_texts(values, "voice_characteristics")


class AssetRequest(ManifestModel):
    """Creative asset need; it does not name a provider, model, or template."""

    asset_type: AssetType
    creative_brief: str | None = Field(default=None, min_length=1)
    image_prompt: str | None = Field(default=None, min_length=1)
    video_prompt: str | None = Field(default=None, min_length=1)
    stock_query: str | None = Field(default=None, min_length=1)
    existing_asset_id: str | None = Field(default=None, min_length=1, max_length=128)
    alternatives: tuple[AssetType, ...] = Field(default_factory=tuple)
    quality_hint: QualityHint = QualityHint.STANDARD
    cost_hint: CostHint = CostHint.BALANCED

    @field_validator("existing_asset_id")
    @classmethod
    def _validate_existing_asset_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_identifier(value, "existing_asset_id")

    @model_validator(mode="after")
    def _validate_asset_inputs(self) -> "AssetRequest":
        if len(set(self.alternatives)) != len(self.alternatives):
            raise ValueError("asset_request.alternatives contiene valores duplicados.")
        if self.asset_type in self.alternatives:
            raise ValueError("asset_type no puede repetirse en alternatives.")

        requested_types = {self.asset_type, *self.alternatives}
        if self.asset_type is AssetType.NONE:
            if self.alternatives or any(
                value is not None
                for value in (
                    self.creative_brief,
                    self.image_prompt,
                    self.video_prompt,
                    self.stock_query,
                    self.existing_asset_id,
                )
            ):
                raise ValueError("asset_type='none' no acepta prompts, referencias ni alternatives.")
            return self

        requirements: tuple[tuple[set[AssetType], str | None, str], ...] = (
            ({AssetType.AI_IMAGE}, self.image_prompt, "image_prompt"),
            ({AssetType.AI_VIDEO}, self.video_prompt, "video_prompt"),
            (
                {AssetType.STOCK_IMAGE, AssetType.STOCK_VIDEO},
                self.stock_query,
                "stock_query",
            ),
            ({AssetType.EXISTING_ASSET}, self.existing_asset_id, "existing_asset_id"),
            (
                {AssetType.MOTION_GRAPHIC, AssetType.TEXT_GRAPHIC},
                self.creative_brief,
                "creative_brief",
            ),
        )
        missing = [name for types, value, name in requirements if requested_types & types and value is None]
        if missing:
            raise ValueError(
                "Faltan datos para los asset_type solicitados: " + ", ".join(missing) + "."
            )
        return self


class VisualDirection(ManifestModel):
    """Creative visual intent without renderer implementation details."""

    intent: str = Field(..., min_length=1)
    composition: str = Field(..., min_length=1)
    subjects: tuple[str, ...] = Field(default_factory=tuple)
    environment: str | None = Field(default=None, min_length=1)
    lighting: str | None = Field(default=None, min_length=1)
    color_palette: tuple[str, ...] = Field(default_factory=tuple)
    negative_constraints: tuple[str, ...] = Field(default_factory=tuple)
    continuity_notes: str | None = Field(default=None, min_length=1)

    @field_validator("subjects", "negative_constraints")
    @classmethod
    def _validate_unique_texts(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return _normalize_unique_texts(values, "visual_direction")

    @field_validator("color_palette")
    @classmethod
    def _validate_palette(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        normalized = _normalize_unique_texts(values, "color_palette")
        for value in normalized:
            if not _HEX_COLOR_PATTERN.fullmatch(value):
                raise ValueError("color_palette requiere colores hexadecimales #RRGGBB.")
        return tuple(value.upper() for value in normalized)


class MotionSpec(ManifestModel):
    """Camera and subject movement intent."""

    camera_movement: CameraMovement = CameraMovement.STATIC
    speed: MotionSpeed = MotionSpeed.MEDIUM
    intensity: StrictUnitInterval = 0.0
    direction: str | None = Field(default=None, min_length=1)
    subject_movement: str | None = Field(default=None, min_length=1)
    notes: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def _validate_static_motion(self) -> "MotionSpec":
        if self.camera_movement is CameraMovement.STATIC and self.intensity != 0.0:
            raise ValueError("camera_movement='static' requiere intensity=0.")
        if self.camera_movement is CameraMovement.CUSTOM and self.notes is None:
            raise ValueError("camera_movement='custom' requiere notes.")
        return self


class OnScreenTextSpec(ManifestModel):
    """One timed text element, positioned relative to its scene."""

    text_id: str = Field(..., min_length=1, max_length=128)
    text: str = Field(..., min_length=1)
    start_offset_seconds: StrictNonNegativeSeconds
    duration_seconds: StrictPositiveSeconds
    placement: TextPlacement
    style_role: TextStyleRole
    respect_safe_area: StrictBool = True
    accessibility_label: str | None = Field(default=None, min_length=1)

    @field_validator("text_id")
    @classmethod
    def _validate_text_id(cls, value: str) -> str:
        return _validate_identifier(value, "text_id")


class CaptionSpec(ManifestModel):
    """Caption intent tied to scene narration or explicit custom text."""

    mode: CaptionMode = CaptionMode.VERBATIM
    custom_text: str | None = Field(default=None, min_length=1)
    emphasis_words: tuple[str, ...] = Field(default_factory=tuple)
    max_characters_per_line: Annotated[int, Field(strict=True, ge=8, le=80)] = 32
    max_lines: Annotated[int, Field(strict=True, ge=1, le=4)] = 2
    placement: TextPlacement = TextPlacement.LOWER_THIRD
    respect_safe_area: StrictBool = True

    @field_validator("emphasis_words")
    @classmethod
    def _validate_emphasis_words(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return _normalize_unique_texts(values, "emphasis_words")

    @model_validator(mode="after")
    def _validate_custom_caption(self) -> "CaptionSpec":
        if self.mode is CaptionMode.CUSTOM and self.custom_text is None:
            raise ValueError("caption.mode='custom' requiere custom_text.")
        if self.mode is not CaptionMode.CUSTOM and self.custom_text is not None:
            raise ValueError("custom_text solo es válido con caption.mode='custom'.")
        return self


class TransitionSpec(ManifestModel):
    """Universal transition intent at one scene boundary."""

    kind: TransitionKind = TransitionKind.CUT
    duration_seconds: StrictNonNegativeSeconds = 0.0
    direction: str | None = Field(default=None, min_length=1)
    notes: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def _validate_transition(self) -> "TransitionSpec":
        if self.kind is TransitionKind.CUT and self.duration_seconds != 0.0:
            raise ValueError("transition.kind='cut' requiere duration_seconds=0.")
        if self.kind is not TransitionKind.CUT and self.duration_seconds <= 0.0:
            raise ValueError("Una transición distinta de 'cut' requiere duración positiva.")
        if self.kind is TransitionKind.CUSTOM and self.notes is None:
            raise ValueError("transition.kind='custom' requiere notes.")
        return self


class SceneSpec(ManifestModel):
    """One ordered, timed shot in the universal production timeline."""

    scene_id: str = Field(..., min_length=1, max_length=128)
    sequence: StrictPositiveInt
    start_seconds: StrictNonNegativeSeconds
    duration_seconds: StrictPositiveSeconds
    narration_text: str | None = Field(default=None, min_length=1)
    asset_request: AssetRequest
    visual_direction: VisualDirection
    motion: MotionSpec = Field(default_factory=MotionSpec)
    on_screen_text: tuple[OnScreenTextSpec, ...] = Field(default_factory=tuple)
    captions: CaptionSpec | None = None
    transition_in: TransitionSpec = Field(default_factory=TransitionSpec)
    transition_out: TransitionSpec = Field(default_factory=TransitionSpec)
    source_reference_ids: tuple[str, ...] = Field(default_factory=tuple)
    metadata: dict[str, JsonValue] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _derive_scene_id(cls, value: Any) -> Any:
        if not isinstance(value, Mapping) or "scene_id" in value:
            return value
        data = dict(value)
        visual = data.get("visual_direction")
        if isinstance(visual, VisualDirection):
            visual_intent = visual.intent
        elif isinstance(visual, Mapping):
            visual_intent = visual.get("intent")
        else:
            visual_intent = None
        data["scene_id"] = deterministic_scene_id(
            data.get("sequence"),
            data.get("narration_text"),
            visual_intent,
        )
        return data

    @field_validator("scene_id")
    @classmethod
    def _validate_scene_id(cls, value: str) -> str:
        return _validate_identifier(value, "scene_id")

    @field_validator("source_reference_ids")
    @classmethod
    def _validate_source_ids(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        normalized = tuple(_validate_identifier(value, "source_reference_id") for value in values)
        if len(set(normalized)) != len(normalized):
            raise ValueError("source_reference_ids contiene valores duplicados.")
        return normalized

    @model_validator(mode="after")
    def _validate_scene_timing(self) -> "SceneSpec":
        text_ids = [item.text_id for item in self.on_screen_text]
        duplicates = _duplicates(text_ids)
        if duplicates:
            raise ValueError(
                "SceneSpec contiene text_id duplicados: " + ", ".join(duplicates) + "."
            )
        for item in self.on_screen_text:
            if item.start_offset_seconds + item.duration_seconds > self.duration_seconds + _TIMING_TOLERANCE:
                raise ValueError(
                    f"El texto '{item.text_id}' excede la duración de la escena."
                )
        if self.transition_in.duration_seconds + self.transition_out.duration_seconds > self.duration_seconds + _TIMING_TOLERANCE:
            raise ValueError("Las transiciones exceden la duración de la escena.")
        if self.captions is not None and self.captions.mode is not CaptionMode.CUSTOM and self.narration_text is None:
            raise ValueError("Los captions no personalizados requieren narration_text.")
        return self

    @property
    def end_seconds(self) -> float:
        """Computed scene end; excluded from the serialized contract."""

        return self.start_seconds + self.duration_seconds


class MusicSpec(ManifestModel):
    """Background music intent with neutral energy and mixing targets."""

    mood: str = Field(..., min_length=1)
    energy: StrictUnitInterval
    ducking_db: Annotated[float, Field(strict=True, ge=-60.0, le=0.0, allow_inf_nan=False)] = -9.0
    instrumental_preferred: StrictBool = True
    creative_brief: str | None = Field(default=None, min_length=1)
    existing_asset_id: str | None = Field(default=None, min_length=1, max_length=128)
    start_seconds: StrictNonNegativeSeconds = 0.0
    duration_seconds: StrictPositiveSeconds | None = None

    @field_validator("existing_asset_id")
    @classmethod
    def _validate_existing_asset_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_identifier(value, "existing_asset_id")


class SoundEffectSpec(ManifestModel):
    """A sound-effect cue positioned relative to a referenced scene."""

    cue_id: str = Field(..., min_length=1, max_length=128)
    scene_id: str = Field(..., min_length=1, max_length=128)
    description: str = Field(..., min_length=1)
    start_offset_seconds: StrictNonNegativeSeconds
    duration_seconds: StrictPositiveSeconds | None = None
    intensity: StrictUnitInterval = 0.5
    existing_asset_id: str | None = Field(default=None, min_length=1, max_length=128)

    @field_validator("cue_id", "scene_id", "existing_asset_id")
    @classmethod
    def _validate_ids(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_identifier(value, "sound effect identifier")


class AudioDesignSpec(ManifestModel):
    """Global voice/music/SFX mix intent for the complete timeline."""

    target_loudness_lufs: Annotated[
        float,
        Field(strict=True, ge=-36.0, le=-5.0, allow_inf_nan=False),
    ] = -14.0
    true_peak_dbfs: Annotated[
        float,
        Field(strict=True, ge=-12.0, le=0.0, allow_inf_nan=False),
    ] = -1.0
    voice_gain_db: Annotated[
        float,
        Field(strict=True, ge=-24.0, le=24.0, allow_inf_nan=False),
    ] = 0.0
    music: MusicSpec | None = None
    sound_effects: tuple[SoundEffectSpec, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def _validate_cue_ids(self) -> "AudioDesignSpec":
        duplicates = _duplicates(item.cue_id for item in self.sound_effects)
        if duplicates:
            raise ValueError(
                "AudioDesignSpec contiene cue_id duplicados: " + ", ".join(duplicates) + "."
            )
        return self


class PublicationSpec(ManifestModel):
    """Cross-platform publication metadata, without API-specific fields."""

    title: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)
    hashtags: tuple[str, ...] = Field(default_factory=tuple)
    keywords: tuple[str, ...] = Field(default_factory=tuple)
    call_to_action: str | None = Field(default=None, min_length=1)

    @field_validator("hashtags")
    @classmethod
    def _normalize_hashtags(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        normalized = tuple(value.strip().lstrip("#") for value in values)
        if any(not value or any(char.isspace() for char in value) for value in normalized):
            raise ValueError("hashtags requiere términos no vacíos y sin espacios.")
        return _ensure_casefold_unique(normalized, "hashtags")

    @field_validator("keywords")
    @classmethod
    def _normalize_keywords(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return _normalize_unique_texts(values, "keywords")


class QualityRequirement(ManifestModel):
    """Machine- or human-verifiable QA requirement."""

    requirement_id: str = Field(..., min_length=1, max_length=128)
    category: QualityCategory
    level: RequirementLevel = RequirementLevel.MUST
    description: str = Field(..., min_length=1)
    metric: str | None = Field(default=None, min_length=1)
    expected: JsonValue | None = None

    @field_validator("requirement_id")
    @classmethod
    def _validate_requirement_id(cls, value: str) -> str:
        return _validate_identifier(value, "requirement_id")


class SourceReference(ManifestModel):
    """Traceable editorial or external source reference."""

    source_id: str = Field(..., min_length=1, max_length=128)
    source_type: SourceType
    title: str = Field(..., min_length=1)
    artifact_id: str | None = Field(default=None, min_length=1, max_length=128)
    uri: str | None = Field(default=None, min_length=1)
    locator: str | None = Field(default=None, min_length=1)
    content_hash: str | None = None

    @field_validator("source_id", "artifact_id")
    @classmethod
    def _validate_ids(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_identifier(value, "source identifier")

    @field_validator("content_hash")
    @classmethod
    def _validate_content_hash(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.lower()
        if len(normalized) != 64 or any(char not in "0123456789abcdef" for char in normalized):
            raise ValueError("content_hash debe ser un SHA-256 hexadecimal de 64 caracteres.")
        return normalized

    @model_validator(mode="after")
    def _validate_reference_target(self) -> "SourceReference":
        if self.artifact_id is None and self.uri is None:
            raise ValueError("SourceReference requiere artifact_id o uri.")
        return self


class ProductionManifest(ManifestModel):
    """Versioned, renderer-independent source of truth for one production."""

    schema_name: Literal["cips.production_manifest"] = PRODUCTION_MANIFEST_SCHEMA_NAME
    schema_version: ManifestVersion = ManifestVersion.V1_0
    manifest_id: str = Field(..., min_length=1, max_length=128)
    project: ProjectIdentity
    locale: str = Field(..., min_length=2, max_length=64)
    style_profile: str = Field(..., min_length=1, max_length=128)
    output: OutputSpec
    narration: NarrationSpec
    scenes: tuple[SceneSpec, ...] = Field(..., min_length=1)
    audio_design: AudioDesignSpec
    publication: PublicationSpec
    quality_requirements: tuple[QualityRequirement, ...] = Field(..., min_length=1)
    source_references: tuple[SourceReference, ...] = Field(default_factory=tuple)
    metadata: dict[str, JsonValue] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _derive_manifest_id(cls, value: Any) -> Any:
        if not isinstance(value, Mapping) or "manifest_id" in value:
            return value
        data = dict(value)
        project = data.get("project")
        if isinstance(project, ProjectIdentity):
            project_id = project.project_id
            production_id = project.production_id
            revision = project.revision
        elif isinstance(project, Mapping):
            project_id = project.get("project_id")
            production_id = project.get("production_id")
            revision = project.get("revision", 1)
        else:
            return value
        data["manifest_id"] = deterministic_manifest_id(
            project_id,
            production_id,
            revision,
            data.get("schema_version", ManifestVersion.V1_0),
        )
        return data

    @field_validator("manifest_id")
    @classmethod
    def _validate_manifest_id(cls, value: str) -> str:
        return _validate_identifier(value, "manifest_id")

    @field_validator("locale")
    @classmethod
    def _validate_locale(cls, value: str) -> str:
        if not _LOCALE_PATTERN.fullmatch(value):
            raise ValueError("locale debe usar un identificador BCP-47 básico, por ejemplo es-MX.")
        parts = value.split("-")
        normalized = [parts[0].lower()]
        normalized.extend(part.upper() if len(part) in {2, 3} else part for part in parts[1:])
        return "-".join(normalized)

    @field_validator("style_profile")
    @classmethod
    def _validate_style_profile(cls, value: str) -> str:
        return _validate_identifier(value, "style_profile")

    @model_validator(mode="after")
    def _validate_manifest_consistency(self) -> "ProductionManifest":
        expected_manifest_id = deterministic_manifest_id(
            self.project.project_id,
            self.project.production_id,
            self.project.revision,
            self.schema_version,
        )
        if self.manifest_id != expected_manifest_id:
            raise ValueError(
                f"manifest_id no coincide con la identidad determinista esperada: {expected_manifest_id}."
            )

        scene_ids = [scene.scene_id for scene in self.scenes]
        duplicates = _duplicates(scene_ids)
        if duplicates:
            raise ValueError(
                "ProductionManifest contiene scene_id duplicados: " + ", ".join(duplicates) + "."
            )
        expected_sequence = tuple(range(1, len(self.scenes) + 1))
        actual_sequence = tuple(scene.sequence for scene in self.scenes)
        if actual_sequence != expected_sequence:
            raise ValueError(
                "scenes debe estar ordenado con sequence contiguo iniciando en 1."
            )
        if abs(self.scenes[0].start_seconds) > _TIMING_TOLERANCE:
            raise ValueError("La primera escena debe iniciar en 0 segundos.")
        for previous, current in zip(self.scenes, self.scenes[1:]):
            if current.start_seconds + _TIMING_TOLERANCE < previous.start_seconds:
                raise ValueError("scenes debe estar ordenado por start_seconds.")
            if current.start_seconds < previous.end_seconds - _TIMING_TOLERANCE:
                raise ValueError(
                    f"Las escenas '{previous.scene_id}' y '{current.scene_id}' se solapan."
                )
        timeline_end = max(scene.end_seconds for scene in self.scenes)
        if abs(timeline_end - self.output.duration_seconds) > _TIMING_TOLERANCE:
            raise ValueError(
                "output.duration_seconds debe coincidir con el final de la timeline."
            )
        if self.narration.estimated_duration_seconds > self.output.duration_seconds + _TIMING_TOLERANCE:
            raise ValueError("La narración estimada excede la duración de salida.")

        _validate_narration_mapping(self.narration.full_text, self.scenes)
        self._validate_sources()
        self._validate_audio(scene_ids)

        requirement_duplicates = _duplicates(
            requirement.requirement_id for requirement in self.quality_requirements
        )
        if requirement_duplicates:
            raise ValueError(
                "quality_requirements contiene requirement_id duplicados: "
                + ", ".join(requirement_duplicates)
                + "."
            )
        return self

    def _validate_sources(self) -> None:
        source_ids = [source.source_id for source in self.source_references]
        duplicates = _duplicates(source_ids)
        if duplicates:
            raise ValueError(
                "source_references contiene source_id duplicados: " + ", ".join(duplicates) + "."
            )
        known_sources = set(source_ids)
        for scene in self.scenes:
            missing = sorted(set(scene.source_reference_ids) - known_sources)
            if missing:
                raise ValueError(
                    f"La escena '{scene.scene_id}' referencia fuentes inexistentes: "
                    + ", ".join(missing)
                    + "."
                )

    def _validate_audio(self, scene_ids: list[str]) -> None:
        scene_by_id = {scene.scene_id: scene for scene in self.scenes}
        for cue in self.audio_design.sound_effects:
            scene = scene_by_id.get(cue.scene_id)
            if scene is None:
                raise ValueError(
                    f"El cue '{cue.cue_id}' referencia una escena inexistente: '{cue.scene_id}'."
                )
            cue_end = cue.start_offset_seconds + (cue.duration_seconds or 0.0)
            if cue_end > scene.duration_seconds + _TIMING_TOLERANCE:
                raise ValueError(f"El cue '{cue.cue_id}' excede la duración de su escena.")
        music = self.audio_design.music
        if music is not None:
            if music.start_seconds >= self.output.duration_seconds - _TIMING_TOLERANCE:
                raise ValueError("La música debe iniciar dentro de la duración de salida.")
            if music.duration_seconds is not None:
                if music.start_seconds + music.duration_seconds > self.output.duration_seconds + _TIMING_TOLERANCE:
                    raise ValueError("La música excede la duración de salida.")


def _validate_narration_mapping(full_text: str, scenes: tuple[SceneSpec, ...]) -> None:
    normalized_full = _collapse_whitespace(full_text).casefold()
    cursor = 0
    for scene in scenes:
        if scene.narration_text is None:
            continue
        fragment = _collapse_whitespace(scene.narration_text).casefold()
        position = normalized_full.find(fragment, cursor)
        if position < 0:
            raise ValueError(
                f"narration_text de '{scene.scene_id}' no aparece en orden dentro de narration.full_text."
            )
        cursor = position + len(fragment)


def _normalize_identity_part(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} debe ser texto.")
    normalized = _collapse_whitespace(value).casefold()
    if not normalized:
        raise ValueError(f"{field_name} es obligatorio.")
    return normalized


def _validate_identifier(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not _ID_PATTERN.fullmatch(normalized):
        raise ValueError(
            f"{field_name} debe iniciar con un carácter alfanumérico y usar solo letras, "
            "números, punto, guion o guion bajo."
        )
    return normalized


def _collapse_whitespace(value: str) -> str:
    return " ".join(value.split())


def _normalize_unique_texts(values: tuple[str, ...], field_name: str) -> tuple[str, ...]:
    normalized = tuple(value.strip() for value in values)
    if any(not value for value in normalized):
        raise ValueError(f"{field_name} no acepta texto vacío.")
    return _ensure_casefold_unique(normalized, field_name)


def _ensure_casefold_unique(values: tuple[str, ...], field_name: str) -> tuple[str, ...]:
    identities = [value.casefold() for value in values]
    if len(set(identities)) != len(identities):
        raise ValueError(f"{field_name} contiene valores duplicados.")
    return values


def _duplicates(values: Any) -> tuple[str, ...]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        else:
            seen.add(value)
    return tuple(sorted(duplicates))


__all__ = [
    "PRODUCTION_MANIFEST_FILENAME",
    "PRODUCTION_MANIFEST_SCHEMA_NAME",
    "PRODUCTION_MANIFEST_SCHEMA_VERSION",
    "AssetRequest",
    "AssetType",
    "AudioDesignSpec",
    "CameraMovement",
    "CaptionMode",
    "CaptionSpec",
    "CostHint",
    "ManifestVersion",
    "MotionSpec",
    "MotionSpeed",
    "MusicSpec",
    "NarrationSpec",
    "OnScreenTextSpec",
    "OutputSpec",
    "ProjectIdentity",
    "ProductionManifest",
    "PublicationSpec",
    "QualityCategory",
    "QualityHint",
    "QualityRequirement",
    "RequirementLevel",
    "SafeAreaSpec",
    "SceneSpec",
    "SoundEffectSpec",
    "SourceReference",
    "SourceType",
    "TargetPlatform",
    "TextPlacement",
    "TextStyleRole",
    "TransitionKind",
    "TransitionSpec",
    "VisualDirection",
    "deterministic_manifest_id",
    "deterministic_scene_id",
]
