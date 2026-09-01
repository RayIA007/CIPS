"""
=========================================================
Proyecto : CIPS
Release  : 0.5
Build    : 020
Archivo  : runtime_constants.py
Estado   : RELEASE
=========================================================

Constantes compartidas por todo el Runtime.
Este archivo representa la única fuente oficial para
las reglas de operación del Runtime.
"""

from typing import Final


# =========================================================
# STAGES OFICIALES DEL PIPELINE (SECUENCIAL)
# =========================================================

STAGES: Final[list[str]] = [
    # Fase Editorial
    "investigacion",
    "verificacion",
    "guion",
    "storyboard",
    "seo",
    "publicacion",
    # Entregable editorial pronunciable
    "narracion",
    # Fase Media Production física
    "voz",
    "imagenes",
    "subtitulos",
    "ensamblado",
    "control_calidad",
    "final",
]


# =========================================================
# ARCHIVOS/CARPETAS ASOCIADOS A CADA STAGE
# =========================================================

STAGE_FILES: Final[dict[str, str]] = {
    "investigacion": "research/01_INVESTIGACION.md",
    "verificacion": "verification/02_VERIFICACION.md",
    "guion": "script/03_GUION.md",
    "storyboard": "storyboard/04_STORYBOARD.md",
    "seo": "seo/05_SEO.md",
    "publicacion": "publication/06_PUBLICACION.md",
    "narracion": "narration/narration.txt",
    "voz": "voice/audio.mp3",
    "imagenes": "images/",
    "subtitulos": "subtitles/subtitles.srt",
    "ensamblado": "video/raw_video.mp4",
    "control_calidad": "final/production_report.json",
    "final": "final/short.mp4",
}


# =========================================================
# ESTADOS DEL SISTEMA / MÁQUINA DE ESTADOS (PRODUCTION STATUS)
# =========================================================

PROJECT_STATES: Final[list[str]] = [
    "CREATED",
    "INITIALIZING",
    "RUNNING",
    "MEDIA_PRODUCTION",
    "VOICE_GENERATION",
    "IMAGE_GENERATION",
    "VIDEO_ASSEMBLY",
    "QUALITY_CONTROL",
    "READY_FOR_REVIEW",
    "APPROVED",
    "REJECTED",
    "PUBLISHED",
]


# =========================================================
# ESTADOS TERMINALES
# =========================================================

FINAL_STAGE: Final[str] = "final"
REVIEW_STATE: Final[str] = "READY_FOR_REVIEW"


# =========================================================
# ESTADOS VÁLIDOS
# =========================================================

VALID_STAGES: Final[set[str]] = set(STAGES)
VALID_PROJECT_STATES: Final[set[str]] = set(PROJECT_STATES)


# =========================================================
# VERSIÓN DEL RUNTIME
# =========================================================

RUNTIME_VERSION: Final[str] = "0.5"
