"""Execution seam for prepared graph-traversal queries.

The runner is the boundary between deciding *which* queries to run (the executors) and *how* a
single prepared query is executed. Injecting it lets the execution strategy be swapped
independently of the executor.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from infrahub.core.query import Query
    from infrahub.database import InfrahubDatabase


class QueryRunner(Protocol):
    """Executes a prepared query under the configured server-side timeout."""

    async def run(self, query: Query, *, db: InfrahubDatabase, timeout_seconds: float | None) -> None: ...


class DefaultQueryRunner:
    """Executes the query against the database."""

    async def run(self, query: Query, *, db: InfrahubDatabase, timeout_seconds: float | None) -> None:
        await query.execute(db=db, timeout_seconds=timeout_seconds)
