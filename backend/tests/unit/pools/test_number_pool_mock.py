from __future__ import annotations

from dataclasses import replace

import pytest

from infrahub.core.query.resource_manager import PoolRecordProvenance
from infrahub.exceptions import ValidationError
from infrahub.pools import number_pool_mock
from infrahub.pools.number_pool_mock import (
    SCOPED_POOL,
    UNSCOPED_POOL,
    UNSCOPED_POOL_ID,
    DivisionFilterEntry,
    MockDivisionEntry,
    MockFigures,
    MockPool,
    get_allocations,
    get_divisions,
    get_utilization,
)

SCOPED_POOL_ID = "any-pool-id"
SITE_A, SITE_B, SITE_C, SITE_D = (entries[0].value for entries in SCOPED_POOL.divisions)
SECOND_RANGE = SCOPED_POOL.ranges[1].id
UNSCOPED_SECOND_RANGE = UNSCOPED_POOL.ranges[1].id


def _counts(figures: MockFigures) -> tuple[int, int, int, int]:
    return figures.size, figures.used, figures.used_default_branch, figures.used_branches


def _site_filter(*sites: str) -> list[DivisionFilterEntry]:
    return [DivisionFilterEntry(path="site", value=site) for site in sites]


def test_scoped_utilization_requires_a_division() -> None:
    with pytest.raises(ValidationError) as exc:
        get_utilization(pool_id=SCOPED_POOL_ID, request_branch="main")

    assert exc.value.message == (
        f"The pool {SCOPED_POOL_ID} has an allocation scope in force on branch main; "
        "give a division to read its utilization"
    )


def test_scoped_utilization_of_one_division_describes_the_pool_and_its_ranges() -> None:
    utilization = get_utilization(pool_id=SCOPED_POOL_ID, request_branch="main", division=_site_filter(SITE_B))

    assert utilization.id == SCOPED_POOL_ID
    assert utilization.display_label == "Device index"
    assert utilization.allocation_scope == ("site",)
    assert utilization.figures.utilization == 30.0
    assert [(item.display_label, item.weight) for item in utilization.ranges] == [("1 - 50", 10), ("51 - 100", 0)]
    assert utilization.ranges[1].figures.utilization == 60.0


def test_scoped_divisions_list_only_the_divisions_holding_a_value() -> None:
    divisions = get_divisions(pool_id=SCOPED_POOL_ID)

    assert SITE_D not in {item.entries[0].value for item in divisions.divisions}

    assert divisions.count == 3
    assert divisions.allocation_scope == ("site",)
    assert [(item.display_label, _counts(item.figures)) for item in divisions.divisions] == [
        ("Site A", (100, 40, 40, 0)),
        ("Site B", (100, 30, 27, 3)),
        ("Site C", (100, 1, 0, 1)),
    ]
    entry = divisions.divisions[0].entries[0]
    assert (entry.path, entry.value, entry.peer_kind) == ("site", SITE_A, "LocationSite")


@pytest.mark.parametrize(
    ("site", "pool_counts", "range_counts"),
    [
        pytest.param(SITE_A, (100, 40, 40, 0), [(50, 40, 40, 0), (50, 0, 0, 0)], id="site-a"),
        pytest.param(SITE_B, (100, 30, 27, 3), [(50, 0, 0, 0), (50, 30, 27, 3)], id="site-b"),
        pytest.param(SITE_C, (100, 1, 0, 1), [(50, 1, 0, 1), (50, 0, 0, 0)], id="site-c"),
        pytest.param("nope", (100, 0, 0, 0), [(50, 0, 0, 0), (50, 0, 0, 0)], id="unknown-site"),
    ],
)
def test_utilization_of_one_division_over_the_pool_and_each_range(
    site: str,
    pool_counts: tuple[int, int, int, int],
    range_counts: list[tuple[int, int, int, int]],
) -> None:
    utilization = get_utilization(pool_id=SCOPED_POOL_ID, request_branch="main", division=_site_filter(site))

    assert _counts(utilization.figures) == pool_counts
    assert [_counts(item.figures) for item in utilization.ranges] == range_counts


def test_utilization_of_a_division_matches_its_divisions_row() -> None:
    for division in get_divisions(pool_id=SCOPED_POOL_ID).divisions:
        utilization = get_utilization(
            pool_id=SCOPED_POOL_ID, request_branch="main", division=_site_filter(division.entries[0].value)
        )

        assert utilization.figures == division.figures


def test_division_used_figures_count_a_shared_value_in_each_division() -> None:
    divisions = {item.display_label: item.figures.used for item in get_divisions(pool_id=SCOPED_POOL_ID).divisions}
    distinct_values = {row.value for row in SCOPED_POOL.rows}

    assert sum(divisions.values()) == len(distinct_values) + 1


def test_division_filter_keeps_every_row_of_a_holder_in_the_division_on_any_branch() -> None:
    allocations = get_allocations(pool_id=SCOPED_POOL_ID, request_branch="main", division=_site_filter(SITE_A), limit=2)

    assert allocations.count == 41
    assert [(row.value, row.branch, row.holder.display_label) for row in allocations.allocations] == [
        (1, "main", "D0"),
        (5, "branch1", "D1"),
    ]


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
            pool_id=SCOPED_POOL_ID, request_branch="main", division=_site_filter(site), limit=1000
        ).allocations
        listed = {(row.value, row.branch, row.holder.id) for row in rows}
        own = {(row.value, row.branch, row.holder.id) for row in SCOPED_POOL.rows if row.division == division.entries}

        assert own <= listed
        assert len({value for value, _, _ in own}) == division.figures.used


