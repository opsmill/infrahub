import pytest

from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind
from infrahub.core.initialization import initialize_registry
from infrahub.core.migrations.graph.m080_number_pool_ranges import Migration080
from infrahub.core.migrations.shared import MigrationInput
from infrahub.core.registry import registry
from infrahub.core.schema import SchemaRoot, core_models
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from tests.helpers.schema import TICKET


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


async def test_range_kind_and_relationship_land_in_the_database_schema(
    db: InfrahubDatabase,
    reset_registry: None,
    default_branch: Branch,
    pre_migration_schema_db: SchemaBranch,
) -> None:
    assert not pre_migration_schema_db.has(name=InfrahubKind.NUMBERPOOLRANGE)

    migration = Migration080.init()
    execution_result = await migration.execute(migration_input=MigrationInput(db=db))
    assert not execution_result.errors, execution_result.errors

    reloaded = await registry.schema.load_schema_from_db(db=db, branch=default_branch)

    range_schema = reloaded.get_node(name=InfrahubKind.NUMBERPOOLRANGE, duplicate=False)
    assert {attribute.name for attribute in range_schema.attributes} >= {"start", "end", "allocation_weight"}
    assert range_schema.get_relationship(name="pool").peer == InfrahubKind.NUMBERPOOL

    pool_schema = reloaded.get_node(name=InfrahubKind.NUMBERPOOL, duplicate=False)
    ranges = pool_schema.get_relationship(name="ranges")
    assert ranges.peer == InfrahubKind.NUMBERPOOLRANGE
    assert ranges.identifier == "numberpool__range"

    validation_result = await migration.validate_migration(db=db)
    assert not validation_result.errors, validation_result.errors


async def test_bootstrap_leaves_the_rest_of_the_pool_schema_to_the_core_schema_update(
    db: InfrahubDatabase,
    reset_registry: None,
    default_branch: Branch,
    pre_migration_schema_db: SchemaBranch,
) -> None:
    """Only the range kind and the ranges relationship reach the stored schema, whose hash the branch then carries."""
    execution_result = await Migration080.init().execute(migration_input=MigrationInput(db=db))
    assert not execution_result.errors, execution_result.errors

    reloaded = await registry.schema.load_schema_from_db(db=db, branch=default_branch)
    pool_schema = reloaded.get_node(name=InfrahubKind.NUMBERPOOL, duplicate=False)
    for bound in ("start_range", "end_range"):
        attribute = pool_schema.get_attribute(name=bound)
        assert attribute.optional is False
        assert attribute.deprecation is None

    stored_branch = await Branch.get_by_name(db=db, name=default_branch.name)
    assert (
        stored_branch.active_schema_hash.main
        == registry.schema.get_schema_branch(name=default_branch.name).get_hash_full().main
    )
