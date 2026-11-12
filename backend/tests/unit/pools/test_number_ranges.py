import sys
from collections.abc import Callable
from dataclasses import dataclass

import pytest

from infrahub.pools.number_ranges import (
    EffectiveSegment,
    EffectiveSpace,
    NumberDomain,
    NumberSpan,
    PoolRange,
    allocation_bounds,
    format_range_label,
)


@dataclass
class EffectiveSpaceTestCase:
    name: str
    ranges: list[PoolRange]
    domain: NumberDomain
    expected_segments: list[EffectiveSegment]
    expected_size: int


EFFECTIVE_SPACE_TEST_CASES: list[EffectiveSpaceTestCase] = [
    EffectiveSpaceTestCase(
        name="higher_weight_first",
        ranges=[PoolRange(id="a", start=100, end=200), PoolRange(id="b", start=205, end=300, weight=10)],
        domain=NumberDomain(),
        expected_segments=[
            EffectiveSegment(start=205, end=300, range_id="b"),
            EffectiveSegment(start=100, end=200, range_id="a"),
        ],
        expected_size=197,
    ),
    EffectiveSpaceTestCase(
        name="equal_weight_lowest_start_first",
        ranges=[PoolRange(id="b", start=205, end=300, weight=5), PoolRange(id="a", start=100, end=200, weight=5)],
        domain=NumberDomain(),
        expected_segments=[
            EffectiveSegment(start=100, end=200, range_id="a"),
            EffectiveSegment(start=205, end=300, range_id="b"),
        ],
        expected_size=197,
    ),
    EffectiveSpaceTestCase(
        name="clipped_to_min_and_max_value",
        ranges=[PoolRange(id="a", start=1, end=100), PoolRange(id="b", start=150, end=500)],
        domain=NumberDomain(lower=10, upper=200),
        expected_segments=[
            EffectiveSegment(start=10, end=100, range_id="a"),
            EffectiveSegment(start=150, end=200, range_id="b"),
        ],
        expected_size=142,
    ),
    EffectiveSpaceTestCase(
        name="range_clipped_to_nothing_yields_no_segment",
        ranges=[PoolRange(id="a", start=1, end=9), PoolRange(id="b", start=20, end=30)],
        domain=NumberDomain(lower=10),
        expected_segments=[EffectiveSegment(start=20, end=30, range_id="b")],
        expected_size=11,
    ),
    EffectiveSpaceTestCase(
        name="exclusions_split_a_range",
        ranges=[PoolRange(id="a", start=1, end=20)],
        domain=NumberDomain(
            exclusions=(NumberSpan(start=5, end=5), NumberSpan(start=10, end=12), NumberSpan(start=20, end=20))
        ),
        expected_segments=[
            EffectiveSegment(start=1, end=4, range_id="a"),
            EffectiveSegment(start=6, end=9, range_id="a"),
            EffectiveSegment(start=13, end=19, range_id="a"),
        ],
        expected_size=15,
    ),
    EffectiveSpaceTestCase(
        name="overlapping_single_and_range_exclusions_subtract_once",
        ranges=[PoolRange(id="a", start=1, end=10)],
        domain=NumberDomain(
            exclusions=(NumberSpan(start=3, end=3), NumberSpan(start=2, end=4), NumberSpan(start=4, end=4))
        ),
        expected_segments=[
            EffectiveSegment(start=1, end=1, range_id="a"),
            EffectiveSegment(start=5, end=10, range_id="a"),
        ],
        expected_size=7,
    ),
    EffectiveSpaceTestCase(
        name="exclusions_outside_every_range_subtract_nothing",
        ranges=[PoolRange(id="a", start=100, end=200), PoolRange(id="b", start=300, end=400)],
        domain=NumberDomain(
            exclusions=(
                NumberSpan(start=1, end=1),
                NumberSpan(start=50, end=99),
                NumberSpan(start=201, end=299),
                NumberSpan(start=401, end=401),
                NumberSpan(start=500, end=600),
            )
        ),
        expected_segments=[
            EffectiveSegment(start=100, end=200, range_id="a"),
            EffectiveSegment(start=300, end=400, range_id="b"),
        ],
        expected_size=202,
    ),
    EffectiveSpaceTestCase(
        name="range_fully_excluded_yields_no_segment",
        ranges=[PoolRange(id="a", start=10, end=20), PoolRange(id="b", start=30, end=40)],
        domain=NumberDomain(exclusions=(NumberSpan(start=5, end=25),)),
        expected_segments=[EffectiveSegment(start=30, end=40, range_id="b")],
        expected_size=11,
    ),
    EffectiveSpaceTestCase(
        name="zero_ranges_gives_size_zero",
        ranges=[],
        domain=NumberDomain(lower=1, upper=100),
        expected_segments=[],
        expected_size=0,
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in EFFECTIVE_SPACE_TEST_CASES])
def test_effective_space_segments_and_size(test_case: EffectiveSpaceTestCase) -> None:
    space = EffectiveSpace(ranges=test_case.ranges, domain=test_case.domain)

    assert list(space.segments) == test_case.expected_segments
    assert space.size == test_case.expected_size
    assert space.is_empty == (test_case.expected_size == 0)
    assert space.as_query_ranges() == [[segment.start, segment.end] for segment in test_case.expected_segments]


