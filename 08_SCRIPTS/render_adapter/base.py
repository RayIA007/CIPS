"""Abstract provider-neutral compilation boundary for render targets."""

from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from collections.abc import Mapping
from typing import Any

from production_manifest import (
    AssetType,
    CameraMovement,
    ProductionManifest,
    serialize_manifest,
)

from .errors import (
    RenderAdapterContractError,
    RenderCapabilityError,
    RenderCompilationError,
)
from .models import (
    RenderPlan,
    RenderScenePlan,
    RenderSubmission,
    RenderTargetCapabilities,
    deterministic_render_plan_id,
    deterministic_submission_id,
)
from .serialization import serialize_render_plan


class RenderTargetAdapter(ABC):
    """Compile a manifest to an inspectable target payload without executing it."""

    adapter_name = ""
    adapter_version = "1.0"
    target_id = ""

    def __init__(
        self,
        *,
        capabilities: RenderTargetCapabilities,
        target_id: str | None = None,
    ) -> None:
        adapter_name = str(self.adapter_name).strip()
        adapter_version = str(self.adapter_version).strip()
        resolved_target_id = str(target_id or self.target_id).strip()
        if not adapter_name:
            raise RenderAdapterContractError(
                f"{type(self).__name__} debe declarar adapter_name."
            )
        if not adapter_version:
            raise RenderAdapterContractError(
                f"{type(self).__name__} debe declarar adapter_version."
            )
        if not resolved_target_id:
            raise RenderAdapterContractError(
                f"{type(self).__name__} debe declarar target_id."
            )
        if not isinstance(capabilities, RenderTargetCapabilities):
            raise TypeError("capabilities debe ser RenderTargetCapabilities.")
        self.adapter_name = adapter_name
        self.adapter_version = adapter_version
        self.target_id = resolved_target_id
        self._capabilities = capabilities

    @property
    def capabilities(self) -> RenderTargetCapabilities:
        return self._capabilities

    def compile(self, manifest: ProductionManifest) -> RenderPlan:
        """Validate capabilities and compile a deterministic offline plan."""

        if not isinstance(manifest, ProductionManifest):
            raise TypeError("manifest debe ser ProductionManifest.")
        required_capabilities = self.required_capabilities(manifest)
        self.validate_capabilities(manifest)
        try:
            raw_payload = self.compile_payload(manifest)
        except (RenderCapabilityError, RenderCompilationError):
            raise
        except Exception as error:
            raise RenderCompilationError(
                f"Falló la compilación de '{self.adapter_name}': "
                f"{type(error).__name__}: {error}"
            ) from error
        if not isinstance(raw_payload, Mapping):
            raise RenderAdapterContractError(
                "compile_payload debe devolver un Mapping JSON-compatible."
            )

        manifest_payload = serialize_manifest(manifest).encode("utf-8")
        manifest_sha256 = hashlib.sha256(manifest_payload).hexdigest()
        plan_id = deterministic_render_plan_id(
            target_id=self.target_id,
            adapter_name=self.adapter_name,
            adapter_version=self.adapter_version,
            manifest_id=manifest.manifest_id,
            manifest_sha256=manifest_sha256,
        )
        plan = RenderPlan(
            plan_id=plan_id,
            target_id=self.target_id,
            adapter_name=self.adapter_name,
            adapter_version=self.adapter_version,
            manifest_id=manifest.manifest_id,
            manifest_sha256=manifest_sha256,
            project_id=manifest.project.project_id,
            production_id=manifest.project.production_id,
            output=manifest.output,
            scenes=tuple(
                RenderScenePlan(
                    scene_id=scene.scene_id,
                    sequence=scene.sequence,
                    start_seconds=scene.start_seconds,
                    duration_seconds=scene.duration_seconds,
                    narration_text=scene.narration_text,
                    asset_request=scene.asset_request,
                    visual_direction=scene.visual_direction,
                    motion=scene.motion,
                    on_screen_text=scene.on_screen_text,
                    captions=scene.captions,
                    transition_in=scene.transition_in,
                    transition_out=scene.transition_out,
                    source_reference_ids=scene.source_reference_ids,
                    metadata=dict(scene.metadata),
                )
                for scene in manifest.scenes
            ),
            audio_design=manifest.audio_design,
            publication=manifest.publication,
            quality_requirements=manifest.quality_requirements,
            source_references=manifest.source_references,
            required_capabilities=required_capabilities,
            target_capabilities=self.capabilities,
            target_payload=dict(raw_payload),
            manifest_metadata=dict(manifest.metadata),
        )
        self.validate_plan(plan, manifest=manifest)
        return plan

    @abstractmethod
    def compile_payload(self, manifest: ProductionManifest) -> Mapping[str, Any]:
        """Compile a validated manifest to one target-owned payload."""

        raise NotImplementedError

    def validate_capabilities(self, manifest: ProductionManifest) -> None:
        """Reject every unsupported manifest requirement in one explicit error."""

        if not isinstance(manifest, ProductionManifest):
            raise TypeError("manifest debe ser ProductionManifest.")
        capabilities = self.capabilities
        unsupported: set[str] = set()
        supported_assets = set(capabilities.supported_asset_types)
        supported_transitions = set(capabilities.supported_transition_kinds)

        for scene in manifest.scenes:
            asset_type = scene.asset_request.asset_type
            if asset_type is not AssetType.NONE and asset_type not in supported_assets:
                unsupported.add(f"asset_type:{asset_type.value}")
            for transition in (scene.transition_in, scene.transition_out):
                if transition.kind not in supported_transitions:
                    unsupported.add(f"transition:{transition.kind.value}")
            if (
                scene.motion.camera_movement is not CameraMovement.STATIC
                or scene.motion.intensity > 0.0
                or scene.motion.subject_movement is not None
            ) and not capabilities.supports_motion:
                unsupported.add("feature:motion")
            if scene.on_screen_text and not capabilities.supports_on_screen_text:
                unsupported.add("feature:on_screen_text")
            if scene.captions is not None and not capabilities.supports_captions:
                unsupported.add("feature:captions")
            if scene.narration_text is not None and not capabilities.supports_narration:
                unsupported.add("feature:narration")

        if manifest.audio_design.music is not None and not capabilities.supports_music:
            unsupported.add("feature:music")
        if (
            manifest.audio_design.sound_effects
            and not capabilities.supports_sound_effects
        ):
            unsupported.add("feature:sound_effects")
        output = manifest.output
        if (
            capabilities.max_width_px is not None
            and output.width_px > capabilities.max_width_px
        ):
            unsupported.add(
                f"output:width_px={output.width_px}>{capabilities.max_width_px}"
            )
        if (
            capabilities.max_height_px is not None
            and output.height_px > capabilities.max_height_px
        ):
            unsupported.add(
                f"output:height_px={output.height_px}>{capabilities.max_height_px}"
            )
        if capabilities.max_fps is not None and output.fps > capabilities.max_fps:
            unsupported.add(f"output:fps={output.fps}>{capabilities.max_fps}")
        if (
            capabilities.max_duration_seconds is not None
            and output.duration_seconds > capabilities.max_duration_seconds
        ):
            unsupported.add(
                "output:duration_seconds="
                f"{output.duration_seconds}>{capabilities.max_duration_seconds}"
            )
        if unsupported:
            raise RenderCapabilityError(self.target_id, tuple(unsupported))

    def validate_plan(
        self,
        plan: RenderPlan,
        *,
        manifest: ProductionManifest,
    ) -> None:
        """Ensure the compiled wrapper preserves the source manifest boundary."""

        if not isinstance(plan, RenderPlan):
            raise RenderAdapterContractError("El adapter debe producir RenderPlan.")
        if plan.adapter_name != self.adapter_name:
            raise RenderAdapterContractError(
                "adapter_name inconsistente en RenderPlan."
            )
        if plan.adapter_version != self.adapter_version:
            raise RenderAdapterContractError(
                "adapter_version inconsistente en RenderPlan."
            )
        if plan.target_id != self.target_id:
            raise RenderAdapterContractError("target_id inconsistente en RenderPlan.")
        if plan.manifest_id != manifest.manifest_id:
            raise RenderAdapterContractError("manifest_id inconsistente en RenderPlan.")
        if plan.output != manifest.output:
            raise RenderAdapterContractError(
                "El RenderPlan alteró output del manifest."
            )
        if len(plan.scenes) != len(manifest.scenes):
            raise RenderAdapterContractError(
                "El RenderPlan alteró el número de escenas."
            )
        for planned, source in zip(plan.scenes, manifest.scenes):
            if (
                planned.scene_id != source.scene_id
                or planned.sequence != source.sequence
                or planned.start_seconds != source.start_seconds
                or planned.duration_seconds != source.duration_seconds
                or planned.source_reference_ids != source.source_reference_ids
                or planned.asset_request != source.asset_request
            ):
                raise RenderAdapterContractError(
                    f"El RenderPlan alteró identidad o trazabilidad de '{source.scene_id}'."
                )

    def prepare_submission(self, plan: RenderPlan) -> RenderSubmission:
        """Build an idempotent offline submission contract; perform no I/O."""

        if not isinstance(plan, RenderPlan):
            raise TypeError("plan debe ser RenderPlan.")
        if plan.target_id != self.target_id or plan.adapter_name != self.adapter_name:
            raise RenderAdapterContractError(
                "El RenderPlan no pertenece a este adapter/target."
            )
        idempotency_key = hashlib.sha256(
            serialize_render_plan(plan).encode("utf-8")
        ).hexdigest()
        submission_id = deterministic_submission_id(
            plan_id=plan.plan_id,
            target_id=plan.target_id,
            idempotency_key=idempotency_key,
        )
        return RenderSubmission(
            submission_id=submission_id,
            plan_id=plan.plan_id,
            manifest_id=plan.manifest_id,
            target_id=plan.target_id,
            idempotency_key=idempotency_key,
            payload=dict(plan.target_payload),
        )

    @staticmethod
    def required_capabilities(manifest: ProductionManifest) -> tuple[str, ...]:
        """Describe manifest requirements in stable, human-inspectable terms."""

        if not isinstance(manifest, ProductionManifest):
            raise TypeError("manifest debe ser ProductionManifest.")
        required: set[str] = set()
        for scene in manifest.scenes:
            asset_type = scene.asset_request.asset_type
            if asset_type is not AssetType.NONE:
                required.add(f"asset_type:{asset_type.value}")
            required.update(
                f"transition:{transition.kind.value}"
                for transition in (scene.transition_in, scene.transition_out)
            )
            if (
                scene.motion.camera_movement is not CameraMovement.STATIC
                or scene.motion.intensity > 0.0
                or scene.motion.subject_movement is not None
            ):
                required.add("feature:motion")
            if scene.on_screen_text:
                required.add("feature:on_screen_text")
            if scene.captions is not None:
                required.add("feature:captions")
            if scene.narration_text is not None:
                required.add("feature:narration")
        if manifest.audio_design.music is not None:
            required.add("feature:music")
        if manifest.audio_design.sound_effects:
            required.add("feature:sound_effects")
        return tuple(sorted(required))

    def descriptor(self) -> dict[str, Any]:
        """Return a serializable, provider-neutral adapter descriptor."""

        return {
            "adapter_name": self.adapter_name,
            "adapter_version": self.adapter_version,
            "target_id": self.target_id,
            "capabilities": self.capabilities.model_dump(mode="json"),
            "execution_mode": "compile_only",
        }


__all__ = ["RenderTargetAdapter"]
