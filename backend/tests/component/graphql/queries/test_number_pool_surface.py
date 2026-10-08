from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from infrahub.core.initialization import create_branch
from infrahub.graphql.initialization import GraphqlParams, prepare_graphql_params
from infrahub.pools.number_pool_mock import OTHER_BRANCH, SCOPED_POOL, SITE_ELEMENT, UNSCOPED_POOL, UNSCOPED_POOL_ID
from tests.helpers.graphql import graphql

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase

SCOPED_POOL_ID = "2a91c0de-0000-4000-8000-000000000001"
SITE_A, SITE_B, SITE_C, SITE_D = (entries[0].value for entries in SCOPED_POOL.divisions)
FIRST_RANGE = SCOPED_POOL.ranges[0].id
SITE_SCOPE = [{"id": SITE_ELEMENT.id, "name": "site"}]

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
  $provenance: NumberPoolProvenance
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


class TestNumberPoolSurface:
    @pytest.fixture(scope="class")
    async def gql_params(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        register_core_models_schema_scope_class: SchemaBranch,
    ) -> GraphqlParams:
        return await prepare_graphql_params(db=db, branch=default_branch_scope_class)

    @pytest.fixture(scope="class")
    async def branch_gql_params(self, db: InfrahubDatabase, gql_params: GraphqlParams) -> GraphqlParams:
        branch = await create_branch(db=db, branch_name=OTHER_BRANCH)
        return await prepare_graphql_params(db=db, branch=branch)

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

    async def test_scoped_divisions_list_only_the_divisions_holding_a_value(self, gql_params: GraphqlParams) -> None:
        data = await self._data(gql_params, DIVISIONS_QUERY, pool_id=SCOPED_POOL_ID)

        divisions = data["InfrahubNumberPoolDivisions"]
        assert divisions["count"] == 2
        assert divisions["allocation_scope"] == SITE_SCOPE
        assert [
            (item["display_label"], item["figures"]["size"], item["figures"]["used"]) for item in divisions["divisions"]
        ] == [("Site A", 100, 40), ("Site B", 100, 30)]
        assert {SITE_C, SITE_D}.isdisjoint({item["entries"][0]["value"] for item in divisions["divisions"]})
        assert divisions["divisions"][0]["entries"] == [
            {
                "id": SITE_ELEMENT.id,
                "path": "site",
                "value": SITE_A,
                "display_label": "Site A",
                "peer_kind": "LocationSite",
            }
        ]

    async def test_divisions_read_each_holder_on_the_request_branch(self, branch_gql_params: GraphqlParams) -> None:
        data = await self._data(branch_gql_params, DIVISIONS_QUERY, pool_id=SCOPED_POOL_ID)

        divisions = data["InfrahubNumberPoolDivisions"]
        assert divisions["count"] == 3
        assert [
            (
                item["display_label"],
                item["figures"]["used"],
                item["figures"]["used_default_branch"],
                item["figures"]["used_branches"],
            )
            for item in divisions["divisions"]
        ] == [("Site A", 39, 39, 0), ("Site B", 30, 27, 3), ("Site C", 1, 1, 0)]

    async def test_utilization_of_one_division(self, gql_params: GraphqlParams) -> None:
        division = [{"path": "site", "value": SITE_B}]
        data = await self._data(gql_params, UTILIZATION_QUERY, pool_id=SCOPED_POOL_ID, division=division)

        utilization = data["InfrahubNumberPoolUtilization"]
        assert utilization["id"] == SCOPED_POOL_ID
        assert utilization["display_label"] == "Device index"
        assert utilization["allocation_scope"] == SITE_SCOPE
        assert utilization["figures"] == {
            "size": 100,
            "used": 30,
            "used_default_branch": 27,
            "used_branches": 3,
            "utilization": 30.0,
            "utilization_default_branch": 27.0,
            "utilization_branches": 3.0,
        }
        assert [
            (item["display_label"], item["figures"]["size"], item["figures"]["used"]) for item in utilization["ranges"]
        ] == [("1 - 50", 50, 0), ("51 - 100", 50, 30)]

    async def test_allocations_count_one_row_per_branch_where_figures_count_each_value_once(
        self, gql_params: GraphqlParams
    ) -> None:
        divisions = await self._data(gql_params, DIVISIONS_QUERY, pool_id=SCOPED_POOL_ID)
        used = {
            item["display_label"]: item["figures"]["used"]
            for item in divisions["InfrahubNumberPoolDivisions"]["divisions"]
        }

        counts = {}
        for label, site in (("Site A", SITE_A), ("Site B", SITE_B)):
            data = await self._data(
                gql_params, ALLOCATIONS_QUERY, pool_id=SCOPED_POOL_ID, division=[{"path": "site", "value": site}]
            )
            counts[label] = data["InfrahubNumberPoolAllocations"]["count"]

        assert (counts["Site A"], used["Site A"]) == (41, 40)
        assert (counts["Site B"], used["Site B"]) == (30, 30)

    async def test_allocations_keep_the_rows_of_a_holder_moved_on_a_branch(self, gql_params: GraphqlParams) -> None:
        data = await self._data(
            gql_params, ALLOCATIONS_QUERY, pool_id=SCOPED_POOL_ID, division=[{"path": "site", "value": SITE_A}], limit=2
        )

        allocations = data["InfrahubNumberPoolAllocations"]
        assert allocations["count"] == 41
        first, second = allocations["allocations"]
        assert (first["value"], first["branch"], first["holder"]["display_label"]) == (1, "main", "D0")
        assert first["holder"]["kind"] == "InfraDevice"
        assert first["range"]["display_label"] == "1 - 50"
        assert (second["value"], second["branch"], second["holder"]["display_label"]) == (5, "branch1", "D1")

    async def test_allocations_follow_a_holder_moved_on_the_request_branch(
        self, branch_gql_params: GraphqlParams
    ) -> None:
        site_c = await self._data(
            branch_gql_params, ALLOCATIONS_QUERY, pool_id=SCOPED_POOL_ID, division=[{"path": "site", "value": SITE_C}]
        )
        site_a = await self._data(
            branch_gql_params, ALLOCATIONS_QUERY, pool_id=SCOPED_POOL_ID, division=[{"path": "site", "value": SITE_A}]
        )

        rows = site_c["InfrahubNumberPoolAllocations"]["allocations"]
        assert [(row["value"], row["branch"], row["holder"]["display_label"]) for row in rows] == [
            (5, "branch1", "D1"),
            (5, "main", "D1"),
        ]
        assert site_a["InfrahubNumberPoolAllocations"]["count"] == 39

    async def test_allocations_filter_on_provenance(self, gql_params: GraphqlParams) -> None:
        data = await self._data(gql_params, ALLOCATIONS_QUERY, pool_id=SCOPED_POOL_ID, provenance="PROVIDED")

        allocations = data["InfrahubNumberPoolAllocations"]["allocations"]
        assert [(row["value"], row["provenance"], row["range"]["display_label"]) for row in allocations] == [
            (51, "PROVIDED", "51 - 100"),
        ]

    async def test_unscoped_dataset(self, gql_params: GraphqlParams) -> None:
        utilization = await self._data(gql_params, UTILIZATION_QUERY, pool_id=UNSCOPED_POOL_ID)
        divisions = await self._data(gql_params, DIVISIONS_QUERY, pool_id=UNSCOPED_POOL_ID)
        allocations = await self._data(
            gql_params, ALLOCATIONS_QUERY, pool_id=UNSCOPED_POOL_ID, range_id=UNSCOPED_POOL.ranges[0].id
        )

        pool = utilization["InfrahubNumberPoolUtilization"]
        assert pool["allocation_scope"] == []
        assert (pool["figures"]["size"], pool["figures"]["used"]) == (99, 3)
        assert divisions["InfrahubNumberPoolDivisions"] == {
            "count": 0,
            "allocation_scope": [],
            "divisions": [],
        }
        assert allocations["InfrahubNumberPoolAllocations"]["count"] == 2
        rows = allocations["InfrahubNumberPoolAllocations"]["allocations"]
        assert [(row["value"], row["branch"], row["provenance"], row["range"]["display_label"]) for row in rows] == [
            (1, "main", "ALLOCATED", "1 - 50"),
            (7, "branch1", "ALLOCATED", "1 - 50"),
        ]

    @pytest.mark.parametrize(
        ("query", "variables", "message"),
        [
            pytest.param(
                UTILIZATION_QUERY,
                {"pool_id": SCOPED_POOL_ID},
                f"The pool {SCOPED_POOL_ID} has an allocation scope; give a division with a value for every "
                "element to read its utilization",
                id="utilization-scoped-pool-without-division",
            ),
            pytest.param(
                UTILIZATION_QUERY,
                {"pool_id": UNSCOPED_POOL_ID, "division": [{"path": "site", "value": SITE_A}]},
                "The pool mock-unscoped has no allocation scope; the division filter cannot be applied",
                id="utilization-division-on-unscoped-pool",
            ),
            pytest.param(
                ALLOCATIONS_QUERY,
                {"pool_id": UNSCOPED_POOL_ID, "range_id": FIRST_RANGE},
                f"The range {FIRST_RANGE} does not belong to the pool {UNSCOPED_POOL_ID}",
                id="allocations-unknown-range",
            ),
            pytest.param(
                ALLOCATIONS_QUERY,
                {"pool_id": UNSCOPED_POOL_ID, "division": [{"path": "site", "value": SITE_A}]},
                "The pool mock-unscoped has no allocation scope; the division filter cannot be applied",
                id="division-on-unscoped-pool",
            ),
            pytest.param(
                ALLOCATIONS_QUERY,
                {"pool_id": SCOPED_POOL_ID, "division": [{"path": "role", "value": "leaf"}]},
                'The division entry "role" is not an element of the pool\'s allocation scope',
                id="path-not-in-scope",
            ),
            pytest.param(
                ALLOCATIONS_QUERY,
                {
                    "pool_id": SCOPED_POOL_ID,
                    "division": [{"path": "site", "value": SITE_A}, {"path": "site", "value": SITE_B}],
                },
                'The division entry "site" is not an element of the pool\'s allocation scope',
                id="duplicate-path",
            ),
            pytest.param(
                ALLOCATIONS_QUERY,
                {"pool_id": SCOPED_POOL_ID, "offset": -1},
                "offset must be 0 or greater",
                id="negative-offset",
            ),
            pytest.param(
                ALLOCATIONS_QUERY,
                {"pool_id": SCOPED_POOL_ID, "limit": -1},
                "limit must be 0 or greater",
                id="negative-limit",
            ),
        ],
    )
    async def test_refusals(
        self, gql_params: GraphqlParams, query: str, variables: dict[str, Any], message: str
    ) -> None:
        assert await self._error(gql_params, query, **variables) == message
