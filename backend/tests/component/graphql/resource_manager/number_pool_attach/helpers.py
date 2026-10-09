from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from infrahub.auth.session import AccountSession
from infrahub.auth.types import AuthType
from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind
from infrahub.core.manager import NodeManager
from infrahub.core.node.resource_manager.number_pool import CoreNumberPool
from infrahub.core.query.resource_manager import NumberPoolGetAllocated, NumberPoolGetTrackingPool
from infrahub.core.schema.attribute_schema import AttributeSchema
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from infrahub.graphql.initialization import prepare_graphql_params
from infrahub.pools.number_pool_repository import NumberPoolRepository
from infrahub.pools.number_ranges import EffectiveSpace, NumberDomain
from tests.helpers.agnostic_edges import EdgeState, attribute_edges
from tests.helpers.graphql import graphql
from tests.helpers.number_pool import add_pool_range, pool_used_numbers
from tests.helpers.schema import TICKET

CREATE_TICKET = """
mutation CreateTicket($title: String!, $ticket_id: NumberAttributeCreate, $sequence: NumberAttributeCreate) {
    TestingTicketCreate(data: { title: { value: $title }, ticket_id: $ticket_id, sequence: $sequence }) {
        ok
        object { id ticket_id { value } sequence { value } }
    }
}
"""

UPDATE_TICKET = """
mutation UpdateTicket($id: String!, $ticket_id: NumberAttributeUpdate, $sequence: NumberAttributeUpdate) {
    TestingTicketUpdate(data: { id: $id, ticket_id: $ticket_id, sequence: $sequence }) {
        ok
        object { ticket_id { value } sequence { value } }
    }
}
"""

TICKET_SOURCES = """
query TicketSources($id: ID!) {
    TestingTicket(ids: [$id]) {
        edges {
            node {
                ticket_id { value source { id } from_pool { pool { id } provenance } }
                sequence { value source { id } from_pool { pool { id } provenance } }
            }
        }
    }
}
"""

DELETE_POOL = """
mutation DeletePool($id: String!) {
    CoreNumberPoolDelete(data: { id: $id }) { ok }
}
"""

OPEN_IS_RESERVED_EDGES_OF_POOL = """
MATCH (:Node { uuid: $pool_id })-[reserved:IS_RESERVED]->(:Attribute)<-[:HAS_ATTRIBUTE]-(node:Node)
WHERE reserved.status = "active" AND reserved.to IS NULL
RETURN DISTINCT node.uuid AS node_id, elementId(reserved) AS edge_id, reserved.allocated_values AS allocated_values
"""

LIVE_IS_RESERVED_EDGES_BY_ATTRIBUTE = """
MATCH (:Node { uuid: $node_id })-[:HAS_ATTRIBUTE]->(attr:Attribute)<-[reserved:IS_RESERVED]-(pool:Node)
WHERE reserved.status = "active" AND reserved.to IS NULL
RETURN attr.name AS attribute_name, pool.uuid AS pool_id, reserved.allocated_values AS allocated_values
"""

SECOND_ACTOR_ID = "5b7d2e0c-4f3a-4c1e-9a6b-2d8f1c0e7a41"
THIRD_ACTOR_ID = "9e1f6a3b-7c2d-4e8f-b5a0-6d4c3b2a1f09"


def session_for(account_id: str) -> AccountSession:
    return AccountSession(authenticated=True, account_id=account_id, auth_type=AuthType.JWT)


# `sequence` is a second pooled number with no uniqueness constraint, so one schema serves every test.
TICKET_WITH_SEQUENCE = deepcopy(TICKET)
TICKET_WITH_SEQUENCE.attributes.append(AttributeSchema(name="sequence", kind="Number", optional=True))


async def execute(
    db: InfrahubDatabase,
    branch: Branch,
    source: str,
    variables: dict[str, Any],
    account_session: AccountSession | None = None,
    at: Timestamp | None = None,
) -> dict[str, Any] | None:
    gql_params = await prepare_graphql_params(db=db, branch=branch, at=at, account_session=account_session)
    result = await graphql(
        schema=gql_params.schema,
        source=source,
        context_value=gql_params.context,
        root_value=None,
        variable_values=variables,
    )
    assert not result.errors, result.errors
    return result.data


async def create_ticket(
    db: InfrahubDatabase,
    branch: Branch,
    title: str,
    account_session: AccountSession | None = None,
    **fields: dict[str, Any],
) -> dict[str, Any]:
    data = await execute(
        db=db,
        branch=branch,
        source=CREATE_TICKET,
        variables={"title": title, **fields},
        account_session=account_session,
    )
    assert data
    return data["TestingTicketCreate"]["object"]


