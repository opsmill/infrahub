# Message Bus

> Part of: `dev/knowledge/backend/` | Related: [ADR-0004](../../adr/0004-message-bus.md), [Creating Messages Guide](../../guides/backend/creating-messages.md)

Infrahub uses a message bus (RabbitMQ or Redis Streams) for asynchronous inter-component communication, focusing on broadcast notifications and rapid-response RPC operations.

## When to Use Message Bus vs Workflows

| Scenario | Use Message Bus | Use Workflow |
|----------|-----------------|--------------|
| Notify all workers (broadcast) | Yes | No |
| Rapid response required | Yes | No |
| Long-running operation | No | Yes |
| User-visible in UI | No | Yes |
| Database modifications | Avoid | Yes |
| Needs observability | No | Yes |

Most asynchronous operations should use Prefect workflows (see [Async Tasks](async-tasks.md)). The message bus is reserved for:

- **Broadcasts**: Registry refresh, cache invalidation
- **Rapid RPC**: Git file retrieval, connectivity checks

## Message Patterns

### Broadcast Messages

One-to-many distribution where all workers process the message:

```text
Sender ──► Message Bus ──► Worker 1
                      ├──► Worker 2
                      └──► Worker 3
```

Workers ignore messages they originated (via `initiator_id` check) to prevent loops.

A broadcast message is never delivered with a delay, so a failed broadcast is not retried. Both drivers drop it: RabbitMQ's dead-letter exchange routes only work-queue keys, and the Redis driver logs a warning instead of scheduling it. A delayed broadcast would reach every worker again, and each worker that failed it would publish another retry.

**Examples**: `RefreshRegistryBranches`, `RefreshGitFetch`

### Request/Reply (RPC)

Synchronous-style calls where a response is expected:

```text
Sender ──► Message Bus ──► Worker
   ▲                         │
   └─── Response ◄───────────┘
```

Responses are correlated using `correlation_id` in message metadata.

**Examples**: `GitFileGet` → `GitFileGetResponse`

#### Every RPC call is bounded

`rpc()` never waits indefinitely. Both the publish and the wait for the reply run under a single
timeout, so a broker that withholds its publish confirmation is bounded the same way a worker that
never answers is. The bound defaults to `INFRAHUB_BROKER_RPC_TIMEOUT` (120 seconds, minimum 1); an
individual call can override it with `timeout=`. The default leaves room for a worker without a
local copy to clone the repository before it answers a file fetch.

When the bound elapses, `rpc()` raises `WorkerTimeoutError`. Callers must decide what that means for
their operation. The GraphQL layer surfaces it as HTTP 504 with the `WORKER_TIMEOUT` error code and
a `retry_after_seconds` hint. A caller that has already written to the database before the RPC is
responsible for undoing that write, because the creating mutations do not run in a transaction: see
`RepositoryFinalizer.post_create`, which removes the repository before re-raising so the name is not
left taken by a repository that was never cloned.

## Message Structure

### Base Message

All messages extend `InfrahubMessage`:

```python
from infrahub.message_bus import InfrahubMessage

class RefreshRegistryBranches(InfrahubMessage):
    """Sent to indicate that the registry should be refreshed."""
    pass
```

### Message with Fields

Messages use Pydantic fields for typed parameters:

```python
from pydantic import Field
from infrahub.message_bus import InfrahubMessage

class GitFileGet(InfrahubMessage):
    """Read a file from a Git repository."""
    commit: str = Field(..., description="The commit id")
    file: str = Field(..., description="The path and filename")
    repository_id: str = Field(..., description="The repository ID")
```

### Response Messages

RPC responses extend `InfrahubResponse`:

```python
from infrahub.message_bus import InfrahubResponse, InfrahubResponseData

class GitFileGetResponseData(InfrahubResponseData):
    content: str | None = None
    error_message: str | None = None

class GitFileGetResponse(InfrahubResponse):
    routing_key: str = "git.file.get"
    data: GitFileGetResponseData
```

## Message Metadata

The `Meta` class provides message metadata:

| Field | Purpose |
|-------|---------|
| `request_id` | Correlation with HTTP request |
| `correlation_id` | RPC response correlation |
| `initiator_id` | Worker that sent the message (loop prevention) |
| `retry_count` | Number of retry attempts |
| `priority` | Message priority (1-5, default 3) |
| `expiration` | TTL in seconds |
| `reply_to` | Queue for RPC response |

## Routing Keys

Messages are mapped to routing keys in `MESSAGE_MAP`:

