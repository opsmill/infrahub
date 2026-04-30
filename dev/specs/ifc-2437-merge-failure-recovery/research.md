# Phase 0 Research: Merge Failure Recovery

**Spec**: `spec.md` | **Date**: 2026-04-29 (revised after merge architecture rewrite on this branch)

This document resolves the open implementation questions that the spec deferred. Each section below states a question, a decision, the rationale, and alternatives considered.

> **Context note**: The merge code path on this branch was substantially rewritten — `DiffMerger.merge_graph` now executes a sequence of five bulk Cypher queries (each in its own retried transaction) plus a metadata batch update, and discovers affected node UUIDs by querying the diff graph rather than walking an in-memory `EnrichedDiffRoot`. The recovery design has been updated to take advantage of those properties.

## R1. How is the "merge in progress" marker persisted?

**Decision**: Add **two** new `BranchStatus` enum values plus one supplementary scalar field on the `Branch` Pydantic model:

- `BranchStatus.MERGING` — the broad transient state, covering the full `_do_merge_branch` window (graph merge → migrations → repo merges).
- `BranchStatus.MERGING_GRAPH` — the narrow transient state, set only inside `DiffMerger.merge_graph`.
- `merge_started_at: Timestamp | None` — the `at` Timestamp passed to `DiffMerger.merge_graph`. Set when transitioning to `MERGING_GRAPH`; cleared when transitioning out. The rollback Cypher is `MATCH (v)-[r {from: $at, branch: $target_branch}]-()` — without the original `at`, recovery cannot run rollback.

