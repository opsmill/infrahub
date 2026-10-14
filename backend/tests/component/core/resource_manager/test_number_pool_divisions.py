from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import pytest

from infrahub.core import registry
from infrahub.core.constants import (
    InfrahubKind,
    PoolRecordProvenance,
    RelationshipCardinality,
    RelationshipDirection,
)
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.migrations.query.node_duplicate import NodeDuplicateQuery, SchemaNodeInfo
from infrahub.core.node import Node
from infrahub.core.node.resource_manager.number_pool import CoreNumberPool
from infrahub.core.query.resource_manager import NumberPoolGetAllocated
from infrahub.core.schema import AttributeSchema, RelationshipSchema, SchemaRoot
from infrahub.pools.number import NumberUtilizationGetter
from infrahub.pools.number_pool_repository import NumberPoolRepository
from infrahub.pools.number_ranges import EffectiveSpace, NumberDomain
from infrahub.pools.scope import (
    AllocationScope,
    AllocationScopeResolver,
    Division,
    ScopeElement,
    division_element_path,
)
from tests.component.core.resource_manager.conftest import delete_branch
from tests.helpers.number_pool import (
    SCOPED_ATTRIBUTE_NAME,
    SCOPED_DEVICE,
    SCOPED_POOL_END,
    SCOPED_POOL_SCHEMA,
    SCOPED_POOL_START,
    SCOPED_SITE,
    save_schema_kinds,
    scoped_device,
    scoped_device_holding,
    scoped_pool,
    scoped_site,
)

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
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
        )

        await query.execute(db=db)

        assert await query.count(db=db) == 2
        assert [(row.value, dataset.name_of(row.id)) for row in query.get_data()] == [(2, "allocated-2")]


@dataclass
class DivisionsDataset:
    """Two pools over the device's `vlan_id` whose numbers were all provided by a user.

    The pool scoped by `site`: on the default branch a1 holds 1 and a2 holds 2 in site-a, b1 holds 3 in
    site-b, and site-d holds nothing; on the other branch a2 sits in site-c, b1 holds 5, and x, which exists
    only there, holds 4 in site-a. a2 occupies site-a and site-c, each on a live branch.

    The pool scoped by `site` and `role`: on the default branch leaf-1 holds 1 and leaf-2 holds 2 as leaves
    of site-a, and spine-1 holds 1 as a spine of site-a.
    """

    default_branch: Branch
    site_pool: CoreNumberPool
    site_role_pool: CoreNumberPool
    sites: dict[str, str]
    other_branch: Branch = field(init=False)
    names_by_id: dict[str, str] = field(default_factory=dict)


def element_fields_of(
    pool: CoreNumberPool, branch: Branch
) -> list[tuple[ScopeElement, AttributeSchema | RelationshipSchema]]:
    scope = AllocationScope.from_stored(pool.get_attribute("allocation_scope").value, pool=pool.id)
    return AllocationScopeResolver(schema_branch=registry.schema.get_schema_branch(name=branch.name)).element_fields(
        kind=SCOPED_DEVICE.kind, scope=scope, pool=pool.id, attribute=SCOPED_ATTRIBUTE_NAME
    )


async def division_figures(
    db: InfrahubDatabase, pool: CoreNumberPool, branch: Branch, domain: NumberDomain | None = None
) -> dict[tuple[str | int | float | bool, ...], tuple[int, int, int]]:
    """The used, used on the default branch and used only on other branches figures of each division."""
    element_fields = element_fields_of(pool=pool, branch=branch)
    repository = NumberPoolRepository(db=db)
    divisions = await repository.get_divisions(
        pool=pool,
        branch=branch,
        space=EffectiveSpace(ranges=await repository.get_pool_ranges(pool_id=pool.id), domain=domain or NumberDomain()),
        elements=[division_element_path(field=field) for _, field in element_fields],
    )
    return {
        division.values: (division.used, division.used_default_branch, division.used_branches) for division in divisions
    }


async def allocated_in_division(
    db: InfrahubDatabase,
    dataset: DivisionsDataset,
    pool: CoreNumberPool,
    branch: Branch,
    entries: list[tuple[str, str]],
    branch_name: str | None = None,
    provenance: PoolRecordProvenance | None = None,
) -> list[tuple[int, str, str]]:
    """The value, branch and holding object name of each row the allocated numbers query reports for the division."""
    query = await NumberPoolGetAllocated.init(
        db=db,
        pool=pool,
        ranges=[[SCOPED_POOL_START, SCOPED_POOL_END]],
        division=Division.from_entries(entries=entries, element_fields=element_fields_of(pool=pool, branch=branch)),
        branch_name=branch_name,
        provenance=provenance,
        branch=branch,
    )
    await query.execute(db=db)
    return [(row.value, row.branch, dataset.names_by_id[row.id]) for row in query.get_data()]


