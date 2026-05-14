# Phase 0 Research: Schema-Based Path Planning

**Feature**: Schema-Based Path Planning for Graph Traversal Queries
**Plan**: [plan-schema-planning.md](plan-schema-planning.md)
**Spec**: [spec-schema-planning.md](spec-schema-planning.md)

This research consolidates findings from a code exploration of the current path traversal subsystem, the Infrahub schema API, the permission system, existing Cypher generation idioms, the test layout, and the diagnostic logging infrastructure. Each section ends with a **Decision** that resolves an unknown in the plan.

---

## 1. Current PathTraversalQuery / ReachableNodesQuery shape

**Findings**

- Both classes inherit `Query` (`backend/infrahub/core/query/__init__.py`). The base provides `params: dict`, `query_lines: list[str]`, `return_labels: list[str]`, async `execute(db)`, and per-row `QueryResult` traversal.
- `PathTraversalQuery` ([`backend/infrahub/core/query/path.py:79-214`](../../../../backend/infrahub/core/query/path.py)) emits a single variable-length Cypher pattern `MATCH path = (source)-[:IS_RELATED*2..N]-(target)` with where-clause filters for branch, namespace, kind, and relationship identifier, then validates each edge in a `CALL { ... }` subquery, then orders by `length(path)` and limits.
- `ReachableNodesQuery` ([`backend/infrahub/core/query/reachable.py:25-141`](../../../../backend/infrahub/core/query/reachable.py)) follows the same shape but pivots the terminal predicate to `target:Node` whose `kind` is in `$target_kinds`.
- Return data is exposed through `extract_path_data(neo4j.Path)` which already produces frozen dataclasses (`PathData`, `PathHopData`, `PathNodeData`). No record-leakage at the boundary.
- Branch and temporal filtering is reused via `branch.get_query_filter_path(at=...)`; returns a `(clause: str, params: dict)` tuple suitable for interpolation into a `WHERE` slot.

**Decision**: The **GraphQL resolver** is the orchestrator: it resolves the source/destination objects, constructs and initializes the `SchemaPlanner`, calls `plan()`, and short-circuits at the resolver level when `plan.routes` is empty (no pointless `Query.execute()` reaches the database). Only when a non-empty plan exists does it instantiate `PathTraversalQuery(plan=plan, …)` or `ReachableNodesQuery(plan=plan, …)`. The Query class takes a non-empty `Plan` in `__init__` (it raises `ValueError` if given an empty one — a defensive backstop) and renders Cypher in `query_init` via the shared private helper at `backend/infrahub/graph_traversal/_cypher.py` (`render_plan_to_cypher`). The Query class never calls the planner. All imports live at module top. The planner package does **not** import or emit Cypher. `extract_path_data` is reused as-is.

**Rationale**: Minimizes blast radius. GraphQL types, resolvers, dataclasses, and call sites stay intact. Tests at the resolver layer continue to pass without modification (SC-004).

**Alternatives considered**:

- *Move planning into the GraphQL resolver*: rejected — couples GraphQL layer to Cypher concerns the Query class already encapsulates.
- *Replace `Query` base entirely*: rejected — `Query` is shared infrastructure; subclassing it remains the cheapest path.

---

## 2. Schema introspection capabilities

**Findings**

- `schema_branch.get(name, branch, duplicate=False)` ([`backend/infrahub/core/schema/schema_branch.py`](../../../../backend/infrahub/core/schema/schema_branch.py)) returns `NodeSchema | GenericSchema | ProfileSchema | TemplateSchema`. Existing GraphQL resolver already uses this; idiom is well-established.
- `schema.relationships: list[RelationshipSchema]` exposes every relationship on a kind. Each `RelationshipSchema` carries: `identifier`, `name`, `direction (OUTBOUND|INBOUND|BIDIR)`, `peer` (kind name), `cardinality`, `kind`, `inherited`.
- For generics, the planner needs both directions of the inheritance graph:
  - *Up*: `NodeSchema.inherit_from: list[str]` lists generics the kind implements.
  - *Down*: `GenericSchema.used_by: list[str]` ([`backend/infrahub/core/schema/generated/genericnode_schema.py:21`](../../../../backend/infrahub/core/schema/generated/genericnode_schema.py)) lists concrete kinds that inherit from this generic. This is a direct reverse index — no iteration of `get_all()` is required.
