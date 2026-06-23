# Implementation Plan: Schema-Based Path Planning for Graph Traversal Queries

**Branch**: `ajtm-05142026-traversal-schema-planning` | **Date**: 2026-05-14 | **Spec**: [spec-schema-planning.md](spec-schema-planning.md)
**Input**: Feature specification from [`spec-schema-planning.md`](spec-schema-planning.md)

## Summary

Replace the blind variable-length Cypher traversal in `PathTraversalQuery` and `ReachableNodesQuery` with a two-stage pipeline: (1) a schema-driven **planner** that enumerates the kind-sequences and relationship hops connecting a source kind to a destination object/kind, pruning routes the requester cannot read or that violate user-supplied filters; (2) a **plan-to-query translator** that emits a single parameterized Cypher query whose path patterns are constrained to those exact routes. The translator supports two terminal predicates — fixed destination uuid (for `InfrahubPathTraversal`) and destination-kind set (for `InfrahubReachableNodes`) — so both GraphQL queries share one code path. Inputs and outputs of both GraphQL queries remain unchanged.

## Technical Context

**Language/Version**: Python 3.12 (backend only — no UI work in this scope)
**Primary Dependencies**: Existing Infrahub stack — FastAPI, Pydantic 2.10, Neo4j 5.28 driver, structlog. No new dependencies.
**Storage**: Neo4j (existing graph), no schema/data changes.
**Testing**: pytest (unit tests under `backend/tests/unit/core/`, component tests under `backend/tests/component/core/`), pytest-benchmark for performance regression. Schema fixtures from existing `tests/fixtures/schemas/`.
**Target Platform**: Linux server (backend service).
**Project Type**: Single-project backend module — no client or contract artifacts shipped externally.
**Performance Goals**:
- For kind-pairs with no schema route at depth ≤ 20: short-circuit return < 100 ms (no DB I/O).
- For reachable kind-pairs: p95 latency no worse than current implementation; on 100k-node graphs target ≥ 30% improvement. To revise the 30% target downward, run `/speckit-specify` (or manually edit `spec-schema-planning.md` and the checklist) with the measured baseline-vs-feature numbers attached. `/speckit-analyze` is read-only and cannot perform the revision.
**Constraints**:
- Plan generation is in-process and synchronous; no network calls.
- Generated Cypher MUST be parameter-bound (constitution V/VI).
- Branch- and time-aware: planner reads schema for the request's branch at the requested time.
- Must not change the GraphQL input/output shape (FR-007, FR-008).
**Scale/Scope**:
- Schema sizes: hundreds of kinds, thousands of relationships per branch (typical Infrahub deployments).
- Plan size: bounded by max_depth × out-degree; we cap enumeration depth at the user's `max_depth` (≤ 20).
- Result sizes: capped by existing `max_paths` (≤ 100) and `max_results` (≤ 200).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-evaluated after Phase 1 design.*

| Principle | Status | Notes |
|---|---|---|
| I. Schema-Driven Integrity | ✅ | Feature *consumes* the schema as primary input. No schema changes. No generated-file edits. |
| II. Branch-Safe by Default | ✅ | Planner takes `branch` + `at` and reads `schema_branch` accordingly. Generated Cypher reuses existing `branch.get_query_filter_path()` patterns so branch/temporal filtering on edges is unchanged. |
| III. Type Safety & Explicit Contracts | ✅ | New module uses frozen `@dataclass` for `Plan`, `TerminalPredicate`, `UserFilters`, and the `results.py` shapes (`PathData`, `PathHopData`, `PathNodeData`). All public APIs typed. No `Optional[T]` — use `T \| None`. |
| IV. Test Discipline | ✅ | Unit tests for planner (schema-only, no DB) covering edge cases from spec §Edge Cases. Component tests covering integration with `Query.execute()`. Benchmark test under `tests/query_benchmark/` for SC-001/SC-002 validation. No functional-test tier is required: this refactor preserves the existing GraphQL→backend→DB layering; new behavior (planner + Cypher renderer) is covered at the unit level, and end-to-end correctness is verified by the existing component tests at the GraphQL boundary. |
| V. Query Performance & Efficiency | ✅ | This refactor *is* the performance improvement. Generated Cypher returns only fields needed. Parameter-bound. Benchmark gates included. No N+1 (single Cypher per request). |
| VI. Security & Input Boundaries | ✅ | Plan-time permission pruning is defense-in-depth; existing API authentication is unchanged. All Cypher parameterized. User-supplied kind/relationship lists pass through Pydantic-validated GraphQL inputs (already enforced). |
| VII. Simplicity & Maintainability | ✅ | Reduces duplication: two Cypher templates → one. New module is internal; no new external abstractions. No new dependencies. |

