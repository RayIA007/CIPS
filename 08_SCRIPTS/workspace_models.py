"""
=========================================================
Proyecto : CIPS
Release  : 0.8
Build    : 065-F3.1
Archivo  : workspace_models.py
Estado   : FASE 3.1
=========================================================

Modelos mínimos para identificar y resolver workspaces CIPS.

Responsabilidades:
- Representar la identidad lógica (proyecto, plataforma, ejecución).
- Transportar las rutas físicas resueltas sin construirlas.

Este módulo NO:
- Accede al filesystem.
- Crea directorios.
- Decide políticas de rutas.
- Procesa artefactos.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class WorkspaceIdentity:
    """
    Identidad lógica de un workspace CIPS.

    ``project_id`` siempre identifica el proyecto. ``platform`` y
    ``execution_id`` son opcionales como pareja: si se proporciona uno,
    debe proporcionarse también el otro.
    """

    project_id: str
    platform: str | None = None
    execution_id: str | None = None

    def __post_init__(self) -> None:
        project_id = str(self.project_id).strip()
        platform = None if self.platform is None else str(self.platform).strip()
        execution_id = (
            None if self.execution_id is None else str(self.execution_id).strip()
        )

        if not project_id:
            raise ValueError("project_id no puede estar vacío.")

        has_platform = bool(platform)
        has_execution = bool(execution_id)
        if has_platform != has_execution:
            raise ValueError(
                "platform y execution_id deben proporcionarse juntos."
            )

        object.__setattr__(self, "project_id", project_id)
        object.__setattr__(self, "platform", platform if has_platform else None)
        object.__setattr__(
            self,
            "execution_id",
            execution_id if has_execution else None,
        )

    @property
    def has_execution(self) -> bool:
        """Indica si la identidad incluye plataforma y ejecución."""

        return self.platform is not None and self.execution_id is not None


@dataclass(frozen=True, slots=True)
class WorkspacePaths:
    """Rutas físicas resueltas para una ``WorkspaceIdentity``."""

    project_root: Path
    execution_root: Path | None = None


def get_workspace_models_info() -> dict[str, object]:
    """Devuelve información pública del módulo F3.1."""

    return {
        "component": "workspace_models",
        "version": "0.8",
        "build": "065-F3.1",
        "models": ["WorkspaceIdentity", "WorkspacePaths"],
    }
