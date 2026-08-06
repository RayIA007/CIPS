#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
===============================================================================
CLEAN-001
08_SCRIPTS Cleanup Planner

File:
    plan_clean_08_scripts.py

Purpose:
    Inspect C:\\ConsejoIA_V5\\08_SCRIPTS and classify every item before any
    cleanup operation is allowed.

Safety:
    - DRY RUN only.
    - Does not move, rename, delete or modify repository files.
    - Produces a deterministic cleanup plan.
    - Unknown files are preserved and marked REVIEW_REQUIRED.

Output:
    12_PRODUCTION_SYSTEM/99_PROJECT_CONTROL/
    CLEAN_001_08_SCRIPTS_PLAN.json

===============================================================================
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path


VERSION = "1.0.0"
DELIVERABLE = "CLEAN-001"

SCRIPT_DIRECTORY = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIRECTORY.parent

PROJECT_CONTROL_DIRECTORY = (
    PROJECT_ROOT
    / "12_PRODUCTION_SYSTEM"
    / "99_PROJECT_CONTROL"
)

DEFAULT_OUTPUT = (
    PROJECT_CONTROL_DIRECTORY
    / "CLEAN_001_08_SCRIPTS_PLAN.json"
)


class CleanupCategory(str, Enum):
    PRODUCTION = "PRODUCTION"
    VALIDATION = "VALIDATION"
    ENGINEERING = "ENGINEERING"
    BACKUP = "BACKUP"
    CACHE = "CACHE"
    TEMPORARY = "TEMPORARY"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


class CleanupAction(str, Enum):
    KEEP = "KEEP"
    ARCHIVE = "ARCHIVE"
    DELETE_CANDIDATE = "DELETE_CANDIDATE"
    REVIEW = "REVIEW"


@dataclass(frozen=True, slots=True)
class CleanupRecord:
    name: str
    relative_path: str
    item_type: str
    size_bytes: int
    category: CleanupCategory
    proposed_action: CleanupAction
    reason: str


@dataclass(frozen=True, slots=True)
class CleanupPlan:
    document: dict[str, str]
    root: str
    records: tuple[CleanupRecord, ...]
    summary: dict[str, int]
    safety: dict[str, str]


KNOWN_KEEP_FILES = {
    # Project Control
    "validate_project_control.py",
    "sync_project_control.py",
    "finalize_ctrl016.py",
    "close_ctrl016_after_ctrl018.py",

    # Repository Audit System
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
    "finalize_repository_audit_system.py",

    # This planner
    "plan_clean_08_scripts.py",
}


VALIDATION_PATTERNS = (
    re.compile(r"(^|_)test\.py$", re.IGNORECASE),
    re.compile(r"_smoke_test\.py$", re.IGNORECASE),
    re.compile(r"^validate_.*\.py$", re.IGNORECASE),
    re.compile(r"_integration_test\.py$", re.IGNORECASE),
    re.compile(r"^finalize_.*\.py$", re.IGNORECASE),
)


ENGINEERING_PATTERNS = (
    re.compile(r"^apply_.*\.py$", re.IGNORECASE),
    re.compile(r"^patch_.*\.py$", re.IGNORECASE),
    re.compile(r"^fix_.*\.py$", re.IGNORECASE),
    re.compile(r"^repair_.*\.py$", re.IGNORECASE),
    re.compile(r"^migrate_.*\.py$", re.IGNORECASE),
    re.compile(r"^diagnose_.*\.py$", re.IGNORECASE),
    re.compile(r"^debug_.*\.py$", re.IGNORECASE),
)


BACKUP_PATTERNS = (
    re.compile(r"\.bak(?:_|$)", re.IGNORECASE),
    re.compile(r"\.backup(?:_|$)", re.IGNORECASE),
    re.compile(r"~$", re.IGNORECASE),
)


TEMPORARY_PATTERNS = (
    re.compile(r"\.tmp$", re.IGNORECASE),
    re.compile(r"\.temp$", re.IGNORECASE),
    re.compile(r"^temp_", re.IGNORECASE),
    re.compile(r"^tmp_", re.IGNORECASE),
)


CACHE_NAMES = {
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
}


def matches_any(
    name: str,
    patterns: tuple[re.Pattern[str], ...],
) -> bool:
    return any(
        pattern.search(name)
        for pattern in patterns
    )


