"""Constructor-validation tests for ReachableNodesQuery."""

from __future__ import annotations

import pytest

from infrahub.graph_traversal.planning.models import Plan, TerminalByKinds
from infrahub.graph_traversal.reachable import ReachableNodesQuery


def _plan_with_one_hop() -> Plan:
    return Plan(
        adjacency={"KindA": {"a__b": frozenset({"KindB"})}},
        source_kind="KindA",
        terminal_predicate=TerminalByKinds(kinds=frozenset({"KindB"})),
        max_depth=5,
    )


def _empty_plan() -> Plan:
    return Plan(
        adjacency={},
        source_kind="KindA",
        terminal_predicate=TerminalByKinds(kinds=frozenset({"KindB"})),
        max_depth=5,
    )


class TestReachableNodesQueryValidation:
    def test_rejects_empty_plan(self) -> None:
        with pytest.raises(ValueError, match=r"non-empty plan"):
            ReachableNodesQuery(plan=_empty_plan(), source_id="src-uuid", default_branch_name="main")

    def test_accepts_valid_parameters(self) -> None:
        plan = _plan_with_one_hop()
        query = ReachableNodesQuery(plan=plan, source_id="src-uuid", default_branch_name="main", max_results=25)
        assert query.plan is plan
        assert query.source_id == "src-uuid"
        assert query.default_branch_name == "main"
        assert query.max_results == 25

    def test_default_max_results(self) -> None:
        query = ReachableNodesQuery(plan=_plan_with_one_hop(), source_id="src-uuid", default_branch_name="main")
        assert query.max_results == 50
