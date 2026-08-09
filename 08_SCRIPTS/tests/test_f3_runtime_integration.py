from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from master_producer import MasterProducer, create_master_producer
from master_producer_models import (
    ContentType,
    MasterProducerConfiguration,
    MonetizationObjective,
    PlatformType,
    ProductionBrief,
)
from metadata_store import MetadataStore
from text_store import TextStore
from workspace_resolver import WorkspaceResolver, WorkspaceSecurityError


def make_brief(*, project_id: str = "project-f34") -> ProductionBrief:
    return ProductionBrief(
        topic="Integración F3.4",
        objective="Validar integración runtime sin LLM",
        audience="equipo técnico",
        platform=PlatformType.YOUTUBE_SHORTS,
        content_type=ContentType.SHORT_VIDEO,
        project_name="Proyecto F3.4",
        project_id=project_id,
        monetization_objective=MonetizationObjective.NONE,
        requires_sources=False,
    )


def make_resolver(tmp_path: Path) -> WorkspaceResolver:
    return WorkspaceResolver(
        projects_root=tmp_path / "04_PROYECTOS",
        outputs_root=tmp_path / "05_OUTPUTS",
    )


def make_config(tmp_path: Path, *, overwrite: bool = False) -> MasterProducerConfiguration:
    return MasterProducerConfiguration(
        persist_outputs=True,
        output_root=str(tmp_path / "legacy_output"),
        create_project_directory=True,
        overwrite_existing=overwrite,
    )


def content_files(root: Path) -> set[str]:
    return {
        path.name
        for path in root.iterdir()
        if path.is_file() and not path.name.endswith(".meta.json")
    }


def test_legacy_context_keeps_existing_output_root_contract(tmp_path: Path) -> None:
    producer = MasterProducer(configuration=make_config(tmp_path))
    context = producer.create_context(make_brief())

    root = Path(context.output_root)
    assert root.parent == tmp_path / "legacy_output"
    assert "f3_workspace" not in context.working_data
    assert producer.workspace_resolver is None
    assert producer.text_store is None
    assert producer.metadata_store is None


def test_legacy_persistence_does_not_create_f3_sidecars(tmp_path: Path) -> None:
    producer = MasterProducer(configuration=make_config(tmp_path))
    result = producer.execute(make_brief(), persist=True)

    assert result.success is True
    root = Path(producer._last_context.output_root)
    assert (root / "brief.json").is_file()
    assert (root / "README.md").is_file()
    assert not list(root.glob("*.meta.json"))


def test_f3_injection_resolves_project_platform_execution_workspace(tmp_path: Path) -> None:
    resolver = make_resolver(tmp_path)
    producer = MasterProducer(
        configuration=make_config(tmp_path),
        workspace_resolver=resolver,
    )
    brief = make_brief()

    context = producer.create_context(brief)
    workspace = context.working_data["f3_workspace"]
    root = Path(context.output_root)

    assert workspace["managed"] is True
    assert workspace["project_id"] == brief.project_id
    assert workspace["platform"] == brief.platform.value
    assert workspace["execution_id"] == context.context_id
    assert Path(workspace["project_root"]) == resolver.projects_root / brief.project_id
    assert root == resolver.outputs_root / brief.platform.value / context.context_id
    assert Path(workspace["execution_root"]) == root
    assert root.is_dir()


def test_factory_exposes_f3_runtime_injection(tmp_path: Path) -> None:
    resolver = make_resolver(tmp_path)
    producer = create_master_producer(workspace_resolver=resolver)

    assert producer.workspace_resolver is resolver
    assert isinstance(producer.text_store, TextStore)
    assert isinstance(producer.metadata_store, MetadataStore)
    assert producer.text_store.workspace_resolver is resolver
    assert producer.metadata_store.workspace_resolver is resolver


def test_stores_can_supply_shared_resolver(tmp_path: Path) -> None:
    resolver = make_resolver(tmp_path)
    text_store = TextStore(resolver)
    metadata_store = MetadataStore(resolver)
    producer = MasterProducer(
        text_store=text_store,
        metadata_store=metadata_store,
    )

    assert producer.workspace_resolver is resolver
    assert producer.text_store is text_store
    assert producer.metadata_store is metadata_store


def test_mismatched_store_resolver_is_rejected(tmp_path: Path) -> None:
    resolver_a = make_resolver(tmp_path / "a")
    resolver_b = make_resolver(tmp_path / "b")

    with pytest.raises(ValueError, match="misma instancia WorkspaceResolver"):
        MasterProducer(
            workspace_resolver=resolver_a,
            text_store=TextStore(resolver_b),
        )


def test_f3_explicit_output_root_must_stay_confined(tmp_path: Path) -> None:
    resolver = make_resolver(tmp_path)
    producer = MasterProducer(workspace_resolver=resolver)

    with pytest.raises(WorkspaceSecurityError):
        producer.create_context(
            make_brief(),
            output_root=str(tmp_path / "outside"),
        )


def test_f3_authorized_output_override_remains_managed(tmp_path: Path) -> None:
    resolver = make_resolver(tmp_path)
    producer = MasterProducer(workspace_resolver=resolver)
    custom_root = resolver.outputs_root / "manual_execution"

    context = producer.create_context(
        make_brief(),
        output_root=str(custom_root),
    )

    assert Path(context.output_root) == custom_root.resolve(strict=False)
    assert context.working_data["f3_workspace"]["managed"] is True
    assert Path(context.working_data["f3_workspace"]["execution_root"]) == custom_root.resolve(strict=False)



