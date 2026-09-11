from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass
from typing import TYPE_CHECKING

from infrahub import config
from infrahub.components import ComponentType
from infrahub.log import get_logger
from infrahub.services.heartbeat import WorkerHeartbeat
from infrahub.tasks.recurring import trigger_branch_refresh

if TYPE_CHECKING:
    from infrahub.services import InfrahubServices, ServiceFunction

log = get_logger()

background_tasks: set[asyncio.Task[None]] = set()

HEARTBEAT_COMPONENT_TYPES = (ComponentType.API_SERVER, ComponentType.GIT_AGENT)
"""Process types that report liveness; a CLI or test process (``NONE``) does not."""


@dataclass
class Schedule:
    name: str
    interval: int
    function: ServiceFunction
    start_delay: int = 30


class InfrahubScheduler:
    """Run this process's recurring background work.

    Asyncio schedules run on the main event loop. The worker liveness heartbeat is the exception:
    it runs on the ``WorkerHeartbeat`` thread so a flow that blocks the main loop cannot make the
    worker look dead (see ``infrahub.services.heartbeat``). Both start and stop together.
    """

    # TODO we could remove service dependency by adding kwargs to Schedule instead of passing services
    service: InfrahubServices | None

    def __init__(self, component_type: ComponentType, heartbeat: WorkerHeartbeat | None = None) -> None:
        self.running: bool = False
        self.schedules: list[Schedule] = []
        self.heartbeat: WorkerHeartbeat | None = heartbeat

        self.running = config.SETTINGS.miscellaneous.start_background_runner
        # Add some randomness to the interval to avoid having all workers pulling the latest update at the same time
        random_number = random.randint(0, 5)
        if component_type in HEARTBEAT_COMPONENT_TYPES:
            self.heartbeat = heartbeat or WorkerHeartbeat(component_type=component_type)
            self.schedules.append(
                Schedule(
                    name="branch_refresh", interval=900, function=trigger_branch_refresh, start_delay=random_number
                )
            )

    async def start_schedule(self) -> None:
        if self.running and self.heartbeat is not None:
            self.heartbeat.start()
        for schedule in self.schedules:
            task = asyncio.create_task(self.run_schedule(schedule=schedule), name=f"scheduled_task_{schedule.name}")
            background_tasks.add(task)
            task.add_done_callback(background_tasks.discard)

    async def shutdown(self) -> None:
        self.running = False
        if self.heartbeat is not None:
            await asyncio.to_thread(self.heartbeat.stop)

    async def run_schedule(self, schedule: Schedule) -> None:
        """Execute the task provided in the schedule as per the defined interval.

        Once the service is marked to be shutdown the scheduler will stop executing tasks.

        Raises:
            ValueError: When the scheduler has not been initialized with a service instance.

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
