# Internal Contracts: Merge Failure Recovery

**Spec**: `../spec.md` | **Plan**: `../plan.md` | **Research**: `../research.md` | **Date**: 2026-06-04

This feature exposes **no new external REST/GraphQL endpoint**. The only client-visible change is a
new value in the auto-generated `BranchStatus` GraphQL enum. The contracts below are the internal
Python interfaces added or modified.

## 1. BranchStatus and Branch model

**File**: `backend/infrahub/core/branch/enums.py`

Add one durable status (do **not** add it to `TERMINAL_BRANCH_STATUSES`):

```python
class BranchStatus(InfrahubStringEnum):
    OPEN = "OPEN"
    NEED_REBASE = "NEED_REBASE"
    NEED_UPGRADE_REBASE = "NEED_UPGRADE_REBASE"
    DELETING = "DELETING"
    MERGING = "MERGING"
    MERGE_FAILED = "MERGE_FAILED"   # NEW — set by the detector; cleared only by recovery
    MERGED = "MERGED"
```

**File**: `python_sdk/infrahub_sdk/branch.py` (submodule) — mirror the value into the SDK enum so
clients can read and reason about it.

**File**: `backend/infrahub/core/branch/models.py`

```python
class Branch(StandardNode):
    # ... existing fields ...
    merge_started_at: Optional[str] = None   # ISO timestamp string; normalized by a field_validator
```

> **Type note:** stored as `Optional[str]`, not `Timestamp | None`. A `Timestamp` field cannot
> serialize through `StandardNode` (pydantic rejects it without `arbitrary_types_allowed`, and
> `to_db()` fails on `ujson.dumps`), so this mirrors the existing `branched_from` string pattern with
> a `field_validator` that normalizes a `Timestamp`/`str` to an ISO string. Callers assign
> `merge_started_at = merge_at.to_string()`.

**Persistence contract**: `merge_started_at` persists on the `:Branch` node via the existing
`StandardNode.save()` path. It is **(over)written when entering `MERGING`** and then **left in
place** — it records when the most recent merge started. It is **not** cleared on `MERGED`/`OPEN`:
nothing keys off its presence (detection reads it only when `status == MERGING`, recovery only when
`MERGE_FAILED`, and the write block is the cache key), so a residual value on an `OPEN`/`MERGED`
branch is inert and is overwritten by the next merge. The merge target is always
`registry.default_branch` and is not persisted.

## 2. Merge orchestration changes (persist the timestamp)

**File**: `backend/infrahub/core/branch/tasks.py`

Minimal edits to the existing flow — no signature changes:

- `_do_merge_branch`, at the `OPEN → MERGING` transition (currently line 396-397): also set
  `branch.merge_started_at = merge_at` before `branch.save(...)`. (`merge_at` already exists at
  line 376.) This is the **only** write to `merge_started_at` — it is not cleared on `MERGED`,
  `OPEN`, or recovery (it is overwritten by the next merge); see the persistence contract in §1.
- **Set the `merge:protected` cache key** on the `OPEN → MERGING` transition (value
  `"{branch}::MERGING"`), as the first step of the merge — right after acquiring the global merge
  lock and before any graph write — and **delete it** at the `MERGED` transition and in
  `_rollback_merge`. This is the immediately-consistent signal every worker reads on the write path
  (research R11). No `RefreshRegistryBranches` broadcast is added at the merge-status transitions.
- **Reorder post-graph follow-on after the point of no return — MANDATORY** (research R12): the
  `IPAM_RECONCILIATION` submission (currently lines 444-454, *before* `MERGED`) MUST move to *after*
  the `branch.status = MERGED` save (after line 479). Compute `ipam_node_details` where it is today
  (a read, before `freeze_diffs`) but defer the `submit_workflow(IPAM_RECONCILIATION, ...)` call
  until after `MERGED`. This is **load-bearing for the metadata restore (§3)**: the IPAM reconciler
  does not write `previous_*` snapshots, so if IPAM ran for a failed merge its collateral vertices
  could not be metadata-restored. Reordering guarantees a `MERGE_FAILED` branch (never `MERGED`)
  never ran IPAM — no IPAM collateral, and no IPAM run racing/following recovery. `/speckit-tasks`
  audits for any other pre-`MERGED` follow-on that writes the default branch without snapshotting
  `previous_*` (schema migrations are handled by co-writing `previous_*`, §3).