### Frontend principles

Not applicable — no UI changes.

### Shared Components Inventory

Not applicable — backend-only feature.

**Result**: All gates pass. No Complexity Tracking entries needed.

## Project Structure

### Documentation (this feature)

```text
dev/specs/infp-1991-graph-path-traversal/
├── spec.md                                       # Original umbrella spec
└── schema-based-traversal-planning/
    ├── spec-schema-planning.md                   # This refinement's spec
    ├── plan-schema-planning.md                   # ← this file
    ├── research-schema-planning.md               # Phase 0 output
    ├── data-model-schema-planning.md             # Phase 1 output (entity definitions)
    ├── contracts/                                # Phase 1 output (internal API contracts)
    │   ├── planner.md
    │   └── query-generator.md
    ├── quickstart-schema-planning.md             # Phase 1 output
    ├── checklists/
    │   └── requirements-schema-planning.md
    └── tasks-schema-planning.md                  # Phase 2 output (/speckit-tasks — NOT in this command)
```

### Source Code (repository root)

```text
backend/infrahub/graph_traversal/        # NEW top-level package
├── __init__.py                          # Empty — callers import from concrete submodules
├── path.py                              # PathTraversalQuery — moved from backend/infrahub/core/query/path.py. Accepts a non-empty Plan in __init__ (raises ValueError on empty); query_init renders Cypher via _cypher.py. get_paths() delegates to extract_path_from_result in _extract.py. Does NOT call the planner.
├── reachable.py                         # ReachableNodesQuery — moved from backend/infrahub/core/query/reachable.py. Currently still consumes a Neo4j Path until it migrates onto the planner shape; once migrated it will also delegate to _extract.py. Does NOT call the planner.
├── results.py                           # Public dataclasses returned by the Query classes: PathData, PathHopData, PathNodeData. PathData carries a required start_node: PathNodeData plus hops: list[PathHopData] (hops excludes the start). PathHopData.relationship_identifier is a required str — every hop is reached via an edge. PathNodeData carries just uuid + kind — the resolver loads display metadata separately via NodeManager and merges it at response time.
├── _cypher.py                           # Private helper: Plan→Cypher rendering. Single QPP MATCH for both default- and user-branch requests, parameterized by a planner-derived $allowed_path_maps. User-branch query adds two NOT EXISTS deletion-supersedes filters and extends $valid_branches. Projects start_node_uuid / start_node_kind / hops (list of {relationship_identifier, uuid, kind}) / depth rather than returning the full Neo4j Path. Used by path.py and reachable.py (two callers — Constitution VII).
├── _extract.py                          # Private helper: QueryResult → PathData. Owns the _HopRow TypedDict describing the per-hop projection and exposes extract_path_from_result(result) -> PathData | None for the Query classes to call. Returns None when the row has no start node or no hops so callers can skip degenerate rows. Used by path.py (and reachable.py once migrated).
└── planning/                            # NEW internal package — planner ONLY, no Cypher generation
    ├── __init__.py                      # Empty — callers import from concrete submodules
    ├── planner.py                       # SchemaPlanner (two-pass kind-BFS that builds an adjacency map)
    ├── models.py                        # Plan / TerminalPredicate / UserFilters dataclasses
    ├── constants.py                     # MIN_DEPTH / MAX_DEPTH / DEFAULT_EXCLUDED_NAMESPACES
    └── permissions.py                   # Per-request KindPermissionCache used by planner

backend/infrahub/core/query/
├── path.py                              # DELETED after move — no compatibility shim (Constitution VII)
└── reachable.py                         # DELETED after move — no compatibility shim

backend/infrahub/graphql/queries/
├── path.py                              # Resolver now orchestrates: resolves source/dest kinds, builds plan via SchemaPlanner, short-circuits on empty plan, only then instantiates PathTraversalQuery(plan=plan, ...). Imports updated to `from infrahub.graph_traversal.path import PathTraversalQuery`, `from infrahub.graph_traversal.results import PathData`, and `from infrahub.graph_traversal.planning.{models,planner,constants} import ...`.
└── reachable.py                         # Resolver orchestrates the equivalent flow with TerminalByKinds. Imports updated to `from infrahub.graph_traversal.reachable import ReachableNodesQuery` and `from infrahub.graph_traversal.planning import SchemaPlanner, TerminalByKinds, UserFilters`.

backend/tests/unit/graph_traversal/      # NEW (replaces backend/tests/unit/core/test_*_query.py)
├── test_path_traversal_query.py         # Moved + extended for plan-driven behavior (constructor validation, plan-empty short-circuit). Also exercises render_plan_to_cypher end-to-end.
├── test_reachable_nodes_query.py        # Moved + extended for plan-driven behavior
└── planning/
    ├── test_planner.py                  # Pure schema-driven planner tests
    └── test_permissions_filter.py       # Plan pruning by permission resolver

backend/tests/component/graph_traversal/ # NEW (replaces backend/tests/component/core/test_*_query.py)
├── test_path_traversal_query.py         # Moved + extended: zero-route short-circuit, permission pruning, two-route fanout
└── test_reachable_nodes_query.py        # Moved + extended

backend/tests/query_benchmark/
└── test_path_traversal_benchmark.py     # New — SC-001/SC-002 baseline vs new
```

