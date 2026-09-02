# Merge Failure Recovery

> Part of: `dev/knowledge/backend/` | Related: [branch-status.md](branch-status.md), [merge-recompute.md](merge-recompute.md), [database-schema.md](database-schema.md)

A branch merge into the default branch runs as a single database-level operation. If the worker
running it dies mid-flight, the default branch is left partially merged and the branch stuck in
`MERGING`. Recovery detects that dead merge, reverses the partial write, and returns the system to a
writable state.

The load-bearing idea — and the reason this note exists — is that **recovery does not record what a
merge wrote**. It keeps no per-node undo log and enumerates no affected ids. Instead it reverses the
merge by reversing *every* default-branch write in a time window, trusting a set of invariants that
the merge architecture currently guarantees. Those invariants are what make a blind range revert
correct. If a future change to the merge path breaks one of them, recovery breaks silently — the
rollback would under- or over-revert with no error. **Re-evaluate this design whenever the merge
window's locking, write scoping, timestamping, or metadata handling changes.**

## The shape of recovery

- **Detection** (`core/merge/failure_identifier.py`, `MergeFailureIdentifier`): a branch still
  `MERGING` whose global merge lock is held by a worker that is no longer alive, past a grace period,
  is flipped to the durable `MERGE_FAILED` status and the write protection is held. Runs from a
  recurring cron (`tasks/merge_watcher.py`) and once at API-server startup (`server.py`).
- **Recovery** (`core/merge/failure_recoverer.py`, `MergeFailureRecoverer`, driven by the
  `infrahub recover merge` CLI in `cli/recover.py`): range-rollback the partial merge, reset any
  associated proposed change and then the branch to `OPEN`, release the stale merge lock, and lift
  the write protection. Idempotent.
- **Range rollback** (`core/rollback.py`, `GraphRollbacker` with `RollbackScope.SINCE_TIMESTAMP`):
  reopen edges closed at/after the merge start and delete edges created at/after it. Both passes
  cover two branches (`core/query/rollback.py`, `_rollback_branches`): the target branch, where the
  window follows the scope, and the global branch, where it is always the *exact* timestamp. A
  global edge stamped at the merge `$at` was written by this merge, but a later global timestamp
  came from an unrelated write on some other branch and has to survive — the global branch is
  written by every branch, so a range there would over-revert. Each pass runs as its own
  statement — chaining them into one statement stacks planner Eager buffers and can exhaust the
  database's transaction memory pool on large rollbacks — and each is a single label-less pass over
  those branches' edges: the `from`/`to` range predicates cannot use the per-type relationship
  indexes, so type-scoped statements would only multiply the full passes. Each pass also cleans up
  after its own edges — deleting newly orphaned vertices in the same batch as the edge deletions
  that orphaned them, and restoring
  `previous_updated_at`/`previous_updated_by` no later than the edge reversal it belongs to (the
  delete pass restores in a transactional block that commits entirely before the first edge
  deletion). That ordering is what makes an interrupted rollback resumable: cleanup driven by ids
  collected in the recovering process would be lost with it, leaving orphans and stale metadata
  that a re-run could no longer find (the already reversed edges no longer match the window).

## The invariants recovery depends on

1. **The global merge lock is held for the entire merge window.** The `MergeLocker` `all_branches`
   lock (`core/merge/merge_locker.py`, `MERGE_LOCK_KEY`) is acquired before any graph write and held
   until the merge finishes. A dead worker cannot release it, so a held lock whose token names a
   worker that is no longer active is the failure signal for the whole `MERGING` state. An *absent*
   lock is deliberately treated as ambiguous (a cache flush during a healthy merge looks the same)
   and is only recovered under `--force`.

2. **The default branch is write-blocked for the whole window.** From the `OPEN→MERGING` transition
   until recovery, every worker reads a shared `merge:protected` cache key
   (`core/merge/write_blocker.py`, `MergeWriteBlocker`) and rejects default-branch and source-branch
   writes. The key is set before the first graph write and is immediately consistent (one shared
   key), so no unrelated write interleaves into the window. This is the invariant that makes "revert
   everything at/after the merge start" correct: within that window, every default-branch write
   belongs to this merge. The recurring scan reconciles the volatile key against the durable branch
   status, which is reloaded at startup — so protection survives a restart or cache flush.

