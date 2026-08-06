#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Final terminal-state patch for validate_project_control.py

Purpose
-------
Allow last_accepted == current_deliverable only when:

- the current deliverable is the verified final dependency-graph node;
- next_deliverable uses the terminal NONE sentinel; and
- the existing CTRL-016 terminal compatibility layer is active.

The patch:
- creates a timestamped backup;
- changes only validate_project_control.py;
- validates Python syntax before and after writing;
- automatically restores the backup if verification fails;
- modifies no YAML or Markdown files.
"""

from __future__ import annotations

import ast
import shutil
import sys
from datetime import datetime
from pathlib import Path


TARGET_NAME = "validate_project_control.py"

OLD_BLOCK = """    terminal_codes = {
        "PCV-CTL-DEPENDENCY-STATE-MISSING",
        "PCV-CTL-DELIVERABLE-ID-MISSING",
        "PCV-CTL-MANIFEST-STATUS-MISSING",
        "PCV-CTL-DELIVERABLE-NOT-IN-GRAPH",
        "PCV-CTL-NEXT-NOT-ORDERED",
    }
"""

NEW_BLOCK = """    terminal_codes = {
        "PCV-CTL-DEPENDENCY-STATE-MISSING",
        "PCV-CTL-DELIVERABLE-ID-MISSING",
        "PCV-CTL-MANIFEST-STATUS-MISSING",
        "PCV-CTL-DELIVERABLE-NOT-IN-GRAPH",
        "PCV-CTL-NEXT-NOT-ORDERED",
        "PCV-CTL-PREVIOUS-ORDER",
    }
"""


def syntax_check(text: str, filename: str) -> None:
    ast.parse(text, filename=filename)


def main() -> int:
    script_directory = Path(__file__).resolve().parent
    target = script_directory / TARGET_NAME

    if not target.is_file():
        print(f"ERROR: File not found: {target}", file=sys.stderr)
        return 2

    original = target.read_text(encoding="utf-8")

    if original.count(NEW_BLOCK) == 1 and original.count(OLD_BLOCK) == 0:
        print("NO CHANGES REQUIRED")
        print("The terminal previous-order compatibility fix is already installed.")
        return 0

    old_count = original.count(OLD_BLOCK)

    if old_count != 1:
        print(
            "ERROR: Expected exactly one terminal compatibility block; "
            f"found {old_count}.",
            file=sys.stderr,
        )
        return 3

    if "def _is_valid_terminal_execution_state(" not in original:
        print(
            "ERROR: The verified terminal-state compatibility layer "
            "was not found.",
            file=sys.stderr,
        )
        return 4

    updated = original.replace(
        OLD_BLOCK,
        NEW_BLOCK,
        1,
    )

    try:
        syntax_check(updated, str(target))
    except SyntaxError as error:
        print("PATCH NOT APPLIED", file=sys.stderr)
        print(f"Syntax verification failed: {error}", file=sys.stderr)
        return 5

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = target.with_name(
        f"{target.name}.bak_terminal_previous_order_{timestamp}"
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

        if verification.count(
            '"PCV-CTL-PREVIOUS-ORDER"'
        ) < 1:
            raise RuntimeError(
                "PCV-CTL-PREVIOUS-ORDER was not registered."
            )

    except Exception as error:
        if backup.is_file():
            shutil.copy2(backup, target)

        print("PATCH ROLLED BACK", file=sys.stderr)
        print(f"Reason: {error}", file=sys.stderr)
        return 6

    print("PATCH APPLIED")
    print(f"Updated : {target}")
    print(f"Backup  : {backup}")
    print()
    print("Final terminal rule installed:")
    print("- last_accepted may equal current_deliverable")
    print("  only for a verified final dependency-graph node.")
    print("- PCV-CTL-PREVIOUS-ORDER remains active")
    print("  for every non-terminal project state.")
    print("- Python syntax was verified.")
    print()
    print("No YAML or Markdown files were modified.")
    print()
    print("Next safe command:")
    print("python -B finalize_ctrl016.py")
    print()
    print("Then apply:")
    print("python -B finalize_ctrl016.py --apply --verbose")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())