import pytest

from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind, NumberPoolType
from infrahub.core.initialization import initialize_registry
from infrahub.core.manager import NodeManager
from infrahub.core.migrations.graph.m079_number_pool_ranges import Migration079
from infrahub.core.migrations.shared import MigrationInput
from infrahub.core.node import Node
from infrahub.core.node.resource_manager.number_pool import CoreNumberPool
from infrahub.core.registry import registry
from infrahub.core.schema import SchemaRoot, core_models
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from infrahub.database.validation import verify_graph
from infrahub.graphql.queries.resource_manager import resolve_number_pool_utilization
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
async def pre_migration_schema_db(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_internal_models_schema: SchemaBranch,
) -> SchemaBranch:
    """Persist a core schema that predates the range kind, plus the kind the pools allocate for."""
    schema_branch = registry.schema.get_schema_branch(name=default_branch.name)
    schema_branch.load_schema(schema=SchemaRoot(**core_models))
    _downgrade_schema(schema_branch)
    schema_branch.load_schema(schema=SchemaRoot(nodes=[TICKET]))
    schema_branch.process()
    default_branch.update_schema_hash()

    await registry.schema.load_schema_to_db(schema=schema_branch, branch=default_branch, db=db, at=Timestamp())
    updated_schema = await registry.schema.load_schema_from_db(db=db, branch=default_branch)
    registry.schema.set_schema_branch(name=default_branch.name, schema=updated_schema)
    await initialize_registry(db=db)
    return updated_schema


async def _create_pool(
    db: InfrahubDatabase, name: str, bounds: tuple[int, int], pool_type: NumberPoolType
) -> CoreNumberPool:
    pool = await CoreNumberPool.init(db=db, schema=InfrahubKind.NUMBERPOOL)
    await pool.new(
        db=db,
        name=name,
        node=TICKET.kind,
        node_attribute="ticket_id",
        start_range=bounds[0],
        end_range=bounds[1],
        pool_type=pool_type.value,
    )
    await pool.save(db=db)
    return pool


async def _allocate(db: InfrahubDatabase, pool: CoreNumberPool, count: int, title: str) -> None:
    for index in range(count):
        ticket = await Node.init(db=db, schema=TICKET.kind)
        await ticket.new(db=db, title=f"{title}-{index}", ticket_id={"from_pool": {"id": pool.get_id()}})
        await ticket.save(db=db)


async def _reload(db: InfrahubDatabase, pool: CoreNumberPool) -> CoreNumberPool:
    return await NodeManager.get_one_by_id_or_default_filter(db=db, id=pool.get_id(), kind=CoreNumberPool)


@pytest.fixture
async def migrated_pools(
    db: InfrahubDatabase,
    reset_registry: None,
    default_branch: Branch,
    pre_migration_schema_db: SchemaBranch,
) -> tuple[CoreNumberPool, CoreNumberPool, list[int], list[int]]:
    """Run the migration once over a user pool and a schema pool that both hold allocations."""
    user_pool = await _create_pool(db=db, name="user-pool", bounds=USER_POOL_BOUNDS, pool_type=NumberPoolType.USER)
    schema_pool = await _create_pool(
        db=db, name="schema-pool", bounds=SCHEMA_POOL_BOUNDS, pool_type=NumberPoolType.SCHEMA
    )

    await _allocate(db=db, pool=user_pool, count=3, title="user")
    await _allocate(db=db, pool=schema_pool, count=2, title="schema")

    used_before = {
        user_pool.get_id(): await user_pool.get_used(db=db, branch=default_branch),
        schema_pool.get_id(): await schema_pool.get_used(db=db, branch=default_branch),
    }
    assert used_before[user_pool.get_id()] == [1, 2, 3]
    assert used_before[schema_pool.get_id()] == [100, 101]

    assert not pre_migration_schema_db.has(name=InfrahubKind.NUMBERPOOLRANGE)

    migration = Migration079.init()
    execution_result = await migration.execute(migration_input=MigrationInput(db=db))
    assert not execution_result.errors, execution_result.errors
    assert execution_result.nbr_migrations_executed == 2

    return (
        await _reload(db=db, pool=user_pool),
        await _reload(db=db, pool=schema_pool),
        used_before[user_pool.get_id()],
        used_before[schema_pool.get_id()],
    )


