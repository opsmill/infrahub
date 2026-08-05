from __future__ import annotations

import asyncio
import contextlib
import time
from dataclasses import dataclass
from fnmatch import fnmatch
from typing import TYPE_CHECKING, Awaitable, Callable, MutableMapping, TypeVar

import redis.asyncio as redis
import ujson
from infrahub_sdk.uuidt import UUIDT
from opentelemetry import context, propagate, trace
from opentelemetry.instrumentation.utils import is_instrumentation_enabled

from infrahub import config
from infrahub.components import ComponentType
from infrahub.exceptions import RPCError
from infrahub.log import clear_log_context, get_log_data, get_logger
from infrahub.message_bus import InfrahubMessage, Meta, messages
from infrahub.message_bus.operations import execute_message
from infrahub.services.adapters.message_bus import InfrahubMessageBus
from infrahub.worker import WORKER_IDENTITY

if TYPE_CHECKING:
    from redis.typing import EncodableT, FieldT

    from infrahub.config import BrokerSettings
    from infrahub.message_bus.types import MessageTTL

MessageFunction = Callable[[InfrahubMessage], Awaitable[None]]
ResponseClass = TypeVar("ResponseClass")


async def _add_request_id(message: InfrahubMessage) -> None:
    """Add request ID to message metadata from log context."""
    log_data = get_log_data()
    message.meta.request_id = log_data.get("request_id", "")


@dataclass
class StreamSubscription:
    """Describes how one consumer task reads a Redis stream.

    Without a group the stream is read directly from `start_id`, tracking
    concrete entry ids afterwards. With a group, entries are read through
    `XREADGROUP` and acknowledged when `ack_messages` is set. When `bindings`
    is set, entries whose routing key matches no pattern are skipped.
    """

    stream: str
    consumer: str
    callback: Callable[[dict], Awaitable[None]]
    group: str | None = None
    ack_messages: bool = False
    start_id: str = "0"
    bindings: list[str] | None = None


