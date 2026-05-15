"""Schema-driven unit tests for SchemaPlanner.

Uses real ``SchemaBranch`` and ``PermissionResolver`` constructed via
``tests.helpers.graph_traversal.builders``. No database required —
``SchemaBranch.process()`` is sufficient to populate relationship identifiers
and ``GenericSchema.used_by``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.constants import RelationshipCardinality, RelationshipDirection, RelationshipKind
from infrahub.core.schema import GenericSchema, NodeSchema, RelationshipSchema
from infrahub.graph_traversal.planning.models import (
    Hop,
    HopDirection,
    Route,
    TerminalById,
    TerminalByKinds,
    UserFilters,
)
from tests.helpers.graph_traversal.builders import build_schema_branch, make_planner

if TYPE_CHECKING:
    from infrahub.core.schema.schema_branch import SchemaBranch


def _node(
    name: str,
    *,
    namespace: str = "Testing",
    relationships: list[RelationshipSchema] | None = None,
    inherit_from: list[str] | None = None,
) -> NodeSchema:
    return NodeSchema(
        name=name,
        namespace=namespace,
        relationships=relationships or [],
        inherit_from=inherit_from or [],
    )


def _rel(
    *,
    name: str,
    peer: str,
    identifier: str,
    direction: RelationshipDirection = RelationshipDirection.BIDIR,
) -> RelationshipSchema:
    return RelationshipSchema(
        name=name,
        kind=RelationshipKind.GENERIC,
        peer=peer,
        cardinality=RelationshipCardinality.ONE,
        identifier=identifier,
        direction=direction,
    )


def _bidir_hop(start: str, end: str, identifier: str) -> Hop:
    return Hop(start_kind=start, end_kind=end, relationship_identifier=identifier, direction=HopDirection.BIDIR)


def _route_from_hops(*hops: Hop) -> Route:
    return Route(hops=hops, source_kind=hops[0].start_kind, terminal_kind=hops[-1].end_kind)


def _default_filters() -> UserFilters:
    return UserFilters.from_graphql_input(None)


class TestEmptyPlan:
    def test_empty_when_source_and_target_kinds_are_disconnected(self, disconnected_schema: SchemaBranch) -> None:
        planner = make_planner(schema_branch=disconnected_schema)
        plan = planner.plan(
            source_kind="TestingAlpha",
            terminal_predicate=TerminalByKinds(kinds=frozenset({"TestingBeta"})),
            max_depth=5,
            user_filters=_default_filters(),
        )
        assert plan.routes == ()
        assert plan.pruned_for_user_filters == ()
        assert plan.pruned_for_permission == ()


class TestRouteEnumeration:
    def test_finds_single_hop_route(self, linear_a_b_c_schema: SchemaBranch) -> None:
        planner = make_planner(schema_branch=linear_a_b_c_schema)
        plan = planner.plan(
            source_kind="TestingKindA",
            terminal_predicate=TerminalByKinds(kinds=frozenset({"TestingKindB"})),
            max_depth=1,
            user_filters=_default_filters(),
        )
        expected = _route_from_hops(_bidir_hop("TestingKindA", "TestingKindB", "a__b"))
        assert plan.routes == (expected,)

    def test_finds_multi_hop_route_through_intermediate(self, linear_a_b_c_schema: SchemaBranch) -> None:
        """With the default ``allow_schema_revisits=False`` filter, A→C over a
        BIDIR chain returns exactly the direct route — the length-4 BIDIR
        revisits that would otherwise appear are pruned at BFS time."""
        planner = make_planner(schema_branch=linear_a_b_c_schema)
        plan = planner.plan(
            source_kind="TestingKindA",
            terminal_predicate=TerminalByKinds(kinds=frozenset({"TestingKindC"})),
            max_depth=5,
            user_filters=_default_filters(),
        )
        assert plan.routes == (
            _route_from_hops(
                _bidir_hop("TestingKindA", "TestingKindB", "a__b"),
                _bidir_hop("TestingKindB", "TestingKindC", "b__c"),
            ),
        )

    def test_max_depth_caps_route_length(self) -> None:
        schema = build_schema_branch(
            nodes=[
                _node("Aaa", relationships=[_rel(name="rel_b", peer="TestingBbb", identifier="aaa__bbb")]),
                _node("Bbb", relationships=[_rel(name="rel_c", peer="TestingCcc", identifier="bbb__ccc")]),
                _node("Ccc", relationships=[_rel(name="rel_d", peer="TestingDdd", identifier="ccc__ddd")]),
                _node("Ddd", relationships=[_rel(name="rel_e", peer="TestingEee", identifier="ddd__eee")]),
                _node("Eee", relationships=[_rel(name="rel_f", peer="TestingFff", identifier="eee__fff")]),
                _node("Fff"),
            ]
        )
        planner = make_planner(schema_branch=schema)
        plan_shallow = planner.plan(
            source_kind="TestingAaa",
            terminal_predicate=TerminalByKinds(kinds=frozenset({"TestingFff"})),
            max_depth=3,
            user_filters=_default_filters(),
        )
        assert plan_shallow.routes == ()

        plan_deep = planner.plan(
            source_kind="TestingAaa",
            terminal_predicate=TerminalByKinds(kinds=frozenset({"TestingFff"})),
            max_depth=5,
            user_filters=_default_filters(),
        )
        # The shortest route is the direct A→B→C→D→E→F chain (length 5).
        assert plan_deep.routes[0] == _route_from_hops(
            _bidir_hop("TestingAaa", "TestingBbb", "aaa__bbb"),
            _bidir_hop("TestingBbb", "TestingCcc", "bbb__ccc"),
            _bidir_hop("TestingCcc", "TestingDdd", "ccc__ddd"),
            _bidir_hop("TestingDdd", "TestingEee", "ddd__eee"),
            _bidir_hop("TestingEee", "TestingFff", "eee__fff"),
        )

    def test_allow_schema_revisits_emits_routes_that_revisit_kinds_within_depth_cap(
        self, linear_a_b_c_schema: SchemaBranch
    ) -> None:
        """With ``allow_schema_revisits=True``, the planner walks each BIDIR
        schema edge in both directions during enumeration. A route like
        A→B→A→B is therefore valid: each hop traverses a real schema edge,
        the same kind may appear multiple times along a route, and only the
        total hop count is bounded by ``max_depth``.

        With ``max_depth=5`` and terminal ``KindB``, this yields seven routes —
        the direct one plus six revisits — sorted by length, then kinds, then
        identifiers, then directions.
        """
        planner = make_planner(schema_branch=linear_a_b_c_schema)
        plan = planner.plan(
            source_kind="TestingKindA",
            terminal_predicate=TerminalByKinds(kinds=frozenset({"TestingKindB"})),
            max_depth=5,
            user_filters=UserFilters(allow_schema_revisits=True),
        )
        a, b, c = "TestingKindA", "TestingKindB", "TestingKindC"
        ab = _bidir_hop(a, b, "a__b")
        ba = _bidir_hop(b, a, "a__b")
        bc = _bidir_hop(b, c, "b__c")
        cb = _bidir_hop(c, b, "b__c")
        assert plan.routes == (
            _route_from_hops(ab),
            _route_from_hops(ab, ba, ab),
            _route_from_hops(ab, bc, cb),
            _route_from_hops(ab, ba, ab, ba, ab),
            _route_from_hops(ab, ba, ab, bc, cb),
            _route_from_hops(ab, bc, cb, ba, ab),
            _route_from_hops(ab, bc, cb, bc, cb),
        )


class TestGenericExpansion:
    def test_generic_peer_expands_to_one_route_per_concrete_inheritor(self) -> None:
        schema = build_schema_branch(
            nodes=[
                _node(
                    "Device",
                    relationships=[
                        _rel(name="interfaces", peer="TestingInterfaceGeneric", identifier="device__interfaces"),
                    ],
                ),
                _node("EthernetInterface", inherit_from=["TestingInterfaceGeneric"]),
                _node("VirtualInterface", inherit_from=["TestingInterfaceGeneric"]),
            ],
            generics=[GenericSchema(name="InterfaceGeneric", namespace="Testing")],
        )
        planner = make_planner(schema_branch=schema)
        plan = planner.plan(
            source_kind="TestingDevice",
            terminal_predicate=TerminalByKinds(
                kinds=frozenset({"TestingEthernetInterface", "TestingVirtualInterface"})
            ),
            max_depth=1,
            user_filters=_default_filters(),
        )
        # One route per concrete inheritor of the generic peer; the generic kind
        # itself never appears in a Hop. Both routes share the rel identifier
        # because they walk the same schema edge declared on Device, only the
        # concrete end-kind differs (alphabetical Ethernet first per sort).
        assert plan.routes == (
            _route_from_hops(_bidir_hop("TestingDevice", "TestingEthernetInterface", "device__interfaces")),
            _route_from_hops(_bidir_hop("TestingDevice", "TestingVirtualInterface", "device__interfaces")),
        )


class TestDirectionPreservation:
    def test_bidir_is_recorded_verbatim_and_not_split(self) -> None:
        schema = build_schema_branch(
            nodes=[
                _node(
                    "Owner",
                    relationships=[
                        _rel(
                            name="rel_peer",
                            peer="TestingPeer",
                            identifier="owner__peer",
                            direction=RelationshipDirection.BIDIR,
                        ),
                    ],
                ),
                _node("Peer"),
            ]
        )
        planner = make_planner(schema_branch=schema)
        plan = planner.plan(
            source_kind="TestingOwner",
            terminal_predicate=TerminalByKinds(kinds=frozenset({"TestingPeer"})),
            max_depth=1,
            user_filters=_default_filters(),
        )
        # Single hop, direction recorded as BIDIR — not split into OUTBOUND+INBOUND routes.
        assert plan.routes == (_route_from_hops(_bidir_hop("TestingOwner", "TestingPeer", "owner__peer")),)

    def test_outbound_in_forward_walk_is_outbound(self) -> None:
        schema = build_schema_branch(
            nodes=[
                _node(
                    "Source",
                    relationships=[
                        _rel(
                            name="rel_target",
                            peer="TestingTarget",
                            identifier="source__target",
                            direction=RelationshipDirection.OUTBOUND,
                        ),
                    ],
                ),
                _node("Target"),
            ]
        )
        planner = make_planner(schema_branch=schema)
        plan = planner.plan(
            source_kind="TestingSource",
            terminal_predicate=TerminalByKinds(kinds=frozenset({"TestingTarget"})),
            max_depth=1,
            user_filters=_default_filters(),
        )
        assert plan.routes == (
            Route(
                hops=(
                    Hop(
                        start_kind="TestingSource",
                        end_kind="TestingTarget",
                        relationship_identifier="source__target",
                        direction=HopDirection.OUTBOUND,
                    ),
                ),
                source_kind="TestingSource",
                terminal_kind="TestingTarget",
            ),
        )

    def test_outbound_in_reverse_walk_is_inbound(self) -> None:
        """A schema rel declared on Source as OUTBOUND with peer=Target is also
        walkable from Target back to Source — and the Hop must record that
        reverse walk as INBOUND so the renderer emits the correct arrow shape.
        """
        schema = build_schema_branch(
            nodes=[
                _node(
                    "Source",
                    relationships=[
                        _rel(
                            name="rel_target",
                            peer="TestingTarget",
                            identifier="source__target",
                            direction=RelationshipDirection.OUTBOUND,
                        ),
                    ],
                ),
                _node("Target"),
            ]
        )
        planner = make_planner(schema_branch=schema)
        plan = planner.plan(
            source_kind="TestingTarget",
            terminal_predicate=TerminalByKinds(kinds=frozenset({"TestingSource"})),
            max_depth=1,
            user_filters=_default_filters(),
        )
        assert plan.routes == (
            Route(
                hops=(
                    Hop(
                        start_kind="TestingTarget",
                        end_kind="TestingSource",
                        relationship_identifier="source__target",
                        direction=HopDirection.INBOUND,
                    ),
                ),
                source_kind="TestingTarget",
                terminal_kind="TestingSource",
            ),
        )


class TestAllowSchemaRevisits:
    def test_default_revisit_free_collapses_bidir_cycles_to_direct_route(
        self, linear_a_b_c_schema: SchemaBranch
    ) -> None:
        """With the default ``allow_schema_revisits=False``, the BIDIR chain
        A↔B↔C produces only the direct A→B route from A toward kind B — the
        six cyclic variants the planner would otherwise emit are pruned at
        BFS time."""
        planner = make_planner(schema_branch=linear_a_b_c_schema)
        plan = planner.plan(
            source_kind="TestingKindA",
            terminal_predicate=TerminalByKinds(kinds=frozenset({"TestingKindB"})),
            max_depth=5,
            user_filters=_default_filters(),
        )
        assert plan.routes == (_route_from_hops(_bidir_hop("TestingKindA", "TestingKindB", "a__b")),)

    def test_same_kind_source_and_terminal_is_allowed_under_default(self) -> None:
        """The single boundary-case exception: a route may begin and end at
        the same kind (supporting same-kind source/target queries) — the
        intermediates still must be distinct and not equal the boundary kind."""
        schema = build_schema_branch(
            nodes=[
                _node(
                    "Friend",
                    relationships=[
                        _rel(name="rel_other", peer="TestingFriend", identifier="friend__friend"),
                    ],
                ),
            ]
        )
        planner = make_planner(schema_branch=schema)
        # Direct Friend→Friend (1-hop self-relationship — terminal kind == source kind).
        plan = planner.plan(
            source_kind="TestingFriend",
            terminal_predicate=TerminalByKinds(kinds=frozenset({"TestingFriend"})),
            max_depth=2,
            user_filters=_default_filters(),
        )
        # The single direct route survives; revisits within the same path are still pruned.
        assert plan.routes == (_route_from_hops(_bidir_hop("TestingFriend", "TestingFriend", "friend__friend")),)

    def test_same_kind_endpoints_via_intermediate_works_under_default(self) -> None:
        """A→B→A is allowed under the default revisit-free policy when the
        terminal kind matches the source kind. The intermediate (B) is
        distinct from the boundary kind (A), so the route is not a revisit."""
        schema = build_schema_branch(
            nodes=[
                _node("Aaa", relationships=[_rel(name="rel_b", peer="TestingBbb", identifier="a__b")]),
                _node("Bbb"),
            ]
        )
        planner = make_planner(schema_branch=schema)
        plan = planner.plan(
            source_kind="TestingAaa",
            terminal_predicate=TerminalByKinds(kinds=frozenset({"TestingAaa"})),
            max_depth=2,
            user_filters=_default_filters(),
        )
        # The A→B→A route survives — A appears at source and terminal positions,
        # B is a distinct intermediate. Further A→B→A→B→A would put A as an
        # intermediate (forbidden), so no length-4 routes are emitted.
        assert plan.routes == (
            _route_from_hops(
                _bidir_hop("TestingAaa", "TestingBbb", "a__b"),
                _bidir_hop("TestingBbb", "TestingAaa", "a__b"),
            ),
        )


class TestUserFilters:
    def test_default_excluded_namespaces_prune_routes_through_excluded_kinds(self) -> None:
        """A route that traverses a kind in a default-excluded namespace (``Internal``)
        must be pruned to ``Plan.pruned_for_user_filters``."""
        schema = build_schema_branch(
            nodes=[
                _node(
                    "Item",
                    namespace="Testing",
                    relationships=[_rel(name="rel_int", peer="InternalThing", identifier="test__int")],
                ),
                _node(
                    "Thing",
                    namespace="Internal",
                    relationships=[_rel(name="rel_oth", peer="TestingOther", identifier="int__other")],
                ),
                _node("Other", namespace="Testing"),
            ]
        )
        planner = make_planner(schema_branch=schema)
        plan = planner.plan(
            source_kind="TestingItem",
            terminal_predicate=TerminalByKinds(kinds=frozenset({"TestingOther"})),
            max_depth=5,
            user_filters=UserFilters.from_graphql_input(None),
        )
        assert plan.routes == ()
        # The only Item→Other route under the default revisit-free policy
        # passes through InternalThing, which is in the default excluded set.
        assert plan.pruned_for_user_filters == (
            _route_from_hops(
                _bidir_hop("TestingItem", "InternalThing", "test__int"),
                _bidir_hop("InternalThing", "TestingOther", "int__other"),
            ),
        )

    def test_excluded_kinds_drops_routes_containing_that_kind(self, linear_a_b_c_schema: SchemaBranch) -> None:
        """With ``excluded_kinds={"TestingKindB"}`` and the default revisit-free
        policy, the only A→C route (which passes through KindB) is pruned."""
        planner = make_planner(schema_branch=linear_a_b_c_schema)
        plan = planner.plan(
            source_kind="TestingKindA",
            terminal_predicate=TerminalByKinds(kinds=frozenset({"TestingKindC"})),
            max_depth=5,
            user_filters=UserFilters(excluded_kinds=frozenset({"TestingKindB"})),
        )
        assert plan.routes == ()
        assert plan.pruned_for_user_filters == (
            _route_from_hops(
                _bidir_hop("TestingKindA", "TestingKindB", "a__b"),
                _bidir_hop("TestingKindB", "TestingKindC", "b__c"),
            ),
        )

    def test_relationship_filter_requires_every_hop_match(self, linear_a_b_c_schema: SchemaBranch) -> None:
        planner = make_planner(schema_branch=linear_a_b_c_schema)
        plan = planner.plan(
            source_kind="TestingKindA",
            terminal_predicate=TerminalByKinds(kinds=frozenset({"TestingKindC"})),
            max_depth=5,
            user_filters=UserFilters(relationship_filter=frozenset({"a__b"})),  # excludes b__c
        )
        # Every A→C route requires at least one b__c hop, which violates the filter.
        assert plan.routes == ()
        for pruned in plan.pruned_for_user_filters:
            assert any(hop.relationship_identifier == "b__c" for hop in pruned.hops)


class TestDeterminism:
    def test_two_invocations_produce_identical_plans(self, linear_a_b_c_schema: SchemaBranch) -> None:
        planner = make_planner(schema_branch=linear_a_b_c_schema)
        kwargs = {
            "source_kind": "TestingKindA",
            "terminal_predicate": TerminalByKinds(kinds=frozenset({"TestingKindC"})),
            "max_depth": 5,
            "user_filters": _default_filters(),
        }
        plan_a = planner.plan(**kwargs)
        plan_b = planner.plan(**kwargs)
        assert plan_a == plan_b
        assert plan_a.routes == plan_b.routes


class TestTerminalById:
    def test_terminal_by_id_matches_only_specified_kind(self) -> None:
        schema = build_schema_branch(
            nodes=[
                _node(
                    "Start",
                    relationships=[
                        _rel(name="rel_a", peer="TestingEndA", identifier="start__a"),
                        _rel(name="rel_b", peer="TestingEndB", identifier="start__b"),
                    ],
                ),
                _node("EndA"),
                _node("EndB"),
            ]
        )
        planner = make_planner(schema_branch=schema)
        plan = planner.plan(
            source_kind="TestingStart",
            terminal_predicate=TerminalById(node_id="uuid-1", kind="TestingEndA"),
            max_depth=1,
            user_filters=_default_filters(),
        )
        assert plan.routes == (_route_from_hops(_bidir_hop("TestingStart", "TestingEndA", "start__a")),)


class TestKindFilter:
    def test_kind_filter_exempts_source_and_terminal(self) -> None:
        schema = build_schema_branch(
            nodes=[
                _node("Start", relationships=[_rel(name="rel_m", peer="TestingMid", identifier="s__m")]),
                _node("Mid", relationships=[_rel(name="rel_e", peer="TestingEnd", identifier="m__e")]),
                _node("End"),
            ]
        )
        planner = make_planner(schema_branch=schema)
        plan = planner.plan(
            source_kind="TestingStart",
            terminal_predicate=TerminalByKinds(kinds=frozenset({"TestingEnd"})),
            max_depth=2,
            user_filters=UserFilters(kind_filter=frozenset({"TestingMid"})),
        )
        # Start (source) and End (terminal) are exempt from kind_filter; the
        # intermediate Mid is in the filter, so the direct route survives.
        assert (
            _route_from_hops(
                _bidir_hop("TestingStart", "TestingMid", "s__m"),
                _bidir_hop("TestingMid", "TestingEnd", "m__e"),
            )
            in plan.routes
        )
