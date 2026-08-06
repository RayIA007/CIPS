#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Automatic patch for CIPS_DEPENDENCY_MAP.yaml

Changes:
- Creates a timestamped backup.
- Sets CTRL-001 through CTRL-015 to ACCEPTED.
- Adds CTRL-016 when it is not registered.
- Sets CTRL-016 to IN_PROGRESS.
- Updates current_graph_state:
    current_phase: PHASE-0
    current_deliverable: CTRL-016
    last_accepted_deliverable: CTRL-015
    next_deliverable: ""
- Preserves the rest of the YAML text.
- Validates the resulting YAML before replacing the original file.
"""

from __future__ import annotations

import re
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Iterable


TARGET_RELATIVE = Path(
    "12_PRODUCTION_SYSTEM/99_PROJECT_CONTROL/CIPS_DEPENDENCY_MAP.yaml"
)


def leading_spaces(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def find_top_level_key(lines: list[str], key: str) -> int:
    pattern = re.compile(rf"^{re.escape(key)}:\s*$")
    matches = [
        index for index, line in enumerate(lines)
        if pattern.match(line.rstrip("\r\n"))
    ]

    if len(matches) != 1:
        raise RuntimeError(
            f"Expected exactly one top-level {key!r} section; found {len(matches)}."
        )

    return matches[0]


def find_section_end(lines: list[str], start_index: int) -> int:
    for index in range(start_index + 1, len(lines)):
        raw = lines[index].rstrip("\r\n")

        if not raw.strip() or raw.lstrip().startswith("#"):
            continue

        if leading_spaces(raw) == 0 and re.match(r"^[A-Za-z0-9_]+:\s*", raw):
            return index

    return len(lines)


def find_mapping_entry(
    lines: list[str],
    section_start: int,
    section_end: int,
    entry_id: str,
) -> tuple[int, int] | None:
    entry_pattern = re.compile(rf"^  {re.escape(entry_id)}:\s*$")

    entry_start = None

    for index in range(section_start + 1, section_end):
        if entry_pattern.match(lines[index].rstrip("\r\n")):
            entry_start = index
            break

    if entry_start is None:
        return None

    entry_end = section_end

    for index in range(entry_start + 1, section_end):
        raw = lines[index].rstrip("\r\n")

        if re.match(r"^  [A-Za-z0-9_-]+:\s*$", raw):
            entry_end = index
            break

    return entry_start, entry_end


def replace_or_insert_scalar(
    block: list[str],
    field: str,
    value: str,
    indentation: str = "    ",
) -> list[str]:
    pattern = re.compile(
        rf"^{re.escape(indentation)}{re.escape(field)}:\s*(.*?)\s*$"
    )

    matches = [
        index for index, line in enumerate(block)
        if pattern.match(line.rstrip("\r\n"))
    ]

    replacement = f"{indentation}{field}: {value}\n"

    if len(matches) > 1:
        raise RuntimeError(
            f"Entry contains duplicate field {field!r}."
        )

    if len(matches) == 1:
        block[matches[0]] = replacement
        return block

    insert_at = 1

    while insert_at < len(block):
        stripped = block[insert_at].strip()

        if stripped and not stripped.startswith("#"):
            break

        insert_at += 1

    block.insert(insert_at, replacement)
    return block


def update_deliverable_status(
    lines: list[str],
    deliverables_start: int,
    deliverables_end: int,
    deliverable_id: str,
    new_status: str,
) -> None:
    location = find_mapping_entry(
        lines,
        deliverables_start,
        deliverables_end,
        deliverable_id,
    )

    if location is None:
        raise RuntimeError(
            f"Required deliverable {deliverable_id} is not registered."
        )

    start, end = location
    block = lines[start:end]
    block = replace_or_insert_scalar(
        block,
        "status",
        new_status,
    )
    lines[start:end] = block


def add_ctrl_016(
    lines: list[str],
    deliverables_start: int,
    deliverables_end: int,
) -> None:
    existing = find_mapping_entry(
        lines,
        deliverables_start,
        deliverables_end,
        "CTRL-016",
    )

    if existing is not None:
        start, end = existing
        block = lines[start:end]
        block = replace_or_insert_scalar(block, "status", "IN_PROGRESS")
        block = replace_or_insert_scalar(block, "phase", "PHASE-0")
        lines[start:end] = block
        return

    ctrl_015 = find_mapping_entry(
        lines,
        deliverables_start,
        deliverables_end,
        "CTRL-015",
    )

    if ctrl_015 is None:
        raise RuntimeError(
            "CTRL-015 was not found; CTRL-016 cannot be inserted safely."
        )

    _, ctrl_015_end = ctrl_015

    new_block = [
        "\n",
        "  CTRL-016:\n",
        "    name: sync_project_control.py\n",
        "    status: IN_PROGRESS\n",
        "    dependencies:\n",
        "      - CTRL-015\n",
        "    phase: PHASE-0\n",
    ]

    lines[ctrl_015_end:ctrl_015_end] = new_block


def update_current_graph_state(lines: list[str]) -> None:
    start = find_top_level_key(lines, "current_graph_state")
    end = find_section_end(lines, start)

    desired = {
        "current_phase": "PHASE-0",
        "current_deliverable": "CTRL-016",
        "last_accepted_deliverable": "CTRL-015",
        'next_deliverable': '""',
    }

    block = lines[start:end]

    for field, value in desired.items():
        block = replace_or_insert_scalar(
            block,
            field,
            value,
            indentation="  ",
        )

    lines[start:end] = block


def validate_yaml(path: Path) -> None:
    try:
        import yaml
    except ImportError as exc:
        raise RuntimeError(
            "PyYAML is required. Install it with: python -m pip install PyYAML"
        ) from exc

    with path.open("r", encoding="utf-8") as stream:
        loaded = yaml.safe_load(stream)

    if not isinstance(loaded, dict):
        raise RuntimeError("Patched YAML root is not a mapping.")

    deliverables = loaded.get("deliverables")

    if not isinstance(deliverables, dict):
        raise RuntimeError("Patched YAML has no valid 'deliverables' mapping.")

    for number in range(1, 16):
        deliverable_id = f"CTRL-{number:03d}"
        record = deliverables.get(deliverable_id)

        if not isinstance(record, dict):
            raise RuntimeError(
                f"{deliverable_id} is missing after patch."
            )

        if str(record.get("status", "")).strip().upper() != "ACCEPTED":
            raise RuntimeError(
                f"{deliverable_id} was not set to ACCEPTED."
            )

    ctrl_016 = deliverables.get("CTRL-016")

    if not isinstance(ctrl_016, dict):
        raise RuntimeError("CTRL-016 is missing after patch.")

    if str(ctrl_016.get("status", "")).strip().upper() != "IN_PROGRESS":
        raise RuntimeError("CTRL-016 was not set to IN_PROGRESS.")

    state = loaded.get("current_graph_state")

    if not isinstance(state, dict):
        raise RuntimeError("current_graph_state is missing after patch.")

    expected = {
        "current_phase": "PHASE-0",
        "current_deliverable": "CTRL-016",
        "last_accepted_deliverable": "CTRL-015",
        "next_deliverable": "",
    }

    for field, value in expected.items():
        actual = state.get(field)

        if actual != value:
            raise RuntimeError(
                f"current_graph_state.{field}: "
                f"expected {value!r}, received {actual!r}."
            )


def main() -> int:
    script_directory = Path(__file__).resolve().parent
    project_root = script_directory.parent
    target = project_root / TARGET_RELATIVE

    if not target.is_file():
        print(f"ERROR: File not found: {target}", file=sys.stderr)
        return 2

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = target.with_name(
        f"{target.name}.bak_{timestamp}"
    )
    temporary = target.with_name(
        f"{target.name}.tmp_{timestamp}"
    )

    original_text = target.read_text(encoding="utf-8")
    lines = original_text.splitlines(keepends=True)

    try:
        deliverables_start = find_top_level_key(lines, "deliverables")
        deliverables_end = find_section_end(lines, deliverables_start)

        for number in range(1, 16):
            update_deliverable_status(
                lines,
                deliverables_start,
                deliverables_end,
                f"CTRL-{number:03d}",
                "ACCEPTED",
            )

            # Recalculate section end because line insertions can shift it.
            deliverables_end = find_section_end(lines, deliverables_start)

        add_ctrl_016(
            lines,
            deliverables_start,
            deliverables_end,
        )

        update_current_graph_state(lines)

        updated_text = "".join(lines)

        if updated_text == original_text:
            print("NO CHANGES REQUIRED")
            print(f"File: {target}")
            return 0

        shutil.copy2(target, backup)
        temporary.write_text(updated_text, encoding="utf-8")
        validate_yaml(temporary)
        temporary.replace(target)

    except Exception as exc:
        if temporary.exists():
            temporary.unlink()

        print("PATCH NOT APPLIED", file=sys.stderr)
        print(f"Reason: {exc}", file=sys.stderr)
        return 3

    print("PATCH APPLIED")
    print(f"Updated : {target}")
    print(f"Backup  : {backup}")
    print()
    print("New Project Control position:")
    print("- CTRL-001 through CTRL-015: ACCEPTED")
    print("- CTRL-016: IN_PROGRESS")
    print("- current_deliverable: CTRL-016")
    print("- last_accepted_deliverable: CTRL-015")
    print("- next_deliverable: empty")
    print()
    print("No other project files were modified.")
    print()
    print("Next command:")
    print("python -B sync_project_control.py")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())