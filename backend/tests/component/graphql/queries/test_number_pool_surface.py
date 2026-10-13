from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import pytest

from infrahub.core import registry
from infrahub.core.constants import InfrahubKind
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.node.resource_manager.number_pool import CoreNumberPool
from infrahub.core.query.resource_manager import NumberPoolGetAllocated
from infrahub.core.schema import AttributeSchema, SchemaRoot
from infrahub.core.schema.attribute_parameters import NumberAttributeParameters
from infrahub.core.schema.attribute_schema import NumberAttributeSchema
from infrahub.graphql.initialization import GraphqlParams, prepare_graphql_params
from infrahub.pools.scope import AllocationScopeResolver
from tests.helpers.db_query_counter import CountingInfrahubDatabase
from tests.helpers.graphql import graphql
from tests.helpers.number_pool import (
    SCOPED_DEVICE,
    SCOPED_POOL_SCHEMA,
    SCOPED_SITE,
    add_pool_range,
    save_schema_kinds,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase

OTHER_BRANCH = "branch1"
SCOPED_POOL_NAME = "Device index"
UNSCOPED_POOL_NAME = "VLANs"
SMALL_POOL_NAME = "Small device index"
FIRST_RANGE = "1 - 50"
SECOND_RANGE = "51 - 100"


FIGURES = "size used used_default_branch used_branches utilization utilization_default_branch utilization_branches"

UTILIZATION_QUERY = f"""
query NumberPoolUtilization($pool_id: String!, $division: [NumberPoolDivisionEntryInput!]) {{
  InfrahubNumberPoolUtilization(pool_id: $pool_id, division: $division) {{
    id
    display_label
    allocation_scope {{ id name }}
    figures {{ {FIGURES} }}
    ranges {{ id display_label start end weight figures {{ {FIGURES} }} }}
  }}
}}
"""

DIVISIONS_QUERY = f"""
query NumberPoolDivisions($pool_id: String!) {{
  InfrahubNumberPoolDivisions(pool_id: $pool_id) {{
    count
    allocation_scope {{ id name }}
    divisions {{
      display_label
      entries {{ id path value display_label peer_kind }}
      figures {{ {FIGURES} }}
    }}
  }}
}}
"""

ALLOCATIONS_QUERY = """
query NumberPoolAllocations(
  $pool_id: String!
  $division: [NumberPoolDivisionEntryInput!]
  $range_id: String
  $branch: String
  $provenance: PoolRecordProvenance
  $offset: Int
  $limit: Int
) {
  InfrahubNumberPoolAllocations(
    pool_id: $pool_id
    division: $division
    range_id: $range_id
    branch: $branch
    provenance: $provenance
    offset: $offset
    limit: $limit
  ) {
    count
    allocations {
      value
      branch
      identifier
      provenance
      holder { id hfid kind display_label }
      range { id display_label }
    }
  }
}
"""


@dataclass
class SurfaceDataset:
    """Three pools over the device's `vlan_id`, each with the ranges 1 - 50 (weight 10) and 51 - 100.

    The scoped pool divides by `site`; every number it tracks was provided by a user:

    - site-a: D0 holds 1, D1 holds 5 and D2 holds 6 on the default branch; on the other branch D1 sits
      in site-c and X, which exists only there, holds 7
    - site-b: B0 holds 51, B1 holds 52 and B2 holds 53 on the default branch; on the other branch B1 holds 54
    - site-d holds no number

    D1 occupies site-a on the default branch and site-c on the other branch, so it counts in both.

    The unscoped pool allocated 1 to sw1 on the default branch and 2 to sw2 on the other branch, and
    tracks 51, which a user gave sw3 on the default branch.

    The small pool also divides by `site` and tracks 9, which a user gave R0 in site-d on the default branch.
    """

    default_branch: Branch
    other_branch: Branch = field(init=False)
    scoped_pool_id: str = ""
    unscoped_pool_id: str = ""
    small_pool_id: str = ""
    site_element_id: str = ""
    sites: dict[str, str] = field(default_factory=dict)
    devices: dict[str, str] = field(default_factory=dict)
    ranges: dict[tuple[str, str], str] = field(default_factory=dict)

    def site_entry(self, site: str) -> dict[str, Any]:
        return {
            "id": self.site_element_id,
            "path": "site",
            "value": self.sites[site],
            "display_label": site,
            "peer_kind": SCOPED_SITE.kind,
        }

    def division(self, site: str) -> list[dict[str, str]]:
        return [{"path": "site", "value": self.sites[site]}]


def figures(size: int, default_branch: int, branches: int) -> dict[str, Any]:
    used = default_branch + branches
    return {
        "size": size,
        "used": used,
        "used_default_branch": default_branch,
        "used_branches": branches,
        "utilization": used * 100 / size,
        "utilization_default_branch": default_branch * 100 / size,
        "utilization_branches": branches * 100 / size,
    }


def stored_device_scope(names: list[str]) -> list[dict[str, str]]:
    return (
        AllocationScopeResolver(schema_branch=registry.schema.get_schema_branch(name=registry.default_branch))
        .resolve(kind=SCOPED_DEVICE.kind, entries=names)
        .to_stored()
    )


async def two_range_pool(db: InfrahubDatabase, name: str, scope: list[str] | None) -> tuple[str, str, str]:
    """Create a pool over the device's `vlan_id` and return its id and the ids of its two ranges."""
    pool = await CoreNumberPool.init(db=db, schema=InfrahubKind.NUMBERPOOL)
    await pool.new(
        db=db,
        name=name,
        node=SCOPED_DEVICE.kind,
        node_attribute="vlan_id",
        allocation_scope=stored_device_scope(names=scope) if scope else None,
    )
    await pool.save(db=db)
    first = await add_pool_range(db=db, pool=pool, start=1, end=50, weight=10)
    second = await add_pool_range(db=db, pool=pool, start=51, end=100)
    return pool.id, first.id, second.id


async def create_device(
    db: InfrahubDatabase, dataset: SurfaceDataset, branch: Branch, name: str, site: str, vlan_id: dict[str, Any]
) -> Node:
    node = await Node.init(db=db, schema=SCOPED_DEVICE.kind, branch=branch)
    await node.new(db=db, name=name, role="leaf", tags=["red"], site=dataset.sites[site], vlan_id=vlan_id)
    await node.save(db=db)
    dataset.devices[name] = node.id
    return node


async def device_with_number(
    db: InfrahubDatabase, dataset: SurfaceDataset, branch: Branch, name: str, site: str, pool_id: str, number: int
) -> None:
    node = await create_device(
        db=db,
        dataset=dataset,
        branch=branch,
        name=name,
        site=site,
        vlan_id={"value": number, "from_pool": {"id": pool_id}},
    )
    assert node.get_attribute("vlan_id").value == number


async def device_from_pool(
    db: InfrahubDatabase, dataset: SurfaceDataset, branch: Branch, name: str, expected: int
) -> None:
    node = await create_device(
        db=db,
        dataset=dataset,
        branch=branch,
        name=name,
        site="site-d",
        vlan_id={"from_pool": {"id": dataset.unscoped_pool_id}},
    )
    assert node.get_attribute("vlan_id").value == expected


async def tracked_numbers(db: InfrahubDatabase, dataset: SurfaceDataset, pool_id: str) -> list[tuple[int, str, str]]:
    """The value, branch and holding object name of every number the pool tracks, read without the dedicated queries."""
    pool = await NodeManager.get_one(db=db, id=pool_id, kind=InfrahubKind.NUMBERPOOL, raise_on_error=True)
    query = await NumberPoolGetAllocated.init(
        db=db, pool=pool, ranges=[[1, 100]], branch=dataset.default_branch, branch_agnostic=True
    )
    await query.execute(db=db)
    names_by_id = {node_id: name for name, node_id in dataset.devices.items()}
    return [(row.value, row.branch, names_by_id[row.id]) for row in query.get_data()]


@dataclass(frozen=True)
class RefusalCase:
    name: str
    query: str
    variables: Callable[[SurfaceDataset], dict[str, Any]]
    message: Callable[[SurfaceDataset], str]


REFUSAL_CASES = [
    RefusalCase(
        name="utilization-scoped-pool-without-division",
        query=UTILIZATION_QUERY,
        variables=lambda data: {"pool_id": data.scoped_pool_id},
        message=lambda data: (
            f"The pool {data.scoped_pool_id} has an allocation scope; give a division with a value for every "
            "element to read its utilization"
        ),
    ),
    RefusalCase(
        name="path-not-in-scope",
        query=ALLOCATIONS_QUERY,
        variables=lambda data: {"pool_id": data.scoped_pool_id, "division": [{"path": "role", "value": "leaf"}]},
        message=lambda _: 'The division entry "role" is not an element of the pool\'s allocation scope',
    ),
    RefusalCase(
        name="range-of-another-pool",
        query=ALLOCATIONS_QUERY,
        variables=lambda data: {
            "pool_id": data.unscoped_pool_id,
            "range_id": data.ranges[SCOPED_POOL_NAME, FIRST_RANGE],
        },
        message=lambda data: (
            f"The range {data.ranges[SCOPED_POOL_NAME, FIRST_RANGE]} does not belong to the pool "
            f"{data.unscoped_pool_id}"
        ),
    ),
    *(
        RefusalCase(
            name=f"unknown-pool-{query_name}",
            query=query,
            variables=lambda _: {"pool_id": "unknown-pool"},
            message=lambda _: f"Unable to find the node unknown-pool / {InfrahubKind.NUMBERPOOL} in the database.",
        )
        for query_name, query in (
            ("utilization", UTILIZATION_QUERY),
            ("divisions", DIVISIONS_QUERY),
            ("allocations", ALLOCATIONS_QUERY),
        )
    ),
]


class TestNumberPoolSurface:
    @pytest.fixture(scope="class")
    async def dataset(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        register_core_models_schema_scope_class: SchemaBranch,
    ) -> SurfaceDataset:
        await save_schema_kinds(db=db, schema=SCOPED_POOL_SCHEMA)
        registry.node[InfrahubKind.NUMBERPOOL] = CoreNumberPool
        main = default_branch_scope_class
        dataset = SurfaceDataset(default_branch=main)
        site_element = registry.schema.get(name=SCOPED_DEVICE.kind, duplicate=False).get_relationship(name="site")
        assert site_element.id
        dataset.site_element_id = site_element.id

        for name in ("site-a", "site-b", "site-c", "site-d"):
            site_node = await Node.init(db=db, schema=SCOPED_SITE.kind, branch=main)
            await site_node.new(db=db, name=name)
            await site_node.save(db=db)
            dataset.sites[name] = site_node.id

        for pool_name, scope in ((SCOPED_POOL_NAME, ["site"]), (UNSCOPED_POOL_NAME, None)):
            pool_id, first, second = await two_range_pool(db=db, name=pool_name, scope=scope)
            dataset.ranges[pool_name, FIRST_RANGE] = first
            dataset.ranges[pool_name, SECOND_RANGE] = second
            if scope:
                dataset.scoped_pool_id = pool_id
            else:
                dataset.unscoped_pool_id = pool_id
        dataset.small_pool_id, _, _ = await two_range_pool(db=db, name=SMALL_POOL_NAME, scope=["site"])

        for name, site, number in (
            ("D0", "site-a", 1),
            ("D1", "site-a", 5),
            ("D2", "site-a", 6),
            ("B0", "site-b", 51),
            ("B1", "site-b", 52),
            ("B2", "site-b", 53),
        ):
            await device_with_number(
                db=db, dataset=dataset, branch=main, name=name, site=site, pool_id=dataset.scoped_pool_id, number=number
            )
        await device_from_pool(db=db, dataset=dataset, branch=main, name="sw1", expected=1)
        await device_with_number(
            db=db, dataset=dataset, branch=main, name="R0", site="site-d", pool_id=dataset.small_pool_id, number=9
        )
        await device_with_number(
            db=db, dataset=dataset, branch=main, name="sw3", site="site-d", pool_id=dataset.unscoped_pool_id, number=51
        )

        branch = dataset.other_branch = await create_branch(db=db, branch_name=OTHER_BRANCH)
        moved = await NodeManager.get_one(db=db, branch=branch, id=dataset.devices["D1"], raise_on_error=True)
        await moved.get_relationship("site").update(db=db, data=dataset.sites["site-c"])
        await moved.save(db=db)
        renumbered = await NodeManager.get_one(db=db, branch=branch, id=dataset.devices["B1"], raise_on_error=True)
        renumbered.get_attribute("vlan_id").value = 54
        await renumbered.save(db=db)
        await device_with_number(
            db=db, dataset=dataset, branch=branch, name="X", site="site-a", pool_id=dataset.scoped_pool_id, number=7
        )
        await device_from_pool(db=db, dataset=dataset, branch=branch, name="sw2", expected=2)

        assert await tracked_numbers(db=db, dataset=dataset, pool_id=dataset.scoped_pool_id) == [
            (1, "main", "D0"),
            (5, "main", "D1"),
            (6, "main", "D2"),
            (7, OTHER_BRANCH, "X"),
            (51, "main", "B0"),
            (52, "main", "B1"),
            (53, "main", "B2"),
            (54, OTHER_BRANCH, "B1"),
        ]
        assert await tracked_numbers(db=db, dataset=dataset, pool_id=dataset.unscoped_pool_id) == [
            (1, "main", "sw1"),
            (2, OTHER_BRANCH, "sw2"),
            (51, "main", "sw3"),
        ]
        assert await tracked_numbers(db=db, dataset=dataset, pool_id=dataset.small_pool_id) == [(9, "main", "R0")]
        return dataset

    @pytest.fixture(scope="class")
    async def gql_params(self, db: InfrahubDatabase, dataset: SurfaceDataset) -> GraphqlParams:
        return await prepare_graphql_params(db=db, branch=dataset.default_branch)

    @pytest.fixture(scope="class")
    async def branch_gql_params(self, db: InfrahubDatabase, dataset: SurfaceDataset) -> GraphqlParams:
        return await prepare_graphql_params(db=db, branch=dataset.other_branch)

    @staticmethod
    async def _execute(gql_params: GraphqlParams, query: str, variables: dict[str, Any]) -> Any:
        return await graphql(
            schema=gql_params.schema,
            source=query,
            context_value=gql_params.context,
            root_value=None,
            variable_values=variables,
        )

    async def _data(self, gql_params: GraphqlParams, query: str, **variables: Any) -> dict[str, Any]:
        result = await self._execute(gql_params=gql_params, query=query, variables=variables)
        assert result.errors is None
        assert result.data is not None
        return result.data

    async def _error(self, gql_params: GraphqlParams, query: str, **variables: Any) -> str:
        result = await self._execute(gql_params=gql_params, query=query, variables=variables)
        assert result.errors is not None
        return result.errors[0].message

    @staticmethod
    def _rows(data: dict[str, Any]) -> list[tuple[int, str, str, str, str]]:
        """The value, branch, holding object, provenance and range of each row of an allocations page."""
        return [
            (
                row["value"],
                row["branch"],
                row["holder"]["display_label"],
                row["provenance"],
                row["range"]["display_label"],
            )
            for row in data["InfrahubNumberPoolAllocations"]["allocations"]
        ]

    @pytest.mark.parametrize("on_other_branch", [False, True], ids=["default-branch", "other-branch"])
    async def test_divisions_count_a_holding_object_in_every_division_it_occupies(
        self,
        dataset: SurfaceDataset,
        gql_params: GraphqlParams,
        branch_gql_params: GraphqlParams,
        on_other_branch: bool,
    ) -> None:
        params = branch_gql_params if on_other_branch else gql_params

        data = await self._data(params, DIVISIONS_QUERY, pool_id=dataset.scoped_pool_id)

        assert data["InfrahubNumberPoolDivisions"] == {
            "count": 3,
            "allocation_scope": [{"id": dataset.site_element_id, "name": "site"}],
            "divisions": [
                {
                    "display_label": "site-a",
                    "entries": [dataset.site_entry("site-a")],
                    "figures": figures(size=100, default_branch=3, branches=1),
                },
                {
                    "display_label": "site-b",
                    "entries": [dataset.site_entry("site-b")],
                    "figures": figures(size=100, default_branch=3, branches=1),
                },
                {
                    "display_label": "site-c",
                    "entries": [dataset.site_entry("site-c")],
                    "figures": figures(size=100, default_branch=1, branches=0),
                },
            ],
        }

    async def test_utilization_of_one_division(self, dataset: SurfaceDataset, gql_params: GraphqlParams) -> None:
        data = await self._data(
            gql_params, UTILIZATION_QUERY, pool_id=dataset.scoped_pool_id, division=dataset.division("site-b")
        )

        assert data["InfrahubNumberPoolUtilization"] == {
            "id": dataset.scoped_pool_id,
            "display_label": SCOPED_POOL_NAME,
            "allocation_scope": [{"id": dataset.site_element_id, "name": "site"}],
            "figures": figures(size=100, default_branch=3, branches=1),
            "ranges": [
                {
                    "id": dataset.ranges[SCOPED_POOL_NAME, FIRST_RANGE],
                    "display_label": FIRST_RANGE,
                    "start": 1,
                    "end": 50,
                    "weight": 10,
                    "figures": figures(size=50, default_branch=0, branches=0),
                },
                {
                    "id": dataset.ranges[SCOPED_POOL_NAME, SECOND_RANGE],
                    "display_label": SECOND_RANGE,
                    "start": 51,
                    "end": 100,
                    "weight": 0,
                    "figures": figures(size=50, default_branch=3, branches=1),
                },
            ],
        }

    async def test_allocations_of_a_division_give_one_row_per_branch_holding_a_number(
        self, dataset: SurfaceDataset, gql_params: GraphqlParams
    ) -> None:
        data = await self._data(
            gql_params, ALLOCATIONS_QUERY, pool_id=dataset.scoped_pool_id, division=dataset.division("site-b")
        )

        assert data["InfrahubNumberPoolAllocations"]["count"] == 4
        assert self._rows(data) == [
            (51, "main", "B0", "PROVIDED", SECOND_RANGE),
            (52, "main", "B1", "PROVIDED", SECOND_RANGE),
            (53, "main", "B2", "PROVIDED", SECOND_RANGE),
            (54, OTHER_BRANCH, "B1", "PROVIDED", SECOND_RANGE),
        ]
        assert data["InfrahubNumberPoolAllocations"]["allocations"][0]["holder"] == {
            "id": dataset.devices["B0"],
            "hfid": ["B0"],
            "kind": SCOPED_DEVICE.kind,
            "display_label": "B0",
        }

    @pytest.mark.parametrize("on_other_branch", [False, True], ids=["default-branch", "other-branch"])
    async def test_allocations_of_a_division_list_a_holding_object_moved_on_a_branch_in_both_sites(
        self,
        dataset: SurfaceDataset,
        gql_params: GraphqlParams,
        branch_gql_params: GraphqlParams,
        on_other_branch: bool,
    ) -> None:
        params = branch_gql_params if on_other_branch else gql_params

        site_a = await self._data(
            params, ALLOCATIONS_QUERY, pool_id=dataset.scoped_pool_id, division=dataset.division("site-a")
        )
        site_c = await self._data(
            params, ALLOCATIONS_QUERY, pool_id=dataset.scoped_pool_id, division=dataset.division("site-c")
        )

        assert [row[:3] for row in self._rows(site_a)] == [
            (1, "main", "D0"),
            (5, "main", "D1"),
            (6, "main", "D2"),
            (7, OTHER_BRANCH, "X"),
        ]
        assert [row[:3] for row in self._rows(site_c)] == [(5, "main", "D1")]

    async def test_allocations_filter_on_branch_and_provenance(
        self, dataset: SurfaceDataset, gql_params: GraphqlParams
    ) -> None:
        on_branch = await self._data(gql_params, ALLOCATIONS_QUERY, pool_id=dataset.scoped_pool_id, branch=OTHER_BRANCH)
        allocated = await self._data(
            gql_params, ALLOCATIONS_QUERY, pool_id=dataset.unscoped_pool_id, provenance="ALLOCATED"
        )

        assert self._rows(on_branch) == [
            (7, OTHER_BRANCH, "X", "PROVIDED", FIRST_RANGE),
            (54, OTHER_BRANCH, "B1", "PROVIDED", SECOND_RANGE),
        ]
        assert self._rows(allocated) == [
            (1, "main", "sw1", "ALLOCATED", FIRST_RANGE),
            (2, OTHER_BRANCH, "sw2", "ALLOCATED", FIRST_RANGE),
        ]

    async def test_allocations_count_the_rows_before_pagination(
        self, dataset: SurfaceDataset, gql_params: GraphqlParams
    ) -> None:
        data = await self._data(gql_params, ALLOCATIONS_QUERY, pool_id=dataset.scoped_pool_id, offset=2, limit=3)

        assert data["InfrahubNumberPoolAllocations"]["count"] == 8
        assert [row[:3] for row in self._rows(data)] == [
            (6, "main", "D2"),
            (7, OTHER_BRANCH, "X"),
            (51, "main", "B0"),
        ]

    async def test_a_limit_of_zero_gives_an_empty_page(
        self, dataset: SurfaceDataset, gql_params: GraphqlParams
    ) -> None:
        data = await self._data(gql_params, ALLOCATIONS_QUERY, pool_id=dataset.scoped_pool_id, offset=2, limit=0)

        assert data["InfrahubNumberPoolAllocations"] == {"count": 8, "allocations": []}

    async def test_unscoped_pool(self, dataset: SurfaceDataset, gql_params: GraphqlParams) -> None:
        utilization = await self._data(gql_params, UTILIZATION_QUERY, pool_id=dataset.unscoped_pool_id)
        divisions = await self._data(gql_params, DIVISIONS_QUERY, pool_id=dataset.unscoped_pool_id)
        first_range = await self._data(
            gql_params,
            ALLOCATIONS_QUERY,
            pool_id=dataset.unscoped_pool_id,
            range_id=dataset.ranges[UNSCOPED_POOL_NAME, FIRST_RANGE],
        )

        pool = utilization["InfrahubNumberPoolUtilization"]
        assert pool["allocation_scope"] == []
        assert pool["figures"] == figures(size=100, default_branch=2, branches=1)
        assert [(item["display_label"], item["figures"]) for item in pool["ranges"]] == [
            (FIRST_RANGE, figures(size=50, default_branch=1, branches=1)),
            (SECOND_RANGE, figures(size=50, default_branch=1, branches=0)),
        ]
        assert divisions["InfrahubNumberPoolDivisions"] == {"count": 0, "allocation_scope": [], "divisions": []}
        assert self._rows(first_range) == [
            (1, "main", "sw1", "ALLOCATED", FIRST_RANGE),
            (2, OTHER_BRANCH, "sw2", "ALLOCATED", FIRST_RANGE),
        ]

    @pytest.mark.parametrize(
        ("query", "pool"),
        [
            pytest.param(UTILIZATION_QUERY, "unscoped", id="utilization-unscoped-pool"),
            pytest.param(ALLOCATIONS_QUERY, "unscoped", id="allocations-unscoped-pool"),
            pytest.param(ALLOCATIONS_QUERY, "scoped", id="allocations-scoped-pool"),
        ],
    )
    async def test_an_empty_division_reads_like_no_division(
        self, dataset: SurfaceDataset, gql_params: GraphqlParams, query: str, pool: str
    ) -> None:
        pool_id = dataset.scoped_pool_id if pool == "scoped" else dataset.unscoped_pool_id

        with_empty_division = await self._data(gql_params, query, pool_id=pool_id, division=[])
        without_division = await self._data(gql_params, query, pool_id=pool_id)

        assert with_empty_division == without_division

    async def test_the_number_of_queries_does_not_grow_with_the_rows(
        self, db: InfrahubDatabase, dataset: SurfaceDataset
    ) -> None:
        counting_db = CountingInfrahubDatabase.from_db(db=db)
        on_main = await prepare_graphql_params(db=counting_db, branch=dataset.default_branch)

        queries: dict[str, int] = {}
        sizes: dict[str, int] = {}
        site_a_on_main = {"division": dataset.division("site-a"), "branch": dataset.default_branch.name}
        for label, pool_id, query, variables in (
            ("one division", dataset.small_pool_id, DIVISIONS_QUERY, {}),
            ("three divisions", dataset.scoped_pool_id, DIVISIONS_QUERY, {}),
            ("one row", dataset.scoped_pool_id, ALLOCATIONS_QUERY, {**site_a_on_main, "limit": 1}),
            ("three rows", dataset.scoped_pool_id, ALLOCATIONS_QUERY, site_a_on_main),
        ):
            counting_db.reset_counts()
            data = await self._data(on_main, query, pool_id=pool_id, **variables)
            queries[label] = sum(counting_db.query_counts.values())
            sizes[label] = len(
                data["InfrahubNumberPoolDivisions"]["divisions"]
                if query == DIVISIONS_QUERY
                else data["InfrahubNumberPoolAllocations"]["allocations"]
            )

        assert sizes == {"one division": 1, "three divisions": 3, "one row": 1, "three rows": 3}
        assert queries["one division"] > 0
        assert queries["one division"] == queries["three divisions"]
        assert queries["one row"] > 0
        assert queries["one row"] == queries["three rows"]

    @pytest.mark.parametrize("case", REFUSAL_CASES, ids=[case.name for case in REFUSAL_CASES])
    async def test_refusals(self, dataset: SurfaceDataset, gql_params: GraphqlParams, case: RefusalCase) -> None:
        assert await self._error(gql_params, case.query, **case.variables(dataset)) == case.message(dataset)


async def test_a_branch_whose_schema_lacks_a_scope_element_is_refused(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    await save_schema_kinds(db=db, schema=SCOPED_POOL_SCHEMA)
    registry.node[InfrahubKind.NUMBERPOOL] = CoreNumberPool
    stale_branch = await create_branch(db=db, branch_name="stale-branch")
    zoned_device = deepcopy(SCOPED_DEVICE)
    zoned_device.attributes.append(AttributeSchema(name="zone", kind="Text", optional=False, default_value="z1"))
    await save_schema_kinds(db=db, schema=SchemaRoot(nodes=[zoned_device]))
    pool_id, _, _ = await two_range_pool(db=db, name="zoned", scope=["zone"])
    params = await prepare_graphql_params(db=db, branch=stale_branch)

    result = await graphql(
        schema=params.schema,
        source=DIVISIONS_QUERY,
        context_value=params.context,
        root_value=None,
        variable_values={"pool_id": pool_id},
    )

    assert result.errors is not None
    assert result.errors[0].message == (
        f'The scope element "zone" of pool {pool_id} does not exist on {SCOPED_DEVICE.kind} on branch stale-branch'
    )


async def test_a_holding_object_that_cannot_be_read_keeps_its_row(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    await save_schema_kinds(db=db, schema=SCOPED_POOL_SCHEMA)
    registry.node[InfrahubKind.NUMBERPOOL] = CoreNumberPool
    pool_id, _, _ = await two_range_pool(db=db, name="orphans", scope=None)
    site = await Node.init(db=db, schema=SCOPED_SITE.kind, branch=default_branch)
    await site.new(db=db, name="site-a")
    await site.save(db=db)
    device = await Node.init(db=db, schema=SCOPED_DEVICE.kind, branch=default_branch)
    await device.new(db=db, name="D0", role="leaf", tags=["red"], site=site.id, vlan_id={"from_pool": {"id": pool_id}})
    await device.save(db=db)
    # Detaching the node from the root leaves its attribute holding the number while no node read finds it.
    await db.execute_query(
        query="MATCH (:Node {uuid: $uuid})-[r:IS_PART_OF]->(:Root) DELETE r", params={"uuid": device.id}
    )
    params = await prepare_graphql_params(db=db, branch=default_branch)

    result = await graphql(
        schema=params.schema,
        source=ALLOCATIONS_QUERY,
        context_value=params.context,
        root_value=None,
        variable_values={"pool_id": pool_id},
    )

    assert result.errors is None
    assert result.data is not None
    page = result.data["InfrahubNumberPoolAllocations"]
    assert page["count"] == 1
    assert [(row["value"], row["holder"]) for row in page["allocations"]] == [
        (1, {"id": device.id, "hfid": None, "kind": SCOPED_DEVICE.kind, "display_label": device.id})
    ]


async def test_a_number_and_a_boolean_scope_element_keep_their_type_from_the_divisions_to_the_filter(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    rack_device = deepcopy(SCOPED_DEVICE)
    rack_device.attributes.extend(
        [
            AttributeSchema(name="floor", kind="Number", optional=False, default_value=0),
            AttributeSchema(name="managed", kind="Boolean", optional=False, default_value=False),
        ]
    )
    await save_schema_kinds(
        db=db,
        schema=SchemaRoot(
            generics=SCOPED_POOL_SCHEMA.generics,
            nodes=[rack_device if node.kind == SCOPED_DEVICE.kind else node for node in SCOPED_POOL_SCHEMA.nodes],
        ),
    )
    registry.node[InfrahubKind.NUMBERPOOL] = CoreNumberPool
    pool_id, _, _ = await two_range_pool(db=db, name="per-floor", scope=["floor", "managed"])
    site = await Node.init(db=db, schema=SCOPED_SITE.kind, branch=default_branch)
    await site.new(db=db, name="site-a")
    await site.save(db=db)
    for name, floor, managed, number in (("F1", 1, True, 1), ("F2", 1, True, 2), ("F3", 2, False, 3)):
        device = await Node.init(db=db, schema=SCOPED_DEVICE.kind, branch=default_branch)
        await device.new(
            db=db,
            name=name,
            role="leaf",
            tags=["red"],
            site=site.id,
            floor=floor,
            managed=managed,
            vlan_id={"value": number, "from_pool": {"id": pool_id}},
        )
        await device.save(db=db)
    params = await prepare_graphql_params(db=db, branch=default_branch)

    async def execute(query: str, variables: dict[str, Any]) -> Any:
        return await graphql(
            schema=params.schema,
            source=query,
            context_value=params.context,
            root_value=None,
            variable_values={"pool_id": pool_id, **variables},
        )

    listed = await execute(DIVISIONS_QUERY, {})
    assert listed.errors is None
    divisions = listed.data["InfrahubNumberPoolDivisions"]["divisions"]
    values = [[(entry["path"], entry["value"]) for entry in division["entries"]] for division in divisions]
    assert values == [[("floor", 1), ("managed", True)], [("floor", 2), ("managed", False)]]
    assert all(type(entry["value"]) is not str for division in divisions for entry in division["entries"])

    division = [{"path": entry["path"], "value": entry["value"]} for entry in divisions[0]["entries"]]
    measured = await execute(UTILIZATION_QUERY, {"division": division})
    assert measured.errors is None
    assert measured.data["InfrahubNumberPoolUtilization"]["figures"]["used"] == 2

    refused = await execute(UTILIZATION_QUERY, {"division": [{"path": "floor", "value": "1"}, division[1]]})
    assert refused.errors is not None
    assert refused.errors[0].message == "1 is not a valid Number at floor"


async def test_the_bounds_and_exclusions_of_the_attribute_narrow_the_space_of_every_dedicated_query(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    bounded_device = deepcopy(SCOPED_DEVICE)
    bounded_device.attributes = [
        NumberAttributeSchema(
            name="vlan_id",
            kind="Number",
            optional=True,
            parameters=NumberAttributeParameters(max_value=40, excluded_values="5-9"),
        )
        if attribute.name == "vlan_id"
        else attribute
        for attribute in bounded_device.attributes
    ]
    await save_schema_kinds(
        db=db,
        schema=SchemaRoot(
            generics=SCOPED_POOL_SCHEMA.generics,
            nodes=[bounded_device if node.kind == SCOPED_DEVICE.kind else node for node in SCOPED_POOL_SCHEMA.nodes],
        ),
    )
    registry.node[InfrahubKind.NUMBERPOOL] = CoreNumberPool
    pool_id, _, _ = await two_range_pool(db=db, name="bounded", scope=["site"])
    site = await Node.init(db=db, schema=SCOPED_SITE.kind, branch=default_branch)
    await site.new(db=db, name="site-a")
    await site.save(db=db)
    for name, number in (("D3", 3), ("D30", 30)):
        device = await Node.init(db=db, schema=SCOPED_DEVICE.kind, branch=default_branch)
        await device.new(
            db=db,
            name=name,
            role="leaf",
            tags=["red"],
            site=site.id,
            vlan_id={"value": number, "from_pool": {"id": pool_id}},
        )
        await device.save(db=db)
    params = await prepare_graphql_params(db=db, branch=default_branch)
    division = [{"path": "site", "value": site.id}]

    async def execute(query: str, variables: dict[str, Any]) -> Any:
        result = await graphql(
            schema=params.schema,
            source=query,
            context_value=params.context,
            root_value=None,
            variable_values={"pool_id": pool_id, **variables},
        )
        assert result.errors is None
        return result.data

    utilization = (await execute(UTILIZATION_QUERY, {"division": division}))["InfrahubNumberPoolUtilization"]
    assert (utilization["figures"]["size"], utilization["figures"]["used"]) == (35, 2)
    assert [(item["figures"]["size"], item["figures"]["used"]) for item in utilization["ranges"]] == [(35, 2), (0, 0)]

    divisions = (await execute(DIVISIONS_QUERY, {}))["InfrahubNumberPoolDivisions"]["divisions"]
    assert [(item["figures"]["size"], item["figures"]["used"]) for item in divisions] == [(35, 2)]

    allocations = (await execute(ALLOCATIONS_QUERY, {"division": division}))["InfrahubNumberPoolAllocations"]
    assert (allocations["count"], [row["value"] for row in allocations["allocations"]]) == (2, [3, 30])
