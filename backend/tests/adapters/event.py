from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.services.adapters.event import InfrahubEventService

if TYPE_CHECKING:
    from infrahub.events import InfrahubEvent


class MemoryInfrahubEvent(InfrahubEventService):
    def __init__(self) -> None:
        self.events: list[InfrahubEvent] = []

    async def send(self, event: InfrahubEvent) -> None:
        self.events.append(event)
