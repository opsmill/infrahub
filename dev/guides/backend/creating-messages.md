# Creating Messages

> Part of: `dev/guides/backend/` | Related: [Message Bus Knowledge](../../knowledge/backend/message-bus.md), [ADR-0004](../../adr/0004-message-bus.md)

Step-by-step guide for creating a new message in the Infrahub message bus.

## When to Create a Message

Create a new message when you need to:

- Broadcast notifications to all workers (e.g., cache invalidation)
- Perform rapid RPC operations that cannot wait for workflow execution
- Communicate between components without direct dependencies

**Consider using a Prefect workflow instead** if:

- The operation is long-running
- Users should see execution status in the UI
- The operation modifies the database
- You need observability and logging

See [Async Tasks Knowledge](../../knowledge/backend/async-tasks.md) for workflow creation.

## Prerequisites

- Understanding of Pydantic models
- Familiarity with the message bus (see [Message Bus Knowledge](../../knowledge/backend/message-bus.md))
- Knowledge of whether you need broadcast or RPC pattern

## Steps

### Step 1: Choose the Message Pattern

| Pattern | Use When | Needs Response Class |
|---------|----------|---------------------|
| Broadcast | Notify all workers | No |
| RPC | Need a response | Yes |

### Step 2: Create the Message File

Create a new file in `backend/infrahub/message_bus/messages/`:

```python
# backend/infrahub/message_bus/messages/my_domain_action.py
from pydantic import Field

from infrahub.message_bus import InfrahubMessage

ROUTING_KEY = "my.domain.action"


class MyDomainAction(InfrahubMessage):
    """Description of when this message is sent."""

    resource_id: str = Field(..., description="The ID of the resource")
    action_type: str = Field(..., description="The type of action")
```

**Naming conventions:**

- Routing key: `<domain>.<subdomain>.<action>` using lowercase with dots
- Class name: PascalCase matching the action (e.g., `GitFileGet`, `RefreshRegistryBranches`)
- Include a docstring describing when the message is sent

### Step 3: Add Response Class (RPC Only)

For RPC messages that expect a response:

```python
from infrahub.message_bus import InfrahubMessage, InfrahubResponse, InfrahubResponseData

ROUTING_KEY = "my.domain.action"


class MyDomainAction(InfrahubMessage):
    """Request to perform an action."""
    resource_id: str = Field(..., description="The resource ID")


class MyDomainActionResponseData(InfrahubResponseData):
    result: str | None = None
    error_message: str | None = None


class MyDomainActionResponse(InfrahubResponse):
    routing_key: str = ROUTING_KEY
    data: MyDomainActionResponseData
```

### Step 4: Register the Message

Add your message to `backend/infrahub/message_bus/messages/__init__.py`:

```python
from .my_domain_action import MyDomainAction, MyDomainActionResponse  # if RPC

MESSAGE_MAP: dict[str, type[InfrahubMessage]] = {
    # ... existing messages
    "my.domain.action": MyDomainAction,
}

# For RPC messages only:
RESPONSE_MAP: dict[str, type[InfrahubResponse]] = {
    # ... existing responses
    "my.domain.action": MyDomainActionResponse,
}
```

### Step 5: Create the Operation Handler

Create or add to a handler file in `backend/infrahub/message_bus/operations/`:

```python
# backend/infrahub/message_bus/operations/my_domain/__init__.py
from infrahub.message_bus import messages
from infrahub.worker import WORKER_IDENTITY
from infrahub.workers.dependencies import get_database


async def action(message: messages.MyDomainAction) -> None:
    # For broadcast messages: check initiator to prevent loops
    if message.meta and message.meta.initiator_id == WORKER_IDENTITY:
        return

    database = await get_database()
    async with database.start_session() as db:
        # Process the message
        pass
```

For RPC handlers that return a response:

```python
async def action(message: messages.MyDomainAction) -> messages.MyDomainActionResponse:
    database = await get_database()
    async with database.start_session() as db:
        result = await perform_action(db, message.resource_id)

    return messages.MyDomainActionResponse(
        routing_key=messages.ROUTING_KEY,
        data=messages.MyDomainActionResponseData(result=result),
    )
```

### Step 6: Register the Handler

Add your handler to the operations registry in `backend/infrahub/message_bus/operations/__init__.py`.

## Complete Example: Broadcast Message

```python
# backend/infrahub/message_bus/messages/refresh_my_cache.py
from infrahub.message_bus import InfrahubMessage


class RefreshMyCache(InfrahubMessage):
    """Sent to indicate that the cache should be refreshed."""
    pass
```

```python
# backend/infrahub/message_bus/messages/__init__.py
from .refresh_my_cache import RefreshMyCache

MESSAGE_MAP: dict[str, type[InfrahubMessage]] = {
    # ...
    "refresh.my.cache": RefreshMyCache,
}
```

```python
# backend/infrahub/message_bus/operations/refresh/cache.py
from infrahub.message_bus import messages
from infrahub.worker import WORKER_IDENTITY


async def my_cache(message: messages.RefreshMyCache) -> None:
    if message.meta and message.meta.initiator_id == WORKER_IDENTITY:
        return  # Ignore own messages

    # Refresh the cache
    await refresh_cache()
```

## Complete Example: RPC Message

```python
# backend/infrahub/message_bus/messages/get_resource_info.py
from pydantic import Field

from infrahub.message_bus import InfrahubMessage, InfrahubResponse, InfrahubResponseData

ROUTING_KEY = "resource.info.get"


class GetResourceInfo(InfrahubMessage):
    """Request information about a resource."""
    resource_id: str = Field(..., description="The resource ID")


class GetResourceInfoResponseData(InfrahubResponseData):
    name: str | None = None
    status: str | None = None
    error_message: str | None = None


class GetResourceInfoResponse(InfrahubResponse):
    routing_key: str = ROUTING_KEY
    data: GetResourceInfoResponseData
```

## Quality Checklist

Before submitting your message:

- [ ] Message class extends `InfrahubMessage`
- [ ] Routing key uses lowercase with dots (`domain.subdomain.action`)
- [ ] All fields use `Field()` with descriptions
- [ ] Docstring describes when the message is sent
- [ ] Message registered in `MESSAGE_MAP`
- [ ] Response registered in `RESPONSE_MAP` (RPC only)
- [ ] Operation handler created
- [ ] Broadcast handler checks `initiator_id` to prevent loops
- [ ] Code passes `uv run invoke lint`

## Related Resources

- [Message Bus Knowledge](../../knowledge/backend/message-bus.md) - How the message bus works
- [ADR-0004: Message Bus Architecture](../../adr/0004-message-bus.md) - Architectural decision
- [Async Tasks Knowledge](../../knowledge/backend/async-tasks.md) - Preferred for most async operations
- [Python Coding Standards](../../guidelines/backend/python.md) - Code style requirements
