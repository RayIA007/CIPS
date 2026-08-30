from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
TESTS_DIR = Path(__file__).resolve().parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

from canonical_subtitles import (  # noqa: E402
    CanonicalSubtitleAlignmentError,
    CanonicalSubtitleService,
    PhysicalAudioDurationProbe,
    validate_srt_against_manifest,
)
from artifact_store import CollisionPolicy  # noqa: E402
from json2video_adapter import (  # noqa: E402
    JSON2VideoAdapter,
    estimate_json2video_credits,
    validate_json2video_payload,
)
from json2video_api import (  # noqa: E402
    JSON2VideoApiClient,
    JSON2VideoApiConfig,
    JSON2VideoHttpResponse,
    JSON2VideoRenderService,
    JSON2VideoTransportError,
)
from production_acceptance import ProductionAcceptanceBlockedError  # noqa: E402
from render_adapter import (  # noqa: E402
    RenderCompilationError,
    RenderResult,
    RenderStatus,
)
import run_pm9_full_production_acceptance as pm9_cli  # noqa: E402
from test_pm9_full_production_acceptance import (  # noqa: E402
    ASSET_TYPES,
    EXISTING_IDS,
    _environment,
)


class FakeTransport:
    def __init__(self, responses: list[JSON2VideoHttpResponse | Exception]) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, object]] = []

    def request(self, **kwargs):
        self.calls.append(dict(kwargs))
        if not self.responses:
            raise AssertionError("FakeTransport recibió una llamada no esperada.")
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def _json_response(payload: dict, status: int = 200) -> JSON2VideoHttpResponse:
    return JSON2VideoHttpResponse(
        status_code=status,
        headers={"content-type": "application/json"},
        body=json.dumps(payload).encode("utf-8"),
    )


def _mp4_response() -> JSON2VideoHttpResponse:
    return JSON2VideoHttpResponse(
        status_code=200,
        headers={"content-type": "video/mp4"},
        body=b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isomJSON2VIDEO-PM9",
    )


def _json2video_prepare(
    tmp_path: Path,
    *,
    music_volume_ceiling: float = 0.2,
    sound_effect_gain: float = 1.0,
    subtitle_mode: str = "inline_srt",
    subtitle_audio_duration: float = 10.5,
    ambient_diagram_background: bool = False,
    seed_legacy_canonical_subtitles: bool = False,
):
    project, _, acceptance, planned = _environment(tmp_path)
    if seed_legacy_canonical_subtitles:
        acceptance.canonical_subtitle_service.text_store.persist_text(
            workspace_root=project,
            relative_path=Path("subtitles") / "canonical_subtitles.srt",
            content="legacy canonical subtitles\n",
            artifact_type="canonical_subtitles",
            mime_type="text/plain",
            artifact_id=f"canonical-subtitles-{planned.manifest_id}",
            collision_policy=CollisionPolicy.REPLACE,
        )
    if subtitle_mode == "canonical_srt":
        acceptance.canonical_subtitle_service = CanonicalSubtitleService(
            acceptance.workspace_resolver,
            duration_probe=PhysicalAudioDurationProbe(
                runner=lambda command: {
                    "format": {"duration": f"{subtitle_audio_duration:.3f}"}
                }
            ),
        )
    prepared = acceptance.prepare(
        project,
        asset_types_by_sequence=ASSET_TYPES,
        existing_asset_ids_by_sequence=EXISTING_IDS,
        adapter_factory=lambda bundle, canonical_track: JSON2VideoAdapter(
            resolved_assets=bundle,
            music_volume_ceiling=music_volume_ceiling,
            sound_effect_gain=sound_effect_gain,
            subtitle_mode=subtitle_mode,
            canonical_subtitle_track=canonical_track,
            ambient_diagram_background=ambient_diagram_background,
        ),
        payload_relative_path=Path("render") / "json2video_payload.json",
        canonical_subtitles=subtitle_mode == "canonical_srt",
    )
    return project, acceptance, planned, prepared


def test_adapter_compiles_full_hd_movie_with_physical_media_and_inline_srt(
    tmp_path: Path,
) -> None:
    project, _, planned, prepared = _json2video_prepare(tmp_path)

    payload = validate_json2video_payload(
        prepared.plan.target_payload,
        expected_duration_seconds=planned.output.duration_seconds,
    )
    assert prepared.plan.target_id == "json2video.movie"
    assert prepared.evidence.ready_for_real_render is True
    assert prepared.evidence.persisted_asset_count == 13
    assert prepared.evidence.renderer_native_asset_count == 0
    assert prepared.payload_path == project / "render" / "json2video_payload.json"
    assert (payload["width"], payload["height"], payload["fps"]) == (1080, 1920, 30)
    assert payload["quality"] == "high"
    assert payload["client-data"]["publication_performed"] is False
    assert len(payload["scenes"]) == 4
    assert sum(float(scene["duration"]) for scene in payload["scenes"]) == 46.0
    assert all("transition" not in scene for scene in payload["scenes"])
    assert all(
        any(element["type"] in {"image", "video"} for element in scene["elements"])
        for scene in payload["scenes"]
    )
    visuals = [
        next(
            element
            for element in scene["elements"]
            if element["type"] in {"image", "video"}
        )
        for scene in payload["scenes"]
    ]
    assert visuals[0]["fade-out"] == pytest.approx(0.3)
    assert visuals[1]["fade-in"] == pytest.approx(0.3)
    assert visuals[1]["fade-out"] == pytest.approx(0.3)
    assert visuals[2]["fade-in"] == pytest.approx(0.3)
    media = [
        element
        for scene in payload["scenes"]
        for element in scene["elements"]
        if element["type"] in {"audio", "image", "video"}
    ]
    media.extend(
        element
        for element in payload["elements"]
        if element["type"] == "audio"
    )
    assert all(item["src"].startswith("https://cdn.example.test/") for item in media)
    assert all(
        item["cache"] is False
        for item in media
        if item["type"] == "audio"
    )
    subtitles = [
        element for element in payload["elements"] if element["type"] == "subtitles"
    ]
    assert len(subtitles) == 1
    assert "00:00:00,000 -->" in subtitles[0]["captions"]
    assert estimate_json2video_credits(planned.output.duration_seconds) == 46


def test_adapter_applies_audible_project_mix_from_the_first_frame(
    tmp_path: Path,
) -> None:
    _, _, _, prepared = _json2video_prepare(
        tmp_path,
        music_volume_ceiling=0.32,
        sound_effect_gain=1.4,
    )

    music = next(
        element
        for element in prepared.plan.target_payload["elements"]
        if element.get("id") == "background-music"
    )
    effects = [
        element
        for scene in prepared.plan.target_payload["scenes"]
        for element in scene["elements"]
        if str(element.get("id", "")).startswith("sfx-")
    ]

    assert music["start"] == 0
    assert music["volume"] == 0.32
    assert [effect["volume"] for effect in effects] == pytest.approx(
        [0.77, 0.49, 0.49, 0.63]
    )


def test_adapter_can_delegate_subtitle_timing_to_spanish_whisper(
    tmp_path: Path,
) -> None:
    _, _, _, prepared = _json2video_prepare(
        tmp_path,
        subtitle_mode="automatic_whisper",
    )

    subtitles = next(
        element
        for element in prepared.plan.target_payload["elements"]
        if element["type"] == "subtitles"
    )

    assert subtitles["language"] == "es-419"
    assert subtitles["model"] == "whisper"
    assert "captions" not in subtitles
    assert "Audio-synchronized" in subtitles["comment"]


def test_adapter_uses_physical_timing_with_canonical_words_and_f3_evidence(
    tmp_path: Path,
) -> None:
    project, _, planned, prepared = _json2video_prepare(
        tmp_path,
        subtitle_mode="canonical_srt",
    )

    result = prepared.canonical_subtitles
    assert result is not None
    assert result.artifact_path == project / "subtitles" / "canonical_subtitles.srt"
    assert result.artifact_path.is_file()
    assert result.sidecar_path.is_file()
    assert len(result.content_sha256) == 64
    assert set(result.track.audio_duration_ms_by_scene.values()) == {10500}
    subtitles = next(
        element
        for element in prepared.plan.target_payload["elements"]
        if element["type"] == "subtitles"
    )
    assert subtitles["captions"] == result.srt_text
    assert "model" not in subtitles
    assert "músculos" in subtitles["captions"]
    assert prepared.evidence.canonical_subtitles_sha256 == result.content_sha256
    assert prepared.evidence.canonical_subtitles_relative_path == (
        "subtitles/canonical_subtitles.srt"
    )
    for scene in planned.scenes:
        if scene.captions is None:
            continue
        scene_cues = [
            cue for cue in result.track.cues if cue.scene_id == scene.scene_id
        ]
        assert scene_cues[0].start_ms == round(scene.start_seconds * 1000)
        assert scene_cues[-1].end_ms == round(scene.start_seconds * 1000) + 10500
        assert all(
            left.end_ms == right.start_ms
            for left, right in zip(scene_cues, scene_cues[1:])
        )
        assert " ".join(cue.text for cue in scene_cues) == scene.narration_text
        assert all(cue.end_ms - cue.start_ms >= 650 for cue in scene_cues)
        assert all(len(cue.text.split()) >= 2 for cue in scene_cues)

    tampered = subtitles["captions"].replace("músculos", "musculos", 1)
    with pytest.raises(CanonicalSubtitleAlignmentError, match="Congruencia"):
        validate_srt_against_manifest(tampered, planned)

    cue_position = next(
        index
        for index, cue in enumerate(result.track.cues)
        if "músculos" in cue.text
    )
    tampered_cue = result.track.cues[cue_position].model_copy(
        update={
            "text": result.track.cues[cue_position].text.replace(
                "músculos", "musculos"
            )
        }
    )
    tampered_cues = list(result.track.cues)
    tampered_cues[cue_position] = tampered_cue
    tampered_track = result.track.model_copy(
        update={"cues": tuple(tampered_cues)}
    )
    adapter = JSON2VideoAdapter(
        resolved_assets=prepared.asset_run.bundle,
        subtitle_mode="canonical_srt",
        canonical_subtitle_track=tampered_track,
    )
    with pytest.raises(RenderCompilationError, match="congruencia"):
        adapter.compile(planned)


