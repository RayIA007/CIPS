#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
===============================================================================
RAS-FIN-001
Repository Audit System Finalizer

File:
    finalize_repository_audit_system.py

Purpose:
    Perform the final technical closure of the Repository Audit System
    after AUD-001 through AUD-012 have passed validation.

Behavior:
    DRY RUN by default.
    Use --apply to write the completion certificate.

Safety:
    - Executes the complete RAS validator.
    - Executes the full RAS integration test.
    - Requires PASS, 0 critical errors, 0 errors and 0 warnings.
    - Writes the certificate through a temporary file.
    - Creates a timestamped backup when replacing an existing certificate.
    - Restores the previous certificate automatically on failure.
    - Does not modify source modules, YAML files or Markdown files.

Output:
    12_PRODUCTION_SYSTEM/99_PROJECT_CONTROL/
    RAS_COMPLETION_CERTIFICATE.json

===============================================================================
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


VERSION = "1.0.0"
DELIVERABLE = "RAS-FIN-001"
SYSTEM_NAME = "Repository Audit System"
SYSTEM_RANGE = "AUD-001 through AUD-012"

SCRIPT_DIRECTORY = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIRECTORY.parent

VALIDATOR = (
    SCRIPT_DIRECTORY
    / "validate_repository_audit_system.py"
)

INTEGRATION_TEST = (
    SCRIPT_DIRECTORY
    / "repository_audit_system_integration_test.py"
)

PROJECT_CONTROL_DIRECTORY = (
    PROJECT_ROOT
    / "12_PRODUCTION_SYSTEM"
    / "99_PROJECT_CONTROL"
)

CERTIFICATE_PATH = (
    PROJECT_CONTROL_DIRECTORY
    / "RAS_COMPLETION_CERTIFICATE.json"
)

RAS_SOURCE_FILES = (
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
    "directory_tree_builder.py",
    "directory_tree_smoke_test.py",
    "python_module_scanner.py",
    "python_module_inventory_writer.py",
    "python_module_smoke_test.py",
    "dependency_scanner.py",
    "dependency_inventory_writer.py",
    "dependency_smoke_test.py",
    "configuration_scanner.py",
    "configuration_inventory_writer.py",
    "configuration_smoke_test.py",
    "runtime_scanner.py",
    "runtime_inventory_writer.py",
    "runtime_smoke_test.py",
    "pipeline_scanner.py",
    "pipeline_inventory_writer.py",
    "pipeline_smoke_test.py",
    "entrypoint_scanner.py",
    "entrypoint_inventory_writer.py",
    "entrypoint_smoke_test.py",
    "test_inventory_scanner.py",
    "test_inventory_writer.py",
    "test_inventory_smoke_test.py",
    "compatibility_assessment.py",
    "compatibility_report_writer.py",
    "compatibility_smoke_test.py",
    "legacy_baseline_builder.py",
    "legacy_baseline_report_writer.py",
    "legacy_baseline_smoke_test.py",
    "baseline_acceptance.py",
    "baseline_acceptance_writer.py",
    "baseline_acceptance_smoke_test.py",
    "validate_repository_audit_system.py",
    "repository_audit_system_integration_test.py",
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Finalize the Repository Audit System after "
            "complete validation."
        )
    )

    parser.add_argument(
        "--apply",
        action="store_true",
        help=(
            "Write the RAS completion certificate."
        ),
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        help=(
            "Print complete validator and integration output."
        ),
    )

    return parser


def run_command(
    command: list[str],
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=str(SCRIPT_DIRECTORY),
        text=True,
        capture_output=True,
        check=False,
    )


def print_command_output(
    result: subprocess.CompletedProcess[str],
    *,
    verbose: bool,
) -> None:
    if not verbose:
        return

    if result.stdout:
        print(
            result.stdout,
            end=(
                ""
                if result.stdout.endswith("\n")
                else "\n"
            ),
        )

    if result.stderr:
        print(
            result.stderr,
            file=sys.stderr,
            end=(
                ""
                if result.stderr.endswith("\n")
                else "\n"
            ),
        )


def extract_validator_summary(
    output: str,
) -> dict[str, int | str]:
    final_index = output.rfind(
        "FINAL RESULT"
    )

    if final_index < 0:
        raise RuntimeError(
            "Validator output does not contain FINAL RESULT."
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
                f"Validator summary is missing {label!r}."
            )

        return match.group(1).strip()

    def extract_int(label: str) -> int:
        value = extract_text(label)

        try:
            return int(value)
        except ValueError as error:
            raise RuntimeError(
                f"Validator summary value is invalid: "
                f"{label}={value!r}."
            ) from error

    return {
        "status": extract_text("Status"),
        "checks_executed": extract_int(
            "Checks executed"
        ),
        "critical_errors": extract_int(
            "Critical errors"
        ),
        "errors": extract_int("Errors"),
        "warnings": extract_int("Warnings"),
    }