@dataclass(frozen=True)
class SiteDivisionCase:
    name: str
    site: str
    expected: list[tuple[int, str, str]]


SITE_DIVISION_CASES = [
    SiteDivisionCase(
        name="two-sites-and-one-branch-only",
        site="site-a",
        expected=[(1, "main", "a1"), (2, "main", "a2"), (4, OTHER_BRANCH, "x")],
    ),
    SiteDivisionCase(
        name="renumbered-on-a-branch",
        site="site-b",
        expected=[(3, "main", "b1"), (5, OTHER_BRANCH, "b1")],
    ),
    SiteDivisionCase(name="moved-on-a-branch", site="site-c", expected=[(2, "main", "a2")]),
    SiteDivisionCase(name="no-number", site="site-d", expected=[]),
]


@dataclass(frozen=True)
class DivisionFilterCase:
    name: str
    branch_name: str | None
    provenance: PoolRecordProvenance | None
    expected: list[tuple[int, str, str]]


DIVISION_FILTER_CASES = [
    DivisionFilterCase(name="branch", branch_name=OTHER_BRANCH, provenance=None, expected=[(4, OTHER_BRANCH, "x")]),
    DivisionFilterCase(
        name="branch-and-provenance",
        branch_name="main",
        provenance=PoolRecordProvenance.PROVIDED,
        expected=[(1, "main", "a1"), (2, "main", "a2")],
    ),
    DivisionFilterCase(
        name="provenance-no-match", branch_name=None, provenance=PoolRecordProvenance.ALLOCATED, expected=[]
    ),
]


