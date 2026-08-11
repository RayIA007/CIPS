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
        """Compile a validated spec and let Core validate its dependency graph."""

        workflow = VideoPipelineCompiler._build_workflow(spec)

        # Reuse Core's canonical dependency validation instead of introducing
        # a parallel DAG implementation in F6.
        TaskGraph(workflow)
        return workflow

    @staticmethod
    def dependency_order(spec: VideoPipelineSpec) -> tuple[str, ...]:
        """Return Core's deterministic topological order without executing tasks.

        This is a read-only compilation aid. It intentionally does not reorder
        ``WorkflowDefinition.tasks`` because declarative scene order can carry
        composition meaning independently from dependency execution order.
        """

        workflow = VideoPipelineCompiler._build_workflow(spec)
        return tuple(TaskGraph(workflow).topological_order())

    @staticmethod
    def _build_workflow(spec: VideoPipelineSpec) -> WorkflowDefinition:
        if not isinstance(spec, VideoPipelineSpec):
            raise TypeError("spec debe ser VideoPipelineSpec.")

        return WorkflowDefinition(
            name=spec.name,
            tasks=[VideoPipelineCompiler._compile_scene(scene) for scene in spec.scenes],
            workflow_id=spec.pipeline_id,
            version=spec.version,
            metadata=dict(spec.metadata),
        )

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

        # Explicit identifiers prevent Core's generated defaults from making
        # the compiled workflow identity nondeterministic.
        return TaskDefinition(
            name=scene.name or scene.scene_id,
            capability=VIDEO_RENDERING_CAPABILITY,
            task_id=scene.scene_id,
            dependencies=set(scene.dependencies),
            input_data=input_data,
        )


__all__ = ["VIDEO_RENDERING_CAPABILITY", "VideoPipelineCompiler"]
