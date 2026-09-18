"""Check a NumberPool is reported as an attribute's source even though it does not use HAS_SOURCE

A number pool is not stored in `HAS_SOURCE`. It is derived from the branch-agnostic reservation
record instead, so an attribute with no source of its own still names the pool, and one the user gave
a source keeps showing that source while the pool goes on tracking the number.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from infrahub.core import registry
from infrahub.core.constants import InfrahubKind, MetadataOptions
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.node.resource_manager.number_pool import CoreNumberPool
from infrahub.core.query.node import NodeListGetAttributeQuery
from infrahub.core.schema import SchemaRoot
from tests.helpers.schema import TICKET, load_schema

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase

POOL_START = 1
POOL_END = 10
TRACKED_ATTRIBUTE_NAME = "ticket_id"


@pytest.fixture
async def ticket_pool(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> CoreNumberPool:
    await load_schema(db=db, schema=SchemaRoot(nodes=[TICKET]))
    registry.node[InfrahubKind.NUMBERPOOL] = CoreNumberPool
    pool = await CoreNumberPool.init(db=db, schema=InfrahubKind.NUMBERPOOL)
    await pool.new(
        db=db,
        name="ticket-pool",
        node=TICKET.kind,
        node_attribute=TRACKED_ATTRIBUTE_NAME,
        start_range=POOL_START,
        end_range=POOL_END,
    )
    await pool.save(db=db)
    return pool


async def stored_source_edge_count(db: InfrahubDatabase, node_id: str) -> int:
    """How many source edges the object's tracked attribute actually carries in the graph."""
    results = await db.execute_query(
        query="""
        MATCH (:Node {uuid: $node_id})-[:HAS_ATTRIBUTE]->(a:Attribute {name: $attribute_name})
        WITH DISTINCT a
        MATCH (a)-[e:HAS_SOURCE]-()
        WHERE e.status = "active" AND e.to IS NULL
        RETURN count(e) AS stored
        """,
        params={"node_id": node_id, "attribute_name": TRACKED_ATTRIBUTE_NAME},
    )
    return int(results[0]["stored"])


async def read_source_labels(db: InfrahubDatabase, branch: Branch, node_id: str) -> list[str]:
    """The labels the attribute read returns for the source, which select its GraphQL type."""
    query = await NodeListGetAttributeQuery.init(
        db=db,
        branch=branch,
        ids=[node_id],
        fields={TRACKED_ATTRIBUTE_NAME: True},
        include_metadata=MetadataOptions.SOURCE,
    )
    await query.execute(db=db)
    attribute, _ = query.get_result_by_id_and_name(node_id=node_id, attr_name=TRACKED_ATTRIBUTE_NAME)
    source = attribute.node_properties.get("source")
    return sorted(source.labels) if source else []


async def test_a_pooled_attribute_with_no_user_source_reports_the_pool(
    db: InfrahubDatabase, default_branch: Branch, ticket_pool: CoreNumberPool
) -> None:
    ticket = await Node.init(db=db, schema=TICKET.kind, branch=default_branch)
    await ticket.new(db=db, title="pooled", ticket_id={"from_pool": {"id": ticket_pool.id}})
    await ticket.save(db=db)

    assert ticket.get_attribute("ticket_id").value == POOL_START
    assert await stored_source_edge_count(db=db, node_id=ticket.id) == 0, (
        "the pool must not be written to the attribute's source storage"
    )

    reloaded = await NodeManager.get_one(
        db=db, id=ticket.id, branch=default_branch, include_metadata=MetadataOptions.SOURCE, raise_on_error=True
    )
    source = await reloaded.get_attribute("ticket_id").get_source(db=db)
    assert source is not None, "an attribute a pool accounts for reports the pool as its source"
    assert source.get_id() == ticket_pool.id
    assert source.get_kind() == InfrahubKind.NUMBERPOOL, (
        "the resolved source must carry the pool's own kind, not a bare id"
    )
    assert InfrahubKind.NUMBERPOOL in await read_source_labels(db=db, branch=default_branch, node_id=ticket.id), (
        "the read returns the pool vertex, so its labels can select the concrete GraphQL type"
    )


async def test_a_user_source_on_a_pooled_attribute_wins_and_changes_nothing_the_pool_reports(
    db: InfrahubDatabase, default_branch: Branch, ticket_pool: CoreNumberPool, first_account: Node
) -> None:
    ticket = await Node.init(db=db, schema=TICKET.kind, branch=default_branch)
    await ticket.new(db=db, title="pooled", ticket_id={"from_pool": {"id": ticket_pool.id}})
    await ticket.save(db=db)

    used_before = await ticket_pool.get_used(db=db, branch=default_branch)
    free_before = await ticket_pool.get_free(db=db, branch=default_branch)
    assert used_before == [POOL_START]

    reloaded = await NodeManager.get_one(
        db=db, id=ticket.id, branch=default_branch, include_metadata=MetadataOptions.SOURCE, raise_on_error=True
    )
    reloaded.get_attribute("ticket_id").source = first_account.id
    await reloaded.save(db=db)

    reread = await NodeManager.get_one(
        db=db, id=ticket.id, branch=default_branch, include_metadata=MetadataOptions.SOURCE, raise_on_error=True
    )
    source = await reread.get_attribute("ticket_id").get_source(db=db)
    assert source is not None
    assert source.get_id() == first_account.id, "a source the user set is what the attribute reports"
    assert source.get_kind() != InfrahubKind.NUMBERPOOL

    assert await ticket_pool.get_used(db=db, branch=default_branch) == used_before, (
        "setting a source says nothing about which numbers are taken"
    )
    assert await ticket_pool.get_free(db=db, branch=default_branch) == free_before
    assert reread.get_attribute("ticket_id").value == POOL_START
