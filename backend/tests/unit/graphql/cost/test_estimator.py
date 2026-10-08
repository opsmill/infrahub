from __future__ import annotations

import itertools
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import pytest

from infrahub.core.constants import RelationshipCardinality, RelationshipDirection
from infrahub.core.constants.schema import PARENT_CHILD_IDENTIFIER
from infrahub.graphql.cost.estimator import estimate
from infrahub.graphql.cost.histogram import RelationshipSideAccumulator
from infrahub.graphql.cost.models import (
    CostFigures,
    CostTreeField,
    EstimateMode,
    EstimateReason,
    EstimateSource,
    FieldDescription,
    FieldEstimate,
    FirstStepCounts,
    FirstStepKindCount,
    FirstStepPeerCount,
    FirstStepTopLevelCount,
    KindStatistics,
    RelationshipRef,
    RelationshipSideStatistics,
    StatisticsPointer,
    StatisticsSnapshot,
    TopNode,
)
from infrahub.graphql.cost.queries import RelationshipSideDegreeQueryResult

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from infrahub.graphql.cost.models import QueryEstimate

PERSON = "TestPerson"
ELECTRIC = "TestElectricCar"
GAZ = "TestGazCar"
CAR_KINDS = (ELECTRIC, GAZ)
OWNERSHIP = "person__car"
PREVIOUS_OWNERSHIP = "person_previous__car"

CARS = RelationshipRef(identifier=OWNERSHIP, direction=RelationshipDirection.BIDIR, name="cars", hierarchical=False)
OWNER = RelationshipRef(identifier=OWNERSHIP, direction=RelationshipDirection.BIDIR, name="owner", hierarchical=False)
PREVIOUS_OWNER = RelationshipRef(
    identifier=PREVIOUS_OWNERSHIP, direction=RelationshipDirection.BIDIR, name="previous_owner", hierarchical=False
)
TAGS = RelationshipRef(identifier="car__tag", direction=RelationshipDirection.BIDIR, name="tags", hierarchical=False)

PERSON_FIELD = FieldDescription(kind=PERSON, relationship_identifier=None, cardinality=RelationshipCardinality.MANY)
CAR_FIELD = FieldDescription(kind="TestCar", relationship_identifier=None, cardinality=RelationshipCardinality.MANY)
CARS_FIELD = FieldDescription(
    kind="TestCar", relationship_identifier=OWNERSHIP, cardinality=RelationshipCardinality.MANY
)
OWNER_FIELD = FieldDescription(kind=PERSON, relationship_identifier=OWNERSHIP, cardinality=RelationshipCardinality.ONE)
PREVIOUS_OWNER_FIELD = FieldDescription(
    kind=PERSON, relationship_identifier=PREVIOUS_OWNERSHIP, cardinality=RelationshipCardinality.ONE
)

POINTER = StatisticsPointer(
    version=1,
    branch="main",
    computed_at=datetime(2026, 10, 8, 4, 12, tzinfo=UTC),
    schema_hash="5e1f0c2a9b7d",
    kinds=(PERSON, ELECTRIC, GAZ),
)


def _side(
    identifier: str, kind: str, peers: Mapping[str, Mapping[str, int]], active_count: int
) -> RelationshipSideStatistics:
    """Statistics of one side, from the peers of each node by concrete peer kind."""
    accumulator = RelationshipSideAccumulator(identifier=identifier, direction=RelationshipDirection.BIDIR, kind=kind)
    accumulator.add_chunk(
        rows=[
            RelationshipSideDegreeQueryResult(node_id=node_id, peer_kind=peer_kind, peers=count)
            for node_id, by_kind in peers.items()
            for peer_kind, count in by_kind.items()
        ]
    )
    return accumulator.build(active_count=active_count)


def _kind(
    kind: str, active_count: int, label_count: int, sides: Mapping[str, Mapping[str, Mapping[str, int]]]
) -> KindStatistics:
    return KindStatistics(
        kind=kind,
        label_count=label_count,
        active_count=active_count,
        relationships=tuple(
            _side(identifier=identifier, kind=kind, peers=peers, active_count=active_count)
            for identifier, peers in sides.items()
        ),
    )


def _snapshot(*kinds: KindStatistics) -> StatisticsSnapshot:
    return StatisticsSnapshot(pointer=POINTER, kinds={kind.kind: kind for kind in kinds})


# p1 owns two electric cars and one gaz car, p2 one gaz car, p3 and p4 none; p3 owned the gaz car g1 before.
EVEN_SNAPSHOT = _snapshot(
    _kind(
        kind=PERSON,
        active_count=4,
        label_count=4,
        sides={
            OWNERSHIP: {"p1": {ELECTRIC: 2, GAZ: 1}, "p2": {GAZ: 1}},
            PREVIOUS_OWNERSHIP: {"p3": {GAZ: 1}},
        },
    ),
    _kind(
        kind=ELECTRIC,
        active_count=2,
        label_count=2,
        sides={OWNERSHIP: {"e1": {PERSON: 1}, "e2": {PERSON: 1}}, PREVIOUS_OWNERSHIP: {}},
    ),
    _kind(
        kind=GAZ,
        active_count=2,
        label_count=2,
        sides={OWNERSHIP: {"g1": {PERSON: 1}, "g2": {PERSON: 1}}, PREVIOUS_OWNERSHIP: {"g1": {PERSON: 1}}},
    ),
)
EVEN_LABELS = {PERSON: 4, ELECTRIC: 2, GAZ: 2}

