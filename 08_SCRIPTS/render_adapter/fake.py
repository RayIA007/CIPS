"""Fully offline reference adapter for the universal render boundary."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from production_manifest import AssetType, ProductionManifest, TransitionKind

from .base import RenderTargetAdapter
from .models import RenderTargetCapabilities


def universal_fake_capabilities() -> RenderTargetCapabilities:
    """Return complete PM4 capabilities without target-specific assumptions."""

    return RenderTargetCapabilities(
        supported_asset_types=tuple(
            asset_type for asset_type in AssetType if asset_type is not AssetType.NONE
        ),
        supported_transition_kinds=tuple(TransitionKind),
        supports_narration=True,
        supports_motion=True,
        supports_on_screen_text=True,
        supports_captions=True,
        supports_music=True,
        supports_sound_effects=True,
    )


class FakeRenderTargetAdapter(RenderTargetAdapter):
    """Compile manifests to a deterministic synthetic payload for tests."""

    adapter_name = "FakeRenderTargetAdapter"
    adapter_version = "1.0"
    target_id = "fake.universal"

    def __init__(
        self,
        *,
        capabilities: RenderTargetCapabilities | None = None,
        target_id: str | None = None,
    ) -> None:
        super().__init__(
            capabilities=capabilities or universal_fake_capabilities(),
            target_id=target_id,
        )

    def compile_payload(self, manifest: ProductionManifest) -> Mapping[str, Any]:
        """Expose the complete neutral recipe as JSON-compatible data."""

        return {
            "schema_name": "cips.fake_render_payload",
            "schema_version": "1.0",
            "manifest_id": manifest.manifest_id,
            "project": manifest.project.model_dump(mode="json", exclude_none=True),
            "output": manifest.output.model_dump(mode="json", exclude_none=True),
            "timeline": [
                {
                    "scene_id": scene.scene_id,
                    "sequence": scene.sequence,
                    "start_seconds": scene.start_seconds,
                    "duration_seconds": scene.duration_seconds,
                    "narration_text": scene.narration_text,
                    "asset_request": scene.asset_request.model_dump(
                        mode="json",
                        exclude_none=True,
                    ),
                    "visual_direction": scene.visual_direction.model_dump(
                        mode="json",
                        exclude_none=True,
                    ),
                    "motion": scene.motion.model_dump(mode="json", exclude_none=True),
                    "on_screen_text": [
                        item.model_dump(mode="json", exclude_none=True)
                        for item in scene.on_screen_text
                    ],
                    "captions": (
                        scene.captions.model_dump(mode="json", exclude_none=True)
                        if scene.captions is not None
                        else None
                    ),
                    "transition_in": scene.transition_in.model_dump(
                        mode="json",
                        exclude_none=True,
                    ),
                    "transition_out": scene.transition_out.model_dump(
                        mode="json",
                        exclude_none=True,
                    ),
                    "source_reference_ids": list(scene.source_reference_ids),
                    "metadata": dict(scene.metadata),
                }
                for scene in manifest.scenes
            ],
            "audio_design": manifest.audio_design.model_dump(
                mode="json",
                exclude_none=True,
            ),
            "publication": manifest.publication.model_dump(
                mode="json",
                exclude_none=True,
            ),
            "quality_requirements": [
                item.model_dump(mode="json", exclude_none=True)
                for item in manifest.quality_requirements
            ],
            "source_references": [
                item.model_dump(mode="json", exclude_none=True)
                for item in manifest.source_references
            ],
            "metadata": dict(manifest.metadata),
        }


__all__ = ["FakeRenderTargetAdapter", "universal_fake_capabilities"]
