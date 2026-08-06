"""
===============================================================================
AUD-011
Protected Legacy Baseline

File:
    legacy_baseline_report_writer.py

Purpose:
    Serialize the Protected Legacy Baseline candidate.

Execution policy:
    READ ONLY

Output:
    legacy_baseline_candidate.json

===============================================================================
"""

from __future__ import annotations

import json

from dataclasses import asdict
from pathlib import Path
from typing import Any

from legacy_baseline_builder import (
    LegacyBaselineCandidate,
)


class LegacyBaselineReportWriter:
    """
    Serialize the Legacy Baseline Candidate.
    """

    def write(
        self,
        candidate: LegacyBaselineCandidate,
        output_file: Path,
    ) -> None:

        output_file.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        payload = self._convert(

            asdict(candidate)

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


def write_legacy_baseline_report(
    *,
    candidate: LegacyBaselineCandidate,
    output_file: Path,
) -> None:
    """
    Convenience API.
    """

    LegacyBaselineReportWriter().write(

        candidate,

        output_file,

    )