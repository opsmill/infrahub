from __future__ import annotations

import asyncio
import contextlib
import time
from dataclasses import dataclass, field
from fnmatch import fnmatch
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Iterator, MutableMapping, TypeVar

import redis.asyncio as redis
import ujson
from infrahub_sdk.uuidt import UUIDT
from opentelemetry import context, propagate, trace
from opentelemetry.instrumentation.utils import is_instrumentation_enabled
from prefect_redis.connection import aclose_redis_client

from infrahub import config
from infrahub.components import ComponentType
from infrahub.log import clear_log_context, get_logger
from infrahub.message_bus import InfrahubMessage, messages
from infrahub.message_bus.operations import execute_message
from infrahub.redis_connection import build_broker_redis_connection
from infrahub.services.adapters.message_bus import (
    InfrahubMessageBus,
    MessageListener,
    add_request_id,
    topic_matches,
)
from infrahub.worker import WORKER_IDENTITY

if TYPE_CHECKING:
    from opentelemetry.trace import Span
    from redis.commands.core import AsyncScript
    from redis.typing import EncodableT, FieldT, XReadGroupResponse, XReadResponse

    from infrahub.config import BrokerSettings
    from infrahub.message_bus.types import MessageTTL

MessageFunction = Callable[[InfrahubMessage], Awaitable[None]]
ResponseClass = TypeVar("ResponseClass")

# Re-publishes due entries of the delayed queue (KEYS[1]) onto their target
# streams. Every entry is removed right after its own successful XADD, so a
# failure can never replay already-delivered entries (script errors abort
# without rolling back applied effects). A failing entry is rescored to a
# later due time instead of staying at the head of every scan; once it
# exhausts its delivery attempts (tracked in KEYS[2]) it is parked in the
# dead-letter list (KEYS[3]) for inspection. Retried and parked members are
# returned to the caller for logging. The whole script runs serialized, so
# concurrent pollers never deliver an entry twice. The target streams cannot
# be declared as KEYS up front, so this requires a non-clustered Redis.
DELIVER_DUE_MESSAGES_LUA = """
local due = redis.call('ZRANGEBYSCORE', KEYS[1], '-inf', ARGV[1], 'LIMIT', 0, ARGV[2])
local retried = {}
local dead = {}
for _, member in ipairs(due) do
    local delivered = false
    local entry_id = member
    local ok, entry = pcall(cjson.decode, member)
    if ok and type(entry) == 'table' and type(entry.fields) == 'table' and entry.stream then
        if entry.id then
            entry_id = entry.id
        end
        local fields = {}
        for key, value in pairs(entry.fields) do
            fields[#fields + 1] = key
            fields[#fields + 1] = value
        end
        local result
        if entry.maxlen then
            result = redis.pcall('XADD', entry.stream, 'MAXLEN', '~', entry.maxlen, '*', unpack(fields))
        else
            result = redis.pcall('XADD', entry.stream, '*', unpack(fields))
        end
        delivered = not (type(result) == 'table' and result.err)
    end
    if delivered then
        redis.call('ZREM', KEYS[1], member)
        redis.call('HDEL', KEYS[2], entry_id)
    else
        local attempts = redis.call('HINCRBY', KEYS[2], entry_id, 1)
        if attempts < tonumber(ARGV[4]) then
            redis.call('ZADD', KEYS[1], tonumber(ARGV[1]) + tonumber(ARGV[3]), member)
            retried[#retried + 1] = member
        else
            redis.call('ZREM', KEYS[1], member)
            redis.call('RPUSH', KEYS[3], member)
            redis.call('LTRIM', KEYS[3], -tonumber(ARGV[5]), -1)
            redis.call('HDEL', KEYS[2], entry_id)
            dead[#dead + 1] = member
        end
    end
end
return {retried, dead}
"""


