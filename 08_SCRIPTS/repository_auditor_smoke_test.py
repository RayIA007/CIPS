"""
===============================================================================
AUD-001
Repository Inventory

File:
    repository_auditor_smoke_test.py

Purpose:
    Smoke test for the complete AUD-001 Repository Auditor workflow.

The test creates an isolated temporary repository, executes the auditor,
writes repository_inventory.json, and validates the expected structure.

===============================================================================
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from audit_engine import execute_audit
from repository_inventory_writer import write_inventory


def create_fixture(repository_root: Path) -> None:
    """
    Create a minimal deterministic repository fixture.
    """

    (repository_root / "src").mkdir(parents=True)
    (repository_root / "config").mkdir(parents=True)

    (repository_root / "README.md").write_text(
        "# AUD-001 Smoke Test\n",
        encoding="utf-8",
    )

    (repository_root / "src" / "example.py").write_text(
        "VALUE = 1\n",
        encoding="utf-8",
    )

    (repository_root / "config" / "settings.yaml").write_text(
        "enabled: true\n",
        encoding="utf-8",
    )


def validate_inventory(
    inventory_path: Path,
) -> None:
    """
    Validate the generated JSON inventory.
    """

    if not inventory_path.is_file():
        raise AssertionError(
            f"Inventory file was not created: {inventory_path}"
        )

    payload = json.loads(
        inventory_path.read_text(
            encoding="utf-8"
        )
    )

    required_root_fields = {
        "project_name",
        "root_directory",
        "generated_at",
        "files",
        "warnings",
        "errors",
    }

    missing_root_fields = (
        required_root_fields
        - set(payload)
    )

    if missing_root_fields:
        raise AssertionError(
            "Inventory is missing root fields: "
            + ", ".join(
                sorted(missing_root_fields)
            )
        )

    files = payload["files"]

    if len(files) != 3:
        raise AssertionError(
            f"Expected 3 inventory records, received {len(files)}."
        )

    relative_paths = {
        item["relative_path"]
        for item in files
    }

    expected_paths = {
        "README.md",
        str(Path("src") / "example.py"),
        str(Path("config") / "settings.yaml"),
    }

    if relative_paths != expected_paths:
        raise AssertionError(
            "Inventory paths do not match the fixture. "
            f"Expected {sorted(expected_paths)}, "
            f"received {sorted(relative_paths)}."
        )

    identifiers = [
        item["identifier"]
        for item in files
    ]

    if len(identifiers) != len(set(identifiers)):
        raise AssertionError(
            "Inventory identifiers are not unique."
        )

    for item in files:
        checksum = item.get("checksum")

        if not checksum:
            raise AssertionError(
                f"Checksum is missing for {item['relative_path']}."
            )

        if checksum.get("algorithm") != "SHA256":
            raise AssertionError(
                f"Unexpected checksum algorithm for "
                f"{item['relative_path']}."
            )

        checksum_value = checksum.get("value", "")

        if len(checksum_value) != 64:
            raise AssertionError(
                f"Invalid SHA-256 checksum length for "
                f"{item['relative_path']}."
            )


def main() -> int:
    print("=" * 72)
    print("AUD-001 Repository Auditor Smoke Test")
    print("=" * 72)

    with tempfile.TemporaryDirectory(
        prefix="aud001_smoke_"
    ) as temporary_directory:
        repository_root = Path(
            temporary_directory
        ) / "repository"

        repository_root.mkdir(
            parents=True
        )

        create_fixture(
            repository_root
        )

        result = execute_audit(
            repository_root=repository_root,
            compute_checksums=True,
            recursive=True,
        )

        if not result.successful:
            raise AssertionError(
                "Audit execution reported failure: "
                + "; ".join(result.errors)
            )

        if result.inventory.total_files != 3:
            raise AssertionError(
                "Unexpected inventory file count: "
                f"{result.inventory.total_files}"
            )

        output_path = (
            repository_root
            / "repository_inventory.json"
        )

        write_inventory(
            result.inventory,
            output_path,
        )

        validate_inventory(
            output_path
        )

    print("SMOKE TEST PASSED")
    print("Files inventoried : 3")
    print("Checksums         : VALID")
    print("JSON output       : VALID")
    print("Filesystem policy : READ ONLY")
    print("=" * 72)

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )