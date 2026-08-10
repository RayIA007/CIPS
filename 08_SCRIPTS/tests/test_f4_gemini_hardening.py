from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from gemini_llm_provider import GeminiLLMProvider
from llm_provider import ProviderResult
from runtime_models import LLMResponse


class _FakeHttpOptions:
    def __init__(self, **kwargs):
        self.kwargs = dict(kwargs)
        self.timeout = kwargs.get("timeout")
        self.retry_options = kwargs.get("retry_options")


def _install_fake_google_genai(monkeypatch: pytest.MonkeyPatch):
    captured: dict[str, object] = {"client_calls": 0}

    google_module = ModuleType("google")
    genai_module = ModuleType("google.genai")
    types_module = ModuleType("google.genai.types")

    types_module.HttpOptions = _FakeHttpOptions

    class _FakeClient:
        def __init__(self, **kwargs):
            captured["client_calls"] = int(captured["client_calls"]) + 1
            captured["client_kwargs"] = dict(kwargs)

    genai_module.Client = _FakeClient
    genai_module.types = types_module
    google_module.genai = genai_module

    monkeypatch.setitem(sys.modules, "google", google_module)
    monkeypatch.setitem(sys.modules, "google.genai", genai_module)
    monkeypatch.setitem(sys.modules, "google.genai.types", types_module)

    return captured


def test_get_client_applies_timeout_seconds_as_milliseconds(monkeypatch):
    captured = _install_fake_google_genai(monkeypatch)

    provider = GeminiLLMProvider(
        api_key="fake-key",
        timeout_seconds=120,
        retry_enabled=False,
    )

    client = provider._get_client()

    assert captured["client_calls"] == 1
    assert captured["client_kwargs"]["api_key"] == "fake-key"

    http_options = captured["client_kwargs"]["http_options"]
    assert isinstance(http_options, _FakeHttpOptions)
    assert http_options.timeout == 120_000

    assert provider._get_client() is client
    assert captured["client_calls"] == 1


def test_get_client_does_not_enable_sdk_retry(monkeypatch):
    captured = _install_fake_google_genai(monkeypatch)

    provider = GeminiLLMProvider(
        api_key="fake-key",
        timeout_seconds=15,
        retry_enabled=True,
    )

    provider._get_client()

    http_options = captured["client_kwargs"]["http_options"]
    assert http_options.kwargs == {"timeout": 15_000}
    assert http_options.retry_options is None


def test_retry_engine_behavior_is_preserved_for_transient_failure(monkeypatch):
    provider = GeminiLLMProvider(
        api_key="fake-key",
        retry_enabled=True,
        max_attempts=2,
        initial_retry_delay_seconds=0.0,
        max_retry_delay_seconds=0.0,
        retry_jitter_enabled=False,
    )

    results = iter(
        [
            ProviderResult.fail(
                message="temporarily unavailable",
                errors=["429 rate limit"],
                metadata={
                    "retryable": True,
                    "status_code": 429,
                },
            ),
            ProviderResult.ok(
                response=LLMResponse(
                    content="ok",
                    model=provider.model_name,
                ),
                message="success",
                metadata={"retryable": False},
            ),
        ]
    )

    calls = {"count": 0}

    def _fake_generate_once(*, prompt, metadata):
        calls["count"] += 1
        return next(results)

    monkeypatch.setattr(provider, "_generate_once", _fake_generate_once)

    result = provider.generate("hola")

    assert result.success is True
    assert calls["count"] == 2
    assert result.metadata["retry_enabled"] is True
    assert result.metadata["retry_attempts"] == 2
    assert result.metadata["retry_count"] == 1
    assert result.metadata["retry_exhausted"] is False
    assert result.metadata["succeeded_after_retry"] is True


def test_non_retryable_failure_still_stops_after_one_attempt(monkeypatch):
    provider = GeminiLLMProvider(
        api_key="fake-key",
        retry_enabled=True,
        max_attempts=3,
        initial_retry_delay_seconds=0.0,
        max_retry_delay_seconds=0.0,
        retry_jitter_enabled=False,
    )

    calls = {"count": 0}

    def _fake_generate_once(*, prompt, metadata):
        calls["count"] += 1
        return ProviderResult.fail(
            message="invalid api key",
            errors=["401 unauthorized"],
            metadata={
                "retryable": False,
                "status_code": 401,
            },
        )

    monkeypatch.setattr(provider, "_generate_once", _fake_generate_once)

    result = provider.generate("hola")

    assert result.success is False
    assert calls["count"] == 1
    assert result.metadata["retry_attempts"] == 1
    assert result.metadata["retry_count"] == 0
    assert result.metadata["retry_exhausted"] is False