def test_canonical_subtitles_replace_legacy_content_with_content_addressed_id(
    tmp_path: Path,
) -> None:
    _, _, planned, prepared = _json2video_prepare(
        tmp_path,
        subtitle_mode="canonical_srt",
        seed_legacy_canonical_subtitles=True,
    )

    result = prepared.canonical_subtitles
    assert result is not None
    sidecar = json.loads(result.sidecar_path.read_text(encoding="utf-8"))
    artifact_ids = {event["artifact_id"] for event in sidecar["events"]}
    assert result.artifact_path.read_text(encoding="utf-8") == result.srt_text
    assert artifact_ids == {
        f"canonical-subtitles-{planned.manifest_id}-{result.content_sha256}"
    }


def test_canonical_subtitles_block_audio_that_exceeds_its_scene(
    tmp_path: Path,
) -> None:
    with pytest.raises(ProductionAcceptanceBlockedError, match="excede su escena"):
        _json2video_prepare(
            tmp_path,
            subtitle_mode="canonical_srt",
            subtitle_audio_duration=99.0,
        )


@pytest.mark.parametrize(
    ("keyword", "value"),
    [
        ("music_volume_ceiling", 1.1),
        ("sound_effect_gain", -0.1),
        ("subtitle_mode", "unknown"),
    ],
)
def test_adapter_rejects_out_of_range_mix_values(
    tmp_path: Path,
    keyword: str,
    value: float,
) -> None:
    _, _, _, prepared = _json2video_prepare(tmp_path)

    with pytest.raises(ValueError, match=keyword):
        JSON2VideoAdapter(
            resolved_assets=prepared.asset_run.bundle,
            **{keyword: value},
        )


