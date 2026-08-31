from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


SCRIPTS_DIR = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = SCRIPTS_DIR.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from fao_operational_baseline import (  # noqa: E402
    BASELINE_SCHEMA_NAME,
    BASELINE_SCHEMA_VERSION,
    OPERATIONAL_CONTRACT_SCHEMA_NAME,
    OPERATIONAL_CONTRACT_SCHEMA_VERSION,
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


def test_baseline_reproducibly_proves_the_current_pipeline_gap_offline() -> None:
    first = inspect_operational_baseline(REPOSITORY_ROOT)
    second = inspect_operational_baseline(REPOSITORY_ROOT)

    assert first == second
    assert first["schema_name"] == BASELINE_SCHEMA_NAME
    assert first["schema_version"] == BASELINE_SCHEMA_VERSION
    assert first["phase"] == "FAO.1"
    assert first["gap_confirmed"] is True
    assert first["bridge_status"] == "missing"

    legacy = first["legacy_topic_pipeline"]
    assert legacy["accepts_topic"] is True
    assert legacy["calls_pipeline_engine"] is True
    assert legacy["calls_legacy_media_pipeline"] is True
    assert legacy["invokes_pm9_acceptance"] is False

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
    assert payload["baseline"]["safety"]["network_called"] is False
    assert payload["baseline"]["safety"]["render_performed"] is False
    assert payload["baseline"]["safety"]["credits_used"] == 0
    assert payload["baseline"]["safety"]["publication_performed"] is False
    assert payload["contract"]["schema_name"] == OPERATIONAL_CONTRACT_SCHEMA_NAME
    assert payload["contract"]["schema_version"] == (
        OPERATIONAL_CONTRACT_SCHEMA_VERSION
    )
