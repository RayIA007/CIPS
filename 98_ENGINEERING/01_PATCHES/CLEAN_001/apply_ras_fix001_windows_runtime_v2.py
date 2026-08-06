#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
RAS-FIX-001 v2
Windows path and runtime compatibility correction.

Corrects:
- configuration_scanner.py
- test_inventory_scanner.py
- runtime_scanner.py

Includes backups, syntax validation, smoke tests, integration test,
full validator, and automatic rollback.
"""

from __future__ import annotations

import ast
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent

CONFIGURATION_SCANNER = ROOT / "configuration_scanner.py"
TEST_SCANNER = ROOT / "test_inventory_scanner.py"
RUNTIME_SCANNER = ROOT / "runtime_scanner.py"

TARGETS = (
    CONFIGURATION_SCANNER,
    TEST_SCANNER,
    RUNTIME_SCANNER,
)

PATH_HELPER = '# =============================================================================\n# RAS WINDOWS PATH NORMALIZATION\n# =============================================================================\n\ndef _canonical_filesystem_path(path: Path) -> Path:\n    """Return a stable absolute path, expanding Windows 8.3 aliases."""\n    candidate = Path(os.path.abspath(os.fspath(path)))\n\n    if os.name != "nt":\n        return candidate\n\n    try:\n        import ctypes\n\n        get_long_path_name = ctypes.windll.kernel32.GetLongPathNameW\n        get_long_path_name.argtypes = [\n            ctypes.c_wchar_p,\n            ctypes.c_wchar_p,\n            ctypes.c_uint,\n        ]\n        get_long_path_name.restype = ctypes.c_uint\n\n        source = str(candidate)\n        required = get_long_path_name(source, None, 0)\n\n        if required == 0:\n            return candidate\n\n        buffer = ctypes.create_unicode_buffer(required + 1)\n        written = get_long_path_name(\n            source,\n            buffer,\n            len(buffer),\n        )\n\n        if written == 0:\n            return candidate\n\n        return Path(buffer.value)\n\n    except Exception:\n        return candidate\n\n\ndef _safe_relative_to(\n    path: Path,\n    repository_root: Path,\n) -> Path:\n    """Return a safe repository-relative path after path canonicalization."""\n    canonical_path = _canonical_filesystem_path(path)\n    canonical_root = _canonical_filesystem_path(repository_root)\n\n    relative_text = os.path.relpath(\n        str(canonical_path),\n        str(canonical_root),\n    )\n\n    if (\n        relative_text == os.pardir\n        or relative_text.startswith(os.pardir + os.sep)\n    ):\n        raise ValueError(\n            f"{str(path)!r} is not inside repository root "\n            f"{str(repository_root)!r}"\n        )\n\n    return Path(relative_text)\n\n\n# =============================================================================\n# END RAS WINDOWS PATH NORMALIZATION\n# =============================================================================\n'


def validate_syntax(text: str, filename: str) -> None:
    ast.parse(text, filename=filename)


def ensure_import_os(text: str) -> str:
    if re.search(r"^import os\s*$", text, flags=re.MULTILINE):
        return text

    marker = "from __future__ import annotations"

    if marker not in text:
        raise RuntimeError(
            "Future import marker not found."
        )

    return text.replace(
        marker,
        marker + "\n\nimport os",
        1,
    )


def insert_path_helper(text: str) -> str:
    if "RAS WINDOWS PATH NORMALIZATION" in text:
        return text

    match = re.search(
        r"^class\s+[A-Za-z_][A-Za-z0-9_]*",
        text,
        flags=re.MULTILINE,
    )

    if match is None:
        raise RuntimeError(
            "Unable to find first class for helper insertion."
        )

    return (
        text[:match.start()]
        + PATH_HELPER
        + "\n\n"
        + text[match.start():]
    )


def replace_relative_calls(text: str) -> str:
    pattern = re.compile(
        r"(?P<name>[A-Za-z_][A-Za-z0-9_]*)"
        r"\.relative_to\(\s*self\.repository_root\s*\)",
        flags=re.MULTILINE,
    )

    updated, count = pattern.subn(
        r"_safe_relative_to(\g<name>, self.repository_root)",
        text,
    )

    if count == 0 and "_safe_relative_to(" not in updated:
        raise RuntimeError(
            "No repository-relative path expression was found."
        )

    return updated


def patch_path_scanner(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    text = ensure_import_os(text)
    text = insert_path_helper(text)
    text = replace_relative_calls(text)
    return text


def patch_runtime_scanner(path: Path) -> str:
    text = path.read_text(encoding="utf-8")

    exact_block = """    @staticmethod
    def _scan_packages(
        self,
    ) -> tuple[InstalledPackageRecord, ...]:
