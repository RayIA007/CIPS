"""
===============================================================================
AUD-004
Dependency Inventory

File:
    dependency_scanner.py

Purpose:
    Build a deterministic dependency inventory from Python module records.

Execution policy:
    READ ONLY

Output:
    dependency_inventory.json

===============================================================================
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from python_module_scanner import PythonModuleRecord


@dataclass(frozen=True, slots=True)
class DependencyEdge:
    """
    Directed dependency from one Python module to another import target.
    """

    source_module: str
    target_module: str
    imported_names: tuple[str, ...]
    relative_level: int
    source_line: int
    is_internal: bool
    is_relative: bool


@dataclass(frozen=True, slots=True)
class ModuleDependencyRecord:
    """
    Dependency summary for one Python module.
    """

    module_name: str
    relative_path: str
    dependencies: tuple[DependencyEdge, ...]
    internal_dependencies: tuple[str, ...]
    external_dependencies: tuple[str, ...]
    unresolved_relative_dependencies: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DependencyInventory:
    """
    Canonical AUD-004 dependency inventory.
    """

    modules: tuple[ModuleDependencyRecord, ...]
    internal_edges: tuple[DependencyEdge, ...]
    external_edges: tuple[DependencyEdge, ...]
    unresolved_edges: tuple[DependencyEdge, ...]
    circular_dependencies: tuple[tuple[str, ...], ...] = field(
        default_factory=tuple
    )


class DependencyScanner:
    """
    Resolve imports collected by AUD-003 into an explicit dependency graph.
    """

    def __init__(
        self,
        repository_root: Path,
    ) -> None:
        self.repository_root = repository_root.resolve()

    def scan(
        self,
        modules: Iterable[PythonModuleRecord],
    ) -> DependencyInventory:
        module_records = tuple(
            sorted(
                modules,
                key=lambda item: item.module_name,
            )
        )

        known_modules = {
            record.module_name
            for record in module_records
            if record.module_name
        }

        module_summaries: list[ModuleDependencyRecord] = []
        internal_edges: list[DependencyEdge] = []
        external_edges: list[DependencyEdge] = []
        unresolved_edges: list[DependencyEdge] = []

        for record in module_records:
            edges = tuple(
                self._resolve_import(
                    source=record,
                    imported_module=import_record.module,
                    imported_names=import_record.names,
                    relative_level=import_record.level,
                    source_line=import_record.line,
                    known_modules=known_modules,
                )
                for import_record in record.imports
            )

            internal_names = tuple(
                sorted(
                    {
                        edge.target_module
                        for edge in edges
                        if edge.is_internal
                    }
                )
            )

            external_names = tuple(
                sorted(
                    {
                        edge.target_module
                        for edge in edges
                        if (
                            not edge.is_internal
                            and not (
                                edge.is_relative
                                and not edge.target_module
                            )
                        )
                    }
                )
            )

            unresolved_names = tuple(
                sorted(
                    {
                        edge.target_module
                        for edge in edges
                        if (
                            edge.is_relative
                            and not edge.is_internal
                        )
                    }
                )
            )

            module_summaries.append(
                ModuleDependencyRecord(
                    module_name=record.module_name,
                    relative_path=record.relative_path,
                    dependencies=edges,
                    internal_dependencies=internal_names,
                    external_dependencies=external_names,
                    unresolved_relative_dependencies=unresolved_names,
                )
            )

            for edge in edges:
                if edge.is_internal:
                    internal_edges.append(edge)
                elif edge.is_relative:
                    unresolved_edges.append(edge)
                else:
                    external_edges.append(edge)

        circular_dependencies = self._find_cycles(
            known_modules=known_modules,
            internal_edges=internal_edges,
        )

        return DependencyInventory(
            modules=tuple(module_summaries),
            internal_edges=tuple(
                sorted(
                    internal_edges,
                    key=self._edge_sort_key,
                )
            ),
            external_edges=tuple(
                sorted(
                    external_edges,
                    key=self._edge_sort_key,
                )
            ),
            unresolved_edges=tuple(
                sorted(
                    unresolved_edges,
                    key=self._edge_sort_key,
                )
            ),
            circular_dependencies=circular_dependencies,
        )

    def _resolve_import(
        self,
        *,
        source: PythonModuleRecord,
        imported_module: str,
        imported_names: tuple[str, ...],
        relative_level: int,
        source_line: int,
        known_modules: set[str],
    ) -> DependencyEdge:
        is_relative = relative_level > 0

        if is_relative:
            target_module = self._resolve_relative_module(
                source_module=source.module_name,
                imported_module=imported_module,
                relative_level=relative_level,
            )
        else:
            target_module = imported_module

        internal_target = self._match_internal_module(
            target_module=target_module,
            known_modules=known_modules,
        )

        return DependencyEdge(
            source_module=source.module_name,
            target_module=(
                internal_target
                or target_module
            ),
            imported_names=imported_names,
            relative_level=relative_level,
            source_line=source_line,
            is_internal=internal_target is not None,
            is_relative=is_relative,
        )

    @staticmethod
    def _resolve_relative_module(
        *,
        source_module: str,
        imported_module: str,
        relative_level: int,
    ) -> str:
        source_parts = source_module.split(".")

        if source_parts:
            source_parts = source_parts[:-1]

        parent_hops = max(
            relative_level - 1,
            0,
        )

        if parent_hops > len(source_parts):
            return imported_module

        base_parts = (
            source_parts[: len(source_parts) - parent_hops]
            if parent_hops
            else source_parts
        )

        if imported_module:
            base_parts.extend(
                imported_module.split(".")
            )

        return ".".join(
            part
            for part in base_parts
            if part
        )

    @staticmethod
    def _match_internal_module(
        *,
        target_module: str,
        known_modules: set[str],
    ) -> str | None:
        if target_module in known_modules:
            return target_module

        candidates = [
            module_name
            for module_name in known_modules
            if target_module.startswith(
                module_name + "."
            )
        ]

        if not candidates:
            return None

        return max(
            candidates,
            key=len,
        )

    @staticmethod
    def _find_cycles(
        *,
        known_modules: set[str],
        internal_edges: list[DependencyEdge],
    ) -> tuple[tuple[str, ...], ...]:
        adjacency: dict[str, set[str]] = {
            module_name: set()
            for module_name in known_modules
        }

        for edge in internal_edges:
            if (
                edge.source_module in adjacency
                and edge.target_module in adjacency
            ):
                adjacency[
                    edge.source_module
                ].add(
                    edge.target_module
                )

        state: dict[str, int] = {
            module_name: 0
            for module_name in known_modules
        }
        stack: list[str] = []
        cycles: set[tuple[str, ...]] = set()

        def visit(module_name: str) -> None:
            state[module_name] = 1
            stack.append(module_name)

            for target in sorted(
                adjacency[module_name]
            ):
                if state[target] == 0:
                    visit(target)
                elif state[target] == 1:
                    start = stack.index(target)
                    cycle = stack[start:] + [target]
                    cycles.add(
                        DependencyScanner._canonical_cycle(
                            cycle
                        )
                    )

            stack.pop()
            state[module_name] = 2

        for module_name in sorted(
            known_modules
        ):
            if state[module_name] == 0:
                visit(module_name)

        return tuple(
            sorted(cycles)
        )

    @staticmethod
    def _canonical_cycle(
        cycle: list[str],
    ) -> tuple[str, ...]:
        if len(cycle) <= 1:
            return tuple(cycle)

        body = cycle[:-1]

        rotations = [
            tuple(
                body[index:]
                + body[:index]
            )
            for index in range(
                len(body)
            )
        ]

        canonical = min(rotations)

        return canonical + (
            canonical[0],
        )

    @staticmethod
    def _edge_sort_key(
        edge: DependencyEdge,
    ) -> tuple[str, int, str]:
        return (
            edge.source_module,
            edge.source_line,
            edge.target_module,
        )


def scan_dependencies(
    *,
    repository_root: Path,
    modules: Iterable[PythonModuleRecord],
) -> DependencyInventory:
    """
    Convenience API for AUD-004.
    """

    return DependencyScanner(
        repository_root
    ).scan(modules)