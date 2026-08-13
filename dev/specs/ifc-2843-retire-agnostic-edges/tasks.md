---

description: "Task list for retirement of branch-agnostic property edges (IFC-2843)"
---

# Tasks: Retirement of branch-agnostic property edges

**Input**: Design documents from `specs/ifc-2843-retire-agnostic-edges/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md,
critiques/critique-20260812.md (remediation already folded into the artifacts)

**Tests**: Included. Every functional requirement in spec.md carries a `Verify:` clause, the PRD
contributed a full Testing Decisions section, and constitution Principle IV requires tests written
before or alongside implementation.

**Branch**: `retire-agnostic-edges-ifc-2843` (off `release-1.11`)

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Exact file paths in every description

## Path Conventions

Backend-only change to an existing service. Source under `backend/infrahub/`, tests under
`backend/tests/{unit,component}/`, user docs under `docs/docs/`.

## ⚠️ Blocking gate before any implementation

`AGENTS.md` **Boundaries → Ask First** requires maintainer sign-off for database/migration changes.
This feature adds graph migration `m076`, bumps `GRAPH_VERSION` 75 → 76, and **hard-deletes**
customer `Attribute` / `Relationship` vertices during upgrade. T001 exists to obtain that sign-off
and must complete before T033 (the migration) begins. Phases 1–3 touch no migration and may proceed
in parallel with the sign-off request.

---

## Phase 1: Setup

**Purpose**: Read the governing guidance and create the package skeleton

- [ ] T001 Request maintainer sign-off for the migration gate: `m076`, `GRAPH_VERSION` 75 → 76, and the hard-delete of `Attribute`/`Relationship` vertices with no linked node. Record the outcome in `specs/ifc-2843-retire-agnostic-edges/plan.md` under Ask-First Gate.
- [ ] T002 [P] Read `dev/guidelines/backend/python.md` (typing, and §"Best-effort side effects degrade to a safe fallback" — the rule T024 depends on) and `dev/guidelines/backend/checklist.md`
- [ ] T003 [P] Read `dev/knowledge/backend/query-pattern.md` and `dev/knowledge/backend/database-schema.md` for the Query-class contract and edge-activity ordering (`branch_level DESC, from DESC, status ASC`)
- [ ] T004 Create the package `backend/infrahub/core/agnostic/__init__.py` and the test packages `backend/tests/unit/core/agnostic/__init__.py`
- [ ] T005 Commit the currently-untracked `backend/tests/component/core/test_agnostic_attribute_fork_window.py` unchanged, so the pre-fix leak it documents is recorded in history before the fix lands

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The invariant's three units. Both P1 user stories consume them — US1 through five
enforcement points, US2 through the query's unbounded form.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

### Types and the pure builder

- [ ] T006 [P] Define the frozen dataclasses `BranchWindow`, `BranchWindowSet`, `RetirementCandidates` (discriminated: explicit node ids / fork-point bound / unbounded) and `RetirementResult(edges_closed, vertices_removed)` in `backend/infrahub/core/agnostic/models.py`
- [ ] T007 [P] Write unit tests for the branch-window builder in `backend/tests/unit/core/agnostic/test_branch_windows.py`: default branch emits one pair and never collapses; a non-default branch emits two pairs and collapses its origin read to `branched_from`; a branch forked after `at` does not collapse; an empty branch list yields an empty set (not an error). Use hand-picked branch metadata, no DB fixtures.
- [ ] T008 Implement `AgnosticBranchWindowBuilder.build(branches, at)` in `backend/infrahub/core/agnostic/branch_windows.py`, mirroring the `min(at, branched_from)` collapse of `Branch.get_branches_and_times_to_query_global`. Expose **no** parameter to disable isolation (FR-012), so no future caller can reach for one.

### The query

- [ ] T009 Write component tests for the retirement query in `backend/tests/component/query/test_agnostic_retirement_query.py`, asserting graph shape directly (edge presence, `status`, `to`): unretained attribute closes; retained attribute stays open; relationship closes when either peer becomes unreachable; relationship stays open only while **both** peers are live with **both** `IS_RELATED` edges active on the same branch.
- [ ] T010 Implement `RetireAgnosticPropertyEdgesQuery` in `backend/infrahub/core/query/agnostic_retirement.py`. Candidate traversal MUST start from open, active global `HAS_ATTRIBUTE`/`IS_RELATED` edges (FR-011); anchor on the `:Node`/`:Attribute`/`:Relationship` labels, never on schema kinds; close `HAS_VALUE`, `IS_PROTECTED`, `HAS_SOURCE`, `HAS_OWNER` by `SET e.to = $at` (FR-013 — never a `deleted`-status edge); parameterise every value; expose `get_data() -> RetirementResult`.
- [ ] T011 Extend `RetireAgnosticPropertyEdgesQuery` to read the branch set from `(:Branch)` vertices in the same pass and compute the fork-window collapse in Cypher, so no stale branch list can reach the predicate. Verify the in-query collapse against `AgnosticBranchWindowBuilder` (T008) on the same inputs. **Never** source branches from `registry.branch` — it is per-worker, lazily filled and only ever pruned, so a branch created by another worker would be treated as non-retaining.
- [ ] T012 Add the three candidate bounds to `RetireAgnosticPropertyEdgesQuery` (explicit node ids, fork-point timestamp, unbounded) as swappable `MATCH` prefixes over one shared predicate body, with batching (`IN TRANSACTIONS OF n ROWS`) for the unbounded form
- [ ] T013 [P] Add a component test in `backend/tests/component/query/test_agnostic_retirement_query.py` asserting an `AttributeValue` shared by two attributes is never deleted while any attribute still references it (FR-017)
- [ ] T014 Run `EXPLAIN` on the candidate traversal under all three bounds and record the plans in `specs/ifc-2843-retire-agnostic-edges/research.md` under a new "Query plans" section (Principle V)

### The component

- [ ] T015 [P] Write unit tests for the retirement component in `backend/tests/unit/core/agnostic/test_retirement.py` using a **recording double** behind the query protocol (no mocks): assert the exact candidate sets and closure calls in order; assert a `Failing` double's exception does not propagate and leaves the edges untouched
- [ ] T016 Define the query `Protocol` and implement `AgnosticFieldRetirer.retire(candidates, at) -> RetirementResult` in `backend/infrahub/core/agnostic/retirement.py`. All constructor dependencies required (`db`, the query collaborator) — no optional injection, no late registration. The component never reads the clock; `at` is always supplied.
- [ ] T017 Add best-effort failure handling and logging to `AgnosticFieldRetirer` per `dev/guidelines/backend/python.md` §"Best-effort side effects degrade to a safe fallback": log the failure; fall back to **leaving the global edges open** (over-reserving — today's behaviour, never data loss); log edges closed, and the retaining-branch count when retirement is deferred

**Checkpoint**: The invariant is implemented and independently tested. Both user stories can now proceed in parallel.

---

## Phase 3: User Story 1 - Enforcement wherever a field stops being retained (Priority: P1) 🎯 MVP

**Goal**: On every path by which a branch-agnostic field stops being reachable from a live node on
any branch, its global property edges are retired; while a retaining branch exists, retirement is
deferred and re-evaluated whenever an event could have emptied the retaining set.

**Independent Test**: Exercise each enforcement point against a branch-aware kind carrying a
branch-agnostic attribute under a uniqueness constraint, asserting the graph shape after each
operation. Delivers value with no migration present.

**Ordering note**: Branch deletion comes **first**. It is the only enforcement point that gains a
query the others do not, so it carries the entire FR-018 performance risk. Measuring it before the
other four means a failed gate surfaces before four integrations are built on the assumption it
passed.

### Branch deletion and the performance gate (risk-first)

- [ ] T018 [US1] Write a component test in `backend/tests/component/core/test_agnostic_retirement.py` for branch deletion: a node deleted on the default branch while branch `B` retained it, then `B` is deleted → global edges closed (FR-008, acceptance scenario 5d)
- [ ] T019 [US1] Wire the fork-point-bounded retirement into `BranchDataDeleter._delete_agnostic_peers` in `backend/infrahub/core/branch/data_deleter.py`, alongside the existing branch-only cleanup. It MUST run **before** `_delete_edges` removes the branch's `IS_PART_OF` edges — the reachability determination reads them.
- [ ] T020 [US1] Measure FR-018 for branch deletion at **two** open-branch counts (~3 and ~100) using `backend/tests/query_benchmark/`, before and after, and record medians in `specs/ifc-2843-retire-agnostic-edges/quickstart.md`. Gate: ≤ +10% median at **both** counts. If breached, narrow the bound with the existence edge's `from` against the fork point and re-measure.

### Remaining enforcement points

- [ ] T021 [P] [US1] Write component tests in `backend/tests/component/core/test_agnostic_retirement.py` for node deletion: delete on the default branch with no branch forked during the object's lifetime → closed; delete on `B` an object existing only on `B` → closed immediately; delete on one of two branches holding it → stays open, then closed after the second (FR-005, scenarios 1–3)
- [ ] T022 [P] [US1] Write the **negative** component tests in the same file — these are what a naive implementation breaks: a branch forked between creation and deletion keeps the edges open, the value reserved, and the object readable on `B` (scenario 4); rebase or merge of a retaining branch on which the object survives leaves the edges open (scenario 6, FR-009)
- [ ] T023 [US1] Invoke retirement from `Node.delete` in `backend/infrahub/core/node/__init__.py`, after `NodeDeleteQuery` writes the existence tombstone, stamped with `delete_at` (FR-005, FR-015)
- [ ] T024 [US1] Verify the best-effort wrapper from T017 holds at this call site: a retirement failure must not fail the user's delete, and must not close anything (`dev/guidelines/backend/python.md` §"Best-effort side effects")
- [ ] T025 [P] [US1] Write a component test for merge in `backend/tests/component/core/test_agnostic_retirement.py`: delete on a branch, merge it → closed (FR-006, scenario 5c)
- [ ] T026 [US1] Invoke retirement from `DiffMerger.merge_graph` in `backend/infrahub/core/diff/merger/merger.py`, after the bulk merge queries complete, for the deleted nodes named by the merge diff, at the merge `at`
- [ ] T027 [P] [US1] Write a component test for rebase: a node deleted on the default branch while a branch is open, rebase that branch → closed (FR-007, scenario 5b); plus scenario 11 — a node created and deleted on `B`, then `B` rebased, leaves no vertex with open global edges
- [ ] T028 [US1] Invoke retirement from `rebase_branch` in `backend/infrahub/core/branch/tasks.py`, inside the existing `lock.registry.global_graph_lock()` and **before** `user_branch.rebase(...)` is applied, at `rebase_at`. Obtain the base-branch deletions via a second `DiffRepository` read under the existing tracking id (decided in plan.md §"Resolved during critique").
- [ ] T029 [P] [US1] Write component tests for schema removal: a branch-agnostic attribute removed from the schema → closed; likewise a relationship; and with a branch that forked beforehand → deferred and still readable there (FR-010, scenarios 8–9)
- [ ] T030 [US1] Invoke retirement from `NodeAttributeRemoveMigration` in `backend/infrahub/core/migrations/schema/node_attribute_remove.py` and `NodeRelationshipRemoveMigration` in `backend/infrahub/core/migrations/schema/node_relationship_remove.py`, after each existing removal query runs

### Cross-cutting correctness tests for US1

- [ ] T031 [P] [US1] Write a regression test in `backend/tests/component/core/test_agnostic_retirement.py`: rename a kind, then run every enforcement point → the surviving vertex keeps its value (FR-011, scenario 10). Confirms same-UUID copies are excluded by the open-edge anchor rather than by luck.
- [ ] T032 [P] [US1] Write a component test asserting retirement registers no change on a branch that forked before it — diff the pre-existing branch after a default-branch delete and assert no attribute or relationship change is reported for that node (FR-014)
- [ ] T033 [P] [US1] Replace the `_close_global_property_edges` stub in `backend/tests/component/core/test_agnostic_attribute_fork_window.py` with the real delete path and update the pre-fix assertion (`"expected to leave the global value edge open today"`). Both fork-window expectations must hold unchanged — that is the proof the time-close hedge of FR-013 works.
- [ ] T034 [P] [US1] Write the pool re-allocation test in `backend/tests/component/core/test_agnostic_retirement.py`: allocate, delete, retire, allocate again → the same value is returned (SC-007, scenario 12). Guards the three-edge `IS_RESERVED`/`HAS_VALUE`/`HAS_ATTRIBUTE` dependency documented in data-model.md.
- [ ] T035 [P] [US1] Write the late-branch-creation test: create a branch after candidate selection → the object stays readable on it. Bounds the residual race and locks in the degraded-read property that makes the time-close choice load-bearing.
- [ ] T036 [P] [US1] Write the out-of-scope boundary test: deleting a truly branch-agnostic *node* closes its edges exactly once and retirement is a no-op. `Node.delete` resolves `branch` to the global branch for such nodes, so the enforcement point does run against them.
- [ ] T037 [US1] Measure FR-018 for node deletion, branch merge and branch rebase at both open-branch counts and record medians in `quickstart.md`. Gate: ≤ +10% at both.

**Checkpoint**: User Story 1 is fully functional and independently testable. Deletes and schema removals no longer leak; SC-004 through SC-007 are demonstrable.

---

## Phase 4: User Story 2 - Existing damage repaired on upgrade (Priority: P1)

**Goal**: Upgrading retires the global property edges of every branch-agnostic field that no branch
retains, including the branch-deletion orphans that dominate the reported incident.

**Independent Test**: Build the orphan shapes as fixtures, run the migration, assert the edges are
closed or the vertices removed and the reported counts are correct. Delivers value with no
enforcement present — this is what unblocks a customer stuck today.

**Depends on**: T001 (migration gate sign-off) and Phase 2 (the query's unbounded form). Does
**not** depend on Phase 3.

- [ ] T038 [P] [US2] Write component tests in `backend/tests/component/migrations/test_m076_retire_agnostic_property_edges.py` for the **close** shape: a node with open global `HAS_VALUE` edges and no active existence edge on any branch → edges carry `to`, count reported (scenario 1). Build the fixture with raw Cypher — current code paths cannot produce it, which is the point of the migration.
- [ ] T039 [P] [US2] Write component tests for the **hard-delete** shape: an `Attribute` or `Relationship` vertex with no linked node vertex at all → vertex removed, count reported (scenario 2)
- [ ] T040 [P] [US2] Write component tests for the **shared-value** shape: two attributes sharing one `AttributeValue`, one orphaned → orphan detached, surviving attribute keeps its value (scenario 3); and for unrepairable state → reported, migration completes without raising (scenario 4)
- [ ] T041 [P] [US2] Write a component test asserting `m076` is safe to re-run: a second run reports zero, so an interrupted upgrade is resumable
- [ ] T042 [US2] Implement `Migration076` in `backend/infrahub/core/migrations/graph/m076_retire_agnostic_property_edges.py` as an `ArbitraryMigration` with `minimum_version: int = 75`, modelled on `m075_finish_deleting_branches.py`: run the query's unbounded form, batch at the existing `MAX_AGNOSTIC_PEER_BATCH_SIZE` (500) cap, report **both** counts via `get_migration_console()`, and return `MigrationResult(errors=[...])` without raising (FR-016)
- [ ] T043 [US2] Log the irreversibility of the hard-delete to the console before the migration begins, in `backend/infrahub/core/migrations/graph/m076_retire_agnostic_property_edges.py`, so an operator's pre-upgrade backup is an informed decision. No rollback is built — for vertices with no linked node there is nothing to roll back to.
- [ ] T044 [US2] Register `Migration076` in `backend/infrahub/core/migrations/graph/__init__.py` and bump `GRAPH_VERSION` from 75 to 76 in `backend/infrahub/core/graph/__init__.py`
- [ ] T045 [US2] Verify SC-001 and SC-002 on a dataset carrying the pre-fix orphan shapes, adding the checks to `backend/tests/component/migrations/test_m076_retire_agnostic_property_edges.py`: a data-only proposed change validates clean, and a schema update adding a uniqueness constraint on a previously-orphaned branch-agnostic attribute loads successfully

**Checkpoint**: A stuck deployment can escape without a database intervention. User Stories 1 and 2 both work independently.

---

## Phase 5: User Story 3 - The deletion semantics are documented (Priority: P2)

**Goal**: An operator reading the user-facing documentation can predict what happens to a
branch-agnostic attribute or relationship when its object is deleted or the field is removed from
the schema.

**Independent Test**: Documentation review against the enforcement points.

**Depends on**: Phase 3 (the behaviour must exist before it is documented).

- [ ] T046 [US3] Document the deletion semantics for branch-agnostic attributes and relationships on branch-aware objects in the relevant page under `docs/docs/`: when the value is released, when release is deferred, what resolves the deferral (delete on the retaining branch, rebase past the deletion, merge, or branch deletion), and what a branch forked before the deletion sees (FR-019, SC-009)
- [ ] T047 [US3] Document that `m076` mutates existing data on upgrade — closing edges and hard-deleting vertices with no linked node — and that it is irreversible, in the upgrade documentation under `docs/docs/`
- [ ] T048 [US3] Run `uv run invoke docs.lint` and fix any Markdown violations per `dev/guidelines/markdown.md`

**Checkpoint**: All three user stories independently functional.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [ ] T049 [P] Add a towncrier changelog fragment under `changelog/` for the user-visible behaviour: branch-agnostic values are released when no branch retains their object, and freed pool values become allocatable again
- [ ] T050 [P] Update `dev/knowledge/backend/` with the retirement invariant and the six enforcement points, per the constitution's Documentation Requirements for backend architecture changes
- [ ] T051 Run `uv run invoke format` and `uv run invoke lint` (ruff + mypy) — zero lint errors, no unjustified `type: ignore`
- [ ] T052 Run `uv run invoke backend.test-unit` and the full component suite for this feature: `uv run pytest backend/tests/unit/core/agnostic/ backend/tests/component -k agnostic`
- [ ] T053 Run `/pre-ci` (`.agents/commands/pre-ci.md`), including `uv run invoke docs.validate` — CI fails on any stale generated doc
- [ ] T054 Walk `specs/ifc-2843-retire-agnostic-edges/quickstart.md` end to end, including the manual smoke check (allocate → delete → re-allocate the same value), and fill in the FR-018 table with the measured medians
- [ ] T055 Confirm every FR-001 … FR-019 has a passing test or a recorded measurement, and record the mapping in `specs/ifc-2843-retire-agnostic-edges/tasks.md` under a Traceability section

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies. T001 (migration gate) is long-lead — start it first, then continue.
- **Foundational (Phase 2)**: depends on Phase 1. **Blocks both P1 user stories.**
- **User Story 1 (Phase 3)**: depends on Phase 2 only.
- **User Story 2 (Phase 4)**: depends on Phase 2 and T001. **Independent of Phase 3.**
- **User Story 3 (Phase 5)**: depends on Phase 3 (behaviour before documentation).
- **Polish (Phase 6)**: depends on all desired stories.

### Critical path

```text
T001 (gate) ─────────────────────────────────┐
T004 → T006 → T008 → T010 → T011 → T012 → T016 → T017 ─┬─→ T019 → T020 (perf gate) → T023…T030 → T037
                                                        └─→ T042 → T044 → T045
