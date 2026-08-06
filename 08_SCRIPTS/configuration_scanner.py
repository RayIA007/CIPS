"""
===============================================================================
AUD-005
Configuration Inventory

File:
    configuration_scanner.py

Purpose:
    Detect and classify configuration files across the repository.

Execution policy:
    READ ONLY

Output:
    configuration_inventory.json

===============================================================================
"""

from __future__ import annotations

import os

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable


CONFIGURATION_SUFFIXES = {
    ".yaml",
    ".yml",
    ".json",
    ".toml",
    ".ini",
    ".cfg",
    ".conf",
    ".xml",
    ".env",
    ".properties",
}

CONFIGURATION_FILENAMES = {
    ".env",
    ".env.local",
    ".env.development",
    ".env.production",
    ".env.test",
    "pyproject.toml",
    "requirements.txt",
    "requirements-dev.txt",
    "setup.cfg",
    "tox.ini",
    "pytest.ini",
    "mypy.ini",
    "ruff.toml",
    "docker-compose.yml",
    "docker-compose.yaml",
    "Dockerfile",
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
class ConfigurationRecord:
    """
    Canonical representation of one configuration file.
    """

    relative_path: str
    filename: str
    suffix: str
    format: str
    size_bytes: int
    parse_status: str
    top_level_keys: tuple[str, ...] = field(
        default_factory=tuple
    )
    error: str | None = None


@dataclass(frozen=True, slots=True)
class ConfigurationInventory:
    """
    Canonical AUD-005 configuration inventory.
    """

    records: tuple[ConfigurationRecord, ...]
    total_files: int
    valid_files: int
    invalid_files: int
    formats: tuple[str, ...]


class ConfigurationScanner:
    """
    Detect and inspect repository configuration files.
    """

    def __init__(
        self,
        repository_root: Path,
    ) -> None:
        self.repository_root = repository_root.resolve()

    def scan(
        self,
        files: Iterable[Path],
    ) -> ConfigurationInventory:
        records = tuple(
            self._inspect(path.resolve())
            for path in sorted(
                (
                    path
                    for path in files
                    if self._is_configuration_file(path)
                ),
                key=lambda item: str(
                    _safe_relative_to(item, self.repository_root)
                ).lower(),
            )
        )

        valid_files = sum(
            record.parse_status == "VALID"
            for record in records
        )

        invalid_files = sum(
            record.parse_status == "INVALID"
            for record in records
        )

        formats = tuple(
            sorted(
                {
                    record.format
                    for record in records
                }
            )
        )

        return ConfigurationInventory(
            records=records,
            total_files=len(records),
            valid_files=valid_files,
            invalid_files=invalid_files,
            formats=formats,
        )

    def _inspect(
        self,
        file_path: Path,
    ) -> ConfigurationRecord:
        relative_path = str(
            _safe_relative_to(file_path, self.repository_root)
        )

        file_format = self._format_for(
            file_path
        )

        try:
            size_bytes = file_path.stat().st_size
        except OSError:
            size_bytes = 0

        try:
            top_level_keys = self._parse_top_level_keys(
                file_path=file_path,
                file_format=file_format,
            )

            return ConfigurationRecord(
                relative_path=relative_path,
                filename=file_path.name,
                suffix=file_path.suffix.lower(),
                format=file_format,
                size_bytes=size_bytes,
                parse_status="VALID",
                top_level_keys=top_level_keys,
            )

        except Exception as error:
            return ConfigurationRecord(
                relative_path=relative_path,
                filename=file_path.name,
                suffix=file_path.suffix.lower(),
                format=file_format,
                size_bytes=size_bytes,
                parse_status="INVALID",
                error=str(error),
            )

    @staticmethod
    def _is_configuration_file(
        file_path: Path,
    ) -> bool:
        name = file_path.name
        suffix = file_path.suffix.lower()

        if name in CONFIGURATION_FILENAMES:
            return True

        if suffix in CONFIGURATION_SUFFIXES:
            return True

        if name.startswith(".env"):
            return True

        return False

    @staticmethod
    def _format_for(
        file_path: Path,
    ) -> str:
        name = file_path.name.lower()
        suffix = file_path.suffix.lower()

        if name == "dockerfile":
            return "DOCKERFILE"

        if name.startswith(".env"):
            return "ENV"

        mapping = {
            ".yaml": "YAML",
            ".yml": "YAML",
            ".json": "JSON",
            ".toml": "TOML",
            ".ini": "INI",
            ".cfg": "CFG",
            ".conf": "CONF",
            ".xml": "XML",
            ".properties": "PROPERTIES",
            ".txt": "TEXT",
        }

        return mapping.get(
            suffix,
            "UNKNOWN",
        )

    def _parse_top_level_keys(
        self,
        *,
        file_path: Path,
        file_format: str,
    ) -> tuple[str, ...]:
        if file_format == "JSON":
            return self._parse_json_keys(
                file_path
            )

        if file_format == "TOML":
            return self._parse_toml_keys(
                file_path
            )

        if file_format in {
            "INI",
            "CFG",
        }:
            return self._parse_ini_sections(
                file_path
            )

        if file_format == "ENV":
            return self._parse_env_keys(
                file_path
            )

        if file_format == "YAML":
            return self._parse_yaml_keys(
                file_path
            )

        return ()

    @staticmethod
    def _parse_json_keys(
        file_path: Path,
    ) -> tuple[str, ...]:
        payload = json.loads(
            file_path.read_text(
                encoding="utf-8"
            )
        )

        if isinstance(
            payload,
            dict,
        ):
            return tuple(
                sorted(
                    str(key)
                    for key in payload
                )
            )

        return ()

    @staticmethod
    def _parse_toml_keys(
        file_path: Path,
    ) -> tuple[str, ...]:
        import tomllib

        with file_path.open("rb") as stream:
            payload = tomllib.load(stream)

        return tuple(
            sorted(
                str(key)
                for key in payload
            )
        )

    @staticmethod
    def _parse_ini_sections(
        file_path: Path,
    ) -> tuple[str, ...]:
        import configparser

        parser = configparser.ConfigParser()
        parser.read(
            file_path,
            encoding="utf-8",
        )

        return tuple(
            sorted(
                parser.sections()
            )
        )

    @staticmethod
    def _parse_env_keys(
        file_path: Path,
    ) -> tuple[str, ...]:
        keys: set[str] = set()

        for raw_line in file_path.read_text(
            encoding="utf-8"
        ).splitlines():
            line = raw_line.strip()

            if (
                not line
                or line.startswith("#")
                or "=" not in line
            ):
                continue

            key = line.split(
                "=",
                1,
            )[0].strip()

            if key:
                keys.add(key)

        return tuple(
            sorted(keys)
        )

    @staticmethod
    def _parse_yaml_keys(
        file_path: Path,
    ) -> tuple[str, ...]:
        try:
            import yaml  # type: ignore[import-not-found]
        except ImportError:
            return ()

        payload = yaml.safe_load(
            file_path.read_text(
                encoding="utf-8"
            )
        )

        if isinstance(
            payload,
            dict,
        ):
            return tuple(
                sorted(
                    str(key)
                    for key in payload
                )
            )

        return ()


def scan_configurations(
    *,
    repository_root: Path,
    files: Iterable[Path],
) -> ConfigurationInventory:
    """
    Convenience API for AUD-005.
    """

    return ConfigurationScanner(
        repository_root
    ).scan(files)