"""Component tests for the per-worker resource figures in the telemetry gather.

The gather is driven end to end against the testcontainers Neo4j with worker
heartbeats synthesized directly into the in-memory cache (no mocking): each block
reports one worker's share of its container, an api_server container is split
across the gunicorn processes that report from it, and no prior payload key is
renamed or removed.
"""

import logging
from collections.abc import AsyncGenerator
from dataclasses import dataclass
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
from infrahub.telemetry.models import TelemetryPerWorkerData
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
    the bounded retries are exhausted and the warning-then-null branch runs. Its
    container name is fixed, so the stored reading can be checked exactly.
    """

    def read(self) -> WorkerResourceReading:
        raise OSError("resource read unavailable")

    def container_name(self) -> str:
        return "worker-container"


class _NamelessFailingProcessResources(_AlwaysFailingProcessResources):
    """A resource reader that cannot read even its container's name, the case where no name can be stored."""

    def container_name(self) -> str:
        raise OSError("container name unavailable")


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


async def test_gather_reports_one_workers_share_for_each_component(resource_environment: MemoryCache) -> None:
    """Each block counts its own processes and reports one worker's share of its container."""
    cache = resource_environment

    # Two git_agent replicas, one process per container.
    git_reading = WorkerResourceReading(
        host="git-host-1",
        processor_available=4,
        processor_assigned=None,
        memory_total=8_000_000_000,
        memory_available=6_000_000_000,
    )
    _seed_active(cache, "git_agent", "w1")
    _seed_reading(cache, "git_agent", "w1", git_reading)
    _seed_active(cache, "git_agent", "w2")
    _seed_reading(cache, "git_agent", "w2", git_reading.model_copy(update={"host": "git-host-2"}))

    # One api_server container running three gunicorn processes, which share it.
    api_reading = WorkerResourceReading(
        host="api-host",
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
    data = await gatherer.gather()

    # `workers` counts every worker process, as before; the new blocks break it down by component.
    assert (data.workers.total, data.workers.active) == (6, 5)
    assert (data.task_workers.total, data.task_workers.active) == (2, 2)
    assert (data.server.total, data.server.active) == (3, 3)

    # A git_agent process has its container to itself.
    assert data.task_workers.per_worker == TelemetryPerWorkerData(
        processor_available=4.0,
        processor_assigned=None,
        memory_total=8_000_000_000,
        memory_available=6_000_000_000,
    )

    # An api_server process gets a third of its container.
    assert data.server.per_worker == TelemetryPerWorkerData(
        processor_available=2.0,
        processor_assigned=2.0,
        memory_total=4_000_000_000,
        memory_available=3_000_000_000,
    )

    # The test database leaves the Cypher parallel runtime's worker limit at its default.
    assert data.database.system_info is not None
    assert data.database.system_info.processor_available > 0
    assert data.database.system_info.memory_total > 0
    assert data.database.system_info.processor_assigned is None


async def test_corrupted_reading_is_dropped(resource_environment: MemoryCache) -> None:
    """A cache entry corrupted into a negative figure is dropped instead of reaching the payload."""
    cache = resource_environment

    healthy_reading = WorkerResourceReading(
        host="git-host-good",
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
        '{"host": "git-host-bad", "processor_available": -4, "processor_assigned": 2, '
        '"memory_total": 8000000000, "memory_available": 6000000000}'
    )

    gatherer = await build_anonymous_telemetry_gatherer()
    data = await gatherer.gather()

    # Both workers are still counted...
    assert (data.task_workers.total, data.task_workers.active) == (2, 2)
    # ...but only the healthy reading is reported.
    assert data.task_workers.per_worker == TelemetryPerWorkerData(
        processor_available=4.0,
        processor_assigned=None,
        memory_total=8_000_000_000,
        memory_available=6_000_000_000,
    )
    assert await gatherer.component.read_worker_resources() == {"git_agent": [healthy_reading]}


async def test_payload_keeps_every_prior_key_and_its_version(resource_environment: MemoryCache) -> None:
    """No prior key is renamed, removed or changed, and the version is unchanged."""
    # The payload version is deliberately not bumped this phase.
    assert TELEMETRY_VERSION == "20260628"

    gatherer = await build_anonymous_telemetry_gatherer()
    data = await gatherer.gather()
    dumped = data.model_dump(mode="json")

    # Nothing existing is renamed or removed; the only top-level additions are the two new blocks.
    assert set(dumped) == _PRE_FEATURE_DATA_FIELDS | {"server", "task_workers"}

    # `workers` is exactly as before.
    assert set(dumped["workers"]) == _PRE_FEATURE_WORKER_FIELDS
    assert isinstance(dumped["workers"]["total"], int)
    assert isinstance(dumped["workers"]["active"], int)

    # The new blocks follow the same total/active convention and add one worker's figures.
    for block in ("server", "task_workers"):
        assert set(dumped[block]) == _PRE_FEATURE_WORKER_FIELDS | {"per_worker"}
        assert set(dumped[block]["per_worker"]) == _RESOURCE_FIELDS

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

    # Two git_agent replicas, and one api_server container shared by two processes.
    git_reading = WorkerResourceReading(
        host="git-host-1",
        processor_available=4,
        processor_assigned=None,
        memory_total=8_000_000_000,
        memory_available=6_000_000_000,
    )
    _seed_active(cache, "git_agent", "w1")
    _seed_reading(cache, "git_agent", "w1", git_reading)
    _seed_active(cache, "git_agent", "w2")
    _seed_reading(cache, "git_agent", "w2", git_reading.model_copy(update={"host": "git-host-2"}))
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
    assert payload["task_workers"]["per_worker"] == {
        "processor_available": 4.0,
        "processor_assigned": None,
        "memory_total": 8_000_000_000,
        "memory_available": 6_000_000_000,
    }
    # The api_server container is split between its two processes.
    assert payload["server"]["per_worker"] == {
        "processor_available": 4.0,
        "processor_assigned": None,
        "memory_total": 8_000_000_000,
        "memory_available": 5_000_000_000,
    }

    # The test database leaves the Cypher parallel runtime's worker limit at its default.
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


async def test_a_worker_that_does_not_report_is_still_counted(resource_environment: MemoryCache) -> None:
    """An active worker that wrote no resource reading is counted, and the reporter's share is used."""
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

    assert (data.task_workers.total, data.task_workers.active) == (2, 2)
    assert data.task_workers.per_worker == TelemetryPerWorkerData(
        processor_available=4.0,
        processor_assigned=None,
        memory_total=8_000_000_000,
        memory_available=6_000_000_000,
    )


async def test_resources_key_does_not_change_worker_counts(resource_environment: MemoryCache) -> None:
    """Writing a per-process resource key for an existing identity leaves the census untouched.

    A running deployment writes both an active heartbeat and a resource reading for the
    same worker identity on every beat. The resource key must not be mistaken for a new
    worker: every block counts distinct identities, and reusing an identity for its
    resource reading adds none. Baseline the counts from active heartbeats
    alone, then add the resource keys for those same identities and confirm neither moves.
    """
    cache = resource_environment

    # Three worker identities announce themselves via active heartbeats only, exactly as
    # they did before per-process resource reporting existed.
    _seed_active(cache, "git_agent", "w1")
    _seed_active(cache, "git_agent", "w2")
    _seed_active(cache, "api_server", "w3")

    gatherer = await build_anonymous_telemetry_gatherer()
    baseline = await gatherer.gather()
    assert (baseline.workers.total, baseline.workers.active) == (3, 3)
    assert (baseline.task_workers.total, baseline.task_workers.active) == (2, 2)
    assert (baseline.server.total, baseline.server.active) == (1, 1)

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

    # The resource keys must not change any block's count.
    assert (after.workers.total, after.workers.active) == (3, 3)
    assert (after.task_workers.total, after.task_workers.active) == (2, 2)
    assert (after.server.total, after.server.active) == (1, 1)


@dataclass
class FailedSelfReadCase:
    name: str
    process_resources: ProcessResources
    expected_reading: WorkerResourceReading


FAILED_SELF_READ_CASES = [
    FailedSelfReadCase(
        name="the_empty_reading_keeps_the_container_name",
        process_resources=_AlwaysFailingProcessResources(),
        expected_reading=WorkerResourceReading(host="worker-container"),
    ),
    FailedSelfReadCase(
        name="a_container_name_that_cannot_be_read_is_stored_as_unknown",
        process_resources=_NamelessFailingProcessResources(),
        expected_reading=WorkerResourceReading(host="unknown"),
    ),
]


@pytest.mark.parametrize("case", FAILED_SELF_READ_CASES, ids=[case.name for case in FAILED_SELF_READ_CASES])
async def test_self_read_failure_after_retries_logs_and_writes_null(
    db: InfrahubDatabase,
    caplog: pytest.LogCaptureFixture,
    case: FailedSelfReadCase,
) -> None:
    """An exhausted self-read logs a warning with component + source, then writes a reading with no figures.

    A reader that raises on every attempt exhausts the bounded retries; the heartbeat
    must leave a traceable warning carrying the component and the failing source, then
    write a reading with no figures so a worker that stops reporting leaves a trace in the log.
    The reading keeps the container's name, so the process still counts as sharing its container.
    """
    cache = MemoryCache()
    component = InfrahubComponent(
        cache=cache,
        db=db,
        message_bus=BusSimulator(),
        component_type=ComponentType.GIT_AGENT,
        process_resources=case.process_resources,
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

    # After exhausted retries the heartbeat still writes a reading, with no figures.
    stored = cache.storage[f"workers:resources:git_agent:worker:{WORKER_IDENTITY}"]
    assert WorkerResourceReading.model_validate_json(stored) == case.expected_reading
