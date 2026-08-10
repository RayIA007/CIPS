from __future__ import annotations

from pathlib import Path

import yaml

from llm_config import LLMConfigManager, LLMSettings
from llm_provider import LLMProvider, ProviderResult
from llm_provider_factory import LLMProviderFactory
from llm_provider_name import normalize_provider_name
from provider_registry import ProviderRegistry


class DummyProvider(LLMProvider):
    provider_name = "Vendor-Alpha"
    model_name = "dummy-v1"

    def generate(
        self,
        prompt: str,
        metadata: dict | None = None,
    ) -> ProviderResult:
        return ProviderResult.fail(
            message="Dummy provider; no external execution.",
            metadata=dict(metadata or {}),
        )


def test_shared_provider_name_normalization_is_deterministic() -> None:
    assert normalize_provider_name(" Vendor-Alpha ") == "vendor_alpha"
    assert normalize_provider_name("Vendor Alpha") == "vendor_alpha"
    assert normalize_provider_name("VENDOR_ALPHA") == "vendor_alpha"


def test_factory_registers_builtin_openai_without_removing_existing() -> None:
    assert LLMProviderFactory.available_providers() == [
        "gemini",
        "manual",
        "ollama",
        "openai",
    ]


def test_factory_creates_openai_from_canonical_config_aliases() -> None:
    provider = LLMProviderFactory.create(
        " OpenAI ",
        api_key="test-key",
        model="gpt-5-mini",
        temperature=0.3,
        timeout_seconds=33,
        max_output_tokens=777,
        retry_enabled=False,
    )

    assert provider.provider_name == "openai"
    assert provider.model_name == "gpt-5-mini"
    assert provider.timeout == 33
    assert provider.max_tokens == 777


def test_factory_preserves_explicit_openai_legacy_options() -> None:
    provider = LLMProviderFactory.create(
        "openai",
        api_key="test-key",
        timeout=99,
        timeout_seconds=33,
        max_tokens=111,
        max_output_tokens=222,
        retry_enabled=False,
    )

    assert provider.timeout == 99
    assert provider.max_tokens == 111


def test_factory_dynamic_registration_uses_shared_normalization() -> None:
    original = dict(LLMProviderFactory._providers)
    try:
        LLMProviderFactory.register(
            "Vendor-Alpha",
            DummyProvider,
        )
        assert LLMProviderFactory.is_registered("vendor alpha")
        created = LLMProviderFactory.create("VENDOR_ALPHA")
        assert isinstance(created, DummyProvider)
    finally:
        LLMProviderFactory._providers = original


def test_provider_registry_uses_shared_normalization() -> None:
    provider = DummyProvider()
    registry = ProviderRegistry()
    registry.register(provider)

    assert registry.exists("vendor alpha")
    assert registry.get("VENDOR_ALPHA") is provider
    assert registry.list() == ["vendor_alpha"]


def test_config_manager_builds_openai_from_common_runtime_settings() -> None:
    manager = LLMConfigManager()
    settings = LLMSettings(
        mode="automatic",
        provider="openai",
        model="gpt-5-mini",
        enabled=True,
        timeout_seconds=45,
        temperature=0.4,
        max_output_tokens=1234,
        provider_options={
            "api_key": "test-key",
            "retry_enabled": False,
        },
        metadata={"provider_enabled": True},
    )

    provider = manager.create_provider(settings)

    assert provider.provider_name == "openai"
    assert provider.model_name == "gpt-5-mini"
    assert provider.timeout == 45
    assert provider.max_tokens == 1234
    assert provider.temperature == 0.4


def test_provider_specific_options_preserve_existing_precedence() -> None:
    manager = LLMConfigManager()
    settings = LLMSettings(
        mode="automatic",
        provider="openai",
        model="gpt-5-mini",
        enabled=True,
        timeout_seconds=45,
        temperature=0.4,
        max_output_tokens=1234,
        provider_options={
            "api_key": "test-key",
            "model": "gpt-5",
            "timeout": 88,
            "max_tokens": 999,
            "retry_enabled": False,
        },
        metadata={"provider_enabled": True},
    )

    provider = manager.create_provider(settings)

    assert provider.model_name == "gpt-5"
    assert provider.timeout == 88
    assert provider.max_tokens == 999


def test_disabled_provider_falls_back_to_manual_without_foreign_options() -> None:
    manager = LLMConfigManager()
    settings = LLMSettings(
        mode="automatic",
        provider="openai",
        model="gpt-5",
        enabled=True,
        timeout_seconds=120,
        provider_options={"api_key": "must-not-reach-manual"},
        metadata={"provider_enabled": False},
    )

    provider = manager.create_provider(settings)
    assert provider.provider_name == "manual"


def test_unknown_provider_falls_back_to_manual() -> None:
    manager = LLMConfigManager()
    settings = LLMSettings(
        mode="automatic",
        provider="not_installed",
        model="unknown-model",
        enabled=True,
        provider_options={"unexpected": "value"},
        metadata={"provider_enabled": True},
    )

    provider = manager.create_provider(settings)
    assert provider.provider_name == "manual"


def test_load_normalizes_provider_section_and_provider_enabled(tmp_path: Path) -> None:
    config_path = tmp_path / "llm.yaml"
    config_path.write_text(
        """
runtime:
  mode: automatic
  provider: Vendor-Alpha
  model: runtime-model
  enabled: true
  timeout_seconds: 42
  temperature: 0.6
  max_output_tokens: 321
  provider_options:
    runtime_flag: true
providers:
  Vendor Alpha:
    enabled: false
    options:
      provider_flag: true
""".strip(),
        encoding="utf-8",
    )

    settings = LLMConfigManager(config_path=config_path).load()

    assert settings.provider == "vendor_alpha"
    assert settings.metadata["provider_enabled"] is False
    assert settings.provider_options == {
        "runtime_flag": True,
        "provider_flag": True,
    }


def test_repository_llm_yaml_marks_openai_available_without_switching_runtime() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    config_path = repo_root / "01_CONFIG" / "llm.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))

    assert config["runtime"]["provider"] == "gemini"

    openai_config = config["providers"]["openai"]
    assert openai_config["enabled"] is True
    assert "pendiente de implementación" not in openai_config[
        "description"
    ].lower()
    assert openai_config["options"] == {
        "model": "gpt-5",
        "api_key_env": "OPENAI_API_KEY",
        "temperature": 0.2,
        "max_output_tokens": 4000,
        "timeout_seconds": 120,
    }


def test_existing_gemini_ollama_and_manual_construction_remains_compatible() -> None:
    manual = LLMProviderFactory.create("manual")
    gemini = LLMProviderFactory.create(
        "gemini",
        model="gemini-3.5-flash",
        api_key="test-key",
        temperature=0.2,
        max_output_tokens=128,
        timeout_seconds=30,
        retry_enabled=False,
    )
    ollama = LLMProviderFactory.create(
        "ollama",
        model="llama3:8b",
        base_url="http://localhost:11434/v1",
        timeout_seconds=25,
    )

    assert manual.provider_name == "manual"
    assert gemini.provider_name == "gemini"
    assert ollama.provider_name == "ollama"
