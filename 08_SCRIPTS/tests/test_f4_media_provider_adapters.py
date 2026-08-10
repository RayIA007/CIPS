from __future__ import annotations

from pathlib import Path
import sys

import pytest

SCRIPT_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from capability_registry import CapabilityRegistry  # noqa: E402
from capability_resolver import CapabilityResolver  # noqa: E402
from fake_media_provider import FakeMediaProvider  # noqa: E402
from media_provider import MediaRequest  # noqa: E402
from media_provider_adapters import (  # noqa: E402
    ImageGenerationAdapter,
    VideoRenderingAdapter,
    VoiceSynthesisAdapter,
)
from media_provider_registry import MediaProviderRegistry  # noqa: E402


def test_voice_adapter_declares_expected_capability():
    provider = VoiceSynthesisAdapter(lambda project_dir: project_dir / "voice.mp3")
    assert provider.capabilities() == {"voice_synthesis": {}}


def test_image_adapter_declares_expected_capability():
    provider = ImageGenerationAdapter(lambda project_dir: [project_dir / "01.png"])
    assert provider.capabilities() == {"image_generation": {}}


def test_video_adapter_declares_expected_capability():
    provider = VideoRenderingAdapter(lambda project_dir: project_dir / "short.mp4")
    assert provider.capabilities() == {"video_rendering": {}}


def test_adapter_copies_capability_metadata():
    metadata = {"formats": ["png"]}
    provider = ImageGenerationAdapter(
        lambda project_dir: [],
        capability_metadata=metadata,
    )
    metadata["formats"].append("jpg")
    declared = provider.capabilities()
    declared["image_generation"]["formats"].append("webp")
    assert provider.capabilities() == {"image_generation": {"formats": ["png"]}}


def test_adapter_invokes_backend_once_with_project_path_and_options(tmp_path):
    calls = []

    def backend(project_dir, *, num_escenas=3):
        calls.append((project_dir, num_escenas))
        return [project_dir / f"scene-{num_escenas}.png"]

    provider = ImageGenerationAdapter(backend, provider_name="local_images")
    result = provider.generate(
        MediaRequest(
            "image_generation",
            str(tmp_path),
            options={"num_escenas": 5},
        )
    )

    assert result.success is True
    assert calls == [(tmp_path, 5)]
    assert result.output == [tmp_path / "scene-5.png"]
    assert result.metadata == {
        "provider": "local_images",
        "capability": "image_generation",
        "adapter": "ImageGenerationAdapter",
    }


def test_adapter_rejects_unsupported_capability_without_backend_call(tmp_path):
    calls = []

    def backend(project_dir):
        calls.append(project_dir)
        return project_dir

    provider = VoiceSynthesisAdapter(backend)
    result = provider.generate(MediaRequest("video_rendering", tmp_path))

    assert result.success is False
    assert calls == []
    assert "no soporta" in result.errors[0]


def test_adapter_rejects_non_path_payload_without_backend_call():
    calls = []
    provider = VoiceSynthesisAdapter(lambda value: calls.append(value))

    result = provider.generate(MediaRequest("voice_synthesis", 123))

    assert result.success is False
    assert calls == []
    assert "ruta de proyecto" in result.errors[0]


def test_adapter_rejects_empty_path_string():
    provider = VoiceSynthesisAdapter(lambda project_dir: project_dir)
    result = provider.generate(MediaRequest("voice_synthesis", "   "))
    assert result.success is False
    assert "ruta vacía" in result.errors[0]


def test_adapter_normalizes_backend_exception_without_retry(tmp_path):
    calls = []

    def backend(project_dir):
        calls.append(project_dir)
        raise RuntimeError("boom")

    provider = VideoRenderingAdapter(backend, provider_name="movie_backend")
    result = provider.generate(MediaRequest("video_rendering", tmp_path))

    assert result.success is False
    assert calls == [tmp_path]
    assert result.metadata["backend_error_type"] == "RuntimeError"
    assert result.errors == ["RuntimeError: boom"]


def test_fake_provider_generates_deterministic_output_and_records_call():
    provider = FakeMediaProvider(
        provider_name="fake_voice",
        capabilities={"voice_synthesis": {"source": "fake"}},
        outputs={"voice_synthesis": b"audio"},
    )
    request = MediaRequest("VOICE_SYNTHESIS", "project-a", options={"x": 1})

    first = provider.generate(request)
    second = provider.generate(request)

    assert first.success is True
    assert second.success is True
    assert first.output == second.output == b"audio"
    assert len(provider.calls) == 2
    assert provider.calls[0].capability == "voice_synthesis"


