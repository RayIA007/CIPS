"""
===============================================================================
AUD-010
Compatibility Assessment

File:
    compatibility_report_writer.py

Purpose:
    Serialize the canonical Compatibility Assessment report.

Execution policy:
    READ ONLY

Output:
    compatibility_report.json

===============================================================================
"""

from __future__ import annotations

import json

from dataclasses import asdict
from pathlib import Path
from typing import Any

from compatibility_assessment import (
    CompatibilityAssessment,
)


class CompatibilityReportWriter:
    """
    Serialize the Compatibility Assessment report.
    """

    def write(
        self,
        report: CompatibilityAssessment,
        output_file: Path,
    ) -> None:

        output_file.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        payload = self._serialize(
            report
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
        report: CompatibilityAssessment,
    ) -> dict[str, Any]:

        return self._convert(

            asdict(report)

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


def write_compatibility_report(
    *,
    report: CompatibilityAssessment,
    output_file: Path,
) -> None:
    """
    Convenience API for AUD-010.
    """

    CompatibilityReportWriter().write(

        report,

        output_file,

    )