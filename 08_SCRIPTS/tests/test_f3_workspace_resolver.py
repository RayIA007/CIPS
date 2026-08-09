"""Tests deterministas de F3.1 para WorkspaceResolver."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest


SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from workspace_models import WorkspaceIdentity
from workspace_resolver import (
    WorkspaceIdentityError,
    WorkspaceResolver,
    WorkspaceSecurityError,
)


def _resolver(base: Path) -> WorkspaceResolver:
    return WorkspaceResolver(
        projects_root=base / "04_PROYECTOS",
        outputs_root=base / "05_OUTPUTS",
    )


def test_identity_requires_project_id() -> None:
    with pytest.raises(ValueError):
        WorkspaceIdentity(project_id="   ")


def test_identity_requires_platform_and_execution_as_pair() -> None:
    with pytest.raises(ValueError):
        WorkspaceIdentity(project_id="PROYECTO_0001", platform="youtube")
    with pytest.raises(ValueError):
        WorkspaceIdentity(project_id="PROYECTO_0001", execution_id="RUN_001")


def test_project_workspace_is_deterministic_and_not_created_by_default() -> None:
    with TemporaryDirectory() as temp_dir:
        base = Path(temp_dir)
        resolver = _resolver(base)

        first = resolver.resolve_project_workspace("PROYECTO_0001")
        second = resolver.resolve_project_workspace("PROYECTO_0001")

        assert first == second
        assert first == (base / "04_PROYECTOS" / "PROYECTO_0001").resolve()
        assert not first.exists()


def test_project_workspace_create_and_reopen_is_idempotent() -> None:
    with TemporaryDirectory() as temp_dir:
        resolver = _resolver(Path(temp_dir))

        first = resolver.resolve_project_workspace("PROYECTO_0001", create=True)
        marker = first / "marker.txt"
        marker.write_text("preserve", encoding="utf-8")
        second = resolver.resolve_project_workspace("PROYECTO_0001", create=True)

        assert first == second
        assert second.is_dir()
        assert marker.read_text(encoding="utf-8") == "preserve"


def test_execution_workspace_uses_platform_and_execution() -> None:
    with TemporaryDirectory() as temp_dir:
        base = Path(temp_dir)
        resolver = _resolver(base)

        path = resolver.resolve_execution_workspace(
            "youtube",
            "RUN_2026_001",
            create=True,
        )

        expected = (base / "05_OUTPUTS" / "youtube" / "RUN_2026_001").resolve()
        assert path == expected
        assert path.is_dir()


def test_resolve_returns_project_and_execution_paths() -> None:
    with TemporaryDirectory() as temp_dir:
        base = Path(temp_dir)
        resolver = _resolver(base)
        identity = WorkspaceIdentity(
            project_id="PROYECTO_0007",
            platform="tiktok",
            execution_id="EXEC_0042",
        )

        paths = resolver.resolve(identity, create=True)

        assert paths.project_root == (
            base / "04_PROYECTOS" / "PROYECTO_0007"
        ).resolve()
        assert paths.execution_root == (
            base / "05_OUTPUTS" / "tiktok" / "EXEC_0042"
        ).resolve()
        assert paths.project_root.is_dir()
        assert paths.execution_root is not None
        assert paths.execution_root.is_dir()


@pytest.mark.parametrize(
    "invalid",
    [
        "..",
        ".",
        "../outside",
        "..\\outside",
        "folder/name",
        "folder\\name",
        "C:\\outside",
        "CON",
        "NUL.txt",
        "bad*name",
        "trailing.",
        " leading",
        "trailing ",
    ],
)
def test_invalid_workspace_segments_are_rejected(invalid: str) -> None:
    with TemporaryDirectory() as temp_dir:
        resolver = _resolver(Path(temp_dir))
        with pytest.raises((WorkspaceIdentityError, WorkspaceSecurityError)):
            resolver.resolve_project_workspace(invalid)


def test_confine_path_accepts_safe_nested_relative_path() -> None:
    with TemporaryDirectory() as temp_dir:
        resolver = _resolver(Path(temp_dir))
        workspace = resolver.resolve_project_workspace(
            "PROYECTO_0001",
            create=True,
        )

        target = resolver.confine_path(workspace, "04_CONTENIDO/script.md")

        assert target == (workspace / "04_CONTENIDO" / "script.md").resolve()
        assert not target.exists()


@pytest.mark.parametrize(
    "unsafe",
    [
        "../../outside.txt",
        "..\\..\\outside.txt",
        "/tmp/outside.txt",
        "C:\\outside\\file.txt",
        "safe/../outside.txt",
    ],
)
def test_confine_path_blocks_traversal_and_absolute_paths(unsafe: str) -> None:
    with TemporaryDirectory() as temp_dir:
        resolver = _resolver(Path(temp_dir))
        workspace = resolver.resolve_project_workspace(
            "PROYECTO_0001",
            create=True,
        )

        with pytest.raises(WorkspaceSecurityError):
            resolver.confine_path(workspace, unsafe)


def test_confine_path_rejects_workspace_outside_authorized_roots() -> None:
    with TemporaryDirectory() as temp_dir:
        base = Path(temp_dir)
        resolver = _resolver(base)
        outside = base / "OUTSIDE"
        outside.mkdir()

        with pytest.raises(WorkspaceSecurityError):
            resolver.confine_path(outside, "file.txt")


def test_confine_path_detects_existing_symlink_escape_when_supported() -> None:
    with TemporaryDirectory() as temp_dir:
        base = Path(temp_dir)
        resolver = _resolver(base)
        workspace = resolver.resolve_project_workspace(
            "PROYECTO_0001",
            create=True,
        )
        outside = base / "OUTSIDE"
        outside.mkdir()
        link = workspace / "escape_link"

        try:
            os.symlink(outside, link, target_is_directory=True)
        except (OSError, NotImplementedError):
            pytest.skip("El entorno no permite crear symlinks para esta prueba.")

        with pytest.raises(WorkspaceSecurityError):
            resolver.confine_path(workspace, "escape_link/file.txt")


def test_roots_can_be_injected_without_touching_real_cips_directories() -> None:
    with TemporaryDirectory() as temp_dir:
        base = Path(temp_dir)
        projects_root = base / "CUSTOM_PROJECTS"
        outputs_root = base / "CUSTOM_OUTPUTS"
        resolver = WorkspaceResolver(projects_root, outputs_root)

        assert resolver.projects_root == projects_root.resolve()
        assert resolver.outputs_root == outputs_root.resolve()
        assert not projects_root.exists()
        assert not outputs_root.exists()


def test_default_roots_reuse_existing_utils_constants(monkeypatch: pytest.MonkeyPatch) -> None:
    from types import ModuleType

    with TemporaryDirectory() as temp_dir:
        base = Path(temp_dir)
        fake_utils = ModuleType("utils")
        fake_utils.PROJECTS_DIR = base / "04_PROYECTOS"
        fake_utils.OUTPUTS_DIR = base / "05_OUTPUTS"
        monkeypatch.setitem(sys.modules, "utils", fake_utils)

        resolver = WorkspaceResolver()

        assert resolver.projects_root == fake_utils.PROJECTS_DIR.resolve()
        assert resolver.outputs_root == fake_utils.OUTPUTS_DIR.resolve()


def test_project_only_identity_has_no_execution_workspace() -> None:
    with TemporaryDirectory() as temp_dir:
        resolver = _resolver(Path(temp_dir))
        paths = resolver.resolve(
            WorkspaceIdentity(project_id="PROYECTO_0003"),
            create=True,
        )

        assert paths.project_root.is_dir()
        assert paths.execution_root is None
