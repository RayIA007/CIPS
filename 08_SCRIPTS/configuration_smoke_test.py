"""
===============================================================================
AUD-005
Configuration Inventory

File:
    configuration_smoke_test.py

Purpose:
    Smoke Test for the Configuration Scanner.

Execution Policy:
    READ ONLY

===============================================================================
"""

from __future__ import annotations

import json
import tempfile

from pathlib import Path

from audit_models import (
    ScanConfiguration,
)

from filesystem_scanner import (
    discover_repository_files,
)

from configuration_scanner import (
    scan_configurations,
)

from configuration_inventory_writer import (
    write_configuration_inventory,
)


# =============================================================================
# TEST REPOSITORY
# =============================================================================


def create_repository(
    root: Path,
) -> None:

    (root / "config").mkdir()

    (root / ".env").write_text(

        """
HOST=localhost
PORT=8080
DEBUG=true
""".strip(),

        encoding="utf-8",

    )

    (root / "config" / "settings.json").write_text(

        json.dumps(

            {

                "database": {},

                "logging": {},

                "runtime": {}

            },

            indent=4,

        ),

        encoding="utf-8",

    )

    (root / "pyproject.toml").write_text(

        """
[project]
name="demo"

[tool.demo]
enabled=true
""".strip(),

        encoding="utf-8",

    )


# =============================================================================
# MAIN
# =============================================================================


def main() -> int:

    print("=" * 72)

    print("AUD-005 Configuration Inventory Smoke Test")

    print("=" * 72)

    with tempfile.TemporaryDirectory(

        prefix="aud005_",

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

            include_hidden=True,
            )

        )

        inventory = scan_configurations(

            repository_root=repository,

            files=files,

        )

        if inventory.total_files != 3:

            raise AssertionError(

                "Unexpected number of configuration files."

            )

        if inventory.invalid_files != 0:

            raise AssertionError(

                "Expected every configuration file to be valid."

            )

        formats = set(

            inventory.formats

        )

        if "JSON" not in formats:

            raise AssertionError(

                "JSON format not detected."

            )

        if "TOML" not in formats:

            raise AssertionError(

                "TOML format not detected."

            )

        if "ENV" not in formats:

            raise AssertionError(

                "ENV format not detected."

            )

        output = (

            repository

            / "configuration_inventory.json"

        )

        write_configuration_inventory(

            inventory=inventory,

            output_file=output,

        )

        if not output.exists():

            raise AssertionError(

                "Configuration inventory was not generated."

            )

    print()

    print("SMOKE TEST PASSED")

    print("Configuration scan : VALID")

    print("Parser validation  : VALID")

    print("Inventory JSON     : VALID")

    print("READ ONLY          : VALID")

    print("=" * 72)

    return 0


if __name__ == "__main__":

    raise SystemExit(

        main()

    )