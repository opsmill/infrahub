from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from prefect.events import emit_event

if TYPE_CHECKING:
    from infrahub.events import InfrahubEvent
    from infrahub.services import InfrahubMessageBus


class InfrahubEventService:
    """Base class for infrahub event service"""

    def __init__(self, message_bus: InfrahubMessageBus | None = None) -> None:
        # Ideally message_bus should not be optional, we let it like this for existing tests that
        #  pass without a bus as corresponding tested events do not send bus messages.
        self.message_bus = message_bus

    async def send(self, event: InfrahubEvent) -> None:
        tasks = [self._send_bus(event=event), self._send_prefect(event=event)]
        await asyncio.gather(*tasks)

    async def _send_bus(self, event: InfrahubEvent) -> None:
        for message in event.get_messages():
            if self.message_bus is None:
                raise ValueError("InfrahubEventService.message_bus is None.")
            await self.message_bus.send(message=message)

    async def _send_prefect(self, event: InfrahubEvent) -> None:
        emit_event(
            id=event.meta.id,
            event=event.event_name,
            resource=event.get_resource(),
            related=event.get_related(),
            payload=event.get_event_payload(),
        )
