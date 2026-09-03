from __future__ import annotations

import json
import hashlib
import re
import subprocess
import sys
import wave
from pathlib import Path

import pytest


SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import production_acceptance.source_assets as source_assets  # noqa: E402
from editorial_contract import canonical_editorial_path  # noqa: E402
from fao_pm9_unification import FAOPM9UnificationEngine  # noqa: E402
from fao_quality_recovery import (  # noqa: E402
    FAOQualityRecoveryBlockedError,
    FAOQualityRecoveryEngine,
    SourceFetchResult,
)
from production_acceptance import (  # noqa: E402
    ApprovedAssetCatalog,
    FullProductionAcceptance,
    NarrationConformanceGate,
    NarrationTranscription,
    PM9SourceAssetBuilder,
    PhysicalAudioDurationProbe,
)
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


class _ExactTranscriber:
    network_called = False

    def __init__(self, manifest) -> None:
        self._text_by_sequence = {
            scene.sequence: scene.narration_text or ""
            for scene in manifest.scenes
        }

    def transcribe(self, audio_path: Path) -> NarrationTranscription:
        match = re.search(r"narration-(\d+)", audio_path.name)
        assert match is not None
        return NarrationTranscription(
            text=self._text_by_sequence[int(match.group(1))],
            detected_language="es",
            language_probability=1.0,
        )


def _source_builder_factory(monkeypatch: pytest.MonkeyPatch, calls: dict[str, int]):
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
        for voice_id in kwargs["config"]["narration_voice_candidates"]:
            (model_dir / f"{voice_id}.onnx").write_bytes(b"offline-model")
            (model_dir / f"{voice_id}.onnx.json").write_text("{}", encoding="utf-8")

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
                    b"ID3\x04\x00\x00-FAO6-" + destination.name.encode()
                )
            return _completed()

        manifest = kwargs["manifest"]
        policy = kwargs["config"]["narration_conformance_policy"]
        gate = NarrationConformanceGate(
            policy,
            _ExactTranscriber(manifest),
            metadata_store=kwargs["metadata_store"],
        )
        return PM9SourceAssetBuilder(
            manifest,
            project_path=kwargs["project_path"],
            assets_root=kwargs["assets_root"],
            model_dir=model_dir,
            delivery_base_uri=kwargs["delivery_base_uri"],
            narration_conformance_gate=gate,
            narration_voice_candidates=kwargs["config"]["narration_voice_candidates"],
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
        narration_conformance_policy=kwargs["config"][
            "narration_conformance_policy"
        ],
    )


