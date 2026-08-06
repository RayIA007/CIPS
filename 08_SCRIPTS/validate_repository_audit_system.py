#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
===============================================================================
RAS-VAL-001
Repository Audit System Validator

File:
    validate_repository_audit_system.py

Purpose:
    Validate the complete Repository Audit System implementation covering
    AUD-001 through AUD-012.

Validation scope:
    - Required file presence
    - Python syntax
    - Module imports
    - Smoke-test execution
    - Cross-module contracts
    - Read-only source protection
    - Final aggregate status

Execution policy:
    READ ONLY

Exit codes:
    0 = PASS
    1 = WARNING
    2 = FAIL
    3 = CRITICAL
    4 = EXECUTION ERROR

===============================================================================
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import importlib
import json
import subprocess
import sys
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Iterable


VALIDATOR_NAME = "Repository Audit System Validator"
VALIDATOR_VERSION = "1.0.0"
VALIDATOR_DELIVERABLE = "RAS-VAL-001"

SCRIPT_DIRECTORY = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIRECTORY.parent


REQUIRED_MODULES = (
    # AUD-001
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

    # AUD-002
    "directory_tree_builder.py",
    "directory_tree_smoke_test.py",

    # AUD-003
    "python_module_scanner.py",
    "python_module_inventory_writer.py",
    "python_module_smoke_test.py",

    # AUD-004
    "dependency_scanner.py",
    "dependency_inventory_writer.py",
    "dependency_smoke_test.py",

    # AUD-005
    "configuration_scanner.py",
    "configuration_inventory_writer.py",
    "configuration_smoke_test.py",

    # AUD-006
    "runtime_scanner.py",
    "runtime_inventory_writer.py",
    "runtime_smoke_test.py",

    # AUD-007
    "pipeline_scanner.py",
    "pipeline_inventory_writer.py",
    "pipeline_smoke_test.py",

    # AUD-008
    "entrypoint_scanner.py",
    "entrypoint_inventory_writer.py",
    "entrypoint_smoke_test.py",

    # AUD-009
    "test_inventory_scanner.py",
    "test_inventory_writer.py",
    "test_inventory_smoke_test.py",

    # AUD-010
    "compatibility_assessment.py",
    "compatibility_report_writer.py",
    "compatibility_smoke_test.py",

    # AUD-011
    "legacy_baseline_builder.py",
    "legacy_baseline_report_writer.py",
    "legacy_baseline_smoke_test.py",

    # AUD-012
    "baseline_acceptance.py",
    "baseline_acceptance_writer.py",
    "baseline_acceptance_smoke_test.py",
)


SMOKE_TESTS = (
    "repository_auditor_smoke_test.py",
    "directory_tree_smoke_test.py",
    "python_module_smoke_test.py",
    "dependency_smoke_test.py",
    "configuration_smoke_test.py",
    "runtime_smoke_test.py",
    "pipeline_smoke_test.py",
    "entrypoint_smoke_test.py",
    "test_inventory_smoke_test.py",
    "compatibility_smoke_test.py",
    "legacy_baseline_smoke_test.py",
    "baseline_acceptance_smoke_test.py",
)


IMPORTABLE_MODULES = tuple(
    Path(filename).stem
    for filename in REQUIRED_MODULES
    if not filename.endswith("_smoke_test.py")
)


class Severity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class ValidationStatus(str, Enum):
    PASS = "PASS"
    WARNING = "WARNING"
    FAIL = "FAIL"


@dataclass(frozen=True, slots=True)
class Finding:
    code: str
    severity: Severity
    message: str
    path: str | None = None
    remediation: str | None = None


@dataclass(slots=True)
class StageResult:
    name: str
    findings: list[Finding] = field(default_factory=list)
    checks_executed: int = 0
    duration_seconds: float = 0.0

    @property
    def status(self) -> ValidationStatus:
        if any(
            finding.severity in {
                Severity.ERROR,
                Severity.CRITICAL,
            }
            for finding in self.findings
        ):
            return ValidationStatus.FAIL

        if any(
            finding.severity is Severity.WARNING
            for finding in self.findings
        ):
            return ValidationStatus.WARNING

        return ValidationStatus.PASS

    @property
    def critical_errors(self) -> int:
        return sum(
            finding.severity is Severity.CRITICAL
            for finding in self.findings
        )

    @property
    def errors(self) -> int:
        return sum(
            finding.severity is Severity.ERROR
            for finding in self.findings
        )

    @property
    def warnings(self) -> int:
        return sum(
            finding.severity is Severity.WARNING
            for finding in self.findings
        )