def test_fake_provider_can_fail_deterministically():
    provider = FakeMediaProvider(
        provider_name="fake_image",
        capabilities={"image_generation": None},
        fail_capabilities={"image_generation"},
    )
    result = provider.generate(MediaRequest("image_generation", "project-a"))
    assert result.success is False
    assert result.errors == ["fake_failure:image_generation"]


def test_fake_provider_rejects_empty_capability_set():
    with pytest.raises(ValueError):
        FakeMediaProvider(provider_name="fake", capabilities={})


def test_registry_and_capability_registry_accept_minimum_adapters(tmp_path):
    voice = VoiceSynthesisAdapter(
        lambda project_dir: project_dir / "audio.mp3",
        provider_name="edge_adapter",
    )
    images = ImageGenerationAdapter(
        lambda project_dir: [project_dir / "01.png"],
        provider_name="pil_adapter",
    )
    video = VideoRenderingAdapter(
        lambda project_dir: project_dir / "short.mp4",
        provider_name="moviepy_adapter",
    )
    providers = MediaProviderRegistry([voice, images, video])
    capabilities = CapabilityRegistry(providers)

    assert capabilities.capabilities() == {
        "image_generation": ["pil_adapter"],
        "video_rendering": ["moviepy_adapter"],
        "voice_synthesis": ["edge_adapter"],
    }


def test_resolver_selection_is_deterministic_across_fake_registration_order():
    alpha = FakeMediaProvider(
        provider_name="alpha_voice",
        capabilities={"voice_synthesis": None},
    )
    zeta = FakeMediaProvider(
        provider_name="zeta_voice",
        capabilities={"voice_synthesis": None},
    )

    first = CapabilityResolver(MediaProviderRegistry([zeta, alpha]))
    second = CapabilityResolver(MediaProviderRegistry([alpha, zeta]))

    assert first.resolve("voice_synthesis").provider_name == "alpha_voice"
    assert second.resolve("voice_synthesis").provider_name == "alpha_voice"


def test_resolver_preference_overrides_alphabetical_default():
    alpha = FakeMediaProvider(
        provider_name="alpha_voice",
        capabilities={"voice_synthesis": None},
    )
    zeta = FakeMediaProvider(
        provider_name="zeta_voice",
        capabilities={"voice_synthesis": None},
    )
    resolver = CapabilityResolver(MediaProviderRegistry([alpha, zeta]))

    assert resolver.resolve(
        "voice_synthesis",
        preferred_provider="ZETA_VOICE",
    ) is zeta


def test_disabled_adapter_is_removed_from_deterministic_candidates():
    alpha = FakeMediaProvider(
        provider_name="alpha_image",
        capabilities={"image_generation": None},
    )
    zeta = FakeMediaProvider(
        provider_name="zeta_image",
        capabilities={"image_generation": None},
    )
    registry = MediaProviderRegistry([alpha, zeta])
    registry.disable("alpha_image")
    resolver = CapabilityResolver(registry)

    assert resolver.resolve("image_generation") is zeta


def test_resolved_adapter_executes_only_selected_backend(tmp_path):
    calls = []

    def alpha_backend(project_dir):
        calls.append("alpha")
        return project_dir / "alpha.mp3"

    def zeta_backend(project_dir):
        calls.append("zeta")
        return project_dir / "zeta.mp3"

    alpha = VoiceSynthesisAdapter(alpha_backend, provider_name="alpha_voice")
    zeta = VoiceSynthesisAdapter(zeta_backend, provider_name="zeta_voice")
    resolver = CapabilityResolver(MediaProviderRegistry([zeta, alpha]))

    selected = resolver.resolve("voice_synthesis")
    result = selected.generate(MediaRequest("voice_synthesis", tmp_path))

    assert result.success is True
    assert result.output == tmp_path / "alpha.mp3"
    assert calls == ["alpha"]


def test_f45_modules_do_not_import_external_media_sdks():
    module_text = "\n".join(
        (SCRIPT_DIR / name).read_text(encoding="utf-8")
        for name in ("media_provider_adapters.py", "fake_media_provider.py")
    ).lower()

    forbidden = ("import edge_tts", "from pil", "import moviepy", "from moviepy")
    assert all(token not in module_text for token in forbidden)