```

T020 is the **decision point**: if the branch-deletion timing gate fails at ~100 branches, the
bound narrows and re-measures before T023 onward proceed.

### Within Phase 2

- T006 blocks T008, T010, T016 (they consume the dataclasses)
- T010 → T011 → T012 are strictly sequential (same file, layered behaviour)
- T007 before T008; T009 before T010; T015 before T016 (tests first)
- T014 (`EXPLAIN`) after T012, before T019

### Within User Story 1

- T018 before T019 before T020 — the risk-first slice, strictly ordered
- T021, T022 before T023; T025 before T026; T027 before T028; T029 before T030
- T031 – T036 are independent of each other and of the enforcement-point order
- T037 last in the phase — it measures the three points added after T020

### Parallel Opportunities

- **Phase 1**: T002, T003 in parallel
- **Phase 2**: T006 and T007 in parallel; T013 and T015 in parallel once T012 lands
- **Phase 3**: T021, T022, T025, T027, T029 (all test-authoring, different concerns) in parallel; T031 – T036 all in parallel
- **Phase 4**: T038 – T041 all in parallel (all test-authoring in one new file — coordinate or split by class)
- **Phases 3 and 4 in parallel** once Phase 2 completes — the two P1 stories share no source file
- **Phase 6**: T049, T050 in parallel

## Parallel Example: User Story 1 test authoring

```bash
# After Phase 2 completes and T019/T020 have settled the branch-deletion path:
Task: "T021 node-deletion component tests (scenarios 1-3)"
Task: "T022 negative component tests (scenarios 4, 6)"
Task: "T025 merge component test (scenario 5c)"
Task: "T027 rebase component tests (scenarios 5b, 11)"
Task: "T029 schema-removal component tests (scenarios 8-9)"

