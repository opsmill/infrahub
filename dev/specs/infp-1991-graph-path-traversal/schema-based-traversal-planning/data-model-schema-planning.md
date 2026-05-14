# Phase 1 Data Model: Schema-Based Path Planning

**Plan**: [plan-schema-planning.md](plan-schema-planning.md)
**Spec**: [spec-schema-planning.md](spec-schema-planning.md)

This document defines the in-memory entities produced and consumed by the planner and query builder. No persistent storage is added by this feature; everything described here is request-scoped and lives in `backend/infrahub/graph_traversal/planning/models.py`.

All entities are frozen `@dataclass(frozen=True, slots=True)` per Constitution III (Type Safety).

---

## Enumerations

### `HopDirection`

```text
HopDirection ∈ { OUTBOUND = 0, INBOUND = 1, BIDIR = 2 }   # IntEnum
```

`HopDirection` mirrors the schema's `RelationshipDirection` 1:1 and is **not** expanded by the planner. Members are an `IntEnum` with explicit integer values so the planner's lexicographic determinism sort key (which embeds a `tuple[HopDirection, ...]`) is totally ordered across Python versions. The three values correspond to distinct storage patterns in the Infrahub graph, where every schema-level relationship is materialized as a `:Relationship` vertex between two `:Node` vertices:

- `OUTBOUND` — `(:start_kind)-[:IS_RELATED]->(:Relationship {name})-[:IS_RELATED]->(:end_kind)`
- `INBOUND`  — `(:start_kind)<-[:IS_RELATED]-(:Relationship {name})<-[:IS_RELATED]-(:end_kind)`
- `BIDIR`    — `(:start_kind)-[:IS_RELATED]->(:Relationship {name})<-[:IS_RELATED]-(:end_kind)`

Each schema hop therefore corresponds to *two* `IS_RELATED` edges in Cypher, both of which must pass the edge-validity check (see [contracts/query-generator.md](contracts/query-generator.md)).

---

## Entities

### `Hop`

A single schema-level edge between two kinds, ready to be projected into one Cypher hop.

| Field | Type | Description | Source / Constraint |
|---|---|---|---|
| `start_kind` | `str` | Concrete kind name of the node entering this hop. | From planner's route enumeration. Must exist in active `schema_branch`. |
| `end_kind` | `str` | Concrete kind name of the node exiting this hop. | Must exist in active `schema_branch`. |
| `relationship_identifier` | `str` | The `RelationshipSchema.identifier` value used to traverse this edge. Stored on the `:Relationship` vertex as the `name` property. | Sourced from `start_kind` schema's `relationships`. |
| `direction` | `HopDirection` | Direction as recorded in the schema's `RelationshipSchema.direction`. Determines the Cypher arrow pattern; see `HopDirection` above. | Direct copy from `RelationshipSchema.direction`. |

**Invariants**:
- `relationship_identifier` is non-empty.
- `start_kind` and `end_kind` are concrete (never a generic kind name); planner expands generics before constructing `Hop`s.
- `direction` may be any of `OUTBOUND`, `INBOUND`, `BIDIR` — preserved verbatim from the schema.

### `Route`

An ordered sequence of `Hop`s connecting a `source_kind` to a `terminal_kind`.

| Field | Type | Description | Constraint |
|---|---|---|---|
| `hops` | `tuple[Hop, ...]` | Ordered hops, hop 0 starts at `source_kind`. | Length ∈ [1, `max_depth`]. |
| `source_kind` | `str` | The first hop's `start_kind`. | Stored explicitly for readability. |
| `terminal_kind` | `str` | The last hop's `end_kind`. | Used by query builder. |

**Invariants**:
- For `i ≥ 1`: `hops[i].start_kind == hops[i-1].end_kind` (continuity).
- `hops[0].start_kind == source_kind`.
- `hops[-1].end_kind == terminal_kind`.
- No kind appears more than `max_depth` times in `hops` (cycle bound — see spec Edge Cases).

**Derived properties**:
- `length: int = len(hops)`.
- `kinds: tuple[str, ...] = (source_kind, hops[0].end_kind, ..., terminal_kind)`.

### `Plan`

