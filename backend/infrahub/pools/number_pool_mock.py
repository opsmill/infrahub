"""Fixed in-memory number-pool data served by the dedicated number-pool queries; reads nothing from the database."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from infrahub.core.constants import PoolRecordProvenance
from infrahub.exceptions import ValidationError

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping, Sequence

UNSCOPED_POOL_ID = "mock-unscoped"
DEFAULT_BRANCH = "main"
OTHER_BRANCH = "branch1"
DEFAULT_OFFSET = 0
DEFAULT_LIMIT = 10


@dataclass(frozen=True, slots=True)
class MockScopeElement:
    id: str
    name: str


@dataclass(frozen=True, slots=True)
class MockDivisionEntry:
    id: str
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
    range: MockRangeRef


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
    allocation_scope: tuple[MockScopeElement, ...]
    figures: MockFigures
    ranges: tuple[MockRangeUtilization, ...]


@dataclass(frozen=True, slots=True)
class MockDivision:
    display_label: str
    entries: tuple[MockDivisionEntry, ...]
    figures: MockFigures


@dataclass(frozen=True, slots=True)
class MockDivisions:
    count: int
    allocation_scope: tuple[MockScopeElement, ...]
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
    """One tracked value; division is where the holder sits on the default branch."""

    value: int
    branch: str
    holder: MockHolder
    provenance: PoolRecordProvenance = PoolRecordProvenance.ALLOCATED
    identifier: str | None = None
    division: tuple[MockDivisionEntry, ...] = ()


@dataclass(frozen=True, slots=True)
class MockPool:
    display_label: str
    allocation_scope: tuple[MockScopeElement, ...]
    ranges: tuple[MockRange, ...]
    excluded_values: frozenset[int]
    divisions: tuple[tuple[MockDivisionEntry, ...], ...]
    rows: tuple[_Row, ...] = field(repr=False)
    # Keyed by holder id and branch: where a holder sits on a branch when it differs from the default branch.
    moved_holders: Mapping[tuple[str, str], tuple[MockDivisionEntry, ...]] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        if self.allocation_scope and not self.divisions:
            raise ValueError(
                f"The mock pool {self.display_label} has an allocation scope and needs at least one division"
            )
        if not self.allocation_scope and self.divisions:
            raise ValueError(f"The mock pool {self.display_label} has no allocation scope and cannot hold a division")
        for row in self.rows:
            if row.value in self.excluded_values or not self._in_a_range(row.value):
                raise ValueError(f"The mock pool {self.display_label} holds {row.value}, a value it cannot allocate")

    @property
    def size(self) -> int:
        return sum(self.size_of(item) for item in self.ranges)

    def size_of(self, item: MockRange) -> int:
        return item.size - sum(1 for value in self.excluded_values if item.holds(value))

    def _in_a_range(self, value: int) -> bool:
        return any(item.holds(value) for item in self.ranges)

    def range_of(self, value: int) -> MockRange:
        return next(item for item in self.ranges if item.holds(value))

    @property
    def scope_names(self) -> tuple[str, ...]:
        return tuple(element.name for element in self.allocation_scope)

    def division_of(self, row: _Row, request_branch: str) -> tuple[MockDivisionEntry, ...]:
        return self.moved_holders.get((row.holder.id, request_branch), row.division)


def _holder(number: int, label: str) -> MockHolder:
    return MockHolder(
        id=f"18a0c0de-0000-4000-8000-{number:012d}", hfid=(label,), kind="InfraDevice", display_label=label
    )


SITE_ELEMENT = MockScopeElement(id="18a0c0de-5c09-4000-8000-000000000001", name="site")


def _site(letter: str, number: int) -> tuple[MockDivisionEntry, ...]:
    return (
        MockDivisionEntry(
            id=SITE_ELEMENT.id,
            path=SITE_ELEMENT.name,
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
    site_a, site_b, site_c, site_d = _site("A", 1), _site("B", 2), _site("C", 3), _site("D", 4)
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
    rows.append(_Row(value=5, branch=OTHER_BRANCH, holder=_holder(1, "D1"), division=site_a))

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

    return MockPool(
        display_label="Device index",
        allocation_scope=(SITE_ELEMENT,),
        ranges=_two_ranges("aaaa"),
        excluded_values=frozenset(),
        divisions=(site_a, site_b, site_c, site_d),
        rows=tuple(rows),
        moved_holders={(_holder(1, "D1").id, OTHER_BRANCH): site_c},
    )


def _build_unscoped_pool() -> MockPool:
    return MockPool(
        display_label="VLANs",
        allocation_scope=(),
        ranges=_two_ranges("bbbb"),
        excluded_values=frozenset({40}),
        divisions=(),
        rows=(
            _Row(value=1, branch=DEFAULT_BRANCH, holder=_holder(201, "sw-access-01"), identifier="access-vlan"),
            _Row(value=7, branch=OTHER_BRANCH, holder=_holder(202, "sw-access-02")),
            _Row(value=51, branch=DEFAULT_BRANCH, holder=_holder(204, "sw-dist-01")),
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


def _space_figures(pool: MockPool, rows: Iterable[_Row], space: MockRange | None) -> MockFigures:
    if space is None:
        return _figures(rows=rows, size=pool.size)
    return _figures(rows=(row for row in rows if space.holds(row.value)), size=pool.size_of(space))


def _as_filter(entries: tuple[MockDivisionEntry, ...]) -> list[DivisionFilterEntry]:
    return [DivisionFilterEntry(path=entry.path, value=entry.value) for entry in entries]


def _row_in_division(entries: tuple[MockDivisionEntry, ...], division: Sequence[DivisionFilterEntry]) -> bool:
    return all(
        any(entry.path == wanted.path and entry.value == wanted.value for entry in entries) for wanted in division
    )


def _own_rows(pool: MockPool, division: Sequence[DivisionFilterEntry], request_branch: str) -> list[_Row]:
    """The rows whose holder sits in the division as read on the request branch."""
    return [
        row
        for row in pool.rows
        if _row_in_division(entries=pool.division_of(row=row, request_branch=request_branch), division=division)
    ]


def _division_list(pool: MockPool, request_branch: str) -> tuple[MockDivision, ...]:
    divisions = []
    for entries in pool.divisions:
        rows = _own_rows(pool=pool, division=_as_filter(entries), request_branch=request_branch)
        if not rows:
            continue
        divisions.append(
            MockDivision(
                display_label=_division_label(entries),
                entries=entries,
                figures=_space_figures(pool=pool, rows=rows, space=None),
            )
        )
    return tuple(sorted(divisions, key=lambda division: (-division.figures.utilization, division.display_label)))


def _get_range(pool: MockPool, pool_id: str, range_id: str | None) -> MockRange | None:
    if range_id is None:
        return None
    for item in pool.ranges:
        if item.id == range_id:
            return item
    raise ValidationError(input_value=f"The range {range_id} does not belong to the pool {pool_id}")


def get_utilization(
    pool_id: str, request_branch: str, division: Sequence[DivisionFilterEntry] | None = None
) -> MockUtilization:
    pool = get_mock_pool(pool_id)
    counted_rows: Sequence[_Row] = pool.rows
    if division:
        _validate_division_filter(pool=pool, pool_id=pool_id, division=division)
        _validate_complete_division(pool=pool, pool_id=pool_id, division=division)
        counted_rows = _own_rows(pool=pool, division=division, request_branch=request_branch)
    elif pool.allocation_scope:
        raise ValidationError(input_value=_incomplete_division_message(pool_id))

    def figures_of(space: MockRange | None) -> MockFigures:
        return _space_figures(pool=pool, rows=counted_rows, space=space)

    ranges = tuple(
        MockRangeUtilization(
            id=item.id,
            display_label=item.display_label,
            start=item.start,
            end=item.end,
            weight=item.weight,
            figures=figures_of(item),
        )
        for item in sorted(pool.ranges, key=lambda item: item.start)
    )
    return MockUtilization(
        id=pool_id,
        display_label=pool.display_label,
        allocation_scope=pool.allocation_scope,
        figures=figures_of(None),
        ranges=ranges,
    )


def get_divisions(pool_id: str, request_branch: str) -> MockDivisions:
    pool = get_mock_pool(pool_id)
    divisions = _division_list(pool=pool, request_branch=request_branch)
    return MockDivisions(count=len(divisions), allocation_scope=pool.allocation_scope, divisions=divisions)


def _incomplete_division_message(pool_id: str) -> str:
    return (
        f"The pool {pool_id} has an allocation scope; give a division with a value for every element "
        "to read its utilization"
    )


def _validate_division_filter(pool: MockPool, pool_id: str, division: Sequence[DivisionFilterEntry]) -> None:
    if not pool.allocation_scope:
        raise ValidationError(
            input_value=f"The pool {pool_id} has no allocation scope; the division filter cannot be applied"
        )
    seen: set[str] = set()
    for entry in division:
        if entry.path not in pool.scope_names or entry.path in seen:
            raise ValidationError(
                input_value=f'The division entry "{entry.path}" is not an element of the pool\'s allocation scope'
            )
        seen.add(entry.path)


def _validate_complete_division(pool: MockPool, pool_id: str, division: Sequence[DivisionFilterEntry]) -> None:
    given = {entry.path for entry in division}
    if any(name not in given for name in pool.scope_names):
        raise ValidationError(input_value=_incomplete_division_message(pool_id))


def _validate_page(offset: int | None, limit: int | None) -> None:
    for name, value in (("offset", offset), ("limit", limit)):
        if value is not None and value < 0:
            raise ValidationError(input_value=f"{name} must be 0 or greater")


def _to_allocation(pool: MockPool, row: _Row) -> MockAllocation:
    held_by = pool.range_of(row.value)
    return MockAllocation(
        value=row.value,
        branch=row.branch,
        holder=row.holder,
        identifier=row.identifier,
        provenance=row.provenance,
        range=MockRangeRef(id=held_by.id, display_label=held_by.display_label),
    )


def get_allocations(
    pool_id: str,
    request_branch: str,
    division: Sequence[DivisionFilterEntry] | None = None,
    range_id: str | None = None,
    branch: str | None = None,
    provenance: PoolRecordProvenance | None = None,
    offset: int | None = None,
    limit: int | None = None,
) -> MockAllocations:
    _validate_page(offset=offset, limit=limit)
    pool = get_mock_pool(pool_id)
    space = _get_range(pool=pool, pool_id=pool_id, range_id=range_id)
    if division:
        _validate_division_filter(pool=pool, pool_id=pool_id, division=division)

    candidates = _own_rows(pool=pool, division=division or (), request_branch=request_branch)
    rows = [
        row
        for row in candidates
        if (space is None or space.holds(row.value))
        and (branch is None or row.branch == branch)
        and (provenance is None or row.provenance == provenance)
    ]
    rows.sort(key=lambda row: (row.value, row.branch, row.holder.id))

    start = DEFAULT_OFFSET if offset is None else offset
    page_size = DEFAULT_LIMIT if limit is None else limit
    page = rows[start : start + page_size]
    return MockAllocations(count=len(rows), allocations=tuple(_to_allocation(pool=pool, row=row) for row in page))
