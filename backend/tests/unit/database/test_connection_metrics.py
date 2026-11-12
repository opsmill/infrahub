from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from neo4j import AsyncDriver, AsyncGraphDatabase
from neo4j.exceptions import ConnectionAcquisitionTimeoutError, ServiceUnavailable
from prometheus_client import REGISTRY
from structlog.testing import capture_logs

from infrahub import config
from infrahub.database import get_db, validated_database
from infrahub.database.connection_metrics import instrument_connection_pool

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

WAIT_SECONDS = 0.25


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


class RecordingWait:
    def __init__(self) -> None:
        self.waits: list[float] = []

    def __call__(self, seconds: float) -> None:
        self.waits.append(seconds)


class FailingWait:
    def __call__(self, seconds: float) -> None:
        raise RuntimeError("metric storage unavailable")


@pytest.fixture
async def driver() -> AsyncIterator[AsyncDriver]:
    driver = AsyncGraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "neo4j"))
    yield driver
    await driver.close()


def stand_in_for_the_network(driver: AsyncDriver, clock: FakeClock, connection: object) -> None:
    """Replace the pool's acquisition with one that waits `WAIT_SECONDS` on the fake clock and opens no socket."""

    async def acquire(*args: Any, **kwargs: Any) -> object:
        clock.now += WAIT_SECONDS
        return connection

    driver._pool.acquire = acquire


def stand_in_for_a_full_pool(driver: AsyncDriver, clock: FakeClock) -> None:
    async def acquire(*args: Any, **kwargs: Any) -> object:
        clock.now += WAIT_SECONDS
        raise ConnectionAcquisitionTimeoutError("failed to obtain a connection from the pool within 60.0s")

    driver._pool.acquire = acquire


@pytest.mark.parametrize("uri", ["bolt://localhost:7687", "neo4j://localhost:7687"])
async def test_driver_pool_exposes_the_acquisition_the_wait_metric_wraps(uri: str) -> None:
    driver = AsyncGraphDatabase.driver(uri, auth=("neo4j", "neo4j"))
    try:
        assert callable(driver._pool.acquire)
        assert str(driver._pool.address) == "localhost:7687"
    finally:
        await driver.close()


async def test_pool_size_gauge_equals_the_configured_pool_size(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config.SETTINGS.database, "address", "pool-size-probe")
    monkeypatch.setattr(config.SETTINGS.database, "port", 7687)
    monkeypatch.setattr(config.SETTINGS.database, "protocol", "bolt")
    monkeypatch.setattr(config.SETTINGS.database, "max_connection_pool_size", 7)
    # Mark the database as already validated so get_db does not open a real session.
    monkeypatch.setitem(validated_database, config.SETTINGS.database.database_name, True)

    driver = await get_db()
    try:
        assert REGISTRY.get_sample_value("infrahub_db_connection_pool_size", {"address": "pool-size-probe:7687"}) == 7
    finally:
        await driver.close()


async def test_driver_from_get_db_records_the_wait_of_a_failed_acquisition(monkeypatch: pytest.MonkeyPatch) -> None:
    # Nothing listens on port 1, so the acquisition fails at once without leaving the host.
    monkeypatch.setattr(config.SETTINGS.database, "address", "127.0.0.1")
    monkeypatch.setattr(config.SETTINGS.database, "port", 1)
    monkeypatch.setattr(config.SETTINGS.database, "protocol", "bolt")
    monkeypatch.setitem(validated_database, config.SETTINGS.database.database_name, True)
    count_before = REGISTRY.get_sample_value("infrahub_db_connection_wait_seconds_count") or 0

    driver = await get_db()
    try:
        with pytest.raises(ServiceUnavailable, match=r"^Couldn't connect to 127\.0\.0\.1:1"):
            await driver.verify_connectivity()
    finally:
        await driver.close()

    assert REGISTRY.get_sample_value("infrahub_db_connection_wait_seconds_count") == count_before + 1


async def test_each_acquisition_records_its_wait(driver: AsyncDriver) -> None:
    clock = FakeClock()
    recorder = RecordingWait()
    connection = object()
    stand_in_for_the_network(driver=driver, clock=clock, connection=connection)
    instrument_connection_pool(driver=driver, pool_size=7, record_wait=recorder, clock=clock)

    first = await driver._pool.acquire()
    second = await driver._pool.acquire()

    assert first is connection
    assert second is connection
    assert recorder.waits == [WAIT_SECONDS, WAIT_SECONDS]


async def test_failed_acquisition_records_its_wait_and_raises(driver: AsyncDriver) -> None:
    clock = FakeClock()
    recorder = RecordingWait()
    stand_in_for_a_full_pool(driver=driver, clock=clock)
    instrument_connection_pool(driver=driver, pool_size=7, record_wait=recorder, clock=clock)

    with pytest.raises(
        ConnectionAcquisitionTimeoutError, match=r"^failed to obtain a connection from the pool within 60\.0s$"
    ):
        await driver._pool.acquire()

    assert recorder.waits == [WAIT_SECONDS]


async def test_failure_to_record_the_wait_still_returns_the_connection(driver: AsyncDriver) -> None:
    clock = FakeClock()
    connection = object()
    stand_in_for_the_network(driver=driver, clock=clock, connection=connection)
    instrument_connection_pool(driver=driver, pool_size=7, record_wait=FailingWait(), clock=clock)

    with capture_logs() as records:
        acquired = await driver._pool.acquire()

    assert acquired is connection
    assert [(record["event"], record["log_level"]) for record in records] == [
        ("Failed to record the database connection wait", "error")
    ]


async def test_failure_to_record_the_wait_keeps_the_acquisition_error(driver: AsyncDriver) -> None:
    clock = FakeClock()
    stand_in_for_a_full_pool(driver=driver, clock=clock)
    instrument_connection_pool(driver=driver, pool_size=7, record_wait=FailingWait(), clock=clock)

    with (
        capture_logs(),
        pytest.raises(
            ConnectionAcquisitionTimeoutError, match=r"^failed to obtain a connection from the pool within 60\.0s$"
        ),
    ):
        await driver._pool.acquire()
