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
  reopen edges closed at/after the merge start and delete edges created at/after it. The rollback
  takes the operation's timestamps. Both
  passes cover two branches (`core/query/rollback.py`, `_rollback_branches`): the target branch,
  where the window follows the scope (with `SINCE_TIMESTAMP`, it starts at the earliest of the
  timestamps), and the global branch, where an edge matches only when its timestamp is *exactly* one
  of them. A global edge stamped at one of the operation's timestamps was written by this operation,
  but any other global timestamp came from an unrelated write on some other branch and has to
  survive — the global branch is written by every branch, so a range there would over-revert. Each
  pass runs as its own statement — chaining them into one statement stacks planner Eager buffers and
  can exhaust the database's transaction memory pool on large rollbacks — and each is a single
  label-less pass over those branches' edges: the `from`/`to` range predicates cannot use the
  per-type relationship indexes, so type-scoped statements would only multiply the full passes. Each
  pass also cleans up after its own edges — deleting newly orphaned vertices in the same batch as
  the edge deletions that orphaned them, and restoring `previous_updated_at`/`previous_updated_by`
  no later than the edge reversal it belongs to (the delete pass restores in a transactional block
  that commits entirely before the first edge deletion). That ordering is what makes an interrupted
  rollback resumable: cleanup driven by ids collected in the recovering process would be lost with
  it, leaving orphans and stale metadata that a re-run could no longer find (the already reversed
  edges no longer match the window).

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

3. **Every merge-window write is stamped with one of the merge's step timestamps, and lands on
   the target branch or the global branch.** The merge passes one timestamp today. The bulk
   graph-merge queries write only to `branch = $target_branch` and stamp every edge with the same
   merge timestamp `$at`. What writes outside the target branch is branch-agnostic retirement, which
   closes global-branch edges — also at the merge `$at`. It reaches the window two ways: the merge's
   own re-evaluation for the nodes whose deletion it carried over
   (`DiffMerger._retire_agnostic_fields_of_deleted_nodes`), and any agnostic-field removal migration
   the merge carries (`AttributeRemoveQuery`, `node_relationship_remove`), which runs at the merge
   `$at` like every other merge-window migration. The merge's start timestamp is persisted on the
   branch as `merge_started_at` at the `MERGING` transition. Because all writes carry the merge's
   timestamp, a range query keyed on `merge_started_at` over the target branch, plus an
   exact-timestamp query over the global branch, reverses exactly the merge's edges.

4. **Only the graph merge and schema migrations write to the default branch during the window.** Both
   run at the merge `$at`. IPAM reconciliation is deliberately submitted *after* the `MERGED`
   transition (`core/merge/post_merge.py`), so it never runs for a merge that failed before `MERGED` and
   never leaves partial IPAM state for recovery to reverse. Repository (git) merges are also deferred
   past `MERGED`.

5. **Vertex metadata carries a restorable previous value.** The rollback restores
   `updated_at`/`updated_by` from `previous_updated_at`/`previous_updated_by` on every endpoint
   vertex whose `updated_at` equals any of the operation's timestamps — not
   the whole window, and not varying with the scope. A vertex stamped without a snapshot was new to
   the branch, so restoring its NULL snapshot correctly resets its metadata to unset. The exact
   match also keeps the restore idempotent when every writer of the operation received the
   operation's earlier timestamps: the restored value is then the one from before the operation,
   which is not one of the timestamps, so a later pass or a re-run cannot null what an earlier one
   put back. When a writer did not receive them, a restored value can be one of the timestamps and a
   later match nulls the metadata (see the re-evaluation bullet on a step that misses the earlier
   timestamps). The rollback's `ats` must include every timestamp that the operation's writers
   received in `operation_ats`: rolling back only some of them restores a vertex to its value from
   before the whole operation while the edges of the earlier steps remain. The diff-merge write path
   co-writes those `previous_*` fields (`core/diff/query/merge.py`, `DiffMergeMetadataQuery`), and
   the schema-migration queries that bump vertex metadata do the same (e.g.
   `core/migrations/schema/attribute_kind_update.py`, `core/migrations/query/attribute_add.py`,
   `node_duplicate.py`, `node_remove.py`).

   A migration writer saves the previous value only when the vertex's `updated_at` is unset or is
   not one of the operation's timestamps (`stamp_vertex_metadata` in
   `core/query/vertex_metadata.py`). The operation's timestamps are the query's `operation_ats` (a
   `Query` argument that schema migrations fill from `MigrationInput.operation_ats`), and the stamp
   helper always adds the write's own `at`. A vertex changed by several steps keeps the value from
   before the operation when each step's `MigrationInput.operation_ats` holds the earlier steps'
   timestamps. The schema migration flow (`core/migrations/schema/tasks.py`) does not pass them, so
   each schema load's migrations know only their own timestamp, which covers an operation stamped at
   one timestamp. This is what lets the metadata restore cover both merge-diff and migration
   collateral without enumerating which step touched which node. The number pool writers that a
   NumberPool attribute-add migration runs after its queries (`core/query/resource_manager.py`)
   stamp with only their own `at`, not `MigrationInput.operation_ats`.

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
- A step stamps vertex metadata at a merge timestamp without receiving the earlier steps'
  timestamps in `operation_ats` — the vertex saves the earlier step's stamp as its previous value.
  When the rollback is given both timestamps, each edge row runs its own restore, so the restore
  matches the vertex again after it restored the earlier step's stamp. That repeat comes from
  another edge of the same vertex, in the same batch or a later one, or from the other pass. The
  metadata ends up unset when more than one edge reversal reaches the vertex, and with the earlier
  step's stamp when only one does. Neither is the value from before the operation.
  `core/migrations/schema/tasks.py` builds `MigrationInput` without `operation_ats`, so its
  migrations see only their own `at`.
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
| `core/query/vertex_metadata.py` | `stamp_vertex_metadata` — the Cypher that stamps vertex metadata and keeps the value from before the operation as the previous one |
| `core/diff/query/merge.py` | `DiffMergeMetadataQuery` — co-writes `previous_*` for the merge diff |
| `core/merge/orchestrator.py` | `BranchMergeOrchestrator` — publishes the write protection, sets `merge_started_at` at `MERGING`, lifts the protection at `MERGED` |
| `core/merge/post_merge.py` | `PostMergeDispatcher` — submits the repository merges and the IPAM reconciliation after `MERGED` |
| `tasks/merge_watcher.py` | The recurring detection cron |
| `cli/recover.py` | The `infrahub recover merge` operator command |

## See Also

- [Branch Status](branch-status.md) — the `BranchStatus` lifecycle and the write gate
- [Coalesced Recompute on Merge and Rebase](merge-recompute.md) — the post-`MERGED` recompute path
