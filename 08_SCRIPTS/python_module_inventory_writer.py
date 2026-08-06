"""
===============================================================================
AUD-003
Python Module Inventory

File:
    python_module_inventory_writer.py

Purpose:
    Serialize the canonical Python Module Inventory into JSON.

Execution policy:
    READ ONLY

Output:
    python_module_inventory.json

===============================================================================
"""

from __future__ import annotations

import json

from dataclasses import asdict
from pathlib import Path
from typing import Any


class PythonModuleInventoryWriter:
    """
    Serialize Python module inventory.
    """

    def write(
        self,
        records: list,
        output_file: Path,
    ) -> None:

        output_file.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        payload = self._serialize(
            records
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

    # ---------------------------------------------------------------------

    def _serialize(
        self,
        records: list,
    ) -> list[dict]:

        return [

            self._convert(

                asdict(record)

            )

            for record in records

        ]

    # ---------------------------------------------------------------------

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


def write_python_module_inventory(
    *,
    records: list,
    output_file: Path,
) -> None:
    """
    Convenience API.
    """

    PythonModuleInventoryWriter().write(

        records,

        output_file,

    )