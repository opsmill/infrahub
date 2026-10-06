import pytest

from infrahub.core.branch import Branch
from infrahub.core.initialization import initialize_registry
from infrahub.core.node.resource_manager.number_pool import CoreNumberPool
from infrahub.core.registry import registry
from infrahub.core.schema import SchemaRoot
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase
from infrahub.exceptions import PoolExhaustedError
from tests.helpers.number_pool import add_pool_range, shorthand_mirror
from tests.helpers.schema import TICKET, load_schema


@pytest.mark.xfail(
    strict=True, reason="allocation still reads the shorthand bounds; walking the range set lands with IFC-3065 phase 3"
)
async def test_allocation_from_a_pool_holding_several_ranges_starts_at_the_lowest_range(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    """A pool whose shorthand is null because it holds several ranges allocates from those ranges."""
    await load_schema(db=db, schema=SchemaRoot(nodes=[TICKET]))
    await initialize_registry(db=db)

    pool = await CoreNumberPool.init(db=db, schema="CoreNumberPool")
    await pool.new(db=db, name="pool1", node="TestingTicket", node_attribute="ticket_id", start_range=1, end_range=10)
    await pool.save(db=db)
    await add_pool_range(db=db, pool=pool, start=100, end=200)
    await add_pool_range(db=db, pool=pool, start=300, end=400)
    await shorthand_mirror(db=db).sync(pool=pool)
    assert (pool.start_range.value, pool.end_range.value) == (None, None)

    attribute = registry.schema.get_node_schema(name=TICKET.kind).get_attribute(name="ticket_id")
    assert await pool.get_next(db=db, branch=default_branch, attribute=attribute) == 100


async def test_allocation_from_a_pool_without_range_names_the_single_range_it_needs(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    await load_schema(db=db, schema=SchemaRoot(nodes=[TICKET]))
    await initialize_registry(db=db)

    pool = await CoreNumberPool.init(db=db, schema="CoreNumberPool")
    await pool.new(db=db, name="empty-pool", node="TestingTicket", node_attribute="ticket_id")
    await pool.save(db=db)

    attribute = registry.schema.get_node_schema(name=TICKET.kind).get_attribute(name="ticket_id")
    with pytest.raises(PoolExhaustedError) as exc_info:
        await pool.get_next(db=db, branch=default_branch, attribute=attribute)

    assert exc_info.value.message == (
        "There are no values available in this pool: allocation draws from a pool holding exactly one range."
    )
