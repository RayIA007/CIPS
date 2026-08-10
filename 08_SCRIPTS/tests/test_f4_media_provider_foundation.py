from __future__ import annotations

from pathlib import Path
import sys

import pytest

SCRIPT_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from capability_registry import CapabilityRegistry  # noqa: E402
from capability_resolver import (  # noqa: E402
    CapabilityNotAvailableError,
    CapabilityResolver,
    PreferredProviderUnavailableError,
)
from media_provider import (  # noqa: E402
    MediaProvider,
    MediaRequest,
    MediaResult,
    normalize_capability,
)
from media_provider_registry import (  # noqa: E402
    MediaProviderAlreadyRegisteredError,
    MediaProviderDisabledError,
    MediaProviderNotFoundError,
    MediaProviderRegistry,
)


class FakeVoiceProvider(MediaProvider):
    provider_name = "fake_voice"

    def capabilities(self):
        return {
            "voice_synthesis": {
                "languages": ["es-MX", "en-US"],
                "source": "fake",
            }
        }

    def generate(self, request: MediaRequest) -> MediaResult:
        errors = self.validate_input(request)
        if errors:
            return MediaResult.fail(errors=errors)
        return MediaResult.ok(
            b"fake-audio",
            metadata={"provider": self.provider_name},
        )


class AlphaVoiceProvider(FakeVoiceProvider):
    provider_name = "alpha_voice"


class ZetaVoiceProvider(FakeVoiceProvider):
    provider_name = "zeta_voice"


class FakeImageProvider(MediaProvider):
    provider_name = "fake_image"

    def capabilities(self):
        return {
            "image_generation": {
                "formats": ["png"],
                "source": "fake",
            }
        }

    def generate(self, request: MediaRequest) -> MediaResult:
        errors = self.validate_input(request)
        if errors:
            return MediaResult.fail(errors=errors)
        return MediaResult.ok(b"fake-image")


class MultiMediaProvider(MediaProvider):
    provider_name = "multi"

    def capabilities(self):
        return {
            "voice_synthesis": {"languages": ["es-MX"]},
            "image_generation": {"formats": ["png", "jpg"]},
        }

    def generate(self, request: MediaRequest) -> MediaResult:
        errors = self.validate_input(request)
        if errors:
            return MediaResult.fail(errors=errors)
        return MediaResult.ok(b"multi-output")


class InvalidCapabilitiesProvider(MediaProvider):
    provider_name = "invalid_capabilities"

    def capabilities(self):
        return ["voice_synthesis"]

    def generate(self, request: MediaRequest) -> MediaResult:
        return MediaResult.ok(b"unused")


class InvalidMetadataProvider(MediaProvider):
    provider_name = "invalid_metadata"

    def capabilities(self):
        return {"voice_synthesis": True}

    def generate(self, request: MediaRequest) -> MediaResult:
        return MediaResult.ok(b"unused")


def test_media_provider_is_abstract():
    with pytest.raises(TypeError):
        MediaProvider()


def test_media_result_success_and_failure_helpers_copy_inputs():
    warnings = ["w"]
    metadata = {"k": "v"}
    success = MediaResult.ok(b"x", warnings=warnings, metadata=metadata)
    failure = MediaResult.fail(errors=["e"], metadata=metadata)
    warnings.append("later")
    metadata["k"] = "changed"

    assert success.success is True
    assert success.output == b"x"
    assert success.warnings == ["w"]
    assert success.metadata == {"k": "v"}
    assert failure.success is False
    assert failure.output is None
    assert failure.errors == ["e"]
    assert failure.metadata == {"k": "v"}


def test_normalize_capability_is_case_and_whitespace_insensitive():
    assert normalize_capability("  Voice_Synthesis ") == "voice_synthesis"


@pytest.mark.parametrize("value", ["", "   "])
def test_normalize_capability_rejects_empty(value):
    with pytest.raises(ValueError):
        normalize_capability(value)


def test_normalize_capability_rejects_non_string():
    with pytest.raises(TypeError):
        normalize_capability(123)


def test_provider_validates_supported_capability():
    provider = FakeVoiceProvider()
    request = MediaRequest(
        capability="VOICE_SYNTHESIS",
        payload="hola",
    )
    assert provider.validate_input(request) == []


def test_provider_rejects_unsupported_capability():
    provider = FakeVoiceProvider()
    request = MediaRequest(
        capability="image_generation",
        payload="prompt",
    )
    errors = provider.validate_input(request)
    assert len(errors) == 1
    assert "no soporta" in errors[0]


