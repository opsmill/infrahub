from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from prefect.events import emit_event

if TYPE_CHECKING:
    from infrahub.events import InfrahubEvent
    from infrahub.log_forwarding.service import LogForwardingService
    from infrahub.services.adapters.message_bus import InfrahubMessageBus

logger = logging.getLogger(__name__)


class InfrahubEventService:
    """Base class for infrahub event service"""

    def __init__(
        self,
        message_bus: InfrahubMessageBus | None = None,
        log_forwarding: LogForwardingService | None = None,
    ) -> None:
        # Ideally message_bus should not be optional, we let it like this for existing tests that
        #  pass without a bus as corresponding tested events do not send bus messages.
        self.message_bus = message_bus
        self.log_forwarding = log_forwarding

    async def send(self, event: InfrahubEvent) -> None:
        tasks = [self._send_bus(event=event), self._send_prefect(event=event)]
        await asyncio.gather(*tasks)
        self._send_log_forwarding(event=event)

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

    def _send_log_forwarding(self, event: InfrahubEvent) -> None:
        """Forward an event to the log forwarding service."""
        if self.log_forwarding is None:
            return

        try:
            self.log_forwarding.forward_event(event)
        except Exception:
            logger.warning("Failed to forward event for log forwarding", exc_info=True)