- **Reorder the repository (git) merge after `MERGED` — DONE (T005a)**: `merge_repositories()` was
  the only non-IPAM pre-`MERGED` follow-on that writes the default branch. It issues a
  `CoreRepositoryUpdate` through the SDK/GraphQL, which the target write-gate rejects during the
  protected window, so the merge self-blocked. It is moved out of `BranchMerger.merge()` to the
  post-`MERGED` section (best-effort, before `BRANCH_DELETE`). Same recovery benefit as the IPAM
  reorder: a `MERGE_FAILED` branch never ran the repository merge, so there is no repository-node
  collateral on the default branch and the write-block invariant holds with no GraphQL write inside the
  window. All other in-window default-branch writes (bulk graph merge, schema migrations, branch/PC
  saves) are direct Cypher and bypass the gate. See `../repo-merge-write-block-plan.md`.

> The global `MergeLocker` lock at line 297 is already held for the entire `_do_merge_branch` call,
> so its `timestamp::worker_id` token is present throughout the `MERGING` window and is the signal
> the detector reads. No lock change is required.

## 3. Range-based rollback query

**Files**: `backend/infrahub/core/query/rollback.py`, `backend/infrahub/core/diff/merger/merger.py`,
`backend/infrahub/core/graph/index.py`.

Recovery reverses a failed merge with a **single range query** keyed on `merge_started_at`
(research R8). Every step is **scoped to the default branch** — `WHERE r.branch = <default branch>`
(the only merge target; `merge` writes nowhere else). The source branch and all other branches are
untouched. The query:

1. **Reopens** every default-branch edge with `to >= $merge_at` (set `to = NULL`, `to_user_id = NULL`).
2. **Deletes** every default-branch edge with `from >= $merge_at`.
3. **Deletes orphaned vertices** left with no remaining edges (batched `IN TRANSACTIONS OF 500`).
4. **Restores `previous_updated_at/by`** for the vertices connected to the reverted edges **where
   `updated_at >= $merge_at`** (optionally clearing `previous_*` after — not required, see below).

This reverses graph merge **and** schema migrations uniformly (IPAM never ran for a failed merge —
§2 reorder). **No `get_affected_node_uuids` list is needed for either the structural revert or the
metadata restore** — steps 1-3 are scoped by `branch` + timestamp; step 4 is scoped to the
already-collected reverted-edge vertices filtered by `updated_at >= $merge_at`. So recovery needs
only `(default branch, merge_started_at)` and works post-restart with no in-memory state.

The step-4 filter (`updated_at >= $merge_at`) selects exactly the vertices this merge bumped: the
global vertex `updated_at` is written only by default-branch ops, and the merge is the sole
default-branch writer in the write-blocked window. It is **robust to partial failure** — a vertex's
`updated_at` is bumped only by `DiffMergeMetadataQuery` (or a migration), which run *after* the
bulk-merge edge queries; so if the merge crashed before that step the vertex still holds its correct
pre-merge `updated_at` (`< merge_at`), the filter skips it, and nothing needs restoring. For this to
cover migration collateral, **schema migration queries MUST co-write `previous_*`** when they bump
`updated_at/by` (the same `SET previous_* = current` the merge query does). Clearing `previous_*` on
restore is **optional**: a re-run is excluded by the same timestamp filter (the restored `updated_at`
is `< merge_at`) and the next merge overwrites `previous_*` anyway.

**Correctness rests on the write-block invariant**: while the branch is `MERGING`/`MERGE_FAILED`, the
default branch is closed to client writes via the target gate (§5, R11), so every target-branch edge
with `from`/`to >= merge_at` belongs to this merge. The block is **immediately consistent** — the gate
reads the shared `merge:protected` cache key, set before any graph write — so no stray write can
interleave on the default branch after `merge_at`. The range rollback enforces the invariant rather
than depending on per-timestamp accounting.

**Index-aware shape (required)**: Neo4j relationship indexes are per-type, so steps 1-2 MUST be
written as **per-edge-type subqueries** — one `MATCH ()-[r:<TYPE> {branch:$target_branch}]->()
WHERE r.from >= $merge_at` (and the `to` variant) for each `DatabaseEdgeType` (`IS_PART_OF`,
`HAS_ATTRIBUTE`, `IS_RELATED`, `HAS_VALUE`, `IS_PROTECTED`, `HAS_OWNER`, `HAS_SOURCE`,
`IS_RESERVED`) — not a single label-less match (which uses no index).

