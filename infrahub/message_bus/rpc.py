from __future__ import annotations

import asyncio
import uuid
from collections import defaultdict
from typing import Any, MutableMapping

from aio_pika.abc import (
    AbstractChannel,
    AbstractIncomingMessage,
    AbstractQueue,
    AbstractRobustConnection,
)

from . import get_broker
from .events import InfrahubMessage, InfrahubRPC, InfrahubRPCResponse, MessageType


class InfrahubRpcClientBase:
    connection: AbstractRobustConnection
    channel: AbstractChannel
    callback_queue: AbstractQueue
    loop: asyncio.AbstractEventLoop

    def __init__(self) -> None:
        self.futures: MutableMapping[str, asyncio.Future] = {}
        self.loop = asyncio.get_running_loop()

    async def connect(self) -> InfrahubRpcClient:
        self.connection = await get_broker()

        if not self.connection:
            return self

        self.channel = await self.connection.channel()
        self.callback_queue = await self.channel.declare_queue(exclusive=True)
        await self.callback_queue.consume(self.on_response)

        return self

    def on_response(self, message: AbstractIncomingMessage) -> None:
        if message.correlation_id is None:
            print(f"Bad message {message!r}")
            return

        future: asyncio.Future = self.futures.pop(message.correlation_id)

        if future:
            future.set_result(InfrahubMessage.convert(message))

    async def call(self, message: InfrahubRPC, wait_for_response: bool = True) -> Any:
        correlation_id = str(uuid.uuid4())

        if wait_for_response:
            future = self.loop.create_future()
            self.futures[correlation_id] = future
        else:
            self.futures[correlation_id] = None

        await message.send(channel=self.channel, correlation_id=correlation_id, reply_to=self.callback_queue.name)

        if wait_for_response:
            return await future


class InfrahubRpcClient(InfrahubRpcClientBase):
    pass


class InfrahubRpcClientTesting(InfrahubRpcClientBase):
    """InfrahubRPCClient instrumented for testing and mocking."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.responses = defaultdict(list)

    async def connect(self) -> InfrahubRpcClient:
        return self

    async def call(self, message: InfrahubRPC, wait_for_response: bool = True) -> Any:
        if len(self.responses[(message.type, message.action)]) == 0:
            raise IndexError(f"No more RPC message in store for '{message.type}::{message.action}'")

        if (message.type, message.action) in self.responses:
            return self.responses[(message.type, message.action)].pop(0)

        raise NotImplementedError(f"Unable to find an RPC message for '{message.type}::{message.action}'")

    async def add_response(self, response: InfrahubRPCResponse, message_type: MessageType, action: Any):
        """Register a predefined response for a given message_type and action."""

        self.responses[(message_type.value, action.value)].append(response)

    async def ensure_all_responses_have_been_delivered(self) -> bool:
        for key, messages in self.responses.items():
            if len(messages) != 0:
                raise Exception(f"Some responses for {key}, haven't been delivered.")

        return True
