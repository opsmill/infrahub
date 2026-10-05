from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

import pytest

from infrahub.core import registry
from infrahub.core.constants import InfrahubKind
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.node.resource_manager.number_pool import CoreNumberPool
from infrahub.core.schema import SchemaRoot
from infrahub.graphql.initialization import prepare_graphql_params
from tests.helpers.graphql import graphql
from tests.helpers.schema import TICKET, load_schema

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase


UPDATE_TICKET_WITH_POOL = """
mutation UpdateTicketWithPool($ticket_id: String!, $pool_id: String!) {
    TestingTicketUpdate(data: {
        id: $ticket_id
        ticket_id: {
            from_pool: {
                id: $pool_id
            }
        }
    }) {
        ok
    }
}
"""

LIVE_IS_RESERVED_EDGES = """
MATCH (:Node { uuid: $node_id })-[:HAS_ATTRIBUTE]->(attr:Attribute { name: "ticket_id" })
MATCH (pool:%(number_pool)s)-[reserved:IS_RESERVED]->(attr)
WHERE reserved.status = "active" AND reserved.to IS NULL
RETURN pool.uuid AS pool_id
""" % {"number_pool": InfrahubKind.NUMBERPOOL}


class TestConcurrentRePool:
    @pytest.fixture
    async def pools(
        self, db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
    ) -> list[CoreNumberPool]:
        # Without a uniqueness constraint over the number, the writes share no lock on the attribute's value.
        ticket = TICKET.model_copy(deep=True)
        ticket.human_friendly_id = None
        ticket.get_attribute(name="ticket_id").unique = False
        await load_schema(db=db, schema=SchemaRoot(nodes=[ticket]))
        registry.node[InfrahubKind.NUMBERPOOL] = CoreNumberPool

        pools = []
        for name, start_range in (("pool-a", 1), ("pool-b", 100), ("pool-c", 200)):
            pool = await CoreNumberPool.init(db=db, schema=InfrahubKind.NUMBERPOOL)
            await pool.new(
                db=db,
                name=name,
                node="TestingTicket",
                node_attribute="ticket_id",
                start_range=start_range,
                end_range=start_range + 98,
            )
            await pool.save(db=db)
            pools.append(pool)
        default_branch.update_schema_hash()
        return pools

    @pytest.fixture
    async def ticket_from_pool_a(
        self, db: InfrahubDatabase, default_branch: Branch, pools: list[CoreNumberPool]
    ) -> Node:
        ticket = await Node.init(db=db, schema="TestingTicket", branch=default_branch)
        await ticket.new(db=db, title="re-pooled", ticket_id={"from_pool": {"id": pools[0].id}})
        await ticket.save(db=db)
        return ticket

    async def _live_reserving_pool_ids(self, db: InfrahubDatabase, node_id: str) -> list[str]:
        results = await db.execute_query(query=LIVE_IS_RESERVED_EDGES, params={"node_id": node_id})
        return [result.get("pool_id") for result in results]

    async def _re_pool(
        self, db: InfrahubDatabase, branch: Branch, ticket_id: str, pool_id: str
    ) -> dict[str, Any] | None:
        # A session holds a single connection, which cannot serve two racing coroutines.
        async with db.start_session() as session_db:
            gql_params = await prepare_graphql_params(db=session_db, branch=branch)
            result = await graphql(
                schema=gql_params.schema,
                source=UPDATE_TICKET_WITH_POOL,
                context_value=gql_params.context,
                root_value=None,
                variable_values={"ticket_id": ticket_id, "pool_id": pool_id},
            )
        assert not result.errors
        return result.data

    async def test_concurrent_re_pool_into_two_pools_leaves_one_live_is_reserved_edge(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        pools: list[CoreNumberPool],
        ticket_from_pool_a: Node,
    ) -> None:
        _, pool_b, pool_c = pools

        results = await asyncio.gather(
            self._re_pool(db=db, branch=default_branch, ticket_id=ticket_from_pool_a.id, pool_id=pool_b.id),
            self._re_pool(db=db, branch=default_branch, ticket_id=ticket_from_pool_a.id, pool_id=pool_c.id),
        )

        assert all(result and result["TestingTicketUpdate"]["ok"] for result in results)
        live_pool_ids = await self._live_reserving_pool_ids(db=db, node_id=ticket_from_pool_a.id)
        assert len(live_pool_ids) == 1
        numbers_by_pool_id = {pool_b.id: range(100, 199), pool_c.id: range(200, 299)}
        ticket = await NodeManager.get_one(db=db, id=ticket_from_pool_a.id, branch=default_branch)
        assert ticket is not None
        assert ticket.get_attribute(name="ticket_id").value in numbers_by_pool_id[live_pool_ids[0]]
