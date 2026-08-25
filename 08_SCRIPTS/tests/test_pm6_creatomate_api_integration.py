from __future__ import annotations

import json
import sys
from collections.abc import Mapping
from pathlib import Path
from types import SimpleNamespace

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from creatomate_adapter import CreatomateAdapter  # noqa: E402
from creatomate_api import (  # noqa: E402
    CREATOMATE_API_KEY_ENV,
    CreatomateAmbiguousSubmissionError,
    CreatomateApiClient,
    CreatomateApiConfig,
    CreatomateAuthenticationError,
    CreatomateConfigurationError,
    CreatomateExecutionContext,
    CreatomateFailureCategory,
    CreatomateHttpResponse,
    CreatomateInvalidResponseError,
    CreatomatePollingTimeoutError,
    CreatomateRenderService,
    CreatomateTransportError,
    estimate_render_credits,
)
from render_adapter import RenderStatus  # noqa: E402
from run_pm6_creatomate_trial import build_trial_manifest  # noqa: E402
from workspace_resolver import WorkspaceResolver  # noqa: E402

API_KEY = "pm6-secret-api-key"
MP4_BYTES = b"\x00\x00\x00\x18ftypmp42CIPS-PM6-video"
OUTPUT_URL = "https://cdn.creatomate.com/renders/render-pm6.mp4"


class FakeTransport:
    def __init__(self, *responses: object) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, object]] = []

    def request(
        self,
        *,
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: bytes | None,
        timeout_seconds: float,
        max_response_bytes: int,
    ) -> CreatomateHttpResponse:
        self.calls.append(
            {
                "method": method,
                "url": url,
                "headers": dict(headers),
                "body": body,
                "timeout_seconds": timeout_seconds,
                "max_response_bytes": max_response_bytes,
            }
        )
        if not self.responses:
            raise AssertionError("FakeTransport no tiene otra respuesta preparada.")
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        assert isinstance(response, CreatomateHttpResponse)
        return response


class SpyRecorder:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.events = []

    def record_event(self, event, **kwargs):
        if self.fail:
            raise RuntimeError("telemetry unavailable")
        self.events.append(event)
        return SimpleNamespace(success=True)


class FakeClock:
    def __init__(self) -> None:
        self.value = 0.0

    def __call__(self) -> float:
        return self.value

    def sleep(self, seconds: float) -> None:
        self.value += seconds


def _json_response(status_code: int, payload: object, **headers: str) -> CreatomateHttpResponse:
    return CreatomateHttpResponse(
        status_code=status_code,
        headers={key.casefold(): value for key, value in headers.items()},
        body=json.dumps(payload).encode("utf-8"),
    )


def _binary_response(
    content: bytes = MP4_BYTES,
    content_type: str = "video/mp4",
) -> CreatomateHttpResponse:
    return CreatomateHttpResponse(
        status_code=200,
        headers={"content-type": content_type},
        body=content,
    )


def _render_payload(status: str, **overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "id": "render-pm6",
        "status": status,
        "output_format": "mp4",
        "width": 1080,
        "height": 1920,
        "frame_rate": 30,
        "duration": 1,
    }
    values.update(overrides)
    return values


def _config(**overrides: object) -> CreatomateApiConfig:
    values = {
        "api_key": API_KEY,
        "max_attempts": 3,
        "initial_retry_delay_seconds": 0.0,
        "max_retry_delay_seconds": 0.01,
        "poll_interval_seconds": 0.0,
        "poll_timeout_seconds": 10.0,
    }
    values.update(overrides)
    return CreatomateApiConfig(**values)


def _submission():
    adapter = CreatomateAdapter()
    plan = adapter.compile(build_trial_manifest())
    return plan, adapter.prepare_submission(plan)


