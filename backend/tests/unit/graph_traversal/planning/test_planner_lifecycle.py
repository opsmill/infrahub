"""SchemaPlanner input-validation tests.

The planner is synchronous and fully constructible at instantiation time, so
there is no async initialization stage to guard against. The validation tests
here cover the ValueError paths in ``plan()``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from infrahub.core.schema import NodeSchema
from infrahub.graph_traversal.planning.constants import MAX_DEPTH, MIN_DEPTH
from infrahub.graph_traversal.planning.models import TerminalById, TerminalByKinds, UserFilters
from tests.helpers.graph_traversal.builders import build_schema_branch, make_planner

if TYPE_CHECKING:
    from infrahub.core.schema.schema_branch import SchemaBranch

_MAX_DEPTH_RE = rf"max_depth must be in \[{MIN_DEPTH}, {MAX_DEPTH}\]"


def _real_schema_with_single_kind() -> SchemaBranch:
    return build_schema_branch(nodes=[NodeSchema(name="Real", namespace="Testing")])


class TestSourceKindValidation:
    def test_source_kind_not_in_schema_raises_value_error(self) -> None:
        planner = make_planner(schema_branch=_real_schema_with_single_kind())
        with pytest.raises(ValueError, match="source_kind 'NotInSchema' not in schema"):
            planner.plan(
                source_kind="NotInSchema",
                terminal_predicate=TerminalByKinds(kinds=frozenset({"TestingReal"})),
                max_depth=5,
                user_filters=UserFilters(),
            )


class TestMaxDepthValidation:
    def test_max_depth_below_minimum_raises_value_error(self) -> None:
        planner = make_planner(schema_branch=_real_schema_with_single_kind())
        with pytest.raises(ValueError, match=_MAX_DEPTH_RE):
            planner.plan(
                source_kind="TestingReal",
                terminal_predicate=TerminalByKinds(kinds=frozenset({"TestingReal"})),
                max_depth=MIN_DEPTH - 1,
                user_filters=UserFilters(),
            )

    def test_max_depth_above_maximum_raises_value_error(self) -> None:
        planner = make_planner(schema_branch=_real_schema_with_single_kind())
        with pytest.raises(ValueError, match=_MAX_DEPTH_RE):
            planner.plan(
                source_kind="TestingReal",
                terminal_predicate=TerminalByKinds(kinds=frozenset({"TestingReal"})),
                max_depth=MAX_DEPTH + 1,
                user_filters=UserFilters(),
            )


class TestTerminalKindValidation:
    def test_terminal_by_id_kind_not_in_schema_raises_value_error(self) -> None:
        planner = make_planner(schema_branch=_real_schema_with_single_kind())
        with pytest.raises(ValueError, match="terminal kind 'NotInSchema' not in schema"):
            planner.plan(
                source_kind="TestingReal",
                terminal_predicate=TerminalById(node_id="uuid", kind="NotInSchema"),
                max_depth=5,
                user_filters=UserFilters(),
            )

    def test_terminal_by_kinds_with_unknown_kind_raises_value_error(self) -> None:
        planner = make_planner(schema_branch=_real_schema_with_single_kind())
        with pytest.raises(ValueError, match="terminal kind 'NotInSchema' not in schema"):
            planner.plan(
                source_kind="TestingReal",
                terminal_predicate=TerminalByKinds(kinds=frozenset({"TestingReal", "NotInSchema"})),
                max_depth=5,
                user_filters=UserFilters(),
            )
