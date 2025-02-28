from __future__ import annotations

import asyncio
import ssl
from typing import TYPE_CHECKING, Awaitable, Callable, MutableMapping, TypeVar

import nats
import ujson
from infrahub_sdk.uuidt import UUIDT
from opentelemetry import context, propagate, trace
from opentelemetry.instrumentation.utils import is_instrumentation_enabled

from infrahub import config
from infrahub.components import ComponentType
from infrahub.log import clear_log_context, get_log_data
from infrahub.message_bus import InfrahubMessage, Meta, messages
from infrahub.message_bus.operations import execute_message
from infrahub.services.adapters.message_bus import InfrahubMessageBus
from infrahub.worker import WORKER_IDENTITY

if TYPE_CHECKING:
    from infrahub.config import BrokerSettings
    from infrahub.message_bus.types import MessageTTL
    from infrahub.services import InfrahubServices

MessageFunction = Callable[[InfrahubMessage], Awaitable[None]]
ResponseClass = TypeVar("ResponseClass")


async def _add_request_id(message: InfrahubMessage) -> None:
    log_data = get_log_data()
    message.meta.request_id = log_data.get("request_id", "")


class NATSMessageBus(InfrahubMessageBus):
    def __init__(self, component_type: ComponentType, settings: BrokerSettings | None = None) -> None:
        self.settings = settings or config.SETTINGS.broker

        self.service: InfrahubServices
        self.connection: nats.NATS
        self.jetstream: nats.js.JetStreamContext
        self.callback_queue: nats.js.api.StreamInfo
        self.events_queue: nats.js.api.StreamInfo
        self.message_enrichers: list[MessageFunction] = []

        self.loop = asyncio.get_running_loop()
        self.futures: MutableMapping[str, asyncio.Future] = {}

        self.component_type: ComponentType = component_type

    @classmethod
    async def new(cls, component_type: ComponentType, settings: BrokerSettings | None = None) -> NATSMessageBus:
        message_bus = cls(component_type=component_type, settings=settings)
        await message_bus._initialize()
        return message_bus

    async def _initialize(self) -> None:
        tls_context = None
        if self.settings.tls_enabled:
            tls_context = ssl.create_default_context(purpose=ssl.Purpose.SERVER_AUTH)
            if self.settings.tls_ca_file:
                tls_context.load_verify_locations(cafile=self.settings.tls_ca_file)
            if self.settings.tls_insecure:
                tls_context.check_hostname = False
                tls_context.verify_mode = ssl.CERT_NONE

        self.connection = await nats.connect(
            f"nats://{self.settings.address}:{self.settings.service_port}",
            user=self.settings.username,
            password=self.settings.password,
            tls=tls_context,
        )

        self.jetstream = self.connection.jetstream()

        if self.component_type == ComponentType.API_SERVER:
            await self._initialize_api_server()
        elif self.component_type == ComponentType.GIT_AGENT:
            await self._initialize_git_worker()

    async def shutdown(self) -> None:
        await self.connection.drain()

    async def on_callback(self, message: nats.aio.msg.Msg) -> None:
        if is_instrumentation_enabled() and message.headers:
            ctx = propagate.extract(message.headers)
            token = context.attach(ctx)

        try:
            with trace.get_tracer(__name__).start_as_current_span("on_callback") as span:
                span.set_attribute("routing_key", message.subject)

                if message.headers and "correlation_id" in message.headers:
                    span.set_attribute("correlation_id", message.headers["correlation_id"])
                    future: asyncio.Future = self.futures.pop(message.headers["correlation_id"])

                    if future:
                        future.set_result(message)
                        return

                clear_log_context()
                if message.subject in messages.MESSAGE_MAP:
                    await execute_message(routing_key=message.subject, message_body=message.data, service=self.service)
                else:
                    self.service.log.error("Invalid message received", message=f"{message!r}")
        finally:
            if is_instrumentation_enabled() and message.headers:
                context.detach(token)

    async def on_message(self, message: nats.aio.msg.Msg) -> None:
        if is_instrumentation_enabled() and message.headers:
            ctx = propagate.extract(message.headers)
            token = context.attach(ctx)

        try:
            with trace.get_tracer(__name__).start_as_current_span("on_message") as span:
                span.set_attribute("routing_key", message.subject)

                clear_log_context()
                if message.subject in messages.MESSAGE_MAP:
                    delay = await execute_message(
                        routing_key=message.subject, message_body=message.data, service=self.service
                    )
                    if delay:
                        return await message.nak(delay / 1000)
                else:
                    self.service.log.error("Invalid message received", message=f"{message!r}")

                return await message.ack()
        finally:
            if is_instrumentation_enabled() and message.headers:
                context.detach(token)

    async def _subscribe_events(self, events: list[str], identity: str) -> None:
        for subject in events:
            await self.jetstream.subscribe(
                subject=subject,
                stream=f"{self.settings.namespace}-events",
                config=nats.js.api.ConsumerConfig(ack_policy=nats.js.api.AckPolicy.NONE, description=identity),
                cb=self.on_callback,
            )

    async def _setup_callback(self, identity: str) -> None:
        self.callback_queue = await self.jetstream.add_stream(
            name=f"{self.settings.namespace}-callback-{WORKER_IDENTITY}",
            retention=nats.js.api.RetentionPolicy.LIMITS,
        )

        await self.jetstream.subscribe(
            subject="*",
            stream=f"{self.settings.namespace}-callback-{WORKER_IDENTITY}",
            cb=self.on_callback,
            config=nats.js.api.ConsumerConfig(ack_policy=nats.js.api.AckPolicy.NONE, description=identity),
        )

    async def _initialize_api_server(self) -> None:
        self.events_queue = await self.jetstream.add_stream(
            name=f"{self.settings.namespace}-events",
            subjects=self.event_bindings,
            retention=nats.js.api.RetentionPolicy.INTEREST,
        )

        await self.jetstream.add_stream(
            name=f"{self.settings.namespace}-rpcs",
            subjects=self.worker_bindings,
            retention=nats.js.api.RetentionPolicy.WORK_QUEUE,
        )

        await self._subscribe_events(self.event_bindings, f"api-worker-{WORKER_IDENTITY}")

        await self._setup_callback(f"api-worker-{WORKER_IDENTITY}")

        self.message_enrichers.append(_add_request_id)

    async def _initialize_git_worker(self) -> None:
        bindings = self.event_bindings + self.broadcasted_event_bindings
        await self._subscribe_events(bindings, f"git-worker-{WORKER_IDENTITY}")

        consumer_config = nats.js.api.ConsumerConfig(
            ack_policy=nats.js.api.AckPolicy.EXPLICIT,
            max_deliver=self.settings.maximum_message_retries,
            ack_wait=self.DELIVER_TIMEOUT,
            # Does not work as expected, must switch to pull-based consumer...
            # max_ack_pending=self.settings.maximum_concurrent_messages,
            # flow_control=True,
            # idle_heartbeat=5.0,  # default value
            filter_subjects=bindings,
            durable_name="git-workers",
            deliver_group="git-workers",
            deliver_subject=self.connection.new_inbox(),
        )

        try:
            await self.jetstream.add_consumer(stream=f"{self.settings.namespace}-rpcs", config=consumer_config)
        except nats.js.errors.BadRequestError as exc:
            if exc.err_code != 10013:  # consumer name already in use
                raise

        for subject in bindings:
            await self.jetstream.subscribe(
                subject=subject,
                queue="git-workers",
                stream=f"{self.settings.namespace}-rpcs",
                config=consumer_config,
                cb=self.on_message,
                manual_ack=True,
            )

        await self._setup_callback(f"git-worker-{WORKER_IDENTITY}")

    async def _publish_with_delay(self, message: InfrahubMessage, routing_key: str, delay: MessageTTL) -> None:
        await asyncio.sleep(delay.value / 1000)
        await self.publish(message, routing_key)

    async def publish(
        self, message: InfrahubMessage, routing_key: str, delay: MessageTTL | None = None, is_retry: bool = False
    ) -> None:
        with trace.get_tracer(__name__).start_as_current_span("publish_message") as span:
            span.set_attribute("routing_key", routing_key)

            if delay:
                if is_retry:
                    # Delayed retries are directly handled in the callback using Nack
                    return
                # Use asyncio task for delayed publish since NATS does not support that out of the box
                asyncio.create_task(self._publish_with_delay(message, routing_key, delay))
                return

            for enricher in self.message_enrichers:
                await enricher(message)
            message.assign_priority(priority=messages.message_priority(routing_key=routing_key))

            headers = {}
            if message.meta.correlation_id:
                headers["correlation_id"] = message.meta.correlation_id
            if message.meta.reply_to:
                headers["reply_to"] = message.meta.reply_to
            if message.meta.expiration:
                headers["expiration"] = str(message.meta.expiration)

            if message.meta.headers:
                # Filter None and non-string values
                for k, v in message.meta.headers.items():
                    if v:
                        headers[k] = str(v)

            if is_instrumentation_enabled():
                propagate.inject(headers)

            await self.jetstream.publish(
                subject=routing_key,
                payload=message.body,
                headers=headers,  # None value throws exception
            )

    async def reply(self, message: InfrahubMessage, routing_key: str) -> None:
        headers = {}
        if message.meta.correlation_id:
            headers["correlation_id"] = message.meta.correlation_id
        if message.meta.reply_to:
            headers["reply_to"] = message.meta.reply_to
        if message.meta.expiration:
            headers["expiration"] = str(message.meta.expiration)
        if message.meta.headers:
            # Filter None and non-string values
            for k, v in message.meta.headers.items():
                if v:
                    headers[k] = str(v)

        if is_instrumentation_enabled():
            propagate.inject(headers)

        await self.jetstream.publish(
            subject=routing_key,
            payload=message.body,
            headers=headers,
        )

    async def rpc(self, message: InfrahubMessage, response_class: type[ResponseClass]) -> ResponseClass:
        correlation_id = str(UUIDT())

        future = self.loop.create_future()
        self.futures[correlation_id] = future

        log_data = get_log_data()
        request_id = log_data.get("request_id", "")
        message.meta = Meta(
            request_id=request_id, correlation_id=correlation_id, reply_to=self.callback_queue.config.name
        )

        await self.service.message_bus.send(message=message)

        response: nats.aio.msg.Msg = await future
        data = ujson.loads(response.data)
        return response_class(**data)
