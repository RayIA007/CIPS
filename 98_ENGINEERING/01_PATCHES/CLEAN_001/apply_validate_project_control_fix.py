#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Apply the approved path corrections to validate_project_control.py."""

from __future__ import annotations

import sys
from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(
            f"Expected exactly one occurrence for {label}, found {count}."
        )
    return text.replace(old, new, 1)


def main() -> int:
    target = (
        Path(sys.argv[1]).expanduser().resolve()
        if len(sys.argv) > 1
        else Path(__file__).resolve().parent / "validate_project_control.py"
    )

    if not target.is_file():
        print(f"ERROR: validator not found: {target}", file=sys.stderr)
        return 2

    original = target.read_text(encoding="utf-8")
    updated = original

    updated = replace_once(
        updated,
        '''SCRIPT_PATH: Final[Path] = Path(__file__).resolve()\nSCRIPTS_DIRECTORY: Final[Path] = SCRIPT_PATH.parent\nPRODUCTION_SYSTEM_ROOT: Final[Path] = SCRIPTS_DIRECTORY.parent\nPROJECT_ROOT: Final[Path] = PRODUCTION_SYSTEM_ROOT.parent''',
        '''SCRIPT_PATH: Final[Path] = Path(__file__).resolve()\nSCRIPTS_DIRECTORY: Final[Path] = SCRIPT_PATH.parent\nPROJECT_ROOT: Final[Path] = SCRIPTS_DIRECTORY.parent\nPRODUCTION_SYSTEM_ROOT: Final[Path] = (\n    PROJECT_ROOT / "12_PRODUCTION_SYSTEM"\n)''',
        "base path constants",
    )

    updated = replace_once(
        updated,
        '''    if arguments.scripts_directory is None:\n        scripts_directory = (\n            production_system_root / "08_SCRIPTS"\n        ).resolve()''',
        '''    if arguments.scripts_directory is None:\n        scripts_directory = (\n            project_root / "08_SCRIPTS"\n        ).resolve()''',
        "default scripts directory",
    )

    updated = replace_once(
        updated,
        '''    if not is_relative_to(\n        config.scripts_directory,\n        config.production_system_root,\n    ):\n        raise ConfigurationError(\n            "Scripts directory must exist inside the "\n            "Production System root."\n        )''',
        '''    if not is_relative_to(\n        config.scripts_directory,\n        config.project_root,\n    ):\n        raise ConfigurationError(\n            "Scripts directory must exist inside the project root."\n        )''',
        "scripts boundary validation",
    )

    updated = replace_once(
        updated,
        '''                    "Place validate_project_control.py in "\n                    "12_PRODUCTION_SYSTEM/08_SCRIPTS."''',
        '''                    "Place validate_project_control.py in "\n                    "08_SCRIPTS."''',
        "script location remediation",
    )

    backup = target.with_suffix(target.suffix + ".bak")
    backup.write_text(original, encoding="utf-8")
    target.write_text(updated, encoding="utf-8")

    print("PATCH APPLIED")
    print(f"Updated : {target}")
    print(f"Backup  : {backup}")
    print()
    print("Now verify CIPS_FILE_MANIFEST.yaml contains:")
    print("relative_path: 08_SCRIPTS/validate_project_control.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())