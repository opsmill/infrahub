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
resources (flow run, task run, flow, deployment, work queue, work pool, and
one per flow-run tag) after the event has been handed over, and attaches only
as many of them as still fit under the maximum, logging a warning for the rest.
An event that leaves Infrahub on the maximum therefore reaches the API valid
but stripped of its run context, which carries the tags a run is filtered by.
The reserved headroom keeps room for those resources.

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

## Branch scoping of automations

The per-node trigger families — Jinja2 computed attributes, Python computed attributes (owner and
query), display labels, human-friendly ids, and profile refresh — build one automation per branch
whose definition differs from the default branch, plus one default-branch automation that owns
every other branch. Divergence is the schema hash for the schema-driven families. The two Python
transform families diverge on the repository commit or on that same whole-branch schema hash, so
any schema difference gives a branch its own automations, whether or not the transform query reads
the part that changed. A branch that edits the `CoreGraphQLQuery` text through the API moves
neither, so it keeps the default-branch automations and its reads are answered with the default
branch's read set.

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
- **origin**: For node mutation events, how the mutation was produced (`live`, `merge`, `rebase`, `recompute`), defaulting to `live`. The recompute triggers for the four coalesced families (Jinja2 computed attributes, display labels, human-friendly ids and Python transform computed attributes) match only `live`, so a merge, rebase, or recompute write does not re-trigger their per-node flows. See [merge-recompute.md](merge-recompute.md).

Use `EventMeta.from_parent()` to create child events that maintain hierarchy.

## Scoping branch for webhook matching

Webhook branch scoping matches an event against `meta.context.branch` (see [Webhooks](webhooks.md)). Not every branch-agnostic event overrides the caller's context, so the scoping branch is set per event:

- Proposed change merge and review events (merged, approved, rejected, and the approval/rejection revoke variants) are stamped to the default branch, so scoping is independent of the branch the mutation ran on.
- `branch.merged` is stamped to the default branch as well, since the merge lands there. Its payload still carries the merged branch in `branch_name` / `branch_id`; only the scoping branch is the default one.
- `branch.created` and `branch.deleted` are stamped to the global branch, pending a general rule for branch-agnostic node events.
- `branch.rebased` and `branch.migrated` inherit the caller's context branch; they are not overridden.

## Activity log behaviour

