# Quickstart: Developing the Schema-Based Planner

**Plan**: [plan-schema-planning.md](plan-schema-planning.md)

## Prerequisites

- Repo dependencies installed: `uv sync --all-groups`.
- A running Infrahub stack is **not** required for unit tests; it **is** required for component and benchmark tests. Spin one up only when needed: `uv run invoke dev.start` (or the project's equivalent).

## Local dev loop

### 1. Iterate on the planner (no DB needed)

```bash
# Run just the planning unit tests.
uv run pytest backend/tests/unit/graph_traversal/planning/ -x -q

# Run the path-traversal Query-class unit tests (moved from tests/unit/core/) to confirm wiring still validates inputs.
uv run pytest backend/tests/unit/graph_traversal/test_path_traversal_query.py -x -q
uv run pytest backend/tests/unit/graph_traversal/test_reachable_nodes_query.py -x -q
```

### 2. Run component tests (DB required)

```bash
# Brings up TestContainers; first run is slow.
uv run pytest backend/tests/component/graph_traversal/test_path_traversal_query.py -x -v
uv run pytest backend/tests/component/graph_traversal/test_reachable_nodes_query.py -x -v
```

### 3. Benchmark before/after

```bash
# Capture baseline on stable/develop first (separate branch).
uv run pytest backend/tests/query_benchmark/test_path_traversal_benchmark.py --benchmark-save=baseline

# Switch to feature branch, run again, compare.
uv run pytest backend/tests/query_benchmark/test_path_traversal_benchmark.py --benchmark-compare=baseline
```

## Manually inspecting a plan

When iterating on the planner, the fastest feedback is to print the plan rather than the Cypher:

```python
# In a REPL or scratch test with a loaded schema_branch and account.
# The planner's lifecycle is: sync __init__, then await initialize(), then sync plan().
planner = SchemaPlanner(
    schema_branch=schema_branch,
    branch=branch,
    account_session=session,
)
await planner.initialize(db=db)  # one-shot async setup; loads the permission cache
plan = planner.plan(
    source_kind="InfraDevice",
    terminal_predicate=TerminalByKinds(kinds=frozenset({"InfraInterface"})),
    max_depth=4,
    user_filters=UserFilters(),
)

for route in plan.routes:
    print(" -> ".join(route.kinds), "via", [h.relationship_identifier for h in route.hops])
print("pruned for permission:", len(plan.pruned_for_permission))
print("pruned for user filters:", len(plan.pruned_for_user_filters))
```

## Diagnostic logs

To see the structured plan diagnostics in the running backend:

```bash
INFRAHUB_LOG_LEVEL=DEBUG uv run invoke dev.start
# Then run a GraphQL query against InfrahubPathTraversal or InfrahubReachableNodes.
# Tail logs for: traversal_plan_computed (INFO) and traversal_plan_route (DEBUG)
```

The `traversal_plan_computed` event includes route counts and pruning totals; `traversal_plan_route` (DEBUG) emits each route's kind sequence and relationship identifiers. Object UUIDs are intentionally excluded (Constitution VI).

## Common pitfalls

1. **Confusing schema direction with traversal direction**: `HopDirection` is `OUTBOUND`, `INBOUND`, or `BIDIR`, mirroring the schema. The planner does **not** expand `BIDIR` into two `Hop`s — it copies the direction verbatim. The query builder emits a distinct two-edge Cypher pattern per direction. If a route is missing, check whether the schema relationship exists between the two kinds in either direction (the planner walks the schema bidirectionally for enumeration even though it preserves the recorded direction).
2. **Mistaking schema namespace for kind name**: `ObjectPermission` requires both `namespace` and `name` (kind). The planner's permission cache is responsible for splitting them — don't construct `ObjectPermission` ad-hoc elsewhere.
3. **Generic-kind leakage**: Generic kind names must never appear in `Hop.start_kind` or `Hop.end_kind`. If a unit test asserts `"CoreNode"` (or any generic) appears in a route's kinds, the planner has a bug.
4. **Cycle infinite-loop**: The planner caps enumeration at `max_depth`. If a unit test hangs, check that the iterative expansion bumps depth before recursing.
5. **Parameter name collisions**: When two routes share a hop index, relationship-identifier parameter names must still be unique (`$rel_route0_hop1` vs `$rel_route1_hop1`). The query builder enforces a route-id suffix. (Kind names are interpolated as labels, not parameters — no collision concern there.)
6. **Filter semantics on source/terminal**: `kind_filter` applies to *intermediate* kinds. Don't accidentally apply it to `source_kind` or `terminal_kind` — that breaks the spec's intent.
7. **Forgetting the `:Relationship` intermediary**: Each schema hop is **two** `IS_RELATED` edges through a `:Relationship` vertex (its `name` property holds the relationship identifier). When debugging a Cypher snapshot test, count edges as 2× the route length.

## Where to write changelog entries

This feature is user-visible (perf improvement + permission-aware filtering). Add a Towncrier fragment under `changelog/`:

```bash
# Choose: changed, fixed, security
cat > changelog/+infp-1991-schema-planning.changed.md <<'EOF'
Graph path traversal queries now use a schema-driven query planner that
constrains traversals to viable kind sequences and excludes routes the
requesting account cannot read.
EOF
```
