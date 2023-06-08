import aio_pika

import infrahub.config as config


class Broker:
    client: aio_pika.abc.AbstractRobustConnection = None


broker = Broker()


async def connect_to_broker():
    if not config.SETTINGS.broker.enable:
        return False

    broker.client = await aio_pika.connect_robust(
        host=config.SETTINGS.broker.address,
        login=config.SETTINGS.broker.username,
        password=config.SETTINGS.broker.password,
        port=config.SETTINGS.broker.service_port,
    )


async def close_broker_connection():
    if not config.SETTINGS.broker.enable:
        return False
    await broker.client.close()


async def get_broker() -> aio_pika.abc.AbstractRobustConnection:
    if not config.SETTINGS.broker.enable:
        return False
    if not broker.client:
        await connect_to_broker()

    return broker.client
