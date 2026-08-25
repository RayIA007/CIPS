"""Evidence-backed built-in CIPS style profiles for PM7."""

from __future__ import annotations

from .models import (
    AudioPolicy,
    BrollPolicy,
    CaptionPolicy,
    CaptionTiming,
    CompositionPolicy,
    LayoutPolicy,
    MotionCharacter,
    MotionGraphicsPolicy,
    MotionPolicy,
    NarrativePolicy,
    OutputLayoutFamily,
    ReferenceEvidence,
    RhythmPolicy,
    StyleProfile,
    TransitionCharacter,
    TransitionPolicy,
    VisualDensity,
    VisualFit,
)

IMMERSIVE_PROCESS_EXPLAINER_ID = "immersive-process-explainer-v1"
CINEMATIC_CELLULAR_DOCUMENTARY_ID = "cinematic-cellular-documentary-v1"
MINIMAL_BIOMEDICAL_EXPLAINER_ID = "minimal-biomedical-explainer-v1"


_SCAR_HEALING_EVIDENCE = ReferenceEvidence(
    source_id="gold-scar-healing-short",
    frame_width_px=1440,
    frame_height_px=2560,
    duration_seconds=10.094,
    fps=30.0,
    shot_count=2,
    integrated_loudness_lufs=-16.5,
    true_peak_dbfs=-4.1,
    observations=(
        "Hook visual inmediato, sin introducción separada.",
        "Proceso 3D macro continuo con alta densidad de movimiento interno.",
        "Captions superiores en mayúsculas con énfasis progresivo cian.",
        "CTA visual breve integrado cerca del cierre.",
    ),
)

_IMMUNE_BATTLEGROUND_EVIDENCE = ReferenceEvidence(
    source_id="gold-immune-system-battleground",
    frame_width_px=1920,
    frame_height_px=1080,
    duration_seconds=485.734,
    fps=30.0,
    shot_count=60,
    integrated_loudness_lufs=-18.9,
    true_peak_dbfs=1.0,
    observations=(
        "Documental 3D de ritmo cinematográfico con planos medios de 8.1 segundos.",
        "Paleta cálida naranja contra acentos azul y cian sobre fondos oscuros.",
        "Movimiento lento dentro del plano, profundidad de campo y luz de recorte.",
        "Texto ocasional; no requiere captions permanentes ni CTA invasivo.",
    ),
)

_MITOCHONDRIA_EVIDENCE = ReferenceEvidence(
    source_id="gold-mitochondria-energy",
    frame_width_px=1280,
    frame_height_px=720,
    duration_seconds=102.454,
    fps=25.0,
    shot_count=4,
    integrated_loudness_lufs=-13.2,
    true_peak_dbfs=-1.8,
    observations=(
        "Visualización biomédica minimalista de cuatro secuencias macro extensas.",
        "Paleta blanca, azul hielo y cian con abundante espacio negativo.",
        "Etiquetas técnicas pequeñas y cámara muy lenta con transiciones suaves.",
        "Cierre sin CTA y con silencio final aproximado de 2.4 segundos.",
    ),
)


def _layouts(
    *,
    vertical_y: float,
    horizontal_y: float,
    square_y: float,
    vertical_width: float,
    horizontal_width: float,
    square_width: float,
    vertical_scale: float,
    horizontal_scale: float,
    square_scale: float,
) -> tuple[LayoutPolicy, ...]:
    return (
        LayoutPolicy(
            family=OutputLayoutFamily.VERTICAL,
            focal_x=0.5,
            focal_y=0.5,
            caption_x=0.5,
            caption_y=vertical_y,
            caption_width=vertical_width,
            caption_height=0.18,
            caption_font_scale=vertical_scale,
        ),
        LayoutPolicy(
            family=OutputLayoutFamily.HORIZONTAL,
            focal_x=0.5,
            focal_y=0.5,
            caption_x=0.5,
            caption_y=horizontal_y,
            caption_width=horizontal_width,
            caption_height=0.2,
            caption_font_scale=horizontal_scale,
        ),
        LayoutPolicy(
            family=OutputLayoutFamily.SQUARE,
            focal_x=0.5,
            focal_y=0.5,
            caption_x=0.5,
            caption_y=square_y,
            caption_width=square_width,
            caption_height=0.18,
            caption_font_scale=square_scale,
        ),
    )