@dataclass(slots=True)
class ValidationReport:
    stages: list[StageResult] = field(default_factory=list)
    duration_seconds: float = 0.0

    @property
    def status(self) -> ValidationStatus:
        if any(
            stage.status is ValidationStatus.FAIL
            for stage in self.stages
        ):
            return ValidationStatus.FAIL

        if any(
            stage.status is ValidationStatus.WARNING
            for stage in self.stages
        ):
            return ValidationStatus.WARNING

        return ValidationStatus.PASS

    @property
    def checks_executed(self) -> int:
        return sum(
            stage.checks_executed
            for stage in self.stages
        )

    @property
    def critical_errors(self) -> int:
        return sum(
            stage.critical_errors
            for stage in self.stages
        )

    @property
    def errors(self) -> int:
        return sum(
            stage.errors
            for stage in self.stages
        )

    @property
    def warnings(self) -> int:
        return sum(
            stage.warnings
            for stage in self.stages
        )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as stream:
        while True:
            block = stream.read(1024 * 1024)

            if not block:
                break

            digest.update(block)

    return digest.hexdigest()


def snapshot_sources(
    paths: Iterable[Path],
) -> dict[str, str]:
    return {
        str(path): sha256_file(path)
        for path in paths
        if path.is_file()
    }


def validate_presence() -> StageResult:
    stage = StageResult(
        name="PRESENCE"
    )
    started = time.perf_counter()

    for filename in REQUIRED_MODULES:
        stage.checks_executed += 1
        path = SCRIPT_DIRECTORY / filename

        if path.is_file():
            stage.findings.append(
                Finding(
                    code="RAS-PRE-FILE-PRESENT",
                    severity=Severity.INFO,
                    message=f"Required file is present: {filename}",
                    path=str(path),
                )
            )
        else:
            stage.findings.append(
                Finding(
                    code="RAS-PRE-FILE-MISSING",
                    severity=Severity.CRITICAL,
                    message=f"Required file is missing: {filename}",
                    path=str(path),
                    remediation=(
                        "Restore or generate the missing RAS file."
                    ),
                )
            )

    stage.duration_seconds = (
        time.perf_counter() - started
    )
    return stage


def validate_syntax() -> StageResult:
    stage = StageResult(
        name="SYNTAX"
    )
    started = time.perf_counter()

    for filename in REQUIRED_MODULES:
        path = SCRIPT_DIRECTORY / filename

        if not path.is_file():
            continue

        stage.checks_executed += 1

        try:
            source = path.read_text(
                encoding="utf-8"
            )
            ast.parse(
                source,
                filename=str(path),
            )

            stage.findings.append(
                Finding(
                    code="RAS-SYN-PYTHON-VALID",
                    severity=Severity.INFO,
                    message=f"Python syntax is valid: {filename}",
                    path=str(path),
                )
            )

        except Exception as error:
            stage.findings.append(
                Finding(
                    code="RAS-SYN-PYTHON-INVALID",
                    severity=Severity.ERROR,
                    message=(
                        f"Python syntax validation failed: "
                        f"{filename}: {error}"
                    ),
                    path=str(path),
                    remediation=(
                        "Correct the Python syntax and rerun validation."
                    ),
                )
            )

    stage.duration_seconds = (
        time.perf_counter() - started
    )
    return stage


def validate_imports() -> StageResult:
    stage = StageResult(
        name="IMPORTS"
    )
    started = time.perf_counter()

    if str(SCRIPT_DIRECTORY) not in sys.path:
        sys.path.insert(
            0,
            str(SCRIPT_DIRECTORY),
        )

    for module_name in IMPORTABLE_MODULES:
        stage.checks_executed += 1

        try:
            importlib.invalidate_caches()
            importlib.import_module(
                module_name
            )

            stage.findings.append(
                Finding(
                    code="RAS-IMP-MODULE-VALID",
                    severity=Severity.INFO,
                    message=(
                        f"Module imports successfully: "
                        f"{module_name}"
                    ),
                )
            )

        except Exception as error:
            stage.findings.append(
                Finding(
                    code="RAS-IMP-MODULE-FAILED",
                    severity=Severity.ERROR,
                    message=(
                        f"Module import failed: "
                        f"{module_name}: {error}"
                    ),
                    remediation=(
                        "Correct missing symbols, circular imports, "
                        "or incompatible module contracts."
                    ),
                )
            )

    stage.duration_seconds = (
        time.perf_counter() - started
    )
    return stage


