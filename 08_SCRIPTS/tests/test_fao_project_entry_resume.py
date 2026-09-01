from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
import yaml


SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import menu_controller as menu_controller_module  # noqa: E402
import project_manager as project_manager_module  # noqa: E402
from menu_controller import MenuController  # noqa: E402
from project_manager import ProjectManager  # noqa: E402
from runtime_models import EngineResult  # noqa: E402


@pytest.fixture
def isolated_projects(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    projects_dir = tmp_path / "04_PROYECTOS"
    monkeypatch.setattr(
        project_manager_module,
        "PROJECTS_DIR",
        projects_dir,
    )
    return projects_dir


def test_project_creation_persists_all_operational_inputs_and_checkpoint(
    isolated_projects: Path,
) -> None:
    manager = ProjectManager()

    created = manager.create_project(
        "Cómo funciona un eclipse solar",
        plataforma="Instagram Reels",
        duracion_segundos=60,
        audiencia="estudiantes de secundaria",
        estilo_creativo="documental visual y accesible",
    )

    project_path = Path(created["path"])
    assert project_path == isolated_projects / "PROYECTO_0001"
    assert Path(created["checkpoint_path"]).is_file()
    assert {
        "research",
        "verification",
        "script",
        "storyboard",
        "narration",
        "seo",
        "publication",
        "assets",
        "voice",
        "images",
        "subtitles",
        "video",
        "final",
        "state",
    }.issubset({path.name for path in project_path.iterdir() if path.is_dir()})

    request = json.loads(
        (project_path / "operational_request.json").read_text(encoding="utf-8")
    )
    assert request["schema_name"] == "cips.fao.operational_request"
    assert request["schema_version"] == "1.0"
    assert request["topic"] == "Cómo funciona un eclipse solar"
    assert request["platform"] == "Instagram Reels"
    assert request["duration_seconds"] == 60
    assert request["audience"] == "estudiantes de secundaria"
    assert request["creative_style"] == "documental visual y accesible"
    assert request["free_tier_default"] is True
    assert request["publication_performed"] is False

    project_yaml = yaml.safe_load(
        (project_path / "proyecto.yaml").read_text(encoding="utf-8")
    )
    assert project_yaml["stage_actual"] == "investigacion"
    assert project_yaml["solicitud_operativa"]["platform"] == "Instagram Reels"

    context = (project_path / "CONTEXTO.md").read_text(encoding="utf-8")
    assert "estudiantes de secundaria" in context
    assert "documental visual y accesible" in context
    assert "Alimentación, ejercicio y salud" not in context

    state = json.loads(
        (project_path / "state" / "production_state.json").read_text(
            encoding="utf-8"
        )
    )
    assert state["current_stage"] == "investigacion"
    assert state["global_metadata"] == {
        "fao_schema_name": "cips.fao.project_checkpoint",
        "fao_schema_version": "1.0",
        "fao_lifecycle_state": "project_created",
        "operational_request_path": "operational_request.json",
        "publication_performed": False,
    }
    assert state["snapshots"][-1]["label"] == "project_created"
    assert state["snapshots"][-1]["metadata"]["publication_performed"] is False


def test_legacy_create_project_call_remains_compatible(
    isolated_projects: Path,
) -> None:
    created = ProjectManager().create_project("Tema compatible")
    request = json.loads(
        (Path(created["path"]) / "operational_request.json").read_text(
            encoding="utf-8"
        )
    )

    assert request["platform"] == "YouTube Shorts"
    assert request["duration_seconds"] == 45
    assert request["audience"] == "público general"
    assert request["creative_style"] == "educativo, claro y dinámico"


@pytest.mark.parametrize("duration", [True, 0, 3601, 45.5, "45"])
def test_project_creation_rejects_invalid_duration_without_workspace(
    isolated_projects: Path,
    duration: object,
) -> None:
    manager = ProjectManager()

    with pytest.raises(ValueError, match="duración"):
        manager.create_project(
            "Tema inválido",
            duracion_segundos=duration,  # type: ignore[arg-type]
        )

    assert list(isolated_projects.iterdir()) == []


def test_latest_project_prefers_fresh_numeric_workspace(
    isolated_projects: Path,
) -> None:
    manager = ProjectManager()
    first = Path(manager.create_project("Tema uno")["path"])
    second = Path(manager.create_project("Tema dos")["path"])
    closed_pm9 = isolated_projects / "PROYECTO_PM9_CIELO_0001"
    closed_pm9.mkdir()
    (closed_pm9 / "proyecto.yaml").write_text(
        "id: PROYECTO_PM9_CIELO_0001\ntema: Cerrado\nestado: final\n",
        encoding="utf-8",
    )

    assert manager.get_latest_project_path() == second
    assert manager.get_latest_project_path() != closed_pm9
    assert first != second


class _PipelineStub:
    def __init__(self, result: EngineResult) -> None:
        self.result = result
        self.project_paths: list[Path] = []

    def execute(self, project_path: Path | None = None) -> EngineResult:
        assert project_path is not None
        self.project_paths.append(project_path)
        return self.result


def test_continue_project_selects_checkpoint_without_internal_path_input(
    isolated_projects: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = ProjectManager()
    first = Path(manager.create_project("Proyecto a reanudar")["path"])
    manager.create_project("Otro proyecto")
    pipeline = _PipelineStub(
        EngineResult.ok(
            data={
                "completed_stage": "investigacion",
                "next_stage": "verificacion",
            },
            message="Etapa completada.",
            metadata={
                "completed_stage": "investigacion",
                "next_stage": "verificacion",
            },
        )
    )
    controller = MenuController()
    controller.project_manager = manager
    controller.pipeline_engine = pipeline
    controller.pause = lambda: None
    monkeypatch.setattr("builtins.input", lambda _prompt="": "1")

    controller.continue_project_runtime()

    assert pipeline.project_paths == [first]
    state = json.loads(
        (first / "state" / "production_state.json").read_text(encoding="utf-8")
    )
    labels = [snapshot["label"] for snapshot in state["snapshots"]]
    assert labels[-2:] == ["resume_requested", "runtime_step_completed"]
    assert state["global_metadata"]["publication_performed"] is False


def test_official_new_project_collects_request_and_pauses_recoverably(
    isolated_projects: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = ProjectManager()
    pipeline = _PipelineStub(
        EngineResult.ok(
            message="Respuesta manual pendiente.",
            metadata={
                "requires_user_action": True,
                "prompt_path": "prompt.md",
            },
        )
    )
    controller = MenuController()
    controller.project_manager = manager
    controller.pipeline_engine = pipeline
    controller.pause = lambda: None
    answers = iter(
        [
            "La historia del cacao en México",
            "TikTok",
            "75",
            "jóvenes adultos",
            "histórico, colorido y ágil",
        ]
    )
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(answers))
    monkeypatch.setattr(
        menu_controller_module,
        "ejecutar_media_production",
        lambda _path: pytest.fail("No debía ejecutarse multimedia"),
    )

    controller.new_project()

    project_path = isolated_projects / "PROYECTO_0001"
    request = json.loads(
        (project_path / "operational_request.json").read_text(encoding="utf-8")
    )
    assert request["topic"] == "La historia del cacao en México"
    assert request["platform"] == "TikTok"
    assert request["duration_seconds"] == 75
    assert request["audience"] == "jóvenes adultos"
    assert request["creative_style"] == "histórico, colorido y ágil"
    assert pipeline.project_paths == [project_path]

    state = json.loads(
        (project_path / "state" / "production_state.json").read_text(
            encoding="utf-8"
        )
    )
    assert state["global_metadata"]["fao_lifecycle_state"] == (
        "editorial_in_progress"
    )
    assert state["snapshots"][-1]["label"] == "runtime_paused"
    assert state["snapshots"][-1]["metadata"]["requires_user_action"] is True
    assert state["global_metadata"]["publication_performed"] is False
