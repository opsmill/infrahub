from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime

import pytest

from infrahub.core.constants import RelationshipCardinality, RelationshipDirection
from infrahub.graphql.cost.models import (
    CostFigures,
    CostTreeField,
    EstimateReason,
    EstimateSource,
    FieldDescription,
    FieldEstimate,
    HistogramBucket,
    KindStatistics,
    RelationshipRef,
    RelationshipSideStatistics,
    StatisticsPointer,
    StatisticsSnapshot,
    TopNode,
)

PERSON_CARS = RelationshipSideStatistics(
    identifier="testcar__testperson",
    direction=RelationshipDirection.INBOUND,
    nodes_with_peers=2,
    total_peers=7,
    peers_by_kind={"TestElectricCar": 5, "TestGazCar": 2},
    histogram=(
        HistogramBucket(lower=0, upper=0, node_count=1, max=0),
        HistogramBucket(lower=2, upper=3, node_count=1, max=2),
        HistogramBucket(lower=4, upper=7, node_count=1, max=5),
    ),
    top_nodes=(
        TopNode(node_id="18a1f2c4-6a5e-4b0f-9a57-1f0d3c2b8e01", peers=5),
        TopNode(node_id="18a1f2c4-6a5e-4b0f-9a57-1f0d3c2b8e02", peers=2),
    ),
)

PERSON_MANAGER = RelationshipSideStatistics(
    identifier="testperson__testperson",
    direction=RelationshipDirection.OUTBOUND,
    nodes_with_peers=1,
    total_peers=1,
    peers_by_kind={"TestPerson": 1},
    histogram=(
        HistogramBucket(lower=0, upper=0, node_count=2, max=0),
        HistogramBucket(lower=1, upper=1, node_count=1, max=1),
    ),
    top_nodes=(TopNode(node_id="18a1f2c4-6a5e-4b0f-9a57-1f0d3c2b8e01", peers=1),),
)

PERSON_REPORTS = RelationshipSideStatistics(
    identifier="testperson__testperson",
    direction=RelationshipDirection.INBOUND,
    nodes_with_peers=1,
    total_peers=1,
    peers_by_kind={"TestPerson": 1},
    histogram=(
        HistogramBucket(lower=0, upper=0, node_count=2, max=0),
        HistogramBucket(lower=1, upper=1, node_count=1, max=1),
    ),
    top_nodes=(TopNode(node_id="18a1f2c4-6a5e-4b0f-9a57-1f0d3c2b8e03", peers=1),),
)

PERSON_STATISTICS = KindStatistics(
    kind="TestPerson",
    label_count=4,
    active_count=3,
    relationships=(PERSON_CARS, PERSON_MANAGER, PERSON_REPORTS),
)

POINTER = StatisticsPointer(
    version=3,
    branch="main",
    computed_at=datetime(2026, 10, 7, 4, 12, 30, tzinfo=UTC),
    schema_hash="9f3c0a7e5d1b",
    kinds=("TestPerson", "TestElectricCar"),
)

SNAPSHOT = StatisticsSnapshot(pointer=POINTER, kinds={"TestPerson": PERSON_STATISTICS})


@dataclass
class KindStatisticsRoundTripCase:
    name: str
    statistics: KindStatistics


KIND_STATISTICS_ROUND_TRIP_CASES: list[KindStatisticsRoundTripCase] = [
    KindStatisticsRoundTripCase(
        name="kind_with_relationship_sides",
        statistics=PERSON_STATISTICS,
    ),
    KindStatisticsRoundTripCase(
        name="kind_without_active_nodes",
        statistics=KindStatistics(
            kind="TestGazCar",
            label_count=2,
            active_count=0,
            relationships=(
                RelationshipSideStatistics(
                    identifier="testcar__testperson",
                    direction=RelationshipDirection.OUTBOUND,
                    nodes_with_peers=0,
                    total_peers=0,
                    peers_by_kind={},
                    histogram=(),
                    top_nodes=(),
                ),
            ),
        ),
    ),
    KindStatisticsRoundTripCase(
        name="kind_without_relationships",
        statistics=KindStatistics(kind="TestTag", label_count=5, active_count=5, relationships=()),
    ),
]


@pytest.mark.parametrize(
    "test_case",
    [pytest.param(tc, id=tc.name) for tc in KIND_STATISTICS_ROUND_TRIP_CASES],
)
def test_kind_statistics_survives_json_round_trip(test_case: KindStatisticsRoundTripCase) -> None:
    assert KindStatistics.from_json(value=test_case.statistics.to_json()) == test_case.statistics


