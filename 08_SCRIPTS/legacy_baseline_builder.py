"""
===============================================================================
AUD-011
Protected Legacy Baseline

File:
    legacy_baseline_builder.py

Purpose:
    Build a protected legacy baseline candidate from Repository Audit System
    inventories without modifying the existing repository.

Execution policy:
    READ ONLY

Output:
    legacy_baseline_candidate.json

===============================================================================
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True, slots=True)
class BaselineArtifactRecord:
    """
    One artifact registered in the legacy baseline candidate.
    """

    relative_path: str
    size_bytes: int
    sha256: str
    category: str
    status: str


@dataclass(frozen=True, slots=True)
class LegacyBaselineCandidate:
    """
    Canonical AUD-011 protected legacy baseline candidate.
    """

    baseline_id: str
    project_name: str
    repository_root: str
    generated_at: str
    version: str
    git_commit: str | None
    reference_project: str | None
    functional_entrypoints: tuple[str, ...]
    pipeline_modules: tuple[str, ...]
    artifacts: tuple[BaselineArtifactRecord, ...]
    total_files: int
    total_bytes: int
    aggregate_sha256: str
    protection_status: str
    metadata: dict[str, str] = field(default_factory=dict)


class LegacyBaselineBuilder:
    """
    Build a deterministic, read-only baseline candidate.
    """

    def __init__(
        self,
        repository_root: Path,
    ) -> None:
        self.repository_root = repository_root.resolve()

    def build(
        self,
        *,
        repository_inventory,
        entrypoint_inventory,
        pipeline_inventory,
        baseline_id: str = "LEGACY-STABLE-BASELINE",
        version: str = "1.0.0",
        reference_project: Path | None = None,
    ) -> LegacyBaselineCandidate:
        artifacts = tuple(
            sorted(
                (
                    BaselineArtifactRecord(
                        relative_path=record.relative_path,
                        size_bytes=record.metadata.size_bytes,
                        sha256=(
                            record.checksum.value
                            if record.checksum is not None
                            else ""
                        ),
                        category=record.category.value,
                        status=record.status.value,
                    )
                    for record in repository_inventory.files
                ),
                key=lambda item: item.relative_path.lower(),
            )
        )

        aggregate_sha256 = self._aggregate_hash(
            artifacts
        )

        functional_entrypoints = tuple(
            sorted(
                {
                    record.relative_path
                    for record in entrypoint_inventory.records
                }
            )
        )

        pipeline_modules = tuple(
            sorted(
                {
                    record.module_name
                    for record in pipeline_inventory.records
                }
            )
        )

        return LegacyBaselineCandidate(
            baseline_id=baseline_id,
            project_name=repository_inventory.project_name,
            repository_root=str(self.repository_root),
            generated_at=datetime.now(
                timezone.utc
            ).isoformat(),
            version=version,
            git_commit=self._git_commit(),
            reference_project=(
                str(reference_project.resolve())
                if reference_project is not None
                else None
            ),
            functional_entrypoints=functional_entrypoints,
            pipeline_modules=pipeline_modules,
            artifacts=artifacts,
            total_files=len(artifacts),
            total_bytes=sum(
                artifact.size_bytes
                for artifact in artifacts
            ),
            aggregate_sha256=aggregate_sha256,
            protection_status="CANDIDATE",
            metadata={
                "hash_algorithm": "SHA256",
                "execution_policy": "READ_ONLY",
                "deliverable": "AUD-011",
            },
        )

    def write_candidate(
        self,
        *,
        candidate: LegacyBaselineCandidate,
        output_file: Path,
    ) -> None:
        output_file.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        output_file.write_text(
            json.dumps(
                asdict(candidate),
                indent=4,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    def _git_commit(self) -> str | None:
        try:
            result = subprocess.run(
                [
                    "git",
                    "-C",
                    str(self.repository_root),
                    "rev-parse",
                    "HEAD",
                ],
                text=True,
                capture_output=True,
                check=False,
            )

            if result.returncode != 0:
                return None

            value = result.stdout.strip()

            return value or None

        except OSError:
            return None

    @staticmethod
    def _aggregate_hash(
        artifacts: Iterable[BaselineArtifactRecord],
    ) -> str:
        digest = hashlib.sha256()

        for artifact in artifacts:
            digest.update(
                artifact.relative_path.encode(
                    "utf-8"
                )
            )
            digest.update(b"\0")
            digest.update(
                artifact.sha256.encode(
                    "ascii"
                )
            )
            digest.update(b"\0")
            digest.update(
                str(artifact.size_bytes).encode(
                    "ascii"
                )
            )
            digest.update(b"\n")

        return digest.hexdigest()


def build_legacy_baseline_candidate(
    *,
    repository_root: Path,
    repository_inventory,
    entrypoint_inventory,
    pipeline_inventory,
    baseline_id: str = "LEGACY-STABLE-BASELINE",
    version: str = "1.0.0",
    reference_project: Path | None = None,
) -> LegacyBaselineCandidate:
    """
    Convenience API for AUD-011.
    """

    return LegacyBaselineBuilder(
        repository_root
    ).build(
        repository_inventory=repository_inventory,
        entrypoint_inventory=entrypoint_inventory,
        pipeline_inventory=pipeline_inventory,
        baseline_id=baseline_id,
        version=version,
        reference_project=reference_project,
    )