def _prepared_project(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> tuple[Path, dict[str, int]]:
    project, _, _ = _completed_project(monkeypatch, tmp_path)
    calls = {"source_builder": 0, "wikimedia_factory": 0}
    wikimedia = _wikimedia_provider()

    def wikimedia_factory():
        calls["wikimedia_factory"] += 1
        return wikimedia

    bridge = FAOPM9UnificationEngine(
        render_provider="creatomate",
        delivery_base_uri=(
            "https://raw.githubusercontent.com/example/CIPS/main/"
            "04_PROYECTOS/PROYECTO_0001/source_assets"
        ),
        source_asset_builder_factory=_source_builder_factory(monkeypatch, calls),
        wikimedia_provider_factory=wikimedia_factory,
        acceptance_factory=_acceptance_factory,
    )
    bridge.prepare(project)
    # The shared PM9 fixture intentionally uses generic titles. FAO.6 requires
    # the selected title to retain the permitted query so relevance is auditable.
    fulfillment_path = project / "acceptance" / "visual_asset_fulfillment.json"
    fulfillment = json.loads(fulfillment_path.read_text(encoding="utf-8"))
    for asset in fulfillment["assets"]:
        if asset["role"] == "scene_visual" and asset.get("prompt_permitted"):
            asset["selected_title"] = asset["prompt_permitted"]
    fulfillment_path.write_text(
        json.dumps(fulfillment, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    evidence_path = project / "state" / "fao_pm9_unification.json"
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    reference = evidence["outputs"]["visual_fulfillment_report"]
    content = fulfillment_path.read_bytes()
    reference["sha256"] = hashlib.sha256(content).hexdigest()
    reference["size_bytes"] = len(content)
    evidence_path.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return project, calls


class _SourceFetcher:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def __call__(self, url: str) -> SourceFetchResult:
        self.calls.append(url)
        body = (
            "<html><body><h1>Solar Eclipses and the Moon</h1>"
            "Cómo funcionan los eclipses solares. Solar eclipse, Moon, Earth and Sun. "
            "La alineación produce umbra y penumbra y explica la totalidad o parcialidad. "
            "Esta página educativa describe la sombra lunar, la observación regional y "
            "la seguridad ocular con suficiente contexto para verificar el tema. "
            "Royal Museums Greenwich NASA Science astronomy education reference."
            "</body></html>"
        ).encode("utf-8")
        return SourceFetchResult(
            requested_url=url,
            final_url=url,
            status_code=200,
            content_type="text/html; charset=utf-8",
            content=body,
            etag='"source-v1"',
        )


class _AssetFetcher:
    def __init__(self, project: Path) -> None:
        evidence = json.loads(
            (project / "state" / "fao_pm9_unification.json").read_text(
                encoding="utf-8"
            )
        )
        catalog_path = project / evidence["outputs"]["fulfilled_asset_catalog"]["path"]
        catalog = ApprovedAssetCatalog.load(catalog_path)
        assets_root = catalog_path.parent
        self.content = {
            entry.delivery_uri: (assets_root / entry.relative_path).read_bytes()
            for entry in catalog.entries
        }
        self.calls: list[str] = []

    def __call__(self, url: str) -> bytes:
        self.calls.append(url)
        return self.content[url]


def _quality_engine(project: Path):
    sources = _SourceFetcher()
    assets = _AssetFetcher(project)
    return (
        FAOQualityRecoveryEngine(
            source_fetcher=sources,
            asset_fetcher=assets,
        ),
        sources,
        assets,
    )


def test_fao6_approves_all_five_gates_and_resume_reuses_network_evidence(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    project, upstream_calls = _prepared_project(monkeypatch, tmp_path)
    engine, sources, assets = _quality_engine(project)

    first = engine.evaluate(project)
    report_before = first.evidence_path.read_bytes()
    first_counts = (len(sources.calls), len(assets.calls), dict(upstream_calls))
    second = engine.evaluate(project)

    assert first.approved is True
    assert first.passed_gates == (
        "factual",
        "editorial",
        "visual",
        "acoustic",
        "technical",
    )
    assert first.blocking_codes == ()
    assert first.reused_existing is False
    assert second.reused_existing is True
    assert second.evidence_path.read_bytes() == report_before
    assert (len(sources.calls), len(assets.calls), upstream_calls) == (
        first_counts[0],
        first_counts[1],
        first_counts[2],
    )
    report = json.loads(report_before)
    assert report["status"] == "quality_approved_for_render_authorization"
    assert report["paid_provider_called"] is False
    assert report["render_performed"] is False
    assert report["f7_review_performed"] is False
    assert report["publication_performed"] is False
    assert Path(f"{first.evidence_path}.meta.json").is_file()


def test_fao6_unavailable_source_blocks_with_retryable_operator_diagnostic(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    project, _ = _prepared_project(monkeypatch, tmp_path)
    assets = _AssetFetcher(project)

    def unavailable(url: str) -> SourceFetchResult:
        raise TimeoutError(f"sin respuesta: {url}")

    engine = FAOQualityRecoveryEngine(
        source_fetcher=unavailable,
        asset_fetcher=assets,
    )

    with pytest.raises(FAOQualityRecoveryBlockedError) as raised:
        engine.evaluate(project)

    result = raised.value.result
    assert "factual_source_unavailable" in result.blocking_codes
    assert result.retryable is True
    assert "bloqueó el render" in result.operator_message
    assert result.evidence_path.is_file()
    assert not (project / "final" / "short.mp4").exists()


def test_fao6_corrupted_visual_is_blocked_and_nonretryable_resume_is_idempotent(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    project, _ = _prepared_project(monkeypatch, tmp_path)
    engine, sources, assets = _quality_engine(project)
    catalog = ApprovedAssetCatalog.load(
        project / "source_assets" / "automated_asset_catalog.json"
    )
    visual = next(entry for entry in catalog.entries if entry.role == "scene_visual")
    visual_path = project / "source_assets" / visual.relative_path
    visual_path.write_bytes(visual_path.read_bytes() + b"corruption")

    with pytest.raises(FAOQualityRecoveryBlockedError) as first_error:
        engine.evaluate(project)
    call_counts = (len(sources.calls), len(assets.calls))
    with pytest.raises(FAOQualityRecoveryBlockedError) as second_error:
        engine.evaluate(project)

    assert "visual_asset_quality_failed" in first_error.value.result.blocking_codes
    assert first_error.value.result.retryable is False
    assert second_error.value.result.reused_existing is True
    assert (len(sources.calls), len(assets.calls)) == call_counts


def test_fao6_stale_acoustic_report_blocks_without_invoking_asr(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    project, _ = _prepared_project(monkeypatch, tmp_path)
    conformance = project / "acceptance" / "narration_conformance.json"
    payload = json.loads(conformance.read_text(encoding="utf-8"))
    payload["manifest_id"] = "pm-stale-acoustic-evidence"
    conformance.write_text(json.dumps(payload), encoding="utf-8")
    engine, _, _ = _quality_engine(project)

    with pytest.raises(FAOQualityRecoveryBlockedError) as raised:
        engine.evaluate(project)

    assert "narration_conformance_missing_or_stale" in (
        raised.value.result.blocking_codes
    )


def test_fao6_public_delivery_mismatch_blocks_before_render(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    project, _ = _prepared_project(monkeypatch, tmp_path)
    sources = _SourceFetcher()
    engine = FAOQualityRecoveryEngine(
        source_fetcher=sources,
        asset_fetcher=lambda url: b"different-remote-bytes",
    )

    with pytest.raises(FAOQualityRecoveryBlockedError) as raised:
        engine.evaluate(project)

    assert "technical_public_delivery_unavailable" in (
        raised.value.result.blocking_codes
    )
    assert raised.value.result.delivery_network_calls == 1
    assert not (project / "render" / "creatomate_result.json").exists()


def test_fao6_repeated_narration_blocks_editorial_quality(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    project, _ = _prepared_project(monkeypatch, tmp_path)
    narration = canonical_editorial_path(project, "narracion")
    original = narration.read_text(encoding="utf-8").strip()
    narration.write_text(f"{original} {original}\n", encoding="utf-8")
    engine, _, _ = _quality_engine(project)

    with pytest.raises(FAOQualityRecoveryBlockedError) as raised:
        engine.evaluate(project)

    assert any(
        code in raised.value.result.blocking_codes
        for code in (
            "editorial_repetition",
            "editorial_spoken_duration_out_of_range",
        )
    )