# p1 owns six electric cars, p2 two gaz cars, p3 none; p3 owned the gaz car g1 before.
UNEVEN_SNAPSHOT = _snapshot(
    _kind(
        kind=PERSON,
        active_count=3,
        label_count=3,
        sides={OWNERSHIP: {"p1": {ELECTRIC: 6}, "p2": {GAZ: 2}}, PREVIOUS_OWNERSHIP: {"p3": {GAZ: 1}}},
    ),
    _kind(
        kind=ELECTRIC,
        active_count=6,
        label_count=6,
        sides={OWNERSHIP: {f"e{index}": {PERSON: 1} for index in range(1, 7)}, PREVIOUS_OWNERSHIP: {}},
    ),
    _kind(
        kind=GAZ,
        active_count=2,
        label_count=2,
        sides={OWNERSHIP: {"g1": {PERSON: 1}, "g2": {PERSON: 1}}, PREVIOUS_OWNERSHIP: {"g1": {PERSON: 1}}},
    ),
)
UNEVEN_LABELS = {PERSON: 3, ELECTRIC: 6, GAZ: 2}
UNEVEN_FIRST_STEP_PERSONS = FirstStepTopLevelCount(
    kinds=(FirstStepKindCount(kind=PERSON, node_count=2, node_ids=("p1", "p2")),), exceeds_size_limit=False
)
UNEVEN_FIRST_STEP_CARS = (
    FirstStepPeerCount(peer_kind=ELECTRIC, paths=6, distinct_peers=6, max_parents=1),
    FirstStepPeerCount(peer_kind=GAZ, paths=2, distinct_peers=2, max_parents=1),
)

# No histogram is stored: only the node with the most peers of each side is known.
NO_HISTOGRAM_SNAPSHOT = _snapshot(
    KindStatistics(
        kind=PERSON,
        label_count=3,
        active_count=3,
        relationships=(
            RelationshipSideStatistics(
                identifier=OWNERSHIP,
                direction=RelationshipDirection.BIDIR,
                nodes_with_peers=2,
                total_peers=4,
                peers_by_kind={GAZ: 4},
                histogram=(),
                top_nodes=(TopNode(node_id="p1", peers=3),),
            ),
        ),
    ),
    KindStatistics(
        kind=GAZ,
        label_count=4,
        active_count=4,
        relationships=(
            RelationshipSideStatistics(
                identifier=OWNERSHIP,
                direction=RelationshipDirection.BIDIR,
                nodes_with_peers=4,
                total_peers=4,
                peers_by_kind={PERSON: 4},
                histogram=(),
                top_nodes=(TopNode(node_id="g1", peers=1),),
            ),
        ),
    ),
)

# Twenty persons own three gaz cars and ten own two, so the persons left out of the list count as owning three;
# every gaz car has ten tags.
SPREAD_SNAPSHOT = _snapshot(
    _kind(
        kind=PERSON,
        active_count=30,
        label_count=30,
        sides={
            OWNERSHIP: {f"p{index}": {GAZ: 3 if index <= 20 else 2} for index in range(1, 31)},
        },
    ),
    _kind(
        kind=GAZ,
        active_count=80,
        label_count=80,
        sides={
            OWNERSHIP: {f"g{index}": {PERSON: 1} for index in range(1, 81)},
            "car__tag": {f"g{index}": {"BuiltinTag": 10} for index in range(1, 81)},
        },
    ),
)

SCALED_SNAPSHOT = _snapshot(
    _kind(kind=PERSON, active_count=2, label_count=5, sides={}),
    _kind(kind=ELECTRIC, active_count=2, label_count=4, sides={}),
    _kind(kind=GAZ, active_count=2, label_count=2, sides={}),
)

SITE_SNAPSHOT = _snapshot(_kind(kind="TestingSite", active_count=2, label_count=2, sides={}))


def _top_level(path: str, kind: str, **fields: Any) -> CostTreeField:
    """A top-level field that selects its nodes and nothing else, with the given fields changed."""
    return replace(
        CostTreeField(
            path=path,
            kind=kind,
            concrete_kinds=(kind,),
            parent_kinds=(),
            relationship=None,
            cardinality=RelationshipCardinality.MANY,
            selected_attribute_count=0,
            selected_cardinality_one_count=0,
            selects_count=False,
            selects_nodes=True,
            id_only=False,
            max_matching_nodes=None,
            arguments={},
            children=(),
        ),
        **fields,
    )


def _relationship(
    path: str,
    kind: str,
    relationship: RelationshipRef,
    cardinality: RelationshipCardinality,
    **fields: Any,
) -> CostTreeField:
    """A relationship field that selects its nodes and nothing else, with the given fields changed."""
    return replace(
        CostTreeField(
            path=path,
            kind=kind,
            concrete_kinds=(kind,),
            parent_kinds=(),
            relationship=relationship,
            cardinality=cardinality,
            selected_attribute_count=0,
            selected_cardinality_one_count=0,
            selects_count=False,
            selects_nodes=True,
            id_only=False,
            max_matching_nodes=None,
            arguments={},
            children=(),
        ),
        **fields,
    )


def _cars(path: str = "TestPerson/cars", **fields: Any) -> CostTreeField:
    """The cars of the persons, with the given fields changed."""
    fields = {"concrete_kinds": CAR_KINDS, "parent_kinds": (PERSON,), **fields}
    return _relationship(
        path=path, kind="TestCar", relationship=CARS, cardinality=RelationshipCardinality.MANY, **fields
    )


def _owner(path: str = "TestPerson/cars/owner", relationship: RelationshipRef = OWNER, **fields: Any) -> CostTreeField:
    """The owner, or the previous owner, of the cars, with the given fields changed."""
    fields = {"parent_kinds": CAR_KINDS, **fields}
    return _relationship(
        path=path, kind=PERSON, relationship=relationship, cardinality=RelationshipCardinality.ONE, **fields
    )


def _figures(nodes: int, calls: int, rows: int) -> CostFigures:
    return CostFigures(nodes=nodes, resolver_calls=calls, database_rows=rows)