def test_kind_statistics_json_form_uses_stored_field_names() -> None:
    statistics = KindStatistics(
        kind="TestPerson",
        label_count=2,
        active_count=1,
        relationships=(
            RelationshipSideStatistics(
                identifier="testcar__testperson",
                direction=RelationshipDirection.INBOUND,
                nodes_with_peers=1,
                total_peers=3,
                peers_by_kind={"TestElectricCar": 3},
                histogram=(HistogramBucket(lower=2, upper=3, node_count=1, max=3),),
                top_nodes=(TopNode(node_id="18a1f2c4-6a5e-4b0f-9a57-1f0d3c2b8e01", peers=3),),
            ),
        ),
    )

    assert json.loads(statistics.to_json()) == {
        "kind": "TestPerson",
        "label_count": 2,
        "active_count": 1,
        "relationships": [
            {
                "identifier": "testcar__testperson",
                "direction": "inbound",
                "nodes_with_peers": 1,
                "total_peers": 3,
                "peers_by_kind": {"TestElectricCar": 3},
                "histogram": [{"lower": 2, "upper": 3, "node_count": 1, "max": 3}],
                "top_nodes": [{"node_id": "18a1f2c4-6a5e-4b0f-9a57-1f0d3c2b8e01", "peers": 3}],
            }
        ],
    }


def test_statistics_pointer_survives_json_round_trip() -> None:
    assert StatisticsPointer.from_json(value=POINTER.to_json()) == POINTER


@dataclass
class SideLookupCase:
    name: str
    identifier: str
    direction: RelationshipDirection
    kind: str
    expected: RelationshipSideStatistics | None


SIDE_LOOKUP_CASES: list[SideLookupCase] = [
    SideLookupCase(
        name="matching_side_is_returned",
        identifier="testcar__testperson",
        direction=RelationshipDirection.INBOUND,
        kind="TestPerson",
        expected=PERSON_CARS,
    ),
    SideLookupCase(
        name="outbound_side_of_a_relationship_to_the_same_kind",
        identifier="testperson__testperson",
        direction=RelationshipDirection.OUTBOUND,
        kind="TestPerson",
        expected=PERSON_MANAGER,
    ),
    SideLookupCase(
        name="inbound_side_of_a_relationship_to_the_same_kind",
        identifier="testperson__testperson",
        direction=RelationshipDirection.INBOUND,
        kind="TestPerson",
        expected=PERSON_REPORTS,
    ),
    SideLookupCase(
        name="unknown_kind_has_no_side",
        identifier="testcar__testperson",
        direction=RelationshipDirection.INBOUND,
        kind="TestElectricCar",
        expected=None,
    ),
    SideLookupCase(
        name="unknown_identifier_has_no_side",
        identifier="testperson__testtag",
        direction=RelationshipDirection.INBOUND,
        kind="TestPerson",
        expected=None,
    ),
    SideLookupCase(
        name="unknown_direction_has_no_side",
        identifier="testcar__testperson",
        direction=RelationshipDirection.OUTBOUND,
        kind="TestPerson",
        expected=None,
    ),
]


@pytest.mark.parametrize(
    "test_case",
    [pytest.param(tc, id=tc.name) for tc in SIDE_LOOKUP_CASES],
)
def test_snapshot_side_lookup(test_case: SideLookupCase) -> None:
    side = SNAPSHOT.side(identifier=test_case.identifier, direction=test_case.direction, kind=test_case.kind)

    assert side == test_case.expected


@dataclass
class NegativeFiguresCase:
    name: str
    nodes: int
    resolver_calls: int
    database_rows: int
    expected_message: str


NEGATIVE_FIGURES_CASES: list[NegativeFiguresCase] = [
    NegativeFiguresCase(
        name="negative_nodes",
        nodes=-1,
        resolver_calls=0,
        database_rows=0,
        expected_message=r"^Cost figures cannot be negative: nodes=-1, resolver_calls=0, database_rows=0$",
    ),
    NegativeFiguresCase(
        name="negative_resolver_calls",
        nodes=0,
        resolver_calls=-2,
        database_rows=0,
        expected_message=r"^Cost figures cannot be negative: nodes=0, resolver_calls=-2, database_rows=0$",
    ),
    NegativeFiguresCase(
        name="negative_database_rows",
        nodes=0,
        resolver_calls=0,
        database_rows=-3,
        expected_message=r"^Cost figures cannot be negative: nodes=0, resolver_calls=0, database_rows=-3$",
    ),
]


@pytest.mark.parametrize(
    "test_case",
    [pytest.param(tc, id=tc.name) for tc in NEGATIVE_FIGURES_CASES],
)
def test_cost_figures_reject_negative_values(test_case: NegativeFiguresCase) -> None:
    with pytest.raises(ValueError, match=test_case.expected_message):
        CostFigures(
            nodes=test_case.nodes,
            resolver_calls=test_case.resolver_calls,
            database_rows=test_case.database_rows,
        )


def test_cost_figures_accept_zero() -> None:
    figures = CostFigures(nodes=0, resolver_calls=0, database_rows=0)

    assert (figures.nodes, figures.resolver_calls, figures.database_rows) == (0, 0, 0)