IMMERSIVE_PROCESS_EXPLAINER = StyleProfile(
    profile_id=IMMERSIVE_PROCESS_EXPLAINER_ID,
    display_name="Immersive Process Explainer",
    description=(
        "Explicación breve y visceral de un proceso continuo, con macrovisual 3D, "
        "hook inmediato, captions cinéticos y cierre visual compacto."
    ),
    evidence=(_SCAR_HEALING_EVIDENCE,),
    rhythm=RhythmPolicy(
        preferred_shot_seconds=5.0,
        minimum_shot_seconds=0.8,
        maximum_shot_seconds=10.0,
        visual_density=VisualDensity.HIGH,
    ),
    composition=CompositionPolicy(
        visual_fit=VisualFit.COVER,
        canvas_color="#06141B",
        visual_density=VisualDensity.HIGH,
        layouts=_layouts(
            vertical_y=0.18,
            horizontal_y=0.14,
            square_y=0.16,
            vertical_width=0.86,
            horizontal_width=0.7,
            square_width=0.82,
            vertical_scale=1.0,
            horizontal_scale=0.72,
            square_scale=0.86,
        ),
    ),
    captions=CaptionPolicy(
        timing=CaptionTiming.SYNCHRONIZED_WORDS,
        uppercase=True,
        font_family="Montserrat",
        font_weight=800,
        font_size_fraction=0.068,
        line_height=1.05,
        fill_color="#FFFFFF",
        emphasis_color="#22D3EE",
        stroke_color="#050505",
        stroke_width_fraction=0.012,
        background_color="rgba(0,0,0,0)",
        background_x_padding=0.14,
        background_y_padding=0.1,
        background_border_radius=0.06,
        maximum_characters=26,
    ),
    motion=MotionPolicy(
        character=MotionCharacter.CONTINUOUS,
        intensity_multiplier=1.25,
        preferred_easing="linear",
        techniques=("zoom macro", "tracking", "parallax biológico"),
    ),
    motion_graphics=MotionGraphicsPolicy(
        density=VisualDensity.MEDIUM,
        allowed_elements=("caption cinético", "cursor", "confeti", "CTA localizado"),
        label_strategy="Texto grande por frases cortas; énfasis sincronizado por palabra.",
    ),
    b_roll=BrollPolicy(
        strategy="Insertos del mismo proceso, sin abandonar la continuidad anatómica.",
        density=VisualDensity.LOW,
        preferred_subjects=("detalle macro", "resultado exterior", "cambio de escala"),
        continuity_rule="Conservar anatomía, iluminación y dirección del movimiento.",
    ),
    transitions=TransitionPolicy(
        character=TransitionCharacter.DIRECT,
        preferred_duration_seconds=0.12,
    ),
    audio=AudioPolicy(
        target_loudness_lufs=-16.0,
        maximum_true_peak_dbfs=-1.5,
        music_energy=0.22,
        ducking_db=-13.0,
        sound_effect_density=VisualDensity.MEDIUM,
    ),
    narrative=NarrativePolicy(
        hook="Mostrar el proceso desde el primer instante, sin bumper previo.",
        call_to_action="Overlay visual breve, localizado y coherente con el idioma.",
        text_in_generated_visuals=(
            "No generar texto dentro del asset; toda tipografía se compone como capa."
        ),
    ),
)


CINEMATIC_CELLULAR_DOCUMENTARY = StyleProfile(
    profile_id=CINEMATIC_CELLULAR_DOCUMENTARY_ID,
    display_name="Cinematic Cellular Documentary",
    description=(
        "Documental científico de escala celular, metáforas visuales, iluminación "
        "dramática y cadencia de plano contemplativa."
    ),
    evidence=(_IMMUNE_BATTLEGROUND_EVIDENCE,),
    rhythm=RhythmPolicy(
        preferred_shot_seconds=8.1,
        minimum_shot_seconds=2.0,
        maximum_shot_seconds=18.0,
        visual_density=VisualDensity.MEDIUM,
    ),
    composition=CompositionPolicy(
        visual_fit=VisualFit.COVER,
        canvas_color="#07111F",
        visual_density=VisualDensity.MEDIUM,
        layouts=_layouts(
            vertical_y=0.72,
            horizontal_y=0.78,
            square_y=0.74,
            vertical_width=0.84,
            horizontal_width=0.64,
            square_width=0.78,
            vertical_scale=0.82,
            horizontal_scale=0.62,
            square_scale=0.72,
        ),
    ),
    captions=CaptionPolicy(
        timing=CaptionTiming.STATIC,
        uppercase=False,
        font_family="Montserrat",
        font_weight=600,
        font_size_fraction=0.052,
        line_height=1.15,
        fill_color="#F8FAFC",
        emphasis_color="#F59E0B",
        background_color="rgba(3,7,18,0.66)",
        background_x_padding=0.18,
        background_y_padding=0.14,
        background_border_radius=0.08,
        maximum_characters=42,
    ),
    motion=MotionPolicy(
        character=MotionCharacter.CINEMATIC,
        intensity_multiplier=0.72,
        preferred_easing="cubic-in-out",
        techniques=("dolly lento", "órbita", "pan", "profundidad de campo"),
    ),
    motion_graphics=MotionGraphicsPolicy(
        density=VisualDensity.MEDIUM,
        allowed_elements=("diagrama anatómico", "flecha", "escudo", "etiqueta breve"),
        label_strategy="Etiquetas ocasionales, verificadas y editables; nunca glifos simulados.",
    ),
    b_roll=BrollPolicy(
        strategy="Alternar macro celular, anatomía y metáfora visual explicativa.",
        density=VisualDensity.MEDIUM,
        preferred_subjects=("células", "órganos", "barrera", "mecanismo molecular"),
        continuity_rule="Unificar con luz de recorte y contraste naranja contra cian.",
    ),
    transitions=TransitionPolicy(
        character=TransitionCharacter.SOFT,
        preferred_duration_seconds=0.45,
    ),
    audio=AudioPolicy(
        target_loudness_lufs=-18.0,
        maximum_true_peak_dbfs=-1.5,
        music_energy=0.45,
        ducking_db=-11.0,
        sound_effect_density=VisualDensity.LOW,
    ),
    narrative=NarrativePolicy(
        hook="Abrir con una amenaza, escala o pregunta visual claramente legible.",
        call_to_action="Reservar el CTA para un cierre editorial, si se solicita.",
        text_in_generated_visuals=(
            "Prohibir glifos simulados; etiquetas verificadas solo como capas editables."
        ),
    ),
)


