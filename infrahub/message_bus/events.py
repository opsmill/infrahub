from typing import Generator, Any

from enum import Enum

import json
from aio_pika import DeliveryMode, ExchangeType, Message, connect
from aio_pika.abc import AbstractRobustConnection, AbstractChannel, AbstractExchange

from fastapi import Depends

import infrahub.config as config

from . import get_broker

class EventType(Enum):
    DATA = "data"           # create, update , delete
    BRANCH = "branch"       # create, rebase, merge, delete, pull_request
    SCHEMA = "schema"       # create, update, delete
    GIT = "git"             # pull
    INTERNAL = "internal"   # cache

class Event(Message):
    pass
    # CONTENT_TYPE = "application/json"

    # def serialize(self, data: Any) -> bytes:
    #     return json.dumps(data)

    # def deserialize(self, data: bytes) -> bytes:
    #     return json.loads(data)

async def get_event_exchange(channel = None) -> Generator:

    if not channel:
        broker = await get_broker()
        channel = await broker.channel()

    exchange_name = f"{config.SETTINGS.broker.namespace}.events"
    return await channel.declare_exchange(exchange_name, ExchangeType.FANOUT)

async def send_event(event_type, body: str, routing_key = None, branch = None):

    exchange = await get_event_exchange()

    message = Event(
        type=event_type,
        # content_type="application/json",
        body={"message": body},
        delivery_mode=DeliveryMode.PERSISTENT,
    )

    await exchange.publish(message, routing_key=config.SETTINGS.broker.namespace)

