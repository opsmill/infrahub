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
    expected: list[tuple[int | None, int | None, int | None]]
    """Each effective range as (start, end, weight)."""


EFFECTIVE_RANGES_TEST_CASES: list[EffectiveRangesTestCase] = [
    EffectiveRangesTestCase(
        name="both_shorthand_bounds_yield_one_range",
        parameters={"start_range": 100, "end_range": 200},
        expected=[(100, 200, None)],
    ),
    EffectiveRangesTestCase(
        name="start_only_leaves_the_end_open",
        parameters={"start_range": 100},
        expected=[(100, None, None)],
    ),
    EffectiveRangesTestCase(
        name="end_only_leaves_the_start_open",
        parameters={"end_range": 200},
        expected=[(None, 200, None)],
    ),
    EffectiveRangesTestCase(
        name="neither_spelling_yields_one_range_open_at_both_ends",
        parameters={},
        expected=[(None, None, None)],
    ),
    EffectiveRangesTestCase(
        name="explicitly_empty_range_list_yields_no_range",
        parameters={"ranges": []},
        expected=[],
    ),
    EffectiveRangesTestCase(
        name="open_ranges_ordered_by_resolved_start",
        parameters={"ranges": [{"start": 205}, {"end": 200, "weight": 10}]},
        expected=[(None, 200, 10), (205, None, None)],
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
        name="range_end_below_its_open_start",
        parameters={"ranges": [{"end": 0}]},
        message=r"Range end \(0\) cannot be lower than start \(1\)",
    ),
    RefusedDeclarationTestCase(
        name="open_ranges_overlapping_named_with_min_and_max",
        parameters={"ranges": [{"start": 100}, {"end": 150}]},
        message="Range 1 - 150 overlaps 100 - MAX",
    ),
    RefusedDeclarationTestCase(
        name="range_start_above_end",
        parameters={"ranges": [{"start": 300, "end": 200}]},
        message=r"Range end \(200\) cannot be lower than start \(300\)",
    ),
    RefusedDeclarationTestCase(
        name="overlapping_ranges_named",
        parameters={"ranges": [{"start": 150, "end": 250}, {"start": 100, "end": 200}]},
        message="Range 100 - 200 overlaps 150 - 250",
    ),
    RefusedDeclarationTestCase(
        name="ranges_sharing_an_edge_overlap",
        parameters={"ranges": [{"start": 100, "end": 200}, {"start": 200, "end": 300}]},
        message="Range 100 - 200 overlaps 200 - 300",
    ),
    RefusedDeclarationTestCase(
        name="range_overlapping_two_others_names_both",
        parameters={"ranges": [{"start": 300, "end": 350}, {"start": 100, "end": 400}, {"start": 150, "end": 200}]},
        message="Range 100 - 400 overlaps 150 - 200, 300 - 350",
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
    assert NumberPoolParameters(ranges=[]).get_pool_size() == 0


@dataclass
class OpenPoolSizeTestCase:
    name: str
    parameters: dict[str, Any]
    expected: int


OPEN_POOL_SIZE_TEST_CASES: list[OpenPoolSizeTestCase] = [
    OpenPoolSizeTestCase(name="nothing_declared", parameters={}, expected=sys.maxsize),
    OpenPoolSizeTestCase(name="start_only_shorthand", parameters={"start_range": 101}, expected=sys.maxsize - 100),
    OpenPoolSizeTestCase(name="open_start_range", parameters={"ranges": [{"end": 50}]}, expected=50),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in OPEN_POOL_SIZE_TEST_CASES])
def test_pool_size_counts_an_open_bound_from_one_or_up_to_the_largest_number(test_case: OpenPoolSizeTestCase) -> None:
    assert NumberPoolParameters(**test_case.parameters).get_pool_size() == test_case.expected


def test_hash_of_a_range_with_open_bounds_is_stable_and_differs_from_the_resolved_bounds() -> None:
    open_end = NumberPoolRangeParameters(start=205)
    open_start = NumberPoolRangeParameters(end=200, weight=10)
    first = NumberPoolParameters(ranges=[open_end, open_start])
    second = NumberPoolParameters(ranges=[open_start.duplicate(), open_end.duplicate()])
    resolved = NumberPoolParameters(
        ranges=[
            NumberPoolRangeParameters(start=205, end=sys.maxsize),
            NumberPoolRangeParameters(start=1, end=200, weight=10),
        ]
    )

    assert first.get_hash() == second.get_hash()
    assert first.get_hash() != resolved.get_hash()


@dataclass
class RangeDeclarationDiffTestCase:
    name: str
    current: dict[str, Any]
    new: dict[str, Any]
    expected_changed: set[str]
    """The NumberPool parameters the diff reports as changed."""


RANGE_DECLARATION_DIFF_TEST_CASES: list[RangeDeclarationDiffTestCase] = [
    RangeDeclarationDiffTestCase(
        name="nothing_declared_to_empty_range_list", current={}, new={"ranges": []}, expected_changed={"ranges"}
    ),
    RangeDeclarationDiffTestCase(
        name="empty_range_list_to_nothing_declared", current={"ranges": []}, new={}, expected_changed={"ranges"}
    ),
    RangeDeclarationDiffTestCase(
        name="empty_range_list_unchanged", current={"ranges": []}, new={"ranges": []}, expected_changed=set()
    ),
    RangeDeclarationDiffTestCase(name="nothing_declared_unchanged", current={}, new={}, expected_changed=set()),
    RangeDeclarationDiffTestCase(
        name="empty_range_list_to_ranges",
        current={"ranges": []},
        new={"ranges": [{"start": 1, "end": 100}]},
        expected_changed={"ranges"},
    ),
    RangeDeclarationDiffTestCase(
        name="shorthand_to_empty_range_list",
        current={"start_range": 40, "end_range": 60},
        new={"ranges": []},
        expected_changed={"start_range", "end_range", "ranges"},
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in RANGE_DECLARATION_DIFF_TEST_CASES])
def test_diff_of_range_declarations(test_case: RangeDeclarationDiffTestCase) -> None:
    current = NumberPoolParameters(**test_case.current)
    new = NumberPoolParameters(**test_case.new)

    assert set(new.diff(other=current).changed) == test_case.expected_changed
    assert set(current.diff(other=new).changed) == test_case.expected_changed


def _declared(
    parameters: NumberPoolParameters,
) -> tuple[int | None, int | None, list[tuple[int | None, int | None, int | None]] | None]:
    if parameters.ranges is None:
        return parameters.start_range, parameters.end_range, None
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

    assert _declared(current) == (40, 60, None)


def test_update_with_a_single_bound_shorthand_leaves_the_other_bound_open() -> None:
    current = NumberPoolParameters(start_range=40, end_range=60)

    current.update(NumberPoolParameters(start_range=50))

    assert [pool_range.label for pool_range in current.effective_ranges()] == ["50 - MAX"]


def test_update_with_ranges_replaces_the_previous_ranges() -> None:
    current = NumberPoolParameters(ranges=[NumberPoolRangeParameters(start=1, end=100)])

    current.update(
        NumberPoolParameters(
            ranges=[NumberPoolRangeParameters(start=45, end=55), NumberPoolRangeParameters(start=70, end=80, weight=5)]
        )
    )

    assert _declared(current) == (None, None, [(45, 55, None), (70, 80, 5)])


@dataclass
class ZeroRangeUpdateTestCase:
    name: str
    current: dict[str, Any]


ZERO_RANGE_UPDATE_TEST_CASES: list[ZeroRangeUpdateTestCase] = [
    ZeroRangeUpdateTestCase(name="shorthand_removed", current={"start_range": 40, "end_range": 60}),
    ZeroRangeUpdateTestCase(name="ranges_removed", current={"ranges": [{"start": 45, "end": 55}]}),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in ZERO_RANGE_UPDATE_TEST_CASES])