3. **Every merge-window write is timestamp-uniform, and lands on the target branch or the global
   branch.** The bulk graph-merge queries write only to `branch = $target_branch` and stamp every
   edge with the same merge timestamp `$at`. The one writer outside the target branch is
   branch-agnostic retirement (`DiffMerger._retire_agnostic_fields_of_deleted_nodes`), which closes
   global-branch edges for the nodes whose deletion this merge carried over — also at the merge
   `$at`. The merge's start timestamp is persisted on the branch as `merge_started_at` at the
   `MERGING` transition. Because all writes share one timestamp, a range query keyed on
   `merge_started_at` over the target branch, plus an exact-timestamp query over the global branch,
   reverses exactly the merge's edges.

4. **Only the graph merge and schema migrations write to the default branch during the window.** Both
   run at the merge `$at`. IPAM reconciliation is deliberately submitted *after* the `MERGED`
   transition (`core/branch/tasks.py`), so it never runs for a merge that failed before `MERGED` and
   never leaves partial IPAM state for recovery to reverse. Repository (git) merges are also deferred
   past `MERGED`.

5. **Vertex metadata carries a restorable previous value.** The rollback restores
   `updated_at`/`updated_by` from `previous_updated_at`/`previous_updated_by` on every endpoint
   vertex whose `updated_at` equals the operation's *exact* timestamp — not the whole window, and
   not varying with the scope. A vertex stamped without a snapshot was new to the branch, so
   restoring its NULL snapshot correctly resets its metadata to unset. The exact match is also what
   keeps the restore idempotent: a restored vertex no longer carries the timestamp, so a later pass
   or a re-run cannot null what an earlier one put back. The diff-merge write path co-writes those
   `previous_*` fields (`core/diff/query/merge.py`,
   `DiffMergeMetadataQuery`), and the schema-migration queries that bump vertex metadata do the
   same (e.g. `core/migrations/schema/attribute_kind_update.py`,
   `core/migrations/query/attribute_add.py`, `node_duplicate.py`, `node_remove.py`). This is what
   lets the metadata restore cover both merge-diff and migration collateral without enumerating
   which step touched which node.

6. **Repository (git) merges are out of scope.** They are not graph edges on the target branch, so the
   range rollback does not reverse them. Recovery restores the graph and node metadata only.

## Re-evaluate recovery if any of these change

- The merge lock stops being held for the whole window, or its token stops identifying the worker —
  detection's liveness signal breaks.
- A merge-window writer starts writing to the default branch at a timestamp other than the merge
  `$at`, or before the `merge:protected` key is set — the range revert would miss or over-reach.
- A merge-window writer starts writing to a branch other than the target or the global one, or
  stamps global-branch edges at anything other than the merge `$at` — the rollback covers only
  those two branches, and only the exact timestamp on the global one.
- Any pre-`MERGED` step (a new follow-on, or IPAM/repository sync moved back before `MERGED`) starts
  mutating default-branch graph state — recovery would leave it partially applied.
- A merge-window writer bumps vertex `updated_at`/`updated_by` to the merge `$at` without
  co-writing `previous_*` — the restore still fires on those vertices and writes whatever
  `previous_*` holds (unset, or a leftover snapshot from an older operation), silently corrupting
  their metadata instead of restoring it. Only a writer stamping a *different* timestamp is out of
  the restore's reach.
- The write block stops being immediately consistent (e.g. a per-worker cache instead of one shared
  key) — an unrelated write could interleave into the rollback window.

## Key Files

| File | What |
|------|------|
| `core/merge/failure_identifier.py` | `MergeFailureIdentifier`, `scan_for_failed_merges` — dead-merge detection + protection-key reconcile |
| `core/merge/failure_recoverer.py` | `MergeFailureRecoverer` — rollback, PC/branch reset, lock release, protection lift |
| `core/merge/write_blocker.py` | `MergeWriteBlocker`, `MergeProtectionState` — the shared `merge:protected` write block |
| `core/merge/merge_locker.py` | `MergeLocker`, `MERGE_LOCK_KEY`, `get_merge_lock_holder_worker_id` — the global merge lock and its holder |
| `core/rollback.py` | `GraphRollbacker` — orchestrates the per-phase range revert + metadata restore |
| `core/query/rollback.py` | per-phase rollback queries, `RollbackScope` |
| `core/diff/query/merge.py` | `DiffMergeMetadataQuery` — co-writes `previous_*` for the merge diff |
| `core/branch/tasks.py` | `_do_merge_branch` — sets `merge_started_at`/protection at `MERGING`, defers IPAM/repository past `MERGED` |
| `tasks/merge_watcher.py` | The recurring detection cron |
| `cli/recover.py` | The `infrahub recover merge` operator command |

## See Also

- [Branch Status](branch-status.md) — the `BranchStatus` lifecycle and the write gate
- [Coalesced Recompute on Merge and Rebase](merge-recompute.md) — the post-`MERGED` recompute path
