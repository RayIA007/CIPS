"""
===============================================================================
AUD-001
Repository Inventory

File:
    metadata_collector.py

Purpose:
    Collect portable filesystem metadata for repository files.

This module performs read-only metadata inspection and converts native
filesystem information into the canonical FileMetadata model.

===============================================================================
"""

from __future__ import annotations

import os
import stat
from datetime import datetime, timezone
from pathlib import Path

from audit_exceptions import MetadataCollectionError
from audit_models import FileMetadata


class MetadataCollector:
    """
    Collect canonical metadata for one repository file.
    """

    def collect(
        self,
        file_path: Path,
    ) -> FileMetadata:
        """
        Read filesystem metadata without modifying the target file.
        """

        try:
            file_stat = file_path.stat()

            extension = file_path.suffix.lower()
            owner = self._resolve_owner(
                file_path=file_path,
                user_id=getattr(
                    file_stat,
                    "st_uid",
                    None,
                ),
            )

            readonly = not os.access(
                file_path,
                os.W_OK,
            )

            executable = self._is_executable(
                file_path=file_path,
                mode=file_stat.st_mode,
            )

            return FileMetadata(
                size_bytes=file_stat.st_size,
                created=self._to_datetime(
                    self._created_timestamp(
                        file_stat
                    )
                ),
                modified=self._to_datetime(
                    file_stat.st_mtime
                ),
                accessed=self._to_datetime(
                    file_stat.st_atime
                ),
                extension=extension,
                suffix=extension,
                owner=owner,
                readonly=readonly,
                executable=executable,
            )

        except MetadataCollectionError:
            raise

        except Exception as error:
            raise MetadataCollectionError(
                file_path,
                reason=str(error),
            ) from error

    # -------------------------------------------------------------------------
    # INTERNAL HELPERS
    # -------------------------------------------------------------------------

    @staticmethod
    def _created_timestamp(
        file_stat: os.stat_result,
    ) -> float:
        """
        Return the most suitable creation timestamp available.

        Windows exposes st_ctime as creation time. Some Unix filesystems
        expose st_birthtime. When birth time is unavailable, st_ctime is
        used as the closest portable fallback.
        """

        birth_time = getattr(
            file_stat,
            "st_birthtime",
            None,
        )

        if birth_time is not None:
            return float(birth_time)

        return float(file_stat.st_ctime)

    @staticmethod
    def _to_datetime(
        timestamp: float,
    ) -> datetime:
        """
        Convert a native timestamp to an explicit UTC datetime.
        """

        return datetime.fromtimestamp(
            timestamp,
            tz=timezone.utc,
        )

    @staticmethod
    def _is_executable(
        *,
        file_path: Path,
        mode: int,
    ) -> bool:
        """
        Detect executable files portably.

        On POSIX, permission bits are authoritative.
        On Windows, executable extensions are also considered.
        """

        if stat.S_ISREG(mode) and (
            mode
            & (
                stat.S_IXUSR
                | stat.S_IXGRP
                | stat.S_IXOTH
            )
        ):
            return True

        return file_path.suffix.lower() in {
            ".exe",
            ".bat",
            ".cmd",
            ".com",
            ".ps1",
            ".sh",
        }

    @staticmethod
    def _resolve_owner(
        *,
        file_path: Path,
        user_id: int | None,
    ) -> str | None:
        """
        Resolve the filesystem owner when the platform supports it.
        """

        try:
            if os.name == "nt":
                return MetadataCollector._resolve_windows_owner(
                    file_path
                )

            if user_id is None:
                return None

            import pwd

            return pwd.getpwuid(
                user_id
            ).pw_name

        except Exception:
            return None

    @staticmethod
    def _resolve_windows_owner(
        file_path: Path,
    ) -> str | None:
        """
        Resolve a Windows owner using pywin32 when available.

        AUD-001 does not require optional dependencies, so absence of
        pywin32 returns None instead of failing the inventory.
        """

        try:
            import win32security  # type: ignore[import-not-found]

            security_descriptor = (
                win32security.GetFileSecurity(
                    str(file_path),
                    win32security.OWNER_SECURITY_INFORMATION,
                )
            )

            owner_sid = (
                security_descriptor.GetSecurityDescriptorOwner()
            )

            account_name, domain_name, _ = (
                win32security.LookupAccountSid(
                    None,
                    owner_sid,
                )
            )

            if domain_name:
                return (
                    f"{domain_name}\\{account_name}"
                )

            return account_name

        except Exception:
            return None


# =============================================================================
# CONVENIENCE API
# =============================================================================


def collect_file_metadata(
    file_path: Path,
) -> FileMetadata:
    """
    Collect canonical metadata for one file.
    """

    return MetadataCollector().collect(
        file_path
    )