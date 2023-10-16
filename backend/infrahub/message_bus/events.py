from __future__ import annotations

import importlib
import pickle
from typing import TYPE_CHECKING, Any, Optional

from aio_pika import DeliveryMode, IncomingMessage, Message
from aio_pika.patterns.base import Base as PickleSerializer

import infrahub.config as config
from infrahub.exceptions import ProcessingError, ValidationError
from infrahub.utils import BaseEnum

from . import get_broker

if TYPE_CHECKING:
    from aio_pika.abc import AbstractExchange
    from typing_extensions import Self


# pylint: disable=arguments-differ


class MessageType(str, BaseEnum):
    DATA = "data"  # ACTIONS: create, update , delete
    """
    <type>.<branch_name>.node.<node_type>.<action>.<object_id>
    """
    SCHEMA = "schema"  # create, update, delete
    """
    <type>.<branch_name>.node.<node_type>.<action>.<object_id>
    """
    BRANCH = "branch"  # ACTIONS: create, rebase, merge, delete, pull_request
    """
    <type>.<branch_name>.<action>
    """
    GIT = "git"  # ACTIONS: pull, push, rebase, merge
    RPC_RESPONSE = "rpc-response"
    TRANSFORMATION = "transformation"  # jinja, python
    ARTIFACT = "artifact"

    # INTERNAL = "internal"   # cache


MESSAGE_MAPPING = {
    MessageType.DATA: "InfrahubDataMessage",
    MessageType.BRANCH: "InfrahubBranchMessage",
    MessageType.ARTIFACT: "InfrahubArtifactRPC",
    MessageType.RPC_RESPONSE: "InfrahubRPCResponse",
}


class DataMessageAction(str, BaseEnum):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"


class BranchMessageAction(str, BaseEnum):
    CREATE = "create"
    REBASE = "rebase"
    MERGE = "merge"
    DELETE = "delete"
    PULL_REQUEST = "pullrequest"


class GitMessageAction(str, BaseEnum):
    MERGE = "merge"
    DIFF = "diff"
    REPO_ADD = "repo-add"
    BRANCH_ADD = "branch-add"


class ArtifactMessageAction(str, BaseEnum):
    GENERATE = "generate"


class RPCStatusCode(int, BaseEnum):
    OK = 200
    CREATED = 201
    ACCEPTED = 202
    # Requester Errors
    BAD_REQUEST = 400
    UNAUTHORIZED = 401
    FORBIDDEN = 403
    NOT_FOUND = 404
    NOT_ALLOWED = 405
    REQUEST_TIMEOUT = 408
    CONFLICT = 409  # AKA Failed
    TOO_EARLY = 425
    # Worker Errors
    INTERNAL_ERROR = 500
    NOT_IMPLEMENTED = 501


class InfrahubMessage(PickleSerializer):
    """
    Generic Object to help send and receive message over the message Bus (RabbitMQ)
    """

    type = None
    request_id: Optional[str] = None

    SERIALIZER = pickle
    CONTENT_TYPE = "application/python-pickle"

    def __init__(self, *args, request_id: Optional[str] = None, **kwargs):  # pylint: disable=unused-argument
        self._message = None
        self.request_id = request_id

    @classmethod
    def convert(cls, message: IncomingMessage) -> Self:
        """
        Convert an IncomingMessage into its proper InfrahubMessage class
        """

        if message.type not in MessageType:
            raise TypeError(f"Message type not recognized : {message.type}")

        body = cls.deserialize(message.body)

        module = importlib.import_module(".", package=__name__)
        message_class = getattr(module, MESSAGE_MAPPING[message.type])

        return message_class.init(message=message, **body)

    @classmethod
    def init(cls, message: IncomingMessage, *args, **kwargs) -> Self:
        """Initialize an Message from an Incoming Message."""

        return cls(message=message, *args, **kwargs)

    @classmethod
    def serialize(cls, data: Any) -> bytes:
        """Serialize data to the bytes."""
        return cls.SERIALIZER.dumps(data)

    @classmethod
    def deserialize(cls, data: bytes) -> Any:
        """Deserialize data from bytes."""
        return cls.SERIALIZER.loads(data)

    def generate_message_body(self) -> dict:
        """Generate the body of the message as a dict."""
        body = {}
        if self.request_id:
            body["request_id"] = self.request_id
        return body

    def generate_message(self) -> Message:
        """Generate AMQP Message with body in JSON and store it in self._message."""

        self._message = Message(
            type=self.type.value,
            content_type=self.CONTENT_TYPE,
            body=self.serialize(self.generate_message_body()),
            delivery_mode=DeliveryMode.PERSISTENT,
        )

        return self._message

    @property
    def message(self) -> Message:
        """AMQP Message for this Message, generate it if not defined."""
        return self._message or self.generate_message()

    def __repr__(self) -> str:
        return f"[{self.type.value.upper()}]"


class InfrahubActionMessage(InfrahubMessage):
    """
    Generic Object to help send and receive message over the message Bus (RabbitMQ)
    """

    actions = None

    def __init__(self, action: str, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if not self.validate_action(action):
            raise ValidationError(f"{action} is not a valid action for {self.type} Message.")

        self.action = action

    @property
    def topic(self) -> str:
        """Name of the topic for this event, must be implemented for each type of Message."""
        raise NotImplementedError

    def validate_action(self, action: str) -> bool:
        """Validate if the action provided is valid for this event."""

        return action in self.actions

    def generate_message_body(self) -> dict:
        """Generate the body of the message as a dict."""

        body = super().generate_message_body()
        body["action"] = self.action

        return body

    def __repr__(self) -> str:
        return f"[{self.type.value.upper()}] {self.action}"

    async def send(self):
        """Send the Message to the Exchange."""
        exchange = await get_event_exchange()
        return await exchange.publish(self.message, routing_key=self.topic)


# --------------------------------------------------------
# RPC
# --------------------------------------------------------
class InfrahubRPC(InfrahubActionMessage):
    def __init__(
        self,
        message=None,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        if message:
            self.correlation_id = message.correlation_id
            self.reply_to = message.reply_to

    @property
    def topic(self) -> str:
        return f"{config.SETTINGS.broker.namespace}.rpcs"

    async def send(
        self,
        channel,
        correlation_id: str,
        reply_to: str,
    ):
        """Send the Message to the RPC Queue."""

        self.message.correlation_id = correlation_id
        self.message.reply_to = reply_to

        await channel.default_exchange.publish(self.message, routing_key=self.topic)


class InfrahubRPCResponse(InfrahubMessage):
    type = MessageType.RPC_RESPONSE

    def __init__(
        self,
        status: RPCStatusCode,
        response: Optional[dict] = None,
        errors: Optional[list] = None,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        self.status = status
        self.errors = errors
        self.response = response

    async def send(self, channel, correlation_id: str, reply_to: str):
        """Send the Response to the Queue specified."""

        self.message.correlation_id = correlation_id

        await channel.default_exchange.publish(self.message, routing_key=reply_to)

    def generate_message_body(self) -> dict:
        """Generate the body of the message as a dict."""

        body = super().generate_message_body()
        body["status"] = self.status
        body["response"] = self.response
        body["errors"] = self.errors
        return body

    def raise_for_status(self) -> None:
        if self.errors:
            raise ProcessingError("\n".join(self.errors))


async def get_event_exchange(channel=None) -> AbstractExchange:
    """Return the event exchange initialized as TOPIC."""
    if not channel:
        broker = await get_broker()
        channel = await broker.channel()

    exchange_name = f"{config.SETTINGS.broker.namespace}.events"
    return await channel.get_exchange(name=exchange_name)
