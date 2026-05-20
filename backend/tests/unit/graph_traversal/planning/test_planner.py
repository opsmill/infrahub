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


def _adj(*triples: tuple[str, str, str]) -> dict[str, dict[str, frozenset[str]]]:
    """Build an adjacency map from ``(start, rel, end)`` triples."""
    accumulator: dict[str, dict[str, set[str]]] = {}
    for start, identifier, end in triples:
        accumulator.setdefault(start, {}).setdefault(identifier, set()).add(end)
    return {start: {rel: frozenset(ends) for rel, ends in rels.items()} for start, rels in accumulator.items()}


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
        assert plan.adjacency == {}
        assert plan.is_empty is True


class TestAdjacencyEnumeration:
    def test_finds_single_hop_adjacency(self, linear_a_b_c_schema: SchemaBranch) -> None:
        planner = make_planner(schema_branch=linear_a_b_c_schema)
        plan = planner.plan(
            source_kind="TestingKindA",
            terminal_predicate=TerminalByKinds(kinds=frozenset({"TestingKindB"})),
            max_depth=1,
            user_filters=_default_filters(),
        )
        assert plan.adjacency == _adj(("TestingKindA", "a__b", "TestingKindB"))

    def test_finds_multi_hop_adjacency_through_intermediate(self, linear_a_b_c_schema: SchemaBranch) -> None:
        """Over a BIDIR chain A↔B↔C with ``max_depth=5`` and terminal=C, the
        adjacency includes every (start, rel, end) hop that lies on some path
        from A to C of length ≤ 5.

        Forward BFS records all reachable hops; the back-pass keeps only
        those reaching a terminal. The legal cycles from A to C are A→B→C,
        A→B→A→B→C, A→B→C→B→C — so all four undirected hops appear: A↔B and
        B↔C, in both directions.
        """
        planner = make_planner(schema_branch=linear_a_b_c_schema)
        plan = planner.plan(
            source_kind="TestingKindA",
            terminal_predicate=TerminalByKinds(kinds=frozenset({"TestingKindC"})),
            max_depth=5,
            user_filters=_default_filters(),
        )
        assert plan.adjacency == _adj(
            ("TestingKindA", "a__b", "TestingKindB"),
            ("TestingKindB", "a__b", "TestingKindA"),
            ("TestingKindB", "b__c", "TestingKindC"),
            ("TestingKindC", "b__c", "TestingKindB"),
        )

    def test_max_depth_caps_adjacency(self) -> None:
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
        assert plan_shallow.adjacency == {}

        plan_deep = planner.plan(
            source_kind="TestingAaa",
            terminal_predicate=TerminalByKinds(kinds=frozenset({"TestingFff"})),
            max_depth=5,
            user_filters=_default_filters(),
        )
        # The shortest route is A→B→C→D→E→F (length 5); each forward hop appears once.
        assert plan_deep.adjacency == _adj(
            ("TestingAaa", "aaa__bbb", "TestingBbb"),
            ("TestingBbb", "bbb__ccc", "TestingCcc"),
            ("TestingCcc", "ccc__ddd", "TestingDdd"),
            ("TestingDdd", "ddd__eee", "TestingEee"),
            ("TestingEee", "eee__fff", "TestingFff"),
        )


class TestGenericExpansion:
    def test_generic_peer_expands_to_concrete_end_kinds(self) -> None:
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
        # The generic kind itself never appears as an end_kind. Both concrete
        # inheritors are reached via the same `device__interfaces` identifier.
        assert plan.adjacency == _adj(
            ("TestingDevice", "device__interfaces", "TestingEthernetInterface"),
            ("TestingDevice", "device__interfaces", "TestingVirtualInterface"),
        )


class TestUserFilters:
    def test_default_excluded_namespaces_prune_hops_through_excluded_kinds(self) -> None:
        """A hop through a kind in a default-excluded namespace (``Internal``) is
        dropped during BFS, so the adjacency never includes any path through it."""
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
        assert plan.adjacency == {}

    def test_excluded_kinds_drops_paths_containing_that_kind(self, linear_a_b_c_schema: SchemaBranch) -> None:
        """Every A→C path requires KindB as an intermediate, which is excluded."""
        planner = make_planner(schema_branch=linear_a_b_c_schema)
        plan = planner.plan(
            source_kind="TestingKindA",
            terminal_predicate=TerminalByKinds(kinds=frozenset({"TestingKindC"})),
            max_depth=5,
            user_filters=UserFilters(excluded_kinds=frozenset({"TestingKindB"})),
        )
        assert plan.adjacency == {}

    def test_relationship_filter_requires_every_hop_match(self, linear_a_b_c_schema: SchemaBranch) -> None:
        """Every A→C path requires the ``b__c`` identifier, which the filter excludes."""
        planner = make_planner(schema_branch=linear_a_b_c_schema)
        plan = planner.plan(
            source_kind="TestingKindA",
            terminal_predicate=TerminalByKinds(kinds=frozenset({"TestingKindC"})),
            max_depth=5,
            user_filters=UserFilters(relationship_filter=frozenset({"a__b"})),
        )
        assert plan.adjacency == {}


class TestDeterminism:
    def test_two_invocations_produce_identical_plans(self, linear_a_b_c_schema: SchemaBranch) -> None:
        planner = make_planner(schema_branch=linear_a_b_c_schema)
        plan_a = planner.plan(
            source_kind="TestingKindA",
            terminal_predicate=TerminalByKinds(kinds=frozenset({"TestingKindC"})),
            max_depth=5,
            user_filters=_default_filters(),
        )
        plan_b = planner.plan(
            source_kind="TestingKindA",
            terminal_predicate=TerminalByKinds(kinds=frozenset({"TestingKindC"})),
            max_depth=5,
            user_filters=_default_filters(),
        )
        assert plan_a == plan_b
        assert plan_a.adjacency == plan_b.adjacency


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
        # Only the EndA edge is kept; the EndB edge is on a non-terminal path.
        assert plan.adjacency == _adj(("TestingStart", "start__a", "TestingEndA"))


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
        # Start (source) and End (terminal) are exempt from kind_filter; Mid is
        # in the filter as an intermediate. The two-hop path survives.
        assert plan.adjacency == _adj(
            ("TestingStart", "s__m", "TestingMid"),
            ("TestingMid", "m__e", "TestingEnd"),
        )
