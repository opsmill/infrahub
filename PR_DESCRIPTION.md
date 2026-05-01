# Why

1. It was possible for a merge operation to fail in such a way that the merge changes had already been applied and were not rolled back. This PR adds greater rollback coverage to the merge logic.
2. Both SchemaUpdateCoordinator and DiffMerger had rollback logic, but they were slightly different. The rollback logic is now consolidated in a single query.
3. `DiffMerger.merge_graph()` advances the source branch's `branched_from` to `merge_at - 1µs` on success. When a downstream step in the wider merge flow then failed, the advance was never undone — making the next merge attempt's diff window exclude the branch's pre-`merge_at` changes. The retry would then "succeed" while silently merging nothing, and any schema migrations would fail with confusing errors (`Unable to find the attribute …`). Surfaced via manual testing.

**Goal:** any unexpected failure between the start of `_do_merge_branch` and the `MERGED` status save should leave the graph and registry as they were before the merge attempt. The branch should never be left in a half-merged state silently looking like `OPEN`.

**Non-goals:**
- Does not change the rebase flow at `tasks.py:rebase_branch` (same shape, same gap, deferred).
- Does not add any method for recovering from a failure during a rollback. This would probably require restoring from a backup or some sort of manual cypher intervention

Closes #9115

## What changed

**Behavioral changes**

- New `BranchStatus.MERGING`. A branch is set to `MERGING` for the duration of `_do_merge_branch`; transitions to `MERGED` on full success, back to `OPEN` if rollback succeeds, or stays at `MERGING` if rollback itself fails (signals "needs human intervention"). Mutations, rebases, re-merges, and proposed-change creation are blocked against a `MERGING` branch with the same semantics as `MERGED`.
- A failed merge now restores the destination branch's graph and registry, regardless of exactly where the failure occurs. Failures in `load_schema_from_db`, `calculate_migrations`, and `coordinator.execute()` are all wrapped.
- A failed merge now also restores the source branch's `branched_from` to its pre-merge value, so a retry sees the same diff window the first attempt did.
- `SchemaUpdateCoordinator.execute()` accepts `manage_rollback: bool = True`. The merge call site passes `False` so the outer wrapper is the sole rollback authority. All other call sites are unchanged.

**Implementation notes**

- `DiffMergeRollbackQuery` and `RollbackQuery` are consolidated into a single `RollbackQuery`. It now accepts an optional `node_uuids` list to restore  `updated_at`/`updated_by` metadata for Node, Attribute, and Relationship vertices using `previous_updated_at/by`. It always resets `to_user_id` along with `to`, and always deletes orphan vertices. All write subqueries use `CALL { ... } IN TRANSACTIONS`.
- New private helper `_rollback_merge` in `tasks.py` runs three steps: `merger.rollback()`, registry restore, then a single `branch.save()` that flips status back to `OPEN` and restores `branched_from`. Each step is independently `try/except`-wrapped; the helper does not raise. If rollback fails, the branch is left at `MERGING`. Ideally this would be reorganized to be more SOLID, but that would be a bigger change and this fix is for a specific bug.
- `_do_merge_branch` captures `pre_merge_branched_from = branch.branched_from` before the merge starts and threads it through to `_rollback_merge`. The advance itself remains inside `DiffMerger.merge_graph`. Moving it to the success path of `_do_merge_branch` would arguably be cleaner — `branched_from` and `status=MERGED` are paired "this merge committed" facts — but that's a wider refactor (other direct callers of `merge_graph` would have to change). Capture + restore on the rollback path is the smaller, more targeted fix for the bug at hand.

**What stayed the same**

- API contract for `/schema/load` is unchanged (`manage_rollback` defaults to `True`).
- Rebase flow in `tasks.py` is unchanged.
- `BranchMerger.merge()` and its inner rollback are unchanged.
- Schema-only rollback path (`/schema/load`, CLI init) keeps `IN TRANSACTIONS` batching; behavior is identical except that `to_user_id` is now reset alongside `to` (a strictly more-correct fix).

