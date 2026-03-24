from __future__ import annotations

from infrahub.services import InfrahubServices
from infrahub.services.scheduler import Schedule
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
