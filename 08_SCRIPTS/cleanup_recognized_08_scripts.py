#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
===============================================================================
CLEAN-001
Recognized 08_SCRIPTS Cleanup Executor

File:
    cleanup_recognized_08_scripts.py

Purpose:
    Clean only items already classified by
    CLEAN_001_08_SCRIPTS_PLAN.json as:

        ARCHIVE
        DELETE_CANDIDATE

The executor never touches REVIEW_REQUIRED or KEEP items.

Execution:
    DRY RUN by default.
    Use --apply to perform the cleanup.

Transactional strategy:
    1. Load and validate the authoritative cleanup plan.
    2. Move all selected items into a temporary quarantine.
    3. Run Project Control validation.
    4. Run Repository Audit System validation.
    5. Run Repository Audit System integration.
    6. Commit:
       - Engineering files -> 98_ENGINEERING/01_PATCHES/CLEAN_001
       - Backups          -> 98_ENGINEERING/02_BACKUPS/08_SCRIPTS
       - Cache/temporary  -> permanently removed
    7. Roll back every quarantined item if validation or commit fails.

No KEEP or REVIEW_REQUIRED item is modified.

===============================================================================
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


VERSION = "1.0.0"
DELIVERABLE = "CLEAN-001"

SCRIPT_DIRECTORY = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIRECTORY.parent

PROJECT_CONTROL_DIRECTORY = (
    PROJECT_ROOT
    / "12_PRODUCTION_SYSTEM"
    / "99_PROJECT_CONTROL"
)

PLAN_PATH = (
    PROJECT_CONTROL_DIRECTORY
    / "CLEAN_001_08_SCRIPTS_PLAN.json"
)

ENGINEERING_ARCHIVE = (
    PROJECT_ROOT
    / "98_ENGINEERING"
    / "01_PATCHES"
    / "CLEAN_001"
)

BACKUP_ARCHIVE = (
    PROJECT_ROOT
    / "98_ENGINEERING"
    / "02_BACKUPS"
    / "08_SCRIPTS"
)

QUARANTINE_ROOT = (
    PROJECT_ROOT
    / "98_ENGINEERING"
    / "99_QUARANTINE"
)

REPORT_PATH = (
    PROJECT_CONTROL_DIRECTORY
    / "CLEAN_001_EXECUTION_REPORT.json"
)

PROJECT_CONTROL_VALIDATOR = (
    SCRIPT_DIRECTORY
    / "validate_project_control.py"
)

RAS_VALIDATOR = (
    SCRIPT_DIRECTORY
    / "validate_repository_audit_system.py"
)

RAS_INTEGRATION_TEST = (
    SCRIPT_DIRECTORY
    / "repository_audit_system_integration_test.py"
)


@dataclass(frozen=True, slots=True)
class PlannedOperation:
    source: Path
    relative_path: Path
    category: str
    action: str
    destination: Path | None
    reason: str


@dataclass(slots=True)
class QuarantinedItem:
    operation: PlannedOperation
    quarantine_path: Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Clean only recognized ARCHIVE and "
            "DELETE_CANDIDATE items from 08_SCRIPTS."
        )
    )

    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply the cleanup transaction.",
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print complete validator output.",
    )

    return parser


def load_plan() -> dict[str, Any]:
    if not PLAN_PATH.is_file():
        raise FileNotFoundError(
            f"Cleanup plan not found: {PLAN_PATH}"
        )

    payload = json.loads(
        PLAN_PATH.read_text(
            encoding="utf-8"
        )
    )

    safety = payload.get(
        "safety",
        {},
    )

    if (
        safety.get("unknown_policy")
        != "REVIEW_REQUIRED"
    ):
        raise RuntimeError(
            "Cleanup plan does not preserve unknown items."
        )

    if Path(
        payload.get(
            "root",
            "",
        )
    ).resolve() != SCRIPT_DIRECTORY.resolve():
        raise RuntimeError(
            "Cleanup plan root does not match 08_SCRIPTS."
        )

    records = payload.get("records")

    if not isinstance(records, list):
        raise RuntimeError(
            "Cleanup plan records are invalid."
        )

    return payload


