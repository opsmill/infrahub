"""Constructor-validation and dispatch tests for the path-traversal Cypher renderer."""

from __future__ import annotations

import pytest

from infrahub.core.branch import Branch
from infrahub.core.timestamp import Timestamp
from infrahub.graph_traversal._cypher import PathTraversalCypherRenderer
from infrahub.graph_traversal.planning.models import Plan, TerminalByKinds


def _empty_plan() -> Plan:
    return Plan(
        source_kind="KindA",
        terminal_predicate=TerminalByKinds(kinds=frozenset({"KindB"})),
        max_depth=5,
    )


def _default_branch() -> Branch:
    branch = Branch(name="main")
    branch.is_default = True
    return branch


def _build_renderer() -> PathTraversalCypherRenderer:
    return PathTraversalCypherRenderer(branch=_default_branch(), default_branch_name="main")


def _render_empty(*, max_targets: int = 25, max_paths: int = 100) -> None:
    _build_renderer().render(
        plan=_empty_plan(),
        source_id="src-uuid",
        at=Timestamp(),
        max_targets=max_targets,
        max_paths=max_paths,
    )


class TestPathTraversalCypherRendererValidation:
    def test_rejects_max_targets_below_minimum(self) -> None:
        with pytest.raises(ValueError, match=r"max_targets must be in \[1, 200\]"):
            _render_empty(max_targets=0)

    def test_rejects_max_targets_above_maximum(self) -> None:
        with pytest.raises(ValueError, match=r"max_targets must be in \[1, 200\]"):
            _render_empty(max_targets=201)

    def test_rejects_max_paths_below_minimum(self) -> None:
        with pytest.raises(ValueError, match=r"max_paths must be in \[1, 5000\]"):
            _render_empty(max_paths=0)

    def test_rejects_max_paths_above_maximum(self) -> None:
        with pytest.raises(ValueError, match=r"max_paths must be in \[1, 5000\]"):
            _render_empty(max_paths=5001)

    def test_render_rejects_empty_plan(self) -> None:
        with pytest.raises(ValueError, match=r"plan has no adjacency"):
            _render_empty()
