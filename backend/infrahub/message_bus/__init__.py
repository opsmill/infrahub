from __future__ import annotations

from typing import Any, Dict, Optional, TypeVar
from uuid import uuid4

import aio_pika
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
    correlation_id: Optional[str] = Field(default=None)
    reply_to: Optional[str] = Field(default=None)
    initiator_id: Optional[str] = Field(
        default=None, description="The worker identity of the initial sender of this message"
    )
    retry_count: Optional[int] = Field(
        default=None, description="Indicates how many times this message has been retried."
    )
    headers: Optional[Dict[str, Any]] = Field(default=None)
    validator_execution_id: Optional[str] = Field(
        default=None, description="Validator execution ID related to this message"
    )
    check_execution_id: Optional[str] = Field(default=None, description="Check execution ID related to this message")
    priority: int = Field(default=3, description="Message Priority")
    expiration: Optional[int] = Field(default=None, description="TTL before this message expires in seconds")
    task_id: Optional[str] = Field(default=None, description="Assigned task ID if applicable")

    @classmethod
    def default(cls) -> Meta:
        return cls()


class InfrahubMessage(BaseModel):
    """Base Model for messages"""

    meta: Meta = Field(default_factory=Meta.default, description="Meta properties for the message")

    def assign_meta(self, parent: "InfrahubMessage") -> None:
        """Assign relevant meta properties from a parent message."""
        self.meta.request_id = parent.meta.request_id
        self.meta.initiator_id = parent.meta.initiator_id

    def assign_header(self, key: str, value: Any) -> None:
        self.meta.headers = self.meta.headers or {}
        self.meta.headers[key] = value

    def assign_priority(self, priority: int) -> None:
        self.meta.priority = priority

    def assign_task_id(self) -> None:
        self.meta.task_id = str(uuid4())

    def assign_expiration(self, expiration: int) -> None:
        self.meta.expiration = expiration

    def set_log_data(self, routing_key: str) -> None:
        set_log_data(key="routing_key", value=routing_key)
        if self.meta.request_id:
            set_log_data(key="request_id", value=self.meta.request_id)
        if self.meta.task_id:
            set_log_data(key="task_id", value=self.meta.request_id)

    @property
    def reply_requested(self) -> bool:
        if self.meta.reply_to:
            return True
        return False

    @property
    def body(self) -> bytes:
        return self.model_dump_json(
            exclude={"meta": {"headers", "priority", "expiration"}, "value": True}, exclude_none=True
        ).encode("UTF-8")

    def increase_retry_count(self, count: int = 1) -> None:
        current_retry = self.meta.retry_count or 0
        self.meta.retry_count = current_retry + count

    @property
    def reached_max_retries(self) -> bool:
        if self.meta and self.meta.retry_count:
            return self.meta.retry_count >= config.SETTINGS.broker.maximum_message_retries
        return False


class InfrahubResponse(InfrahubMessage):
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
