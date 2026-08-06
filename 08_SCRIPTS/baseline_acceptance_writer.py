"""
===============================================================================
AUD-012
Official Baseline Acceptance

File:
    baseline_acceptance_writer.py

Purpose:
    Serialize the Official Baseline Acceptance Report.

Execution policy:
    READ ONLY

Output:
    baseline_acceptance_report.json

===============================================================================
"""

from __future__ import annotations

import json

from dataclasses import asdict
from pathlib import Path
from typing import Any

from baseline_acceptance import (
    BaselineAcceptanceReport,
)


class BaselineAcceptanceWriter:
    """
    Serialize the Official Baseline Acceptance Report.
    """

    def write(
        self,
        report: BaselineAcceptanceReport,
        output_file: Path,
    ) -> None:

        output_file.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        payload = self._convert(

            asdict(report)

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


# =============================================================================
# CONVENIENCE API
# =============================================================================


def write_baseline_acceptance_report(
    *,
    report: BaselineAcceptanceReport,
    output_file: Path,
) -> None:
    """
    Convenience API.
    """

    BaselineAcceptanceWriter().write(

        report,

        output_file,

    )