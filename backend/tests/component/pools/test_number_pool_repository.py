from infrahub.core.branch import Branch
from infrahub.core.initialization import initialize_registry
from infrahub.core.node.resource_manager.number_pool import CoreNumberPool
from infrahub.core.query.resource_manager import NumberPoolGetTaken, NumberPoolGetUsed
from infrahub.core.schema import SchemaRoot
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase
from infrahub.pools.number_pool_repository import NumberPoolRepository
from infrahub.pools.number_ranges import EffectiveSpace, NumberDomain
from tests.helpers.db_query_counter import CountingInfrahubDatabase
from tests.helpers.number_pool import add_pool_range
from tests.helpers.schema import TICKET, load_schema


async def test_get_ranges(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    """The pool's ranges come back lowest start first, whatever order they were created in."""
    await load_schema(db=db, schema=SchemaRoot(nodes=[TICKET]))
    await initialize_registry(db=db)

    pool = await CoreNumberPool.init(db=db, schema="CoreNumberPool")
    await pool.new(db=db, name="pool1", node="TestingTicket", node_attribute="ticket_id", start_range=1, end_range=10)
    await pool.save(db=db)

    assert await NumberPoolRepository(db=db).get_ranges(pool_id=pool.get_id()) == []

    second = await add_pool_range(db=db, pool=pool, start=300, end=400)
    first = await add_pool_range(db=db, pool=pool, start=100, end=200)

    ranges = await NumberPoolRepository(db=db).get_ranges(pool_id=pool.get_id())
    assert [(item.start.value, item.end.value) for item in ranges] == [(100, 200), (300, 400)]
    assert [item.get_id() for item in ranges] == [first.get_id(), second.get_id()]


async def test_an_empty_space_reads_no_used_or_taken_number_without_querying(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    """A space holding no segment answers the used and taken reads without running their queries."""
    await load_schema(db=db, schema=SchemaRoot(nodes=[TICKET]))
    await initialize_registry(db=db)
    pool = await CoreNumberPool.init(db=db, schema="CoreNumberPool")
    await pool.new(db=db, name="empty-pool", node="TestingTicket", node_attribute="ticket_id")
    await pool.save(db=db)
    counting_db = CountingInfrahubDatabase.from_db(db=db)
    repository = NumberPoolRepository(db=counting_db)
    space = EffectiveSpace(ranges=[], domain=NumberDomain())

    assert await repository.get_used(pool=pool, branch=default_branch, space=space) == []
    assert await repository.get_taken(pool=pool, branch=default_branch, space=space) == set()
    assert counting_db.count_for(NumberPoolGetUsed.name) == 0
    assert counting_db.count_for(NumberPoolGetTaken.name) == 0
