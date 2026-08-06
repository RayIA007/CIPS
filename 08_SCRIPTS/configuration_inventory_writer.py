"""
===============================================================================
AUD-005
Configuration Inventory

File:
    configuration_inventory_writer.py

Purpose:
    Serialize the canonical Configuration Inventory.

Execution policy:
    READ ONLY

Output:
    configuration_inventory.json

===============================================================================
"""

from __future__ import annotations

import json

from dataclasses import asdict
from pathlib import Path
from typing import Any

from configuration_scanner import (
    ConfigurationInventory,
)


class ConfigurationInventoryWriter:
    """
    Serialize the Configuration Inventory.
    """

    def write(
        self,
        inventory: ConfigurationInventory,
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
        inventory: ConfigurationInventory,
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


def write_configuration_inventory(
    *,
    inventory: ConfigurationInventory,
    output_file: Path,
) -> None:
    """
    Convenience API for AUD-005.
    """

    ConfigurationInventoryWriter().write(

        inventory,

        output_file,

    )