- Generics can themselves have relationships defined on them; those relationships are inherited by every implementing kind via `RelationshipSchema.inherited=True`.

**Decision**: At plan time, build a per-request "schema view" backed by the schema's own indexes:

1. `kind → list[RelationshipSchema]` — read directly from `schema.relationships` per kind on demand (cached after first read).
2. `generic_kind → list[concrete_kind]` — read directly from `GenericSchema.used_by`. No `get_all()` iteration.
3. `kind → namespace` — read directly from each schema's `namespace` field on demand.

These accesses are O(1) per kind and the planner only touches kinds reachable from `source_kind` within `max_depth`, so the view stays scoped to the work actually needed. The cache is per-request to stay branch- and time-correct.

**Rationale**: Schema reads are already cached in `schema_branch`. With `used_by` available, the previously-considered eager `get_all()` pass is unnecessary — direct reads beat a one-shot reverse-index build when most requests touch only a small subset of kinds.

**Alternatives considered**:

- *Eagerly iterate `schema_branch.get_all()` once per request*: rejected — `used_by` already provides the down-index, and most requests touch only a fraction of the schema. Eager iteration would do strictly more work.
- *Cache the schema view across requests*: rejected — schema is branch- and time-specific; cross-request cache would need invalidation logic outside this work's scope.

---

## 3. Permission model — granularity and access pattern

**Findings**

- Permissions are **kind-level only**, expressed as `ObjectPermission(namespace, name, action, decision)` ([`backend/infrahub/permissions/resolver.py:74-93`](../../../../backend/infrahub/permissions/resolver.py), [`backend/infrahub/core/account.py:40-50`](../../../../backend/infrahub/core/account.py)). No object-level or attribute-level permissions exist.
- `PermissionManager.load_for_account(db, branch, default_branch_name, account_session)` loads the resolver once; thereafter `resolver.has_permission(ObjectPermission(...))` is in-memory.
- The relevant action for read access is `"view"`.
- `ALLOW_DEFAULT` vs `ALLOW_OTHER` distinguishes default-branch vs feature-branch permissions; both must be considered against the request's branch context.

**Decision**: The planner owns its own `KindPermissionCache` — it is **planner-internal**, not constructed or passed by callers. The planner exposes an explicit async `initialize()` method that performs the single `PermissionManager.load_for_account(...)` call and builds the cache. The cache exposes one method internally: `can_view(kind: str) -> bool`, which constructs the `ObjectPermission` and memoizes per kind. The planner consults `can_view` for every kind that appears in a candidate route and drops any route containing a forbidden kind. Calling `plan()` before `initialize()` raises `RuntimeError`.

**Rationale**: Permission granularity question (raised in the requirements checklist) resolves to **kind-level**: the existing system has no finer granularity to enforce. Object-level and attribute-level enforcement would require permission-system changes outside this work's scope.

**Alternatives considered**:

- *Filter object-by-object at query result time*: rejected — the spec requires plan-time pruning, and post-hoc filtering would still cost the same DB traversal we are trying to avoid.
- *Reuse a global permission cache*: rejected — permissions depend on the requesting account and branch; per-request scope is correct.

**Follow-up flag**: If a future requirement needs attribute-level or object-level permission pruning, the planner is the wrong layer; that would need to move filtering into the Cypher result projection.

---

## 4. Cypher generation idioms in this codebase

**Findings**

- The codebase already does dynamic Cypher assembly with parameter dictionaries: `branch.get_query_filter_path()` returns `(clause, params)` and call sites do `self.query_lines.append("WHERE " + clause)` plus `self.params.update(params)`.
- `NodeRelationshipsQuery` ([`backend/infrahub/core/query/node.py:1179-1249`](../../../../backend/infrahub/core/query/node.py)) uses `UNION` with same-schema return rows from separate per-direction matches. This is the established pattern for "one query, multiple shapes."
- APOC is generally avoided; native Cypher is preferred.
- Edge validity is verified with a `CALL (n, rel, peer) { ... ORDER BY r.branch_level DESC, r.from DESC, r.status ASC LIMIT 1 ... }` pattern that returns the authoritative edge per `(n, rel, peer)` triple.

