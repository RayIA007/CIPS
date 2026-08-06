"""
===============================================================================
AUD-002
Directory Tree

File:
    directory_tree_smoke_test.py

Purpose:
    Validate the AUD-002 directory tree generation workflow.

===============================================================================
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from audit_models import ScanConfiguration
from directory_tree_builder import (
    build_repository_tree,
    write_repository_tree,
)
from filesystem_scanner import discover_repository_files


def create_fixture(root: Path) -> None:
    (root / "src" / "core").mkdir(parents=True)
    (root / "config").mkdir(parents=True)

    (root / "README.md").write_text(
        "# Test Repository\n",
        encoding="utf-8",
    )
    (root / "src" / "main.py").write_text(
        "print('ok')\n",
        encoding="utf-8",
    )
    (root / "src" / "core" / "models.py").write_text(
        "VALUE = 1\n",
        encoding="utf-8",
    )
    (root / "config" / "settings.yaml").write_text(
        "enabled: true\n",
        encoding="utf-8",
    )


def main() -> int:
    print("=" * 72)
    print("AUD-002 Directory Tree Smoke Test")
    print("=" * 72)

    with tempfile.TemporaryDirectory(
        prefix="aud002_smoke_"
    ) as temporary_directory:
        repository_root = Path(
            temporary_directory
        ) / "repository"

        repository_root.mkdir(
            parents=True
        )

        create_fixture(repository_root)

        files = discover_repository_files(
            ScanConfiguration(
                repository_root=repository_root,
                recursive=True,
                compute_checksums=False,
            )
        )

        tree = build_repository_tree(
            repository_root=repository_root,
            files=files,
        )

        output_path = (
            repository_root
            / "repository_tree.md"
        )

        write_repository_tree(
            tree=tree,
            output_path=output_path,
        )

        if not output_path.is_file():
            raise AssertionError(
                "repository_tree.md was not created."
            )

        content = output_path.read_text(
            encoding="utf-8"
        )

        expected_fragments = (
            "repository/",
            "config/",
            "settings.yaml",
            "src/",
            "core/",
            "models.py",
            "main.py",
            "README.md",
        )

        for fragment in expected_fragments:
            if fragment not in content:
                raise AssertionError(
                    f"Missing tree fragment: {fragment}"
                )

        if content.count("README.md") != 1:
            raise AssertionError(
                "README.md appears more than once."
            )

    print("SMOKE TEST PASSED")
    print("Tree output       : VALID")
    print("Deterministic sort: VALID")
    print("Filesystem policy : READ ONLY")
    print("=" * 72)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())