| Situation | What happens |
|---|---|
| An Infrahub event is emitted | Prefect stores it and its related resources, keeps it for `task_manager.retention.activity_log` (7 days by default), then its hourly vacuum deletes both; see [Event retention](task-manager-retention.md#event-retention) |
| Prefect records one of its own events (run states, heartbeats, workers) | It is never shown, and it is kept for `prefect_own_events` when its type is in `PREFECT_EVENT_TYPES`, otherwise for `activity_log` |
| The Activities page loads its first page | The task manager reads newest first, one time window at a time, back from now |
| The user loads more events | The page sends the time of the oldest event shown as `until` (`since` in ascending order) and drops the events it already shows by ID |
| A filter names a branch | The resolver sends the ID of the current branch with that name, else the ID from the newest `infrahub.branch.deleted` event for that name; with neither, it returns an empty page without querying |
| A query sets no `since` | The task manager reads back to its event retention, past Prefect's 180-day default |
| A query selects `count` | The task manager counts the whole range; otherwise `total` is null and no count runs |
| An API client pages with `offset` | Still accepted; a window counts as full only when it holds `offset + limit` matches, so the result equals one read of the whole range, but deep offsets get slower |

## Querying Events

Events can be queried through:

- **GraphQL**: `Events` query with filtering
- **REST API**: `/infrahub/events/filter` endpoint
- **Prefect Client**: Direct Prefect event API access

### Query-path performance constraints

The `/infrahub/events/filter` endpoint reads the `LIMIT`-ed page newest first, one time window
at a time (1 hour, 1 day, 7 days, 30 days, then the whole range, back from the filter's `until`),
and runs an unbounded `count(*)` over the whole range when asked. The range starts at the filter's
`since` when the caller set one, and otherwise at the request's `retention_seconds`, else Prefect's
event retention, back from `until`. `InfrahubEventFilter.to_request` leaves an unset `since` out of
the request so that this default applies. A filter in ascending order is read in one query.
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
  prepared-statement plan caching — at the cost of replanning these queries per
  request (~1.5 ms). Do not remove it without re-checking the event queries' plans under
  `plan_cache_mode = force_generic_plan`.

### Activities filters match indexed IDs

Filter on a resource ID or a related item's ID, not on a label alone. Labels are JSON fields
without an index, so a label filter reads every related row in the range, while Prefect indexes
`resource_id` on both the events and their related resources. The filters in
`task_manager/event/models.py::InfrahubEventFilter` match:

| Filter | Match |
|---|---|
| Account | Related ID `infrahub.account.<id>`, role `infrahub.account` |
| Branch | Related ID `infrahub.branch.<branch_id>`, role `infrahub.branch`, after the GraphQL resolver resolves names to IDs |
| Parent event | Related ID `<parent_id>`, role `infrahub.ancestor_event`, plus the `infrahub.event_parent.id` label, because ancestors include grandparents |
| Merged, rebased or migrated by branch name | Resource ID `infrahub.branch.<name>` when every listed event type is a branch event; otherwise the `infrahub.branch.name` label, which other event types also have |
| Primary node | The resource ID forms `infrahub.node.<id>`, `<id>`, `infrahub.account.<id>` and `infrahub.proposed_change.<id>` plus the `infrahub.node.id` label, but only when the request lists event types and none of them is `infrahub.branch.merged`, `infrahub.branch.deleted` or `infrahub.group.auto_created`, which have the node only in a label; otherwise the label alone |

- Match the primary node with the `prefect.resource.id` label of `EventResourceFilter`, which Prefect
  looks up in the related-resources table, not with `EventResourceFilter.id`, which reads the
  `resource_id` column of the events table: the only index containing that column starts with the
  event name, which PostgreSQL 14 cannot skip over.
- `backend/tests/component/task_manager/test_event_filter_equivalence.py` compares each filter with
  the label filter it replaced, kept in `backend/tests/helpers/event_filters.py`, so a Prefect
  upgrade that changes how resource IDs are stored fails CI.
- A label-only filter is correct but slow on a long activity log; give a new filter an ID match
  before adding it to the Activities page.

## Retention

The activity log is kept for `task_manager.retention.activity_log`, and Prefect's own events for
`prefect_own_events`, through Prefect's global and per-type event retention. The settings, the list
of Prefect event types and the tests that guard it are described in
[Task Manager Retention](task-manager-retention.md#event-retention).

## Key Locations

| Component | Location |
|-----------|----------|
| Base models | `backend/infrahub/events/models.py` |
| Event definitions | `backend/infrahub/events/*.py` |
| Service adapter | `backend/infrahub/services/adapters/event/__init__.py` |
| Trigger models | `backend/infrahub/trigger/models.py` |
| GraphQL queries | `backend/infrahub/graphql/queries/event.py` |
| Activities filters | `backend/infrahub/task_manager/event/models.py` |
| Newest-first time windows | `backend/infrahub/prefect_server/database.py::query_events` |
| Activities paging by time | `frontend/app/src/entities/events/ui/queries/get-events.query.ts` |

## See Also

- [ADR-0002: Prefect Events System](../../adr/0002-events-system.md) - Why we use Prefect Events
- [Task Manager Retention](task-manager-retention.md) - How long events and task runs are kept, and how they are deleted
- [Creating Events Guide](../../guides/backend/creating-events.md) - How to create a new event
- [Authentication](authentication.md) - SSO group resolution and auto-create group events
- [Webhooks](webhooks.md) - HTTP notification delivery triggered by events
- [Merge/Rebase Recompute](merge-recompute.md) - node mutation origin and how it suppresses recompute triggers
- [Backend Architecture](architecture.md) - Overall backend structure
