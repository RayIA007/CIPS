#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
===============================================================================
RAS-VAL-002
Repository Audit System Integration Test

File:
    repository_audit_system_integration_test.py

Purpose:
    Execute the complete Repository Audit System workflow from AUD-001
    through AUD-012 against an isolated temporary repository.

Execution policy:
    READ ONLY

===============================================================================
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from audit_models import ScanConfiguration
from filesystem_scanner import discover_repository_files
from inventory_builder import InventoryBuilder
from directory_tree_builder import build_repository_tree
from python_module_scanner import scan_python_modules
from dependency_scanner import scan_dependencies
from configuration_scanner import scan_configurations
from runtime_scanner import scan_runtime
from pipeline_scanner import scan_pipelines
from entrypoint_scanner import scan_entrypoints
from test_inventory_scanner import scan_tests
from compatibility_assessment import assess_repository
from legacy_baseline_builder import build_legacy_baseline_candidate
from baseline_acceptance import (
    AcceptanceStatus,
    assess_baseline_acceptance,
)


def create_fixture(root: Path) -> None:
    """
    Create a deterministic repository fixture for end-to-end validation.
    """

    (root / "src").mkdir(parents=True)
    (root / "tests").mkdir(parents=True)
    (root / "config").mkdir(parents=True)

    (root / "src" / "__init__.py").write_text(
        "",
        encoding="utf-8",
    )

    (root / "src" / "models.py").write_text(
        "class Item:\n    pass\n",
        encoding="utf-8",
    )

    (root / "src" / "production_pipeline.py").write_text(
        """
from .models import Item


class ProductionPipeline:

    def run(self):
        return Item()


def main():
    pipeline = ProductionPipeline()
    pipeline.run()


if __name__ == "__main__":
    main()
""".strip()
        + "\n",
        encoding="utf-8",
    )

    (root / "tests" / "test_pipeline.py").write_text(
        """
import pytest

from src.production_pipeline import ProductionPipeline


@pytest.fixture
def pipeline():
    return ProductionPipeline()


def test_run(pipeline):
    assert pipeline.run() is not None
""".strip()
        + "\n",
        encoding="utf-8",
    )

    (root / "config" / "settings.json").write_text(
        '{"enabled": true}\n',
        encoding="utf-8",
    )

    (root / "README.md").write_text(
        "# Repository Audit System Integration Fixture\n",
        encoding="utf-8",
    )


def main() -> int:
    print("=" * 72)
    print("Repository Audit System Integration Test")
    print("=" * 72)

    with tempfile.TemporaryDirectory(
        prefix="ras_integration_"
    ) as temporary_directory:
        repository_root = (
            Path(temporary_directory)
            / "repository"
        )
        repository_root.mkdir(
            parents=True
        )

        create_fixture(
            repository_root
        )

        configuration = ScanConfiguration(
            repository_root=repository_root,
            recursive=True,
            compute_checksums=True,
            include_hidden=True,
        )

        files = discover_repository_files(
            configuration
        )

        repository_inventory = InventoryBuilder(
            repository_root=repository_root,
            compute_checksums=True,
        ).build(files)

        directory_tree = build_repository_tree(
            repository_root=repository_root,
            files=files,
        )

        python_modules = scan_python_modules(
            repository_root=repository_root,
            files=files,
        )

        dependency_inventory = scan_dependencies(
            repository_root=repository_root,
            modules=python_modules,
        )

        configuration_inventory = scan_configurations(
            repository_root=repository_root,
            files=files,
        )

        runtime_inventory = scan_runtime()

        internal_dependencies = {
            record.module_name: record.internal_dependencies
            for record in dependency_inventory.modules
        }

        external_dependencies = {
            record.module_name: record.external_dependencies
            for record in dependency_inventory.modules
        }

        pipeline_inventory = scan_pipelines(
            repository_root=repository_root,
            modules=python_modules,
            internal_dependencies=internal_dependencies,
            external_dependencies=external_dependencies,
        )

        entrypoint_inventory = scan_entrypoints(
            repository_root=repository_root,
            modules=python_modules,
        )

        test_inventory = scan_tests(
            repository_root=repository_root,
            files=files,
        )

        compatibility = assess_repository(
            repository_inventory=repository_inventory,
            dependency_inventory=dependency_inventory,
            configuration_inventory=configuration_inventory,
            runtime_inventory=runtime_inventory,
            test_inventory=test_inventory,
        )

        baseline_candidate = build_legacy_baseline_candidate(
            repository_root=repository_root,
            repository_inventory=repository_inventory,
            entrypoint_inventory=entrypoint_inventory,
            pipeline_inventory=pipeline_inventory,
        )

        acceptance = assess_baseline_acceptance(
            candidate=baseline_candidate,
            compatibility=compatibility,
        )

        if repository_inventory.total_files < 5:
            raise AssertionError(
                "Repository inventory is incomplete."
            )

        if not directory_tree.children:
            raise AssertionError(
                "Directory tree is empty."
            )

        if len(python_modules) < 3:
            raise AssertionError(
                "Python module inventory is incomplete."
            )

        if not dependency_inventory.internal_edges:
            raise AssertionError(
                "Internal dependency graph was not detected."
            )

        if configuration_inventory.total_files < 1:
            raise AssertionError(
                "Configuration inventory is empty."
            )

        if pipeline_inventory.total_pipelines < 1:
            raise AssertionError(
                "Pipeline inventory is empty."
            )

        if entrypoint_inventory.total_entrypoints < 2:
            raise AssertionError(
                "Entrypoint inventory is incomplete."
            )

        if test_inventory.total_test_cases < 1:
            raise AssertionError(
                "Test inventory is empty."
            )

        if not compatibility.passed:
            raise AssertionError(
                "Compatibility assessment failed."
            )

        if acceptance.status not in {
            AcceptanceStatus.ACCEPTED,
            AcceptanceStatus.ACCEPTED_WITH_WARNINGS,
        }:
            raise AssertionError(
                "Baseline acceptance was rejected."
            )

    print("INTEGRATION TEST PASSED")
    print("AUD-001 through AUD-012 : VALID")
    print("Cross-module contracts  : VALID")
    print("Baseline acceptance     : VALID")
    print("Execution policy        : READ ONLY")
    print("=" * 72)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())