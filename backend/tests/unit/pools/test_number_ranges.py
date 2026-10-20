from collections.abc import Callable
from dataclasses import dataclass

import pytest

from infrahub.pools.number_ranges import EffectiveSegment, EffectiveSpace, NumberDomain, NumberSpan, PoolRange


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
    assert space.size == space.size_of("a") + space.size_of("b") + space.size_of("c")


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