def verify_validator(
    result: subprocess.CompletedProcess[str],
) -> dict[str, int | str]:
    output = (
        result.stdout
        + result.stderr
    )

    summary = extract_validator_summary(
        output
    )

    failures: list[str] = []

    if result.returncode != 0:
        failures.append(
            f"exit code={result.returncode}"
        )

    if summary["status"] != "PASS":
        failures.append(
            f"status={summary['status']!r}"
        )

    for field in (
        "critical_errors",
        "errors",
        "warnings",
    ):
        if summary[field] != 0:
            failures.append(
                f"{field}={summary[field]}"
            )

    if failures:
        raise RuntimeError(
            "RAS validator did not produce a clean PASS: "
            + ", ".join(failures)
        )

    return summary


def verify_integration(
    result: subprocess.CompletedProcess[str],
) -> None:
    output = (
        result.stdout
        + result.stderr
    )

    if result.returncode != 0:
        raise RuntimeError(
            "RAS integration test failed with exit code "
            f"{result.returncode}."
        )

    required_markers = (
        "INTEGRATION TEST PASSED",
        "AUD-001 through AUD-012 : VALID",
        "Cross-module contracts  : VALID",
        "Baseline acceptance     : VALID",
        "Execution policy        : READ ONLY",
    )

    missing = [
        marker
        for marker in required_markers
        if marker not in output
    ]

    if missing:
        raise RuntimeError(
            "RAS integration output is missing required "
            "success markers: "
            + ", ".join(missing)
        )


def sha256_file(
    path: Path,
) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as stream:
        while True:
            block = stream.read(
                1024 * 1024
            )

            if not block:
                break

            digest.update(block)

    return digest.hexdigest()