def test_provider_rejects_invalid_request_type():
    provider = FakeVoiceProvider()
    assert provider.validate_input("not-a-request") == [
        "request debe ser una instancia de MediaRequest."
    ]


def test_provider_default_cost_estimate_is_unknown_not_invented():
    provider = FakeVoiceProvider()
    request = MediaRequest("voice_synthesis", "hola")
    assert provider.estimate_cost(request) is None


def test_provider_info_contains_normalized_capabilities():
    info = MultiMediaProvider().get_provider_info()
    assert info == {
        "provider": "multi",
        "capabilities": ["image_generation", "voice_synthesis"],
    }


def test_fake_provider_generates_without_external_calls():
    provider = FakeVoiceProvider()
    result = provider.generate(MediaRequest("voice_synthesis", "hola"))
    assert result.success is True
    assert result.output == b"fake-audio"
    assert result.metadata["provider"] == "fake_voice"


def test_registry_registers_and_resolves_case_insensitively():
    provider = FakeVoiceProvider()
    registry = MediaProviderRegistry([provider])
    assert registry.get("  FAKE_VOICE ") is provider
    assert registry.list() == ["fake_voice"]


def test_registry_rejects_non_media_provider():
    registry = MediaProviderRegistry()
    with pytest.raises(TypeError):
        registry.register(object())


def test_registry_rejects_reserved_base_name():
    class ReservedProvider(FakeVoiceProvider):
        provider_name = " base "

    registry = MediaProviderRegistry()
    with pytest.raises(ValueError):
        registry.register(ReservedProvider())


def test_registry_rejects_duplicate_by_normalized_name():
    registry = MediaProviderRegistry([FakeVoiceProvider()])
    with pytest.raises(MediaProviderAlreadyRegisteredError):
        registry.register(FakeVoiceProvider())


def test_registry_replace_is_explicit():
    first = FakeVoiceProvider()
    second = FakeVoiceProvider()
    registry = MediaProviderRegistry([first])
    registry.register(second, replace=True)
    assert registry.get("fake_voice") is second


def test_registry_disable_blocks_normal_get_but_preserves_inventory():
    provider = FakeVoiceProvider()
    registry = MediaProviderRegistry([provider])
    registry.disable("fake_voice")

    with pytest.raises(MediaProviderDisabledError):
        registry.get("fake_voice")

    assert registry.get("fake_voice", require_enabled=False) is provider
    assert registry.list(enabled_only=True) == []
    assert registry.list() == ["fake_voice"]


def test_registry_enable_restores_provider():
    provider = FakeVoiceProvider()
    registry = MediaProviderRegistry([provider])
    registry.disable("fake_voice")
    registry.enable("fake_voice")
    assert registry.get("fake_voice") is provider


def test_registry_unregister_returns_provider_and_removes_it():
    provider = FakeVoiceProvider()
    registry = MediaProviderRegistry([provider])
    assert registry.unregister("fake_voice") is provider
    assert registry.exists("fake_voice") is False
    with pytest.raises(MediaProviderNotFoundError):
        registry.get("fake_voice")


def test_registry_capabilities_are_copied():
    provider = FakeVoiceProvider()
    registry = MediaProviderRegistry([provider])
    capabilities = registry.capabilities("fake_voice")
    capabilities["voice_synthesis"]["source"] = "mutated"
    capabilities["voice_synthesis"]["languages"].append("fr-FR")
    current = provider.capabilities()["voice_synthesis"]
    assert current["source"] == "fake"
    assert current["languages"] == ["es-MX", "en-US"]


def test_registry_rejects_invalid_capability_contract():
    registry = MediaProviderRegistry([InvalidCapabilitiesProvider()])
    with pytest.raises(TypeError):
        registry.capabilities("invalid_capabilities")


def test_registry_rejects_invalid_capability_metadata_contract():
    registry = MediaProviderRegistry([InvalidMetadataProvider()])
    with pytest.raises(TypeError):
        registry.capabilities("invalid_metadata")


def test_registry_status_is_serializable_shape():
    registry = MediaProviderRegistry([FakeVoiceProvider()])
    assert registry.status() == {
        "fake_voice": {
            "enabled": True,
            "provider": "fake_voice",
            "capabilities": {
                "voice_synthesis": {
                    "languages": ["es-MX", "en-US"],
                    "source": "fake",
                }
            },
        }
    }


