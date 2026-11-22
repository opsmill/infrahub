from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from neo4j import AsyncGraphDatabase

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from neo4j import AsyncDriver


@pytest.fixture
async def driver() -> AsyncGenerator[AsyncDriver, None]:
    # Building a driver opens no connection, and these tests never execute against it.
    driver = AsyncGraphDatabase.driver("bolt://127.0.0.1:9", auth=("neo4j", "unused"))
    yield driver
    await driver.close()
