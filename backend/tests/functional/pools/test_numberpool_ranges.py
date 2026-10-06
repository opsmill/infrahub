from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import pytest

from infrahub.core.schema import SchemaRoot
from tests.helpers.schema import TICKET
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from pathlib import Path

    from infrahub_sdk import InfrahubClient

    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase

CREATE_POOL = """
mutation CreatePool($name: String!) {
    CoreNumberPoolCreate(data: {
        name: { value: $name }
        node: { value: "TestingTicket" }
        node_attribute: { value: "ticket_id" }
    }) {
        object { id }
    }
}
"""

CREATE_RANGE = """
mutation CreateRange($pool_id: String!, $start: BigInt!, $end: BigInt!, $weight: BigInt) {
    CoreNumberPoolRangeCreate(data: {
        start: { value: $start }
        end: { value: $end }
        allocation_weight: { value: $weight }
        pool: { id: $pool_id }
    }) {
        object { id }
    }
}
"""

DELETE_RANGE = """
mutation DeleteRange($range_id: String!) {
    CoreNumberPoolRangeDelete(data: { id: $range_id }) {
        ok
    }
}
"""

POOL_UTILIZATION = """
query PoolUtilization($pool_id: String!) {
    InfrahubResourcePoolUtilization(pool_id: $pool_id) {
        count
        utilization
        edges {
            node {
                display_label
                weight
                utilization
            }
        }
    }
}
"""


@dataclass(frozen=True)
class RangedPool:
    """A user pool holding a heavier 100-102 range and a 205-207 range."""

    pool_id: str
    heavy_range_id: str
    light_range_id: str


def _percent(used: int, size: int) -> float:
    return used / size * 100


class TestNumberPoolRanges(TestInfrahubApp):
    """Allocation over a two-range user pool, through the API and the SDK, over the class in order."""

    @pytest.fixture(scope="class")
    async def ranged_pool(
        self,
        db: InfrahubDatabase,
        initialize_registry: None,
        git_repos_source_dir_module_scope: Path,
        client: InfrahubClient,
        prefect_test_fixture: None,
        default_branch: Branch,
    ) -> RangedPool:
        schema_load_response = await client.schema.load(
            schemas=[SchemaRoot(version="1.0", nodes=[TICKET]).model_dump()], wait_until_converged=True
        )
        assert not schema_load_response.errors

        created = await client.execute_graphql(query=CREATE_POOL, variables={"name": "ticket-numbers"})
        pool_id = created["CoreNumberPoolCreate"]["object"]["id"]
        return RangedPool(
            pool_id=pool_id,
            heavy_range_id=await self._create_range(client=client, pool_id=pool_id, start=100, end=102, weight=10),
            light_range_id=await self._create_range(client=client, pool_id=pool_id, start=205, end=207),
        )

    @staticmethod
    async def _create_range(
        client: InfrahubClient, pool_id: str, start: int, end: int, weight: int | None = None
    ) -> str:
        created = await client.execute_graphql(
            query=CREATE_RANGE, variables={"pool_id": pool_id, "start": start, "end": end, "weight": weight}
        )
        return created["CoreNumberPoolRangeCreate"]["object"]["id"]

    @staticmethod
    async def _allocate(client: InfrahubClient, pool_id: str, title: str) -> int:
        ticket = await client.create(kind=TICKET.kind, title=title, ticket_id={"from_pool": {"id": pool_id}})
        await ticket.save()
        return ticket.ticket_id.value

    @staticmethod
    async def _utilization(client: InfrahubClient, pool_id: str) -> dict[str, Any]:
        result = await client.execute_graphql(query=POOL_UTILIZATION, variables={"pool_id": pool_id})
        return result["InfrahubResourcePoolUtilization"]

    async def test_allocation_drains_the_heavier_range_then_falls_through(
        self, client: InfrahubClient, ranged_pool: RangedPool
    ) -> None:
        allocated = [
            await self._allocate(client=client, pool_id=ranged_pool.pool_id, title=f"ticket-{index}")
            for index in range(4)
        ]

        assert allocated == [100, 101, 102, 205]
        assert await self._utilization(client=client, pool_id=ranged_pool.pool_id) == {
            "count": 2,
            "utilization": _percent(4, 6),
            "edges": [
                {"node": {"display_label": "100 - 102", "weight": 10, "utilization": 100.0}},
                {"node": {"display_label": "205 - 207", "weight": 0, "utilization": _percent(1, 3)}},
            ],
        }

    async def test_a_removed_range_keeps_its_number_recorded_until_it_is_re_added(
        self, client: InfrahubClient, ranged_pool: RangedPool
    ) -> None:
        deleted = await client.execute_graphql(query=DELETE_RANGE, variables={"range_id": ranged_pool.light_range_id})
        assert deleted["CoreNumberPoolRangeDelete"]["ok"]
        assert await self._utilization(client=client, pool_id=ranged_pool.pool_id) == {
            "count": 1,
            "utilization": 100.0,
            "edges": [{"node": {"display_label": "100 - 102", "weight": 10, "utilization": 100.0}}],
        }

        await self._create_range(client=client, pool_id=ranged_pool.pool_id, start=205, end=207)
        assert await self._utilization(client=client, pool_id=ranged_pool.pool_id) == {
            "count": 2,
            "utilization": _percent(4, 6),
            "edges": [
                {"node": {"display_label": "100 - 102", "weight": 10, "utilization": 100.0}},
                {"node": {"display_label": "205 - 207", "weight": 0, "utilization": _percent(1, 3)}},
            ],
        }
        assert await self._allocate(client=client, pool_id=ranged_pool.pool_id, title="after-re-add") == 206, (
            "205 stayed recorded while its range was gone"
        )
