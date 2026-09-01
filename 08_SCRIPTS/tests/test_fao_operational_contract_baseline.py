from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path, PureWindowsPath


SCRIPTS_DIR = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = SCRIPTS_DIR.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from fao_operational_baseline import (  # noqa: E402
    BASELINE_SCHEMA_NAME,
    BASELINE_SCHEMA_VERSION,
    OPERATIONAL_CONTRACT_SCHEMA_NAME,
    OPERATIONAL_CONTRACT_SCHEMA_VERSION,
    _portable_path,
    build_operational_contract,
    inspect_operational_baseline,
)


def test_fao_contract_formalizes_inputs_outputs_gates_and_states() -> None:
    contract = build_operational_contract()

    assert contract.schema_name == OPERATIONAL_CONTRACT_SCHEMA_NAME
    assert contract.schema_version == OPERATIONAL_CONTRACT_SCHEMA_VERSION
    assert contract.phase == "FAO"
    assert tuple(field.name for field in contract.inputs) == (
        "topic",
        "platform",
        "duration_seconds",
        "audience",
        "creative_style",
    )
    assert all(field.required and field.operator_supplied for field in contract.inputs)
    assert {
        "project_workspace",
        "editorial_package",
        "production_manifest",
        "production_acceptance_config",
        "asset_catalog",
        "canonical_subtitles",
        "render_readiness_evidence",
        "final_video",
        "review_decision",
        "acceptance_evidence",
    } == {field.name for field in contract.outputs}

    gates = {gate.name: gate for gate in contract.human_gates}
    assert gates["render_cost_authorization"].single_use is True
    assert gates["render_cost_authorization"].choices == ("authorize", "reject")
    assert gates["final_review"].choices == (
        "approve",
        "request_changes",
        "cancel",
    )
    assert gates["publication_authorization"].enabled_during_fao is False
    assert "ready_for_real_render" in {
        state.name for state in contract.lifecycle_states
    }
    assert "exported" in {
        state.name for state in contract.lifecycle_states if state.terminal
    }
    assert len(contract.current_pipelines) == 2
    official_pipeline = contract.current_pipelines[0]
    assert official_pipeline.name == "official_topic_pipeline"
    assert official_pipeline.entrypoint == "CIPS/run.py:main"
    assert official_pipeline.accepted_input == "interactive menu option 1 plus topic"


def test_fao_contract_preserves_cost_review_and_publication_invariants() -> None:
    contract = build_operational_contract()

    assert "production_manifest_is_provider_neutral" in contract.invariants
    assert "free_tier_is_default" in contract.invariants
    assert (
        "no_credit_use_without_new_explicit_quantified_authorization"
        in contract.invariants
    )
    assert "publication_performed_is_false" in contract.invariants
    assert "publish_during_fao" in contract.prohibited_operator_interventions
    assert "repair_normal_execution_with_llm_assistance" in (
        contract.prohibited_operator_interventions
    )


def test_baseline_serializes_repository_paths_portably() -> None:
    assert _portable_path(PureWindowsPath("CIPS", "run.py")) == "CIPS/run.py"
    assert _portable_path(
        PureWindowsPath("08_SCRIPTS", "tests", "test_example.py")
    ) == "08_SCRIPTS/tests/test_example.py"


def test_baseline_reproducibly_proves_the_current_pipeline_gap_offline() -> None:
    first = inspect_operational_baseline(REPOSITORY_ROOT)
    second = inspect_operational_baseline(REPOSITORY_ROOT)

    assert first == second
    assert first["schema_name"] == BASELINE_SCHEMA_NAME
    assert first["schema_version"] == BASELINE_SCHEMA_VERSION
    assert first["phase"] == "FAO.1"
    assert first["gap_confirmed"] is True
    assert first["bridge_status"] == "missing"

    official_entrypoint = first["official_entrypoint"]
    assert official_entrypoint == {
        "entrypoint": "CIPS/run.py",
        "calls_build_menu": True,
        "instantiates_menu_controller": True,
        "reads_menu_option": True,
        "dispatches_selected_option": True,
        "main_guard_calls_main": True,
    }

    main_menu = first["main_menu"]
    assert main_menu == {
        "path": "08_SCRIPTS/menu.py",
        "declares_new_project_option": True,
        "new_project_option": "1",
    }

    official_pipeline = first["official_topic_pipeline"]
    assert official_pipeline["entrypoint"] == "CIPS/run.py"
    assert official_pipeline["controller"] == "08_SCRIPTS/menu_controller.py"
    assert official_pipeline["dispatches_option_1_to_new_project"] is True
    assert official_pipeline["accepts_topic"] is True
    assert official_pipeline["creates_project_workspace"] is True
    assert official_pipeline["calls_pipeline_engine"] is True
    assert official_pipeline["calls_legacy_media_pipeline"] is True
    assert official_pipeline["invokes_pm9_acceptance"] is False

    pm9 = first["pm9_acceptance_pipeline"]
    assert pm9["accepts_project"] is True
    assert pm9["accepts_topic"] is False
    assert "--project" in pm9["cli_arguments"]

    existing_test = first["existing_fresh_project_test"]
    assert existing_test["copies_prebuilt_editorial_project"] is True
    assert "production_acceptance_config.json" in existing_test[
        "copied_source_paths"
    ]
    assert "research" in existing_test["copied_source_paths"]
    assert "script" in existing_test["copied_source_paths"]

    assert first["safety"] == {
        "inspection_mode": "static_ast",
        "network_called": False,
        "credits_used": 0,
        "render_performed": False,
        "publication_performed": False,
        "files_modified": False,
    }
    assert set(first["source_sha256"]) == {
        "CIPS/run.py",
        "08_SCRIPTS/menu.py",
        "08_SCRIPTS/menu_controller.py",
        "08_SCRIPTS/project_manager.py",
        "08_SCRIPTS/pipeline_engine.py",
        "11_MEDIA_PRODUCTION/media_pipeline.py",
        "08_SCRIPTS/run_pm9_full_production_acceptance.py",
        "08_SCRIPTS/tests/test_pm9_fresh_project_end_to_end.py",
    }
    assert all(len(digest) == 64 for digest in first["source_sha256"].values())


def test_baseline_cli_emits_machine_readable_evidence_without_side_effects() -> None:
    completed = subprocess.run(
        (
            sys.executable,
            str(SCRIPTS_DIR / "fao_operational_baseline.py"),
            "--repository-root",
            str(REPOSITORY_ROOT),
            "--include-contract",
        ),
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["baseline"]["gap_confirmed"] is True
    assert payload["baseline"]["official_entrypoint"]["entrypoint"] == "CIPS/run.py"
    assert payload["baseline"]["main_menu"]["declares_new_project_option"] is True
    assert payload["baseline"]["official_topic_pipeline"][
        "dispatches_option_1_to_new_project"
    ] is True
    assert payload["baseline"]["safety"]["network_called"] is False
    assert payload["baseline"]["safety"]["render_performed"] is False
    assert payload["baseline"]["safety"]["credits_used"] == 0
    assert payload["baseline"]["safety"]["publication_performed"] is False
    assert payload["contract"]["schema_name"] == OPERATIONAL_CONTRACT_SCHEMA_NAME
    assert payload["contract"]["schema_version"] == (
        OPERATIONAL_CONTRACT_SCHEMA_VERSION
    )
