"""Plan-time permission pruning tests for SchemaPlanner.

Uses a real ``PermissionResolver`` populated with wildcard-allow plus
per-kind-deny ``ObjectPermission`` entries. The resolver's specificity ranking
ensures kind-specific DENY overrides the wildcard ALLOW.
"""

from __future__ import annotations

from infrahub.core.constants import RelationshipCardinality, RelationshipDirection, RelationshipKind
from infrahub.core.schema import NodeSchema, RelationshipSchema
from infrahub.graph_traversal.planning.models import Hop, HopDirection, Route, TerminalByKinds, UserFilters
from tests.helpers.graph_traversal.builders import build_schema_branch, make_planner


def _node(name: str, *, relationships: list[RelationshipSchema] | None = None) -> NodeSchema:
    return NodeSchema(name=name, namespace="Testing", relationships=relationships or [])


def _rel(*, name: str, peer: str, identifier: str) -> RelationshipSchema:
    return RelationshipSchema(
        name=name,
        kind=RelationshipKind.GENERIC,
        peer=peer,
        cardinality=RelationshipCardinality.ONE,
        identifier=identifier,
        direction=RelationshipDirection.BIDIR,
    )


def _bidir_hop(start: str, end: str, identifier: str) -> Hop:
    return Hop(start_kind=start, end_kind=end, relationship_identifier=identifier, direction=HopDirection.BIDIR)


def _route_from_hops(*hops: Hop) -> Route:
    return Route(hops=hops, source_kind=hops[0].start_kind, terminal_kind=hops[-1].end_kind)


def _default_filters() -> UserFilters:
    return UserFilters.from_graphql_input(None)


class TestPermissionPruning:
    def test_route_excluded_when_intermediate_kind_is_forbidden(self) -> None:
        """With ``TestingForbidden`` denied and the default revisit-free policy,
        the only Source→Target route (through Forbidden) is pruned. No routes
        survive."""
        schema = build_schema_branch(
            nodes=[
                _node("Source", relationships=[_rel(name="rel_f", peer="TestingForbidden", identifier="s__f")]),
                _node("Forbidden", relationships=[_rel(name="rel_t", peer="TestingTarget", identifier="f__t")]),
                _node("Target"),
            ]
        )
        planner = make_planner(schema_branch=schema, denied_kinds={"TestingForbidden"})
        plan = planner.plan(
            source_kind="TestingSource",
            terminal_predicate=TerminalByKinds(kinds=frozenset({"TestingTarget"})),
            max_depth=5,
            user_filters=_default_filters(),
        )
        assert plan.routes == ()
        assert plan.pruned_for_permission == (
            _route_from_hops(
                _bidir_hop("TestingSource", "TestingForbidden", "s__f"),
                _bidir_hop("TestingForbidden", "TestingTarget", "f__t"),
            ),
        )

    def test_route_retained_when_alternate_route_avoids_forbidden_kind(self) -> None:
        """Two structural routes exist (Source→Allowed→Target and
        Source→Forbidden→Target). ``TestingForbidden`` is denied, so only the
        Allowed route survives — and the Forbidden route is recorded in
        ``pruned_for_permission`` verbatim."""
        schema = build_schema_branch(
            nodes=[
                _node(
                    "Source",
                    relationships=[
                        _rel(name="rel_a", peer="TestingAllowed", identifier="s__a"),
                        _rel(name="rel_f", peer="TestingForbidden", identifier="s__f"),
                    ],
                ),
                _node("Allowed", relationships=[_rel(name="rel_t", peer="TestingTarget", identifier="a__t")]),
                _node("Forbidden", relationships=[_rel(name="rel_t", peer="TestingTarget", identifier="f__t")]),
                _node("Target"),
            ]
        )
        planner = make_planner(schema_branch=schema, denied_kinds={"TestingForbidden"})
        plan = planner.plan(
            source_kind="TestingSource",
            terminal_predicate=TerminalByKinds(kinds=frozenset({"TestingTarget"})),
            max_depth=3,
            user_filters=_default_filters(),
        )
        assert plan.routes == (
            _route_from_hops(
                _bidir_hop("TestingSource", "TestingAllowed", "s__a"),
                _bidir_hop("TestingAllowed", "TestingTarget", "a__t"),
            ),
        )
        assert plan.pruned_for_permission == (
            _route_from_hops(
                _bidir_hop("TestingSource", "TestingForbidden", "s__f"),
                _bidir_hop("TestingForbidden", "TestingTarget", "f__t"),
            ),
        )

    def test_pruned_for_permission_records_dropped_routes_exactly(self) -> None:
        """``pruned_for_permission`` carries the full Route object — kinds,
        identifiers, and directions — for each dropped route, not just a count."""
        schema = build_schema_branch(
            nodes=[
                _node("Aaa", relationships=[_rel(name="rel_b", peer="TestingBbb", identifier="a__b")]),
                _node("Bbb", relationships=[_rel(name="rel_c", peer="TestingCcc", identifier="b__c")]),
                _node("Ccc"),
            ]
        )
        planner = make_planner(schema_branch=schema, denied_kinds={"TestingCcc"})
        plan = planner.plan(
            source_kind="TestingAaa",
            terminal_predicate=TerminalByKinds(kinds=frozenset({"TestingCcc"})),
            max_depth=2,
            user_filters=_default_filters(),
        )
        assert plan.routes == ()
        assert plan.pruned_for_permission == (
            _route_from_hops(
                _bidir_hop("TestingAaa", "TestingBbb", "a__b"),
                _bidir_hop("TestingBbb", "TestingCcc", "b__c"),
            ),
        )

    def test_route_excluded_when_source_kind_is_forbidden(self) -> None:
        """Permission pruning applies to every kind in the route, including the source position."""
        schema = build_schema_branch(
            nodes=[
                _node("Source", relationships=[_rel(name="rel_t", peer="TestingTarget", identifier="s__t")]),
                _node("Target"),
            ]
        )
        planner = make_planner(schema_branch=schema, denied_kinds={"TestingSource"})
        plan = planner.plan(
            source_kind="TestingSource",
            terminal_predicate=TerminalByKinds(kinds=frozenset({"TestingTarget"})),
            max_depth=2,
            user_filters=_default_filters(),
        )
        assert plan.routes == ()
        assert plan.pruned_for_permission == (_route_from_hops(_bidir_hop("TestingSource", "TestingTarget", "s__t")),)

    def test_terminal_kind_is_checked(self) -> None:
        schema = build_schema_branch(
            nodes=[
                _node("Source", relationships=[_rel(name="rel_t", peer="TestingTarget", identifier="s__t")]),
                _node("Target"),
            ]
        )
        planner = make_planner(schema_branch=schema, denied_kinds={"TestingTarget"})
        plan = planner.plan(
            source_kind="TestingSource",
            terminal_predicate=TerminalByKinds(kinds=frozenset({"TestingTarget"})),
            max_depth=2,
            user_filters=_default_filters(),
        )
        assert plan.routes == ()
        assert plan.pruned_for_permission == (_route_from_hops(_bidir_hop("TestingSource", "TestingTarget", "s__t")),)
