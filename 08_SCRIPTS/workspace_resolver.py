"""
=========================================================
Proyecto : CIPS
Release  : 0.8
Build    : 065-F3.1
Archivo  : workspace_resolver.py
Estado   : FASE 3.1
=========================================================

Resolución central y segura de workspaces CIPS.

La responsabilidad de ``WorkspaceResolver`` es exclusivamente decidir
DÓNDE debe vivir un recurso dentro de las raíces autorizadas de CIPS.
No persiste artefactos ni procesa medios.
"""

from __future__ import annotations

import os
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Iterable

from workspace_models import WorkspaceIdentity, WorkspacePaths


_WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
}
_WINDOWS_INVALID_CHARS = frozenset('<>:"/\\|?*')


class WorkspaceError(ValueError):
    """Error base de resolución de workspace."""


class WorkspaceIdentityError(WorkspaceError):
    """La identidad contiene un segmento inválido para filesystem."""


class WorkspaceSecurityError(WorkspaceError):
    """La operación intentaría escapar de una raíz autorizada."""


class WorkspaceResolver:
    """
    Resuelve workspaces de proyecto y de ejecución de forma determinista.

    Raíces canónicas actuales de CIPS:
    - proyectos: ``04_PROYECTOS``;
    - outputs de ejecución: ``05_OUTPUTS``.

    Las raíces pueden inyectarse para testing. Si no se especifican,
    se reutilizan ``PROJECTS_DIR`` y ``OUTPUTS_DIR`` desde ``utils``.
    """

    def __init__(
        self,
        projects_root: str | Path | None = None,
        outputs_root: str | Path | None = None,
    ) -> None:
        if projects_root is None or outputs_root is None:
            from utils import OUTPUTS_DIR, PROJECTS_DIR

            projects_root = PROJECTS_DIR if projects_root is None else projects_root
            outputs_root = OUTPUTS_DIR if outputs_root is None else outputs_root

        self._projects_root = self._normalize_root(projects_root)
        self._outputs_root = self._normalize_root(outputs_root)

    @property
    def projects_root(self) -> Path:
        """Raíz autorizada para proyectos CIPS."""

        return self._projects_root

    @property
    def outputs_root(self) -> Path:
        """Raíz autorizada para outputs de ejecución CIPS."""

        return self._outputs_root

    def resolve(
        self,
        identity: WorkspaceIdentity,
        *,
        create: bool = False,
    ) -> WorkspacePaths:
        """Resuelve todas las rutas físicas representadas por ``identity``."""

        project_root = self.resolve_project_workspace(
            identity.project_id,
            create=create,
        )

        execution_root: Path | None = None
        if identity.has_execution:
            execution_root = self.resolve_execution_workspace(
                identity.platform or "",
                identity.execution_id or "",
                create=create,
            )

        return WorkspacePaths(
            project_root=project_root,
            execution_root=execution_root,
        )

    def resolve_project_workspace(
        self,
        project_id: str,
        *,
        create: bool = False,
    ) -> Path:
        """Resuelve ``04_PROYECTOS/<project_id>`` con confinement."""

        project_segment = self._validate_segment(project_id, "project_id")
        path = self._confined_join(self._projects_root, (project_segment,))
        if create:
            path.mkdir(parents=True, exist_ok=True)
        return path

    def resolve_execution_workspace(
        self,
        platform: str,
        execution_id: str,
        *,
        create: bool = False,
    ) -> Path:
        """Resuelve ``05_OUTPUTS/<platform>/<execution_id>`` con confinement."""

        platform_segment = self._validate_segment(platform, "platform")
        execution_segment = self._validate_segment(execution_id, "execution_id")
        path = self._confined_join(
            self._outputs_root,
            (platform_segment, execution_segment),
        )
        if create:
            path.mkdir(parents=True, exist_ok=True)
        return path

    def confine_path(
        self,
        workspace_root: str | Path,
        relative_path: str | Path,
    ) -> Path:
        """
        Resuelve una ruta relativa sin permitir escape del workspace.

        Este método no crea archivos ni directorios. Está destinado a que
        F3.2+ pueda resolver destinos antes de persistir un artefacto.
        """

        authorized_workspace = self._validate_workspace_root(workspace_root)
        parts = self._validate_relative_path(relative_path)
        return self._confined_join(authorized_workspace, parts)

    @staticmethod
    def _normalize_root(root: str | Path) -> Path:
        raw = os.fspath(root)
        if not str(raw).strip():
            raise WorkspaceIdentityError("La raíz del workspace no puede estar vacía.")
        return Path(raw).expanduser().resolve(strict=False)

    def _validate_workspace_root(self, workspace_root: str | Path) -> Path:
        candidate = Path(workspace_root).expanduser().resolve(strict=False)
        if self._is_within(candidate, self._projects_root) or self._is_within(
            candidate,
            self._outputs_root,
        ):
            return candidate
        raise WorkspaceSecurityError(
            "workspace_root está fuera de las raíces autorizadas de CIPS."
        )

    @classmethod
    def _validate_relative_path(cls, relative_path: str | Path) -> tuple[str, ...]:
        raw = os.fspath(relative_path)
        text = str(raw)
        if not text.strip():
            raise WorkspaceIdentityError("relative_path no puede estar vacío.")
        if "\x00" in text:
            raise WorkspaceIdentityError("relative_path contiene un carácter NUL.")

        windows = PureWindowsPath(text)
        posix = PurePosixPath(text.replace("\\", "/"))
        if windows.is_absolute() or windows.drive or posix.is_absolute():
            raise WorkspaceSecurityError("No se permiten paths absolutos.")

        parts = tuple(posix.parts)
        if not parts:
            raise WorkspaceIdentityError("relative_path no contiene segmentos.")

        validated: list[str] = []
        for index, part in enumerate(parts):
            if part in {".", ".."}:
                raise WorkspaceSecurityError(
                    "No se permiten segmentos '.' ni '..' en relative_path."
                )
            validated.append(cls._validate_segment(part, f"relative_path[{index}]"))
        return tuple(validated)

    @classmethod
    def _validate_segment(cls, value: str, label: str) -> str:
        segment = str(value)
        if not segment or not segment.strip():
            raise WorkspaceIdentityError(f"{label} no puede estar vacío.")
        if segment != segment.strip():
            raise WorkspaceIdentityError(
                f"{label} no puede iniciar o terminar con espacios."
            )
        if segment in {".", ".."}:
            raise WorkspaceSecurityError(f"{label} no puede ser '{segment}'.")
        if any(char in segment for char in _WINDOWS_INVALID_CHARS):
            raise WorkspaceIdentityError(
                f"{label} contiene caracteres inválidos para filesystem."
            )
        if any(ord(char) < 32 for char in segment):
            raise WorkspaceIdentityError(
                f"{label} contiene caracteres de control inválidos."
            )
        if segment.endswith("."):
            raise WorkspaceIdentityError(
                f"{label} no puede terminar con punto en Windows."
            )

        device_name = segment.split(".", 1)[0].upper()
        if device_name in _WINDOWS_RESERVED_NAMES:
            raise WorkspaceIdentityError(
                f"{label} utiliza un nombre reservado por Windows."
            )

        return segment

    @classmethod
    def _confined_join(cls, root: Path, parts: Iterable[str]) -> Path:
        resolved_root = root.resolve(strict=False)
        candidate = resolved_root.joinpath(*parts).resolve(strict=False)
        if not cls._is_within(candidate, resolved_root):
            raise WorkspaceSecurityError(
                "La ruta resuelta intenta escapar del workspace autorizado."
            )
        return candidate

    @staticmethod
    def _is_within(candidate: Path, root: Path) -> bool:
        try:
            candidate.relative_to(root)
            return True
        except ValueError:
            return False


def get_workspace_resolver_info() -> dict[str, object]:
    """Devuelve información pública del componente F3.1."""

    return {
        "component": "workspace_resolver",
        "version": "0.8",
        "build": "065-F3.1",
        "roots": ["04_PROYECTOS", "05_OUTPUTS"],
        "security": ["path_confinement", "path_traversal_protection"],
    }
