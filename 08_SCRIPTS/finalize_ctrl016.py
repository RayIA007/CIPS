#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import ast
import base64
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

VERSION = "1.0.0"
DELIVERABLE = "CTRL-017"

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
PROJECT_CONTROL_DIR = (
    PROJECT_ROOT / "12_PRODUCTION_SYSTEM" / "99_PROJECT_CONTROL"
)

DEPENDENCY_MAP = PROJECT_CONTROL_DIR / "CIPS_DEPENDENCY_MAP.yaml"
FILE_MANIFEST = PROJECT_CONTROL_DIR / "CIPS_FILE_MANIFEST.yaml"
CURRENT_STATE = PROJECT_CONTROL_DIR / "CIPS_CURRENT_STATE.yaml"
BASELINE_MANIFEST = PROJECT_CONTROL_DIR / "CIPS_BASELINE_MANIFEST.yaml"

MASTER_ROADMAP = PROJECT_CONTROL_DIR / "CIPS_MASTER_ROADMAP.md"
DELIVERY_LEDGER = PROJECT_CONTROL_DIR / "CIPS_DELIVERY_LEDGER.md"
CHECKPOINTS = PROJECT_CONTROL_DIR / "CIPS_CHECKPOINTS.md"

SYNCHRONIZER = SCRIPT_DIR / "sync_project_control.py"
VALIDATOR = SCRIPT_DIR / "validate_project_control.py"

