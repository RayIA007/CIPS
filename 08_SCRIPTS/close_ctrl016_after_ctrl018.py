#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
CTRL-019 — Phase 0 Governance Synchronization and Final Closure

Purpose
-------
Execute the already prepared CTRL-016 finalizer after the CTRL-018
Validator Result Consistency Refactor, then verify that the repository
finishes with:

- FINAL RESULT: PASS
- Critical errors: 0
- Errors: 0
- Warnings: 0

This runner does not edit project files directly. All repository
mutations and rollback protection remain delegated to
finalize_ctrl016.py.

Usage
-----
Safe preflight:
    python -B close_ctrl016_after_ctrl018.py

Apply final closure:
    python -B close_ctrl016_after_ctrl018.py --apply
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path


VERSION = "1.0.0"
DELIVERABLE = "CTRL-019"

SCRIPT_DIR = Path(__file__).resolve().parent
VALIDATOR = SCRIPT_DIR / "validate_project_control.py"
FINALIZER = SCRIPT_DIR / "finalize_ctrl016.py"


def run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=str(SCRIPT_DIR),
        text=True,
        capture_output=True,
        check=False,
    )


def print_output(result: subprocess.CompletedProcess[str]) -> None:
    if result.stdout:
        print(result.stdout, end="" if result.stdout.endswith("\n") else "\n")

    if result.stderr:
        print(
            result.stderr,
            file=sys.stderr,
            end="" if result.stderr.endswith("\n") else "\n",
        )


def extract_final_summary(output: str) -> dict[str, int | str]:
    final_index = output.rfind("FINAL RESULT")

    if final_index < 0:
        raise RuntimeError(
            "Validator output does not contain a FINAL RESULT section."
        )

    final_text = output[final_index:]

    def extract_text(label: str) -> str:
        match = re.search(
            rf"^{re.escape(label)}\s*:\s*(.+?)\s*$",
            final_text,
            flags=re.MULTILINE,
        )

        if match is None:
            raise RuntimeError(
                f"Validator FINAL RESULT is missing {label!r}."
            )

        return match.group(1).strip()

    def extract_int(label: str) -> int:
        raw_value = extract_text(label)

        try:
            return int(raw_value)
        except ValueError as error:
            raise RuntimeError(
                f"Validator value {label!r} is not an integer: "
                f"{raw_value!r}."
            ) from error

    return {
        "status": extract_text("Status"),
        "critical_errors": extract_int("Critical errors"),
        "errors": extract_int("Errors"),
        "warnings": extract_int("Warnings"),
    }


def assert_clean_pass(
    result: subprocess.CompletedProcess[str],
) -> None:
    summary = extract_final_summary(
        result.stdout + result.stderr
    )

    problems: list[str] = []

    if result.returncode != 0:
        problems.append(
            f"validator exit code is {result.returncode}, expected 0"
        )

    if summary["status"] != "PASS":
        problems.append(
            f"status is {summary['status']!r}, expected 'PASS'"
        )

    for field in (
        "critical_errors",
        "errors",
        "warnings",
    ):
        if summary[field] != 0:
            problems.append(
                f"{field} is {summary[field]}, expected 0"
            )

    if problems:
        raise RuntimeError(
            "Final Project Control verification failed:\n- "
            + "\n- ".join(problems)
        )


def verify_required_files() -> None:
    missing = [
        path
        for path in (
            VALIDATOR,
            FINALIZER,
        )
        if not path.is_file()
    ]

    if missing:
        raise RuntimeError(
            "Required files are missing:\n- "
            + "\n- ".join(str(path) for path in missing)
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run the final CTRL-016 closure after the CTRL-018 "
            "validator consistency refactor."
        )
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Execute the final transactional closure.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()

    print("=" * 72)
    print("CTRL-019 Phase 0 Governance Synchronization")
    print("=" * 72)
    print(f"Version      : {VERSION}")
    print("Closes       : CTRL-016")
    print("Requires     : CTRL-018 consistency refactor")
    print()

    try:
        verify_required_files()
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2

    print("[1/2] Validator preflight")
    print("-" * 72)

    preflight = run_command(
        [
            sys.executable,
            "-B",
            str(VALIDATOR),
            "--verbose",
        ]
    )
    print_output(preflight)

    if preflight.returncode not in {0, 1}:
        print(
            "PRECHECK FAILED: The validator still has blocking findings.",
            file=sys.stderr,
        )
        return 3

    if not args.apply:
        print()
        print("PRECHECK COMPLETED")
        print("No repository files were modified.")
        print()
        print("Apply the final closure with:")
        print(
            "python -B close_ctrl016_after_ctrl018.py --apply"
        )
        return 0

    print()
    print("[2/2] Transactional finalization")
    print("-" * 72)

    finalization = run_command(
        [
            sys.executable,
            "-B",
            str(FINALIZER),
            "--apply",
            "--verbose",
        ]
    )
    print_output(finalization)

    if finalization.returncode != 0:
        print()
        print(
            "FINALIZATION FAILED",
            file=sys.stderr,
        )
        print(
            "finalize_ctrl016.py reported failure and should have "
            "restored its transaction automatically.",
            file=sys.stderr,
        )
        return 4

    print()
    print("Post-finalization independent verification")
    print("-" * 72)

    verification = run_command(
        [
            sys.executable,
            "-B",
            str(VALIDATOR),
            "--verbose",
        ]
    )
    print_output(verification)

    try:
        assert_clean_pass(verification)
    except Exception as error:
        print()
        print(
            "FINAL VERIFICATION FAILED",
            file=sys.stderr,
        )
        print(
            str(error),
            file=sys.stderr,
        )
        return 5

    print()
    print("=" * 72)
    print("PHASE 0 GOVERNANCE SYNCHRONIZED")
    print("=" * 72)
    print("CTRL-016      : ACCEPTED")
    print("Validator     : PASS")
    print("Critical      : 0")
    print("Errors        : 0")
    print("Warnings      : 0")
    print("=" * 72)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())