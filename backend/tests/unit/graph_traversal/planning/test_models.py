from dataclasses import dataclass

import pytest

from infrahub.graph_traversal.planning.constants import DEFAULT_EXCLUDED_NAMESPACES
from infrahub.graph_traversal.planning.models import (
    Plan,
    TerminalById,
    TerminalByKinds,
    UserFilters,
)


class TestTerminalByKinds:
    def test_rejects_empty_kinds(self) -> None:
        with pytest.raises(ValueError, match=r"TerminalByKinds\.kinds must be non-empty"):
            TerminalByKinds(kinds=frozenset())

    def test_accepts_non_empty(self) -> None:
        terminal = TerminalByKinds(kinds=frozenset({"InfraDevice", "InfraInterface"}))
        assert terminal.kinds == frozenset({"InfraDevice", "InfraInterface"})


class TestTerminalById:
    def test_holds_node_id_and_kind(self) -> None:
        terminal = TerminalById(node_id="uuid-123", kind="InfraDevice")
        assert terminal.node_id == "uuid-123"
        assert terminal.kind == "InfraDevice"


class TestPlan:
    def test_add_hop_builds_adjacency_and_min_depth(self) -> None:
        plan = Plan(
            source_kind="A",
            terminal_predicate=TerminalById(node_id="uuid", kind="B"),
            max_depth=5,
        )
        plan.add_hop(source_kind="A", relationship_identifier="rel_ab", end_kind="B", min_hops_to_terminal=0)

        assert plan.get_all_source_kinds() == ["A"]
        assert plan.get_relationship_map_for_kind("A") == {"rel_ab": ["B"]}
        assert plan.get_min_depth_to_terminal_for_kind("B") == 0
        assert plan.get_min_depth_to_terminal_for_kind("A") is None
        assert plan.get_kinds_within_hops_of_terminal(max_hops=0) == ["B"]
        assert plan.is_empty is False

    def test_add_hop_keeps_smallest_min_depth_for_repeated_end_kind(self) -> None:
        plan = Plan(
            source_kind="A",
            terminal_predicate=TerminalById(node_id="uuid", kind="B"),
            max_depth=5,
        )
        plan.add_hop(source_kind="A", relationship_identifier="r1", end_kind="C", min_hops_to_terminal=3)
        plan.add_hop(source_kind="A", relationship_identifier="r2", end_kind="C", min_hops_to_terminal=1)
        plan.add_hop(source_kind="A", relationship_identifier="r3", end_kind="C", min_hops_to_terminal=5)

        assert plan.get_min_depth_to_terminal_for_kind("C") == 1

    def test_rejects_max_depth_below_minimum(self) -> None:
        with pytest.raises(ValueError, match=r"Plan.max_depth must be in \[1, 20\]"):
            Plan(
                source_kind="A",
                terminal_predicate=TerminalById(node_id="uuid", kind="B"),
                max_depth=0,
            )

    def test_rejects_max_depth_above_maximum(self) -> None:
        with pytest.raises(ValueError, match=r"Plan.max_depth must be in \[1, 20\]"):
            Plan(
                source_kind="A",
                terminal_predicate=TerminalById(node_id="uuid", kind="B"),
                max_depth=21,
            )

    def test_plan_with_no_hops_is_empty(self) -> None:
        plan = Plan(
            source_kind="A",
            terminal_predicate=TerminalById(node_id="uuid", kind="B"),
            max_depth=5,
        )
        assert plan.is_empty is True


@dataclass(kw_only=True)
class FakeGraphqlInput:
    """Stand-in for the graphene InputObjectType instances passed at runtime."""

    name: str
    kind_filter: list[str] | None = None
    excluded_kinds: list[str] | None = None
    excluded_namespaces: list[str] | None = None
    relationship_filter: list[str] | None = None


class TestUserFilters:
    def test_from_graphql_input_with_none_applies_default_excluded_namespaces(self) -> None:
        filters = UserFilters.from_graphql_input(None)
        assert filters.kind_filter == frozenset()
        assert filters.excluded_kinds == frozenset()
        assert filters.relationship_filter == frozenset()
        assert filters.excluded_namespaces == frozenset(DEFAULT_EXCLUDED_NAMESPACES)

    def test_from_graphql_input_with_empty_excluded_namespaces_keeps_defaults(self) -> None:
        # Additive: an empty list contributes nothing, defaults still apply.
        data = FakeGraphqlInput(name="empty_excluded", excluded_namespaces=[])
        filters = UserFilters.from_graphql_input(data)
        assert filters.excluded_namespaces == frozenset(DEFAULT_EXCLUDED_NAMESPACES)

    def test_from_graphql_input_with_user_supplied_excluded_namespaces_unions_with_defaults(self) -> None:
        # Additive: caller entries are unioned with the default set.
        data = FakeGraphqlInput(name="custom_excluded", excluded_namespaces=["Foo", "Bar"])
        filters = UserFilters.from_graphql_input(data)
        assert filters.excluded_namespaces == frozenset({"Foo", "Bar"}) | frozenset(DEFAULT_EXCLUDED_NAMESPACES)

    def test_from_graphql_input_passes_through_filter_fields(self) -> None:
        data = FakeGraphqlInput(
            name="all_filters",
            kind_filter=["InfraDevice"],
            excluded_kinds=["TestThing"],
            excluded_namespaces=["Foo"],
            relationship_filter=["primary_tag"],
        )
        filters = UserFilters.from_graphql_input(data)
        assert filters.kind_filter == frozenset({"InfraDevice"})
        assert filters.excluded_kinds == frozenset({"TestThing"})
        assert filters.excluded_namespaces == frozenset({"Foo"}) | frozenset(DEFAULT_EXCLUDED_NAMESPACES)
        assert filters.relationship_filter == frozenset({"primary_tag"})

    def test_from_graphql_input_handles_object_without_filter_fields(self) -> None:
        """ReachableNodesInput has none of the filter fields; getattr-defaults handle it."""

        @dataclass
        class MinimalInput:
            source_id: str

        filters = UserFilters.from_graphql_input(MinimalInput(source_id="x"))
        assert filters.kind_filter == frozenset()
        assert filters.excluded_kinds == frozenset()
        assert filters.relationship_filter == frozenset()
        assert filters.excluded_namespaces == frozenset(DEFAULT_EXCLUDED_NAMESPACES)
