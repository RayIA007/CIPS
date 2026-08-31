"""Formaliza el contrato FAO y diagnostica la brecha operativa actual.

El diagnóstico es deliberadamente estático: sólo analiza archivos Python del
repositorio. No importa los puntos de entrada inspeccionados, no usa red, no
invoca proveedores, no renderiza y no modifica el workspace.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Sequence


OPERATIONAL_CONTRACT_SCHEMA_NAME = "cips.fao.operational_contract"
OPERATIONAL_CONTRACT_SCHEMA_VERSION = "1.0"
BASELINE_SCHEMA_NAME = "cips.fao.operational_baseline"
BASELINE_SCHEMA_VERSION = "1.0"

PM9_ENTRYPOINT = Path("08_SCRIPTS/run_pm9_full_production_acceptance.py")
LEGACY_ENTRYPOINT = Path("08_SCRIPTS/menu_controller.py")
FRESH_PROJECT_TEST = Path("08_SCRIPTS/tests/test_pm9_fresh_project_end_to_end.py")


@dataclass(frozen=True)
class OperationalField:
    """Describe una entrada o salida estable del contrato operativo."""

    name: str
    required: bool
    operator_supplied: bool
    description: str


@dataclass(frozen=True)
class HumanGate:
    """Describe una decisión que CIPS no puede tomar por el operador."""

    name: str
    timing: str
    choices: tuple[str, ...]
    enabled_during_fao: bool
    single_use: bool
    description: str


@dataclass(frozen=True)
class LifecycleState:
    """Describe un estado observable del flujo unificado objetivo."""

    name: str
    checkpointed: bool
    terminal: bool
    description: str


@dataclass(frozen=True)
class PipelineBoundary:
    """Documenta uno de los puntos de entrada existentes en el baseline."""

    name: str
    entrypoint: str
    accepted_input: str
    produced_output: str
    missing_boundary: str


@dataclass(frozen=True)
class FaoOperationalContract:
    """Contrato provider-neutral de la experiencia operativa objetivo."""

    schema_name: str
    schema_version: str
    phase: str
    objective: str
    inputs: tuple[OperationalField, ...]
    outputs: tuple[OperationalField, ...]
    human_gates: tuple[HumanGate, ...]
    lifecycle_states: tuple[LifecycleState, ...]
    current_pipelines: tuple[PipelineBoundary, ...]
    allowed_operator_interventions: tuple[str, ...]
    prohibited_operator_interventions: tuple[str, ...]
    invariants: tuple[str, ...]
    master_close_criteria: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        """Devuelve una representación JSON estable del contrato."""

        return asdict(self)


def build_operational_contract() -> FaoOperationalContract:
    """Construye la versión 1.0 del contrato operativo de FAO."""

    return FaoOperationalContract(
        schema_name=OPERATIONAL_CONTRACT_SCHEMA_NAME,
        schema_version=OPERATIONAL_CONTRACT_SCHEMA_VERSION,
        phase="FAO",
        objective=(
            "Convertir un tema nuevo en un MP4 revisable mediante una entrada "
            "oficial, sin edición manual de archivos ni asistencia operativa "
            "del LLM."
        ),
        inputs=(
            OperationalField(
                "topic",
                True,
                True,
                "Tema nuevo elegido por el operador.",
            ),
            OperationalField(
                "platform",
                True,
                True,
                "Plataforma objetivo de la producción.",
            ),
            OperationalField(
                "duration_seconds",
                True,
                True,
                "Duración objetivo solicitada.",
            ),
            OperationalField(
                "audience",
                True,
                True,
                "Audiencia objetivo del contenido.",
            ),
            OperationalField(
                "creative_style",
                True,
                True,
                "Preferencias creativas solicitadas por la interfaz.",
            ),
        ),
        outputs=(
            OperationalField(
                "project_workspace",
                True,
                False,
                "Workspace nuevo y reanudable del proyecto.",
            ),
            OperationalField(
                "editorial_package",
                True,
                False,
                "Investigación, verificación, guion, storyboard, narración y SEO.",
            ),
            OperationalField(
                "production_manifest",
                True,
                False,
                "ProductionManifest provider-neutral derivado del paquete editorial.",
            ),
            OperationalField(
                "production_acceptance_config",
                True,
                False,
                "Configuración de activos y aceptación derivada sin JSON manual.",
            ),
            OperationalField(
                "asset_catalog",
                True,
                False,
                "Catálogo F3 con hashes, procedencia, licencias y costos.",
            ),
            OperationalField(
                "canonical_subtitles",
                True,
                False,
                "Subtítulos ligados al texto aprobado y al audio conforme.",
            ),
            OperationalField(
                "render_readiness_evidence",
                True,
                False,
                "Evidencia de preparación y costo antes de cualquier render.",
            ),
            OperationalField(
                "final_video",
                True,
                False,
                "MP4 revisable producido sólo tras una autorización de costo válida.",
            ),
            OperationalField(
                "review_decision",
                True,
                True,
                "Decisión humana persistida mediante F7.",
            ),
            OperationalField(
                "acceptance_evidence",
                True,
                False,
                "Evidencia y exportación F8 con publicación desactivada.",
            ),
        ),
        human_gates=(
            HumanGate(
                "render_cost_authorization",
                "after_ready_for_real_render",
                ("authorize", "reject"),
                True,
                True,
                (
                    "Exige proveedor y costo máximo explícitos; la autorización "
                    "se consume al utilizarse."
                ),
            ),
            HumanGate(
                "final_review",
                "after_final_video",
                ("approve", "request_changes", "cancel"),
                True,
                False,
                "Registra la decisión humana final mediante F7.",
            ),
            HumanGate(
                "publication_authorization",
                "after_approved_review",
                ("authorize", "reject"),
                False,
                True,
                "Debe ser independiente; permanece desactivada durante FAO.",
            ),
        ),
        lifecycle_states=(
            LifecycleState(
                "topic_received",
                True,
                False,
                "Las entradas del operador fueron validadas.",
            ),
            LifecycleState(
                "project_created",
                True,
                False,
                "El workspace nuevo quedó inicializado.",
            ),
            LifecycleState(
                "editorial_in_progress",
                True,
                False,
                "CIPS genera el paquete editorial trazable.",
            ),
            LifecycleState(
                "editorial_validated",
                True,
                False,
                "Los gates factual y editorial fueron aprobados.",
            ),
            LifecycleState(
                "production_derived",
                True,
                False,
                "Manifest y configuración fueron derivados automáticamente.",
            ),
            LifecycleState(
                "assets_ready",
                True,
                False,
                "Activos, audio y subtítulos están conformes y persistidos.",
            ),
            LifecycleState(
                "ready_for_real_render",
                True,
                False,
                "La preparación terminó sin ejecutar un render real.",
            ),
            LifecycleState(
                "awaiting_render_authorization",
                True,
                False,
                "CIPS espera la decisión humana sobre proveedor y costo.",
            ),
            LifecycleState(
                "rendering",
                True,
                False,
                "Una autorización vigente habilitó el render.",
            ),
            LifecycleState(
                "ready_for_review",
                True,
                False,
                "El MP4 pasó QA técnico y espera F7.",
            ),
            LifecycleState(
                "changes_requested",
                True,
                False,
                "F7 solicitó correcciones y un regreso controlado.",
            ),
            LifecycleState(
                "approved",
                True,
                False,
                "F7 aprobó el MP4.",
            ),
            LifecycleState(
                "cancelled",
                True,
                True,
                "El operador canceló la producción.",
            ),
            LifecycleState(
                "exported",
                True,
                True,
                "F8 persistió el resultado sin publicar.",
            ),
        ),
        current_pipelines=(
            PipelineBoundary(
                "legacy_topic_pipeline",
                "08_SCRIPTS/menu_controller.py:MenuController.new_project",
                "topic",
                "legacy editorial and media workspace",
                "No invoca la cadena de aceptación PM9, F7 ni F8.",
            ),
            PipelineBoundary(
                "pm9_acceptance_pipeline",
                "08_SCRIPTS/run_pm9_full_production_acceptance.py:main",
                "prebuilt project plus production_acceptance_config.json",
                "render readiness, authorized render, F7 and F8 evidence",
                "No recibe un tema ni construye el paquete editorial.",
            ),
        ),
        allowed_operator_interventions=(
            "provide_topic_platform_duration_audience_and_style",
            "authorize_or_reject_quantified_render_cost",
            "review_final_video_with_f7",
        ),
        prohibited_operator_interventions=(
            "manually_edit_markdown_json_or_python",
            "copy_external_llm_responses",
            "select_internal_paths",
            "repair_normal_execution_with_llm_assistance",
            "publish_during_fao",
        ),
        invariants=(
            "production_manifest_is_provider_neutral",
            "free_tier_is_default",
            "no_credit_use_without_new_explicit_quantified_authorization",
            "publication_performed_is_false",
            "f3_f7_f8_evidence_is_preserved",
            "operations_are_idempotent_and_resumable",
        ),
        master_close_criteria=(
            "unseen_topic_selected_by_operator",
            "normal_execution_without_operational_llm_assistance",
            "reviewable_mp4_with_technical_and_quality_evidence",
            "f7_decision_and_f8_evidence_persisted",
            "publication_performed_is_false",
        ),
    )


def inspect_operational_baseline(repository_root: Path) -> dict[str, Any]:
    """Inspecciona de forma determinista la separación de pipelines actual."""

    root = repository_root.expanduser().resolve(strict=True)
    sources = {
        str(PM9_ENTRYPOINT): _read_source(root, PM9_ENTRYPOINT),
        str(LEGACY_ENTRYPOINT): _read_source(root, LEGACY_ENTRYPOINT),
        str(FRESH_PROJECT_TEST): _read_source(root, FRESH_PROJECT_TEST),
    }
    pm9_tree = ast.parse(sources[str(PM9_ENTRYPOINT)])
    legacy_tree = ast.parse(sources[str(LEGACY_ENTRYPOINT)])
    fresh_tree = ast.parse(sources[str(FRESH_PROJECT_TEST)])

    pm9_arguments = _argument_names(pm9_tree)
    legacy_method = _find_method(legacy_tree, "MenuController", "new_project")
    legacy_input_targets = _input_assignment_targets(legacy_method)
    legacy_imports = _imported_names(legacy_tree)
    legacy_calls = _called_names(legacy_method)
    copied_source_paths = _literal_string_sequence(
        fresh_tree,
        "FRESH_PROJECT_SOURCE_PATHS",
    )

    required_prebuilt_sources = {
        "narration",
        "production_acceptance_config.json",
        "publication",
        "research",
        "script",
        "seo",
        "storyboard",
        "verification",
    }
    pm9_accepts_topic = "--topic" in pm9_arguments or "--tema" in pm9_arguments
    legacy_accepts_topic = "tema" in legacy_input_targets or "topic" in legacy_input_targets
    legacy_invokes_pm9 = bool(
        {
            "run_pm9_full_production_acceptance",
            "FullProductionAcceptance",
        }
        & (legacy_imports | legacy_calls)
    )
    copies_prebuilt_editorial = required_prebuilt_sources.issubset(
        set(copied_source_paths)
    )
    gap_confirmed = all(
        (
            legacy_accepts_topic,
            "PipelineEngine" in legacy_imports,
            "ejecutar_media_production" in legacy_calls,
            not legacy_invokes_pm9,
            "--project" in pm9_arguments,
            not pm9_accepts_topic,
            copies_prebuilt_editorial,
        )
    )

    return {
        "schema_name": BASELINE_SCHEMA_NAME,
        "schema_version": BASELINE_SCHEMA_VERSION,
        "phase": "FAO.1",
        "gap_confirmed": gap_confirmed,
        "bridge_status": "missing" if gap_confirmed else "requires_review",
        "legacy_topic_pipeline": {
            "entrypoint": str(LEGACY_ENTRYPOINT),
            "accepts_topic": legacy_accepts_topic,
            "calls_pipeline_engine": "PipelineEngine" in legacy_imports,
            "calls_legacy_media_pipeline": "ejecutar_media_production" in legacy_calls,
            "invokes_pm9_acceptance": legacy_invokes_pm9,
        },
        "pm9_acceptance_pipeline": {
            "entrypoint": str(PM9_ENTRYPOINT),
            "cli_arguments": list(pm9_arguments),
            "accepts_project": "--project" in pm9_arguments,
            "accepts_topic": pm9_accepts_topic,
        },
        "existing_fresh_project_test": {
            "path": str(FRESH_PROJECT_TEST),
            "copied_source_paths": list(copied_source_paths),
            "copies_prebuilt_editorial_project": copies_prebuilt_editorial,
        },
        "safety": {
            "inspection_mode": "static_ast",
            "network_called": False,
            "credits_used": 0,
            "render_performed": False,
            "publication_performed": False,
            "files_modified": False,
        },
        "source_sha256": {
            relative_path: hashlib.sha256(content.encode("utf-8")).hexdigest()
            for relative_path, content in sorted(sources.items())
        },
    }


def _read_source(repository_root: Path, relative_path: Path) -> str:
    path = repository_root / relative_path
    if not path.is_file():
        raise FileNotFoundError(f"No existe el archivo requerido: {relative_path}")
    return path.read_text(encoding="utf-8")


def _argument_names(tree: ast.AST) -> tuple[str, ...]:
    arguments: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Attribute) or node.func.attr != "add_argument":
            continue
        for argument in node.args:
            if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
                arguments.add(argument.value)
    return tuple(sorted(arguments))


def _find_method(tree: ast.AST, class_name: str, method_name: str) -> ast.FunctionDef:
    for node in ast.iter_child_nodes(tree):
        if not isinstance(node, ast.ClassDef) or node.name != class_name:
            continue
        for child in node.body:
            if isinstance(child, ast.FunctionDef) and child.name == method_name:
                return child
    raise ValueError(f"No se encontró {class_name}.{method_name}.")


def _input_assignment_targets(function: ast.FunctionDef) -> set[str]:
    targets: set[str] = set()
    for node in ast.walk(function):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        value = node.value
        if value is None or "input" not in _called_names(value):
            continue
        assignment_targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        for target in assignment_targets:
            if isinstance(target, ast.Name):
                targets.add(target.id)
    return targets


def _imported_names(tree: ast.AST) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.asname or alias.name.split(".")[-1])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                names.add(node.module.split(".")[-1])
            for alias in node.names:
                names.add(alias.asname or alias.name)
    return names


def _called_names(tree: ast.AST) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name):
            names.add(node.func.id)
        elif isinstance(node.func, ast.Attribute):
            names.add(node.func.attr)
    return names


def _literal_string_sequence(tree: ast.AST, name: str) -> tuple[str, ...]:
    for node in ast.iter_child_nodes(tree):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        if not any(isinstance(target, ast.Name) and target.id == name for target in targets):
            continue
        value = ast.literal_eval(node.value)
        if not isinstance(value, (tuple, list)) or not all(
            isinstance(item, str) for item in value
        ):
            raise ValueError(f"{name} no es una secuencia literal de texto.")
        return tuple(value)
    raise ValueError(f"No se encontró la constante {name}.")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Diagnóstico offline y determinista del baseline FAO.1.",
    )
    parser.add_argument(
        "--repository-root",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="Raíz del repositorio CIPS que será inspeccionado.",
    )
    parser.add_argument(
        "--include-contract",
        action="store_true",
        help="Incluye el contrato operativo versionado junto al baseline.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    baseline = inspect_operational_baseline(args.repository_root)
    payload: dict[str, Any] = {"baseline": baseline}
    if args.include_contract:
        payload["contract"] = build_operational_contract().to_dict()
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if baseline["gap_confirmed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
