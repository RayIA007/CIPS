#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

TARGET_NAME = "sync_project_control.py"

PART_V_CODE = r'''
# =============================================================================
# TEXT-PRESERVING YAML UPDATE SUPPORT
# =============================================================================

def format_yaml_scalar(value: Any) -> str:
    """Format a simple YAML scalar deterministically."""

    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, (int, float)):
        return str(value)

    text = str(value)
    if text == "":
        return '""'
    if re.fullmatch(r"[A-Za-z0-9_.:/+-]+", text):
        return text
    return json.dumps(text, ensure_ascii=False)


def line_indentation(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def find_yaml_key_line(
    lines: List[str],
    *,
    key: str,
    indentation: int,
    start: int,
    end: int
) -> int:
    pattern = re.compile(
        rf"^{' ' * indentation}{re.escape(key)}:\s*(?:.*?)\s*$"
    )
    matches = [
        index
        for index in range(start, end)
        if pattern.match(lines[index].rstrip("\r\n"))
    ]
    if len(matches) != 1:
        raise ValueError(
            f"Expected exactly one YAML key {key!r} at indentation "
            f"{indentation}; found {len(matches)}."
        )
    return matches[0]


def find_yaml_block_end(
    lines: List[str],
    *,
    key_line: int,
    indentation: int,
    limit: Optional[int] = None
) -> int:
    upper_limit = len(lines) if limit is None else limit

    for index in range(key_line + 1, upper_limit):
        raw = lines[index].rstrip("\r\n")
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        if line_indentation(raw) <= indentation:
            return index

    return upper_limit


def replace_yaml_scalar_path(
    text: str,
    path: Tuple[str, ...],
    value: Any
) -> str:
    if not path:
        raise ValueError("YAML path cannot be empty.")

    lines = text.splitlines(keepends=True)
    start = 0
    end = len(lines)
    indentation = 0
    target_line = -1

    for position, key in enumerate(path):
        target_line = find_yaml_key_line(
            lines,
            key=key,
            indentation=indentation,
            start=start,
            end=end
        )

        if position == len(path) - 1:
            break

        end = find_yaml_block_end(
            lines,
            key_line=target_line,
            indentation=indentation,
            limit=end
        )
        start = target_line + 1
        indentation += 2

    newline = "\r\n" if lines[target_line].endswith("\r\n") else "\n"
    lines[target_line] = (
        f"{' ' * indentation}{path[-1]}: "
        f"{format_yaml_scalar(value)}{newline}"
    )
    return "".join(lines)


def insert_or_replace_yaml_scalar_path(
    text: str,
    path: Tuple[str, ...],
    value: Any
) -> str:
    try:
        return replace_yaml_scalar_path(text, path, value)
    except ValueError:
        if len(path) < 2:
            raise

    lines = text.splitlines(keepends=True)
    parent_path = path[:-1]
    start = 0
    end = len(lines)
    indentation = 0
    parent_line = -1

    for key in parent_path:
        parent_line = find_yaml_key_line(
            lines,
            key=key,
            indentation=indentation,
            start=start,
            end=end
        )
        end = find_yaml_block_end(
            lines,
            key_line=parent_line,
            indentation=indentation,
            limit=end
        )
        start = parent_line + 1
        indentation += 2

    newline = "\r\n" if lines[parent_line].endswith("\r\n") else "\n"
    insertion = (
        f"{' ' * indentation}{path[-1]}: "
        f"{format_yaml_scalar(value)}{newline}"
    )

    insert_at = end
    while insert_at > parent_line + 1 and not lines[insert_at - 1].strip():
        insert_at -= 1

    lines.insert(insert_at, insertion)
    return "".join(lines)


def replace_baseline_artifact_status(
    text: str,
    *,
    file_id: str,
    expected_status: str
) -> str:
    lines = text.splitlines(keepends=True)
    file_pattern = re.compile(
        rf"^(\s*)-\s+file_id:\s*{re.escape(file_id)}\s*$"
    )
    matches = [
        index
        for index, line in enumerate(lines)
        if file_pattern.match(line.rstrip("\r\n"))
    ]

    if len(matches) != 1:
        raise ValueError(
            f"Expected exactly one baseline artifact {file_id!r}; "
            f"found {len(matches)}."
        )

    start = matches[0]
    match = file_pattern.match(lines[start].rstrip("\r\n"))
    if match is None:
        raise ValueError(f"Unable to inspect baseline artifact {file_id!r}.")

    item_indentation = len(match.group(1))
    end = len(lines)

    for index in range(start + 1, len(lines)):
        raw = lines[index].rstrip("\r\n")
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue

        indentation = line_indentation(raw)
        if indentation == item_indentation and raw.lstrip().startswith("- "):
            end = index
            break
        if indentation < item_indentation:
            end = index
            break

    status_pattern = re.compile(
        rf"^{' ' * (item_indentation + 2)}expected_status:\s*(.*?)\s*$"
    )
    status_matches = [
        index
        for index in range(start + 1, end)
        if status_pattern.match(lines[index].rstrip("\r\n"))
    ]

    if len(status_matches) != 1:
        raise ValueError(
            f"Expected exactly one expected_status for {file_id!r}; "
            f"found {len(status_matches)}."
        )

    target = status_matches[0]
    newline = "\r\n" if lines[target].endswith("\r\n") else "\n"
    lines[target] = (
        f"{' ' * (item_indentation + 2)}expected_status: "
        f"{format_yaml_scalar(expected_status)}{newline}"
    )
    return "".join(lines)


# =============================================================================
# TEXT-PRESERVING DOCUMENT BUILDERS
# =============================================================================

def build_current_state_text(
    canonical_state: CanonicalExecutionState
) -> str:
    text = CURRENT_STATE.read_text(encoding="utf-8")
    current_document = SafeYaml.load(CURRENT_STATE)

    if not isinstance(current_document, dict):
        raise ValueError(
            "CIPS_CURRENT_STATE.yaml must contain a mapping root."
        )

    phase_value = resolve_current_state_phase_value(
        current_document,
        canonical_state.current_phase
    )

    updates = (
        (("execution", "current_phase", "id"), phase_value),
        (
            ("execution", "current_deliverable", "id"),
            canonical_state.current_deliverable
        ),
        (
            ("execution", "last_accepted", "id"),
            canonical_state.last_accepted
        ),
        (
            ("execution", "next_deliverable", "id"),
            canonical_state.next_deliverable
        )
    )

    for path, value in updates:
        text = replace_yaml_scalar_path(text, path, value)

    for flag_name, value in canonical_state.ready_flags.items():
        text = insert_or_replace_yaml_scalar_path(
            text,
            ("project_control", flag_name),
            value
        )

    return text


def build_baseline_manifest_text(
    canonical_state: CanonicalExecutionState
) -> str:
    text = BASELINE_MANIFEST.read_text(encoding="utf-8")
    baseline_document = SafeYaml.load(BASELINE_MANIFEST)

    if not isinstance(baseline_document, dict):
        raise ValueError(
            "CIPS_BASELINE_MANIFEST.yaml must contain a mapping root."
        )

    synchronizer = BaselineManifestSynchronizer(canonical_state)
    phase_value = synchronizer._resolve_phase_value()

    text = replace_yaml_scalar_path(
        text,
        ("current_baseline", "phase"),
        phase_value
    )
    text = replace_yaml_scalar_path(
        text,
        ("current_baseline", "active_deliverable"),
        canonical_state.current_deliverable
    )

    artifacts = baseline_document.get("baseline_artifacts", {})
    if not isinstance(artifacts, dict):
        raise ValueError("baseline_artifacts must be a mapping.")

    for baseline_record in artifacts.values():
        if not isinstance(baseline_record, dict):
            continue

        for group in baseline_record.values():
            if not isinstance(group, list):
                continue

            for artifact in group:
                if not isinstance(artifact, dict):
                    continue

                file_id = normalize_identifier(artifact.get("file_id"))
                if not file_id:
                    continue

                canonical_status = (
                    synchronizer.manifest_status_by_file_id.get(file_id)
                )
                if canonical_status is None:
                    continue

                text = replace_baseline_artifact_status(
                    text,
                    file_id=file_id,
                    expected_status=canonical_status
                )

    return text


# =============================================================================
# TRANSACTION SUPPORT
# =============================================================================

@dataclass(frozen=True)
class TransactionFile:
    target: Path
    backup: Path
    temporary: Path
    content: str


def create_transaction_file(
    *,
    target: Path,
    content: str,
    timestamp: str
) -> TransactionFile:
    return TransactionFile(
        target=target,
        backup=target.with_name(f"{target.name}.bak_sync_{timestamp}"),
        temporary=target.with_name(f"{target.name}.tmp_sync_{timestamp}"),
        content=content
    )


def validate_temporary_documents(
    current_transaction: TransactionFile,
    baseline_transaction: TransactionFile,
    canonical_state: CanonicalExecutionState
) -> None:
    current_transaction.temporary.write_text(
        current_transaction.content,
        encoding="utf-8"
    )
    baseline_transaction.temporary.write_text(
        baseline_transaction.content,
        encoding="utf-8"
    )

    current_document = SafeYaml.load(current_transaction.temporary)
    baseline_document = SafeYaml.load(baseline_transaction.temporary)

    if not isinstance(current_document, dict):
        raise ValueError(
            "Temporary Current State does not contain a mapping root."
        )
    if not isinstance(baseline_document, dict):
        raise ValueError(
            "Temporary Baseline Manifest does not contain a mapping root."
        )

    validate_current_state_result(current_document, canonical_state)
    validate_baseline_manifest_result(baseline_document, canonical_state)


def restore_transactions(
    transactions: Tuple[TransactionFile, ...]
) -> None:
    for transaction in transactions:
        if transaction.backup.is_file():
            shutil.copy2(transaction.backup, transaction.target)


def cleanup_transaction_temporary_files(
    transactions: Tuple[TransactionFile, ...]
) -> None:
    for transaction in transactions:
        if transaction.temporary.exists():
            transaction.temporary.unlink()


def execute_validator_process() -> int:
    import subprocess

    completed = subprocess.run(
        [
            sys.executable,
            "-B",
            str(VALIDATOR_SCRIPT),
            "--verbose"
        ],
        cwd=str(SCRIPT_DIRECTORY),
        check=False
    )
    return int(completed.returncode)


# =============================================================================
# PRODUCTION SYNCHRONIZATION
# =============================================================================

def apply_project_control_synchronization(
    canonical_state: CanonicalExecutionState,
    *,
    run_validator: bool
) -> int:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    current_transaction = create_transaction_file(
        target=CURRENT_STATE,
        content=build_current_state_text(canonical_state),
        timestamp=timestamp
    )
    baseline_transaction = create_transaction_file(
        target=BASELINE_MANIFEST,
        content=build_baseline_manifest_text(canonical_state),
        timestamp=timestamp
    )
    transactions = (current_transaction, baseline_transaction)

    try:
        validate_temporary_documents(
            current_transaction,
            baseline_transaction,
            canonical_state
        )

        for transaction in transactions:
            shutil.copy2(transaction.target, transaction.backup)

        for transaction in transactions:
            transaction.temporary.replace(transaction.target)

        current_loaded = SafeYaml.load(CURRENT_STATE)
        baseline_loaded = SafeYaml.load(BASELINE_MANIFEST)

        if not isinstance(current_loaded, dict):
            raise ValueError("Written Current State is invalid.")
        if not isinstance(baseline_loaded, dict):
            raise ValueError("Written Baseline Manifest is invalid.")

        validate_current_state_result(current_loaded, canonical_state)
        validate_baseline_manifest_result(baseline_loaded, canonical_state)

        if run_validator:
            validator_code = execute_validator_process()
            if validator_code != 0:
                raise RuntimeError(
                    "Project Control Validator returned "
                    f"exit code {validator_code}."
                )

    except Exception as error:
        restore_transactions(transactions)
        cleanup_transaction_temporary_files(transactions)

        print("\nSYNCHRONIZATION ROLLED BACK", file=sys.stderr)
        print(f"Reason: {error}", file=sys.stderr)
        print(
            "Both target files were restored from backup.",
            file=sys.stderr
        )
        return 2

    cleanup_transaction_temporary_files(transactions)

    print("\nSYNCHRONIZATION APPLIED")
    print(f"Updated : {CURRENT_STATE}")
    print(f"Backup  : {current_transaction.backup}")
    print(f"Updated : {BASELINE_MANIFEST}")
    print(f"Backup  : {baseline_transaction.backup}")

    if run_validator:
        print("\nProject Control Validator: PASS")

    return 0


# =============================================================================
# COMPLETE CTRL-016 EXECUTION
# =============================================================================

def run_part_five(args: argparse.Namespace) -> int:
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

    total_changes = len(current_state_changes) + len(baseline_changes)
    print(f"Total proposed changes: {total_changes}\n")

    if not args.apply:
        print("DRY RUN completed. No repository files were modified.")
        return 0

    if total_changes == 0:
        print("No synchronization changes are required.")

        if args.validate:
            validator_code = execute_validator_process()
            if validator_code != 0:
                return 2
            print("Project Control Validator: PASS")

        return 0

    return apply_project_control_synchronization(
        canonical_state,
        run_validator=bool(args.validate)
    )


# =============================================================================
# END OF PART V
# =============================================================================
'''


