"""
===============================================================================
AUD-008
Entrypoint Inventory

File:
    entrypoint_smoke_test.py

Purpose:
    Smoke Test for the Entrypoint Scanner.

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

from entrypoint_scanner import (
    scan_entrypoints,
)

from entrypoint_inventory_writer import (
    write_entrypoint_inventory,
)


# =============================================================================
# TEST REPOSITORY
# =============================================================================


def create_repository(
    root: Path,
) -> None:

    (root / "application").mkdir()

    (root / "application" / "__init__.py").write_text(
        "",
        encoding="utf-8",
    )

    (root / "application" / "main.py").write_text(
        """
class Application:

    def start(self):
        pass


def helper():
    pass


def main():
    pass


if __name__ == "__main__":
    main()
""".strip(),
        encoding="utf-8",
    )


# =============================================================================
# MAIN
# =============================================================================


def main() -> int:

    print("=" * 72)
    print("AUD-008 Entrypoint Inventory Smoke Test")
    print("=" * 72)

    with tempfile.TemporaryDirectory(
        prefix="aud008_",
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

        inventory = scan_entrypoints(

            repository_root=repository,

            modules=modules,

        )

        if inventory.total_entrypoints != 3:

            raise AssertionError(

                "Expected three entrypoints."

            )

        types = {

            record.entrypoint_type

            for record in inventory.records

        }

        expected = {

            "MAIN_FUNCTION",

            "MAIN_GUARD",

            "APPLICATION_CLASS",

        }

        if not expected.issubset(types):

            raise AssertionError(

                "Entrypoint classification failed."

            )

        output = (

            repository

            / "entrypoint_inventory.json"

        )

        write_entrypoint_inventory(

            inventory=inventory,

            output_file=output,

        )

        if not output.exists():

            raise AssertionError(

                "Entrypoint inventory not generated."

            )

    print()

    print("SMOKE TEST PASSED")

    print("Entrypoint Discovery : VALID")

    print("Classification       : VALID")

    print("Inventory JSON       : VALID")

    print("READ ONLY            : VALID")

    print("=" * 72)

    return 0


if __name__ == "__main__":

    raise SystemExit(

        main()

    )