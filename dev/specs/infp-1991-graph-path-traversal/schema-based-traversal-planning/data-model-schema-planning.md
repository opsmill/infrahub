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

The set of `Route`s the planner produced for a request.

| Field | Type | Description | Constraint |
|---|---|---|---|
| `routes` | `tuple[Route, ...]` | Viable routes that survived all pruning. | Possibly empty. Sorted lexicographically (see Determinism below). |
| `source_kind` | `str` | Echoed for traceability. | Matches `source_kind` of every route. |
| `terminal_predicate` | `TerminalPredicate` | What closes a path (specific id vs kind set). | See below. |
| `max_depth` | `int` | The depth cap used during enumeration. | ∈ [1, 20]. |

**Invariants**:
- If `routes` is empty, the query builder MUST short-circuit and the caller MUST return an empty result without executing Cypher (FR-004).
- A `Plan` is **immutable** after construction.

**No pruned-route accounting**: the planner does not surface what was pruned. Filters and permission checks are applied *during* BFS expansion (see [contracts/planner.md §Behavior — required](contracts/planner.md#behavior--required)), so pruned subtrees are never enumerated and there are no candidate `Route` objects to record. Diagnostic logging (FR-014) reports route counts only.

**Determinism**: For identical inputs (schema-branch, source_kind, terminal_predicate, max_depth, filters, requester permissions) the `Plan` is byte-identical (FR-016). The planner enforces this by:
- Iterating `schema_branch` items in alphabetical order by kind name.
- Sorting routes by `(length, kinds, relationship_identifiers, directions)` lexicographically before constructing the `Plan`.

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
| `_resolver` | `PermissionResolver` | Injected into `SchemaPlanner.__init__` by the caller. The caller builds it via `PermissionLoader.load(...)` + `PermissionResolver(...)` before constructing the planner. |
| `_branch` | `Branch` | The branch the request is bound to. |
| `_schema_branch` | `SchemaBranch` | Used by `can_view` to resolve `kind → namespace` when constructing `ObjectPermission`. |
| `_decisions` | `dict[str, bool]` | Memoized `kind → can_view` map. Mutated only by the cache itself. |

**Public API**:
- `can_view(kind: str) -> bool` — memoized; constructs an `ObjectPermission(namespace, name, action="view", ...)` from `schema_branch.get(kind).namespace` and `kind`, then defers to the resolver.

**Lifecycle**: Constructed eagerly inside `SchemaPlanner.__init__` from the injected `PermissionResolver`; discarded when the planner instance is garbage-collected.

### `UserFilters`

A typed view of the GraphQL inputs the planner uses for plan-level filtering.

| Field | Type | Description | Default |
|---|---|---|---|
| `kind_filter` | `frozenset[str]` | If non-empty, every intermediate kind in a route MUST be in this set. Source and terminal kinds are exempt. | empty (no constraint) |
| `excluded_kinds` | `frozenset[str]` | No kind reached during BFS expansion may be in this set; no exemption. | empty |
| `excluded_namespaces` | `frozenset[str]` | No kind whose namespace is in this set may appear; no exemption. The default set (`Core`, `Internal`, `Builtin`, `Lineage`, `Profile`, `Template`) is defined in `planning/constants.py` and applied by `UserFilters.from_graphql_input` when the caller omits the field. | empty constructor default; `from_graphql_input` always applies the default set, optionally unioned with caller-supplied entries |
| `relationship_filter` | `frozenset[str]` | If non-empty, every `Hop.relationship_identifier` MUST be in this set; no exemption. | empty |
| `allow_schema_revisits` | `bool` | If `False` (the default), routes in which a schema kind appears more than once are pruned — with the explicit exception that the source kind may also appear at the terminal position (same-kind source/terminal queries). If `True`, the planner enumerates all routes bounded only by `max_depth`, allowing kinds to repeat anywhere. | `False` |

**Notes**:
- `UserFilters` is constructed by the GraphQL resolver from `PathTraversalInput` / `ReachableNodesInput` and passed to the planner. The planner does not consult GraphQL types directly (Constitution III — boundary typing).
- All five fields are consulted *during* BFS expansion in `SchemaPlanner._step`, not after. Excluded peers cause the entire downstream subtree to be skipped — critical for schemas where the unfiltered fan-out is exponential.
- `kind_filter` is the only filter with an exemption: a peer that matches `terminal_predicate` is emitted as a route even when not in the filter, but expansion past it is forbidden (it would otherwise become an intermediate of a longer route).

---

## Entity Relationships

The `SchemaPlanner` is fully synchronous from the outside: every dependency (schema view, branch, permission resolver) is injected at construction time. The caller does the one `await` for permission loading itself, before building the planner. Callers never touch `KindPermissionCache` directly; it is constructed by `__init__` from the injected resolver. See [contracts/planner.md §Surface](contracts/planner.md#surface).
```text
GraphQL resolver (backend/infrahub/graphql/queries/{path,reachable}.py):

    1. Resolve source/destination objects via NodeManager.get_one(...)
    2. permissions = await PermissionLoader(account_session=...).load(db=db, branch=branch)
       resolver = PermissionResolver(permissions=permissions, default_branch_name=registry.default_branch)
    3. planner = SchemaPlanner(schema_branch=..., branch=..., permission_resolver=resolver)
       plan = planner.plan(source_kind, terminal_predicate, max_depth, user_filters)
    4. if not plan.routes: return empty result  ← short-circuit (FR-004)
    5. query = PathTraversalQuery(plan=plan, source_id=..., ...)
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
| `max_depth` ∈ [1, 20] | `SchemaPlanner.plan` validates before enumeration; `Plan.__post_init__` validates the field. | FR-010 |
| `Plan.routes` empty ⇒ no Cypher executed | Caller (GraphQL resolver) checks `plan.routes` and short-circuits before instantiating the Query class. | FR-004 |
| Generated Cypher must reflect *only* `plan.routes` | `render_plan_to_cypher` (in `graph_traversal/_cypher.py`) consumes only `plan.routes`; no fallback. | FR-005 |
| Every kind in every route is `view`-permitted | `SchemaPlanner` consults `KindPermissionCache.can_view` for the source upfront and for every peer during BFS expansion. | FR-003 |
| User filters applied at plan time | `SchemaPlanner._step` consults `UserFilters` during BFS expansion. | FR-009 |
| Plans deterministic for identical inputs | Planner walks the inverse index in sorted order and sorts the final route tuple; `Plan` is frozen. | FR-016 |

---

## State Transitions

`Plan` is immutable; there are no state transitions on instances. The transitions worth documenting are the planner's *internal* phases (informational, not part of the data model):

1. **Source permission gate**: if `permission_cache.can_view(source_kind) == False`, skip BFS entirely and return a `Plan` with empty `routes`. Every viable route would start at the source, so a forbidden source has no possible plan.
2. **BFS with inline pruning**: iterative expansion up to `max_depth` from `source_kind`. For each candidate peer, `_step` consults — in order — the revisit rule, `permission_cache.can_view`, `excluded_kinds`, `excluded_namespaces`, `relationship_filter`, and `kind_filter`. Any violation drops the entire downstream subtree; no candidate `Route` is constructed. Generics are expanded to concrete kinds before the checks run.
3. **Sort & freeze**: lexicographic sort of surviving routes; wrap in `Plan`.

The inline pruning is essential: full Infrahub schemas have enough relationships that a naive enumeration-then-filter approach goes exponential at `max_depth ≥ 3` (Core, Internal, Builtin, Profile kinds dominate the fan-out).