**Structure Decision**: Promote graph-traversal queries out of `core/query/` into a dedicated top-level package `backend/infrahub/graph_traversal/`. The **GraphQL resolver** is the orchestrator — it constructs and initializes the `SchemaPlanner`, calls `plan()`, and decides (a) when to return an empty result without executing any Cypher and (b) when to instantiate the Query class with the plan. Each Query class accepts a non-empty `Plan` in its `__init__` and emits Cypher in `query_init` via the shared private helper `graph_traversal/_cypher.py`. The Query class never calls the planner. The `planning/` sub-package is **planner-only** — it produces a `Plan` and emits no Cypher; the Cypher boundary belongs to the Query layer (which has always owned Cypher in this codebase). The old `backend/infrahub/core/query/path.py` and `backend/infrahub/core/query/reachable.py` are **deleted** as part of this change — every import site (GraphQL resolvers in `backend/infrahub/graphql/queries/path.py` and `reachable.py`, plus any other consumers found by a repo-wide grep) is updated to import from `infrahub.graph_traversal.*`. No compatibility shim is left behind (Constitution VII). Tests move to mirror the source layout.

> **Import-site audit required**: Before deletion, `rg "from infrahub.core.query.path import|from infrahub.core.query.reachable import|infrahub\.core\.query\.path|infrahub\.core\.query\.reachable"` over `backend/` and `python_sdk/` must return only the call sites enumerated above (GraphQL handlers and tests being moved). Any additional callers identified by the audit are migrated in the same change set.

## Phase 0: Research

See [research-schema-planning.md](research-schema-planning.md).

## Phase 1: Design & Contracts

- Entities and their fields: [data-model-schema-planning.md](data-model-schema-planning.md).
- Internal API contracts: [contracts/](contracts/).
- Local developer flow: [quickstart-schema-planning.md](quickstart-schema-planning.md).

### Post-Design Constitution Re-check

| Concern raised in Phase 1 | Verdict |
|---|---|
| Permission lookups per kind could be N+1 if naive. | Mitigated by per-request `KindPermissionCache` (see [contracts/planner.md](contracts/planner.md)). One `PermissionManager.load_for_account` call per request; in-memory lookups thereafter. Constitution V satisfied. |
| Plan enumeration could explode on cyclic schemas. | Capped by `max_depth` (≤ 20). The planner emits a per-hop adjacency map via two-pass kind-BFS (forward from source, reverse from terminal-matching kinds) — working set is bounded by `reachable_kinds × relationships_per_kind`, not by the number of routes. Memory bounded; documented in research. |
| Generated Cypher must remain parameterized. | `_cypher.py`'s `render_plan_to_cypher` interpolates kind names as Neo4j labels (validated `^[A-Za-z][A-Za-z0-9]*$`) and parameter-binds relationship identifiers, UUIDs, and limits. User-supplied filter strings never enter the generated Cypher. Constitution VI satisfied. |
| Diagnostic logging risks leaking sensitive data. | Plan logs include kind names and relationship identifiers (already public via schema); they do NOT include object UUIDs or attribute values. Constitution VI satisfied. |

Re-evaluated: all gates still pass.

## Complexity Tracking

No violations — section intentionally empty.
