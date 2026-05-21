# Phase 0 Research: Schema-Based Path Planning

**Feature**: Schema-Based Path Planning for Graph Traversal Queries
**Plan**: [plan-schema-planning.md](plan-schema-planning.md)
**Spec**: [spec-schema-planning.md](spec-schema-planning.md)

This research consolidates findings from a code exploration of the current path traversal subsystem, the Infrahub schema API, the permission system, existing Cypher generation idioms, the test layout, and the diagnostic logging infrastructure. Each section ends with a **Decision** that resolves an unknown in the plan.

---

## 1. Current PathTraversalQuery / ReachableNodesQuery shape

**Findings**

- Both classes inherit `Query` (`backend/infrahub/core/query/__init__.py`). The base provides `params: dict`, `query_lines: list[str]`, `return_labels: list[str]`, async `execute(db)`, and per-row `QueryResult` traversal.
- `PathTraversalQuery` (`backend/infrahub/core/query/path.py:79-214`) emits a single variable-length Cypher pattern `MATCH path = (source)-[:IS_RELATED*2..N]-(target)` with where-clause filters for branch, namespace, kind, and relationship identifier, then validates each edge in a `CALL { ... }` subquery, then orders by `length(path)` and limits.
- `ReachableNodesQuery` (`backend/infrahub/core/query/reachable.py:25-141`) follows the same shape but pivots the terminal predicate to `target:Node` whose `kind` is in `$target_kinds`.
- Return data is exposed through frozen dataclasses (`PathData`, `PathHopData`, `PathNodeData`) that now live in `backend/infrahub/graph_traversal/results.py`. `PathNodeData` carries just `uuid` and `kind` — the GraphQL resolver loads richer display metadata separately via `NodeManager.get_many` and merges it at response time. Path extraction is a private static method on each Query class (`PathTraversalQuery._extract_path_data` consumes the structured `path_data` list projected by the new Cypher; `ReachableNodesQuery._extract_path_data` consumes a Neo4j Path until Phase 4 rewires it).
- Branch and temporal filtering is reused via `branch.get_query_filter_path(at=...)`; returns a `(clause: str, params: dict)` tuple suitable for interpolation into a `WHERE` slot.

**Decision**: The **GraphQL resolver** is the orchestrator: it resolves the source/destination objects, constructs and initializes the `SchemaPlanner`, calls `plan()`, and short-circuits at the resolver level when `plan.is_empty` (no pointless `Query.execute()` reaches the database). Only when a non-empty plan exists does it instantiate `PathTraversalQuery(plan=plan, …)` or `ReachableNodesQuery(plan=plan, …)`. The Query class takes a non-empty `Plan` in `__init__` (it raises `ValueError` if given an empty one — a defensive backstop) and renders Cypher in `query_init` via the shared private helper at `backend/infrahub/graph_traversal/_cypher.py` (`render_plan_to_cypher`). The Query class never calls the planner. All imports live at module top. The planner package does **not** import or emit Cypher.

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

**Decision (current)**: The renderer emits a **single quantified-path-pattern (QPP) MATCH** for both default-branch and user-branch requests, parameterized by a planner-derived `$allowed_path_maps` (nested `{start_kind: {rel_name: [end_kind, ...]}}`). The QPP body uses *undirected* `-[:IS_RELATED]-` arrows so it can match all three schema-direction storage orientations (`OUTBOUND`/`INBOUND`/`BIDIR`) in one pattern; `$allowed_path_maps` enforces the structural `(start_kind, rel_name, end_kind)` constraint per iteration. Source and target-by-uuid endpoints are resolved through their active `IS_PART_OF` edge to `Root` with `ORDER BY ... LIMIT 1` to handle kind migrations safely. The two branch-conditional pieces are:

- `$valid_branches` — `[default, global]` on the default branch, `[default, global, user]` on a user branch.
- A user-branch-only `NOT EXISTS { ... :IS_RELATED {status: "deleted", branch: $user_branch} ... }` deletion-supersedes filter inside the QPP body, with the `del.from > rN.from` asymmetry that ensures deletions only supersede strictly-newer active edges.

