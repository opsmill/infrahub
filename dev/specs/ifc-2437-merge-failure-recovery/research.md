# Phase 0 Research: Merge Failure Recovery

**Spec**: `spec.md` | **Date**: 2026-06-04 (rewritten for the single-state, operator-driven design)

This document resolves the open implementation questions the spec deferred to planning. Each
section states a question, a decision, the rationale, and alternatives considered. All file
references reflect the current code on this branch.

> **Why this is a rewrite.** An earlier revision of this document described a two-status
> (`MERGING` + `MERGING_GRAPH`) marker and *automatic* rollback at startup. The current spec
> instead mandates (1) a single dedicated `MERGE_FAILED` status, (2) a recurring background
> detector that does not depend on a restart or write traffic, and (3) *operator-driven* recovery
> via an `infrahub recover` CLI. The decisions below are aligned to the current spec and to a key
> code fact the earlier version missed: the global merge lock is held for the *entire* `MERGING`
> window, not just the graph-merge step.

## R1. What marks a branch as "merging" and "merge-failed", and is a sub-phase status needed?

**Decision**: Add **one** new `BranchStatus` value, `MERGE_FAILED`, and **one** persisted scalar
field on `Branch`, `merge_started_at: Timestamp | None`. No `MERGING_GRAPH` sub-status.

- `MERGING` already exists (`backend/infrahub/core/branch/enums.py`) and is set on the source
  branch at `backend/infrahub/core/branch/tasks.py:396` for the duration of `_do_merge_branch`.
- `merge_started_at` is the `merge_at` Timestamp created at `tasks.py:376` and passed into
  `merger.merge(at=merge_at)`. It is persisted when the branch transitions `OPEN → MERGING` and
  is required by recovery because the rollback Cypher is keyed on it (`from=$at`/`to=$at`).
- `MERGE_FAILED` is set by the detector (R4) when it observes the failed-merge condition (R3).
  It is durable and is the persistent signal that drives all protections.

The merge target is always `registry.default_branch`, so the target name is not persisted;
recovery resolves it via the registry.

**Why a sub-phase status is *not* needed (the key correction).** The global merge lock is acquired
in `merge_branch` *around the whole* `_do_merge_branch` call:

```python
# backend/infrahub/core/branch/tasks.py:296-309
merge_locker = MergeLocker()
async with merge_locker.acquire_global_lock():      # held for the FULL window
    obj = await Branch.get_by_name(db=db, name=branch)
    if obj.status != BranchStatus.OPEN:
        return
    node_events = await _do_merge_branch(...)         # graph merge + migrations + IPAM + MERGED
```

So the lock's lifetime exactly brackets the `MERGING` state. A single condition — *branch in
`MERGING` while the merge lock is no longer held by a live worker* — covers the entire failure
window with no ambiguity, which is precisely what the spec's FR-007 asks for. The earlier design
split the window only because it assumed the lock was released before the post-graph-merge steps;
it is not.

**Rationale**:

- `BranchStatus` already uses durable transient states (`DELETING`, `MERGING`) as precedent;
  `MERGE_FAILED` follows the same shape and is persisted on the `:Branch` node, so it survives
  any restart (constitution II).
- `merge_started_at` must be persisted because the in-memory merge context (the `merge_at`
  Timestamp and `DiffMerger._affected_node_uuids`) is lost when a worker dies, and rollback
  completeness depends only on that timestamp (R3, R7).

**Alternatives considered**:

- **Two statuses (`MERGING`/`MERGING_GRAPH`).** Rejected — superseded by the lock-lifetime fact
  above and contradicts the spec's single-`MERGE_FAILED` decision. It also forced recovery to
  ignore migration-phase crashes structurally; we handle that scoping explicitly instead (R8).
- **A `merge_in_progress: bool` separate from status.** Rejected — splits "is this branch
  writable?" across two fields and duplicates the existing status gate.
- **A separate `:MergeAttempt` node.** Unjustified for one scalar field; complicates the scan.
- **External store (Redis) for the marker.** Not durable enough; markers must survive any restart.

## R2. How is the failed-merge condition evaluated reliably?

**Decision**: Reuse the **exact mechanism `clean_up_deadlocks` already uses**
(`backend/infrahub/locks/tasks.py`): read the merge-lock token, split `timestamp::worker_id`, and
treat the merge as dead when `worker_id` is not in the active-worker set returned by
`service.component.list_workers(...)`.

The predicate (a pure function, unit-testable):