CARS_FIELD = FieldDescription(
    kind="TestCar", relationship_identifier="testcar__testperson", cardinality=RelationshipCardinality.MANY
)
FIGURES = CostFigures(nodes=7, resolver_calls=3, database_rows=21)


@dataclass
class InvalidFieldEstimateCase:
    name: str
    expected: CostFigures | None
    worst_case: CostFigures | None
    source: EstimateSource | None
    worst_case_is_bound: bool
    reason: EstimateReason | None
    expected_message: str


INVALID_FIELD_ESTIMATE_CASES: list[InvalidFieldEstimateCase] = [
    InvalidFieldEstimateCase(
        name="reason_with_expected_figures",
        expected=FIGURES,
        worst_case=None,
        source=None,
        worst_case_is_bound=False,
        reason=EstimateReason.NO_STATISTICS,
        expected_message=r"^An estimate with a reason has no figures, no source and no bound$",
    ),
    InvalidFieldEstimateCase(
        name="reason_with_worst_case_figures",
        expected=None,
        worst_case=FIGURES,
        source=None,
        worst_case_is_bound=False,
        reason=EstimateReason.NO_STATISTICS,
        expected_message=r"^An estimate with a reason has no figures, no source and no bound$",
    ),
    InvalidFieldEstimateCase(
        name="reason_with_source",
        expected=None,
        worst_case=None,
        source=EstimateSource.STATISTICS,
        worst_case_is_bound=False,
        reason=EstimateReason.NO_STATISTICS,
        expected_message=r"^An estimate with a reason has no figures, no source and no bound$",
    ),
    InvalidFieldEstimateCase(
        name="reason_with_bound",
        expected=None,
        worst_case=None,
        source=None,
        worst_case_is_bound=True,
        reason=EstimateReason.NO_STATISTICS,
        expected_message=r"^An estimate with a reason has no figures, no source and no bound$",
    ),
    InvalidFieldEstimateCase(
        name="no_reason_without_expected_figures",
        expected=None,
        worst_case=FIGURES,
        source=EstimateSource.STATISTICS,
        worst_case_is_bound=False,
        reason=None,
        expected_message=r"^An estimate without a reason has expected figures, worst-case figures and a source$",
    ),
    InvalidFieldEstimateCase(
        name="no_reason_without_worst_case_figures",
        expected=FIGURES,
        worst_case=None,
        source=EstimateSource.STATISTICS,
        worst_case_is_bound=False,
        reason=None,
        expected_message=r"^An estimate without a reason has expected figures, worst-case figures and a source$",
    ),
    InvalidFieldEstimateCase(
        name="no_reason_without_source",
        expected=FIGURES,
        worst_case=FIGURES,
        source=None,
        worst_case_is_bound=False,
        reason=None,
        expected_message=r"^An estimate without a reason has expected figures, worst-case figures and a source$",
    ),
]


@pytest.mark.parametrize(
    "test_case",
    [pytest.param(tc, id=tc.name) for tc in INVALID_FIELD_ESTIMATE_CASES],
)
def test_field_estimate_rejects_inconsistent_combinations(test_case: InvalidFieldEstimateCase) -> None:
    with pytest.raises(ValueError, match=test_case.expected_message):
        FieldEstimate(
            field=CARS_FIELD,
            expected=test_case.expected,
            worst_case=test_case.worst_case,
            source=test_case.source,
            worst_case_is_bound=test_case.worst_case_is_bound,
            reason=test_case.reason,
        )


@dataclass
class ValidFieldEstimateCase:
    name: str
    expected: CostFigures | None
    worst_case: CostFigures | None
    source: EstimateSource | None
    worst_case_is_bound: bool
    reason: EstimateReason | None


VALID_FIELD_ESTIMATE_CASES: list[ValidFieldEstimateCase] = [
    ValidFieldEstimateCase(
        name="estimate_without_statistics",
        expected=None,
        worst_case=None,
        source=None,
        worst_case_is_bound=False,
        reason=EstimateReason.NO_STATISTICS,
    ),
    ValidFieldEstimateCase(
        name="counted_estimate_with_bound",
        expected=FIGURES,
        worst_case=FIGURES,
        source=EstimateSource.COUNTED,
        worst_case_is_bound=True,
        reason=None,
    ),
    ValidFieldEstimateCase(
        name="statistics_estimate_without_bound",
        expected=FIGURES,
        worst_case=CostFigures(nodes=12, resolver_calls=3, database_rows=36),
        source=EstimateSource.STATISTICS,
        worst_case_is_bound=False,
        reason=None,
    ),
]


