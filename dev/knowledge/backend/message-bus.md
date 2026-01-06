# Message Bus

> Part of: `dev/knowledge/backend/` | Related: [ADR-0004](../../adr/0004-message-bus.md), [Creating Messages Guide](../../guides/backend/creating-messages.md)

Infrahub uses a message bus (RabbitMQ or NATS) for asynchronous inter-component communication, focusing on broadcast notifications and rapid-response RPC operations.

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

## Key Locations

| Component | Location |
|-----------|----------|
| Base classes | `backend/infrahub/message_bus/__init__.py` |
| Message definitions | `backend/infrahub/message_bus/messages/` |
| Message registry | `backend/infrahub/message_bus/messages/__init__.py` |
| Operation handlers | `backend/infrahub/message_bus/operations/` |
| Types and enums | `backend/infrahub/message_bus/types.py` |

## See Also

- [ADR-0004: Message Bus Architecture](../../adr/0004-message-bus.md) - Why we use a message bus
- [Creating Messages Guide](../../guides/backend/creating-messages.md) - How to create a new message
- [Async Tasks](async-tasks.md) - Preferred method for most async operations
- [Events System](events.md) - Event system (uses message bus internally)