def build_source_manifest() -> list[dict[str, Any]]:
    manifest: list[dict[str, Any]] = []

    for filename in RAS_SOURCE_FILES:
        path = SCRIPT_DIRECTORY / filename

        if not path.is_file():
            raise RuntimeError(
                f"Required RAS file is missing: {path}"
            )

        manifest.append(
            {
                "filename": filename,
                "relative_path": str(
                    path.relative_to(
                        PROJECT_ROOT
                    )
                ),
                "size_bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )

    return manifest


def aggregate_manifest_hash(
    manifest: list[dict[str, Any]],
) -> str:
    digest = hashlib.sha256()

    for entry in sorted(
        manifest,
        key=lambda item: item["relative_path"],
    ):
        digest.update(
            entry["relative_path"].encode(
                "utf-8"
            )
        )
        digest.update(b"\0")
        digest.update(
            entry["sha256"].encode(
                "ascii"
            )
        )
        digest.update(b"\0")
        digest.update(
            str(
                entry["size_bytes"]
            ).encode("ascii")
        )
        digest.update(b"\n")

    return digest.hexdigest()


def build_certificate(
    *,
    validator_summary: dict[str, int | str],
) -> dict[str, Any]:
    manifest = build_source_manifest()

    return {
        "document": {
            "name": CERTIFICATE_PATH.name,
            "type": "RAS_COMPLETION_CERTIFICATE",
            "version": VERSION,
            "status": "ACTIVE",
            "generated_at": datetime.now(
                timezone.utc
            ).isoformat(),
        },
        "system": {
            "name": SYSTEM_NAME,
            "deliverables": SYSTEM_RANGE,
            "technical_status": "ACCEPTED",
            "execution_policy": "READ_ONLY",
        },
        "validation": {
            "validator": VALIDATOR.name,
            "validator_deliverable": (
                "RAS-VAL-001"
            ),
            "status": validator_summary["status"],
            "checks_executed": (
                validator_summary[
                    "checks_executed"
                ]
            ),
            "critical_errors": (
                validator_summary[
                    "critical_errors"
                ]
            ),
            "errors": validator_summary["errors"],
            "warnings": validator_summary[
                "warnings"
            ],
            "integration_test": "PASS",
        },
        "source_manifest": {
            "file_count": len(manifest),
            "aggregate_sha256": (
                aggregate_manifest_hash(
                    manifest
                )
            ),
            "files": manifest,
        },
        "certification": {
            "statement": (
                "Repository Audit System AUD-001 through "
                "AUD-012 passed complete syntax, import, "
                "contract, smoke-test, integration and "
                "serialization validation."
            ),
            "accepted": True,
        },
    }


def validate_certificate(
    certificate: dict[str, Any],
) -> None:
    if (
        certificate["system"][
            "technical_status"
        ]
        != "ACCEPTED"
    ):
        raise RuntimeError(
            "Certificate technical status is not ACCEPTED."
        )

    validation = certificate["validation"]

    if validation["status"] != "PASS":
        raise RuntimeError(
            "Certificate validator status is not PASS."
        )

    for field in (
        "critical_errors",
        "errors",
        "warnings",
    ):
        if validation[field] != 0:
            raise RuntimeError(
                f"Certificate contains nonzero {field}."
            )

    manifest = certificate[
        "source_manifest"
    ]

    if manifest["file_count"] != len(
        manifest["files"]
    ):
        raise RuntimeError(
            "Certificate source-manifest count is inconsistent."
        )

    if len(
        manifest["aggregate_sha256"]
    ) != 64:
        raise RuntimeError(
            "Certificate aggregate SHA-256 is invalid."
        )


def write_certificate_transactionally(
    certificate: dict[str, Any],
) -> Path | None:
    PROJECT_CONTROL_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )

    backup: Path | None = None

    if CERTIFICATE_PATH.exists():
        timestamp = datetime.now().strftime(
            "%Y%m%d_%H%M%S"
        )
        backup = CERTIFICATE_PATH.with_name(
            CERTIFICATE_PATH.name
            + f".bak_ras_finalizer_{timestamp}"
        )

        shutil.copy2(
            CERTIFICATE_PATH,
            backup,
        )

    temporary_path: Path | None = None

    try:
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=(
                CERTIFICATE_PATH.name
                + "."
            ),
            suffix=".tmp",
            dir=str(
                PROJECT_CONTROL_DIRECTORY
            ),
            text=True,
        )

        os.close(descriptor)

        temporary_path = Path(
            temporary_name
        )

        temporary_path.write_text(
            json.dumps(
                certificate,
                indent=4,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )

        restored = json.loads(
            temporary_path.read_text(
                encoding="utf-8"
            )
        )

        validate_certificate(
            restored
        )

        os.replace(
            temporary_path,
            CERTIFICATE_PATH,
        )

        return backup

    except Exception:
        if (
            temporary_path is not None
            and temporary_path.exists()
        ):
            temporary_path.unlink()

        if backup is not None:
            shutil.copy2(
                backup,
                CERTIFICATE_PATH,
            )
        elif CERTIFICATE_PATH.exists():
            CERTIFICATE_PATH.unlink()

        raise


def main() -> int:
    args = build_parser().parse_args()

    print("=" * 72)
    print("Repository Audit System Finalizer")
    print("=" * 72)
    print(f"Version      : {VERSION}")
    print(f"Deliverable  : {DELIVERABLE}")
    print(f"System       : {SYSTEM_NAME}")
    print(f"Scope        : {SYSTEM_RANGE}")
    print(
        "Mode         : "
        + (
            "APPLY"
            if args.apply
            else "DRY RUN"
        )
    )
    print("=" * 72)

    required_files = (
        VALIDATOR,
        INTEGRATION_TEST,
    )

    missing = [
        path
        for path in required_files
        if not path.is_file()
    ]

    if missing:
        print(
            "FINALIZATION BLOCKED",
            file=sys.stderr,
        )

        for path in missing:
            print(
                f"Missing: {path}",
                file=sys.stderr,
            )

        return 2

    print()
    print("[1/3] Complete RAS validation")
    print("-" * 72)

    validator_result = run_command(
        [
            sys.executable,
            "-B",
            str(VALIDATOR),
            "--verbose",
        ]
    )

    print_command_output(
        validator_result,
        verbose=args.verbose,
    )

    try:
        validator_summary = verify_validator(
            validator_result
        )
    except Exception as error:
        print(
            f"VALIDATION FAILED: {error}",
            file=sys.stderr,
        )
        return 3

    print(
        "Validator : PASS "
        f"({validator_summary['checks_executed']} checks)"
    )

    print()
    print("[2/3] End-to-end integration")
    print("-" * 72)

    integration_result = run_command(
        [
            sys.executable,
            "-B",
            str(INTEGRATION_TEST),
        ]
    )

    print_command_output(
        integration_result,
        verbose=args.verbose,
    )

    try:
        verify_integration(
            integration_result
        )
    except Exception as error:
        print(
            f"INTEGRATION FAILED: {error}",
            file=sys.stderr,
        )
        return 4

    print("Integration test : PASS")

    print()
    print("[3/3] Completion certificate")
    print("-" * 72)

    try:
        certificate = build_certificate(
            validator_summary=validator_summary,
        )

        validate_certificate(
            certificate
        )

    except Exception as error:
        print(
            f"CERTIFICATE BUILD FAILED: {error}",
            file=sys.stderr,
        )
        return 5

    print(
        "Source files      : "
        f"{certificate['source_manifest']['file_count']}"
    )
    print(
        "Aggregate SHA-256 : "
        f"{certificate['source_manifest']['aggregate_sha256']}"
    )
    print(
        f"Target            : {CERTIFICATE_PATH}"
    )

    if not args.apply:
        print()
        print("DRY RUN COMPLETED")
        print("No repository files were modified.")
        print()
        print("Apply final closure with:")
        print(
            "python -B "
            "finalize_repository_audit_system.py "
            "--apply --verbose"
        )
        return 0

    try:
        backup = write_certificate_transactionally(
            certificate
        )
    except Exception as error:
        print(
            f"FINALIZATION ROLLED BACK: {error}",
            file=sys.stderr,
        )
        return 6

    print()
    print("=" * 72)
    print("REPOSITORY AUDIT SYSTEM FINALIZED")
    print("=" * 72)
    print(f"Certificate : {CERTIFICATE_PATH}")

    if backup is not None:
        print(f"Backup      : {backup}")

    print("Status      : ACCEPTED")
    print("Validator   : PASS")
    print("Integration : PASS")
    print("Critical    : 0")
    print("Errors      : 0")
    print("Warnings    : 0")
    print("=" * 72)

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )