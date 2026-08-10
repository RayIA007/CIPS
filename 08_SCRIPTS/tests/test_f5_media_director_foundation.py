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
    ImageStrategy,
    MediaDirector,
    MediaRequest,
    MediaRequestValidationError,
    MediaResultValidationError,
    MediaType,
    VideoStrategy,
    VoiceStrategy,
)
import media_director.director as director_module


def test_f5_strategies_map_to_f4_capabilities() -> None:
    voice = VoiceStrategy()
    image = ImageStrategy()
    video = VideoStrategy()

    assert (voice.media_type, voice.provider_capability, voice.output_format) == (
        MediaType.VOICE,
        "voice_synthesis",
        "audio",
    )
    assert (image.media_type, image.provider_capability, image.output_format) == (
        MediaType.IMAGE,
        "image_generation",
        "image",
    )
    assert (video.media_type, video.provider_capability, video.output_format) == (
        MediaType.VIDEO,
        "video_rendering",
        "video",
    )


def test_f5_prepare_builds_provider_agnostic_work_package() -> None:
    request = MediaRequest(
        prompt="Create a clean product image",
        input_data={"aspect_ratio": "1:1"},
        preferred_provider=" Fake-One ",
        metadata={"project_id": "project-1"},
    )

    package = MediaDirector(ImageStrategy()).prepare(request)

    assert package.request_id == request.request_id
    assert package.capability == "image_generation"
    assert package.preferred_provider == "fake-one"
    assert package.provider_payload == {
        "prompt": "Create a clean product image",
        "aspect_ratio": "1:1",
    }
    assert [step.name for step in package.post_process_chain] == [
        "optimize",
        "resize",
        "package",
    ]


def test_f5_director_executes_provider_boundary_once_without_retry() -> None:
    calls = []

    def fake_executor(package):
        calls.append(package)
        return {"asset": "synthetic-image"}

    director = MediaDirector(ImageStrategy())
    result = director.execute(
        MediaRequest(prompt="Synthetic test"),
        provider_executor=fake_executor,
    )

    assert len(calls) == 1
    assert result.output == {"asset": "synthetic-image"}
    assert result.capability == "image_generation"


def test_f5_director_propagates_provider_error_without_retry() -> None:
    calls = 0

    def failing_executor(package):
        nonlocal calls
        calls += 1
        raise RuntimeError("provider failed")

    director = MediaDirector(VideoStrategy())

    with pytest.raises(RuntimeError, match="provider failed"):
        director.execute(
            MediaRequest(prompt="Synthetic video"),
            provider_executor=failing_executor,
        )

    assert calls == 1


def test_f5_post_process_chain_is_declarative_only() -> None:
    executed_steps = []

    def fake_executor(package):
        assert [step.name for step in package.post_process_chain] == [
            "compress",
            "subtitle",
            "package",
        ]
        return b"synthetic-video"

    result = MediaDirector(VideoStrategy()).execute(
        MediaRequest(prompt="Synthetic video"),
        provider_executor=fake_executor,
    )

    assert executed_steps == []
    assert [step.name for step in result.post_process_chain] == [
        "compress",
        "subtitle",
        "package",
    ]


def test_f5_input_schema_can_require_strategy_specific_fields() -> None:
    strategy = VoiceStrategy(input_schema={"prompt": str, "voice": str})

    with pytest.raises(MediaRequestValidationError, match="voice"):
        MediaDirector(strategy).prepare(MediaRequest(prompt="Say hello"))

    package = MediaDirector(strategy).prepare(
        MediaRequest(prompt="Say hello", input_data={"voice": "neutral"})
    )
    assert package.provider_payload["voice"] == "neutral"


def test_f5_none_provider_output_is_rejected() -> None:
    director = MediaDirector(VoiceStrategy())

    with pytest.raises(MediaResultValidationError, match="resultado vacío"):
        director.execute(
            MediaRequest(prompt="Synthetic voice"),
            provider_executor=lambda package: None,
        )


def test_f5_models_are_serializable_without_filesystem_objects() -> None:
    result = MediaDirector(VoiceStrategy()).execute(
        MediaRequest(prompt="Synthetic voice", metadata={"source": "unit-test"}),
        provider_executor=lambda package: {"bytes": 12},
    )

    payload = result.to_dict()
    assert payload["media_type"] == "voice"
    assert payload["metadata"] == {"source": "unit-test"}
    assert payload["post_process_chain"] == [
        {"name": "package", "required": True, "parameters": {}},
    ]


def test_f5_media_director_does_not_import_pipeline_or_stage_executor() -> None:
    source = inspect.getsource(director_module)
    tree = ast.parse(source)
    imported_modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)

    assert "stage_executor" not in imported_modules
    assert "pipeline_engine" not in imported_modules
    assert "artifact_store" not in imported_modules
    assert "workspace_resolver" not in imported_modules


def test_f5_package_has_no_direct_sdk_imports() -> None:
    package_root = Path(director_module.__file__).resolve().parent
    forbidden_prefixes = (
        "openai",
        "google.generativeai",
        "google.genai",
        "anthropic",
        "elevenlabs",
    )

    for path in package_root.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            else:
                continue
            assert not any(
                name == prefix or name.startswith(prefix + ".")
                for name in names
                for prefix in forbidden_prefixes
            ), f"SDK directo no permitido en {path.name}: {names}"