### Suggested review order

1. `backend/infrahub/core/query/rollback.py` — the consolidated query.
2. `backend/infrahub/core/branch/tasks.py` — `_rollback_merge` and the restructured `_do_merge_branch`.
3. `backend/infrahub/core/schema/update_coordinator.py` — `manage_rollback` plumbing.
4. `backend/infrahub/core/branch/enums.py` and the audit changes (`status_checker.py`, `permissions/report.py`, GraphQL mutations).
5. Tests last.

## How to review

**Focus areas**

- The order of operations in `_rollback_merge`: DB rollback first, then registry restore, then the final `branch.save()` that resets `status` and `branched_from` together.
- The decision to keep the `branched_from` advance in `DiffMerger.merge_graph` (versus moving it to the success path of `_do_merge_branch`). Both options are correct; the move would tie the advance to the success path more directly, at the cost of a wider refactor of `merge_graph`'s direct callers. Worth a second opinion on whether the larger change is preferable.
- The `manage_rollback=False` path in `SchemaUpdateCoordinator.execute()` confirm it propagates the original exception (or `MigrationError` from `error_msgs`) without invoking `_handle_failure_and_rollback`.
- The `BaseException` (not `Exception`) catch in `_do_merge_branch` so cancellation also triggers cleanup.

## How to test

I did manual testing using a local Infrahub instance. I inserted an error into the merge branch workflow; verified all changes were rolled back and branch was in the correct state; removed the error; ran the merge again; verified that it succeeded and merged branch was updated correctly. The retry-after-rollback scenario surfaced the `branched_from` bug noted in **Why** above; the fix is covered by an extension to `test_merge_branch_rollback` that asserts both `status` and `branched_from` are restored after a failed merge.

```bash
# Targeted component / integration tests for rollback query and merge flow:
uv run pytest -x backend/tests/component/core/diff/query/test_rollback.py
uv run pytest -x backend/tests/component/core/diff/test_diff_merger.py
uv run pytest -x backend/tests/component/core/diff/test_diff_and_merge.py
uv run pytest -x backend/tests/component/core/schema_manager/test_schema_rollback.py
uv run pytest -x backend/tests/integration/diff/test_merge_rollback.py

# Unit tests for the BranchStatus.MERGING audit:
uv run pytest backend/tests/unit/core/branch/test_merged_status.py
```

Manual: trigger a merge through the UI on a branch with schema changes, confirm the success path is unchanged. To exercise rollback, the existing `BrokenBranchMerger` pattern in `test_merge_rollback.py` injects a `ValueError` after `merge_graph` returns; the branch returns to `OPEN` and `main` data is restored.

## Impact & rollout

- **Backward compatibility:** `BranchStatus` enum gains `MERGING`. Any consumer that exhaustively switches on `BranchStatus` (clients, dashboards, reports) needs a case for it. `is_terminal` does not include `MERGING`. The new `manage_rollback` parameter on `SchemaUpdateCoordinator.execute()` is keyword-only with a default that preserves existing behavior, so all current call sites are unaffected.
- **Performance:** Adds one extra `Branch.save()` at the start of every merge (for the `MERGING` write) and one at the end of the rollback path. Negligible. The consolidated `RollbackQuery` does the same DB work as the two queries it replaces, plus orphan vertex cleanup that the merge-rollback path was missing.
- **Config / env changes:** None.
- **Deployment notes:** Safe to deploy. No data migration needed. Branches currently at `OPEN` continue to behave as before; the new `MERGING` state only appears for newly initiated merges.

## Checklist

- [x] Tests added/updated
- [x] [Changelog entry](../dev/guidelines/changelog.md) added (`changelog/9115.fixed.md`)
- [ ] External docs updated (if user-facing or ops-facing change)
- [ ] Internal .md docs updated (internal knowledge and AI code tools knowledge)
- [x] I have reviewed AI generated content
