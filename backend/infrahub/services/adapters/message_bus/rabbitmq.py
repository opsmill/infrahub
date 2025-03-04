from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Awaitable, Callable, MutableMapping, TypeVar

import aio_pika
import opentelemetry.instrumentation.aio_pika.span_builder
import ujson
from infrahub_sdk.uuidt import UUIDT
from opentelemetry.instrumentation.aio_pika import AioPikaInstrumentor
from opentelemetry.semconv.trace import SpanAttributes

from infrahub import config
from infrahub.components import ComponentType
from infrahub.log import clear_log_context, get_log_data
from infrahub.message_bus import InfrahubMessage, Meta, messages
from infrahub.message_bus.operations import execute_message
from infrahub.message_bus.types import MessageTTL
from infrahub.services.adapters.message_bus import InfrahubMessageBus
from infrahub.worker import WORKER_IDENTITY

if TYPE_CHECKING:
    from aio_pika.abc import (
        AbstractChannel,
        AbstractExchange,
        AbstractIncomingMessage,
        AbstractQueue,
        AbstractRobustConnection,
    )
    from opentelemetry.instrumentation.aio_pika.span_builder import SpanBuilder

    from infrahub.config import BrokerSettings
    from infrahub.services import InfrahubServices

MessageFunction = Callable[[InfrahubMessage], Awaitable[None]]
ResponseClass = TypeVar("ResponseClass")


AioPikaInstrumentor().instrument()


# TODO: remove this once https://github.com/open-telemetry/opentelemetry-python-contrib/issues/1835 is resolved
def patch_spanbuilder_set_channel() -> None:
    """
    The default SpanBuilder.set_channel does not work with aio_pika 9.1 and the refactored connection
    attribute
    """

    def set_channel(self: SpanBuilder, channel: AbstractChannel) -> None:
        if hasattr(channel, "_connection"):
            url = channel._connection.url
            self._attributes.update(
                {
                    SpanAttributes.NET_PEER_NAME: url.host,
                    SpanAttributes.NET_PEER_PORT: url.port,
                }
            )

    opentelemetry.instrumentation.aio_pika.span_builder.SpanBuilder.set_channel = set_channel  # type: ignore


async def _add_request_id(message: InfrahubMessage) -> None:
    log_data = get_log_data()
    message.meta.request_id = log_data.get("request_id", "")


