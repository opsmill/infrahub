# ADR-0009: Events System

## Status

Draft

## Context

Infrahub needs a robust event-driven architecture to enable reactive workflows, automation, and decoupled component communication. Events need to be:

- Emitted when state changes occur (node mutations, branch operations, schema updates)
- Queryable and filterable for debugging and monitoring
- Capable of triggering automated actions and workflows
- Rich in metadata to enable complex filtering and routing

The system must integrate with our existing Prefect-based task execution infrastructure (see ADR-0006) and message bus architecture (see ADR-0005).

## Decision

We use **Prefect Events** as the foundation for our event system, leveraging Prefect's built-in event storage, querying capabilities, and **Prefect Automation** to trigger workflows based on event patterns.

### Architecture Overview

1. **Event Emission**: Events are emitted using Prefect's `emit_event()` function through the `InfrahubEventService` adapter
2. **Event Storage**: Events are stored in Prefect's database and queryable via a custom API endpoint
3. **Event Triggering**: Prefect Automations match events using filters and trigger Prefect workflows (deployments)
4. **Event Metadata**: Events include rich resource and related resource metadata for flexible filtering

### Event Structure

Events follow Prefect's event model with:

- **Event Name**: Namespaced under `infrahub.*` (e.g., `infrahub.node.created`)
- **Resource**: Primary resource identifier with metadata (node ID, kind, branch, etc.)
- **Related Resources**: Additional context (account, branch, parent events, related nodes, etc.)
- **Payload**: Event-specific data including changelog information

### Integration Points

- **Message Bus**: Events can also send messages to the message bus for synchronous component communication
- **GraphQL API**: Events are queryable via GraphQL with filtering capabilities
- **Workflows**: Events trigger Prefect workflows that execute actions (generators, group operations, etc.)

## Consequences

### Positive

- Leverages Prefect's mature event infrastructure
- Built-in event storage and querying
- Powerful filtering capabilities via Prefect Automation
- Integration with existing Prefect workflow system
- Rich metadata enables complex event matching
- Event history and audit trail
- Parent-child event relationships for tracking event chains

### Negative

- Tight coupling to Prefect infrastructure
- Events stored in Prefect database (additional storage requirements)
- Learning curve for Prefect Automation concepts
- Requires Prefect server to be running
- Event querying depends on Prefect API availability

## Notes

### Event Types

Events are defined in `backend/infrahub/events/`:

- **Node Events**: `NodeCreatedEvent`, `NodeUpdatedEvent`, `NodeDeletedEvent` - emitted on node mutations
- **Group Events**: `GroupMemberAddedEvent`, `GroupMemberRemovedEvent` - emitted on group membership changes
- **Branch Events**: `BranchCreatedEvent`, `BranchDeletedEvent`, `BranchMergedEvent`, etc.
- **Schema Events**: `SchemaUpdatedEvent` - emitted on schema changes
- **Proposed Change Events**: Various events for proposed change lifecycle
- **Artifact Events**: `ArtifactCreatedEvent`, `ArtifactUpdatedEvent`
- **Validator Events**: `ValidatorStartedEvent`, `ValidatorPassedEvent`, `ValidatorFailedEvent`

### Event Emission

Events are emitted through `InfrahubEventService` (`backend/infrahub/services/adapters/event/__init__.py`):

```python
async def send(self, event: InfrahubEvent) -> None:
    tasks = [self._send_bus(event=event), self._send_prefect(event=event)]
    await asyncio.gather(*tasks)

async def _send_prefect(self, event: InfrahubEvent) -> None:
    emit_event(
        id=event.meta.id,
        event=event.event_name,
        resource=event.get_resource(),
        related=event.get_related(),
        payload=event.get_event_payload(),
    )
```

### Dual Event Channels: Message Bus vs Prefect Events

Infrahub uses two distinct event channels with different purposes:

#### 1. Message Bus Events (RabbitMQ/NATS) - Internal Operations

**Purpose**: Internal, operational messages for specific tasks and broadcast-type communication between Infrahub components.

**Characteristics:**

- **Legacy system**: Part of the original message bus architecture (see ADR-0005)
- **Point-to-point or broadcast**: Used for direct component-to-component communication
- **Specific tasks**: Triggers specific internal operations like:
  - Git repository synchronization (`RefreshRegistryBranches`)
  - Registry updates (`RefreshRegistryRebasedBranch`)
  - Git file operations (`GitFileGet`)
- **Not all events**: Only certain events send messages via `get_messages()` method
- **Operational focus**: Primarily for infrastructure-level operations

**Example**: When a branch is created, `BranchCreatedEvent` sends a `RefreshRegistryBranches` message to update the git registry, but also emits a Prefect event for automation triggers.

```python
class BranchCreatedEvent(InfrahubEvent):
    def get_messages(self) -> list[InfrahubMessage]:
        return [RefreshRegistryBranches()]  # Internal operational message
```

#### 2. Prefect Events - User-Visible Automation

**Purpose**: User-visible events that are part of the automation and trigger system.

**Characteristics:**