The merge target is always `registry.default_branch` (today's behavior), so the target name is not persisted; recovery resolves `$target_branch` via the registry.

The marker is set on the **source** branch only.

- `BranchMerger._enter_merging` transitions `OPEN → MERGING` at merge entry.
- `BranchMerger._enter_merging_graph(at)` transitions `MERGING → MERGING_GRAPH` and persists `merge_started_at` immediately before `merge_graph` runs.
- `_exit_merging_graph()` transitions back to `MERGING` and clears `merge_started_at` after `merge_graph` succeeds or after an in-process rollback.
- Existing `branch/tasks.py:_do_merge_branch` continues to transition to `MERGED` at the end of the successful flow. `_exit_merging_to_open()` is invoked on failure paths to restore `OPEN`.

**Rationale**:

- `BranchStatus` already has `DELETING` as a precedent for transient durable states. The two new statuses follow the same shape.
- **Two statuses, not one**: write-blocking and recovery have different windows. Recovery must only act on a partial graph merge (`MERGING_GRAPH`) — a crash during migrations leaves the graph correctly merged, and applying `DiffMergeRollbackQuery` would un-merge it. Write-blocking, however, must cover the full merge (any post-graph-merge mutation could corrupt migration state). A single status spanning the broad window would over-trigger recovery; a single status spanning the narrow window would under-trigger write-blocking. Two statuses resolve both cleanly.
- `merge_started_at` is mandatory because the rollback Cypher is keyed on it. It only needs to exist during `MERGING_GRAPH`.
- `merge_target_branch` is *not* persisted: today's merge code merges into the default branch only, and `registry.default_branch` is reliably available at recovery time. If a future feature lifts that restriction, this decision must be revisited.
- A separate `merge_attempt_id` is *not* needed: branch names are unique while branches exist, so they suffice as the recovery lock key. Log correlation uses `(branch_name, merge_started_at)`.

**Alternatives considered**:

- **`merge_in_progress: bool` separate from status.** Rejected — splits "is this branch writable?" across two fields and forces extra checks at every enforcement point.
- **Separate `:MergeAttempt` node related to `:Branch`.** Unjustified for two scalar fields; complicates the recovery scan.
- **External store like Redis.** Not durable enough for our needs; markers must survive any restart.

## R2. Where does the recovery scan run at startup?

**Decision**: In `backend/infrahub/core/initialization.py`, after `initialize_registry()` (which loads branches into `registry.branch`) and before `validate_graph_version()` and schema loading.

The step:

1. Queries Neo4j for all branches with `status = "MERGING_GRAPH"` (deliberately not `MERGING` — see R1).
2. For each, attempts to acquire a recovery lock (R4) and runs rollback (R3).
3. If rollback fails, logs at error level and **raises**, aborting lifespan startup so the API does not begin serving traffic (FR-007 / FR-012).

**Rationale**: lifespan startup naturally gates API readiness — FastAPI does not accept requests until the lifespan `yield` is reached. Placing the scan immediately after `initialize_registry()` reuses the just-loaded branch list and runs before any code that might assume a clean graph.

**Alternatives considered**: background task after startup (violates FR-007); recovery on next merge attempt (violates FR-007).

## R3. Can rollback run after a process restart with the new merge architecture?

**Decision**: Yes — and more cleanly than under the old architecture.

The new `merge_graph`:

- Runs five bulk merge queries (`BulkMergeNodeExistenceQuery`, `BulkMergeRelationshipEdgesQuery`, `BulkMergeCardinalityOneResolutionQuery`, `BulkMergeAttributePropertyEdgesQuery`, `BulkMergeRelationshipPropertyEdgesQuery`) — all writes use the same `$at` timestamp and all writes target `$target_branch` only.
- Queries `DiffRepository.get_affected_node_uuids(source_branch, target_branch, at, tracking_id)` to compute the affected UUID list. This call is **stateless** — it derives the list from the persisted diff graph, not from in-memory state.
- Runs `DiffMergeMetadataQuery` per batch of UUIDs.
- Updates `source_branch.branched_from`.

The existing `DiffMergeRollbackQuery`:

- Deletes every edge with `from=$at, branch=$target_branch` (line 224–227 of `merge.py`) — globally, not scoped to specific node UUIDs.
- Reopens every edge with `to=$at, branch=$target_branch` (line 217–220) — globally.
- Restores `previous_updated_at/by` on Node vertices in `$node_uuids` and on connected Attribute/Relationship vertices.

**Implication**: Recovery only needs `(source_branch, target_branch, merge_started_at, tracking_id)` — all of which the marker provides — to run rollback. We will:

1. Add a `DiffMerger.rollback(*, at, node_uuids=None)` overload (or a thin recovery helper) that, when `node_uuids` is None, fetches them via `get_affected_node_uuids` instead of relying on `self._affected_node_uuids`.
2. Recovery calls this with the marker's `merge_started_at`.

Idempotence: re-running rollback against an already-rolled-back state is safe — `OPTIONAL MATCH (v)-[r {from: $at}]-()` finds nothing and the `DELETE` is a no-op; `WHERE n.previous_updated_at IS NOT NULL` skips already-restored vertices.

**Why "more cleanly" than the old design**: under the previous code, rollback's edge cleanup was scoped via `_affected_node_uuids` populated incrementally during merge — losing that list (e.g., on restart) would have left rollback incomplete. The current rollback's edge sweep is keyed on `from/to=$at`, so completeness depends only on the timestamp, which is already persisted in the marker.

**Alternatives considered**:

- **Persist `affected_node_uuids` incrementally during the merge.** Now unnecessary — `get_affected_node_uuids` is a stateless query.
- **Replay the merge transaction log.** Neo4j does not expose this.

## R4. How are concurrent recovery attempts coordinated?

**Decision**: Use the existing `lock.registry` (Redis or NATS, depending on cache driver) with a lock key derived from the source branch name.

- Lock name: `recovery.merge.{source_branch_name}`.
- A worker that fails to acquire the lock skips the branch (and logs that another worker is handling it). The failing-to-acquire worker re-reads the branch status after a bounded wait — if no longer `MERGING`, the recovery is done; otherwise it exits the scan (no retry — the holder will either succeed and transition out of `MERGING`, or fail and the next startup will retry).

**Rationale**: reuses existing lock infrastructure. Branch names are unique while branches exist, so they are sufficient as the lock key — no separate `merge_attempt_id` is needed. If a branch were deleted and recreated (with the same name) between the failed merge and recovery, the recovery would still apply to the same logical entity, since it operates only on graph data tied to that name.

**Alternatives considered**: keying on a generated `merge_attempt_id` (rejected — adds a field whose only purpose is uniqueness already provided by the branch name); ad-hoc Cypher MERGE on a sentinel node (unfamiliar pattern); leader election (overkill for once-per-startup).

## R5. How are writes blocked on the source and target branches during a merge?

**Decision**: Extend the existing `BranchStatusChecker` (`backend/infrahub/branch/status_checker.py`) with a `check_merging_status` method, and have the existing `check()` method call it alongside the existing `check_merge_status` (gates `MERGED`) and `check_needs_rebase_status` (gates `NEED_REBASE`).

The new check fails if:

- The branch's `status` is `MERGING` or `MERGING_GRAPH` (it is the source of an active merge, in either the broad or narrow window), OR
- The branch is the default branch and any other branch has `status` in `(MERGING, MERGING_GRAPH)` (this branch is the implicit merge target — today's merge code merges into the default branch only).

Both statuses block writes; only `MERGING_GRAPH` triggers recovery. See R1 for the rationale on the split.

Existing callers of `BranchStatusChecker.check` automatically pick up the new gate without per-call changes. Any mutation paths that don't currently call `BranchStatusChecker.check` must be updated; the audit is part of the work generated by `/speckit-tasks`.

**Rationale**:

- `BranchStatusChecker` is the existing chokepoint for "is this branch writable?" gates. Extending it is the in-pattern fix.
- This is the same shape as the existing `DELETING` precedent: a transient status that gates writes.
- Removes the need for a separate `Branch.assert_writable` helper or a `BranchWriteBlockedError`. The existing `BranchStatusError` covers the failure case.

**Alternatives considered**:

- **A new `Branch.assert_writable()` helper.** Rejected on review feedback — duplicates `BranchStatusChecker`'s role.
- **A separate `merge_in_progress: bool` field instead of a status.** Rejected — splits "is this branch writable?" across two fields. See R1.
- **Cypher-level constraints.** Cannot easily express "writes forbidden during transient state."

<!-- TODO I think this requires some more thought -->
## R6. What about schema migrations and post-merge work?

**Decision**: Recovery is out of scope for them; write-blocking is in scope.

- Schema migrations run *after* `merge_graph` completes (in `_do_merge_branch`). A SIGKILL during `merge_graph` cannot leave migrations partially applied.
- **Recovery window = `MERGING_GRAPH` only**: the recovery scan ignores the broad `MERGING` status. Transition out of `MERGING_GRAPH` (back to `MERGING`) as soon as `merge_graph` returns successfully, *before* migrations run. If migrations subsequently fail, `SchemaUpdateCoordinator` has its own rollback path; we do not want this feature's recovery to undo a successfully-merged graph just because migrations crashed.
- **Write-block window = `MERGING` ∪ `MERGING_GRAPH`**: writes to source/target branches are blocked for the *full* `_do_merge_branch` window, not just for `merge_graph`. This closes the previous design's gap where post-graph-merge mutations to migrating branches were not rejected.
- Repository merges run after `merge_graph` returns — recovery does not cover them, but they are inside the broad `MERGING` window so writes are still blocked during them.

## R7. How do we test SIGKILL/process-death scenarios?

**Decision**: Two tests.

1. **Component test** (`backend/tests/component/core/merge/test_recovery.py`): does not actually kill a process. Calls `BranchMerger.merge` to completion, then *manually* sets the marker fields on the source branch *as if* the marker were never cleared, and runs the recovery entry point. Asserts the rollback completes idempotently. A second variant interrupts by raising mid-`merge_graph` (e.g., monkey-patching one of the bulk-merge queries to raise after committing) and verifies recovery against the partial state.
2. **Integration_docker test** (`backend/tests/integration_docker/test_merge_kill_recovery.py`): launches the merge in a worker process, sends `SIGKILL` mid-merge, restarts the API, and asserts the API comes up healthy and the source/target branches are consistent. Required by Constitution Principle IV for cross-process behavior.

**Alternatives considered**: unit-test only — rejected; the failure mode requires cross-process verification.

## R8. What logging and observability does recovery emit?

**Decision**: Structured logs at the following events:

- `merge.graph.start` — when the branch transitions to `MERGING_GRAPH`; fields: `branch`, `target`, `started_at`.
- `merge.graph.complete` — when the branch transitions back to `MERGING` after a successful graph merge; fields: `branch`, `started_at`, `duration_ms`.
- `merge.recovery.detected` — when the startup scan finds a lingering marker.
- `merge.recovery.rollback_started` / `merge.recovery.rollback_complete` / `merge.recovery.rollback_failed`.

No new metrics in this iteration.

**Rationale**: logs are sufficient for SC-006.

## R9. (New) Does the rollback fully undo all five bulk-merge stages if one of them was killed mid-execution?

**Decision**: Yes, because:

- All five bulk merges write to `$target_branch` only (never the source branch), confirmed by inspection of `bulk_merge.py`.
- All five share the same `$at` timestamp.
- Each bulk merge runs in its own `@retry_db_transaction` — a partially-executed bulk merge either commits its writes (visible to rollback) or rolls back the transaction (no writes to undo).
- The rollback's edge sweep (`from=$at` deletes; `to=$at` reopens) is global on the target branch, not scoped to specific UUIDs, so it cleans up regardless of which subset of bulk merges committed.

The vertex metadata restoration (the `$node_uuids` portion of rollback) is the only scoped step. Because `get_affected_node_uuids` queries the diff graph rather than the merge results, it returns the *intended* set of touched nodes — at worst over-broad, never under-broad. Restoring `previous_updated_at/by` on a vertex that was not actually updated is a no-op (the `WHERE previous_updated_at IS NOT NULL` guard skips it).

**Implication**: no checkpoint scheme is needed. Recovery is a single rollback call.

**Alternative considered**: wrap all five bulk merges in a single Neo4j transaction. Rejected — would require lifting transaction boundaries across many query objects, and the current per-query retry semantics would have to change. The rollback approach is strictly simpler.