# Then the cross-cutting correctness set, all independent:
Task: "T031 kind-rename regression"
Task: "T034 pool re-allocation"
Task: "T035 late branch creation"
Task: "T036 branch-agnostic node no-op"
```

## Implementation Strategy

### MVP scope

**Both P1 stories are required to ship.** This feature is unusual in having no single-story MVP:
without US2 an affected deployment stays stuck, and without US1 it becomes stuck again. The spec's
priority rationale says so explicitly.

If work must be split across releases, **US2 (the migration) ships first** — it is what unblocks a
customer today, and it stands alone. US1 alone would leave the reported incident unresolved.

### Recommended order

1. Phase 1 + Phase 2 → the invariant exists and is unit- and component-tested
2. T018 – T020 → branch deletion **and its timing gate**; stop and evaluate
3. Phase 4 (US2) → the customer-unblocking deliverable, in parallel with the rest of Phase 3
4. Rest of Phase 3 (US1) → recurrence prevented
5. Phase 5 (US3) → documented
6. Phase 6 → changelog, lint, `/pre-ci`, quickstart walkthrough

### Why the gate is at T020 and not at the end

The predicate's cost grows with open-branch count, not graph size, and branch deletion is the only
point that adds a query the others do not. A gate deferred to Phase 6 would be discovered after
five integrations already assumed it passed. T020 is deliberately early and deliberately blocking.

## Notes

- `[P]` = different files, no dependencies on incomplete tasks
- Assert the **graph shape** (edge presence, `status`, `to`) — not API responses. The bug is a
  graph-shape bug the API hides.
- The negative cases (T022, T029's deferral case, T031, T035, T036) are what a naive implementation
  breaks. A run in which only the positive cases pass is a failed run.
- No mocks anywhere (`.agents/rules/testing-python.md`): recording and failing doubles behind the
  query protocol.
- No ticket IDs, issue numbers, or FR identifiers in source comments, docstrings, or test names
  (`.agents/rules/code-doc-style.md`). They belong in commit messages, the changelog, and these
  spec files.
- Commit after each task or logical group. Do not push without being asked.
