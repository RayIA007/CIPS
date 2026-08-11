"""Compile validated video pipeline specs to existing CIPS Core contracts."""

from __future__ import annotations

from typing import Any

from cips_core.adapters.contracts import TASK_ARTIFACT_REF_KEY
from cips_core.tasks import TaskDefinition, TaskGraph, WorkflowDefinition

from .models import VideoArtifactRefSpec, VideoPipelineSpec, VideoSceneSpec


VIDEO_RENDERING_CAPABILITY = "video_rendering"
ARTIFACT_TARGET_KEY = "artifact_target"
RENDER_PROFILE_KEY = "render_profile"
POST_PROCESS_CHAIN_KEY = "post_process_chain"


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
            "media_refs": [
                VideoPipelineCompiler._compile_media_ref(item)
                for item in scene.media_refs
            ],
            "transitions": [item.model_dump(mode="json") for item in scene.transitions],
        }
        if scene.audio_track is not None:
            input_data["audio_track"] = scene.audio_track
        if scene.subtitle_track is not None:
            input_data["subtitle_track"] = scene.subtitle_track
        if scene.render_profile is not None:
            input_data[RENDER_PROFILE_KEY] = scene.render_profile.model_dump(
                mode="json",
                exclude_none=True,
            )
        if scene.post_process_chain is not None:
            input_data[POST_PROCESS_CHAIN_KEY] = [
                item.model_dump(mode="json") for item in scene.post_process_chain
            ]
        if scene.artifact_target is not None:
            input_data[ARTIFACT_TARGET_KEY] = scene.artifact_target.model_dump(
                mode="json",
                exclude_none=True,
            )

        # Explicit identifiers prevent Core's generated defaults from making
        # the compiled workflow identity nondeterministic.
        return TaskDefinition(
            name=scene.name or scene.scene_id,
            capability=VIDEO_RENDERING_CAPABILITY,
            task_id=scene.scene_id,
            dependencies=set(scene.dependencies),
            input_data=input_data,
        )

    @staticmethod
    def _compile_media_ref(value: str | VideoArtifactRefSpec) -> Any:
        if isinstance(value, str):
            return value

        payload: dict[str, Any] = {
            "task_id": value.scene_id,
            "artifact_index": value.artifact_index,
        }
        if value.role is not None:
            payload["role"] = value.role
        return {TASK_ARTIFACT_REF_KEY: payload}


__all__ = [
    "ARTIFACT_TARGET_KEY",
    "POST_PROCESS_CHAIN_KEY",
    "RENDER_PROFILE_KEY",
    "VIDEO_RENDERING_CAPABILITY",
    "VideoPipelineCompiler",
]