> A branch is a *failed merge* iff `branch.status == MERGING` **and** the `MergeLocker`
> "all_branches" lock is **present** but held by a `worker_id` not in the active-worker set **and**
> `now − merge_started_at > grace_period`. A branch whose lock is held by an active worker — or whose
> merge is younger than the grace period — is *healthy in-progress* and MUST NOT be marked failed.
> An **absent** lock is deliberately **not** treated as failure (see below): the predicate requires
> the lock to be present so it can read the holder's `worker_id` and so an ambiguous absence (cache
> flush during a live merge, or a lock already swept) cannot false-positive.

Supporting facts:

- The merge lock is `MergeLocker().acquire_global_lock()` → `lock.registry.get(name="all_branches",
  namespace="merge")` (`backend/infrahub/core/merge/merge_locker.py`). Its cache value is the
  `timestamp::worker_id` token (`backend/infrahub/lock.py`).
- The worker that runs the `branch-merge` Prefect flow refreshes a heartbeat key
  `workers:active:{component}:worker:{WORKER_IDENTITY}` with a 15-second TTL every 10 seconds
  (`backend/infrahub/services/component.py`; `backend/infrahub/services/scheduler.py`). When the
  worker dies, its heartbeat expires within ~15 s, so its `worker_id` leaves the active set well
  inside one ~1-minute scan interval.