The complete set of `Route`s the planner produced for a request, plus accounting for routes that were pruned (used for diagnostics).

| Field | Type | Description | Constraint |
|---|---|---|---|
| `routes` | `tuple[Route, ...]` | Viable routes that survived all pruning. | Possibly empty. Sorted ascending by `route.length`. |
| `source_kind` | `str` | Echoed for traceability. | Matches `source_kind` of every route. |
| `terminal_predicate` | `TerminalPredicate` | What closes a path (specific id vs kind set). | See below. |
| `max_depth` | `int` | The depth cap used during enumeration. | ∈ [1, 20]. |
| `pruned_for_permission` | `tuple[Route, ...]` | Routes dropped because some kind on the route was unreadable to the requester. | Possibly empty. For diagnostic logging only. |
| `pruned_for_user_filters` | `tuple[Route, ...]` | Routes dropped by `kind_filter`, `excluded_kinds`, `excluded_namespaces`, or `relationship_filter`. | Possibly empty. For diagnostic logging only. |

**Invariants**:
- If `routes` is empty, the query builder MUST short-circuit and the caller MUST return an empty result without executing Cypher (FR-004).
- The three lists are mutually exclusive in any given request: a route appears in at most one of `routes`, `pruned_for_permission`, `pruned_for_user_filters`.
- A `Plan` is **immutable** after construction.

**Determinism**: For identical inputs (schema-branch, source_kind, terminal_predicate, max_depth, filters, requester permissions) the `Plan` is byte-identical (FR-016). The planner enforces this by:
- Iterating `schema_branch` items in alphabetical order by kind name.
- Sorting routes by `(length, kinds, relationship_identifiers)` lexicographically before constructing the `Plan`.

### `TerminalPredicate` (tagged union)

Discriminates the two modes the query builder supports.

| Variant | Fields | Used by |
|---|---|---|
| `TerminalById` | `node_id: str`, `kind: str` | `PathTraversalQuery` |
| `TerminalByKinds` | `kinds: frozenset[str]` | `ReachableNodesQuery` |

**Invariants**:
- `TerminalById.node_id` is a UUID string (validated upstream by GraphQL resolver).
- `TerminalById.kind` is the destination object's kind, resolved by the GraphQL resolver via `NodeManager.get_one(...).get_kind()`. The planner uses it to match route terminals without re-loading the destination node. The kind MUST exist in `schema_branch`.
- `TerminalByKinds.kinds` is non-empty; every member exists in `schema_branch`.

### `KindPermissionCache` (planner-internal)

Per-request, in-memory yes/no answers for "can the requester view kind X." **Internal to `SchemaPlanner`** — not part of the planner's public surface; callers never construct or pass one. Lives in `backend/infrahub/graph_traversal/planning/permissions.py`.

| Field | Type | Description |
|---|---|---|
| `_resolver` | `PermissionResolver` | Loaded by `SchemaPlanner.initialize()` via `PermissionManager.load_for_account(...)`. |
| `_branch` | `Branch` | The branch the request is bound to. |
| `_schema_branch` | `SchemaBranch` | Used by `can_view` to resolve `kind → namespace` when constructing `ObjectPermission`. |
| `_decisions` | `dict[str, bool]` | Memoized `kind → can_view` map. Mutated only by the cache itself. |

**Public API**:
- `can_view(kind: str) -> bool` — memoized; constructs an `ObjectPermission(namespace, name, action="view", ...)` from `schema_branch.get(kind).namespace` and `kind`, then defers to the resolver.

**Lifecycle**: Constructed inside `SchemaPlanner.initialize()`; discarded when the planner instance is garbage-collected.

### `UserFilters`

A typed view of the GraphQL inputs the planner uses for plan-level filtering.

| Field | Type | Description | Default |
|---|---|---|---|
| `kind_filter` | `frozenset[str]` | If non-empty, every intermediate kind in a route MUST be in this set. Source and terminal kinds are exempt. | empty (no constraint) |
| `excluded_kinds` | `frozenset[str]` | No kind in a route may be in this set. | empty |
| `excluded_namespaces` | `frozenset[str]` | No kind whose namespace is in this set may appear (with default Core/Internal/Builtin/Lineage/Profile/Template exclusions applied if the input is `None`). | spec-defined defaults |
| `relationship_filter` | `frozenset[str]` | If non-empty, every `Hop.relationship_identifier` MUST be in this set. | empty |

