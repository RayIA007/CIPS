"""
===============================================================================
AUD-001
Repository Inventory

File:
    audit_constants.py

Purpose:
    Shared constants used by the Repository Auditor.

Authoritative Deliverable:
    AUD-001

===============================================================================
"""

from __future__ import annotations

from pathlib import Path


# =============================================================================
# VERSION
# =============================================================================

AUDITOR_NAME = "Repository Auditor"

AUDITOR_VERSION = "1.0.0"

AUDITOR_DELIVERABLE = "AUD-001"


# =============================================================================
# INVENTORY
# =============================================================================

DEFAULT_OUTPUT_FILENAME = "repository_inventory.json"

DEFAULT_HASH_ALGORITHM = "SHA256"


# =============================================================================
# EXCLUDED DIRECTORIES
# =============================================================================

DEFAULT_EXCLUDED_DIRECTORIES = {

    ".git",

    ".idea",

    ".vscode",

    "__pycache__",

    ".pytest_cache",

    ".mypy_cache",

    ".ruff_cache",

    ".venv",

    "venv",

    "env",

    "node_modules",

    ".DS_Store",

}


# =============================================================================
# EXCLUDED FILES
# =============================================================================

DEFAULT_EXCLUDED_FILES = {

    "Thumbs.db",

    ".DS_Store",

}


# =============================================================================
# CATEGORY MAP
# =============================================================================

CATEGORY_BY_SUFFIX = {

    ".py": "PYTHON",

    ".yaml": "YAML",

    ".yml": "YAML",

    ".json": "JSON",

    ".md": "MARKDOWN",

    ".txt": "TEXT",

    ".png": "IMAGE",

    ".jpg": "IMAGE",

    ".jpeg": "IMAGE",

    ".gif": "IMAGE",

    ".svg": "IMAGE",

    ".pdf": "PDF",

    ".ini": "CONFIGURATION",

    ".cfg": "CONFIGURATION",

    ".toml": "CONFIGURATION",

    ".xml": "CONFIGURATION",

}


# =============================================================================
# IDENTIFIERS
# =============================================================================

FILE_IDENTIFIER_PREFIX = "AUDFILE"

REPORT_IDENTIFIER_PREFIX = "AUDREPORT"


# =============================================================================
# DEFAULT PATHS
# =============================================================================

PROJECT_CONTROL_DIRECTORY = Path(
    "12_PRODUCTION_SYSTEM/99_PROJECT_CONTROL"
)

DEFAULT_OUTPUT_DIRECTORY = PROJECT_CONTROL_DIRECTORY