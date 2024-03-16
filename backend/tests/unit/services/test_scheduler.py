from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.services import InfrahubServices
from infrahub.services.scheduler import InfrahubScheduler, Schedule, run_schedule

if TYPE_CHECKING:
    from tests.adapters.log import FakeLogger


async def nothing_to_see(service: InfrahubServices) -> None:
    service.scheduler.running = False
    raise NotImplementedError("This function has not been implemented")


async def log_once_and_stop(service: InfrahubServices) -> None:
    service.log.info("Writing entry to the log")
    if len(service.log.info_logs) == 3:
        service.scheduler.running = False


async def test_scheduler_return_on_not_running(fake_log: FakeLogger):
    """The scheduler should return without writing entries to the log if it is not running."""
    schedule_manager = InfrahubScheduler()
    schedule_manager.running = False
    service = InfrahubServices(log=fake_log)
    service.scheduler = schedule_manager
    schedule = Schedule(name="inactive", interval=10, start_delay=1, function=log_once_and_stop)
    await run_schedule(schedule=schedule, service=service)

    assert len(fake_log.info_logs) == 0


async def test_scheduler_exit_after_first(fake_log: FakeLogger):
    """The scheduler should return without writing entries to the log if it is not running."""

    schedule_manager = InfrahubScheduler()
    schedule_manager.running = True
    service = InfrahubServices(log=fake_log)
    service.scheduler = schedule_manager
    schedule = Schedule(name="inactive", interval=1, start_delay=1, function=log_once_and_stop)
    await run_schedule(schedule=schedule, service=service)

    assert len(fake_log.info_logs) == 3
    assert fake_log.info_logs[0] == "Started recurring task"
    assert fake_log.info_logs[1] == "Writing entry to the log"
    assert fake_log.info_logs[2] == "Writing entry to the log"


async def test_scheduler_task_with_error(fake_log: FakeLogger):
    """The scheduler should return without writing entries to the log if it is not running."""
    schedule_manager = InfrahubScheduler()
    schedule_manager.running = True
    service = InfrahubServices(log=fake_log)
    service.scheduler = schedule_manager
    schedule = Schedule(name="inactive", interval=1, start_delay=0, function=nothing_to_see)
    await run_schedule(schedule=schedule, service=service)

    assert len(fake_log.info_logs) == 1
    assert len(fake_log.error_logs) == 1
    assert fake_log.info_logs[0] == "Started recurring task"
    assert fake_log.error_logs[0] == "This function has not been implemented"
