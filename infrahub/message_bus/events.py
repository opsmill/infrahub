from __future__ import annotations

import importlib
from re import A
from typing import Generator, Any, TYPE_CHECKING
from infrahub.exceptions import ValidationError

from infrahub.utils import BaseEnum

import json
from aio_pika import DeliveryMode, ExchangeType, Message, connect, IncomingMessage
from aio_pika.abc import AbstractRobustConnection, AbstractChannel, AbstractExchange

from fastapi import Depends

import infrahub.config as config

from . import get_broker

if TYPE_CHECKING:
    from infrahub.core.node import Node


class EventType(str, BaseEnum):
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

    # GIT = "git"             # pull
    # INTERNAL = "internal"   # cache


EVENT_MAPPING = {
    EventType.DATA: "DataEvent",
    EventType.SCHEMA: "SchemaEvent",
    EventType.BRANCH: "BranchEvent",
}


class DataEventAction(str, BaseEnum):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"


class SchemaEventAction(str, BaseEnum):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"


class BranchEventAction(str, BaseEnum):
    CREATE = "create"
    REBASE = "rebase"
    MERGE = "merge"
    DELETE = "delete"
    PULL_REQUEST = "pullrequest"


class Event:

    type = None
    actions = None

    def __init__(self, action: str):

        if not self.validate_action(action):
            raise ValidationError(f"{action} is not a valid action for {self.type} event.")

        self.action = action
        self._message = None

    @classmethod
    def init(cls, message: IncomingMessage) -> Event:

        if message.type not in EventType:
            raise TypeError(f"Message type not recognized : {message.type}")

        body = json.loads(message.body)

        module = importlib.import_module(".", package=__name__)
        event_class = getattr(module, EVENT_MAPPING[message.type])

        return event_class.init(body=body, message=message)

    def validate_action(self, action: str) -> bool:
        """Validate if the action provided is valid for this event."""

        return action in self.actions

    def generate_message_body(self) -> dict:
        """Generate the body of the message as a dict."""

        body = {"action": self.action}

        return body

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
    def topic(self) -> str:
        """Name of the topic for this event, must be implemented for each type of Event."""
        raise NotImplementedError

    @property
    def message(self) -> Message:
        """AMQP Message for this Event, generate it if not defined."""
        return self._message or self.generate_message()

    def __repr__(self) -> str:
        return f"[{self.type.value.upper()}] {self.action}"

    async def send(self):
        """Send the Event to the Exchange."""
        exchange = await get_event_exchange()
        return await exchange.publish(self.message, routing_key=self.topic)


class DataEvent(Event):

    type = EventType.DATA
    actions = DataEventAction

    def __init__(
        self, node: Node = None, node_id: str = None, node_kind: str = None, branch: str = None, *args, **kwargs
    ):

        super().__init__(*args, **kwargs)

        self.node_kind = node_kind or node.get_kind()
        self.node_id = node_id or node.id
        self.branch = branch or node._branch.name
        self._node = node

    @classmethod
    def init(cls, body: dict, message: IncomingMessage) -> DataEvent:
        """Initialize an Event from an Incoming Message and a body."""

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


class SchemaEvent(DataEvent):
    """Infrahub Event related to action on the Schema.

    topic format: schema.<branch_name>.node.<node_type>.<action>.<object_id>
    """

    type = EventType.SCHEMA
    actions = SchemaEventAction


class BranchEvent(Event):
    """Infrahub Event related to action on the branches.

    topic format: branch.<branch_name>.<action>
    """

    type = EventType.BRANCH
    actions = BranchEventAction

    def __init__(self, branch: str, *args, **kwargs):

        super().__init__(*args, **kwargs)
        self.branch = branch

    @classmethod
    def init(cls, body: dict, message: IncomingMessage) -> DataEvent:
        """Initialize an Event from an Incoming Message and a body."""

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


async def send_event(event: Event):
    """Task Wrapper to send an Event as a background task."""
    return await event.send()