def test_unset_weight_counts_as_zero() -> None:
    unweighted = PoolRange(id="unweighted", start=1, end=10)
    space = EffectiveSpace(
        ranges=[
            PoolRange(id="negative", start=50, end=60, weight=-1),
            unweighted,
            PoolRange(id="zero", start=20, end=30, weight=0),
        ],
        domain=NumberDomain(),
    )

    assert unweighted.weight == 0
    assert [segment.range_id for segment in space.segments] == ["unweighted", "zero", "negative"]


def test_segments_inside_a_range_follow_ascending_start() -> None:
    space = EffectiveSpace(
        ranges=[PoolRange(id="low", start=1, end=10), PoolRange(id="high", start=100, end=110, weight=1)],
        domain=NumberDomain(exclusions=(NumberSpan(start=5, end=5), NumberSpan(start=105, end=105))),
    )

    assert space.as_query_ranges() == [[100, 104], [106, 110], [1, 4], [6, 10]]


def test_range_for_and_contains() -> None:
    space = EffectiveSpace(
        ranges=[PoolRange(id="a", start=100, end=200), PoolRange(id="b", start=205, end=300, weight=10)],
        domain=NumberDomain(exclusions=(NumberSpan(start=150, end=150),)),
    )

    assert space.range_for(100) == "a"
    assert space.range_for(200) == "a"
    assert space.range_for(205) == "b"
    assert space.range_for(300) == "b"
    assert space.range_for(150) is None
    assert space.range_for(202) is None
    assert space.range_for(99) is None
    assert space.range_for(301) is None
    assert space.contains(151)
    assert not space.contains(150)
    assert not space.contains(203)


def test_segments_of_returns_the_segments_of_one_range() -> None:
    space = EffectiveSpace(
        ranges=[PoolRange(id="a", start=1, end=10), PoolRange(id="b", start=20, end=30)],
        domain=NumberDomain(exclusions=(NumberSpan(start=5, end=5),)),
    )

    assert space.segments_of("a") == (
        EffectiveSegment(start=1, end=4, range_id="a"),
        EffectiveSegment(start=6, end=10, range_id="a"),
    )
    assert space.segments_of("missing") == ()


def test_size_of_counts_the_numbers_a_range_contributes() -> None:
    space = EffectiveSpace(
        ranges=[
            PoolRange(id="a", start=1, end=10),
            PoolRange(id="b", start=20, end=30),
            PoolRange(id="c", start=40, end=45),
        ],
        domain=NumberDomain(upper=30, exclusions=(NumberSpan(start=5, end=5),)),
    )

    assert space.size_of("a") == 9
    assert space.size_of("b") == 11
    assert space.size_of("c") == 0, "a range clipped to nothing contributes no number"
    assert space.size_of("missing") == 0
    assert space.size == 20


@dataclass
class OpenEndSizeTestCase:
    name: str
    domain: NumberDomain
    expected_size: int | None
    expected_by_range: dict[str, int | None]


OPEN_END_SIZE_TEST_CASES = [
    OpenEndSizeTestCase(
        name="open_end_without_upper_limit",
        domain=NumberDomain(),
        expected_size=None,
        expected_by_range={"closed": 50, "open": None, "missing": 0},
    ),
    OpenEndSizeTestCase(
        name="open_end_clipped_by_upper_limit",
        domain=NumberDomain(upper=4094),
        expected_size=50 + 3995,
        expected_by_range={"closed": 50, "open": 3995, "missing": 0},
    ),
]


@pytest.mark.parametrize("test_case", OPEN_END_SIZE_TEST_CASES, ids=[case.name for case in OPEN_END_SIZE_TEST_CASES])
def test_a_space_running_up_to_the_largest_number_has_no_size(test_case: OpenEndSizeTestCase) -> None:
    space = EffectiveSpace(
        ranges=[PoolRange(id="closed", start=1, end=50), PoolRange(id="open", start=100, end=sys.maxsize)],
        domain=test_case.domain,
    )

    assert space.size == test_case.expected_size
    assert {range_id: space.size_of(range_id) for range_id in test_case.expected_by_range} == (
        test_case.expected_by_range
    )
    assert not space.is_empty


def test_a_span_counts_both_of_its_bounds() -> None:
    assert NumberSpan(start=3, end=3).size == 1
    assert PoolRange(id="a", start=10, end=20).size == 11


