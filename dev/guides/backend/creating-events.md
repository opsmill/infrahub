# Creating Events

> Part of: `dev/guides/backend/` | Related: [Events Knowledge](../../knowledge/backend/events.md), [ADR-0002](../../adr/0002-events-system.md)

Step-by-step guide for creating a new event in the Infrahub events system.

## When to Create an Event

Create a new event when you need to:

- Notify external systems or automations about state changes
- Provide audit trails for user-visible operations
- Trigger Prefect workflows based on specific conditions
- Enable users to build automations on specific actions

If you only need internal message passing without user visibility, consider using the message bus directly instead.

## Prerequisites

- Understanding of Pydantic models and Field definitions
- Familiarity with the events system (see [Events Knowledge](../../knowledge/backend/events.md))
- Knowledge of which domain your event belongs to (node, branch, schema, etc.)

## Steps

### Step 1: Choose the Event Location

Determine which file your event belongs in based on its domain:

| Domain | File |
|--------|------|
| Node operations | `backend/infrahub/events/node_action.py` |
| Branch operations | `backend/infrahub/events/branch_action.py` |
| Group operations | `backend/infrahub/events/group_action.py` |
| Schema operations | `backend/infrahub/events/schema_action.py` |
| New domain | Create `backend/infrahub/events/<domain>_action.py` |

### Step 2: Define the Event Class

Create a class that extends `InfrahubEvent`:

```python
from typing import ClassVar

from pydantic import Field

from .constants import EVENT_NAMESPACE
from .models import InfrahubEvent


class MyDomainActionEvent(InfrahubEvent):
    """Event generated when a specific action occurs"""

    event_name: ClassVar[str] = f"{EVENT_NAMESPACE}.domain.action"

    # Add event-specific fields
    resource_id: str = Field(..., description="The ID of the affected resource")
    action_type: str = Field(..., description="The type of action performed")
```

Key requirements:

- Extend `InfrahubEvent`
- Set `event_name` as a `ClassVar[str]` following the pattern `infrahub.<domain>.<action>`
- Add fields using Pydantic `Field()` with descriptions
- Include a docstring describing when this event is generated

### Step 3: Implement get_resource()

The `get_resource()` method returns the primary resource metadata for Prefect:

```python
def get_resource(self) -> dict[str, str]:
    return {
        "prefect.resource.id": f"infrahub.domain.{self.resource_id}",
        "infrahub.domain.id": self.resource_id,
        "infrahub.domain.action": self.action_type,
    }
```

Requirements:

- Must include `prefect.resource.id` as a unique identifier
- Add any domain-specific attributes needed for filtering
- All values must be strings

### Step 4: Override get_related() (Optional)

Override `get_related()` to add additional context resources:

```python
def get_related(self) -> list[dict[str, str]]:
    related = super().get_related()  # Include base related resources

    # Add custom related resources
    related.append({
        "prefect.resource.id": self.related_resource_id,
        "prefect.resource.role": "infrahub.related.custom",
        "infrahub.custom.attribute": self.custom_value,
    })

    return related
```

Common patterns:

- Always call `super().get_related()` first to include account, branch, and event metadata
- Use `prefect.resource.role` to categorize the relationship
- Add domain-specific attributes for filtering

### Step 5: Override get_messages() (Optional)

Override `get_messages()` if your event should trigger internal message bus operations:

```python
from infrahub.message_bus import InfrahubMessage
from infrahub.message_bus.messages.some_message import SomeMessage


def get_messages(self) -> list[InfrahubMessage]:
    return [
        SomeMessage(
            resource_id=self.resource_id,
            meta=self.get_message_meta(),
        ),
    ]
```

Use this when the event should trigger:

- Registry refreshes
- Git synchronization
- Cache invalidation
- Other internal operations

### Step 6: Export the Event

Add your event to the module's `__init__.py` if creating a new file:

```python
# In backend/infrahub/events/__init__.py
from .domain_action import MyDomainActionEvent
```

### Step 7: Emit the Event

Emit your event from application code using `InfrahubEventService`:

```python
from infrahub.events.domain_action import MyDomainActionEvent
from infrahub.events.models import EventMeta


# Create event metadata from context
meta = EventMeta.from_context(context=infrahub_context, branch=branch)

# Create and emit the event
event = MyDomainActionEvent(
    meta=meta,
    resource_id="abc123",
    action_type="created",
)

await service.event.send(event=event)
```

## Complete Example

Here is a complete example based on `BranchCreatedEvent`:

```python
from typing import ClassVar

from pydantic import Field

from infrahub.message_bus import InfrahubMessage
from infrahub.message_bus.messages.refresh_registry_branches import RefreshRegistryBranches

from .constants import EVENT_NAMESPACE
from .models import InfrahubEvent


class BranchCreatedEvent(InfrahubEvent):
    """Event generated when a branch has been created"""

    event_name: ClassVar[str] = f"{EVENT_NAMESPACE}.branch.created"

    branch_name: str = Field(..., description="The name of the branch")
    branch_id: str = Field(..., description="The ID of the branch")
    sync_with_git: bool = Field(..., description="Indicates if the branch was extended to Git")

    def get_resource(self) -> dict[str, str]:
        return {
            "prefect.resource.id": f"infrahub.branch.{self.branch_name}",
            "infrahub.branch.id": self.branch_id,
            "infrahub.branch.name": self.branch_name,
        }

    def get_messages(self) -> list[InfrahubMessage]:
        return [RefreshRegistryBranches()]
```

## Quality Checklist

Before submitting your event:

- [ ] Event class extends `InfrahubEvent`
- [ ] `event_name` follows pattern `infrahub.<domain>.<action>`
- [ ] All fields use `Field()` with descriptions
- [ ] `get_resource()` includes `prefect.resource.id`
- [ ] All resource/related values are strings
- [ ] Docstring describes when event is generated
- [ ] Event is exported from module `__init__.py`
- [ ] Tests cover event creation and emission
- [ ] Code passes `uv run invoke lint`

## Related Resources

- [Events Knowledge](../../knowledge/backend/events.md) - How the event system works
- [ADR-0002: Prefect Events System](../../adr/0002-events-system.md) - Architectural decision
- [Python Coding Standards](../../guidelines/backend/python.md) - Code style requirements