- **All events**: Every `InfrahubEvent` is sent to Prefect
- **Queryable**: Events are stored in Prefect database and queryable via GraphQL/REST APIs
- **Automation triggers**: Used by Prefect Automation to trigger workflows based on event patterns
- **Rich metadata**: Includes resource and related resource metadata for flexible filtering
- **Audit trail**: Provides event history and observability
- **User-facing**: Events represent user actions and state changes visible in the UI

**Example**: A `NodeCreatedEvent` is always sent to Prefect, enabling:

- Querying via GraphQL: `query { events(filter: { event: { name: ["infrahub.node.created"] } }) { ... } }`
- Triggering workflows: Prefect Automation can match the event and run generators, group actions, etc.
- Event history: Users can see when nodes were created

**Key Difference**: Message bus events are for **internal operational tasks** (like refreshing caches, syncing git), while Prefect events are for **user-visible automation and observability**.

### Prefect Automation Setup

Trigger definitions (`backend/infrahub/trigger/models.py`) define:

- **EventTrigger**: Event patterns to match (event names, resource filters, related resource filters)
- **ExecuteWorkflow**: Workflow to execute when matched, with Jinja2 templated parameters

Example trigger definition (`backend/infrahub/actions/triggers.py`):

```python
TRIGGER_ACTION_RULE_UPDATE = BuiltinTriggerDefinition(
    name="action-trigger-setup-all",
    trigger=EventTrigger(
        events={NodeCreatedEvent.event_name, NodeDeletedEvent.event_name, NodeUpdatedEvent.event_name},
        match={"infrahub.node.kind": NODES_THAT_TRIGGER_ACTION_RULES_SETUP},
    ),
    actions=[
        ExecuteWorkflow(
            workflow=CONFIGURE_ACTION_RULES,
            parameters={},
        ),
    ],
)
```

Triggers are registered with Prefect via `setup_triggers()` (`backend/infrahub/trigger/setup.py`), which:

1. Creates or updates Prefect Automations
2. Maps workflow names to Prefect deployment IDs
3. Handles trigger lifecycle (create, update, delete)

### Event Querying

Events are queryable via:

- **GraphQL API**: `Events` query with filtering (`backend/infrahub/graphql/queries/event.py`)
- **REST API**: Custom endpoint `/infrahub/events/filter` (`backend/infrahub/prefect_server/events.py`)
- **Prefect Client**: Direct querying via Prefect's event API

Event filtering uses `InfrahubEventFilter` which extends Prefect's `EventFilter` with Infrahub-specific prefixes.

### Example: Node Mutation Event

When a node is created/updated/deleted (`backend/infrahub/events/node_action.py`):

```python
class NodeCreatedEvent(NodeMutatedEvent):
    event_name: ClassVar[str] = f"{EVENT_NAMESPACE}.node.created"
    action: MutationAction = MutationAction.CREATED

    def get_resource(self) -> dict[str, str]:
        return {
            "prefect.resource.id": f"infrahub.node.{self.node_id}",
            "infrahub.node.kind": self.kind,
            "infrahub.node.id": self.node_id,
            "infrahub.node.action": self.action.value,
            "infrahub.branch.name": self.meta.context.branch.name,
        }
```

The event includes related resources for:

- Attribute changes (with old/new values)
- Relationship changes (added/removed peers)
- Parent nodes
- Related nodes

### Example: HFID Trigger

Human-friendly ID computation triggered by schema updates (`backend/infrahub/hfid/triggers.py`):

```python
TRIGGER_HFID_ALL_SCHEMA = BuiltinTriggerDefinition(
    name="hfid-setup-all",
    trigger=EventTrigger(events={SchemaUpdatedEvent.event_name, BranchDeletedEvent.event_name}),
    actions=[
        ExecuteWorkflow(
            workflow=HFID_SETUP,
            parameters={
                "branch_name": "{{ event.resource['infrahub.branch.name'] }}",
                "event_name": "{{ event.event }}",
                "context": {
                    "__prefect_kind": "json",
                    "value": {"__prefect_kind": "jinja", "template": "{{ event.payload['context'] | tojson }}"},
                },
            },
        ),
    ],
)
```

### Event Metadata Structure

Events include comprehensive metadata:

- **Event ID**: UUID for event identification
- **Parent Events**: Support for event hierarchies
- **Branch Context**: Branch name and ID
- **Account Context**: Account ID of the initiator
- **Level**: Event nesting level
- **Request ID**: Correlation ID for request tracking

### Related ADRs

- ADR-0005: Message Bus Architecture (events also send messages to message bus)
- ADR-0006: Asynchronous Tasks Execution (events trigger Prefect workflows)
- ADR-0008: Pydantic Models (events use Pydantic for validation)

### Implementation Files

- Event definitions: `backend/infrahub/events/`
- Event service adapter: `backend/infrahub/services/adapters/event/`
- Trigger models: `backend/infrahub/trigger/models.py`
- Trigger setup: `backend/infrahub/trigger/setup.py`
- Prefect server integration: `backend/infrahub/prefect_server/`
- Event querying: `backend/infrahub/task_manager/event.py`
- GraphQL queries: `backend/infrahub/graphql/queries/event.py`