def collision_safe_destination(
    destination: Path,
) -> Path:
    if not destination.exists():
        return destination

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    if destination.is_dir():
        return destination.with_name(
            destination.name
            + f"_archived_{timestamp}"
        )

    return destination.with_name(
        destination.name
        + f".archived_{timestamp}"
    )


def build_operations(
    plan: dict[str, Any],
) -> list[PlannedOperation]:
    operations: list[PlannedOperation] = []

    for record in plan["records"]:
        action = str(
            record.get(
                "proposed_action",
                "",
            )
        )

        if action not in {
            "ARCHIVE",
            "DELETE_CANDIDATE",
        }:
            continue

        category = str(
            record.get(
                "category",
                "",
            )
        )

        if category not in {
            "ENGINEERING",
            "BACKUP",
            "CACHE",
            "TEMPORARY",
        }:
            raise RuntimeError(
                "Unsafe category selected for cleanup: "
                f"{category!r}"
            )

        relative_path = Path(
            str(
                record.get(
                    "relative_path",
                    "",
                )
            )
        )

        source = (
            PROJECT_ROOT
            / relative_path
        ).resolve()

        try:
            source.relative_to(
                SCRIPT_DIRECTORY.resolve()
            )
        except ValueError as error:
            raise RuntimeError(
                "Cleanup candidate is outside 08_SCRIPTS: "
                f"{source}"
            ) from error

        if category == "ENGINEERING":
            destination = (
                ENGINEERING_ARCHIVE
                / source.name
            )
        elif category == "BACKUP":
            destination = (
                BACKUP_ARCHIVE
                / source.name
            )
        else:
            destination = None

        operations.append(
            PlannedOperation(
                source=source,
                relative_path=relative_path,
                category=category,
                action=action,
                destination=destination,
                reason=str(
                    record.get(
                        "reason",
                        "",
                    )
                ),
            )
        )

    operations.sort(
        key=lambda item: str(
            item.relative_path
        ).lower()
    )

    return operations


def print_plan(
    operations: list[PlannedOperation],
) -> None:
    print("=" * 78)
    print("CLEAN-001 — Recognized 08_SCRIPTS Cleanup")
    print("=" * 78)
    print(f"Plan        : {PLAN_PATH}")
    print(f"Candidates  : {len(operations)}")
    print("=" * 78)

    for index, operation in enumerate(
        operations,
        start=1,
    ):
        print(
            f"{index:03d}. "
            f"{operation.action:<16} "
            f"{operation.category:<12} "
            f"{operation.source.name}"
        )

        if operation.destination is not None:
            print(
                f"     Destination: "
                f"{operation.destination}"
            )
        else:
            print(
                "     Destination: "
                "DELETE AFTER VALIDATION"
            )


def run_command(
    command: list[str],
    *,
    label: str,
    verbose: bool,
) -> None:
    completed = subprocess.run(
        command,
        cwd=str(SCRIPT_DIRECTORY),
        text=True,
        capture_output=True,
        check=False,
    )

    if verbose:
        if completed.stdout:
            print(
                completed.stdout,
                end=(
                    ""
                    if completed.stdout.endswith("\n")
                    else "\n"
                ),
            )

        if completed.stderr:
            print(
                completed.stderr,
                file=sys.stderr,
                end=(
                    ""
                    if completed.stderr.endswith("\n")
                    else "\n"
                ),
            )

    if completed.returncode != 0:
        output = (
            completed.stdout
            + completed.stderr
        ).strip()

        raise RuntimeError(
            f"{label} failed with exit code "
            f"{completed.returncode}. "
            f"Output: {output[-2000:]}"
        )