The default branch needs no version race resolution (`[default, global]` carries at most one authoritative edge per pair at `$at`) so it skips the deletion filter, but otherwise reuses the same query shape.

See [contracts/query-generator.md](contracts/query-generator.md) for the full template.

**Rationale**: One Cypher shape covers both branches. The QPP collapses N per-route MATCHes into one declarative walk and lets Neo4j's planner pick the search strategy; the planner-derived structural map cuts the search space without per-route fan-out. Endpoint matches use the canonical "latest active IS_PART_OF" pattern already used elsewhere in Infrahub, which handles the migration case where the same UUID exists on multiple `:Node` vertices.

**Alternative preserved for future evaluation — per-route UNION ALL on the default branch**: an earlier design split the renderer into two strategies (UNION ALL fan-out for the default branch, QPP for the user branch). On the default branch's flat history there's at most one authoritative edge per pair, so each route can be emitted as a fixed-length MATCH inside its own `CALL { ... }` subquery, joined by `UNION ALL`. This shape gives Neo4j stronger per-route specialization and may outperform the unified QPP when the planner emits many routes through wide label sets. The dispatch is a 5-line change inside `_cypher.py` (no caller impact). Re-evaluate against the benchmark task (SC-002): if `EXPLAIN` on the unified QPP shows an `AllNodesScan` or p95 latency on 100k-node graphs is materially worse than the fan-out shape, switch the default branch to the alternative. See [contracts/query-generator.md §Alternative](contracts/query-generator.md#alternative-per-route-union-all-for-default-branch) for the full template and parameter deltas.

**Other alternatives rejected**:

- *Iterative deepening with `*N..N`*: rejected — Neo4j cannot leverage kind labels in variable-length patterns as effectively as fixed-length / QPP patterns, and we can't enforce per-hop relationship identifiers tightly.
- *APOC `apoc.path.expandConfig`*: rejected — adds a runtime dependency the codebase avoids, and parameter-binding is less straightforward.
- *Per-hop inline-`CALL`-with-`LIMIT 1` for every branch context*: rejected — overkill on the default branch where the latest-version dance is unnecessary; the simpler four-predicate WHERE (branch, status, `from <= $at`, `to IS NULL OR to >= $at`) is provably equivalent.
- *Match-then-`UNWIND` post-hoc validation*: rejected — materializes doomed paths before discarding them.

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

**Decision**: The planner logs a single structured event per request: `traversal_plan_computed` with fields `{source_kind, target_predicate, route_count, max_depth, branch}`. Each route is *not* logged individually at INFO level. A DEBUG-level event `traversal_plan_route` logs each route's kind sequence + relationship identifiers when verbose diagnostics are enabled. Object UUIDs are not logged (constitution VI). The planner no longer accumulates pruned-route accounting (filter and permission violations are dropped during BFS expansion, so there is nothing to count), so the log event omits the `pruned_for_*` fields the earlier design carried.

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
| How Cypher is generated | A **single quantified-path-pattern (QPP) MATCH** shared by both default-branch and user-branch requests, parameterized by `$allowed_path_maps` (`{start_kind: {rel_name: [end_kind, ...]}}`). The QPP body uses undirected `-[:IS_RELATED]-` arrows and validates each edge with the four-predicate form `r.branch IN $valid_branches AND r.status = "active" AND r.from <= $at AND (r.to IS NULL OR r.to >= $at)`. Branch-conditional pieces: `$valid_branches` is `[default, global]` on the default branch and `[default, global, user]` on a user branch; the user-branch query additionally emits two `NOT EXISTS { … {status: "deleted", branch: $user_branch} … WHERE del.from > rN.from AND del.from <= $at AND (del.to IS NULL OR del.to >= $at) }` deletion-supersedes clauses inside the QPP body. Kind names are interpolated as Neo4j labels for index-driven matching; relationship identifiers, UUIDs, branch names, `$at`, and `$allowed_path_maps` are parameter-bound. The per-route UNION ALL fan-out described in earlier drafts is preserved as a documented alternative — see §4 above. | §4 above |
| Reverse generic-to-concrete index | Use `GenericSchema.used_by` directly — no `get_all()` iteration. | §2 above |

No `[NEEDS CLARIFICATION]` items remain.
