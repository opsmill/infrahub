from infrahub.core.branch import Branch
from infrahub.core.initialization import first_time_initialization
from infrahub.core.migrations.graph.m086_create_no_owner_vertex import Migration086
from infrahub.core.migrations.shared import MigrationInput
from infrahub.core.ownership.constants import NO_OWNER_VERTEX_UUID
from infrahub.database import InfrahubDatabase


async def _no_owner_uuids(db: InfrahubDatabase) -> list[str]:
    return [record["uuid"] for record in await db.execute_query(query="MATCH (n:NoOwner) RETURN n.uuid AS uuid")]


async def test_new_database_has_one_no_owner_vertex(db: InfrahubDatabase, default_branch: Branch) -> None:
    assert await _no_owner_uuids(db=db) == [NO_OWNER_VERTEX_UUID]


async def test_upgrade_creates_one_no_owner_vertex(db: InfrahubDatabase, default_branch: Branch) -> None:
    # A database of the release before has no such vertex.
    await db.execute_query(query="MATCH (n:NoOwner) DELETE n")
    assert await _no_owner_uuids(db=db) == []

    result = await Migration086().execute(migration_input=MigrationInput(db=db))
    second_result = await Migration086().execute(migration_input=MigrationInput(db=db))

    assert result.errors == []
    assert second_result.errors == []
    assert await _no_owner_uuids(db=db) == [NO_OWNER_VERTEX_UUID]


async def test_first_start_creates_one_no_owner_vertex(db: InfrahubDatabase, default_branch: Branch) -> None:
    await db.execute_query(query="MATCH (n:NoOwner) DELETE n")

    await first_time_initialization(db=db)

    assert await _no_owner_uuids(db=db) == [NO_OWNER_VERTEX_UUID]
