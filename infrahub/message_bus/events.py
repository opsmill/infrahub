from __future__ import annotations

import importlib

from typing import Generator, TYPE_CHECKING
from infrahub.exceptions import ValidationError

from infrahub.utils import BaseEnum

import json
from aio_pika import DeliveryMode, ExchangeType, Message, IncomingMessage

import infrahub.config as config

from . import get_broker

if TYPE_CHECKING:
    from infrahub.core.node import Node
    from infrahub.core.repository import Repository


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
    """
    <type>.<repository_id>.<action>
    """
    RPC_RESPONSE = "rpc-response"
    # INTERNAL = "internal"   # cache


EVENT_MAPPING = {
    MessageType.DATA: "InfrahubDataMessage",
    MessageType.SCHEMA: "InfrahubSchemaMessage",
    MessageType.BRANCH: "InfrahubBranchMessage",
    MessageType.GIT: "InfrahubGitRPC",
    MessageType.RPC_RESPONSE: "InfrahubRPCResponse",
}


class DataMessageAction(str, BaseEnum):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"


class SchemaMessageAction(str, BaseEnum):
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
    CREATE = "create"
    PULL = "pull"
    PUSH = "push"
    REBASE = "rebase"
    MERGE = "merge"


class InfrahubMessage:
    """
    Generic Object to help send and receive message over the message Bus (RabbitMQ)
    """

    type = None

    def __init__(self, *args, **kwargs):

        self._message = None

    @classmethod
    def init(cls, message: IncomingMessage) -> InfrahubMessage:

        if message.type not in MessageType:
            raise TypeError(f"Message type not recognized : {message.type}")

        body = json.loads(message.body)

        module = importlib.import_module(".", package=__name__)
        message_class = getattr(module, EVENT_MAPPING[message.type])

        return message_class.init(body=body, message=message)

    def generate_message_body(self) -> dict:
        """Generate the body of the message as a dict."""

        return {}

    def generate_message(self) -> Message:
        """Generate AMQP Message with body in JSON and store it in self._message."""

        self._message = Message(
            type=self.type.value,
            content_type="application/json",
            body=json.dumps(self.generate_message_body()).encode(),
            delivery_mode=DeliveryMode.PERSISTENT,
        )

        return self._message

    @property
    def message(self) -> Message:
        """AMQP Message for this Message, generate it if not defined."""
        return self._message or self.generate_message()

    def __repr__(self) -> str:
        return f"[{self.type.value.upper()}]"

    async def send(self):
        """Send the Message to the Exchange."""
        exchange = await get_event_exchange()
        return await exchange.publish(self.message, routing_key=self.topic)


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
        status: bool,
        # message: str = None,
        context: dict = None,
        *args,
        **kwargs,
    ):

        super().__init__(*args, **kwargs)

        self.status = status
        # self.message = message
        self.context = context

    @classmethod
    def init(cls, body: dict, message: IncomingMessage) -> InfrahubRPCResponse:
        """Initialize an Message from an Incoming Message and a body."""

        status = body.get("status")
        context = body.get("context", None)

        return cls(message=message, status=status, context=context)

    async def send(self, channel, correlation_id: str, reply_to: str):
        """Send the Response to the Queue specified."""

        self.message.correlation_id = correlation_id

        await channel.default_exchange.publish(self.message, routing_key=reply_to)

    def generate_message_body(self) -> dict:
        """Generate the body of the message as a dict."""

        body = super().generate_message_body()
        body["status"] = self.status
        body["context"] = self.context

        return body


