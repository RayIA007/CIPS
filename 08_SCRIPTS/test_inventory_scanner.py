"""
===============================================================================
AUD-009
Test Inventory

File:
    test_inventory_scanner.py

Purpose:
    Discover, classify and evaluate repository test assets.

Execution policy:
    READ ONLY

Output:
    test_inventory.json

===============================================================================
"""

from __future__ import annotations

import os

import ast

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable


TEST_FILE_PREFIXES = (
    "test_",
)

TEST_FILE_SUFFIXES = (
    "_test.py",
)

TEST_DIRECTORIES = {
    "tests",
    "test",
    "testing",
}


# =============================================================================
# RAS WINDOWS PATH NORMALIZATION
# =============================================================================

def _canonical_filesystem_path(path: Path) -> Path:
    """Return a stable absolute path, expanding Windows 8.3 aliases."""
    candidate = Path(os.path.abspath(os.fspath(path)))

    if os.name != "nt":
        return candidate

    try:
        import ctypes

        get_long_path_name = ctypes.windll.kernel32.GetLongPathNameW
        get_long_path_name.argtypes = [
            ctypes.c_wchar_p,
            ctypes.c_wchar_p,
            ctypes.c_uint,
        ]
        get_long_path_name.restype = ctypes.c_uint

        source = str(candidate)
        required = get_long_path_name(source, None, 0)

        if required == 0:
            return candidate

        buffer = ctypes.create_unicode_buffer(required + 1)
        written = get_long_path_name(
            source,
            buffer,
            len(buffer),
        )

        if written == 0:
            return candidate

        return Path(buffer.value)

    except Exception:
        return candidate


def _safe_relative_to(
    path: Path,
    repository_root: Path,
) -> Path:
    """Return a safe repository-relative path after canonicalization."""
    canonical_path = _canonical_filesystem_path(path)
    canonical_root = _canonical_filesystem_path(repository_root)

    relative_text = os.path.relpath(
        str(canonical_path),
        str(canonical_root),
    )

    if (
        relative_text == os.pardir
        or relative_text.startswith(os.pardir + os.sep)
    ):
        raise ValueError(
            f"{str(path)!r} is not inside repository root "
            f"{str(repository_root)!r}"
        )

    return Path(relative_text)


# =============================================================================
# END RAS WINDOWS PATH NORMALIZATION
# =============================================================================


@dataclass(frozen=True, slots=True)
class TestCaseRecord:
    """
    Canonical representation of one discovered test case.
    """

    name: str

    line: int

    asynchronous: bool


@dataclass(frozen=True, slots=True)
class TestModuleRecord:
    """
    Canonical representation of one test module.
    """

    module_name: str

    relative_path: str

    framework: str

    test_cases: tuple[TestCaseRecord, ...]

    fixtures: tuple[str, ...]

    imports: tuple[str, ...]

    syntax_valid: bool

    syntax_error: str | None = None


@dataclass(frozen=True, slots=True)
class TestInventory:
    """
    Canonical AUD-009 inventory.
    """

    modules: tuple[TestModuleRecord, ...]

    total_modules: int

    total_test_cases: int

    frameworks: tuple[str, ...]

    metadata: dict[str, str] = field(
        default_factory=dict
    )


class TestInventoryScanner:
    """
    Scan repository test modules.
    """

    def __init__(
        self,
        repository_root: Path,
    ) -> None:

        self.repository_root = repository_root.resolve()

    # ---------------------------------------------------------------------

    def scan(
        self,
        files: Iterable[Path],
    ) -> TestInventory:

        modules = []

        for file_path in sorted(

            files,

            key=lambda value: str(value),

        ):

            if self._is_test_file(file_path):

                modules.append(

                    self._scan_module(

                        file_path.resolve()

                    )

                )

        frameworks = sorted(

            {

                module.framework

                for module in modules

            }

        )

        return TestInventory(

            modules=tuple(modules),

            total_modules=len(modules),

            total_test_cases=sum(

                len(module.test_cases)

                for module in modules

            ),

            frameworks=tuple(frameworks),

        )

    # ---------------------------------------------------------------------

    def _is_test_file(
        self,
        file_path: Path,
    ) -> bool:

        relative = _safe_relative_to(file_path, self.repository_root)

        if any(

            part.lower() in TEST_DIRECTORIES

            for part in relative.parts

        ):

            return True

        name = file_path.name.lower()

        if name.startswith(TEST_FILE_PREFIXES):

            return True

        if name.endswith(TEST_FILE_SUFFIXES):

            return True

        return False

    # ---------------------------------------------------------------------

    def _scan_module(
        self,
        file_path: Path,
    ) -> TestModuleRecord:

        relative = str(

            _safe_relative_to(file_path, self.repository_root)

        )

        module_name = ".".join(

            _safe_relative_to(file_path, self.repository_root).with_suffix("").parts

        )

        source = file_path.read_text(

            encoding="utf-8"

        )

        try:

            tree = ast.parse(

                source,

                filename=str(file_path),

            )

        except SyntaxError as error:

            return TestModuleRecord(

                module_name=module_name,

                relative_path=relative,

                framework="UNKNOWN",

                test_cases=(),

                fixtures=(),

                imports=(),

                syntax_valid=False,

                syntax_error=str(error),

            )

        imports = []

        framework = "UNKNOWN"

        fixtures = []

        tests = []

        for node in ast.walk(tree):

            if isinstance(node, ast.Import):

                for alias in node.names:

                    imports.append(alias.name)

            elif isinstance(node, ast.ImportFrom):

                imports.append(node.module or "")

            elif isinstance(

                node,

                (

                    ast.FunctionDef,

                    ast.AsyncFunctionDef,

                ),

            ):

                if node.name.startswith("test_"):

                    tests.append(

                        TestCaseRecord(

                            name=node.name,

                            line=node.lineno,

                            asynchronous=isinstance(

                                node,

                                ast.AsyncFunctionDef,

                            ),

                        )

                    )

                for decorator in node.decorator_list:

                    if isinstance(

                        decorator,

                        ast.Name,

                    ):

                        if decorator.id == "fixture":

                            fixtures.append(node.name)

                    elif isinstance(

                        decorator,

                        ast.Attribute,

                    ):

                        if decorator.attr == "fixture":

                            fixtures.append(node.name)

        lowered = {

            value.lower()

            for value in imports

        }

        if "pytest" in lowered:

            framework = "PYTEST"

        elif "unittest" in lowered:

            framework = "UNITTEST"

        elif "nose" in lowered:

            framework = "NOSE"

        return TestModuleRecord(

            module_name=module_name,

            relative_path=relative,

            framework=framework,

            test_cases=tuple(tests),

            fixtures=tuple(sorted(fixtures)),

            imports=tuple(sorted(imports)),

            syntax_valid=True,

        )


def scan_tests(
    *,
    repository_root: Path,
    files: Iterable[Path],
) -> TestInventory:
    """
    Convenience API.
    """

    return TestInventoryScanner(

        repository_root

    ).scan(

        files

    )