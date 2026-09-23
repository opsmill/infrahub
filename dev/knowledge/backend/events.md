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

### Sensitive values are masked only at construction

The changelog models (`backend/infrahub/core/changelog/models.py`) mask `Password`/
`HashedPassword` attribute values to `***` in a `model_validator(mode="after")` — which runs only
when the model is constructed. Assigning `value`/`value_previous` on an existing instance bypasses
the mask (`validate_assignment` is not enabled) and leaks the secret into the event payload. Build
changelog entries with their final values; never patch them after construction.

### Related resources cap

The Prefect API rejects any event whose `related` list exceeds
`PREFECT_SERVER_EVENTS_MAXIMUM_RELATED_RESOURCES` (500 in the Infrahub image) —
an oversized event is dropped entirely, never recorded. Node mutation events
build their related resources in priority order — node-scoped entries first
(attribute updates, parent, the node's own related-node entry), then
relationship updates (which automation triggers match on), then per-peer
related-node entries — and truncate with a warning log. A node
with a very large cardinality-many relationship therefore keeps its event, but
not every peer is represented in `related`; the full peer list remains
available in the event payload's changelog.

Events truncate to `get_related_resource_budget()`, which sits below that
maximum rather than on it. Prefect's events worker appends run-context
resources — flow run, task run, flow, deployment, work queue, work pool, and
one per flow-run tag — after the event has been handed over, extending the list
in place in a way that skips the client-side validation. An event that leaves
Infrahub on the maximum therefore arrives above it, and the Prefect API answers
by closing the `/events/in` websocket rather than by dropping the single event.
The reserved headroom keeps the enlarged event acceptable.

Group mutation events (`member_added` / `member_removed`) follow the same rule.
Each member and each ancestor is a single related resource carrying its own
role (`infrahub.group.member` / `infrahub.group.ancestor`) rather than a
role-plus-duplicate pair, so the list grows by one per member instead of two.
The fixed group-scoped entries come first and members/ancestors come last, so
the same ordered truncation keeps the event within the budget. Group
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

For example, `BranchDeletedEvent` drives the `branch-deleted-purge-tasks-trigger` automation, which runs the `branch-purge-tasks` flow to delete the deleted branch's settled flow runs so their completed tasks no longer surface on a same-named recreation (see [Asynchronous Tasks](async-tasks.md)).

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
- **origin**: For node mutation events, how the mutation was produced (`live`, `merge`, `rebase`, `recompute`), defaulting to `live`. The recompute triggers for computed attributes, display labels, and human-friendly ids match only `live`, so a merge, rebase, or recompute write does not re-trigger their per-node flows. See [merge-recompute.md](merge-recompute.md).

Use `EventMeta.from_parent()` to create child events that maintain hierarchy.

## Querying Events

Events can be queried through:

- **GraphQL**: `Events` query with filtering
- **REST API**: `/infrahub/events/filter` endpoint
- **Prefect Client**: Direct Prefect event API access

### Query-path performance constraints

The `/infrahub/events/filter` endpoint runs two SQL statements against the task manager's
Postgres: an unbounded `count(*)` over the whole filter window and the `LIMIT`-ed page read.
Two hard-earned constraints apply to this path:

- **The count is only computed when the caller asks for it.** The count aggregates every
  matching row while the page read stops at the page size, so the count dominates the
  endpoint's cost. The GraphQL resolver requests it (`include_total`) only when the query
  selects `count` — the activity-log UI does not, so its page loads skip the aggregate
  entirely. Keep that property when extending the endpoint.
- **The endpoint forces per-execution planning** (`SET LOCAL plan_cache_mode =
  force_custom_plan` at the start of its transaction). After five executions of a
  prepared statement, Postgres may switch it to a *generic* plan chosen without seeing
  the parameter values. For these event filters — a wide `occurred` window plus a JSON
  label match against `event_resources` — the generic plan degrades from a linear hash
  join to a quadratic nested loop (measured: 5 ms → 3.5 s on a 5k-event table, growing
  quadratically). The flip is per pool connection and per statement, which made the
  resulting stalls look like a once-a-week CI flake: one pool connection runs the
  pathological plan while its siblings answer in milliseconds. `SET LOCAL` scopes the
  countermeasure to this transaction only — the rest of the Prefect server keeps its
  prepared-statement plan caching — at the cost of replanning these two queries per
  request (~1.5 ms). Do not remove it without re-checking the event queries' plans under
  `plan_cache_mode = force_generic_plan`.

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
- [Merge/Rebase Recompute](merge-recompute.md) - node mutation origin and how it suppresses recompute triggers
- [Backend Architecture](architecture.md) - Overall backend structure