def validate_smoke_tests(
    *,
    timeout_seconds: int,
) -> StageResult:
    stage = StageResult(
        name="SMOKE_TESTS"
    )
    started = time.perf_counter()

    source_paths = tuple(
        SCRIPT_DIRECTORY / filename
        for filename in REQUIRED_MODULES
        if (
            SCRIPT_DIRECTORY / filename
        ).is_file()
    )

    before = snapshot_sources(
        source_paths
    )

    for filename in SMOKE_TESTS:
        path = SCRIPT_DIRECTORY / filename

        if not path.is_file():
            continue

        stage.checks_executed += 1

        try:
            completed = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(path),
                ],
                cwd=str(SCRIPT_DIRECTORY),
                text=True,
                capture_output=True,
                timeout=timeout_seconds,
                check=False,
            )

        except subprocess.TimeoutExpired:
            stage.findings.append(
                Finding(
                    code="RAS-TST-TIMEOUT",
                    severity=Severity.ERROR,
                    message=(
                        f"Smoke test exceeded "
                        f"{timeout_seconds} seconds: "
                        f"{filename}"
                    ),
                    path=str(path),
                )
            )
            continue

        if completed.returncode == 0:
            stage.findings.append(
                Finding(
                    code="RAS-TST-PASS",
                    severity=Severity.INFO,
                    message=f"Smoke test passed: {filename}",
                    path=str(path),
                )
            )
        else:
            output = (
                completed.stdout
                + completed.stderr
            ).strip()

            stage.findings.append(
                Finding(
                    code="RAS-TST-FAIL",
                    severity=Severity.ERROR,
                    message=(
                        f"Smoke test failed: {filename}. "
                        f"Output: {output[-1500:]}"
                    ),
                    path=str(path),
                    remediation=(
                        "Correct the failing module or smoke-test contract."
                    ),
                )
            )

    after = snapshot_sources(
        source_paths
    )

    stage.checks_executed += 1

    if before == after:
        stage.findings.append(
            Finding(
                code="RAS-TST-READ-ONLY",
                severity=Severity.INFO,
                message=(
                    "RAS source files were unchanged by smoke tests."
                ),
            )
        )
    else:
        changed = sorted(
            path
            for path in set(before) | set(after)
            if before.get(path) != after.get(path)
        )

        stage.findings.append(
            Finding(
                code="RAS-TST-SOURCE-MODIFIED",
                severity=Severity.CRITICAL,
                message=(
                    "Smoke tests modified protected RAS source files: "
                    + ", ".join(changed)
                ),
                remediation=(
                    "Restore source files and remove write side effects."
                ),
            )
        )

    stage.duration_seconds = (
        time.perf_counter() - started
    )
    return stage


def validate_contracts() -> StageResult:
    stage = StageResult(
        name="CONTRACTS"
    )
    started = time.perf_counter()

    checks = (
        (
            "audit_models",
            "RepositoryInventory",
        ),
        (
            "dependency_scanner",
            "DependencyInventory",
        ),
        (
            "configuration_scanner",
            "ConfigurationInventory",
        ),
        (
            "runtime_scanner",
            "RuntimeInventory",
        ),
        (
            "pipeline_scanner",
            "PipelineInventory",
        ),
        (
            "entrypoint_scanner",
            "EntrypointInventory",
        ),
        (
            "test_inventory_scanner",
            "TestInventory",
        ),
        (
            "compatibility_assessment",
            "CompatibilityAssessment",
        ),
        (
            "legacy_baseline_builder",
            "LegacyBaselineCandidate",
        ),
        (
            "baseline_acceptance",
            "BaselineAcceptanceReport",
        ),
    )

    for module_name, symbol_name in checks:
        stage.checks_executed += 1

        try:
            module = importlib.import_module(
                module_name
            )
            symbol = getattr(
                module,
                symbol_name,
            )

            if symbol is None:
                raise AttributeError(
                    symbol_name
                )

            stage.findings.append(
                Finding(
                    code="RAS-CON-SYMBOL-PRESENT",
                    severity=Severity.INFO,
                    message=(
                        f"Contract symbol is present: "
                        f"{module_name}.{symbol_name}"
                    ),
                )
            )

        except Exception as error:
            stage.findings.append(
                Finding(
                    code="RAS-CON-SYMBOL-MISSING",
                    severity=Severity.ERROR,
                    message=(
                        f"Contract symbol unavailable: "
                        f"{module_name}.{symbol_name}: {error}"
                    ),
                    remediation=(
                        "Restore the expected public contract."
                    ),
                )
            )

    stage.duration_seconds = (
        time.perf_counter() - started
    )
    return stage


