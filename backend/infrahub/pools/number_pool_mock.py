"""Fixed in-memory number-pool data served by the dedicated number-pool queries; reads nothing from the database."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from infrahub.core.query.resource_manager import PoolRecordProvenance
from infrahub.exceptions import ValidationError

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

UNSCOPED_POOL_ID = "mock-unscoped"
DEFAULT_BRANCH = "main"
OTHER_BRANCH = "branch1"
DEFAULT_OFFSET = 0
DEFAULT_LIMIT = 10


@dataclass(frozen=True, slots=True)
class MockDivisionEntry:
    path: str
    value: str
    display_label: str
    peer_kind: str | None


@dataclass(frozen=True, slots=True)
class MockRange:
    id: str
    display_label: str
    start: int
    end: int
    weight: int

    @property
    def size(self) -> int:
        return self.end - self.start + 1

    def holds(self, value: int) -> bool:
        return self.start <= value <= self.end


@dataclass(frozen=True, slots=True)
class MockRangeRef:
    id: str
    display_label: str


@dataclass(frozen=True, slots=True)
class MockHolder:
    id: str
    hfid: tuple[str, ...] | None
    kind: str
    display_label: str


@dataclass(frozen=True, slots=True)
class MockAllocation:
    value: int
    branch: str
    holder: MockHolder
    identifier: str | None
    provenance: PoolRecordProvenance
    in_space: bool
    range: MockRangeRef | None
    division: tuple[MockDivisionEntry, ...]


@dataclass(frozen=True, slots=True)
class MockFigures:
    size: int
    used: int
    used_default_branch: int
    used_branches: int
    utilization: float
    utilization_default_branch: float
    utilization_branches: float


@dataclass(frozen=True, slots=True)
class MockRangeUtilization:
    id: str
    display_label: str
    start: int
    end: int
    weight: int
    figures: MockFigures


@dataclass(frozen=True, slots=True)
class MockUtilization:
    id: str
    display_label: str
    allocation_scope: tuple[str, ...]
    figures: MockFigures
    ranges: tuple[MockRangeUtilization, ...]
    out_of_space_count: int


@dataclass(frozen=True, slots=True)
class MockDivision:
    display_label: str
    entries: tuple[MockDivisionEntry, ...]
    figures: MockFigures


@dataclass(frozen=True, slots=True)
class MockDivisions:
    count: int
    allocation_scope: tuple[str, ...]
    divisions: tuple[MockDivision, ...]


@dataclass(frozen=True, slots=True)
class MockAllocations:
    count: int
    allocations: tuple[MockAllocation, ...]


@dataclass(frozen=True, slots=True)
class DivisionFilterEntry:
    path: str
    value: str


@dataclass(frozen=True, slots=True)
class _Row:
    value: int
    branch: str
    holder: MockHolder
    provenance: PoolRecordProvenance = PoolRecordProvenance.ALLOCATED
    identifier: str | None = None
    division: tuple[MockDivisionEntry, ...] = ()


@dataclass(frozen=True, slots=True)
class MockPool:
    display_label: str
    allocation_scope: tuple[str, ...]
    ranges: tuple[MockRange, ...]
    excluded_values: frozenset[int]
    divisions: tuple[tuple[MockDivisionEntry, ...], ...]
    rows: tuple[_Row, ...] = field(repr=False)

    def __post_init__(self) -> None:
        if not self.divisions:
            raise ValueError(f"The mock pool {self.display_label} needs at least one division, even an empty one")

    @property
    def size(self) -> int:
        return sum(item.size for item in self.ranges) - len(
            {value for value in self.excluded_values if self.range_of(value) is not None}
        )

    def range_of(self, value: int) -> MockRange | None:
        return next((item for item in self.ranges if item.holds(value)), None)

    def in_space(self, value: int) -> bool:
        return self.range_of(value) is not None and value not in self.excluded_values


def _holder(number: int, label: str) -> MockHolder:
    return MockHolder(
        id=f"18a0c0de-0000-4000-8000-{number:012d}", hfid=(label,), kind="InfraDevice", display_label=label
    )


def _site(letter: str, number: int) -> tuple[MockDivisionEntry, ...]:
    return (
        MockDivisionEntry(
            path="site",
            value=f"18a0c0de-5173-4000-8000-{number:012d}",
            display_label=f"Site {letter}",
            peer_kind="LocationSite",
        ),
    )


def _two_ranges(prefix: str) -> tuple[MockRange, ...]:
    return (
        MockRange(id=f"18a0c0de-{prefix}-4000-8000-000000000001", display_label="1 - 50", start=1, end=50, weight=10),
        MockRange(
            id=f"18a0c0de-{prefix}-4000-8000-000000000002", display_label="51 - 100", start=51, end=100, weight=0
        ),
    )


def _build_scoped_pool() -> MockPool:
    site_a, site_b, site_c = _site("A", 1), _site("B", 2), _site("C", 3)
    rows: list[_Row] = []

    site_a_values = [1, 5, *range(6, 44)]
    for index, value in enumerate(site_a_values):
        rows.append(
            _Row(
                value=value,
                branch=DEFAULT_BRANCH,
                holder=_holder(index, f"D{index}"),
                identifier="edge-uplink" if index == 0 else None,
                division=site_a,
            )
        )
    rows.append(_Row(value=5, branch=OTHER_BRANCH, holder=_holder(1, "D1"), division=site_c))

    for index, value in enumerate(range(51, 81)):
        rows.append(
            _Row(
                value=value,
                branch=OTHER_BRANCH if value > 77 else DEFAULT_BRANCH,
                holder=_holder(100 + index, f"B{index}"),
                provenance=PoolRecordProvenance.PROVIDED if index == 0 else PoolRecordProvenance.ALLOCATED,
                division=site_b,
            )
        )
    rows.append(
        _Row(
            value=500,
            branch=DEFAULT_BRANCH,
            holder=_holder(130, "B30"),
            provenance=PoolRecordProvenance.PROVIDED,
            division=site_b,
        )
    )

    return MockPool(
        display_label="Device index",
        allocation_scope=("site",),
        ranges=_two_ranges("aaaa"),
        excluded_values=frozenset(),
        divisions=(site_a, site_b, site_c),
        rows=tuple(rows),
    )


def _build_unscoped_pool() -> MockPool:
    return MockPool(
        display_label="VLANs",
        allocation_scope=(),
        ranges=_two_ranges("bbbb"),
        excluded_values=frozenset({40}),
        divisions=((),),
        rows=(
            _Row(value=1, branch=DEFAULT_BRANCH, holder=_holder(201, "sw-access-01"), identifier="access-vlan"),
            _Row(value=7, branch=OTHER_BRANCH, holder=_holder(202, "sw-access-02")),
            _Row(
                value=40,
                branch=DEFAULT_BRANCH,
                holder=_holder(203, "sw-access-03"),
                provenance=PoolRecordProvenance.PROVIDED,
            ),
            _Row(value=51, branch=DEFAULT_BRANCH, holder=_holder(204, "sw-dist-01")),
            _Row(
                value=500,
                branch=DEFAULT_BRANCH,
                holder=_holder(205, "sw-core-01"),
                provenance=PoolRecordProvenance.PROVIDED,
            ),
        ),
    )


SCOPED_POOL = _build_scoped_pool()
UNSCOPED_POOL = _build_unscoped_pool()


def get_mock_pool(pool_id: str) -> MockPool:
    return UNSCOPED_POOL if pool_id == UNSCOPED_POOL_ID else SCOPED_POOL


def _percentage(count: int, size: int) -> float:
    if size <= 0:
        return 0.0
    return (count / size) * 100


def _figures(rows: Iterable[_Row], size: int) -> MockFigures:
    values: set[int] = set()
    default_branch_values: set[int] = set()
    for row in rows:
        values.add(row.value)
        if row.branch == DEFAULT_BRANCH:
            default_branch_values.add(row.value)
    used = len(values)
    used_default_branch = len(default_branch_values)
    used_branches = used - used_default_branch
    return MockFigures(
        size=size,
        used=used,
        used_default_branch=used_default_branch,
        used_branches=used_branches,
        utilization=_percentage(used, size),
        utilization_default_branch=_percentage(used_default_branch, size),
        utilization_branches=_percentage(used_branches, size),
    )


def _division_label(entries: tuple[MockDivisionEntry, ...]) -> str:
    return " / ".join(entry.display_label for entry in entries)


def _counted_rows(pool: MockPool, space: MockRange | None) -> list[_Row]:
    return [row for row in pool.rows if pool.in_space(row.value) and (space is None or space.holds(row.value))]


def _division_list(pool: MockPool, space: MockRange | None) -> tuple[MockDivision, ...]:
    size = space.size if space else pool.size
    rows = _counted_rows(pool=pool, space=space)
    divisions = [
        MockDivision(
            display_label=_division_label(entries),
            entries=entries,
            figures=_figures(rows=[row for row in rows if row.division == entries], size=size),
        )
        for entries in pool.divisions
    ]
    return tuple(sorted(divisions, key=lambda division: (-division.figures.utilization, division.display_label)))


def _get_range(pool: MockPool, pool_id: str, range_id: str | None) -> MockRange | None:
    if range_id is None:
        return None
    for item in pool.ranges:
        if item.id == range_id:
            return item
    raise ValidationError(
        input_value=f"The selected pool_id={pool_id} doesn't contain the requested range_id={range_id}"
    )


def get_utilization(pool_id: str) -> MockUtilization:
    pool = get_mock_pool(pool_id)
    ranges = tuple(
        MockRangeUtilization(
            id=item.id,
            display_label=item.display_label,
            start=item.start,
            end=item.end,
            weight=item.weight,
            figures=_division_list(pool=pool, space=item)[0].figures,
        )
        for item in sorted(pool.ranges, key=lambda item: item.start)
    )
    return MockUtilization(
        id=pool_id,
        display_label=pool.display_label,
        allocation_scope=pool.allocation_scope,
        figures=_division_list(pool=pool, space=None)[0].figures,
        ranges=ranges,
        out_of_space_count=sum(1 for row in pool.rows if not pool.in_space(row.value)),
    )


def get_divisions(pool_id: str, range_id: str | None = None) -> MockDivisions:
    pool = get_mock_pool(pool_id)
    space = _get_range(pool=pool, pool_id=pool_id, range_id=range_id)
    divisions = _division_list(pool=pool, space=space)
    return MockDivisions(count=len(divisions), allocation_scope=pool.allocation_scope, divisions=divisions)


def _validate_division_filter(
    pool: MockPool, pool_id: str, division: Sequence[DivisionFilterEntry], request_branch: str
) -> None:
    if not pool.allocation_scope:
        raise ValidationError(
            input_value=(
                f"The pool {pool_id} has no allocation scope in force on branch {request_branch}; "
                "the division filter cannot be applied"
            )
        )
    seen: set[str] = set()
    for entry in division:
        if entry.path not in pool.allocation_scope:
            raise ValidationError(
                input_value=(
                    f"The division entry '{entry.path}' is not in the allocation scope in force "
                    f"on branch {request_branch}"
                )
            )
        if entry.path in seen:
            raise ValidationError(input_value=f"The division entry '{entry.path}' is given twice")
        seen.add(entry.path)


def _validate_page(offset: int | None, limit: int | None) -> None:
    for name, value in (("offset", offset), ("limit", limit)):
        if value is not None and value < 0:
            raise ValidationError(input_value=f"{name} must be 0 or greater")


def _holder_divisions(pool: MockPool) -> dict[str, set[tuple[MockDivisionEntry, ...]]]:
    """The divisions each holder sits in, over every branch it holds a value on."""
    divisions: dict[str, set[tuple[MockDivisionEntry, ...]]] = {}
    for row in pool.rows:
        divisions.setdefault(row.holder.id, set()).add(row.division)
    return divisions


def _matches_division(
    holder_divisions: set[tuple[MockDivisionEntry, ...]], division: Sequence[DivisionFilterEntry]
) -> bool:
    return any(
        all(any(entry.path == wanted.path and entry.value == wanted.value for entry in entries) for wanted in division)
        for entries in holder_divisions
    )


def _to_allocation(pool: MockPool, row: _Row) -> MockAllocation:
    held_by = pool.range_of(row.value)
    return MockAllocation(
        value=row.value,
        branch=row.branch,
        holder=row.holder,
        identifier=row.identifier,
        provenance=row.provenance,
        in_space=pool.in_space(row.value),
        range=MockRangeRef(id=held_by.id, display_label=held_by.display_label) if held_by else None,
        division=row.division,
    )


def get_allocations(
    pool_id: str,
    request_branch: str,
    division: Sequence[DivisionFilterEntry] | None = None,
    range_id: str | None = None,
    in_space: bool | None = None,
    branch: str | None = None,
    provenance: PoolRecordProvenance | None = None,
    offset: int | None = None,
    limit: int | None = None,
) -> MockAllocations:
    _validate_page(offset=offset, limit=limit)
    pool = get_mock_pool(pool_id)
    space = _get_range(pool=pool, pool_id=pool_id, range_id=range_id)
    if division:
        _validate_division_filter(pool=pool, pool_id=pool_id, division=division, request_branch=request_branch)

    holder_divisions = _holder_divisions(pool)
    rows = [
        row
        for row in pool.rows
        if (space is None or space.holds(row.value))
        and (in_space is None or pool.in_space(row.value) == in_space)
        and (branch is None or row.branch == branch)
        and (provenance is None or row.provenance == provenance)
        and (not division or _matches_division(holder_divisions[row.holder.id], division))
    ]
    rows.sort(key=lambda row: (row.value, row.branch, row.holder.id))

    start = DEFAULT_OFFSET if offset is None else offset
    page_size = DEFAULT_LIMIT if limit is None else limit
    page = rows[start : start + page_size]
    return MockAllocations(count=len(rows), allocations=tuple(_to_allocation(pool=pool, row=row) for row in page))