def test_json2video_render_uses_same_configured_submission_as_prepare(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project, acceptance, _, prepared = _json2video_prepare(
        tmp_path,
        music_volume_ceiling=0.32,
        sound_effect_gain=1.4,
        subtitle_mode="automatic_whisper",
        ambient_diagram_background=True,
    )
    config = {
        "json2video_music_volume": 0.32,
        "json2video_sound_effect_gain": 1.4,
        "json2video_subtitle_mode": "automatic_whisper",
        "json2video_ambient_diagram_background": True,
    }
    captured: dict[str, str] = {}

    class FakeRenderService:
        def __init__(self, *, adapter, **kwargs) -> None:
            del kwargs
            self.adapter = adapter

        def execute(self, manifest, *, workspace_root):
            del workspace_root
            plan = self.adapter.compile(manifest)
            submission = self.adapter.prepare_submission(plan)
            captured["submission_id"] = submission.submission_id
            return RenderResult(
                job_id="rj-config-parity",
                plan_id=plan.plan_id,
                manifest_id=plan.manifest_id,
                target_id=plan.target_id,
                status=RenderStatus.SUCCEEDED,
                output_artifact_ids=("render-config-parity",),
                metadata={"credits_used": 46.0},
            )

    monkeypatch.setenv(pm9_cli.CONFIRMATION_ENV, pm9_cli.CONFIRMATION_VALUE)
    monkeypatch.setattr(
        pm9_cli.JSON2VideoApiConfig,
        "from_environment",
        lambda: object(),
    )
    monkeypatch.setattr(pm9_cli, "JSON2VideoApiClient", lambda config: config)
    monkeypatch.setattr(pm9_cli, "JSON2VideoRenderService", FakeRenderService)

    result = pm9_cli._render_command(
        prepared,
        acceptance,
        max_credits=46,
        provider="json2video",
        config=config,
    )

    assert result == 0
    assert captured["submission_id"] == prepared.submission.submission_id
    assert (project / "render" / "json2video_result.json").is_file()


def test_json2video_render_gate_requires_explicit_46_credit_authorization(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, acceptance, _, prepared = _json2video_prepare(tmp_path)
    monkeypatch.delenv(pm9_cli.CONFIRMATION_ENV, raising=False)

    with pytest.raises(ProductionAcceptanceBlockedError, match="46 créditos"):
        pm9_cli._render_command(
            prepared,
            acceptance,
            max_credits=46,
            provider="json2video",
        )


def test_client_uses_api_key_parses_terminal_metadata_and_downloads_mp4() -> None:
    project_id = "JkGxEoPRF9EgRb32"
    output_url = "https://assets.json2video.com/render/test.mp4"
    transport = FakeTransport(
        [
            _json_response({"success": True, "project": project_id}),
            _json_response(
                {
                    "success": True,
                    "movie": {
                        "success": True,
                        "status": "done",
                        "message": "",
                        "project": project_id,
                        "url": output_url,
                        "width": 1080,
                        "height": 1920,
                        "duration": 46,
                        "size": 1024,
                        "consumed_credits": [{"credits": 46}],
                    },
                }
            ),
            _mp4_response(),
        ]
    )
    config = JSON2VideoApiConfig(api_key="secret-test-key")
    client = JSON2VideoApiClient(config, transport=transport)

    submitted = client.create_movie({"scenes": [{"elements": []}]})
    terminal = client.get_movie(submitted.project_id)
    content = client.download_movie(terminal.output_url or "")

    assert submitted.project_id == project_id
    assert terminal.status is RenderStatus.SUCCEEDED
    assert (terminal.width, terminal.height, terminal.duration) == (1080, 1920, 46.0)
    assert terminal.consumed_credits == 46.0
    assert b"ftyp" in content
    assert all(
        call["headers"]["x-api-key"] == "secret-test-key"
        for call in transport.calls[:2]
    )
    assert "x-api-key" not in transport.calls[2]["headers"]
    assert "secret-test-key" not in repr(config)


def test_submit_transport_failure_is_not_retried() -> None:
    transport = FakeTransport([JSON2VideoTransportError("timeout")])
    client = JSON2VideoApiClient(
        JSON2VideoApiConfig(api_key="secret"),
        transport=transport,
    )

    with pytest.raises(Exception) as captured:
        client.create_movie({"scenes": [{"elements": []}]})

    assert getattr(captured.value, "ambiguous_submission", False) is True
    assert len(transport.calls) == 1


def test_service_persists_and_reuses_success_without_second_submission(
    tmp_path: Path,
) -> None:
    project, acceptance, _, prepared = _json2video_prepare(tmp_path)
    project_id = "JkGxEoPRF9EgRb32"
    output_url = "https://assets.json2video.com/render/test.mp4"
    transport = FakeTransport(
        [
            _json_response({"success": True, "project": project_id}),
            _json_response(
                {
                    "success": True,
                    "movie": {
                        "success": True,
                        "status": "done",
                        "message": "",
                        "project": project_id,
                        "url": output_url,
                        "width": 1080,
                        "height": 1920,
                        "duration": 46,
                        "size": 1024,
                        "consumed_credits": [{"credits": 46}],
                    },
                }
            ),
            _mp4_response(),
        ]
    )
    service = JSON2VideoRenderService(
        client=JSON2VideoApiClient(
            JSON2VideoApiConfig(api_key="secret", poll_interval_seconds=0.01),
            transport=transport,
        ),
        workspace_resolver=acceptance.workspace_resolver,
        adapter=JSON2VideoAdapter(resolved_assets=prepared.asset_run.bundle),
    )

    result = service.execute(prepared.manifest, workspace_root=project)
    reused = service.execute(prepared.manifest, workspace_root=project)

    assert result.status is RenderStatus.SUCCEEDED
    assert result.metadata["width"] == 1080
    assert result.metadata["height"] == 1920
    assert result.metadata["credits_used"] == 46.0
    assert reused.status is RenderStatus.SUCCEEDED
    assert reused.metadata["idempotency_reused"] is True
    assert len(transport.calls) == 3
    video_path = project / "video" / "json2video" / f"{prepared.submission.submission_id}.mp4"
    assert video_path.is_file()


def test_cli_parser_keeps_creatomate_default_and_accepts_json2video() -> None:
    assert pm9_cli._parser().parse_args(["prepare"]).provider == "creatomate"
    assert (
        pm9_cli._parser().parse_args(["prepare", "--provider", "json2video"]).provider
        == "json2video"
    )