**New indexes (Ask First)**: today `core/graph/index.py` indexes `branch` on 7 edge types and `from`
on `HAS_ATTRIBUTE`/`HAS_VALUE` only; `to` is unindexed everywhere. Add RANGE indexes on `from` and
`to` for the relevant edge types. **Additionally, an index on `updated_at`** (a node index on the
`Node`/`Attribute`/`Relationship` vertex labels) **may be needed** for the step-4 metadata selection,
depending on how it is written. All of this is a **database index change** (AGENTS.md "Ask First")
and ships as a new graph migration plus `IndexItem` entries — requires approval before
implementation.

**Migration co-write (`previous_*`)**: schema migration queries that bump vertex `updated_at/by`
(e.g. `core/migrations/schema/attribute_kind_update.py`, `core/migrations/query/attribute_add.py`,
`node_duplicate.py`, `node_remove.py`, …) MUST first `SET previous_updated_at = updated_at,
previous_updated_by = updated_by` — mirroring `DiffMergeMetadataQuery` — so migration-collateral
vertices can be metadata-restored on recovery. `/speckit-tasks` enumerates the exact set.

**Range rollback vs the in-process rollback**: recovery uses this range query, which needs no
node-UUID list (so recovery does **not** call `get_affected_node_uuids`). The existing in-process
rollback (the merge's own caught-exception path, which runs *before* migrations and has its
in-memory `_affected_node_uuids` + snapshots) may keep its current UUID-scoped restore — it only has
to undo the graph merge, and migration collateral does not exist yet at that point. `/speckit-tasks`
decides whether to unify both paths on the range query. Idempotent — re-running after a partial
rollback is a no-op (no edges match `>= merge_at` once deleted/reopened; the `updated_at >= merge_at`
filter excludes already-restored vertices).

## 4. Detection + recovery component

**New file**: `backend/infrahub/core/merge/failure_recovery.py`

A DI component (constructor-injected collaborators) with two entry points:

```python
class MergeFailureRecovery:
    def __init__(
        self,
        db: InfrahubDatabase,
        diff_merger: DiffMerger,       # owns the range rollback query (no get_affected_node_uuids needed)
        cache: InfrahubCache,          # merge:protected key set/update/delete; read the lock-holder token
        component: InfrahubComponent,  # list_workers() -> active-worker set for the liveness predicate
        merge_locker: MergeLocker,     # read-side helper: current merge-lock holder worker_id (or None)
    ) -> None: ...

    async def detect_and_mark(self) -> str | None:
        """Evaluate the failed-merge predicate and, if matched, transition the
        branch MERGING -> MERGE_FAILED (preserving merge_started_at) and update
        the merge:protected cache key to '{branch}::MERGE_FAILED'.
        Idempotent. Returns the branch name marked failed, or None.

        Predicate: status == MERGING AND the MergeLocker 'all_branches' lock is
        PRESENT AND its token worker_id is not in the active-worker set AND
        (now - merge_started_at) > grace_period. The lock must be present (a dead
        worker cannot release it, so a real failure leaves it present); an ABSENT
        lock is not auto-flagged, because absence is ambiguous (a cache flush
        during a live merge would otherwise false-positive). A branch whose lock
        holder is active, or whose merge is younger than the grace period, is
        healthy in-progress and left untouched. The grace period (small,
        configurable, default ~2-3 min) absorbs a transient heartbeat-write blip.
        """

    async def recover(self, *, confirmed: bool) -> RecoveryReport:
        """Find the failed merge and (when confirmed) recover it.

        Detection covers BOTH (FR-016): (i) a branch recorded MERGE_FAILED, and
        (ii) a branch stuck in MERGING whose merge-lock holder is not a live
        worker (the ambiguous case detect_and_mark deliberately does not flag).
        The human confirmation is what makes acting on (ii) safe. Then:

          1. Run the range rollback (§3) over the default branch: reopen edges
             with to >= merge_started_at, delete edges with from >= merge_started_at,
             clean orphaned vertices, restore previous_* metadata for reverted-edge
             vertices where updated_at >= merge_started_at. Reverses graph merge
             and schema migrations (IPAM never ran — §2 reorder).
          2. Reset the source branch status to OPEN (merge_started_at is left as
             the record of the failed merge; it is overwritten by the next merge).
          3. Reset the associated proposed change (if any) to OPEN.
          4. Delete the merge:protected cache key so the write block lifts.

        No-op + report when nothing to recover. Idempotent. Clears an orphaned
        marker (branch removed out-of-band) without raising.
        """
```