def _estimated(
    description: FieldDescription,
    expected: CostFigures,
    worst_case: CostFigures,
    source: EstimateSource = EstimateSource.STATISTICS,
    bound: bool = True,
) -> FieldEstimate:
    return FieldEstimate(
        field=description,
        expected=expected,
        worst_case=worst_case,
        source=source,
        worst_case_is_bound=bound,
        reason=None,
    )


def _without_statistics(description: FieldDescription) -> FieldEstimate:
    return FieldEstimate(
        field=description,
        expected=None,
        worst_case=None,
        source=None,
        worst_case_is_bound=False,
        reason=EstimateReason.NO_STATISTICS,
    )


@dataclass
class EstimateCase:
    name: str
    tree: list[CostTreeField]
    snapshot: StatisticsSnapshot | None
    label_counts: dict[str, int]
    expected: dict[str, FieldEstimate]
    first_step: FirstStepCounts | None = None
    reads_main_now: bool = True
    expected_mode: EstimateMode = EstimateMode.STATISTICS_ONLY


ESTIMATE_CASES: list[EstimateCase] = [
    EstimateCase(
        # Two of the four persons are read; each brings one car on average, and one gaz car in two has a
        # previous owner.
        name="expected_nodes_are_parent_paths_times_the_mean_and_cardinality_one_uses_the_share_with_a_peer",
        tree=[
            _top_level(
                path="TestPerson",
                kind=PERSON,
                selected_attribute_count=1,
                arguments={"limit": 2},
                children=(
                    _cars(
                        selected_cardinality_one_count=2,
                        children=(
                            _owner(selected_attribute_count=1),
                            _owner(
                                path="TestPerson/cars/previous_owner",
                                relationship=PREVIOUS_OWNER,
                                selected_attribute_count=1,
                            ),
                        ),
                    ),
                ),
            )
        ],
        snapshot=EVEN_SNAPSHOT,
        label_counts=EVEN_LABELS,
        expected={
            "TestPerson": _estimated(PERSON_FIELD, expected=_figures(2, 1, 6), worst_case=_figures(2, 1, 6)),
            "TestPerson/cars": _estimated(CARS_FIELD, expected=_figures(2, 2, 8), worst_case=_figures(4, 2, 16)),
            "TestPerson/cars/owner": _estimated(OWNER_FIELD, expected=_figures(2, 2, 4), worst_case=_figures(4, 4, 8)),
            "TestPerson/cars/previous_owner": _estimated(
                PREVIOUS_OWNER_FIELD, expected=_figures(1, 2, 1), worst_case=_figures(1, 4, 2)
            ),
        },
    ),
    EstimateCase(
        # Six of the eight cars are electric, so the owner field is resolved six times for electric cars, and the
        # previous owner, selected on gaz cars only, twice.
        name="paths_are_split_by_peer_kind_and_narrowed_to_the_parent_kinds_of_the_field",
        tree=[
            _top_level(
                path="TestPerson",
                kind=PERSON,
                children=(
                    _cars(
                        selected_cardinality_one_count=2,
                        children=(
                            _owner(selected_attribute_count=1),
                            _owner(
                                path="TestPerson/cars/previous_owner",
                                relationship=PREVIOUS_OWNER,
                                parent_kinds=(GAZ,),
                                id_only=True,
                            ),
                        ),
                    ),
                ),
            )
        ],
        snapshot=UNEVEN_SNAPSHOT,
        label_counts=UNEVEN_LABELS,
        expected={
            "TestPerson": _estimated(PERSON_FIELD, expected=_figures(3, 1, 6), worst_case=_figures(3, 1, 6)),
            "TestPerson/cars": _estimated(CARS_FIELD, expected=_figures(8, 3, 32), worst_case=_figures(8, 3, 32)),
            "TestPerson/cars/owner": _estimated(
                OWNER_FIELD, expected=_figures(8, 8, 16), worst_case=_figures(8, 8, 16)
            ),
            "TestPerson/cars/previous_owner": _estimated(
                PREVIOUS_OWNER_FIELD, expected=_figures(1, 2, 0), worst_case=_figures(1, 2, 0)
            ),
        },
    ),
    EstimateCase(
        name="the_counted_first_step_gives_the_paths_of_each_peer_kind",
        tree=[
            _top_level(
                path="TestPerson",
                kind=PERSON,
                children=(
                    _cars(
                        selected_cardinality_one_count=2,
                        children=(
                            _owner(selected_attribute_count=1),
                            _owner(
                                path="TestPerson/cars/previous_owner",
                                relationship=PREVIOUS_OWNER,
                                parent_kinds=(GAZ,),
                                id_only=True,
                            ),
                        ),
                    ),
                ),
            )
        ],
        snapshot=UNEVEN_SNAPSHOT,
        label_counts=UNEVEN_LABELS,
        first_step=FirstStepCounts(
            top_level={"TestPerson": UNEVEN_FIRST_STEP_PERSONS},
            relationships={"TestPerson/cars": UNEVEN_FIRST_STEP_CARS},
            label_counts=UNEVEN_LABELS,
        ),
        expected_mode=EstimateMode.COUNTED_FIRST_STEP,
        expected={
            "TestPerson": _estimated(
                PERSON_FIELD, expected=_figures(2, 1, 4), worst_case=_figures(2, 1, 4), source=EstimateSource.COUNTED
            ),
            "TestPerson/cars": _estimated(
                CARS_FIELD, expected=_figures(8, 2, 32), worst_case=_figures(8, 2, 32), source=EstimateSource.COUNTED
            ),
            "TestPerson/cars/owner": _estimated(
                OWNER_FIELD, expected=_figures(8, 8, 16), worst_case=_figures(8, 8, 16)
            ),
            "TestPerson/cars/previous_owner": _estimated(
                PREVIOUS_OWNER_FIELD, expected=_figures(1, 2, 0), worst_case=_figures(1, 2, 0)
            ),
        },
    ),
    EstimateCase(
        name="a_nested_limit_caps_the_peers_of_each_parent",
        tree=[
            _top_level(
                path="TestPerson",
                kind=PERSON,
                children=(
                    _cars(
                        selected_cardinality_one_count=1,
                        arguments={"limit": 1},
                        children=(_owner(selected_attribute_count=1),),
                    ),
                ),
            )
        ],
        snapshot=UNEVEN_SNAPSHOT,
        label_counts=UNEVEN_LABELS,
        expected={
            "TestPerson": _estimated(PERSON_FIELD, expected=_figures(3, 1, 6), worst_case=_figures(3, 1, 6)),
            "TestPerson/cars": _estimated(CARS_FIELD, expected=_figures(2, 3, 6), worst_case=_figures(2, 3, 6)),
            "TestPerson/cars/owner": _estimated(OWNER_FIELD, expected=_figures(2, 2, 4), worst_case=_figures(4, 4, 8)),
        },
    ),
    EstimateCase(
        name="a_nested_limit_caps_the_counted_peers_of_each_parent",
        tree=[
            _top_level(
                path="TestPerson",
                kind=PERSON,
                children=(
                    _cars(
                        selected_cardinality_one_count=1,
                        arguments={"limit": 2},
                        children=(_owner(selected_attribute_count=1),),
                    ),
                ),
            )
        ],
        snapshot=UNEVEN_SNAPSHOT,
        label_counts=UNEVEN_LABELS,
        first_step=FirstStepCounts(
            top_level={"TestPerson": UNEVEN_FIRST_STEP_PERSONS},
            relationships={"TestPerson/cars": UNEVEN_FIRST_STEP_CARS},
            label_counts=UNEVEN_LABELS,
        ),
        expected_mode=EstimateMode.COUNTED_FIRST_STEP,
        expected={
            "TestPerson": _estimated(
                PERSON_FIELD, expected=_figures(2, 1, 4), worst_case=_figures(2, 1, 4), source=EstimateSource.COUNTED
            ),
            "TestPerson/cars": _estimated(
                CARS_FIELD, expected=_figures(4, 2, 12), worst_case=_figures(4, 2, 12), source=EstimateSource.COUNTED
            ),
            "TestPerson/cars/owner": _estimated(OWNER_FIELD, expected=_figures(4, 4, 8), worst_case=_figures(6, 6, 12)),
        },
    ),
    EstimateCase(
        # 3 persons, at most 3 cars each, at most 1 owner each: 3 x 3 x 1 paths at most.
        name="without_a_histogram_the_worst_case_is_the_product_of_the_largest_peer_counts",
        tree=[
            _top_level(
                path="TestPerson",
                kind=PERSON,
                children=(_cars(selected_cardinality_one_count=1, children=(_owner(),)),),
            )
        ],
        snapshot=NO_HISTOGRAM_SNAPSHOT,
        label_counts={PERSON: 3, GAZ: 4},
        expected={
            "TestPerson": _estimated(PERSON_FIELD, expected=_figures(3, 1, 6), worst_case=_figures(3, 1, 6)),
            "TestPerson/cars": _estimated(CARS_FIELD, expected=_figures(4, 3, 12), worst_case=_figures(9, 3, 27)),
            "TestPerson/cars/owner": _estimated(OWNER_FIELD, expected=_figures(4, 4, 4), worst_case=_figures(9, 9, 9)),
        },
    ),
    EstimateCase(
        # Persons: 2 active x 11 labels now / 5 labels at refresh = 4.4; cars: 2 x 6 / 4 + 2 x 3 / 2 = 6.
        name="label_counts_scale_the_stored_node_counts",
        tree=[
            _top_level(path="TestPerson", kind=PERSON),
            _top_level(path="TestCar", kind="TestCar", concrete_kinds=CAR_KINDS),
        ],
        snapshot=SCALED_SNAPSHOT,
        label_counts={PERSON: 11, ELECTRIC: 6, GAZ: 3},
        expected={
            "TestPerson": _estimated(PERSON_FIELD, expected=_figures(4, 1, 9), worst_case=_figures(5, 1, 10)),
            "TestCar": _estimated(CAR_FIELD, expected=_figures(6, 1, 12), worst_case=_figures(6, 1, 12)),
        },
    ),
    EstimateCase(
        # p1 is listed with its six cars.
        name="a_listed_top_level_node_uses_its_stored_peer_count",
        tree=[
            _top_level(
                path="TestPerson",
                kind=PERSON,
                max_matching_nodes=1,
                arguments={"ids": ["p1"]},
                children=(_cars(selected_cardinality_one_count=1, children=(_owner(selected_attribute_count=1),)),),
            )
        ],
        snapshot=UNEVEN_SNAPSHOT,
        label_counts=UNEVEN_LABELS,
        expected={
            "TestPerson": _estimated(PERSON_FIELD, expected=_figures(1, 1, 2), worst_case=_figures(1, 1, 2)),
            "TestPerson/cars": _estimated(CARS_FIELD, expected=_figures(6, 1, 18), worst_case=_figures(6, 1, 18)),
            "TestPerson/cars/owner": _estimated(
                OWNER_FIELD, expected=_figures(6, 6, 12), worst_case=_figures(8, 8, 16)
            ),
        },
    ),
    EstimateCase(
        # p1 is listed with its six cars; p3, not listed, is estimated from p2 and p3, which own two cars together.
        name="a_listed_node_uses_its_stored_peer_count_and_the_other_ids_the_other_nodes",
        tree=[
            _top_level(
                path="TestPerson",
                kind=PERSON,
                max_matching_nodes=2,
                arguments={"ids": ["p1", "p3"]},
                children=(_cars(selected_cardinality_one_count=1, children=(_owner(selected_attribute_count=1),)),),
            )
        ],
        snapshot=UNEVEN_SNAPSHOT,
        label_counts=UNEVEN_LABELS,
        expected={
            "TestPerson": _estimated(PERSON_FIELD, expected=_figures(2, 1, 4), worst_case=_figures(2, 1, 4)),
            "TestPerson/cars": _estimated(CARS_FIELD, expected=_figures(7, 2, 21), worst_case=_figures(8, 2, 24)),
            "TestPerson/cars/owner": _estimated(
                OWNER_FIELD, expected=_figures(7, 7, 14), worst_case=_figures(8, 8, 16)
            ),
        },
    ),
    EstimateCase(
        name="a_top_level_node_that_is_not_listed_uses_the_statistics",
        tree=[
            _top_level(
                path="TestPerson",
                kind=PERSON,
                max_matching_nodes=1,
                arguments={"ids": ["p9"]},
                children=(_cars(selected_cardinality_one_count=1, children=(_owner(selected_attribute_count=1),)),),
            )
        ],
        snapshot=UNEVEN_SNAPSHOT,
        label_counts=UNEVEN_LABELS,
        expected={
            "TestPerson": _estimated(PERSON_FIELD, expected=_figures(1, 1, 2), worst_case=_figures(1, 1, 2)),
            "TestPerson/cars": _estimated(CARS_FIELD, expected=_figures(3, 1, 8), worst_case=_figures(6, 1, 18)),
            "TestPerson/cars/owner": _estimated(OWNER_FIELD, expected=_figures(3, 3, 5), worst_case=_figures(8, 8, 16)),
        },
    ),
    EstimateCase(
        # The 29 IDs that are not listed are estimated at 77.3 cars from the 29 other persons, and p1 has 3, so
        # 80.3 cars are expected where only 80 exist; their tags are then capped at 80 x 10.
        name="an_expected_share_above_its_bound_is_capped_by_the_bound",
        tree=[
            _top_level(
                path="TestPerson",
                kind=PERSON,
                max_matching_nodes=30,
                arguments={"ids": ["p1"] + [f"x{index}" for index in range(1, 30)]},
                children=(
                    _cars(
                        children=(
                            _relationship(
                                path="TestPerson/cars/tags",
                                kind="BuiltinTag",
                                relationship=TAGS,
                                cardinality=RelationshipCardinality.MANY,
                                parent_kinds=(GAZ,),
                            ),
                        ),
                    ),
                ),
            )
        ],
        snapshot=SPREAD_SNAPSHOT,
        label_counts={PERSON: 30, GAZ: 80},
        expected={
            "TestPerson": _estimated(PERSON_FIELD, expected=_figures(30, 1, 60), worst_case=_figures(30, 1, 60)),
            "TestPerson/cars": _estimated(CARS_FIELD, expected=_figures(80, 30, 161), worst_case=_figures(90, 30, 180)),
            "TestPerson/cars/tags": _estimated(
                FieldDescription(
                    kind="BuiltinTag", relationship_identifier="car__tag", cardinality=RelationshipCardinality.MANY
                ),
                expected=_figures(800, 80, 1600),
                worst_case=_figures(800, 80, 1600),
            ),
        },
    ),
    EstimateCase(
        name="count_adds_one_row_for_each_parent_node",
        tree=[
            _top_level(
                path="TestPerson",
                kind=PERSON,
                selects_count=True,
                children=(
                    _cars(selects_count=True),
                    _cars(path="TestPerson/total_cars", selects_count=True, selects_nodes=False),
                ),
            )
        ],
        snapshot=EVEN_SNAPSHOT,
        label_counts=EVEN_LABELS,
        expected={
            "TestPerson": _estimated(PERSON_FIELD, expected=_figures(4, 1, 9), worst_case=_figures(4, 1, 9)),
            "TestPerson/cars": _estimated(CARS_FIELD, expected=_figures(4, 4, 12), worst_case=_figures(4, 4, 12)),
            "TestPerson/total_cars": _estimated(CARS_FIELD, expected=_figures(0, 4, 4), worst_case=_figures(0, 4, 4)),
        },
    ),
    EstimateCase(
        # Rows for each node: the list or peer query, the node itself, each attribute, each cardinality-one peer;
        # a cardinality-one field reads its peer ID with its parent, and reads nothing when it selects only the ID.
        name="rows_follow_each_resolver_path",
        tree=[
            _top_level(
                path="TestPerson",
                kind=PERSON,
                selected_attribute_count=2,
                children=(
                    _relationship(
                        path="TestPerson/cars",
                        kind="TestCar",
                        relationship=CARS,
                        cardinality=RelationshipCardinality.MANY,
                        parent_kinds=(PERSON,),
                        concrete_kinds=CAR_KINDS,
                        selected_attribute_count=1,
                        selected_cardinality_one_count=2,
                        children=(
                            _owner(id_only=True),
                            _owner(
                                path="TestPerson/cars/previous_owner",
                                relationship=PREVIOUS_OWNER,
                                selected_attribute_count=1,
                            ),
                        ),
                    ),
                ),
            )
        ],
        snapshot=EVEN_SNAPSHOT,
        label_counts=EVEN_LABELS,
        expected={
            "TestPerson": _estimated(PERSON_FIELD, expected=_figures(4, 1, 16), worst_case=_figures(4, 1, 16)),
            "TestPerson/cars": _estimated(CARS_FIELD, expected=_figures(4, 4, 20), worst_case=_figures(4, 4, 20)),
            "TestPerson/cars/owner": _estimated(OWNER_FIELD, expected=_figures(4, 4, 0), worst_case=_figures(4, 4, 0)),
            "TestPerson/cars/previous_owner": _estimated(
                PREVIOUS_OWNER_FIELD, expected=_figures(1, 4, 2), worst_case=_figures(1, 4, 2)
            ),
        },
    ),
    EstimateCase(
        name="a_field_aliased_node_adds_its_figures_to_the_path_of_its_parent",
        tree=[_top_level(path="TestPerson", kind=PERSON, children=(_cars(path="TestPerson"),))],
        snapshot=EVEN_SNAPSHOT,
        label_counts=EVEN_LABELS,
        expected={
            "TestPerson": _estimated(PERSON_FIELD, expected=_figures(8, 5, 16), worst_case=_figures(8, 5, 16)),
        },
    ),
    EstimateCase(
        name="a_relationship_side_without_statistics_has_no_estimate_and_neither_do_the_fields_below_it",
        tree=[
            _top_level(
                path="TestPerson",
                kind=PERSON,
                children=(
                    _cars(
                        selected_cardinality_one_count=1,
                        children=(
                            _owner(
                                path="TestPerson/cars/new_owner",
                                relationship=RelationshipRef(
                                    identifier="person_new__car",
                                    direction=RelationshipDirection.BIDIR,
                                    name="new_owner",
                                    hierarchical=False,
                                ),
                                children=(_cars(path="TestPerson/cars/new_owner/cars"),),
                            ),
                        ),
                    ),
                ),
            )
        ],
        snapshot=EVEN_SNAPSHOT,
        label_counts=EVEN_LABELS,
        expected={
            "TestPerson": _estimated(PERSON_FIELD, expected=_figures(4, 1, 8), worst_case=_figures(4, 1, 8)),
            "TestPerson/cars": _estimated(CARS_FIELD, expected=_figures(4, 4, 12), worst_case=_figures(4, 4, 12)),
            "TestPerson/cars/new_owner": _without_statistics(
                FieldDescription(
                    kind=PERSON, relationship_identifier="person_new__car", cardinality=RelationshipCardinality.ONE
                )
            ),
            "TestPerson/cars/new_owner/cars": _without_statistics(CARS_FIELD),
        },
    ),
    EstimateCase(
        name="a_kind_without_statistics_has_no_estimate",
        tree=[
            _top_level(
                path="TestCar",
                kind="TestCar",
                concrete_kinds=CAR_KINDS,
                children=(_owner(path="TestCar/owner"),),
            )
        ],
        snapshot=_snapshot(*(kind for kind in EVEN_SNAPSHOT.kinds.values() if kind.kind != GAZ)),
        label_counts=EVEN_LABELS,
        expected={
            "TestCar": _without_statistics(CAR_FIELD),
            "TestCar/owner": _without_statistics(OWNER_FIELD),
        },
    ),
    EstimateCase(
        name="without_statistics_no_field_has_an_estimate",
        tree=[_top_level(path="TestPerson", kind=PERSON, children=(_cars(),))],
        snapshot=None,
        label_counts=EVEN_LABELS,
        expected={
            "TestPerson": _without_statistics(PERSON_FIELD),
            "TestPerson/cars": _without_statistics(CARS_FIELD),
        },
    ),
    EstimateCase(
        name="hierarchical_fields_have_no_statistics",
        tree=[
            _top_level(
                path="TestingSite",
                kind="TestingSite",
                children=(
                    _relationship(
                        path="TestingSite/ancestors",
                        kind="TestingLocation",
                        relationship=RelationshipRef(
                            identifier=PARENT_CHILD_IDENTIFIER,
                            direction=RelationshipDirection.OUTBOUND,
                            name="ancestors",
                            hierarchical=True,
                        ),
                        cardinality=RelationshipCardinality.MANY,
                        parent_kinds=("TestingSite",),
                        concrete_kinds=("TestingContinent", "TestingCountry", "TestingSite"),
                    ),
                ),
            )
        ],
        snapshot=SITE_SNAPSHOT,
        label_counts={"TestingSite": 2},
        expected={
            "TestingSite": _estimated(
                FieldDescription(
                    kind="TestingSite", relationship_identifier=None, cardinality=RelationshipCardinality.MANY
                ),
                expected=_figures(2, 1, 4),
                worst_case=_figures(2, 1, 4),
            ),
            "TestingSite/ancestors": _without_statistics(
                FieldDescription(
                    kind="TestingLocation",
                    relationship_identifier=PARENT_CHILD_IDENTIFIER,
                    cardinality=RelationshipCardinality.MANY,
                )
            ),
        },
    ),
    EstimateCase(
        name="the_worst_case_is_no_bound_on_another_branch_or_at_another_time",
        tree=[
            _top_level(
                path="TestPerson",
                kind=PERSON,
                children=(_cars(selected_cardinality_one_count=1, children=(_owner(),)),),
            )
        ],
        snapshot=UNEVEN_SNAPSHOT,
        label_counts=UNEVEN_LABELS,
        reads_main_now=False,
        expected={
            "TestPerson": _estimated(
                PERSON_FIELD, expected=_figures(3, 1, 6), worst_case=_figures(3, 1, 6), bound=False
            ),
            "TestPerson/cars": _estimated(
                CARS_FIELD, expected=_figures(8, 3, 24), worst_case=_figures(8, 3, 24), bound=False
            ),
            "TestPerson/cars/owner": _estimated(
                OWNER_FIELD, expected=_figures(8, 8, 8), worst_case=_figures(8, 8, 8), bound=False
            ),
        },
    ),
    EstimateCase(
        # Twice as many persons as at the refresh: the paths beyond what the stored nodes can take are given the
        # largest peer count.
        name="nodes_added_since_the_refresh_keep_the_worst_case_above_the_expected_figures",
        tree=[
            _top_level(
                path="TestPerson",
                kind=PERSON,
                children=(_cars(selected_cardinality_one_count=1, children=(_owner(),)),),
            )
        ],
        snapshot=UNEVEN_SNAPSHOT,
        label_counts={PERSON: 6, ELECTRIC: 6, GAZ: 2},
        expected={
            "TestPerson": _estimated(PERSON_FIELD, expected=_figures(6, 1, 12), worst_case=_figures(6, 1, 12)),
            "TestPerson/cars": _estimated(CARS_FIELD, expected=_figures(16, 6, 48), worst_case=_figures(26, 6, 78)),
            "TestPerson/cars/owner": _estimated(
                OWNER_FIELD, expected=_figures(16, 16, 16), worst_case=_figures(44, 44, 44)
            ),
        },
    ),
]


