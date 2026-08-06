"""
===============================================================================
AUD-001
Repository Inventory

File:
    audit_exceptions.py

Purpose:
    Canonical exception hierarchy used by the Repository Auditor.

Authoritative Deliverable:
    AUD-001

===============================================================================
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


# =============================================================================
# BASE EXCEPTION
# =============================================================================


class RepositoryAuditError(Exception):
    """
    Base exception for every Repository Auditor failure.

    All domain-specific exceptions must inherit from this class so callers
    can handle Repository Auditor failures consistently.
    """


# =============================================================================
# CONFIGURATION ERRORS
# =============================================================================


class AuditConfigurationError(RepositoryAuditError):
    """
    Raised when the auditor receives an invalid configuration.
    """


class InvalidRepositoryRootError(AuditConfigurationError):
    """
    Raised when the configured repository root does not exist or is invalid.
    """

    def __init__(self, repository_root: Path) -> None:
        self.repository_root = repository_root

        super().__init__(
            f"Repository root is invalid or does not exist: "
            f"{repository_root}"
        )


class InvalidOutputPathError(AuditConfigurationError):
    """
    Raised when the configured output path cannot be used.
    """

    def __init__(self, output_path: Path) -> None:
        self.output_path = output_path

        super().__init__(
            f"Inventory output path is invalid: {output_path}"
        )


# =============================================================================
# FILESYSTEM ERRORS
# =============================================================================


class AuditFilesystemError(RepositoryAuditError):
    """
    Base exception for filesystem inspection failures.
    """


class FileAccessError(AuditFilesystemError):
    """
    Raised when a repository file cannot be accessed.
    """

    def __init__(
        self,
        path: Path,
        *,
        operation: str,
        reason: str,
    ) -> None:
        self.path = path
        self.operation = operation
        self.reason = reason

        super().__init__(
            f"Unable to {operation} '{path}': {reason}"
        )


class SymlinkResolutionError(AuditFilesystemError):
    """
    Raised when a symbolic link cannot be resolved safely.
    """

    def __init__(
        self,
        path: Path,
        *,
        reason: str,
    ) -> None:
        self.path = path
        self.reason = reason

        super().__init__(
            f"Unable to resolve symbolic link '{path}': {reason}"
        )


class RepositoryTraversalError(AuditFilesystemError):
    """
    Raised when the repository traversal cannot continue.
    """

    def __init__(
        self,
        path: Path,
        *,
        reason: str,
    ) -> None:
        self.path = path
        self.reason = reason

        super().__init__(
            f"Repository traversal failed at '{path}': {reason}"
        )


# =============================================================================
# CHECKSUM ERRORS
# =============================================================================


class ChecksumError(RepositoryAuditError):
    """
    Base exception for checksum calculation failures.
    """


class ChecksumCalculationError(ChecksumError):
    """
    Raised when a file checksum cannot be calculated.
    """

    def __init__(
        self,
        path: Path,
        *,
        algorithm: str,
        reason: str,
    ) -> None:
        self.path = path
        self.algorithm = algorithm
        self.reason = reason

        super().__init__(
            f"Unable to calculate {algorithm} checksum for "
            f"'{path}': {reason}"
        )


class UnsupportedHashAlgorithmError(ChecksumError):
    """
    Raised when the requested hash algorithm is unsupported.
    """

    def __init__(self, algorithm: str) -> None:
        self.algorithm = algorithm

        super().__init__(
            f"Unsupported hash algorithm: {algorithm}"
        )


# =============================================================================
# METADATA ERRORS
# =============================================================================


class MetadataCollectionError(RepositoryAuditError):
    """
    Raised when file metadata cannot be collected.
    """

    def __init__(
        self,
        path: Path,
        *,
        reason: str,
    ) -> None:
        self.path = path
        self.reason = reason

        super().__init__(
            f"Unable to collect metadata for '{path}': {reason}"
        )


# =============================================================================
# INVENTORY ERRORS
# =============================================================================


class InventoryBuildError(RepositoryAuditError):
    """
    Raised when a repository inventory cannot be constructed.
    """


class DuplicateInventoryEntryError(InventoryBuildError):
    """
    Raised when the same repository path is registered more than once.
    """

    def __init__(self, relative_path: str) -> None:
        self.relative_path = relative_path

        super().__init__(
            f"Duplicate repository inventory entry: {relative_path}"
        )


class InvalidInventoryRecordError(InventoryBuildError):
    """
    Raised when an inventory record is structurally invalid.
    """

    def __init__(
        self,
        *,
        identifier: str,
        reason: str,
    ) -> None:
        self.identifier = identifier
        self.reason = reason

        super().__init__(
            f"Inventory record '{identifier}' is invalid: {reason}"
        )


# =============================================================================
# SERIALIZATION ERRORS
# =============================================================================


class InventorySerializationError(RepositoryAuditError):
    """
    Raised when the repository inventory cannot be serialized.
    """

    def __init__(
        self,
        *,
        output_path: Path,
        reason: str,
    ) -> None:
        self.output_path = output_path
        self.reason = reason

        super().__init__(
            f"Unable to serialize repository inventory to "
            f"'{output_path}': {reason}"
        )


class InventoryWriteError(RepositoryAuditError):
    """
    Raised when serialized inventory data cannot be written.
    """

    def __init__(
        self,
        *,
        output_path: Path,
        reason: str,
    ) -> None:
        self.output_path = output_path
        self.reason = reason

        super().__init__(
            f"Unable to write repository inventory to "
            f"'{output_path}': {reason}"
        )


# =============================================================================
# VALIDATION ERRORS
# =============================================================================


@dataclass(frozen=True, slots=True)
class AuditValidationIssue:
    """
    Structured validation issue reported by AUD-001.
    """

    code: str
    message: str
    path: Path | None = None
    details: dict[str, Any] | None = None


class AuditValidationError(RepositoryAuditError):
    """
    Raised when the generated inventory fails AUD-001 validation.
    """

    def __init__(
        self,
        issues: list[AuditValidationIssue],
    ) -> None:
        self.issues = tuple(issues)

        summary = "; ".join(
            f"{issue.code}: {issue.message}"
            for issue in self.issues
        )

        super().__init__(
            "Repository inventory validation failed"
            + (f": {summary}" if summary else ".")
        )


# =============================================================================
# EXECUTION ERRORS
# =============================================================================


class AuditExecutionError(RepositoryAuditError):
    """
    Raised when the complete Repository Auditor execution fails.
    """


class AuditInterruptedError(AuditExecutionError):
    """
    Raised when the audit execution is interrupted before completion.
    """


class AuditInvariantError(AuditExecutionError):
    """
    Raised when an internal Repository Auditor invariant is violated.
    """