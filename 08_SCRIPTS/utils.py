"""
=========================================================
UTILS
Funciones auxiliares reutilizables
=========================================================
"""

from pathlib import Path
from datetime import datetime
import uuid
import yaml


# --------------------------------------------------------
# Directorios
# --------------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent

PROJECTS_DIR = ROOT / "04_PROYECTOS"

OUTPUTS_DIR = ROOT / "05_OUTPUTS"

LOGS_DIR = ROOT / "07_LOGS"

MEMORY_DIR = ROOT / "06_MEMORIA"


# --------------------------------------------------------
# Utilidades generales
# --------------------------------------------------------

def ensure_directory(path: Path) -> None:
    """
    Crea una carpeta si no existe.
    """
    path.mkdir(parents=True, exist_ok=True)


def write_text(path: Path, content: str) -> None:
    """
    Guarda un archivo de texto UTF-8.
    """
    path.write_text(content, encoding="utf-8")


def read_yaml(path: Path) -> dict:
    """
    Lee un archivo YAML.
    """
    if not path.exists():
        return {}

    with open(path, "r", encoding="utf-8") as file:
        return yaml.safe_load(file) or {}


def write_yaml(path: Path, data: dict) -> None:
    """
    Guarda un archivo YAML.
    """
    with open(path, "w", encoding="utf-8") as file:
        yaml.dump(
            data,
            file,
            allow_unicode=True,
            sort_keys=False,
        )


def current_datetime() -> str:
    """
    Fecha y hora actual.
    """
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def generate_uuid() -> str:
    """
    UUID único.
    """
    return str(uuid.uuid4())


# --------------------------------------------------------
# Inicialización
# --------------------------------------------------------

ensure_directory(PROJECTS_DIR)
ensure_directory(OUTPUTS_DIR)
ensure_directory(LOGS_DIR)
ensure_directory(MEMORY_DIR)