from __future__ import annotations

import pytest

from infrahub.core.query.resource_manager import PoolRecordProvenance
from infrahub.exceptions import ValidationError
from infrahub.pools.number_pool_mock import (
    SCOPED_POOL,
    UNSCOPED_POOL,
    UNSCOPED_POOL_ID,
    DivisionFilterEntry,
    MockFigures,
    MockPool,
    get_allocations,
    get_divisions,
    get_utilization,
)

SCOPED_POOL_ID = "any-pool-id"
SITE_A, SITE_B, SITE_C = (entries[0].value for entries in SCOPED_POOL.divisions)
FIRST_RANGE, SECOND_RANGE = (item.id for item in SCOPED_POOL.ranges)
UNSCOPED_FIRST_RANGE, UNSCOPED_SECOND_RANGE = (item.id for item in UNSCOPED_POOL.ranges)


def _counts(figures: MockFigures) -> tuple[int, int, int, int]:
    return figures.size, figures.used, figures.used_default_branch, figures.used_branches


def _site_filter(*sites: str) -> list[DivisionFilterEntry]:
    return [DivisionFilterEntry(path="site", value=site) for site in sites]


def test_scoped_utilization_reports_the_fullest_division() -> None:
    utilization = get_utilization(pool_id=SCOPED_POOL_ID)

    assert utilization.id == SCOPED_POOL_ID
    assert utilization.allocation_scope == ("site",)
    assert _counts(utilization.figures) == (100, 40, 40, 0)
    assert utilization.figures.utilization == 40.0
    assert [(item.display_label, item.weight) for item in utilization.ranges] == [("1 - 50", 10), ("51 - 100", 0)]
    assert _counts(utilization.ranges[0].figures) == (50, 40, 40, 0)
    assert _counts(utilization.ranges[1].figures) == (50, 30, 27, 3)
    assert utilization.ranges[1].figures.utilization == 60.0
    assert utilization.out_of_space_count == 1


def test_scoped_divisions_over_the_whole_pool() -> None:
    divisions = get_divisions(pool_id=SCOPED_POOL_ID)

    assert divisions.count == 3
    assert divisions.allocation_scope == ("site",)
    assert [(item.display_label, _counts(item.figures)) for item in divisions.divisions] == [
        ("Site A", (100, 40, 40, 0)),
        ("Site B", (100, 30, 27, 3)),
        ("Site C", (100, 1, 0, 1)),
    ]
    entry = divisions.divisions[0].entries[0]
    assert (entry.path, entry.value, entry.peer_kind) == ("site", SITE_A, "LocationSite")


def test_scoped_divisions_restricted_to_one_range_sort_by_utilization() -> None:
    divisions = get_divisions(pool_id=SCOPED_POOL_ID, range_id=FIRST_RANGE)

    assert [(item.display_label, _counts(item.figures)) for item in divisions.divisions] == [
        ("Site A", (50, 40, 40, 0)),
        ("Site C", (50, 1, 0, 1)),
        ("Site B", (50, 0, 0, 0)),
    ]


def test_division_used_figures_count_a_shared_value_in_each_division() -> None:
    divisions = {item.display_label: item.figures.used for item in get_divisions(pool_id=SCOPED_POOL_ID).divisions}
    distinct_values = {row.value for row in SCOPED_POOL.rows if SCOPED_POOL.in_space(row.value)}

    assert sum(divisions.values()) == len(distinct_values) + 1


def test_division_filter_keeps_every_row_of_a_holder_in_the_division_on_any_branch() -> None:
    allocations = get_allocations(pool_id=SCOPED_POOL_ID, request_branch="main", division=_site_filter(SITE_A), limit=2)

    assert allocations.count == 41
    assert [(row.value, row.branch, row.holder.display_label) for row in allocations.allocations] == [
        (1, "main", "D0"),
        (5, "branch1", "D1"),
    ]
    assert allocations.allocations[1].division[0].value == SITE_C


