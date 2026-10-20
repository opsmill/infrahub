from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

import pytest
from neo4j import AsyncGraphDatabase

from infrahub.core.constants import InfrahubKind
from infrahub.core.protocols import CoreNumberPool
from infrahub.database import InfrahubDatabase
from infrahub.exceptions import NodeNotFoundError
from infrahub.pools.number_pool_lookup import NumberPoolLookup

from .helpers import InMemoryNumberPool

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator


@dataclass
class GetOneCall:
    id: str
    db: InfrahubDatabase
    kind: type[CoreNumberPool]


@dataclass
class QueryCall:
    db: InfrahubDatabase
    schema: type[CoreNumberPool]
    filters: dict | None


@dataclass
class RecordingNumberPoolReader:
    """Holds pools in memory and records each read, in order."""

    pools: list[InMemoryNumberPool]
    calls: list[GetOneCall | QueryCall] = field(default_factory=list)

    async def get_one(
        self, id: str, db: InfrahubDatabase, kind: type[CoreNumberPool], raise_on_error: Literal[True]
    ) -> InMemoryNumberPool:
        self.calls.append(GetOneCall(id=id, db=db, kind=kind))
        for pool in self.pools:
            if pool.id == id:
                return pool
        raise NodeNotFoundError(node_type=InfrahubKind.NUMBERPOOL, identifier=id)

    async def query(
        self, db: InfrahubDatabase, schema: type[CoreNumberPool], filters: dict | None
    ) -> list[InMemoryNumberPool]:
        self.calls.append(QueryCall(db=db, schema=schema, filters=filters))
        name = (filters or {}).get("name__value")
        return [pool for pool in self.pools if pool.name.value == name]


POOL_ID = "5c1f6e0a-0000-0000-0000-00000000bbbb"
UNKNOWN_ID = "5c1f6e0a-0000-0000-0000-00000000ffff"


@pytest.fixture
async def db() -> AsyncGenerator[InfrahubDatabase, None]:
    # Building a driver opens no connection, and the lookup only hands the database to the reader.
    driver = AsyncGraphDatabase.driver("bolt://127.0.0.1:9", auth=("neo4j", "unused"))
    yield InfrahubDatabase(driver=driver)
    await driver.close()


@pytest.fixture
def pool() -> InMemoryNumberPool:
    return InMemoryNumberPool(id=POOL_ID, name="tickets")


@pytest.fixture
def reader(pool: InMemoryNumberPool) -> RecordingNumberPoolReader:
    return RecordingNumberPoolReader(pools=[pool])


@pytest.fixture
def lookup(db: InfrahubDatabase, reader: RecordingNumberPoolReader) -> NumberPoolLookup:
    return NumberPoolLookup(db=db, node_manager=reader)


async def test_a_pool_named_by_id_is_read_by_id(
    db: InfrahubDatabase, pool: InMemoryNumberPool, lookup: NumberPoolLookup, reader: RecordingNumberPoolReader
) -> None:
    assert await lookup.find(pool_ref=POOL_ID) is pool
    assert reader.calls == [GetOneCall(id=POOL_ID, db=db, kind=CoreNumberPool)]


async def test_a_pool_named_by_name_is_read_by_its_name(
    db: InfrahubDatabase, pool: InMemoryNumberPool, lookup: NumberPoolLookup, reader: RecordingNumberPoolReader
) -> None:
    assert await lookup.find(pool_ref="tickets") is pool
    assert reader.calls == [QueryCall(db=db, schema=CoreNumberPool, filters={"name__value": "tickets"})]


async def test_an_unknown_name_is_not_found(lookup: NumberPoolLookup) -> None:
    with pytest.raises(
        NodeNotFoundError, match=r"Unable to find the node no-such-pool / CoreNumberPool in the database\."
    ):
        await lookup.find(pool_ref="no-such-pool")


async def test_an_unknown_id_is_not_found_and_not_read_as_a_name(
    db: InfrahubDatabase, lookup: NumberPoolLookup, reader: RecordingNumberPoolReader
) -> None:
    with pytest.raises(
        NodeNotFoundError, match=rf"Unable to find the node {UNKNOWN_ID} / CoreNumberPool in the database\."
    ):
        await lookup.find(pool_ref=UNKNOWN_ID)
    assert reader.calls == [GetOneCall(id=UNKNOWN_ID, db=db, kind=CoreNumberPool)]
