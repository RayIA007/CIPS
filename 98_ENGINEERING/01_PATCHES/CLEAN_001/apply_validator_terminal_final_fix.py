#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import ast
import shutil
import sys
from datetime import datetime
from pathlib import Path


TARGET_NAME = "validate_project_control.py"

OLD_BLOCK = '''    terminal_codes = {
        "PCV-CTL-DEPENDENCY-STATE-MISSING",
        "PCV-CTL-DELIVERABLE-ID-MISSING",
        "PCV-CTL-MANIFEST-STATUS-MISSING",
    }
'''

NEW_BLOCK = '''    terminal_codes = {
        "PCV-CTL-DEPENDENCY-STATE-MISSING",
        "PCV-CTL-DELIVERABLE-ID-MISSING",
        "PCV-CTL-MANIFEST-STATUS-MISSING",
        "PCV-CTL-DELIVERABLE-NOT-IN-GRAPH",
        "PCV-CTL-NEXT-NOT-ORDERED",
    }
'''


def syntax_check(text: str, filename: str) -> None:
    ast.parse(text, filename=filename)


def main() -> int:
    script_directory = Path(__file__).resolve().parent
    target = script_directory / TARGET_NAME

    if not target.is_file():
        print(f"ERROR: File not found: {target}", file=sys.stderr)
        return 2

    original = target.read_text(encoding="utf-8")

    old_count = original.count(OLD_BLOCK)
    new_count = original.count(NEW_BLOCK)

    if new_count == 1 and old_count == 0:
        print("NO CHANGES REQUIRED")
        print("The final end-of-graph compatibility fix is already installed.")
        return 0

    if old_count != 1:
        print(
            "ERROR: Expected exactly one existing terminal_codes block; "
            f"found {old_count}.",
            file=sys.stderr,
        )
        return 3

    updated = original.replace(OLD_BLOCK, NEW_BLOCK, 1)

    try:
        syntax_check(updated, str(target))
    except SyntaxError as error:
        print("PATCH NOT APPLIED", file=sys.stderr)
        print(f"Syntax verification failed: {error}", file=sys.stderr)
        return 4

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = target.with_name(
        f"{target.name}.bak_terminal_fix_{timestamp}"
    )

    try:
        shutil.copy2(target, backup)
        target.write_text(updated, encoding="utf-8")
        verification = target.read_text(encoding="utf-8")

        syntax_check(verification, str(target))

        if verification.count(NEW_BLOCK) != 1:
            raise RuntimeError(
                "The updated terminal compatibility block was not verified."
            )

    except Exception as error:
        if backup.is_file():
            shutil.copy2(backup, target)

        print("PATCH ROLLED BACK", file=sys.stderr)
        print(f"Reason: {error}", file=sys.stderr)
        return 5

    print("PATCH APPLIED")
    print(f"Updated : {target}")
    print(f"Backup  : {backup}")
    print()
    print("Legacy terminal findings now normalized:")
    print("- PCV-CTL-DELIVERABLE-NOT-IN-GRAPH")
    print("- PCV-CTL-NEXT-NOT-ORDERED")
    print()
    print("The fix applies only after the validator confirms")
    print("that the current deliverable is the final graph node.")
    print()
    print("No YAML files were modified.")
    print()
    print("Next command:")
    print("python -B validate_project_control.py --verbose")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())