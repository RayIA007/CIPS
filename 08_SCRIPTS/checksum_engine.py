"""
===============================================================================
AUD-001
Repository Inventory

File:
    checksum_engine.py

Purpose:
    Canonical SHA-256 checksum engine.

This module computes deterministic file hashes using a streaming
implementation to support very large files without excessive memory
consumption.

===============================================================================
"""

from __future__ import annotations

import hashlib

from pathlib import Path

from audit_exceptions import (
    ChecksumCalculationError,
    UnsupportedHashAlgorithmError,
)

from audit_models import (
    FileHash,
    HashAlgorithm,
)


DEFAULT_BUFFER_SIZE = 1024 * 1024


class ChecksumEngine:
    """
    Streaming checksum calculator.
    """

    def __init__(
        self,
        algorithm: HashAlgorithm = HashAlgorithm.SHA256,
        buffer_size: int = DEFAULT_BUFFER_SIZE,
    ) -> None:

        self.algorithm = algorithm
        self.buffer_size = buffer_size

    # -------------------------------------------------------------------------

    def calculate(
        self,
        file_path: Path,
    ) -> FileHash:

        if self.algorithm is not HashAlgorithm.SHA256:

            raise UnsupportedHashAlgorithmError(
                self.algorithm.value
            )

        digest = hashlib.sha256()

        try:

            with file_path.open(
                "rb"
            ) as stream:

                while True:

                    block = stream.read(
                        self.buffer_size
                    )

                    if not block:

                        break

                    digest.update(block)

        except Exception as error:

            raise ChecksumCalculationError(
                file_path,
                algorithm=self.algorithm.value,
                reason=str(error),
            ) from error

        return FileHash(

            algorithm=self.algorithm,

            value=digest.hexdigest(),

        )


# =============================================================================
# HELPERS
# =============================================================================


def sha256(
    file_path: Path,
) -> FileHash:

    engine = ChecksumEngine()

    return engine.calculate(
        file_path
    )