def test_division_filter_on_site_c_returns_both_rows_of_the_moved_holder() -> None:
    allocations = get_allocations(pool_id=SCOPED_POOL_ID, request_branch="main", division=_site_filter(SITE_C))

    assert [(row.value, row.branch) for row in allocations.allocations] == [(5, "branch1"), (5, "main")]


def test_division_filter_with_an_unknown_value_returns_nothing() -> None:
    allocations = get_allocations(pool_id=SCOPED_POOL_ID, request_branch="main", division=_site_filter("nope"))

    assert (allocations.count, allocations.allocations) == (0, ())


def test_filtered_count_matches_the_division_rows() -> None:
    for division in get_divisions(pool_id=SCOPED_POOL_ID).divisions:
        site = division.entries[0].value
        rows = get_allocations(
            pool_id=SCOPED_POOL_ID, request_branch="main", division=_site_filter(site), in_space=True, limit=1000
        ).allocations
        own_rows = [row for row in rows if row.division == division.entries]

        assert len({row.value for row in own_rows}) == division.figures.used


def test_range_filter_returns_the_values_the_range_holds() -> None:
    allocations = get_allocations(pool_id=SCOPED_POOL_ID, request_branch="main", range_id=SECOND_RANGE, limit=1000)

    assert allocations.count == 30
    assert all(51 <= row.value <= 100 for row in allocations.allocations)


def test_in_space_filter_returns_the_out_of_space_rows() -> None:
    scoped = get_allocations(pool_id=SCOPED_POOL_ID, request_branch="main", in_space=False)
    unscoped = get_allocations(pool_id=UNSCOPED_POOL_ID, request_branch="main", in_space=False)

    assert [(row.value, row.range) for row in scoped.allocations] == [(500, None)]
    assert [(row.value, row.range.display_label if row.range else None) for row in unscoped.allocations] == [
        (40, "1 - 50"),
        (500, None),
    ]


def test_branch_filter_returns_the_rows_of_that_branch() -> None:
    allocations = get_allocations(pool_id=SCOPED_POOL_ID, request_branch="main", branch="branch1")

    assert [(row.value, row.holder.display_label) for row in allocations.allocations] == [
        (5, "D1"),
        (78, "B27"),
        (79, "B28"),
        (80, "B29"),
    ]
    assert get_allocations(pool_id=SCOPED_POOL_ID, request_branch="main", branch="unknown").count == 0


def test_provenance_filter_returns_the_provided_rows() -> None:
    allocations = get_allocations(
        pool_id=SCOPED_POOL_ID, request_branch="main", provenance=PoolRecordProvenance.PROVIDED
    )

    assert [row.value for row in allocations.allocations] == [51, 500]


def test_filters_combine_with_and() -> None:
    allocations = get_allocations(
        pool_id=SCOPED_POOL_ID,
        request_branch="main",
        division=_site_filter(SITE_B),
        provenance=PoolRecordProvenance.PROVIDED,
        in_space=True,
    )

    assert [row.value for row in allocations.allocations] == [51]


def test_pagination_counts_before_offset_and_limit() -> None:
    first_page = get_allocations(pool_id=SCOPED_POOL_ID, request_branch="main")
    second_page = get_allocations(pool_id=SCOPED_POOL_ID, request_branch="main", offset=10, limit=5)
    every_row = get_allocations(pool_id=SCOPED_POOL_ID, request_branch="main", limit=1000).allocations

    assert first_page.count == second_page.count == len(SCOPED_POOL.rows) == 72
    assert first_page.allocations == every_row[:10]
    assert second_page.allocations == every_row[10:15]


def test_rows_are_ordered_by_value_then_branch_then_holder() -> None:
    rows = get_allocations(pool_id=SCOPED_POOL_ID, request_branch="main", limit=1000).allocations

    keys = [(row.value, row.branch, row.holder.id) for row in rows]
    assert keys == sorted(keys)