```python
class RecoveryOutcome(Enum):
    NOTHING_TO_RECOVER = "nothing_to_recover"  # no failed merge found
    DECLINED = "declined"                      # failure found; operator answered no
    RECOVERED = "recovered"                    # rolled back + reset to OPEN
    ORPHANED_CLEARED = "orphaned_cleared"      # branch gone out-of-band; stale marker cleared
    FAILED = "failed"                          # rollback raised

@dataclass(frozen=True)
class RecoveryReport:
    outcome: RecoveryOutcome
    branch: str | None
    proposed_change: str | None
    merge_started_at: str | None
```

The `outcome` enum (not a free-text `note`) lets the CLI format its own human-readable message and
lets tests assert on a structured value; the remaining fields carry what to report (branch name, the
persisted merge timestamp, the associated proposed change if any).

The failed-merge **predicate** is a pure helper (unit-testable without DB), taking
`(status, lock_token: str | None, active_worker_ids: set[str], merge_started_at: Timestamp | None,
now: Timestamp, grace_period: Duration)` → `bool`. Both `detect_and_mark` and the on-write/on-merge
fast paths call it.

**Detection callers**:

- Recurring scan flow (new) — see §8.
- `backend/infrahub/core/initialization.py`, after `initialize_registry()` (runs on both API server
  and git-agent startup).
- Write gate (§5) when a default-branch write finds a branch in `MERGING`.
- Merge/rebase gate (§5) before starting a new operation.

**Recovery caller**: the `infrahub recover` CLI command (§7).

## 5. Write / merge / delete blocking via BranchStatusChecker

**File**: `backend/infrahub/branch/status_checker.py`

Extend the existing checker (which already raises on `MERGED`/`MERGING`/`NEED_REBASE`):

```python
class BranchStatusChecker:
    def __init__(self, db: InfrahubDatabase, merge_write_blocker: MergeWriteBlocker) -> None: ...   # db required, first
    # ... existing methods ...

    async def check_merging_status(self, branch: Branch) -> None:   # async: awaits the cache read
        """Read the shared merge:protected key (via MergeWriteBlocker) and raise if this branch is
        blocked by a merge:
          - key present and its branch == branch.name (source gate) -> branch-specific read-only
            message ("Branch '{name}' is being merged and is read-only…", mirroring MERGED), OR
          - branch is the default branch and the key is present (target gate) -> transient
            'merge in progress, retry shortly' (it becomes writable again after the merge).
        (MERGE_FAILED message — 'contact an administrator to run infrahub recover' — is added in PR-3.)
        On cache error: log the exception and fall back to the durable DB branch status
        (Branch.get_list(status=MERGING)) — the source of truth.
        """

    async def check(self, branch: Branch) -> None:
        self.check_needs_rebase_status(branch)
        self.check_merge_status(branch)
        await self.check_merging_status(branch)   # NEW (async)
```

**New `db` (required, first) + `MergeWriteBlocker` dependencies + async**: the gate reads the
`merge:protected` key through an injected `MergeWriteBlocker` (which owns the cache), and takes a
required `db` handle used by the cache-unreachable fallback; `check`/`check_merging_status` become
`async`. The call sites run in async contexts and have both handles — the GraphQL mutation middleware
(`info.context.active_service.cache`, `info.context.db`) and REST handlers
(`request.app.state.service.cache`, the `db` dependency) construct
`BranchStatusChecker(db=..., merge_write_blocker=MergeWriteBlocker(cache=...))` and `await` the check.
`check_merge_status` now raises only for `MERGED`; the `MERGING` block moved to `check_merging_status`
(key-driven, immediately consistent across workers).

- **FR-002 vs FR-009 messaging**: the messages MUST be distinct. The default branch during a healthy
  merge is transient/retry; the branch being merged is read-only ("is being merged…", like `MERGED`);
  `MERGE_FAILED` names `infrahub recover` and the administrator.
