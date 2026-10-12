from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

from infrahub.constants.database import DatabaseType, Neo4jRuntime
from infrahub.core.query import QueryType
from infrahub.database import InfrahubDatabase, QueryConfig
from infrahub.graphql.cost.runtime import replace_parallel_runtime

PARALLEL_QUERY = "parallel_query"
QUERY = "MATCH (n) RETURN n"


class RecordingDatabase:
    """A database that sends nothing and records the text of each query it would send."""

    def __init__(self) -> None:
        driver = MagicMock()
        driver._pool.in_use_connection_count.return_value = 0
        self.db = InfrahubDatabase(
            driver=driver,
            db_type=DatabaseType.NEO4J,
            queries_names_to_config={PARALLEL_QUERY: QueryConfig(neo4j_runtime=Neo4jRuntime.PARALLEL)},
        )
        self.run_query = AsyncMock(return_value=None)
        self.db.run_query = self.run_query  # type: ignore[method-assign]

    async def sent_query(self, name: str = PARALLEL_QUERY, query_type: QueryType = QueryType.READ) -> str:
        await self.db.execute_query_with_metadata(query=QUERY, name=name, type=query_type)
        assert self.run_query.await_args
        return self.run_query.await_args.kwargs["query"]


async def test_query_configured_for_the_parallel_runtime_uses_it_outside_a_replacement() -> None:
    database = RecordingDatabase()

    assert await database.sent_query() == f"CYPHER runtime = parallel\n{QUERY}"


async def test_replacement_runs_the_parallel_queries_with_the_pipelined_runtime_until_the_block_ends() -> None:
    database = RecordingDatabase()

    with replace_parallel_runtime(Neo4jRuntime.PIPELINED):
        inside = await database.sent_query()
    after = await database.sent_query()

    assert inside == f"CYPHER runtime = pipelined\n{QUERY}"
    assert after == f"CYPHER runtime = parallel\n{QUERY}"


async def test_replacement_applies_to_the_tasks_started_inside_the_block() -> None:
    database = RecordingDatabase()

    with replace_parallel_runtime(Neo4jRuntime.PIPELINED):
        await asyncio.gather(database.sent_query(), database.sent_query())

    assert [call.kwargs["query"] for call in database.run_query.await_args_list] == [
        f"CYPHER runtime = pipelined\n{QUERY}",
        f"CYPHER runtime = pipelined\n{QUERY}",
    ]


async def test_replacement_leaves_the_other_queries_unchanged() -> None:
    database = RecordingDatabase()

    with replace_parallel_runtime(Neo4jRuntime.PIPELINED):
        without_config = await database.sent_query(name="other_query")
        write = await database.sent_query(query_type=QueryType.WRITE)

    assert without_config == QUERY
    assert write == QUERY
