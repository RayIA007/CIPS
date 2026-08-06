"""
===============================================================================
AUD-002
Directory Tree

File:
    directory_tree_builder.py

Purpose:
    Build the official repository directory tree from the existing
    Repository Audit System scan results.

Execution policy:
    READ ONLY

Output:
    repository_tree.md

===============================================================================
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable


@dataclass(slots=True)
class DirectoryTreeNode:
    """
    One directory or file node in the repository tree.
    """

    name: str
    relative_path: str
    is_directory: bool
    children: list["DirectoryTreeNode"] = field(
        default_factory=list
    )

    def add_child(
        self,
        child: "DirectoryTreeNode",
    ) -> None:
        self.children.append(child)

    def sort(self) -> None:
        self.children.sort(
            key=lambda item: (
                not item.is_directory,
                item.name.lower(),
            )
        )

        for child in self.children:
            child.sort()


class DirectoryTreeBuilder:
    """
    Build a deterministic repository tree from discovered files.

    The builder does not traverse the filesystem directly. It consumes
    the same file list produced by AUD-001 so both deliverables share a
    single repository scan.
    """

    def __init__(
        self,
        repository_root: Path,
    ) -> None:
        self.repository_root = repository_root.resolve()

    def build(
        self,
        files: Iterable[Path],
    ) -> DirectoryTreeNode:
        root = DirectoryTreeNode(
            name=self.repository_root.name,
            relative_path=".",
            is_directory=True,
        )

        directory_index: dict[str, DirectoryTreeNode] = {
            ".": root
        }

        normalized_files = sorted(
            (
                path.resolve()
                for path in files
            ),
            key=lambda path: str(
                path.relative_to(
                    self.repository_root
                )
            ).lower(),
        )

        for file_path in normalized_files:
            relative = file_path.relative_to(
                self.repository_root
            )

            parent_key = "."
            parent_node = root

            for part in relative.parts[:-1]:
                current_key = (
                    part
                    if parent_key == "."
                    else str(
                        Path(parent_key) / part
                    )
                )

                if current_key not in directory_index:
                    directory_node = DirectoryTreeNode(
                        name=part,
                        relative_path=current_key,
                        is_directory=True,
                    )
                    parent_node.add_child(
                        directory_node
                    )
                    directory_index[current_key] = (
                        directory_node
                    )

                parent_node = directory_index[
                    current_key
                ]
                parent_key = current_key

            file_node = DirectoryTreeNode(
                name=relative.name,
                relative_path=str(relative),
                is_directory=False,
            )

            parent_node.add_child(
                file_node
            )

        root.sort()
        return root


class RepositoryTreeWriter:
    """
    Serialize a DirectoryTreeNode hierarchy to Markdown.
    """

    def write(
        self,
        tree: DirectoryTreeNode,
        output_path: Path,
    ) -> None:
        output_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        lines = [
            "# Repository Directory Tree",
            "",
            "```text",
        ]

        lines.extend(
            self._render_node(
                tree,
                prefix="",
                is_last=True,
                is_root=True,
            )
        )

        lines.extend(
            [
                "```",
                "",
            ]
        )

        output_path.write_text(
            "\n".join(lines),
            encoding="utf-8",
        )

    def _render_node(
        self,
        node: DirectoryTreeNode,
        *,
        prefix: str,
        is_last: bool,
        is_root: bool = False,
    ) -> list[str]:
        lines: list[str] = []

        if is_root:
            lines.append(
                f"{node.name}/"
            )
        else:
            connector = (
                "└── "
                if is_last
                else "├── "
            )
            suffix = (
                "/"
                if node.is_directory
                else ""
            )
            lines.append(
                f"{prefix}{connector}"
                f"{node.name}{suffix}"
            )

        child_prefix = prefix

        if not is_root:
            child_prefix += (
                "    "
                if is_last
                else "│   "
            )

        for index, child in enumerate(
            node.children
        ):
            lines.extend(
                self._render_node(
                    child,
                    prefix=child_prefix,
                    is_last=(
                        index
                        == len(node.children) - 1
                    ),
                )
            )

        return lines


def build_repository_tree(
    *,
    repository_root: Path,
    files: Iterable[Path],
) -> DirectoryTreeNode:
    """
    Convenience API for AUD-002.
    """

    return DirectoryTreeBuilder(
        repository_root
    ).build(files)


def write_repository_tree(
    *,
    tree: DirectoryTreeNode,
    output_path: Path,
) -> None:
    """
    Convenience API for AUD-002.
    """

    RepositoryTreeWriter().write(
        tree,
        output_path,
    )