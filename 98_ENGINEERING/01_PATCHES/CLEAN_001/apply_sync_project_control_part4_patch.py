#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

TARGET_NAME = "sync_project_control.py"

PART_IV_CODE = r'''
# =============================================================================
# BASELINE MANIFEST SYNCHRONIZATION
# =============================================================================

class BaselineManifestSynchronizer:

    DOCUMENT_NAME = "CIPS_BASELINE_MANIFEST.yaml"

    def __init__(self, canonical_state: CanonicalExecutionState):

        self.canonical_state = canonical_state

        loaded = SafeYaml.load(BASELINE_MANIFEST)

        if not isinstance(loaded, dict):

            raise ValueError(
                "CIPS_BASELINE_MANIFEST.yaml must contain a mapping at its root."
            )

        self.original_document: Dict[str, Any] = loaded
        self.updated_document: Dict[str, Any] = copy.deepcopy(loaded)

        file_manifest = SafeYaml.load(FILE_MANIFEST)

        if not isinstance(file_manifest, dict):

            raise ValueError(
                "CIPS_FILE_MANIFEST.yaml must contain a mapping at its root."
            )

        self.manifest_status_by_file_id: Dict[str, str] = {}

        for section_name in ("files", "reserved_project_control_files"):

            section = file_manifest.get(section_name, {})

            if not isinstance(section, dict):

                continue

            for file_id, record in section.items():

                if not isinstance(record, dict):

                    continue

                self.manifest_status_by_file_id[
                    normalize_identifier(file_id)
                ] = normalize_state(record.get("status"))

    def _resolve_phase_value(self) -> Any:

        existing = nested_get(
            self.original_document,
            ("current_baseline", "phase"),
            default=None
        )

        canonical = normalize_phase_identifier(
            self.canonical_state.current_phase
        )

        if isinstance(existing, int) and canonical.startswith("PHASE-"):

            raw_number = canonical.removeprefix("PHASE-")

            if raw_number.isdigit():

                return int(raw_number)

        if (
            isinstance(existing, str)
            and existing.strip().isdigit()
            and canonical.startswith("PHASE-")
        ):

            return canonical.removeprefix("PHASE-")

        return canonical

    def plan_changes(self) -> List[FieldChange]:

        changes: List[FieldChange] = []

        phase_change = compare_field(
            document_name=self.DOCUMENT_NAME,
            source_document=self.original_document,
            field_path=("current_baseline", "phase"),
            expected_value=self._resolve_phase_value(),
            authority=Authority.DEPENDENCY_MAP,
            reason=(
                "Current baseline phase is derived from the authoritative "
                "Dependency Map execution state."
            )
        )

        if phase_change is not None:

            changes.append(phase_change)

        deliverable_change = compare_field(
            document_name=self.DOCUMENT_NAME,
            source_document=self.original_document,
            field_path=("current_baseline", "active_deliverable"),
            expected_value=self.canonical_state.current_deliverable,
            authority=Authority.DEPENDENCY_MAP,
            reason=(
                "Current baseline active deliverable is derived from "
                "current_graph_state."
            )
        )

        if deliverable_change is not None:

            changes.append(deliverable_change)

        artifacts = self.original_document.get("baseline_artifacts", {})

        if not isinstance(artifacts, dict):

            raise ValueError(
                "CIPS_BASELINE_MANIFEST.yaml: "
                "'baseline_artifacts' must be a mapping."
            )

        for baseline_id, baseline_record in artifacts.items():

            if not isinstance(baseline_record, dict):

                continue

            for group_name, group in baseline_record.items():

                if not isinstance(group, list):

                    continue

                for index, artifact in enumerate(group):

                    if not isinstance(artifact, dict):

                        continue

                    file_id = normalize_identifier(
                        artifact.get("file_id")
                    )

                    if not file_id:

                        continue

                    canonical_status = self.manifest_status_by_file_id.get(
                        file_id
                    )

                    if canonical_status is None:

                        continue

                    previous_status = normalize_state(
                        artifact.get("expected_status")
                    )

                    if previous_status == canonical_status:

                        continue

                    changes.append(
                        FieldChange(
                            document=self.DOCUMENT_NAME,
                            field_path=(
                                "baseline_artifacts."
                                f"{baseline_id}."
                                f"{group_name}."
                                f"{index}."
                                "expected_status"
                            ),
                            previous_value=previous_status,
                            new_value=canonical_status,
                            authority=Authority.FILE_MANIFEST,
                            reason=(
                                "Baseline artifact expected status is derived "
                                "from the official File Manifest."
                            )
                        )
                    )

        return changes

    def apply_changes(
        self,
        changes: List[FieldChange]
    ) -> Dict[str, Any]:

        for change in changes:

            path_parts = change.field_path.split(".")

            if path_parts[0] == "baseline_artifacts":

                if len(path_parts) != 5:

                    raise ValueError(
                        "Unexpected Baseline artifact field path: "
                        f"{change.field_path}"
                    )

                baseline_id = path_parts[1]
                group_name = path_parts[2]
                item_index = int(path_parts[3])
                field_name = path_parts[4]

                self.updated_document[
                    "baseline_artifacts"
                ][
                    baseline_id
                ][
                    group_name
                ][
                    item_index
                ][
                    field_name
                ] = change.new_value

                continue

            nested_set(
                self.updated_document,
                tuple(path_parts),
                change.new_value
            )

        return self.updated_document

    def synchronize(
        self
    ) -> Tuple[Dict[str, Any], List[FieldChange]]:

        changes = self.plan_changes()
        updated_document = self.apply_changes(changes)

        return updated_document, changes


def validate_baseline_manifest_result(
    document: Dict[str, Any],
    canonical_state: CanonicalExecutionState
) -> None:

    errors: List[str] = []

    actual_phase = normalize_phase_identifier(
        nested_get(
            document,
            ("current_baseline", "phase"),
            default=""
        )
    )

    expected_phase = normalize_phase_identifier(
        canonical_state.current_phase
    )

    if actual_phase != expected_phase:

        errors.append(
            "current_baseline.phase: "
            f"expected {expected_phase!r}, received {actual_phase!r}"
        )

    actual_deliverable = normalize_identifier(
        nested_get(
            document,
            ("current_baseline", "active_deliverable"),
            default=""
        )
    )

    if actual_deliverable != canonical_state.current_deliverable:

        errors.append(
            "current_baseline.active_deliverable: "
            f"expected {canonical_state.current_deliverable!r}, "
            f"received {actual_deliverable!r}"
        )

    file_manifest = SafeYaml.load(FILE_MANIFEST)

    manifest_status_by_file_id: Dict[str, str] = {}

    if isinstance(file_manifest, dict):

        for section_name in ("files", "reserved_project_control_files"):

            section = file_manifest.get(section_name, {})

            if not isinstance(section, dict):

                continue

            for file_id, record in section.items():

                if isinstance(record, dict):

                    manifest_status_by_file_id[
                        normalize_identifier(file_id)
                    ] = normalize_state(record.get("status"))

    artifacts = document.get("baseline_artifacts", {})

    if not isinstance(artifacts, dict):

        errors.append("baseline_artifacts must be a mapping.")

    else:

        for baseline_id, baseline_record in artifacts.items():

            if not isinstance(baseline_record, dict):

                continue

            for group_name, group in baseline_record.items():

                if not isinstance(group, list):

                    continue

                for index, artifact in enumerate(group):

                    if not isinstance(artifact, dict):

                        continue

                    file_id = normalize_identifier(
                        artifact.get("file_id")
                    )

                    if not file_id:

                        continue

                    expected = manifest_status_by_file_id.get(file_id)

                    if expected is None:

                        continue

                    actual = normalize_state(
                        artifact.get("expected_status")
                    )

                    if actual != expected:

                        errors.append(
                            "baseline_artifacts."
                            f"{baseline_id}."
                            f"{group_name}."
                            f"{index}.expected_status: "
                            f"expected {expected!r}, received {actual!r}"
                        )

    if errors:

        raise ValueError(
            "Synchronized Baseline Manifest failed semantic validation:\n- "
            + "\n- ".join(errors)
        )


def synchronize_baseline_manifest(
    canonical_state: CanonicalExecutionState,
    result: SynchronizationResult
) -> Tuple[Dict[str, Any], List[FieldChange]]:

    synchronizer = BaselineManifestSynchronizer(
        canonical_state
    )

    updated_document, changes = synchronizer.synchronize()

    validate_baseline_manifest_result(
        updated_document,
        canonical_state
    )

    for change in changes:

        result.proposed_operations.append(
            change.describe()
        )

    if changes:

        result.changed = True

    return updated_document, changes


def run_part_four_preview() -> int:

    resolver = CanonicalStateResolver()
    canonical_state = resolver.resolve()
    result = SynchronizationResult()

    _, current_state_changes = synchronize_current_state(
        canonical_state,
        result
    )

    _, baseline_changes = synchronize_baseline_manifest(
        canonical_state,
        result
    )

    print_change_plan(
        current_state_changes,
        title="CIPS_CURRENT_STATE.yaml Synchronization Plan"
    )

    print_change_plan(
        baseline_changes,
        title="CIPS_BASELINE_MANIFEST.yaml Synchronization Plan"
    )

    total_changes = (
        len(current_state_changes)
        + len(baseline_changes)
    )

    print(f"Total proposed changes: {total_changes}")
    print()
    print("DRY RUN completed. No repository files were modified.")

    return 0


# =============================================================================
# END OF PART IV
# =============================================================================
'''


