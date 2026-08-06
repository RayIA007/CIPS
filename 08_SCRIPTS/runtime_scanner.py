"""
===============================================================================
AUD-006
Runtime Inventory

File:
    runtime_scanner.py

Purpose:
    Inspect the active execution environment and produce a deterministic
    runtime inventory for the Repository Audit System.

Execution policy:
    READ ONLY

Output:
    runtime_inventory.json

===============================================================================
"""

from __future__ import annotations

import importlib.metadata
import os
import platform
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True, slots=True)
class RuntimeToolRecord:
    """
    One executable tool discovered in the active environment.
    """

    name: str
    available: bool
    path: str | None


@dataclass(frozen=True, slots=True)
class InstalledPackageRecord:
    """
    One installed Python distribution.
    """

    name: str
    version: str


@dataclass(frozen=True, slots=True)
class RuntimeInventory:
    """
    Canonical AUD-006 runtime inventory.
    """

    python_version: str
    python_implementation: str
    python_executable: str
    python_prefix: str
    python_base_prefix: str
    virtual_environment_active: bool
    virtual_environment_path: str | None
    operating_system: str
    operating_system_release: str
    operating_system_version: str
    machine: str
    processor: str
    architecture: str
    hostname: str
    current_working_directory: str
    environment_variable_names: tuple[str, ...]
    tools: tuple[RuntimeToolRecord, ...]
    installed_packages: tuple[InstalledPackageRecord, ...]
    metadata: dict[str, str] = field(
        default_factory=dict
    )


class RuntimeScanner:
    """
    Inspect the current runtime without modifying it.
    """

    DEFAULT_TOOLS = (
        "python",
        "python3",
        "pip",
        "pip3",
        "git",
        "ffmpeg",
        "ffprobe",
        "magick",
        "convert",
        "docker",
    )

    def scan(self) -> RuntimeInventory:
        virtual_environment_path = self._virtual_environment_path()

        return RuntimeInventory(
            python_version=platform.python_version(),
            python_implementation=platform.python_implementation(),
            python_executable=str(
                Path(sys.executable).resolve()
            ),
            python_prefix=str(
                Path(sys.prefix).resolve()
            ),
            python_base_prefix=str(
                Path(sys.base_prefix).resolve()
            ),
            virtual_environment_active=(
                sys.prefix != sys.base_prefix
                or virtual_environment_path is not None
            ),
            virtual_environment_path=virtual_environment_path,
            operating_system=platform.system(),
            operating_system_release=platform.release(),
            operating_system_version=platform.version(),
            machine=platform.machine(),
            processor=platform.processor(),
            architecture=platform.architecture()[0],
            hostname=platform.node(),
            current_working_directory=str(
                Path.cwd().resolve()
            ),
            environment_variable_names=tuple(
                sorted(os.environ.keys())
            ),
            tools=self._scan_tools(),
            installed_packages=self._scan_packages(),
            metadata={
                "filesystem_encoding": (
                    sys.getfilesystemencoding()
                ),
                "default_encoding": (
                    sys.getdefaultencoding()
                ),
                "byte_order": sys.byteorder,
            },
        )

    def _scan_tools(
        self,
    ) -> tuple[RuntimeToolRecord, ...]:
        records = []

        for name in self.DEFAULT_TOOLS:
            resolved = shutil.which(name)

            records.append(
                RuntimeToolRecord(
                    name=name,
                    available=resolved is not None,
                    path=resolved,
                )
            )

        return tuple(records)

    def _scan_packages(
        self,
    ) -> tuple[InstalledPackageRecord, ...]:
        packages: list[InstalledPackageRecord] = []

        for distribution in importlib.metadata.distributions():
            name = (
                distribution.metadata.get("Name")
                or distribution.metadata.get("Summary")
                or "UNKNOWN"
            )

            packages.append(
                InstalledPackageRecord(
                    name=str(name),
                    version=str(distribution.version),
                )
            )

        packages.sort(
            key=lambda item: (
                item.name.lower(),
                item.version,
            )
        )

        return tuple(packages)

    @staticmethod
    def _virtual_environment_path() -> str | None:
        configured = (
            os.environ.get("VIRTUAL_ENV")
            or os.environ.get("CONDA_PREFIX")
        )

        if not configured:
            return None

        return str(
            Path(configured).resolve()
        )


def scan_runtime() -> RuntimeInventory:
    """
    Convenience API for AUD-006.
    """

    return RuntimeScanner().scan()