def main() -> int:
    script_directory = Path(__file__).resolve().parent
    target = script_directory / TARGET_NAME

    if not target.is_file():
        print(f"ERROR: File not found: {target}", file=sys.stderr)
        return 2

    original = target.read_text(encoding="utf-8")

    if "def run_part_five(" in original:
        print("NO CHANGES REQUIRED")
        print("Part V is already installed.")
        return 0

    if "def run_part_four_preview() -> int:" not in original:
        print("ERROR: Part IV was not found.", file=sys.stderr)
        return 3

    call_pattern = re.compile(
        r"exit_code\s*=\s*run_part_four_preview\(\)"
    )
    if len(call_pattern.findall(original)) != 1:
        print(
            "ERROR: Expected exactly one run_part_four_preview() call.",
            file=sys.stderr
        )
        return 4

    entry_pattern = re.compile(
        r'\nif __name__ == "__main__":\s*'
        r'\n\s*raise SystemExit\(\s*'
        r'\n\s*main\(\)\s*'
        r'\n\s*\)\s*',
        re.MULTILINE
    )
    entry_matches = list(entry_pattern.finditer(original))
    if len(entry_matches) != 1:
        print(
            "ERROR: Expected exactly one script entry point.",
            file=sys.stderr
        )
        return 5

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = target.with_name(f"{target.name}.bak_part5_{timestamp}")
    shutil.copy2(target, backup)

    updated = call_pattern.sub(
        "exit_code = run_part_five(args)",
        original,
        count=1
    )
    entry_match = entry_pattern.search(updated)
    if entry_match is None:
        print("ERROR: Entry point could not be relocated.", file=sys.stderr)
        return 6

    without_entry = (
        updated[:entry_match.start()]
        + updated[entry_match.end():]
    )

    final_entry = r'''

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
        + PART_V_CODE.rstrip()
        + "\n"
        + final_entry
    )
    target.write_text(assembled, encoding="utf-8")

    verification = target.read_text(encoding="utf-8")
    required_markers = (
        "def build_current_state_text(",
        "def build_baseline_manifest_text(",
        "def apply_project_control_synchronization(",
        "def run_part_five(",
        "exit_code = run_part_five(args)",
    )
    missing = [
        marker
        for marker in required_markers
        if marker not in verification
    ]
    entry_count = verification.count('if __name__ == "__main__":')

    if missing or entry_count != 1:
        shutil.copy2(backup, target)
        print("PATCH ROLLED BACK", file=sys.stderr)
        if missing:
            print(
                "Missing markers: " + ", ".join(missing),
                file=sys.stderr
            )
        if entry_count != 1:
            print(f"Entry point count: {entry_count}", file=sys.stderr)
        return 7

    print("PATCH APPLIED")
    print(f"Updated : {target}")
    print(f"Backup  : {backup}")
    print()
    print("Part V installed:")
    print("- Text-preserving YAML writes")
    print("- Timestamped backups")
    print("- Temporary-file validation")
    print("- Transactional two-file update")
    print("- Automatic rollback")
    print("- --apply")
    print("- --validate")
    print()
    print("No YAML files were modified during patch installation.")
    print()
    print("Next safe command:")
    print("python -B sync_project_control.py")
    print()
    print("Do not use --apply until the new DRY RUN is confirmed.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())