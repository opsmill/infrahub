from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass
from typing import TYPE_CHECKING, List

from infrahub import config
from infrahub.components import ComponentType
from infrahub.tasks.keepalive import refresh_heartbeat
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
        # Add some randomness to the interval to avoid having all workers pulling the latest update at the same time
        random_number = random.randint(30, 60)
        if self.service.component_type == ComponentType.API_SERVER:
            schedules = [
                Schedule(name="refresh_api_components", interval=10, function=refresh_heartbeat, start_delay=0),
                Schedule(
                    name="branch_refresh", interval=900, function=trigger_branch_refresh, start_delay=random_number
                ),
            ]
            self.schedules.extend(schedules)

            if config.SETTINGS.git.sync_interval:
                self.schedules.append(
                    Schedule(
                        name="resync_repositories",
                        interval=config.SETTINGS.git.sync_interval,
                        function=resync_repositories,
                    )
                )
        if self.service.component_type == ComponentType.GIT_AGENT:
            schedules = [
                Schedule(name="refresh_components", interval=10, function=refresh_heartbeat),
                Schedule(
                    name="branch_refresh", interval=900, function=trigger_branch_refresh, start_delay=random_number
                ),
            ]
            self.schedules.extend(schedules)

        await self.start_schedule()

    async def start_schedule(self) -> None:
        for schedule in self.schedules:
            asyncio.create_task(
                run_schedule(schedule=schedule, service=self.service), name=f"scheduled_task_{schedule.name}"
            )

    async def shutdown(self) -> None:
        self.running = False


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
            await schedule.function(service)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            service.log.error(str(exc))
        for _ in range(schedule.interval):
            if not service.scheduler.running:
                return
            await asyncio.sleep(delay=1)
