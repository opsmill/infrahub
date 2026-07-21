"""Component tests for resource aggregation in the telemetry gather.

The gather is driven end to end against the testcontainers Neo4j with worker
heartbeats synthesized directly into the in-memory cache (no mocking): the
git_agent fleet is summed over distinct hosts, the api_server host is counted
once regardless of how many gunicorn processes report it, and the additions stay
backward compatible with the existing payload.
"""

import logging
from collections.abc import AsyncGenerator
from typing import Generator

import pytest

from infrahub import __version__, config
from infrahub.components import ComponentType
from infrahub.core import registry
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from infrahub.services.component import InfrahubComponent
from infrahub.telemetry import database as telemetry_database
from infrahub.telemetry.constants import TELEMETRY_VERSION, RemoteSendStatus
from infrahub.telemetry.repository import TelemetrySnapshotRepository
from infrahub.telemetry.resources import ProcessResources, WorkerResourceReading
from infrahub.telemetry.tasks import build_anonymous_telemetry_gatherer, send_telemetry_push
from infrahub.worker import WORKER_IDENTITY
from infrahub.workers.dependencies import (
    build_component,
    clear_singletons,
    set_component_type,
)
from tests.adapters.cache import MemoryCache
from tests.adapters.message_bus import BusSimulator


class _AlwaysFailingProcessResources(ProcessResources):
    """A resource reader whose self-read always fails, to drive the retry-then-null path.

    The production reader is built to degrade unreadable sources to null rather than
    raise, so it cannot be deterministically forced into the transient failure the
    retry loop guards against (a control-group file rotated mid-read, a psutil
    hiccup). This adapter stands in for that failure by raising on every attempt, so
    the bounded retries are exhausted and the warning-then-null branch runs.
    """

    def read(self) -> WorkerResourceReading:
        raise OSError("resource read unavailable")


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


async def test_optout_snapshot_carries_resources_without_transmission(
    db: InfrahubDatabase,
    resource_environment: MemoryCache,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Opted out: the resource figures reach the local snapshot and nothing is transmitted.

    The whole payload, resource fields included, is assembled before the store and
    opt-out branch, so with remote transmission disabled the flow persists the
    snapshot and marks it skipped rather than posting it. The git_agent, api_server,
    and database figures must all survive into that stored payload.
    """
    cache = resource_environment
    monkeypatch.setattr(config.SETTINGS.main, "telemetry_optout", True)

    # Two git_agent hosts sum; one api_server host is counted once across its processes.
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
    api_reading = WorkerResourceReading(
        host="api-host",
        processor_available=8,
        processor_assigned=None,
        memory_total=16_000_000_000,
        memory_available=10_000_000_000,
    )
    _seed_reading(cache, "api_server", "w1", api_reading)
    _seed_reading(cache, "api_server", "w2", api_reading)

    # Identify this run's snapshot by set difference so leftover snapshots don't confuse the read-back.
    repository = TelemetrySnapshotRepository(db=db)
    before = {str(snapshot.uuid) for snapshot in await repository.get_list()}

    await send_telemetry_push()

    added = [snapshot for snapshot in await repository.get_list() if str(snapshot.uuid) not in before]
    assert len(added) == 1
    stored = added[0]

    # Opted out: stored locally, marked skipped, never posted.
    assert stored.remote_send_status == RemoteSendStatus.SKIPPED

    payload = stored.data
    # git_agent fleet summed across its two distinct hosts.
    assert payload["workers"]["processor_available"] == 6
    assert payload["workers"]["processor_assigned"] is None
    assert payload["workers"]["memory_total"] == 12_000_000_000
    assert payload["workers"]["memory_available"] == 7_000_000_000

    # api_server host counted once, not per gunicorn process.
    assert payload["server"]["processor_available"] == 8
    assert payload["server"]["processor_assigned"] is None
    assert payload["server"]["memory_total"] == 16_000_000_000
    assert payload["server"]["memory_available"] == 10_000_000_000

    # The database reports cores/memory but enforces no Cypher-parallelism cap.
    assert payload["database"]["system_info"]["processor_assigned"] is None


async def test_database_processor_assigned_read_failure_nulls_only_that_field(
    resource_environment: MemoryCache,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A failing assigned read nulls only that field; the rest of the snapshot survives.

    Feeding an unserializable value as the setting name makes the real Cypher settings
    read fail at the database driver, so the assigned read raises for real rather than
    returning the natural auto-is-null. Only ``processor_assigned`` degrades; the
    JMX-derived figures and the whole snapshot are still produced.
    """
    monkeypatch.setattr(telemetry_database, "DB_WORKER_LIMIT_SETTING", object())

    gatherer = await build_anonymous_telemetry_gatherer()
    with caplog.at_level(logging.WARNING, logger="infrahub.tasks"):
        data = await gatherer.gather()

    # The read genuinely raised and was caught (not merely the auto-is-null default).
    assert any("Telemetry metric collection failed" in record.getMessage() for record in caplog.records)

    # Only the assigned field is null; the independent JMX figures are intact.
    assert data.database.system_info is not None
    assert data.database.system_info.processor_assigned is None
    assert data.database.system_info.processor_available > 0
    assert data.database.system_info.memory_total > 0

    # The snapshot is still fully assembled.
    assert data.execution_time is not None
    assert data.deployment_id == "test-deployment"


async def test_worker_undercount_when_a_worker_does_not_report(resource_environment: MemoryCache) -> None:
    """A worker that never reported its resources is still counted; the aggregate undercounts.

    One git_agent worker reports a reading and a second is active but wrote no resource
    key. The worker count reflects both, while the resource sum covers only the
    reporter, so the shortfall is detectable against the count.
    """
    cache = resource_environment

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
    # A second active worker that never wrote a resources key.
    _seed_active(cache, "git_agent", "w2")

    gatherer = await build_anonymous_telemetry_gatherer()
    data = await gatherer.gather()

    # Both workers are counted...
    assert data.workers.total == 2
    assert data.workers.active == 2
    # ...but the resource aggregate reflects only the one host that reported.
    assert data.workers.processor_available == 4
    assert data.workers.memory_total == 8_000_000_000
    assert data.workers.memory_available == 6_000_000_000


async def test_worker_processor_assigned_is_null_when_a_host_is_unbounded(resource_environment: MemoryCache) -> None:
    """One unbounded host nulls the fleet's assigned cores while available still sums.

    A fleet that contains a node with no enforced quota has no finite assignment, so
    the summed assignment is null even though another host reports a bound; the
    independent available figure still sums across both hosts.
    """
    cache = resource_environment

    _seed_active(cache, "git_agent", "w1")
    _seed_reading(
        cache,
        "git_agent",
        "w1",
        WorkerResourceReading(
            host="git-host-1",
            processor_available=4,
            processor_assigned=4,
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

    gatherer = await build_anonymous_telemetry_gatherer()
    data = await gatherer.gather()

    # The unbounded host nulls the fleet assignment...
    assert data.workers.processor_assigned is None
    # ...while the available cores still sum across both hosts.
    assert data.workers.processor_available == 6


async def test_resources_key_does_not_change_worker_counts(resource_environment: MemoryCache) -> None:
    """Writing a per-process resource key for an existing identity leaves the census untouched.

    A running deployment writes both an active heartbeat and a resource reading for the
    same worker identity on every beat. The resource key must not be mistaken for a new
    worker: the count reflects distinct identities, and reusing an identity for its
    resource reading adds none. Baseline the count from active heartbeats alone, then add
    the resource keys for those same identities and confirm total and active are unchanged.
    """
    cache = resource_environment

    # Three worker identities announce themselves via active heartbeats only, exactly as
    # they did before per-process resource reporting existed.
    _seed_active(cache, "git_agent", "w1")
    _seed_active(cache, "git_agent", "w2")
    _seed_active(cache, "api_server", "w3")

    gatherer = await build_anonymous_telemetry_gatherer()
    baseline = await gatherer.gather()
    assert baseline.workers.total == 3
    assert baseline.workers.active == 3

    # Each of those same identities now also writes its resource reading. The identity is
    # reused, so no new worker should appear in the census.
    reading = WorkerResourceReading(
        host="host-1",
        processor_available=4,
        processor_assigned=None,
        memory_total=8_000_000_000,
        memory_available=6_000_000_000,
    )
    _seed_reading(cache, "git_agent", "w1", reading)
    _seed_reading(cache, "git_agent", "w2", reading)
    _seed_reading(cache, "api_server", "w3", reading)

    after = await gatherer.gather()

    # The resource keys must not perturb the worker count versus the baseline.
    assert after.workers.total == baseline.workers.total == 3
    assert after.workers.active == baseline.workers.active == 3


async def test_self_read_failure_after_retries_logs_and_writes_null(
    db: InfrahubDatabase,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """An exhausted self-read logs a warning with component + source, then writes a null reading.

    A reader that raises on every attempt exhausts the bounded retries; the heartbeat
    must leave a traceable warning carrying the component and the failing source, then
    write a null-valued reading so a worker that stops reporting leaves a trace rather
    than only an aggregate undercount.
    """
    cache = MemoryCache()
    component = InfrahubComponent(
        cache=cache,
        db=db,
        message_bus=BusSimulator(),
        component_type=ComponentType.GIT_AGENT,
        process_resources=_AlwaysFailingProcessResources(),
    )

    with caplog.at_level(logging.WARNING, logger="infrahub"):
        await component.refresh_heartbeat()

    warnings = [
        record
        for record in caplog.records
        if "Unable to read process resource allocation for telemetry" in record.getMessage()
    ]
    assert len(warnings) == 1
    message = warnings[0].getMessage()
    # The warning identifies the component and the failing source so the gap is traceable.
    assert "GIT_AGENT" in message
    assert WORKER_IDENTITY in message
    assert "resource read unavailable" in message

    # After exhausted retries the heartbeat still writes a reading, with null figures.
    stored = cache.storage[f"workers:resources:git_agent:worker:{WORKER_IDENTITY}"]
    reading = WorkerResourceReading.model_validate_json(stored)
    assert reading.processor_available is None
    assert reading.processor_assigned is None
    assert reading.memory_total is None
    assert reading.memory_available is None
    # The dedup key is still populated so the reading is attributable to a host.
    assert reading.host
