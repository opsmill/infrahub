from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub.database import InfrahubDatabase, InfrahubDatabaseMode

if TYPE_CHECKING:
    from neo4j import Record

    from infrahub.core.query import QueryType


class InjectedQueryError(Exception):
    """Raised in place of a query the failing database was told to fail."""


class FailingQueryInfrahubDatabase(InfrahubDatabase):
    """Database that raises instead of running the queries with the given names."""

    def __init__(self, failing_query_names: frozenset[str] = frozenset(), **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.failing_query_names = failing_query_names

    @classmethod
    def from_db(cls, db: InfrahubDatabase, failing_query_names: set[str]) -> FailingQueryInfrahubDatabase:
        """Build a failing database on the driver of an existing one."""
        return cls(
            mode=InfrahubDatabaseMode.DRIVER,
            driver=db._driver,
            db_type=db.db_type,
            default_neo4j_runtime=db.default_neo4j_runtime,
            queries_names_to_config=db.queries_names_to_config,
            failing_query_names=frozenset(failing_query_names),
        )

    def get_context(self) -> dict[str, Any]:
        ctx = super().get_context()
        ctx["failing_query_names"] = self.failing_query_names
        return ctx

    async def execute_query_with_metadata(
        self,
        query: str,
        params: dict[str, Any] | None = None,
        name: str = "undefined",
        context: dict[str, str] | None = None,
        type: QueryType | None = None,
        timeout_seconds: float | None = None,
    ) -> tuple[list[Record], dict[str, Any]]:
        if name in self.failing_query_names:
            raise InjectedQueryError(f"Query '{name}' failed on purpose")
        return await super().execute_query_with_metadata(
            query=query, params=params, name=name, context=context, type=type, timeout_seconds=timeout_seconds
        )