**Decision**: The renderer dispatches on `branch.is_default` and emits one of **two** Cypher shapes. Both consume the same `Plan` and model the same underlying graph (every schema hop materializes as two `IS_RELATED` edges through an intermediate `:Relationship` vertex; arrow orientation encodes `OUTBOUND` / `INBOUND` / `BIDIR`; kind names appear as Neo4j labels for index-driven matching).

**Strategy A — default-branch fast path.** When `branch.is_default` is `True`, the default branch's flat history means there is at most one authoritative `IS_RELATED` edge per vertex pair, and at the requested point-in-time `$at` it is current iff `e.branch IN [$default_branch, $global_branch] AND e.status = "active" AND e.from <= $at AND (e.to IS NULL OR e.to >= $at)`. The renderer emits one `UNION ALL` branch per route (each route in its own `CALL { ... }` subquery), with every `IS_RELATED` edge validated by an **inline four-predicate WHERE** clause on its named edge variable. No `branch.get_query_filter_path(at=...)` clause and no latest-authoritative `LIMIT 1` subquery are needed. The `$at` predicates are required (not optional): Infrahub supports point-in-time queries, so an edge active *now* may have been inactive at `$at` (still pre-`from` or already past-`to`).

**Strategy B — user-branch QPP.** When `branch.is_default` is `False`, the latest-authoritative-edge ambiguity returns (a user-branch edge may shadow a default-branch edge), but a different optimization opens up: instead of emitting one fixed-length MATCH per route, the renderer emits **one quantified-path-pattern MATCH** parameterized by a planner-derived `$allowed_path_maps` (a nested `{start_kind: {rel_name: [end_kind, ...]}}` map). The QPP iterates the `(a)-[r1]->(rel:Relationship)<-[r2]-(b)` schema-hop pattern `{1, $max_path_length}` times, gating each iteration on (1) `r1` and `r2` being active on `[default, global, user]` at `$at` (the same four-predicate active-edge clause as strategy A but with `$valid_branches`), (2) the `(a, rel)` and `(rel, b)` pairs not having a user-branch deletion edge whose `from` is **after** the active edge's `from` and is itself current at `$at` — captured as `NOT EXISTS { ... :IS_RELATED {status: "deleted", branch: $user_branch} ... WHERE del.from > r1.from AND del.from <= $at AND (del.to IS NULL OR del.to >= $at) }`, and (3) `(a.kind, rel.name, b.kind)` being in `$allowed_path_maps`. Routes the planner pruned (permission, user-filter) contribute no entries to the map, so the QPP cannot walk through them. The label-union `(a:TypeA|TypeB|...)` pre-filter drives the label index; `a.kind` is read as a property only after the label cuts down the candidate set. This collapses N per-route MATCHes into one declarative walk and lets Neo4j's planner pick the search strategy.

The `del.from > r1.from` comparison is the critical asymmetry: a deletion supersedes the active edge only when it happened *after* the active edge began. Without it, an old deletion that the active edge already overrode would falsely invalidate the path.

The previously-considered single-strategy designs are rejected:

- *Per-hop inline-`CALL`-with-`LIMIT 1` for every branch context*: rejected — overkill on the default branch where the latest-version dance is unnecessary; the simpler four-predicate WHERE (branch, status, `from <= $at`, `to IS NULL OR to >= $at`) is provably equivalent and lets Neo4j fold the conjunction into edge-property filtering.
- *QPP for the default branch too*: rejected — strategy A is more direct on the default branch because every route is fully kind-pinned at the label level, giving Neo4j the strongest index-driven plan. QPP is more general but doesn't pay off when every kind is already known per hop.
- *Match-then-`UNWIND` post-hoc validation*: rejected for both strategies — materializes doomed paths before discarding them.

See [contracts/query-generator.md](contracts/query-generator.md) for both full shapes and the dispatch contract.

**Rationale**: One Cypher per request keeps it parameter-bound and within Neo4j's plan cache. Fixed-length per-route patterns let Neo4j use kind labels as starting points and eliminate the variable-length explosion that drove the original feature's perf concerns. `UNION ALL` is the idiom this codebase already uses.

**Alternatives considered**:

- *Iterative deepening with `*N..N`*: rejected — Neo4j cannot leverage kind labels in variable-length patterns as effectively as fixed-length ones, and we can't enforce per-hop relationship identifiers tightly.
- *APOC `apoc.path.expandConfig`*: rejected — adds a runtime dependency the codebase avoids, and parameter-binding is less straightforward.

---

