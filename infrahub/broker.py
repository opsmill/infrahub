from typing import Generator

import aio_pika
from aio_pika import DeliveryMode, ExchangeType, Message, connect
from aio_pika.abc import AbstractRobustConnection, AbstractChannel, AbstractExchange

from fastapi import Depends

import infrahub.config as config


async def get_broker() -> Generator:

    connection = await aio_pika.connect_robust(
        host=config.SETTINGS.broker.address,
        login=config.SETTINGS.broker.username,
        password=config.SETTINGS.broker.password,
    )

    try:
        yield connection
    finally:
        await connection.close()


async def get_graph_exchange(broker: AbstractRobustConnection = Depends(get_broker)) -> Generator:

    channel = await broker.channel()
    exchange_name = f"{config.SETTINGS.broker.namespace}.graph"
    yield await channel.declare_exchange(exchange_name, ExchangeType.FANOUT)
