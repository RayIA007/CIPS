"""
===============================================================================
AUD-010
Compatibility Assessment

File:
    compatibility_assessment.py

Purpose:
    Perform a deterministic compatibility assessment over the complete
    Repository Audit System inventory.

Execution policy:
    READ ONLY

Output:
    compatibility_report.json

===============================================================================
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


# =============================================================================
# SEVERITY
# =============================================================================


class CompatibilitySeverity(str, Enum):

    INFO = "INFO"

    WARNING = "WARNING"

    ERROR = "ERROR"

    CRITICAL = "CRITICAL"


# =============================================================================
# FINDING
# =============================================================================


@dataclass(frozen=True, slots=True)
class CompatibilityFinding:

    identifier: str

    severity: CompatibilitySeverity

    title: str

    description: str

    recommendation: str

    source: str

    category: str


# =============================================================================
# REPORT
# =============================================================================


@dataclass(frozen=True, slots=True)
class CompatibilityAssessment:

    findings: tuple[CompatibilityFinding, ...]

    passed: bool

    total_rules: int

    passed_rules: int

    failed_rules: int

    score: float

    metadata: dict[str, str] = field(
        default_factory=dict
    )


# =============================================================================
# ENGINE
# =============================================================================


class CompatibilityAssessmentEngine:

    """
    Executes deterministic compatibility rules over all
    Repository Audit System inventories.
    """

    def assess(

        self,

        *,

        repository_inventory,

        dependency_inventory,

        configuration_inventory,

        runtime_inventory,

        test_inventory,

    ) -> CompatibilityAssessment:

        findings = []

        rules = 0

        failures = 0

        # ------------------------------------------------------------------
        # Rule 1
        # ------------------------------------------------------------------

        rules += 1

        if repository_inventory.total_files == 0:

            failures += 1

            findings.append(

                CompatibilityFinding(

                    identifier="COMP-001",

                    severity=CompatibilitySeverity.CRITICAL,

                    title="Repository is empty",

                    description=(
                        "Repository Inventory reports zero files."
                    ),

                    recommendation=(
                        "Verify repository checkout."
                    ),

                    source="AUD-001",

                    category="Repository",

                )

            )

        # ------------------------------------------------------------------
        # Rule 2
        # ------------------------------------------------------------------

        rules += 1

        if dependency_inventory.unresolved_edges:

            failures += 1

            findings.append(

                CompatibilityFinding(

                    identifier="COMP-002",

                    severity=CompatibilitySeverity.ERROR,

                    title="Unresolved dependencies",

                    description=(
                        "Dependency graph contains unresolved imports."
                    ),

                    recommendation=(
                        "Review missing modules."
                    ),

                    source="AUD-004",

                    category="Dependencies",

                )

            )

        # ------------------------------------------------------------------
        # Rule 3
        # ------------------------------------------------------------------

        rules += 1

        if configuration_inventory.invalid_files:

            failures += 1

            findings.append(

                CompatibilityFinding(

                    identifier="COMP-003",

                    severity=CompatibilitySeverity.ERROR,

                    title="Invalid configuration",

                    description=(
                        "One or more configuration files cannot be parsed."
                    ),

                    recommendation=(
                        "Correct configuration syntax."
                    ),

                    source="AUD-005",

                    category="Configuration",

                )

            )

        # ------------------------------------------------------------------
        # Rule 4
        # ------------------------------------------------------------------

        rules += 1

        if not runtime_inventory.virtual_environment_active:

            findings.append(

                CompatibilityFinding(

                    identifier="COMP-004",

                    severity=CompatibilitySeverity.WARNING,

                    title="Virtual environment not detected",

                    description=(
                        "Repository is running outside an isolated environment."
                    ),

                    recommendation=(
                        "Use a dedicated virtual environment."
                    ),

                    source="AUD-006",

                    category="Runtime",

                )

            )

        # ------------------------------------------------------------------
        # Rule 5
        # ------------------------------------------------------------------

        rules += 1

        if test_inventory.total_test_cases == 0:

            failures += 1

            findings.append(

                CompatibilityFinding(

                    identifier="COMP-005",

                    severity=CompatibilitySeverity.ERROR,

                    title="No automated tests detected",

                    description=(
                        "Repository contains no executable test cases."
                    ),

                    recommendation=(
                        "Implement automated testing."
                    ),

                    source="AUD-009",

                    category="Quality",

                )

            )

        # ------------------------------------------------------------------

        passed = failures == 0

        passed_rules = rules - failures

        score = round(

            (passed_rules / rules) * 100,

            2,

        )

        return CompatibilityAssessment(

            findings=tuple(findings),

            passed=passed,

            total_rules=rules,

            passed_rules=passed_rules,

            failed_rules=failures,

            score=score,

        )


# =============================================================================
# API
# =============================================================================


def assess_repository(

    **inventories,

) -> CompatibilityAssessment:

    """
    Convenience API.
    """

    return CompatibilityAssessmentEngine().assess(

        **inventories

    )