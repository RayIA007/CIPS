"""
===============================================================================
AUD-003
Python Module Inventory

File:
    python_module_smoke_test.py

Purpose:
    Smoke test for the Python Module Scanner.

Execution policy:
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

from python_module_inventory_writer import (
    write_python_module_inventory,
)


# =============================================================================
# TEST REPOSITORY
# =============================================================================


def create_repository(
    root: Path,
) -> None:

    (root / "package").mkdir()

    (root / "package" / "__init__.py").write_text(

        '__all__ = ["Example"]\n',

        encoding="utf-8",

    )

    (root / "package" / "example.py").write_text(

        """
import os
import json

from pathlib import Path


class Example:

    def run(self):

        return 1


def helper(a, b):

    return a + b
""".strip(),

        encoding="utf-8",

    )


# =============================================================================
# MAIN
# =============================================================================


def main() -> int:

    print("=" * 72)

    print("AUD-003 Python Module Inventory Smoke Test")

    print("=" * 72)

    with tempfile.TemporaryDirectory(

        prefix="aud003_",

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

        records = scan_python_modules(

            repository_root=repository,

            files=files,

        )

        if len(records) != 2:

            raise AssertionError(

                "Expected two Python modules."

            )

        module = next(

            record

            for record in records

            if record.module_name.endswith(

                "example"

            )

        )

        if not module.syntax_valid:

            raise AssertionError(

                "Syntax validation failed."

            )

        if len(module.classes) != 1:

            raise AssertionError(

                "Class inventory mismatch."

            )

        if len(module.functions) != 1:

            raise AssertionError(

                "Function inventory mismatch."

            )

        if len(module.imports) != 3:

            raise AssertionError(

                "Import inventory mismatch."

            )

        output = (

            repository

            / "python_module_inventory.json"

        )

        write_python_module_inventory(

            records=records,

            output_file=output,

        )

        if not output.exists():

            raise AssertionError(

                "Inventory file not generated."

            )

    print()

    print("SMOKE TEST PASSED")

    print("Python modules : VALID")

    print("AST parser     : VALID")

    print("Inventory JSON : VALID")

    print("READ ONLY      : VALID")

    print("=" * 72)

    return 0


if __name__ == "__main__":

    raise SystemExit(

        main()

    )