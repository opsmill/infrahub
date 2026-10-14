import sys
from dataclasses import dataclass
from typing import Any

import pydantic
import pytest

from infrahub.core.schema.attribute_parameters import NumberPoolParameters, NumberPoolRangeParameters


@dataclass
class EffectiveRangesTestCase:
    name: str
    parameters: dict[str, Any]
    expected: list[tuple[int, int, int | None]]
    """Each effective range as (start, end, weight)."""


EFFECTIVE_RANGES_TEST_CASES: list[EffectiveRangesTestCase] = [
    EffectiveRangesTestCase(
        name="both_shorthand_bounds_yield_one_range",
        parameters={"start_range": 100, "end_range": 200},
        expected=[(100, 200, None)],
    ),
    EffectiveRangesTestCase(
        name="start_only_resolves_end_to_maxsize",
        parameters={"start_range": 100},
        expected=[(100, sys.maxsize, None)],
    ),
    EffectiveRangesTestCase(
        name="end_only_resolves_start_to_one",
        parameters={"end_range": 200},
        expected=[(1, 200, None)],
    ),
    EffectiveRangesTestCase(
        name="neither_spelling_yields_no_range",
        parameters={},
        expected=[],
    ),
    EffectiveRangesTestCase(
        name="explicit_ranges_kept_with_weights_ordered_by_start",
        parameters={"ranges": [{"start": 205, "end": 300}, {"start": 100, "end": 200, "weight": 10}]},
        expected=[(100, 200, 10), (205, 300, None)],
    ),
    EffectiveRangesTestCase(
        name="adjacent_ranges_accepted",
        parameters={"ranges": [{"start": 100, "end": 200}, {"start": 201, "end": 300}]},
        expected=[(100, 200, None), (201, 300, None)],
    ),
    EffectiveRangesTestCase(
        name="empty_ranges_list_with_shorthand_uses_shorthand",
        parameters={"start_range": 5, "end_range": 9, "ranges": []},
        expected=[(5, 9, None)],
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in EFFECTIVE_RANGES_TEST_CASES])
def test_effective_ranges(test_case: EffectiveRangesTestCase) -> None:
    parameters = NumberPoolParameters(**test_case.parameters)

    effective = [(pool_range.start, pool_range.end, pool_range.weight) for pool_range in parameters.effective_ranges()]

    assert effective == test_case.expected


@dataclass
class RefusedDeclarationTestCase:
    name: str
    parameters: dict[str, Any]
    message: str


REFUSED_DECLARATION_TEST_CASES: list[RefusedDeclarationTestCase] = [
    RefusedDeclarationTestCase(
        name="start_range_with_ranges",
        parameters={"start_range": 1, "ranges": [{"start": 100, "end": 200}]},
        message="start_range/end_range cannot be combined with ranges",
    ),
    RefusedDeclarationTestCase(
        name="end_range_with_ranges",
        parameters={"end_range": 50, "ranges": [{"start": 100, "end": 200}]},
        message="start_range/end_range cannot be combined with ranges",
    ),
    RefusedDeclarationTestCase(
        name="shorthand_start_above_end",
        parameters={"start_range": 30, "end_range": 25},
        message="`start_range` can't be less than `end_range`",
    ),
    RefusedDeclarationTestCase(
        name="shorthand_end_below_resolved_start",
        parameters={"end_range": 0},
        message="`start_range` can't be less than `end_range`",
    ),
    RefusedDeclarationTestCase(
        name="range_start_above_end",
        parameters={"ranges": [{"start": 300, "end": 200}]},
        message=r"Range end \(200\) cannot be lower than start \(300\)",
    ),
    RefusedDeclarationTestCase(
        name="overlapping_ranges_named",
        parameters={"ranges": [{"start": 150, "end": 250}, {"start": 100, "end": 200}]},
        message="Range 100-200 overlaps 150-250",
    ),
    RefusedDeclarationTestCase(
        name="ranges_sharing_an_edge_overlap",
        parameters={"ranges": [{"start": 100, "end": 200}, {"start": 200, "end": 300}]},
        message="Range 100-200 overlaps 200-300",
    ),
    RefusedDeclarationTestCase(
        name="range_overlapping_two_others_names_both",
        parameters={"ranges": [{"start": 300, "end": 350}, {"start": 100, "end": 400}, {"start": 150, "end": 200}]},
        message="Range 100-400 overlaps 150-200, 300-350",
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in REFUSED_DECLARATION_TEST_CASES])
def test_refused_declaration(test_case: RefusedDeclarationTestCase) -> None:
    with pytest.raises(pydantic.ValidationError, match=test_case.message):
        NumberPoolParameters(**test_case.parameters)


def test_pool_size_sums_effective_ranges() -> None:
    parameters = NumberPoolParameters(
        ranges=[NumberPoolRangeParameters(start=100, end=200), NumberPoolRangeParameters(start=205, end=300)]
    )

    assert parameters.get_pool_size() == 101 + 96


def test_pool_size_of_zero_ranges_is_zero() -> None:
    assert NumberPoolParameters().get_pool_size() == 0


def _declared(parameters: NumberPoolParameters) -> tuple[int | None, int | None, list[tuple[int, int, int | None]]]:
    return (
        parameters.start_range,
        parameters.end_range,
        [(pool_range.start, pool_range.end, pool_range.weight) for pool_range in parameters.ranges],
    )


def test_update_with_ranges_replaces_the_shorthand() -> None:
    current = NumberPoolParameters(start_range=40, end_range=60)

    current.update(NumberPoolParameters(ranges=[NumberPoolRangeParameters(start=45, end=55)]))

    assert _declared(current) == (None, None, [(45, 55, None)])


def test_update_with_the_shorthand_replaces_the_ranges() -> None:
    current = NumberPoolParameters(ranges=[NumberPoolRangeParameters(start=45, end=55)])

    current.update(NumberPoolParameters(start_range=40, end_range=60))

    assert _declared(current) == (40, 60, [])


def test_update_with_a_single_bound_shorthand_leaves_the_other_bound_to_its_default() -> None:
    current = NumberPoolParameters(start_range=40, end_range=60)

    current.update(NumberPoolParameters(start_range=50))

    assert [pool_range.label for pool_range in current.effective_ranges()] == [f"50-{sys.maxsize}"]


def test_update_with_ranges_replaces_the_previous_ranges() -> None:
    current = NumberPoolParameters(ranges=[NumberPoolRangeParameters(start=1, end=100)])

    current.update(
        NumberPoolParameters(
            ranges=[NumberPoolRangeParameters(start=45, end=55), NumberPoolRangeParameters(start=70, end=80, weight=5)]
        )
    )

    assert _declared(current) == (None, None, [(45, 55, None), (70, 80, 5)])


def test_update_without_any_range_spelling_keeps_the_current_declaration() -> None:
    shorthand = NumberPoolParameters(start_range=40, end_range=60)
    explicit = NumberPoolParameters(ranges=[NumberPoolRangeParameters(start=45, end=55)])

    shorthand.update(NumberPoolParameters(number_pool_id="pool-id"))
    explicit.update(NumberPoolParameters(number_pool_id="pool-id"))

    assert _declared(shorthand) == (40, 60, [])
    assert _declared(explicit) == (None, None, [(45, 55, None)])
    assert shorthand.number_pool_id == explicit.number_pool_id == "pool-id"