**Notes**:
- `UserFilters` is constructed by the GraphQL resolver from `PathTraversalInput` / `ReachableNodesInput` and passed to the planner. The planner does not consult GraphQL types directly (Constitution III — boundary typing).
- The "default namespace exclusion" semantics already exist; this dataclass codifies them as data, not as inline conditionals in the planner.

---

## Entity Relationships

The `SchemaPlanner` lifecycle is **sync `__init__` + explicit async `initialize()` + sync `plan()`**. The async I/O for permission loading is encapsulated inside `initialize()` so callers never touch `KindPermissionCache` directly; calling `plan()` before `initialize()` raises `RuntimeError`. See [contracts/planner.md §Surface](contracts/planner.md#surface).
```text
GraphQL resolver (backend/infrahub/graphql/queries/{path,reachable}.py):

    1. Resolve source/destination objects via NodeManager.get_one(...)
    2. planner = SchemaPlanner(schema_branch, branch, account_session)
       await planner.initialize(db=db)
       plan = planner.plan(source_kind, terminal_predicate, max_depth, user_filters)
    3. if not plan.routes: return empty result  ← short-circuit (FR-004)
    4. query = PathTraversalQuery(plan=plan, source_id=..., ...)
       await query.execute(db=db)

Query class (backend/infrahub/graph_traversal/{path,reachable}.py):

    def __init__(self, *, plan, ...):
        if not plan.routes:
            raise ValueError(...)   # backstop; resolver should have short-circuited
        self.plan = plan
        ...

    def query_init(self):
        rendered = render_plan_to_cypher(plan=self.plan, ...)
        self.query_lines = [rendered.text]
        ...
```

`Plan` is the only data structure that crosses the planner / Query-class boundary. The GraphQL resolver — not the Query class — calls the planner and decides whether to instantiate the Query at all. The planner package (`backend/infrahub/graph_traversal/planning/`) ships **no** Cypher generation code — that responsibility belongs to the Query classes in `backend/infrahub/graph_traversal/path.py` and `backend/infrahub/graph_traversal/reachable.py`, which share a private helper (see plan §Source Code).

---

## Validation Rules

These map to FRs in the spec and are enforced at construction or in tests:

| Rule | Where enforced | Spec ref |
|---|---|---|
| `max_depth` ∈ [1, 20] | `SchemaPlanner.plan` validates before enumeration. | FR-010 |
| `Plan.routes` empty ⇒ no Cypher executed | Caller (Query class) checks `plan.routes` and short-circuits. | FR-004 |
| Generated Cypher must reflect *only* `plan.routes` | `render_plan_to_cypher` (in `graph_traversal/_cypher.py`) consumes only `plan.routes`; no fallback. | FR-005 |
| Every kind in every route is `view`-permitted | `SchemaPlanner` filters via `KindPermissionCache` before constructing `Plan.routes`. | FR-003 |
| User filters applied at plan time | `SchemaPlanner` consumes `UserFilters` before final route assembly. | FR-009 |
| Plans deterministic for identical inputs | Planner sorts everything; `Plan` is frozen. | FR-016 |

---

## State Transitions

`Plan` is immutable; there are no state transitions on instances. The transitions worth documenting are the planner's *internal* phases (informational, not part of the data model):

1. **Enumerate**: BFS up to `max_depth` from `source_kind`, expanding generics, producing candidate routes whose terminal matches `terminal_predicate`.
2. **Filter (user)**: drop routes that violate `UserFilters`; record dropped routes in `pruned_for_user_filters`.
3. **Filter (permission)**: drop routes containing any kind for which `permission_cache.can_view(kind) == False`; record in `pruned_for_permission`.
4. **Sort & freeze**: lexicographic sort of surviving routes; wrap in `Plan`.

These phases are sequential because user-filter pruning is cheaper than permission lookups, so doing user filtering first reduces the permission-check workload.
