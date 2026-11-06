from __future__ import annotations

import socket

import pytest
from neo4j import AsyncGraphDatabase
from neo4j.exceptions import ServiceUnavailable

from infrahub.database import InfrahubDatabase
from infrahub.health import ErrorCategory, classify_error


def _closed_local_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


async def test_check_health_passes_on_a_reachable_database(db: InfrahubDatabase) -> None:
    await db.check_health()


async def test_check_health_raises_when_nothing_listens_at_the_database_address() -> None:
    driver = AsyncGraphDatabase.driver(f"bolt://127.0.0.1:{_closed_local_port()}", auth=("neo4j", "unused"))
    database = InfrahubDatabase(driver=driver)
    try:
        with pytest.raises(ServiceUnavailable, match=r"^Couldn't connect to 127\.0\.0\.1:\d+") as exc_info:
            await database.check_health()
    finally:
        await database.close()

    assert classify_error(exc_info.value) == ErrorCategory.CONNECTION_REFUSED