class TestScopedPoolQueries:
    """Every test reads the one dataset of the class and writes nothing."""

    @pytest.fixture(scope="class")
    async def dataset(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, scoped_schema_scope_class: None
    ) -> DivisionsDataset:
        main = default_branch_scope_class
        sites = {
            name: await scoped_site(db=db, branch=main, name=name) for name in ("site-a", "site-b", "site-c", "site-d")
        }
        dataset = DivisionsDataset(
            default_branch=main,
            site_pool=await scoped_pool(db=db, name="vlan-per-site", allocation_scope=["site"]),
            site_role_pool=await scoped_pool(db=db, name="vlan-per-site-and-role", allocation_scope=["site", "role"]),
            sites={name: site.id for name, site in sites.items()},
        )

        devices = {}
        for name, site, number in (("a1", "site-a", 1), ("a2", "site-a", 2), ("b1", "site-b", 3)):
            devices[name] = await scoped_device_holding(
                db=db, branch=main, pool=dataset.site_pool, name=name, site=sites[site], number=number
            )
        for name, role, number in (("leaf-1", "leaf", 1), ("leaf-2", "leaf", 2), ("spine-1", "spine", 1)):
            devices[name] = await scoped_device_holding(
                db=db,
                branch=main,
                pool=dataset.site_role_pool,
                name=name,
                site=sites["site-a"],
                number=number,
                role=role,
            )

        branch = dataset.other_branch = await create_branch(db=db, branch_name=OTHER_BRANCH)
        moved = await NodeManager.get_one(db=db, branch=branch, id=devices["a2"].id, raise_on_error=True)
        await moved.get_relationship("site").update(db=db, data=sites["site-c"])
        await moved.save(db=db)
        renumbered = await NodeManager.get_one(db=db, branch=branch, id=devices["b1"].id, raise_on_error=True)
        renumbered.get_attribute("vlan_id").value = 5
        await renumbered.save(db=db)
        devices["x"] = await scoped_device_holding(
            db=db, branch=branch, pool=dataset.site_pool, name="x", site=sites["site-a"], number=4
        )
        dataset.names_by_id = {device.id: name for name, device in devices.items()}
        return dataset

    @pytest.mark.parametrize("on_other_branch", [False, True], ids=["default-branch", "other-branch"])
    async def test_a_holding_object_counts_in_every_division_it_occupies_on_a_live_branch(
        self, db: InfrahubDatabase, dataset: DivisionsDataset, on_other_branch: bool
    ) -> None:
        branch = dataset.other_branch if on_other_branch else dataset.default_branch

        figures = await division_figures(db=db, pool=dataset.site_pool, branch=branch)

        assert figures == {
            (dataset.sites["site-a"],): (3, 2, 1),
            (dataset.sites["site-b"],): (2, 1, 1),
            (dataset.sites["site-c"],): (1, 1, 0),
        }

    async def test_the_utilization_of_a_division_counts_the_numbers_the_division_lists(
        self, db: InfrahubDatabase, dataset: DivisionsDataset
    ) -> None:
        pool = dataset.site_pool
        branch = dataset.default_branch
        repository = NumberPoolRepository(db=db)
        getter = NumberUtilizationGetter(
            db=db,
            pool=pool,
            space=EffectiveSpace(ranges=await repository.get_pool_ranges(pool_id=pool.id), domain=NumberDomain()),
            branch=branch,
            division=Division.from_entries(
                entries=[("site", dataset.sites["site-a"])], element_fields=element_fields_of(pool=pool, branch=branch)
            ),
        )

        await getter.load_data()

        assert (getter.figures.used_default_branch, getter.figures.used_branches) == (2, 1)

    async def test_divisions_read_one_row_at_a_time_are_each_counted_once(
        self, db: InfrahubDatabase, dataset: DivisionsDataset, query_limit_of_one: None
    ) -> None:
        figures = await division_figures(db=db, pool=dataset.site_pool, branch=dataset.other_branch)

        assert figures == {
            (dataset.sites["site-a"],): (3, 2, 1),
            (dataset.sites["site-b"],): (2, 1, 1),
            (dataset.sites["site-c"],): (1, 1, 0),
        }

    async def test_a_division_of_two_elements(self, db: InfrahubDatabase, dataset: DivisionsDataset) -> None:
        figures = await division_figures(db=db, pool=dataset.site_role_pool, branch=dataset.default_branch)

        assert figures == {
            (dataset.sites["site-a"], "leaf"): (2, 2, 0),
            (dataset.sites["site-a"], "spine"): (1, 1, 0),
        }

    @pytest.mark.parametrize("on_other_branch", [False, True], ids=["default-branch", "other-branch"])
    @pytest.mark.parametrize("case", SITE_DIVISION_CASES, ids=[case.name for case in SITE_DIVISION_CASES])
    async def test_allocated_numbers_of_a_division_count_every_division_a_holding_object_occupies(
        self, db: InfrahubDatabase, dataset: DivisionsDataset, case: SiteDivisionCase, on_other_branch: bool
    ) -> None:
        branch = dataset.other_branch if on_other_branch else dataset.default_branch

        rows = await allocated_in_division(
            db=db, dataset=dataset, pool=dataset.site_pool, branch=branch, entries=[("site", dataset.sites[case.site])]
        )

        assert rows == case.expected

    @pytest.mark.parametrize("case", DIVISION_FILTER_CASES, ids=[case.name for case in DIVISION_FILTER_CASES])
    async def test_the_division_filter_combines_with_the_branch_and_provenance_filters(
        self, db: InfrahubDatabase, dataset: DivisionsDataset, case: DivisionFilterCase
    ) -> None:
        rows = await allocated_in_division(
            db=db,
            dataset=dataset,
            pool=dataset.site_pool,
            branch=dataset.default_branch,
            entries=[("site", dataset.sites["site-a"])],
            branch_name=case.branch_name,
            provenance=case.provenance,
        )

        assert rows == case.expected

    async def test_the_count_of_a_division_covers_its_rows_before_pagination(
        self, db: InfrahubDatabase, dataset: DivisionsDataset
    ) -> None:
        pool = dataset.site_pool
        branch = dataset.default_branch
        query = await NumberPoolGetAllocated.init(
            db=db,
            pool=pool,
            ranges=[[SCOPED_POOL_START, SCOPED_POOL_END]],
            division=Division.from_entries(
                entries=[("site", dataset.sites["site-a"])], element_fields=element_fields_of(pool=pool, branch=branch)
            ),
            offset=1,
            limit=1,
            branch=branch,
        )

        await query.execute(db=db)

        assert await query.count(db=db) == 3
        assert [(row.value, dataset.names_by_id[row.id]) for row in query.get_data()] == [(2, "a2")]

    async def test_divisions_count_only_the_numbers_inside_the_space(
        self, db: InfrahubDatabase, dataset: DivisionsDataset
    ) -> None:
        figures = await division_figures(
            db=db, pool=dataset.site_pool, branch=dataset.default_branch, domain=NumberDomain(upper=2)
        )

        assert figures == {(dataset.sites["site-a"],): (2, 2, 0), (dataset.sites["site-c"],): (1, 1, 0)}

    async def test_an_empty_space_holds_no_division(self, db: InfrahubDatabase, dataset: DivisionsDataset) -> None:
        element_fields = element_fields_of(pool=dataset.site_pool, branch=dataset.default_branch)

        divisions = await NumberPoolRepository(db=db).get_divisions(
            pool=dataset.site_pool,
            branch=dataset.default_branch,
            space=EffectiveSpace(ranges=[], domain=NumberDomain()),
            elements=[division_element_path(field=field) for _, field in element_fields],
        )

        assert divisions == []

    async def test_allocated_numbers_of_a_division_naming_some_of_the_elements(
        self, db: InfrahubDatabase, dataset: DivisionsDataset
    ) -> None:
        site_only = await allocated_in_division(
            db=db,
            dataset=dataset,
            pool=dataset.site_role_pool,
            branch=dataset.default_branch,
            entries=[("site", dataset.sites["site-a"])],
        )
        role_only = await allocated_in_division(
            db=db,
            dataset=dataset,
            pool=dataset.site_role_pool,
            branch=dataset.default_branch,
            entries=[("role", "spine")],
        )

        assert sorted(site_only) == [(1, "main", "leaf-1"), (1, "main", "spine-1"), (2, "main", "leaf-2")]
        assert role_only == [(1, "main", "spine-1")]

    @pytest.mark.parametrize("on_other_branch", [False, True], ids=["default-branch", "other-branch"])
    async def test_the_allocated_numbers_of_each_listed_division_give_its_figures(
        self, db: InfrahubDatabase, dataset: DivisionsDataset, on_other_branch: bool
    ) -> None:
        branch = dataset.other_branch if on_other_branch else dataset.default_branch

        for pool in (dataset.site_pool, dataset.site_role_pool):
            names = [element.name for element, _ in element_fields_of(pool=pool, branch=branch)]
            figures = await division_figures(db=db, pool=pool, branch=branch)
            assert figures
            for values, (used, used_default_branch, _) in figures.items():
                rows = await allocated_in_division(
                    db=db,
                    dataset=dataset,
                    pool=pool,
                    branch=branch,
                    entries=[(name, str(value)) for name, value in zip(names, values, strict=True)],
                )
                assert len({value for value, _, _ in rows}) == used
                assert len({value for value, row_branch, _ in rows if row_branch == "main"}) == used_default_branch