def test_range_filter_returns_the_values_the_range_holds() -> None:
    allocations = get_allocations(pool_id=SCOPED_POOL_ID, request_branch="main", range_id=SECOND_RANGE, limit=1000)

    assert allocations.count == 30
    assert all(51 <= row.value <= 100 for row in allocations.allocations)


def test_unscoped_range_filter_returns_the_rows_of_that_range() -> None:
    allocations = get_allocations(pool_id=UNSCOPED_POOL_ID, request_branch="main", range_id=UNSCOPED_POOL.ranges[0].id)

    assert allocations.count == 2
    assert [(row.value, row.branch, row.range.display_label) for row in allocations.allocations] == [
        (1, "main", "1 - 50"),
        (7, "branch1", "1 - 50"),
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

    assert [row.value for row in allocations.allocations] == [51]


def test_filters_combine_with_and() -> None:
    allocations = get_allocations(
        pool_id=SCOPED_POOL_ID,
        request_branch="main",
        division=_site_filter(SITE_B),
        provenance=PoolRecordProvenance.PROVIDED,
    )

    assert [row.value for row in allocations.allocations] == [51]


def test_pagination_counts_before_offset_and_limit() -> None:
    first_page = get_allocations(pool_id=SCOPED_POOL_ID, request_branch="main")
    second_page = get_allocations(pool_id=SCOPED_POOL_ID, request_branch="main", offset=10, limit=5)
    every_row = get_allocations(pool_id=SCOPED_POOL_ID, request_branch="main", limit=1000).allocations

    assert first_page.count == second_page.count == len(SCOPED_POOL.rows) == 71
    assert first_page.allocations == every_row[:10]
    assert second_page.allocations == every_row[10:15]


def test_rows_are_ordered_by_value_then_branch_then_holder() -> None:
    rows = get_allocations(pool_id=SCOPED_POOL_ID, request_branch="main", limit=1000).allocations

    keys = [(row.value, row.branch, row.holder.id) for row in rows]
    assert keys == sorted(keys)


def test_unscoped_pool_figures_and_single_division() -> None:
    utilization = get_utilization(pool_id=UNSCOPED_POOL_ID, request_branch="main")
    divisions = get_divisions(pool_id=UNSCOPED_POOL_ID)

    assert utilization.allocation_scope == ()
    assert _counts(utilization.figures) == (99, 3, 2, 1)
    assert [_counts(item.figures) for item in utilization.ranges] == [(50, 2, 1, 1), (50, 1, 1, 0)]
    assert [(item.display_label, item.entries, item.figures) for item in divisions.divisions] == [
        ("", (), utilization.figures)
    ]


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
    with pytest.raises(ValidationError) as allocations_exc:
        get_allocations(pool_id=pool_id, request_branch="main", division=division)
    with pytest.raises(ValidationError) as utilization_exc:
        get_utilization(pool_id=pool_id, request_branch="main", division=division)

    assert allocations_exc.value.message == utilization_exc.value.message == message


def _two_entry_pool() -> MockPool:
    site = MockDivisionEntry(path="site", value="site-a", display_label="Site A", peer_kind="LocationSite")
    tenant = MockDivisionEntry(
        path="tenant", value="tenant-x", display_label="Tenant X", peer_kind="OrganizationTenant"
    )
    return MockPool(
        display_label="Device index per tenant",
        allocation_scope=("site", "tenant"),
        ranges=UNSCOPED_POOL.ranges,
        excluded_values=frozenset(),
        divisions=((site, tenant),),
        rows=(),
    )


def test_utilization_refuses_a_division_that_omits_an_entry(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(number_pool_mock, "get_mock_pool", lambda pool_id: _two_entry_pool())  # noqa: ARG005
    partial = [DivisionFilterEntry(path="site", value="site-a")]

    with pytest.raises(ValidationError) as exc:
        get_utilization(pool_id=SCOPED_POOL_ID, request_branch="main", division=partial)

    assert exc.value.message == (
        "The division filter must give a value for every allocation scope entry in force on branch main; "
        "missing: tenant"
    )
    assert get_allocations(pool_id=SCOPED_POOL_ID, request_branch="main", division=partial).count == 0


def test_unknown_range_is_refused_by_allocations() -> None:
    with pytest.raises(ValidationError) as exc:
        get_allocations(pool_id=SCOPED_POOL_ID, request_branch="main", range_id=UNSCOPED_SECOND_RANGE)

    assert exc.value.message == (
        f"The selected pool_id={SCOPED_POOL_ID} doesn't contain the requested range_id={UNSCOPED_SECOND_RANGE}"
    )


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

    assert (allocations.count, allocations.allocations) == (71, ())


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


@pytest.mark.parametrize(
    "value",
    [
        pytest.param(40, id="excluded-value"),
        pytest.param(500, id="value-held-by-no-range"),
    ],
)
def test_a_pool_holding_a_value_it_cannot_allocate_is_refused(value: int) -> None:
    with pytest.raises(ValueError, match=f"holds {value}, a value it cannot allocate"):
        MockPool(
            display_label="VLANs",
            allocation_scope=(),
            ranges=UNSCOPED_POOL.ranges,
            excluded_values=frozenset({40}),
            divisions=((),),
            rows=(replace(UNSCOPED_POOL.rows[0], value=value),),
        )
