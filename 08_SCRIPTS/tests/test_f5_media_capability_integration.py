from __future__ import annotations

import ast
import inspect
from pathlib import Path
import sys

import pytest


SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from media_director import (
    CapabilityProviderExecutor,
    ImageStrategy,
    MediaDirector,
    MediaRequest,
    MediaWorkPackage,
    VideoStrategy,
)
import media_director.provider_integration as integration_module


class RecordingResolver:
    def __init__(self, provider: object) -> None:
        self.provider = provider
        self.calls: list[tuple[str, str | None]] = []

    def resolve(
        self,
        capability: str,
        *,
        preferred_provider: str | None = None,
    ) -> object:
        self.calls.append((capability, preferred_provider))
        return self.provider


class SyntheticProvider:
    def __init__(self, name: str = "fake-media") -> None:
        self.name = name


def test_f5_3_f4_capability_resolver_public_contract_is_compatible() -> None:
    from capability_resolver import CapabilityResolver

    signature = inspect.signature(CapabilityResolver.resolve)
    parameters = signature.parameters

    assert "capability" in parameters
    assert "preferred_provider" in parameters
    assert parameters["preferred_provider"].default is None



def test_f5_3_resolves_capability_and_invokes_selected_provider_once() -> None:
    provider = SyntheticProvider()
    resolver = RecordingResolver(provider)
    invocations: list[tuple[object, MediaWorkPackage]] = []

    def provider_invoker(selected_provider, work_package):
        invocations.append((selected_provider, work_package))
        return {"asset": "synthetic-image"}

    executor = CapabilityProviderExecutor(
        resolver,
        provider_invoker=provider_invoker,
    )
    package = MediaDirector(ImageStrategy()).prepare(
        MediaRequest(prompt="Create a synthetic image")
    )

    output = executor(package)

    assert resolver.calls == [("image_generation", None)]
    assert len(invocations) == 1
    assert invocations[0][0] is provider
    assert invocations[0][1] is package
    assert output == {"asset": "synthetic-image"}


def test_f5_3_forwards_preferred_provider_to_resolver() -> None:
    provider = SyntheticProvider("preferred-fake")
    resolver = RecordingResolver(provider)
    executor = CapabilityProviderExecutor(
        resolver,
        provider_invoker=lambda selected, package: selected.name,
    )
    package = MediaDirector(ImageStrategy()).prepare(
        MediaRequest(
            prompt="Create image",
            preferred_provider=" Preferred-Fake ",
        )
    )

    assert executor(package) == "preferred-fake"
    assert resolver.calls == [("image_generation", "preferred-fake")]


def test_f5_3_media_director_normalizes_resolved_provider_output() -> None:
    provider = SyntheticProvider()
    resolver = RecordingResolver(provider)
    executor = CapabilityProviderExecutor(
        resolver,
        provider_invoker=lambda selected, package: {
            "provider": selected.name,
            "prompt": package.provider_payload["prompt"],
        },
    )

    result = MediaDirector(ImageStrategy()).execute(
        MediaRequest(prompt="A clean product image"),
        provider_executor=executor,
    )

    assert result.capability == "image_generation"
    assert result.output == {
        "provider": "fake-media",
        "prompt": "A clean product image",
    }
    assert resolver.calls == [("image_generation", None)]


def test_f5_3_resolution_error_propagates_without_provider_invocation() -> None:
    class FailingResolver:
        def __init__(self) -> None:
            self.calls = 0

        def resolve(self, capability, *, preferred_provider=None):
            self.calls += 1
            raise RuntimeError("no capability available")

    resolver = FailingResolver()
    provider_calls = 0

    def provider_invoker(selected, package):
        nonlocal provider_calls
        provider_calls += 1
        return b"unexpected"

    executor = CapabilityProviderExecutor(
        resolver,
        provider_invoker=provider_invoker,
    )

    with pytest.raises(RuntimeError, match="no capability available"):
        MediaDirector(VideoStrategy()).execute(
            MediaRequest(prompt="Synthetic video"),
            provider_executor=executor,
        )

    assert resolver.calls == 1
    assert provider_calls == 0


def test_f5_3_provider_error_propagates_without_retry_or_failover() -> None:
    resolver = RecordingResolver(SyntheticProvider())
    provider_calls = 0

    def provider_invoker(selected, package):
        nonlocal provider_calls
        provider_calls += 1
        raise RuntimeError("provider failed")

    executor = CapabilityProviderExecutor(
        resolver,
        provider_invoker=provider_invoker,
    )

    with pytest.raises(RuntimeError, match="provider failed"):
        MediaDirector(VideoStrategy()).execute(
            MediaRequest(prompt="Synthetic video"),
            provider_executor=executor,
        )

    assert resolver.calls == [("video_rendering", None)]
    assert provider_calls == 1


def test_f5_3_rejects_invalid_boundaries() -> None:
    with pytest.raises(TypeError, match="resolve"):
        CapabilityProviderExecutor(
            object(),
            provider_invoker=lambda provider, package: None,
        )

    with pytest.raises(TypeError, match="provider_invoker"):
        CapabilityProviderExecutor(RecordingResolver(object()), provider_invoker=None)

    executor = CapabilityProviderExecutor(
        RecordingResolver(object()),
        provider_invoker=lambda provider, package: None,
    )
    with pytest.raises(TypeError, match="MediaWorkPackage"):
        executor(object())


def test_f5_3_integration_layer_has_no_pipeline_artifact_retry_or_sdk_imports() -> None:
    source = inspect.getsource(integration_module)
    tree = ast.parse(source)
    imported_modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)

    forbidden = {
        "stage_executor",
        "pipeline_engine",
        "artifact_store",
        "workspace_resolver",
        "retry_engine",
        "openai",
        "google.generativeai",
        "google.genai",
        "anthropic",
        "elevenlabs",
    }
    assert imported_modules.isdisjoint(forbidden)
