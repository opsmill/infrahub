from dataclasses import dataclass, field

import pytest

from infrahub.core.schema.attribute_parameters import NumberPoolRangeParameters
from infrahub.pools.number_pool_range_reconciler import NumberPoolRangeReconciler

from .helpers import InMemoryRangeStore, PoolReference

POOL = PoolReference(id="pool")
STORED: list[tuple[int, int, int | None]] = [(1, 10, None), (20, 30, 5), (40, 50, None)]


@dataclass
class ReconcileCase:
    name: str
    stored: list[tuple[int, int, int | None]]
    declared: list[NumberPoolRangeParameters]
    expected_writes: list[tuple[str, str]]
    expected_ranges: list[tuple[str, int, int, int | None]]
    expected_created: list[str] = field(default_factory=list)
    expected_updated: list[str] = field(default_factory=list)
    expected_deleted: list[str] = field(default_factory=list)


RECONCILE_CASES: list[ReconcileCase] = [
    ReconcileCase(
        name="same_ranges_write_nothing",
        stored=STORED,
        declared=[
            NumberPoolRangeParameters(start=40, end=50),
            NumberPoolRangeParameters(start=1, end=10),
            NumberPoolRangeParameters(start=20, end=30, weight=5),
        ],
        expected_writes=[],
        expected_ranges=[("stored-0", 1, 10, None), ("stored-1", 20, 30, 5), ("stored-2", 40, 50, None)],
    ),
    ReconcileCase(
        name="empty_pool_creates_every_range_lowest_start_first",
        stored=[],
        declared=[NumberPoolRangeParameters(start=200, end=300), NumberPoolRangeParameters(start=1, end=10, weight=2)],
        expected_writes=[("create", "created-0"), ("create", "created-1")],
        expected_ranges=[("created-0", 1, 10, 2), ("created-1", 200, 300, None)],
        expected_created=["created-0", "created-1"],
    ),
    ReconcileCase(
        name="empty_declaration_deletes_every_range_lowest_start_first",
        stored=STORED,
        declared=[],
        expected_writes=[("delete", "stored-0"), ("delete", "stored-1"), ("delete", "stored-2")],
        expected_ranges=[],
        expected_deleted=["stored-0", "stored-1", "stored-2"],
    ),
    ReconcileCase(
        name="same_bounds_with_another_weight_reweight_the_stored_range",
        stored=STORED,
        declared=[
            NumberPoolRangeParameters(start=1, end=10, weight=7),
            NumberPoolRangeParameters(start=20, end=30),
            NumberPoolRangeParameters(start=40, end=50),
        ],
        expected_writes=[("save", "stored-0"), ("save", "stored-1")],
        expected_ranges=[("stored-0", 1, 10, 7), ("stored-1", 20, 30, None), ("stored-2", 40, 50, None)],
        expected_updated=["stored-0", "stored-1"],
    ),
    ReconcileCase(
        name="new_bounds_replace_the_stored_range_instead_of_rewriting_it",
        stored=[(1, 10, 3)],
        declared=[NumberPoolRangeParameters(start=1, end=15, weight=3)],
        expected_writes=[("delete", "stored-0"), ("create", "created-1")],
        expected_ranges=[("created-1", 1, 15, 3)],
        expected_created=["created-1"],
        expected_deleted=["stored-0"],
    ),
    ReconcileCase(
        name="each_range_is_kept_reweighted_created_or_deleted_on_its_own",
        stored=STORED,
        declared=[
            NumberPoolRangeParameters(start=80, end=90),
            NumberPoolRangeParameters(start=1, end=10, weight=4),
            NumberPoolRangeParameters(start=25, end=35, weight=5),
            NumberPoolRangeParameters(start=40, end=50),
        ],
        expected_writes=[
            ("delete", "stored-1"),
            ("save", "stored-0"),
            ("create", "created-2"),
            ("create", "created-3"),
        ],
        expected_ranges=[
            ("stored-0", 1, 10, 4),
            ("created-2", 25, 35, 5),
            ("stored-2", 40, 50, None),
            ("created-3", 80, 90, None),
        ],
        expected_created=["created-2", "created-3"],
        expected_updated=["stored-0"],
        expected_deleted=["stored-1"],
    ),
]


@pytest.mark.parametrize("case", RECONCILE_CASES, ids=lambda case: case.name)
async def test_reconcile(case: ReconcileCase) -> None:
    store = InMemoryRangeStore(ranges=case.stored)

    reconciliation = await NumberPoolRangeReconciler(range_store=store).reconcile(pool=POOL, declared=case.declared)

    assert store.writes == case.expected_writes
    assert [pool_range.details for pool_range in reconciliation.ranges] == case.expected_ranges
    assert [pool_range.details for pool_range in await store.get_ranges(pool_id=POOL.get_id())] == case.expected_ranges
    assert [pool_range.id for pool_range in reconciliation.created] == case.expected_created
    assert [pool_range.id for pool_range in reconciliation.updated] == case.expected_updated
    assert [pool_range.id for pool_range in reconciliation.deleted] == case.expected_deleted
    assert reconciliation.changed is bool(case.expected_writes)


@dataclass
class SingleRangeCase:
    name: str
    stored: list[tuple[int, int, int | None]]
    declared: NumberPoolRangeParameters
    expected_writes: list[tuple[str, str]]
    expected_ranges: list[tuple[str, int, int, int | None]]


SINGLE_RANGE_CASES: list[SingleRangeCase] = [
    SingleRangeCase(
        name="empty_pool_gets_the_range",
        stored=[],
        declared=NumberPoolRangeParameters(start=1, end=10, weight=4),
        expected_writes=[("create", "created-0")],
        expected_ranges=[("created-0", 1, 10, 4)],
    ),
    SingleRangeCase(
        name="new_bounds_rewrite_the_range_in_place",
        stored=[(1, 10, 2)],
        declared=NumberPoolRangeParameters(start=50, end=60, weight=2),
        expected_writes=[("save", "stored-0")],
        expected_ranges=[("stored-0", 50, 60, 2)],
    ),
    SingleRangeCase(
        name="same_range_writes_nothing",
        stored=[(1, 10, 2)],
        declared=NumberPoolRangeParameters(start=1, end=10, weight=2),
        expected_writes=[],
        expected_ranges=[("stored-0", 1, 10, 2)],
    ),
]


@pytest.mark.parametrize("case", SINGLE_RANGE_CASES, ids=lambda case: case.name)
async def test_rewrite_single_range(case: SingleRangeCase) -> None:
    store = InMemoryRangeStore(ranges=case.stored)

    reconciliation = await NumberPoolRangeReconciler(range_store=store).rewrite_single_range(
        pool=POOL, declared=case.declared
    )

    assert store.writes == case.expected_writes
    assert [pool_range.details for pool_range in reconciliation.ranges] == case.expected_ranges
    assert reconciliation.changed is bool(case.expected_writes)


async def test_rewrite_single_range_refuses_a_pool_holding_several_ranges() -> None:
    store = InMemoryRangeStore(ranges=[(1, 10, None), (20, 30, None)])

    with pytest.raises(ValueError, match=r"^Number pool pool holds 2 ranges, a single range is rewritten$"):
        await NumberPoolRangeReconciler(range_store=store).rewrite_single_range(
            pool=POOL, declared=NumberPoolRangeParameters(start=1, end=30)
        )

    assert store.writes == []