- **A long merge does not falsely expire the heartbeat.** The merge flow runs in-process in the
  worker's async event loop (`InfrahubWorkerAsync`, no subprocess/thread), and Neo4j calls are
  awaited, so the heartbeat task keeps firing during a long query. Verified locally against Neo4j on
  `localhost:7687`: a 17 s server-side compute and a 100 s 5M-row result-consumption each kept a 1 s
  ticker (standing in for the scheduler's refresh loop) at ~1 s cadence throughout — no stall past
  the 15 s TTL. So `worker-inactive` is a reliable death signal, not a "busy" artifact.
- **Grace period.** The predicate still requires `now − merge_started_at > grace_period` (a small
  configurable threshold, default ~2–3 minutes) as cheap insurance against a transient
  cache/heartbeat-write blip momentarily expiring a live worker's key. This is *not* needed to cover
  long merges (the heartbeat survives those); it just makes a single missed heartbeat non-fatal. It
  mirrors `clean_up_deadlocks`, which deletes a lock only when the worker is inactive **and** the
  lock is older than `clean_up_deadlocks_interval_mins` (default 15). Because the default branch is
  blocked for the whole `MERGING` window regardless, the grace period only delays the
  `MERGING → MERGE_FAILED` transition, not the write protection.
- `clean_up_deadlocks` already compares merge-lock tokens against this active set, so the signal
  is proven for this exact lock.

**Mechanism choice (spec Assumption b vs a)**: use **worker-liveness** (b), *not* a lock TTL (a).
Liveness avoids the "slow-but-healthy merge misclassified by a timer" risk that a TTL introduces,
needs no new lock lifetime tuning, and matches the existing precedent. We therefore do **not** add
a TTL to the merge lock.

**Interaction with `clean_up_deadlocks`**: that task will itself delete the dead merge lock once it
is older than `clean_up_deadlocks_interval_mins` (default 15). The merge watcher marks `MERGE_FAILED`
within grace + one scan interval (≈3–4 min) — well before the 15-min sweep — so a real failed merge
is always flipped while its lock is still present. The two tasks are complementary and do not race
destructively.

**Why "lock present" and not "lock absent or present"**: requiring the lock to be present is both
sufficient and safer. A dead worker cannot run its lock release, so a genuinely failed merge always
leaves the lock present with a dead holder — caught by the predicate before the 15-min sweep. The
only ways the lock is *absent* while `status == MERGING` are (a) the deadlock sweep, which only
occurs after the branch is already `MERGE_FAILED`, or (b) a **cache flush during a live merge** — the
merging worker holds the lock in-process via its `async with` block and never re-reads the cache, so
the lock key vanishes while the merge runs healthily. If the detector treated "lock absent" as
failure, case (b) would false-positive a live merge (blocking the default branch with the recovery
message after the grace period). So an absent lock is **not** auto-flagged. This fails safe: the
branch stays `MERGING` and write-blocked (the recurring scan re-derives the `merge:protected` key
from the durable `MERGING` status), it is simply not auto-transitioned to `MERGE_FAILED` on an
ambiguous signal. `infrahub recover` (operator-confirmed) **does** act on such a `MERGING` branch with
no live lock holder — its detection covers both `MERGE_FAILED` and this stuck-`MERGING` case (spec
clarification 2026-06-09, FR-016) — so the ambiguous/swept-lock edge always has a recovery path, with
a human verifying first.

**Alternatives considered**: TTL-based expiry (rejected, see above); reading Prefect flow-run
state to detect a crashed merge (rejected — couples detection to the orchestrator's internal state
and is not durable across Prefect restarts); **persisting the merge worker's `WORKER_IDENTITY` on the
branch** so liveness could be checked without the lock present (rejected — the holder id is read from
the merge lock token, exactly as `clean_up_deadlocks` does, so no new persisted field is introduced;
the "lock present" precondition is intrinsic to that precedent, not an extra gate, and the one case
it does not auto-detect — a dead merge whose lock also vanished via a cache flush — fails safe, since
the recurring scan re-derives the `merge:protected` block from the durable `MERGING` status and
operator recovery can finish it).

## R3. Can rollback run with no in-memory merge context (after the worker died)?

**Decision**: Yes. Recovery needs only `(source_branch, target_branch, merge_started_at)` plus a
node-UUID list it can fetch statelessly.

The post-rewrite `DiffMerger.merge_graph(at)` (`backend/infrahub/core/diff/merger/merger.py`):

- Runs five bulk merge queries (`BulkMergeNodeExistenceQuery`, `BulkMergeRelationshipEdgesQuery`,
  `BulkMergeCardinalityOneResolutionQuery`, `BulkMergeAttributePropertyEdgesQuery`,
  `BulkMergeRelationshipPropertyEdgesQuery`), each `@retry_db_transaction`, all writing to
  `branch=$target_branch` only and stamping every created edge `from=$at` and every closed edge
  `to=$at` (`backend/infrahub/core/diff/query/bulk_merge.py`).
- Discovers affected node UUIDs via `DiffRepository.get_affected_node_uuids(source_branch,
  target_branch, at, tracking_id)` — a **stateless** query over the persisted diff graph
  (`AffectedDiffNodeUUIDsQuery`), not in-memory state.
- Writes metadata + rollback snapshots (`previous_updated_at/by`) via `DiffMergeMetadataQuery`.

The existing `RollbackQuery` (`backend/infrahub/core/query/rollback.py`):

- Restores `updated_at/by` from `previous_*` on the given `node_uuids` and their connected
  Attribute/Relationship vertices,
- Reopens edges with `to=$at, branch=$target_branch` (sets `to=NULL`),
- Deletes edges with `from=$at, branch=$target_branch` and cleans orphaned vertices.

Edge cleanup is **keyed on `$at` + branch**, not on specific UUIDs — so completeness depends only on
`merge_started_at` being correct, which the persisted marker provides.

**Implication**: recovery needs **only `(default branch, merge_started_at)`** and runs entirely from
the persisted graph + the durable `merge_started_at` marker — no in-memory merge context, and (with
the R8 range design) **no `get_affected_node_uuids` list at all**: the structural revert is scoped by
branch + timestamp range, and the metadata restore is scoped to the reverted-edge vertices filtered
by `updated_at >= merge_started_at` (R8). The earlier iteration of this section fetched the affected
UUIDs via `get_affected_node_uuids(...)` for an exact-`$at`, UUID-scoped restore; R8 supersedes that
with the range query, which removes the UUID dependency entirely.

**Idempotence**: re-running rollback is safe — no edges match `>= merge_started_at` after deletion;
reopen finds nothing; the `updated_at >= merge_started_at` filter excludes already-restored vertices
(their `updated_at` was restored to `< merge_started_at`).

**Alternatives considered**: persist `affected_node_uuids` incrementally during merge (unnecessary —
recovery needs no UUID list under R8); replay a transaction log (Neo4j exposes none).

## R4. Where does detection run, and how is it single-flighted?

**Decision**: Three places evaluate the R2 predicate; the recurring one is authoritative.

1. **Authoritative recurring scan (FR-010)** — a new Prefect `INTERNAL` workflow `MERGE_WATCHER`
   added to `WORKFLOWS` in `backend/infrahub/workflows/catalogue.py`, modeled exactly on
   `CLEAN_UP_DEADLOCKS`:
   ```python
   MERGE_WATCHER = WorkflowDefinition(
       name="merge-watcher",
       type=WorkflowType.INTERNAL,
       cron="* * * * *",                               # one minute, below any merge duration margin
       module="infrahub.tasks.merge_watcher",          # flow function lives here
       function="detect_failed_merges",
       concurrency_limit=1,
       concurrency_limit_strategy=ConcurrencyLimitStrategy.CANCEL_NEW,
   )
   ```
   `concurrency_limit=1` + `CANCEL_NEW` gives single-flighting across all workers — the same
   guarantee `CLEAN_UP_DEADLOCKS` relies on. `setup_deployments()`
   (`backend/infrahub/workflows/initialization.py`) iterates `get_workflows()` and creates the
   cron deployment automatically once the definition is in `WORKFLOWS`.

2. **Startup fast path (FR-011a)** — call the detector once from
   `backend/infrahub/core/initialization.py` after `initialize_registry()` has loaded branches.
   Both the API server (`server.py:app_initialization`) and the git-agent
   (`cli/git_agent.py:start`) call `initialization(db)`, so a restart of either records the
   failure immediately.

3. **On-demand fast paths (FR-011b/c, FR-012)** — when a write to the default branch finds a branch
   in `MERGING`, escalate by evaluating the predicate so the write returns the recovery message
   instead of "retry shortly"; likewise evaluate before starting a new merge/rebase. These are
   evaluated inside the write/merge gates (R5). FR-012: once `MERGE_FAILED` is persisted, the
   steady-state write check reads status only and does not inspect the lock.

**Single-flight detail**: even though three entry points exist, marking is idempotent — setting
`MERGE_FAILED` on a branch already in `MERGE_FAILED` is a no-op, and only `MERGING` branches are
candidates. Writes happen under the branch's own save; concurrent detectors converge on the same
status.

**Alternatives considered**: an asyncio `Schedule` in `services/scheduler.py` (rejected — it is
per-process, not single-flighted across workers, and the Prefect `INTERNAL` pattern already exists
for exactly this kind of cluster-wide recurring maintenance task).

## R5. How are writes, merges, rebases, and deletes blocked?

**Decision**: Extend the existing `BranchStatusChecker`
(`backend/infrahub/branch/status_checker.py`) — the established chokepoint that already gates on
`MERGED`/`MERGING`/`NEED_REBASE`.

- **Writes during a healthy merge (FR-001/002/003)**: `check_merge_status` already treats `MERGING`
  as read-only and raises `BranchAlreadyMergedError`. We refine the messaging so a `MERGING` block
  returns the *transient* "merge in progress, retry shortly" message (FR-002), distinct from the
  `MERGE_FAILED` message. The **target gate** (default branch is read-only while a branch is
  `MERGING`/`MERGE_FAILED`) and the **source gate** both read the shared `merge:protected` cache key
  (R11) — immediately consistent across workers, one cache `GET`, no per-write database read.
- **Writes after a failure (FR-009/012/013)**: a new branch in `MERGE_FAILED` (the branch itself
  and the default branch as target) rejects writes with a message naming `infrahub recover` and
  "contact an administrator". This reads persisted status only — the fast path of FR-012.
- **New merges/rebases (FR-004)**: block when the source is non-`OPEN` (already enforced at
  `tasks.py:299`) and when *any* branch is `MERGING`/`MERGE_FAILED` (the merge lock would also
  serialize them, but the status gate makes the block explicit and gives a clear error).
- **Deletion of a `MERGE_FAILED` branch (FR-014)**: `Branch.delete()`
  (`backend/infrahub/core/branch/models.py`) currently has no status gate. Add a guard that refuses
  deletion when `status == MERGE_FAILED` (recover first). `MERGED` branches remain deletable.

`BranchStatusError`/`BranchAlreadyMergedError` (existing) cover these cases; the only genuinely new
need is a distinct error/message for the `MERGE_FAILED` recovery instruction (contract §6). The
write-gate call sites are the existing callers of `BranchStatusChecker.check` (GraphQL mutation
middleware `graphql/middleware.py`, REST `api/schema.py`, `api/artifact.py`). An audit during
`/speckit-tasks` confirms every mutating path funnels through the checker.

**Alternatives considered**: a new `Branch.assert_writable()` helper (rejected — duplicates the
checker's role); Cypher-level constraints (cannot express "writes forbidden during a transient
state").

## R6. The `infrahub recover` CLI command shape.

**Decision**: A new `AsyncTyper` command mirroring the existing admin pattern in
`backend/infrahub/cli/db.py` (e.g. `reset-deployment-id`):

- Registered in `backend/infrahub/cli/__init__.py`. Either a top-level `infrahub recover` command
  or a small typer group; top-level command is simplest and matches the spec wording.
- Bootstrap: `config.load_and_exit(config_file)` → `context.init_db(retry=1)` →
  `initialize_registry(db=db)` (needed to resolve the default branch and load schema) → operate →
  `await dbdriver.close()` in `finally`.
- Auto-detect (FR-016): run the R2 predicate to find the single `MERGE_FAILED` (or lingering
  `MERGING` whose lock is dead) branch. Report branch name, persisted `merge_started_at`, and the
  associated proposed change if any (R7), using `rich.Console`.
- Confirm (FR-016/017): `typer.confirm(...)` unless `--yes/-y` is passed (the `db.py` pattern).
- Recover (FR-018/019/020/021): rollback (R3) → reset source branch status to `OPEN` (leave
  `merge_started_at` in place; it is overwritten by the next merge) → reset associated proposed
  change to `OPEN` (R7) → delete the `merge:protected` key so the write block lifts.
- No-failure (FR-023): report "nothing to recover", exit 0, no changes.
- Orphaned state (FR-024): if the recorded branch no longer exists in the DB, clear the orphaned
  marker / log and exit without crashing.
- Idempotent (FR-022): a second run finds nothing to recover (status already `OPEN`); a run
  interrupted after rollback but before the status reset re-runs rollback (no-op) and completes the
  reset.

The recovery logic itself lives in the injectable `failure_recovery.py` component (per
`dev/rules/backend-component-design.md`); the CLI is a thin entry point that wires `db` and calls
the component, so the same logic is unit/component-testable without the CLI.

**Alternatives considered**: a GraphQL mutation for recovery (rejected — the spec explicitly wants
operator-driven, DB-access-gated recovery, not an API surface that could be hit during the failure
window); auto-recovery at startup (rejected — the spec deliberately shifted away from unattended
rollback to a loud, operator-confirmed flow).

## R7. Finding and resetting the associated proposed change.

**Decision**: The proposed change is not stored on the branch, but it is recoverable.

- `ProposedChangeState` (`backend/infrahub/proposed_change/constants.py`):
  `OPEN/MERGED/MERGING/CLOSED/CANCELED`. During a PC merge the state is set to `MERGING`
  (`graphql/mutations/proposed_change.py`) and to `MERGED` on success
  (`proposed_change/tasks.py:_proposed_change_transition_state`); on failure it is already reset
  toward `OPEN` in that task.
- Recovery finds the PC by querying `CoreProposedChange` nodes with `source_branch__value ==
  <failed branch>` and `state__value == "merging"` (the same node-manager filter the PC tasks use).
  A direct branch merge has no such PC — recovery proceeds without one (FR-020 / edge case).
- Reset reuses the existing transition: load via `registry.manager.get_one(kind=...,
  id=...)`, set `proposed_change.state.value = "open"`, `await proposed_change.save(...)`.

**Rationale**: avoids persisting a redundant `proposed_change_id` on the branch; the association is
derivable. Branch names are unique while branches exist, so they suffice to correlate.

**Alternatives considered**: persist `proposed_change_id` on the branch marker (rejected — it is
queryable from PC state; storing it duplicates a derivable fact).

## R8. Recovery rollback: a single range query over `>= merge_at` on the target branch.

**Question**: How should recovery reverse a failed merge, given that the `MERGING` window can hold
writes from the graph merge (`merge_at`), schema migrations (`merge_at`), and IPAM reconciliation
(a *later* timestamp)?

**Verified timestamp facts.** Every target-branch write during the merge window was traced:

| Step | Execution | Edge timestamp |
|---|---|---|
| Graph merge (the five bulk-merge queries) | sync, inside `merge_graph` | exactly `merge_at` |
| Schema migrations (`MigrationExecutor.WORKFLOW`) | sync, awaited; no child workflows / computed-attr triggers / other-branch writes | exactly `merge_at` |
| IPAM reconciliation | async `submit_workflow` | its **own later `Timestamp()`** |
| `mark_tracking_ids_merged`, `freeze_diffs`, changelog | — | metadata only |

**Decision**: recover with **one range-based rollback query** that, on the target (default) branch,
reopens every edge with `to >= merge_started_at`, deletes every edge with `from >= merge_started_at`,
cleans the resulting orphaned vertices, and restores vertex metadata (below). This reverses graph
merge, migrations, **and** IPAM in a single uniform pass — no per-step logic, no phase distinction,
no invariant-check branch, no IPAM backstop. Recovery needs only `(default branch,
merge_started_at)` — no `get_affected_node_uuids` list for either the structural revert or the
metadata restore.

**Why this is correct**: the write-block invariant *is* the safety proof. While a branch is
`MERGING` (or `MERGE_FAILED`), the default branch is closed to client writes (target gate, R5/R11),
new merges/rebases are blocked, and merges are serialized by the global lock. So from `merge_at`
until recovery, the writes to the default branch are this merge's own (graph + migrations + IPAM +
any follow-on it ran). Therefore "everything on the default branch with `from`/`to >= merge_at` is
the failed merge's work" — deleting/reopening all of it is correct. The range query and the
write-block are the same invariant from two ends; the range rollback *enforces* the block rather
than depending on fragile per-timestamp accounting.

**The block is immediately consistent (R11).** The write gates read the shared `merge:protected`
cache key, which the merging worker sets *before* any graph write — so once the merge begins writing,
every worker's gate sees the block at check time, with no propagation window. No stray client write
can interleave on the default branch after `merge_at`, so the range rollback never clobbers a
legitimate write: everything on the default branch with `from`/`to >= merge_at` is provably this
merge's own. The recurring scan and persisted status remain backstops (and keep the cache key
reconciled with the durable status).