class RedisMessageBus(InfrahubMessageBus):
    """Message bus implementation using Redis Streams.

    Events are broadcast by having every worker read the shared events stream
    independently, work-queue messages are distributed through a consumer
    group, and RPC replies flow through a per-worker callback stream.
    """

    # Stream and consumer group names
    EVENTS_STREAM = "events"
    RPCS_STREAM = "rpcs"
    CALLBACK_STREAM_PREFIX = "callback"
    RPCS_GROUP = "git-workers"

    # Approximate upper bound for the events stream; events are fire-and-forget
    # broadcasts so older entries only need to survive long enough for live
    # readers to catch up.
    EVENTS_STREAM_MAXLEN = 10_000

    # Seconds between the pending-claim and trim passes of a group consumer.
    MAINTENANCE_INTERVAL: float = 60.0

    def __init__(self, component_type: ComponentType, settings: BrokerSettings | None = None) -> None:
        self.settings = settings or config.SETTINGS.broker
        self.connection: redis.Redis
        self.events_stream = f"{self.settings.namespace}:{self.EVENTS_STREAM}"
        self.rpcs_stream = f"{self.settings.namespace}:{self.RPCS_STREAM}"
        self.callback_stream = f"{self.settings.namespace}:{self.CALLBACK_STREAM_PREFIX}:{WORKER_IDENTITY}"
        self.message_enrichers: list[MessageFunction] = []

        self.loop = asyncio.get_running_loop()
        self.futures: MutableMapping[str, asyncio.Future] = {}

        self.component_type: ComponentType = component_type
        self._consumer_tasks: list[asyncio.Task] = []
        self._publish_tasks: set[asyncio.Task] = set()
        self._group_memberships: list[tuple[str, str, str]] = []
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

        if self.component_type == ComponentType.API_SERVER:
            await self._initialize_api_server()
        elif self.component_type == ComponentType.GIT_AGENT:
            await self._initialize_git_worker()

    async def shutdown(self) -> None:
        """Shutdown the message bus and clean up resources."""
        self._shutdown_event.set()

        for task in self._consumer_tasks:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

        for task in list(self._publish_tasks):
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

        with contextlib.suppress(redis.RedisError):
            await self._deregister_consumers()

        # Clean up callback stream
        with contextlib.suppress(redis.RedisError):
            await self.connection.delete(self.callback_stream)

        await self.connection.aclose()

    async def _deregister_consumers(self) -> None:
        """Remove this worker's consumers from their groups.

        A consumer that still owns pending entries is kept: it may have been
        cancelled mid-message, and deleting it would discard those entries
        instead of leaving them for a peer to claim.
        """
        for stream, group, consumer in self._group_memberships:
            pending = await self.connection.xpending_range(
                stream, group, min="-", max="+", count=1, consumername=consumer
            )
            if not pending:
                await self.connection.xgroup_delconsumer(stream, group, consumer)

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

    async def _get_last_stream_id(self, stream: str) -> str:
        """Return the id of the most recent entry in a stream, or "0" if the stream doesn't exist."""
        try:
            info = await self.connection.xinfo_stream(stream)
        except redis.ResponseError:
            return "0"
        last_id = info.get("last-generated-id", "0")
        if isinstance(last_id, bytes):
            return last_id.decode()
        return last_id

    def _maintenance_due(self, last_maintenance: float | None) -> bool:
        return last_maintenance is None or time.monotonic() - last_maintenance > self.MAINTENANCE_INTERVAL

    async def _consume_stream(self, subscription: StreamSubscription) -> None:
        """Consume messages from a Redis stream until shutdown.

        Args:
            subscription: The stream subscription to consume.

        """
        last_id = ">" if subscription.group else subscription.start_id
        last_maintenance: float | None = None

        while not self._shutdown_event.is_set():
            try:
                if subscription.group and self._maintenance_due(last_maintenance):
                    await self._claim_pending_messages(subscription)
                    await self._trim_worked_stream(subscription)
                    last_maintenance = time.monotonic()

                entries, last_id = await self._read_stream_entries(subscription, last_id)
                if not entries:
                    continue

                await self._process_stream_entries(entries, subscription)

            except asyncio.CancelledError:
                break
            except redis.RedisError as exc:
                if subscription.group and isinstance(exc, redis.ResponseError) and "NOGROUP" in str(exc):
                    get_logger().warning(
                        "Stream or consumer group missing, recreating",
                        stream=subscription.stream,
                        group=subscription.group,
                    )
                    with contextlib.suppress(redis.RedisError):
                        await self._create_stream_and_group(subscription.stream, subscription.group)
                    continue
                get_logger().exception("Redis error in consumer")
                await asyncio.sleep(1)  # Back off on errors
            except Exception:
                # A malformed entry or driver surprise must not silently kill the
                # consumer task; log and keep consuming.
                get_logger().exception("Unexpected error in consumer")
                await asyncio.sleep(1)  # Back off on errors

    async def _read_stream_entries(self, subscription: StreamSubscription, last_id: str) -> tuple[list, str]:
        """Read entries from a Redis stream.

        Args:
            subscription: The stream subscription to read for.
            last_id: The last message ID read.

        Returns:
            A tuple of (entries list, updated last_id).

        """
        if subscription.group:
            entries = await self.connection.xreadgroup(
                groupname=subscription.group,
                consumername=subscription.consumer,
                streams={subscription.stream: last_id},
                count=1,
                block=1000,
            )
        else:
            entries = await self.connection.xread(
                streams={subscription.stream: last_id},
                count=1,
                block=1000,
            )
            if entries:
                last_id = entries[0][1][-1][0]

        return entries or [], last_id

    async def _process_stream_entries(self, entries: list, subscription: StreamSubscription) -> None:
        """Process entries from a Redis stream.

        Args:
            entries: List of stream entries to process.
            subscription: The stream subscription the entries were read for.

        """
        for _stream_name, stream_entries in entries:
            for message_id, message_data in stream_entries:
                await self._process_single_message(message_id, message_data, subscription)

    async def _process_single_message(
        self, message_id: bytes, message_data: dict, subscription: StreamSubscription
    ) -> None:
        """Process a single message from a stream.

        Args:
            message_id: The message ID.
            message_data: The message data.
            subscription: The stream subscription the message was read for.

        """
        try:
            if self._matches_bindings(message_data=message_data, bindings=subscription.bindings):
                await subscription.callback(message_data)
        except Exception:
            # Failed messages are retried through a delayed re-publish, so the
            # original entry is acknowledged either way.
            get_logger().exception("Error processing message", message_id=message_id)
        if subscription.ack_messages and subscription.group:
            await self.connection.xack(subscription.stream, subscription.group, message_id)

    @staticmethod
    def _matches_bindings(message_data: dict, bindings: list[str] | None) -> bool:
        """Check whether an entry's routing key matches one of the binding patterns."""
        if bindings is None:
            return True
        routing_key = message_data.get(b"routing_key") or message_data.get("routing_key") or b""
        if isinstance(routing_key, bytes):
            routing_key = routing_key.decode()
        return any(fnmatch(routing_key, pattern) for pattern in bindings)

    async def _claim_pending_messages(self, subscription: StreamSubscription) -> None:
        """Take over entries whose owner stopped before acknowledging them.

        An entry left pending for longer than DELIVER_TIMEOUT is considered
        abandoned by a dead worker and is re-processed here; nothing
        legitimately runs longer than that, so live handlers are never
        double-executed.
        """
        if not subscription.group:
            return

        start_id = "0-0"
        while not self._shutdown_event.is_set():
            response = await self.connection.xautoclaim(
                name=subscription.stream,
                groupname=subscription.group,
                consumername=subscription.consumer,
                min_idle_time=self.DELIVER_TIMEOUT * 1000,
                start_id=start_id,
                count=10,
            )
            next_start_id, claimed = response[0], response[1]
            if not claimed:
                break

            for message_id, message_data in claimed:
                if message_data is None:
                    # The entry was trimmed while pending; acknowledge to stop re-claiming it.
                    await self.connection.xack(subscription.stream, subscription.group, message_id)
                    continue
                await self._process_single_message(message_id, message_data, subscription)

            start_id = next_start_id

    async def _trim_worked_stream(self, subscription: StreamSubscription) -> None:
        """Delete entries the consumer group is done with.

        The stream is trimmed up to the oldest entry still pending in the
        group, so entries a crashed worker never acknowledged stay claimable.
        With nothing pending, everything before the group's last delivered
        entry is acknowledged history and can go.
        """
        if not subscription.group:
            return

        pending_summary = await self.connection.xpending(subscription.stream, subscription.group)
        threshold = pending_summary.get("min") if pending_summary.get("pending") else None

        if threshold is None:
            group_name = subscription.group.encode()
            groups = await self.connection.xinfo_groups(subscription.stream)
            for group_info in groups:
                if group_info.get("name") in (group_name, subscription.group):
                    threshold = group_info.get("last-delivered-id")
                    break

        if threshold in (None, b"0-0", "0-0"):
            return

        await self.connection.xtrim(subscription.stream, minid=threshold, approximate=False)

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
                    if future and not future.done():
                        future.set_result(data)
                    else:
                        get_logger().info("Discarding reply to an expired RPC request", correlation_id=correlation_id)
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
                    # Failure retries are re-published with a delay, so there is
                    # nothing to do with the returned TTL here.
                    await execute_message(routing_key=routing_key, message_body=body, message_bus=self)
                else:
                    get_logger().error("Invalid message received", message=f"{data!r}")
        finally:
            if token is not None:
                context.detach(token)

    async def _subscribe_events(self, identity: str, bindings: list[str]) -> None:
        """Subscribe this worker to the shared events stream.

        Every worker reads the stream independently starting from its current
        tail, giving broadcast semantics without durable per-worker state: a
        worker that goes away leaves nothing behind, and one that starts up
        only sees events published from that point on.

        Args:
            identity: Consumer identity string.
            bindings: Routing key patterns this worker handles.

        """
        start_id = await self._get_last_stream_id(self.events_stream)
        task = asyncio.create_task(
            self._consume_stream(
                StreamSubscription(
                    stream=self.events_stream,
                    consumer=identity,
                    callback=self.on_callback,
                    start_id=start_id,
                    bindings=bindings,
                )
            )
        )
        self._consumer_tasks.append(task)

    async def _setup_callback(self, identity: str) -> None:
        """Set up callback stream for RPC responses.

        The callback stream is unique to this process, so reading from "0" is
        safe, while "$" would silently drop entries added before the first
        XREAD or between two XREADs on an idle stream.

        Args:
            identity: Consumer identity string.

        """
        task = asyncio.create_task(
            self._consume_stream(
                StreamSubscription(
                    stream=self.callback_stream,
                    consumer=identity,
                    callback=self.on_callback,
                )
            )
        )
        self._consumer_tasks.append(task)

    async def _initialize_api_server(self) -> None:
        """Initialize message bus for API server component."""
        # Create the work queue group up front so work published before the
        # first git worker boots is delivered once one joins.
        await self._create_stream_and_group(self.rpcs_stream, self.RPCS_GROUP)

        await self._subscribe_events(identity=f"api-worker-{WORKER_IDENTITY}", bindings=self.event_bindings)

        await self._setup_callback(identity=f"api-worker-{WORKER_IDENTITY}")

        self.message_enrichers.append(_add_request_id)

    async def _initialize_git_worker(self) -> None:
        """Initialize message bus for Git worker component."""
        await self._subscribe_events(
            identity=f"git-worker-{WORKER_IDENTITY}",
            bindings=self.event_bindings + self.broadcasted_event_bindings,
        )

        await self._create_stream_and_group(self.rpcs_stream, self.RPCS_GROUP)

        consumer = f"git-worker-{WORKER_IDENTITY}"
        self._group_memberships.append((self.rpcs_stream, self.RPCS_GROUP, consumer))
        task = asyncio.create_task(
            self._consume_stream(
                StreamSubscription(
                    stream=self.rpcs_stream,
                    group=self.RPCS_GROUP,
                    consumer=consumer,
                    callback=self.on_message,
                    ack_messages=True,
                )
            )
        )
        self._consumer_tasks.append(task)

        await self._setup_callback(identity=consumer)

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
        self,
        message: InfrahubMessage,
        routing_key: str,
        delay: MessageTTL | None = None,
        is_retry: bool = False,  # noqa: ARG002
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
                # Redis has no broker-side delayed delivery; the pending publish
                # only survives as long as this process does.
                task = asyncio.create_task(self._publish_with_delay(message, routing_key, delay))
                self._publish_tasks.add(task)
                task.add_done_callback(self._publish_tasks.discard)
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

            fields: dict[FieldT, EncodableT] = {
                "routing_key": routing_key,
                "body": message.body,
                "headers": ujson.dumps(headers),
                "priority": str(message.meta.priority or 0),
            }
            if stream == self.events_stream:
                await self.connection.xadd(stream, fields, maxlen=self.EVENTS_STREAM_MAXLEN, approximate=True)
            else:
                await self.connection.xadd(stream, fields)

    def _get_stream_for_routing_key(self, routing_key: str) -> str:
        """Determine the appropriate stream for a routing key.

        Args:
            routing_key: The routing key to check.

        Returns:
            The stream name to use.

        """
        # Events go to events stream, work items go to RPCs stream
        if any(fnmatch(routing_key, pattern) for pattern in self.event_bindings + self.broadcasted_event_bindings):
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

    async def rpc(
        self,
        message: InfrahubMessage,
        response_class: type[ResponseClass],
        timeout: int | None = None,  # noqa: ASYNC109
    ) -> ResponseClass:
        """Make an RPC call and wait for the response.

        Args:
            message: The RPC request message.
            response_class: The expected response class type.
            timeout: Seconds to wait for the reply; RPC_TIMEOUT when unset.

        Returns:
            The deserialized response object.

        Raises:
            RPCError: If no reply arrives within the timeout.

        """
        correlation_id = str(UUIDT())

        future: asyncio.Future = self.loop.create_future()
        self.futures[correlation_id] = future

        log_data = get_log_data()
        request_id = log_data.get("request_id", "")
        message.meta = Meta(request_id=request_id, correlation_id=correlation_id, reply_to=self.callback_stream)

        await self.send(message=message)

        timeout = timeout or self.RPC_TIMEOUT
        try:
            response: dict = await asyncio.wait_for(future, timeout=timeout)
        except TimeoutError as exc:
            self.futures.pop(correlation_id, None)
            raise RPCError(message=f"No response to RPC message '{type(message).__name__}' within {timeout}s") from exc
        body = response.get("body", b"")
        if isinstance(body, bytes):
            body = body.decode()
        data = ujson.loads(body)
        return response_class(**data)
