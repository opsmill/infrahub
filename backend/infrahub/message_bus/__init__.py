from typing import Iterator, Optional, TypeVar

import aio_pika
import aiormq
from pydantic import BaseModel, Field

from infrahub import config
from infrahub.exceptions import Error, RPCError
from infrahub.log import set_log_data
from infrahub.message_bus.responses import RESPONSE_MAP

ResponseClass = TypeVar("ResponseClass")


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


class Meta(BaseModel):
    request_id: str = ""
    correlation_id: Optional[str] = None
    reply_to: Optional[str] = None
    initiator_id: Optional[str] = Field(None, description="The worker identity of the initial sender of this message")


class InfrahubBaseMessage(BaseModel, aio_pika.abc.AbstractMessage):
    """Base Model for messages"""

    meta: Optional[Meta] = None

    def assign_meta(self, parent: "InfrahubBaseMessage") -> None:
        """Assign relevant meta properties from a parent message."""
        self.meta = self.meta or Meta()
        if parent.meta:
            self.meta.request_id = parent.meta.request_id
            self.meta.initiator_id = parent.meta.initiator_id

    def set_log_data(self, routing_key: str) -> None:
        set_log_data(key="routing_key", value=routing_key)
        if self.meta:
            if self.meta.request_id:
                set_log_data(key="request_id", value=self.meta.request_id)

    def info(self) -> aio_pika.abc.MessageInfo:
        raise NotImplementedError

    @property
    def reply_requested(self) -> bool:
        if self.meta and self.meta.reply_to:
            return True
        return False

    @property
    def body(self) -> bytes:
        return self.json(exclude_none=True).encode("UTF-8")

    @property
    def locked(self) -> bool:
        raise NotImplementedError

    @property
    def properties(self) -> aiormq.spec.Basic.Properties:
        correlation_id = None
        if self.meta:
            correlation_id = self.meta.correlation_id
        return aiormq.spec.Basic.Properties(
            content_type="application/json", content_encoding="utf-8", correlation_id=correlation_id
        )

    def __iter__(self) -> Iterator[int]:
        raise NotImplementedError

    def lock(self) -> None:
        raise NotImplementedError

    def __copy__(self) -> aio_pika.Message:
        correlation_id = None
        if self.meta:
            correlation_id = self.meta.correlation_id
        return aio_pika.Message(
            body=self.body, content_type="application/json", content_encoding="utf-8", correlation_id=correlation_id
        )


class InfrahubResponse(InfrahubBaseMessage):
    """A response to an RPC request"""

    passed: bool = True
    response_class: str
    response_data: dict

    def raise_for_status(self) -> None:
        if self.passed:
            return

        # Later we would load information about the error based on the response_class and response_data
        raise RPCError(message=self.response_data.get("error", "Unknown Error"))

    def parse(self, response_class: type[ResponseClass]) -> ResponseClass:
        self.raise_for_status()
        if self.response_class not in RESPONSE_MAP:
            raise Error(f"Unable to find response_class: {self.response_class}")

        if not isinstance(response_class, type(RESPONSE_MAP[self.response_class])):
            raise Error(f"Invalid response class for response message: {self.response_class}")

        return RESPONSE_MAP[self.response_class](**self.response_data)