async def test_a_node_moved_on_the_default_branch_counts_in_the_site_an_older_branch_reads(
    db: InfrahubDatabase, default_branch: Branch, site_scoped_pool: CoreNumberPool
) -> None:
    site_a = await scoped_site(db=db, branch=default_branch, name="site-a")
    site_c = await scoped_site(db=db, branch=default_branch, name="site-c")
    device = await scoped_device_holding(
        db=db, branch=default_branch, pool=site_scoped_pool, name="device-1", site=site_a, number=5
    )
    await create_branch(branch_name="forked-in-site-a", db=db)
    moved = await NodeManager.get_one(db=db, branch=default_branch, id=device.id, raise_on_error=True)
    await moved.get_relationship(name="site").update(db=db, data=site_c)
    await moved.save(db=db)

    figures = await division_figures(db=db, pool=site_scoped_pool, branch=default_branch)

    assert figures == {(site_a.id,): (1, 1, 0), (site_c.id,): (1, 1, 0)}


async def test_a_number_changed_on_the_default_branch_counts_on_the_older_branch_that_still_holds_it(
    db: InfrahubDatabase, default_branch: Branch, site_scoped_pool: CoreNumberPool
) -> None:
    site_a = await scoped_site(db=db, branch=default_branch, name="site-a")
    device = await scoped_device_holding(
        db=db, branch=default_branch, pool=site_scoped_pool, name="device-1", site=site_a, number=5
    )
    older = await create_branch(branch_name="holds-the-old-number", db=db)
    changed = await NodeManager.get_one(db=db, branch=default_branch, id=device.id, raise_on_error=True)
    changed.get_attribute(SCOPED_ATTRIBUTE_NAME).value = 6
    await changed.save(db=db)

    figures = await division_figures(db=db, pool=site_scoped_pool, branch=default_branch)
    rows = await allocated_rows_in_division(
        db=db, pool=site_scoped_pool, branch=default_branch, entries=[("site", site_a.id)]
    )

    assert figures == {(site_a.id,): (2, 1, 1)}
    assert rows == [(5, older.name), (6, default_branch.name)]