def validate_repository(
    *,
    verbose: bool,
) -> None:
    required = (
        PROJECT_CONTROL_VALIDATOR,
        RAS_VALIDATOR,
        RAS_INTEGRATION_TEST,
    )

    for path in required:
        if not path.is_file():
            raise FileNotFoundError(
                f"Required validator is missing: {path}"
            )

    print()
    print("[1/3] Project Control validation")
    print("-" * 78)

    run_command(
        [
            sys.executable,
            "-B",
            str(
                PROJECT_CONTROL_VALIDATOR
            ),
        ],
        label="Project Control validator",
        verbose=verbose,
    )

    print("Project Control : PASS")

    print()
    print("[2/3] Repository Audit System validation")
    print("-" * 78)

    run_command(
        [
            sys.executable,
            "-B",
            str(
                RAS_VALIDATOR
            ),
            "--strict",
        ],
        label="RAS validator",
        verbose=verbose,
    )

    print("RAS validator   : PASS")

    print()
    print("[3/3] Repository Audit System integration")
    print("-" * 78)

    run_command(
        [
            sys.executable,
            "-B",
            str(
                RAS_INTEGRATION_TEST
            ),
        ],
        label="RAS integration test",
        verbose=verbose,
    )

    print("RAS integration : PASS")


def quarantine_operations(
    operations: list[PlannedOperation],
    quarantine_directory: Path,
) -> list[QuarantinedItem]:
    quarantined: list[QuarantinedItem] = []

    quarantine_directory.mkdir(
        parents=True,
        exist_ok=False,
    )

    try:
        for index, operation in enumerate(
            operations,
            start=1,
        ):
            if not operation.source.exists():
                print(
                    "[ SKIP ] Missing candidate: "
                    f"{operation.source}"
                )
                continue

            quarantine_path = (
                quarantine_directory
                / f"{index:04d}"
                / operation.source.name
            )

            quarantine_path.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            shutil.move(
                str(operation.source),
                str(quarantine_path),
            )

            quarantined.append(
                QuarantinedItem(
                    operation=operation,
                    quarantine_path=quarantine_path,
                )
            )

            print(
                f"[ HOLD ] {operation.source.name}"
            )

    except Exception:
        rollback_quarantine(
            quarantined
        )
        raise

    return quarantined


def rollback_quarantine(
    quarantined: list[QuarantinedItem],
) -> None:
    for item in reversed(
        quarantined
    ):
        source = item.operation.source
        held = item.quarantine_path

        if not held.exists():
            continue

        source.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        if source.exists():
            raise RuntimeError(
                "Rollback destination already exists: "
                f"{source}"
            )

        shutil.move(
            str(held),
            str(source),
        )


def commit_quarantine(
    quarantined: list[QuarantinedItem],
) -> dict[str, list[str]]:
    committed = {
        "archived_engineering": [],
        "archived_backups": [],
        "deleted_cache_or_temporary": [],
    }

    committed_moves: list[
        tuple[Path, Path]
    ] = []

    try:
        ENGINEERING_ARCHIVE.mkdir(
            parents=True,
            exist_ok=True,
        )
        BACKUP_ARCHIVE.mkdir(
            parents=True,
            exist_ok=True,
        )

        for item in quarantined:
            operation = item.operation
            held = item.quarantine_path

            if not held.exists():
                continue

            if operation.destination is None:
                if held.is_dir():
                    shutil.rmtree(
                        held
                    )
                else:
                    held.unlink()

                committed[
                    "deleted_cache_or_temporary"
                ].append(
                    str(
                        operation.relative_path
                    )
                )
                continue

            destination = collision_safe_destination(
                operation.destination
            )

            destination.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            shutil.move(
                str(held),
                str(destination),
            )

            committed_moves.append(
                (
                    destination,
                    operation.source,
                )
            )

            key = (
                "archived_engineering"
                if operation.category
                == "ENGINEERING"
                else "archived_backups"
            )

            committed[key].append(
                str(destination)
            )

    except Exception:
        for destination, original in reversed(
            committed_moves
        ):
            if destination.exists():
                original.parent.mkdir(
                    parents=True,
                    exist_ok=True,
                )
                shutil.move(
                    str(destination),
                    str(original),
                )

        rollback_quarantine(
            [
                item
                for item in quarantined
                if item.quarantine_path.exists()
            ]
        )
        raise

    return committed


def remove_empty_quarantine(
    quarantine_directory: Path,
) -> None:
    if not quarantine_directory.exists():
        return

    for directory in sorted(
        (
            path
            for path in quarantine_directory.rglob("*")
            if path.is_dir()
        ),
        key=lambda path: len(
            path.parts
        ),
        reverse=True,
    ):
        try:
            directory.rmdir()
        except OSError:
            pass

    try:
        quarantine_directory.rmdir()
    except OSError:
        pass


