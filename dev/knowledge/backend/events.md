# Events System

> Part of: `dev/knowledge/backend/` | Related: [ADR-0002](../../adr/0002-events-system.md), [Creating Events Guide](../../guides/backend/creating-events.md)

Infrahub uses a dual-channel event system that dispatches events to both the internal message bus and Prefect for automation and observability.

## Dual-Channel Architecture

When an event is emitted, it flows through two channels:

| Channel | Purpose | Storage | Use Case |
|---------|---------|---------|----------|
| Message Bus | Internal operations | Transient | Git sync, registry updates, file operations |
| Prefect Events | User-visible automation | Persistent | Automation triggers, audit trails, event history |

The `InfrahubEventService` adapter handles this dual dispatch via `asyncio.gather()`.

## Event Structure

All events extend `InfrahubEvent` from `backend/infrahub/events/models.py` and contain:

- **event_name**: Namespaced identifier (e.g., `infrahub.node.created`)
- **meta**: Metadata including branch, account, request ID, parent event
- **resource**: Primary resource being affected (returned by `get_resource()`)
- **related**: Additional context resources (returned by `get_related()`)
- **payload**: Event-specific data (returned by `get_event_payload()`)

## Event Types

Events are organized by domain in `backend/infrahub/events/`:

| Domain | Events | File |
|--------|--------|------|
| Node | `NodeCreatedEvent`, `NodeUpdatedEvent`, `NodeDeletedEvent` | `node_action.py` |
| Branch | `BranchCreatedEvent`, `BranchDeletedEvent`, `BranchMergedEvent`, `BranchRebasedEvent` | `branch_action.py` |
| Group | `GroupMemberAddedEvent`, `GroupMemberRemovedEvent` | `group_action.py` |
| Schema | `SchemaUpdatedEvent` | `schema_action.py` |
| Artifact | `ArtifactCreatedEvent`, `ArtifactUpdatedEvent` | `artifact_action.py` |
| Validator | `ValidatorStartedEvent`, `ValidatorPassedEvent`, `ValidatorFailedEvent` | `validator_action.py` |
| Proposed Change | Lifecycle events | `proposed_change_action.py` |
| Repository | Repository action events | `repository_action.py` |

## Event Flow

```text
Application Code
       │
       ▼
InfrahubEventService.send(event)
       │
       ├──► _send_bus() ──► Message Bus (RabbitMQ/NATS)
       │         │
       │         └──► event.get_messages() → Internal handlers
       │
       └──► _send_prefect() ──► Prefect Events API
                   │
                   └──► emit_event() → Prefect Automations
```

## Event Metadata

The `EventMeta` class provides rich context:

- **id**: UUID of the event
- **parent**: UUID of parent event (for hierarchies)
- **ancestors**: Chain of parent events with names
- **level**: Nesting level in event hierarchy
- **branch**: Branch context
- **account_id**: Initiating account
- **request_id**: Correlation ID
- **context**: Full `InfrahubContext` for the operation

Use `EventMeta.from_parent()` to create child events that maintain hierarchy.

## Querying Events

Events can be queried through:

- **GraphQL**: `Events` query with filtering
- **REST API**: `/infrahub/events/filter` endpoint
- **Prefect Client**: Direct Prefect event API access

## Key Locations

| Component | Location |
|-----------|----------|
| Base models | `backend/infrahub/events/models.py` |
| Event definitions | `backend/infrahub/events/*.py` |
| Service adapter | `backend/infrahub/services/adapters/event/__init__.py` |
| Trigger models | `backend/infrahub/trigger/models.py` |
| GraphQL queries | `backend/infrahub/graphql/queries/event.py` |

## See Also

- [ADR-0002: Prefect Events System](../../adr/0002-events-system.md) - Why we use Prefect Events
- [Creating Events Guide](../../guides/backend/creating-events.md) - How to create a new event
- [Backend Architecture](architecture.md) - Overall backend structure