async def test_a_node_deleted_on_the_default_branch_counts_on_the_older_branch_that_still_holds_it(
    db: InfrahubDatabase, default_branch: Branch, site_scoped_pool: CoreNumberPool
) -> None:
    site_a = await scoped_site(db=db, branch=default_branch, name="site-a")
    device = await scoped_device_holding(
        db=db, branch=default_branch, pool=site_scoped_pool, name="device-1", site=site_a, number=5
    )
    older = await create_branch(branch_name="holds-the-deleted-node", db=db)
    deleted = await NodeManager.get_one(db=db, branch=default_branch, id=device.id, raise_on_error=True)
    await deleted.delete(db=db)

    figures = await division_figures(db=db, pool=site_scoped_pool, branch=default_branch)
    rows = await allocated_rows_in_division(
        db=db, pool=site_scoped_pool, branch=default_branch, entries=[("site", site_a.id)]
    )

    assert figures == {(site_a.id,): (1, 0, 1)}
    assert rows == [(5, older.name)]


async def test_a_number_counts_in_every_site_its_node_occupies_on_any_branch_in_allocation_and_reporting(
    db: InfrahubDatabase, default_branch: Branch, site_scoped_pool: CoreNumberPool
) -> None:
    """Pin how a division pairs a number with the sites of its holding Node across branches.

    Division membership is read across every live branch, independently of the branch that holds the number.
    The default branch holds 5 in site-b, and the other branch moves the device to site-c with a number outside
    the pool's range, so no branch holds 5 in site-c. The allocation and reporting queries still count 5 in
    site-c. For allocation this is deliberate: merging both branches would put 5 in site-c, so the pool must not
    hand 5 to another site-c device. The reporting queries apply the same rule, so they agree with allocation.
    """
    site_b = await scoped_site(db=db, branch=default_branch, name="site-b")
    site_c = await scoped_site(db=db, branch=default_branch, name="site-c")
    device = await scoped_device_holding(
        db=db, branch=default_branch, pool=site_scoped_pool, name="device-a", site=site_b, number=5
    )
    branch = await create_branch(branch_name="moves-device-a-out-of-range", db=db)
    # on the branch, move device from site-b to site-c and move the value our of the pool range
    on_branch = await NodeManager.get_one(db=db, branch=branch, id=device.id, raise_on_error=True)
    await on_branch.get_relationship(name="site").update(db=db, data=site_c)
    on_branch.get_attribute(SCOPED_ATTRIBUTE_NAME).value = SCOPED_POOL_END + 40
    await on_branch.save(db=db)

    repository = NumberPoolRepository(db=db)
    space = EffectiveSpace(ranges=await repository.get_pool_ranges(pool_id=site_scoped_pool.id), domain=NumberDomain())
    element_fields = element_fields_of(pool=site_scoped_pool, branch=default_branch)

    # The branch's out-of-range number is outside every figure, so only the default branch's 5 is counted.
    # 5 is counted in site-c too, because the Node is in site-c on the other branch.
    assert await division_figures(db=db, pool=site_scoped_pool, branch=default_branch) == {
        (site_b.id,): (1, 1, 0),
        (site_c.id,): (1, 1, 0),
    }

    for site_name, site in (("site-b", site_b), ("site-c", site_c)):
        division = Division.from_entries(entries=[("site", site.id)], element_fields=element_fields)
        # Reporting: the allocated numbers list 5 in both sites, on the default branch that holds it.
        reported = await allocated_rows_in_division(
            db=db, pool=site_scoped_pool, branch=default_branch, entries=[("site", site.id)]
        )
        assert reported == [(5, default_branch.name)], site_name
        # Allocation: the used numbers of the division match the reported ones.
        used = await repository.get_used(pool=site_scoped_pool, branch=default_branch, space=space, division=division)
        assert used == [value for value, _ in reported], site_name
        # Allocation: the lowest free number skips 5, so the pool never hands 5 to another device in either site.
        free_from_5 = await repository.get_free(
            pool=site_scoped_pool,
            branch=default_branch,
            min_value=5,
            max_value=SCOPED_POOL_END,
            division=division,
        )
        assert free_from_5 == 6, site_name


