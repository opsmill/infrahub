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
This feature adds graph migration `m077`, bumps `GRAPH_VERSION` 76 → 77 (corrected by T058 from the
stale `m076` / 75 → 76 this section originally stated), and **hard-deletes**
customer `Attribute` / `Relationship` vertices during upgrade. T001 exists to obtain that sign-off
and must complete before T044 (the migration) begins. Phases 1–3 touch no migration and may proceed
in parallel with the sign-off request.

---

## Phase 1: Setup

- [X] T001 Request maintainer sign-off for the migration gate: `m076`, `GRAPH_VERSION` 75 → 76, and the hard-delete of `Attribute`/`Relationship` vertices with no linked node. Record the outcome in `specs/ifc-2843-retire-agnostic-edges/plan.md` under Ask-First Gate. **Signed off 2026-08-25**; recorded in plan.md §Ask-First Gate. The approval covers the T058-corrected numbers — `m077` and `GRAPH_VERSION` 76 → 77 — since the numbers stated here were already taken on the base branch.

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
  **Status 2026-08-23: implementation and measurement delivered; open only on the gate verdict.**
  T018/T019 shipped (`RetireBranchAgnosticFieldsQuery`, wired as `_retire_agnostic_fields` between
  the agnostic-peer hard-delete and `_delete_edges`, three component tests, mutation-checked both
  ways, one shared-predicate extension — `DELETING` branches never retain). T038's six cells all
  pass. T020's branch-deletion cell fails the relative gate at ~100 branches (+37.6%, ~+13 ms
  absolute on an empty-branch ~35 ms baseline) with the prescribed fallback already built in; see
  T020's note and quickstart.md for the numbers, noise analysis, and the pending decision
  (absolute-floor gate amendment vs. further query work). Tick this once that decision lands.
- [X] R06 **Slice 5 — repair migration.** Blocked on T001. Supersedes Phase 4; C4 in
  `contracts/retirement-component.md` states its contract, including the per-candidate stamp
  derivation that FR-015 now requires.
  **Done 2026-08-31.** T001 signed off 2026-08-25; shipped as the
  `m077_retire_agnostic_property_edges/` package (`migration.py`, `queries.py`) with
  `Migration077`, `minimum_version = 76` and `GRAPH_VERSION` 76 → 77 — the numbering corrected from
  the artifacts' stale `m076` / 75→76 by T058, since `m076_heal_missing_attribute_rows` already
  occupied 76. Two batched write passes (`CloseUnretainedAgnosticFieldsQuery` reusing
  `UNRETAINED_AGNOSTIC_FIELD_PREDICATE` verbatim under a widened anchor, and
  `DeleteDetachedAgnosticFieldsQuery` hard-deleting field vertices with no linked node), each
  exception-guarded independently. Component tests live in
  `backend/tests/component/core/migrations/graph/m077_retire_agnostic_property_edges/`. Registration
  needed no edit — `discover_migrations()` finds the package by placement. Two boundary decisions
  from the slice remain open for the maintainer and are **not** blockers on the checkbox: whether a
  repair-pass query failure may abort the upgrade (FR-016 vs. the code's `errors` population, which
  also needs contract C4 amended either way), and the hard delete's blast radius and missing audit
  trail. Both are recorded in `opsmill-implement-report-r06.md` §5.
- [X] R07 **Re-run `EXPLAIN`** against the delivered queries and record the plans. The recorded
  plans in research.md were measured against the superseded query and are marked stale; Principle
  V's obligation is currently unmet.
  **Done 2026-08-31.** All five delivered queries `EXPLAIN`ed and their read-only truncations
  `PROFILE`d against a purpose-built 285,007-vertex throwaway database on Neo4j 2026.05.0-enterprise
  carrying the production index set; results and dataset composition recorded in research.md under
  "Query plans (delivered queries, 2026-08-31)", with the superseded section demoted beneath it.
  No `AllNodesScan` and no `CartesianProduct` anywhere. Three queries are index-seeded; the two label
  scans are over `Attribute|Relationship`, and `DeleteDetachedAgnosticFieldsQuery`'s cannot be
  otherwise because it matches the absence of an edge. The node-bound query — which three of the six
  enforcement points ride on — costs 35,632 db hits for a full 500-uuid batch, ~71 per candidate.
  **One result feeds T020 directly:** the branch-delete query's label-scan seed is not what makes it
  expensive. Hinting the relationship-index seek changes the seed and cuts db hits by 14%, but the
  median wall clock gets slightly worse (328.6 → 357.1 ms); the cost is the per-branch existence
  resolution below it, which scales with branch count exactly as T020's +37.6%-at-100-branches
  measurement shows. That retires the "invert the candidate seed" option T020 left on the table.
- [X] R08 **Remove the superseded stack** once the last slice lands: `backend/infrahub/core/agnostic/`,
  `backend/infrahub/core/query/agnostic_retirement.py`, and their tests. Until then the retention
  logic exists twice, deliberately and visibly.
  **Done.** Neither `backend/infrahub/core/agnostic/` nor
  `backend/infrahub/core/query/agnostic_retirement.py` exists on this branch; the retention logic
  now lives once, in the shared predicate (R01).

