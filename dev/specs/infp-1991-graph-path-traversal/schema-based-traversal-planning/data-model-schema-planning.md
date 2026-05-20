# Phase 1 Data Model: Schema-Based Path Planning

**Plan**: [plan-schema-planning.md](plan-schema-planning.md)
**Spec**: [spec-schema-planning.md](spec-schema-planning.md)

This document defines the in-memory entities produced and consumed by the planner and query builder. No persistent storage is added by this feature; everything described here is request-scoped and lives in `backend/infrahub/graph_traversal/planning/models.py`.

All entities are frozen `@dataclass(frozen=True, slots=True)` per Constitution III (Type Safety).

---

## Entities

### `Plan`

The per-hop adjacency map of legal `(start_kind, rel_name, end_kind)` triples plus the source/terminal/depth context the renderer needs.

| Field | Type | Description | Constraint |
|---|---|---|---|
| `adjacency` | `Mapping[str, Mapping[str, frozenset[str]]]` | `{start_kind: {rel_name: frozenset(end_kind, ...)}}`. Every triple that may appear on some ≤`max_depth` path from `source_kind` to a kind matching `terminal_predicate`, after permission + user-filter pruning. | Possibly empty. Outer/inner dicts sorted at construction (Determinism). |
| `source_kind` | `str` | The kind the planner BFS'd from. | Must exist in active `schema_branch`. |
| `terminal_predicate` | `TerminalPredicate` | What closes a path (specific id vs kind set). | See below. |
| `max_depth` | `int` | The depth cap used during enumeration. | ∈ [1, 20]. |

**Derived properties**:
- `is_empty: bool = not adjacency`.

**Invariants**:
- If `is_empty`, the query builder MUST short-circuit and the caller MUST return an empty result without executing Cypher (FR-004).
- A `Plan` is **immutable** after construction.

**Why a per-hop adjacency, not full routes**: the rendered Cypher uses a Quantified Path Pattern (QPP) whose only structural gate is `rel.name IN keys($allowed_path_maps[a.kind])` plus `b.kind IN $allowed_path_maps[a.kind][rel.name]` (see [contracts/query-generator.md](contracts/query-generator.md) and `backend/infrahub/graph_traversal/_cypher.py`). The QPP cannot enforce route-shape constraints, so the per-hop adjacency is the only data it actually consumes. Materializing routes only to flatten them back into this map would be wasted enumeration — exponential in cyclic schemas.

**No pruned-route accounting**: the planner does not surface what was pruned. Filters and permission checks are applied *during* BFS expansion (see [contracts/planner.md §Behavior — required](contracts/planner.md#behavior--required)). Diagnostic logging (FR-014) reports the adjacency size.

**Determinism**: For identical inputs (schema-branch, source_kind, terminal_predicate, max_depth, filters, requester permissions) the `Plan` is byte-identical (FR-016). The planner enforces this by:
- Iterating `schema_branch` items in alphabetical order by kind name.
- Sorting the outer adjacency by start_kind, the inner mapping by rel_name, and each end-kind set's eventual list form by end_kind.

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
| `kind_filter` | `frozenset[str]` | If non-empty, every intermediate kind in a path MUST be in this set. Source and terminal kinds are exempt. | empty (no constraint) |
| `excluded_kinds` | `frozenset[str]` | No kind reached during BFS expansion may be in this set; no exemption. | empty |
| `excluded_namespaces` | `frozenset[str]` | No kind whose namespace is in this set may appear; no exemption. The default set (`Core`, `Internal`, `Builtin`, `Lineage`, `Profile`, `Template`) is defined in `planning/constants.py` and applied by `UserFilters.from_graphql_input` when the caller omits the field. | empty constructor default; `from_graphql_input` always applies the default set, optionally unioned with caller-supplied entries |
| `relationship_filter` | `frozenset[str]` | If non-empty, every hop's `relationship_identifier` MUST be in this set; no exemption. | empty |

**Notes**:
- `UserFilters` is constructed by the GraphQL resolver from `PathTraversalInput` / `ReachableNodesInput` and passed to the planner. The planner does not consult GraphQL types directly (Constitution III — boundary typing).
- All four fields are consulted *during* BFS expansion in `SchemaPlanner._build_adjacency`, not after. Excluded peers cause the entire downstream subtree to be skipped — critical for schemas where the unfiltered fan-out is exponential.
- `kind_filter` is the only filter with an exemption: a peer that matches `terminal_predicate` is recorded as a hop even when not in the filter, but expansion past it is forbidden (it would otherwise become an intermediate of a longer path).
- The planner does not track schema kind revisits. The runtime Cypher uses the per-hop adjacency map as a per-hop legality gate and cannot enforce schema-uniqueness on the matched path, so any planner-side revisit pruning would be invisible to query results. Cycles are bounded by `max_depth` alone.

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
    4. if plan.is_empty: return empty result  ← short-circuit (FR-004)
    5. query = PathTraversalQuery(plan=plan, source_id=..., ...)
       await query.execute(db=db)

Query class (backend/infrahub/graph_traversal/{path,reachable}.py):

    def __init__(self, *, plan, ...):
        if plan.is_empty:
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
| `plan.is_empty` ⇒ no Cypher executed | Caller (GraphQL resolver) checks `plan.is_empty` and short-circuits before instantiating the Query class. | FR-004 |
| Generated Cypher must reflect *only* `plan.adjacency` | `render_plan_to_cypher` (in `graph_traversal/_cypher.py`) consumes only `plan.adjacency`; no fallback. | FR-005 |
| Every kind in `adjacency` is `view`-permitted | `SchemaPlanner` consults `KindPermissionCache.can_view` for the source upfront and for every peer during BFS expansion. | FR-003 |
| User filters applied at plan time | `SchemaPlanner._build_adjacency` consults `UserFilters` during BFS expansion. | FR-009 |
| Plans deterministic for identical inputs | Planner walks the inverse index in sorted order and sorts the adjacency at construction; `Plan` is frozen. | FR-016 |

---

## State Transitions

`Plan` is immutable; there are no state transitions on instances. The transitions worth documenting are the planner's *internal* phases (informational, not part of the data model):

1. **Source permission gate**: if `permission_cache.can_view(source_kind) == False`, skip BFS entirely and return a `Plan` with empty `adjacency`. Every viable path would start at the source, so a forbidden source has no possible plan.
2. **Forward BFS with inline pruning**: iterative kind-level expansion from `source_kind` up to `max_depth`. For each candidate hop `(kind, identifier, peer_kind)`, the planner consults — in order — `permission_cache.can_view(peer_kind)`, `excluded_kinds`, `excluded_namespaces`, `relationship_filter`, and `kind_filter`. Any violation drops the hop and its entire downstream subtree. Generics are expanded to concrete kinds before the checks run. The minimum depth from source to each kind is recorded.
3. **Reverse BFS from terminal-matching kinds**: walk the forward adjacency backwards from kinds matching `terminal_predicate` to compute the minimum depth from each kind to a terminal.
4. **Combine with depth bound**: keep only edges `(s, r, e)` whose total path length `min_depth_from_source[s] + 1 + min_depth_to_terminal[e]` is ≤ `max_depth`. Sort the surviving adjacency for determinism, then wrap in `Plan`.

The inline pruning is essential: full Infrahub schemas have enough relationships that an unfiltered enumeration goes exponential at `max_depth ≥ 3` (Core, Internal, Builtin, Profile kinds dominate the fan-out). Outputting an adjacency map rather than route tuples bounds the planner's working set at O(reachable_kinds × relationships_per_kind), regardless of how cyclic the schema is.