def _estimate_case(test_case: EstimateCase) -> QueryEstimate:
    return estimate(
        tree=test_case.tree,
        snapshot=test_case.snapshot,
        first_step=test_case.first_step,
        label_counts=test_case.label_counts,
        reads_main_now=test_case.reads_main_now,
    )


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in ESTIMATE_CASES])
def test_estimate(test_case: EstimateCase) -> None:
    result = _estimate_case(test_case=test_case)

    assert result.mode == test_case.expected_mode
    assert result.statistics == (test_case.snapshot.pointer if test_case.snapshot is not None else None)
    assert list(result.estimates.items()) == list(test_case.expected.items())


@pytest.mark.parametrize(
    "test_case",
    [
        pytest.param(tc, id=tc.name)
        for tc in ESTIMATE_CASES
        if any(field_estimate.reason is None for field_estimate in tc.expected.values())
    ],
)
def test_worst_case_is_at_least_the_expected_figure(test_case: EstimateCase) -> None:
    result = _estimate_case(test_case=test_case)

    estimated = [field_estimate for field_estimate in result.estimates.values() if field_estimate.reason is None]
    assert estimated
    for field_estimate in estimated:
        assert field_estimate.expected is not None
        assert field_estimate.worst_case is not None
        assert field_estimate.worst_case.nodes >= field_estimate.expected.nodes
        assert field_estimate.worst_case.resolver_calls >= field_estimate.expected.resolver_calls
        assert field_estimate.worst_case.database_rows >= field_estimate.expected.database_rows


