"""
===============================================================================
AUD-001
Repository Inventory

File:
    audit_models.py

Purpose:
    Canonical data models used by every Repository Auditor component.

Authoritative Deliverable:
    AUD-001

Production Status:
    FOUNDATION

===============================================================================
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict
from typing import List
from typing import Optional


# =============================================================================
# ENUMERATIONS
# =============================================================================


class AuditCategory(str, Enum):

    UNKNOWN = "UNKNOWN"

    PYTHON = "PYTHON"

    YAML = "YAML"

    JSON = "JSON"

    MARKDOWN = "MARKDOWN"

    TEXT = "TEXT"

    IMAGE = "IMAGE"

    PDF = "PDF"

    CONFIGURATION = "CONFIGURATION"

    EXECUTABLE = "EXECUTABLE"

    DIRECTORY = "DIRECTORY"

    OTHER = "OTHER"


class AuditStatus(str, Enum):

    DISCOVERED = "DISCOVERED"

    INVENTORIED = "INVENTORIED"

    VERIFIED = "VERIFIED"

    ERROR = "ERROR"

    SKIPPED = "SKIPPED"


class HashAlgorithm(str, Enum):

    SHA256 = "SHA256"


# =============================================================================
# FILE HASH
# =============================================================================


@dataclass(slots=True)
class FileHash:

    algorithm: HashAlgorithm

    value: str


# =============================================================================
# FILE METADATA
# =============================================================================


@dataclass(slots=True)
class FileMetadata:

    size_bytes: int

    created: datetime

    modified: datetime

    accessed: datetime

    extension: str

    suffix: str

    owner: Optional[str]

    readonly: bool

    executable: bool


# =============================================================================
# FILE RECORD
# =============================================================================


@dataclass(slots=True)
class RepositoryFile:

    identifier: str

    relative_path: str

    absolute_path: Path

    category: AuditCategory

    metadata: FileMetadata

    checksum: Optional[FileHash]

    status: AuditStatus = AuditStatus.DISCOVERED

    tags: List[str] = field(default_factory=list)

    attributes: Dict[str, str] = field(default_factory=dict)

    def filename(self) -> str:

        return self.absolute_path.name

    def directory(self) -> Path:

        return self.absolute_path.parent

    def is_python(self) -> bool:

        return self.category is AuditCategory.PYTHON

    def is_directory(self) -> bool:

        return self.category is AuditCategory.DIRECTORY


# =============================================================================
# INVENTORY
# =============================================================================


@dataclass(slots=True)
class RepositoryInventory:

    project_name: str

    root_directory: Path

    generated_at: datetime

    files: List[RepositoryFile] = field(default_factory=list)

    warnings: List[str] = field(default_factory=list)

    errors: List[str] = field(default_factory=list)

    def add(self, file: RepositoryFile) -> None:

        self.files.append(file)

    @property
    def total_files(self) -> int:

        return len(self.files)

    @property
    def total_size(self) -> int:

        return sum(
            file.metadata.size_bytes
            for file in self.files
        )

    def category_count(
        self,
        category: AuditCategory
    ) -> int:

        return sum(
            file.category is category
            for file in self.files
        )


# =============================================================================
# SCAN CONFIGURATION
# =============================================================================


@dataclass(slots=True)
class ScanConfiguration:

    repository_root: Path

    follow_symlinks: bool = False

    compute_checksums: bool = True

    recursive: bool = True

    include_hidden: bool = False

    exclude_patterns: List[str] = field(
        default_factory=list
    )


# =============================================================================
# AUDIT RESULT
# =============================================================================


@dataclass(slots=True)
class AuditResult:

    inventory: RepositoryInventory

    duration_seconds: float

    successful: bool

    warnings: List[str] = field(
        default_factory=list
    )

    errors: List[str] = field(
        default_factory=list
    )

    statistics: Dict[str, int] = field(
        default_factory=dict
    )