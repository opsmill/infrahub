from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest
from neo4j import AsyncGraphDatabase

from infrahub.components import ComponentType
from infrahub.database import InfrahubDatabase
from infrahub.message_bus.types import KVTTL
from infrahub.services import InfrahubServices
from infrahub.services.component import (
    COMPONENT_API_SERVER,
    COMPONENT_GIT_AGENT,
    RESOURCE_KEY_PREFIX,
    InfrahubComponent,
    WorkerInfo,
    refresh_worker_heartbeat,
)
from infrahub.tasks.recurring import trigger_resource_refresh
from infrahub.telemetry.resources import ProcessResources, WorkerResourceReading
from infrahub.worker import WORKER_IDENTITY
from tests.adapters.cache import MemoryCache
from tests.adapters.machine import FixedMachine
from tests.adapters.message_bus import BusRecorder

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Awaitable, Callable

RESOURCE_KEY = f"{RESOURCE_KEY_PREFIX}{COMPONENT_GIT_AGENT}:worker:{WORKER_IDENTITY}"
ACTIVE_KEY = f"workers:active:{COMPONENT_GIT_AGENT}:worker:{WORKER_IDENTITY}"
API_RESOURCE_KEY = f"{RESOURCE_KEY_PREFIX}{COMPONENT_API_SERVER}:worker:{WORKER_IDENTITY}"


@dataclass
class AttributionCase:
    name: str
    keys: list[str]
    expected_component: str | None
    expected_active: bool


ATTRIBUTION_CASES = [
    AttributionCase(
        name="active_key_names_the_component",
        keys=["workers:active:git_agent:worker:w1", "workers:worker:w1"],
        expected_component=COMPONENT_GIT_AGENT,
        expected_active=True,
    ),
    AttributionCase(
        # A process that stopped heartbeating keeps its schema-hash key for a while,
        # which still says what it ran as, whatever the branch segment holds.
        name="schema_hash_key_attributes_an_exited_process",
        keys=["workers:schema_hash:branch:3f2a-branch:api_server:worker:w1", "workers:worker:w1"],
        expected_component=COMPONENT_API_SERVER,
        expected_active=False,
    ),
    AttributionCase(
        name="resource_key_names_the_component",
        keys=["workers:resources:api_server:worker:w1"],
        expected_component=COMPONENT_API_SERVER,
        expected_active=False,
    ),
    AttributionCase(
        name="presence_key_alone_leaves_the_process_unattributed",
        keys=["workers:worker:w1"],
        expected_component=None,
        expected_active=False,
    ),
    AttributionCase(
        name="an_unknown_component_name_is_not_taken_on_trust",
        keys=["workers:active:scheduler:worker:w1"],
        expected_component=None,
        expected_active=True,
    ),
]


@pytest.mark.parametrize("case", ATTRIBUTION_CASES, ids=[case.name for case in ATTRIBUTION_CASES])
def test_worker_is_attributed_to_the_component_its_keys_name(case: AttributionCase) -> None:
    worker = WorkerInfo(identity="w1")

    for key in case.keys:
        worker.add_key(key=key)

    assert worker.component == case.expected_component
    assert worker.active is case.expected_active


async def test_heartbeat_writes_liveness_and_no_resource_reading() -> None:
    cache = MemoryCache()

    await refresh_worker_heartbeat(cache=cache, component_type=ComponentType.GIT_AGENT)

    assert set(cache.storage) == {ACTIVE_KEY, f"workers:worker:{WORKER_IDENTITY}"}


THREAD_TEST_READING = WorkerResourceReading(
    host="api-host", processor_available=4, processor_assigned=2, memory_total=8, memory_available=6
)


class ThreadRecordingProcessResources(ProcessResources):
    """A resource reader that records, for each read, whether it ran on the thread running the event loop."""

    def __init__(self, event_loop_thread_id: int) -> None:
        super().__init__(machine=FixedMachine())
        self.event_loop_thread_id = event_loop_thread_id
        self.reads_on_event_loop_thread: list[bool] = []

    def read(self) -> WorkerResourceReading:
        self.reads_on_event_loop_thread.append(threading.get_ident() == self.event_loop_thread_id)
        return THREAD_TEST_READING


async def refresh_at_startup(component: InfrahubComponent) -> None:
    await component.refresh_heartbeat()


async def refresh_on_schedule(component: InfrahubComponent) -> None:
    service = await InfrahubServices.new(component=component)
    await trigger_resource_refresh(service)


@dataclass
class ResourceRefreshCase:
    name: str
    refresh: Callable[[InfrahubComponent], Awaitable[None]]


RESOURCE_REFRESH_CASES = [
    ResourceRefreshCase(name="startup_heartbeat", refresh=refresh_at_startup),
    ResourceRefreshCase(name="recurring_schedule", refresh=refresh_on_schedule),
]


@pytest.fixture
async def unconnected_db() -> AsyncIterator[InfrahubDatabase]:
    # Building a driver opens no connection, and the resource refresh never queries the database.
    driver = AsyncGraphDatabase.driver("bolt://127.0.0.1:9", auth=("neo4j", "unused"))
    yield InfrahubDatabase(driver=driver)
    await driver.close()


