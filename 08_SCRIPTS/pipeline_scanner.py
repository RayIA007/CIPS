"""
===============================================================================
AUD-007
Pipeline Inventory

File:
    pipeline_scanner.py

Purpose:
    Detect and inventory pipeline-oriented Python modules in the repository.

Execution policy:
    READ ONLY

Output:
    pipeline_inventory.json

===============================================================================
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from python_module_scanner import PythonModuleRecord


PIPELINE_NAME_HINTS = (
    "pipeline",
    "workflow",
    "orchestrator",
    "runner",
    "engine",
    "executor",
    "scheduler",
)

PIPELINE_SYMBOL_HINTS = (
    "pipeline",
    "workflow",
    "orchestrator",
    "runner",
    "run",
    "execute",
    "process",
    "build",
    "validate",
)


@dataclass(frozen=True, slots=True)
class PipelineStageRecord:
    """
    One discovered stage-like symbol within a pipeline module.
    """

    name: str
    symbol_type: str
    line: int


@dataclass(frozen=True, slots=True)
class PipelineRecord:
    """
    Canonical representation of one pipeline-oriented module.
    """

    module_name: str
    relative_path: str
    pipeline_type: str
    entrypoints: tuple[str, ...]
    stages: tuple[PipelineStageRecord, ...]
    internal_dependencies: tuple[str, ...]
    external_dependencies: tuple[str, ...]
    confidence: float
    evidence: tuple[str, ...] = field(
        default_factory=tuple
    )


@dataclass(frozen=True, slots=True)
class PipelineInventory:
    """
    Canonical AUD-007 pipeline inventory.
    """

    records: tuple[PipelineRecord, ...]
    total_pipelines: int
    pipeline_types: tuple[str, ...]


class PipelineScanner:
    """
    Identify pipeline-oriented modules from AUD-003 and AUD-004 data.
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
        internal_dependencies: dict[str, tuple[str, ...]] | None = None,
        external_dependencies: dict[str, tuple[str, ...]] | None = None,
    ) -> PipelineInventory:
        internal_dependencies = internal_dependencies or {}
        external_dependencies = external_dependencies or {}

        records: list[PipelineRecord] = []

        for module in modules:
            record = self._classify_module(
                module=module,
                internal_dependencies=internal_dependencies.get(
                    module.module_name,
                    (),
                ),
                external_dependencies=external_dependencies.get(
                    module.module_name,
                    (),
                ),
            )

            if record is not None:
                records.append(record)

        records.sort(
            key=lambda item: (
                item.pipeline_type,
                item.module_name,
            )
        )

        pipeline_types = tuple(
            sorted(
                {
                    record.pipeline_type
                    for record in records
                }
            )
        )

        return PipelineInventory(
            records=tuple(records),
            total_pipelines=len(records),
            pipeline_types=pipeline_types,
        )

    def _classify_module(
        self,
        *,
        module: PythonModuleRecord,
        internal_dependencies: tuple[str, ...],
        external_dependencies: tuple[str, ...],
    ) -> PipelineRecord | None:
        evidence: list[str] = []
        score = 0.0

        module_name_lower = module.module_name.lower()
        path_lower = module.relative_path.lower()

        if any(
            hint in module_name_lower
            or hint in path_lower
            for hint in PIPELINE_NAME_HINTS
        ):
            score += 0.45
            evidence.append(
                "module_or_path_name_matches_pipeline_hint"
            )

        entrypoints = self._entrypoints(module)

        if entrypoints:
            score += 0.25
            evidence.append(
                "contains_pipeline_entrypoint"
            )

        stages = self._stages(module)

        if stages:
            score += min(
                0.20,
                0.05 * len(stages),
            )
            evidence.append(
                "contains_stage_like_symbols"
            )

        if internal_dependencies:
            score += 0.05
            evidence.append(
                "has_internal_dependencies"
            )

        if external_dependencies:
            score += 0.05
            evidence.append(
                "has_external_dependencies"
            )

        if score < 0.45:
            return None

        return PipelineRecord(
            module_name=module.module_name,
            relative_path=module.relative_path,
            pipeline_type=self._pipeline_type(
                module
            ),
            entrypoints=entrypoints,
            stages=stages,
            internal_dependencies=tuple(
                sorted(
                    set(internal_dependencies)
                )
            ),
            external_dependencies=tuple(
                sorted(
                    set(external_dependencies)
                )
            ),
            confidence=round(
                min(score, 1.0),
                2,
            ),
            evidence=tuple(evidence),
        )

    @staticmethod
    def _entrypoints(
        module: PythonModuleRecord,
    ) -> tuple[str, ...]:
        names: set[str] = set()

        for function in module.functions:
            if function.name.lower() in {
                "main",
                "run",
                "execute",
                "start",
                "process",
                "build",
            }:
                names.add(
                    function.name
                )

        for class_record in module.classes:
            for method in class_record.methods:
                if method.lower() in {
                    "run",
                    "execute",
                    "start",
                    "process",
                    "build",
                    "validate",
                }:
                    names.add(
                        f"{class_record.name}.{method}"
                    )

        return tuple(
            sorted(names)
        )

    @staticmethod
    def _stages(
        module: PythonModuleRecord,
    ) -> tuple[PipelineStageRecord, ...]:
        stages: list[PipelineStageRecord] = []

        for function in module.functions:
            if any(
                hint in function.name.lower()
                for hint in PIPELINE_SYMBOL_HINTS
            ):
                stages.append(
                    PipelineStageRecord(
                        name=function.name,
                        symbol_type=(
                            "ASYNC_FUNCTION"
                            if function.is_async
                            else "FUNCTION"
                        ),
                        line=function.line,
                    )
                )

        for class_record in module.classes:
            if any(
                hint in class_record.name.lower()
                for hint in PIPELINE_SYMBOL_HINTS
            ):
                stages.append(
                    PipelineStageRecord(
                        name=class_record.name,
                        symbol_type="CLASS",
                        line=class_record.line,
                    )
                )

            for method in class_record.methods:
                if any(
                    hint in method.lower()
                    for hint in PIPELINE_SYMBOL_HINTS
                ):
                    stages.append(
                        PipelineStageRecord(
                            name=(
                                f"{class_record.name}.{method}"
                            ),
                            symbol_type="METHOD",
                            line=class_record.line,
                        )
                    )

        stages.sort(
            key=lambda item: (
                item.line,
                item.name,
            )
        )

        return tuple(stages)

    @staticmethod
    def _pipeline_type(
        module: PythonModuleRecord,
    ) -> str:
        value = (
            module.module_name
            + " "
            + module.relative_path
        ).lower()

        mapping = (
            ("validation", "VALIDATION"),
            ("render", "RENDER"),
            ("publication", "PUBLICATION"),
            ("prompt", "PROMPT"),
            ("research", "RESEARCH"),
            ("media", "MEDIA"),
            ("voice", "VOICE"),
            ("subtitle", "SUBTITLE"),
            ("analytics", "ANALYTICS"),
            ("production", "PRODUCTION"),
            ("pipeline", "GENERAL"),
        )

        for token, pipeline_type in mapping:
            if token in value:
                return pipeline_type

        return "GENERAL"


def scan_pipelines(
    *,
    repository_root: Path,
    modules: Iterable[PythonModuleRecord],
    internal_dependencies: dict[str, tuple[str, ...]] | None = None,
    external_dependencies: dict[str, tuple[str, ...]] | None = None,
) -> PipelineInventory:
    """
    Convenience API for AUD-007.
    """

    return PipelineScanner(
        repository_root
    ).scan(
        modules=modules,
        internal_dependencies=internal_dependencies,
        external_dependencies=external_dependencies,
    )