MINIMAL_BIOMEDICAL_EXPLAINER = StyleProfile(
    profile_id=MINIMAL_BIOMEDICAL_EXPLAINER_ID,
    display_name="Minimal Biomedical Explainer",
    description=(
        "Visualización académica limpia, luminosa y pausada, con espacio negativo, "
        "etiquetas discretas y continuidad macro."
    ),
    evidence=(_MITOCHONDRIA_EVIDENCE,),
    rhythm=RhythmPolicy(
        preferred_shot_seconds=24.0,
        minimum_shot_seconds=8.0,
        maximum_shot_seconds=64.0,
        visual_density=VisualDensity.LOW,
    ),
    composition=CompositionPolicy(
        visual_fit=VisualFit.CONTAIN,
        canvas_color="#F4FBFF",
        visual_density=VisualDensity.LOW,
        layouts=_layouts(
            vertical_y=0.78,
            horizontal_y=0.82,
            square_y=0.8,
            vertical_width=0.78,
            horizontal_width=0.58,
            square_width=0.72,
            vertical_scale=0.68,
            horizontal_scale=0.52,
            square_scale=0.6,
        ),
    ),
    captions=CaptionPolicy(
        timing=CaptionTiming.STATIC,
        uppercase=False,
        font_family="Aileron",
        font_weight=500,
        font_size_fraction=0.046,
        line_height=1.2,
        fill_color="#0F2942",
        emphasis_color="#0891B2",
        background_color="rgba(244,251,255,0.82)",
        background_x_padding=0.12,
        background_y_padding=0.1,
        background_border_radius=0.04,
        maximum_characters=48,
    ),
    motion=MotionPolicy(
        character=MotionCharacter.MINIMAL,
        intensity_multiplier=0.42,
        preferred_easing="cubic-in-out",
        techniques=("zoom lento", "pan suave", "parallax sutil"),
    ),
    motion_graphics=MotionGraphicsPolicy(
        density=VisualDensity.LOW,
        allowed_elements=("etiqueta técnica", "línea guía", "título académico"),
        label_strategy="Etiquetas pequeñas, discretas y siempre legibles sobre espacio negativo.",
    ),
    b_roll=BrollPolicy(
        strategy="Cutaways científicos limpios dentro del mismo nivel de explicación.",
        density=VisualDensity.LOW,
        preferred_subjects=("célula", "organelo", "membrana", "complejo proteico"),
        continuity_rule="Mantener fondo luminoso, escala progresiva y paleta clínica.",
    ),
    transitions=TransitionPolicy(
        character=TransitionCharacter.DISSOLVE,
        preferred_duration_seconds=0.7,
    ),
    audio=AudioPolicy(
        target_loudness_lufs=-16.0,
        maximum_true_peak_dbfs=-1.5,
        music_energy=0.12,
        ducking_db=-15.0,
        sound_effect_density=VisualDensity.LOW,
    ),
    narrative=NarrativePolicy(
        hook="Usar título o premisa breve antes de profundizar en el mecanismo.",
        call_to_action="Sin CTA por defecto; terminar con una conclusión respirable.",
        text_in_generated_visuals=(
            "Mantener etiquetas fuera del asset y validarlas como texto editable."
        ),
    ),
)


BUILTIN_STYLE_PROFILES = (
    IMMERSIVE_PROCESS_EXPLAINER,
    CINEMATIC_CELLULAR_DOCUMENTARY,
    MINIMAL_BIOMEDICAL_EXPLAINER,
)


__all__ = [
    "BUILTIN_STYLE_PROFILES",
    "CINEMATIC_CELLULAR_DOCUMENTARY",
    "CINEMATIC_CELLULAR_DOCUMENTARY_ID",
    "IMMERSIVE_PROCESS_EXPLAINER",
    "IMMERSIVE_PROCESS_EXPLAINER_ID",
    "MINIMAL_BIOMEDICAL_EXPLAINER",
    "MINIMAL_BIOMEDICAL_EXPLAINER_ID",
]