class RabbitMQMessageBus(InfrahubMessageBus):
    def __init__(
        self, component_type: ComponentType = ComponentType.NONE, settings: BrokerSettings | None = None
    ) -> None:
        self.settings = settings or config.SETTINGS.broker
        self.channel: AbstractChannel
        self.exchange: AbstractExchange
        self.delayed_exchange: AbstractExchange
        self.service: InfrahubServices  # Needed because we inject `service` while sending messages.
        self.connection: AbstractRobustConnection
        self.callback_queue: AbstractQueue
        self.events_queue: AbstractQueue
        self.dlx: AbstractExchange
        self.message_enrichers: list[MessageFunction] = []

        self.loop = asyncio.get_running_loop()
        self.futures: MutableMapping[str, asyncio.Future] = {}

        self.component_type: ComponentType = component_type

    @classmethod
    async def new(cls, component_type: ComponentType, settings: BrokerSettings | None = None) -> RabbitMQMessageBus:
        message_bus = cls(component_type=component_type, settings=settings)
        await message_bus._initialize()
        return message_bus

    async def _initialize(self) -> None:
        patch_spanbuilder_set_channel()

        self.connection = await aio_pika.connect_robust(
            host=self.settings.address,
            login=self.settings.username,
            password=self.settings.password,
            port=self.settings.service_port,
            virtualhost=self.settings.virtualhost,
            ssl=self.settings.tls_enabled,
            ssl_options={
                "no_verify_ssl": int(self.settings.tls_insecure),
                "cafile": self.settings.tls_ca_file or "",
            },
        )
        self.connection.reconnect_callbacks.add(self.on_reconnect, weak=False)

        await self._initialize_connection()

    async def _initialize_connection(self) -> None:
        self.channel = await self.connection.channel()

        if self.component_type == ComponentType.API_SERVER:
            await self._initialize_api_server()
        elif self.component_type == ComponentType.GIT_AGENT:
            await self._initialize_git_worker()

    async def shutdown(self) -> None:
        await self.connection.close()

    async def on_callback(self, message: AbstractIncomingMessage) -> None:
        if message.correlation_id:
            future: asyncio.Future = self.futures.pop(message.correlation_id)

            if future:
                future.set_result(message)
                return

        clear_log_context()
        if message.routing_key in messages.MESSAGE_MAP:
            await execute_message(routing_key=message.routing_key, message_body=message.body, service=self.service)
        else:
            self.service.log.error("Invalid message received", message=f"{message!r}")

    async def on_message(self, message: AbstractIncomingMessage) -> None:
        async with message.process():
            clear_log_context()
            if message.routing_key in messages.MESSAGE_MAP:
                await execute_message(routing_key=message.routing_key, message_body=message.body, service=self.service)
            else:
                self.service.log.error("Invalid message received", message=f"{message!r}")

    async def on_reconnect(
        self,
        weak: bool = False,  # noqa: ARG002
    ) -> None:
        self.service.log.info("Reconnected to RabbitMQ, reinitializing connection")
        await self._initialize_connection()

    async def _initialize_api_server(self) -> None:
        self.callback_queue = await self.channel.declare_queue(name=f"api-callback-{WORKER_IDENTITY}", exclusive=True)
        self.events_queue = await self.channel.declare_queue(name=f"api-events-{WORKER_IDENTITY}", exclusive=True)

        await self.callback_queue.consume(self.on_callback, no_ack=True)
        await self.events_queue.consume(self.on_callback, no_ack=True)
        self.exchange = await self.channel.declare_exchange(
            f"{self.settings.namespace}.events", type="topic", durable=True
        )
        self.dlx = await self.channel.declare_exchange(f"{self.settings.namespace}.dlx", type="topic", durable=True)

        queue = await self.channel.declare_queue(
            f"{self.settings.namespace}.rpcs",
            durable=True,
            arguments={"x-max-priority": 5},
        )

        self.delayed_exchange = await self.channel.declare_exchange(
            f"{self.settings.namespace}.delayed", type="headers", durable=True
        )
        for routing_key in self.worker_bindings:
            await queue.bind(self.exchange, routing_key=routing_key)
            await queue.bind(self.dlx, routing_key=routing_key)

        for ttl in MessageTTL.variations():
            ttl_queue = await self.channel.declare_queue(
                f"{self.settings.namespace}.delay.{ttl.name.lower()}_seconds",
                durable=True,
                arguments={
                    "x-dead-letter-exchange": self.dlx.name,
                    "x-message-ttl": ttl.value,
                    "x-max-priority": 5,
                },
            )
            await ttl_queue.bind(
                self.delayed_exchange,
                arguments={"x-match": "all", "delay": ttl.value},
            )

        for routing_key in self.event_bindings:
            await self.events_queue.bind(self.exchange, routing_key=routing_key)

        self.message_enrichers.append(_add_request_id)

    async def _initialize_git_worker(self) -> None:
        bindings = self.event_bindings + self.broadcasted_event_bindings
        events_queue = await self.channel.declare_queue(name=f"worker-events-{WORKER_IDENTITY}", exclusive=True)

        self.exchange = await self.channel.declare_exchange(
            f"{self.settings.namespace}.events", type="topic", durable=True
        )

        for routing_key in bindings:
            await events_queue.bind(self.exchange, routing_key=routing_key)
        self.delayed_exchange = await self.channel.get_exchange(name=f"{self.settings.namespace}.delayed")

        await events_queue.consume(callback=self.on_callback, no_ack=True)
        self.callback_queue = await self.channel.declare_queue(
            name=f"worker-callback-{WORKER_IDENTITY}", exclusive=True
        )
        await self.callback_queue.consume(self.on_callback, no_ack=True)

        message_channel = await self.connection.channel()
        await message_channel.set_qos(prefetch_count=self.settings.maximum_concurrent_messages)

        queue = await message_channel.get_queue(f"{self.settings.namespace}.rpcs")
        await queue.consume(callback=self.on_message, no_ack=False)

    async def publish(
        self,
        message: InfrahubMessage,
        routing_key: str,
        delay: MessageTTL | None = None,
        is_retry: bool = False,  # noqa: ARG002
    ) -> None:
        for enricher in self.message_enrichers:
            await enricher(message)
        message.assign_priority(priority=messages.message_priority(routing_key=routing_key))
        if delay:
            message.assign_header(key="delay", value=delay.value)
            await self.delayed_exchange.publish(self.format_message(message=message), routing_key=routing_key)
        else:
            await self.exchange.publish(self.format_message(message=message), routing_key=routing_key)

    async def reply(self, message: InfrahubMessage, routing_key: str) -> None:
        await self.channel.default_exchange.publish(self.format_message(message=message), routing_key=routing_key)

    async def rpc(self, message: InfrahubMessage, response_class: type[ResponseClass]) -> ResponseClass:
        correlation_id = str(UUIDT())

        future = self.loop.create_future()
        self.futures[correlation_id] = future

        log_data = get_log_data()
        request_id = log_data.get("request_id", "")
        message.meta = Meta(request_id=request_id, correlation_id=correlation_id, reply_to=self.callback_queue.name)

        await self.service.message_bus.send(message=message)

        response: AbstractIncomingMessage = await future
        data = ujson.loads(response.body)
        return response_class(**data)

    @staticmethod
    def format_message(message: InfrahubMessage) -> aio_pika.Message:
        pika_message = aio_pika.Message(
            body=message.body,
            content_type="application/json",
            content_encoding="utf-8",
            correlation_id=message.meta.correlation_id,
            reply_to=message.meta.reply_to,
            priority=message.meta.priority,
            headers=message.meta.headers,
            expiration=message.meta.expiration,
        )
        return pika_message
