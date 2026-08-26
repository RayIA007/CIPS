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
from render_adapter import RenderStatus  # noqa: E402
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


def _json2video_prepare(tmp_path: Path):
    project, _, acceptance, planned = _environment(tmp_path)
    prepared = acceptance.prepare(
        project,
        asset_types_by_sequence=ASSET_TYPES,
        existing_asset_ids_by_sequence=EXISTING_IDS,
        adapter_factory=lambda bundle: JSON2VideoAdapter(resolved_assets=bundle),
        payload_relative_path=Path("render") / "json2video_payload.json",
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
    assert all(
        any(element["type"] in {"image", "video"} for element in scene["elements"])
        for scene in payload["scenes"]
    )
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
    subtitles = [
        element for element in payload["elements"] if element["type"] == "subtitles"
    ]
    assert len(subtitles) == 1
    assert "00:00:00,000 -->" in subtitles[0]["captions"]
    assert estimate_json2video_credits(planned.output.duration_seconds) == 46


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
