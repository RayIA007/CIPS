"""
=========================================================
Proyecto : CIPS
Release  : 0.3
Build    : 011
Archivo  : runtime_constants.py
Estado   : RELEASE
=========================================================

Constantes compartidas por todo el Runtime.
Este archivo representa la única fuente oficial para
las reglas de operación del Runtime.
"""

from typing import Final


# =========================================================
# STAGES OFICIALES
# =========================================================

STAGES: Final[list[str]] = [
    "investigacion",
    "verificacion",
    "guion",
    "storyboard",
    "seo",
    "publicacion",
    "final",
]


# =========================================================
# ARCHIVOS ASOCIADOS A CADA STAGE
# =========================================================

STAGE_FILES: Final[dict[str, str]] = {
    "investigacion": "01_INVESTIGACION.md",
    "verificacion": "02_VERIFICACION.md",
    "guion": "03_GUION.md",
    "storyboard": "04_STORYBOARD.md",
    "seo": "05_SEO.md",
    "publicacion": "06_PUBLICACION.md",
    "final": "07_FINAL.md",
}


# =========================================================
# ESTADOS TERMINALES
# =========================================================

FINAL_STAGE: Final[str] = "final"


# =========================================================
# ESTADOS VÁLIDOS
# =========================================================

VALID_STAGES: Final[set[str]] = set(STAGES)


# =========================================================
# VERSIÓN DEL RUNTIME
# =========================================================

RUNTIME_VERSION: Final[str] = "0.3"