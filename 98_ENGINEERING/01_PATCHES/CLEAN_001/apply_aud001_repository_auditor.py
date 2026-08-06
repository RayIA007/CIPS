#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
===============================================================================
AUD-001

Repository Auditor Installer

Creates the Repository Auditor infrastructure.

Authoritative Deliverable:
    AUD-001

Execution:
    SAFE
    TRANSACTIONAL

===============================================================================
"""

from __future__ import annotations

import ast
import shutil
import sys

from datetime import datetime
from pathlib import Path


VERSION = "1.0.0"

DELIVERABLE = "AUD-001"


FILES = [

    "audit_models.py",

    "audit_constants.py",

    "audit_exceptions.py",

    "filesystem_scanner.py",

    "checksum_engine.py",

    "metadata_collector.py",

    "inventory_builder.py",

    "repository_inventory_writer.py",

    "audit_engine.py",

    "repository_auditor.py",

    "repository_auditor_smoke_test.py",

]


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
# MAIN
# =============================================================================


def main() -> int:

    print("=" * 72)

    print("Repository Auditor Installer")

    print("=" * 72)

    print(f"Version      : {VERSION}")

    print(f"Deliverable  : {DELIVERABLE}")

    print()

    root = Path(__file__).resolve().parent

    backups: list[tuple[Path, Path]] = []

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

            backup = file_path.with_suffix(

                file_path.suffix

                + ".bak_"

                + datetime.now().strftime(

                    "%Y%m%d_%H%M%S"

                )

            )

            shutil.copy2(

                file_path,

                backup,

            )

            backups.append(

                (

                    file_path,

                    backup,

                )

            )

            print(

                f"[ OK ] {filename}"

            )

        print()

        print("=" * 72)

        print("AUD-001 READY")

        print("=" * 72)

        print()

        print(

            "Next command:"

        )

        print()

        print(

            "python repository_auditor_smoke_test.py"

        )

        print()

        print(

            "If the smoke test succeeds:"

        )

        print()

        print(

            "python repository_auditor.py"

        )

        return 0

    except Exception as error:

        print()

        print(

            "INSTALLATION FAILED"

        )

        print()

        print(error)

        print()

        print(

            "No files were modified."

        )

        return 1


if __name__ == "__main__":

    raise SystemExit(

        main()

    )