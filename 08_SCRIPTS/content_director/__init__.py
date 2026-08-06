"""Dominio del Content Director de CIPS."""
from .models import (
    AudienceSegment,
    CalendarCadence,
    CallToAction,
    ChannelPlan,
    ContentBrief,
    ContentBuildResult,
    ContentFormat,
    ContentIntent,
    ContentMetricsTarget,
    ContentObjective,
    ContentPackage,
    ContentPiece,
    ContentPillar,
    ContentQualityScore,
    ContentStatus,
    CTAType,
    EditorialCalendar,
    EditorialSlot,
    SEOBrief,
)
from .validators import (
    ContentDomainValidationError,
    ValidationIssue,
    assert_valid_content_package,
    validate_content_package,
)

__all__ = [
    "AudienceSegment",
    "CalendarCadence",
    "CallToAction",
    "ChannelPlan",
    "ContentBrief",
    "ContentBuildResult",
    "ContentFormat",
    "ContentIntent",
    "ContentMetricsTarget",
    "ContentObjective",
    "ContentPackage",
    "ContentPiece",
    "ContentPillar",
    "ContentQualityScore",
    "ContentStatus",
    "CTAType",
    "EditorialCalendar",
    "EditorialSlot",
    "SEOBrief",
    "ContentDomainValidationError",
    "ValidationIssue",
    "assert_valid_content_package",
    "validate_content_package",
]

from .planning_models import (
    ContentAllocation,
    ContentPlan,
    EditorialPolicy,
    PlanningBuildResult,
    PlanningQualityScore,
)
from .planning import ContentPlanningEngine, ContentPlanningError, PlanningConfig

__all__ += [
    "ContentAllocation",
    "ContentPlan",
    "EditorialPolicy",
    "PlanningBuildResult",
    "PlanningQualityScore",
    "ContentPlanningEngine",
    "ContentPlanningError",
    "PlanningConfig",
]