@pytest.mark.parametrize(
    "test_case",
    [pytest.param(tc, id=tc.name) for tc in VALID_FIELD_ESTIMATE_CASES],
)
def test_field_estimate_accepts_consistent_combinations(test_case: ValidFieldEstimateCase) -> None:
    estimate = FieldEstimate(
        field=CARS_FIELD,
        expected=test_case.expected,
        worst_case=test_case.worst_case,
        source=test_case.source,
        worst_case_is_bound=test_case.worst_case_is_bound,
        reason=test_case.reason,
    )

    assert estimate.reason == test_case.reason


CARS_RELATIONSHIP = RelationshipRef(
    identifier="testcar__testperson", direction=RelationshipDirection.INBOUND, name="cars", hierarchical=False
)


@dataclass
class InvalidTreeFieldCase:
    name: str
    relationship: RelationshipRef | None
    cardinality: RelationshipCardinality
    expected_message: str
    parent_kinds: tuple[str, ...] = ()
    selects_count: bool = False
    selects_nodes: bool = True
    id_only: bool = False
    max_matching_nodes: int | None = None
    children: tuple[CostTreeField, ...] = ()


OWNER_LEAF = CostTreeField(
    path="TestPerson/cars/owner",
    kind="TestPerson",
    concrete_kinds=("TestPerson",),
    parent_kinds=("TestCar",),
    relationship=RelationshipRef(
        identifier="testcar__testperson", direction=RelationshipDirection.OUTBOUND, name="owner", hierarchical=False
    ),
    cardinality=RelationshipCardinality.ONE,
    selected_attribute_count=0,
    selected_cardinality_one_count=0,
    selects_count=False,
    selects_nodes=True,
    id_only=True,
    max_matching_nodes=None,
    arguments={},
    children=(),
)


INVALID_TREE_FIELD_CASES: list[InvalidTreeFieldCase] = [
    InvalidTreeFieldCase(
        name="top_level_field_with_cardinality_one",
        relationship=None,
        cardinality=RelationshipCardinality.ONE,
        expected_message=r"^The top-level field 'TestPerson' must have cardinality many$",
    ),
    InvalidTreeFieldCase(
        name="top_level_field_with_parent_kinds",
        relationship=None,
        cardinality=RelationshipCardinality.MANY,
        parent_kinds=("TestCar",),
        expected_message=r"^The top-level field 'TestPerson' has no parent kinds$",
    ),
    InvalidTreeFieldCase(
        name="relationship_field_bounding_its_matching_nodes",
        relationship=CARS_RELATIONSHIP,
        cardinality=RelationshipCardinality.MANY,
        parent_kinds=("TestPerson",),
        max_matching_nodes=1,
        expected_message=r"^Only a top-level field can bound its matching nodes: 'TestPerson'$",
    ),
    InvalidTreeFieldCase(
        name="count_on_cardinality_one",
        relationship=CARS_RELATIONSHIP,
        cardinality=RelationshipCardinality.ONE,
        selects_count=True,
        expected_message=r"^Only a field of cardinality many can select count: 'TestPerson'$",
    ),
    InvalidTreeFieldCase(
        name="no_nodes_on_cardinality_one",
        relationship=CARS_RELATIONSHIP,
        cardinality=RelationshipCardinality.ONE,
        selects_nodes=False,
        expected_message=r"^Only a field of cardinality many without children can skip its nodes: 'TestPerson'$",
    ),
    InvalidTreeFieldCase(
        name="no_nodes_with_children",
        relationship=CARS_RELATIONSHIP,
        cardinality=RelationshipCardinality.MANY,
        selects_nodes=False,
        children=(OWNER_LEAF,),
        expected_message=r"^Only a field of cardinality many without children can skip its nodes: 'TestPerson'$",
    ),
    InvalidTreeFieldCase(
        name="id_only_on_cardinality_many",
        relationship=CARS_RELATIONSHIP,
        cardinality=RelationshipCardinality.MANY,
        id_only=True,
        expected_message=r"^Only a field of cardinality one can select only its id: 'TestPerson'$",
    ),
]


@pytest.mark.parametrize(
    "test_case",
    [pytest.param(tc, id=tc.name) for tc in INVALID_TREE_FIELD_CASES],
)
def test_cost_tree_field_rejects_impossible_selections(test_case: InvalidTreeFieldCase) -> None:
    with pytest.raises(ValueError, match=test_case.expected_message):
        CostTreeField(
            path="TestPerson",
            kind="TestPerson",
            concrete_kinds=("TestPerson",),
            parent_kinds=test_case.parent_kinds,
            relationship=test_case.relationship,
            cardinality=test_case.cardinality,
            selected_attribute_count=1,
            selected_cardinality_one_count=0,
            selects_count=test_case.selects_count,
            selects_nodes=test_case.selects_nodes,
            id_only=test_case.id_only,
            max_matching_nodes=test_case.max_matching_nodes,
            arguments={},
            children=test_case.children,
        )