class InfrahubGitRPC(InfrahubRPC):

    type = MessageType.GIT
    actions = GitMessageAction

    def __init__(
        self,
        branch_name: str = None,
        repository: Repository = None,
        repository_id: str = None,
        source_branch_name: str = None,
        *args,
        **kwargs,
    ):

        if not repository and not repository_id:
            raise ValueError("Either Repository or repository_id must be provided for InfrahubGitRPC.")

        super().__init__(*args, **kwargs)

        self.repository = repository
        self.repository_id = repository_id
        if repository and not repository_id:
            self.repository_id = repository.id

        self.branch_name = branch_name
        self.source_branch_name = source_branch_name

    @classmethod
    def init(cls, body: dict, message: IncomingMessage) -> InfrahubGitRPC:
        """Initialize an Message from an Incoming Message and a body."""

        action = body.get("action")
        repository_id = body.get("repository_id")
        branch_name = body.get("branch_name", None)
        source_branch_name = body.get("source_branch_name", None)

        return cls(
            action=action,
            message=message,
            repository_id=repository_id,
            branch_name=branch_name,
            source_branch_name=source_branch_name,
        )

    def generate_message_body(self) -> dict:
        """Generate the body of the message as a dict."""

        body = super().generate_message_body()
        body["repository_id"] = self.repository_id
        body["branch_name"] = self.branch_name
        body["source_branch_name"] = self.source_branch_name

        return body


# --------------------------------------------------------
# Events
# --------------------------------------------------------
class InfrahubDataMessage(InfrahubActionMessage):

    type = MessageType.DATA
    actions = DataMessageAction

    def __init__(
        self, node: Node = None, node_id: str = None, node_kind: str = None, branch: str = None, *args, **kwargs
    ):

        super().__init__(*args, **kwargs)

        self.node_kind = node_kind or node.get_kind()
        self.node_id = node_id or node.id
        self.branch = branch or node._branch.name
        self._node = node

    @classmethod
    def init(cls, body: dict, message: IncomingMessage) -> InfrahubDataMessage:
        """Initialize an Message from an Incoming Message and a body."""

        action = body.get("action")
        branch = body.get("branch")
        node_id = body.get("node", {}).get("id")
        node_kind = body.get("node", {}).get("kind")

        return cls(action=action, branch=branch, node_id=node_id, node_kind=node_kind)

    def __repr__(self) -> str:
        return f"[{self.type.value.upper()}] branch: {self.branch} | {self.action} | {self.node_kind} | {self.node_id} "

    @property
    def topic(self):
        """name of the topic for this event."""
        return f"{self.type}.{self.branch}.node.{self.node_kind}.{self.action}.{self.node_id}"

    def generate_message_body(self) -> dict:
        """Generate the body of the message as a dict."""

        body = super().generate_message_body()
        body["branch"] = self.branch
        body["node"] = {"kind": self.node_kind, "id": self.node_id}

        return body


class SchemaMessage(InfrahubDataMessage):
    """Infrahub Message related to action on the Schema.

    topic format: schema.<branch_name>.node.<node_type>.<action>.<object_id>
    """

    type = MessageType.SCHEMA
    actions = SchemaMessageAction


class InfrahubBranchMessage(InfrahubActionMessage):
    """Infrahub Message related to action on the branches.

    topic format: branch.<branch_name>.<action>
    """

    type = MessageType.BRANCH
    actions = BranchMessageAction

    def __init__(self, branch: str, *args, **kwargs):

        super().__init__(*args, **kwargs)
        self.branch = branch

    @classmethod
    def init(cls, body: dict, message: IncomingMessage) -> InfrahubBranchMessage:
        """Initialize an Message from an Incoming Message and a body."""

        action = body.get("action")
        branch = body.get("branch")

        return cls(action=action, branch=branch)

    @property
    def topic(self) -> str:
        """name of the topic for this event."""
        return f"{self.type}.{self.branch}.{self.action}"

    def generate_message_body(self) -> dict:
        """Generate the body of the message as a dict."""
        body = super().generate_message_body()
        body["branch"] = self.branch

        return body


async def get_event_exchange(channel=None) -> Generator:
    """Return the event exchange initialized as TOPIC."""
    if not channel:
        broker = await get_broker()
        channel = await broker.channel()

    exchange_name = f"{config.SETTINGS.broker.namespace}.events"
    return await channel.declare_exchange(exchange_name, ExchangeType.TOPIC)


async def send_event(msg: Message):
    """Task Wrapper to send a message as a background task."""
    return await msg.send()
