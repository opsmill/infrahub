"""Constructor-validation tests for PathTraversalQuery."""

from __future__ import annotations

import pytest

from infrahub.graph_traversal.path import PathTraversalQuery
from infrahub.graph_traversal.planning.models import (
    Plan,
    TerminalById,
    TerminalByKinds,
)


def _plan_with_one_hop() -> Plan:
    return Plan(
        adjacency={"KindA": {"a__b": frozenset({"KindB"})}},
        source_kind="KindA",
        terminal_predicate=TerminalById(node_id="dest-uuid", kind="KindB"),
        max_depth=5,
    )


def _empty_plan() -> Plan:
    return Plan(
        adjacency={},
        source_kind="KindA",
        terminal_predicate=TerminalByKinds(kinds=frozenset({"KindB"})),
        max_depth=5,
    )


class TestPathTraversalQueryValidation:
    def test_rejects_empty_plan(self) -> None:
        with pytest.raises(ValueError, match=r"non-empty plan"):
            PathTraversalQuery(plan=_empty_plan(), source_id="src-uuid")

    def test_accepts_valid_parameters(self) -> None:
        plan = _plan_with_one_hop()
        query = PathTraversalQuery(plan=plan, source_id="src-uuid", max_paths=5)
        assert query.plan is plan
        assert query.source_id == "src-uuid"
        assert query.max_paths == 5

    def test_default_max_paths(self) -> None:
        query = PathTraversalQuery(plan=_plan_with_one_hop(), source_id="src-uuid")
        assert query.max_paths == 10