async def test_deleting_the_branch_that_moved_a_node_removes_it_from_the_new_site(
    db: InfrahubDatabase, default_branch: Branch, site_scoped_pool: CoreNumberPool
) -> None:
    site_a = await scoped_site(db=db, branch=default_branch, name="site-a")
    site_c = await scoped_site(db=db, branch=default_branch, name="site-c")
    device = await scoped_device_holding(
        db=db, branch=default_branch, pool=site_scoped_pool, name="device-1", site=site_a, number=5
    )
    branch = await create_branch(branch_name="moves-device-1", db=db)
    moved = await NodeManager.get_one(db=db, branch=branch, id=device.id, raise_on_error=True)
    await moved.get_relationship(name="site").update(db=db, data=site_c)
    await moved.save(db=db)

    await delete_branch(db=db, branch=branch)

    assert await division_figures(db=db, pool=site_scoped_pool, branch=default_branch) == {(site_a.id,): (1, 1, 0)}


async def test_a_role_changed_on_a_branch_counts_in_the_division_of_each_role(
    db: InfrahubDatabase, default_branch: Branch, site_role_scoped_pool: CoreNumberPool
) -> None:
    site_a = await scoped_site(db=db, branch=default_branch, name="site-a")
    device = await scoped_device_holding(
        db=db, branch=default_branch, pool=site_role_scoped_pool, name="device-1", site=site_a, number=3, role="leaf"
    )
    branch = await create_branch(branch_name="makes-device-1-a-spine", db=db)
    changed = await NodeManager.get_one(db=db, branch=branch, id=device.id, raise_on_error=True)
    changed.get_attribute("role").value = "spine"
    await changed.save(db=db)

    figures = await division_figures(db=db, pool=site_role_scoped_pool, branch=default_branch)

    assert figures == {(site_a.id, "leaf"): (1, 1, 0), (site_a.id, "spine"): (1, 1, 0)}


async def allocated_rows_in_division(
    db: InfrahubDatabase, pool: CoreNumberPool, branch: Branch, entries: list[tuple[str, object]]
) -> list[tuple[int, str]]:
    """The value and holding branch of each row the allocated numbers query reports for the division."""
    query = await NumberPoolGetAllocated.init(
        db=db,
        pool=pool,
        ranges=[[SCOPED_POOL_START, SCOPED_POOL_END]],
        division=Division.from_entries(entries=entries, element_fields=element_fields_of(pool=pool, branch=branch)),
        branch=branch,
    )
    await query.execute(db=db)
    return [(row.value, row.branch) for row in query.get_data()]


async def allocated_values_in_division(
    db: InfrahubDatabase, pool: CoreNumberPool, branch: Branch, entries: list[tuple[str, object]]
) -> list[int]:
    rows = await allocated_rows_in_division(db=db, pool=pool, branch=branch, entries=entries)
    return [value for value, _ in rows]


async def test_a_number_held_on_the_default_branch_and_on_a_branch_counts_once_in_its_division(
    db: InfrahubDatabase, default_branch: Branch, site_scoped_pool: CoreNumberPool
) -> None:
    site_a = await scoped_site(db=db, branch=default_branch, name="site-a")
    await scoped_device_holding(
        db=db, branch=default_branch, pool=site_scoped_pool, name="device-1", site=site_a, number=5
    )
    branch = await create_branch(branch_name="holds-5-again", db=db)
    await scoped_device_holding(db=db, branch=branch, pool=site_scoped_pool, name="device-2", site=site_a, number=5)

    figures = await division_figures(db=db, pool=site_scoped_pool, branch=default_branch)

    assert figures == {(site_a.id,): (1, 1, 0)}


async def test_the_allocated_numbers_of_a_division_keep_a_node_moved_on_the_default_branch_after_a_branch_forked(
    db: InfrahubDatabase, default_branch: Branch, site_scoped_pool: CoreNumberPool
) -> None:
    site_a = await scoped_site(db=db, branch=default_branch, name="site-a")
    site_c = await scoped_site(db=db, branch=default_branch, name="site-c")
    device = await scoped_device_holding(
        db=db, branch=default_branch, pool=site_scoped_pool, name="device-1", site=site_a, number=5
    )
    await create_branch(branch_name="forked-in-site-a", db=db)
    moved = await NodeManager.get_one(db=db, branch=default_branch, id=device.id, raise_on_error=True)
    await moved.get_relationship(name="site").update(db=db, data=site_c)
    await moved.save(db=db)

    for site in (site_a, site_c):
        values = await allocated_values_in_division(
            db=db, pool=site_scoped_pool, branch=default_branch, entries=[("site", site.id)]
        )
        assert values == [5]


