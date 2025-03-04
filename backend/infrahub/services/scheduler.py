from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass
from typing import TYPE_CHECKING

from infrahub import config
from infrahub.components import ComponentType
from infrahub.log import get_logger
from infrahub.tasks.keepalive import refresh_heartbeat
from infrahub.tasks.recurring import trigger_branch_refresh

if TYPE_CHECKING:
    from infrahub.services import InfrahubServices, ServiceFunction

log = get_logger()


@dataclass
class Schedule:
    name: str
    interval: int
    function: ServiceFunction
    start_delay: int = 30


class InfrahubScheduler:
    # TODO we could remove service dependency by adding kwargs to Schedule instead of passing services
    service: InfrahubServices | None

    def __init__(self, component_type: ComponentType) -> None:
        self.running: bool = False
        self.schedules: list[Schedule] = []

        self.running = config.SETTINGS.miscellaneous.start_background_runner
        # Add some randomness to the interval to avoid having all workers pulling the latest update at the same time
        random_number = random.randint(0, 5)
        if component_type == ComponentType.API_SERVER:
            schedules = [
                Schedule(name="refresh_api_components", interval=10, function=refresh_heartbeat, start_delay=0),
                Schedule(
                    name="branch_refresh", interval=900, function=trigger_branch_refresh, start_delay=random_number
                ),
            ]
            self.schedules.extend(schedules)

        if component_type == ComponentType.GIT_AGENT:
            schedules = [
                Schedule(name="refresh_components", interval=10, function=refresh_heartbeat),
                Schedule(
                    name="branch_refresh", interval=900, function=trigger_branch_refresh, start_delay=random_number
                ),
            ]
            self.schedules.extend(schedules)

    async def start_schedule(self) -> None:
        for schedule in self.schedules:
            asyncio.create_task(self.run_schedule(schedule=schedule), name=f"scheduled_task_{schedule.name}")

    async def shutdown(self) -> None:
        self.running = False

    async def run_schedule(self, schedule: Schedule) -> None:
        """Execute the task provided in the schedule as per the defined interval

        Once the service is marked to be shutdown the scheduler will stop executing tasks.
        """
        for _ in range(schedule.start_delay):
            if not self.running:
                return
            await asyncio.sleep(delay=1)

        if self.service is None:
            raise ValueError("InfrahubScheduler.service is None")

        self.service.log.info("Started recurring task", task=schedule.name)
        while self.running:
            try:
                await schedule.function(self.service)
            except Exception as exc:
                self.service.log.error(str(exc))
            for _ in range(schedule.interval):
                if not self.running:
                    return
                await asyncio.sleep(delay=1)
