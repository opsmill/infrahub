from __future__ import annotations

from dataclasses import dataclass

import pytest

from infrahub.core.constants import RelationshipDirection
from infrahub.graphql.cost.histogram import RelationshipSideAccumulator, max_peers, mean_peers, peers_at_percentile
from infrahub.graphql.cost.models import HistogramBucket, RelationshipSideStatistics, TopNode
from infrahub.graphql.cost.queries import RelationshipSideDegreeQueryResult


def _node_id(index: int) -> str:
    return f"18a1f2c4-6a5e-4b0f-9a57-{index:012d}"


def _rows_split_over_two_kinds(indexes: range) -> list[RelationshipSideDegreeQueryResult]:
    """Rows of nodes whose peer count equals their index, split between two peer kinds."""
    rows: list[RelationshipSideDegreeQueryResult] = []
    for index in indexes:
        electric = index - index // 2
        gaz = index // 2
        rows.append(
            RelationshipSideDegreeQueryResult(node_id=_node_id(index), peer_kind="TestElectricCar", peers=electric)
        )
        if gaz:
            rows.append(RelationshipSideDegreeQueryResult(node_id=_node_id(index), peer_kind="TestGazCar", peers=gaz))
    return rows


def _build_thirty_five_nodes() -> RelationshipSideStatistics:
    """35 active nodes: 5 without peers, and nodes 1 to 30 with as many peers as their index."""
    accumulator = RelationshipSideAccumulator(
        identifier="person__car", direction=RelationshipDirection.BIDIR, kind="TestPerson"
    )
    accumulator.add_chunk(rows=_rows_split_over_two_kinds(indexes=range(21, 31)))
    accumulator.add_chunk(rows=_rows_split_over_two_kinds(indexes=range(1, 11)))
    accumulator.add_chunk(rows=[])
    accumulator.add_chunk(rows=_rows_split_over_two_kinds(indexes=range(11, 21)))
    return accumulator.build(active_count=35)


def test_histogram_has_powers_of_two_buckets_with_node_count_and_maximum() -> None:
    statistics = _build_thirty_five_nodes()

    assert statistics.histogram == (
        HistogramBucket(lower=0, upper=0, node_count=5, max=0),
        HistogramBucket(lower=1, upper=1, node_count=1, max=1),
        HistogramBucket(lower=2, upper=3, node_count=2, max=3),
        HistogramBucket(lower=4, upper=7, node_count=4, max=7),
        HistogramBucket(lower=8, upper=15, node_count=8, max=15),
        HistogramBucket(lower=16, upper=31, node_count=15, max=30),
    )


def test_histogram_lists_only_buckets_that_hold_a_node() -> None:
    accumulator = RelationshipSideAccumulator(
        identifier="person__car", direction=RelationshipDirection.BIDIR, kind="TestPerson"
    )
    accumulator.add_chunk(
        rows=[
            RelationshipSideDegreeQueryResult(node_id=_node_id(1), peer_kind="TestGazCar", peers=1),
            RelationshipSideDegreeQueryResult(node_id=_node_id(2), peer_kind="TestGazCar", peers=40),
        ]
    )

    statistics = accumulator.build(active_count=2)

    assert statistics.histogram == (
        HistogramBucket(lower=1, upper=1, node_count=1, max=1),
        HistogramBucket(lower=32, upper=63, node_count=1, max=40),
    )


def test_totals_add_up_over_chunks_and_peer_kinds() -> None:
    statistics = _build_thirty_five_nodes()

    assert statistics.identifier == "person__car"
    assert statistics.direction == RelationshipDirection.BIDIR
    assert statistics.nodes_with_peers == 30
    assert statistics.total_peers == 465
    assert statistics.peers_by_kind == {"TestElectricCar": 240, "TestGazCar": 225}


def test_top_nodes_are_the_twenty_nodes_with_the_most_peers_in_decreasing_order() -> None:
    statistics = _build_thirty_five_nodes()

    assert statistics.top_nodes == tuple(TopNode(node_id=_node_id(index), peers=index) for index in range(30, 10, -1))


def test_kind_with_fewer_than_twenty_nodes_lists_every_node_with_a_peer() -> None:
    accumulator = RelationshipSideAccumulator(
        identifier="person__car", direction=RelationshipDirection.BIDIR, kind="TestPerson"
    )
    accumulator.add_chunk(
        rows=[
            RelationshipSideDegreeQueryResult(node_id=_node_id(7), peer_kind="TestElectricCar", peers=1),
            RelationshipSideDegreeQueryResult(node_id=_node_id(4), peer_kind="TestElectricCar", peers=3),
        ]
    )
    accumulator.add_chunk(
        rows=[
            RelationshipSideDegreeQueryResult(node_id=_node_id(9), peer_kind="TestElectricCar", peers=4),
            RelationshipSideDegreeQueryResult(node_id=_node_id(9), peer_kind="TestGazCar", peers=6),
            RelationshipSideDegreeQueryResult(node_id=_node_id(2), peer_kind="TestGazCar", peers=3),
        ]
    )

    statistics = accumulator.build(active_count=5)

    assert statistics.nodes_with_peers == 4
    assert statistics.top_nodes == (
        TopNode(node_id=_node_id(9), peers=10),
        TopNode(node_id=_node_id(2), peers=3),
        TopNode(node_id=_node_id(4), peers=3),
        TopNode(node_id=_node_id(7), peers=1),
    )
    assert statistics.histogram == (
        HistogramBucket(lower=0, upper=0, node_count=1, max=0),
        HistogramBucket(lower=1, upper=1, node_count=1, max=1),
        HistogramBucket(lower=2, upper=3, node_count=2, max=3),
        HistogramBucket(lower=8, upper=15, node_count=1, max=10),
    )