### Corrections to Phases 3–6 arising from the revision

- **Every test path named below is stale.** The suites were consolidated after the fact and the task
  text was never rewritten. The actual layout is: `backend/tests/component/core/agnostic_retirement/`
  — `test_on_node_delete.py`, `test_on_merge.py`, `test_on_rebase.py`, `test_on_branch_delete.py`,
  plus `support.py`; `backend/tests/component/core/migrations/schema/test_agnostic_field_removal.py`
  for the schema-removal points; `backend/tests/component/query/test_node_agnostic_retirement_query.py`
  for the query alone; and
  `backend/tests/component/core/migrations/graph/m077_retire_agnostic_property_edges/` — `test_repair.py`
  and `test_retention.py`. The per-shape files the migration tasks name (`test_close.py`,
  `test_hard_delete.py`, `test_shared_value.py`, `test_half_closed.py`, `test_rerun.py`,
  `test_unrepairable.py`, `test_success_criteria.py`) no longer exist.

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

- [X] T018 [US1] Write a component test in `backend/tests/component/core/test_agnostic_retirement.py` for branch deletion: a node deleted on the default branch while branch `B` retained it, then `B` is deleted → global edges closed (FR-008, acceptance scenario 5d) — delivered by slice 4 (R05), plus the FR-009 negative (deleting a branch releases nothing while another branch retains it; deleting that retainer afterwards is what releases) and a failure-propagation test proving a retirement failure stops the branch delete before the branch's edges are removed, leaving it resumable
- [X] T019 [US1] Wire the fork-point-bounded retirement into `BranchDataDeleter._delete_agnostic_peers` in `backend/infrahub/core/branch/data_deleter.py`, alongside the existing branch-only cleanup. It MUST run **before** `_delete_edges` removes the branch's `IS_PART_OF` edges — the reachability determination reads them. Delivered by slice 4 (R05) as `RetireBranchAgnosticFieldsQuery` (`backend/infrahub/core/query/branch_agnostic_retirement.py`), a new `_retire_agnostic_fields` stage between `_delete_agnostic_peers` and `_delete_edges` — after the peer hard-delete so already-removed vertices are not candidates. Candidates are bounded in Cypher by the branch's own view (its active `IS_PART_OF` edges, plus its origin's as of `branched_from`), read from the `(:Branch)` vertex with an `OPTIONAL MATCH` so a resumed delete whose vertex is gone still covers the branch's own edges; closures batched at the `MAX_AGNOSTIC_PEER_BATCH_SIZE` cap via `CALL … IN TRANSACTIONS`. Required one shared-predicate extension: branches in `DELETING` status are excluded from the retaining set, because the deleter judges retention while the branch vertex still exists in that status — without it the point is a permanent no-op (mutation-checked both ways: wiring disabled and exclusion dropped each fail all three tests). Stamp is the branch deletion's own time, consistent with merge/rebase stamping their operation time.
- [ ] T020 [US1] Measure FR-018 for branch deletion at **two** open-branch counts (~3 and ~100) using `backend/tests/query_benchmark/`, before and after, and record medians in `specs/ifc-2843-retire-agnostic-edges/quickstart.md`. Gate: ≤ +10% median at **both** counts. If breached, narrow the bound with the existence edge's `from` against the fork point and re-measure. **Measured and recorded 2026-08-23; the gate is breached at ~100 branches and the task stays open pending a maintainer decision.** Medians (interleaved before/after runs, see quickstart.md): 34.9→27.9 ms at 3 (−19.8%, pass) and 35.2→48.5 ms at ~100 (+37.6%, fail). The prescribed fallback is exhausted — the fork-point narrowing via the existence edge's `from`/`to` was built into the query from the start (see T019's note). Stage profiling puts the warm query at ~7 ms at 100 branches (seed 4.2 ms, predicate ~2 ms), so the breach is ~+13 ms absolute on an empty-branch baseline of ~35 ms — the relative gate has a degenerate denominator here, since the benchmark deletes branches carrying no data. A first measurement session recorded 364 ms for this cell; three re-measurements never reproduced it (30/48/63 ms) and it is attributed to plan-compile and environment effects. Options on the table: accept with an absolute floor added to the gate (e.g. ≤ +10% or ≤ +25 ms, whichever is greater), or invert the candidate seed to seek from the branch's `IS_PART_OF` edges — rejected so far because with only a single-property `IS_PART_OF(branch)` index its origin arm scans every default-branch node, a regression on any deployment where nodes outnumber branch-agnostic fields.

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
- [X] T030 [US1] **Superseded by R03 — do not implement as written.** The original said to invoke retirement from `NodeAttributeRemoveMigration` and `NodeRelationshipRemoveMigration` *after* each existing removal query runs. That cannot work: the removal query has already closed the owning edge by then, so an open-edge anchor finds no candidate and retirement is a silent no-op. Instead fold the closure into `AttributeRemoveQuery` (`backend/infrahub/core/migrations/query/attribute_remove.py`) and its relationship equivalent, which already match the right vertices for the kind and already carry the branch filter. **Closed as superseded — nothing to implement.** The closure is part of `AttributeRemoveQuery` / `RelationshipRemoveQuery` themselves (delivered by R03); no separate call from the migrations exists or should.
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
- [X] T038 [US1] Measure FR-018 for node deletion, branch merge and branch rebase at both open-branch counts and record medians in `quickstart.md`. Gate: ≤ +10% at both. Delivered 2026-08-23 by slice 4 (R05)'s measurement pass: all six cells pass at both counts (after is faster than before in every cell — see the noise notes in quickstart.md). Methodology: interleaved before/after full runs (ABAB) against a pre-feature worktree, 14–18 samples per cell, harness `backend/tests/query_benchmark/test_fr018_agnostic_retirement_operations.py` (uncommitted by design).

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

- [X] T039 [P] [US2] Write component tests in `backend/tests/component/migrations/test_m076_retire_agnostic_property_edges.py` for the **close** shape: a node with open global edges and no active existence edge on any branch → edges carry `to`, count reported (scenario 1). Build the fixture with raw Cypher — current code paths cannot produce it, which is the point of the migration. Delivered as `backend/tests/component/core/migrations/graph/m077_retire_agnostic_property_edges/test_close.py` (T058's path, not the one named here). Three tests: the orphan's open global attribute and relationship edges all close and the closure count appears in the console output; two orphans that went away at different times each carry their own stamp and neither carries the run time (the FR-015 verify clause, which T039's text omits); and a still-readable object keeps every open edge, which is the guard that the widened anchor did not cost selectivity. Fixture built with `tombstone_existence_only` (raw Cypher) after creating the objects at an explicitly earlier timestamp, because a derived stamp earlier than an edge's own `from` is clamped and would have hidden a wrong stamp. Mutation-checked: neutering `execute` fails all but the guard test; stamping `$at` instead of the derived time fails both stamp assertions.
- [X] T040 [P] [US2] Write component tests for the **hard-delete** shape: an `Attribute` or `Relationship` vertex with no linked node vertex at all → vertex removed, count reported (scenario 2) Delivered as `.../m077_retire_agnostic_property_edges/test_hard_delete.py`. The shape is built by `DETACH DELETE`ing the node vertices out from under their fields, which is what a branch deletion predating the agnostic-peer cleanup left behind; both an `Attribute` and a `Relationship` vertex are covered in one fixture. Asserts the vertices are gone by uuid, the detached population is empty afterwards, the removal count appears in the console output, and the shared `AttributeValue` vertices survive untouched. A second test asserts a re-run of the removal reports zero — narrower than T043, which still owns the general re-run claim.
- [X] T041 [P] [US2] Write component tests for the **shared-value** shape: two attributes sharing one `AttributeValue`, one orphaned → orphan detached, surviving attribute keeps its value (scenario 3); and for unrepairable state → reported, migration completes without raising (scenario 4) Delivered as two files. `.../m077_retire_agnostic_property_edges/test_shared_value.py` covers scenario 3 twice, because the orphan reaches the shared value through either repair: the close side (one owner tombstoned → the orphan's own `HAS_VALUE` edge closes, the survivor's edges are byte-identical and still read the value) and the hard-delete side (one node vertex detached → the orphan attribute vertex is removed, the survivor's attribute and the shared value vertex both survive). Sharing is pinned on `elementId(value)`, not on the value property, so two equal-but-separate vertices cannot pass for one. Mutation-checked: making the hard-delete `DETACH DELETE field, v` fails the delete-side test.

  **Retracted 2026-08-31.** This note certified a skipped-candidate report — `CountUnstampableAgnosticFieldsQuery`, a
  third `execute` pass, and a `Skipped N branch-agnostic field(s)…` console line — that the shipped migration does not
  have. `execute` runs the close and delete passes only and logs `Closed N` / `Removed N`; `queries.py` defines two query
  classes. The stamp derivation also differs: `coalesce(derived_at, $at)` closes a candidate with no derivable time at the
  run time, so nothing is ever skipped or counted. Scenario 4 is therefore **not** delivered; whether that count is worth
  reporting folds into the open FR-016 / C4 decision (see `opsmill-implement-report-r06.md` §5).
- [X] T042 [P] [US2] Write component tests for the **half-closed** shapes: an owning edge already closed with property edges still open, and the reverse → each fully closed and counted (FR-002a, FR-011a). Build them with raw Cypher. **T042's closing claim was wrong and is retracted**: "no runtime path can create one" is false. The confirmed root cause of the reported damage is itself a runtime-produced half-closed shape — object deletion closed the `HAS_ATTRIBUTE` owning edge and left `HAS_VALUE` open — and a kind-update migration produces a `:Relationship` with one `IS_RELATED` arm closed and the other open. **Three** shapes are therefore covered, not two.

  Delivered as `.../m077_retire_agnostic_property_edges/test_half_closed.py`: (a) owner tombstoned, owning edge closed, property edges open — the confirmed real-world shape; (b) the mirror, property edges closed with the owning edge open; (c) a relationship with one arm closed while **both peers are still live**, which closes on the peer count rather than on either owner being gone, and which also asserts the widget's own agnostic attribute is left untouched. Built with three new raw-Cypher conftest helpers (`close_global_owning_edge`, `close_global_property_edges`, `close_one_relationship_arm`), each asserting it actually changed something so a silently-ineffective fixture cannot make a test vacuous.

  **All three passed on the first run**, which is the expected result: T044 already shipped the widened anchor. The evidence that they are load-bearing is the mutation check — restoring `AND anchor.to IS NULL` in `queries.py` (the runtime anchor) fails shape (a) with `HAS_VALUE` and `IS_PROTECTED` left open, and the migration reports `Closed 0`. That is exactly the reported damage going unrepaired, and it is the concrete proof FR-011a is load-bearing rather than defensive. Worth recording: shapes (b) and (c) pass under **either** anchor, because each still has one open owning/`IS_RELATED` edge for the narrow anchor to find. Only shape (a) — every owning edge closed — is anchor-sensitive, so T042's "which only the widened anchor can reach" applies to (a) alone.
- [X] T043 [P] [US2] Write a component test asserting `m077` is safe to re-run: a second run reports zero, so an interrupted upgrade is resumable (SC-004a) Delivered as `.../m077_retire_agnostic_property_edges/test_rerun.py`, one test over a database holding all four situations at once — a plain orphan (attribute **and** relationship), a half-closed orphan, a detached vertex, and a live object — so the claim covers the whole migration rather than the removal pass alone, which is all `test_hard_delete.py`'s narrower re-run test covered. Asserts the second run reports `Closed 0` / `Removed 0` and `nbr_migrations_executed == 0` (the `Skipped 0` assertion this note originally claimed went with the retracted skipped-count pass — see T041), and compares every field's edge summary before and after the second run, so a re-run that re-stamped an already-closed edge with a fresh time would fail even though the count read zero.

  **Superseded 2026-08-27 — the T039-T043 notes above describe an interim state.** Two later
  maintainer decisions changed what shipped, and neither is reflected in the paragraphs above.

  1. **There is no skipped-candidate report.** A candidate whose retirement time the graph does not
     record is no longer left alone and counted; the close falls back to the run time
     (`coalesce(derived_at, $at)`), which releases the value instead of leaving it reserved forever.
     Such a field is unreadable on every branch anyway — nothing dates its release because nothing
     recorded its owner leaving — so the run time shifts no branch's view of it.
     `CountUnstampableAgnosticFieldsQuery`, `UnstampableAgnosticFieldCount` and the third pass in
     `execute` are gone, and no `Skipped N` line is emitted. T041's point 1 above still stands as a
     fact about the runner — a non-empty `errors` does abort the upgrade, and C4 still needs
     amending — but it no longer describes this migration.
  2. **The per-shape test files are gone.** `test_close.py`, `test_half_closed.py`,
     `test_hard_delete.py`, `test_shared_value.py`, `test_unrepairable.py` and `test_rerun.py` were
     consolidated into `test_repair.py`: one class that builds every damaged shape into a single
     graph, runs the migration, verifies the whole graph, runs it again, and asserts the identical
     expectations still hold. Idempotency is therefore pinned for every shape rather than the four
     `test_rerun.py` carried, and the closure count is one exact total across all of them.
     `test_retention.py` stays separate — a branch forked into that graph would read every object in
     it that is still live, leaving the migration nothing to repair. The mutation findings recorded
     above were re-run against the consolidated suite and still hold, with one exception: reverting
     the stamp to `coalesce(owner_gone_at, owning_closed_at)` now passes, because resolving the owner
     from its newest existence edge already prevents the back-dating the later-of-two comparison was
     added to stop.

  Mutation check, and the finding is worth keeping: **idempotence is doubly guarded**, so a single-site mutation is not caught. Dropping `edge_to_close.to IS NULL` from the write subquery alone still passes, because the shared predicate's quick filter has already dropped the candidate for want of an open global edge; dropping the quick filter's `global_edge.to IS NULL` alone still passes, because the write guard catches it. Only removing both makes the second run report `Closed 9`, which fails the test. Either guard alone is sufficient for SC-004a — a useful robustness property, not a redundancy to clean up.
- [X] T044 [US2] Implement `Migration076` in `backend/infrahub/core/migrations/graph/m076_retire_agnostic_property_edges.py` as an `ArbitraryMigration` with `minimum_version: int = 75`, modelled on `m075_finish_deleting_branches.py`: read branches with `Branch.get_list(db=db)` (the registry may be unpopulated in an upgrade process), run the query's unbounded form **with the widened anchor** (T011), batch at the existing `MAX_AGNOSTIC_PEER_BATCH_SIZE` (500) cap, report **both** counts via `get_migration_console()`, and return `MigrationResult(errors=[...])` without raising (FR-016) Delivered as `Migration077` in the package `backend/infrahub/core/migrations/graph/m077_retire_agnostic_property_edges/` (`__init__.py`, `migration.py`, `queries.py`), `minimum_version = 76`, per T058. Four deviations from the text above, all deliberate:

  1. **No `Branch.get_list(db=db)`.** That instruction belongs to the withdrawn Phase 2, where branch windows were built in Python. The shipped `UNRETAINED_AGNOSTIC_FIELD_PREDICATE` reads `(:Branch)` in Cypher, so a Python branch read would be dead code. The concern behind it is still satisfied: the migration touches the registry nowhere.
  2. **Two queries, not one.** `CloseUnretainedAgnosticFieldsQuery` reuses the shared predicate verbatim under a widened anchor; `DeleteDetachedAgnosticFieldsQuery` hard-deletes the field vertices with no linked node vertex. Both batch at `MAX_AGNOSTIC_PEER_BATCH_SIZE` via `CALL … IN TRANSACTIONS`, and each is exception-guarded independently so a failure in one is reported and the other still runs.
  3. **The widened anchor was kept**, per the maintainer's 2026-08-25 decision rule ("if handling half-closed shapes does not change the query much, take the more thorough approach"). It costs exactly two omitted lines relative to the runtime anchor — the `anchor.from <= $at` and `anchor.to IS NULL` filters are dropped, `anchor.status = "active"` stays — with no extra pass and no same-UUID rewrite, since the shared predicate already carries that protection by reading every linked node vertex. Verified against a half-closed fixture (owning edge closed, property edges open) in a throwaway test that was not kept, because T042 owns those tests. Per-edge closure (FR-002a) is guarded by `edge_to_close.to IS NULL` inside the write subquery, so each edge closes only where still open, independently of the others.
  4. **Counts come from the query stats, not a `RETURN`** (`properties_set` and `nodes_deleted`, summed with a `or 0` guard because Bolt omits zero counters), since `CALL … IN TRANSACTIONS` must be a unit subquery. Reported through `migration_input.console`, whose default is `get_migration_console()`.

  Per-candidate stamp derivation (C4, which T044's text omits): `coalesce(owner_gone_at, owning_closed_at)` where `owner_gone_at` is `max` over every linked node vertex's existence edges of (`from` of a `deleted` edge, else `to` of a closed `active` edge) and `owning_closed_at` is `max` of the `to` of the vertex's already-closed owning edges. Neither derivable ⇒ `WHERE retired_at IS NOT NULL` drops the candidate untouched. One guard beyond the contract: the `SET` clamps to `edge_to_close.from` when the derived stamp predates it, so a derived stamp can never produce an inverted interval.

  Not built here, deliberately: shape 4 ("anything else the predicate cannot resolve") is skipped in Cypher and the migration completes without raising, but the **count** of skipped candidates is not reported — that would need a second unbounded predicate pass. T041 owns the scenario-4 test and can add a read query for it purely additively; nothing about the current shape blocks it. Note also that a non-empty `MigrationResult.errors` **does** abort the upgrade in the migration runner, so C4's "returns `errors=[...]` … never fails the upgrade" cannot both hold: errors carry caught exceptions only, and unrepairable data shapes are skipped rather than recorded there.
- [X] T046 [US2] Register `Migration076` in `backend/infrahub/core/migrations/graph/__init__.py` and bump `GRAPH_VERSION` from 75 to 76 in `backend/infrahub/core/graph/__init__.py` Registration needed no edit: `discover_migrations()` picks up the `m077_…/` package from its `__init__.py` export, which `MIGRATION_PACKAGE_PATTERN` already matches. `GRAPH_VERSION` bumped 76 → 77 per T058, not 75 → 76. `backend/tests/unit/core/graph/test_graph_version.py` (last migration number == `GRAPH_VERSION`, last `minimum_version` == `GRAPH_VERSION - 1`) passes.
- [ ] T047 [US2] Verify SC-001 and SC-002 on a dataset carrying the pre-fix orphan shapes, adding the checks to `backend/tests/component/migrations/test_m076_retire_agnostic_property_edges.py`: a data-only proposed change validates clean, and a schema update adding a uniqueness constraint on a previously-orphaned branch-agnostic attribute loads successfully Delivered as `.../m077_retire_agnostic_property_edges/test_success_criteria.py` (T058's path, not the one named here), two tests. Unlike the other 13 in the package these assert no graph shape at all: each builds the orphan with the raw-Cypher fixtures, drives the real validation machinery, asserts the violation the operator is stuck on today, runs the migration, and asserts the same validation now comes back clean. Asserting both sides in the test itself — rather than proving it by a one-off mutation — makes a no-op migration a permanent test failure. Four things worth recording: **Reopened 2026-08-27**: the two tests that verified SC-001/SC-002 (`test_success_criteria.py`) were deleted by maintainer decision — the migration's contract is the graph state it leaves behind, and re-testing every consumer that the pre-fix data used to break is out of scope for it. The behaviour they proved is unchanged and their finding stands (only the non-targeted uniqueness checkers ever saw the phantom, since `TargetedUniquenessValidationQuery` and `AffectedUniquenessDependentsQuery` both apply an `IS_PART_OF` liveness filter), but SC-001 and SC-002 now have no automated coverage. Decide whether they are verified another way or dropped from the success criteria.

  1. **Only the non-targeted, full-population uniqueness checkers ever saw the phantom.** `TargetedUniquenessValidationQuery` and `AffectedUniquenessDependentsQuery` both resolve each candidate's latest `IS_PART_OF` edge and drop anything whose winner is not `active`, so a vertex whose owner is tombstoned was never counted by them. `AttributeUniqueUpdateValidatorQuery` (`attribute.unique.update`) and `NodeUniqueAttributeConstraintQuery` (`node.uniqueness_constraints.update` with `node_uuids=None`) have no such filter: they walk `(:Kind)-[:HAS_ATTRIBUTE]->(:Attribute)-[:HAS_VALUE]->(:AttributeValue)` and require only that the path be active and in the branch window, which an open global edge satisfies. That narrows where the reported symptom was ever reachable from, and it shows in the observed output: the data-only run reports only the attribute-level violation, because the node-level constraint derived from a *data* diff carries `node_uuids` and therefore goes down the immune targeted path, while the schema-diff run reports both.
  2. **The data-only change had to be a node deletion, not a create or an update.** A branch-agnostic field's edges live on the global branch, and `DiffAllPathsQuery` requires `r_node.branch = top_diff_rel.branch` (`backend/infrahub/core/query/diff.py`), so a widget created or updated on a branch never puts `serial` in that branch's diff and the determiner never emits the constraint that trips. A deletion does, because the delete writes branch-scoped `deleted` edges for the agnostic field alongside the existence edge. The branch in the test therefore removes an unrelated widget, which is also the more honest scenario: the change touches nothing holding the reserved value and is refused anyway.
  3. **The drivers are production code, not re-implementations.** SC-001 runs `MergeConstraintValidator.validate(candidate_schema, schema_diff_constraints=[])` over the branch's tracked diff — the same determiner + `build_constraint_info_merger` + `schema_validate_migrations` composition the proposed change's schema-integrity check runs, with an empty schema-diff side standing for "data-only"; only the source of the field summaries differs (diff repository rather than the SDK diff summary, which would need a live API). SC-002 runs `evaluate_candidate_schemas` + `schema_validate_migrations`, which is exactly `load_schema`'s gate: a non-empty message list is what it turns into `SchemaNotValidError`.
  4. **Both payoff assertions were confirmed to fail without the migration**, and to fail as the phantom-holder duplicate specifically rather than incidentally: `Attribute-level 'unique' constraint violation on schema 'AgnosticretireWidget' ... field serial='8100'` naming both the live holder and the orphan, plus the node-level equivalent on the schema-update side. The assertions match on the constraint *and* the value, so a broken fixture or an errored validator cannot stand in for the symptom.

**Checkpoint**: A stuck deployment can escape without a database intervention. User Stories 1 and 2 both work independently.

---

## Phase 5: User Story 3 - The deletion semantics are documented (Priority: P2)

**Goal**: An operator reading the user-facing documentation can predict what happens to a
branch-agnostic attribute or relationship when its object is deleted or the field is removed from
the schema.

**Independent Test**: Documentation review against the enforcement points.

**Depends on**: Phase 3 (the behaviour must exist before it is documented).

- [ ] T048 [US3] Document the deletion semantics for branch-agnostic attributes and relationships on branch-aware objects in the relevant page under `docs/docs/`: when the value is released, when release is deferred, what resolves the deferral (delete on the retaining branch, rebase past the deletion, merge, or branch deletion), and what a branch forked before the deletion sees (FR-019, SC-009) **Written 2026-08-31; in the working tree, not yet committed — tick when it lands.** Added "Deleting a branch-agnostic attribute or relationship" to `docs/docs/schema/branch-awareness.mdx` — the page that already defines `branch: agnostic`, so the semantics sit next to the setting that causes them. Three subsections: when the value is released (no branch holds a live owner; one owner for an attribute, both peers for a relationship), when release is deferred (a **retaining branch** — one created before the deletion, which reads the object unchanged), and what resolves the deferral (delete on the retaining branch, rebase past the deletion, merge, branch deletion, schema removal), stating explicitly that none of them releases unconditionally. A note ties resource-pool allocations to the same rule, and the Related concepts list gains a resource-manager link. FR-019/SC-009 covered.
- [X] T049 [US3] Document that `m077` mutates existing data on upgrade — closing edges and hard-deleting vertices with no linked node — and that it is irreversible, in the upgrade documentation under `docs/docs/` **Closed 2026-08-31 as not required**, by maintainer decision: a database migration is Infrahub's responsibility and should be transparent to the operator, and the standard upgrade procedure already tells them to take a backup first. A section had been written into `docs/docs/deploy-manage/maintain-upgrade/upgrade/overview.mdx` and was reverted.
- [ ] T050 [US3] Run `uv run invoke docs.lint` and fix any Markdown violations per `dev/guidelines/markdown.md` **Run 2026-08-31 over the working-tree changes; re-run when they land.** `markdownlint-cli2` over all 187 pages: 0 errors (`uv run invoke docs.lint` aborts before running it unless `markdownlint-cli2` is on `PATH`; run it from `docs/node_modules/.bin`). `vale` is not installed locally either — ran it through `jdkato/vale` in Docker over the changed pages plus the changelog fragment: clean after one fix, "tombstoned" tripped `Infrahub.spelling` in the fragment and was reworded. A full-tree vale run in that image reports 247 pre-existing errors, almost all frontmatter keys (`hide_table_of_contents`, `toc_max_heading_level`), which is an image/version artifact rather than a real regression.

**Checkpoint**: All three user stories independently functional.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [ ] T051 [P] Add a towncrier changelog fragment under `changelog/` for the user-visible behaviour: branch-agnostic values are released when no branch retains their object, and freed pool values become allocatable again **Written 2026-08-31** as `changelog/9762.fixed.md`, named for the issue it fixes. Covers the pre-fix symptom (proposed-change conflicts naming IDs that resolve to nothing, a uniqueness constraint that cannot load, pool values allocated to objects that are gone), the release rule and its per-kind arity, deferral by a retaining branch and the four events that resolve it, the six enforcement points, and that upgrading clears the backlog.
- [ ] T052 [P] Update `dev/knowledge/backend/` with the retirement invariant and the six enforcement points, per the constitution's Documentation Requirements for backend architecture changes **Written 2026-08-31; in the working tree, not yet committed — tick when it lands.** Added as a "Branch-agnostic fields on branch-aware Nodes" subsection under Node Lifecycle → Deletion in `dev/knowledge/backend/database-schema.md`, rather than as its own page: that doc already carries `branch_support`, the global branch and the delete edge mechanics, which is the context the rule only makes sense in. Three paragraphs — why a branch-level delete alone leaks the value, the rule that every path which can stop an object being readable must re-evaluate retention (with the per-branch/per-vertex conjunction and the two-peer requirement for a `Relationship`), and the pointer to `UNRETAINED_AGNOSTIC_FIELD_PREDICATE` as the one place the logic lives, listing the six call sites plus `m077` and stating that a seventh deletion path needs a seventh call site. A first draft as a standalone `branch-agnostic-retirement.md` was discarded as too verbose for what the reader needs.
- [X] T053 Run `uv run invoke format` and `uv run invoke lint` (ruff + mypy) — zero lint errors, no unjustified `type: ignore`
- [X] T054 Run `uv run invoke backend.test-unit` and the full component suite for this feature: `uv run pytest backend/tests/unit/core/agnostic/ backend/tests/component -k agnostic`
- [X] T055 Run `/pre-ci` (`.agents/commands/pre-ci.md`), including `uv run invoke docs.validate` — CI fails on any stale generated doc
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

---

## Phase 7: Convergence

Appended by `/speckit-converge` on 2026-08-24. Assessment of the codebase against spec.md,
plan.md, and tasks.md found twelve gaps; eight are already carried by open tasks above
(T001, T020, T039–T047, T048, T049, T051, T052, T057, R05, R06, R07) and are **not**
duplicated here. These four have no existing task.

R08's removal targets never shipped — Phase 2 was withdrawn before `backend/infrahub/core/agnostic/`
or `backend/infrahub/core/query/agnostic_retirement.py` were created — so the superseded stack does
not exist and R08 has no remaining work.

- [X] T058 Renumber the repair migration from `m076` to `m077` and the version bump from 75→76 to 76→77 per T044/T046 and `contracts/retirement-component.md` C4 (contradicts). `m076_heal_missing_attribute_rows/` already occupies the m076 slot and `GRAPH_VERSION` is already 76 on the base branch (landed via #10353), so the numbers every artifact states are now taken. Create `backend/infrahub/core/migrations/graph/m077_retire_agnostic_property_edges.py` with `minimum_version: int = 76`, bump `GRAPH_VERSION` 76 → 77 in `backend/infrahub/core/graph/__init__.py`, and name its tests `backend/tests/component/core/migrations/graph/m077_retire_agnostic_property_edges/`. No manual registration is needed — `backend/infrahub/core/migrations/graph/__init__.py` discovers migrations via `discover_migrations()`, so T046's registration half is already satisfied by placement. Correct the stale `m076` / 75→76 references in the Blocking-gate section, T044, T046, T049, and C4 while making the change, and re-confirm the migration number is still free at the moment it lands, since the base branch may take another slot first. **Done 2026-08-25.** `m077` re-confirmed free at implementation time (`m076_heal_missing_attribute_rows/` is the highest occupied slot; `GRAPH_VERSION` was 76). Shipped as a package rather than the single module the task names, following the `m076` convention: `backend/infrahub/core/migrations/graph/m077_retire_agnostic_property_edges/{__init__,migration,queries}.py`, class `Migration077`, `minimum_version = 76`, `GRAPH_VERSION` 76 → 77. Tests live in `backend/tests/component/core/migrations/graph/m077_retire_agnostic_property_edges/`. Stale references corrected in the Blocking-gate section, T044, T045, T046, T049, and C4 of `contracts/retirement-component.md`; the numbers in plan.md §Scope and §Complexity Tracking still read `m076` and are left for the plan's own revision.
- [X] T059 Measure branch rebase for memory exhaustion at a deletion count large enough to stress both unbounded dimensions, per Constitution Principle V ("Memory footprint MUST be considered: large result sets MUST use pagination or streaming") and FR-018 (missing). Nothing currently tests this: `backend/tests/query_benchmark/test_fr018_agnostic_retirement_operations.py` reports wall-clock medians only, over small datasets at ~3 and ~100 open branches, and rebases one victim node per sample. Two dimensions grow unbounded in a real large rebase and neither is covered:

  1. **Process side** — `_retire_agnostic_fields_of_base_deletions` (`backend/infrahub/core/branch/tasks.py:484`) receives the base-branch diff's complete removed-node uuid list and holds all of it in memory before slicing it at `RETIREMENT_BATCH_SIZE = 500`. The batching bounds each query, not the list that feeds it.
  2. **Database side** — `_RETIRE_UNRETAINED_FIELDS_OF_NODES` (`backend/infrahub/core/query/node_agnostic_retirement.py`) does `WITH collect(DISTINCT field) AS agnostic_candidates` and then runs `UNRETAINED_AGNOSTIC_FIELD_PREDICATE`, which cross-joins that collected list against every non-`DELETING` branch and every linked vertex. A 500-uuid batch is bounded in uuids but not in fields-per-node or branches, so the intermediate row set is the product of three growing terms.

  Build the case in the FR-018 harness: a branch open across a base-branch deletion of enough nodes to exceed several `RETIREMENT_BATCH_SIZE` slices, each carrying a branch-agnostic attribute and relationship, at the realistic-high open-branch count. Assert the rebase completes and record peak Neo4j heap and peak Python RSS alongside the duration, so the ceiling is a number rather than an assumption. If either grows with total deletion count rather than with batch size, bound it — stream the uuids from `DiffRepository.get_affected_node_uuids` instead of listing them, and/or cap the candidate collection inside the query — and re-measure. Apply the same check to `DiffMerger.merge_graph` (`backend/infrahub/core/diff/merger/merger.py`), which feeds the same query the same way and has the same shape.

  **Measured 2026-08-31; no bound needed.** Built
  `backend/tests/query_benchmark/test_t059_agnostic_retirement_memory.py`, which runs rebase and merge
  at two deletion counts 4x apart (600 and 2,100 — 2 and 5 `RETIREMENT_BATCH_SIZE` slices), each
  object carrying a branch-agnostic attribute **and** relationship, ten background branches forked so
  every candidate is retained and the predicate prunes nothing. RSS is sampled on a polling thread and
  reported as growth from the operation's start, since the absolute peak also carries the resident
  population; the harness's own leftovers are cleared between cells, because stale branches inflate the
  predicate and make the two counts incomparable. Full numbers in quickstart.md §Memory footprint.

  1. **Merge does not grow at all** — 0.0 MB at both counts, and 3.5x the deletions costs 2.9x the
     time. Dimension 2 is closed for the merge path outright.
  2. **Rebase grows with the total deletion count** (74.6 → 177.5 MB), but that is the *whole* rebase.
     A separate run wrapped the retirement call in its own sampler: over 2,100 candidates in 5 batches
     it costs **768.7 ms of 63,662.9 ms (1.2%) and 2.0 MB of 188.4 MB (1.1%)**. The growth is the
     rebase's own diff machinery, not this feature.
  3. **The prescribed remedy is therefore not worth applying.** Streaming the uuids out of
     `DiffRepository.get_affected_node_uuids` would target ~1% of the footprint: 2,100 uuids is ~76 KB
     of strings, and a million deletions would be ~36 MB. Recorded as a known residual — the list is
     linear in deletion count, just far too small to matter — rather than bounded.
  4. **The database side is bounded as designed.** R07's profile puts one 500-uuid batch at 35,632 db
     hits, and the collected candidate list never exceeds a batch, which is what the batching buys.

  Not measured: heap. The JMX readings are before/after rather than sampled and are dominated by GC
  (one merge cell read 879.7 MB before and 332.9 MB after), so they describe the JVM's collection
  schedule rather than this feature, and are omitted rather than reported as peaks.
- [X] T060 Justify or revert the `python_sdk` submodule pointer bump `99a380a → f9e28cf` (unrequested). No requirement, plan decision, or task in this feature calls for an SDK change, and `AGENTS.md` §Submodules requires the SDK commit be pushed upstream and merged there before the pointer bump lands here — a pointer to an unpushed commit breaks every other checkout. Confirm the target commit exists on the SDK branch named after this Infrahub branch's base (`release-1.11`), or restore the original pointer before opening the PR. **Resolved 2026-08-31:** `git diff stable...HEAD -- python_sdk` is empty — the pointer bump is no longer on the branch, so nothing needs justifying or reverting.
- [ ] T061 Remove or relocate the untracked repo-root working files not named by any artifact (unrequested): `IFC-2843-ROLLBACK.md`, `PR_DESCRIPTION.md`, and the `repositories/` directory. `IFC-2843-prd.md` stays — spec.md names it as the feature's input. Fold anything in the rollback notes still worth keeping into `plan.md` §"The rollback is part of the invariant" rather than leaving it at the repo root.