@dataclass
class AssignmentCase:
    name: str
    peer_counts: list[int]
    """Peers of each gaz car through the tags relationship."""

    paths: int
    """Paths that reach the gaz cars."""

    paths_per_car: int
    """Largest number of those paths that reach one gaz car."""

    expected_worst_case: int
    limit: int | None = None


ASSIGNMENT_CASES: list[AssignmentCase] = [
    AssignmentCase(
        name="two_paths_on_each_car_with_most_tags",
        peer_counts=[5, 3, 3, 1, 0],
        paths=4,
        paths_per_car=2,
        expected_worst_case=16,
    ),
    AssignmentCase(
        name="last_path_on_the_smallest_car", peer_counts=[4, 4, 1], paths=7, paths_per_car=3, expected_worst_case=25
    ),
    AssignmentCase(name="one_path_per_car", peer_counts=[2, 2, 2, 2], paths=3, paths_per_car=1, expected_worst_case=6),
    AssignmentCase(
        name="every_path_on_one_car", peer_counts=[6, 1, 1, 1], paths=5, paths_per_car=5, expected_worst_case=30
    ),
    AssignmentCase(
        name="limit_on_each_car", peer_counts=[5, 3, 1], paths=3, paths_per_car=1, expected_worst_case=5, limit=2
    ),
]


