from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from infrahub.components import ComponentType
    from infrahub.events import InfrahubEvent


class EventExportService(ABC):
    """Abstract base for exporting every sent event to external systems."""

    @abstractmethod
    async def start(self, component_type: ComponentType) -> None:
        """Start background work; `component_type` tells the implementation which process it runs in."""

    @abstractmethod
    async def capture(self, event: InfrahubEvent) -> None:
        """Record the event for export."""

    @abstractmethod
    async def shutdown(self) -> None:
        """Stop background work and release connections."""


class EventExportServiceCommunity(EventExportService):
    """No-op stub for community edition."""

    async def start(self, component_type: ComponentType) -> None:
        pass

    async def capture(self, event: InfrahubEvent) -> None:
        pass

    async def shutdown(self) -> None:
        pass
