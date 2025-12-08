from __future__ import annotations

import asyncio
import contextlib
from typing import TYPE_CHECKING, Awaitable, Callable, MutableMapping, TypeVar

import redis.asyncio as redis
import ujson
from infrahub_sdk.uuidt import UUIDT
from opentelemetry import context, propagate, trace
from opentelemetry.instrumentation.utils import is_instrumentation_enabled

from infrahub import config
from infrahub.components import ComponentType
from infrahub.log import clear_log_context, get_log_data, get_logger
from infrahub.message_bus import InfrahubMessage, Meta, messages
from infrahub.message_bus.operations import execute_message
from infrahub.services.adapters.message_bus import InfrahubMessageBus
from infrahub.worker import WORKER_IDENTITY

if TYPE_CHECKING:
    from infrahub.config import BrokerSettings
    from infrahub.message_bus.types import MessageTTL

MessageFunction = Callable[[InfrahubMessage], Awaitable[None]]
ResponseClass = TypeVar("ResponseClass")

publish_tasks: set[asyncio.Task] = set()


async def _add_request_id(message: InfrahubMessage) -> None:
    """Add request ID to message metadata from log context."""
    log_data = get_log_data()
    message.meta.request_id = log_data.get("request_id", "")


class RedisMessageBus(InfrahubMessageBus):
    """Message bus implementation using Redis Streams.

    This implementation uses Redis Streams for message queuing with consumer groups
    for reliable message delivery and processing.
    """

    # Stream and consumer group names
    EVENTS_STREAM = "events"
    RPCS_STREAM = "rpcs"
    CALLBACK_STREAM_PREFIX = "callback"
    CONSUMER_GROUP = "workers"

    def __init__(self, component_type: ComponentType, settings: BrokerSettings | None = None) -> None:
        self.settings = settings or config.SETTINGS.broker
        self.connection: redis.Redis
        self.callback_stream: str
        self.events_stream: str
        self.rpcs_stream: str
        self.message_enrichers: list[MessageFunction] = []

        self.loop = asyncio.get_running_loop()
        self.futures: MutableMapping[str, asyncio.Future] = {}

        self.component_type: ComponentType = component_type
        self._consumer_tasks: list[asyncio.Task] = []
        self._shutdown_event: asyncio.Event = asyncio.Event()

    @classmethod
    async def new(cls, component_type: ComponentType, settings: BrokerSettings | None = None) -> RedisMessageBus:
        """Create and initialize a new RedisMessageBus instance.

        Args:
            component_type: The type of component (API_SERVER, GIT_AGENT, etc.)
            settings: Optional broker settings. Falls back to global config if not provided.

        Returns:
            An initialized RedisMessageBus instance.

        """
        message_bus = cls(component_type=component_type, settings=settings)
        await message_bus._initialize()
        return message_bus

    async def _initialize(self) -> None:
        """Initialize Redis connection and streams."""
        ssl_context = None
        if self.settings.tls_enabled:
            import ssl

            ssl_context = ssl.create_default_context(purpose=ssl.Purpose.SERVER_AUTH)
            if self.settings.tls_ca_file:
                ssl_context.load_verify_locations(cafile=self.settings.tls_ca_file)
            if self.settings.tls_insecure:
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE

        self.connection = redis.Redis(
            host=self.settings.address,
            port=self.settings.service_port,
            username=self.settings.username or None,
            password=self.settings.password or None,
            ssl=ssl_context if self.settings.tls_enabled else False,
            decode_responses=False,  # We handle decoding ourselves for binary data
        )

        # Set up stream names with namespace
        self.events_stream = f"{self.settings.namespace}:{self.EVENTS_STREAM}"
        self.rpcs_stream = f"{self.settings.namespace}:{self.RPCS_STREAM}"
        self.callback_stream = f"{self.settings.namespace}:{self.CALLBACK_STREAM_PREFIX}:{WORKER_IDENTITY}"

        if self.component_type == ComponentType.API_SERVER:
            await self._initialize_api_server()
        elif self.component_type == ComponentType.GIT_AGENT:
            await self._initialize_git_worker()

    async def shutdown(self) -> None:
        """Shutdown the message bus and clean up resources."""
        self._shutdown_event.set()

        # Cancel consumer tasks
        for task in self._consumer_tasks:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

        # Clean up callback stream
        with contextlib.suppress(redis.RedisError):
            await self.connection.delete(self.callback_stream)

        await self.connection.aclose()

    async def _create_stream_and_group(self, stream: str, group: str) -> None:
        """Create a stream and consumer group if they don't exist.

        Args:
            stream: The stream name to create.
            group: The consumer group name to create.

        Raises:
            ResponseError: If group creation fails for any reason other than the group already existing.

        """
        try:
            # Create stream with a dummy entry if it doesn't exist, then delete it
            await self.connection.xgroup_create(stream, group, id="0", mkstream=True)
        except redis.ResponseError as exc:
            if "BUSYGROUP" not in str(exc):
                raise

    async def _consume_stream(
        self,
        stream: str,
        group: str | None,
        consumer: str,
        callback: Callable[[dict], Awaitable[None]],
        ack_messages: bool = True,
    ) -> None:
        """Consume messages from a Redis stream.

        Args:
            stream: The stream name to consume from.
            group: The consumer group name (None for direct stream reads).
            consumer: The consumer name.
            callback: Async callback function to process messages.
            ack_messages: Whether to acknowledge messages after processing.

        """
        last_id = ">" if group else "$"

        while not self._shutdown_event.is_set():
            try:
                entries, last_id = await self._read_stream_entries(stream, group, consumer, last_id)
                if not entries:
                    continue

                await self._process_stream_entries(entries, stream, group, callback, ack_messages)

            except asyncio.CancelledError:
                break
            except redis.RedisError:
                get_logger().exception("Redis error in consumer")
                await asyncio.sleep(1)  # Back off on errors

    async def _read_stream_entries(
        self, stream: str, group: str | None, consumer: str, last_id: str
    ) -> tuple[list, str]:
        """Read entries from a Redis stream.

        Args:
            stream: The stream name to read from.
            group: The consumer group name (None for direct reads).
            consumer: The consumer name.
            last_id: The last message ID read.

        Returns:
            A tuple of (entries list, updated last_id).

        """
        if group:
            entries = await self.connection.xreadgroup(
                groupname=group,
                consumername=consumer,
                streams={stream: last_id},
                count=1,
                block=1000,
            )
        else:
            entries = await self.connection.xread(
                streams={stream: last_id},
                count=1,
                block=1000,
            )
            if entries:
                last_id = entries[0][1][-1][0]

        return entries or [], last_id

    async def _process_stream_entries(
        self,
        entries: list,
        stream: str,
        group: str | None,
        callback: Callable[[dict], Awaitable[None]],
        ack_messages: bool,
    ) -> None:
        """Process entries from a Redis stream.

        Args:
            entries: List of stream entries to process.
            stream: The stream name.
            group: The consumer group name.
            callback: Async callback function to process messages.
            ack_messages: Whether to acknowledge messages after processing.

        """
        for _stream_name, stream_entries in entries:
            for message_id, message_data in stream_entries:
                await self._process_single_message(message_id, message_data, stream, group, callback, ack_messages)

    async def _process_single_message(
        self,
        message_id: bytes,
        message_data: dict,
        stream: str,
        group: str | None,
        callback: Callable[[dict], Awaitable[None]],
        ack_messages: bool,
    ) -> None:
        """Process a single message from a stream.

        Args:
            message_id: The message ID.
            message_data: The message data.
            stream: The stream name.
            group: The consumer group name.
            callback: Async callback function.
            ack_messages: Whether to acknowledge the message.

        """
        try:
            await callback(message_data)
            if ack_messages and group:
                await self.connection.xack(stream, group, message_id)
        except Exception:
            get_logger().exception("Error processing message", message_id=message_id)
            if ack_messages and group:
                # Acknowledge even on error to avoid infinite retries
                # The execute_message handles retries internally
                await self.connection.xack(stream, group, message_id)

    def _decode_message_data(self, data: dict) -> dict:
        """Decode message data from Redis bytes to strings/dicts.

        Args:
            data: Raw message data from Redis.

        Returns:
            Decoded message data dictionary.

        """
        decoded = {}
        for key, value in data.items():
            key_str = key.decode() if isinstance(key, bytes) else key
            if isinstance(value, bytes):
                decoded[key_str] = value.decode()
            else:
                decoded[key_str] = value
        return decoded

    async def on_callback(self, message_data: dict) -> None:
        """Handle callback messages (responses and events).

        Args:
            message_data: The raw message data from Redis.

        """
        data = self._decode_message_data(message_data)

        headers = ujson.loads(data.get("headers", "{}"))
        if is_instrumentation_enabled() and headers:
            ctx = propagate.extract(headers)
            token = context.attach(ctx)
        else:
            token = None

        try:
            with trace.get_tracer(__name__).start_as_current_span("on_callback") as span:
                routing_key = data.get("routing_key", "")
                span.set_attribute("routing_key", routing_key)

                correlation_id = headers.get("correlation_id")
                if correlation_id:
                    span.set_attribute("correlation_id", correlation_id)
                    future = self.futures.pop(correlation_id, None)
                    if future:
                        future.set_result(data)
                        return

                clear_log_context()
                if routing_key in messages.MESSAGE_MAP:
                    body = data.get("body", b"")
                    if isinstance(body, str):
                        body = body.encode()
                    await execute_message(routing_key=routing_key, message_body=body, message_bus=self)
                else:
                    get_logger().error("Invalid message received", message=f"{data!r}")
        finally:
            if token is not None:
                context.detach(token)

    async def on_message(self, message_data: dict) -> None:
        """Handle work queue messages (RPCs).

        Args:
            message_data: The raw message data from Redis.

        """
        data = self._decode_message_data(message_data)

        headers = ujson.loads(data.get("headers", "{}"))
        if is_instrumentation_enabled() and headers:
            ctx = propagate.extract(headers)
            token = context.attach(ctx)
        else:
            token = None

        try:
            with trace.get_tracer(__name__).start_as_current_span("on_message") as span:
                routing_key = data.get("routing_key", "")
                span.set_attribute("routing_key", routing_key)

                clear_log_context()
                if routing_key in messages.MESSAGE_MAP:
                    body = data.get("body", b"")
                    if isinstance(body, str):
                        body = body.encode()
                    delay = await execute_message(routing_key=routing_key, message_body=body, message_bus=self)
                    if delay:
                        # Schedule retry with delay
                        await asyncio.sleep(delay / 1000)
                else:
                    get_logger().error("Invalid message received", message=f"{data!r}")
        finally:
            if token is not None:
                context.detach(token)

    async def _subscribe_events(self, identity: str) -> None:
        """Subscribe to event streams.

        Args:
            identity: Consumer identity string.

        """
        # For events, we use a pattern-based approach with consumer groups
        await self._create_stream_and_group(self.events_stream, f"{self.settings.namespace}-events")

        task = asyncio.create_task(
            self._consume_stream(
                stream=self.events_stream,
                group=f"{self.settings.namespace}-events",
                consumer=identity,
                callback=self.on_callback,
                ack_messages=True,
            )
        )
        self._consumer_tasks.append(task)

    async def _setup_callback(self, identity: str) -> None:
        """Set up callback stream for RPC responses.

        Args:
            identity: Consumer identity string.

        """
        # Callback stream doesn't use consumer groups - direct reads
        task = asyncio.create_task(
            self._consume_stream(
                stream=self.callback_stream,
                group=None,
                consumer=identity,
                callback=self.on_callback,
                ack_messages=False,
            )
        )
        self._consumer_tasks.append(task)

    async def _initialize_api_server(self) -> None:
        """Initialize message bus for API server component."""
        # Create events stream and consumer group
        await self._create_stream_and_group(self.events_stream, f"{self.settings.namespace}-events")

        # Create RPC stream and consumer group
        await self._create_stream_and_group(self.rpcs_stream, f"{self.settings.namespace}-rpcs")

        # Subscribe to events
        await self._subscribe_events(f"api-worker-{WORKER_IDENTITY}")

        # Set up callback queue for RPC responses
        await self._setup_callback(f"api-worker-{WORKER_IDENTITY}")

        self.message_enrichers.append(_add_request_id)

    async def _initialize_git_worker(self) -> None:
        """Initialize message bus for Git worker component."""
        # Subscribe to events
        await self._subscribe_events(f"git-worker-{WORKER_IDENTITY}")

        # Create consumer group for RPC stream
        await self._create_stream_and_group(self.rpcs_stream, "git-workers")

        # Start consuming from RPC stream
        task = asyncio.create_task(
            self._consume_stream(
                stream=self.rpcs_stream,
                group="git-workers",
                consumer=f"git-worker-{WORKER_IDENTITY}",
                callback=self.on_message,
                ack_messages=True,
            )
        )
        self._consumer_tasks.append(task)

        # Set up callback queue
        await self._setup_callback(f"git-worker-{WORKER_IDENTITY}")

    async def _publish_with_delay(self, message: InfrahubMessage, routing_key: str, delay: MessageTTL) -> None:
        """Publish a message after a delay.

        Args:
            message: The message to publish.
            routing_key: The routing key for the message.
            delay: The delay before publishing.

        """
        await asyncio.sleep(delay.value / 1000)
        await self.publish(message, routing_key)

    async def publish(
        self, message: InfrahubMessage, routing_key: str, delay: MessageTTL | None = None, is_retry: bool = False
    ) -> None:
        """Publish a message to the appropriate stream.

        Args:
            message: The message to publish.
            routing_key: The routing key for the message.
            delay: Optional delay before message delivery.
            is_retry: Whether this is a retry of a previously failed message.

        """
        with trace.get_tracer(__name__).start_as_current_span("publish_message") as span:
            span.set_attribute("routing_key", routing_key)

            if delay:
                if is_retry:
                    # Delayed retries are handled in the message processor
                    return
                # Use asyncio task for delayed publish
                task = asyncio.create_task(self._publish_with_delay(message, routing_key, delay))
                publish_tasks.add(task)
                task.add_done_callback(publish_tasks.discard)
                return

            for enricher in self.message_enrichers:
                await enricher(message)
            message.assign_priority(priority=messages.message_priority(routing_key=routing_key))

            headers: dict[str, str] = {}
            if message.meta.correlation_id:
                headers["correlation_id"] = message.meta.correlation_id
            if message.meta.reply_to:
                headers["reply_to"] = message.meta.reply_to
            if message.meta.expiration:
                headers["expiration"] = str(message.meta.expiration)

            if message.meta.headers:
                for k, v in message.meta.headers.items():
                    if v:
                        headers[k] = str(v)

            if is_instrumentation_enabled():
                propagate.inject(headers)

            # Determine which stream to publish to based on routing key
            stream = self._get_stream_for_routing_key(routing_key)

            await self.connection.xadd(
                stream,
                {
                    "routing_key": routing_key,
                    "body": message.body,
                    "headers": ujson.dumps(headers),
                    "priority": str(message.meta.priority or 0),
                },
            )

    def _get_stream_for_routing_key(self, routing_key: str) -> str:
        """Determine the appropriate stream for a routing key.

        Args:
            routing_key: The routing key to check.

        Returns:
            The stream name to use.

        """
        # Events go to events stream, work items go to RPCs stream
        if routing_key.startswith(("refresh.registry.", "refresh.git.")):
            return self.events_stream
        return self.rpcs_stream

    async def reply(self, message: InfrahubMessage, routing_key: str) -> None:
        """Send a reply message to a callback stream.

        Args:
            message: The reply message to send.
            routing_key: The callback stream name (from message.meta.reply_to).

        """
        headers: dict[str, str] = {}
        if message.meta.correlation_id:
            headers["correlation_id"] = message.meta.correlation_id
        if message.meta.reply_to:
            headers["reply_to"] = message.meta.reply_to
        if message.meta.expiration:
            headers["expiration"] = str(message.meta.expiration)
        if message.meta.headers:
            for k, v in message.meta.headers.items():
                if v:
                    headers[k] = str(v)

        if is_instrumentation_enabled():
            propagate.inject(headers)

        await self.connection.xadd(
            routing_key,
            {
                "routing_key": routing_key,
                "body": message.body,
                "headers": ujson.dumps(headers),
            },
        )

    async def rpc(self, message: InfrahubMessage, response_class: type[ResponseClass]) -> ResponseClass:
        """Make an RPC call and wait for the response.

        Args:
            message: The RPC request message.
            response_class: The expected response class type.

        Returns:
            The deserialized response object.

        """
        correlation_id = str(UUIDT())

        future: asyncio.Future = self.loop.create_future()
        self.futures[correlation_id] = future

        log_data = get_log_data()
        request_id = log_data.get("request_id", "")
        message.meta = Meta(request_id=request_id, correlation_id=correlation_id, reply_to=self.callback_stream)

        await self.send(message=message)

        response: dict = await future
        body = response.get("body", b"")
        if isinstance(body, bytes):
            body = body.decode()
        data = ujson.loads(body)
        return response_class(**data)
