from __future__ import annotations

import json
import subprocess
import sys
import wave
from pathlib import Path

import pytest


SCRIPTS_DIR = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = SCRIPTS_DIR.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import menu_controller as menu_controller_module  # noqa: E402
import project_manager as project_manager_module  # noqa: E402
import production_acceptance.source_assets as source_assets  # noqa: E402
from canonical_subtitles import PhysicalAudioDurationProbe  # noqa: E402
from fao_pm9_unification import (  # noqa: E402
    FAOPM9UnificationBlockedError,
    FAOPM9UnificationEngine,
)
from fao_quality_recovery import (  # noqa: E402
    FAOQualityRecoveryBlockedError,
    FAOQualityRecoveryResult,
)
from menu_controller import MenuController  # noqa: E402
from production_acceptance import (  # noqa: E402
    FullProductionAcceptance,
    NarrationConformancePolicy,
    PM9SourceAssetBuilder,
)
from project_manager import ProjectManager  # noqa: E402
from runtime_constants import STAGES  # noqa: E402
from runtime_models import EngineResult  # noqa: E402
from tests.test_fao_production_derivation import _completed_project  # noqa: E402
from tests.test_pm9_fresh_project_end_to_end import _wikimedia_provider  # noqa: E402


def _write_wav(path: Path, *, seconds: float = 1.0) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(8_000)
        stream.writeframes(b"\x00\x00" * max(1, round(seconds * 8_000)))


