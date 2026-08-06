"""
===============================================================================
AUD-001
Repository Inventory

File:
    audit_engine.py

Purpose:
    Canonical orchestration engine for Repository Auditor.

Responsibilities

    • Scan repository
    • Collect metadata
    • Compute checksums
    • Build inventory
    • Produce statistics
    • Return canonical AuditResult

Execution policy

    READ ONLY

===============================================================================
"""

from __future__ import annotations

import time

from pathlib import Path

from audit_models import (
    AuditResult,
    RepositoryInventory,
    ScanConfiguration,
)

from filesystem_scanner import (
    discover_repository_files,
)

from inventory_builder import (
    InventoryBuilder,
)


class AuditEngine:
    """
    Canonical Repository Auditor engine.
    """

    def __init__(
        self,
        configuration: ScanConfiguration,
    ) -> None:

        self.configuration = configuration

    # -------------------------------------------------------------------------

    def execute(
        self,
    ) -> AuditResult:

        started = time.perf_counter()

        inventory = self._inventory()

        statistics = self._statistics(
            inventory
        )

        finished = time.perf_counter()

        return AuditResult(

            inventory=inventory,

            duration_seconds=(
                finished - started
            ),

            successful=(
                len(
                    inventory.errors
                ) == 0
            ),

            warnings=list(
                inventory.warnings
            ),

            errors=list(
                inventory.errors
            ),

            statistics=statistics,

        )

    # -------------------------------------------------------------------------

    def _inventory(
        self,
    ) -> RepositoryInventory:

        discovered_files = discover_repository_files(

            self.configuration

        )

        builder = InventoryBuilder(

            repository_root=(
                self.configuration.repository_root
            ),

            compute_checksums=(
                self.configuration.compute_checksums
            ),

        )

        return builder.build(
            discovered_files
        )

    # -------------------------------------------------------------------------

    def _statistics(
        self,
        inventory: RepositoryInventory,
    ) -> dict[str, int]:

        stats: dict[str, int] = {}

        stats["files"] = inventory.total_files

        stats["bytes"] = inventory.total_size

        for category in (
            "PYTHON",
            "YAML",
            "JSON",
            "MARKDOWN",
            "TEXT",
            "IMAGE",
            "PDF",
            "CONFIGURATION",
            "EXECUTABLE",
            "DIRECTORY",
            "OTHER",
        ):

            try:

                stats[category.lower()] = (
                    inventory.category_count(
                        getattr(
                            __import__(
                                "audit_models"
                            ),
                            "AuditCategory",
                        )[category]
                    )
                )

            except Exception:

                pass

        return stats


# =============================================================================
# CONVENIENCE API
# =============================================================================


def execute_audit(
    repository_root: Path,
    *,
    compute_checksums: bool = True,
    recursive: bool = True,
) -> AuditResult:
    """
    Execute one Repository Audit.
    """

    configuration = ScanConfiguration(

        repository_root=repository_root,

        compute_checksums=compute_checksums,

        recursive=recursive,

    )

    engine = AuditEngine(
        configuration
    )

    return engine.execute()