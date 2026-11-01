from contextlib import nullcontext as does_not_raise
from dataclasses import dataclass

import pytest

from infrahub.exceptions import ValidationError
from infrahub.pools.number_pool_range_validation import (
    NumberRangeBounds,
    validate_number_pool_range,
    validate_number_pool_ranges,
    validate_ranges_within_attribute,
    validate_shorthand_target,
)
from infrahub.pools.number_ranges import NumberDomain

UNBOUNDED = NumberDomain()
LIMITS = NumberDomain(lower=10, upper=100)
STORED = [NumberRangeBounds(start=100, end=200, id="low"), NumberRangeBounds(start=300, end=400, id="high")]


@dataclass
class CandidateCase:
    name: str
    candidate: NumberRangeBounds


ACCEPTED_CANDIDATE_CASES: list[CandidateCase] = [
    CandidateCase(name="fills_the_gap_exactly", candidate=NumberRangeBounds(start=201, end=299)),
    CandidateCase(name="single_value", candidate=NumberRangeBounds(start=250, end=250)),
    CandidateCase(name="resized_over_its_own_bounds", candidate=NumberRangeBounds(start=100, end=250, id="low")),
    CandidateCase(name="open_start_below_every_range", candidate=NumberRangeBounds(start=None, end=99)),
    CandidateCase(name="open_end_above_every_range", candidate=NumberRangeBounds(start=401, end=None)),
]


@pytest.mark.parametrize("case", ACCEPTED_CANDIDATE_CASES, ids=lambda case: case.name)
def test_range_within_free_space_is_accepted(case: CandidateCase) -> None:
    with does_not_raise():
        validate_number_pool_range(candidate=case.candidate, others=STORED, domain=UNBOUNDED)


@dataclass
class RefusedCandidateCase:
    name: str
    candidate: NumberRangeBounds
    message: str
    domain: NumberDomain = UNBOUNDED


REFUSED_CANDIDATE_CASES: list[RefusedCandidateCase] = [
    RefusedCandidateCase(
        name="shares_an_end",
        candidate=NumberRangeBounds(start=200, end=250),
        message="Range 200 - 250 overlaps 100 - 200 (low)",
    ),
    RefusedCandidateCase(
        name="shares_a_start",
        candidate=NumberRangeBounds(start=250, end=300),
        message="Range 250 - 300 overlaps 300 - 400 (high)",
    ),
    RefusedCandidateCase(
        name="covers_both",
        candidate=NumberRangeBounds(start=50, end=500),
        message="Range 50 - 500 overlaps 100 - 200 (low), 300 - 400 (high)",
    ),
    RefusedCandidateCase(
        name="backwards",
        candidate=NumberRangeBounds(start=300, end=200),
        message="Range end (200) cannot be lower than start (300)",
    ),
    RefusedCandidateCase(
        name="open_start_reaches_a_range",
        candidate=NumberRangeBounds(start=None, end=150),
        message="Range 1 - 150 overlaps 100 - 200 (low)",
    ),
    RefusedCandidateCase(
        name="open_end_reaches_a_range",
        candidate=NumberRangeBounds(start=350, end=None),
        message="Range 350 - MAX overlaps 300 - 400 (high)",
    ),
    RefusedCandidateCase(
        name="fully_open_covers_both",
        candidate=NumberRangeBounds(start=None, end=None),
        message="Range 1 - MAX overlaps 100 - 200 (low), 300 - 400 (high)",
    ),
    RefusedCandidateCase(
        name="open_start_reads_as_min_value",
        candidate=NumberRangeBounds(start=None, end=150),
        domain=NumberDomain(lower=50, upper=4094),
        message="Range 50 - 150 overlaps 100 - 200 (low)",
    ),
    RefusedCandidateCase(
        name="open_end_reads_as_max_value",
        candidate=NumberRangeBounds(start=350, end=None),
        domain=NumberDomain(lower=50, upper=4094),
        message="Range 350 - 4094 overlaps 300 - 400 (high)",
    ),
    RefusedCandidateCase(
        name="open_start_reads_above_its_end",
        candidate=NumberRangeBounds(start=None, end=0),
        message="Range end (0) cannot be lower than start (1)",
    ),
]


