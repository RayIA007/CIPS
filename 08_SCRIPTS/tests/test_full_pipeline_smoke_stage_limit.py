"""
Regresión para impedir que el Full Pipeline Smoke quede limitado
a menos ejecuciones que Stages productivos.
"""

from __future__ import annotations

import ast
from pathlib import Path


SOURCE_PATH = (
    Path(__file__).resolve().parents[1]
    / "full_pipeline_smoke_test.py"
)


def _module_tree() -> ast.Module:
    return ast.parse(
        SOURCE_PATH.read_text(encoding="utf-8"),
        filename=str(SOURCE_PATH),
    )


def _assignment_value(name: str) -> ast.expr:
    for node in _module_tree().body:
        if not isinstance(node, ast.Assign):
            continue

        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == name:
                return node.value

    raise AssertionError(f"No existe la asignación {name!r}.")


def test_max_executions_is_derived_from_expected_production_stages():
    value = _assignment_value("MAX_EXECUTIONS")

    assert isinstance(value, ast.Call)
    assert isinstance(value.func, ast.Name)
    assert value.func.id == "len"
    assert len(value.args) == 1
    assert isinstance(value.args[0], ast.Name)
    assert value.args[0].id == "EXPECTED_PRODUCTION_STAGES"


def test_max_executions_is_not_a_hardcoded_number():
    value = _assignment_value("MAX_EXECUTIONS")

    assert not (
        isinstance(value, ast.Constant)
        and isinstance(value.value, int)
    )


def test_main_loop_uses_max_executions_guard():
    tree = _module_tree()

    matching_ranges = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.For):
            continue
        if not isinstance(node.iter, ast.Call):
            continue
        if not isinstance(node.iter.func, ast.Name):
            continue
        if node.iter.func.id != "range":
            continue

        matching_ranges.append(node.iter)

    assert any(
        any(
            isinstance(child, ast.Name)
            and child.id == "MAX_EXECUTIONS"
            for child in ast.walk(range_call)
        )
        for range_call in matching_ranges
    )