```python
MESSAGE_MAP: dict[str, type[InfrahubMessage]] = {
    "git.file.get": GitFileGet,
    "refresh.registry.branches": RefreshRegistryBranches,
}
```

Routing key convention: `<domain>.<subdomain>.<action>` using lowercase with dots.

## Operation Handlers

Handlers process incoming messages in `message_bus/operations/`:

```python
async def branches(message: messages.RefreshRegistryBranches) -> None:
    if message.meta and message.meta.initiator_id == WORKER_IDENTITY:
        return  # Ignore own messages

    database = await get_database()
    async with database.start_session() as db:
        await refresh_branches(db=db)
```

Handlers:

- Check `initiator_id` for broadcast messages (loop prevention)
- Use dependency injection for services
- Return nothing for broadcasts, or response object for RPC

## RabbitMQ Queue Types

Declare a durable queue with the arguments from `infrahub/services/adapters/message_bus/rabbitmq.py::_durable_queue_arguments`, never with a fixed `x-queue-type` or `x-max-priority`: quorum queues reject `x-max-priority`, and a fixed type breaks the deployments that use the other one.

- **Durable queues** (`<namespace>.rpcs`, `<namespace>.delay.*_seconds`) take their type from `broker.queue_type`: classic by default, quorum on a RabbitMQ cluster, where RabbitMQ replicates them across nodes.
- **Per-process queues** (`api-*`, `worker-*`) stay classic: they are exclusive to one connection, which quorum queues cannot be, and the process declares them again when it reconnects.
- **Changing the type** requires deleting the durable queues first: RabbitMQ refuses a redeclaration with other arguments (`PRECONDITION_FAILED`), so the server does not start. The procedure is in the high availability deployment docs.

## Redis Driver Connection

Build the Redis driver's client with `build_broker_redis_connection` from `infrahub/redis_connection.py`, never with `redis.Redis(...)`: it shares the cache's URL handling, so the client accepts Sentinel URLs, retries connection errors and follows a failover.

- **Settings**: `broker.url` (`INFRAHUB_BROKER_URL`) supersedes `address`, `port`, `username`, `password`, `tls_enabled` and `tls_insecure`. Without it, these settings build a single-node URL on database 0. A `username` or `password` left at its default is not sent, because that default is the RabbitMQ default user (`infrahub`/`infrahub`), which a Redis server does not have. The settings fail to load when the URL is set with a driver other than `redis`.
- **Closing**: close the client with `prefect_redis.connection.aclose_redis_client`, which also closes a Sentinel client's connections to the Sentinel nodes.
- **After a failover**: a connection that only reads (the `XREAD` of the events and callback streams) stays on the demoted master, now a replica, until it fails, and still receives new entries through replication. A connection that sends a write command, `XREADGROUP` included, gets `READONLY` from the replica and reconnects to the promoted master.

## Redis Driver Message Handling

The Redis driver requires Redis 6.2 or later, for `XAUTOCLAIM` and `XTRIM MINID`.

- **Concurrency**: each entry is handled in a task of its own, as the RabbitMQ client library (aiormq) does for each delivery. A task worker reads the work queue only while fewer than `broker.maximum_concurrent_messages` of its work items are running, so the entries it cannot start yet stay with the group for other workers. Events and RPC replies have no limit, as on RabbitMQ.
- **Maintenance**: once a minute, a worker claims the work queue entries left pending for 30 minutes, trims the entries the group is done with, and deletes the consumers that hold no pending entry and have read nothing for 30 minutes, which belong to workers that stopped without their shutdown cleanup. A failing maintenance step is retried at the next pass and does not stop the reads.
- **Listening**: `listen()` reads the events stream and the work queue stream with `XREAD` from their current ends, which leaves the group's deliveries unchanged.

## Key Locations

| Component | Location |
|-----------|----------|
| Base classes | `backend/infrahub/message_bus/__init__.py` |
| Message definitions | `backend/infrahub/message_bus/messages/` |
| Message registry | `backend/infrahub/message_bus/messages/__init__.py` |
| Operation handlers | `backend/infrahub/message_bus/operations/` |
| Types and enums | `backend/infrahub/message_bus/types.py` |
| Redis client for the Redis driver and the cache | `backend/infrahub/redis_connection.py` |

## See Also

- [ADR-0004: Message Bus Architecture](../../adr/0004-message-bus.md) - Why we use a message bus
- [Creating Messages Guide](../../guides/backend/creating-messages.md) - How to create a new message
- [Async Tasks](async-tasks.md) - Preferred method for most async operations
- [Events System](events.md) - Event system (uses message bus internally)
