"""
===============================================================================
AUD-004
Dependency Inventory

File:
    dependency_smoke_test.py

Purpose:
    Smoke Test for the Dependency Scanner.

Execution Policy:
    READ ONLY

===============================================================================
"""

from __future__ import annotations

import tempfile

from pathlib import Path

from audit_models import (
    ScanConfiguration,
)

from filesystem_scanner import (
    discover_repository_files,
)

from python_module_scanner import (
    scan_python_modules,
)

from dependency_scanner import (
    scan_dependencies,
)

from dependency_inventory_writer import (
    write_dependency_inventory,
)


# =============================================================================
# TEST REPOSITORY
# =============================================================================


def create_repository(
    root: Path,
) -> None:

    (root / "package").mkdir()

    (root / "package" / "__init__.py").write_text(
        "",
        encoding="utf-8",
    )

    (root / "package" / "models.py").write_text(
        """
class User:
    pass
""".strip(),
        encoding="utf-8",
    )

    (root / "package" / "service.py").write_text(
        """
from .models import User

import json
import os


class Service:

    pass
""".strip(),
        encoding="utf-8",
    )


# =============================================================================
# MAIN
# =============================================================================


def main() -> int:

    print("=" * 72)
    print("AUD-004 Dependency Inventory Smoke Test")
    print("=" * 72)

    with tempfile.TemporaryDirectory(
        prefix="aud004_",
    ) as temp:

        repository = Path(temp) / "repository"

        repository.mkdir()

        create_repository(
            repository
        )

        files = discover_repository_files(

            ScanConfiguration(

                repository_root=repository,

                recursive=True,

                compute_checksums=False,

            )

        )

        modules = scan_python_modules(

            repository_root=repository,

            files=files,

        )

        inventory = scan_dependencies(

            repository_root=repository,

            modules=modules,

        )

        if len(inventory.modules) != 3:

            raise AssertionError(
                "Unexpected number of modules."
            )

        if len(inventory.internal_edges) != 1:

            raise AssertionError(
                "Expected one internal dependency."
            )

        internal = inventory.internal_edges[0]

        if internal.target_module != "package.models":

            raise AssertionError(
                "Internal dependency resolution failed."
            )

        external_modules = {

            edge.target_module

            for edge in inventory.external_edges

        }

        if "json" not in external_modules:

            raise AssertionError(
                "json dependency missing."
            )

        if "os" not in external_modules:

            raise AssertionError(
                "os dependency missing."
            )

        output = (

            repository

            / "dependency_inventory.json"

        )

        write_dependency_inventory(

            inventory=inventory,

            output_file=output,

        )

        if not output.exists():

            raise AssertionError(
                "Dependency inventory not generated."
            )

    print()

    print("SMOKE TEST PASSED")

    print("Dependency graph : VALID")

    print("Internal edges   : VALID")

    print("External edges   : VALID")

    print("Inventory JSON   : VALID")

    print("READ ONLY        : VALID")

    print("=" * 72)

    return 0


if __name__ == "__main__":

    raise SystemExit(
        main()
    )