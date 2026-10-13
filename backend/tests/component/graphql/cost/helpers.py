from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import FastAPI

from tests.adapters.cache import MemoryCache
from tests.helpers.db_query_counter import CountingInfrahubDatabase

if TYPE_CHECKING:
    from fastapi.testclient import TestClient

ADMIN_HEADERS = {"X-INFRAHUB-KEY": "admin-security"}
QUERY_COST_HEADERS = {**ADMIN_HEADERS, "X-Infrahub-Query-Cost": "details"}

CARS_BY_PERSON = {"Alice": 0, "Bob": 2, "Carol": 5}


class StatisticsUnreachableCache(MemoryCache):
    """Serves every key except the statistics keys, whose reads fail as when the cache cannot be reached."""

    async def get(self, key: str) -> str | None:
        if key.startswith("graphql_cost:"):
            raise ConnectionError("cache unreachable")
        return await super().get(key=key)


def get_counting_database(client: TestClient) -> CountingInfrahubDatabase:
    """Return the database of a started client application, which the counting client makes a counting one.

    Raises:
        TypeError: When the client does not serve the application or its database does not count queries.

    """
    application = client.app
    if not isinstance(application, FastAPI):
        raise TypeError(f"The client serves a {type(application).__name__}, not a FastAPI application")
    database = application.state.db
    if not isinstance(database, CountingInfrahubDatabase):
        raise TypeError(f"The application database is a {type(database).__name__}, not a counting database")
    return database
