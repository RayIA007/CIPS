"""
===============================================================================
AUD-006
Runtime Inventory

File:
    runtime_inventory_writer.py

Purpose:
    Serialize the canonical Runtime Inventory.

Execution policy:
    READ ONLY

Output:
    runtime_inventory.json

===============================================================================
"""

from __future__ import annotations

import json

from dataclasses import asdict
from pathlib import Path
from typing import Any

from runtime_scanner import (
    RuntimeInventory,
)


class RuntimeInventoryWriter:
    """
    Serialize the Runtime Inventory.
    """

    def write(
        self,
        inventory: RuntimeInventory,
        output_file: Path,
    ) -> None:

        output_file.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        payload = self._serialize(
            inventory
        )

        output_file.write_text(

            json.dumps(

                payload,

                indent=4,

                ensure_ascii=False,

                sort_keys=False,

            ),

            encoding="utf-8",

        )

    # -------------------------------------------------------------------------

    def _serialize(
        self,
        inventory: RuntimeInventory,
    ) -> dict[str, Any]:

        return self._convert(

            asdict(
                inventory
            )

        )

    # -------------------------------------------------------------------------

    def _convert(
        self,
        value: Any,
    ) -> Any:

        if isinstance(
            value,
            Path,
        ):

            return str(value)

        if isinstance(
            value,
            dict,
        ):

            return {

                key: self._convert(val)

                for key, val in value.items()

            }

        if isinstance(
            value,
            (
                list,
                tuple,
            ),
        ):

            return [

                self._convert(item)

                for item in value

            ]

        return value


# =============================================================================
# CONVENIENCE API
# =============================================================================


def write_runtime_inventory(
    *,
    inventory: RuntimeInventory,
    output_file: Path,
) -> None:
    """
    Convenience API for AUD-006.
    """

    RuntimeInventoryWriter().write(

        inventory,

        output_file,

    )