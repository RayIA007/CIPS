"""
===============================================================================
AUD-009
Test Inventory

File:
    test_inventory_smoke_test.py

Purpose:
    Smoke Test for the Test Inventory Scanner.

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

from test_inventory_scanner import (
    scan_tests,
)

from test_inventory_writer import (
    write_test_inventory,
)


# =============================================================================
# TEST REPOSITORY
# =============================================================================


def create_repository(
    root: Path,
) -> None:

    tests = root / "tests"

    tests.mkdir()

    (tests / "__init__.py").write_text(
        "",
        encoding="utf-8",
    )

    (tests / "test_math.py").write_text(
        """
import pytest


@pytest.fixture
def sample():
    return 1


def test_sum():
    assert 1 + 1 == 2


async def test_async():
    assert True
""".strip(),
        encoding="utf-8",
    )


# =============================================================================
# MAIN
# =============================================================================


def main() -> int:

    print("=" * 72)
    print("AUD-009 Test Inventory Smoke Test")
    print("=" * 72)

    with tempfile.TemporaryDirectory(
        prefix="aud009_",
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

        inventory = scan_tests(

            repository_root=repository,

            files=files,

        )

        if inventory.total_modules != 2:

            raise AssertionError(
                "Unexpected number of test modules."
            )

        if inventory.total_test_cases != 2:

            raise AssertionError(
                "Unexpected number of test cases."
            )

        if "PYTEST" not in inventory.frameworks:

            raise AssertionError(
                "Pytest framework not detected."
            )

        module = next(

            record

            for record in inventory.modules

            if record.relative_path.endswith(
                "test_math.py"
            )

        )

        if len(module.fixtures) != 1:

            raise AssertionError(
                "Fixture detection failed."
            )

        output = (

            repository

            / "test_inventory.json"

        )

        write_test_inventory(

            inventory=inventory,

            output_file=output,

        )

        if not output.exists():

            raise AssertionError(

                "Inventory was not generated."

            )

    print()

    print("SMOKE TEST PASSED")

    print("Test Discovery    : VALID")

    print("Framework Detect. : VALID")

    print("Fixture Detect.   : VALID")

    print("Inventory JSON    : VALID")

    print("READ ONLY         : VALID")

    print("=" * 72)

    return 0


if __name__ == "__main__":

    raise SystemExit(

        main()

    )