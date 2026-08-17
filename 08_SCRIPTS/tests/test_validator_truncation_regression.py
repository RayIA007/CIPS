from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[1]

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from validator_engine import ValidatorEngine


@pytest.fixture
def engine() -> ValidatorEngine:
    return ValidatorEngine.__new__(ValidatorEngine)


@pytest.fixture
def truncation_rules() -> dict:
    return {
        "truncation": {
            "suspicious_endings": [
                ":",
                "-",
                "—",
                ",",
                ";",
                "(",
                "[",
                "{",
                "/",
            ],
            "incomplete_markers": [
                "continuará",
                "continúa...",
                "por completar",
                "contenido pendiente",
                "respuesta incompleta",
                "etc...",
            ],
        }
    }


@pytest.mark.parametrize(
    "content",
    [
        "Texto completo.",
        "Texto completo!",
        "Texto completo?",
        "**Texto completo en Markdown**",
        "# ETIQUETAS\nAprendizaje eficiente, Ergonomía en el estudio, Hábitos saludables",
        "# STORYBOARD\nVisual: estudiante realiza una pausa activa",
        "Texto completo sin puntuación final",
        "- Último elemento de una lista",
        "1. Último elemento de una lista numerada",
    ],
)
def test_complete_content_is_not_marked_as_truncated(
    engine: ValidatorEngine,
    truncation_rules: dict,
    content: str,
) -> None:
    assert engine._is_truncated(content, truncation_rules) is False


@pytest.mark.parametrize(
    "content",
    [
        "Texto pendiente:",
        "Texto pendiente -",
        "Texto pendiente —",
        "Texto pendiente,",
        "Texto pendiente;",
        "Texto pendiente (",
        "Texto pendiente [",
        "Texto pendiente {",
        "Texto pendiente /",
        "La explicación continúa...",
        "Contenido pendiente",
        "Respuesta incompleta",
    ],
)
def test_positive_truncation_signals_are_still_rejected(
    engine: ValidatorEngine,
    truncation_rules: dict,
    content: str,
) -> None:
    assert engine._is_truncated(content, truncation_rules) is True


def test_empty_content_is_truncated(
    engine: ValidatorEngine,
    truncation_rules: dict,
) -> None:
    assert engine._is_truncated("", truncation_rules) is True


def test_seo_terminal_labels_do_not_add_truncation_error(
    engine: ValidatorEngine,
) -> None:
    content = """# TÍTULO
Beneficios de las pausas activas en el estudio

# DESCRIPCIÓN
Las pausas activas ayudan a recuperar la atención durante jornadas prolongadas. También favorecen el movimiento y reducen la fatiga asociada con una postura sostenida. Su aplicación puede integrarse de forma sencilla dentro de una rutina de estudio.

# PALABRAS CLAVE
pausas activas, concentración, técnicas de estudio, bienestar

# HASHTAGS
#PausasActivas #TecnicasDeEstudio #Bienestar

# ETIQUETAS
Aprendizaje eficiente, Concentración mental, Hábitos de estudio saludables"""

    rules = {
        "general": {
            "minimum_characters": 100,
            "minimum_words": 20,
            "reject_truncated_response": True,
            "reject_prompt_leakage": True,
        },
        "truncation": {
            "suspicious_endings": [":", "-", "—", ",", ";", "(", "[", "{", "/"],
            "incomplete_markers": [
                "continuará",
                "continúa...",
                "por completar",
                "contenido pendiente",
                "respuesta incompleta",
                "etc...",
            ],
        },
        "model_text": {
            "prompt_leakage_markers": [],
            "refusal_markers": [],
            "generic_markers": [],
        },
        "quality": {
            "minimum_sentence_count": 3,
            "excessive_repetition_threshold": 0.35,
            "sensationalism_markers": [],
        },
    }
    stage_rules = {
        "minimum_characters": 100,
        "minimum_words": 20,
        "required_headings": ["TÍTULO", "DESCRIPCIÓN", "PALABRAS CLAVE"],
        "recommended_headings": ["HASHTAGS", "ETIQUETAS"],
    }
    errors: list[str] = []
    warnings: list[str] = []
    observations: list[str] = []

    analysis = engine._analyze_content(
        content=content,
        rules=rules,
        stage_rules=stage_rules,
        errors=errors,
        warnings=warnings,
        observations=observations,
    )

    assert analysis["truncated"] is False
    assert "La respuesta parece truncada o incompleta." not in errors