def _brute_force_worst_case(peer_counts: Sequence[int], paths: int, paths_per_car: int, limit: int | None) -> int:
    """Largest number of tags over every way to send the paths to the cars."""
    returned = [count if limit is None else min(count, limit) for count in peer_counts]
    return max(
        sum(car_paths * tags for car_paths, tags in zip(assignment, returned, strict=True))
        for assignment in itertools.product(range(paths_per_car + 1), repeat=len(peer_counts))
        if sum(assignment) <= paths
    )


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in ASSIGNMENT_CASES])
def test_worst_case_equals_the_largest_value_over_every_assignment_of_paths(test_case: AssignmentCase) -> None:
    cars = {f"g{index}": count for index, count in enumerate(test_case.peer_counts)}
    snapshot = _snapshot(
        _kind(kind=PERSON, active_count=test_case.paths, label_count=test_case.paths, sides={OWNERSHIP: {}}),
        _kind(
            kind=GAZ,
            active_count=len(cars),
            label_count=len(cars),
            sides={"car__tag": {car: {"BuiltinTag": count} for car, count in cars.items() if count}},
        ),
    )
    tree = [
        _top_level(
            path="TestPerson",
            kind=PERSON,
            children=(
                _cars(
                    children=(
                        _relationship(
                            path="TestPerson/cars/tags",
                            kind="BuiltinTag",
                            relationship=TAGS,
                            cardinality=RelationshipCardinality.MANY,
                            parent_kinds=(GAZ,),
                            arguments={"limit": test_case.limit} if test_case.limit is not None else {},
                        ),
                    ),
                ),
            ),
        )
    ]
    first_step = FirstStepCounts(
        top_level={
            "TestPerson": FirstStepTopLevelCount(
                kinds=(FirstStepKindCount(kind=PERSON, node_count=test_case.paths, node_ids=()),),
                exceeds_size_limit=False,
            )
        },
        relationships={
            "TestPerson/cars": (
                FirstStepPeerCount(
                    peer_kind=GAZ,
                    paths=test_case.paths,
                    distinct_peers=min(len(cars), test_case.paths),
                    max_parents=test_case.paths_per_car,
                ),
            )
        },
        label_counts={PERSON: test_case.paths, GAZ: len(cars)},
    )

    result = estimate(
        tree=tree, snapshot=snapshot, first_step=first_step, label_counts=first_step.label_counts, reads_main_now=True
    )

    tags = result.estimates["TestPerson/cars/tags"].worst_case
    assert tags is not None
    assert tags.nodes == test_case.expected_worst_case
    assert tags.nodes == _brute_force_worst_case(
        peer_counts=test_case.peer_counts,
        paths=test_case.paths,
        paths_per_car=test_case.paths_per_car,
        limit=test_case.limit,
    )