def _service_env(
    tmp_path: Path,
    transport: FakeTransport,
    *,
    config: CreatomateApiConfig | None = None,
    recorder: SpyRecorder | None = None,
    clock: FakeClock | None = None,
):
    projects = tmp_path / "04_PROYECTOS"
    outputs = tmp_path / "05_OUTPUTS"
    projects.mkdir()
    outputs.mkdir()
    resolver = WorkspaceResolver(projects_root=projects, outputs_root=outputs)
    workspace = resolver.resolve_execution_workspace(
        "creatomate", "pm6-test", create=True
    )
    effective_clock = clock or FakeClock()
    client = CreatomateApiClient(
        config or _config(),
        transport=transport,
        sleep_function=effective_clock.sleep,
        clock_function=effective_clock,
    )
    spy = recorder or SpyRecorder()
    service = CreatomateRenderService(
        client=client,
        workspace_resolver=resolver,
        telemetry_recorder=spy,
        sleep_function=effective_clock.sleep,
        clock_function=effective_clock,
    )
    return service, workspace, spy


def test_configuration_comes_from_environment_and_never_repr_exposes_key() -> None:
    with pytest.raises(CreatomateConfigurationError) as missing:
        CreatomateApiConfig.from_environment({})
    assert CREATOMATE_API_KEY_ENV in str(missing.value)

    config = CreatomateApiConfig.from_environment(
        {CREATOMATE_API_KEY_ENV: API_KEY}
    )
    assert config.api_key == API_KEY
    assert API_KEY not in repr(config)
    assert API_KEY not in str(config.safe_descriptor())
    assert config.safe_descriptor()["credential_source"] == CREATOMATE_API_KEY_ENV
    assert config.redact(f"Authorization: Bearer {API_KEY}") == (
        "Authorization: Bearer [REDACTED]"
    )


def test_submit_reuses_pm5_payload_and_adds_only_safe_tracking_metadata() -> None:
    plan, submission = _submission()
    transport = FakeTransport(_json_response(201, _render_payload("planned")))
    client = CreatomateApiClient(_config(), transport=transport)

    call = client.create_render(submission)
    snapshot = client.parse_snapshot(call.data)

    assert snapshot.status is RenderStatus.QUEUED
    assert len(call.attempts) == 1
    assert transport.calls[0]["method"] == "POST"
    assert transport.calls[0]["url"] == "https://api.creatomate.com/v2/renders"
    headers = transport.calls[0]["headers"]
    assert headers["Authorization"] == f"Bearer {API_KEY}"
    sent = json.loads(transport.calls[0]["body"])
    tracking = json.loads(sent.pop("metadata"))
    assert sent == submission.payload == plan.target_payload
    assert tracking == {
        "cips_idempotency_key": submission.idempotency_key,
        "cips_submission_id": submission.submission_id,
    }
    assert "metadata" not in submission.payload


@pytest.mark.parametrize(
    ("provider_status", "neutral_status"),
    [
        ("planned", RenderStatus.QUEUED),
        ("waiting", RenderStatus.RUNNING),
        ("transcribing", RenderStatus.RUNNING),
        ("rendering", RenderStatus.RUNNING),
        ("succeeded", RenderStatus.SUCCEEDED),
        ("failed", RenderStatus.FAILED),
    ],
)
def test_documented_provider_statuses_map_to_pm4(
    provider_status: str,
    neutral_status: RenderStatus,
) -> None:
    client = CreatomateApiClient(_config(), transport=FakeTransport())
    extras: dict[str, object] = {}
    if provider_status == "succeeded":
        extras["url"] = OUTPUT_URL
    if provider_status == "failed":
        extras["error_message"] = "invalid composition"
    snapshot = client.parse_snapshot(_render_payload(provider_status, **extras))
    assert snapshot.status is neutral_status


def test_rate_limit_retries_with_retry_after_and_records_attempts() -> None:
    _, submission = _submission()
    sleeps: list[float] = []
    transport = FakeTransport(
        _json_response(429, {"message": "too many requests"}, **{"Retry-After": "0"}),
        _json_response(201, _render_payload("planned")),
    )
    client = CreatomateApiClient(
        _config(max_attempts=2),
        transport=transport,
        sleep_function=sleeps.append,
    )

    call = client.create_render(submission)

    assert len(transport.calls) == 2
    assert len(call.attempts) == 2
    assert call.attempts[0].status_code == 429
    assert call.attempts[0].retryable is True
    assert sleeps == [0.0]


def test_authentication_error_is_terminal_classified_and_secret_safe() -> None:
    _, submission = _submission()
    transport = FakeTransport(
        _json_response(401, {"message": f"invalid key {API_KEY}"})
    )
    client = CreatomateApiClient(_config(), transport=transport)

    with pytest.raises(CreatomateAuthenticationError) as captured:
        client.create_render(submission)

    error = captured.value
    assert error.category is CreatomateFailureCategory.CONFIGURATION
    assert error.retryable is False
    assert error.status_code == 401
    assert len(error.attempts) == 1
    assert len(transport.calls) == 1
    assert API_KEY not in str(error)


def test_submit_transport_failure_is_ambiguous_and_never_auto_retried() -> None:
    _, submission = _submission()
    transport = FakeTransport(CreatomateTransportError("connection reset"))
    client = CreatomateApiClient(_config(max_attempts=3), transport=transport)

    with pytest.raises(CreatomateAmbiguousSubmissionError) as captured:
        client.create_render(submission)

    assert captured.value.ambiguous_submission is True
    assert captured.value.retryable is False
    assert len(transport.calls) == 1


def test_complete_lifecycle_persists_mp4_f3_emits_f8_and_reuses_idempotently(
    tmp_path: Path,
) -> None:
    transport = FakeTransport(
        _json_response(201, _render_payload("planned")),
        _json_response(200, _render_payload("rendering")),
        _json_response(
            200,
            _render_payload(
                "succeeded",
                url=OUTPUT_URL,
                file_size=len(MP4_BYTES),
                credits_used=1,
            ),
        ),
        _binary_response(),
    )
    service, workspace, recorder = _service_env(tmp_path, transport)
    context = CreatomateExecutionContext(
        workflow_id="workflow-pm6",
        run_id="run-pm6",
        task_id="task-pm6",
        correlation_id="corr-pm6",
    )

    result = service.execute(
        build_trial_manifest(), workspace_root=workspace, context=context
    )

    assert result.status is RenderStatus.SUCCEEDED
    assert len(result.output_artifact_ids) == 1
    assert result.metadata["estimated_credits"] == 1
    assert result.metadata["credits_used"] == 1.0
    assert len(transport.calls) == 4
    assert transport.calls[-1]["headers"].get("Authorization") is None
    video_files = list((workspace / "video" / "creatomate").glob("*.mp4"))
    assert len(video_files) == 1
    assert video_files[0].read_bytes() == MP4_BYTES
    sidecar = Path(f"{video_files[0]}.meta.json")
    assert sidecar.is_file()
    sidecar_data = json.loads(sidecar.read_text(encoding="utf-8"))
    assert sidecar_data["media_type"] == "video"
    assert sidecar_data["events"][0]["artifact_id"] == result.output_artifact_ids[0]

    state_files = [
        path
        for path in (workspace / "metadata" / "creatomate").glob("*.json")
        if not path.name.endswith(".meta.json")
    ]
    assert len(state_files) == 1
    state_text = state_files[0].read_text(encoding="utf-8")
    assert API_KEY not in state_text
    assert json.loads(state_text)["state"] == "succeeded"

    assert {event.operation for event in recorder.events}.issuperset(
        {"render.submit", "render.status", "render.download", "render.persist", "render.result"}
    )
    assert all(event.provider == "creatomate" for event in recorder.events)
    assert all(event.run_id == "run-pm6" for event in recorder.events)
    assert API_KEY not in str([event.to_dict() for event in recorder.events])

    repeated = service.execute(
        build_trial_manifest(), workspace_root=workspace, context=context
    )
    assert repeated.status is RenderStatus.SUCCEEDED
    assert repeated.output_artifact_ids == result.output_artifact_ids
    assert repeated.metadata["idempotency_reused"] is True
    assert len(transport.calls) == 4


