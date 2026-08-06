"""
===============================================================================
AUD-012
Official Baseline Acceptance

File:
    baseline_acceptance.py

Purpose:
    Evaluate whether a legacy baseline candidate can be formally accepted.

Execution policy:
    READ ONLY

Output:
    baseline_acceptance_report.json

===============================================================================
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable

from compatibility_assessment import (
    CompatibilityAssessment,
    CompatibilitySeverity,
)
from legacy_baseline_builder import (
    LegacyBaselineCandidate,
)


class AcceptanceStatus(str, Enum):
    """
    Final AUD-012 acceptance states.
    """

    ACCEPTED = "ACCEPTED"
    ACCEPTED_WITH_WARNINGS = "ACCEPTED_WITH_WARNINGS"
    REJECTED = "REJECTED"


@dataclass(frozen=True, slots=True)
class AcceptanceCriterion:
    """
    One deterministic baseline acceptance criterion.
    """

    identifier: str
    description: str
    passed: bool
    blocking: bool
    evidence: str


@dataclass(frozen=True, slots=True)
class BaselineAcceptanceReport:
    """
    Canonical AUD-012 baseline acceptance report.
    """

    baseline_id: str
    baseline_version: str
    status: AcceptanceStatus
    accepted: bool
    criteria: tuple[AcceptanceCriterion, ...]
    blocking_failures: tuple[str, ...]
    warnings: tuple[str, ...]
    compatibility_score: float
    aggregate_sha256: str
    total_files: int
    total_bytes: int
    certification_statement: str
    metadata: dict[str, str] = field(
        default_factory=dict
    )


class BaselineAcceptanceEngine:
    """
    Evaluate a legacy baseline candidate against deterministic gates.
    """

    def assess(
        self,
        *,
        candidate: LegacyBaselineCandidate,
        compatibility: CompatibilityAssessment,
    ) -> BaselineAcceptanceReport:
        criteria = tuple(
            self._criteria(
                candidate=candidate,
                compatibility=compatibility,
            )
        )

        blocking_failures = tuple(
            criterion.identifier
            for criterion in criteria
            if (
                criterion.blocking
                and not criterion.passed
            )
        )

        warnings = tuple(
            finding.identifier
            for finding in compatibility.findings
            if finding.severity is CompatibilitySeverity.WARNING
        )

        accepted = len(blocking_failures) == 0

        if not accepted:
            status = AcceptanceStatus.REJECTED
        elif warnings:
            status = (
                AcceptanceStatus.ACCEPTED_WITH_WARNINGS
            )
        else:
            status = AcceptanceStatus.ACCEPTED

        return BaselineAcceptanceReport(
            baseline_id=candidate.baseline_id,
            baseline_version=candidate.version,
            status=status,
            accepted=accepted,
            criteria=criteria,
            blocking_failures=blocking_failures,
            warnings=warnings,
            compatibility_score=compatibility.score,
            aggregate_sha256=candidate.aggregate_sha256,
            total_files=candidate.total_files,
            total_bytes=candidate.total_bytes,
            certification_statement=(
                self._certification_statement(
                    baseline_id=candidate.baseline_id,
                    status=status,
                )
            ),
            metadata={
                "deliverable": "AUD-012",
                "execution_policy": "READ_ONLY",
                "source_baseline_status": (
                    candidate.protection_status
                ),
            },
        )

    def _criteria(
        self,
        *,
        candidate: LegacyBaselineCandidate,
        compatibility: CompatibilityAssessment,
    ) -> Iterable[AcceptanceCriterion]:
        yield AcceptanceCriterion(
            identifier="ACC-001",
            description=(
                "Baseline candidate contains at least one artifact."
            ),
            passed=candidate.total_files > 0,
            blocking=True,
            evidence=(
                f"total_files={candidate.total_files}"
            ),
        )

        yield AcceptanceCriterion(
            identifier="ACC-002",
            description=(
                "Aggregate SHA-256 is structurally valid."
            ),
            passed=(
                len(candidate.aggregate_sha256) == 64
                and all(
                    character in "0123456789abcdefABCDEF"
                    for character in (
                        candidate.aggregate_sha256
                    )
                )
            ),
            blocking=True,
            evidence=(
                f"aggregate_sha256="
                f"{candidate.aggregate_sha256}"
            ),
        )

        yield AcceptanceCriterion(
            identifier="ACC-003",
            description=(
                "Compatibility assessment has no blocking failures."
            ),
            passed=compatibility.passed,
            blocking=True,
            evidence=(
                f"compatibility_passed="
                f"{compatibility.passed}; "
                f"failed_rules="
                f"{compatibility.failed_rules}"
            ),
        )

        yield AcceptanceCriterion(
            identifier="ACC-004",
            description=(
                "Every baseline artifact has a checksum."
            ),
            passed=all(
                len(artifact.sha256) == 64
                for artifact in candidate.artifacts
            ),
            blocking=True,
            evidence=(
                f"artifacts={len(candidate.artifacts)}"
            ),
        )

        yield AcceptanceCriterion(
            identifier="ACC-005",
            description=(
                "Baseline candidate is in CANDIDATE protection state."
            ),
            passed=(
                candidate.protection_status
                == "CANDIDATE"
            ),
            blocking=True,
            evidence=(
                f"protection_status="
                f"{candidate.protection_status}"
            ),
        )

    @staticmethod
    def _certification_statement(
        *,
        baseline_id: str,
        status: AcceptanceStatus,
    ) -> str:
        if status is AcceptanceStatus.ACCEPTED:
            return (
                f"Baseline {baseline_id} satisfies all "
                "AUD-012 acceptance criteria."
            )

        if (
            status
            is AcceptanceStatus.ACCEPTED_WITH_WARNINGS
        ):
            return (
                f"Baseline {baseline_id} satisfies all "
                "blocking AUD-012 acceptance criteria "
                "with non-blocking warnings."
            )

        return (
            f"Baseline {baseline_id} does not satisfy "
            "all blocking AUD-012 acceptance criteria."
        )


def assess_baseline_acceptance(
    *,
    candidate: LegacyBaselineCandidate,
    compatibility: CompatibilityAssessment,
) -> BaselineAcceptanceReport:
    """
    Convenience API for AUD-012.
    """

    return BaselineAcceptanceEngine().assess(
        candidate=candidate,
        compatibility=compatibility,
    )