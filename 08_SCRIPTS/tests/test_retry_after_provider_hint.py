"""
Regresión de RetryInfo / retry_after_seconds para proveedores.

No realiza llamadas reales a servicios externos.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from gemini_llm_provider import GeminiLLMProvider
from retry_engine import RetryEngine
from retry_policy import RetryPolicy


@dataclass
class _Result:
    success: bool
    message: str = ""
    errors: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


def _run_retry_case(
    *,
    provider_delay: float | str | None,
    policy_delay: float = 5.0,
    max_policy_delay: float = 30.0,
):
    sleeps: list[float] = []
    calls = {"count": 0}

    policy = RetryPolicy(
        max_attempts=2,
        initial_delay_seconds=policy_delay,
        backoff_multiplier=2.0,
        max_delay_seconds=max_policy_delay,
        jitter_enabled=False,
    )

    engine = RetryEngine(
        policy=policy,
        sleep_function=lambda seconds: sleeps.append(seconds),
    )

    def operation():
        calls["count"] += 1

        if calls["count"] == 1:
            metadata = {
                "retryable": True,
                "status_code": 429,
            }

            if provider_delay is not None:
                metadata["retry_after_seconds"] = provider_delay

            return _Result(
                success=False,
                message="rate limited",
                errors=["429 RESOURCE_EXHAUSTED"],
                metadata=metadata,
            )

        return _Result(
            success=True,
            message="ok",
            metadata={},
        )

    result = engine.execute(
        operation=operation,
        result_success_resolver=lambda item: item.success,
        error_resolver=lambda item: (
            "\n".join(item.errors)
            if item.errors
            else item.message
        ),
        metadata_resolver=lambda item: dict(item.metadata),
    )

    return sleeps, result


def test_provider_retry_after_is_used_as_minimum_delay():
    sleeps, result = _run_retry_case(
        provider_delay=7.5,
        policy_delay=5.0,
    )

    assert result.success is True
    assert sleeps == [7.5]

    first_attempt = result.attempts[0]

    assert first_attempt.delay_seconds == 7.5
    assert (
        first_attempt.metadata[
            "provider_retry_after_seconds"
        ]
        == 7.5
    )
    assert (
        first_attempt.metadata["delay_source"]
        == "provider_retry_after"
    )


def test_policy_backoff_wins_when_it_is_longer():
    sleeps, result = _run_retry_case(
        provider_delay=2.0,
        policy_delay=5.0,
    )

    assert result.success is True
    assert sleeps == [5.0]
    assert (
        result.attempts[0].metadata["delay_source"]
        == "policy_backoff"
    )


def test_provider_retry_after_can_exceed_local_backoff_cap():
    sleeps, result = _run_retry_case(
        provider_delay=43.0,
        policy_delay=5.0,
        max_policy_delay=30.0,
    )

    assert result.success is True
    assert sleeps == [43.0]


def test_invalid_provider_retry_after_is_ignored():
    sleeps, result = _run_retry_case(
        provider_delay="invalid",
        policy_delay=5.0,
    )

    assert result.success is True
    assert sleeps == [5.0]


def test_gemini_extracts_retry_delay_from_retryinfo():
    provider = GeminiLLMProvider(
        api_key="fake-key",
        retry_enabled=False,
    )

    error = RuntimeError(
        "429 RESOURCE_EXHAUSTED. "
        "{'details': [{'retryDelay': '43s'}]}"
    )

    assert (
        provider._extract_retry_after_seconds(error)
        == 43.0
    )


def test_gemini_extracts_decimal_retry_delay_from_message():
    provider = GeminiLLMProvider(
        api_key="fake-key",
        retry_enabled=False,
    )

    error = RuntimeError(
        "Please retry in 7.492025323s."
    )

    assert (
        provider._extract_retry_after_seconds(error)
        == 7.492
    )


def test_gemini_failure_metadata_exposes_retry_after(monkeypatch):
    provider = GeminiLLMProvider(
        api_key="fake-key",
        retry_enabled=False,
    )

    class _Models:
        def generate_content(self, **kwargs):
            raise RuntimeError(
                "429 RESOURCE_EXHAUSTED. "
                "{'details': [{'retryDelay': '7s'}]}"
            )

    class _Client:
        models = _Models()

    provider._client = _Client()

    monkeypatch.setattr(
        provider,
        "_build_generation_config",
        lambda: {},
    )

    result = provider._generate_once(
        prompt="health check",
        metadata={"test": True},
    )

    assert result.success is False
    assert result.metadata["status_code"] == 429
    assert result.metadata["retryable"] is True
    assert result.metadata["retry_after_seconds"] == 7.0
