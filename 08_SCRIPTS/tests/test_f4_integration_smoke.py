from __future__ import annotations

from pathlib import Path
import sys


SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from audio_store import AudioStore  # noqa: E402
from capability_registry import CapabilityRegistry  # noqa: E402
from capability_resolver import CapabilityResolver  # noqa: E402
from fake_media_provider import FakeMediaProvider  # noqa: E402
from image_store import ImageStore  # noqa: E402
from llm_manager import LLMManager  # noqa: E402
from media_provider import MediaRequest  # noqa: E402
from media_provider_registry import MediaProviderRegistry  # noqa: E402
from mock_provider import MockProvider  # noqa: E402
from provider_registry import ProviderRegistry  # noqa: E402
from text_store import TextStore  # noqa: E402
from video_store import VideoStore  # noqa: E402
from workspace_resolver import WorkspaceResolver  # noqa: E402


CREATED_AT = "2026-08-10T14:00:00+00:00"


def test_f46_fake_llm_media_and_f3_storage_integrate_without_real_providers(
    tmp_path: Path,
) -> None:
    resolver = WorkspaceResolver(
        projects_root=tmp_path / "04_PROYECTOS",
        outputs_root=tmp_path / "05_OUTPUTS",
    )
    workspace = resolver.resolve_execution_workspace(
        "youtube",
        "F4_6_SMOKE",
        create=True,
    )

    llm_manager = LLMManager()
    mock_llm = MockProvider()
    llm_registry = ProviderRegistry([mock_llm])
    assert llm_registry.get("  MOCK ") is mock_llm
    llm_manager.register(llm_registry.get("mock"))
    llm_result = llm_manager.generate("CIPS F4.6 integration smoke")

    assert llm_result.success is True
    assert llm_result.response is not None
    assert llm_result.metadata["provider"] == "mock"
    assert llm_result.metadata["simulated"] is True

    text_store = TextStore(resolver)
    text_write = text_store.persist_text(
        workspace_root=workspace,
        relative_path="text/llm_response.md",
        content=llm_result.response.content,
        artifact_id="f46_llm_text",
        metadata={
            "provider": llm_result.metadata["provider"],
            "model": llm_result.response.model,
            "simulated": True,
        },
        created_at=CREATED_AT,
    )

    alpha_voice = FakeMediaProvider(
        provider_name="alpha_voice",
        capabilities={"voice_synthesis": {"source": "fake"}},
        outputs={"voice_synthesis": b"ID3-CIPS-F4.6-AUDIO"},
    )
    zeta_voice = FakeMediaProvider(
        provider_name="zeta_voice",
        capabilities={"voice_synthesis": {"source": "fake"}},
        outputs={"voice_synthesis": b"ID3-UNUSED"},
    )
    image_fake = FakeMediaProvider(
        provider_name="image_fake",
        capabilities={"image_generation": {"source": "fake"}},
        outputs={"image_generation": b"\x89PNG\r\n\x1a\nCIPS-F4.6"},
    )
    video_fake = FakeMediaProvider(
        provider_name="video_fake",
        capabilities={"video_rendering": {"source": "fake"}},
        outputs={"video_rendering": b"ftyp-CIPS-F4.6-VIDEO"},
    )

    media_registry = MediaProviderRegistry(
        [zeta_voice, video_fake, image_fake, alpha_voice]
    )
    capabilities = CapabilityRegistry(media_registry)
    media_resolver = CapabilityResolver(media_registry, capabilities)

    assert capabilities.capabilities() == {
        "image_generation": ["image_fake"],
        "video_rendering": ["video_fake"],
        "voice_synthesis": ["alpha_voice", "zeta_voice"],
    }

    requests = {
        "voice_synthesis": MediaRequest(
            "voice_synthesis",
            {"project": "F4_6_SMOKE"},
        ),
        "image_generation": MediaRequest(
            "image_generation",
            {"project": "F4_6_SMOKE"},
        ),
        "video_rendering": MediaRequest(
            "video_rendering",
            {"project": "F4_6_SMOKE"},
        ),
    }

    selected_voice = media_resolver.resolve("voice_synthesis")
    selected_image = media_resolver.resolve("image_generation")
    selected_video = media_resolver.resolve("video_rendering")

    assert selected_voice is alpha_voice
    assert selected_image is image_fake
    assert selected_video is video_fake

    voice_result = selected_voice.generate(requests["voice_synthesis"])
    image_result = selected_image.generate(requests["image_generation"])
    video_result = selected_video.generate(requests["video_rendering"])

    assert voice_result.success is True
    assert image_result.success is True
    assert video_result.success is True
    assert len(alpha_voice.calls) == 1
    assert len(zeta_voice.calls) == 0
    assert len(image_fake.calls) == 1
    assert len(video_fake.calls) == 1

    audio_write = AudioStore(resolver).persist_audio(
        workspace_root=workspace,
        relative_path="audio/voice.mp3",
        content=voice_result.output,
        artifact_id="f46_voice",
        metadata=voice_result.metadata,
        created_at=CREATED_AT,
    )
    image_write = ImageStore(resolver).persist_image(
        workspace_root=workspace,
        relative_path="images/frame.png",
        content=image_result.output,
        artifact_id="f46_image",
        metadata=image_result.metadata,
        created_at=CREATED_AT,
    )
    video_write = VideoStore(resolver).persist_video(
        workspace_root=workspace,
        relative_path="video/final.mp4",
        content=video_result.output,
        artifact_id="f46_video",
        metadata=video_result.metadata,
        created_at=CREATED_AT,
    )

    writes = [text_write, audio_write, image_write, video_write]
    for write in writes:
        artifact_path = Path(write.artifact.path)
        assert artifact_path.is_file()
        assert write.sidecar_path.is_file()
        assert write.artifact.content_hash
        assert write.deduplicated is False
        assert write.event_created is True
        assert artifact_path.is_relative_to(workspace)

    assert Path(text_write.artifact.path).read_text(encoding="utf-8").startswith(
        "# Briefing Estratégico"
    )
    assert Path(audio_write.artifact.path).read_bytes() == voice_result.output
    assert Path(image_write.artifact.path).read_bytes() == image_result.output
    assert Path(video_write.artifact.path).read_bytes() == video_result.output
