from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import pytest

from infrahub.core.constants import PoolRecordProvenance
from infrahub.core.initialization import create_branch
from infrahub.core.query.resource_manager import NumberPoolGetAllocated
from tests.helpers.number_pool import (
    SCOPED_POOL_END,
    SCOPED_POOL_START,
    scoped_device,
    scoped_device_holding,
    scoped_pool,
    scoped_site,
)

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.node.resource_manager.number_pool import CoreNumberPool
    from infrahub.database import InfrahubDatabase

OTHER_BRANCH = "branch1"


@dataclass
class AllocatedDataset:
    """An unscoped pool whose number 1 is held by two devices on the default branch and one on another branch."""

    pool: CoreNumberPool
    default_branch: Branch
    names_by_id: dict[str, str] = field(default_factory=dict)

    def name_of(self, holding_object_id: str) -> str:
        return self.names_by_id[holding_object_id]


async def allocated_dataset(db: InfrahubDatabase, default_branch: Branch) -> AllocatedDataset:
    """Allocate 1 to `allocated-1` and 2 to `allocated-2`, and record 1 as provided by `provided-main` and `provided-branch1`."""
    pool = await scoped_pool(db=db, name="vlan-allocations", allocation_scope=None)
    dataset = AllocatedDataset(pool=pool, default_branch=default_branch)
    site = await scoped_site(db=db, branch=default_branch, name="site-a")

    first = await scoped_device(db=db, branch=default_branch, pool=pool, name="allocated-1", site=site)
    provided = await scoped_device_holding(
        db=db, branch=default_branch, pool=pool, name="provided-main", site=site, number=1
    )
    second = await scoped_device(db=db, branch=default_branch, pool=pool, name="allocated-2", site=site)
    other_branch = await create_branch(db=db, branch_name=OTHER_BRANCH)
    on_branch = await scoped_device_holding(
        db=db, branch=other_branch, pool=pool, name="provided-branch1", site=site, number=1
    )

    assert (first.get_attribute("vlan_id").value, second.get_attribute("vlan_id").value) == (1, 2)
    dataset.names_by_id = {
        first.id: "allocated-1",
        provided.id: "provided-main",
        second.id: "allocated-2",
        on_branch.id: "provided-branch1",
    }
    return dataset


async def allocated_rows(
    db: InfrahubDatabase,
    dataset: AllocatedDataset,
    ranges: list[list[int]] | None = None,
    branch_name: str | None = None,
    provenance: PoolRecordProvenance | None = None,
    offset: int | None = None,
    limit: int | None = None,
) -> list[tuple[int, str, str, PoolRecordProvenance]]:
    """The value, branch, holding object name and provenance of each row, in the order the query returns them."""
    query = await NumberPoolGetAllocated.init(
        db=db,
        pool=dataset.pool,
        ranges=ranges or [[SCOPED_POOL_START, SCOPED_POOL_END]],
        branch_name=branch_name,
        provenance=provenance,
        offset=offset,
        limit=limit,
        branch=dataset.default_branch,
        branch_agnostic=True,
    )
    await query.execute(db=db)
    return [(row.value, row.branch, dataset.name_of(row.id), row.provenance) for row in query.get_data()]


@dataclass(frozen=True)
class AllocatedFilterCase:
    name: str
    ranges: list[list[int]] | None = None
    branch_name: str | None = None
    provenance: PoolRecordProvenance | None = None
    expected: list[tuple[int, str, str, PoolRecordProvenance]] = field(default_factory=list)


ALLOCATED_FILTER_CASES = [
    AllocatedFilterCase(
        name="range-bounds",
        ranges=[[2, SCOPED_POOL_END]],
        expected=[(2, "main", "allocated-2", PoolRecordProvenance.ALLOCATED)],
    ),
    AllocatedFilterCase(
        name="branch-holding-the-value",
        branch_name=OTHER_BRANCH,
        expected=[(1, OTHER_BRANCH, "provided-branch1", PoolRecordProvenance.PROVIDED)],
    ),
    AllocatedFilterCase(
        name="default-branch",
        branch_name="main",
        expected=[
            (1, "main", "allocated-1", PoolRecordProvenance.ALLOCATED),
            (1, "main", "provided-main", PoolRecordProvenance.PROVIDED),
            (2, "main", "allocated-2", PoolRecordProvenance.ALLOCATED),
        ],
    ),
    AllocatedFilterCase(
        name="branch-holding-no-value",
        branch_name="unknown",
        expected=[],
    ),
    AllocatedFilterCase(
        name="allocated",
        provenance=PoolRecordProvenance.ALLOCATED,
        expected=[
            (1, "main", "allocated-1", PoolRecordProvenance.ALLOCATED),
            (2, "main", "allocated-2", PoolRecordProvenance.ALLOCATED),
        ],
    ),
    AllocatedFilterCase(
        name="provided",
        provenance=PoolRecordProvenance.PROVIDED,
        expected=[
            (1, OTHER_BRANCH, "provided-branch1", PoolRecordProvenance.PROVIDED),
            (1, "main", "provided-main", PoolRecordProvenance.PROVIDED),
        ],
    ),
    AllocatedFilterCase(
        name="branch-and-provenance",
        branch_name="main",
        provenance=PoolRecordProvenance.PROVIDED,
        expected=[(1, "main", "provided-main", PoolRecordProvenance.PROVIDED)],
    ),
]


class TestNumberPoolGetAllocated:
    """Every test reads the one dataset of the class and writes nothing."""

    @pytest.fixture(scope="class")
    async def dataset(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, scoped_schema_scope_class: None
    ) -> AllocatedDataset:
        return await allocated_dataset(db=db, default_branch=default_branch_scope_class)

    async def test_rows_are_ordered_by_value_then_branch_then_holding_object_id(
        self, db: InfrahubDatabase, dataset: AllocatedDataset
    ) -> None:
        holding_objects_of_one_on_main = sorted(
            holding_object_id
            for holding_object_id, name in dataset.names_by_id.items()
            if name in {"allocated-1", "provided-main"}
        )

        rows = await allocated_rows(db=db, dataset=dataset)

        assert [(value, branch, name) for value, branch, name, _ in rows] == [
            (1, OTHER_BRANCH, "provided-branch1"),
            (1, "main", dataset.name_of(holding_objects_of_one_on_main[0])),
            (1, "main", dataset.name_of(holding_objects_of_one_on_main[1])),
            (2, "main", "allocated-2"),
        ]

    @pytest.mark.parametrize("case", ALLOCATED_FILTER_CASES, ids=[case.name for case in ALLOCATED_FILTER_CASES])
    async def test_filters(self, db: InfrahubDatabase, dataset: AllocatedDataset, case: AllocatedFilterCase) -> None:
        rows = await allocated_rows(
            db=db, dataset=dataset, ranges=case.ranges, branch_name=case.branch_name, provenance=case.provenance
        )

        assert sorted(rows) == sorted(case.expected)

    async def test_the_count_covers_the_filtered_rows_before_pagination(
        self, db: InfrahubDatabase, dataset: AllocatedDataset
    ) -> None:
        query = await NumberPoolGetAllocated.init(
            db=db,
            pool=dataset.pool,
            ranges=[[SCOPED_POOL_START, SCOPED_POOL_END]],
            provenance=PoolRecordProvenance.ALLOCATED,
            offset=1,
            limit=1,
            branch=dataset.default_branch,
            branch_agnostic=True,
        )

        await query.execute(db=db)

        assert await query.count(db=db) == 2
        assert [(row.value, dataset.name_of(row.id)) for row in query.get_data()] == [(2, "allocated-2")]
