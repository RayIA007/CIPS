"""Accumulative, request-aware context for FAO.3 editorial stages."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from editorial_contract import (
    EDITORIAL_PREREQUISITES,
    EDITORIAL_STAGES,
    canonical_editorial_path,
    contains_placeholder,
)
from runtime_component import RuntimeComponent
from runtime_context import RuntimeContext
from runtime_models import EngineResult


class EditorialContextEngine(RuntimeComponent):
    """Append the operational request and validated prior artifacts to context."""

    component_name = "editorial_context"
    REQUEST_SCHEMA_NAME = "cips.fao.operational_request"

    def execute(self, runtime_context: RuntimeContext) -> EngineResult:
        project = runtime_context.project
        stage = project.stage_actual

        if stage not in EDITORIAL_STAGES:
            return EngineResult.ok(
                data=runtime_context,
                message="El Stage no requiere contexto editorial FAO.3.",
                metadata={
                    "component": self.component_name,
                    "project_id": project.project_id,
                    "stage": stage,
                    "applied": False,
                },
            )

        if runtime_context.context_object is None:
            return EngineResult.fail(
                message="No existe ContextObject para ampliar con datos editoriales.",
                errors=["RuntimeContext.context_object no disponible."],
                metadata=self._base_metadata(runtime_context),
            )

        request_path = project.path / "operational_request.json"
        if not request_path.is_file():
            return EngineResult.ok(
                data=runtime_context,
                message=(
                    "Proyecto heredado sin solicitud FAO; se conserva el contexto "
                    "editorial anterior."
                ),
                warnings=[
                    "La validación editorial FAO.3 no se aplica a este proyecto heredado."
                ],
                metadata={
                    **self._base_metadata(runtime_context),
                    "applied": False,
                    "legacy_project": True,
                },
            )

        try:
            request = self._load_request(request_path)
            prerequisite_blocks, inputs = self._load_prerequisites(
                project.path,
                stage,
            )
        except (OSError, ValueError, json.JSONDecodeError) as error:
            return EngineResult.fail(
                message="No fue posible construir el contexto editorial verificable.",
                errors=[str(error)],
                metadata=self._base_metadata(runtime_context),
            )

        request_block = self._render_request(request)
        blocks = [
            runtime_context.context_object.content.strip(),
            request_block,
            *prerequisite_blocks,
        ]
        runtime_context.context_object.content = "\n\n---\n\n".join(
            block for block in blocks if block
        )
        runtime_context.context_object.metadata.update(
            {
                "editorial_context_applied": True,
                "operational_request_path": str(request_path),
                "editorial_input_paths": [item["path"] for item in inputs],
                "editorial_input_hashes": {
                    item["stage"]: item["sha256"] for item in inputs
                },
            }
        )
        runtime_context.metadata["operational_request"] = dict(request)
        runtime_context.metadata["editorial_inputs"] = inputs

        return EngineResult.ok(
            data=runtime_context,
            message="Solicitud y entregables previos añadidos al contexto editorial.",
            metadata={
                **self._base_metadata(runtime_context),
                "applied": True,
                "request_path": str(request_path),
                "prerequisite_stages": list(EDITORIAL_PREREQUISITES[stage]),
                "input_count": len(inputs),
                "context_characters": len(runtime_context.context_object.content),
            },
        )

    def _load_request(self, path: Path) -> dict[str, Any]:
        if not path.is_file():
            raise ValueError(f"Falta la solicitud operativa: {path}")

        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("operational_request.json debe contener un objeto JSON.")
        if data.get("schema_name") != self.REQUEST_SCHEMA_NAME:
            raise ValueError("La solicitud operativa no usa el schema FAO esperado.")
        if data.get("publication_performed") is not False:
            raise ValueError("La solicitud debe conservar publication_performed=false.")

        required = (
            "topic",
            "platform",
            "duration_seconds",
            "audience",
            "creative_style",
        )
        missing = [name for name in required if data.get(name) in (None, "")]
        if missing:
            raise ValueError(
                "La solicitud operativa está incompleta: " + ", ".join(missing)
            )
        return data

    def _load_prerequisites(
        self,
        project_path: Path,
        stage: str,
    ) -> tuple[list[str], list[dict[str, str]]]:
        blocks: list[str] = []
        inputs: list[dict[str, str]] = []

        for prerequisite in EDITORIAL_PREREQUISITES[stage]:
            path = canonical_editorial_path(project_path, prerequisite)
            if not path.is_file():
                raise ValueError(
                    f"Falta el entregable previo '{prerequisite}': {path}"
                )
            content = path.read_text(encoding="utf-8").strip()
            if not content or contains_placeholder(content):
                raise ValueError(
                    f"El entregable previo '{prerequisite}' está vacío o pendiente."
                )

            relative_path = path.relative_to(project_path).as_posix()
            digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
            blocks.append(
                "\n".join(
                    (
                        f"# ENTREGABLE APROBADO — {prerequisite.upper()}",
                        "",
                        f"Ruta: {relative_path}",
                        f"SHA-256: {digest}",
                        "",
                        content,
                    )
                )
            )
            inputs.append(
                {
                    "stage": prerequisite,
                    "path": relative_path,
                    "sha256": digest,
                }
            )

        return blocks, inputs

    @staticmethod
    def _render_request(request: dict[str, Any]) -> str:
        return "\n".join(
            (
                "# SOLICITUD OPERATIVA AUTORITATIVA",
                "",
                f"- Tema: {request['topic']}",
                f"- Plataforma: {request['platform']}",
                f"- Duración objetivo: {request['duration_seconds']} segundos",
                f"- Audiencia: {request['audience']}",
                f"- Estilo creativo: {request['creative_style']}",
                f"- Free Tier predeterminado: {str(bool(request.get('free_tier_default', True))).lower()}",
                "- Publicación realizada: false",
            )
        )

    def _base_metadata(self, runtime_context: RuntimeContext) -> dict[str, Any]:
        project = runtime_context.project
        return {
            "component": self.component_name,
            "project_id": project.project_id,
            "stage": project.stage_actual,
        }


__all__ = ["EditorialContextEngine"]
