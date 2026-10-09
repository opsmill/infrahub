"""An attribute's source and the pool tracking it are reported apart from each other.

The pool is read from the live reservation record into the attribute's tracking pool, never into its
source. The source only ever reports a `HAS_SOURCE` edge the user stored, so an attribute with no source of
its own reports none while the pool goes on tracking its number, and a save naming a pool stores no source.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import pytest

from infrahub.core import registry
from infrahub.core.constants import InfrahubKind, MetadataOptions, PoolRecordProvenance
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.node.resource_manager.number_pool import CoreNumberPool
from infrahub.core.query.resource_manager import TrackingPoolRecord
from infrahub.core.schema import SchemaRoot
from infrahub.pools.attribute_pool_applier_factory import build_attribute_pool_applier
from tests.helpers.number_pool import add_pool_range, pool_lowest_free_number, pool_used_numbers
from tests.helpers.schema import TICKET, load_schema

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase

POOL_START = 1
POOL_END = 10
SECOND_POOL_START = 11
SECOND_POOL_END = 20
TRACKED_ATTRIBUTE_NAME = "ticket_id"


async def create_ticket_pool(db: InfrahubDatabase, name: str, start: int, end: int) -> CoreNumberPool:
    pool = await CoreNumberPool.init(db=db, schema=InfrahubKind.NUMBERPOOL)
    await pool.new(
        db=db,
        name=name,
        node=TICKET.kind,
        node_attribute=TRACKED_ATTRIBUTE_NAME,
        start_range=start,
        end_range=end,
    )
    await pool.save(db=db)
    await add_pool_range(db=db, pool=pool, start=start, end=end)
    return pool


@pytest.fixture
async def ticket_pool(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> CoreNumberPool:
    await load_schema(db=db, schema=SchemaRoot(nodes=[TICKET]))
    registry.node[InfrahubKind.NUMBERPOOL] = CoreNumberPool
    return await create_ticket_pool(db=db, name="ticket-pool", start=POOL_START, end=POOL_END)


@pytest.fixture
async def second_ticket_pool(db: InfrahubDatabase, ticket_pool: CoreNumberPool) -> CoreNumberPool:
    return await create_ticket_pool(db=db, name="ticket-pool-2", start=SECOND_POOL_START, end=SECOND_POOL_END)


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


async def reload_ticket(db: InfrahubDatabase, branch: Branch, node_id: str, include_metadata: MetadataOptions) -> Node:
    return await NodeManager.get_one(
        db=db, id=node_id, branch=branch, include_metadata=include_metadata, raise_on_error=True
    )


async def test_a_pooled_attribute_with_no_user_source_reports_no_source_and_the_pool(
    db: InfrahubDatabase, default_branch: Branch, ticket_pool: CoreNumberPool
) -> None:
    ticket = await Node.init(db=db, schema=TICKET.kind, branch=default_branch)
    await ticket.new(db=db, title="pooled", ticket_id={"from_pool": {"id": ticket_pool.id}})
    await ticket.save(db=db)

    assert ticket.get_attribute(TRACKED_ATTRIBUTE_NAME).value == POOL_START
    assert await stored_source_edge_count(db=db, node_id=ticket.id) == 0, (
        "the pool must not be written to the attribute's source storage"
    )
    expected_record = TrackingPoolRecord(pool_id=ticket_pool.id, provenance=PoolRecordProvenance.ALLOCATED)

    read_with_record = await reload_ticket(
        db=db,
        branch=default_branch,
        node_id=ticket.id,
        include_metadata=MetadataOptions.SOURCE | MetadataOptions.TRACKING_POOL,
    )
    attribute = read_with_record.get_attribute(TRACKED_ATTRIBUTE_NAME)
    assert await attribute.get_source(db=db) is None, "a pool is never reported as the attribute's source"
    assert await attribute.get_tracking_pool(db=db) == expected_record

    read_without_record = await reload_ticket(
        db=db, branch=default_branch, node_id=ticket.id, include_metadata=MetadataOptions.NONE
    )
    assert (
        await read_without_record.get_attribute(TRACKED_ATTRIBUTE_NAME).get_tracking_pool(db=db) == expected_record
    ), "an attribute loaded without the record reads it on demand"


async def test_a_user_source_on_a_pooled_attribute_is_reported_beside_the_pool(
    db: InfrahubDatabase, default_branch: Branch, ticket_pool: CoreNumberPool, first_account: Node
) -> None:
    ticket = await Node.init(db=db, schema=TICKET.kind, branch=default_branch)
    await ticket.new(db=db, title="pooled", ticket_id={"from_pool": {"id": ticket_pool.id}})
    await ticket.save(db=db)

    used_before = await pool_used_numbers(db=db, pool=ticket_pool, branch=default_branch)
    free_before = await pool_lowest_free_number(db=db, pool=ticket_pool, branch=default_branch)
    assert used_before == [POOL_START]

    reloaded = await reload_ticket(
        db=db, branch=default_branch, node_id=ticket.id, include_metadata=MetadataOptions.SOURCE
    )
    reloaded.get_attribute(TRACKED_ATTRIBUTE_NAME).source = first_account.id
    await reloaded.save(db=db)

    reread = await reload_ticket(
        db=db,
        branch=default_branch,
        node_id=ticket.id,
        include_metadata=MetadataOptions.SOURCE | MetadataOptions.TRACKING_POOL,
    )
    attribute = reread.get_attribute(TRACKED_ATTRIBUTE_NAME)
    source = await attribute.get_source(db=db)
    assert source is not None
    assert source.get_id() == first_account.id, "a source the user set is what the attribute reports"
    assert await attribute.get_tracking_pool(db=db) == TrackingPoolRecord(
        pool_id=ticket_pool.id, provenance=PoolRecordProvenance.ALLOCATED
    )
    assert await stored_source_edge_count(db=db, node_id=ticket.id) == 1

    assert await pool_used_numbers(db=db, pool=ticket_pool, branch=default_branch) == used_before, (
        "setting a source says nothing about which numbers are taken"
    )
    assert await pool_lowest_free_number(db=db, pool=ticket_pool, branch=default_branch) == free_before
    assert attribute.value == POOL_START


@dataclass(frozen=True)
class PoolSaveCase:
    name: str
    data: dict[str, Any]
    """The payload for the tracked attribute; a pool is named as `"first"` or `"second"`."""
    expected_pool: str | None
    expected_provenance: PoolRecordProvenance | None
    expected_value: int


POOL_SAVE_CASES: list[PoolSaveCase] = [
    PoolSaveCase(
        name="re_pool_keeping_the_number",
        data={"from_pool": {"id": "second"}, "value": POOL_START},
        expected_pool="second",
        expected_provenance=PoolRecordProvenance.PROVIDED,
        expected_value=POOL_START,
    ),
    PoolSaveCase(
        name="re_pool_drawing_a_new_number",
        data={"from_pool": {"id": "second"}, "value": None},
        expected_pool="second",
        expected_provenance=PoolRecordProvenance.ALLOCATED,
        expected_value=SECOND_POOL_START,
    ),
    PoolSaveCase(
        name="detach",
        data={"from_pool": None},
        expected_pool=None,
        expected_provenance=None,
        expected_value=POOL_START,
    ),
    PoolSaveCase(
        name="restate_the_same_pool_with_the_number",
        data={"from_pool": {"id": "first"}, "value": POOL_START},
        expected_pool="first",
        expected_provenance=PoolRecordProvenance.ALLOCATED,
        expected_value=POOL_START,
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(case, id=case.name) for case in POOL_SAVE_CASES])
async def test_a_save_naming_a_pool_stores_no_source_and_updates_the_tracking_pool(
    db: InfrahubDatabase,
    default_branch: Branch,
    ticket_pool: CoreNumberPool,
    second_ticket_pool: CoreNumberPool,
    test_case: PoolSaveCase,
) -> None:
    pools = {"first": ticket_pool, "second": second_ticket_pool}
    ticket = await Node.init(db=db, schema=TICKET.kind, branch=default_branch)
    await ticket.new(db=db, title="pooled", ticket_id={"from_pool": {"id": ticket_pool.id}})
    await ticket.save(db=db)
    assert ticket.get_attribute(TRACKED_ATTRIBUTE_NAME).value == POOL_START

    data = dict(test_case.data)
    if data.get("from_pool"):
        data["from_pool"] = {"id": pools[data["from_pool"]["id"]].id}

    loaded = await reload_ticket(
        db=db, branch=default_branch, node_id=ticket.id, include_metadata=MetadataOptions.SOURCE
    )
    await loaded.get_attribute(TRACKED_ATTRIBUTE_NAME).from_graphql(
        data=data, pool_applier=build_attribute_pool_applier(db=db)
    )
    await loaded.save(db=db)

    assert await stored_source_edge_count(db=db, node_id=ticket.id) == 0, (
        "a save naming a pool must not write the pool to the attribute's source storage"
    )
    reloaded = await reload_ticket(
        db=db,
        branch=default_branch,
        node_id=ticket.id,
        include_metadata=MetadataOptions.SOURCE | MetadataOptions.TRACKING_POOL,
    )
    attribute = reloaded.get_attribute(TRACKED_ATTRIBUTE_NAME)
    assert attribute.value == test_case.expected_value
    assert await attribute.get_source(db=db) is None
    expected_record = (
        TrackingPoolRecord(pool_id=pools[test_case.expected_pool].id, provenance=test_case.expected_provenance)
        if test_case.expected_pool is not None and test_case.expected_provenance is not None
        else None
    )
    assert await attribute.get_tracking_pool(db=db) == expected_record