def test_empty_kind_has_no_peers() -> None:
    accumulator = RelationshipSideAccumulator(
        identifier="person__car", direction=RelationshipDirection.BIDIR, kind="TestPerson"
    )

    statistics = accumulator.build(active_count=0)

    assert statistics == RelationshipSideStatistics(
        identifier="person__car",
        direction=RelationshipDirection.BIDIR,
        nodes_with_peers=0,
        total_peers=0,
        peers_by_kind={},
        histogram=(),
        top_nodes=(),
    )
    assert mean_peers(statistics=statistics) == 0
    assert peers_at_percentile(statistics=statistics, percentile=50) == 0
    assert peers_at_percentile(statistics=statistics, percentile=95) == 0
    assert max_peers(statistics=statistics) == 0


def test_more_nodes_with_peers_than_active_nodes_is_rejected() -> None:
    accumulator = RelationshipSideAccumulator(
        identifier="person__car", direction=RelationshipDirection.BIDIR, kind="TestPerson"
    )
    accumulator.add_chunk(
        rows=[
            RelationshipSideDegreeQueryResult(node_id=_node_id(1), peer_kind="TestGazCar", peers=1),
            RelationshipSideDegreeQueryResult(node_id=_node_id(2), peer_kind="TestGazCar", peers=1),
        ]
    )

    with pytest.raises(
        ValueError,
        match=r"^2 nodes of TestPerson have a peer through person__car \(bidirectional\), more than its 1 active nodes$",
    ):
        accumulator.build(active_count=1)


def test_row_without_peers_is_rejected() -> None:
    accumulator = RelationshipSideAccumulator(
        identifier="person__car", direction=RelationshipDirection.BIDIR, kind="TestPerson"
    )

    with pytest.raises(
        ValueError,
        match=r"^The peer count must be at least 1, got 0 for node 18a1f2c4-6a5e-4b0f-9a57-000000000001 of TestPerson through person__car$",
    ):
        accumulator.add_chunk(
            rows=[RelationshipSideDegreeQueryResult(node_id=_node_id(1), peer_kind="TestGazCar", peers=0)]
        )


@dataclass
class PercentileCase:
    name: str
    histogram: tuple[HistogramBucket, ...]
    total_peers: int
    median: int
    percentile_95: int
    maximum: int
    mean: float


PERCENTILE_CASES: list[PercentileCase] = [
    PercentileCase(
        name="thirty_five_nodes",
        histogram=(
            HistogramBucket(lower=0, upper=0, node_count=5, max=0),
            HistogramBucket(lower=1, upper=1, node_count=1, max=1),
            HistogramBucket(lower=2, upper=3, node_count=2, max=3),
            HistogramBucket(lower=4, upper=7, node_count=4, max=7),
            HistogramBucket(lower=8, upper=15, node_count=8, max=15),
            HistogramBucket(lower=16, upper=31, node_count=15, max=30),
        ),
        total_peers=465,
        median=15,
        percentile_95=30,
        maximum=30,
        mean=465 / 35,
    ),
    PercentileCase(
        name="four_nodes_median_on_the_second_node",
        histogram=(
            HistogramBucket(lower=0, upper=0, node_count=1, max=0),
            HistogramBucket(lower=1, upper=1, node_count=1, max=1),
            HistogramBucket(lower=2, upper=3, node_count=1, max=3),
            HistogramBucket(lower=8, upper=15, node_count=1, max=10),
        ),
        total_peers=14,
        median=1,
        percentile_95=10,
        maximum=10,
        mean=3.5,
    ),
    PercentileCase(
        name="one_node",
        histogram=(HistogramBucket(lower=4, upper=7, node_count=1, max=5),),
        total_peers=5,
        median=5,
        percentile_95=5,
        maximum=5,
        mean=5.0,
    ),
    PercentileCase(
        name="twenty_nodes_95th_percentile_on_the_nineteenth_node",
        histogram=(
            HistogramBucket(lower=0, upper=0, node_count=18, max=0),
            HistogramBucket(lower=1, upper=1, node_count=1, max=1),
            HistogramBucket(lower=64, upper=127, node_count=1, max=100),
        ),
        total_peers=101,
        median=0,
        percentile_95=1,
        maximum=100,
        mean=5.05,
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(case, id=case.name) for case in PERCENTILE_CASES])
def test_percentiles_are_read_from_the_bucket_maximum(test_case: PercentileCase) -> None:
    statistics = RelationshipSideStatistics(
        identifier="person__car",
        direction=RelationshipDirection.BIDIR,
        nodes_with_peers=sum(bucket.node_count for bucket in test_case.histogram if bucket.lower > 0),
        total_peers=test_case.total_peers,
        peers_by_kind={"TestGazCar": test_case.total_peers},
        histogram=test_case.histogram,
        top_nodes=(),
    )

    assert peers_at_percentile(statistics=statistics, percentile=50) == test_case.median
    assert peers_at_percentile(statistics=statistics, percentile=95) == test_case.percentile_95
    assert max_peers(statistics=statistics) == test_case.maximum
    assert mean_peers(statistics=statistics) == pytest.approx(test_case.mean)


@pytest.mark.parametrize("percentile", [0, 101])
def test_percentile_outside_one_to_one_hundred_is_rejected(percentile: int) -> None:
    statistics = _build_thirty_five_nodes()

    with pytest.raises(ValueError, match=rf"^The percentile must be between 1 and 100, got {percentile}$"):
        peers_at_percentile(statistics=statistics, percentile=percentile)
