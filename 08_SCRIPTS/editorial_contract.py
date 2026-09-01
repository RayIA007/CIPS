"""Provider-neutral contract for FAO.3 editorial automation.

This module centralizes the stages, prerequisite artifacts and prompt rules
used by the automatic editorial path.  It deliberately contains no provider
SDK calls and no production-manifest derivation; those responsibilities remain
outside FAO.3.
"""

from __future__ import annotations

from pathlib import Path

from runtime_constants import STAGE_FILES


EDITORIAL_STAGES: tuple[str, ...] = (
    "investigacion",
    "verificacion",
    "guion",
    "storyboard",
    "seo",
    "publicacion",
    "narracion",
)

EDITORIAL_PREREQUISITES: dict[str, tuple[str, ...]] = {
    "investigacion": (),
    "verificacion": ("investigacion",),
    "guion": ("investigacion", "verificacion"),
    "storyboard": ("verificacion", "guion"),
    "seo": ("verificacion", "guion"),
    "publicacion": ("verificacion", "guion", "seo"),
    "narracion": ("verificacion", "guion", "storyboard"),
}

LEGACY_EDITORIAL_FILES: dict[str, str] = {
    "investigacion": "01_INVESTIGACION.md",
    "verificacion": "02_VERIFICACION.md",
    "guion": "03_GUION.md",
    "storyboard": "04_STORYBOARD.md",
    "seo": "05_SEO.md",
    "publicacion": "06_PUBLICACION.md",
}

PLACEHOLDER_MARKERS: tuple[str, ...] = (
    "pendiente",
    "por completar",
    "contenido pendiente",
    "aquí va",
    "aqui va",
)

STAGE_TRACEABILITY_INSTRUCTIONS: dict[str, tuple[str, ...]] = {
    "investigacion": (
        "Asigna identificadores [A1], [A2], ... a las afirmaciones factuales.",
        "Declara al menos dos fuentes independientes como [F1], [F2], ...; cada entrada debe incluir título, organización responsable y URL http/https completa.",
        "En EVIDENCIA relaciona explícitamente cada [A#] con uno o más [F#].",
        "No inventes títulos, organizaciones ni URL. Si una afirmación no tiene respaldo suficiente, identifícala como incertidumbre en RIESGOS.",
    ),
    "verificacion": (
        "Revisa todas las [A#] de la investigación y conserva exactamente esos identificadores.",
        "Incluye una tabla con columnas Afirmación, Estado, Fuentes y Justificación.",
        "Usa únicamente los estados APROBADA, RECHAZADA o INCIERTA.",
        "Cada decisión debe citar al menos un [F#] existente en la investigación; no inventes referencias nuevas.",
    ),
    "guion": (
        "Utiliza únicamente afirmaciones marcadas APROBADA en la verificación.",
        "Incluye TRAZABILIDAD al final y relaciona cada bloque factual del guion con sus [A#] aprobadas.",
        "Adapta lenguaje, tono y complejidad a la audiencia, plataforma, duración y estilo de la solicitud operativa.",
    ),
    "storyboard": (
        "Crea al menos dos secciones ESCENA numeradas.",
        "En cada escena incluye exactamente los campos Duración, Visual, Locución y Evidencia.",
        "Expresa Duración como un número entero seguido de s; la suma debe coincidir con duration_seconds.",
        "Evidencia sólo puede citar [A#] aprobadas por la verificación.",
    ),
    "seo": (
        "Alinea título, descripción y palabras clave con el guion verificado y la plataforma solicitada.",
        "No añadas afirmaciones factuales que no estén presentes en el material aprobado.",
        "Evita promesas, clickbait engañoso y hashtags irrelevantes.",
    ),
    "publicacion": (
        "Prepara el paquete editorial, pero no publiques ni afirmes que fue publicado.",
        "Incluye CONTROL DE PUBLICACIÓN con las líneas exactas publication_performed: false y authorization_required: true.",
        "Mantén título, copy y hashtags coherentes con SEO, guion y plataforma.",
    ),
    "narracion": (
        "Entrega sólo el texto que debe pronunciar la voz, sin Markdown, encabezados, listas, URL, [A#] ni [F#].",
        "Conserva exclusivamente hechos APROBADOS y el sentido del guion validado.",
        "Ajusta la extensión para una locución natural dentro de duration_seconds.",
        "No incluyas acotaciones técnicas, créditos, instrucciones ni autorización de publicación.",
    ),
}


def canonical_editorial_path(project_path: Path, stage: str) -> Path:
    """Return the canonical artifact path for one FAO.3 stage."""

    if stage not in EDITORIAL_STAGES:
        raise ValueError(f"Stage editorial no soportado: {stage}")
    return Path(project_path) / STAGE_FILES[stage]


def legacy_editorial_path(project_path: Path, stage: str) -> Path | None:
    """Return the legacy mirror path when one exists for ``stage``."""

    filename = LEGACY_EDITORIAL_FILES.get(stage)
    if filename is None:
        return None
    return Path(project_path) / filename


def contains_placeholder(content: str) -> bool:
    """Identify unresolved placeholder content without matching valid prose."""

    normalized_lines = {
        line.strip().casefold().strip("#*_-:;. ")
        for line in str(content or "").splitlines()
        if line.strip()
    }
    return any(marker in normalized_lines for marker in PLACEHOLDER_MARKERS)


def render_traceability_contract(stage: str) -> str:
    """Render the stage-specific FAO.3 rules for inclusion in a prompt."""

    rules = STAGE_TRACEABILITY_INSTRUCTIONS.get(stage, ())
    if not rules:
        return "- No existen reglas editoriales adicionales para este Stage."
    return "\n".join(f"- {rule}" for rule in rules)


__all__ = [
    "EDITORIAL_PREREQUISITES",
    "EDITORIAL_STAGES",
    "LEGACY_EDITORIAL_FILES",
    "PLACEHOLDER_MARKERS",
    "STAGE_TRACEABILITY_INSTRUCTIONS",
    "canonical_editorial_path",
    "contains_placeholder",
    "legacy_editorial_path",
    "render_traceability_contract",
]
