from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass
from typing import TYPE_CHECKING, List

from infrahub import config
from infrahub.components import ComponentType
from infrahub.tasks.keepalive import refresh_api_server_components
from infrahub.tasks.recurring import resync_repositories, trigger_branch_refresh

if TYPE_CHECKING:
    from infrahub.services import InfrahubServices, ServiceFunction


@dataclass
class Schedule:
    name: str
    interval: int
    function: ServiceFunction
    start_delay: int = 30


class InfrahubScheduler:
    def __init__(self) -> None:
        self.service: InfrahubServices
        self.running: bool = False
        self.schedules: List[Schedule] = []

    async def initialize(self, service: InfrahubServices) -> None:
        self.service = service

        self.running = config.SETTINGS.miscellaneous.start_background_runner
        if self.service.component_type == ComponentType.API_SERVER:
            # Add some randomness to the interval to avoid having all workers pulling the latest update at the same time
            random_number = 30 + random.randint(1, 4) - 2

            schedules = [
                Schedule(name="refresh_api_components", interval=10, function=refresh_api_server_components),
                Schedule(name="resync_repositories", interval=10, function=resync_repositories),
                Schedule(
                    name="branch_refresh", interval=10, function=trigger_branch_refresh, start_delay=random_number
                ),
            ]
            self.schedules.extend(schedules)
        await self.start_schedule()

    async def start_schedule(self) -> None:
        for schedule in self.schedules:
            asyncio.create_task(
                run_schedule(schedule=schedule, service=self.service), name=f"scheduled_task_{schedule.name}"
            )


async def run_schedule(schedule: Schedule, service: InfrahubServices) -> None:
    """Execute the task provided in the schedule as per the defined interval

    Once the service is marked to be shutdown the scheduler will stop executing tasks.
    """
    for _ in range(schedule.start_delay):
        if not service.scheduler.running:
            return
        await asyncio.sleep(delay=1)

    service.log.info("Started recurring task", task=schedule.name)

    while service.scheduler.running:
        try:
            await schedule.function(service, schedule.interval)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            service.log.error(str(exc))
        for _ in range(schedule.interval):
            if not service.scheduler.running:
                return
            await asyncio.sleep(delay=1)
