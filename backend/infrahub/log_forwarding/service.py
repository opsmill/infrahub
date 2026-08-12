from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from infrahub.events import InfrahubEvent
    from infrahub.exceptions import ForwardableError
    from infrahub.log_forwarding.models import LogForwardingContext, SyslogMessage


class LogForwardingService(ABC):
    """Abstract base for log forwarding."""

    @abstractmethod
    async def start(self) -> None:
        """Start consumer tasks for all destinations."""

    @abstractmethod
    def enqueue(self, message: SyslogMessage) -> None:
        """Add message to be forwarded to all destinations. Should not block."""

    @abstractmethod
    def forward_event(self, event: InfrahubEvent) -> None:
        """Convert an InfrahubEvent to a syslog message and enqueue it. Should not block."""

    @abstractmethod
    def forward_exception(self, exception: ForwardableError, context: LogForwardingContext) -> None:
        """Convert a ForwardableError to a syslog message and enqueue it. Should not block."""

    @abstractmethod
    async def shutdown(self) -> None:
        """Signal consumers to drain queues, then force close."""


class LogForwardingServiceCommunity(LogForwardingService):
    """No-op stub for community edition."""

    async def start(self) -> None:
        pass

    def enqueue(self, message: SyslogMessage) -> None:
        pass

    def forward_event(self, event: InfrahubEvent) -> None:
        pass

    def forward_exception(self, exception: ForwardableError, context: LogForwardingContext) -> None:
        pass

    async def shutdown(self) -> None:
        pass
