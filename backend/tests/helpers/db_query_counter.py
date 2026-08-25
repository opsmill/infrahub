from __future__ import annotations

from collections import Counter
from typing import TYPE_CHECKING, Any

from infrahub.database import InfrahubDatabase, InfrahubDatabaseMode

if TYPE_CHECKING:
    from neo4j import Record

    from infrahub.core.query import QueryType


class CountingInfrahubDatabase(InfrahubDatabase):
    """Database that records how many queries were executed, keyed by query name."""

    def __init__(
        self, query_counts: Counter[str] | None = None, row_counts: Counter[str] | None = None, **kwargs: Any
    ) -> None:
        super().__init__(**kwargs)
        # shared by reference so counts recorded by derived session/transaction instances land here
        self.query_counts: Counter[str] = query_counts if query_counts is not None else Counter()
        self.row_counts: Counter[str] = row_counts if row_counts is not None else Counter()

    @classmethod
    def from_db(cls, db: InfrahubDatabase) -> CountingInfrahubDatabase:
        """Build a counting database on the driver of an existing one."""
        return cls(
            mode=InfrahubDatabaseMode.DRIVER,
            driver=db._driver,
            db_type=db.db_type,
            default_neo4j_runtime=db.default_neo4j_runtime,
            queries_names_to_config=db.queries_names_to_config,
        )

    def get_context(self) -> dict[str, Any]:
        ctx = super().get_context()
        ctx["query_counts"] = self.query_counts
        ctx["row_counts"] = self.row_counts
        return ctx

    def count_for(self, name: str) -> int:
        return self.query_counts[name]

    def rows_for(self, name: str) -> int:
        """Number of rows the queries of that name returned, to catch a read that grows with the data."""
        return self.row_counts[name]

    def reset_counts(self) -> None:
        self.query_counts.clear()
        self.row_counts.clear()

    async def execute_query_with_metadata(
        self,
        query: str,
        params: dict[str, Any] | None = None,
        name: str = "undefined",
        context: dict[str, str] | None = None,
        type: QueryType | None = None,
        timeout_seconds: float | None = None,
    ) -> tuple[list[Record], dict[str, Any]]:
        self.query_counts[name] += 1
        results, metadata = await super().execute_query_with_metadata(
            query=query, params=params, name=name, context=context, type=type, timeout_seconds=timeout_seconds
        )
        self.row_counts[name] += len(results)
        return results, metadata
