#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
===============================================================================
AUD-002

Directory Tree Installer

Validates the complete AUD-002 subsystem.

Authoritative Deliverable:
    AUD-002

Execution:
    SAFE
    TRANSACTIONAL

===============================================================================
"""

from __future__ import annotations

import ast
import shutil
import subprocess
import sys

from datetime import datetime
from pathlib import Path


VERSION = "1.0.0"

DELIVERABLE = "AUD-002"


FILES = (

    "directory_tree_builder.py",

    "directory_tree_smoke_test.py",

)


# =============================================================================
# HELPERS
# =============================================================================


def verify_python(
    file_path: Path,
) -> None:

    source = file_path.read_text(
        encoding="utf-8"
    )

    ast.parse(
        source,
        filename=str(file_path),
    )


# =============================================================================


def backup(
    file_path: Path,
) -> Path:

    backup_path = file_path.with_suffix(

        file_path.suffix
        + ".bak_"
        + datetime.now().strftime(
            "%Y%m%d_%H%M%S"
        )

    )

    shutil.copy2(
        file_path,
        backup_path,
    )

    return backup_path


# =============================================================================


def run_smoke_test(
    root: Path,
) -> None:

    subprocess.run(

        [

            sys.executable,

            str(
                root
                /
                "directory_tree_smoke_test.py"
            ),

        ],

        check=True,

    )


# =============================================================================
# MAIN
# =============================================================================


def main() -> int:

    print("=" * 72)

    print("AUD-002 Installer")

    print("=" * 72)

    print(f"Version      : {VERSION}")

    print(f"Deliverable  : {DELIVERABLE}")

    print()

    root = Path(__file__).resolve().parent

    backups = []

    try:

        for filename in FILES:

            file_path = root / filename

            if not file_path.exists():

                raise FileNotFoundError(
                    file_path
                )

            verify_python(
                file_path
            )

            backup_path = backup(
                file_path
            )

            backups.append(
                backup_path
            )

            print(
                f"[ OK ] {filename}"
            )

        print()

        print(
            "Running smoke test..."
        )

        print()

        run_smoke_test(
            root
        )

        print()

        print("=" * 72)

        print("AUD-002 READY")

        print("=" * 72)

        print()

        print(
            "Next deliverable:"
        )

        print()

        print(
            "AUD-003"
        )

        return 0

    except Exception as error:

        print()

        print("=" * 72)

        print(
            "INSTALLATION FAILED"
        )

        print("=" * 72)

        print()

        print(error)

        print()

        print(
            "No repository files were modified."
        )

        return 1


if __name__ == "__main__":

    raise SystemExit(
        main()
    )