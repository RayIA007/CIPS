#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import ast
import base64
import shutil
import sys
from datetime import datetime
from pathlib import Path


SYNC_NAME = "sync_project_control.py"
VALIDATOR_NAME = "validate_project_control.py"

SYNC_BLOCK = base64.b64decode(
    "CiMgPT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT0KIyBDVFJMLTAxNiBGSU5BTCBBQ0NFUFRBTkNFIFNUQVRFCiMgPT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT0KCl9wcmV2aW91c19yZXNvbHZlX2dyYXBoX3N0YXRlX2N0cmwwMTZfZmluYWwgPSByZXNvbHZlX2dyYXBoX3N0YXRlCgoKZGVmIHJlc29sdmVfZ3JhcGhfc3RhdGUoCiAgICBkZXBlbmRlbmN5X21hcDogRGljdFtzdHIsIEFueV0sCiAgICBkZWxpdmVyYWJsZXM6IERpY3Rbc3RyLCBEZWxpdmVyYWJsZVJlY29yZF0sCiAgICBvcmRlcmVkX2RlbGl2ZXJhYmxlczogTGlzdFtzdHJdCikgLT4gVHVwbGVbc3RyLCBzdHIsIHN0ciwgc3RyXToKICAgICIiIgogICAgVHJlYXQgdGhlIGFjY2VwdGVkIGZpbmFsIGdyYXBoIG5vZGUgYXMgYm90aCBjdXJyZW50IGNoZWNrcG9pbnQgYW5kCiAgICBsYXN0IGFjY2VwdGVkIGRlbGl2ZXJhYmxlIHdoZW4gbm8gc3Vic2VxdWVudCBkZWxpdmVyYWJsZSBleGlzdHMuCiAgICAiIiIKCiAgICAoCiAgICAgICAgY3VycmVudF9waGFzZSwKICAgICAgICBjdXJyZW50X2RlbGl2ZXJhYmxlLAogICAgICAgIGxhc3RfYWNjZXB0ZWQsCiAgICAgICAgbmV4dF9kZWxpdmVyYWJsZQogICAgKSA9IF9wcmV2aW91c19yZXNvbHZlX2dyYXBoX3N0YXRlX2N0cmwwMTZfZmluYWwoCiAgICAgICAgZGVwZW5kZW5jeV9tYXAsCiAgICAgICAgZGVsaXZlcmFibGVzLAogICAgICAgIG9yZGVyZWRfZGVsaXZlcmFibGVzCiAgICApCgogICAgY3VycmVudF9yZWNvcmQgPSBkZWxpdmVyYWJsZXMuZ2V0KAogICAgICAgIGN1cnJlbnRfZGVsaXZlcmFibGUKICAgICkKCiAgICB0ZXJtaW5hbF9uZXh0ID0gKAogICAgICAgIG5vcm1hbGl6ZV9pZGVudGlmaWVyKAogICAgICAgICAgICBuZXh0X2RlbGl2ZXJhYmxlCiAgICAgICAgKS51cHBlcigpCiAgICAgICAgaW4gRU5EX09GX0dSQVBIX0FMSUFTRVMKICAgICkKCiAgICBpZiAoCiAgICAgICAgY3VycmVudF9yZWNvcmQgaXMgbm90IE5vbmUKICAgICAgICBhbmQgY3VycmVudF9yZWNvcmQuc3RhdHVzIGluIEFDQ0VQVEVEX1NUQVRFUwogICAgICAgIGFuZCB0ZXJtaW5hbF9uZXh0CiAgICApOgogICAgICAgIGxhc3RfYWNjZXB0ZWQgPSBjdXJyZW50X2RlbGl2ZXJhYmxlCiAgICAgICAgbmV4dF9kZWxpdmVyYWJsZSA9IEVORF9PRl9HUkFQSF9JRAoKICAgIHJldHVybiAoCiAgICAgICAgY3VycmVudF9waGFzZSwKICAgICAgICBjdXJyZW50X2RlbGl2ZXJhYmxlLAogICAgICAgIGxhc3RfYWNjZXB0ZWQsCiAgICAgICAgbmV4dF9kZWxpdmVyYWJsZQogICAgKQoKCiMgPT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT0KIyBFTkQgQ1RSTC0wMTYgRklOQUwgQUNDRVBUQU5DRSBTVEFURQojID09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09Cg=="
).decode("utf-8")

