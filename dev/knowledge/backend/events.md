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

## Trigger action parameters

A trigger definition's `ExecuteWorkflow` action passes parameters to the target deployment. Each parameter value is a Jinja template that Prefect renders server-side, against the triggering event, when the automation fires.

Prefect's `RunDeployment._upgrade_v1_templates` (>=3.6.24) rewrites a bare single-expression string such as `"{{ event.id }}"` by appending `| tojson`, which JSON-serializes the rendered value to preserve its type. `json.dumps` raises on values that are not JSON-native (a `UUID` or a `datetime`) or that resolve to an undefined resource key, so the render fails and the deployment never runs.

Emit single-expression parameters through `jinja_parameter()` in `trigger/models.py`, which wraps them as an explicit `{"__prefect_kind": "jinja", "template": ...}` value. Prefect leaves a parameter that already declares a `__prefect_kind` untouched, so it renders as a plain string on every Prefect version. Values that must keep their non-string type use the `{"__prefect_kind": "json", "value": {"__prefect_kind": "jinja", "template": "... | tojson"}}` form instead.

## Branch scoping of automations

The per-node trigger families — Jinja2 computed attributes, Python computed attributes (owner and
query), display labels, human-friendly ids, and profile refresh — build one automation per branch
whose definition differs from the default branch, plus one default-branch automation that owns
every other branch. Divergence is the schema hash for the schema-driven families and the
repository commit for the Python transform ones.

The default-branch automation has to exclude the branches that own their own automation.
**Prefect ORs the patterns of a single label**, so `match["infrahub.branch.name"] = ["!b1", "!b2"]`
excludes nothing: `b1` fails the first pattern and passes the second, and `ResourceSpecification.matches`
only needs one pattern to hold. It **ANDs the entries of `match_related`** instead
(`ResourceTrigger.covers_resources` requires every entry to be satisfied), so each excluded branch
gets its own one-negation specification:

```python
match_related = [
    {"prefect.resource.role": ..., "infrahub.field.name": [...]},   # the field filter
    {"prefect.resource.role": "infrahub.branch", "infrahub.resource.label": "!b1"},
    {"prefect.resource.role": "infrahub.branch", "infrahub.resource.label": "!b2"},
]
```

`EventTrigger.exclude_branches()` builds this. It relies on the `infrahub.branch` related resource
that every event carries (`EventMeta.get_related`), which sits among the first entries and therefore
survives the related-resource truncation above. It sorts the branch names, because a Prefect
automation is reconciled by comparing model dumps and the registry hands back branches in
insertion order.

Two properties are worth keeping:

- **Positive exclusion beats enumeration.** Listing the in-scope branches instead would leave a
  branch created after the last reconcile with no automation at all, and nothing re-runs the setup
  on branch creation (only `SchemaUpdatedEvent` and `BranchDeletedEvent` do). Excluding the known
  divergent branches keeps every unknown branch on the default automation.
- **Assert on behaviour, not on shape.** A filter's dict says nothing about the events it selects.
  Use `automation_covers_event()` in `tests/helpers/trigger.py`, which runs the generated automation
  through Prefect's own server-side matcher.

A single negation on the primary resource is still correct and is used where the split is
default-branch versus everything else (`actions/models.py`, `webhook/models.py`).

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
