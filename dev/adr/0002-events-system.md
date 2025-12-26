# 2. Prefect Events System

**Status:** Accepted
**Date:** 2024-12-26
**Author:** @opsmill-team

## Context

Infrahub requires an event-driven architecture to support:

1. **Event Emission**: Notify the system when state changes occur (node mutations, branch operations, schema updates)
2. **Event Querying**: Provide queryable and filterable events for debugging, monitoring, and audit trails
3. **Automation Triggers**: Enable automated actions and workflows based on event patterns
4. **Rich Metadata**: Include sufficient context for complex filtering and routing decisions

The system must handle both internal operational events (infrastructure-level tasks like git sync, registry updates) and user-visible events (for automation and observability).

## Decision

We implement a **Prefect Events-based system** as the foundation for event-driven architecture, leveraging Prefect's built-in storage, querying, and automation capabilities.

### Dual-Channel Dispatch

Events are dispatched through two channels simultaneously:

1. **Message Bus (RabbitMQ/NATS)**: For internal operational tasks
   - Point-to-point or broadcast communication
   - Handles specific operational tasks (git repository sync, registry updates)
   - Only certain events send messages via `get_messages()` method

2. **Prefect Events**: For user-visible automation and audit trails
   - All `InfrahubEvent` instances are sent to Prefect
   - Stored in Prefect database and queryable via APIs
   - Trigger Prefect Automation workflows
   - Include rich metadata for flexible filtering

### Event Structure

Events follow Prefect's model with Infrahub-specific extensions:

- **Event Name**: Namespaced under `infrahub.*` (e.g., `infrahub.node.created`, `infrahub.branch.merged`)
- **Resource**: Primary identifier with metadata (node ID, kind, branch)
- **Related Resources**: Additional context (account, branch, parent events, related nodes)
- **Payload**: Event-specific data including changelog information and context

### Core Implementation

The `InfrahubEventService` adapter handles dual dispatch:

```python
async def send(self, event: InfrahubEvent) -> None:
    tasks = [self._send_bus(event=event), self._send_prefect(event=event)]
    await asyncio.gather(*tasks)
```

Events inherit from `InfrahubEvent` and implement:

- `event_name`: Class variable defining the event namespace
- `get_resource()`: Returns primary resource metadata
- `get_related()`: Returns additional context (optional override)
- `get_messages()`: Returns message bus messages (optional override)

## Consequences

### Positive

- **Mature infrastructure**: Leverages Prefect's battle-tested event system
- **Built-in storage**: Events stored in Prefect database with retention policies
- **Powerful querying**: Filter events via Prefect Automation rules and APIs
- **Workflow integration**: Direct integration with existing Prefect-based task execution
- **Rich metadata**: Support for parent-child relationships, related resources, and flexible attributes
- **Multiple access methods**: GraphQL, REST API, and Prefect Client for event querying
- **Audit capabilities**: Complete event history for compliance and debugging

### Negative

- **Prefect coupling**: Tight dependency on Prefect infrastructure
- **Storage overhead**: All events stored in Prefect database increases storage requirements
- **Learning curve**: Developers must understand Prefect Automation concepts
- **Availability dependency**: Event querying requires Prefect server availability
- **Dual-system complexity**: Managing both message bus and Prefect events adds complexity

### Neutral

- **Event model adoption**: Following Prefect's event model provides consistency but requires adaptation for Infrahub-specific needs

## Implementation Notes

Key implementation locations:

- Event definitions: `backend/infrahub/events/`
- Service adapter: `backend/infrahub/services/adapters/event/`
- Trigger models: `backend/infrahub/trigger/models.py`
- Trigger setup: `backend/infrahub/trigger/setup.py`
- GraphQL queries: `backend/infrahub/graphql/queries/event.py`

See also:

- `dev/knowledge/backend/events.md` - How the event system works
- `dev/guides/backend/creating-events.md` - How to create a new event
