"""Public API for the CIPS universal render adapter boundary."""

from .base import RenderTargetAdapter
from .errors import (
    RenderAdapterContractError,
    RenderAdapterError,
    RenderCapabilityError,
    RenderCompilationError,
)
from .fake import FakeRenderTargetAdapter, universal_fake_capabilities
from .models import (
    RENDER_PLAN_FILENAME,
    RENDER_PLAN_SCHEMA_NAME,
    RENDER_PLAN_SCHEMA_VERSION,
    RENDER_SUBMISSION_SCHEMA_NAME,
    RenderContractVersion,
    RenderJob,
    RenderPlan,
    RenderResult,
    RenderScenePlan,
    RenderStatus,
    RenderSubmission,
    RenderTargetCapabilities,
    deterministic_render_plan_id,
    deterministic_submission_id,
)
from .serialization import (
    deserialize_render_plan,
    render_plan_json_schema,
    serialize_render_plan,
    validate_render_plan_data,
)

__all__ = [
    "RENDER_PLAN_FILENAME",
    "RENDER_PLAN_SCHEMA_NAME",
    "RENDER_PLAN_SCHEMA_VERSION",
    "RENDER_SUBMISSION_SCHEMA_NAME",
    "FakeRenderTargetAdapter",
    "RenderAdapterContractError",
    "RenderAdapterError",
    "RenderCapabilityError",
    "RenderCompilationError",
    "RenderContractVersion",
    "RenderJob",
    "RenderPlan",
    "RenderResult",
    "RenderScenePlan",
    "RenderStatus",
    "RenderSubmission",
    "RenderTargetAdapter",
    "RenderTargetCapabilities",
    "deserialize_render_plan",
    "deterministic_render_plan_id",
    "deterministic_submission_id",
    "render_plan_json_schema",
    "serialize_render_plan",
    "universal_fake_capabilities",
    "validate_render_plan_data",
]