**Query shape (index-aware).** Relationship indexes in Neo4j are **per-type**, so the current
label-less match (`()-[r {from:$at}]->()`) uses no index. The range query MUST therefore be written
as **per-edge-type subqueries** — one `MATCH ()-[r:<TYPE> {branch:$target}]->() WHERE r.from >=
$merge_at` (and the `to` variant) for each of the 8 `DatabaseEdgeType`s (`IS_PART_OF`,
`HAS_ATTRIBUTE`, `IS_RELATED`, `HAS_VALUE`, `IS_PROTECTED`, `HAS_OWNER`, `HAS_SOURCE`, `IS_RESERVED`)
— so the planner can use the relationship range indexes. Existing indexes (`core/graph/index.py`)
cover `branch` on 7 types and `from` on `HAS_ATTRIBUTE`/`HAS_VALUE` only; **`to` is unindexed
everywhere**. To make the range query performant we add RANGE indexes on `from` and `to` for all
relevant edge types. **Adding indexes is a database change (AGENTS.md "Ask First") and ships as a
new graph migration plus `IndexItem` entries** — flagged for approval before implementation.

**Vertex metadata restoration (`updated_at`/`updated_by`).** On the default branch these vertex
properties are the **source of truth** for metadata queries, ordering, and filtering
(`core/query/node.py` reads `n.updated_at`/`n.updated_by` directly for default/global branches), so
a stale value after recovery would change query *results*, not just display. They are restored from
the `previous_updated_at/by` snapshots — but the snapshot mechanism must cover everything the merge
window touches:

- The merge already snapshots (`DiffMergeMetadataQuery` is the sole writer today; the bulk-merge edge
  queries write no vertex metadata — confirmed).
- **Schema migrations MUST co-write `previous_*`** when they bump `updated_at/by` (the same `SET
  previous_* = current` the merge query does), so migration-collateral vertices have a snapshot.
- **IPAM no longer contributes collateral** because its submission is reordered after `MERGED`
  (R12, now mandatory): a failed merge — never `MERGED` — never ran IPAM.

The rollback restores (and may clear — clearing is optional, not load-bearing) `previous_*` for the
vertices **connected to the reverted edges where `updated_at >= merge_started_at`**. That filter is
exactly "vertices this merge bumped" because the global vertex property is only written by
default-branch ops and the merge is the sole default-branch writer in the write-blocked window. It
is **robust to partial failure**: a vertex is bumped to `merge_at` *only* by the metadata query (or a
migration), so if the merge crashed before reaching that step the vertex's `updated_at` is still its
correct pre-merge value (`< merge_at`) — the filter skips it, which is right, because there is nothing
to restore. This replaces the old `get_affected_node_uuids`-scoped restore (it covers a superset:
merge-diff **plus** migration collateral) at the same kind of cost — a property check on the
already-collected reverted-edge vertices, **no recompute and no edge re-aggregation**.

