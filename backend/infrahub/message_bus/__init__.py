from typing import Iterator

import aio_pika
import aiormq
from pydantic import BaseModel

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


class InfrahubBaseMessage(BaseModel, aio_pika.abc.AbstractMessage):
    """Base Model for messages"""

    def info(self) -> aio_pika.abc.MessageInfo:
        raise NotImplementedError

    @property
    def body(self) -> bytes:
        return self.json().encode("UTF-8")

    @property
    def locked(self) -> bool:
        raise NotImplementedError

    @property
    def properties(self) -> aiormq.spec.Basic.Properties:
        return aiormq.spec.Basic.Properties(content_type="application/json", content_encoding="utf-8")

    def __iter__(self) -> Iterator[int]:
        raise NotImplementedError

    def lock(self) -> None:
        raise NotImplementedError

    def __copy__(self) -> aio_pika.Message:
        return aio_pika.Message(body=self.body, content_type="application/json", content_encoding="utf-8")