def validate_json_serialization() -> StageResult:
    stage = StageResult(
        name="SERIALIZATION"
    )
    started = time.perf_counter()

    stage.checks_executed += 1

    sample = {
        "system": "Repository Audit System",
        "deliverables": [
            f"AUD-{index:03d}"
            for index in range(
                1,
                13,
            )
        ],
        "status": "VALIDATION_PENDING",
    }

    try:
        serialized = json.dumps(
            sample,
            ensure_ascii=False,
        )
        restored = json.loads(
            serialized
        )

        if restored != sample:
            raise ValueError(
                "JSON roundtrip mismatch."
            )

        stage.findings.append(
            Finding(
                code="RAS-SER-JSON-VALID",
                severity=Severity.INFO,
                message="JSON serialization roundtrip is valid.",
            )
        )

    except Exception as error:
        stage.findings.append(
            Finding(
                code="RAS-SER-JSON-FAILED",
                severity=Severity.ERROR,
                message=(
                    f"JSON serialization failed: {error}"
                ),
            )
        )

    stage.duration_seconds = (
        time.perf_counter() - started
    )
    return stage


def execute_validation(
    *,
    timeout_seconds: int,
) -> ValidationReport:
    started = time.perf_counter()

    report = ValidationReport()

    report.stages.append(
        validate_presence()
    )

    if report.stages[-1].status is ValidationStatus.FAIL:
        report.duration_seconds = (
            time.perf_counter() - started
        )
        return report

    report.stages.append(
        validate_syntax()
    )

    if report.stages[-1].status is ValidationStatus.FAIL:
        report.duration_seconds = (
            time.perf_counter() - started
        )
        return report

    report.stages.append(
        validate_imports()
    )

    report.stages.append(
        validate_contracts()
    )

    report.stages.append(
        validate_smoke_tests(
            timeout_seconds=timeout_seconds,
        )
    )

    report.stages.append(
        validate_json_serialization()
    )

    report.duration_seconds = (
        time.perf_counter() - started
    )

    return report


def print_stage(
    stage: StageResult,
    *,
    verbose: bool,
) -> None:
    print()
    print(f"[{stage.name}]")
    print("-" * 72)
    print(f"Status            : {stage.status.value}")
    print(f"Checks executed   : {stage.checks_executed}")
    print(f"Critical errors   : {stage.critical_errors}")
    print(f"Errors            : {stage.errors}")
    print(f"Warnings          : {stage.warnings}")
    print(
        f"Duration          : "
        f"{stage.duration_seconds:.6f} seconds"
    )

    if not verbose:
        return

    print()

    for finding in stage.findings:
        location = (
            f" [{finding.path}]"
            if finding.path
            else ""
        )

        print(
            f"[{finding.severity.value:<8}] "
            f"{finding.code}: "
            f"{finding.message}"
            f"{location}"
        )

        if finding.remediation:
            print(
                f"           Remediation: "
                f"{finding.remediation}"
            )


def print_report(
    report: ValidationReport,
    *,
    verbose: bool,
) -> None:
    print("=" * 72)
    print(VALIDATOR_NAME)
    print("=" * 72)
    print(f"Version           : {VALIDATOR_VERSION}")
    print(f"Deliverable       : {VALIDATOR_DELIVERABLE}")
    print(f"Project root      : {PROJECT_ROOT}")
    print(f"Scripts directory : {SCRIPT_DIRECTORY}")
    print("=" * 72)

    for stage in report.stages:
        print_stage(
            stage,
            verbose=verbose,
        )

    print()
    print("=" * 72)
    print("FINAL RESULT")
    print("=" * 72)
    print(f"Status            : {report.status.value}")
    print(f"Checks executed   : {report.checks_executed}")
    print(f"Critical errors   : {report.critical_errors}")
    print(f"Errors            : {report.errors}")
    print(f"Warnings          : {report.warnings}")
    print(
        f"Duration          : "
        f"{report.duration_seconds:.6f} seconds"
    )
    print("=" * 72)


def resolve_exit_code(
    report: ValidationReport,
    *,
    strict: bool,
) -> int:
    if report.critical_errors > 0:
        return 3

    if report.errors > 0:
        return 2

    if report.warnings > 0:
        return 2 if strict else 1

    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Validate the complete Repository Audit System."
        )
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print every validation finding.",
    )

    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat warnings as validation failures.",
    )

    parser.add_argument(
        "--timeout",
        type=int,
        default=60,
        help=(
            "Maximum number of seconds allowed per smoke test."
        ),
    )

    return parser


def main() -> int:
    args = build_parser().parse_args()

    try:
        report = execute_validation(
            timeout_seconds=args.timeout,
        )

        print_report(
            report,
            verbose=args.verbose,
        )

        return resolve_exit_code(
            report,
            strict=args.strict,
        )

    except KeyboardInterrupt:
        print(
            "Validation interrupted by user.",
            file=sys.stderr,
        )
        return 4

    except Exception as error:
        print(
            f"Validator execution failed: {error}",
            file=sys.stderr,
        )
        return 4


if __name__ == "__main__":
    raise SystemExit(
        main()
    )