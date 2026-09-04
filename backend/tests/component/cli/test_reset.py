from pathlib import Path

from prefect.server.models.flows import count_flows, create_flow
from prefect.server.schemas.core import Flow

from infrahub.cli.db_commands.reset import (
    reset_graph_database,
    reset_task_manager_database,
    task_manager_database,
)
from infrahub.core.branch import Branch
from infrahub.core.graph.index import node_indexes, rel_indexes
from infrahub.core.utils import count_nodes
from infrahub.database import InfrahubDatabase
from infrahub.database.neo4j import IndexManagerNeo4j

DUMMY_VERTEX_COUNT = 250


async def _create_dummy_graph(db: InfrahubDatabase) -> None:
    """Add a few hundred connected vertices so a small batch size has to span several transactions."""
    query = """
    UNWIND range(1, $count) AS idx
    CREATE (a:DummyReset {idx: idx})-[:DUMMY_EDGE]->(:DummyResetPeer {idx: idx})
    """
    await db.execute_query(query=query, params={"count": DUMMY_VERTEX_COUNT}, name="create_dummy_graph")


def _sqlite_url(path: Path) -> str:
    return f"sqlite+aiosqlite:///{path}"


class TestResetGraphDatabase:
    async def test_deletes_every_vertex_across_batches(self, db: InfrahubDatabase, default_branch: Branch) -> None:
        await _create_dummy_graph(db=db)
        assert await count_nodes(db=db) > 2 * DUMMY_VERTEX_COUNT

        await reset_graph_database(db=db, batch_size=100)

        assert await count_nodes(db=db) == 0

    async def test_keeps_indexes(self, db: InfrahubDatabase, default_branch: Branch) -> None:
        manager = IndexManagerNeo4j(db=db)
        manager.init(nodes=node_indexes, rels=rel_indexes)
        indexes_before = {index.name for index in await manager.list()}
        assert indexes_before

        await reset_graph_database(db=db)

        assert {index.name for index in await manager.list()} == indexes_before


class TestResetTaskManagerDatabase:
    async def test_recreates_an_empty_schema(self, tmp_path: Path) -> None:
        with task_manager_database(connection_url=_sqlite_url(tmp_path / "task-manager.db")) as task_db:
            await task_db.create_db()
            async with await task_db.session() as session, session.begin():
                await create_flow(session=session, flow=Flow(name="dummy"))
            async with await task_db.session() as session:
                assert await count_flows(session=session) == 1

            await reset_task_manager_database(task_db=task_db)

            async with await task_db.session() as session:
                assert await count_flows(session=session) == 0

    async def test_resets_a_database_without_tables(self, tmp_path: Path) -> None:
        with task_manager_database(connection_url=_sqlite_url(tmp_path / "task-manager.db")) as task_db:
            await reset_task_manager_database(task_db=task_db)

            async with await task_db.session() as session:
                assert await count_flows(session=session) == 0

    async def test_targets_only_the_given_database(self, tmp_path: Path) -> None:
        """Prefect caches its first database configuration per process; the URL passed in must still win."""
        kept_path = tmp_path / "kept.db"
        reset_path = tmp_path / "reset.db"

        with task_manager_database(connection_url=_sqlite_url(kept_path)) as kept_db:
            await kept_db.create_db()
            async with await kept_db.session() as session, session.begin():
                await create_flow(session=session, flow=Flow(name="kept"))

        with task_manager_database(connection_url=_sqlite_url(reset_path)) as reset_db:
            await reset_task_manager_database(task_db=reset_db)
            async with await reset_db.session() as session:
                assert await count_flows(session=session) == 0
        assert reset_path.exists()

        with task_manager_database(connection_url=_sqlite_url(kept_path)) as kept_db:
            async with await kept_db.session() as session:
                assert await count_flows(session=session) == 1