**Possible extra index**: depending on how the metadata phase is written, an index on `updated_at`
(on the `Node`/`Attribute`/`Relationship` vertex labels) may be needed to make the `updated_at >=
merge_started_at` selection efficient — folded into the same "Ask First" index change as the edge
`from`/`to` indexes.

**Orphan cleanup** keeps the current behavior (delete vertices left with no edges, batched
`IN TRANSACTIONS OF 500`). Note that shared/singleton vertices (`Boolean`, `AttributeValue`) stay
connected via edges on other branches, so they are not falsely orphaned by a target-branch-scoped
sweep — verify in tests.

**Alternatives considered**: keep the exact-`$at` match + reorder IPAM + a recovery-time invariant
check + an IPAM re-reconcile backstop (rejected — it is several coordinated mechanisms and a dual
recovery path to handle what the range query handles in one; the team chose the single query as
cleaner and as a direct enforcement of the write-block invariant); a `MERGING_GRAPH` sub-status to
distinguish graph-phase from post-graph failures (rejected — unnecessary for detection since the
lock covers the whole window, and unnecessary for rollback since the range query reverses the whole
window uniformly); **recomputing `updated_at`/`updated_by` from each vertex's surviving edges**
during rollback instead of using snapshots (rejected — on a large branch that is O(touched × fan-out):
per reverted vertex, re-aggregate all its edges to find the latest, which is exactly the cost the
merge avoids by stamping `previous_*`; the snapshot + migration-co-write approach keeps it to a
property read).

