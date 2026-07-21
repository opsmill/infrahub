"""Component tests for resource aggregation in the telemetry gather.

The gather is driven end to end against the testcontainers Neo4j with worker
heartbeats synthesized directly into the in-memory cache (no mocking): the
git_agent fleet is summed over distinct hosts, the api_server host is counted
once regardless of how many gunicorn processes report it, and the additions stay
backward compatible with the existing payload.
"""

from collections.abc import AsyncGenerator
from typing import Generator

import pytest

from infrahub import __version__, config
from infrahub.components import ComponentType
from infrahub.core import registry
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from infrahub.telemetry.constants import TELEMETRY_VERSION
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
# only additive top-level change is the `server` block.
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
_RESOURCE_FIELDS = {"processor_available", "processor_assigned", "memory_total", "memory_available"}


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


async def test_gather_aggregates_worker_and_server_resources(resource_environment: MemoryCache) -> None:
    """git_agent hosts sum; the api_server host is counted once; DB assignment is null."""
    cache = resource_environment

    # Two git_agent hosts, one process each.
    _seed_active(cache, "git_agent", "w1")
    _seed_reading(
        cache,
        "git_agent",
        "w1",
        WorkerResourceReading(
            host="git-host-1",
            processor_available=4,
            processor_assigned=None,
            memory_total=8_000_000_000,
            memory_available=6_000_000_000,
        ),
    )
    _seed_active(cache, "git_agent", "w2")
    _seed_reading(
        cache,
        "git_agent",
        "w2",
        WorkerResourceReading(
            host="git-host-2",
            processor_available=2,
            processor_assigned=None,
            memory_total=4_000_000_000,
            memory_available=1_000_000_000,
        ),
    )

    # One api_server host fronted by two gunicorn processes: two readings sharing a
    # host. Reusing the two worker identities holds the distinct-identity worker count
    # at two while still exercising the per-host dedup on the server side.
    api_reading = WorkerResourceReading(
        host="api-host",
        processor_available=8,
        processor_assigned=None,
        memory_total=16_000_000_000,
        memory_available=10_000_000_000,
    )
    _seed_reading(cache, "api_server", "w1", api_reading)
    _seed_reading(cache, "api_server", "w2", api_reading)

    gatherer = await build_anonymous_telemetry_gatherer()
    data = await gatherer.gather()

    # The worker count keeps its existing meaning: distinct worker identities.
    assert data.workers.total == 2
    assert data.workers.active == 2

    # git_agent fleet: summed over the two distinct hosts.
    assert data.workers.processor_available == 6
    assert data.workers.processor_assigned is None
    assert data.workers.memory_total == 12_000_000_000
    assert data.workers.memory_available == 7_000_000_000

    # api_server: the single host is counted once, not once per gunicorn process.
    assert data.server.processor_available == 8
    assert data.server.processor_assigned is None
    assert data.server.memory_total == 16_000_000_000
    assert data.server.memory_available == 10_000_000_000

    # The database reports cores/memory today but enforces no Cypher-parallelism cap.
    assert data.database.system_info is not None
    assert data.database.system_info.processor_available > 0
    assert data.database.system_info.memory_total > 0
    assert data.database.system_info.processor_assigned is None


async def test_payload_additions_are_backward_compatible(resource_environment: MemoryCache) -> None:
    """The resource additions are purely additive: the version and prior fields are unchanged."""
    # The payload version is deliberately not bumped this phase.
    assert TELEMETRY_VERSION == "20260628"

    gatherer = await build_anonymous_telemetry_gatherer()
    data = await gatherer.gather()
    dumped = data.model_dump(mode="json")

    # Nothing existing is renamed or removed; the only top-level addition is `server`.
    assert set(dumped) == _PRE_FEATURE_DATA_FIELDS | {"server"}

    # `workers` keeps total/active and gains exactly the four resource fields.
    assert set(dumped["workers"]) == _PRE_FEATURE_WORKER_FIELDS | _RESOURCE_FIELDS
    assert isinstance(dumped["workers"]["total"], int)
    assert isinstance(dumped["workers"]["active"], int)

    # The new `server` block carries exactly the four resource fields.
    assert set(dumped["server"]) == _RESOURCE_FIELDS

    # system_info keeps its three fields and gains exactly processor_assigned.
    assert data.database.system_info is not None
    assert set(dumped["database"]["system_info"]) == _PRE_FEATURE_SYSTEM_INFO_FIELDS | {"processor_assigned"}

    # Stable identifiers are untouched by the additions.
    assert dumped["infrahub_version"] == __version__
    assert dumped["deployment_id"] == "test-deployment"
