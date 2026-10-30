from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from infrahub.database import InfrahubDatabase


class RecordedHold:
    def __init__(self) -> None:
        self.events: list[str] = []

    @asynccontextmanager
    async def hold(self) -> AsyncGenerator[None]:
        self.events.append("enter")
        try:
            yield
        finally:
            self.events.append("exit")


async def test_a_held_context_exits_once_the_transaction_commits(db: InfrahubDatabase) -> None:
    recorded = RecordedHold()

    async with db.start_transaction() as dbt:
        await dbt.hold_until_transaction_end(recorded.hold())
        await dbt.execute_query(query="RETURN 1")

        assert recorded.events == ["enter"]

    assert recorded.events == ["enter", "exit"]


async def test_a_held_context_exits_once_the_transaction_rolls_back(db: InfrahubDatabase) -> None:
    recorded = RecordedHold()

    with pytest.raises(ValueError, match=r"^rolled back$"):
        async with db.start_transaction() as dbt:
            await dbt.hold_until_transaction_end(recorded.hold())
            raise ValueError("rolled back")

    assert recorded.events == ["enter", "exit"]


@asynccontextmanager
async def failing_release() -> AsyncGenerator[None]:
    yield
    raise ConnectionError("cache unreachable")


async def test_a_held_context_failing_to_exit_leaves_the_commit_in_place(db: InfrahubDatabase) -> None:
    recorded = RecordedHold()
    marker = str(uuid.uuid4())

    async with db.start_transaction() as dbt:
        await dbt.hold_until_transaction_end(recorded.hold())
        await dbt.hold_until_transaction_end(failing_release())
        await dbt.execute_query(query="CREATE (:TransactionHoldMarker {id: $id})", params={"id": marker})

    assert recorded.events == ["enter", "exit"]
    async with db.start_session() as session_db:
        results = await session_db.execute_query(
            query="MATCH (m:TransactionHoldMarker {id: $id}) DETACH DELETE m RETURN count(*) AS deleted",
            params={"id": marker},
        )
    assert [result["deleted"] for result in results] == [1]


async def test_a_session_cannot_hold_a_context_until_a_transaction_ends(db: InfrahubDatabase) -> None:
    recorded = RecordedHold()

    async with db.start_session() as session_db:
        assert not session_db.can_hold_until_transaction_end
        with pytest.raises(RuntimeError, match=r"^No database transaction is open to hold the context until it ends$"):
            await session_db.hold_until_transaction_end(recorded.hold())

    assert recorded.events == []
