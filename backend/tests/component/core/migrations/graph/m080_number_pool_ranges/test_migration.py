import pytest

from infrahub.cli.db import migrate_database
from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind, NumberPoolType
from infrahub.core.initialization import initialize_registry
from infrahub.core.manager import NodeManager
from infrahub.core.migrations.graph.m080_number_pool_ranges import Migration080
from infrahub.core.node.resource_manager.number_pool import CoreNumberPool
from infrahub.core.registry import registry
from infrahub.core.schema import SchemaRoot, core_models
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from infrahub.database.validation import verify_graph
from infrahub.pools.number_pool_repository import NumberPoolRepository
from tests.helpers.schema import TICKET

USER_POOL_BOUNDS = (1, 10)
SCHEMA_POOL_BOUNDS = (100, 200)


def _downgrade_schema(schema_branch: SchemaBranch) -> None:
    """Mutate the in-memory schema back to the pre-migration shape, before processing.

    This is what gets persisted, so the rest of the test starts from a database whose schema knows
    nothing about ranges and whose pool bounds are still mandatory.
    """
    schema_branch.delete(name=InfrahubKind.NUMBERPOOLRANGE)

    pool = schema_branch.get_node(name=InfrahubKind.NUMBERPOOL, duplicate=False)
    pool.relationships = [relationship for relationship in pool.relationships if relationship.name != "ranges"]
    for bound in ("start_range", "end_range"):
        attribute = pool.get_attribute(name=bound)
        attribute.optional = False
        attribute.deprecation = None


@pytest.fixture
async def pre_migration_pools(
    db: InfrahubDatabase,
    reset_registry: None,
    default_branch: Branch,
    register_internal_models_schema: SchemaBranch,
) -> tuple[CoreNumberPool, CoreNumberPool]:
    """Persist a core schema that predates the range kind, then a user pool and a schema pool under it."""
    schema_branch = registry.schema.get_schema_branch(name=default_branch.name)
    schema_branch.load_schema(schema=SchemaRoot(**core_models))
    _downgrade_schema(schema_branch)
    schema_branch.load_schema(schema=SchemaRoot(nodes=[TICKET]))
    schema_branch.process()
    default_branch.update_schema_hash()

    await registry.schema.load_schema_to_db(schema=schema_branch, branch=default_branch, db=db, at=Timestamp())
    stored_schema = await registry.schema.load_schema_from_db(db=db, branch=default_branch)
    registry.schema.set_schema_branch(name=default_branch.name, schema=stored_schema)
    await initialize_registry(db=db)
    assert not stored_schema.has(name=InfrahubKind.NUMBERPOOLRANGE)

    pools = []
    for name, (start, end), pool_type in (
        ("user-pool", USER_POOL_BOUNDS, NumberPoolType.USER),
        ("schema-pool", SCHEMA_POOL_BOUNDS, NumberPoolType.SCHEMA),
    ):
        pool = await CoreNumberPool.init(db=db, schema=InfrahubKind.NUMBERPOOL)
        await pool.new(
            db=db,
            name=name,
            node=TICKET.kind,
            node_attribute="ticket_id",
            pool_type=pool_type.value,
            start_range=start,
            end_range=end,
        )
        await pool.save(db=db)
        pools.append(pool)

    # The upgrade runners start the graph migrations with no schema loaded.
    registry.delete_all()
    return pools[0], pools[1]


async def _migrate(db: InfrahubDatabase) -> None:
    assert await migrate_database(db=db, migrations=[Migration080.init()], initialize=True, update_graph_version=False)


async def _range_ids(db: InfrahubDatabase, pool: CoreNumberPool) -> set[str]:
    return {item.get_id() for item in await NumberPoolRepository(db=db).get_ranges(pool_id=pool.get_id())}


async def test_migration_080(
    db: InfrahubDatabase,
    default_branch: Branch,
    pre_migration_pools: tuple[CoreNumberPool, CoreNumberPool],
) -> None:
    await _migrate(db=db)

    stored_schema = await registry.schema.load_schema_from_db(db=db, branch=default_branch)
    range_schema = stored_schema.get_node(name=InfrahubKind.NUMBERPOOLRANGE, duplicate=False)
    assert range_schema.get_relationship(name="pool").peer == InfrahubKind.NUMBERPOOL
    ranges_relationship = stored_schema.get_node(name=InfrahubKind.NUMBERPOOL, duplicate=False).get_relationship(
        name="ranges"
    )
    assert ranges_relationship.peer == InfrahubKind.NUMBERPOOLRANGE
    assert ranges_relationship.identifier == "numberpool__range"

    stored_branch = await Branch.get_by_name(db=db, name=default_branch.name)
    assert (
        stored_branch.active_schema_hash.main
        == registry.schema.get_schema_branch(name=default_branch.name).get_hash_full().main
    )

    for pool, bounds in zip(pre_migration_pools, (USER_POOL_BOUNDS, SCHEMA_POOL_BOUNDS), strict=True):
        migrated = await NodeManager.get_one_by_id_or_default_filter(db=db, id=pool.get_id(), kind=CoreNumberPool)
        ranges = await NumberPoolRepository(db=db).get_ranges(pool_id=migrated.get_id())
        assert [(item.start.value, item.end.value, item.allocation_weight.value) for item in ranges] == [
            (*bounds, None)
        ]
        assert (migrated.get_attribute("start_range").value, migrated.get_attribute("end_range").value) == bounds

    await verify_graph(db=db)


async def test_migration_080_is_idempotent(
    db: InfrahubDatabase,
    pre_migration_pools: tuple[CoreNumberPool, CoreNumberPool],
) -> None:
    await _migrate(db=db)
    range_ids = [await _range_ids(db=db, pool=pool) for pool in pre_migration_pools]

    await _migrate(db=db)

    assert [await _range_ids(db=db, pool=pool) for pool in pre_migration_pools] == range_ids
    range_schema_nodes = await NodeManager.query(
        db=db, schema="SchemaNode", filters={"namespace__value": "Core", "name__value": "NumberPoolRange"}
    )
    assert len(range_schema_nodes) == 1

    await verify_graph(db=db)