async def test_the_allocated_numbers_of_a_division_drop_a_node_once_the_branch_that_moved_it_is_deleted(
    db: InfrahubDatabase, default_branch: Branch, site_scoped_pool: CoreNumberPool
) -> None:
    site_a = await scoped_site(db=db, branch=default_branch, name="site-a")
    site_c = await scoped_site(db=db, branch=default_branch, name="site-c")
    device = await scoped_device_holding(
        db=db, branch=default_branch, pool=site_scoped_pool, name="device-1", site=site_a, number=5
    )
    branch = await create_branch(branch_name="moves-device-1", db=db)
    moved = await NodeManager.get_one(db=db, branch=branch, id=device.id, raise_on_error=True)
    await moved.get_relationship(name="site").update(db=db, data=site_c)
    await moved.save(db=db)

    await delete_branch(db=db, branch=branch)

    on_site_c = await allocated_values_in_division(
        db=db, pool=site_scoped_pool, branch=default_branch, entries=[("site", site_c.id)]
    )
    on_site_a = await allocated_values_in_division(
        db=db, pool=site_scoped_pool, branch=default_branch, entries=[("site", site_a.id)]
    )
    assert (on_site_a, on_site_c) == ([5], [])


FLOORED_DEVICE = deepcopy(SCOPED_DEVICE)
FLOORED_DEVICE.attributes.append(AttributeSchema(name="floor", kind="Number", optional=False))
FLOORED_POOL_SCHEMA = SchemaRoot(
    generics=SCOPED_POOL_SCHEMA.generics,
    nodes=[FLOORED_DEVICE if node.kind == SCOPED_DEVICE.kind else node for node in SCOPED_POOL_SCHEMA.nodes],
)


