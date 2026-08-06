#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
===============================================================================
CLEAN-002 v2
Documentation and Build Artifact Separation

File:
    separate_08_scripts_documentation_v2.py

Purpose:
    Move the reviewed documentation from 08_SCRIPTS into the existing
    canonical documentation root:

        C:\\ConsejoIA_V5\\00_DOCUMENTACION

    Documentation is organized by sprint because the reviewed files describe
    independent deliverables rather than consolidated replacements.

    The three unreferenced Research Director builder fragments are moved to:

        C:\\ConsejoIA_V5\\98_ENGINEERING\\03_BUILD_ARTIFACTS\\RESEARCH_DIRECTOR

Execution:
    DRY RUN by default.
    Use --apply to perform the move.

Safety:
    - No file contents are modified.
    - All moves pass through a transactional quarantine.
    - Project Control validation is executed.
    - Repository Audit System validation is executed.
    - Repository Audit System integration is executed.
    - Every move is rolled back if any validation fails.

===============================================================================
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


VERSION = "2.0.0"
DELIVERABLE = "CLEAN-002"

SCRIPT_DIRECTORY = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIRECTORY.parent

DOCUMENTATION_ROOT = (
    PROJECT_ROOT
    / "00_DOCUMENTACION"
    / "10_SPRINTS"
)

BUILD_ARTIFACT_ROOT = (
    PROJECT_ROOT
    / "98_ENGINEERING"
    / "03_BUILD_ARTIFACTS"
    / "RESEARCH_DIRECTOR"
)

QUARANTINE_ROOT = (
    PROJECT_ROOT
    / "98_ENGINEERING"
    / "99_QUARANTINE"
)

REPORT_PATH = (
    PROJECT_ROOT
    / "12_PRODUCTION_SYSTEM"
    / "99_PROJECT_CONTROL"
    / "CLEAN_002_EXECUTION_REPORT.json"
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


SPRINT_DOCUMENTATION = {
    "SPRINT_2A": (
        ("README.md", "README.md"),
        ("CHANGELOG.md", "CHANGELOG.md"),
        ("MANIFIESTO.md", "MANIFIESTO.md"),
        ("INSTALACION.md", "INSTALACION.md"),
    ),
    "SPRINT_2B": (
        ("README_SPRINT2B.md", "README.md"),
        ("CHANGELOG_SPRINT2B.md", "CHANGELOG.md"),
        ("MANIFIESTO_SPRINT2B.md", "MANIFIESTO.md"),
    ),
    "SPRINT_2C": (
        ("README_SPRINT2C.md", "README.md"),
        ("CHANGELOG_SPRINT2C.md", "CHANGELOG.md"),
        ("MANIFIESTO_SPRINT2C.md", "MANIFIESTO.md"),
        ("INSTALACION_SPRINT2C.md", "INSTALACION.md"),
    ),
    "SPRINT_3": (
        ("README_SPRINT3.md", "README.md"),
        ("CHANGELOG_SPRINT3.md", "CHANGELOG.md"),
        ("MANIFIESTO_SPRINT3.md", "MANIFIESTO.md"),
        ("INSTALACION_SPRINT3.md", "INSTALACION.md"),
    ),
    "SPRINT_4A": (
        ("README_SPRINT4A.md", "README.md"),
        ("CHANGELOG_SPRINT4A.md", "CHANGELOG.md"),
        ("MANIFIESTO_SPRINT4A.md", "MANIFIESTO.md"),
        ("INSTALACION_SPRINT4A.md", "INSTALACION.md"),
    ),
    "SPRINT_4B1": (
        ("README_SPRINT4B1.md", "README.md"),
        ("CHANGELOG_SPRINT4B1.md", "CHANGELOG.md"),
        ("MANIFIESTO_SPRINT4B1.md", "MANIFIESTO.md"),
        ("INSTALACION_SPRINT4B1.md", "INSTALACION.md"),
    ),
}

BUILD_ARTIFACTS = (
    "research_director_prompt_builder_part1.py",
    "research_director_prompt_builder_part2.py",
    "research_director_prompt_builder_part3.py",
)


@dataclass(frozen=True, slots=True)
class MoveOperation:
    source: Path
    destination: Path
    category: str


@dataclass(slots=True)
class QuarantinedMove:
    operation: MoveOperation
    quarantine_path: Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Move reviewed sprint documentation into 00_DOCUMENTACION "
            "and archive Research Director build fragments."
        )
    )

    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply the separation transaction.",
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print complete validator output.",
    )

    return parser


def build_operations() -> list[MoveOperation]:
    operations: list[MoveOperation] = []

    for sprint, documents in SPRINT_DOCUMENTATION.items():
        sprint_directory = (
            DOCUMENTATION_ROOT
            / sprint
        )

        for source_name, destination_name in documents:
            operations.append(
                MoveOperation(
                    source=SCRIPT_DIRECTORY / source_name,
                    destination=(
                        sprint_directory
                        / destination_name
                    ),
                    category=f"DOCUMENTATION/{sprint}",
                )
            )

    for filename in BUILD_ARTIFACTS:
        operations.append(
            MoveOperation(
                source=SCRIPT_DIRECTORY / filename,
                destination=(
                    BUILD_ARTIFACT_ROOT
                    / filename
                ),
                category="BUILD_ARTIFACT/RESEARCH_DIRECTOR",
            )
        )

    return operations


def collision_safe_destination(
    destination: Path,
) -> Path:
    if not destination.exists():
        return destination

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    return destination.with_name(
        destination.name
        + f".archived_{timestamp}"
    )


