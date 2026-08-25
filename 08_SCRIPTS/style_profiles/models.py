"""Provider-neutral style-profile contracts for CIPS production planning.

Style is intentionally separated from output geometry.  A profile describes
editorial and audiovisual behavior, while normalized layout policies adapt it
to vertical, horizontal, or near-square canvases without naming a platform or
renderer.
"""

from __future__ import annotations

import re
from enum import Enum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

STYLE_PROFILE_SCHEMA_NAME = "cips.style_profile"
STYLE_PROFILE_SCHEMA_VERSION = "1.0"

_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_HEX_COLOR_PATTERN = re.compile(r"^#[0-9A-Fa-f]{6}$")

StrictUnit = Annotated[
    float,
    Field(strict=True, ge=0.0, le=1.0, allow_inf_nan=False),
]
StrictPositiveSeconds = Annotated[
    float,
    Field(strict=True, gt=0.0, allow_inf_nan=False),
]


class StyleModel(BaseModel):
    """Strict immutable base for universal style contracts."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
        validate_default=True,
    )


class OutputLayoutFamily(str, Enum):
    """Geometry family inferred from dimensions, never from platform name."""

    VERTICAL = "vertical"
    HORIZONTAL = "horizontal"
    SQUARE = "square"


class VisualDensity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class CaptionTiming(str, Enum):
    STATIC = "static"
    SYNCHRONIZED_WORDS = "synchronized_words"


class MotionCharacter(str, Enum):
    CONTINUOUS = "continuous"
    CINEMATIC = "cinematic"
    MINIMAL = "minimal"


class TransitionCharacter(str, Enum):
    DIRECT = "direct"
    SOFT = "soft"
    DISSOLVE = "dissolve"


class VisualFit(str, Enum):
    COVER = "cover"
    CONTAIN = "contain"


class LayoutPolicy(StyleModel):
    """Normalized positions and sizes for one geometry family."""

    family: OutputLayoutFamily
    focal_x: StrictUnit = 0.5
    focal_y: StrictUnit = 0.5
    caption_x: StrictUnit = 0.5
    caption_y: StrictUnit
    caption_width: Annotated[
        float,
        Field(strict=True, gt=0.0, le=1.0, allow_inf_nan=False),
    ]
    caption_height: Annotated[
        float,
        Field(strict=True, gt=0.0, le=1.0, allow_inf_nan=False),
    ]
    caption_font_scale: Annotated[
        float,
        Field(strict=True, gt=0.0, le=2.0, allow_inf_nan=False),
    ] = 1.0


class ReferenceEvidence(StyleModel):
    """Compact physical observations that justify one reusable profile."""

    source_id: str = Field(..., min_length=1, max_length=128)
    frame_width_px: Annotated[int, Field(strict=True, gt=0)]
    frame_height_px: Annotated[int, Field(strict=True, gt=0)]
    duration_seconds: StrictPositiveSeconds
    fps: StrictPositiveSeconds
    shot_count: Annotated[int, Field(strict=True, gt=0)]
    integrated_loudness_lufs: Annotated[
        float,
        Field(strict=True, ge=-70.0, le=0.0, allow_inf_nan=False),
    ]
    true_peak_dbfs: Annotated[
        float,
        Field(strict=True, ge=-30.0, le=3.0, allow_inf_nan=False),
    ]
    observations: tuple[str, ...] = Field(..., min_length=1)

    @field_validator("source_id")
    @classmethod
    def _validate_source_id(cls, value: str) -> str:
        if not _ID_PATTERN.fullmatch(value):
            raise ValueError("source_id debe ser un identificador estable.")
        return value

    @field_validator("observations")
    @classmethod
    def _validate_observations(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return _unique_non_empty(values, "observations")


class RhythmPolicy(StyleModel):
    """Target shot cadence; it guides planning without rewriting scene timing."""

    preferred_shot_seconds: StrictPositiveSeconds
    minimum_shot_seconds: StrictPositiveSeconds
    maximum_shot_seconds: StrictPositiveSeconds
    visual_density: VisualDensity

    @model_validator(mode="after")
    def _validate_range(self) -> RhythmPolicy:
        if not (
            self.minimum_shot_seconds
            <= self.preferred_shot_seconds
            <= self.maximum_shot_seconds
        ):
            raise ValueError("preferred_shot_seconds debe estar dentro del rango.")
        return self


class CaptionPolicy(StyleModel):
    """Caption behavior independent from a concrete renderer."""

    visible: bool = True
    timing: CaptionTiming = CaptionTiming.STATIC
    uppercase: bool = False
    font_family: str = Field(..., min_length=1, max_length=128)
    font_weight: Annotated[int, Field(strict=True, ge=100, le=900)]
    font_size_fraction: Annotated[
        float,
        Field(strict=True, gt=0.0, le=0.2, allow_inf_nan=False),
    ]
    line_height: Annotated[
        float,
        Field(strict=True, ge=0.8, le=2.0, allow_inf_nan=False),
    ] = 1.15
    fill_color: str
    emphasis_color: str
    stroke_color: str | None = None
    stroke_width_fraction: Annotated[
        float,
        Field(strict=True, ge=0.0, le=0.05, allow_inf_nan=False),
    ] = 0.0
    background_color: str = "rgba(0,0,0,0)"
    background_x_padding: StrictUnit = 0.18
    background_y_padding: StrictUnit = 0.14
    background_border_radius: StrictUnit = 0.1
    maximum_characters: Annotated[int, Field(strict=True, ge=8, le=80)] = 32

    @field_validator("fill_color", "emphasis_color", "stroke_color")
    @classmethod
    def _validate_hex_colors(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not _HEX_COLOR_PATTERN.fullmatch(value):
            raise ValueError("Los colores de texto requieren formato #RRGGBB.")
        return value.upper()

    @model_validator(mode="after")
    def _validate_stroke(self) -> CaptionPolicy:
        if self.stroke_width_fraction > 0.0 and self.stroke_color is None:
            raise ValueError("stroke_width_fraction requiere stroke_color.")
        return self


class MotionPolicy(StyleModel):
    character: MotionCharacter
    intensity_multiplier: Annotated[
        float,
        Field(strict=True, ge=0.0, le=2.0, allow_inf_nan=False),
    ]
    preferred_easing: str = Field(..., min_length=1, max_length=64)
    techniques: tuple[str, ...] = Field(..., min_length=1)

    @field_validator("techniques")
    @classmethod
    def _validate_techniques(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return _unique_non_empty(values, "techniques")


class TransitionPolicy(StyleModel):
    character: TransitionCharacter
    preferred_duration_seconds: Annotated[
        float,
        Field(strict=True, ge=0.0, le=3.0, allow_inf_nan=False),
    ]


class AudioPolicy(StyleModel):
    target_loudness_lufs: Annotated[
        float,
        Field(strict=True, ge=-36.0, le=-5.0, allow_inf_nan=False),
    ]
    maximum_true_peak_dbfs: Annotated[
        float,
        Field(strict=True, ge=-12.0, le=-0.1, allow_inf_nan=False),
    ]
    voice_first: bool = True
    music_energy: StrictUnit
    ducking_db: Annotated[
        float,
        Field(strict=True, ge=-30.0, le=0.0, allow_inf_nan=False),
    ]
    sound_effect_density: VisualDensity


class NarrativePolicy(StyleModel):
    hook: str = Field(..., min_length=1)
    call_to_action: str = Field(..., min_length=1)
    text_in_generated_visuals: str = Field(..., min_length=1)


class BrollPolicy(StyleModel):
    """Editorial use of supporting visuals; physical resolution belongs to PM8."""

    strategy: str = Field(..., min_length=1)
    density: VisualDensity
    preferred_subjects: tuple[str, ...] = Field(..., min_length=1)
    continuity_rule: str = Field(..., min_length=1)

    @field_validator("preferred_subjects")
    @classmethod
    def _validate_subjects(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return _unique_non_empty(values, "preferred_subjects")


class MotionGraphicsPolicy(StyleModel):
    """Graphic-layer intent without renderer or template implementation fields."""

    density: VisualDensity
    allowed_elements: tuple[str, ...] = Field(..., min_length=1)
    label_strategy: str = Field(..., min_length=1)

    @field_validator("allowed_elements")
    @classmethod
    def _validate_elements(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return _unique_non_empty(values, "allowed_elements")


class CompositionPolicy(StyleModel):
    visual_fit: VisualFit
    canvas_color: str
    visual_density: VisualDensity
    layouts: tuple[LayoutPolicy, ...] = Field(..., min_length=3, max_length=3)

    @field_validator("canvas_color")
    @classmethod
    def _validate_canvas_color(cls, value: str) -> str:
        if not _HEX_COLOR_PATTERN.fullmatch(value):
            raise ValueError("canvas_color requiere formato #RRGGBB.")
        return value.upper()

    @model_validator(mode="after")
    def _validate_layouts(self) -> CompositionPolicy:
        actual = {layout.family for layout in self.layouts}
        expected = set(OutputLayoutFamily)
        if actual != expected or len(actual) != len(self.layouts):
            raise ValueError(
                "layouts debe declarar exactamente vertical, horizontal y square."
            )
        return self

    def layout_for(self, family: OutputLayoutFamily) -> LayoutPolicy:
        for layout in self.layouts:
            if layout.family is family:
                return layout
        raise LookupError(f"No existe layout para {family.value}.")


class StyleProfile(StyleModel):
    """Complete provider-neutral, evidence-backed reusable style profile."""

    schema_name: Literal["cips.style_profile"] = STYLE_PROFILE_SCHEMA_NAME
    schema_version: Literal["1.0"] = STYLE_PROFILE_SCHEMA_VERSION
    profile_id: str = Field(..., min_length=1, max_length=128)
    display_name: str = Field(..., min_length=1, max_length=128)
    description: str = Field(..., min_length=1)
    evidence: tuple[ReferenceEvidence, ...] = Field(..., min_length=1)
    rhythm: RhythmPolicy
    composition: CompositionPolicy
    captions: CaptionPolicy
    motion: MotionPolicy
    motion_graphics: MotionGraphicsPolicy
    b_roll: BrollPolicy
    transitions: TransitionPolicy
    audio: AudioPolicy
    narrative: NarrativePolicy

    @field_validator("profile_id")
    @classmethod
    def _validate_profile_id(cls, value: str) -> str:
        if not _ID_PATTERN.fullmatch(value):
            raise ValueError("profile_id debe ser un identificador estable.")
        return value


def classify_output_layout(width_px: int, height_px: int) -> OutputLayoutFamily:
    """Classify any positive canvas by geometry, not by destination platform."""

    if isinstance(width_px, bool) or not isinstance(width_px, int) or width_px <= 0:
        raise ValueError("width_px debe ser un entero positivo.")
    if isinstance(height_px, bool) or not isinstance(height_px, int) or height_px <= 0:
        raise ValueError("height_px debe ser un entero positivo.")
    ratio = width_px / height_px
    if ratio <= 0.85:
        return OutputLayoutFamily.VERTICAL
    if ratio >= 1.18:
        return OutputLayoutFamily.HORIZONTAL
    return OutputLayoutFamily.SQUARE


def _unique_non_empty(values: tuple[str, ...], field_name: str) -> tuple[str, ...]:
    normalized = tuple(value.strip() for value in values)
    if any(not value for value in normalized):
        raise ValueError(f"{field_name} no acepta texto vacío.")
    if len({value.casefold() for value in normalized}) != len(normalized):
        raise ValueError(f"{field_name} contiene valores duplicados.")
    return normalized


__all__ = [
    "STYLE_PROFILE_SCHEMA_NAME",
    "STYLE_PROFILE_SCHEMA_VERSION",
    "AudioPolicy",
    "BrollPolicy",
    "CaptionPolicy",
    "CaptionTiming",
    "CompositionPolicy",
    "LayoutPolicy",
    "MotionCharacter",
    "MotionGraphicsPolicy",
    "MotionPolicy",
    "NarrativePolicy",
    "OutputLayoutFamily",
    "ReferenceEvidence",
    "RhythmPolicy",
    "StyleProfile",
    "TransitionCharacter",
    "TransitionPolicy",
    "VisualDensity",
    "VisualFit",
    "classify_output_layout",
]
