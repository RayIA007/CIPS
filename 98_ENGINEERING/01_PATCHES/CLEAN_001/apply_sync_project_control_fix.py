#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import shutil
import sys
from pathlib import Path

TARGET_NAME = "sync_project_control.py"
BACKUP_NAME = "sync_project_control.py.bak"

OLD_NORMALIZE_IDENTIFIER = '''def normalize_identifier(value: Any) -> str:
    """
    Normalize an identifier without changing its semantic value.
    """

    return str(value or "").strip()
'''

NEW_NORMALIZE_IDENTIFIER = '''def normalize_identifier(value: Any) -> str:
    """
    Normalize an identifier without discarding valid falsy values such as 0.
    """

    if value is None:
        return ""

    return str(value).strip()
'''

OLD_NORMALIZE_STATE = '''def normalize_state(value: Any) -> str:
    """
    Normalize a Project Control state for deterministic comparison.
    """

    return (
        str(value or "")
        .strip()
        .upper()
        .replace(" ", "_")
        .replace("-", "_")
    )
'''

NEW_NORMALIZE_STATE = '''def normalize_state(value: Any) -> str:
    """
    Normalize a state without discarding valid falsy values such as 0.
    """

    if value is None:
        return ""

    return (
        str(value)
        .strip()
        .upper()
        .replace(" ", "_")
        .replace("-", "_")
    )
'''


def main() -> int:
    script_dir = Path(__file__).resolve().parent
    target = script_dir / TARGET_NAME
    backup = script_dir / BACKUP_NAME

    if not target.is_file():
        print(f"ERROR: File not found: {target}", file=sys.stderr)
        return 2

    text = target.read_text(encoding="utf-8")

    identifier_count = text.count(OLD_NORMALIZE_IDENTIFIER)
    state_count = text.count(OLD_NORMALIZE_STATE)

    if identifier_count != 1:
        print(
            "ERROR: Expected exactly one original normalize_identifier() "
            f"block, found {identifier_count}.",
            file=sys.stderr,
        )
        return 3

    if state_count != 1:
        print(
            "ERROR: Expected exactly one original normalize_state() "
            f"block, found {state_count}.",
            file=sys.stderr,
        )
        return 4

    if backup.exists():
        index = 1
        while True:
            candidate = script_dir / f"{BACKUP_NAME}.{index}"
            if not candidate.exists():
                backup = candidate
                break
            index += 1

    shutil.copy2(target, backup)

    updated = text.replace(
        OLD_NORMALIZE_IDENTIFIER,
        NEW_NORMALIZE_IDENTIFIER,
        1,
    ).replace(
        OLD_NORMALIZE_STATE,
        NEW_NORMALIZE_STATE,
        1,
    )

    target.write_text(updated, encoding="utf-8")
    verification = target.read_text(encoding="utf-8")

    if NEW_NORMALIZE_IDENTIFIER not in verification:
        print("ERROR: normalize_identifier() verification failed.", file=sys.stderr)
        return 5

    if NEW_NORMALIZE_STATE not in verification:
        print("ERROR: normalize_state() verification failed.", file=sys.stderr)
        return 6

    print("PATCH APPLIED")
    print(f"Updated : {target}")
    print(f"Backup  : {backup}")
    print()
    print("Corrections:")
    print("- normalize_identifier() now preserves numeric 0.")
    print("- normalize_state() now preserves valid falsy values.")
    print("- No YAML files were modified.")
    print()
    print("Next command:")
    print("python -B sync_project_control.py")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())