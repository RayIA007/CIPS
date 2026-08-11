"""F6/Core execution-result integration for the CIPS F7 review domain.

This module converts an already completed Core/F6 workflow result into the
logical ``ReviewTarget`` introduced in F7.1. It does not execute workflows,
read artifact bytes, persist review records, mutate production state, export
files, select providers, or publish content.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from pydantic import ValidationError

from .errors import InconsistentReviewArtifactError, ReviewTargetBuildError
from .models import ReviewArtifactRef, ReviewTarget


_PHYSICAL_METADATA_KEYS = frozenset(
    {
        "path",
        "sidecar_path",
        "relative_path",
        "requested_relative_path",
        "workspace_root",
    }
)


class ReviewTargetBuilder:
    """Build immutable logical review targets from completed Core/F6 results."""

    @classmethod
    def from_workflow_result(
        cls,
        result: Any,
        *,
        task_ids: Iterable[str] | None = None,
    ) -> ReviewTarget:
        """Convert a successful workflow result into a logical review target.

        ``task_ids`` optionally narrows the review package. When omitted, every
        succeeded task that produced artifacts is included in workflow-result
        order. F7.2 deliberately does not infer finality from task names such as
        ``final`` or from provider-specific metadata.
        """

        cls._validate_result_shape(result)
        cls._require_succeeded(result)

        context = result.context
        if result.workflow_id != context.workflow_id:
            raise ReviewTargetBuildError(
                "WorkflowResult.workflow_id no coincide con ExecutionContext.workflow_id."
            )
        if result.run_id != context.run_id:
            raise ReviewTargetBuildError(
                "WorkflowResult.run_id no coincide con ExecutionContext.run_id."
            )

        selected_task_ids = cls._select_task_ids(result, task_ids)
        artifacts: list[ReviewArtifactRef] = []
        for task_id in selected_task_ids:
            task_result = result.task_results[task_id]
            cls._require_task_succeeded(task_id, task_result)
            task_artifacts = tuple(task_result.artifacts)
            if not task_artifacts:
                raise ReviewTargetBuildError(
                    f"La tarea seleccionada '{task_id}' no produjo artifacts revisables."
                )

            context_artifacts = tuple(context.task_artifacts.get(task_id, ()))
            cls._validate_artifact_consistency(
                task_id,
                task_artifacts,
                context_artifacts,
            )
            artifacts.extend(
                cls._artifact_ref(task_id, artifact)
                for artifact in task_artifacts
            )

        if not artifacts:
            raise ReviewTargetBuildError(
                "El workflow completado no contiene artifacts para revisión final."
            )

        metadata = {
            "source": "f6_workflow_result",
            "workflow_status": cls._status_value(result.status),
            "selected_task_ids": list(selected_task_ids),
        }
        started_at = str(getattr(result, "started_at", "") or "").strip()
        finished_at = str(getattr(result, "finished_at", "") or "").strip()
        if started_at:
            metadata["workflow_started_at"] = started_at
        if finished_at:
            metadata["workflow_finished_at"] = finished_at

        try:
            return ReviewTarget(
                project_id=context.project_id,
                workflow_id=result.workflow_id,
                run_id=result.run_id,
                artifacts=tuple(artifacts),
                metadata=metadata,
            )
        except ValidationError as exc:
            raise ReviewTargetBuildError(
                "Los artifacts del workflow no forman un ReviewTarget válido."
            ) from exc

    @staticmethod
    def _validate_result_shape(result: Any) -> None:
        required = ("workflow_id", "run_id", "status", "context", "task_results")
        missing = [name for name in required if not hasattr(result, name)]
        if missing:
            raise TypeError(
                "result debe exponer el contrato de WorkflowResult; faltan: "
                f"{', '.join(missing)}."
            )
        context_required = ("project_id", "workflow_id", "run_id", "task_artifacts")
        missing_context = [
            name for name in context_required if not hasattr(result.context, name)
        ]
        if missing_context:
            raise TypeError(
                "result.context debe exponer el contrato de ExecutionContext; faltan: "
                f"{', '.join(missing_context)}."
            )
        if not isinstance(result.task_results, Mapping):
            raise TypeError("result.task_results debe ser un Mapping.")
        if not isinstance(result.context.task_artifacts, Mapping):
            raise TypeError("result.context.task_artifacts debe ser un Mapping.")

    @classmethod
    def _require_succeeded(cls, result: Any) -> None:
        status = cls._status_value(result.status)
        if status != "succeeded":
            raise ReviewTargetBuildError(
                "Solo un WorkflowResult con status='succeeded' puede entrar a final review; "
                f"status recibido: {status!r}."
            )

    @classmethod
    def _select_task_ids(
        cls,
        result: Any,
        task_ids: Iterable[str] | None,
    ) -> tuple[str, ...]:
        if task_ids is None:
            selected = tuple(
                str(task_id)
                for task_id, task_result in result.task_results.items()
                if cls._status_value(getattr(task_result, "status", None)) == "succeeded"
                and bool(getattr(task_result, "artifacts", ()))
            )
            if not selected:
                raise ReviewTargetBuildError(
                    "El workflow completado no contiene tareas exitosas con artifacts."
                )
            return selected

        selected = tuple(cls._normalize_task_id(task_id) for task_id in task_ids)
        if not selected:
            raise ReviewTargetBuildError("task_ids no puede estar vacío.")
        if len(set(selected)) != len(selected):
            raise ReviewTargetBuildError("task_ids contiene identificadores duplicados.")
        missing = [task_id for task_id in selected if task_id not in result.task_results]
        if missing:
            raise ReviewTargetBuildError(
                "Las tareas solicitadas no existen en WorkflowResult: "
                f"{', '.join(missing)}."
            )
        return selected

    @classmethod
    def _require_task_succeeded(cls, task_id: str, task_result: Any) -> None:
        status = cls._status_value(getattr(task_result, "status", None))
        if status != "succeeded":
            raise ReviewTargetBuildError(
                f"La tarea seleccionada '{task_id}' no terminó en succeeded: {status!r}."
            )

    @classmethod
    def _validate_artifact_consistency(
        cls,
        task_id: str,
        task_artifacts: tuple[Any, ...],
        context_artifacts: tuple[Any, ...],
    ) -> None:
        if len(task_artifacts) != len(context_artifacts):
            raise InconsistentReviewArtifactError(
                f"Artifacts inconsistentes para '{task_id}': TaskResult={len(task_artifacts)}, "
                f"ExecutionContext={len(context_artifacts)}."
            )
        task_identities = tuple(cls._artifact_identity(item) for item in task_artifacts)
        context_identities = tuple(cls._artifact_identity(item) for item in context_artifacts)
        if task_identities != context_identities:
            raise InconsistentReviewArtifactError(
                f"TaskResult.artifacts y ExecutionContext.task_artifacts difieren para '{task_id}'."
            )

    @classmethod
    def _artifact_ref(cls, task_id: str, artifact: Any) -> ReviewArtifactRef:
        mapping = cls._artifact_mapping(artifact)
        artifact_id = cls._required_text(mapping.get("artifact_id"), "artifact_id", task_id)
        content_hash = cls._optional_text(mapping.get("content_hash"))
        role = cls._optional_text(mapping.get("role"))
        metadata = cls._logical_metadata(mapping)
        try:
            return ReviewArtifactRef(
                artifact_id=artifact_id,
                content_hash=content_hash,
                task_id=task_id,
                role=role,
                metadata=metadata,
            )
        except ValidationError as exc:
            raise ReviewTargetBuildError(
                f"Artifact inválido en la tarea '{task_id}': {artifact_id!r}."
            ) from exc

    @classmethod
    def _artifact_identity(cls, artifact: Any) -> tuple[str, str | None]:
        mapping = cls._artifact_mapping(artifact)
        artifact_id = cls._required_text(mapping.get("artifact_id"), "artifact_id", "artifact")
        return artifact_id, cls._optional_text(mapping.get("content_hash"))

    @staticmethod
    def _artifact_mapping(artifact: Any) -> Mapping[str, Any]:
        if not isinstance(artifact, Mapping):
            raise ReviewTargetBuildError("Cada artifact debe ser un Mapping serializable.")
        return artifact

    @classmethod
    def _logical_metadata(cls, artifact: Mapping[str, Any]) -> dict[str, Any]:
        metadata: dict[str, Any] = {}
        nested = artifact.get("metadata")
        if nested is not None:
            if not isinstance(nested, Mapping):
                raise ReviewTargetBuildError("artifact.metadata debe ser un Mapping cuando exista.")
            metadata.update(
                {
                    str(key): value
                    for key, value in nested.items()
                    if str(key) not in _PHYSICAL_METADATA_KEYS
                }
            )

        for key in (
            "artifact_type",
            "mime_type",
            "media_type",
            "producer_role",
            "size_bytes",
            "deduplicated",
            "event_created",
        ):
            if key in artifact and key not in _PHYSICAL_METADATA_KEYS:
                metadata[key] = artifact[key]
        return metadata

    @staticmethod
    def _required_text(value: Any, label: str, task_id: str) -> str:
        text = "" if value is None else str(value).strip()
        if not text:
            raise ReviewTargetBuildError(
                f"Artifact de '{task_id}' no contiene {label} válido."
            )
        return text

    @staticmethod
    def _optional_text(value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @staticmethod
    def _normalize_task_id(value: Any) -> str:
        text = str(value).strip()
        if not text:
            raise ReviewTargetBuildError("task_ids no puede contener identificadores vacíos.")
        return text

    @staticmethod
    def _status_value(status: Any) -> str:
        value = getattr(status, "value", status)
        if value is None:
            return ""
        return str(value).strip().lower()


def build_review_target(
    result: Any,
    *,
    task_ids: Iterable[str] | None = None,
) -> ReviewTarget:
    """Functional facade for ``ReviewTargetBuilder.from_workflow_result``."""

    return ReviewTargetBuilder.from_workflow_result(result, task_ids=task_ids)


__all__ = ["ReviewTargetBuilder", "build_review_target"]
