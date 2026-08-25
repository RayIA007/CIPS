"""Run the single-credit PM6 Creatomate acceptance render.

This entrypoint is intentionally guarded by two environment variables. It
never enables billing, creates a subscription, or prints the API key. Reusing
the same deterministic manifest/workspace returns the persisted F3 artifact
instead of submitting another paid render.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from creatomate_api import (
    CREATOMATE_API_KEY_ENV,
    CreatomateApiClient,
    CreatomateApiConfig,
    CreatomateApiError,
    CreatomateRenderService,
)
from production_manifest import (
    AssetRequest,
    AssetType,
    AudioDesignSpec,
    CostHint,
    NarrationSpec,
    OnScreenTextSpec,
    OutputSpec,
    ProductionManifest,
    ProjectIdentity,
    PublicationSpec,
    QualityCategory,
    QualityHint,
    QualityRequirement,
    RequirementLevel,
    SceneSpec,
    TargetPlatform,
    TextPlacement,
    TextStyleRole,
    VisualDirection,
)
from workspace_resolver import WorkspaceResolver

CONFIRMATION_ENV = "CIPS_PM6_REAL_RENDER_CONFIRM"
CONFIRMATION_VALUE = "FREE_TRIAL_ONLY"
EXECUTION_ID = "pm6-free-trial-001"


def build_trial_manifest() -> ProductionManifest:
    """Build a provider-neutral, one-second, text-and-shape manifest."""

    return ProductionManifest(
        project=ProjectIdentity(
            project_id="CIPS_PM6_TRIAL",
            production_id="CREATOMATE_RENDER_001",
            title="Prueba técnica PM6",
            revision=1,
        ),
        locale="es-MX",
        style_profile="pm6-technical-trial",
        output=OutputSpec(
            platform=TargetPlatform.YOUTUBE_SHORTS,
            width_px=1080,
            height_px=1920,
            aspect_ratio="9:16",
            fps=30.0,
            duration_seconds=1.0,
        ),
        narration=NarrationSpec(
            full_text="Prueba técnica PM6.",
            hook="Prueba técnica PM6.",
            estimated_duration_seconds=0.5,
        ),
        scenes=(
            SceneSpec(
                scene_id="scene-001-pm6-trial",
                sequence=1,
                start_seconds=0.0,
                duration_seconds=1.0,
                asset_request=AssetRequest(
                    asset_type=AssetType.TEXT_GRAPHIC,
                    creative_brief="Fondo sólido para validar el ciclo técnico PM6.",
                    quality_hint=QualityHint.DRAFT,
                    cost_hint=CostHint.FREE,
                ),
                visual_direction=VisualDirection(
                    intent="Validar submit, status, descarga y persistencia.",
                    composition="Texto centrado sobre fondo azul oscuro.",
                    color_palette=("#0F172A", "#22D3EE", "#FFFFFF"),
                ),
                on_screen_text=(
                    OnScreenTextSpec(
                        text_id="text-pm6-trial",
                        text="CIPS · PM6",
                        start_offset_seconds=0.0,
                        duration_seconds=1.0,
                        placement=TextPlacement.CENTER,
                        style_role=TextStyleRole.TITLE,
                    ),
                ),
            ),
        ),
        audio_design=AudioDesignSpec(),
        publication=PublicationSpec(
            title="Prueba técnica PM6",
            description="Render mínimo de aceptación de la integración Creatomate.",
        ),
        quality_requirements=(
            QualityRequirement(
                requirement_id="pm6-mp4",
                category=QualityCategory.TECHNICAL,
                level=RequirementLevel.MUST,
                description="La salida debe ser un MP4 descargable y persistido.",
                metric="output_format",
                expected="mp4",
            ),
        ),
    )


def main() -> int:
    if os.environ.get(CONFIRMATION_ENV, "").strip() != CONFIRMATION_VALUE:
        print(
            f"Bloqueado: define {CONFIRMATION_ENV}={CONFIRMATION_VALUE} solo después "
            "de confirmar créditos gratuitos/de prueba disponibles y facturación no activada."
        )
        return 2

    try:
        config = CreatomateApiConfig.from_environment()
        resolver = WorkspaceResolver()
        workspace = resolver.resolve_execution_workspace(
            "creatomate",
            EXECUTION_ID,
            create=True,
        )
        service = CreatomateRenderService(
            client=CreatomateApiClient(config),
            workspace_resolver=resolver,
        )
        result = service.execute(
            build_trial_manifest(),
            workspace_root=workspace,
        )
    except CreatomateApiError as error:
        print(
            json.dumps(
                {
                    "success": False,
                    "category": error.category.value,
                    "operation": error.operation,
                    "retryable": error.retryable,
                    "ambiguous_submission": error.ambiguous_submission,
                    "status_code": error.status_code,
                    "error": str(error),
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )
        return 1

    if not result.output_artifact_ids:
        print(
            json.dumps(
                {
                    "success": False,
                    "status": result.status.value,
                    "error": result.error,
                    "metadata": result.metadata,
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )
        return 1

    state_directory = Path(workspace) / "video" / "creatomate"
    candidates = sorted(state_directory.glob("*.mp4"))
    artifact_path = str(candidates[0].resolve()) if candidates else ""
    print(
        json.dumps(
            {
                "success": True,
                "status": result.status.value,
                "artifact_id": result.output_artifact_ids[0],
                "artifact_path": artifact_path,
                "external_job_id": result.metadata.get("external_job_id"),
                "size_bytes": result.metadata.get("size_bytes"),
                "estimated_credits": result.metadata.get("estimated_credits"),
                "credits_used": result.metadata.get("credits_used"),
                "credential_source": CREATOMATE_API_KEY_ENV,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
