"""
===============================================================================
AUD-001
Repository Inventory

File:
    inventory_builder.py

Purpose:
    Build the canonical RepositoryInventory model from filesystem data.

===============================================================================
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from audit_constants import (
    CATEGORY_BY_SUFFIX,
    FILE_IDENTIFIER_PREFIX,
)

from audit_exceptions import (
    DuplicateInventoryEntryError,
)

from audit_models import (
    AuditCategory,
    AuditStatus,
    FileHash,
    RepositoryFile,
    RepositoryInventory,
    RepositoryFile,
)

from checksum_engine import (
    sha256,
)

from metadata_collector import (
    collect_file_metadata,
)


class InventoryBuilder:
    """
    Builds the canonical repository inventory.
    """

    def __init__(
        self,
        repository_root: Path,
        *,
        compute_checksums: bool = True,
    ) -> None:

        self.repository_root = repository_root

        self.compute_checksums = compute_checksums

        self._registered: set[str] = set()

    # -------------------------------------------------------------------------

    def build(
        self,
        files: list[Path],
    ) -> RepositoryInventory:

        inventory = RepositoryInventory(

            project_name=self.repository_root.name,

            root_directory=self.repository_root,

            generated_at=datetime.now(
                timezone.utc
            ),

        )

        for index, file_path in enumerate(files, start=1):

            inventory.add(

                self._build_file(

                    file_path,

                    index,

                )

            )

        return inventory

    # -------------------------------------------------------------------------

    def _build_file(

        self,

        file_path: Path,

        index: int,

    ) -> RepositoryFile:

        relative_path = str(

            file_path.relative_to(

                self.repository_root

            )

        )

        if relative_path in self._registered:

            raise DuplicateInventoryEntryError(

                relative_path

            )

        self._registered.add(

            relative_path

        )

        metadata = collect_file_metadata(

            file_path

        )

        checksum: FileHash | None = None

        if self.compute_checksums:

            checksum = sha256(

                file_path

            )

        return RepositoryFile(

            identifier=self._identifier(

                index

            ),

            relative_path=relative_path,

            absolute_path=file_path,

            category=self._category(

                metadata.extension

            ),

            metadata=metadata,

            checksum=checksum,

            status=AuditStatus.INVENTORIED,

        )

    # -------------------------------------------------------------------------

    @staticmethod
    def _identifier(

        index: int,

    ) -> str:

        return (

            f"{FILE_IDENTIFIER_PREFIX}-"

            f"{index:06d}"

        )

    # -------------------------------------------------------------------------

    @staticmethod
    def _category(

        extension: str,

    ) -> AuditCategory:

        value = CATEGORY_BY_SUFFIX.get(

            extension.lower(),

            "OTHER",

        )

        return AuditCategory[value]