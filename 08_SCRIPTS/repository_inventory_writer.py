"""
===============================================================================
AUD-001
Repository Inventory

File:
    repository_inventory_writer.py

Purpose:
    Serialize the canonical RepositoryInventory model into the official
    repository_inventory.json document.

===============================================================================
"""

from __future__ import annotations

import json

from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from audit_exceptions import (
    InventorySerializationError,
    InventoryWriteError,
)

from audit_models import (
    RepositoryInventory,
)


class RepositoryInventoryWriter:
    """
    Writes the canonical repository inventory.

    Output format:
        JSON

    Encoding:
        UTF-8

    Formatting:
        Pretty printed
    """

    def write(
        self,
        inventory: RepositoryInventory,
        output_file: Path,
    ) -> None:

        try:

            output_file.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            payload = self._serialize(
                inventory
            )

        except Exception as error:

            raise InventorySerializationError(

                output_path=output_file,

                reason=str(error),

            ) from error

        try:

            output_file.write_text(

                json.dumps(

                    payload,

                    indent=4,

                    ensure_ascii=False,

                    sort_keys=False,

                ),

                encoding="utf-8",

            )

        except Exception as error:

            raise InventoryWriteError(

                output_path=output_file,

                reason=str(error),

            ) from error

    # ---------------------------------------------------------------------

    def _serialize(

        self,

        inventory: RepositoryInventory,

    ) -> dict[str, Any]:

        return self._convert(

            asdict(

                inventory

            )

        )

    # ---------------------------------------------------------------------

    def _convert(

        self,

        value: Any,

    ) -> Any:

        if isinstance(

            value,

            datetime,

        ):

            return value.isoformat()

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

            list,

        ):

            return [

                self._convert(

                    item

                )

                for item in value

            ]

        return value


# =============================================================================
# CONVENIENCE API
# =============================================================================


def write_inventory(

    inventory: RepositoryInventory,

    output_file: Path,

) -> None:
    """
    Serialize the repository inventory.
    """

    RepositoryInventoryWriter().write(

        inventory,

        output_file,

    )