# ADR-0005: Message Bus Architecture

## Status

Draft

## Context

Infrahub requires asynchronous communication between components (API server, workers, git agents). Operations like git repository synchronization, cache invalidation, and registry updates need to happen asynchronously without blocking the main request flow.

## History

Historically, the message bus architecture was used for both task executions and broadcast messages to communicate between components. Around 1.0, most asynchronous task execution was migrated to Prefect (see ADR-0006). However, some tasks—especially those requiring very quick response times—were kept in the message bus architecture.

At some point, it may be worth considering consolidating the message bus infrastructure. Instead of relying on RabbitMQ, we could merge this functionality with existing components like NATS or Redis that are already part of the infrastructure stack.

## Decision

We use a message bus (RabbitMQ or NATS) for asynchronous inter-component communication. Messages are typed with Pydantic models, support request/reply patterns, and include retry logic. The message bus enables loose coupling between components and supports horizontal scaling.

## Consequences

### Positive

- Decoupled component communication
- Horizontal scaling of workers
- Asynchronous operation execution
- Request/reply patterns for RPC-like calls
- Retry logic handles transient failures
- Multiple message bus implementations supported

### Negative

- Additional infrastructure dependency
- Message ordering and delivery guarantees to consider
- Debugging distributed operations more complex
- Requires monitoring and observability
- Potential message loss if not configured correctly

## Implementation Guide

### Creating a New Broadcast Message Type

To create a new broadcast message, follow these steps:

#### 1. Define the Message Class

Create a new message class in `backend/infrahub/message_bus/messages/` that inherits from `InfrahubMessage`:

```python
from pydantic import Field
from infrahub.message_bus import InfrahubMessage

class RefreshGitFetch(InfrahubMessage):
    """Fetch a repository remote changes."""

    location: str = Field(..., description="The external URL of the repository")
    repository_id: str = Field(..., description="The unique ID of the repository")
    repository_name: str = Field(..., description="The name of the repository")
    repository_kind: str = Field(..., description="The type of repository")
    infrahub_branch_name: str = Field(..., description="Infrahub branch on which to sync the remote repository")
    infrahub_branch_id: str = Field(..., description="Id of the Infrahub branch on which to sync the remote repository")
```

#### 2. Register the Message

Add the message to the `MESSAGE_MAP` in `backend/infrahub/message_bus/messages/__init__.py`:

```python
from .refresh_git_fetch import RefreshGitFetch

MESSAGE_MAP: dict[str, type[InfrahubMessage]] = {
    "refresh.git.fetch": RefreshGitFetch,
    # ... other messages
}
```

The routing key follows a dot-separated pattern (e.g., `refresh.git.fetch`). Broadcast messages typically use patterns like `refresh.git.*` which are matched by `broadcasted_event_bindings`.

#### 3. Create the Operation Handler

Create an operation handler in `backend/infrahub/message_bus/operations/`:

```python
from prefect import flow
from infrahub.message_bus import messages
from infrahub.workers.dependencies import get_client, get_message_bus

@flow(name="refresh-git-fetch", flow_run_name="Fetch git repository {message.repository_name}")
async def fetch(message: messages.RefreshGitFetch) -> None:
    # Check if message originated from this worker to avoid loops
    if message.meta and message.meta.initiator_id == WORKER_IDENTITY:
        log.info("Ignoring git fetch request originating from self", worker=WORKER_IDENTITY)
        return

    # Perform the actual work
    repo = await get_initialized_repo(
        client=get_client(),
        repository_id=message.repository_id,
        name=message.repository_name,
        repository_kind=message.repository_kind,
    )

    await repo.fetch()
    await repo.pull(
        branch_name=message.infrahub_branch_name,
        branch_id=message.infrahub_branch_id,
        create_if_missing=True,
        update_commit_value=False,
    )
```

#### 4. Register the Operation Handler

Add the handler to `COMMAND_MAP` in `backend/infrahub/message_bus/operations/__init__.py`:

```python
from infrahub.message_bus.operations import git

COMMAND_MAP = {
    "refresh.git.fetch": git.repository.fetch,
    # ... other operations
}
```

#### 5. Send the Message

To send a broadcast message, create an instance and use the message bus:

```python
from infrahub.message_bus import Meta, messages
from infrahub.workers.dependencies import get_message_bus

message_bus = await get_message_bus()
notification = messages.RefreshGitFetch(
    meta=Meta(initiator_id=WORKER_IDENTITY, request_id=get_log_data().get("request_id", "")),
    location=model.location,
    repository_id=model.repository_id,
    repository_name=model.repository_name,
    repository_kind=InfrahubKind.REPOSITORY,
    infrahub_branch_name=model.infrahub_branch_name,
    infrahub_branch_id=model.infrahub_branch_id,
)
await message_bus.send(message=notification)
```

### Request/Reply Pattern (RPC)

For messages that require a response, use the RPC pattern:

#### 1. Define Request and Response Classes

```python
from infrahub.message_bus import InfrahubMessage, InfrahubResponse, InfrahubResponseData

ROUTING_KEY = "git.file.get"

class GitFileGet(InfrahubMessage):
    """Read a file from a Git repository."""

    commit: str = Field(..., description="The commit id to use to access the file")
    file: str = Field(..., description="The path and filename within the repository")
    repository_id: str = Field(..., description="The unique ID of the Repository")
    repository_name: str = Field(..., description="The name of the repository")
    repository_kind: str = Field(..., description="The kind of the repository")

class GitFileGetResponseData(InfrahubResponseData):
    content: str | None = None
    error_message: str | None = None
    http_code: int | None = None

class GitFileGetResponse(InfrahubResponse):
    routing_key: str = ROUTING_KEY
    data: GitFileGetResponseData
```

#### 2. Register Response Type

Add to `RESPONSE_MAP` in `backend/infrahub/message_bus/messages/__init__.py`:

```python
RESPONSE_MAP: dict[str, type[InfrahubResponse]] = {
    "git.file.get": GitFileGetResponse,
    # ... other responses
}
```

#### 3. Handle Reply in Operation

```python
async def get(message: messages.GitFileGet) -> None:
    message_bus = await get_message_bus()
    
    if message.reply_requested:
        try:
            content = await repo.get_file(commit=message.commit, location=message.file)
            response = GitFileGetResponse(data=GitFileGetResponseData(content=content))
        except Exception as e:
            response = GitFileGetResponse(
                data=GitFileGetResponseData(error_message=e.message, http_code=e.HTTP_CODE)
            )
        await message_bus.reply_if_initiator_meta(message=response, initiator=message)
```

#### 4. Make RPC Call

```python
message_bus = await get_message_bus()
request = messages.GitFileGet(
    commit="abc123",
    file="path/to/file.yaml",
    repository_id=repo_id,
    repository_name=repo_name,
    repository_kind=repo_kind,
)
response = await message_bus.rpc(message=request, response_class=messages.GitFileGetResponse)
```

### Key Implementation Details

- **Message Routing**: Routing keys use dot-separated patterns. Broadcast messages match patterns like `refresh.git.*` defined in `broadcasted_event_bindings`.

- **Message Metadata**: The `Meta` class includes:
  - `initiator_id`: Worker identity that sent the message (used to prevent loops)
  - `request_id`: For request correlation
  - `correlation_id`: For linking requests and responses
  - `retry_count`: Tracks retry attempts
  - `priority`: Message priority (1-5, default 3)
  - `expiration`: TTL in seconds

- **Retry Logic**: Messages automatically retry on failure with exponential backoff. Maximum retries are controlled by `config.SETTINGS.broker.maximum_message_retries`.

- **Error Handling**: If a message with `reply_requested=True` fails, an `RPCErrorResponse` is sent. After maximum retries, check status is set to "failure".

- **Prefect Integration**: Operations can be Prefect flows (decorated with `@flow`) or regular async functions. The `execute_message` function handles both.

- **Broadcast vs Direct**: 
  - Broadcast messages (`refresh.git.*`) are sent to all workers
  - Direct messages (`git.file.get`) are sent to a specific worker queue
  - Workers subscribe to patterns defined in `worker_bindings`, `event_bindings`, and `broadcasted_event_bindings`

## Notes

- Message types defined in `infrahub/message_bus/messages/`
- Operations handle messages in `infrahub/message_bus/operations/`
- Supports both RabbitMQ and NATS drivers
- Messages include metadata for correlation and retries
- Priority levels supported for message ordering
- Routing keys map to message classes via `MESSAGE_MAP` and `ROUTING_KEY_MAP`
- Operations are registered in `COMMAND_MAP` in `operations/__init__.py`