@pytest.mark.parametrize("case", REFUSED_CANDIDATE_CASES, ids=lambda case: case.name)
def test_backwards_or_overlapping_range_is_refused(case: RefusedCandidateCase) -> None:
    with pytest.raises(ValidationError) as exc_info:
        validate_number_pool_range(candidate=case.candidate, others=STORED, domain=case.domain)

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
        validate_number_pool_ranges(ranges=case.ranges, domain=UNBOUNDED)


def test_range_set_with_an_overlap_is_refused_from_its_lowest_range() -> None:
    ranges = [*STORED, NumberRangeBounds(start=150, end=320, id="middle")]

    with pytest.raises(ValidationError) as exc_info:
        validate_number_pool_ranges(ranges=ranges, domain=UNBOUNDED)

    assert exc_info.value.message == "Range 100 - 200 overlaps 150 - 320 (middle)"


SHORTHAND_TARGET_CASES: list[RangeSetCase] = [
    RangeSetCase(name="no_range", ranges=[]),
    RangeSetCase(name="one_range", ranges=STORED[:1]),
]


@pytest.mark.parametrize("case", SHORTHAND_TARGET_CASES, ids=lambda case: case.name)
def test_shorthand_applies_to_a_pool_holding_at_most_one_range(case: RangeSetCase) -> None:
    with does_not_raise():
        validate_shorthand_target(ranges=case.ranges, domain=UNBOUNDED)


def test_shorthand_on_a_pool_holding_several_ranges_is_refused_listing_them() -> None:
    with pytest.raises(ValidationError) as exc_info:
        validate_shorthand_target(ranges=list(reversed(STORED)), domain=UNBOUNDED)

    assert exc_info.value.message == (
        "start_range/end_range apply to a pool holding at most one range; "
        "this pool holds: 100 - 200 (low), 300 - 400 (high). Edit the ranges instead."
    )


def test_shorthand_refusal_lists_open_bounds_through_the_attribute_limits() -> None:
    ranges = [NumberRangeBounds(start=300, end=None, id="high"), NumberRangeBounds(start=None, end=200, id="low")]

    with pytest.raises(ValidationError) as exc_info:
        validate_shorthand_target(ranges=ranges, domain=NumberDomain(lower=10, upper=4094))

    assert exc_info.value.message == (
        "start_range/end_range apply to a pool holding at most one range; "
        "this pool holds: 10 - 200 (low), 300 - 4094 (high). Edit the ranges instead."
    )


def test_a_range_overlaps_a_stored_range_with_both_bounds_open() -> None:
    with pytest.raises(ValidationError) as exc_info:
        validate_number_pool_range(
            candidate=NumberRangeBounds(start=5, end=5),
            others=[NumberRangeBounds(start=None, end=None, id="open")],
            domain=UNBOUNDED,
        )

    assert exc_info.value.message == "Range 5 - 5 overlaps 1 - MAX (open)"


@dataclass
class AttributeLimitsCase:
    name: str
    bounds: NumberRangeBounds
    domain: NumberDomain = LIMITS


ACCEPTED_LIMITS_CASES: list[AttributeLimitsCase] = [
    AttributeLimitsCase(name="entered_bounds_on_the_limits", bounds=NumberRangeBounds(start=10, end=100)),
    AttributeLimitsCase(name="both_bounds_open", bounds=NumberRangeBounds(start=None, end=None)),
    AttributeLimitsCase(name="open_start_follows_min_value", bounds=NumberRangeBounds(start=None, end=10)),
    AttributeLimitsCase(name="open_end_follows_max_value", bounds=NumberRangeBounds(start=100, end=None)),
    AttributeLimitsCase(name="no_limits", bounds=NumberRangeBounds(start=-5, end=5000), domain=UNBOUNDED),
]


