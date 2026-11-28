from __future__ import annotations

import asyncio
import importlib
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any, TypeVar

from infrahub_sdk.uuidt import UUIDT

from infrahub.exceptions import WorkerTimeoutError
from infrahub.log import get_log_data, get_logger
from infrahub.message_bus import Meta
from infrahub.message_bus.messages import ROUTING_KEY_MAP

ResponseClass = TypeVar("ResponseClass")

if TYPE_CHECKING:
    from collections.abc import MutableMapping

    from infrahub.components import ComponentType
    from infrahub.config import BrokerDriver, BrokerSettings
    from infrahub.message_bus import InfrahubMessage, InfrahubResponse
    from infrahub.message_bus.types import MessageTTL

MessageListener = Callable[[str, bytes], Awaitable[None]]


async def add_request_id(message: InfrahubMessage) -> None:
    """Copy the request id of the current log context into the message metadata."""
    message.meta.request_id = get_log_data().get("request_id", "")


def topic_matches(topic: str, routing_key: str) -> bool:
    """Tell whether a routing key matches an AMQP topic pattern, where `*` is one word and `#` any number of words."""
    return _words_match(topic.split("."), routing_key.split("."))


def _words_match(pattern: list[str], words: list[str]) -> bool:
    if not pattern:
        return not words
    head, *rest = pattern
    if head == "#":
        return any(_words_match(rest, words[index:]) for index in range(len(words) + 1))
    return bool(words) and head in {"*", words[0]} and _words_match(rest, words[1:])


class InfrahubMessageBus(ABC):
    DELIVER_TIMEOUT: int = 30 * 60  # 30 minutes
    worker_bindings: list[str] = [
        "check.*.*",
        "event.*.*",
        "finalize.*.*",
        "git.*.*",
        "refresh.webhook.*",
        "request.*.*",
        "send.*.*",
        "schema.*.*",
        "transform.*.*",
        "trigger.*.*",
    ]
    event_bindings: list[str] = ["refresh.registry.*", "refresh.settings.*"]
    broadcasted_event_bindings: list[str] = ["refresh.git.*"]

    # Set by the drivers that send RPC requests over a broker.
    settings: BrokerSettings
    loop: asyncio.AbstractEventLoop
    futures: MutableMapping[str, asyncio.Future]

    async def shutdown(self) -> None:  # noqa: B027 We want a default empty behavior, so it's ok to have an empty non-abstract method.
        """Shutdown the Message bus."""

    @classmethod
    async def new(cls, component_type: ComponentType, settings: BrokerSettings | None = None) -> InfrahubMessageBus:
        raise NotImplementedError()

    @classmethod
    async def new_from_driver(
        cls, component_type: ComponentType, driver: BrokerDriver, settings: BrokerSettings | None = None
    ) -> InfrahubMessageBus:
        """Imports and initializes the correct class based on the supplied driver.

        This is to ensure that we only import the Python modules that we actually
        need to operate and not import all possible options.
        """
        module = importlib.import_module(driver.driver_module_path)
        broker_driver: InfrahubMessageBus = getattr(module, driver.driver_class_name)
        return await broker_driver.new(component_type=component_type, settings=settings)

    @abstractmethod
    async def publish(
        self, message: InfrahubMessage, routing_key: str, delay: MessageTTL | None = None, is_retry: bool = False
    ) -> None:
        raise NotImplementedError()

    @abstractmethod
    async def reply(self, message: InfrahubMessage, routing_key: str) -> None:
        raise NotImplementedError()

    @abstractmethod
    async def rpc(
        self,
        message: InfrahubMessage,
        response_class: type[ResponseClass],
        timeout: float | None = None,  # noqa: ASYNC109 part of the published bus contract
    ) -> ResponseClass:
        """Send a message and wait for its reply, for `timeout` seconds or the configured default when None.

        Raises:
            WorkerTimeoutError: When no worker answered in time. An implementation that replies
                in-process never waits and so never raises it.

        """
        raise NotImplementedError()

    async def listen(self, topic: str, listener: MessageListener) -> None:
        """Pass the routing key and body of every published message matching the AMQP `topic` to `listener`.

        Returns once listening has started; the listener keeps being called until the bus shuts down.
        """
        raise NotImplementedError()

    async def _publish_and_await_reply(self, message: InfrahubMessage, reply_to: str, timeout: float | None) -> Any:  # noqa: ASYNC109
        """Publish an RPC request and return its reply, waiting `timeout` seconds or the configured RPC timeout.

        Raises:
            WorkerTimeoutError: When no worker answered in time.
            TimeoutError: When publishing raises one before the bound expires.

        """
        correlation_id = str(UUIDT())
        bound = timeout if timeout is not None else self.settings.rpc_timeout
        routing_key = ROUTING_KEY_MAP.get(type(message), "")

        future = self.loop.create_future()
        self.futures[correlation_id] = future
        request_id = get_log_data().get("request_id", "")
        message.meta = Meta(request_id=request_id, correlation_id=correlation_id, reply_to=reply_to)

        # The publish sits inside the bound because a broker can withhold its publish confirmation indefinitely.
        published = False
        try:
            # Built inside the try so every failure after the future was registered reaches cleanup.
            bounded_call = asyncio.timeout(bound)
            async with bounded_call:
                await self.send(message=message)
                published = True
                return await future
        except TimeoutError as exc:
            if not bounded_call.expired():
                # A broker error that happens to be a TimeoutError is not our bound elapsing.
                raise
            get_logger().warning(
                "No worker answered within the allowed time",
                correlation_id=correlation_id,
                routing_key=routing_key,
                timeout_seconds=bound,
                stage="awaiting_reply" if published else "publishing",
            )
            raise WorkerTimeoutError(operation=routing_key, timeout_seconds=bound) from exc
        finally:
            self.futures.pop(correlation_id, None)

    async def send(self, message: InfrahubMessage, delay: MessageTTL | None = None, is_retry: bool = False) -> None:
        routing_key = ROUTING_KEY_MAP.get(type(message))
        if not routing_key:
            raise ValueError("Unable to determine routing key")
        await self.publish(message, routing_key=routing_key, delay=delay, is_retry=is_retry)

    # TODO rename it
    async def reply_if_initiator_meta(self, message: InfrahubResponse, initiator: InfrahubMessage) -> None:
        if initiator.meta:
            message.meta.correlation_id = initiator.meta.correlation_id
            routing_key = initiator.meta.reply_to or ""
            await self.reply(message, routing_key=routing_key)
