"""Component tests for the CPU and memory figures in the telemetry gather.

The gather is driven end to end against the testcontainers Neo4j with worker
heartbeats and readings synthesized directly into the in-memory cache (no
mocking): each block reports one of its containers whole, with how many processes
share it, only live workers' readings are used, and no prior payload key is
renamed or removed.
"""

import logging
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from typing import Generator

import pytest

from infrahub import config
from infrahub.components import ComponentType
from infrahub.core import registry
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from infrahub.telemetry import database as telemetry_database
from infrahub.telemetry.models import TelemetryContainerData
from infrahub.telemetry.resources import WorkerResourceReading
from infrahub.telemetry.tasks import build_anonymous_telemetry_gatherer
from infrahub.workers.dependencies import (
    build_component,
    clear_singletons,
    set_component_type,
)
from tests.adapters.cache import MemoryCache
from tests.adapters.message_bus import BusSimulator

# The full set of `data` fields the payload emitted before resource telemetry; the
# only top-level additions are the `server` and `task_workers` blocks.
_PRE_FEATURE_DATA_FIELDS = {
    "deployment_id",
    "execution_time",
    "infrahub_version",
    "infrahub_type",
    "python_version",
    "platform",
    "workers",
    "branches",
    "accounts",
    "activity_24h",
    "features",
    "schema_info",
    "database",
    "prefect",
}
_PRE_FEATURE_WORKER_FIELDS = {"total", "active"}
_PRE_FEATURE_SYSTEM_INFO_FIELDS = {"memory_total", "memory_available", "processor_available"}


def _seed_active(cache: MemoryCache, component: str, identity: str) -> None:
    cache.storage[f"workers:active:{component}:worker:{identity}"] = Timestamp().to_string()


def _seed_reading(cache: MemoryCache, component: str, identity: str, reading: WorkerResourceReading) -> None:
    cache.storage[f"workers:resources:{component}:worker:{identity}"] = reading.model_dump_json()


@pytest.fixture
async def resource_environment(
    db: InfrahubDatabase,
    register_core_models_schema: SchemaBranch,
    prefect_test_fixture: Generator[None, None, None],
) -> AsyncGenerator[MemoryCache, None]:
    """Wire in-memory adapters and a heartbeating component, then hand back a clean cache.

    The component's own start-up heartbeat is cleared so each test seeds exactly the
    worker and resource keys the gatherer will read. Overrides and singletons are
    restored on teardown so nothing leaks between modules.
    """
    previous_cache = config.OVERRIDE.cache
    previous_message_bus = config.OVERRIDE.message_bus
    previous_registry_id = registry.id
    clear_singletons()
    cache = MemoryCache()
    config.OVERRIDE.cache = cache
    config.OVERRIDE.message_bus = BusSimulator()
    registry.id = "test-deployment"
    set_component_type(ComponentType.API_SERVER)
    await build_component()
    cache.storage.clear()
    try:
        yield cache
    finally:
        config.OVERRIDE.cache = previous_cache
        config.OVERRIDE.message_bus = previous_message_bus
        registry.id = previous_registry_id
        clear_singletons()


def _whole_number_floats(value: object, path: str = "data") -> list[str]:
    """List the places in a JSON-ready value that hold a float with no fractional part."""
    if isinstance(value, float):
        return [path] if value.is_integer() else []
    if isinstance(value, dict):
        return [found for key, item in value.items() for found in _whole_number_floats(item, f"{path}.{key}")]
    if isinstance(value, list):
        return [found for index, item in enumerate(value) for found in _whole_number_floats(item, f"{path}[{index}]")]
    return []


