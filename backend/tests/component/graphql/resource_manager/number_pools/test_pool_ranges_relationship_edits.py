from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind
from infrahub.core.manager import NodeManager
from infrahub.core.node.resource_manager.number_pool import CoreNumberPool
from infrahub.core.schema import SchemaRoot
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase
from tests.helpers.number_pool import add_pool_range
from tests.helpers.schema import TICKET, load_schema

from .helpers import execute, range_bounds, shorthand

RELATIONSHIP_ADD = """
mutation AddRanges($pool_id: String!, $range_id: String!) {
    RelationshipAdd(data: { id: $pool_id, name: "ranges", nodes: [{ id: $range_id }] }) {
        ok
    }
}
"""

RELATIONSHIP_REMOVE = """
mutation RemoveRanges($pool_id: String!, $range_id: String!) {
    RelationshipRemove(data: { id: $pool_id, name: "ranges", nodes: [{ id: $range_id }] }) {
        ok
    }
}
"""


async def _create_pool(db: InfrahubDatabase, name: str) -> CoreNumberPool:
    pool = await CoreNumberPool.init(db=db, schema=InfrahubKind.NUMBERPOOL)
    await pool.new(db=db, name=name, node="TestingTicket", node_attribute="ticket_id")
    await pool.save(db=db)
    return pool


async def _range_pool_id(db: InfrahubDatabase, range_id: str) -> str | None:
    pool_range = await NodeManager.get_one(db=db, id=range_id, kind=InfrahubKind.NUMBERPOOLRANGE, raise_on_error=True)
    return await pool_range.get_relationship("pool").get_peer_id(db=db)


async def test_removing_a_range_through_relationship_remove_is_refused(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    await load_schema(db=db, schema=SchemaRoot(nodes=[TICKET]))
    pool = await _create_pool(db=db, name="relationship-remove-pool")
    await add_pool_range(db=db, pool=pool, start=10, end=20)
    high = await add_pool_range(db=db, pool=pool, start=30, end=40)
    shorthand_before = await shorthand(db=db, pool_id=pool.get_id())

    result = await execute(
        db=db,
        branch=default_branch,
        source=RELATIONSHIP_REMOVE,
        variables={"pool_id": pool.get_id(), "range_id": high.get_id()},
    )

    assert result.errors
    assert str(result.errors[0].message) == (
        f"'{high.get_id()}' 'CoreNumberPoolRange' can't be removed from 'ranges':"
        " its mandatory relationship 'pool' would be left empty"
    )
    assert await range_bounds(db=db, pool_id=pool.get_id()) == [(10, 20), (30, 40)]
    assert await _range_pool_id(db=db, range_id=high.get_id()) == pool.get_id()
    assert await shorthand(db=db, pool_id=pool.get_id()) == shorthand_before


async def test_adding_a_range_through_relationship_add_is_refused(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    await load_schema(db=db, schema=SchemaRoot(nodes=[TICKET]))
    owner = await _create_pool(db=db, name="relationship-add-owner")
    held_range = await add_pool_range(db=db, pool=owner, start=10, end=20)
    other = await _create_pool(db=db, name="relationship-add-other")

    result = await execute(
        db=db,
        branch=default_branch,
        source=RELATIONSHIP_ADD,
        variables={"pool_id": other.get_id(), "range_id": held_range.get_id()},
    )

    assert result.errors
    assert str(result.errors[0].message) == (
        f"'{held_range.get_id()}' 'CoreNumberPoolRange' is already related to another peer on 'pool'"
    )
    assert await range_bounds(db=db, pool_id=owner.get_id()) == [(10, 20)]
    assert await range_bounds(db=db, pool_id=other.get_id()) == []
