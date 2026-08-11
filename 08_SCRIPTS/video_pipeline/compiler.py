"""Compile validated video pipeline specs to existing CIPS Core contracts."""

from __future__ import annotations

from typing import Any

from cips_core.tasks import TaskDefinition, TaskGraph, WorkflowDefinition

from .models import VideoPipelineSpec, VideoSceneSpec


VIDEO_RENDERING_CAPABILITY = "video_rendering"


class VideoPipelineCompiler:
    """Translate declarative video scenes into the existing Core workflow model."""

    @staticmethod
    def compile(spec: VideoPipelineSpec) -> WorkflowDefinition:
        if not isinstance(spec, VideoPipelineSpec):
            raise TypeError("spec debe ser VideoPipelineSpec.")

        workflow = WorkflowDefinition(
            name=spec.name,
            tasks=[VideoPipelineCompiler._compile_scene(scene) for scene in spec.scenes],
            workflow_id=spec.pipeline_id,
            version=spec.version,
            metadata=dict(spec.metadata),
        )

        # Reuse Core's canonical dependency validation instead of introducing
        # a parallel DAG implementation in F6.
        TaskGraph(workflow)
        return workflow

    @staticmethod
    def _compile_scene(scene: VideoSceneSpec) -> TaskDefinition:
        input_data: dict[str, Any] = {
            "prompt": scene.prompt,
            "duration": scene.duration,
            "media_refs": list(scene.media_refs),
            "transitions": [item.model_dump(mode="json") for item in scene.transitions],
        }
        if scene.audio_track is not None:
            input_data["audio_track"] = scene.audio_track
        if scene.subtitle_track is not None:
            input_data["subtitle_track"] = scene.subtitle_track

        return TaskDefinition(
            name=scene.name or scene.scene_id,
            capability=VIDEO_RENDERING_CAPABILITY,
            task_id=scene.scene_id,
            dependencies=set(scene.dependencies),
            input_data=input_data,
        )


__all__ = ["VIDEO_RENDERING_CAPABILITY", "VideoPipelineCompiler"]