def write_report(
    *,
    operations: list[PlannedOperation],
    committed: dict[str, list[str]],
) -> None:
    report = {
        "document": {
            "name": REPORT_PATH.name,
            "version": VERSION,
            "deliverable": DELIVERABLE,
            "status": "COMPLETED",
            "generated_at": datetime.now(
                timezone.utc
            ).isoformat(),
        },
        "scope": {
            "root": str(
                SCRIPT_DIRECTORY
            ),
            "source_plan": str(
                PLAN_PATH
            ),
            "recognized_candidates": len(
                operations
            ),
            "keep_items_modified": 0,
            "review_items_modified": 0,
        },
        "result": committed,
        "validation": {
            "project_control": "PASS",
            "ras_validator": "PASS",
            "ras_integration": "PASS",
        },
    }

    REPORT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary = REPORT_PATH.with_suffix(
        REPORT_PATH.suffix
        + ".tmp"
    )

    temporary.write_text(
        json.dumps(
            report,
            indent=4,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    json.loads(
        temporary.read_text(
            encoding="utf-8"
        )
    )

    os.replace(
        temporary,
        REPORT_PATH,
    )


def main() -> int:
    args = build_parser().parse_args()

    print("=" * 78)
    print("CLEAN-001 Recognized 08_SCRIPTS Cleanup Executor")
    print("=" * 78)
    print(f"Version : {VERSION}")
    print(f"Mode    : {'APPLY' if args.apply else 'DRY RUN'}")
    print("=" * 78)

    try:
        plan = load_plan()
        operations = build_operations(
            plan
        )
    except Exception as error:
        print(
            f"PLAN ERROR: {error}",
            file=sys.stderr,
        )
        return 2

    print_plan(
        operations
    )

    if not operations:
        print()
        print(
            "No recognized cleanup candidates remain."
        )
        return 0

    if not args.apply:
        print()
        print("DRY RUN COMPLETED")
        print("No files were moved or deleted.")
        print()
        print("Apply with:")
        print(
            "python -B "
            "cleanup_recognized_08_scripts.py "
            "--apply --verbose"
        )
        return 0

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    quarantine_directory = (
        QUARANTINE_ROOT
        / f"CLEAN_001_{timestamp}"
    )

    quarantined: list[
        QuarantinedItem
    ] = []

    try:
        print()
        print("Quarantining recognized candidates...")
        print("-" * 78)

        quarantined = quarantine_operations(
            operations,
            quarantine_directory,
        )

        validate_repository(
            verbose=args.verbose,
        )

        print()
        print("Committing cleanup...")
        print("-" * 78)

        committed = commit_quarantine(
            quarantined
        )

        remove_empty_quarantine(
            quarantine_directory
        )

        write_report(
            operations=operations,
            committed=committed,
        )

    except Exception as error:
        try:
            rollback_quarantine(
                [
                    item
                    for item in quarantined
                    if item.quarantine_path.exists()
                ]
            )
        except Exception as rollback_error:
            print(
                "ROLLBACK ERROR: "
                f"{rollback_error}",
                file=sys.stderr,
            )

        print()
        print(
            "CLEANUP ROLLED BACK",
            file=sys.stderr,
        )
        print(
            f"Reason: {error}",
            file=sys.stderr,
        )
        return 3

    print()
    print("=" * 78)
    print("CLEANUP COMPLETED")
    print("=" * 78)
    print(
        "Engineering archived : "
        f"{len(committed['archived_engineering'])}"
    )
    print(
        "Backups archived     : "
        f"{len(committed['archived_backups'])}"
    )
    print(
        "Caches/temp deleted  : "
        f"{len(committed['deleted_cache_or_temporary'])}"
    )
    print("KEEP items modified   : 0")
    print("REVIEW items modified : 0")
    print("Project Control       : PASS")
    print("RAS validator         : PASS")
    print("RAS integration       : PASS")
    print(f"Report                : {REPORT_PATH}")
    print("=" * 78)

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )