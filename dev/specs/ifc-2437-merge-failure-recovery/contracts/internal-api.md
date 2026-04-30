# Internal Contracts: Merge Failure Recovery

**Spec**: `../spec.md` | **Plan**: `../plan.md` | **Revised** for new bulk-merge architecture and review feedback

This feature exposes no new external (REST/GraphQL) endpoints. The contracts below are the internal Python interfaces added or modified.

## 1. BranchStatus and Branch model

**File**: `backend/infrahub/core/branch/enums.py`

Add two new transient statuses:

```python
class BranchStatus(InfrahubStringEnum):
    OPEN = "OPEN"
    NEED_REBASE = "NEED_REBASE"
    NEED_UPGRADE_REBASE = "NEED_UPGRADE_REBASE"
    DELETING = "DELETING"
    MERGING = "MERGING"          # NEW — set for the full _do_merge_branch window
                                  # (covers migrations and repo merges); blocks writes
                                  # but is NOT scanned by recovery
    MERGING_GRAPH = "MERGING_GRAPH"  # NEW — set only inside DiffMerger.merge_graph;
                                      # scanned by recovery on startup
    MERGED = "MERGED"
```

The two statuses serve distinct purposes:

| Status          | Window                                              | Scanned by recovery | Blocks writes |
|-----------------|-----------------------------------------------------|---------------------|---------------|
| `MERGING_GRAPH` | inside `DiffMerger.merge_graph` only                | yes                 | yes           |
| `MERGING`       | rest of `_do_merge_branch` (migrations, repo merges)| no                  | yes           |

Lifecycle: `OPEN → MERGING → MERGING_GRAPH → MERGING → MERGED` on success; `→ OPEN` on failure (after rollback or after migration error handling).

Recovery only acts on `MERGING_GRAPH` because only graph-merge crashes leave a partial graph state. A crash during `MERGING` (post-graph-merge work) is a different failure mode (out of scope per research R6) and `DiffMergeRollbackQuery` would do the wrong thing if applied there — it would un-merge correctly-merged data.

**File**: `backend/infrahub/core/branch/models.py`

One supplementary field on `Branch`:

```python
class Branch(StandardNode):
    # ... existing fields ...

    merge_started_at: Timestamp | None = None
```

**Persistence contract**: `merge_started_at` persists on the `:Branch` Neo4j node alongside existing branch attributes. It is set when entering `MERGING_GRAPH` and cleared when exiting it: `status == MERGING_GRAPH` iff `merge_started_at is not None`. (It is *not* set during the broader `MERGING` state — it is only meaningful for rollback, which is only relevant during `MERGING_GRAPH`.) Writes go through the helpers in §2.

The merge target is always `registry.default_branch` and is therefore not persisted on the marker. If a future feature lifts that restriction (non-default merge targets), this contract must add a `merge_target_branch` field.

## 2. BranchMerger marker helpers

**File**: `backend/infrahub/core/merge/branch_merger.py`

Two pairs of helpers, each governing one of the two transient statuses. `BranchMerger` owns these because setting/clearing them is a merge-orchestration concern. `Branch` is the data carrier; the merger drives the transitions.

```python
class BranchMerger:
    # ... existing methods ...

    async def _enter_merging(self) -> None:
        """Transition self.source_branch from OPEN to MERGING.

        Raises ValidationError if source_branch.status is not OPEN — a merge
        cannot begin on a branch that is already merging, merged, deleting,
        or needs rebase.
        """

    async def _exit_merging_to_open(self) -> None:
        """Restore self.source_branch.status from MERGING to OPEN.
        Used on failure paths. Idempotent: no-op if not in MERGING.

        Note: the success path is handled by existing code in branch/tasks.py
        which transitions the branch to MERGED at the end of _do_merge_branch.
        """

    async def _enter_merging_graph(self, at: Timestamp) -> None:
        """Transition self.source_branch from MERGING to MERGING_GRAPH and
        persist merge_started_at.

        Raises ValidationError if status is not MERGING.
        """

    async def _exit_merging_graph(self) -> None:
        """Transition self.source_branch from MERGING_GRAPH back to MERGING and
        clear merge_started_at. Idempotent: no-op if not in MERGING_GRAPH.
        """
```

`BranchMerger.merge` is modified to:

1. Call `await self._enter_merging()` at entry (after the early `default_branch` validation, before any other work).
2. Call `await self._enter_merging_graph(at=Timestamp(at))` immediately before `await self.diff_merger.merge_graph(...)`, inside the diff lock.
3. Call `await self._exit_merging_graph()` immediately after `merge_graph` returns successfully, *before* `merge_repositories()` runs.
4. On caught exception during graph merge: in-process rollback runs, then `_exit_merging_graph()`, then `_exit_merging_to_open()`.
5. After `merge_repositories()` returns: leave `MERGING` in place; existing `_do_merge_branch` code transitions to `MERGED`.
<!-- TODO I am not so sure about this, perhaps the failure states of the post-merge steps require some more thought -->
6. On exception during `merge_repositories()` (or any other post-graph-merge step inside `merge`): `_exit_merging_to_open()` runs.

Public signature of `BranchMerger.merge` is unchanged (`-> None` since the recent rewrite).

> **Note**: the broad `MERGING` state's transition to `MERGED` is owned by existing code in `branch/tasks.py:_do_merge_branch` (which already sets `BranchStatus.MERGED` after `BranchMerger.merge` and migrations succeed). That code does not need to change. It does, however, need an audit to confirm it transitions `MERGING → OPEN` (not just leaves the branch in `MERGING`) when its own post-merge work fails — see tasks.

## 3. DiffMerger rollback overload

**File**: `backend/infrahub/core/diff/merger/merger.py`

The existing `rollback` is extended to accept a pre-computed `node_uuids` so it can be called by recovery without relying on `self._affected_node_uuids`:

```python
async def rollback(
    self,
    *,
    at: Timestamp,
    node_uuids: list[str] | None = None,
) -> None:
    """Roll back a merge.

    If node_uuids is None, falls back to self._affected_node_uuids (in-process path).
    Recovery callers pass an explicit node_uuids list obtained from
    DiffRepository.get_affected_node_uuids(...), so rollback works after a
    process restart with no in-memory state.

    Idempotent. Safe to re-run after a partial rollback.
    """
```

The rollback Cypher (`DiffMergeRollbackQuery`) is unchanged — it already operates on `from=$at` / `to=$at` globally on the target branch, so completeness depends only on `$at` being correct, which the persisted `merge_started_at` provides.

## 4. Recovery entry point

**New module**: `backend/infrahub/core/merge/recovery.py`

```python
async def recover_partial_merges(*, db: InfrahubDatabase) -> RecoveryReport:
    """Scan all branches for status=MERGING_GRAPH and roll back any partial
    graph merges.

    The scan deliberately ignores status=MERGING. A crash during MERGING means
    the graph merge succeeded but post-graph-merge work (migrations, repo
    merges) failed — that is not a partial graph merge and DiffMergeRollbackQuery
    must NOT be applied. Operator intervention or a separate recovery flow
    handles MERGING-state crashes (out of scope for this feature; see research
    R6).

    For each detected branch (status=MERGING_GRAPH):
      1. Try to acquire recovery.merge.{branch.name} lock; skip if held by
         another worker.
        #  TODO it would be cleaner to move the rollback logic to its own component: DiffMergerRollbackHandler, or something
      2. Build a DiffMerger from source_branch and
         target_branch = registry.default_branch.
      3. Call DiffRepository.get_affected_node_uuids(...) using
         BranchTrackingId(name=branch.name) to obtain the UUID list.
      4. Call DiffMerger.rollback(at=branch.merge_started_at, node_uuids=...).
      5. Call BranchMerger._exit_merging_graph() and then
         _exit_merging_to_open() to restore status=OPEN and clear
         merge_started_at.
      6. Emit structured log events (see §7).

    Raises:
      RecoveryFailedError: if any branch's rollback fails. Lifespan startup MUST
        treat this as fatal.
    """


@dataclass(frozen=True)
class RecoveryReport:
    detected: list[str]   # branch names with MERGING_GRAPH status
    recovered: list[str]  # branch names successfully rolled back
    skipped: list[str]    # branch names another worker is handling
    failed: list[str]     # branch names whose rollback raised
```

**Caller**: `backend/infrahub/core/initialization.py` — invoked after `initialize_registry()` and before `validate_graph_version()`.

Note: step 5 reuses `BranchMerger._exit_merging_graph` and `_exit_merging_to_open` rather than duplicating the transition logic; recovery instantiates a `BranchMerger` (or extracts the helpers to module-level functions) so the same code path that the in-process merge uses also clears recovered markers.

## 5. Write-block via existing BranchStatusChecker

**File**: `backend/infrahub/branch/status_checker.py`

The existing `BranchStatusChecker` already gates writes on `BranchStatus.MERGED` and `NEED_REBASE`. Extend it for `MERGING`:

```python
class BranchStatusChecker:
    # ... existing methods ...

    def check_merging_status(self, branch: Branch) -> None:
        """Raise BranchStatusError if:
          - branch.status is MERGING or MERGING_GRAPH (this branch is the
            source of an in-flight merge, in either the broad or narrow
            window), OR
          - branch is the default branch and any other branch has
            status=MERGING or MERGING_GRAPH (this branch is the implicit
            merge target).
        """

    def check(self, branch: Branch) -> None:
        self.check_needs_rebase_status(branch)
        self.check_merge_status(branch)
        self.check_merging_status(branch)   # NEW
```

Both `MERGING` and `MERGING_GRAPH` block writes — the entire merge window is read-only on source and target. This satisfies FR-003. It is the same pattern the codebase already uses for read-only branches; no new helper or chokepoint is introduced.

The "any other branch has status=MERGING/MERGING_GRAPH" check (relevant only when the branch under check is the default branch) is implemented as a Cypher lookup against `:Branch` nodes — not an in-memory scan of `registry.branch` — so the gate is correct even if the local registry is stale relative to another worker that just transitioned a branch.

`BranchStatusError` (existing) is the raised exception — no new error type for this case.

## 6. New errors

Added to `backend/infrahub/exceptions.py`:

- `RecoveryFailedError`: raised by `recover_partial_merges` to abort lifespan startup. No GraphQL/REST exposure (recovery runs before the API serves traffic).

No `BranchWriteBlockedError` is needed — the existing `BranchStatusError` covers it.

## 7. Logging events

| Event | Where | Fields |
|-------|-------|--------|
| `merge.graph.start` | `BranchMerger._enter_merging_graph` | `branch`, `target`, `started_at` |
| `merge.graph.complete` | `BranchMerger._exit_merging_graph` (success path) | `branch`, `started_at`, `duration_ms` |
| `merge.recovery.detected` | `recover_partial_merges` | `branch`, `started_at`, `worker_id` |
| `merge.recovery.rollback_started` | `recover_partial_merges` | `branch`, `started_at` |
| `merge.recovery.rollback_complete` | `recover_partial_merges` | `branch`, `started_at`, `duration_ms` |
| `merge.recovery.rollback_failed` | `recover_partial_merges` | `branch`, `started_at`, `error` |

`(branch, started_at)` correlates the lifecycle events for a given attempt — sufficient now that `merge_attempt_id` is dropped (branch names are unique while branches exist; `started_at` distinguishes consecutive attempts on the same branch).

## 8. Dependencies on the new merge architecture

The recovery design relies on the following properties of the post-rewrite merge code, all confirmed by inspection:

- All five bulk-merge queries (`BulkMergeNodeExistenceQuery`, `BulkMergeRelationshipEdgesQuery`, `BulkMergeCardinalityOneResolutionQuery`, `BulkMergeAttributePropertyEdgesQuery`, `BulkMergeRelationshipPropertyEdgesQuery`) write only to `branch=$target_branch` and stamp every created/closed edge with the same `$at`.
- `DiffRepository.get_affected_node_uuids(source_branch, target_branch, at, tracking_id)` is a stateless query against the diff graph — works post-restart.
- `DiffMergeRollbackQuery` deletes edges with `from=$at, branch=$target_branch` globally and reopens edges with `to=$at, branch=$target_branch` globally; metadata vertex restoration is the only step scoped to a UUID list.

If any of those properties change in future merge-architecture work, this design must be re-evaluated. Add a CODEOWNERS / review checklist note in `dev/knowledge/backend/` to flag this dependency.

## 9. Tasks

The detailed task breakdown for implementing these contracts is generated by the `/speckit-tasks` command and lives at `dev/specs/ifc-2437-merge-failure-recovery/tasks.md` after that step runs. It does not exist yet at planning time.