def _completed(stdout: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess([], 0, stdout=stdout, stderr="")


def _source_builder_factory(
    monkeypatch: pytest.MonkeyPatch,
    calls: dict[str, int],
):
    monkeypatch.setattr(source_assets.shutil, "which", lambda name: f"/bin/{name}")
    monkeypatch.setattr(source_assets.importlib.util, "find_spec", lambda name: object())
    monkeypatch.setattr(
        source_assets,
        "_write_procedural_audio",
        lambda path, duration_seconds, kind: _write_wav(path, seconds=0.1),
    )

    def factory(**kwargs):
        calls["source_builder"] += 1
        model_dir = Path(kwargs["model_dir"])
        model_dir.mkdir(parents=True, exist_ok=True)
        (model_dir / "es_MX-claude-high.onnx").write_bytes(b"offline-model")
        (model_dir / "es_MX-claude-high.onnx.json").write_text(
            "{}",
            encoding="utf-8",
        )

        def runner(command):
            command = tuple(str(item) for item in command)
            if command[0] == sys.executable and command[1:3] == ("-m", "piper"):
                _write_wav(Path(command[command.index("-f") + 1]))
            elif command[0] == "ffprobe":
                return _completed("1.000000\n")
            elif command[0] == "ffmpeg":
                destination = Path(command[-1])
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(
                    b"ID3\x04\x00\x00-FAO5-" + destination.name.encode()
                )
            return _completed()

        return PM9SourceAssetBuilder(
            kwargs["manifest"],
            project_path=kwargs["project_path"],
            assets_root=kwargs["assets_root"],
            model_dir=model_dir,
            delivery_base_uri=kwargs["delivery_base_uri"],
            runner=runner,
            fetch_bytes=lambda url: pytest.fail(
                f"El builder genérico no debe descargar visuales: {url}"
            ),
        )

    return factory


def _acceptance_factory(**kwargs) -> FullProductionAcceptance:
    return FullProductionAcceptance(
        workspace_resolver=kwargs["workspace_resolver"],
        asset_resolver=kwargs["asset_resolver"],
        subtitle_duration_probe=PhysicalAudioDurationProbe(
            runner=lambda command: {"format": {"duration": "8.000"}}
        ),
        narration_conformance_policy=NarrationConformancePolicy(enabled=False),
    )


def _bridge(
    monkeypatch: pytest.MonkeyPatch,
    calls: dict[str, int],
) -> FAOPM9UnificationEngine:
    wikimedia = _wikimedia_provider()

    def wikimedia_factory():
        calls["wikimedia_factory"] += 1
        return wikimedia

    return FAOPM9UnificationEngine(
        render_provider="creatomate",
        delivery_base_uri=(
            "https://raw.githubusercontent.com/example/CIPS/main/"
            "04_PROYECTOS/PROYECTO_0001/source_assets"
        ),
        source_asset_builder_factory=_source_builder_factory(monkeypatch, calls),
        wikimedia_provider_factory=wikimedia_factory,
        acceptance_factory=_acceptance_factory,
    )


def test_fresh_fao_project_reaches_zero_cost_pm9_render_readiness(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    project, _, _ = _completed_project(monkeypatch, tmp_path)
    calls = {"source_builder": 0, "wikimedia_factory": 0}

    result = _bridge(monkeypatch, calls).prepare(project)

    assert result.ready_for_real_render is True
    assert result.provider == "creatomate"
    assert result.total_actual_cost_usd == 0.0
    assert result.estimated_render_credits > 0
    assert result.persisted_asset_count > 0
    assert result.canonical_subtitles_path is not None
    assert result.canonical_subtitles_path.is_file()
    assert result.network_called is True
    assert result.reused_existing is False
    assert calls == {"source_builder": 1, "wikimedia_factory": 1}

    evidence = json.loads(result.evidence_path.read_text(encoding="utf-8"))
    assert evidence["schema_name"] == "cips.fao.pm9_unification"
    assert evidence["status"] == "ready_for_render_authorization"
    assert evidence["topic"] == "Cómo funcionan los eclipses solares"
    assert evidence["ready_for_real_render"] is True
    assert evidence["total_actual_cost_usd"] == 0.0
    assert evidence["unknown_cost_count"] == 0
    assert evidence["paid_provider_called"] is False
    assert evidence["render_performed"] is False
    assert evidence["f7_review_state"] == "not_started"
    assert evidence["f7_review_performed"] is False
    assert evidence["f8_preparation_telemetry_persisted"] is True
    assert evidence["publication_performed"] is False
    assert evidence["canonical_subtitles_generated"] is True
    assert evidence["outputs"]["asset_inventory"]["path"] == (
        "acceptance/asset_requirements.json"
    )
    assert "json2video" not in (project / "production_manifest.json").read_text(
        encoding="utf-8"
    ).casefold()

    for output in evidence["outputs"].values():
        path = project / output["path"]
        assert path.is_file()
        assert Path(f"{path}.meta.json").is_file() or output["path"].startswith(
            "source_assets/"
        )
    assert Path(f"{result.evidence_path}.meta.json").is_file()
    assert not (project / "render" / "json2video_result.json").exists()
    assert not (project / "acceptance" / "final_acceptance.json").exists()
    assert not (project / "final" / "short.mp4").exists()


def test_identical_fao5_resume_reuses_verified_evidence_without_new_calls(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    project, _, _ = _completed_project(monkeypatch, tmp_path)
    calls = {"source_builder": 0, "wikimedia_factory": 0}
    bridge = _bridge(monkeypatch, calls)
    first = bridge.prepare(project)
    evidence_before = first.evidence_path.read_bytes()

    second = bridge.prepare(project)

    assert second.reused_existing is True
    assert second.evidence_path.read_bytes() == evidence_before
    assert calls == {"source_builder": 1, "wikimedia_factory": 1}


def test_fao5_rejects_non_free_request_before_media_or_render(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    projects_dir = tmp_path / "04_PROYECTOS"
    monkeypatch.setattr(project_manager_module, "PROJECTS_DIR", projects_dir)
    created = ProjectManager().create_project("Tema con política inválida")
    project = Path(created["path"])
    request_path = project / "operational_request.json"
    request = json.loads(request_path.read_text(encoding="utf-8"))
    request["free_tier_default"] = False
    request_path.write_text(json.dumps(request), encoding="utf-8")

    with pytest.raises(FAOPM9UnificationBlockedError, match="Free Tier"):
        FAOPM9UnificationEngine(
            delivery_base_uri="https://example.test/assets"
        ).prepare(project)

    assert not (project / "state" / "fao_pm9_unification.json").exists()
    assert not (project / "final" / "short.mp4").exists()


def test_fao5_rejects_project_with_existing_render_boundary_output(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    projects_dir = tmp_path / "04_PROYECTOS"
    monkeypatch.setattr(project_manager_module, "PROJECTS_DIR", projects_dir)
    created = ProjectManager().create_project("Tema ya renderizado")
    project = Path(created["path"])
    result_path = project / "render" / "json2video_result.json"
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text("{}", encoding="utf-8")

    with pytest.raises(
        FAOPM9UnificationBlockedError,
        match="contiene render",
    ):
        FAOPM9UnificationEngine(
            delivery_base_uri="https://example.test/assets"
        ).prepare(project)


class _AdvancingEditorialPipeline:
    def __init__(self, manager: ProjectManager) -> None:
        self.manager = manager
        self.project_paths: list[Path] = []

    def execute(self, project_path: Path | None = None) -> EngineResult:
        assert project_path is not None
        self.project_paths.append(project_path)
        project = self.manager.load_project(project_path)
        current_index = STAGES.index(project.stage_actual)
        next_stage = STAGES[current_index + 1]
        if project.stage_actual == "narracion":
            package = project.path / "state" / "editorial_package.json"
            package.write_text("{}", encoding="utf-8")
        self.manager.update_project_stage(project, next_stage)
        return EngineResult.ok(
            data={
                "completed_stage": project.stage_actual,
                "next_stage": next_stage,
            },
            message="Stage completado por fixture.",
            metadata={
                "completed_stage": project.stage_actual,
                "next_stage": next_stage,
            },
        )


class _BridgeResultStub:
    provider = "json2video"
    total_actual_cost_usd = 0.0
    estimated_render_credits = 40

    def __init__(self, project: Path) -> None:
        self.project_path = project
        self.evidence_path = project / "state" / "fao_pm9_unification.json"
        self.evidence_path.write_text("{}", encoding="utf-8")

    def metadata(self) -> dict[str, object]:
        return {
            "ready_for_real_render": True,
            "estimated_render_credits": self.estimated_render_credits,
            "total_actual_cost_usd": self.total_actual_cost_usd,
            "render_performed": False,
            "f7_review_performed": False,
            "publication_performed": False,
        }


class _BridgeStub:
    def __init__(self) -> None:
        self.project_paths: list[Path] = []

    def prepare(self, project_path: Path) -> _BridgeResultStub:
        self.project_paths.append(project_path)
        return _BridgeResultStub(project_path)


class _QualityResultStub:
    def __init__(self, project: Path) -> None:
        self.evidence_path = project / "state" / "fao_quality_recovery.json"
        self.evidence_path.write_text("{}", encoding="utf-8")

    def metadata(self) -> dict[str, object]:
        return {
            "quality_approved": True,
            "quality_passed_gates": [
                "factual",
                "editorial",
                "visual",
                "acoustic",
                "technical",
            ],
            "render_performed": False,
            "f7_review_performed": False,
            "publication_performed": False,
        }


class _QualityStub:
    def __init__(self) -> None:
        self.project_paths: list[Path] = []

    def evaluate(self, project_path: Path) -> _QualityResultStub:
        self.project_paths.append(project_path)
        return _QualityResultStub(project_path)


class _QualityBlockingStub:
    def evaluate(self, project_path: Path) -> None:
        evidence = project_path / "state" / "fao_quality_recovery.json"
        evidence.write_text("{}", encoding="utf-8")
        raise FAOQualityRecoveryBlockedError(
            FAOQualityRecoveryResult(
                project_path=project_path,
                evidence_path=evidence,
                approved=False,
                input_fingerprint="a" * 64,
                passed_gates=("editorial", "visual", "acoustic"),
                blocking_codes=("technical_public_delivery_unavailable",),
                operator_message="Los assets públicos todavía no están disponibles.",
                recovery_steps=("Vuelve a usar Continuar Proyecto.",),
                retryable=True,
                source_network_calls=2,
                delivery_network_calls=1,
                reused_existing=False,
            )
        )


def test_official_new_project_routes_fao_media_to_pm9_and_stops_before_review(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    projects_dir = tmp_path / "04_PROYECTOS"
    monkeypatch.setattr(project_manager_module, "PROJECTS_DIR", projects_dir)
    manager = ProjectManager()
    bridge = _BridgeStub()
    quality = _QualityStub()
    controller = MenuController()
    controller.project_manager = manager
    controller.pipeline_engine = _AdvancingEditorialPipeline(manager)
    controller.fao_pm9_unification = bridge
    controller.fao_quality_recovery = quality
    controller.pause = lambda: None
    answers = iter(
        [
            "Por qué cambian de color las hojas",
            "YouTube Shorts",
            "45",
            "público general",
            "científico y visual",
        ]
    )
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(answers))
    monkeypatch.setattr(
        menu_controller_module,
        "ejecutar_media_production",
        lambda project: pytest.fail(
            f"El proyecto FAO no debe usar multimedia heredada: {project}"
        ),
    )

    controller.new_project()

    project = projects_dir / "PROYECTO_0001"
    assert bridge.project_paths == [project]
    assert quality.project_paths == [project]
    production = json.loads((project / "production.json").read_text(encoding="utf-8"))
    assert production["status"] == "READY_FOR_RENDER_AUTHORIZATION"
    state = json.loads(
        (project / "state" / "production_state.json").read_text(encoding="utf-8")
    )
    assert state["snapshots"][-1]["label"] == "ready_for_render_authorization"
    assert state["snapshots"][-1]["metadata"]["render_performed"] is False
    assert state["snapshots"][-1]["metadata"]["f7_review_performed"] is False
    assert state["snapshots"][-1]["metadata"]["publication_performed"] is False


def test_continue_project_at_media_stage_reuses_same_fao5_bridge(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    projects_dir = tmp_path / "04_PROYECTOS"
    monkeypatch.setattr(project_manager_module, "PROJECTS_DIR", projects_dir)
    manager = ProjectManager()
    created = manager.create_project("Proyecto FAO reanudable")
    project_path = Path(created["path"])
    project = manager.load_project(project_path)
    while project.stage_actual != "voz":
        manager.update_project_stage(
            project,
            STAGES[STAGES.index(project.stage_actual) + 1],
        )
        project = manager.load_project(project_path)
    bridge = _BridgeStub()
    quality = _QualityStub()
    controller = MenuController()
    controller.project_manager = manager
    controller.fao_pm9_unification = bridge
    controller.fao_quality_recovery = quality
    controller.pause = lambda: None
    controller.pipeline_engine.execute = lambda **kwargs: pytest.fail(
        "La reanudación FAO multimedia debe usar el puente PM9."
    )
    monkeypatch.setattr("builtins.input", lambda _prompt="": "1")

    controller.continue_project_runtime()

    assert bridge.project_paths == [project_path]
    assert quality.project_paths == [project_path]
    state = json.loads(
        (project_path / "state" / "production_state.json").read_text(
            encoding="utf-8"
        )
    )
    labels = [snapshot["label"] for snapshot in state["snapshots"]]
    assert labels[-2:] == ["resume_requested", "ready_for_render_authorization"]


def test_official_flow_preserves_fao6_blocked_checkpoint_for_operator_recovery(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    projects_dir = tmp_path / "04_PROYECTOS"
    monkeypatch.setattr(project_manager_module, "PROJECTS_DIR", projects_dir)
    manager = ProjectManager()
    controller = MenuController()
    controller.project_manager = manager
    controller.pipeline_engine = _AdvancingEditorialPipeline(manager)
    controller.fao_pm9_unification = _BridgeStub()
    controller.fao_quality_recovery = _QualityBlockingStub()
    controller.pause = lambda: None
    answers = iter(
        [
            "Tema con entrega remota pendiente",
            "YouTube Shorts",
            "45",
            "público general",
            "educativo y visual",
        ]
    )
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(answers))

    controller.new_project()

    project = projects_dir / "PROYECTO_0001"
    production = json.loads((project / "production.json").read_text(encoding="utf-8"))
    state = json.loads(
        (project / "state" / "production_state.json").read_text(encoding="utf-8")
    )
    assert production["status"] == "QUALITY_GATE_BLOCKED"
    assert state["snapshots"][-1]["label"] == "quality_gate_blocked"
    assert state["snapshots"][-1]["metadata"]["retryable"] is True
    assert state["snapshots"][-1]["metadata"]["render_performed"] is False
    assert state["snapshots"][-1]["metadata"]["publication_performed"] is False
