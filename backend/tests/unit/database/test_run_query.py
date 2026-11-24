from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

import pytest
from neo4j import AsyncGraphDatabase, Query
from neo4j.exceptions import ClientError, ServiceUnavailable

from infrahub.database import InfrahubDatabase, InfrahubDatabaseMode
from infrahub.exceptions import DatabaseError

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from neo4j import AsyncDriver, AsyncResult, AsyncSession, AsyncTransaction

QUERY = "MATCH (n) RETURN n"
PARAMS = {"kind": "TestCar"}
QUERY_NAME = "unit_probe"
TIMEOUT_SECONDS = 12.5


class RecordingRunner:
    """Satisfies the run() contract of AsyncSession and AsyncTransaction, keeping every call."""

    def __init__(self) -> None:
        self.calls: list[tuple[Any, dict[str, Any] | None]] = []
        self.result = cast("AsyncResult", object())

    async def run(self, query: Any, parameters: dict[str, Any] | None = None) -> AsyncResult:
        self.calls.append((query, parameters))
        return self.result


class FailingRunner:
    """Satisfies the same run() contract, but every query fails with the given error."""

    def __init__(self, error: Exception) -> None:
        self.error = error

    async def run(self, query: Any, parameters: dict[str, Any] | None = None) -> AsyncResult:
        raise self.error


@dataclass
class ModeTestCase:
    name: str
    """Descriptive name for the test scenario."""

    mode: InfrahubDatabaseMode
    """The database mode that decides which execution path run_query takes."""


MODE_TEST_CASES: list[ModeTestCase] = [
    ModeTestCase(
        name="explicit_transaction",
        mode=InfrahubDatabaseMode.TRANSACTION,
    ),
    ModeTestCase(
        name="auto_commit_session",
        mode=InfrahubDatabaseMode.SESSION,
    ),
]


@pytest.fixture
async def driver() -> AsyncGenerator[AsyncDriver, None]:
    # Building a driver opens no connection, and these tests never execute against it.
    driver = AsyncGraphDatabase.driver("bolt://127.0.0.1:9", auth=("neo4j", "unused"))
    yield driver
    await driver.close()


def build_db(
    driver: AsyncDriver, mode: InfrahubDatabaseMode, runner: RecordingRunner | FailingRunner
) -> InfrahubDatabase:
    if mode == InfrahubDatabaseMode.TRANSACTION:
        return InfrahubDatabase(driver=driver, mode=mode, transaction=cast("AsyncTransaction", runner))
    return InfrahubDatabase(driver=driver, mode=mode, session=cast("AsyncSession", runner))


async def run_probe(db: InfrahubDatabase) -> AsyncResult:
    return await db.run_query(query=QUERY, params=PARAMS, name=QUERY_NAME, timeout_seconds=TIMEOUT_SECONDS)


async def test_explicit_transaction_runs_the_query_unwrapped(driver: AsyncDriver) -> None:
    """A transaction's timeout is fixed when it begins, so the query cannot carry one of its own."""
    runner = RecordingRunner()
    db = build_db(driver=driver, mode=InfrahubDatabaseMode.TRANSACTION, runner=runner)

    result = await run_probe(db)

    assert result is runner.result
    assert runner.calls == [(QUERY, PARAMS)]


async def test_auto_commit_session_wraps_the_query_with_the_timeout(driver: AsyncDriver) -> None:
    runner = RecordingRunner()
    db = build_db(driver=driver, mode=InfrahubDatabaseMode.SESSION, runner=runner)

    result = await run_probe(db)

    assert result is runner.result
    assert len(runner.calls) == 1
    recorded_query, recorded_params = runner.calls[0]
    assert recorded_params == PARAMS
    assert isinstance(recorded_query, Query)
    assert recorded_query.text == QUERY
    assert recorded_query.timeout == TIMEOUT_SECONDS
    assert set(recorded_query.metadata or {}) == {"name", "infrahub_id"}
    assert (recorded_query.metadata or {})["name"] == QUERY_NAME


@pytest.mark.parametrize(
    "test_case",
    [pytest.param(tc, id=tc.name) for tc in MODE_TEST_CASES],
)
async def test_service_unavailable_becomes_database_error(driver: AsyncDriver, test_case: ModeTestCase) -> None:
    error = ServiceUnavailable("the database went away")
    db = build_db(driver=driver, mode=test_case.mode, runner=FailingRunner(error=error))

    with pytest.raises(DatabaseError, match=r"^Unable to connect to the database$") as exc_info:
        await run_probe(db)

    assert exc_info.value.__cause__ is error


@pytest.mark.parametrize(
    "test_case",
    [pytest.param(tc, id=tc.name) for tc in MODE_TEST_CASES],
)
async def test_other_database_errors_are_not_translated(driver: AsyncDriver, test_case: ModeTestCase) -> None:
    error = ClientError("invalid syntax")
    db = build_db(driver=driver, mode=test_case.mode, runner=FailingRunner(error=error))

    with pytest.raises(ClientError, match=r"^invalid syntax$") as exc_info:
        await run_probe(db)

    assert exc_info.value is error
