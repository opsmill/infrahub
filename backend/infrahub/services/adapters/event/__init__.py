from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from prefect.events import emit_event

from infrahub.exceptions import InitializationError

if TYPE_CHECKING:
    from infrahub.events import InfrahubEvent
    from infrahub.services import InfrahubServices


class InfrahubEventService:
    """Base class for infrahub event service"""

    def __init__(self) -> None:
        self._service: InfrahubServices | None = None

    @property
    def service(self) -> InfrahubServices:
        if not self._service:
            raise InitializationError("Event is not initialized with a service")

        return self._service

    async def initialize(self, service: InfrahubServices) -> None:
        """Initialize the event service"""
        self._service = service

    async def send(self, event: InfrahubEvent) -> None:
        tasks = [self._send_bus(event=event), self._send_prefect(event=event)]
        await asyncio.gather(*tasks)

    async def _send_bus(self, event: InfrahubEvent) -> None:
        for message in event.get_messages():
            await self.service.send(message=message)

    async def _send_prefect(self, event: InfrahubEvent) -> None:
        emit_event(
            event=event.get_name(),
            resource=event.get_resource(),
            related=event.get_related(),
            payload=event.get_payload(),
        )