async def test_gather_reports_one_container_for_each_component(
    resource_environment: MemoryCache, caplog: pytest.LogCaptureFixture
) -> None:
    """Each block counts its own processes and reports one of its containers with the processes that share it."""
    cache = resource_environment

    # Two git_agent replicas, one process per container.
    git_reading = WorkerResourceReading(
        processes_per_container=1,
        processor_available=4,
        processor_assigned=None,
        memory_total=8_000_000_000,
        memory_available=6_000_000_000,
    )
    _seed_active(cache, "git_agent", "w1")
    _seed_reading(cache, "git_agent", "w1", git_reading)
    _seed_active(cache, "git_agent", "w2")
    _seed_reading(cache, "git_agent", "w2", git_reading)

    # One api_server container running three gunicorn processes, which share it.
    api_reading = WorkerResourceReading(
        processes_per_container=3,
        processor_available=6,
        processor_assigned=6,
        memory_total=12_000_000_000,
        memory_available=9_000_000_000,
    )
    for identity in ("api1", "api2", "api3"):
        _seed_active(cache, "api_server", identity)
        _seed_reading(cache, "api_server", identity, api_reading)

    # A process that stopped recently, known only by its presence key.
    cache.storage["workers:worker:exited"] = Timestamp().to_string()

    gatherer = await build_anonymous_telemetry_gatherer()
    with caplog.at_level(logging.WARNING):
        data = await gatherer.gather()

    # `workers` counts every worker process, as before; the new blocks break it down by component.
    assert (data.workers.total, data.workers.active) == (6, 5)
    assert (data.task_workers.total, data.task_workers.active) == (2, 2)
    assert (data.server.total, data.server.active) == (3, 3)

    # A git_agent process has its container to itself.
    assert data.task_workers.processes_per_container == 1
    assert data.task_workers.per_container == TelemetryContainerData(
        processor_available=4,
        processor_assigned=None,
        memory_total=8_000_000_000,
        memory_available=6_000_000_000,
    )

    # The api_server container is reported whole, with the three processes that share it.
    assert data.server.processes_per_container == 3
    assert data.server.per_container == TelemetryContainerData(
        processor_available=6,
        processor_assigned=6,
        memory_total=12_000_000_000,
        memory_available=9_000_000_000,
    )

    # The test database leaves the Cypher parallel runtime's worker limit at its default.
    assert data.database.system_info is not None
    assert data.database.system_info.processor_available > 0
    assert data.database.system_info.memory_total > 0
    assert data.database.system_info.processor_assigned is None
    # A failed settings read would also give null, so the healthy gather must log no warning.
    assert [record.getMessage() for record in caplog.records if record.levelno >= logging.WARNING] == []

    # A whole-number float would fail the telemetry endpoint's checksum check, which writes 2.0 as 2.
    assert _whole_number_floats(data.model_dump(mode="json")) == []


async def test_database_memory_assigned_is_heap_plus_page_cache(
    resource_environment: MemoryCache,
    neo4j: dict[int, int] | None,
    neo4j_heap_bytes: int,
    neo4j_pagecache_bytes: int,
) -> None:
    """The database reports the heap and the page cache it was started with, added up."""
    if neo4j is None:
        pytest.skip("The test session did not start the database, so its memory settings are not known")

    gatherer = await build_anonymous_telemetry_gatherer()
    data = await gatherer.gather()

    assert data.database.system_info is not None
    assert data.database.system_info.memory_assigned == neo4j_heap_bytes + neo4j_pagecache_bytes


async def test_corrupted_reading_is_dropped(resource_environment: MemoryCache) -> None:
    """A cache entry corrupted into a negative figure is dropped instead of reaching the payload."""
    cache = resource_environment

    healthy_reading = WorkerResourceReading(
        processes_per_container=1,
        processor_available=4,
        processor_assigned=None,
        memory_total=8_000_000_000,
        memory_available=6_000_000_000,
    )
    _seed_active(cache, "git_agent", "healthy")
    _seed_reading(cache, "git_agent", "healthy", healthy_reading)

    _seed_active(cache, "git_agent", "corrupted")
    # Written as raw JSON, bypassing WorkerResourceReading's own validation, the way a
    # value actually corrupted or stale in the cache would arrive. It reports one more
    # figure than the healthy reading, so it would be the one reported if it were kept.
    cache.storage["workers:resources:git_agent:worker:corrupted"] = (
        '{"processes_per_container": 1, "processor_available": -4, "processor_assigned": 2, '
        '"memory_total": 8000000000, "memory_available": 6000000000}'
    )

    gatherer = await build_anonymous_telemetry_gatherer()
    data = await gatherer.gather()

    # Both workers are still counted...
    assert (data.task_workers.total, data.task_workers.active) == (2, 2)
    # ...but only the healthy reading is reported.
    assert data.task_workers.per_container == TelemetryContainerData(
        processor_available=4,
        processor_assigned=None,
        memory_total=8_000_000_000,
        memory_available=6_000_000_000,
    )
    assert await gatherer.component.read_worker_resources(worker_ids={"healthy", "corrupted"}) == {
        "git_agent": [healthy_reading]
    }


async def test_a_stopped_workers_reading_is_ignored(resource_environment: MemoryCache) -> None:
    """A stopped worker's reading stays in the cache for up to two hours, but only live workers' readings are used.

    The stopped worker's reading reports more figures, so it would be the one used if it were kept.
    """
    cache = resource_environment

    _seed_active(cache, "api_server", "live")
    _seed_reading(cache, "api_server", "live", WorkerResourceReading(processes_per_container=4, processor_available=4))
    cache.storage["workers:worker:stopped"] = Timestamp().to_string()
    _seed_reading(
        cache,
        "api_server",
        "stopped",
        WorkerResourceReading(processes_per_container=4, processor_available=6, memory_total=8_000_000_000),
    )

    gatherer = await build_anonymous_telemetry_gatherer()
    data = await gatherer.gather()

    # The stopped worker is still counted, the way `workers` counts it, but not as active.
    assert (data.server.total, data.server.active) == (2, 1)
    assert data.server.per_container == TelemetryContainerData(processor_available=4)