def test_f3_reserved_workspace_metadata_cannot_be_overridden(tmp_path: Path) -> None:
    resolver = make_resolver(tmp_path)
    producer = MasterProducer(workspace_resolver=resolver)

    context = producer.create_context(
        make_brief(),
        working_data={"f3_workspace": {"managed": False, "execution_root": "outside"}},
    )

    workspace = context.working_data["f3_workspace"]
    assert workspace["managed"] is True
    assert Path(workspace["execution_root"]) == Path(context.output_root)
    assert Path(context.output_root).is_relative_to(resolver.outputs_root)

def test_f3_execute_persists_bundle_through_specialized_stores(tmp_path: Path) -> None:
    resolver = make_resolver(tmp_path)
    producer = MasterProducer(
        configuration=make_config(tmp_path),
        workspace_resolver=resolver,
    )

    result = producer.execute(make_brief(), persist=True)
    root = Path(producer._last_context.output_root)

    assert result.success is True
    assert content_files(root) == {
        "README.md",
        "brief.json",
        "context.json",
        "plan.json",
        "prompt_package.json",
        "result.json",
    }
    for name in content_files(root):
        sidecar = Path(f"{root / name}.meta.json")
        assert sidecar.is_file(), name
        data = json.loads(sidecar.read_text(encoding="utf-8"))
        assert data["content_hash"]
        assert data["events"]
        assert data["events"][0]["metadata"]["project_id"] == "project-f34"
        assert data["events"][0]["metadata"]["execution_id"] == producer._last_context.context_id


def test_f3_repeating_identical_bundle_does_not_duplicate_physical_files(tmp_path: Path) -> None:
    resolver = make_resolver(tmp_path)
    producer = MasterProducer(
        configuration=make_config(tmp_path),
        workspace_resolver=resolver,
    )
    brief = make_brief()
    result = producer.execute(brief, persist=True)
    context = producer._last_context
    plan = producer._last_plan
    root = Path(context.output_root)
    before = sorted(path.name for path in root.iterdir())

    producer._persist_bundle(brief, context, plan, result)
    after = sorted(path.name for path in root.iterdir())

    assert after == before
    sidecar = json.loads((root / "result.json.meta.json").read_text(encoding="utf-8"))
    assert len(sidecar["events"]) == 2


def test_f3_changed_content_versions_with_hash_and_timestamp(tmp_path: Path) -> None:
    resolver = make_resolver(tmp_path)
    producer = MasterProducer(
        configuration=make_config(tmp_path, overwrite=False),
        workspace_resolver=resolver,
    )
    brief = make_brief()
    result = producer.execute(brief, persist=True)
    context = producer._last_context
    plan = producer._last_plan
    root = Path(context.output_root)
    original_result = (root / "result.json").read_text(encoding="utf-8")

    result.summary = "Resumen modificado para nueva versión F3.4"
    producer._persist_bundle(brief, context, plan, result)

    versioned_results = [
        path
        for path in root.glob("result.*.json")
        if not path.name.endswith(".meta.json")
    ]
    assert len(versioned_results) == 1
    versioned = versioned_results[0]
    parts = versioned.name.split(".")
    assert parts[0] == "result"
    assert len(parts[1]) == 12
    assert parts[-1] == "json"
    versioned_content = versioned.read_bytes()
    import hashlib
    assert parts[1] == hashlib.sha256(versioned_content).hexdigest()[:12]
    assert b"Resumen modificado para nueva versi" in versioned_content
    assert (Path(f"{versioned}.meta.json")).is_file()
    assert (root / "result.json").read_text(encoding="utf-8") == original_result

    producer._persist_bundle(brief, context, plan, result)
    repeated_results = [
        path
        for path in root.glob("result.*.json")
        if not path.name.endswith(".meta.json")
    ]
    assert repeated_results == [versioned]


def test_f3_overwrite_policy_replaces_without_version_file(tmp_path: Path) -> None:
    resolver = make_resolver(tmp_path)
    producer = MasterProducer(
        configuration=make_config(tmp_path, overwrite=True),
        workspace_resolver=resolver,
    )
    brief = make_brief()
    result = producer.execute(brief, persist=True)
    context = producer._last_context
    plan = producer._last_plan
    root = Path(context.output_root)

    result.summary = "Resumen reemplazado explícitamente"
    producer._persist_bundle(brief, context, plan, result)

    assert "Resumen reemplazado explícitamente" in (root / "result.json").read_text(encoding="utf-8")
    assert not [
        path
        for path in root.glob("result.*.json")
        if not path.name.endswith(".meta.json")
    ]


def test_export_summary_public_contract_still_writes_utf8(tmp_path: Path) -> None:
    producer = MasterProducer(configuration=make_config(tmp_path))
    brief = make_brief()
    context = producer.create_context(brief)
    plan = producer.build_production_plan(brief, context)
    destination = tmp_path / "manual" / "summary.md"

    returned = producer.export_summary(brief, plan, destination)

    assert returned == destination
    assert destination.is_file()
    assert destination.read_bytes().startswith(b"# Proyecto F3.4")
    assert not destination.read_bytes().startswith(b"\xef\xbb\xbf")
