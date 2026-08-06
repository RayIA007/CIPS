"""
===============================================================================
AUD-009
Test Inventory

File:
    test_inventory_writer.py

Purpose:
    Serialize the canonical Test Inventory.

Execution policy:
    READ ONLY

Output:
    test_inventory.json

===============================================================================
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from test_inventory_scanner import TestInventory


class TestInventoryWriter:
    """
    Serialize the Test Inventory to UTF-8 JSON.
    """

    def write(
        self,
        inventory: TestInventory,
        output_file: Path,
    ) -> None:
        output_file.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        payload = self._convert(
            asdict(inventory)
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
                key: self._convert(item)
                for key, item in value.items()
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


def write_test_inventory(
    *,
    inventory: TestInventory,
    output_file: Path,
) -> None:
    """
    Convenience API for AUD-009.
    """

    TestInventoryWriter().write(
        inventory,
        output_file,
    )