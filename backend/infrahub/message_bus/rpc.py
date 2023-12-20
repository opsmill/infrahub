from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, List, MutableMapping

from infrahub.log import get_log_data, get_logger

from . import InfrahubMessage, Meta
from .messages import ROUTING_KEY_MAP

if TYPE_CHECKING:
    from aio_pika.abc import (
        AbstractExchange,
    )

log = get_logger()


class InfrahubRpcClientBase:
    exchange: AbstractExchange

    def __init__(self) -> None:
        self.futures: MutableMapping[str, asyncio.Future] = {}
        self.loop = asyncio.get_running_loop()

    async def send(self, message: InfrahubMessage) -> None:
        routing_key = ROUTING_KEY_MAP.get(type(message))

        if not routing_key:
            raise ValueError("Unable to determine routing key")

        log_data = get_log_data()
        request_id = log_data.get("request_id", "")
        message.meta = message.meta or Meta(request_id=request_id)
        await self.exchange.publish(message, routing_key=routing_key)


class InfrahubRpcClient(InfrahubRpcClientBase):
    pass


class InfrahubRpcClientTesting(InfrahubRpcClientBase):
    """InfrahubRPCClient instrumented for testing and mocking."""

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)

        self.sent: List[InfrahubMessage] = []

    async def send(self, message: InfrahubMessage) -> None:
        self.sent.append(message)