def test_unscoped_pool_figures_and_single_division() -> None:
    utilization = get_utilization(pool_id=UNSCOPED_POOL_ID)
    divisions = get_divisions(pool_id=UNSCOPED_POOL_ID)
    range_divisions = get_divisions(pool_id=UNSCOPED_POOL_ID, range_id=UNSCOPED_FIRST_RANGE)

    assert utilization.allocation_scope == ()
    assert _counts(utilization.figures) == (99, 3, 2, 1)
    assert [_counts(item.figures) for item in utilization.ranges] == [(50, 2, 1, 1), (50, 1, 1, 0)]
    assert utilization.out_of_space_count == 2
    assert [(item.display_label, item.entries, item.figures) for item in divisions.divisions] == [
        ("", (), utilization.figures)
    ]
    assert range_divisions.divisions[0].figures == utilization.ranges[0].figures
    assert all(
        row.division == () for row in get_allocations(pool_id=UNSCOPED_POOL_ID, request_branch="main").allocations
    )


@pytest.mark.parametrize(
    ("pool_id", "division", "message"),
    [
        pytest.param(
            UNSCOPED_POOL_ID,
            _site_filter(SITE_A),
            "The pool mock-unscoped has no allocation scope in force on branch main; "
            "the division filter cannot be applied",
            id="unscoped-pool",
        ),
        pytest.param(
            SCOPED_POOL_ID,
            [DivisionFilterEntry(path="role", value="leaf")],
            "The division entry 'role' is not in the allocation scope in force on branch main",
            id="path-not-in-scope",
        ),
        pytest.param(
            SCOPED_POOL_ID,
            _site_filter(SITE_A, SITE_B),
            "The division entry 'site' is given twice",
            id="duplicate-path",
        ),
    ],
)
def test_division_filter_refusals(pool_id: str, division: list[DivisionFilterEntry], message: str) -> None:
    with pytest.raises(ValidationError) as exc:
        get_allocations(pool_id=pool_id, request_branch="main", division=division)

    assert exc.value.message == message


def test_unknown_range_is_refused_by_divisions_and_allocations() -> None:
    message = f"The selected pool_id={SCOPED_POOL_ID} doesn't contain the requested range_id={UNSCOPED_SECOND_RANGE}"

    with pytest.raises(ValidationError) as divisions_exc:
        get_divisions(pool_id=SCOPED_POOL_ID, range_id=UNSCOPED_SECOND_RANGE)
    with pytest.raises(ValidationError) as allocations_exc:
        get_allocations(pool_id=SCOPED_POOL_ID, request_branch="main", range_id=UNSCOPED_SECOND_RANGE)

    assert divisions_exc.value.message == allocations_exc.value.message == message


@pytest.mark.parametrize(
    ("offset", "limit", "message"),
    [
        pytest.param(-1, None, "offset must be 0 or greater", id="negative-offset"),
        pytest.param(None, -1, "limit must be 0 or greater", id="negative-limit"),
    ],
)
def test_negative_page_arguments_are_refused(offset: int | None, limit: int | None, message: str) -> None:
    with pytest.raises(ValidationError) as exc:
        get_allocations(pool_id=SCOPED_POOL_ID, request_branch="main", offset=offset, limit=limit)

    assert exc.value.message == message


def test_zero_offset_and_limit_return_an_empty_page_with_the_full_count() -> None:
    allocations = get_allocations(pool_id=SCOPED_POOL_ID, request_branch="main", offset=0, limit=0)

    assert (allocations.count, allocations.allocations) == (72, ())


def test_a_pool_without_any_division_is_refused() -> None:
    with pytest.raises(ValueError, match="needs at least one division"):
        MockPool(
            display_label="empty",
            allocation_scope=(),
            ranges=UNSCOPED_POOL.ranges,
            excluded_values=frozenset(),
            divisions=(),
            rows=(),
        )