def test_capability_registry_builds_dynamic_index():
    providers = MediaProviderRegistry(
        [FakeVoiceProvider(), FakeImageProvider(), MultiMediaProvider()]
    )
    capabilities = CapabilityRegistry(providers)

    assert capabilities.capabilities() == {
        "image_generation": ["fake_image", "multi"],
        "voice_synthesis": ["fake_voice", "multi"],
    }


def test_capability_registry_reflects_enabled_state_without_rebuild():
    providers = MediaProviderRegistry([FakeVoiceProvider()])
    capabilities = CapabilityRegistry(providers)
    assert capabilities.providers_for("voice_synthesis") == ["fake_voice"]

    providers.disable("fake_voice")
    assert capabilities.providers_for("voice_synthesis") == []
    assert capabilities.providers_for(
        "voice_synthesis", enabled_only=False
    ) == ["fake_voice"]


def test_capability_registry_reports_provider_support():
    providers = MediaProviderRegistry([MultiMediaProvider()])
    capabilities = CapabilityRegistry(providers)
    assert capabilities.provider_supports("multi", "voice_synthesis") is True
    assert capabilities.provider_supports("multi", "video_rendering") is False


def test_capability_registry_returns_metadata_copy():
    providers = MediaProviderRegistry([FakeVoiceProvider()])
    capabilities = CapabilityRegistry(providers)
    metadata = capabilities.metadata_for("fake_voice", "voice_synthesis")
    metadata["source"] = "changed"
    assert capabilities.metadata_for(
        "fake_voice", "voice_synthesis"
    )["source"] == "fake"


def test_resolver_selects_first_candidate_alphabetically():
    providers = MediaProviderRegistry(
        [ZetaVoiceProvider(), AlphaVoiceProvider()]
    )
    resolver = CapabilityResolver(providers)
    assert resolver.resolve("voice_synthesis").provider_name == "alpha_voice"


def test_resolver_honors_explicit_preferred_provider():
    providers = MediaProviderRegistry(
        [ZetaVoiceProvider(), AlphaVoiceProvider()]
    )
    resolver = CapabilityResolver(providers)
    assert resolver.resolve(
        "voice_synthesis",
        preferred_provider="ZETA_VOICE",
    ).provider_name == "zeta_voice"


def test_resolver_rejects_preferred_provider_without_capability():
    providers = MediaProviderRegistry(
        [FakeVoiceProvider(), FakeImageProvider()]
    )
    resolver = CapabilityResolver(providers)
    with pytest.raises(PreferredProviderUnavailableError):
        resolver.resolve(
            "voice_synthesis",
            preferred_provider="fake_image",
        )


def test_resolver_rejects_disabled_preferred_provider():
    providers = MediaProviderRegistry([FakeVoiceProvider()])
    providers.disable("fake_voice")
    resolver = CapabilityResolver(providers)
    with pytest.raises(PreferredProviderUnavailableError):
        resolver.resolve(
            "voice_synthesis",
            preferred_provider="fake_voice",
        )


def test_resolver_excludes_named_candidates():
    providers = MediaProviderRegistry(
        [ZetaVoiceProvider(), AlphaVoiceProvider()]
    )
    resolver = CapabilityResolver(providers)
    assert resolver.resolve(
        "voice_synthesis",
        exclude=["alpha_voice"],
    ).provider_name == "zeta_voice"


def test_resolver_raises_when_no_capability_is_available():
    providers = MediaProviderRegistry([FakeImageProvider()])
    resolver = CapabilityResolver(providers)
    with pytest.raises(CapabilityNotAvailableError):
        resolver.resolve("voice_synthesis")


def test_resolver_rejects_capability_registry_from_other_provider_registry():
    first = MediaProviderRegistry([FakeVoiceProvider()])
    second = MediaProviderRegistry([FakeImageProvider()])
    with pytest.raises(ValueError):
        CapabilityResolver(first, CapabilityRegistry(second))


def test_foundation_does_not_import_llm_provider_contract():
    module_text = "\n".join(
        (SCRIPT_DIR / name).read_text(encoding="utf-8")
        for name in (
            "media_provider.py",
            "media_provider_registry.py",
            "capability_registry.py",
            "capability_resolver.py",
        )
    )
    assert "from llm_provider" not in module_text
    assert "import llm_provider" not in module_text


def test_foundation_has_no_retry_or_external_provider_execution():
    provider = FakeVoiceProvider()
    providers = MediaProviderRegistry([provider])
    resolver = CapabilityResolver(providers)
    resolved = resolver.resolve("voice_synthesis")

    assert resolved is provider
    assert len(providers) == 1
    assert providers.list() == ["fake_voice"]