@pytest.mark.parametrize(
    "build",
    [
        pytest.param(lambda: NumberSpan(start=5, end=4), id="span"),
        pytest.param(lambda: PoolRange(id="a", start=5, end=4), id="pool-range"),
        pytest.param(lambda: EffectiveSegment(start=5, end=4, range_id="a"), id="segment"),
    ],
)
def test_a_span_whose_end_precedes_its_start_is_refused(build: Callable[[], NumberSpan]) -> None:
    with pytest.raises(
        ValueError, match=r"^Span end \(4\) is lower than its start \(5\); a span runs upward from start to end\.$"
    ):
        build()


def test_empty_space_contains_nothing() -> None:
    space = EffectiveSpace(ranges=[], domain=NumberDomain())

    assert space.is_empty
    assert space.as_query_ranges() == []
    assert space.range_for(1) is None
    assert not space.contains(1)


@dataclass
class AllocationBoundsTestCase:
    name: str
    start: int | None
    end: int | None
    expected: tuple[int, int]


ALLOCATION_BOUNDS_TEST_CASES: list[AllocationBoundsTestCase] = [
    AllocationBoundsTestCase(name="both_open", start=None, end=None, expected=(1, sys.maxsize)),
    AllocationBoundsTestCase(name="open_end", start=100, end=None, expected=(100, sys.maxsize)),
    AllocationBoundsTestCase(name="open_start", start=None, end=4094, expected=(1, 4094)),
    AllocationBoundsTestCase(name="both_entered", start=100, end=4094, expected=(100, 4094)),
]


@pytest.mark.parametrize(
    "test_case", ALLOCATION_BOUNDS_TEST_CASES, ids=[case.name for case in ALLOCATION_BOUNDS_TEST_CASES]
)
def test_an_open_bound_spans_to_the_widest_number(test_case: AllocationBoundsTestCase) -> None:
    assert allocation_bounds(start=test_case.start, end=test_case.end) == test_case.expected


@dataclass
class RangeLabelTestCase:
    name: str
    start: int
    end: int
    expected: str


RANGE_LABEL_TEST_CASES: list[RangeLabelTestCase] = [
    RangeLabelTestCase(name="entered_end", start=100, end=4094, expected="100 - 4094"),
    RangeLabelTestCase(name="widest_end", start=1, end=sys.maxsize, expected="1 - MAX"),
    RangeLabelTestCase(name="single_number", start=5, end=5, expected="5 - 5"),
]


@pytest.mark.parametrize("test_case", RANGE_LABEL_TEST_CASES, ids=[case.name for case in RANGE_LABEL_TEST_CASES])
def test_a_range_label_writes_the_widest_end_as_max(test_case: RangeLabelTestCase) -> None:
    assert format_range_label(start=test_case.start, end=test_case.end) == test_case.expected


def test_carving_the_widest_range_clips_it_to_the_domain_bounds() -> None:
    domain = NumberDomain(lower=100, upper=4094, exclusions=(NumberSpan(start=200, end=299),))

    assert domain.carve(1, sys.maxsize) == [NumberSpan(start=100, end=199), NumberSpan(start=300, end=4094)]


@dataclass
class ResolveTestCase:
    name: str
    domain: NumberDomain
    start: int | None
    end: int | None
    expected: tuple[int, int]


RESOLVE_TEST_CASES: list[ResolveTestCase] = [
    ResolveTestCase(
        name="open_bounds_without_limits", domain=NumberDomain(), start=None, end=None, expected=(1, sys.maxsize)
    ),
    ResolveTestCase(
        name="open_bounds_follow_min_and_max_value",
        domain=NumberDomain(lower=100, upper=4094),
        start=None,
        end=None,
        expected=(100, 4094),
    ),
    ResolveTestCase(
        name="open_end_follows_max_value",
        domain=NumberDomain(lower=100, upper=4094),
        start=200,
        end=None,
        expected=(200, 4094),
    ),
    ResolveTestCase(
        name="open_start_follows_min_value",
        domain=NumberDomain(lower=100, upper=4094),
        start=None,
        end=300,
        expected=(100, 300),
    ),
    ResolveTestCase(
        name="min_value_below_one_keeps_the_open_start_at_one",
        domain=NumberDomain(lower=-10),
        start=None,
        end=50,
        expected=(1, 50),
    ),
    ResolveTestCase(
        name="entered_bounds_unchanged_outside_the_limits",
        domain=NumberDomain(lower=100, upper=4094),
        start=10,
        end=5000,
        expected=(10, 5000),
    ),
    ResolveTestCase(
        name="open_start_above_an_entered_end",
        domain=NumberDomain(lower=100),
        start=None,
        end=50,
        expected=(100, 50),
    ),
]


@pytest.mark.parametrize("test_case", RESOLVE_TEST_CASES, ids=[case.name for case in RESOLVE_TEST_CASES])
def test_resolve_reads_open_bounds_through_the_domain_limits(test_case: ResolveTestCase) -> None:
    assert test_case.domain.resolve(start=test_case.start, end=test_case.end) == test_case.expected
