from contextlib import nullcontext as does_not_raise
from dataclasses import dataclass

import pytest

from infrahub.exceptions import ValidationError
from infrahub.pools.number_pool_range_validation import (
    NumberRangeBounds,
    validate_number_pool_range,
    validate_number_pool_ranges,
    validate_shorthand_target,
)

STORED = [NumberRangeBounds(start=100, end=200, id="low"), NumberRangeBounds(start=300, end=400, id="high")]


@dataclass
class CandidateCase:
    name: str
    candidate: NumberRangeBounds


ACCEPTED_CANDIDATE_CASES: list[CandidateCase] = [
    CandidateCase(name="fills_the_gap_exactly", candidate=NumberRangeBounds(start=201, end=299)),
    CandidateCase(name="single_value", candidate=NumberRangeBounds(start=250, end=250)),
    CandidateCase(name="resized_over_its_own_bounds", candidate=NumberRangeBounds(start=100, end=250, id="low")),
]


@pytest.mark.parametrize("case", ACCEPTED_CANDIDATE_CASES, ids=lambda case: case.name)
def test_range_within_free_space_is_accepted(case: CandidateCase) -> None:
    with does_not_raise():
        validate_number_pool_range(candidate=case.candidate, others=STORED)


@dataclass
class RefusedCandidateCase:
    name: str
    candidate: NumberRangeBounds
    message: str


REFUSED_CANDIDATE_CASES: list[RefusedCandidateCase] = [
    RefusedCandidateCase(
        name="shares_an_end",
        candidate=NumberRangeBounds(start=200, end=250),
        message="Range 200-250 overlaps 100-200 (low)",
    ),
    RefusedCandidateCase(
        name="shares_a_start",
        candidate=NumberRangeBounds(start=250, end=300),
        message="Range 250-300 overlaps 300-400 (high)",
    ),
    RefusedCandidateCase(
        name="covers_both",
        candidate=NumberRangeBounds(start=50, end=500),
        message="Range 50-500 overlaps 100-200 (low), 300-400 (high)",
    ),
    RefusedCandidateCase(
        name="backwards",
        candidate=NumberRangeBounds(start=300, end=200),
        message="Range end (200) cannot be lower than start (300)",
    ),
]


@pytest.mark.parametrize("case", REFUSED_CANDIDATE_CASES, ids=lambda case: case.name)
def test_backwards_or_overlapping_range_is_refused(case: RefusedCandidateCase) -> None:
    with pytest.raises(ValidationError) as exc_info:
        validate_number_pool_range(candidate=case.candidate, others=STORED)

    assert exc_info.value.message == case.message


@dataclass
class RangeSetCase:
    name: str
    ranges: list[NumberRangeBounds]


ACCEPTED_RANGE_SET_CASES: list[RangeSetCase] = [
    RangeSetCase(name="no_range", ranges=[]),
    RangeSetCase(name="one_range", ranges=[NumberRangeBounds(start=100, end=200, id="only")]),
    RangeSetCase(
        name="adjacent_ranges",
        ranges=[NumberRangeBounds(start=100, end=200, id="low"), NumberRangeBounds(start=201, end=300, id="high")],
    ),
    RangeSetCase(
        name="unsorted_ranges",
        ranges=[NumberRangeBounds(start=300, end=400, id="high"), NumberRangeBounds(start=100, end=200, id="low")],
    ),
    RangeSetCase(
        name="single_value_ranges",
        ranges=[NumberRangeBounds(start=5, end=5, id="five"), NumberRangeBounds(start=6, end=6, id="six")],
    ),
]


@pytest.mark.parametrize("case", ACCEPTED_RANGE_SET_CASES, ids=lambda case: case.name)
def test_range_set_without_overlap_is_accepted(case: RangeSetCase) -> None:
    with does_not_raise():
        validate_number_pool_ranges(ranges=case.ranges)


def test_range_set_with_an_overlap_is_refused_from_its_lowest_range() -> None:
    ranges = [*STORED, NumberRangeBounds(start=150, end=320, id="middle")]

    with pytest.raises(ValidationError) as exc_info:
        validate_number_pool_ranges(ranges=ranges)

    assert exc_info.value.message == "Range 100-200 overlaps 150-320 (middle)"


SHORTHAND_TARGET_CASES: list[RangeSetCase] = [
    RangeSetCase(name="no_range", ranges=[]),
    RangeSetCase(name="one_range", ranges=STORED[:1]),
]


@pytest.mark.parametrize("case", SHORTHAND_TARGET_CASES, ids=lambda case: case.name)
def test_shorthand_applies_to_a_pool_holding_at_most_one_range(case: RangeSetCase) -> None:
    with does_not_raise():
        validate_shorthand_target(ranges=case.ranges)


def test_shorthand_on_a_pool_holding_several_ranges_is_refused_listing_them() -> None:
    with pytest.raises(ValidationError) as exc_info:
        validate_shorthand_target(ranges=list(reversed(STORED)))

    assert exc_info.value.message == (
        "start_range/end_range apply to a pool holding at most one range; "
        "this pool holds: 100-200 (low), 300-400 (high). Edit the ranges instead."
    )