MANY_TO_ONE_AND_BACK_PATHS = (
    "TestPerson",
    "TestPerson/cars",
    "TestPerson/cars/owner",
    "TestPerson/cars/owner/cars",
)


def _many_to_one_and_back_tree() -> list[CostTreeField]:
    return [
        _top_level(
            path="TestPerson",
            kind=PERSON,
            children=(
                _cars(
                    selected_cardinality_one_count=1,
                    children=(_owner(children=(_cars(path="TestPerson/cars/owner/cars"),)),),
                ),
            ),
        )
    ]


@dataclass(frozen=True)
class OwnershipGraph:
    persons: tuple[str, ...]
    owners: Mapping[str, str]
    """Owner of each car, by car ID."""

    def car_kind(self, car: str) -> str:
        return ELECTRIC if car.startswith("e") else GAZ

    def cars_of(self, person: str) -> list[str]:
        return [car for car, owner in self.owners.items() if owner == person]

    def snapshot(self) -> StatisticsSnapshot:
        person_cars: dict[str, dict[str, int]] = {}
        for car, owner in self.owners.items():
            by_kind = person_cars.setdefault(owner, {})
            by_kind[self.car_kind(car)] = by_kind.get(self.car_kind(car), 0) + 1
        cars_by_kind = {kind: [car for car in self.owners if self.car_kind(car) == kind] for kind in CAR_KINDS}
        return _snapshot(
            _kind(
                kind=PERSON,
                active_count=len(self.persons),
                label_count=len(self.persons),
                sides={OWNERSHIP: person_cars},
            ),
            *(
                _kind(
                    kind=kind,
                    active_count=len(cars),
                    label_count=len(cars),
                    sides={OWNERSHIP: {car: {PERSON: 1} for car in cars}},
                )
                for kind, cars in cars_by_kind.items()
            ),
        )

    def actual_nodes(self) -> dict[str, int]:
        """Walk every path of the query from many persons to their cars, to one owner, and back to its cars."""
        nodes = dict.fromkeys(MANY_TO_ONE_AND_BACK_PATHS, 0)
        for person in self.persons:
            nodes["TestPerson"] += 1
            for car in self.cars_of(person):
                nodes["TestPerson/cars"] += 1
                owner = self.owners[car]
                nodes["TestPerson/cars/owner"] += 1
                nodes["TestPerson/cars/owner/cars"] += len(self.cars_of(owner))
        return nodes