@pytest.mark.parametrize("case", RESOURCE_REFRESH_CASES, ids=[case.name for case in RESOURCE_REFRESH_CASES])
async def test_resource_reading_is_taken_off_the_event_loop_and_kept_for_two_hours(
    case: ResourceRefreshCase, unconnected_db: InfrahubDatabase
) -> None:
    """Reading the limit files and the machine's figures blocks, so it must never hold up requests and flows.

    The reading is kept for two hours, so a long task that keeps the main loop from reading again does not lose it.
    """
    cache = MemoryCache()
    process_resources = ThreadRecordingProcessResources(event_loop_thread_id=threading.get_ident())
    component = InfrahubComponent(
        cache=cache,
        db=unconnected_db,
        message_bus=BusRecorder(),
        component_type=ComponentType.API_SERVER,
        process_resources=process_resources,
    )

    await case.refresh(component)

    assert process_resources.reads_on_event_loop_thread == [False]
    assert WorkerResourceReading.model_validate_json(cache.storage[API_RESOURCE_KEY]) == THREAD_TEST_READING
    assert cache.expiries[API_RESOURCE_KEY] == KVTTL.TWO_HOURS


class ResourceWriteFailingCache(MemoryCache):
    """A cache that refuses to store a resource reading and stores everything else."""

    async def set(self, key: str, value: str, expires: int | None = None, not_exists: bool = False) -> bool | None:
        if key.startswith(RESOURCE_KEY_PREFIX):
            raise ConnectionError("resource write refused")
        return await super().set(key=key, value=value, expires=expires, not_exists=not_exists)


async def test_startup_publishes_liveness_before_storing_the_resource_reading(
    unconnected_db: InfrahubDatabase,
) -> None:
    cache = ResourceWriteFailingCache()
    component = InfrahubComponent(
        cache=cache,
        db=unconnected_db,
        message_bus=BusRecorder(),
        component_type=ComponentType.GIT_AGENT,
        process_resources=ThreadRecordingProcessResources(event_loop_thread_id=threading.get_ident()),
    )

    with pytest.raises(ConnectionError, match=r"^resource write refused$"):
        await component.refresh_heartbeat()

    assert set(cache.storage) == {ACTIVE_KEY, f"workers:worker:{WORKER_IDENTITY}"}


async def test_read_worker_resources_returns_only_the_given_workers(unconnected_db: InfrahubDatabase) -> None:
    """A stopped worker's reading stays in the cache for up to two hours, so it must not be returned."""
    cache = MemoryCache()
    live_reading = WorkerResourceReading(host="api-host", processor_available=4)
    stopped_reading = WorkerResourceReading(host="api-host", processor_available=8, memory_total=16)
    cache.storage[f"{RESOURCE_KEY_PREFIX}{COMPONENT_API_SERVER}:worker:live"] = live_reading.model_dump_json()
    cache.storage[f"{RESOURCE_KEY_PREFIX}{COMPONENT_API_SERVER}:worker:stopped"] = stopped_reading.model_dump_json()
    component = InfrahubComponent(
        cache=cache, db=unconnected_db, message_bus=BusRecorder(), component_type=ComponentType.GIT_AGENT
    )

    assert await component.read_worker_resources(worker_ids={"live"}) == {COMPONENT_API_SERVER: [live_reading]}


class AlwaysFailingProcessResources(ProcessResources):
    """A resource reader whose self-read always fails, to drive the retry-then-empty-reading path.

    It raises from the read itself, so the retries are tested without depending on which source
    makes the real reader fail. Its container name is fixed, so the stored reading can be checked
    exactly.
    """

    def __init__(self) -> None:
        super().__init__(machine=FixedMachine())

    def read(self) -> WorkerResourceReading:
        raise OSError("resource read unavailable")

    def container_name(self) -> str:
        return "worker-container"


class NamelessFailingProcessResources(AlwaysFailingProcessResources):
    """A resource reader that cannot read even its container's name, the case where no name can be stored."""

    def container_name(self) -> str:
        raise OSError("container name unavailable")


@dataclass
class FailedSelfReadCase:
    name: str
    process_resources: ProcessResources
    expected_reading: WorkerResourceReading


FAILED_SELF_READ_CASES = [
    FailedSelfReadCase(
        name="the_empty_reading_keeps_the_container_name",
        process_resources=AlwaysFailingProcessResources(),
        expected_reading=WorkerResourceReading(host="worker-container"),
    ),
    FailedSelfReadCase(
        name="a_container_name_that_cannot_be_read_is_stored_as_unknown",
        process_resources=NamelessFailingProcessResources(),
        expected_reading=WorkerResourceReading(host="unknown"),
    ),
]


@pytest.mark.parametrize("case", FAILED_SELF_READ_CASES, ids=[case.name for case in FAILED_SELF_READ_CASES])
async def test_self_read_failure_after_retries_logs_and_stores_an_empty_reading(
    case: FailedSelfReadCase,
    unconnected_db: InfrahubDatabase,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A read that fails on every try leaves a warning naming the component and the error, and a reading with no figures.

    The reading keeps the container's name, so the process still counts as sharing its container.
    """
    cache = MemoryCache()
    component = InfrahubComponent(
        cache=cache,
        db=unconnected_db,
        message_bus=BusRecorder(),
        component_type=ComponentType.GIT_AGENT,
        process_resources=case.process_resources,
    )

    with caplog.at_level(logging.WARNING, logger="infrahub"):
        await component.refresh_heartbeat()

    warnings = [record for record in caplog.records if WORKER_IDENTITY in record.getMessage()]
    assert [record.levelname for record in warnings] == ["WARNING"]
    assert "GIT_AGENT" in warnings[0].getMessage()
    assert "resource read unavailable" in warnings[0].getMessage()
    assert WorkerResourceReading.model_validate_json(cache.storage[RESOURCE_KEY]) == case.expected_reading