VALIDATOR_BLOCK = base64.b64decode(
    "CiMgPT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT0KIyBDVFJMLTAxNiBURVJNSU5BTCBERVBFTkRFTkNZIFJFRkVSRU5DRSBDT01QQVRJQklMSVRZCiMgPT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT0KCl9wcmV2aW91c192YWxpZGF0ZV9kZXBlbmRlbmNpZXNfY3RybDAxNl90ZXJtaW5hbCA9IHZhbGlkYXRlX2RlcGVuZGVuY2llcwoKCmRlZiB2YWxpZGF0ZV9kZXBlbmRlbmNpZXMoCiAgICBjb250ZXh0OiBWYWxpZGF0aW9uQ29udGV4dCwKKSAtPiBTdGFnZVJlc3VsdDoKICAgICIiIgogICAgUmVtb3ZlIHRoZSBsZWdhY3kgdW5rbm93bi1kZWxpdmVyYWJsZSBlcnJvciBmb3IgdGhlIGV4cGxpY2l0IE5PTkUKICAgIHNlbnRpbmVsIG9ubHkgd2hlbiB0aGUgY3VycmVudCBkZWxpdmVyYWJsZSBpcyB2ZXJpZmllZCBhcyB0aGUgZmluYWwKICAgIGRlcGVuZGVuY3ktZ3JhcGggbm9kZS4KICAgICIiIgoKICAgIHJlc3VsdCA9IF9wcmV2aW91c192YWxpZGF0ZV9kZXBlbmRlbmNpZXNfY3RybDAxNl90ZXJtaW5hbCgKICAgICAgICBjb250ZXh0CiAgICApCgogICAgaWYgbm90IF9pc192YWxpZF90ZXJtaW5hbF9leGVjdXRpb25fc3RhdGUoCiAgICAgICAgY29udGV4dAogICAgKToKICAgICAgICByZXR1cm4gcmVzdWx0CgogICAgcmV0YWluZWQgPSBbXQoKICAgIGZvciBmaW5kaW5nIGluIHJlc3VsdC5maW5kaW5nczoKICAgICAgICBjb2RlID0gc3RyKAogICAgICAgICAgICBnZXRhdHRyKAogICAgICAgICAgICAgICAgZmluZGluZywKICAgICAgICAgICAgICAgICJjb2RlIiwKICAgICAgICAgICAgICAgICIiLAogICAgICAgICAgICApCiAgICAgICAgKQogICAgICAgIG1lc3NhZ2UgPSBzdHIoCiAgICAgICAgICAgIGdldGF0dHIoCiAgICAgICAgICAgICAgICBmaW5kaW5nLAogICAgICAgICAgICAgICAgIm1lc3NhZ2UiLAogICAgICAgICAgICAgICAgIiIsCiAgICAgICAgICAgICkKICAgICAgICApLmxvd2VyKCkKCiAgICAgICAgcmVtb3ZlID0gKAogICAgICAgICAgICBjb2RlID09ICJQQ1YtREVQLUNVUlJFTlQtU1RBVEUtUkVGRVJFTkNFIgogICAgICAgICAgICBhbmQgIm5leHRfZGVsaXZlcmFibGUiIGluIG1lc3NhZ2UKICAgICAgICAgICAgYW5kICJub25lIiBpbiBtZXNzYWdlCiAgICAgICAgKQoKICAgICAgICBpZiBub3QgcmVtb3ZlOgogICAgICAgICAgICByZXRhaW5lZC5hcHBlbmQoZmluZGluZykKCiAgICByZXN1bHQuZmluZGluZ3NbOl0gPSByZXRhaW5lZAogICAgY29udGV4dC5tZXRhZGF0YVsiZGVwZW5kZW5jaWVzX3ZhbGlkYXRlZCJdID0gKAogICAgICAgIHJlc3VsdC5wYXNzZWQKICAgICkKCiAgICByZXR1cm4gcmVzdWx0CgoKIyA9PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PQojIEVORCBDVFJMLTAxNiBURVJNSU5BTCBERVBFTkRFTkNZIFJFRkVSRU5DRSBDT01QQVRJQklMSVRZCiMgPT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT0K"
).decode("utf-8")


def insert_before_entrypoint(
    text: str,
    block: str,
) -> str:
    marker = 'if __name__ == "__main__":'
    index = text.rfind(marker)

    if index < 0:
        raise RuntimeError(
            "Script entry point was not found."
        )

    return (
        text[:index].rstrip()
        + "\n\n"
        + block.rstrip()
        + "\n\n"
        + text[index:]
    )


