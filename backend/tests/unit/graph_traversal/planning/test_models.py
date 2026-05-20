from dataclasses import dataclass

import pytest

from infrahub.graph_traversal.planning.constants import DEFAULT_EXCLUDED_NAMESPACES
from infrahub.graph_traversal.planning.models import (
    Hop,
    HopDirection,
    Plan,
    Route,
    TerminalById,
    TerminalByKinds,
    UserFilters,
)


def make_hop(
    *,
    start_kind: str = "A",
    end_kind: str = "B",
    relationship_identifier: str = "rel",
    direction: HopDirection = HopDirection.OUTBOUND,
) -> Hop:
    return Hop(
        start_kind=start_kind,
        end_kind=end_kind,
        relationship_identifier=relationship_identifier,
        direction=direction,
    )


class TestHop:
    def test_rejects_empty_relationship_identifier(self) -> None:
        with pytest.raises(ValueError, match=r"Hop\.relationship_identifier must be non-empty"):
            Hop(
                start_kind="A",
                end_kind="B",
                relationship_identifier="",
                direction=HopDirection.OUTBOUND,
            )

    def test_accepts_each_direction(self) -> None:
        for direction in (HopDirection.OUTBOUND, HopDirection.INBOUND, HopDirection.BIDIR):
            hop = make_hop(direction=direction)
            assert hop.direction is direction


class TestRoute:
    def test_rejects_discontinuous_hops(self) -> None:
        hop_ab = make_hop(start_kind="A", end_kind="B")
        hop_cd = make_hop(start_kind="C", end_kind="D")
        with pytest.raises(ValueError, match=r"discontinuous at index 1"):
            Route(hops=(hop_ab, hop_cd), source_kind="A", terminal_kind="D")

    def test_rejects_source_kind_mismatch(self) -> None:
        hop = make_hop(start_kind="A", end_kind="B")
        with pytest.raises(ValueError, match=r"Route.source_kind"):
            Route(hops=(hop,), source_kind="X", terminal_kind="B")

    def test_rejects_terminal_kind_mismatch(self) -> None:
        hop = make_hop(start_kind="A", end_kind="B")
        with pytest.raises(ValueError, match=r"Route.terminal_kind"):
            Route(hops=(hop,), source_kind="A", terminal_kind="X")

    def test_rejects_empty_hops(self) -> None:
        with pytest.raises(ValueError, match=r"Route.hops length must be in \[1, 20\]"):
            Route(hops=(), source_kind="A", terminal_kind="A")

    def test_rejects_too_many_hops(self) -> None:
        hops = tuple(make_hop(start_kind="A", end_kind="A") for _ in range(21))
        with pytest.raises(ValueError, match=r"Route.hops length must be in \[1, 20\]"):
            Route(hops=hops, source_kind="A", terminal_kind="A")

    def test_length_and_kinds_properties(self) -> None:
        hop_ab = make_hop(start_kind="A", end_kind="B")
        hop_bc = make_hop(start_kind="B", end_kind="C")
        route = Route(hops=(hop_ab, hop_bc), source_kind="A", terminal_kind="C")
        assert route.length == 2
        assert route.kinds == ("A", "B", "C")


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
    def _make_route(self, *, source: str = "A", terminal: str = "B") -> Route:
        hop = make_hop(start_kind=source, end_kind=terminal)
        return Route(hops=(hop,), source_kind=source, terminal_kind=terminal)

    def test_constructs_with_only_routes(self) -> None:
        route = self._make_route()
        plan = Plan(
            routes=(route,),
            source_kind="A",
            terminal_predicate=TerminalById(node_id="uuid", kind="B"),
            max_depth=5,
        )
        assert plan.routes == (route,)

    def test_rejects_max_depth_below_minimum(self) -> None:
        with pytest.raises(ValueError, match=r"Plan.max_depth must be in \[1, 20\]"):
            Plan(
                routes=(),
                source_kind="A",
                terminal_predicate=TerminalById(node_id="uuid", kind="B"),
                max_depth=0,
            )

    def test_rejects_max_depth_above_maximum(self) -> None:
        with pytest.raises(ValueError, match=r"Plan.max_depth must be in \[1, 20\]"):
            Plan(
                routes=(),
                source_kind="A",
                terminal_predicate=TerminalById(node_id="uuid", kind="B"),
                max_depth=21,
            )

    def test_accepts_empty_routes(self) -> None:
        """Empty routes is the legitimate 'no viable path' signal."""
        plan = Plan(
            routes=(),
            source_kind="A",
            terminal_predicate=TerminalById(node_id="uuid", kind="B"),
            max_depth=5,
        )
        assert plan.routes == ()


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

    def test_from_graphql_input_with_empty_excluded_namespaces_replaces_defaults(self) -> None:
        """Replacement semantics: empty list = 'include all' (matches GraphQL input doc)."""
        data = FakeGraphqlInput(name="empty_excluded", excluded_namespaces=[])
        filters = UserFilters.from_graphql_input(data)
        assert filters.excluded_namespaces == frozenset() | frozenset(DEFAULT_EXCLUDED_NAMESPACES)

    def test_from_graphql_input_with_user_supplied_excluded_namespaces_replaces_defaults(self) -> None:
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
