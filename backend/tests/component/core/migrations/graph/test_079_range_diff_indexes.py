from infrahub.constants.database import IndexType
from infrahub.core.migrations.graph.m079_range_diff_indexes import (
    RANGE_INDEXES_TO_ADD,
    TEXT_INDEXES_TO_DROP,
    Migration079,
)
from infrahub.core.migrations.shared import MigrationInput
from infrahub.database import InfrahubDatabase
from infrahub.database.neo4j import IndexManagerNeo4j


async def _existing_indexes(db: InfrahubDatabase) -> set[tuple[str, tuple[str, ...], IndexType]]:
    index_manager = IndexManagerNeo4j(db=db)
    return {(info.label, tuple(info.properties), info.type) for info in await index_manager.list()}


async def test_migration_079(db: InfrahubDatabase) -> None:
    """The TEXT diff indexes are replaced by RANGE ones, and the new root indexes appear."""
    # Reproduce the pre-migration state: the TEXT indexes exist and the RANGE ones do not.
    index_manager = IndexManagerNeo4j(db=db)
    index_manager.init(nodes=RANGE_INDEXES_TO_ADD, rels=[])
    await index_manager.drop()
    index_manager.init(nodes=TEXT_INDEXES_TO_DROP, rels=[])
    await index_manager.add()

    migration = Migration079()

    # A clean validation after the run only means something if it was dirty before.
    before = await migration.validate_migration(db=db)
    assert before.errors == [
        "text index on DiffNode(uuid) still exists",
        "text index on DiffRoot(uuid) still exists",
        "range index on DiffNode(uuid) is missing",
        "range index on DiffRoot(diff_branch) is missing",
        "range index on DiffRoot(tracking_id) is missing",
        "range index on DiffRoot(uuid) is missing",
    ]

    execution_result = await migration.execute(migration_input=MigrationInput(db=db))
    assert not execution_result.errors

    validation_result = await migration.validate_migration(db=db)
    assert not validation_result.errors

    existing = await _existing_indexes(db=db)
    assert {("DiffRoot", ("uuid",), IndexType.TEXT), ("DiffNode", ("uuid",), IndexType.TEXT)}.isdisjoint(existing)
    assert {
        ("DiffRoot", ("uuid",), IndexType.RANGE),
        ("DiffNode", ("uuid",), IndexType.RANGE),
        ("DiffRoot", ("diff_branch",), IndexType.RANGE),
        ("DiffRoot", ("tracking_id",), IndexType.RANGE),
    } <= existing

    # Running it again is a no-op.
    second_run = await migration.execute(migration_input=MigrationInput(db=db))
    assert not second_run.errors