@pytest.mark.parametrize("case", ACCEPTED_LIMITS_CASES, ids=lambda case: case.name)
def test_a_range_within_the_attribute_limits_is_accepted(case: AttributeLimitsCase) -> None:
    with does_not_raise():
        validate_ranges_within_attribute(ranges=[case.bounds], domain=case.domain)


@dataclass
class RefusedLimitsCase:
    name: str
    bounds: NumberRangeBounds
    message: str


REFUSED_LIMITS_CASES: list[RefusedLimitsCase] = [
    RefusedLimitsCase(
        name="entered_start_below_min_value",
        bounds=NumberRangeBounds(start=9, end=50),
        message="Range 9 - 50 starts below the attribute's min_value (10)",
    ),
    RefusedLimitsCase(
        name="entered_end_above_max_value",
        bounds=NumberRangeBounds(start=50, end=101),
        message="Range 50 - 101 ends above the attribute's max_value (100)",
    ),
    RefusedLimitsCase(
        name="entered_start_below_min_value_with_an_open_end",
        bounds=NumberRangeBounds(start=9, end=None),
        message="Range 9 - 100 starts below the attribute's min_value (10)",
    ),
    RefusedLimitsCase(
        name="entered_end_above_max_value_with_an_open_start",
        bounds=NumberRangeBounds(start=None, end=101),
        message="Range 10 - 101 ends above the attribute's max_value (100)",
    ),
    RefusedLimitsCase(
        name="open_end_with_start_above_max_value",
        bounds=NumberRangeBounds(start=101, end=None),
        message="Range starting at 101 without an end starts above the attribute's max_value (100)",
    ),
    RefusedLimitsCase(
        name="open_start_with_end_below_min_value",
        bounds=NumberRangeBounds(start=None, end=9),
        message="Range ending at 9 without a start ends below the attribute's min_value (10)",
    ),
]


@pytest.mark.parametrize("case", REFUSED_LIMITS_CASES, ids=lambda case: case.name)
def test_a_range_outside_the_attribute_limits_is_refused_naming_the_bound(case: RefusedLimitsCase) -> None:
    with pytest.raises(ValidationError) as exc_info:
        validate_ranges_within_attribute(ranges=[case.bounds], domain=LIMITS)

    assert exc_info.value.message == case.message


def test_ranges_outside_the_attribute_limits_are_all_refused_from_the_lowest_range() -> None:
    ranges = [NumberRangeBounds(start=101, end=None, id="above"), NumberRangeBounds(start=None, end=9, id="below")]

    with pytest.raises(ValidationError) as exc_info:
        validate_ranges_within_attribute(ranges=ranges, domain=LIMITS)

    assert exc_info.value.message == (
        "Range ending at 9 without a start ends below the attribute's min_value (10); "
        "Range starting at 101 without an end starts above the attribute's max_value (100)"
    )


def test_a_range_outside_both_attribute_limits_is_refused_naming_both_bounds() -> None:
    bounds = NumberRangeBounds(start=9, end=101)

    with pytest.raises(ValidationError) as exc_info:
        validate_ranges_within_attribute(ranges=[bounds], domain=LIMITS)

    assert exc_info.value.message == (
        "Range 9 - 101 starts below the attribute's min_value (10); "
        "Range 9 - 101 ends above the attribute's max_value (100)"
    )


SUPPORTED_NUMBERS = "outside the supported numbers (-9223372036854775807 to 9223372036854775807)"


