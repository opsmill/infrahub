from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from infrahub.log_forwarding.models import SyslogMessage


class LogForwardingService(ABC):
    """Abstract base for log forwarding"""

    @abstractmethod
    async def start(self) -> None:
        """Start consumer tasks for all destinations."""

    @abstractmethod
    def enqueue(self, message: SyslogMessage) -> None:
        """Add message to be forwarded to all destinations. Should not block."""

    @abstractmethod
    async def shutdown(self) -> None:
        """Signal consumers to drain queues, then force close."""


class LogForwardingServiceCommunity(LogForwardingService):
    """No-op stub for community edition"""

    async def start(self) -> None:
        pass

    def enqueue(self, message: SyslogMessage) -> None:
        pass

    async def shutdown(self) -> None:
        pass
