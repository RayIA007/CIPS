"""
===============================================================================
AUD-004
Dependency Inventory

File:
    dependency_inventory_writer.py

Purpose:
    Serialize the canonical Dependency Inventory.

Execution policy:
    READ ONLY

Output:
    dependency_inventory.json

===============================================================================
"""

from __future__ import annotations

import json

from dataclasses import asdict
from pathlib import Path
from typing import Any

from dependency_scanner import (
    DependencyInventory,
)


class DependencyInventoryWriter:
    """
    Serialize the Dependency Inventory.
    """

    def write(
        self,
        inventory: DependencyInventory,
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
        inventory: DependencyInventory,
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


def write_dependency_inventory(
    *,
    inventory: DependencyInventory,
    output_file: Path,
) -> None:
    """
    Convenience API.
    """

    DependencyInventoryWriter().write(

        inventory,

        output_file,

    )