## 5. Test layout and fixtures

**Findings**

- Unit tests for query classes live in `backend/tests/unit/core/test_path_traversal_query.py` and `test_reachable_nodes_query.py`. They test constructor validation only (no DB).
- Component tests live in `backend/tests/component/core/test_path_traversal_query.py`. They use real DB containers and existing fixtures like `jack_with_blue_tag` (creates Person and Tag nodes).
- Performance benchmark tests live in `backend/tests/query_benchmark/`.

**Decision**:

- Move the existing unit tests from `backend/tests/unit/core/test_path_traversal_query.py` and `test_reachable_nodes_query.py` to `backend/tests/unit/graph_traversal/`, mirroring the new source layout (Constitution IV — test files mirror source structure).
- Move the existing component tests from `backend/tests/component/core/` to `backend/tests/component/graph_traversal/` and extend them with cases that depend on the new behavior: (a) zero-route short-circuit, (b) permission-pruned route excluded from results, (c) two-route fanout produces both shapes.
- Add a new directory `backend/tests/unit/graph_traversal/planning/` for the planner and query-builder unit tests (pure functions, no DB).
- Add a `test_path_traversal_benchmark.py` in `query_benchmark/` exercising 1k / 10k / 100k-node fixtures with `pytest-benchmark` to validate SC-001 and SC-002.

**Rationale**: Mirrors the constitution's test pyramid — most coverage in unit tests, integration coverage where DB behavior matters, performance gate in the benchmark suite.

**Alternatives considered**: none worth recording.

---

## 6. Diagnostic logging conventions

**Findings**

- `backend/infrahub/log.py` exposes `get_logger(name)` returning a `structlog.stdlib.BoundLogger`. Fields are emitted as structured key-value pairs (JSON in prod, console in dev).
- Existing code uses `logger.info("event_name", field=value)`. Log levels follow `INFRAHUB_LOG_LEVEL`.

**Decision**: The planner logs a single structured event per request: `traversal_plan_computed` with fields `{source_kind, target_predicate, route_count, pruned_for_permission, pruned_for_user_filters, max_depth, branch}`. Each route is *not* logged individually at INFO level. A DEBUG-level event `traversal_plan_route` logs each route's kind sequence + relationship identifiers when verbose diagnostics are enabled. Object UUIDs are not logged (constitution VI).

**Rationale**: Satisfies FR-014 and SC-005 without log spam. Aligns with the structlog idiom.

**Alternatives considered**:

- *Add a GraphQL `_plan` field on the response*: rejected — out of scope per spec Assumptions, and exposing it would require new types in `path.py` / `reachable.py`.

---

## Resolved Clarifications

| Item | Resolution | Source |
|---|---|---|
| Permission granularity (flagged in requirements checklist) | Kind-level only — the permission system has no other granularity to enforce. | §3 above |
| 30% latency-improvement target on 100k-node graphs (flagged in spec SC-002) | Retained as the planning target. Benchmark gate will report actual delta; if not met, the planner remains correct and the SC is revised with evidence at `/speckit-analyze` time. | spec SC-002 |
| Where the new planner lives | `backend/infrahub/graph_traversal/planning/` package (top-level `graph_traversal/`, alongside the moved `path.py` and `reachable.py`). | §1, plan structure |
| How Cypher is generated | Branch-dependent. **Default branch**: one `UNION ALL` per route, each route in its own `CALL { ... }` subquery, with edge validity inlined as `e.branch IN [$default_branch, $global_branch] AND e.status = "active" AND e.from <= $at AND (e.to IS NULL OR e.to >= $at)` on each named edge variable. **User branch**: one quantified-path-pattern MATCH parameterized by `$allowed_path_maps`; per-edge active check uses the same four-predicate form (with `$valid_branches`), plus two `NOT EXISTS { … {status: "deleted", branch: $user_branch} … WHERE del.from > r.from AND del.from <= $at AND (del.to IS NULL OR del.to >= $at) }` clauses. Both strategies bind `$at` as a parameter to support point-in-time queries. Kind names interpolated as labels in both shapes; relationship identifiers, UUIDs, branch names, `$at`, and the path map remain parameter-bound. | §4 above |
| Reverse generic-to-concrete index | Use `GenericSchema.used_by` directly — no `get_all()` iteration. | §2 above |

No `[NEEDS CLARIFICATION]` items remain.