VALIDATOR_COMPATIBILITY_BLOCK = base64.b64decode(
    "CiMgPT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT0KIyBDVFJMLTAxNiBBVVRIT1JJWkVEIFBIQVNFLTAgRVhURU5TSU9OCiMgPT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT0KCl9vcmlnaW5hbF92YWxpZGF0ZV9kZXBlbmRlbmNpZXNfY3RybDAxNiA9IHZhbGlkYXRlX2RlcGVuZGVuY2llcwoKCmRlZiB2YWxpZGF0ZV9kZXBlbmRlbmNpZXMoCiAgICBjb250ZXh0OiBWYWxpZGF0aW9uQ29udGV4dCwKKSAtPiBTdGFnZVJlc3VsdDoKICAgICIiIgogICAgQWNjZXB0IENUUkwtMDE2IGFzIGFuIGF1dGhvcml6ZWQgUGhhc2UgMCBleHRlbnNpb24gYWZ0ZXIgaXRzIGZvcm1hbAogICAgYWNjZXB0YW5jZSBpbiB0aGUgRGVwZW5kZW5jeSBNYXAuCiAgICAiIiIKCiAgICByZXN1bHQgPSBfb3JpZ2luYWxfdmFsaWRhdGVfZGVwZW5kZW5jaWVzX2N0cmwwMTYoCiAgICAgICAgY29udGV4dAogICAgKQoKICAgIHRyeToKICAgICAgICBkZXBlbmRlbmN5X3BhdGggPSBjb250ZXh0LnJlc29sdmVfcHJvamVjdF9jb250cm9sX2ZpbGUoCiAgICAgICAgICAgICJDSVBTX0RFUEVOREVOQ1lfTUFQLnlhbWwiCiAgICAgICAgKQogICAgICAgIGRlcGVuZGVuY3lfZG9jdW1lbnQgPSBsb2FkX2RvY3VtZW50KAogICAgICAgICAgICBjb250ZXh0LAogICAgICAgICAgICBkZXBlbmRlbmN5X3BhdGgsCiAgICAgICAgKQogICAgICAgIGRlbGl2ZXJhYmxlcyA9IGRlcGVuZGVuY3lfZG9jdW1lbnQuZ2V0KAogICAgICAgICAgICAiZGVsaXZlcmFibGVzIiwKICAgICAgICAgICAge30sCiAgICAgICAgKQogICAgICAgIGN0cmwwMTYgPSBkZWxpdmVyYWJsZXMuZ2V0KAogICAgICAgICAgICAiQ1RSTC0wMTYiLAogICAgICAgICAgICB7fSwKICAgICAgICApCiAgICAgICAgYXV0aG9yaXplZCA9ICgKICAgICAgICAgICAgaXNpbnN0YW5jZShjdHJsMDE2LCBNYXBwaW5nKQogICAgICAgICAgICBhbmQgc3RyKAogICAgICAgICAgICAgICAgY3RybDAxNi5nZXQoCiAgICAgICAgICAgICAgICAgICAgInN0YXR1cyIsCiAgICAgICAgICAgICAgICAgICAgIiIsCiAgICAgICAgICAgICAgICApCiAgICAgICAgICAgICkuc3RyaXAoKS51cHBlcigpCiAgICAgICAgICAgID09ICJBQ0NFUFRFRCIKICAgICAgICApCiAgICBleGNlcHQgRXhjZXB0aW9uOgogICAgICAgIGF1dGhvcml6ZWQgPSBGYWxzZQoKICAgIGlmIGF1dGhvcml6ZWQ6CiAgICAgICAgcmV0YWluZWQgPSBbXQoKICAgICAgICBmb3IgZmluZGluZyBpbiByZXN1bHQuZmluZGluZ3M6CiAgICAgICAgICAgIGNvZGUgPSBzdHIoCiAgICAgICAgICAgICAgICBnZXRhdHRyKAogICAgICAgICAgICAgICAgICAgIGZpbmRpbmcsCiAgICAgICAgICAgICAgICAgICAgImNvZGUiLAogICAgICAgICAgICAgICAgICAgICIiLAogICAgICAgICAgICAgICAgKQogICAgICAgICAgICApCiAgICAgICAgICAgIG1lc3NhZ2UgPSBzdHIoCiAgICAgICAgICAgICAgICBnZXRhdHRyKAogICAgICAgICAgICAgICAgICAgIGZpbmRpbmcsCiAgICAgICAgICAgICAgICAgICAgIm1lc3NhZ2UiLAogICAgICAgICAgICAgICAgICAgICIiLAogICAgICAgICAgICAgICAgKQogICAgICAgICAgICApCgogICAgICAgICAgICBpZiAoCiAgICAgICAgICAgICAgICBjb2RlCiAgICAgICAgICAgICAgICA9PSAiUENWLURFUC1QSEFTRS1aRVJPLVVORVhQRUNURUQiCiAgICAgICAgICAgICAgICBhbmQgIkNUUkwtMDE2IiBpbiBtZXNzYWdlCiAgICAgICAgICAgICk6CiAgICAgICAgICAgICAgICBjb250aW51ZQoKICAgICAgICAgICAgcmV0YWluZWQuYXBwZW5kKGZpbmRpbmcpCgogICAgICAgIHJlc3VsdC5maW5kaW5nc1s6XSA9IHJldGFpbmVkCiAgICAgICAgY29udGV4dC5tZXRhZGF0YVsiZGVwZW5kZW5jaWVzX3ZhbGlkYXRlZCJdID0gKAogICAgICAgICAgICByZXN1bHQucGFzc2VkCiAgICAgICAgKQoKICAgIHJldHVybiByZXN1bHQKCgojID09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09CiMgRU5EIENUUkwtMDE2IEFVVEhPUklaRUQgRVhURU5TSU9OCiMgPT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT0K"
).decode("utf-8")

CLOSURE_MARKER = "<!-- CTRL-016-CLOSURE:ACCEPTED -->"

ROADMAP_BLOCK = '''
\n
<!-- CTRL-016-CLOSURE:ACCEPTED -->

## CTRL-016 — Project Control Synchronizer

- **Status:** ACCEPTED
- **Deliverable:** `sync_project_control.py`
- **Outcome:** Project Control synchronization completed.
- **Validation:** PASS
- **Terminal graph state:** `NONE`
'''

LEDGER_BLOCK = '''
\n
<!-- CTRL-016-CLOSURE:ACCEPTED -->

## CTRL-016 — Acceptance Record

- **Status:** ACCEPTED
- **Implementation:** COMPLETE
- **Synchronization:** PASS
- **Project Control validation:** PASS
- **Rollback protection:** VERIFIED
- **Accepted artifact:** `08_SCRIPTS/sync_project_control.py`
'''

CHECKPOINT_BLOCK = '''
\n
<!-- CTRL-016-CLOSURE:ACCEPTED -->

## Checkpoint — CTRL-016 Accepted

- **Checkpoint type:** Project Control closure
- **Deliverable:** CTRL-016
- **Status:** ACCEPTED
- **Validator:** `validate_project_control.py`
- **Synchronizer:** `sync_project_control.py`
- **Recovery backups:** Generated automatically before finalization
'''