## R12. IPAM reconciliation ordering (MANDATORY reorder).

**Question**: Does IPAM ordering matter, given the range rollback (R8) reverses IPAM's edges anyway?

**Verified IPAM facts** (`core/ipam/reconciler.py`, `core/ipam/tasks.py`): reconciliation is
per-node (an `ipam_node_details` list), convergent for nodes that still exist but raises
`NodeNotFoundError` for a node that no longer exists, and is **async fire-and-forget, submitted
before `MERGED`**, with no workflow-level retry. Once enqueued it runs regardless of the merge's
fate — possibly concurrently with, or after, recovery. Critically, the IPAM reconciler does **not**
write `previous_*` snapshots, so the vertices it touches could not be metadata-restored on rollback
if IPAM ran for a failed merge.

**Decision** — the reorder is **mandatory**, for two reasons: defer the `IPAM_RECONCILIATION`
submission to *after* the `branch.status = MERGED` transition (compute `ipam_node_details` before the
diff freeze; submit after `MERGED`).

1. **Metadata restoration (the load-bearing reason).** Because IPAM doesn't snapshot `previous_*`,
   IPAM-collateral vertices would be unrecoverable for the `updated_at/by` restore (R8). Reordering
   so IPAM only runs after `MERGED` means a failed merge (never `MERGED`) never ran IPAM → there is
   no IPAM collateral to restore. This is what keeps the metadata restore correct without having to
   teach the IPAM reconciler to snapshot.
2. **Operational.** It also removes the race where an enqueued IPAM reconciliation runs concurrently
   with — or after — recovery (against pre-merge data, erroring on deleted nodes).

The range rollback still reverses any IPAM *edges* by timestamp, but with the reorder there are none
to reverse for a recovered merge. This is a small merge-ordering change, not a rollback code path.

**Open implementation checks for `/speckit-tasks`**: confirm `get_changed_ipam_node_details` can be
computed before the freeze and submitted after `MERGED`; audit for any other pre-`MERGED` follow-on
that mutates the default branch without snapshotting `previous_*` (schema migrations are handled by
co-writing `previous_*`, R8).

**Scope note**: the original spec text lists IPAM reconciliation as out of scope / "tracked
separately." Recovery now reverses *all* target-branch graph writes since `merge_at` (graph merge +
schema migrations), restores their `updated_at/by` via `previous_*` snapshots (migrations co-write
them), and relies on the mandatory reorder to keep IPAM out of the failed-merge window — so the
spec's scope statement is updated accordingly.

## R9. Logging and observability.

**Decision**: Structured log events (FR-026/027, SC-011), no new metrics this iteration:

- `merge.failure.detected` — when the detector flips a branch to `MERGE_FAILED`; fields: `branch`,
  `merge_started_at`, `proposed_change` (if any), `worker_id` (the dead holder), `source`
  (scan/startup/on-write/on-merge).
- `merge.recovery.started` / `merge.recovery.completed` / `merge.recovery.failed` — emitted by
  `infrahub recover`; fields: `branch`, `merge_started_at`, `proposed_change` (if any), outcome,
  `duration_ms`.

`(branch, merge_started_at)` correlates the detection and recovery of a single failure.

**Per `dev/rules/code-doc-style.md`**, source code must not reference FR-/spec IDs; the IDs above
live only in this planning doc.

## R10. Test strategy for process death.

**Decision** (constitution IV):

- **Unit**: the R2 predicate (healthy vs failed given status + lock token + active set) and the
  status-checker gates (write/merge/delete for each status), with no DB.
- **Component** (`backend/tests/component/core/merge/`): drive a real merge to completion, then
  hand-set the source branch to `MERGING` with a populated `merge_started_at` *as if* the marker
  were never cleared, run the detector → assert `MERGE_FAILED`; run the recovery component → assert
  the graph diff against the pre-merge snapshot is empty, branch is `OPEN`, PC (if present) is
  `OPEN`. A second variant raises inside one bulk-merge query mid-`merge_graph` and verifies
  recovery against the genuinely partial graph. Re-run recovery to assert idempotence (SC-010).
- **Functional** (`backend/tests/functional/`): end-to-end — block writes during a (paused) merge,
  flip to `MERGE_FAILED` via the detector with no restart and no writes (SC-004), assert the write
  rejection message names `infrahub recover`, run recovery, assert writes succeed and the branch
  re-merges (SC-009).
- **Integration_docker** (`backend/tests/integration_docker/`): launch the merge in a worker,
  `SIGKILL` it mid-merge, leave the stack idle (no writes, no restart), assert the recurring scan
  marks `MERGE_FAILED` within one interval (SC-003/004), then run `infrahub recover` and assert a
  clean re-merge.

