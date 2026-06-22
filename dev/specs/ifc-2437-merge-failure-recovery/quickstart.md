# Quickstart: Merge Failure Recovery

A verification walkthrough — what an operator or developer can do to confirm the feature works
end-to-end. The implementation task breakdown is produced by `/speckit-tasks` into `tasks.md`.

## Prerequisites

- Local Infrahub stack up (`uv run invoke dev.start` or equivalent), including the task worker(s)
  that run Prefect flows, so the `merge-watcher` recurring deployment is active.
- A non-default branch with at least one node-level change ready to merge.

## Scenario 1: Normal merge (regression check)

1. Merge the branch into the default branch from the UI or CLI.
2. Confirm the merge completes successfully.
3. Inspect the source branch in Neo4j:

   ```cypher
   MATCH (b:Branch {name: "<source>"}) RETURN b.status, b.merge_started_at
   ```

   `status` MUST be `"MERGED"` (or the branch deleted, if `delete_branch_after_merge` is on);
   `merge_started_at` MUST still be populated (the merge's start time) — it is written when the
   branch enters `MERGING` and deliberately left in place afterward, to be overwritten by the next
   merge.
4. While the merge is in flight (use a paused/long merge if needed), a write to the **default**
   branch MUST be rejected with the *transient* "merge in progress, retry shortly" message; the
   same write MUST succeed once the merge completes.

## Scenario 2: Write protection during a healthy merge (US1)

1. Begin a merge and hold it inside the graph merge (debug pause / large change).
2. While `status = MERGING`:
   - Write to the **source** branch via GraphQL → rejected (`BranchStatusError`).
   - Write to the **default** (target) branch → rejected with the transient retry message.
   - Write to an **unrelated** branch B → succeeds.
3. Release the pause; the merge completes; writes to the default branch succeed again, confirming
   the block lifts automatically.

## Scenario 3: Deterministic detection while idle (US2, SC-003/004/006)

1. Trigger a merge in a task worker and `SIGKILL` that worker mid-merge (before the `MERGED`
   transition). The source branch is left at `status = MERGING` with `merge_started_at` populated.
2. **Do not** restart anything and **do not** issue any writes. Leave the stack idle.
3. Within the grace period plus one scan interval (≈ grace period + 1 minute), the recurring
   `merge-watcher` flow MUST flip the branch:

   ```cypher
   MATCH (b:Branch {name: "<source>"}) RETURN b.status, b.merge_started_at
   ```

   `status` MUST be `"MERGE_FAILED"`; `merge_started_at` MUST still be populated. (Before the flip,
   the default branch is already write-protected because the branch is `MERGING`.)
4. A `merge.failure.detected` structured log entry MUST be emitted with the branch name and
   `merge_started_at` (SC-011).
5. Negative control A — healthy slow merge: repeat steps 1-3 but keep the merge worker **alive** and
   still holding the merge lock. The branch MUST remain `MERGING` and MUST NOT be marked
   `MERGE_FAILED` (SC-006).
6. Negative control B — grace period: kill the worker but check **before** the grace period elapses.
   The branch MUST still be `MERGING` (not yet `MERGE_FAILED`), confirming a transient blip would not
   prematurely flip a merge.

## Scenario 4: Protection persists after a failure (US2, SC-005)

1. With a branch in `MERGE_FAILED` (from Scenario 3):
   - Write to the **default** branch → rejected with a message naming `infrahub recover` and
     "contact an administrator" (distinct from the transient retry message).
   - Write to the **failed source** branch → rejected with the same recovery message.
   - Write to an **unrelated** branch B → succeeds.
   - Attempt a new merge/rebase (including a proposed-change merge) → blocked.
   - Attempt to **delete** the failed branch → rejected (FR-014, SC-007).
2. Restart the API and task workers. Re-run the writes from step 1 — the rejections MUST persist
   (protection is driven by the persisted `MERGE_FAILED` status, not in-memory state). The startup
   detection MUST also (re)confirm the failed state immediately on boot.

## Scenario 5: Recovery via `infrahub recover` (US3, SC-008/009/010)

1. With a branch in `MERGE_FAILED`, run (against the database, as an administrator):

   ```bash
   infrahub recover
   ```

2. The command MUST auto-detect the failure and print the branch name, the persisted
   `merge_started_at`, and the associated proposed change (if any), then prompt for confirmation.
3. Answer **no** → the command exits with no data changes (verify status still `MERGE_FAILED`).
4. Run again and confirm (or run `infrahub recover --yes`). The command MUST:
   - roll back the partial graph merge,
   - reset the source branch to `OPEN`, leaving `merge_started_at` in place as the record of the
     failed merge (it is overwritten by the next merge, never cleared),
   - reset any associated proposed change to `OPEN`,
   - emit `merge.recovery.started` and `merge.recovery.completed` logs.
5. Verify the source-branch graph state equals its pre-merge snapshot (graph diff is empty),
   `status = "OPEN"`, `merge_started_at` still populated (left in place), and the proposed change
   (if any) is `OPEN`.
6. Writes to the default branch MUST succeed again, and the branch MUST be re-mergeable — re-run the
   merge and confirm success (SC-009).
7. Run `infrahub recover` a second time → it reports "nothing to recover" and exits without changes
   (idempotence, SC-010).

## Scenario 6: schema-changing merge — range rollback + metadata restore (SC-008)

1. Prepare a branch with a **schema change whose migration touches nodes beyond the branch's own
   diff** (e.g. adds an attribute with a default that backfills across all nodes of a kind). Record
   the pre-merge `updated_at`/`updated_by` of one such collateral node.
2. Force a failed merge after the migration has run (so collateral nodes were bumped to `merge_at`)
   but before the merge completed — branch left `MERGING` → detected `MERGE_FAILED`.
3. Run `infrahub recover`. The single range rollback MUST reverse all default-branch edges with
   `from`/`to >= merge_started_at` (graph merge + migration edges) **and** restore
   `updated_at`/`updated_by` for the touched nodes — including the **collateral** node from step 1 —
   to their pre-merge values.
4. Verify: the default branch's graph state equals its pre-merge snapshot (graph diff empty); the
   collateral node's `updated_at`/`updated_by` match the values recorded in step 1; the branch is
   `OPEN`; the proposed change (if any) is `OPEN`. Re-merge MUST succeed (SC-008/009).
5. **Completeness checks**: after recovery, query the default branch for any edge with
   `from`/`to >= merge_started_at` (there MUST be none) and for any node with
   `updated_at >= merge_started_at` among the touched set (there MUST be none).
6. **IPAM reorder check**: for a branch whose changes affect IPAM entities, force a failed merge and
   confirm **no** IPAM reconciliation ran for it (IPAM is submitted only after `MERGED`, which a
   failed merge never reaches) — so there is no IPAM-derived state on the default branch to recover.

## Scenario 7: Edge cases

- **No failure present**: with all branches healthy, `infrahub recover` reports nothing to recover
  and exits 0 (FR-023).
- **Direct branch merge (no proposed change)**: produce a failed merge from a branch merged
  directly (not via a proposed change); `infrahub recover` resets the branch only and does not
  assume a proposed change exists (FR-020).
- **Orphaned marker**: delete the `MERGE_FAILED` branch directly in the database, then run
  `infrahub recover` — it MUST clear the orphaned state and log it without crashing (FR-024).
- **Interrupted recovery**: kill `infrahub recover` after the rollback but before the status reset,
  then re-run it — the end state MUST be identical (branch `OPEN`, PC `OPEN`), with no
  double-deletion (FR-022).