def syntax_check(
    text: str,
    filename: str,
) -> None:
    ast.parse(
        text,
        filename=filename,
    )


def main() -> int:
    script_directory = Path(__file__).resolve().parent
    sync_path = script_directory / SYNC_NAME
    validator_path = script_directory / VALIDATOR_NAME

    for path in (
        sync_path,
        validator_path,
    ):
        if not path.is_file():
            print(
                f"ERROR: File not found: {path}",
                file=sys.stderr,
            )
            return 2

    sync_original = sync_path.read_text(
        encoding="utf-8"
    )
    validator_original = validator_path.read_text(
        encoding="utf-8"
    )

    if (
        "CTRL-016 FINAL ACCEPTANCE STATE"
        in sync_original
    ):
        print(
            "ERROR: Synchronizer final-acceptance fix "
            "is already installed.",
            file=sys.stderr,
        )
        return 3

    if (
        "CTRL-016 TERMINAL DEPENDENCY "
        "REFERENCE COMPATIBILITY"
        in validator_original
    ):
        print(
            "ERROR: Validator terminal dependency fix "
            "is already installed.",
            file=sys.stderr,
        )
        return 4

    required_sync_markers = (
        "END_OF_GRAPH_ALIASES",
        "END_OF_GRAPH_ID",
        "def resolve_graph_state(",
    )

    for marker in required_sync_markers:
        if marker not in sync_original:
            print(
                f"ERROR: Missing synchronizer marker: {marker}",
                file=sys.stderr,
            )
            return 5

    required_validator_markers = (
        "def validate_dependencies(",
        "def _is_valid_terminal_execution_state(",
    )

    for marker in required_validator_markers:
        if marker not in validator_original:
            print(
                f"ERROR: Missing validator marker: {marker}",
                file=sys.stderr,
            )
            return 6

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    sync_backup = sync_path.with_name(
        f"{sync_path.name}."
        f"bak_final_acceptance_{timestamp}"
    )

    validator_backup = validator_path.with_name(
        f"{validator_path.name}."
        f"bak_terminal_dependency_{timestamp}"
    )

    sync_updated = insert_before_entrypoint(
        sync_original,
        SYNC_BLOCK,
    )

    validator_updated = insert_before_entrypoint(
        validator_original,
        VALIDATOR_BLOCK,
    )

    try:
        syntax_check(
            sync_updated,
            str(sync_path),
        )
        syntax_check(
            validator_updated,
            str(validator_path),
        )

        shutil.copy2(
            sync_path,
            sync_backup,
        )
        shutil.copy2(
            validator_path,
            validator_backup,
        )

        sync_path.write_text(
            sync_updated,
            encoding="utf-8",
        )
        validator_path.write_text(
            validator_updated,
            encoding="utf-8",
        )

        syntax_check(
            sync_path.read_text(
                encoding="utf-8"
            ),
            str(sync_path),
        )
        syntax_check(
            validator_path.read_text(
                encoding="utf-8"
            ),
            str(validator_path),
        )

    except Exception as error:
        if sync_backup.is_file():
            shutil.copy2(
                sync_backup,
                sync_path,
            )

        if validator_backup.is_file():
            shutil.copy2(
                validator_backup,
                validator_path,
            )

        print(
            "PATCH ROLLED BACK",
            file=sys.stderr,
        )
        print(
            f"Reason: {error}",
            file=sys.stderr,
        )
        return 7

    print("PATCH APPLIED")
    print(f"Updated : {sync_path}")
    print(f"Backup  : {sync_backup}")
    print(f"Updated : {validator_path}")
    print(f"Backup  : {validator_backup}")
    print()
    print("Finalization corrections installed:")
    print(
        "- Accepted final node becomes last_accepted."
    )
    print(
        "- NONE is accepted as terminal dependency sentinel."
    )
    print(
        "- Legacy dependency reference error is removed only "
        "for a verified final graph node."
    )
    print(
        "- Python syntax verified with automatic rollback."
    )
    print()
    print("No YAML or Markdown files were modified.")
    print()
    print("Next safe command:")
    print("python -B finalize_ctrl016.py")
    print()
    print("Then apply with:")
    print(
        "python -B finalize_ctrl016.py "
        "--apply --verbose"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )