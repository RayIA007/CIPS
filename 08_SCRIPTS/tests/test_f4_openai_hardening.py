from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace

import openai_provider
from openai_provider import OpenAIProvider
from retry_engine import RetryEngine
from retry_policy import RetryPolicy


class FakeResponses:
    def __init__(self, sequence):
        self.sequence = list(sequence)
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(dict(kwargs))
        if not self.sequence:
            raise AssertionError("No hay respuesta fake configurada.")
        item = self.sequence.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class FakeClient:
    def __init__(self, sequence):
        self.responses = FakeResponses(sequence)


class FakeOpenAIFactory:
    def __init__(self, sequence):
        self.sequence = list(sequence)
        self.calls: list[dict] = []
        self.clients: list[FakeClient] = []

    def __call__(self, **kwargs):
        self.calls.append(dict(kwargs))
        client = FakeClient(self.sequence)
        self.clients.append(client)
        return client


@dataclass
class FakeUsage:
    input_tokens: int = 11
    output_tokens: int = 7
    total_tokens: int = 18
    output_tokens_details: object = field(
        default_factory=lambda: SimpleNamespace(
            reasoning_tokens=3,
        )
    )


@dataclass
class FakeResponse:
    output_text: str = "respuesta de prueba"
    usage: object = field(default_factory=FakeUsage)
    _request_id: str = "req_test_123"


def _exception(name: str, message: str, status_code=None):
    cls = type(name, (Exception,), {})
    error = cls(message)
    if status_code is not None:
        error.status_code = status_code
    return error


def _retry_components(max_attempts: int = 3):
    policy = RetryPolicy(
        max_attempts=max_attempts,
        initial_delay_seconds=0.0,
        backoff_multiplier=2.0,
        max_delay_seconds=0.0,
        jitter_enabled=False,
    )
    engine = RetryEngine(
        policy=policy,
        sleep_function=lambda _seconds: None,
    )
    return policy, engine


def test_client_applies_timeout_and_disables_sdk_retries(monkeypatch):
    factory = FakeOpenAIFactory([FakeResponse()])
    monkeypatch.setattr(openai_provider, "OpenAI", factory)

    provider = OpenAIProvider(
        api_key="sk-test",
        timeout=17,
        retry_enabled=False,
    )

    client_a = provider.get_client()
    client_b = provider.get_client()

    assert client_a is client_b
    assert len(factory.calls) == 1
    assert factory.calls[0] == {
        "api_key": "sk-test",
        "timeout": 17.0,
        "max_retries": 0,
    }


def test_generate_preserves_output_limit_and_usage_metadata(monkeypatch):
    factory = FakeOpenAIFactory([FakeResponse()])
    monkeypatch.setattr(openai_provider, "OpenAI", factory)

    provider = OpenAIProvider(
        api_key="sk-test",
        model="gpt-5",
        max_tokens=321,
        retry_enabled=False,
    )

    result = provider.generate("hola")

    assert result.success is True
    assert result.response is not None
    assert result.response.content == "respuesta de prueba"

    call = factory.clients[0].responses.calls[0]
    assert call["model"] == "gpt-5"
    assert call["input"] == "hola"
    assert call["max_output_tokens"] == 321

    assert result.metadata["prompt_tokens"] == 11
    assert result.metadata["response_tokens"] == 7
    assert result.metadata["thinking_tokens"] == 3
    assert result.metadata["total_tokens"] == 18
    assert result.metadata["request_id"] == "req_test_123"
    assert result.metadata["sdk_retries_enabled"] is False


def test_cips_retry_recovers_from_openai_connection_error(monkeypatch):
    temporary_error = _exception(
        "APIConnectionError",
        "temporary connection error",
    )
    factory = FakeOpenAIFactory(
        [temporary_error, FakeResponse()]
    )
    monkeypatch.setattr(openai_provider, "OpenAI", factory)

    policy, engine = _retry_components(max_attempts=3)
    provider = OpenAIProvider(
        api_key="sk-test",
        retry_policy=policy,
        retry_engine=engine,
    )

    result = provider.generate("hola")

    assert result.success is True
    assert len(factory.clients[0].responses.calls) == 2
    assert result.metadata["retry_enabled"] is True
    assert result.metadata["retry_attempts"] == 2
    assert result.metadata["retry_count"] == 1
    assert result.metadata["succeeded_after_retry"] is True
    assert result.metadata["retry_exhausted"] is False


def test_permanent_openai_error_is_not_retried(monkeypatch):
    permanent_error = _exception(
        "BadRequestError",
        "400 invalid request",
        status_code=400,
    )
    factory = FakeOpenAIFactory(
        [permanent_error, FakeResponse()]
    )
    monkeypatch.setattr(openai_provider, "OpenAI", factory)

    policy, engine = _retry_components(max_attempts=3)
    provider = OpenAIProvider(
        api_key="sk-test",
        retry_policy=policy,
        retry_engine=engine,
    )

    result = provider.generate("hola")

    assert result.success is False
    assert len(factory.clients[0].responses.calls) == 1
    assert result.metadata["status_code"] == 400
    assert result.metadata["retryable"] is False
    assert result.metadata["error_classification"] == "permanent"
    assert result.metadata["retry_count"] == 0
    assert result.metadata["retry_exhausted"] is False


def test_openai_error_message_redacts_api_key(monkeypatch):
    secret = "sk-super-secret-test"
    auth_error = _exception(
        "AuthenticationError",
        f"401 invalid api key {secret}",
        status_code=401,
    )
    factory = FakeOpenAIFactory([auth_error])
    monkeypatch.setattr(openai_provider, "OpenAI", factory)

    policy, engine = _retry_components(max_attempts=3)
    provider = OpenAIProvider(
        api_key=secret,
        retry_policy=policy,
        retry_engine=engine,
    )

    result = provider.generate("hola")

    assert result.success is False
    assert secret not in "\n".join(result.errors)
    assert "[REDACTED]" in "\n".join(result.errors)
    assert result.metadata["retryable"] is False


def test_missing_credentials_skips_sdk_and_retry(monkeypatch):
    factory = FakeOpenAIFactory([FakeResponse()])
    monkeypatch.setattr(openai_provider, "OpenAI", factory)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    provider = OpenAIProvider(api_key=None)
    result = provider.generate("hola")

    assert result.success is False
    assert factory.calls == []
    assert result.metadata["missing_credentials"] is True
    assert result.metadata["retryable"] is False
    assert result.metadata["retry_skipped"] is True
    assert result.metadata["retry_skip_reason"] == "missing_credentials"


def test_configure_timeout_invalidates_cached_client(monkeypatch):
    factory = FakeOpenAIFactory([FakeResponse()])
    monkeypatch.setattr(openai_provider, "OpenAI", factory)

    provider = OpenAIProvider(
        api_key="sk-test",
        timeout=10,
        retry_enabled=False,
    )

    first_client = provider.get_client()
    provider.configure(timeout=25)
    second_client = provider.get_client()

    assert first_client is not second_client
    assert len(factory.calls) == 2
    assert factory.calls[0]["timeout"] == 10.0
    assert factory.calls[1]["timeout"] == 25.0
    assert factory.calls[0]["max_retries"] == 0
    assert factory.calls[1]["max_retries"] == 0