async def test_every_pool_gets_one_range_carrying_the_old_bounds(
    db: InfrahubDatabase,
    migrated_pools: tuple[CoreNumberPool, CoreNumberPool, list[int], list[int]],
) -> None:
    user_pool, schema_pool, _, _ = migrated_pools

    for pool, bounds in ((user_pool, USER_POOL_BOUNDS), (schema_pool, SCHEMA_POOL_BOUNDS)):
        ranges = await pool.load_ranges(db=db)
        assert len(ranges) == 1
        assert (ranges[0].start.value, ranges[0].end.value) == bounds
        assert ranges[0].allocation_weight.value is None
        assert (pool.start_range.value, pool.end_range.value) == bounds


async def test_allocations_and_utilization_survive_the_migration(
    migrated_pools: tuple[CoreNumberPool, CoreNumberPool, list[int], list[int]],
    db: InfrahubDatabase,
    default_branch: Branch,
) -> None:
    user_pool, schema_pool, user_used, schema_used = migrated_pools

    assert await user_pool.get_used(db=db, branch=default_branch) == user_used
    assert await schema_pool.get_used(db=db, branch=default_branch) == schema_used

    utilization = await resolve_number_pool_utilization(db=db, pool=user_pool, at=Timestamp(), branch=default_branch)
    pool_size = USER_POOL_BOUNDS[1] - USER_POOL_BOUNDS[0] + 1
    assert utilization["utilization"] == len(user_used) / pool_size * 100
    assert utilization["count"] == 1
    assert utilization["edges"][0]["node"]["display_label"] == f"{USER_POOL_BOUNDS[0]} - {USER_POOL_BOUNDS[1]}"
    assert utilization["edges"][0]["node"]["weight"] == 0


async def test_second_run_creates_no_range(
    db: InfrahubDatabase,
    migrated_pools: tuple[CoreNumberPool, CoreNumberPool, list[int], list[int]],
) -> None:
    user_pool, schema_pool, _, _ = migrated_pools
    range_ids = {
        pool.get_id(): {item.get_id() for item in await pool.load_ranges(db=db)} for pool in (user_pool, schema_pool)
    }

    migration = Migration079.init()
    second_result = await migration.execute(migration_input=MigrationInput(db=db))
    assert not second_result.errors, second_result.errors
    assert second_result.nbr_migrations_executed == 0

    for pool in (user_pool, schema_pool):
        assert {item.get_id() for item in await pool.load_ranges(db=db)} == range_ids[pool.get_id()]


async def test_validate_migration_reports_a_clean_graph(
    db: InfrahubDatabase,
    migrated_pools: tuple[CoreNumberPool, CoreNumberPool, list[int], list[int]],
) -> None:
    validation_result = await Migration079.init().validate_migration(db=db)
    assert not validation_result.errors, validation_result.errors

    await verify_graph(db=db)


async def test_range_kind_and_relationship_land_in_the_database_schema(
    migrated_pools: tuple[CoreNumberPool, CoreNumberPool, list[int], list[int]],
    db: InfrahubDatabase,
    default_branch: Branch,
) -> None:
    reloaded = await registry.schema.load_schema_from_db(db=db, branch=default_branch)

    range_schema = reloaded.get_node(name=InfrahubKind.NUMBERPOOLRANGE, duplicate=False)
    assert {attribute.name for attribute in range_schema.attributes} >= {"start", "end", "allocation_weight"}
    assert range_schema.get_relationship(name="pool").peer == InfrahubKind.NUMBERPOOL

    pool_schema = reloaded.get_node(name=InfrahubKind.NUMBERPOOL, duplicate=False)
    ranges = pool_schema.get_relationship(name="ranges")
    assert ranges.peer == InfrahubKind.NUMBERPOOLRANGE
    assert ranges.identifier == "numberpool__range"


async def test_pool_without_bounds_is_left_without_a_range(
    db: InfrahubDatabase,
    reset_registry: None,
    default_branch: Branch,
    pre_migration_schema_db: SchemaBranch,
) -> None:
    """A pool that declares no bounds produces no range and does not fail validation."""
    pool = await _create_pool(db=db, name="user-pool", bounds=USER_POOL_BOUNDS, pool_type=NumberPoolType.USER)

    migration = Migration079.init()
    first_result = await migration.execute(migration_input=MigrationInput(db=db))
    assert not first_result.errors, first_result.errors

    migrated = await _reload(db=db, pool=pool)
    for pool_range in await migrated.load_ranges(db=db):
        await pool_range.delete(db=db)
    await migrated.sync_shorthand_from_ranges(db=db)
    assert migrated.start_range.value is None

    second_result = await migration.execute(migration_input=MigrationInput(db=db))
    assert not second_result.errors, second_result.errors
    assert second_result.nbr_migrations_executed == 0

    validation_result = await migration.validate_migration(db=db)
    assert not validation_result.errors, validation_result.errors
