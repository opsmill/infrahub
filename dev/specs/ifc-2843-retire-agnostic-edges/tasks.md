---

description: "Task list for retirement of branch-agnostic property edges (IFC-2843)"
---

# Tasks: Retirement of branch-agnostic property edges

**Input**: Design documents from `specs/ifc-2843-retire-agnostic-edges/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md,
critiques/critique-20260812.md, alignment-check.md (all remediation folded into the artifacts)

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

Directories come into existence with their first real module. Do **not** create empty
`__init__.py` files as a step of their own — add one only when it has something in it, or when
something concretely requires it.

## ⚠️ Blocking gate before any implementation

`AGENTS.md` **Boundaries → Ask First** requires maintainer sign-off for database/migration changes.
This feature adds graph migration `m076`, bumps `GRAPH_VERSION` 75 → 76, and **hard-deletes**
customer `Attribute` / `Relationship` vertices during upgrade. T001 exists to obtain that sign-off
and must complete before T044 (the migration) begins. Phases 1–3 touch no migration and may proceed
in parallel with the sign-off request.

---

## Phase 1: Setup

- [ ] T001 Request maintainer sign-off for the migration gate: `m076`, `GRAPH_VERSION` 75 → 76, and the hard-delete of `Attribute`/`Relationship` vertices with no linked node. Record the outcome in `specs/ifc-2843-retire-agnostic-edges/plan.md` under Ask-First Gate.

---

## Phase 2: Foundational — withdrawn 2026-08-17

The original foundational phase (T004–T017b) built a `core/agnostic/` package: frozen
branch-window types, a pure window builder, a retirement component behind a query `Protocol`, its
adapter, and one query class carrying three candidate bounds and two anchor modes. A maintainer
decision replaced that design with one shared Cypher predicate composed by a query per enforcement
point, so none of those artifacts ships and their tasks are withdrawn rather than completed. The
reasoning is in plan.md §"Design revision"; the ids are left unused so the numbering below still
matches the critique and alignment-check records.

Work is tracked in **Phase 2R**.

---

## Phase 2R: Delivery by enforcement point (revised plan of record)

Each enforcement point lands as its own slice: its query, its wiring, and the tests that pin it,
with the shared retention predicate extended only where a slice proves it must be.

- [X] R01 **Shared retention predicate** — `UNRETAINED_AGNOSTIC_FIELD_PREDICATE` in
  `backend/infrahub/core/query/agnostic_retention.py`. Flat (no nested subqueries), derives branch
  windows in Cypher from `(:Branch)`, conjoins existence and field-edge axes per branch and per
  linked vertex, counts live peers by uuid, reduces across branches with `max`.
- [X] R02 **Slice 1 — single object deletion.** `RetireNodeAgnosticFieldsQuery` in
  `backend/infrahub/core/query/node_agnostic_retirement.py`, node-uuid anchored, one static Cypher
  body, caller-supplied stamp, no batching; wired into `Node.delete` after the existence tombstone,
  failures propagating. Tests in `backend/tests/component/query/test_node_agnostic_retirement_query.py`
  and `backend/tests/component/core/test_agnostic_retirement.py`.
- [X] R02a **Pool re-allocation test (T035).** Allocate a branch-agnostic value from a pool, delete the
  object, allocate again, and assert the same value comes back. Nothing yet exercises the
  `IS_RESERVED` / `HAS_VALUE` / `HAS_ATTRIBUTE` dependency end to end, and this is the closest thing to
  a proof that the feature does what the ticket asked for: allocation counts a value as used only while
  all three edges pass the branch filter. **Done 2026-08-18, with a correction**: the delete already
  writes branch-scoped `deleted` edges that the pool's `branch_agnostic=True` filter honours, so
  re-allocation works without retirement and SC-007 was satisfied before this feature. The test keeps
  its value through the graph assertions; the spec is amended.
- [X] R03 **Slice 2 — schema attribute and relationship removal.** Fold the closure into
  `AttributeRemoveQuery` (`backend/infrahub/core/migrations/query/attribute_remove.py`) and its
  relationship equivalent rather than calling retirement after them, which also removes the ordering
  problem in T030: once the removal query has closed the owning edge, an open-edge anchor can no
  longer see the candidate. Supersedes T029/T030. Carries T030a and T030b. **Done 2026-08-19**, as a
  shared unit-subquery fragment, `CLOSE_UNRETAINED_AGNOSTIC_FIELDS` in
  `backend/infrahub/core/query/agnostic_field_closure.py`, composed by both removal queries. It takes
  the vertices the removal already matched as a collected list rather than re-selecting them, which is
  what keeps the candidate set intact across the removal's own writes, and returns nothing, so both
  queries keep their existing `RETURN` and their migration counts. T030a and T030b followed the same day.
- [X] R03a **Slice 2a — the rollback's metadata restore. Take this next, before R04.** Slice 2's
  closure writes global-branch edges, so both rollback passes must cover the global branch
  (`_rollback_branches` in `backend/infrahub/core/query/rollback.py`): the target branch follows the
  scope, the global branch is always matched on the exact timestamp, because nothing write-blocks it.
  The metadata restore follows the design in plan.md §"The rollback is part of the invariant"
  (idea brief 2026-08-21): restore on `= $at` on every pass, independent of branch and scope,
  because every write of one operation lands at exactly the operation's `at`. The per-vertex
  criterion this task once went looking for turned out to be a constant. Sub-tasks:

  - [X] R03a.1 **Require `at` on the migration queries.** Make `at` a required constructor argument
    of `DeleteElementInSchemaQuery` (`backend/infrahub/core/migrations/query/delete_element_in_schema.py`)
    and `SchemaAttributeUpdateQuery` (`backend/infrahub/core/migrations/query/schema_attribute_update.py`)
    and drop their `at = self.at or Timestamp()` fallbacks. Dropping the fallback alone enforces
    nothing — the `Query` base defaults a missing `at` to *now* (`Timestamp(None)`), which is exactly
    the silent off-timestamp write being outlawed — and a required parameter alone cannot catch the
    omission either, because the `Query.init` classmethod always forwards `at` explicitly, defaulting
    it to `None`; the guard is a runtime rejection of a missing `at`. Callers already pass it:
    `GraphMigration.do_execute` inits every query with `at=migration_input.at`; the m012/m013
    component tests that construct these queries directly must pass `at=Timestamp()`. State the
    single-timestamp rule where these queries are defined. *Verify: construction without `at` is an
    error, pinned by unit tests.*
  - [X] R03a.2 **Restore on the exact timestamp.** `_render_restore_metadata_pipeline` matches
    `restore_vertex.updated_at = $at` on every pass — delete the `rollback_branch.exact` split from
    the restore (the edge passes keep their exact/range split). The pipeline no longer depends on
    `rollback_branch`; simplify the `WITH`/`CALL` scoping in both queries accordingly. Dedup the
    vertex set (`WITH DISTINCT restore_vertex`) so a vertex reached through several edges in one
    batch is restored once; across batches the exact match is self-limiting, since the first restore
    moves `updated_at` off `$at`. The `TestRollbackSinceTimestamp` dataset must stamp its
    default-branch update and delete exactly at the window start — the shape a merge writes and the
    only stamp the restore matches — while its creation and user-branch changes stay later in the
    window to keep the range edge-reversal covered. *Verify (the R03a failure modes, pinned as
    regression tests, SC-002): a vertex bumped at `at + 5` by an unrelated global write survives a
    `SINCE_TIMESTAMP` rollback untouched, `previous_*` included; a node owning both a branch-aware
    and a branch-agnostic field is restored at most once and `updated_at` is never NULL after
    rollback.*
  - [X] R03a.3 **Delete `restore_metadata`; the restore is unconditional.** Remove the parameter
    from `GraphRollbacker.rollback` and both query classes, the default/global-target `ValueError`
    guard, and the docstring text that justified it. Flip the call sites by deletion:
    `core/schema/update_coordinator.py` (`restore_metadata=False` — stale since #9980 closed the
    snapshot gap PR #9878 declared), `core/diff/merger/merger.py`, `core/merge/failure_recoverer.py`.
    Update every test that passes the flag (~12 files, `rtk grep restore_metadata backend/tests`);
    `test_restore_metadata_rejected_on_non_default_branch` is deleted with the guard. *Verify
    (FR: a failed standalone schema update leaves vertex metadata at pre-update values): extend
    `test_a_rolled_back_removal_leaves_the_global_edges_open`
    (`tests/component/core/migrations/schema/test_agnostic_field_removal.py`) with metadata
    assertions — restored stamps, `previous_*` cleared.*
  - [X] R03a.4 **Rollback targeting a user branch restores global-bump metadata.** The global-exact
    pass runs the restore for any target branch. Today a user-branch removal closes global edges
    without bumping metadata (see the A2 note below), so pin the mechanism with a fixture that bumps
    the vertex at `at` by hand — the shape the closure will write once IFC-3032 lands — rolls back
    targeting the user branch, and asserts the restore.
  - [X] R03a.5 **Document timestamp-as-operation-identity** in `_rollback_branches`: a
    same-microsecond unrelated global write is reversed wrongly — accepted, and shared with what
    `AT_TIMESTAMP` scope already assumes. Also note the one-slot `previous_*` residual (a concurrent
    global write after the merge's bump keeps a phantom pointer to the rolled-back write; current
    values stay correct), and keep the re-run idempotency property pinned (SC: re-running rollback
    is a no-op).

  The two pre-existing metadata gaps this task recorded are resolved as follows: the
  `restore_metadata=False` / `=True` asymmetry between a standalone schema update and the same
  removal rolled back through a merge is dissolved by R03a.3 (the update side was the wrong one);
  the user-branch removal that closes global edges while recording no metadata at all
  (`set_metadata` derived from the migration branch, `attribute_remove.py`, vs the closure writing
  the global branch) is an upstream bump gap, **out of scope**, tracked in
  [IFC-3032](https://opsmill.atlassian.net/browse/IFC-3032).

- [X] R04 **Slice 3 — branch merge and rebase.** Supersedes T025–T028. Both supply node uuids from
  the diff they already compute. **Carries T033 (FR-014)** — diff a branch that forked before the
  deletion and assert no attribute or relationship change is reported for that node. It sits here
  rather than with the delete slice because it is a claim about the diff, and this is the slice where
  the diff machinery is already in hand. Every assertion written so far reads edges directly, so
  nothing yet checks the claim at the layer a user would see it. **Rollback constraint (from R03a's
  design, D5)**: the rebase enforcement point's closures must run **inside the rebase transaction**
  (`backend/infrahub/core/branch/tasks.py`, the `db.start_transaction()` block that applies
  `user_branch.rebase`), because a no-schema-diff rebase never invokes the schema-update coordinator
  and transaction atomicity is then the only rollback cover; the coordinator's `AT_TIMESTAMP`
  rollback at `rebase_at` is covered by the global-exact pass with no new machinery.
  Pre-transaction rebase writes are diff-store only, invisible to rollback by construction.
  **Done 2026-08-22.** Merge: `DiffMerger.merge_graph` feeds the merge diff's removed-node uuids
  (`DiffRepository.get_affected_node_uuids`, extended with optional include/exclude `DiffAction`
  filters rather than a parallel removed-only method) into
  `RetireNodeAgnosticFieldsQuery` — extended from a single uuid to `node_uuids: list[str]` — at the
  merge `at`, batched, candidates/edges-closed logged, failures propagating into the existing
  `MergeFailedError` path. Rebase: same read against the **base** branch under the existing tracking
  id, closures inside the rebase transaction, with one correction to T028's ordering — retirement
  runs **after** `user_branch.rebase(...)`, not before, because the predicate reads each branch's
  window from its `(:Branch)` vertex, and only once `branched_from` moves past the deletions does
  the rebased branch stop retaining them; run before, every candidate reads as retained and the
  point is a permanent no-op. Mutation-checked on both points (wiring disabled → positive test
  fails). T033 delivered at the diff layer: after a default-branch delete whose retirement closed
  the global edges, the pre-existing branch's enriched diff reports nothing for the node.
- [ ] R05 **Slice 4 — branch deletion and the FR-018 timing gate.** Its own query, fork-point
  bounded. Supersedes T018–T020 and carries T038's measurement obligation.
- [ ] R06 **Slice 5 — repair migration.** Blocked on T001. Supersedes Phase 4; C4 in
  `contracts/retirement-component.md` states its contract, including the per-candidate stamp
  derivation that FR-015 now requires.
- [ ] R07 **Re-run `EXPLAIN`** against the delivered queries and record the plans. The recorded
  plans in research.md were measured against the superseded query and are marked stale; Principle
  V's obligation is currently unmet.
- [ ] R08 **Remove the superseded stack** once the last slice lands: `backend/infrahub/core/agnostic/`,
  `backend/infrahub/core/query/agnostic_retirement.py`, and their tests. Until then the retention
  logic exists twice, deliberately and visibly.

### Corrections to Phases 3–6 arising from the revision

- **T024 is inverted.** It requires that a retirement failure must not fail the user's delete. The
  opposite is now true and implemented: failures propagate so the transaction rolls back. See
  T017a.
- **T030's ordering is moot** — the closure is part of the removal query rather than a call after it.
  Implementing it (2026-08-19) also showed T030's stated reason was wrong, though its conclusion was
  right. A removal does **not** close the global owning edge of a branch-agnostic field: both removal
  queries only close an edge in place when its `branch` equals the migration branch, and a global edge
  never does, so they shadow it with a branch-scoped `deleted` edge instead and leave the global one
  open. This holds for the attribute removal as much as the relationship one: its peer match is
  undirected, so the owning node is among the peers, and `HAS_ATTRIBUTE` is the first entry in
  `GraphAttributeRelationships`, so the per-type shadow `CREATE` covers the owning edge too. An
  open-edge anchor would therefore still have found the candidate. The fold earns its place
  for two other reasons: the removal has already computed which vertices belong to the kind, including
  the profile/template expansion and the still-declaring kinds to skip, and it is the removal's own
  writes that make the field unretained — a later pass would have to re-derive both.
- **T037's prediction was right and its reasoning was wrong.** Deleting a fully branch-agnostic
  object *is* a retirement no-op, but not because the enforcement point declines to act: the ordinary
  agnostic delete already both tombstones the global edges and stamps `to` on the superseded active
  ones, so nothing is left to close. Covered by
  `test_an_owner_that_is_itself_branch_agnostic_is_closed_once_by_its_own_deletion`.
- **T015's description is stale** — it asks for a `Failing` double proving the exception does *not*
  propagate. The shipped test proves the opposite.

---

## Phase 3: User Story 1 - Enforcement wherever a field stops being retained (Priority: P1) 🎯 MVP

**Goal**: On every path by which a branch-agnostic field stops being reachable from a live node on
any branch, its global edges are retired; while a retaining branch exists, retirement is deferred
and re-evaluated whenever an event could have emptied the retaining set.

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

- [X] T021 [P] [US1] Write component tests in `backend/tests/component/core/test_agnostic_retirement.py` for node deletion: delete on the default branch with no branch forked during the object's lifetime → closed; delete on `B` an object existing only on `B` → closed immediately; delete on one of two branches holding it → stays open, then closed after the second (FR-005, scenarios 1–3) — delivered by slice 1 (R02)
- [X] T022 [P] [US1] Write the **negative** component tests in the same file — these are what a naive implementation breaks: a branch forked between creation and deletion keeps the edges open, the value reserved, and the object readable on `B` (scenario 4); rebase or merge of a retaining branch on which the object survives leaves the edges open (scenario 6, FR-009) — delivered by slice 1 (R02)
- [X] T023 [US1] Invoke retirement from `Node.delete` in `backend/infrahub/core/node/__init__.py`, after `NodeDeleteQuery` writes the existence tombstone, stamped with `delete_at` (FR-005, FR-015) — delivered by slice 1 (R02)
- [X] T024 [US1] Verify a retirement failure **fails the user's delete** at this call site: it is logged and re-raised, the caller's transaction rolls back, and the existence tombstone is never committed. *Inverted 2026-08-17 from "must not fail the user's delete", which the best-effort design of T017 assumed.* Retirement runs inside the caller's still-open transaction, before the commit, so `dev/guidelines/backend/python.md` §"Best-effort side effects" does not apply: its third condition forbids straddling the point of no return. Delivered by slice 1 (R02); see also the transaction wrap in `git/tasks.py`, since a caller deleting in session mode gets no rollback.
- [X] T025 [P] [US1] Write a component test for merge in `backend/tests/component/core/test_agnostic_retirement.py`: delete on a branch, merge it → closed (FR-006, scenario 5c) — delivered by slice 3 (R04), plus the FR-009 negative (merge releases nothing while another branch retains)
- [X] T026 [US1] Invoke retirement from `DiffMerger.merge_graph` in `backend/infrahub/core/diff/merger/merger.py`, after the bulk merge queries complete, for the deleted nodes named by the merge diff, at the merge `at` — delivered by slice 3 (R04)
- [X] T027 [P] [US1] Write a component test for rebase: a node deleted on the default branch while a branch is open, rebase that branch → closed (FR-007, scenario 5b); plus scenario 11 — a node created and deleted on `B`, then `B` rebased, leaves no vertex with open global edges — delivered by slice 3 (R04), driven through the real `rebase_branch` flow
- [X] T028 [US1] Invoke retirement from `rebase_branch` in `backend/infrahub/core/branch/tasks.py`, inside the existing `lock.registry.global_graph_lock()` and **before** `user_branch.rebase(...)` is applied, at `rebase_at`. Obtain the base-branch deletions via a second `DiffRepository` read under the existing tracking id (decided in plan.md §"Resolved during critique"). Delivered by slice 3 (R04) with one correction: the closure runs inside the rebase transaction **after** `user_branch.rebase` is applied — see R04's Done note.
- [X] T029 [P] [US1] Write component tests for schema removal: a branch-agnostic attribute removed from the schema → closed; likewise a relationship; and with a branch that forked beforehand → deferred and still readable there (FR-010, scenarios 8–9). **Belongs to slice 2 (R03)** and is written against the removal query rather than a separate retirement call. The deferral case is already covered from the delete side by slice 1's field-axis test, which builds the branch-level `deleted` owning edge by hand; these drive it through the real removal path. Delivered 2026-08-19 in `backend/tests/component/core/migrations/schema/test_agnostic_field_removal.py` — four tests, both fields closed and both fields deferred, driven through `NodeAttributeRemoveMigration` / `NodeRelationshipRemoveMigration`. Placed with the other removal-migration component tests rather than in `core/test_agnostic_retirement.py`, whose class-scoped database is shared across its tests while these need the function-scoped `default_branch` reset. Mutation-checked twice: with the fragment emptied the two closure tests fail and the two deferral tests pass; with the retention predicate dropped from the fragment the two deferral tests fail and the two closure tests pass.
- [ ] T030 [US1] **Superseded by R03 — do not implement as written.** The original said to invoke retirement from `NodeAttributeRemoveMigration` and `NodeRelationshipRemoveMigration` *after* each existing removal query runs. That cannot work: the removal query has already closed the owning edge by then, so an open-edge anchor finds no candidate and retirement is a silent no-op. Instead fold the closure into `AttributeRemoveQuery` (`backend/infrahub/core/migrations/query/attribute_remove.py`) and its relationship equivalent, which already match the right vertices for the kind and already carry the branch filter.
- [X] T030a [US1] Write the cross-axis component test driven through the **real** removal migration: an object deleted on the default branch while a branch forked after its creation had the attribute removed from its schema. That branch retains the object but not the field, so nothing retains the value and the global edges must close. Deferred from the object-delete slice deliberately — the fixture is only faithful once the removal path is final, and a hand-built version could encode a shape the schema slice changes. The object-delete slice covers the same conjunction with a raw-Cypher fixture instead. Delivered 2026-08-19 as `test_an_attribute_removed_on_a_fork_is_closed_when_the_object_is_deleted_elsewhere` in `backend/tests/component/core/migrations/schema/test_agnostic_field_removal.py`. The removal is the real migration; the closure comes from the delete, since that is the enforcement point the surviving axis flips on.
- [X] T030b [US1] Write the inverse of T030a: the attribute removed from the schema on the default branch while a branch forked beforehand deleted the object. That branch retains the field but not the object, so again nothing retains the value. Both directions prove the retention conjunction is per branch rather than a disjunction across axes. Delivered 2026-08-19 as `test_an_attribute_removed_from_the_schema_is_closed_when_the_only_fork_deleted_the_object` in the same file, closed by the removal query. Mutation-checked: with the field-edge axis dropped from the shared predicate, so that a live owner alone retains, both tests fail; with the closure fragment emptied, T030b fails and T030a passes, which is where each one's closure comes from. Dropping the existence axis instead leaves both passing, and that is a property of the real paths rather than a gap: an ordinary delete tombstones the field edge alongside the existence edge on its own branch, so no branch in either scenario holds a live field edge over a dead owner. Slice 1's raw-Cypher `tombstone_existence_only` fixture exists for exactly that shape.

### Cross-cutting correctness tests for US1

- [X] T031 [P] [US1] Write a regression test in `backend/tests/component/core/test_agnostic_retirement.py`: rename a kind, then run every enforcement point → the surviving vertex keeps its value (FR-011, scenario 10). Confirms same-UUID copies are excluded by the open-edge anchor rather than by luck. — delivered by slice 1 (R02)
- [X] T032 [P] [US1] Assert in the same file that a retired vertex is no longer a candidate on a second pass — re-run retirement over the same candidates and confirm it closes nothing and reports zero (the property that closing the owning edge buys) — delivered by slice 1 (R02)
- [X] T033 [P] [US1] Write a component test asserting retirement registers no change on a branch that forked before it — diff the pre-existing branch after a default-branch delete and assert no attribute or relationship change is reported for that node (FR-014) — **carried by R04, with the merge and rebase work** — delivered 2026-08-22 as `backend/tests/component/core/diff/diff_calculator/test_aware_node_agnostic_fields.py` — placed with the diff-calculator tests because the property under test is the diff's treatment of global-edge `to` stamps, not retirement's writes
- ~~T034~~ **Withdrawn 2026-08-17.** The fork-window file was to be adopted by swapping its closure stub for the real delete path. That cannot be done: retirement only closes once no branch retains the field, so in that file's scenario — two branches forked before the deletion — the real path correctly closes nothing, and the state the tests explore is unreachable through object deletion by construction. The one path that does produce it is the repair migration, closing edges for pre-existing orphans that an old branch can still read; R06 writes its own tests for that rather than inheriting these.
- [X] T035 [P] [US1] Write the pool re-allocation test in `backend/tests/component/core/test_agnostic_retirement.py`: allocate, delete, allocate again → the same value is returned. Guards the three-edge `IS_RESERVED`/`HAS_VALUE`/`HAS_ATTRIBUTE` dependency documented in data-model.md. **Written 2026-08-18, and it disproved its own premise**: re-allocation does not depend on retirement. It earns its place through the graph assertions, not through SC-007, which is amended accordingly.
- ~~T036~~ **Withdrawn 2026-08-17.** It bounded the race between candidate selection and closure. Those are now one Cypher statement inside one transaction, so there is no window between them and no race to bound.
- [X] T037 [P] [US1] Write the out-of-scope boundary test: deleting a truly branch-agnostic *node* closes its edges exactly once and retirement is a no-op. `Node.delete` resolves `branch` to the global branch for such nodes, so the enforcement point does run against them. — delivered by slice 1 (R02); its premise was wrong and is corrected in Phase 2R
- [ ] T038 [US1] Measure FR-018 for node deletion, branch merge and branch rebase at both open-branch counts and record medians in `quickstart.md`. Gate: ≤ +10% at both.

**Checkpoint**: User Story 1 is fully functional and independently testable. Deletes and schema removals no longer leak; SC-004 through SC-007 are demonstrable.

---

## Phase 4: User Story 2 - Existing damage repaired on upgrade (Priority: P1)

**Goal**: Upgrading retires the global edges of every branch-agnostic field that no branch retains,
covering both the still-linked orphans and the fully detached ones.

**Independent Test**: Build the orphan shapes as fixtures, run the migration, assert the edges are
closed or the vertices removed and the reported counts are correct. Delivers value with no
enforcement present — this is what unblocks a customer stuck today.

**Depends on**: T001 (migration gate sign-off) and Phase 2 (the query's unbounded form and widened
anchor). Does **not** depend on Phase 3.

- [ ] T039 [P] [US2] Write component tests in `backend/tests/component/migrations/test_m076_retire_agnostic_property_edges.py` for the **close** shape: a node with open global edges and no active existence edge on any branch → edges carry `to`, count reported (scenario 1). Build the fixture with raw Cypher — current code paths cannot produce it, which is the point of the migration.
- [ ] T040 [P] [US2] Write component tests for the **hard-delete** shape: an `Attribute` or `Relationship` vertex with no linked node vertex at all → vertex removed, count reported (scenario 2)
- [ ] T041 [P] [US2] Write component tests for the **shared-value** shape: two attributes sharing one `AttributeValue`, one orphaned → orphan detached, surviving attribute keeps its value (scenario 3); and for unrepairable state → reported, migration completes without raising (scenario 4)
- [ ] T042 [P] [US2] Write component tests for the **half-closed** shapes, which only the widened anchor can reach: an owning edge already closed with property edges still open, and the reverse → each fully closed and counted (FR-002a, FR-011a). Build both with raw Cypher. This is the only place half-closed shapes are exercised — no runtime path can create one.
- [ ] T043 [P] [US2] Write a component test asserting `m076` is safe to re-run: a second run reports zero, so an interrupted upgrade is resumable (SC-004a)
- [ ] T044 [US2] Implement `Migration076` in `backend/infrahub/core/migrations/graph/m076_retire_agnostic_property_edges.py` as an `ArbitraryMigration` with `minimum_version: int = 75`, modelled on `m075_finish_deleting_branches.py`: read branches with `Branch.get_list(db=db)` (the registry may be unpopulated in an upgrade process), run the query's unbounded form **with the widened anchor** (T011), batch at the existing `MAX_AGNOSTIC_PEER_BATCH_SIZE` (500) cap, report **both** counts via `get_migration_console()`, and return `MigrationResult(errors=[...])` without raising (FR-016)
- [ ] T045 [US2] Log the irreversibility of the hard-delete to the console before the migration begins, in `backend/infrahub/core/migrations/graph/m076_retire_agnostic_property_edges.py`, so an operator's pre-upgrade backup is an informed decision. No rollback is built — for vertices with no linked node there is nothing to roll back to.
- [ ] T046 [US2] Register `Migration076` in `backend/infrahub/core/migrations/graph/__init__.py` and bump `GRAPH_VERSION` from 75 to 76 in `backend/infrahub/core/graph/__init__.py`
- [ ] T047 [US2] Verify SC-001 and SC-002 on a dataset carrying the pre-fix orphan shapes, adding the checks to `backend/tests/component/migrations/test_m076_retire_agnostic_property_edges.py`: a data-only proposed change validates clean, and a schema update adding a uniqueness constraint on a previously-orphaned branch-agnostic attribute loads successfully

**Checkpoint**: A stuck deployment can escape without a database intervention. User Stories 1 and 2 both work independently.

---

## Phase 5: User Story 3 - The deletion semantics are documented (Priority: P2)

**Goal**: An operator reading the user-facing documentation can predict what happens to a
branch-agnostic attribute or relationship when its object is deleted or the field is removed from
the schema.

**Independent Test**: Documentation review against the enforcement points.

**Depends on**: Phase 3 (the behaviour must exist before it is documented).

- [ ] T048 [US3] Document the deletion semantics for branch-agnostic attributes and relationships on branch-aware objects in the relevant page under `docs/docs/`: when the value is released, when release is deferred, what resolves the deferral (delete on the retaining branch, rebase past the deletion, merge, or branch deletion), and what a branch forked before the deletion sees (FR-019, SC-009)
- [ ] T049 [US3] Document that `m076` mutates existing data on upgrade — closing edges and hard-deleting vertices with no linked node — and that it is irreversible, in the upgrade documentation under `docs/docs/`
- [ ] T050 [US3] Run `uv run invoke docs.lint` and fix any Markdown violations per `dev/guidelines/markdown.md`

**Checkpoint**: All three user stories independently functional.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [ ] T051 [P] Add a towncrier changelog fragment under `changelog/` for the user-visible behaviour: branch-agnostic values are released when no branch retains their object, and freed pool values become allocatable again
- [ ] T052 [P] Update `dev/knowledge/backend/` with the retirement invariant and the six enforcement points, per the constitution's Documentation Requirements for backend architecture changes
- [ ] T053 Run `uv run invoke format` and `uv run invoke lint` (ruff + mypy) — zero lint errors, no unjustified `type: ignore`
- [ ] T054 Run `uv run invoke backend.test-unit` and the full component suite for this feature: `uv run pytest backend/tests/unit/core/agnostic/ backend/tests/component -k agnostic`
- [ ] T055 Run `/pre-ci` (`.agents/commands/pre-ci.md`), including `uv run invoke docs.validate` — CI fails on any stale generated doc
- [ ] T056 Walk `specs/ifc-2843-retire-agnostic-edges/quickstart.md` end to end, including the manual smoke check (allocate → delete → re-allocate the same value), and fill in the FR-018 table with the measured medians
- [ ] T057 Confirm every FR-001 … FR-019 has a passing test or a recorded measurement, and record the mapping in `specs/ifc-2843-retire-agnostic-edges/tasks.md` under a Traceability section

---

## Follow-ups (out of scope here — file separately)

- [ ] F001 File an issue for **merged branches retaining branch-agnostic attributes and relationships**. A branch that forked after an object was created reads that object as live at its fork point regardless of its own status, so a `MERGED` branch keeps the object's branch-agnostic value reserved until the branch itself is deleted. Predates this work — the branch list has always come from sources that include merged branches — but the retirement invariant makes it visible and load-bearing: after a proposed change merges, the value stays allocated with no operator signal, which is the mirror of the leak this feature fixes.

  The desired end state is that a merged branch does **not** retain, while a user querying that merged branch still sees valid objects — a mandatory branch-agnostic attribute still resolving to a value rather than to nothing. That is mechanically achievable and the design is symmetric with the isolation collapse already in `Branch.get_branches_and_times_to_query_global`: the branch's own pair reads `-global-` at the present, and for a merged branch it would collapse to the merge time, exactly as the origin pair collapses to `branched_from`. Three obstacles belong in the issue rather than here:

  1. `Branch` records no merge timestamp — only `status` and `branched_from` — so pinning reads to merge time needs a new field and a migration, which is an Ask-First gate and a second graph-version bump.
  2. That method serves every branch-agnostic read, so the change affects all agnostic data on all merged branches, not only retired values.
  3. Releasing a value at merge while keeping the merged branch readable means the value can legitimately appear twice — historically on the merged branch, currently on its new holder. For a unique attribute (the pool case that opened this ticket) that is only safe if uniqueness validation considers the present only. Answer that before anything ships, or the change re-creates the duplicate-value failure this feature exists to eliminate.

  Until then the conservative behaviour stands: merged branches retain, and deleting the branch releases the value.

- [ ] F002 File an issue for **a kind or inheritance migration run on a branch closing the superseded vertex's global edges for every branch**. Observed while probing whether two same-uuid vertices can be live at once. Running `NodeKindUpdateMigrationQuery01` on a branch leaves the node's uuid on two vertices, and treats them asymmetrically by branch as expected — the superseded vertex keeps an active `IS_PART_OF` on the default branch and gains a `deleted` one on the migrating branch, while the new vertex exists only on the migrating branch. But the superseded vertex's branch-agnostic `IS_RELATED` edge is **time-closed on `-global-`**, not tombstoned per branch:

  ```text
  IS_PART_OF   old vertex   main             active   open
  IS_PART_OF   old vertex   <branch>         deleted  open
  IS_PART_OF   new vertex   <branch>         active   open
  IS_RELATED   old vertex   -global-         active   CLOSED   <- closes for every branch
  IS_RELATED   old vertex   -global-         deleted  open
  IS_RELATED   new vertex   -global-         active   open
  ```

  So the default branch keeps a live object whose branch-agnostic relationship it can no longer reach over a live edge, without anything on the default branch having changed. The new vertex that does hold the live edge is visible only on the migrating branch. Predates this work and is not caused by retirement — retirement only made it visible, because the retention predicate reads exactly these edges. Worth confirming whether the same happens to branch-agnostic **attributes**, which the probe did not cover.

  Relevant to this feature because it is a way for the graph to reach a state the retention predicate reads as "the default branch does not retain this", produced by a schema migration rather than by a deletion.

## Dependencies & Execution Order

- **T001** (the migration gate) is long-lead and blocks only the repair migration, R06.
- **R01** (the shared predicate) is delivered and is what every later slice composes. A slice may
  extend it, but no slice may fork it.
- **R02 – R05** are independent of each other: each enforcement point supplies its own candidate
  selection and stamp. Order them by risk rather than by dependency — R05 (branch deletion) carries
  the FR-018 timing gate, so a failure there is worth surfacing before the remaining wiring assumes
  it passed.
- **R06** depends on T001 and on R01.
- **Phase 5** (documentation) depends on the runtime slices being settled.
- **R08** (removing the superseded stack) is last: until then the retention logic exists twice.

Within a slice the order is the same each time: the tests that pin the behaviour, the query, the
wiring, then the mutation checks that prove the tests bite.

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
- The negative cases (T022, T029's deferral case, T031, T036, T037) are what a naive implementation
  breaks. A run in which only the positive cases pass is a failed run.
- Half-closed shapes are exercised **only** in the migration (T042). No runtime path can create
  one, because the owning edge and the property edges are closed in a single pass.
- No mocks anywhere (`.agents/rules/testing-python.md`): recording and failing doubles behind the
  query protocol.
- Don't create empty `__init__.py` files as a step of their own; add one when it has content or
  when something requires it.
- Don't commit a test that asserts pre-fix behaviour on its own. Land it with the change that turns
  it green.
- No ticket IDs, issue numbers, or FR identifiers in source comments, docstrings, or test names
  (`.agents/rules/code-doc-style.md`). They belong in commit messages, the changelog, and these
  spec files.
- Commit after each task or logical group. Do not push without being asked.
