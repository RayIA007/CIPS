"""
===============================================================================
AUD-001
Repository Inventory

File:
    repository_auditor.py

Purpose:
    Repository Auditor command line interface.

Execution policy:
    READ ONLY

===============================================================================
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from audit_constants import (
    AUDITOR_DELIVERABLE,
    AUDITOR_NAME,
    AUDITOR_VERSION,
    DEFAULT_OUTPUT_DIRECTORY,
    DEFAULT_OUTPUT_FILENAME,
)

from audit_engine import (
    execute_audit,
)

from repository_inventory_writer import (
    write_inventory,
)


# =============================================================================
# ARGUMENTS
# =============================================================================


def build_argument_parser() -> argparse.ArgumentParser:

    parser = argparse.ArgumentParser(

        prog="repository_auditor",

        description=(
            "AUD-001 Repository Inventory"
        ),

    )

    parser.add_argument(

        "--repository",

        type=Path,

        default=Path.cwd(),

        help=(
            "Repository root"
        ),

    )

    parser.add_argument(

        "--output",

        type=Path,

        default=(
            DEFAULT_OUTPUT_DIRECTORY
            /
            DEFAULT_OUTPUT_FILENAME
        ),

        help=(
            "Inventory output file"
        ),

    )

    parser.add_argument(

        "--no-checksum",

        action="store_true",

        help=(
            "Disable SHA-256 calculation"
        ),

    )

    parser.add_argument(

        "--non-recursive",

        action="store_true",

        help=(
            "Scan only first level"
        ),

    )

    parser.add_argument(

        "--summary",

        action="store_true",

        help=(
            "Print summary only"
        ),

    )

    return parser


# =============================================================================
# CONSOLE
# =============================================================================


def print_header() -> None:

    print("=" * 72)

    print(AUDITOR_NAME)

    print("=" * 72)

    print(
        f"Version      : {AUDITOR_VERSION}"
    )

    print(
        f"Deliverable  : {AUDITOR_DELIVERABLE}"
    )

    print()


def print_summary(result) -> None:

    inventory = result.inventory

    print()

    print("Inventory Summary")

    print("-" * 72)

    print(
        f"Files      : {inventory.total_files}"
    )

    print(
        f"Bytes      : {inventory.total_size:,}"
    )

    print(
        f"Warnings   : {len(result.warnings)}"
    )

    print(
        f"Errors     : {len(result.errors)}"
    )

    print(
        f"Duration   : "
        f"{result.duration_seconds:.3f}s"
    )


# =============================================================================
# MAIN
# =============================================================================


def main() -> int:

    parser = build_argument_parser()

    args = parser.parse_args()

    print_header()

    result = execute_audit(

        repository_root=args.repository,

        compute_checksums=(
            not args.no_checksum
        ),

        recursive=(
            not args.non_recursive
        ),

    )

    write_inventory(

        result.inventory,

        args.output,

    )

    print_summary(result)

    print()

    print(
        "Inventory written to:"
    )

    print(
        args.output.resolve()
    )

    if result.errors:

        return 1

    return 0


if __name__ == "__main__":

    raise SystemExit(
        main()
    )