def test_update_with_an_explicitly_empty_range_list_removes_every_range(test_case: ZeroRangeUpdateTestCase) -> None:
    current = NumberPoolParameters(**test_case.current)

    current.update(NumberPoolParameters(ranges=[]))

    assert _declared(current) == (None, None, [])
    assert current.effective_ranges() == []


def test_zero_range_declaration_survives_a_dump_and_a_parse() -> None:
    # A schema merged from several files is dumped and parsed again before it is applied.
    declaration = NumberPoolParameters(ranges=[])

    reparsed = NumberPoolParameters.model_validate(declaration.model_dump())

    assert reparsed.ranges == []


@dataclass
class DumpedRangeFieldsTestCase:
    name: str
    parameters: dict[str, Any]
    expected: dict[str, Any]
    """The start_range, end_range and ranges keys present in the dump, with their values."""


DUMPED_RANGE_FIELDS_TEST_CASES: list[DumpedRangeFieldsTestCase] = [
    DumpedRangeFieldsTestCase(name="unset", parameters={}, expected={}),
    DumpedRangeFieldsTestCase(
        name="shorthand",
        parameters={"start_range": 40, "end_range": 60},
        expected={"start_range": 40, "end_range": 60},
    ),
    DumpedRangeFieldsTestCase(
        name="shorthand_with_an_empty_list",
        parameters={"start_range": 40, "ranges": []},
        expected={"start_range": 40},
    ),
    DumpedRangeFieldsTestCase(name="zero_ranges", parameters={"ranges": []}, expected={"ranges": []}),
    DumpedRangeFieldsTestCase(
        name="ranges",
        parameters={"ranges": [{"start": 45, "end": 55}]},
        expected={"ranges": [{"id": None, "state": "present", "start": 45, "end": 55, "weight": None}]},
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in DUMPED_RANGE_FIELDS_TEST_CASES])
def test_dump_keeps_only_the_declared_range_fields(test_case: DumpedRangeFieldsTestCase) -> None:
    dumped = NumberPoolParameters(**test_case.parameters).model_dump(mode="json")

    assert {key: dumped[key] for key in ("start_range", "end_range", "ranges") if key in dumped} == test_case.expected


def test_update_without_any_range_spelling_keeps_the_current_declaration() -> None:
    shorthand = NumberPoolParameters(start_range=40, end_range=60)
    explicit = NumberPoolParameters(ranges=[NumberPoolRangeParameters(start=45, end=55)])

    shorthand.update(NumberPoolParameters(number_pool_id="pool-id"))
    explicit.update(NumberPoolParameters(number_pool_id="pool-id"))

    assert _declared(shorthand) == (40, 60, None)
    assert _declared(explicit) == (None, None, [(45, 55, None)])
    assert shorthand.number_pool_id == explicit.number_pool_id == "pool-id"
