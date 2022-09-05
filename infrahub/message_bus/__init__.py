from typing import Generator

import aio_pika

import infrahub.config as config


class Broker:
    client: aio_pika.abc.AbstractRobustConnection = None


broker = Broker()


async def connect_to_broker():
    # print("In get_broker()")
    broker.client = await aio_pika.connect_robust(
        host=config.SETTINGS.broker.address,
        login=config.SETTINGS.broker.username,
        password=config.SETTINGS.broker.password,
    )


async def close_broker_connection():
    await broker.client.close()


async def get_broker() -> aio_pika.abc.AbstractRobustConnection:
    if not broker.client:
        await connect_to_broker()

    return broker.client