def test_external_failed_status_returns_terminal_pm4_result_without_download(
    tmp_path: Path,
) -> None:
    transport = FakeTransport(
        _json_response(
            201,
            _render_payload("failed", error_message="invalid RenderScript"),
        )
    )
    service, workspace, recorder = _service_env(tmp_path, transport)

    result = service.execute(build_trial_manifest(), workspace_root=workspace)

    assert result.status is RenderStatus.FAILED
    assert result.output_artifact_ids == ()
    assert result.error == "invalid RenderScript"
    assert len(transport.calls) == 1
    assert any(
        event.operation == "render.result" and event.success is False
        for event in recorder.events
    )


def test_polling_timeout_preserves_external_job_for_safe_resume(tmp_path: Path) -> None:
    clock = FakeClock()
    transport = FakeTransport(
        _json_response(201, _render_payload("planned")),
        _json_response(200, _render_payload("rendering")),
    )
    service, workspace, _ = _service_env(
        tmp_path,
        transport,
        config=_config(poll_interval_seconds=1.0, poll_timeout_seconds=1.0),
        clock=clock,
    )

    with pytest.raises(CreatomatePollingTimeoutError):
        service.execute(build_trial_manifest(), workspace_root=workspace)

    state_file = next(
        path
        for path in (workspace / "metadata" / "creatomate").glob("*.json")
        if not path.name.endswith(".meta.json")
    )
    state = json.loads(state_file.read_text(encoding="utf-8"))
    assert state["state"] == "submitted"
    assert state["external_job_id"] == "render-pm6"
    assert len(transport.calls) == 2


def test_invalid_download_is_rejected_before_f3_persistence(tmp_path: Path) -> None:
    invalid = b"this is not an mp4"
    transport = FakeTransport(
        _json_response(
            201,
            _render_payload(
                "succeeded",
                url=OUTPUT_URL,
                file_size=len(invalid),
            ),
        ),
        _binary_response(invalid),
    )
    service, workspace, _ = _service_env(tmp_path, transport)

    with pytest.raises(CreatomateInvalidResponseError, match="MP4"):
        service.execute(build_trial_manifest(), workspace_root=workspace)

    assert not list((workspace / "video").rglob("*.mp4"))


def test_ambiguous_state_blocks_second_submit_across_service_calls(tmp_path: Path) -> None:
    transport = FakeTransport(CreatomateTransportError("timeout"))
    service, workspace, _ = _service_env(tmp_path, transport)

    with pytest.raises(CreatomateAmbiguousSubmissionError):
        service.execute(build_trial_manifest(), workspace_root=workspace)
    with pytest.raises(CreatomateAmbiguousSubmissionError):
        service.execute(build_trial_manifest(), workspace_root=workspace)

    assert len(transport.calls) == 1
    state_file = next(
        path
        for path in (workspace / "metadata" / "creatomate").glob("*.json")
        if not path.name.endswith(".meta.json")
    )
    state_text = state_file.read_text(encoding="utf-8")
    assert json.loads(state_text)["state"] == "ambiguous"
    assert API_KEY not in state_text


def test_f8_failure_is_fail_open_and_does_not_lose_render_result(tmp_path: Path) -> None:
    transport = FakeTransport(
        _json_response(
            201,
            _render_payload(
                "succeeded",
                url=OUTPUT_URL,
                file_size=len(MP4_BYTES),
            ),
        ),
        _binary_response(),
    )
    service, workspace, _ = _service_env(
        tmp_path,
        transport,
        recorder=SpyRecorder(fail=True),
    )

    result = service.execute(build_trial_manifest(), workspace_root=workspace)

    assert result.status is RenderStatus.SUCCEEDED
    assert len(result.output_artifact_ids) == 1


def test_trial_manifest_compiles_to_one_estimated_free_trial_credit() -> None:
    plan = CreatomateAdapter().compile(build_trial_manifest())

    assert plan.output.duration_seconds == 1.0
    assert plan.target_payload["elements"][0]["type"] == "shape"
    assert all(
        element["type"] in {"shape", "text"}
        for element in plan.target_payload["elements"]
    )
    assert estimate_render_credits(plan) == 1