async def test_a_number_scope_element_lists_and_filters_its_divisions_as_numbers(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    await save_schema_kinds(db=db, schema=FLOORED_POOL_SCHEMA)
    registry.node[InfrahubKind.NUMBERPOOL] = CoreNumberPool
    pool = await scoped_pool(db=db, name="vlan-per-floor", allocation_scope=["floor"])
    site = await scoped_site(db=db, branch=default_branch, name="site-a")
    for name, floor, number in (("f1-a", 1, 1), ("f1-b", 1, 2), ("f2-a", 2, 3)):
        device = await Node.init(db=db, schema=SCOPED_DEVICE.kind, branch=default_branch)
        await device.new(
            db=db,
            name=name,
            role="leaf",
            tags=["red"],
            site=site,
            floor=floor,
            vlan_id={"value": number, "from_pool": {"id": pool.id}},
        )
        await device.save(db=db)

    figures = await division_figures(db=db, pool=pool, branch=default_branch)
    on_floor_1 = await allocated_values_in_division(db=db, pool=pool, branch=default_branch, entries=[("floor", 1)])

    assert figures == {(1,): (2, 2, 0), (2,): (1, 1, 0)}
    assert all(type(value) is int for values in figures for value in values)
    assert on_floor_1 == [1, 2]


DIRECTED_DEVICE = deepcopy(SCOPED_DEVICE)
DIRECTED_DEVICE.relationships.extend(
    [
        RelationshipSchema(
            name="uplink",
            peer=SCOPED_SITE.kind,
            identifier="scope_device__uplink",
            cardinality=RelationshipCardinality.ONE,
            direction=RelationshipDirection.OUTBOUND,
            optional=False,
        ),
        RelationshipSchema(
            name="downlink",
            peer=SCOPED_SITE.kind,
            identifier="scope_device__downlink",
            cardinality=RelationshipCardinality.ONE,
            direction=RelationshipDirection.INBOUND,
            optional=False,
        ),
    ]
)
DIRECTED_POOL_SCHEMA = SchemaRoot(
    generics=SCOPED_POOL_SCHEMA.generics,
    nodes=[DIRECTED_DEVICE if node.kind == SCOPED_DEVICE.kind else node for node in SCOPED_POOL_SCHEMA.nodes],
)


async def test_an_outbound_and_an_inbound_scope_element_list_and_filter_their_peers(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    await save_schema_kinds(db=db, schema=DIRECTED_POOL_SCHEMA)
    registry.node[InfrahubKind.NUMBERPOOL] = CoreNumberPool
    pool = await scoped_pool(db=db, name="vlan-per-link", allocation_scope=["uplink", "downlink"])
    site_a = await scoped_site(db=db, branch=default_branch, name="site-a")
    site_b = await scoped_site(db=db, branch=default_branch, name="site-b")
    for name, uplink, downlink, number in (
        ("ab-1", site_a, site_b, 1),
        ("ab-2", site_a, site_b, 2),
        ("ba-1", site_b, site_a, 3),
    ):
        device = await Node.init(db=db, schema=SCOPED_DEVICE.kind, branch=default_branch)
        await device.new(
            db=db,
            name=name,
            role="leaf",
            tags=["red"],
            site=site_a,
            uplink=uplink,
            downlink=downlink,
            vlan_id={"value": number, "from_pool": {"id": pool.id}},
        )
        await device.save(db=db)

    figures = await division_figures(db=db, pool=pool, branch=default_branch)
    a_to_b = await allocated_values_in_division(
        db=db, pool=pool, branch=default_branch, entries=[("uplink", site_a.id), ("downlink", site_b.id)]
    )

    assert figures == {(site_a.id, site_b.id): (2, 2, 0), (site_b.id, site_a.id): (1, 1, 0)}
    assert a_to_b == [1, 2]


async def test_an_empty_value_lists_and_filters_the_division_of_the_empty_value(
    db: InfrahubDatabase, default_branch: Branch, site_role_scoped_pool: CoreNumberPool
) -> None:
    site_a = await scoped_site(db=db, branch=default_branch, name="site-a")
    for name, role, number in (("device-1", "", 1), ("device-2", "leaf", 2)):
        await scoped_device_holding(
            db=db, branch=default_branch, pool=site_role_scoped_pool, name=name, site=site_a, number=number, role=role
        )

    figures = await division_figures(db=db, pool=site_role_scoped_pool, branch=default_branch)
    empty_role = await allocated_values_in_division(
        db=db, pool=site_role_scoped_pool, branch=default_branch, entries=[("role", "")]
    )

    assert figures == {(site_a.id, ""): (1, 1, 0), (site_a.id, "leaf"): (1, 1, 0)}
    assert empty_role == [1]


async def test_a_node_copied_by_a_kind_migration_counts_in_the_site_of_each_copy(
    db: InfrahubDatabase, default_branch: Branch, site_scoped_pool: CoreNumberPool
) -> None:
    """The migration keeps the kind and leaves the old Node vertex live on a branch that moved it to site C."""
    site_a = await scoped_site(db=db, branch=default_branch, name="site-a")
    site_c = await scoped_site(db=db, branch=default_branch, name="site-c")
    device = await scoped_device_holding(
        db=db, branch=default_branch, pool=site_scoped_pool, name="device-1", site=site_a, number=5
    )
    branch = await create_branch(branch_name="moves-device-1", db=db)
    moved = await NodeManager.get_one(db=db, branch=branch, id=device.id, raise_on_error=True)
    await moved.get_relationship(name="site").update(db=db, data=site_c)
    await moved.save(db=db)
    migration = await NodeDuplicateQuery.init(
        db=db,
        branch=default_branch,
        kind_updates_map={
            SCOPED_DEVICE.kind: SchemaNodeInfo(
                name=SCOPED_DEVICE.name,
                namespace=SCOPED_DEVICE.namespace,
                labels=[SCOPED_DEVICE.kind, "ScopeMigrated"],
                kind=SCOPED_DEVICE.kind,
            )
        },
    )
    await migration.execute(db=db)

    figures = await division_figures(db=db, pool=site_scoped_pool, branch=default_branch)

    assert figures == {(site_a.id,): (1, 1, 0), (site_c.id,): (1, 1, 0)}


async def test_a_node_deleted_on_the_default_branch_leaves_its_division_and_one_deleted_on_a_branch_stays(
    db: InfrahubDatabase, default_branch: Branch, site_scoped_pool: CoreNumberPool
) -> None:
    site_a = await scoped_site(db=db, branch=default_branch, name="site-a")
    kept = await scoped_device_holding(
        db=db, branch=default_branch, pool=site_scoped_pool, name="device-1", site=site_a, number=1
    )
    removed = await scoped_device_holding(
        db=db, branch=default_branch, pool=site_scoped_pool, name="device-2", site=site_a, number=2
    )
    await removed.delete(db=db)
    branch = await create_branch(branch_name="deletes-device-1", db=db)
    kept_on_branch = await NodeManager.get_one(db=db, branch=branch, id=kept.id, raise_on_error=True)
    await kept_on_branch.delete(db=db)

    figures = await division_figures(db=db, pool=site_scoped_pool, branch=default_branch)
    values = await allocated_values_in_division(
        db=db, pool=site_scoped_pool, branch=default_branch, entries=[("site", site_a.id)]
    )

    assert figures == {(site_a.id,): (1, 1, 0)}
    assert values == [1]