def main() -> int:

    script_directory = Path(__file__).resolve().parent
    target = script_directory / TARGET_NAME

    if not target.is_file():

        print(f"ERROR: File not found: {target}", file=sys.stderr)
        return 2

    original = target.read_text(encoding="utf-8")

    if "def run_part_four_preview() -> int:" in original:

        print("NO CHANGES REQUIRED")
        print("Part IV is already installed.")
        return 0

    if "def run_part_three_preview() -> int:" not in original:

        print(
            "ERROR: Part III was not found in sync_project_control.py.",
            file=sys.stderr
        )

        return 3

    call_pattern = re.compile(
        r"exit_code\s*=\s*run_part_three_preview\(\)"
    )

    if len(call_pattern.findall(original)) != 1:

        print(
            "ERROR: Expected exactly one run_part_three_preview() call.",
            file=sys.stderr
        )

        return 4

    entry_pattern = re.compile(
        r'\nif __name__ == "__main__":\s*\n\s*raise SystemExit\(\s*\n\s*main\(\)\s*\n\s*\)\s*',
        re.MULTILINE
    )

    matches = list(entry_pattern.finditer(original))

    if len(matches) != 1:

        print(
            "ERROR: Expected exactly one script entry point.",
            file=sys.stderr
        )

        return 5

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    backup = target.with_name(
        f"{target.name}.bak_part4_{timestamp}"
    )

    shutil.copy2(target, backup)

    updated = call_pattern.sub(
        "exit_code = run_part_four_preview()",
        original,
        count=1
    )

    entry_match = entry_pattern.search(updated)

    if entry_match is None:

        print(
            "ERROR: Entry point could not be relocated.",
            file=sys.stderr
        )

        return 6

    without_entry = (
        updated[:entry_match.start()]
        + updated[entry_match.end():]
    )

    final_entry = '''

# =============================================================================
# SCRIPT ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    raise SystemExit(
        main()
    )
'''

    assembled = (
        without_entry.rstrip()
        + "\n"
        + PART_IV_CODE.rstrip()
        + "\n"
        + final_entry
    )

    target.write_text(assembled, encoding="utf-8")

    verification = target.read_text(encoding="utf-8")

    required = (
        "class BaselineManifestSynchronizer:",
        "def validate_baseline_manifest_result(",
        "def synchronize_baseline_manifest(",
        "def run_part_four_preview() -> int:",
        "exit_code = run_part_four_preview()",
    )

    missing = [
        marker
        for marker in required
        if marker not in verification
    ]

    if missing or verification.count(
        'if __name__ == "__main__":'
    ) != 1:

        shutil.copy2(backup, target)

        print(
            "PATCH ROLLED BACK",
            file=sys.stderr
        )

        if missing:

            print(
                "Missing markers: " + ", ".join(missing),
                file=sys.stderr
            )

        return 7

    print("PATCH APPLIED")
    print(f"Updated : {target}")
    print(f"Backup  : {backup}")
    print()
    print("Part IV installed:")
    print("- Baseline Manifest synchronization plan")
    print("- current_baseline.phase")
    print("- current_baseline.active_deliverable")
    print("- baseline_artifacts expected_status")
    print("- semantic validation")
    print("- combined DRY RUN")
    print()
    print("No YAML files were modified.")
    print()
    print("Next command:")
    print("python -B sync_project_control.py")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())