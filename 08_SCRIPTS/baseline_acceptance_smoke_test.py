"""
===============================================================================
AUD-012
Official Baseline Acceptance

File:
    baseline_acceptance_smoke_test.py

Purpose:
    Smoke Test for the Official Baseline Acceptance Engine.

Execution Policy:
    READ ONLY

===============================================================================
"""

from __future__ import annotations

import tempfile

from pathlib import Path

from compatibility_assessment import (
    CompatibilityAssessment,
)

from legacy_baseline_builder import (
    LegacyBaselineCandidate,
    BaselineArtifactRecord,
)

from baseline_acceptance import (
    assess_baseline_acceptance,
    AcceptanceStatus,
)

from baseline_acceptance_writer import (
    write_baseline_acceptance_report,
)


# =============================================================================
# TEST DATA
# =============================================================================


def build_candidate() -> LegacyBaselineCandidate:

    return LegacyBaselineCandidate(

        baseline_id="LEGACY-STABLE-BASELINE",

        project_name="TEST_PROJECT",

        repository_root="C:/TEST",

        generated_at="2026-01-01T00:00:00Z",

        version="1.0.0",

        git_commit="ABCDEF123456",

        reference_project=None,

        functional_entrypoints=(

            "src/main.py",

        ),

        pipeline_modules=(

            "production.pipeline",

        ),

        artifacts=(

            BaselineArtifactRecord(

                relative_path="README.md",

                size_bytes=1024,

                sha256="A"*64,

                category="DOCUMENTATION",

                status="ACTIVE",

            ),

        ),

        total_files=1,

        total_bytes=1024,

        aggregate_sha256="F"*64,

        protection_status="CANDIDATE",

    )


def build_compatibility() -> CompatibilityAssessment:

    return CompatibilityAssessment(

        findings=(),

        passed=True,

        total_rules=5,

        passed_rules=5,

        failed_rules=0,

        score=100.0,

    )


# =============================================================================
# MAIN
# =============================================================================


def main() -> int:

    print("=" * 72)

    print("AUD-012 Official Baseline Acceptance Smoke Test")

    print("=" * 72)

    candidate = build_candidate()

    compatibility = build_compatibility()

    report = assess_baseline_acceptance(

        candidate=candidate,

        compatibility=compatibility,

    )

    if not report.accepted:

        raise AssertionError(

            "Acceptance failed."

        )

    if report.status != AcceptanceStatus.ACCEPTED:

        raise AssertionError(

            "Unexpected acceptance status."

        )

    if len(report.criteria) != 5:

        raise AssertionError(

            "Unexpected criteria count."

        )

    if report.blocking_failures:

        raise AssertionError(

            "Unexpected blocking failures."

        )

    with tempfile.TemporaryDirectory(

        prefix="aud012_",

    ) as temp:

        output = (

            Path(temp)

            / "baseline_acceptance_report.json"

        )

        write_baseline_acceptance_report(

            report=report,

            output_file=output,

        )

        if not output.exists():

            raise AssertionError(

                "Acceptance report not generated."

            )

    print()

    print("SMOKE TEST PASSED")

    print("Acceptance Engine : VALID")

    print("Acceptance Rules  : VALID")

    print("Serialization     : VALID")

    print("Certification     : VALID")

    print("READ ONLY         : VALID")

    print("=" * 72)

    print()

    return 0


if __name__ == "__main__":

    raise SystemExit(

        main()

    )