def classify(
    path: Path,
) -> tuple[
    CleanupCategory,
    CleanupAction,
    str,
]:
    name = path.name

    if name in CACHE_NAMES:
        return (
            CleanupCategory.CACHE,
            CleanupAction.DELETE_CANDIDATE,
            "Generated cache directory.",
        )

    if matches_any(
        name,
        BACKUP_PATTERNS,
    ):
        return (
            CleanupCategory.BACKUP,
            CleanupAction.ARCHIVE,
            "Timestamped or editor backup artifact.",
        )

    if matches_any(
        name,
        TEMPORARY_PATTERNS,
    ):
        return (
            CleanupCategory.TEMPORARY,
            CleanupAction.DELETE_CANDIDATE,
            "Temporary artifact.",
        )

    if name in KNOWN_KEEP_FILES:
        if (
            "_test" in name
            or name.startswith("validate_")
            or name.startswith("finalize_")
        ):
            return (
                CleanupCategory.VALIDATION,
                CleanupAction.KEEP,
                "Required validation or finalization component.",
            )

        return (
            CleanupCategory.PRODUCTION,
            CleanupAction.KEEP,
            "Required production or support component.",
        )

    if matches_any(
        name,
        ENGINEERING_PATTERNS,
    ):
        return (
            CleanupCategory.ENGINEERING,
            CleanupAction.ARCHIVE,
            "One-shot patch, repair or engineering utility.",
        )

    if matches_any(
        name,
        VALIDATION_PATTERNS,
    ):
        return (
            CleanupCategory.VALIDATION,
            CleanupAction.KEEP,
            "Validation or test component; preserved by default.",
        )

    return (
        CleanupCategory.REVIEW_REQUIRED,
        CleanupAction.REVIEW,
        "Not recognized safely; no automatic cleanup allowed.",
    )


def item_size(path: Path) -> int:
    if path.is_file():
        try:
            return path.stat().st_size
        except OSError:
            return 0

    total = 0

    try:
        for child in path.rglob("*"):
            if child.is_file():
                try:
                    total += child.stat().st_size
                except OSError:
                    continue
    except OSError:
        return 0

    return total


def build_plan() -> CleanupPlan:
    records: list[CleanupRecord] = []

    for path in sorted(
        SCRIPT_DIRECTORY.iterdir(),
        key=lambda item: item.name.lower(),
    ):
        category, action, reason = classify(
            path
        )

        records.append(
            CleanupRecord(
                name=path.name,
                relative_path=str(
                    path.relative_to(
                        PROJECT_ROOT
                    )
                ),
                item_type=(
                    "DIRECTORY"
                    if path.is_dir()
                    else "FILE"
                ),
                size_bytes=item_size(path),
                category=category,
                proposed_action=action,
                reason=reason,
            )
        )

    summary = {
        "total_items": len(records),
        "keep": sum(
            record.proposed_action
            is CleanupAction.KEEP
            for record in records
        ),
        "archive": sum(
            record.proposed_action
            is CleanupAction.ARCHIVE
            for record in records
        ),
        "delete_candidates": sum(
            record.proposed_action
            is CleanupAction.DELETE_CANDIDATE
            for record in records
        ),
        "review_required": sum(
            record.proposed_action
            is CleanupAction.REVIEW
            for record in records
        ),
    }

    return CleanupPlan(
        document={
            "name": DEFAULT_OUTPUT.name,
            "version": VERSION,
            "deliverable": DELIVERABLE,
            "status": "PLANNED",
            "generated_at": datetime.now(
                timezone.utc
            ).isoformat(),
        },
        root=str(SCRIPT_DIRECTORY),
        records=tuple(records),
        summary=summary,
        safety={
            "execution_mode": "DRY_RUN_ONLY",
            "files_modified": "NONE",
            "files_deleted": "NONE",
            "files_moved": "NONE",
            "unknown_policy": "REVIEW_REQUIRED",
        },
    )


def print_plan(
    plan: CleanupPlan,
) -> None:
    print("=" * 78)
    print("CLEAN-001 — 08_SCRIPTS Cleanup Planner")
    print("=" * 78)
    print(f"Root              : {plan.root}")
    print(f"Total items       : {plan.summary['total_items']}")
    print(f"Keep              : {plan.summary['keep']}")
    print(f"Archive           : {plan.summary['archive']}")
    print(
        "Delete candidates : "
        f"{plan.summary['delete_candidates']}"
    )
    print(
        "Review required   : "
        f"{plan.summary['review_required']}"
    )
    print("=" * 78)

    for record in plan.records:
        print(
            f"[{record.proposed_action.value:<16}] "
            f"{record.name}"
        )
        print(
            f"  Category : {record.category.value}"
        )
        print(
            f"  Type     : {record.item_type}"
        )
        print(
            f"  Size     : {record.size_bytes} bytes"
        )
        print(
            f"  Reason   : {record.reason}"
        )


def write_plan(
    plan: CleanupPlan,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path.write_text(
        json.dumps(
            asdict(plan),
            indent=4,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Create a safe cleanup plan for 08_SCRIPTS."
        )
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=(
            "Path for the generated JSON cleanup plan."
        ),
    )

    return parser


def main() -> int:
    args = build_parser().parse_args()

    plan = build_plan()

    print_plan(
        plan
    )

    write_plan(
        plan,
        args.output,
    )

    print()
    print("PLAN GENERATED")
    print(f"Output : {args.output.resolve()}")
    print("No files were moved, deleted or modified.")

    if plan.summary["review_required"] > 0:
        print()
        print(
            "Manual review is required before an "
            "automatic cleanup can be generated."
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )