from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Optional

from prefect.events import emit_event

if TYPE_CHECKING:
    from infrahub.events import InfrahubEvent
    from infrahub.services import InfrahubMessageBus


class InfrahubEventService:
    """Base class for infrahub event service"""

    def __init__(self, message_bus: Optional[InfrahubMessageBus] = None) -> None:
        # TODO message_bus should not be optional, we let it like this for existing tests that
        #  pass without a bus as event send do not have bus messages
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
            event=event.get_name(),
            resource=event.get_resource(),
            related=event.get_related(),
            payload=event.get_payload(),
        )