- **FR-012 fast path**: the gate decides from the `merge:protected` cache key value — its state
  (`MERGING` vs `MERGE_FAILED`) is already set by the detector, so the steady-state write path needs
  no lock inspection, just one cache `GET`.
- **FR-011b escalation (optional)**: when the key still says `MERGING` on a default-branch write, the
  gate MAY run the detector predicate (§4, lock + worker-set + grace) to escalate a dead merge to the
  `MERGE_FAILED` message and update the key immediately, rather than waiting for the next scan. The
  block itself does not depend on this — the key blocks the write either way.
- **Merge/rebase block (FR-004)**: the merge/rebase entry points reject when the key is present
  (any branch `MERGING`/`MERGE_FAILED`).
- **Cross-worker coherence (research R11)**: both gates read the **shared `merge:protected` cache
  key** — one cache `GET`, no per-write database read and no status broadcast. Because every worker
  reads the same shared value, the block is **immediately consistent** (no propagation window), so
  SC-001 is a literal 100% and the range rollback (§3) never clobbers an interleaved write. The
  durable DB status is the source of truth (reloaded at startup, reconciled by the recurring scan),
  so the key survives restarts/flush. `BranchStatusChecker` is therefore given a `MergeWriteBlocker`
  (owns the cache) plus a `db` handle (both reachable in the GraphQL middleware and REST handlers).
  Cache-error fail-mode: log and fall back to the durable DB branch status
  (`Branch.get_list(status=MERGING)`) — a cache outage blocks writes only when a merge is genuinely in
  progress, rather than freezing all default-branch writes.

**Delete prevention (FR-014) at the mutation gate, not in `Branch.delete()`**: the `MERGE_FAILED`
delete block lives where branch-status mutation gating already lives — the GraphQL branch-status
mutation middleware (`graphql/middleware.py`), which today *allows* certain mutations per status
(e.g. `BranchDelete` on a `MERGED` branch). `MERGE_FAILED` is granted **no** mutation exception —
including `BranchDelete` — so deletion is refused until recovery returns the branch to `OPEN`.
`Branch.delete()` stays a low-level operation with no new status logic. (Internal post-merge
auto-delete of a successfully `MERGED` branch is unaffected — it is never `MERGE_FAILED`.)

Existing write call sites funnel through `BranchStatusChecker.check` (GraphQL mutation middleware
`graphql/middleware.py`; REST `api/schema.py`, `api/artifact.py`). `/speckit-tasks` includes an
audit task to confirm no mutating path bypasses the checker.

## 6. Errors / messages

**File**: `backend/infrahub/exceptions.py`

- The `MERGING` (transient) and `MERGE_FAILED` (recovery) rejections both surface through
  `BranchStatusError`/`BranchAlreadyMergedError` with distinct messages. Add a dedicated message
  constant (or a thin `MergeFailedError(BranchStatusError)`) for the `MERGE_FAILED` case so the
  recovery instruction is consistent across GraphQL and REST. Messages MUST NOT leak internal
  details (constitution VI) — they name `infrahub recover` and "contact an administrator" only.

## 7. `infrahub recover` CLI command

**File**: `backend/infrahub/cli/recover.py` (new); registered in `backend/infrahub/cli/__init__.py`.

Mirrors the `reset-deployment-id` admin pattern in `backend/infrahub/cli/db.py`:

```python
@app.command(name="recover")
async def recover_cmd(
    ctx: typer.Context,
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip the confirmation prompt."),
    config_file: str = typer.Argument("infrahub.toml", envvar="INFRAHUB_CONFIG"),
) -> None:
    """Recover a failed branch merge: roll back the partial graph merge and reset
    the branch (and any associated proposed change) to OPEN."""
```