async def update_ticket(
    db: InfrahubDatabase,
    branch: Branch,
    node_id: str,
    account_session: AccountSession | None = None,
    **fields: dict[str, Any],
) -> dict[str, Any]:
    data = await execute(
        db=db, branch=branch, source=UPDATE_TICKET, variables={"id": node_id, **fields}, account_session=account_session
    )
    assert data
    return data["TestingTicketUpdate"]["object"]


async def new_pool(
    db: InfrahubDatabase, name: str, start_range: int, end_range: int, node_attribute: str = "ticket_id"
) -> CoreNumberPool:
    pool = await CoreNumberPool.init(db=db, schema=InfrahubKind.NUMBERPOOL)
    await pool.new(
        db=db,
        name=name,
        node=TICKET.kind,
        node_attribute=node_attribute,
        start_range=start_range,
        end_range=end_range,
    )
    await pool.save(db=db)
    await add_pool_range(db=db, pool=pool, start=start_range, end=end_range)
    return pool


async def open_is_reserved_edges(db: InfrahubDatabase, pool: CoreNumberPool) -> set[tuple[str, tuple[int, ...]]]:
    """The holder and allocated values of each open IS_RESERVED edge the pool has, on any attribute."""
    results = await db.execute_query(query=OPEN_IS_RESERVED_EDGES_OF_POOL, params={"pool_id": pool.get_id()})
    edge_ids = [result.get("edge_id") for result in results]
    assert len(edge_ids) == len(set(edge_ids))
    return {(result.get("node_id"), tuple(result.get("allocated_values"))) for result in results}


async def allocated_rows(db: InfrahubDatabase, branch: Branch, pool: CoreNumberPool) -> list[tuple[str, str, int, str]]:
    """The holder, branch, value and provenance of every row the pool's in-use list reports."""
    space = EffectiveSpace(
        ranges=await NumberPoolRepository(db=db).get_pool_ranges(pool_id=pool.get_id()), domain=NumberDomain()
    )
    query = await NumberPoolGetAllocated.init(
        db=db, pool=pool, ranges=space.as_query_ranges(), branch=branch, branch_agnostic=True
    )
    await query.execute(db=db)
    return sorted((row.id, row.branch, row.value, row.provenance.value) for row in query.get_data())


async def used_numbers(db: InfrahubDatabase, branch: Branch, pool: CoreNumberPool) -> list[int]:
    return await pool_used_numbers(db=db, pool=pool, branch=branch)


async def is_reserved_edges(db: InfrahubDatabase, node_id: str, attribute_name: str = "ticket_id") -> list[EdgeState]:
    edges = await attribute_edges(db=db, node_id=node_id, attribute_name=attribute_name)
    return sorted((edge for edge in edges if edge.edge_type == "IS_RESERVED"), key=lambda edge: edge.edge_id or "")


@dataclass(frozen=True)
class AttributeRead:
    """What a GraphQL read of one pooled number reports: its value, its source and the pool tracking it."""

    value: int | None
    source_id: str | None
    pool_id: str | None
    pool_provenance: str | None


def attribute_read(field: dict[str, Any]) -> AttributeRead:
    from_pool = field["from_pool"] or {}
    return AttributeRead(
        value=field["value"],
        source_id=(field["source"] or {}).get("id"),
        pool_id=(from_pool.get("pool") or {}).get("id"),
        pool_provenance=from_pool.get("provenance"),
    )


async def pooled_numbers(
    db: InfrahubDatabase, branch: Branch, node_id: str, at: Timestamp | None = None
) -> dict[str, AttributeRead]:
    """What a read of each pooled number on the ticket reports, keyed by attribute name."""
    data = await execute(db=db, branch=branch, source=TICKET_SOURCES, variables={"id": node_id}, at=at)
    assert data
    [edge] = data["TestingTicket"]["edges"]
    return {name: attribute_read(edge["node"][name]) for name in ("ticket_id", "sequence")}


async def tracking_pool_id(db: InfrahubDatabase, node_id: str, attribute_name: str = "ticket_id") -> str | None:
    ticket = await NodeManager.get_one(db=db, id=node_id)
    assert ticket is not None
    attribute_id = ticket.get_attribute(name=attribute_name).id
    assert attribute_id is not None
    query = await NumberPoolGetTrackingPool.init(db=db, attribute_id=attribute_id)
    await query.execute(db=db)
    return query.get_pool_id()
