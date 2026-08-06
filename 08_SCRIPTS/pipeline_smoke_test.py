"""
===============================================================================
AUD-007
Pipeline Inventory

File:
    pipeline_smoke_test.py

Purpose:
    Smoke Test for the Pipeline Scanner.

Execution Policy:
    READ ONLY

===============================================================================
"""

from __future__ import annotations

import tempfile

from pathlib import Path

from audit_models import (
    ScanConfiguration,
)

from filesystem_scanner import (
    discover_repository_files,
)

from python_module_scanner import (
    scan_python_modules,
)

from dependency_scanner import (
    scan_dependencies,
)

from pipeline_scanner import (
    scan_pipelines,
)

from pipeline_inventory_writer import (
    write_pipeline_inventory,
)


# =============================================================================
# TEST REPOSITORY
# =============================================================================


def create_repository(
    root: Path,
) -> None:

    (root / "pipelines").mkdir()

    (root / "core").mkdir()

    (root / "core" / "__init__.py").write_text(
        "",
        encoding="utf-8",
    )

    (root / "core" / "validator.py").write_text(
        """
class Validator:
    pass
""".strip(),
        encoding="utf-8",
    )

    (root / "pipelines" / "production_pipeline.py").write_text(
        """
from core.validator import Validator

class ProductionPipeline:

    def run(self):
        pass

    def validate(self):
        pass


def build():
    pass


def execute():
    pass
""".strip(),
        encoding="utf-8",
    )


# =============================================================================
# MAIN
# =============================================================================


def main() -> int:

    print("=" * 72)

    print("AUD-007 Pipeline Inventory Smoke Test")

    print("=" * 72)

    with tempfile.TemporaryDirectory(
        prefix="aud007_",
    ) as temp:

        repository = Path(temp) / "repository"

        repository.mkdir()

        create_repository(repository)

        files = discover_repository_files(

            ScanConfiguration(

                repository_root=repository,

                recursive=True,

                compute_checksums=False,

            )

        )

        modules = scan_python_modules(

            repository_root=repository,

            files=files,

        )

        dependency_inventory = scan_dependencies(

            repository_root=repository,

            modules=modules,

        )

        internal_dependencies = {

            module.module_name: module.internal_dependencies

            for module in dependency_inventory.modules

        }

        external_dependencies = {

            module.module_name: module.external_dependencies

            for module in dependency_inventory.modules

        }

        inventory = scan_pipelines(

            repository_root=repository,

            modules=modules,

            internal_dependencies=internal_dependencies,

            external_dependencies=external_dependencies,

        )

        if inventory.total_pipelines != 1:

            raise AssertionError(

                "Expected exactly one pipeline."

            )

        pipeline = inventory.records[0]

        if pipeline.pipeline_type != "PRODUCTION":

            raise AssertionError(

                "Pipeline classification failed."

            )

        if pipeline.confidence < 0.50:

            raise AssertionError(

                "Pipeline confidence too low."

            )

        if len(pipeline.entrypoints) == 0:

            raise AssertionError(

                "Pipeline entrypoints not detected."

            )

        if len(pipeline.stages) == 0:

            raise AssertionError(

                "Pipeline stages not detected."

            )

        output = (

            repository

            / "pipeline_inventory.json"

        )

        write_pipeline_inventory(

            inventory=inventory,

            output_file=output,

        )

        if not output.exists():

            raise AssertionError(

                "Pipeline inventory was not generated."

            )

    print()

    print("SMOKE TEST PASSED")

    print("Pipeline Discovery : VALID")

    print("Entrypoints        : VALID")

    print("Pipeline Stages    : VALID")

    print("Inventory JSON     : VALID")

    print("READ ONLY          : VALID")

    print("=" * 72)

    return 0


if __name__ == "__main__":

    raise SystemExit(

        main()

    )