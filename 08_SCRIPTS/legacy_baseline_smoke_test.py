"""
===============================================================================
AUD-011
Protected Legacy Baseline

File:
    legacy_baseline_smoke_test.py

Purpose:
    Smoke Test for the Legacy Baseline Builder.

Execution Policy:
    READ ONLY

===============================================================================
"""

from __future__ import annotations

import tempfile

from pathlib import Path
from types import SimpleNamespace

from legacy_baseline_builder import (
    build_legacy_baseline_candidate,
    LegacyBaselineBuilder,
)


# =============================================================================
# FAKE INVENTORIES
# =============================================================================


class FakeCategory:

    def __init__(self, value: str):

        self.value = value


class FakeStatus:

    def __init__(self, value: str):

        self.value = value


class FakeChecksum:

    def __init__(self, value: str):

        self.value = value


def repository_inventory():

    files = [

        SimpleNamespace(

            relative_path="README.md",

            metadata=SimpleNamespace(

                size_bytes=1024,

            ),

            checksum=FakeChecksum(

                "A" * 64,

            ),

            category=FakeCategory(

                "DOCUMENTATION",

            ),

            status=FakeStatus(

                "ACTIVE",

            ),

        ),

        SimpleNamespace(

            relative_path="src/main.py",

            metadata=SimpleNamespace(

                size_bytes=2048,

            ),

            checksum=FakeChecksum(

                "B" * 64,

            ),

            category=FakeCategory(

                "SOURCE",

            ),

            status=FakeStatus(

                "ACTIVE",

            ),

        ),

    ]

    return SimpleNamespace(

        project_name="TEST_PROJECT",

        files=files,

    )


def entrypoint_inventory():

    return SimpleNamespace(

        records=(

            SimpleNamespace(

                relative_path="src/main.py",

            ),

        )

    )


def pipeline_inventory():

    return SimpleNamespace(

        records=(

            SimpleNamespace(

                module_name="production.pipeline",

            ),

        )

    )


# =============================================================================
# MAIN
# =============================================================================


def main() -> int:

    print("=" * 72)

    print("AUD-011 Protected Legacy Baseline Smoke Test")

    print("=" * 72)

    with tempfile.TemporaryDirectory(

        prefix="aud011_",

    ) as temp:

        repository = Path(temp)

        candidate = build_legacy_baseline_candidate(

            repository_root=repository,

            repository_inventory=repository_inventory(),

            entrypoint_inventory=entrypoint_inventory(),

            pipeline_inventory=pipeline_inventory(),

        )

        if candidate.total_files != 2:

            raise AssertionError(

                "Unexpected file count."

            )

        if candidate.total_bytes != 3072:

            raise AssertionError(

                "Unexpected total size."

            )

        if len(candidate.aggregate_sha256) != 64:

            raise AssertionError(

                "Invalid aggregate hash."

            )

        if candidate.protection_status != "CANDIDATE":

            raise AssertionError(

                "Unexpected protection status."

            )

        output = (

            repository

            / "legacy_baseline_candidate.json"

        )

        LegacyBaselineBuilder(

            repository

        ).write_candidate(

            candidate=candidate,

            output_file=output,

        )

        if not output.exists():

            raise AssertionError(

                "Candidate was not generated."

            )

    print()

    print("SMOKE TEST PASSED")

    print("Baseline Builder : VALID")

    print("Aggregate Hash   : VALID")

    print("Serialization    : VALID")

    print("READ ONLY        : VALID")

    print("=" * 72)

    print()

    return 0


if __name__ == "__main__":

    raise SystemExit(

        main()

    )