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
        the only Source→Target route (through Forbidden) is pruned at the
        forbidden peer; no routes survive."""
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

    def test_route_retained_when_alternate_route_avoids_forbidden_kind(self) -> None:
        """Two structural routes exist (Source→Allowed→Target and
        Source→Forbidden→Target). ``TestingForbidden`` is denied, so only the
        Allowed route survives."""
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

    def test_route_excluded_when_source_kind_is_forbidden(self) -> None:
        """A forbidden source short-circuits the whole plan — every route
        would have to start at the source, so BFS doesn't even run."""
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

    def test_terminal_kind_is_checked(self) -> None:
        """A forbidden terminal kind is pruned when BFS reaches it as a peer."""
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