"""

    replacement = """    def _scan_packages(
        self,
    ) -> tuple[InstalledPackageRecord, ...]:
"""

    if exact_block in text:
        return text.replace(
            exact_block,
            replacement,
            1,
        )

    # Fallback for equivalent whitespace/layout.
    pattern = re.compile(
        r"(?P<indent>^[ \t]*)@staticmethod\s*\n"
        r"(?P=indent)def\s+_scan_packages\(\s*\n"
        r"(?P=indent)[ \t]+self,?\s*\n"
        r"(?P=indent)\)",
        flags=re.MULTILINE,
    )

    updated, count = pattern.subn(
        lambda match: (
            f"{match.group('indent')}def _scan_packages(\n"
            f"{match.group('indent')}    self,\n"
            f"{match.group('indent')})"
        ),
        text,
        count=1,
    )

    if count == 1:
        return updated

    if (
        "@staticmethod" not in text[
            max(0, text.find("def _scan_packages") - 80):
            text.find("def _scan_packages") + 80
        ]
        and re.search(
            r"def\s+_scan_packages\(\s*\n?\s*self",
            text,
        )
    ):
        return text

    raise RuntimeError(
        "Unable to correct _scan_packages binding."
    )


def run_checked(command: list[str], label: str) -> None:
    completed = subprocess.run(
        command,
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        check=False,
    )

    if completed.stdout:
        print(completed.stdout, end="")

    if completed.stderr:
        print(completed.stderr, file=sys.stderr, end="")

    if completed.returncode != 0:
        raise RuntimeError(
            f"{label} failed with exit code "
            f"{completed.returncode}."
        )


def main() -> int:
    print("=" * 72)
    print("RAS-FIX-001 v2 Windows Path and Runtime Compatibility")
    print("=" * 72)

    missing = [
        path
        for path in TARGETS
        if not path.is_file()
    ]

    if missing:
        print("PATCH NOT APPLIED", file=sys.stderr)

        for path in missing:
            print(f"Missing: {path}", file=sys.stderr)

        return 2

    originals = {
        path: path.read_text(encoding="utf-8")
        for path in TARGETS
    }

    try:
        updates = {
            CONFIGURATION_SCANNER: patch_path_scanner(
                CONFIGURATION_SCANNER
            ),
            TEST_SCANNER: patch_path_scanner(
                TEST_SCANNER
            ),
            RUNTIME_SCANNER: patch_runtime_scanner(
                RUNTIME_SCANNER
            ),
        }

        for path, text in updates.items():
            validate_syntax(text, str(path))

    except Exception as error:
        print("PATCH NOT APPLIED", file=sys.stderr)
        print(f"Reason: {error}", file=sys.stderr)
        return 3

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backups: dict[Path, Path] = {}

    try:
        for path in TARGETS:
            backup = path.with_name(
                f"{path.name}.bak_ras_fix001_v2_{timestamp}"
            )
            shutil.copy2(path, backup)
            backups[path] = backup

        for path, text in updates.items():
            path.write_text(text, encoding="utf-8")
            validate_syntax(
                path.read_text(encoding="utf-8"),
                str(path),
            )

        for test_name in (
            "configuration_smoke_test.py",
            "runtime_smoke_test.py",
            "test_inventory_smoke_test.py",
        ):
            run_checked(
                [
                    sys.executable,
                    "-B",
                    str(ROOT / test_name),
                ],
                test_name,
            )

        run_checked(
            [
                sys.executable,
                "-B",
                str(
                    ROOT
                    / "repository_audit_system_integration_test.py"
                ),
            ],
            "RAS integration test",
        )

        run_checked(
            [
                sys.executable,
                "-B",
                str(
                    ROOT
                    / "validate_repository_audit_system.py"
                ),
                "--verbose",
            ],
            "RAS validator",
        )

    except Exception as error:
        for path, original in originals.items():
            path.write_text(
                original,
                encoding="utf-8",
            )

        print("PATCH ROLLED BACK", file=sys.stderr)
        print(f"Reason: {error}", file=sys.stderr)
        return 4

    print()
    print("PATCH APPLIED")

    for path in TARGETS:
        print(f"Updated : {path}")
        print(f"Backup  : {backups[path]}")

    print()
    print("Verification completed:")
    print("- AUD-005 smoke test: PASS")
    print("- AUD-006 smoke test: PASS")
    print("- AUD-009 smoke test: PASS")
    print("- RAS integration test: PASS")
    print("- RAS validator: PASS")
    print()
    print("No YAML or Markdown files were modified.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())