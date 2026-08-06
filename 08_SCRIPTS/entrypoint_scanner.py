"""
===============================================================================
AUD-008
Entrypoint Inventory

File:
    entrypoint_scanner.py

Purpose:
    Detect executable entrypoints across Python modules and scripts.

Execution policy:
    READ ONLY

Output:
    entrypoint_inventory.json

===============================================================================
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from python_module_scanner import PythonModuleRecord


@dataclass(frozen=True, slots=True)
class EntrypointRecord:
    """
    Canonical representation of one executable entrypoint.
    """

    module_name: str
    relative_path: str
    entrypoint_type: str
    symbol: str
    line: int
    executable_script: bool
    invocation_hint: str
    evidence: tuple[str, ...] = field(
        default_factory=tuple
    )


@dataclass(frozen=True, slots=True)
class EntrypointInventory:
    """
    Canonical AUD-008 entrypoint inventory.
    """

    records: tuple[EntrypointRecord, ...]
    total_entrypoints: int
    entrypoint_types: tuple[str, ...]


class EntrypointScanner:
    """
    Detect CLI, script and callable entrypoints.
    """

    def __init__(
        self,
        repository_root: Path,
    ) -> None:
        self.repository_root = repository_root.resolve()

    def scan(
        self,
        *,
        modules: Iterable[PythonModuleRecord],
    ) -> EntrypointInventory:
        records: list[EntrypointRecord] = []

        for module in modules:
            records.extend(
                self._scan_module(module)
            )

        records.sort(
            key=lambda item: (
                item.relative_path.lower(),
                item.line,
                item.symbol,
            )
        )

        return EntrypointInventory(
            records=tuple(records),
            total_entrypoints=len(records),
            entrypoint_types=tuple(
                sorted(
                    {
                        record.entrypoint_type
                        for record in records
                    }
                )
            ),
        )

    def _scan_module(
        self,
        module: PythonModuleRecord,
    ) -> list[EntrypointRecord]:
        file_path = (
            self.repository_root
            / module.relative_path
        )

        try:
            source = file_path.read_text(
                encoding="utf-8"
            )
            tree = ast.parse(
                source,
                filename=str(file_path),
            )
        except Exception:
            return []

        records: list[EntrypointRecord] = []
        executable_script = self._is_executable_script(
            file_path
        )

        for node in tree.body:
            if isinstance(
                node,
                (
                    ast.FunctionDef,
                    ast.AsyncFunctionDef,
                ),
            ) and node.name == "main":
                records.append(
                    EntrypointRecord(
                        module_name=module.module_name,
                        relative_path=module.relative_path,
                        entrypoint_type="MAIN_FUNCTION",
                        symbol="main",
                        line=node.lineno,
                        executable_script=executable_script,
                        invocation_hint=(
                            f"python -m {module.module_name}"
                            if module.module_name
                            else f"python {module.relative_path}"
                        ),
                        evidence=(
                            "top_level_main_function",
                        ),
                    )
                )

            if isinstance(
                node,
                ast.If,
            ) and self._is_name_main_guard(node):
                records.append(
                    EntrypointRecord(
                        module_name=module.module_name,
                        relative_path=module.relative_path,
                        entrypoint_type="MAIN_GUARD",
                        symbol='if __name__ == "__main__"',
                        line=node.lineno,
                        executable_script=True,
                        invocation_hint=(
                            f"python {module.relative_path}"
                        ),
                        evidence=(
                            "python_main_guard",
                        ),
                    )
                )

        for class_record in module.classes:
            class_name = class_record.name.lower()

            if class_name.endswith(
                (
                    "cli",
                    "application",
                    "server",
                    "service",
                    "runner",
                )
            ):
                records.append(
                    EntrypointRecord(
                        module_name=module.module_name,
                        relative_path=module.relative_path,
                        entrypoint_type="APPLICATION_CLASS",
                        symbol=class_record.name,
                        line=class_record.line,
                        executable_script=executable_script,
                        invocation_hint=(
                            f"import {module.module_name}"
                        ),
                        evidence=(
                            "entrypoint_like_class_name",
                        ),
                    )
                )

        return records

    @staticmethod
    def _is_name_main_guard(
        node: ast.If,
    ) -> bool:
        test = node.test

        if not isinstance(
            test,
            ast.Compare,
        ):
            return False

        if not isinstance(
            test.left,
            ast.Name,
        ):
            return False

        if test.left.id != "__name__":
            return False

        if len(test.comparators) != 1:
            return False

        comparator = test.comparators[0]

        return (
            isinstance(
                comparator,
                ast.Constant,
            )
            and comparator.value == "__main__"
        )

    @staticmethod
    def _is_executable_script(
        file_path: Path,
    ) -> bool:
        try:
            first_line = file_path.open(
                "r",
                encoding="utf-8",
            ).readline()

            if first_line.startswith("#!"):
                return True

            return file_path.suffix.lower() in {
                ".py",
                ".pyw",
            }

        except Exception:
            return False


def scan_entrypoints(
    *,
    repository_root: Path,
    modules: Iterable[PythonModuleRecord],
) -> EntrypointInventory:
    """
    Convenience API for AUD-008.
    """

    return EntrypointScanner(
        repository_root
    ).scan(
        modules=modules
    )