Flow: `config.load_and_exit(config_file)` → `context.init_db(retry=1)` →
`initialize_registry(db=db)` → build `MergeFailureRecovery` → `report = await recovery.recover(...)`
with confirmation via `typer.confirm(...)` unless `--yes`; print a `rich.Console` summary; close the
DB in `finally`. Auto-detect (FR-016), no-failure (FR-023), orphaned state (FR-024), and idempotence
(FR-022) are handled inside `recover()`. Decline path: report `confirmed=False`, exit without
changes (FR-016 acceptance #3).

## 8. Recurring detector workflow

**File**: `backend/infrahub/tasks/merge_watcher.py` (new) — the Prefect flow:

```python
@flow(name="merge-watcher", flow_run_name="Detect failed merges")
async def detect_failed_merges(service: InfrahubServices) -> None: ...
```

**File**: `backend/infrahub/workflows/catalogue.py` — add to the `WORKFLOWS` list:

```python
MERGE_WATCHER = WorkflowDefinition(
    name="merge-watcher",
    type=WorkflowType.INTERNAL,
    cron="* * * * *",
    module="infrahub.tasks.merge_watcher",
    function="detect_failed_merges",
    concurrency_limit=1,
    concurrency_limit_strategy=ConcurrencyLimitStrategy.CANCEL_NEW,
)
```

`setup_deployments()` (`backend/infrahub/workflows/initialization.py`) iterates `get_workflows()`
and creates the cron deployment automatically once `MERGE_WATCHER` is in `WORKFLOWS`. The flow calls
`MergeFailureRecovery.detect_and_mark()`. `concurrency_limit=1` + `CANCEL_NEW` single-flights it
across workers (same guarantee as `clean-up-deadlocks`).

## 9. Logging events

These are **structured log entries** (e.g. `structlog` / the standard logger), **not** message-bus
`InfrahubEvent`s. That distinction matters for recovery: `infrahub recover` runs standalone with only
a database connection — the message bus and task workers are typically not available to it — so the
`merge.recovery.*` observability MUST be plain structured logs the CLI writes directly, never bus
events it would have to publish. This satisfies the spec (FR-026/027, SC-011 require a "structured
log entry"). The detector runs inside a task worker and could *additionally* emit a bus event for
downstream automation, but that is out of scope here and recovery must not depend on it.

| Log event | Where | Fields |
|-------|-------|--------|
| `merge.failure.detected` | `MergeFailureRecovery.detect_and_mark` (task worker) | `branch`, `merge_started_at`, `proposed_change`, `worker_id`, `source` |
| `merge.recovery.started` | `MergeFailureRecovery.recover` (CLI) | `branch`, `merge_started_at`, `proposed_change` |
| `merge.recovery.completed` | `MergeFailureRecovery.recover` (CLI) | `branch`, `proposed_change`, `duration_ms` |
| `merge.recovery.failed` | `MergeFailureRecovery.recover` (CLI) | `branch`, `error` |

`(branch, merge_started_at)` correlates the detection and recovery of a single failure.

## 10. Dependencies on the merge architecture

Recovery relies on these confirmed properties of the current merge code; if any change in future
merge work, this design must be re-evaluated (add a note under `dev/knowledge/backend/`):

- The `MergeLocker` "all_branches" global lock is held for the entire `_do_merge_branch` window
  (`backend/infrahub/core/branch/tasks.py:297`), so its token is the failure signal for the whole
  `MERGING` state.
- All five bulk-merge queries write only to `branch=$target_branch` and stamp every edge with the
  same `$at`, and write **no** vertex `updated_at`/`previous_*` (confirmed) — only
  `DiffMergeMetadataQuery` does (`bulk_merge.py`, `diff/query/merge.py`). This is what makes the
  step-4 `updated_at >= merge_at` filter robust to partial failure.
- The default-branch write-block (shared `merge:protected` cache key read by every worker, §5/R11)
  means that from `merge_at` until recovery the target-branch writes are this merge's own — the
  invariant that makes the range rollback (delete/reopen everything `>= merge_at`) correct. The block
  is **immediately consistent** (one shared key, set before any graph write), so no stray write
  interleaves. The recurring scan reconciles the key with the durable DB status; the DB status is
  reloaded at startup.
- The merge window's default-branch writers are the graph merge and schema migrations (both at
  `$at`); IPAM is reordered after `MERGED` (§2) so it never runs for a failed merge. The range
  rollback reverses graph + migration edges by timestamp, and the metadata restore covers their
  vertices via `previous_*` (migrations co-write it, §3) — so recovery never enumerates which step
  wrote what, and needs no `get_affected_node_uuids` list.
- Repository (git) merges remain out of scope — they are not graph edges on the target branch and
  are not reversed by the rollback (research R8 scope note).

## 11. Tasks

The dependency-ordered task breakdown is generated by `/speckit-tasks` into
`dev/specs/ifc-2437-merge-failure-recovery/tasks.md`. It does not exist at planning time.