def print_operations(
    operations: list[MoveOperation],
) -> None:
    print("=" * 78)
    print("CLEAN-002 v2 — Documentation and Build Artifact Separation")
    print("=" * 78)
    print(f"Documentation root : {DOCUMENTATION_ROOT}")
    print(f"Candidates         : {len(operations)}")
    print("=" * 78)

    for index, operation in enumerate(
        operations,
        start=1,
    ):
        print(
            f"{index:03d}. {operation.category:<36} "
            f"{operation.source.name}"
        )
        print(
            f"     -> {operation.destination}"
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
    for path in (
        PROJECT_CONTROL_VALIDATOR,
        RAS_VALIDATOR,
        RAS_INTEGRATION_TEST,
    ):
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
            str(PROJECT_CONTROL_VALIDATOR),
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
            str(RAS_VALIDATOR),
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
            str(RAS_INTEGRATION_TEST),
        ],
        label="RAS integration test",
        verbose=verbose,
    )

    print("RAS integration : PASS")


def quarantine_operations(
    operations: list[MoveOperation],
    quarantine_directory: Path,
) -> list[QuarantinedMove]:
    quarantined: list[QuarantinedMove] = []

    quarantine_directory.mkdir(
        parents=True,
        exist_ok=False,
    )

    try:
        for index, operation in enumerate(
            operations,
            start=1,
        ):
            if not operation.source.is_file():
                raise FileNotFoundError(
                    f"Required source file is missing: "
                    f"{operation.source}"
                )

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
                QuarantinedMove(
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
    quarantined: list[QuarantinedMove],
) -> None:
    for item in reversed(
        quarantined
    ):
        if not item.quarantine_path.exists():
            continue

        source = item.operation.source

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
            str(item.quarantine_path),
            str(source),
        )


def commit_moves(
    quarantined: list[QuarantinedMove],
) -> list[dict[str, str]]:
    committed: list[dict[str, str]] = []
    moved: list[tuple[Path, Path]] = []

    try:
        for item in quarantined:
            destination = collision_safe_destination(
                item.operation.destination
            )

            destination.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            shutil.move(
                str(item.quarantine_path),
                str(destination),
            )

            moved.append(
                (
                    destination,
                    item.operation.source,
                )
            )

            committed.append(
                {
                    "source": str(
                        item.operation.source
                    ),
                    "destination": str(
                        destination
                    ),
                    "category": (
                        item.operation.category
                    ),
                }
            )

    except Exception:
        for destination, original in reversed(
            moved
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
        key=lambda path: len(path.parts),
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
    committed: list[dict[str, str]],
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
            "source_directory": str(
                SCRIPT_DIRECTORY
            ),
            "documentation_root": str(
                DOCUMENTATION_ROOT
            ),
            "build_artifact_root": str(
                BUILD_ARTIFACT_ROOT
            ),
            "files_moved": len(committed),
            "files_deleted": 0,
            "file_contents_modified": 0,
        },
        "moves": committed,
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

    REPORT_PATH.write_text(
        json.dumps(
            report,
            indent=4,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )


def main() -> int:
    args = build_parser().parse_args()

    print("=" * 78)
    print("CLEAN-002 v2 Documentation and Build Artifact Separation")
    print("=" * 78)
    print(f"Version : {VERSION}")
    print(f"Mode    : {'APPLY' if args.apply else 'DRY RUN'}")
    print("=" * 78)

    operations = build_operations()

    print_operations(
        operations
    )

    missing = [
        operation.source
        for operation in operations
        if not operation.source.is_file()
    ]

    if missing:
        print()
        print(
            "SEPARATION BLOCKED",
            file=sys.stderr,
        )

        for path in missing:
            print(
                f"Missing: {path}",
                file=sys.stderr,
            )

        return 2

    if not args.apply:
        print()
        print("DRY RUN COMPLETED")
        print("No files were moved or modified.")
        print()
        print("Apply with:")
        print(
            "python -B "
            "separate_08_scripts_documentation_v2.py "
            "--apply --verbose"
        )
        return 0

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    quarantine_directory = (
        QUARANTINE_ROOT
        / f"CLEAN_002_{timestamp}"
    )

    quarantined: list[
        QuarantinedMove
    ] = []

    try:
        print()
        print("Quarantining reviewed files...")
        print("-" * 78)

        quarantined = quarantine_operations(
            operations,
            quarantine_directory,
        )

        validate_repository(
            verbose=args.verbose,
        )

        print()
        print("Committing separation...")
        print("-" * 78)

        committed = commit_moves(
            quarantined
        )

        remove_empty_quarantine(
            quarantine_directory
        )

        write_report(
            committed
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
                f"ROLLBACK ERROR: {rollback_error}",
                file=sys.stderr,
            )

        print()
        print(
            "SEPARATION ROLLED BACK",
            file=sys.stderr,
        )
        print(
            f"Reason: {error}",
            file=sys.stderr,
        )
        return 3

    documentation_count = sum(
        1
        for item in committed
        if item["category"].startswith(
            "DOCUMENTATION/"
        )
    )

    build_artifact_count = (
        len(committed)
        - documentation_count
    )

    print()
    print("=" * 78)
    print("SEPARATION COMPLETED")
    print("=" * 78)
    print(
        "Documentation moved : "
        f"{documentation_count}"
    )
    print(
        "Build artifacts moved: "
        f"{build_artifact_count}"
    )
    print("Files deleted        : 0")
    print("Contents modified    : 0")
    print("Project Control      : PASS")
    print("RAS validator        : PASS")
    print("RAS integration      : PASS")
    print(f"Report               : {REPORT_PATH}")
    print("=" * 78)

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )