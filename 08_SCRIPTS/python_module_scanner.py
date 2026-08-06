"""
===============================================================================
AUD-003
Python Module Inventory

File:
    python_module_scanner.py

Purpose:
    Inspect Python source files and extract their structural inventory.

Execution policy:
    READ ONLY

===============================================================================
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from audit_exceptions import FileAccessError


@dataclass(frozen=True, slots=True)
class PythonImportRecord:
    module: str
    names: tuple[str, ...]
    level: int
    line: int


@dataclass(frozen=True, slots=True)
class PythonClassRecord:
    name: str
    bases: tuple[str, ...]
    methods: tuple[str, ...]
    line: int


@dataclass(frozen=True, slots=True)
class PythonFunctionRecord:
    name: str
    is_async: bool
    arguments: tuple[str, ...]
    line: int


@dataclass(frozen=True, slots=True)
class PythonModuleRecord:
    module_name: str
    relative_path: str
    imports: tuple[PythonImportRecord, ...]
    classes: tuple[PythonClassRecord, ...]
    functions: tuple[PythonFunctionRecord, ...]
    exports: tuple[str, ...]
    syntax_valid: bool
    syntax_error: str | None = None
    metadata: dict[str, str] = field(
        default_factory=dict
    )


class PythonModuleScanner:
    """
    Extract structural information from Python source files.
    """

    def __init__(
        self,
        repository_root: Path,
    ) -> None:
        self.repository_root = repository_root.resolve()

    def scan(
        self,
        files: Iterable[Path],
    ) -> list[PythonModuleRecord]:
        records: list[PythonModuleRecord] = []

        for file_path in sorted(
            (
                path.resolve()
                for path in files
                if path.suffix.lower() == ".py"
            ),
            key=lambda path: str(
                path.relative_to(
                    self.repository_root
                )
            ).lower(),
        ):
            records.append(
                self.scan_file(file_path)
            )

        return records

    def scan_file(
        self,
        file_path: Path,
    ) -> PythonModuleRecord:
        try:
            source = file_path.read_text(
                encoding="utf-8"
            )
        except Exception as error:
            raise FileAccessError(
                file_path,
                operation="read Python source",
                reason=str(error),
            ) from error

        relative_path = str(
            file_path.relative_to(
                self.repository_root
            )
        )

        module_name = self._module_name(
            file_path
        )

        try:
            tree = ast.parse(
                source,
                filename=str(file_path),
            )
        except SyntaxError as error:
            return PythonModuleRecord(
                module_name=module_name,
                relative_path=relative_path,
                imports=(),
                classes=(),
                functions=(),
                exports=(),
                syntax_valid=False,
                syntax_error=(
                    f"{error.msg} "
                    f"(line {error.lineno}, "
                    f"column {error.offset})"
                ),
            )

        imports = tuple(
            self._collect_imports(tree)
        )

        classes = tuple(
            self._collect_classes(tree)
        )

        functions = tuple(
            self._collect_functions(tree)
        )

        exports = tuple(
            self._collect_exports(tree)
        )

        return PythonModuleRecord(
            module_name=module_name,
            relative_path=relative_path,
            imports=imports,
            classes=classes,
            functions=functions,
            exports=exports,
            syntax_valid=True,
        )

    def _module_name(
        self,
        file_path: Path,
    ) -> str:
        relative = file_path.relative_to(
            self.repository_root
        )

        parts = list(relative.with_suffix("").parts)

        if parts and parts[-1] == "__init__":
            parts = parts[:-1]

        return ".".join(parts)

    @staticmethod
    def _collect_imports(
        tree: ast.AST,
    ) -> list[PythonImportRecord]:
        records: list[PythonImportRecord] = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    records.append(
                        PythonImportRecord(
                            module=alias.name,
                            names=(
                                alias.asname
                                or alias.name,
                            ),
                            level=0,
                            line=node.lineno,
                        )
                    )

            elif isinstance(node, ast.ImportFrom):
                records.append(
                    PythonImportRecord(
                        module=node.module or "",
                        names=tuple(
                            alias.asname
                            or alias.name
                            for alias in node.names
                        ),
                        level=node.level,
                        line=node.lineno,
                    )
                )

        records.sort(
            key=lambda item: (
                item.line,
                item.module,
                item.names,
            )
        )

        return records

    @staticmethod
    def _collect_classes(
        tree: ast.AST,
    ) -> list[PythonClassRecord]:
        records: list[PythonClassRecord] = []

        for node in tree.body:
            if not isinstance(
                node,
                ast.ClassDef,
            ):
                continue

            methods = tuple(
                child.name
                for child in node.body
                if isinstance(
                    child,
                    (
                        ast.FunctionDef,
                        ast.AsyncFunctionDef,
                    ),
                )
            )

            bases = tuple(
                ast.unparse(base)
                for base in node.bases
            )

            records.append(
                PythonClassRecord(
                    name=node.name,
                    bases=bases,
                    methods=methods,
                    line=node.lineno,
                )
            )

        return records

    @staticmethod
    def _collect_functions(
        tree: ast.AST,
    ) -> list[PythonFunctionRecord]:
        records: list[PythonFunctionRecord] = []

        for node in tree.body:
            if not isinstance(
                node,
                (
                    ast.FunctionDef,
                    ast.AsyncFunctionDef,
                ),
            ):
                continue

            arguments = tuple(
                argument.arg
                for argument in (
                    list(node.args.posonlyargs)
                    + list(node.args.args)
                    + list(node.args.kwonlyargs)
                )
            )

            records.append(
                PythonFunctionRecord(
                    name=node.name,
                    is_async=isinstance(
                        node,
                        ast.AsyncFunctionDef,
                    ),
                    arguments=arguments,
                    line=node.lineno,
                )
            )

        return records

    @staticmethod
    def _collect_exports(
        tree: ast.AST,
    ) -> list[str]:
        for node in tree.body:
            if not isinstance(
                node,
                ast.Assign,
            ):
                continue

            if not any(
                isinstance(target, ast.Name)
                and target.id == "__all__"
                for target in node.targets
            ):
                continue

            if isinstance(
                node.value,
                (
                    ast.List,
                    ast.Tuple,
                    ast.Set,
                ),
            ):
                exports: list[str] = []

                for element in node.value.elts:
                    if isinstance(
                        element,
                        ast.Constant,
                    ) and isinstance(
                        element.value,
                        str,
                    ):
                        exports.append(
                            element.value
                        )

                return exports

        return []


def scan_python_modules(
    *,
    repository_root: Path,
    files: Iterable[Path],
) -> list[PythonModuleRecord]:
    """
    Convenience API for AUD-003.
    """

    return PythonModuleScanner(
        repository_root
    ).scan(files)