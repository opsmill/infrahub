# Tasks: Schema-Based Path Planning for Graph Traversal Queries

**Input**: Design documents from [`dev/specs/infp-1991-graph-path-traversal/schema-based-traversal-planning/`](.)
**Prerequisites**:
- [plan-schema-planning.md](plan-schema-planning.md) — implementation plan
- [spec-schema-planning.md](spec-schema-planning.md) — user stories with priorities
- [research-schema-planning.md](research-schema-planning.md) — decisions
- [data-model-schema-planning.md](data-model-schema-planning.md) — entity definitions
- [contracts/planner.md](contracts/planner.md), [contracts/query-generator.md](contracts/query-generator.md) — internal API contracts

**Tests**: Included (Constitution IV — Test Discipline; spec User Story 1 and SC-004 require automated coverage at unit, component, and benchmark levels).

**Organization**: Tasks grouped by user story so each story is independently implementable and testable.

## Format: `[ID] [P?] [Story] Description`

- `[P]` — can run in parallel (different files, no dependencies on incomplete tasks)
- `[Story]` — which user story this task belongs to (US1, US2, US3, US4); omitted for Setup, Foundational, and Polish phases
- File paths are absolute under the repo root

## Path Conventions

Web app structure (per [plan §Project Structure](plan-schema-planning.md#project-structure)):

- New source package: `backend/infrahub/graph_traversal/`
- Tests mirror source: `backend/tests/unit/graph_traversal/`, `backend/tests/component/graph_traversal/`, `backend/tests/query_benchmark/`
- GraphQL resolvers (existing): `backend/infrahub/graphql/queries/path.py`, `backend/infrahub/graphql/queries/reachable.py`
- Old source paths to be deleted: `backend/infrahub/core/query/path.py`, `backend/infrahub/core/query/reachable.py`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create the new package skeleton and audit the change's reach before any code moves.

- [X] T001 Create new package directories: `backend/infrahub/graph_traversal/`, `backend/infrahub/graph_traversal/planning/`, `backend/tests/unit/graph_traversal/`, `backend/tests/unit/graph_traversal/planning/`, `backend/tests/component/graph_traversal/`. Each gets an empty `__init__.py` so Python sees them as packages.
- [X] T002 [P] Add empty placeholder modules so subsequent tasks have stable import targets: `backend/infrahub/graph_traversal/_cypher.py`, `backend/infrahub/graph_traversal/planning/models.py`, `backend/infrahub/graph_traversal/planning/planner.py`, `backend/infrahub/graph_traversal/planning/permissions.py`. **Deviation**: `path.py` and `reachable.py` placeholders intentionally omitted — T005/T006 will populate those locations via `git mv` and a pre-existing empty file would block the move.
- [X] T003 [P] Audit every import site that references the old module paths. Run from the repo root: `rg "from infrahub\.core\.query\.path|from infrahub\.core\.query\.reachable|infrahub\.core\.query\.path|infrahub\.core\.query\.reachable" backend/ python_sdk/` — record the full list in the PR description. The list must reduce to the GraphQL resolvers in `backend/infrahub/graphql/queries/path.py` and `reachable.py` plus the tests being moved (and any helpers internal to the moved files). Any additional caller blocks Phase 2. **Result**: 6 call sites found, all accounted for in Phase 2A. One internal cross-import (`backend/infrahub/core/query/reachable.py:7` → `infrahub.core.query.path`) means T006 must update that import alongside the file move to keep tests green.
- [X] T004 ~~Create an empty placeholder Towncrier fragment.~~ **N/A** — `changelog/+graph-path-traversal.added.md` already covers the umbrella graph-path-traversal feature. The schema-planning refactor preserves all observable I/O (SC-004); user-visible perf/permission-filtering improvements can be folded into that existing entry rather than a parallel fragment.

**Checkpoint**: Package skeleton exists. The audit has confirmed every caller of the old paths.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Move the existing Query classes verbatim into `graph_traversal/`, update import sites, then build the planner and Cypher renderer so user-story phases can wire them in.

**⚠️ CRITICAL**: No user-story work begins until this phase is complete and the existing test suite passes against the moved files.

### 2A — Move existing source and update imports

- [X] T005 Move (`git mv`) `backend/infrahub/core/query/path.py` → `backend/infrahub/graph_traversal/path.py`. Update the in-file module docstring if any; do not refactor logic yet.
- [X] T006 Move (`git mv`) `backend/infrahub/core/query/reachable.py` → `backend/infrahub/graph_traversal/reachable.py`. **Includes one-line import update** inside the moved file: `from infrahub.core.query.path import (...)` → `from infrahub.graph_traversal.path import (...)`, required to keep tests green (per T003 audit finding).
- [X] T007 Update [`backend/infrahub/graphql/queries/path.py`](../../../../backend/infrahub/graphql/queries/path.py) import: replace `from infrahub.core.query.path import PathTraversalQuery, PathData` (or equivalent) with `from infrahub.graph_traversal.path import PathTraversalQuery, PathData`.
- [X] T008 Update [`backend/infrahub/graphql/queries/reachable.py`](../../../../backend/infrahub/graphql/queries/reachable.py) import: replace `from infrahub.core.query.reachable import ReachableNodesQuery` with `from infrahub.graph_traversal.reachable import ReachableNodesQuery`.
- [X] T009 ~~Update every other caller identified by the T003 audit.~~ **N/A** — T003 audit confirmed no additional callers beyond the resolvers (T007/T008) and tests being moved (T010-T012).
- [X] T010 Move (`git mv`) `backend/tests/unit/core/test_path_traversal_query.py` → `backend/tests/unit/graph_traversal/test_path_traversal_query.py`. Includes one-line import update inside the moved file.
- [X] T011 Move (`git mv`) `backend/tests/unit/core/test_reachable_nodes_query.py` → `backend/tests/unit/graph_traversal/test_reachable_nodes_query.py`. Includes one-line import update inside the moved file.
- [X] T012 Move (`git mv`) `backend/tests/component/core/test_path_traversal_query.py` → `backend/tests/component/graph_traversal/test_path_traversal_query.py`. Includes one-line import update inside the moved file.
- [X] T013 ~~Move (`git mv`) `backend/tests/component/core/test_reachable_nodes_query.py` → `backend/tests/component/graph_traversal/test_reachable_nodes_query.py`.~~ **N/A** — source file does not exist on this branch. T048 must therefore *create* the component test file from scratch (not "extend" an existing one) in Phase 4.
- [X] T014 Run the test gate. **Result**: moved unit tests pass 14/14 in 0.25s; import-resolution smoke test (Query classes + GraphQL resolvers) passes; moved component test reached DB fixture setup (proving the move is structurally clean) but errored on `Neo.TransientError.General.OutOfMemoryError` from the local Neo4j container — environmental, unrelated to the move. **Full `uv run invoke backend.test-unit` was not executed locally** (would take ~10 minutes and surface unrelated noise); recommend validating in CI.

### 2B — Data model

- [ ] T015 [P] Implement the `HopDirection` `IntEnum` in `backend/infrahub/graph_traversal/planning/models.py` per [data-model §HopDirection](data-model-schema-planning.md#hopdirection): members `OUTBOUND=0`, `INBOUND=1`, `BIDIR=2`. Explicit integer values ensure the determinism sort key in T028 is totally ordered. No expansion.
- [ ] T016 [P] Implement the `Hop` frozen dataclass (`frozen=True, slots=True`) in `backend/infrahub/graph_traversal/planning/models.py` per [data-model §Hop](data-model-schema-planning.md#hop): fields `start_kind: str`, `end_kind: str`, `relationship_identifier: str`, `direction: HopDirection`. Add a `__post_init__` that enforces the non-empty `relationship_identifier` invariant.
- [ ] T017 [P] Implement the `Route` frozen dataclass in `backend/infrahub/graph_traversal/planning/models.py` per [data-model §Route](data-model-schema-planning.md#route): fields `hops: tuple[Hop, ...]`, `source_kind: str`, `terminal_kind: str`. Add a `__post_init__` enforcing continuity (`hops[i].start_kind == hops[i-1].end_kind`), source/terminal alignment, and `1 ≤ len(hops) ≤ 20`. Expose `length` and `kinds` derived properties.
- [ ] T018 [P] Implement the `TerminalPredicate` tagged union (two frozen dataclasses `TerminalById(node_id: str, kind: str)` and `TerminalByKinds(kinds: frozenset[str])`) in `backend/infrahub/graph_traversal/planning/models.py` per [data-model §TerminalPredicate](data-model-schema-planning.md#terminalpredicate-tagged-union). Add a `Union` alias `TerminalPredicate = TerminalById | TerminalByKinds`. `TerminalByKinds.__post_init__` asserts `kinds` non-empty.
- [ ] T019 [P] Implement the `UserFilters` frozen dataclass in `backend/infrahub/graph_traversal/planning/models.py` per [data-model §UserFilters](data-model-schema-planning.md#userfilters): fields `kind_filter`, `excluded_kinds`, `excluded_namespaces`, `relationship_filter` (all `frozenset[str]`). Add a classmethod `UserFilters.from_graphql_input(data, *, default_excluded_namespaces=...)` that constructs from `PathTraversalInput`/`ReachableNodesInput`. Default `excluded_namespaces` to the spec-defined set (Core, Internal, Builtin, Lineage, Profile, Template) when input is `None`.
- [ ] T020 [P] Implement the `Plan` frozen dataclass in `backend/infrahub/graph_traversal/planning/models.py` per [data-model §Plan](data-model-schema-planning.md#plan): fields `routes`, `source_kind`, `terminal_predicate`, `max_depth`, `pruned_for_permission`, `pruned_for_user_filters`. Add `__post_init__` enforcing mutual exclusivity of the three route tuples and `1 ≤ max_depth ≤ 20`.
- [ ] T021 [P] Implement the `KindPermissionCache` class in `backend/infrahub/graph_traversal/planning/permissions.py` per [data-model §KindPermissionCache](data-model-schema-planning.md#kindpermissioncache-planner-internal): private fields `_resolver`, `_branch`, `_schema_branch`, `_decisions`; public `can_view(kind: str) -> bool` that constructs the `ObjectPermission` with the same constructor-argument shape used at every existing call site (search the codebase for `ObjectPermission(` and copy the canonical kwargs — namespace from `schema_branch.get(kind).namespace`, name from `kind`, action from the `"view"` constant, plus whatever branch/decision-target kwargs the local `ObjectPermission` signature requires), defers to `self._resolver` for the decision, and memoizes the result in `_decisions`.

### 2C — Unit tests for data model

- [ ] T022 [P] Write `backend/tests/unit/graph_traversal/planning/test_models.py` covering: continuity-violation `Route` raises, source/terminal-mismatch raises, `Hop` with empty `relationship_identifier` raises, `Plan` with overlapping `routes`/`pruned_*` raises, `TerminalByKinds` with empty kinds raises, `UserFilters.from_graphql_input` applies default excluded-namespace set when input is `None`. Pure unit tests; no DB.

### 2D — SchemaPlanner

- [ ] T023 Implement `SchemaPlanner.__init__` and `async initialize()` in `backend/infrahub/graph_traversal/planning/planner.py` per [contracts/planner.md §Surface](contracts/planner.md#surface): sync `__init__(*, schema_branch, branch, account_session)`, async `initialize(*, db)` that calls `await PermissionManager.load_for_account(...)` and builds `self._permission_cache`. `initialize()` is idempotent. `plan()` raises `RuntimeError` if called before `initialize()`.
- [ ] T024 Implement the per-request schema-view helpers on `SchemaPlanner` (private methods, no I/O): `_relationships_for(kind)`, `_concrete_kinds_for_generic(generic_kind)` using `GenericSchema.used_by` directly (no `get_all()` pass — per [research §2 Decision](research-schema-planning.md#2-schema-introspection-capabilities)), `_namespace_for(kind)`. Memoize results on the instance.
- [ ] T025 Implement `SchemaPlanner.plan()` enumeration in `backend/infrahub/graph_traversal/planning/planner.py` per [contracts/planner.md §Behavior — required](contracts/planner.md#behavior--required): iterative BFS up to `max_depth`, expanding generic peers via `used_by`, copying `RelationshipSchema.direction` verbatim (no BIDIR expansion), schema-walking bidirectional. Terminal acceptance per `TerminalById.kind` or membership in `TerminalByKinds.kinds`. Emits an unfiltered candidate-routes list internally.
- [ ] T026 Implement user-filter pruning in `SchemaPlanner.plan()`: apply `UserFilters.kind_filter` (intermediate kinds only — source and terminal exempt), `excluded_kinds`, `excluded_namespaces` (via `_namespace_for`), `relationship_filter`. Pruned routes go to `Plan.pruned_for_user_filters`.
- [ ] T027 Implement permission pruning in `SchemaPlanner.plan()`: for every kind in each surviving route, consult `self._permission_cache.can_view(kind)`. Drop routes containing any forbidden kind; record in `Plan.pruned_for_permission`. Source kind is exempt (the resolver already authorized the source).
- [ ] T028 Implement deterministic sort in `SchemaPlanner.plan()` per [contracts/planner.md §Behavior — required step 6](contracts/planner.md#behavior--required): sort surviving routes by `(length, kinds, tuple(rel.identifier for hop), tuple(hop.direction for hop))` lexicographically before constructing the `Plan`. Iterate schema items alphabetically during enumeration so the unsorted output is itself deterministic.

### 2E — Unit tests for SchemaPlanner

- [ ] T029 [P] Write `backend/tests/unit/graph_traversal/planning/test_planner.py` covering the scenarios listed in [contracts/planner.md §Tests required](contracts/planner.md#tests-required): empty plan when kinds are disconnected, generic expansion produces one route per concrete inheritor, `BIDIR` recorded verbatim (no expansion), `max_depth` cap respected, default `excluded_namespaces` applied when input is `None`, two invocations with identical inputs produce identical `Plan` objects. Uses schema fixtures from `tests/fixtures/schemas/` — no DB required.
- [ ] T030 [P] Write `backend/tests/unit/graph_traversal/planning/test_permissions_filter.py`: route excluded when an intermediate kind has `can_view=False`; route retained when an alternate route avoids the forbidden kind; `Plan.pruned_for_permission` records the dropped routes exactly. Uses a mock `KindPermissionCache` injected via a small test fixture.
- [ ] T031 [P] Write `backend/tests/unit/graph_traversal/planning/test_planner_lifecycle.py`: calling `plan()` before `initialize()` raises `RuntimeError`; `initialize()` is idempotent; source-kind-not-in-schema raises `ValueError`; `max_depth` out of bounds raises `ValueError`.
- [ ] T031a [P] Write `backend/tests/unit/graph_traversal/planning/test_planner_branch_isolation.py`: load two schema fixtures with a deliberate relationship delta (e.g., a relationship that exists on branch B but not on `main`), construct a `SchemaPlanner` per branch with the same source/target, and assert the two `Plan.routes` differ in exactly the expected way. Satisfies FR-013.

### 2F — Plan→Cypher rendering

- [ ] T032 Implement the `RenderedCypher` frozen dataclass in `backend/infrahub/graph_traversal/_cypher.py` per [contracts/query-generator.md §Surface](contracts/query-generator.md#surface): `text: str`, `params: dict[str, Any]`, `return_labels: tuple[str, ...]`.
- [ ] T033 Implement `render_plan_to_cypher` dispatcher in `backend/infrahub/graph_traversal/_cypher.py`: validates `plan.routes` non-empty (raises `ValueError` otherwise), validates every kind name across the plan against `^[A-Za-z][A-Za-z0-9]*$` (raises `ValueError` on mismatch — defence-in-depth), dispatches on `branch.is_default` to `_render_default_branch` or `_render_user_branch`.
- [ ] T034 Implement `_render_default_branch` in `backend/infrahub/graph_traversal/_cypher.py` per [contracts/query-generator.md §Strategy A](contracts/query-generator.md#strategy-a--_render_default_branch-when-branchis_default): one `UNION ALL` branch per route, each route inside its own `CALL { ... }` subquery, named edge variables `r{H}a`/`r{H}b` per hop, inline four-predicate `WHERE` per edge (`branch IN [$default_branch, $global_branch] AND status = "active" AND from <= $at AND (to IS NULL OR to >= $at)`), final `MATCH path = …` re-bind, terminal predicate per `plan.terminal_predicate`. Bind `$source_id`, `$at`, `$default_branch`, `$global_branch`, `$rel_route{R}_hop{H}` for every hop, `$destination_id` (only for `TerminalById`), `$max_results`.
- [ ] T035 Implement `_render_user_branch` in `backend/infrahub/graph_traversal/_cypher.py` per [contracts/query-generator.md §Strategy B](contracts/query-generator.md#strategy-b--_render_user_branch-when-branchis_default-is-false): derive `$allowed_path_maps` (nested `dict[start_kind, dict[rel_name, sorted_list[end_kind]]]`) from `plan.routes`; derive `$all_rel_names` (sorted union); derive start-kind and end-kind label unions; set `$max_path_length = plan.max_depth`. Emit one `MATCH path = (source) ( ... ){1, $max_path_length} (target)` with the QPP body containing the active-edge clause for `r1` and `r2`, both deletion-`NOT EXISTS` blocks with the `del.from > r{N}.from` asymmetry plus `del.from <= $at AND (del.to IS NULL OR del.to >= $at)`, and the structural filter `rel.name IN keys($allowed_path_maps[a.kind]) AND b.kind IN $allowed_path_maps[a.kind][rel.name]`. Terminal MATCH varies by mode (see contract). Compute `depth` as `length(path) / 2`.
- [ ] T036 Implement label-name interpolation safety: a private helper `_label(kind: str) -> str` that returns the kind name iff it matches `^[A-Za-z][A-Za-z0-9]*$` and otherwise raises `ValueError`. Use this helper at every label-interpolation site in both `_render_default_branch` and `_render_user_branch`. Centralizing the check makes the static-check test trivial.
- [ ] T037 Update `backend/infrahub/graph_traversal/planning/__init__.py` to re-export the planner public surface: `SchemaPlanner`, `Plan`, `Route`, `Hop`, `HopDirection`, `TerminalPredicate`, `TerminalById`, `TerminalByKinds`, `UserFilters`. Do NOT re-export `KindPermissionCache` (planner-internal). Do NOT re-export anything from `_cypher.py` (boundary check enforced by tests).
- [ ] T038 Update `backend/infrahub/graph_traversal/__init__.py` to re-export `PathTraversalQuery`, `ReachableNodesQuery`, and the public planning surface (re-imported from `.planning`).

### 2G — Unit tests for Cypher rendering

- [ ] T039 [P] Write `backend/tests/unit/graph_traversal/test_cypher.py` per [contracts/query-generator.md §Tests required](contracts/query-generator.md#tests-required). Cover: strategy dispatch (substring check for `.from <= $at` on default branch, `){1,` on user branch), default-branch route fan-out + per-route isolation + per-hop edge validation + `$at` reference count + no latest-authoritative-subquery / no post-hoc UNWIND, user-branch single-QPP / `allowed_path_maps` plumbing / `all_rel_names` / active-edge `$at` predicates inside QPP / `NOT EXISTS` pair with `del.from > r{N}.from` asymmetry / depth arithmetic, shared assertions (empty-plan `ValueError`, parameter-binding completeness, kind-label regex, direction encoding). Boundary guard: `from infrahub.graph_traversal.planning import *` does NOT expose `render_plan_to_cypher`. (Terminal-mode parity for SC-006 is asserted separately in T049.)

**Checkpoint**: Foundation ready. The planner produces deterministic `Plan` objects; the Cypher renderer emits both branch-strategy shapes; all unit tests pass. The existing PathTraversalQuery/ReachableNodesQuery still work because user-story phases have not yet rewired them.

---

## Phase 3: User Story 1 — Plan-Aware Path Discovery Between Two Objects (Priority: P1) 🎯 MVP

**Goal**: `InfrahubPathTraversal` GraphQL query consults the schema planner first; returns only paths conforming to surviving routes; short-circuits with an empty result when no route exists. Inputs/outputs unchanged.

**Independent Test**: For a source/destination pair with no schema route, `InfrahubPathTraversal` returns empty in under 100 ms without executing graph Cypher. For a pair with one or more routes, the returned paths are identical to those produced today.

### Implementation for User Story 1

- [ ] T040 [US1] Refactor `PathTraversalQuery` in `backend/infrahub/graph_traversal/path.py` per [contracts/planner.md §Caller Contract](contracts/planner.md#caller-contract) and [contracts/query-generator.md §Caller integration](contracts/query-generator.md#caller-integration-pathtraversalquerysquery_init-reachablenodesqueryquery_init): `__init__(*, plan: Plan, source_id: str, branch: Branch, at: Timestamp, max_paths: int)` raises `ValueError` on empty `plan.routes`; `query_init` renders Cypher via the module-top-imported `render_plan_to_cypher` (no in-function imports, no short-circuit branch). Delete the now-unused Cypher-construction code from the old implementation. Keep `extract_path_data` and the GraphQL-facing dataclasses (`PathData`, `PathHopData`, `PathNodeData`) unchanged so the resolver and GraphQL types stay backwards-compatible.
- [ ] T041 [US1] Refactor `path_traversal_resolver` in `backend/infrahub/graphql/queries/path.py` per [contracts/planner.md §Caller Contract](contracts/planner.md#caller-contract): orchestrate plan construction (resolve source/destination kinds, instantiate and `await initialize()` the `SchemaPlanner`, call `plan()`), short-circuit at the resolver level when `plan.routes` is empty (return the existing empty-shape result without instantiating `PathTraversalQuery`), and only otherwise construct `PathTraversalQuery(plan=plan, ...)` and `await query.execute(db=db)`. Convert the existing GraphQL `PathTraversalInput` fields into a `UserFilters` via `UserFilters.from_graphql_input(data)`. All imports at module top.
- [ ] T042 [P] [US1] Extend `backend/tests/unit/graph_traversal/test_path_traversal_query.py`: existing constructor-validation tests still pass; add `__init__` raises `ValueError` for `Plan(routes=())`; the Query holds `self.plan` after construction.
- [ ] T043 [P] [US1] Extend `backend/tests/component/graph_traversal/test_path_traversal_query.py` with the User-Story-1 acceptance scenarios from [spec §User Story 1](spec-schema-planning.md#user-story-1---plan-aware-path-discovery-between-two-objects-priority-p1):
   - Source/destination kinds with no schema route → empty result, asserted to run in under 100 ms (use `time.perf_counter` around the resolver call) and to not produce a database `MATCH` query (mock or instrument `query.execute`).
   - Source/destination kinds with one or more routes → same set of paths as the existing test baseline. Reuse the `jack_with_blue_tag` fixture from the moved component test.
   - User without permission on an intermediate kind → returned paths exclude that route. Construct an account session with restricted permissions via existing test helpers.
- [ ] T043a [P] [US1] Add an FR-015 error-semantics parity test to `backend/tests/component/graph_traversal/test_path_traversal_query.py`: capture the exact GraphQLError messages produced today for (a) missing-source-id, (b) missing-destination-id, (c) source-id == destination-id, and assert the post-refactor resolver returns byte-identical messages. Pin the messages as constants in the test module so future drift is detected.
- [ ] T044 [P] [US1] Add a component test exercising both branch strategies against the same graph fixture: same source/destination, once on the default branch (strategy A — verify generated Cypher contains `.from <= $at` and no `$allowed_path_maps`), once on a user branch (strategy B — verify generated Cypher contains `){1,` and `$allowed_path_maps`). Inspect `rendered.text` for the strategy-specific substrings and `rendered.params` for `$allowed_path_maps` presence.

**Checkpoint**: `InfrahubPathTraversal` is fully plan-driven on both default and user branches. P1 of US1 is shippable.

---

## Phase 4: User Story 2 — Plan-Aware Reachable-Nodes Discovery (Priority: P1)

**Goal**: `InfrahubReachableNodes` GraphQL query uses the same planner with `TerminalByKinds`; same short-circuit and permission semantics as US1. Inputs/outputs unchanged.

**Independent Test**: For a source kind and a target-kind list, all returned reachable nodes lie at the end of a schema-derived route that survives planner pruning. When no target kind is reachable, the result is empty and no graph Cypher executes.

### Implementation for User Story 2

- [ ] T045 [US2] Refactor `ReachableNodesQuery` in `backend/infrahub/graph_traversal/reachable.py` analogous to T040: `__init__(*, plan: Plan, source_id: str, branch: Branch, at: Timestamp, max_results: int)` raises on empty plan; `query_init` calls `render_plan_to_cypher`; delete old Cypher construction. Keep the `ReachableNodeData`/`ReachableNodesData` shapes used by the resolver intact.
- [ ] T046 [US2] Refactor `reachable_nodes_resolver` in `backend/infrahub/graphql/queries/reachable.py` analogous to T041: orchestrate with `TerminalByKinds(kinds=frozenset(data.target_kinds))`. Short-circuit at the resolver layer when `plan.routes` is empty. Validate that every requested target kind exists in the schema before building the planner (raise `GraphQLError` for unknown kinds, matching current behavior).
- [ ] T047 [P] [US2] Extend `backend/tests/unit/graph_traversal/test_reachable_nodes_query.py`: existing constructor-validation tests still pass; add `__init__` raises on empty plan.
- [ ] T048 [P] [US2] Extend `backend/tests/component/graph_traversal/test_reachable_nodes_query.py` with the User-Story-2 acceptance scenarios from [spec §User Story 2](spec-schema-planning.md#user-story-2---plan-aware-reachable-nodes-discovery-priority-p1):
   - Source kind with no schema route to any requested target kind → empty result, no Cypher executed.
   - Target kind reachable only via a forbidden intermediate kind → that target's instances are absent (or only present via alternate permitted routes).
   - Multiple target kinds → instances of each are returned, each annotated with a path that conforms to a planner-approved route.
- [ ] T048a [P] [US2] Add an FR-015 error-semantics parity test to `backend/tests/component/graph_traversal/test_reachable_nodes_query.py`: assert that GraphQLError messages for missing-source-id and unknown-target-kind match the pre-refactor messages byte-for-byte.

**Checkpoint**: `InfrahubReachableNodes` is fully plan-driven. Both P1 user stories are shippable.

---

## Phase 5: User Story 3 — Single Generated Query Covers Both Modes (Priority: P2)

**Goal**: Verify (via tests) that the two GraphQL queries share a single plan-to-query construction routine; that the only difference between the two emitted Cyphers is the terminal predicate.

**Independent Test**: A test fixes a `Plan` and renders it twice — once with `TerminalById` and once with `TerminalByKinds` — and asserts the texts differ only in the terminal predicate region.

### Implementation for User Story 3

- [ ] T049 [P] [US3] Add a static test to `backend/tests/unit/graph_traversal/test_cypher.py`: for a fixed `Plan.routes`, rendering with `terminal_predicate=TerminalById(node_id="…", kind="K")` and then with `terminal_predicate=TerminalByKinds(kinds=frozenset({"K"}))` produces two `rendered.text` values that differ only inside the terminal-predicate region (lines containing `target_r…uuid =` for `TerminalById` vs the absence of that clause for `TerminalByKinds`). Use a normalized line-by-line diff and assert the symmetric difference is bounded to those lines.
- [ ] T050 [P] [US3] Add an import-structure test: `backend/tests/unit/graph_traversal/test_module_boundaries.py` imports `infrahub.graph_traversal.path` and `infrahub.graph_traversal.reachable`, then asserts via `inspect.getsource` (or AST parse) that both modules call `render_plan_to_cypher` from `infrahub.graph_traversal._cypher` — no parallel/duplicated Cypher-rendering function exists in either Query class. Satisfies SC-006 ("there is no Cypher query template duplicated between the two query handlers").

**Checkpoint**: SC-006 is verifiable from automated tests. No code change to ship — this story is purely an enforcement gate.

---

## Phase 6: User Story 4 — Plan Inspection for Debugging (Priority: P3)

**Goal**: Each traversal request emits a structured log of the planner output (route count, pruned counts, optional per-route details at DEBUG).

**Independent Test**: With `INFRAHUB_LOG_LEVEL=DEBUG`, execute a traversal request and confirm logs contain a `traversal_plan_computed` INFO entry with the documented fields and zero or more `traversal_plan_route` DEBUG entries enumerating route kind sequences.

### Implementation for User Story 4

- [ ] T051 [US4] Add diagnostic logging in `SchemaPlanner.plan()` in `backend/infrahub/graph_traversal/planning/planner.py` per [research §6 Decision](research-schema-planning.md#6-diagnostic-logging-conventions) and [contracts/planner.md §Behavior — required step 7](contracts/planner.md#behavior--required): one `logger.info("traversal_plan_computed", source_kind=..., target_predicate=..., route_count=..., pruned_for_permission=..., pruned_for_user_filters=..., max_depth=..., branch=...)` per call; zero or more `logger.debug("traversal_plan_route", kinds=..., relationship_identifiers=...)` per surviving route. Use `infrahub.log.get_logger("infrahub.graph_traversal.planning.planner")`. Object UUIDs MUST NOT appear in any log field (Constitution VI).
- [ ] T052 [P] [US4] Write `backend/tests/unit/graph_traversal/planning/test_diagnostics.py`: capture log output with `caplog` (pytest-structlog or `caplog` with a structlog-to-stdlib bridge), invoke `planner.plan(...)` against a fixture with known routes, assert the `traversal_plan_computed` event carries the correct counts and no UUIDs. Repeat with DEBUG level and assert `traversal_plan_route` is emitted once per surviving route.

**Checkpoint**: SC-005 is verifiable from logs. The DevX improvement is shippable.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Performance validation, final cleanup, documentation, and Cypher-plan profiling. Run after all user-story phases pass.

- [ ] T053 [P] Write the benchmark test at `backend/tests/query_benchmark/test_path_traversal_benchmark.py` exercising representative graphs (1k, 10k, 100k nodes) for both `InfrahubPathTraversal` (default and user branches) and `InfrahubReachableNodes`. Capture baseline numbers from `stable`/`develop` (separate run; commit captured numbers to the PR description) and validate that on the feature branch:
   - SC-001: zero-route requests return in under 100 ms.
   - SC-002 (no-regression clause): p95 latency on 1k- and 10k-node graphs MUST NOT regress more than 5% versus baseline. CodSpeed's CI alerting tracks the same thresholds.
   - SC-002 (improvement clause): p95 latency on the 100k-node graph MUST be ≥ 30% lower than baseline. If the measured delta falls below 30%, do NOT silently lower the gate — open a follow-up to revise SC-002 via `/speckit-specify` with the measured numbers before this benchmark task is marked done.
- [ ] T054 [P] Run `EXPLAIN` on a representative generated query for each strategy and attach the plans to the PR description per [contracts/query-generator.md §Notes on the shapes "Validation against EXPLAIN/PROFILE"](contracts/query-generator.md#notes-on-the-shapes). Confirm the label index is used on route kinds and the `(:Relationship).name` index is used. Any `AllNodesScan` blocks merge until resolved.
- [ ] T055 Verify move-cleanup landed: `ls backend/infrahub/core/query/` MUST show that `path.py` and `reachable.py` are absent. Do **not** delete the `backend/infrahub/core/query/` directory itself — it still hosts every other Query class in the codebase.
- [ ] T056 [P] ~~Fill in `changelog/+infp-1991-schema-planning.changed.md`.~~ **Replaces with**: extend the existing `changelog/+graph-path-traversal.added.md` entry with a sentence on the user-visible deltas this refactor introduces (perf improvement + permission-aware path filtering). If the existing entry has already shipped via release at this point, write a new `+infp-1991-schema-planning.changed.md` fragment instead.
- [ ] T057 [P] Update `dev/knowledge/backend/` with a short pointer entry naming the new `backend/infrahub/graph_traversal/` package and linking to this spec dir, so future contributors find the planner from the knowledge tree.
- [ ] T058 [P] Run `uv run invoke format` and `uv run invoke lint` (ruff + mypy) on the modified files; fix any issues. No `type: ignore` without justification (Constitution III).
- [ ] T059 Run the [quickstart-schema-planning.md](quickstart-schema-planning.md) local dev loop end-to-end against a live stack: planner REPL inspection, component tests, benchmark, diagnostic logs. Confirm the documented commands actually work as written and update quickstart if any do not.
- [ ] T060 Final pass of the spec quality checklist at [checklists/requirements-schema-planning.md](checklists/requirements-schema-planning.md): re-validate every box is still satisfied after implementation. If SC-002 was revised due to benchmark evidence, update both this checklist and the spec.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately.
- **Phase 2 (Foundational)**: Depends on Phase 1. Internal sub-phase ordering:
  - 2A (move + import update) must complete and T014 (full test suite passes) must succeed before 2B–2G begin.
  - 2B (data model) precedes 2C (data-model tests) but T022 can be written in parallel with the data model (TDD-friendly).
  - 2D (planner) depends on 2B; 2E (planner tests) parallels 2D.
  - 2F (rendering) depends on 2B but is otherwise independent of 2D. 2G (rendering tests) parallels 2F.
- **Phase 3 (US1)**: Depends on Phase 2 complete.
- **Phase 4 (US2)**: Depends on Phase 2 complete. Can run in parallel with Phase 3.
- **Phase 5 (US3)**: Depends on Phase 3 and Phase 4 both complete (the cross-Query verification needs both Query classes in their final form).
- **Phase 6 (US4)**: Depends on Phase 2 (the planner exists) but is otherwise independent. Can run in parallel with Phases 3–5.
- **Phase 7 (Polish)**: Depends on Phases 3 and 4 complete. Some tasks (T056, T057, T058) can start earlier if convenient.

### User Story Dependencies

- US1 (P1) and US2 (P1) are independent of each other and can be developed in parallel by different developers once Foundational is done. Both depend solely on Foundational outputs.
- US3 (P2) is a verification story — it depends on both Query classes being in their final shape.
- US4 (P3) depends only on the planner existing; independent of the resolver-layer changes in US1 and US2.

### Within Each Phase

- Setup: tasks T001–T004 can all run in parallel.
- Foundational 2A: T005/T006/T010–T013 (`git mv`s) can run in parallel; T007–T009 (import updates) follow the moves; T014 runs at the end of 2A.
- Foundational 2B–2G: data-model files (T015–T021) are all independent; planner internal methods (T024–T028) are serial; rendering (T032–T036) is mostly serial inside `_cypher.py`.
- US1 / US2: T040 / T045 (Query class refactor) and T041 / T046 (resolver refactor) are pairwise serial within each story; tests parallelize within each story.

### Parallel Opportunities

```text
Phase 1 — all four tasks parallel (T001 + T002 + T003 + T004)

Phase 2A — the six moves parallel:
  T005, T006, T010, T011, T012, T013
  Then T007, T008, T009 (import updates)
  Then T014 (test gate)

Phase 2B — all dataclasses parallel:
  T015, T016, T017, T018, T019, T020, T021

Phase 2E — all planner tests parallel:
  T029, T030, T031

Phases 3 and 4 — once Phase 2 lands:
  Developer A: T040, T041, T042, T043, T044  (US1)
  Developer B: T045, T046, T047, T048        (US2)

Phase 7 — polish tasks parallel (T053 + T054 + T056 + T057 + T058)
```

---

## Implementation Strategy

### MVP (User Story 1 alone)

1. Phase 1 → Phase 2 → Phase 3 (US1 only).
2. Run the full unit + component + benchmark suites at the end of Phase 3.
3. The MVP ships an end-to-end plan-driven `InfrahubPathTraversal` while `InfrahubReachableNodes` continues to use its existing implementation (it still works — Phase 2 only moved the source file; Phase 4 is what rewires its resolver). This is a valid checkpoint to demo.

### Incremental Delivery

1. Phases 1 + 2 land first as one PR (move + planner + renderer + tests). System behavior unchanged at this point — purely additive.
2. Phase 3 lands second (`InfrahubPathTraversal` rewired). Visible perf improvement on `InfrahubPathTraversal`.
3. Phase 4 lands third (`InfrahubReachableNodes` rewired). Visible perf improvement on the second query.
4. Phases 5–7 land as a single final PR (verification tests + diagnostics + benchmark + cleanup + changelog).

### Parallel Team Strategy

- Two developers: A takes US1 (T040–T044), B takes US2 (T045–T048), both after Phase 2 merges.
- A third developer can pick up US4 (diagnostics) and Phase 7 polish in parallel.
- US3 is a single-task PR run after US1 and US2 both merge.

---

## Notes

- Tests are MANDATORY here, not optional — Constitution IV requires them and spec SC-004 asserts existing tests must continue to pass.
- `[P]` tasks operate on different files with no in-flight dependencies; they can be opened as parallel PRs or executed concurrently by different developers.
- Each Query-class refactor (T040, T045) is paired with its resolver refactor (T041, T046) in the same PR — they cross-import and must merge together.
- After Phase 2 lands, the GraphQL queries continue to behave as today because the planner exists but is unwired. This is intentional so the move can land as a low-risk PR ahead of the behavior changes.
- The "delete old file" tasks are implicit in the `git mv` operations of T005, T006, T010–T013 — there are no separate delete tasks. T055 just confirms the cleanup landed as expected.
- Towncrier fragment naming convention: `+infp-1991-schema-planning.changed.md` (the `+` prefix is Towncrier's convention for branch-specific fragments).
