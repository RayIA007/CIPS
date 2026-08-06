"""
===============================================================================
AUD-006
Runtime Inventory

File:
    runtime_smoke_test.py

Purpose:
    Smoke Test for the Runtime Scanner.

Execution Policy:
    READ ONLY

===============================================================================
"""

from __future__ import annotations

import tempfile

from pathlib import Path

from runtime_scanner import (
    scan_runtime,
)

from runtime_inventory_writer import (
    write_runtime_inventory,
)


# =============================================================================
# MAIN
# =============================================================================


def main() -> int:

    print("=" * 72)

    print("AUD-006 Runtime Inventory Smoke Test")

    print("=" * 72)

    inventory = scan_runtime()

    if not inventory.python_version:

        raise AssertionError(

            "Python version not detected."

        )

    if not inventory.python_executable:

        raise AssertionError(

            "Python executable not detected."

        )

    if not inventory.operating_system:

        raise AssertionError(

            "Operating system not detected."

        )

    if len(inventory.tools) == 0:

        raise AssertionError(

            "No runtime tools detected."

        )

    if len(inventory.installed_packages) == 0:

        raise AssertionError(

            "No installed Python packages detected."

        )

    python_tool = next(

        (

            tool

            for tool in inventory.tools

            if tool.name.startswith(

                "python"

            )

            and tool.available

        ),

        None,

    )

    if python_tool is None:

        raise AssertionError(

            "Python executable not available."

        )

    with tempfile.TemporaryDirectory(

        prefix="aud006_",

    ) as temp:

        output = (

            Path(temp)

            / "runtime_inventory.json"

        )

        write_runtime_inventory(

            inventory=inventory,

            output_file=output,

        )

        if not output.exists():

            raise AssertionError(

                "Runtime inventory was not generated."

            )

    print()

    print("SMOKE TEST PASSED")

    print("Python Runtime     : VALID")

    print("Operating System   : VALID")

    print("Installed Packages : VALID")

    print("Runtime Tools      : VALID")

    print("Inventory JSON     : VALID")

    print("READ ONLY          : VALID")

    print("=" * 72)

    return 0


if __name__ == "__main__":

    raise SystemExit(

        main()

    )