def _worst_case_nodes(snapshot: StatisticsSnapshot) -> dict[str, int]:
    result = estimate(
        tree=_many_to_one_and_back_tree(),
        snapshot=snapshot,
        first_step=None,
        label_counts={kind.kind: kind.label_count for kind in snapshot.kinds.values()},
        reads_main_now=True,
    )
    worst_cases: dict[str, int] = {}
    for path, field_estimate in result.estimates.items():
        assert field_estimate.worst_case is not None
        worst_cases[path] = field_estimate.worst_case.nodes
    return worst_cases


def test_worst_case_of_a_query_from_many_nodes_to_one_and_back_equals_the_brute_force_maximum() -> None:
    """Every way to give four cars to three persons, grouped by the statistics it produces.

    The statistics keep how many cars each person owns, not which ones, so the 81 ways give 15 groups.
    """
    persons = ("p1", "p2", "p3")
    cars = ("e1", "e2", "g1", "g2")
    largest_by_statistics: dict[str, dict[str, int]] = {}
    snapshots: dict[str, StatisticsSnapshot] = {}
    for owners in itertools.product(persons, repeat=len(cars)):
        graph = OwnershipGraph(persons=persons, owners=dict(zip(cars, owners, strict=True)))
        snapshot = graph.snapshot()
        key = "".join(kind.to_json() for kind in sorted(snapshot.kinds.values(), key=lambda kind: kind.kind))
        snapshots[key] = snapshot
        largest = largest_by_statistics.setdefault(key, dict.fromkeys(MANY_TO_ONE_AND_BACK_PATHS, 0))
        for path, nodes in graph.actual_nodes().items():
            largest[path] = max(largest[path], nodes)

    assert len(largest_by_statistics) == 15
    for key, largest in largest_by_statistics.items():
        assert _worst_case_nodes(snapshot=snapshots[key]) == largest


def test_worst_case_of_a_query_from_many_nodes_to_one_and_back_can_exceed_the_brute_force_maximum() -> None:
    """With 3, 2 and 1 cars, the bound lets 3 paths reach the person with 2 cars, though only 2 can.

    The bound keeps the largest number of paths that can reach one node, not how many reach each node.
    """
    graph = OwnershipGraph(
        persons=("p1", "p2", "p3"),
        owners={"e1": "p1", "e2": "p1", "g1": "p1", "e3": "p2", "g2": "p2", "g3": "p3"},
    )

    worst_cases = _worst_case_nodes(snapshot=graph.snapshot())

    assert graph.actual_nodes() == {
        "TestPerson": 3,
        "TestPerson/cars": 6,
        "TestPerson/cars/owner": 6,
        "TestPerson/cars/owner/cars": 14,
    }
    assert worst_cases == {
        "TestPerson": 3,
        "TestPerson/cars": 6,
        "TestPerson/cars/owner": 6,
        "TestPerson/cars/owner/cars": 15,
    }
