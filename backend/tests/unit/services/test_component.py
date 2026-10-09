from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest
from neo4j import AsyncGraphDatabase

from infrahub.components import ComponentType
from infrahub.database import InfrahubDatabase
from infrahub.services import InfrahubServices
from infrahub.services.component import (
    COMPONENT_API_SERVER,
    COMPONENT_GIT_AGENT,
    LATEST_RESOURCE_READING,
    RESOURCE_KEY_PREFIX,
    InfrahubComponent,
    LatestResourceReading,
    WorkerInfo,
    refresh_worker_heartbeat,
)
from infrahub.tasks.recurring import trigger_resource_refresh
from infrahub.telemetry.resources import ProcessResources, WorkerResourceReading
from infrahub.worker import WORKER_IDENTITY
from tests.adapters.cache import MemoryCache
from tests.adapters.message_bus import BusRecorder

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Awaitable, Callable, Iterator

RESOURCE_KEY = f"{RESOURCE_KEY_PREFIX}{COMPONENT_GIT_AGENT}:worker:{WORKER_IDENTITY}"
ACTIVE_KEY = f"workers:active:{COMPONENT_GIT_AGENT}:worker:{WORKER_IDENTITY}"


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


def test_attribution_leaves_the_status_payload_unchanged() -> None:
    worker = WorkerInfo(identity="w1")
    worker.add_key(key="workers:active:git_agent:worker:w1")

    assert set(worker.to_dict()) == {"id", "active", "schema_hash"}


async def test_heartbeat_carries_the_latest_published_resource_reading() -> None:
    cache = MemoryCache()
    resources = LatestResourceReading()
    reading = WorkerResourceReading(host="git-host-1", processor_available=4, memory_total=8, memory_available=6)
    resources.publish(reading)

    await refresh_worker_heartbeat(cache=cache, component_type=ComponentType.GIT_AGENT, resources=resources)

    assert WorkerResourceReading.model_validate_json(cache.storage[RESOURCE_KEY]) == reading


async def test_heartbeat_writes_liveness_but_no_resources_before_a_reading_exists() -> None:
    cache = MemoryCache()

    await refresh_worker_heartbeat(
        cache=cache, component_type=ComponentType.GIT_AGENT, resources=LatestResourceReading()
    )

    assert ACTIVE_KEY in cache.storage
    assert RESOURCE_KEY not in cache.storage


def test_a_newer_reading_replaces_the_one_the_beat_carries() -> None:
    resources = LatestResourceReading()
    resources.publish(WorkerResourceReading(host="h", processor_available=2))
    resources.publish(WorkerResourceReading(host="h", processor_available=4))

    latest = resources.latest()

    assert latest is not None
    assert WorkerResourceReading.model_validate_json(latest).processor_available == 4


THREAD_TEST_READING = WorkerResourceReading(
    host="api-host", processor_available=4, processor_assigned=2, memory_total=8, memory_available=6
)


class ThreadRecordingProcessResources(ProcessResources):
    """A resource reader that records, for each read, whether it ran on the thread running the event loop."""

    def __init__(self, event_loop_thread_id: int) -> None:
        super().__init__()
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
    ResourceRefreshCase(name="ten_second_schedule", refresh=refresh_on_schedule),
]


@pytest.fixture
def latest_resource_reading_restored() -> Iterator[None]:
    """Put the process-wide reading back as it was, because every refresh replaces it."""
    saved = LATEST_RESOURCE_READING._payload
    yield
    LATEST_RESOURCE_READING._payload = saved


@pytest.fixture
async def unconnected_db() -> AsyncIterator[InfrahubDatabase]:
    # Building a driver opens no connection, and the resource refresh never queries the database.
    driver = AsyncGraphDatabase.driver("bolt://127.0.0.1:9", auth=("neo4j", "unused"))
    yield InfrahubDatabase(driver=driver)
    await driver.close()


@pytest.mark.parametrize("case", RESOURCE_REFRESH_CASES, ids=[case.name for case in RESOURCE_REFRESH_CASES])
async def test_resource_read_runs_off_the_event_loop_thread(
    case: ResourceRefreshCase, unconnected_db: InfrahubDatabase, latest_resource_reading_restored: None
) -> None:
    """Reading the limit files and the machine's figures blocks, so it must never hold up requests and flows."""
    process_resources = ThreadRecordingProcessResources(event_loop_thread_id=threading.get_ident())
    component = InfrahubComponent(
        cache=MemoryCache(),
        db=unconnected_db,
        message_bus=BusRecorder(),
        component_type=ComponentType.API_SERVER,
        process_resources=process_resources,
    )

    await case.refresh(component)

    assert process_resources.reads_on_event_loop_thread == [False]
    latest = LATEST_RESOURCE_READING.latest()
    assert latest is not None
    assert WorkerResourceReading.model_validate_json(latest) == THREAD_TEST_READING
