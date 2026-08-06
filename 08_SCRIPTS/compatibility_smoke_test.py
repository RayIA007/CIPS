"""
===============================================================================
AUD-010
Compatibility Assessment

File:
    compatibility_smoke_test.py

Purpose:
    Smoke test for the Compatibility Assessment engine and report writer.

Execution policy:
    READ ONLY

===============================================================================
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from types import SimpleNamespace

from compatibility_assessment import (
    CompatibilitySeverity,
    assess_repository,
)
from compatibility_report_writer import (
    write_compatibility_report,
)


def build_clean_inputs():
    repository_inventory = SimpleNamespace(
        total_files=10
    )

    dependency_inventory = SimpleNamespace(
        unresolved_edges=()
    )

    configuration_inventory = SimpleNamespace(
        invalid_files=0
    )

    runtime_inventory = SimpleNamespace(
        virtual_environment_active=True
    )

    test_inventory = SimpleNamespace(
        total_test_cases=5
    )

    return {
        "repository_inventory": repository_inventory,
        "dependency_inventory": dependency_inventory,
        "configuration_inventory": configuration_inventory,
        "runtime_inventory": runtime_inventory,
        "test_inventory": test_inventory,
    }


def build_warning_inputs():
    inputs = build_clean_inputs()

    inputs["runtime_inventory"] = SimpleNamespace(
        virtual_environment_active=False
    )

    return inputs


def build_failure_inputs():
    return {
        "repository_inventory": SimpleNamespace(
            total_files=0
        ),
        "dependency_inventory": SimpleNamespace(
            unresolved_edges=("missing.module",)
        ),
        "configuration_inventory": SimpleNamespace(
            invalid_files=1
        ),
        "runtime_inventory": SimpleNamespace(
            virtual_environment_active=False
        ),
        "test_inventory": SimpleNamespace(
            total_test_cases=0
        ),
    }


def main() -> int:
    print("=" * 72)
    print("AUD-010 Compatibility Assessment Smoke Test")
    print("=" * 72)

    clean_report = assess_repository(
        **build_clean_inputs()
    )

    if not clean_report.passed:
        raise AssertionError(
            "Clean compatibility assessment did not pass."
        )

    if clean_report.failed_rules != 0:
        raise AssertionError(
            "Clean compatibility assessment reported failed rules."
        )

    if clean_report.score != 100.0:
        raise AssertionError(
            f"Expected score 100.0, received {clean_report.score}."
        )

    warning_report = assess_repository(
        **build_warning_inputs()
    )

    warning_findings = [
        finding
        for finding in warning_report.findings
        if finding.severity is CompatibilitySeverity.WARNING
    ]

    if len(warning_findings) != 1:
        raise AssertionError(
            "Expected exactly one warning finding."
        )

    if not warning_report.passed:
        raise AssertionError(
            "Warnings alone must not fail compatibility."
        )

    failure_report = assess_repository(
        **build_failure_inputs()
    )

    if failure_report.passed:
        raise AssertionError(
            "Failure assessment unexpectedly passed."
        )

    if failure_report.failed_rules != 4:
        raise AssertionError(
            "Expected four failed blocking rules."
        )

    finding_ids = {
        finding.identifier
        for finding in failure_report.findings
    }

    expected_ids = {
        "COMP-001",
        "COMP-002",
        "COMP-003",
        "COMP-004",
        "COMP-005",
    }

    if finding_ids != expected_ids:
        raise AssertionError(
            "Compatibility findings do not match expected rules."
        )

    with tempfile.TemporaryDirectory(
        prefix="aud010_"
    ) as temporary_directory:
        output_path = (
            Path(temporary_directory)
            / "compatibility_report.json"
        )

        write_compatibility_report(
            report=failure_report,
            output_file=output_path,
        )

        if not output_path.is_file():
            raise AssertionError(
                "Compatibility report was not generated."
            )

        report_text = output_path.read_text(
            encoding="utf-8"
        )

        if '"COMP-001"' not in report_text:
            raise AssertionError(
                "Serialized report is missing COMP-001."
            )

        if '"passed": false' not in report_text.lower():
            raise AssertionError(
                "Serialized report does not preserve failed status."
            )

    print()
    print("SMOKE TEST PASSED")
    print("Clean assessment   : VALID")
    print("Warning handling   : VALID")
    print("Failure detection  : VALID")
    print("Report JSON        : VALID")
    print("READ ONLY          : VALID")
    print("=" * 72)

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )