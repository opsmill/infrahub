from __future__ import annotations

import asyncio
import time

from infrahub.components import ComponentType
from infrahub.services import InfrahubServices
from infrahub.services.heartbeat import WorkerHeartbeat
from infrahub.services.scheduler import InfrahubScheduler, Schedule
from infrahub.worker import WORKER_IDENTITY
from tests.adapters.cache import MemoryCache
from tests.adapters.log import FakeLogger


async def nothing_to_see(service: InfrahubServices) -> None:
    service.scheduler.running = False
    raise NotImplementedError("This function has not been implemented")


async def log_once_and_stop(service: InfrahubServices) -> None:
    service.log.info("Writing entry to the log")
    assert isinstance(service.log, FakeLogger)
    if len(service.log.info_logs) == 3:
        service.scheduler.running = False


async def test_scheduler_return_on_not_running(fake_log: FakeLogger) -> None:
    """The scheduler should return without writing entries to the log if it is not running."""
    service = await InfrahubServices.new(log=fake_log)
    schedule = Schedule(name="inactive", interval=10, start_delay=1, function=log_once_and_stop)
    await service.scheduler.run_schedule(schedule=schedule)

    assert len(fake_log.info_logs) == 0


async def test_scheduler_exit_after_first(fake_log: FakeLogger) -> None:
    """The scheduler should return without writing entries to the log if it is not running."""
    service = await InfrahubServices.new(log=fake_log)
    schedule = Schedule(name="inactive", interval=1, start_delay=1, function=log_once_and_stop)
    service.scheduler.running = True
    await service.scheduler.run_schedule(schedule=schedule)

    assert len(fake_log.info_logs) == 3
    assert fake_log.info_logs[0] == "Started recurring task"
    assert fake_log.info_logs[1] == "Writing entry to the log"
    assert fake_log.info_logs[2] == "Writing entry to the log"


async def test_scheduler_task_with_error(fake_log: FakeLogger) -> None:
    """The scheduler should return without writing entries to the log if it is not running."""
    service = await InfrahubServices.new(log=fake_log)
    schedule = Schedule(name="inactive", interval=1, start_delay=0, function=nothing_to_see)
    service.scheduler.running = True
    await service.scheduler.run_schedule(schedule=schedule)

    assert len(fake_log.info_logs) == 1
    assert len(fake_log.error_logs) == 1
    assert fake_log.info_logs[0] == "Started recurring task"
    assert fake_log.error_logs[0] == "This function has not been implemented"


async def test_scheduler_registers_a_heartbeat_thread_only_for_worker_processes() -> None:
    for component_type in (ComponentType.API_SERVER, ComponentType.GIT_AGENT):
        scheduler = InfrahubScheduler(component_type=component_type)
        assert scheduler.heartbeat is not None
        assert scheduler.heartbeat.component_type == component_type
        # The heartbeat no longer runs as an asyncio schedule on the main loop.
        assert [schedule.name for schedule in scheduler.schedules] == ["branch_refresh"]

    assert InfrahubScheduler(component_type=ComponentType.NONE).heartbeat is None


async def test_scheduler_starts_and_stops_the_heartbeat_thread() -> None:
    cache = MemoryCache()

    async def cache_factory() -> MemoryCache:
        return cache

    heartbeat = WorkerHeartbeat(
        component_type=ComponentType.GIT_AGENT, cache_factory=cache_factory, interval_seconds=0.05
    )
    scheduler = InfrahubScheduler(component_type=ComponentType.GIT_AGENT, heartbeat=heartbeat)
    scheduler.schedules = []
    scheduler.running = True

    await scheduler.start_schedule()
    try:
        deadline = time.monotonic() + 2
        while f"workers:active:git_agent:worker:{WORKER_IDENTITY}" not in cache.storage:
            assert time.monotonic() < deadline, "heartbeat thread did not write the active key"
            await asyncio.sleep(0.01)
        assert heartbeat.running
    finally:
        await scheduler.shutdown()

    assert not scheduler.running
    assert not heartbeat.running


async def test_scheduler_does_not_start_the_heartbeat_when_not_running() -> None:
    heartbeat = WorkerHeartbeat(component_type=ComponentType.GIT_AGENT, interval_seconds=0.05)
    scheduler = InfrahubScheduler(component_type=ComponentType.GIT_AGENT, heartbeat=heartbeat)
    scheduler.running = False

    await scheduler.start_schedule()

    assert not heartbeat.running
