from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, List, MutableMapping

from infrahub.services import services

if TYPE_CHECKING:
    from aio_pika.abc import (
        AbstractExchange,
    )

    from . import InfrahubMessage


class InfrahubRpcClientBase:
    exchange: AbstractExchange

    def __init__(self) -> None:
        self.futures: MutableMapping[str, asyncio.Future] = {}
        self.loop = asyncio.get_running_loop()

    async def send(self, message: InfrahubMessage) -> None:
        await services.send(message=message)


class InfrahubRpcClient(InfrahubRpcClientBase):
    pass


class InfrahubRpcClientTesting(InfrahubRpcClientBase):
    """InfrahubRPCClient instrumented for testing and mocking."""

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)

        self.sent: List[InfrahubMessage] = []

    async def send(self, message: InfrahubMessage) -> None:
        self.sent.append(message)