ACCEPTED_SUPPORTED_SPACE_CASES: list[AttributeLimitsCase] = [
    AttributeLimitsCase(
        name="end_on_the_largest_supported_number",
        bounds=NumberRangeBounds(start=700, end=9223372036854775807),
        domain=UNBOUNDED,
    ),
    AttributeLimitsCase(
        name="start_on_the_smallest_supported_number",
        bounds=NumberRangeBounds(start=-9223372036854775807, end=10),
        domain=UNBOUNDED,
    ),
    AttributeLimitsCase(
        name="weight_on_the_largest_supported_number",
        bounds=NumberRangeBounds(start=700, end=800, weight=9223372036854775807),
        domain=UNBOUNDED,
    ),
    AttributeLimitsCase(
        name="weight_on_the_smallest_supported_number",
        bounds=NumberRangeBounds(start=700, end=800, weight=-9223372036854775807),
        domain=UNBOUNDED,
    ),
]


@pytest.mark.parametrize("case", ACCEPTED_SUPPORTED_SPACE_CASES, ids=lambda case: case.name)
def test_a_range_on_the_supported_limits_is_accepted(case: AttributeLimitsCase) -> None:
    with does_not_raise():
        validate_ranges_within_attribute(ranges=[case.bounds], domain=case.domain)


REFUSED_SUPPORTED_SPACE_CASES: list[RefusedLimitsCase] = [
    RefusedLimitsCase(
        name="end_above_the_largest_supported_number",
        bounds=NumberRangeBounds(start=700, end=9223372036854775808),
        message=f"Range 700 - 9223372036854775808 has end 9223372036854775808 {SUPPORTED_NUMBERS}",
    ),
    RefusedLimitsCase(
        name="end_sent_by_a_javascript_client",
        bounds=NumberRangeBounds(start=700, end=9223372036854776000),
        message=f"Range 700 - 9223372036854776000 has end 9223372036854776000 {SUPPORTED_NUMBERS}",
    ),
    RefusedLimitsCase(
        name="start_on_the_64_bit_minimum",
        bounds=NumberRangeBounds(start=-9223372036854775808, end=10),
        message=f"Range -9223372036854775808 - 10 has start -9223372036854775808 {SUPPORTED_NUMBERS}",
    ),
    RefusedLimitsCase(
        name="start_above_the_largest_supported_number_with_an_open_end",
        bounds=NumberRangeBounds(start=9223372036854775808, end=None),
        message=f"Range 9223372036854775808 - MAX has start 9223372036854775808 {SUPPORTED_NUMBERS}",
    ),
    RefusedLimitsCase(
        name="weight_above_the_largest_supported_number",
        bounds=NumberRangeBounds(start=700, end=800, weight=9223372036854775808),
        message=f"Range 700 - 800 has allocation_weight 9223372036854775808 {SUPPORTED_NUMBERS}",
    ),
    RefusedLimitsCase(
        name="weight_on_the_64_bit_minimum",
        bounds=NumberRangeBounds(start=700, end=800, weight=-9223372036854775808),
        message=f"Range 700 - 800 has allocation_weight -9223372036854775808 {SUPPORTED_NUMBERS}",
    ),
]


@pytest.mark.parametrize("case", REFUSED_SUPPORTED_SPACE_CASES, ids=lambda case: case.name)
def test_a_range_outside_the_supported_numbers_is_refused_without_attribute_limits(case: RefusedLimitsCase) -> None:
    with pytest.raises(ValidationError) as exc_info:
        validate_ranges_within_attribute(ranges=[case.bounds], domain=UNBOUNDED)

    assert exc_info.value.message == case.message


def test_a_range_outside_the_supported_numbers_and_the_attribute_limits_is_refused_naming_both() -> None:
    bounds = NumberRangeBounds(start=50, end=9223372036854775808, weight=9223372036854775808)

    with pytest.raises(ValidationError) as exc_info:
        validate_ranges_within_attribute(ranges=[bounds], domain=LIMITS)

    assert exc_info.value.message == (
        f"Range 50 - 9223372036854775808 has end 9223372036854775808 {SUPPORTED_NUMBERS}; "
        f"Range 50 - 9223372036854775808 has allocation_weight 9223372036854775808 {SUPPORTED_NUMBERS}; "
        "Range 50 - 9223372036854775808 ends above the attribute's max_value (100)"
    )