**Alternatives considered**: unit-only (rejected — the failure mode is inherently cross-process and
the spec's deterministic-detection guarantee can only be proven against a real scheduler + real
worker death).

## R11. Cross-worker visibility of the write block: a shared cache key.

**Question**: A merge runs on one task worker; writes are served by other API workers. Branch
status lives in a **per-process in-memory cache** (`registry.branch`, a plain dict in
`backend/infrahub/core/registry.py`) with **no TTL**. So when the merge worker sets `MERGING`, or
the detector sets `MERGE_FAILED`, other workers keep serving the stale `OPEN` status and would not
block writes. How is the block made visible everywhere, immediately?

**Decision**: Use a **single shared cache key** that every worker reads on the write path —
immediately consistent, no per-worker propagation. The durable branch status in Neo4j remains the
source of truth; the cache key is a fast-read mirror.

```
key:   merge:protected
value: "{branch_name}::MERGING"   then   "{branch_name}::MERGE_FAILED"
```

- **Set / update / delete on transitions** (alongside the durable DB status): the merging worker
  sets the key on entering the merge (right after acquiring the global merge lock, *before* any
  graph write); the detector updates it to `MERGE_FAILED`; recovery (`→OPEN`) and success
  (`→MERGED`) delete it.
- **Write gates read the key** (one cache `GET`, sub-ms): the target gate (write to the default
  branch) blocks if the key is present; the source gate (write to branch X) blocks if the value's
  branch is X. The state in the value selects the message (`MERGING` → "retry shortly",
  `MERGE_FAILED` → "contact an administrator"). At most one merge runs at a time, so one key is
  enough.
- **No new broadcasts.** The `RefreshRegistryBranches` messages we previously proposed at the
  `OPEN→MERGING` / `MERGING→MERGE_FAILED` / `→OPEN` transitions are **dropped**. (The pre-existing
  completion broadcast via `BranchMergedEvent` is untouched.)

**Why this beats the broadcast**: the cache key is a single shared value read at check time, so the
gate is **immediately consistent** — there is no per-worker propagation window. This restores SC-001
to a literal "100%" and removes the range-rollback caveat (no stray write can interleave on the
default branch and later be clobbered by the range rollback, R8). The cost is one cache `GET` per
write; there is no existing per-write cache read, so this is a new but marginal round-trip (a single
`GET` before any transaction). The infrastructure is already there: workers coordinate through
shared cache keys today (active-worker set, primary election, schema hash — `services/component.py`)
and `service.cache` is reachable on the write path (`info.context.service.cache`,
`request.app.state.service.cache`).

**Durability / restart**: the cache is volatile (Redis persistence is external and not relied on).
The DB-persisted branch status is the durable source of truth — reloaded into the registry at
startup (`initialize_registry`). So the key is repopulated at startup from the DB, and the
**recurring scan (R4) reconciles the key against the DB status every minute**: DB `OPEN` but key
present → delete; DB `MERGE_FAILED` but key missing → set. This self-heals a missed transition or a
cache flush, with no broadcast.

**Cache-unavailable fail-mode**: if the `GET` errors, the gate **fails closed on the default
branch** (reject the write) and falls back to the in-memory `registry.branch` status for other
branches. A cache outage already halts merges (the merge lock lives in the same cache), so this is a
rare degraded mode; failing closed on the high-value default branch is the safe choice.

**Read-freshness for other consumers (accepted, minor)**: code that reads in-memory
`registry.branch` for *display* (e.g. a branch-status GraphQL query on a worker that has not merged)
may show a stale status until the recurring scan or startup reload refreshes that worker's registry
(~one scan interval). This affects observability only, not the write block (which reads the cache
key). Acceptable; the durable DB status is always correct and the scan converges the registries.

**Implementation notes for `/speckit-tasks`**: (a) set the key as the first step of the merge (after
the lock, before graph writes) so the window between lock-acquire and key-set is negligible; the
merge lock is an available secondary backstop for the target gate if even that window matters.
(b) The recurring scan owns key↔DB reconciliation. (c) `BranchStatusChecker` must be given a cache
handle (reachable in both the GraphQL middleware and REST handlers).

**Alternatives considered**: in-memory gates kept fresh by a `RefreshRegistryBranches` broadcast at
each transition (rejected — eventually consistent, leaves a propagation window that weakens SC-001
and the range rollback, and adds broadcast plumbing); a per-write DB Cypher lookup (rejected — a
graph query on every write, heavier than a cache `GET`); reusing the merge lock key alone (rejected —
its token is `timestamp::worker_id`, carries no branch name, and is swept after 15 min so it cannot
represent durable `MERGE_FAILED`).