async def test_payload_keeps_every_prior_key(resource_environment: MemoryCache) -> None:
    """No prior key is renamed or removed, and the new keys sit only in the new blocks and fields."""
    gatherer = await build_anonymous_telemetry_gatherer()
    data = await gatherer.gather()
    dumped = data.model_dump(mode="json")

    # Nothing existing is renamed or removed; the only top-level additions are the two new blocks.
    assert set(dumped) == _PRE_FEATURE_DATA_FIELDS | {"server", "task_workers"}

    # `workers` is exactly as before.
    assert set(dumped["workers"]) == _PRE_FEATURE_WORKER_FIELDS

    # The new blocks follow the same total/active convention and add one container's figures.
    for block in ("server", "task_workers"):
        assert set(dumped[block]) == _PRE_FEATURE_WORKER_FIELDS | {"processes_per_container", "per_container"}

    # system_info keeps its three fields and gains exactly the two assigned figures.
    assert data.database.system_info is not None
    assert set(dumped["database"]["system_info"]) == _PRE_FEATURE_SYSTEM_INFO_FIELDS | {
        "processor_assigned",
        "memory_assigned",
    }


@dataclass
class AssignedReadFailureCase:
    name: str
    setting_constant: str
    failed_field: str
    other_field: str


ASSIGNED_READ_FAILURE_CASES = [
    AssignedReadFailureCase(
        name="processor_assigned",
        setting_constant="DB_WORKER_LIMIT_SETTING",
        failed_field="processor_assigned",
        other_field="memory_assigned",
    ),
    AssignedReadFailureCase(
        name="memory_assigned",
        setting_constant="DB_HEAP_MAX_SETTING",
        failed_field="memory_assigned",
        other_field="processor_assigned",
    ),
]


@pytest.mark.parametrize("case", ASSIGNED_READ_FAILURE_CASES, ids=[case.name for case in ASSIGNED_READ_FAILURE_CASES])
async def test_database_assigned_read_failure_nulls_only_that_field(
    resource_environment: MemoryCache,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    case: AssignedReadFailureCase,
) -> None:
    """A failing assigned read nulls only that field; the rest of the snapshot survives.

    Feeding an unserializable value as a setting name makes the real Cypher settings
    read fail at the database driver, so the read raises for real rather than
    returning the natural unset-is-null. Only that field degrades; the other assigned
    figure, the JMX-derived figures and the whole snapshot are still produced.
    """
    healthy = await (await build_anonymous_telemetry_gatherer()).gather()
    assert healthy.database.system_info is not None

    monkeypatch.setattr(telemetry_database, case.setting_constant, object())

    gatherer = await build_anonymous_telemetry_gatherer()
    with caplog.at_level(logging.WARNING, logger="infrahub.tasks"):
        data = await gatherer.gather()

    # The read genuinely raised and was caught (not merely the unset-is-null default).
    assert any("Telemetry metric collection failed" in record.getMessage() for record in caplog.records)

    # Only the failed field is null; the other assigned figure matches the healthy gather.
    assert data.database.system_info is not None
    system_info = data.database.system_info.model_dump()
    assert system_info[case.failed_field] is None
    assert system_info[case.other_field] == healthy.database.system_info.model_dump()[case.other_field]
    assert data.database.system_info.processor_available > 0
    assert data.database.system_info.memory_total > 0

    # The snapshot is still fully assembled.
    assert data.execution_time is not None
    assert data.deployment_id == "test-deployment"


async def test_a_worker_that_does_not_report_is_still_counted(resource_environment: MemoryCache) -> None:
    """An active worker that wrote no resource reading is counted, and the reporter's reading is used."""
    cache = resource_environment

    _seed_active(cache, "git_agent", "w1")
    _seed_reading(
        cache,
        "git_agent",
        "w1",
        WorkerResourceReading(
            processes_per_container=1,
            processor_available=4,
            processor_assigned=None,
            memory_total=8_000_000_000,
            memory_available=6_000_000_000,
        ),
    )
    # A second active worker that never wrote a resources key.
    _seed_active(cache, "git_agent", "w2")

    gatherer = await build_anonymous_telemetry_gatherer()
    data = await gatherer.gather()

    assert (data.task_workers.total, data.task_workers.active) == (2, 2)
    assert data.task_workers.per_container == TelemetryContainerData(
        processor_available=4,
        processor_assigned=None,
        memory_total=8_000_000_000,
        memory_available=6_000_000_000,
    )