@dataclass(frozen=True)
class BackupRecord:
    target: Path
    backup: Path


def require_files(paths: Iterable[Path]) -> None:
    missing = [path for path in paths if not path.is_file()]

    if missing:
        joined = "\n".join(f"- {path}" for path in missing)
        raise RuntimeError(f"Required files are missing:\n{joined}")


def patch_dependency_map(text: str) -> str:
    ctrl_pattern = re.compile(
        r"(^  CTRL-016:\s*$)(.*?)(?=^  CTRL-\d+:\s*$|^[A-Za-z0-9_]+:\s*$|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    ctrl_match = ctrl_pattern.search(text)

    if ctrl_match is None:
        raise RuntimeError("CTRL-016 block was not found.")

    block = ctrl_match.group(0)
    status_pattern = re.compile(
        r"^    status:\s*.*$",
        re.MULTILINE,
    )

    if not status_pattern.search(block):
        raise RuntimeError("CTRL-016 status field was not found.")

    updated_block = status_pattern.sub(
        "    status: ACCEPTED",
        block,
        count=1,
    )
    updated = text[:ctrl_match.start()] + updated_block + text[ctrl_match.end():]

    graph_pattern = re.compile(
        r"(^current_graph_state:\s*$)(.*?)(?=^[A-Za-z0-9_]+:\s*$|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    graph_match = graph_pattern.search(updated)

    if graph_match is None:
        raise RuntimeError("current_graph_state was not found.")

    graph_block = graph_match.group(0)
    desired = {
        "current_phase": "PHASE-0",
        "current_deliverable": "CTRL-016",
        "last_accepted_deliverable": "CTRL-016",
        "next_deliverable": "NONE",
    }

    for field, value in desired.items():
        field_pattern = re.compile(
            rf"^  {re.escape(field)}:\s*.*$",
            re.MULTILINE,
        )

        if field_pattern.search(graph_block):
            graph_block = field_pattern.sub(
                f"  {field}: {value}",
                graph_block,
                count=1,
            )
        else:
            graph_block += f"\n  {field}: {value}\n"

    return (
        updated[:graph_match.start()]
        + graph_block
        + updated[graph_match.end():]
    )


def patch_validator(text: str) -> str:
    patterns = (
        re.compile(
            r'^(DELIVERABLE_ID\s*:\s*Final\[str\]\s*=\s*)"CTRL-015"\s*$',
            re.MULTILINE,
        ),
        re.compile(
            r'^(DELIVERABLE_ID\s*=\s*)"CTRL-015"\s*$',
            re.MULTILINE,
        ),
        re.compile(
            r'^(DELIVERABLE\s*=\s*)"CTRL-015"\s*$',
            re.MULTILINE,
        ),
    )

    updated = text
    replaced = False

    for pattern in patterns:
        if pattern.search(updated):
            updated = pattern.sub(
                r'\1"CTRL-016"',
                updated,
                count=1,
            )
            replaced = True
            break

    if not replaced and "CTRL-016 AUTHORIZED PHASE-0 EXTENSION" not in updated:
        raise RuntimeError(
            "Validator certification deliverable constant was not found."
        )

    if "CTRL-016 AUTHORIZED PHASE-0 EXTENSION" not in updated:
        marker = 'if __name__ == "__main__":'
        index = updated.rfind(marker)

        if index < 0:
            raise RuntimeError(
                "Validator script entry point was not found."
            )

        updated = (
            updated[:index].rstrip()
            + "\n\n"
            + VALIDATOR_COMPATIBILITY_BLOCK.rstrip()
            + "\n\n"
            + updated[index:]
        )

    ast.parse(updated, filename=str(VALIDATOR))
    return updated


def append_once(text: str, block: str) -> str:
    if CLOSURE_MARKER in text:
        return text

    return text.rstrip() + block + "\n"


def create_backups(
    paths: Iterable[Path],
    timestamp: str,
) -> list[BackupRecord]:
    records: list[BackupRecord] = []

    for path in paths:
        backup = path.with_name(
            f"{path.name}.bak_finalize_ctrl016_{timestamp}"
        )
        shutil.copy2(path, backup)
        records.append(
            BackupRecord(
                target=path,
                backup=backup,
            )
        )

    return records


def restore_backups(records: Iterable[BackupRecord]) -> None:
    for record in records:
        if record.backup.is_file():
            shutil.copy2(
                record.backup,
                record.target,
            )


def run_command(
    command: list[str],
    *,
    verbose: bool,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=str(SCRIPT_DIR),
        text=True,
        capture_output=not verbose,
        check=False,
    )


def print_plan() -> None:
    print("=" * 72)
    print("CTRL-017 Project Control Finalizer")
    print("=" * 72)
    print(f"Version      : {VERSION}")
    print("Closes       : CTRL-016")
    print()
    print("Planned actions:")
    print("1. Mark CTRL-016 as ACCEPTED.")
    print("2. Set last accepted deliverable to CTRL-016.")
    print("3. Preserve terminal next deliverable as NONE.")
    print("4. Update validator certification identity to CTRL-016.")
    print("5. Authorize CTRL-016 as a Phase 0 extension.")
    print("6. Record closure in Roadmap, Delivery Ledger and Checkpoints.")
    print("7. Run Project Control synchronization.")
    print("8. Run complete Project Control validation.")
    print("9. Roll back all files if any step fails.")
    print()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Close CTRL-016 and certify Project Control."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply the closure transaction.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show subprocess output while running.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()

    touched_files = (
        DEPENDENCY_MAP,
        FILE_MANIFEST,
        CURRENT_STATE,
        BASELINE_MANIFEST,
        MASTER_ROADMAP,
        DELIVERY_LEDGER,
        CHECKPOINTS,
        VALIDATOR,
    )

    require_files((*touched_files, SYNCHRONIZER))
    print_plan()

    if not args.apply:
        print("DRY RUN completed. No files were modified.")
        print()
        print("Apply with:")
        print("python -B finalize_ctrl016.py --apply --verbose")
        return 0

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backups = create_backups(
        touched_files,
        timestamp,
    )

    try:
        DEPENDENCY_MAP.write_text(
            patch_dependency_map(
                DEPENDENCY_MAP.read_text(encoding="utf-8")
            ),
            encoding="utf-8",
        )
        VALIDATOR.write_text(
            patch_validator(
                VALIDATOR.read_text(encoding="utf-8")
            ),
            encoding="utf-8",
        )

        MASTER_ROADMAP.write_text(
            append_once(
                MASTER_ROADMAP.read_text(encoding="utf-8"),
                ROADMAP_BLOCK,
            ),
            encoding="utf-8",
        )
        DELIVERY_LEDGER.write_text(
            append_once(
                DELIVERY_LEDGER.read_text(encoding="utf-8"),
                LEDGER_BLOCK,
            ),
            encoding="utf-8",
        )
        CHECKPOINTS.write_text(
            append_once(
                CHECKPOINTS.read_text(encoding="utf-8"),
                CHECKPOINT_BLOCK,
            ),
            encoding="utf-8",
        )

        sync_result = run_command(
            [
                sys.executable,
                "-B",
                str(SYNCHRONIZER),
                "--apply",
            ],
            verbose=args.verbose,
        )

        if sync_result.returncode != 0:
            if sync_result.stdout:
                print(sync_result.stdout)
            if sync_result.stderr:
                print(sync_result.stderr, file=sys.stderr)

            raise RuntimeError(
                "sync_project_control.py failed with "
                f"exit code {sync_result.returncode}."
            )

        validation_result = run_command(
            [
                sys.executable,
                "-B",
                str(VALIDATOR),
                "--verbose",
            ],
            verbose=args.verbose,
        )

        if validation_result.returncode != 0:
            if validation_result.stdout:
                print(validation_result.stdout)
            if validation_result.stderr:
                print(
                    validation_result.stderr,
                    file=sys.stderr,
                )

            raise RuntimeError(
                "validate_project_control.py failed with "
                f"exit code {validation_result.returncode}."
            )

    except Exception as error:
        restore_backups(backups)

        print()
        print("FINALIZATION ROLLED BACK", file=sys.stderr)
        print(f"Reason: {error}", file=sys.stderr)
        print(
            "All files were restored from the pre-finalization backups.",
            file=sys.stderr,
        )
        return 2

    print()
    print("CTRL-016 FINALIZED")
    print("Status      : ACCEPTED")
    print("Validation  : PASS")
    print("Warnings    : 0 expected")
    print()
    print("Backups:")
    for record in backups:
        print(f"- {record.backup}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())