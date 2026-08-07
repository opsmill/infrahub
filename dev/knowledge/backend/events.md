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

### Related resources cap

The Prefect API rejects any event whose `related` list exceeds
`PREFECT_SERVER_EVENTS_MAXIMUM_RELATED_RESOURCES` (500 in the Infrahub image) —
an oversized event is dropped entirely, never recorded. Node mutation events
build their related resources in priority order — node-scoped entries first
(attribute updates, parent, the node's own related-node entry), then
relationship updates (which automation triggers match on), then per-peer
related-node entries — and truncate at that maximum with a warning log. A node
with a very large cardinality-many relationship therefore keeps its event, but
not every peer is represented in `related`; the full peer list remains
available in the event payload's changelog.

Group mutation events (`member_added` / `member_removed`) follow the same rule.
Each member and each ancestor is a single related resource carrying its own
role (`infrahub.group.member` / `infrahub.group.ancestor`) rather than a
role-plus-duplicate pair, so the list grows by one per member instead of two.
The fixed group-scoped entries come first and members/ancestors come last, so
the same ordered truncation keeps the event within the maximum. Group
automations match the primary group resource and read the changed members from
the payload, so truncating overflow members only trims the event-query display;
the event is always recorded and automations always fire. The event query
API treats members and ancestors as related nodes (matching all three roles and
deduplicating by id), which keeps its output stable across the consolidated
format and any older events still carrying the duplicate related-node role.

## Event Types

Events are organized by domain in `backend/infrahub/events/`:

| Domain | Events | File |
|--------|--------|------|
| Node | `NodeCreatedEvent`, `NodeUpdatedEvent`, `NodeDeletedEvent` | `node_action.py` |
| Branch | `BranchCreatedEvent`, `BranchDeletedEvent`, `BranchMergedEvent`, `BranchRebasedEvent` | `branch_action.py` |
| Group | `GroupMemberAddedEvent`, `GroupMemberRemovedEvent`, `GroupAutoCreatedEvent`, `GroupAutoCreateRejectedEvent`, `GroupAutoCreateCappedEvent` | `group_action.py` |
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

## Trigger action parameters

A trigger definition's `ExecuteWorkflow` action passes parameters to the target deployment. Each parameter value is a Jinja template that Prefect renders server-side, against the triggering event, when the automation fires.

Prefect's `RunDeployment._upgrade_v1_templates` (>=3.6.24) rewrites a bare single-expression string such as `"{{ event.id }}"` by appending `| tojson`, which JSON-serializes the rendered value to preserve its type. `json.dumps` raises on values that are not JSON-native (a `UUID` or a `datetime`) or that resolve to an undefined resource key, so the render fails and the deployment never runs.

Emit single-expression parameters through `jinja_parameter()` in `trigger/models.py`, which wraps them as an explicit `{"__prefect_kind": "jinja", "template": ...}` value. Prefect leaves a parameter that already declares a `__prefect_kind` untouched, so it renders as a plain string on every Prefect version. Values that must keep their non-string type use the `{"__prefect_kind": "json", "value": {"__prefect_kind": "jinja", "template": "... | tojson"}}` form instead.

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
- [Authentication](authentication.md) - SSO group resolution and auto-create group events
- [Webhooks](webhooks.md) - HTTP notification delivery triggered by events
- [Backend Architecture](architecture.md) - Overall backend structure
