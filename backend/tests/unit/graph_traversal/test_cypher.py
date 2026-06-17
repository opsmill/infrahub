"""Constructor-validation and dispatch tests for the path-traversal Cypher renderer."""

from __future__ import annotations

import pytest

from infrahub.core.branch import Branch
from infrahub.core.timestamp import Timestamp
from infrahub.graph_traversal._cypher import GraphTraversalCypherRenderer
from infrahub.graph_traversal.planning.models import Plan, TerminalById, TerminalByKinds


def _empty_plan() -> Plan:
    return Plan(
        source_kind="KindA",
        terminal_predicate=TerminalByKinds(kinds=frozenset({"KindB"})),
        max_depth=5,
    )


def _linear_plan(max_depth: int = 3) -> Plan:
    """A→B→C adjacency with terminal C.

    Feasible at depth 2 (A→B→C) and depth 3 (per-hop tuple reuse allows the
    B→C hop at two positions); infeasible at depth 1 (no direct A→C hop).
    """
    plan = Plan(
        source_kind="KindA",
        terminal_predicate=TerminalById(node_id="uuid-c", kind="KindC"),
        max_depth=max_depth,
    )
    plan.add_hop(source_kind="KindA", relationship_identifier="a__b", end_kind="KindB", min_hops_to_terminal=1)
    plan.add_hop(source_kind="KindB", relationship_identifier="b__c", end_kind="KindC", min_hops_to_terminal=0)
    return plan


def _default_branch() -> Branch:
    branch = Branch(name="main")
    branch.is_default = True
    return branch


def _build_renderer() -> GraphTraversalCypherRenderer:
    return GraphTraversalCypherRenderer(branch=_default_branch(), default_branch_name="main")


def _render_empty(*, max_paths: int = 100) -> None:
    _build_renderer().render(
        plan=_empty_plan(),
        source_id="src-uuid",
        at=Timestamp(),
        max_paths=max_paths,
    )


def _render_targets_empty(*, max_targets: int = 25) -> None:
    _build_renderer().render_reachable_targets(
        plan=_empty_plan(),
        source_id="src-uuid",
        at=Timestamp(),
        max_targets=max_targets,
    )


class TestGraphTraversalCypherRendererValidation:
    def test_rejects_max_targets_below_minimum(self) -> None:
        with pytest.raises(ValueError, match=r"max_targets must be in \[1, 200\]"):
            _render_targets_empty(max_targets=0)

    def test_rejects_max_targets_above_maximum(self) -> None:
        with pytest.raises(ValueError, match=r"max_targets must be in \[1, 200\]"):
            _render_targets_empty(max_targets=201)

    def test_rejects_max_paths_below_minimum(self) -> None:
        with pytest.raises(ValueError, match=r"max_paths must be in \[1, 5000\]"):
            _render_empty(max_paths=0)

    def test_rejects_max_paths_above_maximum(self) -> None:
        with pytest.raises(ValueError, match=r"max_paths must be in \[1, 5000\]"):
            _render_empty(max_paths=5001)

    def test_render_rejects_empty_plan(self) -> None:
        with pytest.raises(ValueError, match=r"plan has no adjacency"):
            _render_empty()


def _render_linear(*, depths: set[int] | None = None) -> str:
    rendered = _build_renderer().render(
        plan=_linear_plan(),
        source_id="src-uuid",
        at=Timestamp(),
        max_paths=10,
        depths=depths,
    )
    return rendered.text


class TestFeasibleDepths:
    def test_empty_plan_has_no_feasible_depths(self) -> None:
        assert _build_renderer().feasible_depths(plan=_empty_plan()) == []

    def test_returns_ascending_depths_that_can_reach_the_terminal(self) -> None:
        assert _build_renderer().feasible_depths(plan=_linear_plan()) == [2, 3]


class TestRenderDepthsFilter:
    def test_render_with_only_unfeasible_depths_raises(self) -> None:
        with pytest.raises(ValueError, match=r"no feasible fixed-depth query"):
            _render_linear(depths={1})