@dataclass
class StreamSubscription:
    """Describes how one consumer task reads a Redis stream.

    Without a group the stream is read directly from `start_id`, tracking
    concrete entry ids afterwards. With a group, entries are read through
    `XREADGROUP` and acknowledged when `ack_messages` is set. When `bindings`
    is set, entries whose routing key matches no pattern are skipped.
    `owns_stream` marks a stream with no other reader, allowing the consumer
    to trim entries it has already read. `in_progress` holds the ids of the
    group entries whose handler has started and not yet acknowledged them.
    """

    stream: str
    consumer: str
    callback: Callable[[dict], Awaitable[None]]
    group: str | None = None
    ack_messages: bool = False
    start_id: str = "0"
    bindings: list[str] | None = None
    owns_stream: bool = False
    in_progress: set[bytes] = field(default_factory=set)


class RedisMessageBus(InfrahubMessageBus):
    """Message bus implementation using Redis Streams.

    Events are broadcast by having every worker read the shared events stream
    independently, work-queue messages are distributed through a consumer
    group, and RPC replies flow through a per-worker callback stream. Delayed
    deliveries wait in a shared sorted set until they come due.
    """

    # Stream, sorted set, and consumer group names
    EVENTS_STREAM = "events"
    RPCS_STREAM = "rpcs"
    CALLBACK_STREAM_PREFIX = "callback"
    DELAYED_QUEUE = "delayed"
    DELAYED_ATTEMPTS = "delayed:attempts"
    DELAYED_DEAD_LETTER = "delayed:dead"
    WORK_DEAD_LETTER = "rpcs:dead"
    RPCS_GROUP = "git-workers"

    # Approximate upper bound for the events stream; events are fire-and-forget
    # broadcasts so older entries only need to survive long enough for live
    # readers to catch up.
    EVENTS_STREAM_MAXLEN = 10_000

    # Expiry for per-worker callback streams. A live worker keeps pushing its
    # stream's expiry out and trims read entries, so the expiry only ever
    # lapses for a stream orphaned by a worker that died without its shutdown
    # cleanup.
    CALLBACK_STREAM_TTL: int = InfrahubMessageBus.DELIVER_TIMEOUT

    # Seconds between the pending-claim and trim passes of a group consumer.
    MAINTENANCE_INTERVAL: float = 30.0

    # A work queue entry that nobody has marked as in progress for this long
    # is claimed by another worker. Workers mark the entries they are handling
    # every few seconds, so this only catches the entries of a worker that
    # stopped, and the deliveries that never reached their worker.
    CLAIM_IDLE_MS: int = 60_000

    # Seconds between two marks of the entries a worker is handling, kept far
    # below the claim threshold so that a live handler never looks abandoned.
    IN_PROGRESS_REFRESH_SECONDS: float = 15.0

    # A work queue entry delivered more times than this, which happens when
    # its handler keeps stopping its worker, is parked in the work dead-letter
    # list, which keeps the newest entries only, instead of being run again.
    WORK_MAX_DELIVERIES: int = 5
    WORK_DEAD_LETTER_MAXLEN: int = 1_000

    # Milliseconds a stream read waits for a new entry, which bounds how long
    # a consumer takes to notice a shutdown or a due maintenance pass.
    READ_BLOCK_MS: int = 1_000

    # Abandoned entries taken over per XAUTOCLAIM call.
    CLAIM_BATCH: int = 10

    # Seconds a consumer waits after a failed read before reading again.
    ERROR_BACKOFF_SECONDS: float = 1.0

    # A consumer that has read nothing for this long and holds no pending
    # entry belongs to a worker that stopped without its shutdown cleanup,
    # since a live one reads every second; by then its abandoned entries have
    # been claimed by others.
    STALE_CONSUMER_IDLE_MS: int = InfrahubMessageBus.DELIVER_TIMEOUT * 1_000

    # Seconds between two scans of the delayed queue, and the maximum number
    # of due entries one scan delivers; anything beyond the batch is picked up
    # by the next scan.
    DELAYED_POLL_INTERVAL: float = 1.0
    DELAYED_DELIVERY_BATCH = 100

    # A delayed entry that fails to deliver becomes due again after this
    # backoff (milliseconds); once it exhausts its delivery attempts it is
    # parked in the dead-letter list, which keeps the newest entries only.
    DELAYED_RETRY_DELAY_MS: int = 60_000
    DELAYED_MAX_ATTEMPTS: int = 5
    DELAYED_DEAD_LETTER_MAXLEN: int = 1_000

    def __init__(self, component_type: ComponentType, settings: BrokerSettings | None = None) -> None:
        self.settings = settings or config.SETTINGS.broker
        self.connection: redis.Redis
        self.events_stream = f"{self.settings.namespace}:{self.EVENTS_STREAM}"
        self.rpcs_stream = f"{self.settings.namespace}:{self.RPCS_STREAM}"
        self.callback_stream = f"{self.settings.namespace}:{self.CALLBACK_STREAM_PREFIX}:{WORKER_IDENTITY}"
        self.delayed_queue = f"{self.settings.namespace}:{self.DELAYED_QUEUE}"
        self.delayed_attempts = f"{self.settings.namespace}:{self.DELAYED_ATTEMPTS}"
        self.delayed_dead_letter = f"{self.settings.namespace}:{self.DELAYED_DEAD_LETTER}"
        self.work_dead_letter = f"{self.settings.namespace}:{self.WORK_DEAD_LETTER}"
        self.message_enrichers: list[MessageFunction] = []

        self.loop = asyncio.get_running_loop()
        self.futures: MutableMapping[str, asyncio.Future] = {}

        self.component_type: ComponentType = component_type
        self._consumer_tasks: list[asyncio.Task] = []
        self._handler_tasks: set[asyncio.Task] = set()
        self._deliver_due_script: AsyncScript
        self._group_subscriptions: list[StreamSubscription] = []
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
        self.connection = build_broker_redis_connection(self.settings)

        if self.component_type == ComponentType.API_SERVER:
            await self._initialize_api_server()
        elif self.component_type == ComponentType.GIT_AGENT:
            await self._initialize_git_worker()
        else:
            # A process that is neither a server nor a worker only sends or listens.
            return

        self._deliver_due_script = self.connection.register_script(DELIVER_DUE_MESSAGES_LUA)
        self._consumer_tasks.append(asyncio.create_task(self._deliver_delayed_messages()))

    async def shutdown(self) -> None:
        """Shutdown the message bus and clean up resources."""
        self._shutdown_event.set()

        for task in [*self._consumer_tasks, *self._handler_tasks]:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

        with contextlib.suppress(redis.RedisError):
            await self._release_unfinished_entries()

        with contextlib.suppress(redis.RedisError):
            await self._deregister_consumers()

        # Clean up callback stream
        with contextlib.suppress(redis.RedisError):
            await self.connection.delete(self.callback_stream)

        await aclose_redis_client(self.connection)

    async def _release_unfinished_entries(self) -> None:
        """Make the entries whose handler the shutdown cancelled claimable by another worker at once.

        The entries stay pending to this consumer with an idle time already at the claim threshold, so they keep
        their delivery count, and the next claim pass of any worker takes them over.
        """
        for subscription in self._group_subscriptions:
            if not subscription.group or not subscription.in_progress:
                continue
            await self.connection.xclaim(
                subscription.stream,
                subscription.group,
                subscription.consumer,
                min_idle_time=0,
                message_ids=list(subscription.in_progress),
                idle=self.CLAIM_IDLE_MS,
                justid=True,
            )
            subscription.in_progress.clear()

    async def _deregister_consumers(self) -> None:
        """Remove this worker's consumers from their groups.

        A consumer that still owns pending entries is kept: it may have been
        cancelled mid-message, and deleting it would discard those entries
        instead of leaving them for a peer to claim.
        """
        for subscription in self._group_subscriptions:
            if not subscription.group:
                continue
            pending = await self.connection.xpending_range(
                subscription.stream,
                subscription.group,
                min="-",
                max="+",
                count=1,
                consumername=subscription.consumer,
            )
            if not pending:
                await self.connection.xgroup_delconsumer(subscription.stream, subscription.group, subscription.consumer)

    async def _create_stream_and_group(self, stream: str, group: str) -> None:
        """Create a stream and consumer group if they don't exist.

        Args:
            stream: The stream name to create.
            group: The consumer group name to create.

        Raises:
            ResponseError: If group creation fails for any reason other than the group already existing.

        """
        try:
            # MKSTREAM creates a missing stream, since a group cannot be created on a stream that does not exist.
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

        Each entry is handled in its own task, so a slow handler does not hold up the entries behind it. A
        consumer group reads an entry only once one of the broker's maximum_concurrent_messages handler slots is
        free, so a busy worker leaves the entries it cannot start yet to the other workers.

        Args:
            subscription: The stream subscription to consume.

        """
        last_id = ">" if subscription.group else subscription.start_id
        last_maintenance: float | None = None
        slots = asyncio.Semaphore(self.settings.maximum_concurrent_messages) if subscription.group else None

        while not self._shutdown_event.is_set():
            holds_slot = False
            try:
                if self._maintenance_due(last_maintenance) and (subscription.group or subscription.owns_stream):
                    # Recorded first, so a maintenance failure waits for the next interval instead of blocking reads.
                    last_maintenance = time.monotonic()
                    if subscription.group:
                        await self._claim_pending_messages(subscription, slots)
                        await self._trim_worked_stream(subscription)
                        await self._remove_stale_consumers(subscription)
                    else:
                        await self._maintain_owned_stream(subscription, last_id)

                if slots is not None:
                    await slots.acquire()
                    holds_slot = True

                # A read returns at most one entry, so an entry never needs more than the slot taken above.
                entries, last_id = await self._read_stream_entries(subscription, last_id)
                for _stream_name, stream_entries in entries:
                    for message_id, message_data in stream_entries:
                        self._start_handler(message_id, message_data, subscription, slots)
                        holds_slot = False

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
                await asyncio.sleep(self.ERROR_BACKOFF_SECONDS)
            # Worker loop boundary: a malformed entry or driver surprise must not kill the consumer task.
            except Exception:  # noqa: BLE001
                get_logger().exception("Unexpected error in consumer")
                await asyncio.sleep(self.ERROR_BACKOFF_SECONDS)
            finally:
                if holds_slot and slots is not None:
                    slots.release()

    def _start_handler(
        self, message_id: bytes, message_data: dict, subscription: StreamSubscription, slots: asyncio.Semaphore | None
    ) -> None:
        """Handle an entry in a task of its own, which gives its handler slot back when it ends."""
        tracked = bool(subscription.group and subscription.ack_messages)
        if tracked:
            subscription.in_progress.add(message_id)

        async def handle() -> None:
            try:
                await self._process_single_message(message_id, message_data, subscription)
                # Left in place when the handler is cancelled, so the shutdown can hand the entry to another worker.
                if tracked:
                    subscription.in_progress.discard(message_id)
            finally:
                if slots is not None:
                    slots.release()

        task = asyncio.create_task(handle())
        self._handler_tasks.add(task)
        task.add_done_callback(self._handler_tasks.discard)

    async def _read_stream_entries(self, subscription: StreamSubscription, last_id: str) -> tuple[list[list[Any]], str]:
        """Read entries from a Redis stream.

        Args:
            subscription: The stream subscription to read for.
            last_id: The last message ID read.

        Returns:
            A tuple of (entries list, updated last_id).

        Raises:
            TypeError: If the reply is not the list of streams that the RESP2 protocol returns.

        """
        response: XReadResponse | XReadGroupResponse
        if subscription.group:
            response = await self.connection.xreadgroup(
                groupname=subscription.group,
                consumername=subscription.consumer,
                streams={subscription.stream: last_id},
                count=1,
                block=self.READ_BLOCK_MS,
            )
        else:
            response = await self.connection.xread(
                streams={subscription.stream: last_id},
                count=1,
                block=self.READ_BLOCK_MS,
            )

        # Under RESP2, which this client speaks, redis-py returns a list of streams, empty when the blocking read times out.
        if not isinstance(response, list):
            raise TypeError(f"Expected a list of streams from the stream read, got {type(response).__name__}")
        if response and not subscription.group:
            last_id = response[0][1][-1][0]

        return response, last_id

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
        # Per-entry boundary: one failing entry is logged instead of stopping the consumer.
        except Exception:  # noqa: BLE001
            # Failed messages are durably re-scheduled before their handler
            # returns, so the original entry is acknowledged either way.
            get_logger().exception("Error processing message", message_id=message_id)
        if subscription.ack_messages and subscription.group:
            try:
                await self.connection.xack(subscription.stream, subscription.group, message_id)
            except redis.RedisError:
                # The entry stays pending, so it is claimed again once it has been idle long enough.
                get_logger().exception("Failed to acknowledge message", message_id=message_id)

    @staticmethod
    def _matches_bindings(message_data: dict, bindings: list[str] | None) -> bool:
        """Check whether an entry's routing key matches one of the binding patterns."""
        if bindings is None:
            return True
        routing_key = message_data.get(b"routing_key") or message_data.get("routing_key") or b""
        if isinstance(routing_key, bytes):
            routing_key = routing_key.decode()
        return any(fnmatch(routing_key, pattern) for pattern in bindings)

    async def _claim_pending_messages(self, subscription: StreamSubscription, slots: asyncio.Semaphore | None) -> None:
        """Take over entries whose owner stopped before acknowledging them.

        A live worker marks the entries it is handling as in progress far more
        often than the claim threshold, so an entry idle for longer belongs to
        a worker that stopped, or was never received by its worker, and is
        re-processed here. An entry delivered too many times is parked instead. A claimed
        entry waits for a free handler slot like a newly read one.
        """
        if not subscription.group:
            return

        start_id = "0-0"
        while not self._shutdown_event.is_set():
            response = await self.connection.xautoclaim(
                name=subscription.stream,
                groupname=subscription.group,
                consumername=subscription.consumer,
                min_idle_time=self.CLAIM_IDLE_MS,
                start_id=start_id,
                count=self.CLAIM_BATCH,
            )
            next_start_id, claimed = response[0], response[1]

            for message_id, message_data in claimed:
                if message_id is None:
                    # Redis 6.2 reports an entry deleted while pending without its id, so it cannot be acknowledged.
                    continue
                if message_data is None:
                    # The entry was trimmed while pending; acknowledge to stop re-claiming it.
                    await self.connection.xack(subscription.stream, subscription.group, message_id)
                    continue
                if message_id in subscription.in_progress:
                    # Already running here, so the claim only reset its idle time.
                    continue
                if await self._park_if_delivered_too_often(subscription, message_id, message_data):
                    continue
                if slots is not None:
                    await slots.acquire()
                self._start_handler(message_id, message_data, subscription, slots)

            # The cursor returns to 0-0 once the scan has covered every pending entry, so one pass never claims an
            # entry whose handler it has just started.
            if next_start_id in (b"0-0", "0-0"):
                break
            start_id = next_start_id

    async def _park_if_delivered_too_often(
        self, subscription: StreamSubscription, message_id: bytes, message_data: dict
    ) -> bool:
        """Move a claimed entry to the work dead-letter list when it has been delivered too many times.

        Returns:
            Whether the entry was parked, in which case it must not be handled.

        Raises:
            TypeError: If the pending entry summary reports a delivery count that is not an integer.

        """
        if not subscription.group:
            return False
        pending = await self.connection.xpending_range(
            subscription.stream, subscription.group, min=message_id, max=message_id, count=1
        )
        deliveries = pending[0]["times_delivered"] if pending else 0
        if not isinstance(deliveries, int):
            raise TypeError(f"Expected an integer delivery count, got {type(deliveries).__name__}")
        if deliveries <= self.WORK_MAX_DELIVERIES:
            return False

        entry = {
            "id": message_id.decode(),
            "stream": subscription.stream,
            "deliveries": deliveries,
            "fields": self._decode_message_data(message_data),
        }
        async with self.connection.pipeline(transaction=True) as pipe:
            pipe.rpush(self.work_dead_letter, ujson.dumps(entry))
            pipe.ltrim(self.work_dead_letter, -self.WORK_DEAD_LETTER_MAXLEN, -1)
            pipe.xack(subscription.stream, subscription.group, message_id)
            await pipe.execute()
        get_logger().error(
            "Parked a work item delivered too many times in the dead-letter list",
            message_id=entry["id"],
            deliveries=deliveries,
        )
        return True

    async def _refresh_in_progress(self, subscription: StreamSubscription) -> None:
        """Mark the entries this worker is handling as in progress, until shutdown.

        Claiming an entry to its own consumer with JUSTID resets its idle time without counting a delivery.
        """
        while not self._shutdown_event.is_set():
            await asyncio.sleep(self.IN_PROGRESS_REFRESH_SECONDS)
            if not subscription.group or not subscription.in_progress:
                continue
            try:
                await self.connection.xclaim(
                    subscription.stream,
                    subscription.group,
                    subscription.consumer,
                    min_idle_time=0,
                    message_ids=list(subscription.in_progress),
                    justid=True,
                )
            except redis.RedisError:
                get_logger().exception("Redis error marking work items as in progress")
            # Worker loop boundary: an unexpected error must not let live work items look abandoned.
            except Exception:  # noqa: BLE001
                get_logger().exception("Unexpected error marking work items as in progress")

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

    async def _remove_stale_consumers(self, subscription: StreamSubscription) -> None:
        """Delete the group's consumers that hold no pending entry and have not read anything for a long time.

        Deleting a consumer discards its pending entries, so one that still holds an entry is kept until another
        worker has claimed it.
        """
        if not subscription.group:
            return

        for consumer in await self.connection.xinfo_consumers(subscription.stream, subscription.group):
            name = consumer["name"].decode() if isinstance(consumer["name"], bytes) else consumer["name"]
            if name == subscription.consumer or consumer["pending"] or consumer["idle"] < self.STALE_CONSUMER_IDLE_MS:
                continue
            await self.connection.xgroup_delconsumer(subscription.stream, subscription.group, name)
            get_logger().info(
                "Removed a consumer that stopped without its shutdown cleanup",
                stream=subscription.stream,
                group=subscription.group,
                consumer=name,
            )

    async def _maintain_owned_stream(self, subscription: StreamSubscription, last_id: str | bytes) -> None:
        """Trim read entries and push out the expiry of a stream this consumer owns.

        Trimming up to the last-read id can never discard an unread entry, so
        this is only safe for streams with a single reader. The newest read
        entry itself is kept, sparing the trim threshold an id increment. The
        refreshed expiry lets a stream whose owner is gone delete itself
        instead of accumulating replies forever.
        """
        if not subscription.owns_stream or subscription.group:
            return
        if last_id not in ("0", b"0"):
            await self.connection.xtrim(subscription.stream, minid=last_id, approximate=False)
        await self.connection.expire(subscription.stream, self.CALLBACK_STREAM_TTL)

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

    @contextlib.contextmanager
    def _traced_message(self, message_data: dict, span_name: str) -> Iterator[tuple[dict, dict, Span]]:
        """Decode a raw stream entry and set up its tracing context.

        Yields the decoded entry data, its parsed headers, and the active
        span; the propagated trace context is detached again on exit.
        """
        data = self._decode_message_data(message_data)
        headers = ujson.loads(data.get("headers", "{}"))
        if is_instrumentation_enabled() and headers:
            token = context.attach(propagate.extract(headers))
        else:
            token = None

        try:
            with trace.get_tracer(__name__).start_as_current_span(span_name) as span:
                span.set_attribute("routing_key", data.get("routing_key", ""))
                yield data, headers, span
        finally:
            if token is not None:
                context.detach(token)

    async def _dispatch(self, data: dict) -> None:
        """Execute a decoded entry with the handler registered for its routing key."""
        clear_log_context()
        routing_key = data.get("routing_key", "")
        if routing_key not in messages.MESSAGE_MAP:
            get_logger().error("Invalid message received", message=f"{data!r}")
            return
        body = data.get("body", b"")
        if isinstance(body, str):
            body = body.encode()
        # Failure retries are durably re-scheduled with a delay, so there is
        # nothing to do with the returned TTL here.
        await execute_message(routing_key=routing_key, message_body=body, message_bus=self)

    async def on_callback(self, message_data: dict) -> None:
        """Handle callback messages (responses and events).

        An entry carrying a correlation id is an RPC reply and resolves the
        future awaiting it; anything else is dispatched as a regular message.

        Args:
            message_data: The raw message data from Redis.

        """
        with self._traced_message(message_data, "on_callback") as (data, headers, span):
            correlation_id = headers.get("correlation_id")
            if correlation_id:
                span.set_attribute("correlation_id", correlation_id)
                future = self.futures.pop(correlation_id, None)
                if future and not future.done():
                    future.set_result(data)
                else:
                    get_logger().info("Discarding reply to an expired RPC request", correlation_id=correlation_id)
                return

            await self._dispatch(data)

    async def on_message(self, message_data: dict) -> None:
        """Handle work queue messages (RPCs).

        RPC requests carry a correlation id for their reply, so unlike
        callback entries they are always dispatched to a handler.

        Args:
            message_data: The raw message data from Redis.

        """
        with self._traced_message(message_data, "on_message") as (data, _headers, _span):
            await self._dispatch(data)

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
                    owns_stream=True,
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

        self.message_enrichers.append(add_request_id)

    async def _initialize_git_worker(self) -> None:
        """Initialize message bus for Git worker component."""
        await self._subscribe_events(
            identity=f"git-worker-{WORKER_IDENTITY}",
            bindings=self.event_bindings + self.broadcasted_event_bindings,
        )

        await self._create_stream_and_group(self.rpcs_stream, self.RPCS_GROUP)

        consumer = f"git-worker-{WORKER_IDENTITY}"
        subscription = StreamSubscription(
            stream=self.rpcs_stream,
            group=self.RPCS_GROUP,
            consumer=consumer,
            callback=self.on_message,
            ack_messages=True,
        )
        self._group_subscriptions.append(subscription)
        self._consumer_tasks.append(asyncio.create_task(self._consume_stream(subscription)))
        self._consumer_tasks.append(asyncio.create_task(self._refresh_in_progress(subscription)))

        await self._setup_callback(identity=consumer)

    async def _server_time_ms(self) -> int:
        """Return the Redis server clock in epoch milliseconds."""
        seconds, microseconds = await self.connection.time()
        return seconds * 1000 + microseconds // 1000

    async def _schedule_delayed(
        self, stream: str, fields: dict[FieldT, EncodableT], delay: MessageTTL, maxlen: int | None
    ) -> None:
        """Persist a message for delivery once its delay elapses.

        The entry lives in a sorted set scored by its due time, so a pending
        delay survives the scheduling process; whichever worker scans the
        queue first after the due time delivers it.
        """
        entry: dict[str, Any] = {
            # A unique id keeps identical payloads scheduled at different
            # times from collapsing into a single sorted set member, and
            # keys the entry's delivery-attempt counter.
            "id": str(UUIDT()),
            "stream": stream,
            "fields": {key: value.decode() if isinstance(value, bytes) else value for key, value in fields.items()},
        }
        if maxlen is not None:
            entry["maxlen"] = maxlen
        due_time = await self._server_time_ms() + delay.value
        await self.connection.zadd(self.delayed_queue, {ujson.dumps(entry): due_time})

    async def _deliver_delayed_messages(self) -> None:
        """Re-publish scheduled messages whose delay has elapsed, until shutdown."""
        while not self._shutdown_event.is_set():
            try:
                retried, dead = await self._deliver_due_script(
                    keys=[self.delayed_queue, self.delayed_attempts, self.delayed_dead_letter],
                    args=[
                        await self._server_time_ms(),
                        self.DELAYED_DELIVERY_BATCH,
                        self.DELAYED_RETRY_DELAY_MS,
                        self.DELAYED_MAX_ATTEMPTS,
                        self.DELAYED_DEAD_LETTER_MAXLEN,
                    ],
                )
                if retried:
                    get_logger().warning(
                        "Failed to deliver delayed messages, retrying after a delay", count=len(retried)
                    )
                if dead:
                    get_logger().error("Parked undeliverable delayed messages in the dead-letter list", count=len(dead))
            except asyncio.CancelledError:
                break
            except redis.RedisError:
                get_logger().exception("Redis error delivering delayed messages")
            # Worker loop boundary: an unexpected error must not stop the delivery of delayed messages.
            except Exception:  # noqa: BLE001
                get_logger().exception("Unexpected error delivering delayed messages")
            await asyncio.sleep(self.DELAYED_POLL_INTERVAL)

    async def publish(
        self,
        message: InfrahubMessage,
        routing_key: str,
        delay: MessageTTL | None = None,
        is_retry: bool = False,
    ) -> None:
        """Publish a message to the appropriate stream.

        Args:
            message: The message to publish.
            routing_key: The routing key for the message.
            delay: Optional delay before message delivery; a delayed broadcast event is dropped.
            is_retry: Whether this is a retry of a previously failed message.

        """
        with trace.get_tracer(__name__).start_as_current_span("publish_message") as span:
            span.set_attribute("routing_key", routing_key)

            stream = self._get_stream_for_routing_key(routing_key)
            if delay and stream == self.events_stream:
                # Every worker reads the events stream, so each worker that fails a delayed event would multiply it.
                get_logger().warning(
                    "Dropping the delayed delivery of a broadcast event", routing_key=routing_key, is_retry=is_retry
                )
                return

            for enricher in self.message_enrichers:
                await enricher(message)
            message.assign_priority(priority=messages.message_priority(routing_key=routing_key))

            maxlen = self.EVENTS_STREAM_MAXLEN if stream == self.events_stream else None

            fields: dict[FieldT, EncodableT] = {
                "routing_key": routing_key,
                "body": message.body,
                "headers": ujson.dumps(self._build_headers(message)),
                "priority": str(message.meta.priority or 0),
            }
            if delay:
                await self._schedule_delayed(stream=stream, fields=fields, delay=delay, maxlen=maxlen)
            elif maxlen is not None:
                await self.connection.xadd(stream, fields, maxlen=maxlen, approximate=True)
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

    @staticmethod
    def _build_headers(message: InfrahubMessage) -> dict[str, str]:
        """Return the headers of a stream entry, carrying the message metadata and the trace context."""
        headers: dict[str, str] = {}
        if message.meta.correlation_id:
            headers["correlation_id"] = message.meta.correlation_id
        if message.meta.reply_to:
            headers["reply_to"] = message.meta.reply_to
        if message.meta.expiration:
            headers["expiration"] = str(message.meta.expiration)
        if message.meta.headers:
            for key, value in message.meta.headers.items():
                if value:
                    headers[key] = str(value)

        if is_instrumentation_enabled():
            propagate.inject(headers)
        return headers

    async def reply(self, message: InfrahubMessage, routing_key: str) -> None:
        """Send a reply message to a callback stream.

        Args:
            message: The reply message to send.
            routing_key: The callback stream name (from message.meta.reply_to).

        """
        await self.connection.xadd(
            routing_key,
            {
                "routing_key": routing_key,
                "body": message.body,
                "headers": ujson.dumps(self._build_headers(message)),
            },
        )
        # Renewed with the same expiry the stream's owner keeps renewing, so a reply never shortens it.
        await self.connection.expire(routing_key, self.CALLBACK_STREAM_TTL)

    async def rpc(
        self,
        message: InfrahubMessage,
        response_class: type[ResponseClass],
        timeout: float | None = None,  # noqa: ASYNC109 part of the published bus contract
    ) -> ResponseClass:
        """Make an RPC call and wait for the response.

        Args:
            message: The RPC request message.
            response_class: The expected response class type.
            timeout: Seconds to wait for the reply; the configured RPC timeout when None.

        Returns:
            The deserialized response object.

        """
        response: dict = await self._publish_and_await_reply(
            message=message, reply_to=self.callback_stream, timeout=timeout
        )
        body = response.get("body", b"")
        if isinstance(body, bytes):
            body = body.decode()
        data = ujson.loads(body)
        return response_class(**data)

    async def listen(self, topic: str, listener: MessageListener) -> None:
        """Pass every message published from now on whose routing key matches the AMQP `topic` to `listener`.

        Reading the work queue stream without its consumer group leaves the group's deliveries unchanged.
        """

        async def forward(message_data: dict) -> None:
            data = self._decode_message_data(message_data)
            routing_key = data.get("routing_key", "")
            if topic_matches(topic, routing_key):
                body = data.get("body", "")
                await listener(routing_key, body.encode() if isinstance(body, str) else body)

        for stream in (self.events_stream, self.rpcs_stream):
            start_id = await self._get_last_stream_id(stream)
            subscription = StreamSubscription(stream=stream, consumer="listener", callback=forward, start_id=start_id)
            self._consumer_tasks.append(asyncio.create_task(self._consume_stream(subscription)))
