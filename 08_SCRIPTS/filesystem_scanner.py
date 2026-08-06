"""
===============================================================================
AUD-001
Repository Inventory

File:
    filesystem_scanner.py

Purpose:
    Canonical repository filesystem scanner.

This module performs a READ ONLY traversal of the repository and
discovers every eligible file according to the configured scan policy.

===============================================================================
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable
from typing import Iterator

from audit_constants import (
    DEFAULT_EXCLUDED_DIRECTORIES,
    DEFAULT_EXCLUDED_FILES,
)

from audit_exceptions import (
    InvalidRepositoryRootError,
    RepositoryTraversalError,
)

from audit_models import (
    ScanConfiguration,
)


class FilesystemScanner:
    """
    Performs a deterministic repository traversal.
    """

    def __init__(
        self,
        configuration: ScanConfiguration,
    ) -> None:

        self.configuration = configuration

    # -------------------------------------------------------------------------
    # PUBLIC API
    # -------------------------------------------------------------------------

    def scan(self) -> list[Path]:

        root = self.configuration.repository_root

        if not root.exists():

            raise InvalidRepositoryRootError(root)

        if not root.is_dir():

            raise InvalidRepositoryRootError(root)

        files: list[Path] = []

        for file in self._walk(root):

            files.append(file)

        files.sort(
            key=lambda item: (
                str(
                    item.relative_to(root)
                ).lower()
            )
        )

        return files

    # -------------------------------------------------------------------------
    # INTERNAL
    # -------------------------------------------------------------------------

    def _walk(
        self,
        directory: Path,
    ) -> Iterator[Path]:

        try:

            entries = sorted(
                directory.iterdir(),
                key=lambda item: item.name.lower(),
            )

        except Exception as error:

            raise RepositoryTraversalError(
                directory,
                reason=str(error),
            ) from error

        for entry in entries:

            if self._is_excluded(entry):

                continue

            if entry.is_symlink():

                if not self.configuration.follow_symlinks:

                    continue

            if entry.is_dir():

                if self.configuration.recursive:

                    yield from self._walk(entry)

                continue

            if entry.is_file():

                yield entry

    # -------------------------------------------------------------------------

    def _is_excluded(
        self,
        path: Path,
    ) -> bool:

        name = path.name

        if (
            not self.configuration.include_hidden
            and name.startswith(".")
            and name not in (
                ".gitignore",
            )
        ):

            return True

        if name in DEFAULT_EXCLUDED_DIRECTORIES:

            return True

        if name in DEFAULT_EXCLUDED_FILES:

            return True

        for pattern in self.configuration.exclude_patterns:

            if path.match(pattern):

                return True

        return False


# =============================================================================
# HELPERS
# =============================================================================


def discover_repository_files(
    configuration: ScanConfiguration,
) -> list[Path]:
    """
    Convenience helper used by the Audit Engine.
    """

    scanner = FilesystemScanner(
        configuration
    )

    return scanner.scan()


def iter_repository_files(
    configuration: ScanConfiguration,
) -> Iterable[Path]:
    """
    Streaming version of the scanner.
    """

    scanner = FilesystemScanner(
        configuration
    )

    return scanner._walk(
        configuration.repository_root
    )