# Branch Status Enforcement

> Part of: `dev/knowledge/backend/` | Related: [architecture.md](architecture.md), [mutations.md](mutations.md)

How Infrahub enforces read-only constraints on branches based on their lifecycle status.

## BranchStatus Enum

`backend/infrahub/core/branch/enums.py`

| Value | Meaning | Mutations allowed |
|-------|---------|-------------------|
| `OPEN` | Active, writable | All |
| `NEED_REBASE` | Behind main; must rebase before changes | `BranchRebase`, `BranchDelete`, `BranchCreate`, `ProposedChangeCreate` |
| `NEED_UPGRADE_REBASE` | Schema version behind | `BranchDelete` |
| `DELETING` | Deletion in progress (internal) | None |
| `MERGING` | Merge in progress; branch and default branch write-blocked | `BranchCreate`, `BranchDelete` (of uninvolved branches) |
| `MERGE_FAILED` | A merge died (worker killed mid-merge); branch and default branch stay write-blocked until recovery | `BranchCreate`, `BranchDelete` (of uninvolved branches) |
| `MERGED` | Successfully merged; permanently read-only | `BranchDelete` only |

`MERGED` is terminal — there is no transition back to `OPEN`. `MERGING` is transient: it becomes `MERGED` on success, reverts to `OPEN` if the merge rolls back, or is flipped to `MERGE_FAILED` if the merge worker dies. `MERGE_FAILED` is cleared only by recovery (it returns the branch to `OPEN`).

### Failed merge detection

`backend/infrahub/core/merge/failure_identifier.py`

A merge holds the global `all_branches` merge lock for its whole `MERGING` window; the lock token encodes the holder's `worker_id`. When the holding worker dies, the lock stays held by a `worker_id` that is no longer in the active-worker set. `MergeFailureIdentifier.scan` flips such a branch `MERGING → MERGE_FAILED` (after a configurable grace period, `INFRAHUB_MERGE_FAILURE_GRACE_PERIOD_SECONDS`, that absorbs a transient heartbeat blip) and updates the `merge:protected` key to `"{branch}::MERGE_FAILED"`. It runs from the recurring `MERGE_WATCHER` workflow (one-minute cron, single-flighted), from a check at worker startup, and the recurring scan also reconciles the cache key against the durable branch status so protection self-heals after a restart or cache flush. A healthy in-progress merge (lock held by a live worker) is never flagged.

## BranchStatusChecker

`backend/infrahub/branch/status_checker.py`

A single class that centralises the status checks. Use this instead of checking `branch.status` inline.

```python
from infrahub.branch.status_checker import BranchStatusChecker

checker = BranchStatusChecker(db=db, merge_write_blocker=merge_write_blocker)
checker.check_merge_status(branch)        # raises BranchAlreadyMergedError if MERGED
checker.check_needs_rebase_status(branch) # raises BranchNeedsRebaseError if NEED_REBASE
await checker.check_merging_status(branch) # raises MergeInProgressError if blocked by a merge
await checker.check(branch)               # runs all three checks
```

Call `check()` when all statuses must be blocked (e.g., REST endpoints). Call individual methods when one status needs a carve-out (e.g., ProposedChangeCreate is allowed on NEED_REBASE but not MERGED).

## Write protection during merge

`backend/infrahub/core/merge/write_blocker.py`

While a merge runs, writes are blocked on two branches: the **source branch** (it is heading to `MERGED`) and the **default branch** (the merge target — the block is transient and lifts when the merge completes). Other branches stay writable.

The gate is driven by `MergeWriteBlocker`, which manages the shared `merge:protected` cache key with value `"{branch}::{state}"` (`MergeProtectionState.MERGING` or `MERGE_FAILED`). The merge flow in `backend/infrahub/core/branch/tasks.py` sets the key before any graph write and deletes it when the merge completes or rolls back. Every worker sees the same state with a single cache lookup per top-level mutation.

`check_merging_status()` reads the key and raises when the write target is the merging branch or the default branch. The key's state decides which error: a `MERGING` key raises the transient, retryable `MergeInProgressError` (code `MERGE_IN_PROGRESS`), while a `MERGE_FAILED` key raises the durable `MergeRecoveryRequiredError` (code `MERGE_RECOVERY_REQUIRED`, HTTP 423) whose message directs an administrator to run `infrahub recover`. `MergeRecoveryRequiredError` is a sibling of `MergeInProgressError`, not a subclass, so the error-catalogue resolver cannot collapse it onto the retryable code. If the cache is unreachable, it falls back to the durable branch status in the database (`_check_merging_status_from_db`), so a cache outage only blocks writes when a merge is genuinely in progress or failed.


## Enforcement Points

### 1. GraphQL Middleware (catch-all)

`backend/infrahub/graphql/middleware.py`

The primary gate. Intercepts every incoming mutation before it reaches the resolver.

```python
ALLOWED_MUTATIONS_ON_NEED_REBASE_BRANCH = ["BranchRebase", "BranchDelete", "BranchCreate", "ProposedChangeCreate"]
ALLOWED_MUTATIONS_ON_MERGED_BRANCH = ["BranchDelete"]
ALLOWED_MUTATIONS_DURING_MERGE = ["BranchCreate", "BranchDelete"]
```

`raise_on_mutation_for_branch_status` checks the allowlists on every top-level mutation field (the merge-protection cache key is read once per mutation, not once per resolved field). Add new mutations to the appropriate allowlist if they must be permitted on restricted branches. `BranchDelete` is allowed during a merge but verifies itself that it is not deleting the merging branch.

### 2. Per-Mutation Guards (defence-in-depth)

Some mutations need explicit status checks beyond the middleware for richer error messages or REST-path coverage:

| File | Mutation | Check |
|------|----------|-------|
| `graphql/mutations/branch.py` | `BranchMerge` | Rejects `MERGED` source; rejects new merges/rebases while any merge is in progress |
| `graphql/mutations/branch.py` | `BranchDelete` | Rejects deleting a `MERGE_FAILED` branch until recovery, enforced against the branch's durable status in the database so it holds regardless of which branch the request targets and even after the volatile write-protection cache key has been dropped; also rejects deleting the branch currently being merged |
| `graphql/mutations/proposed_change.py` | `ProposedChangeCreate` | Rejects `MERGED` source branch |

### 3. REST API Endpoints

`backend/infrahub/api/schema.py` and `backend/infrahub/api/artifact.py` call `BranchStatusChecker().check(branch)` and raise `ValidationError` (HTTP 422) for both `MERGED` and `NEED_REBASE` branches.

### 4. Permission System

`backend/infrahub/permissions/report.py` — `get_permission_report()` returns `DENY` for `create`, `update`, and `delete` actions when `branch.status` is `MERGED` or `NEED_REBASE`. This propagates the constraint to the UI via the permissions API so action buttons are disabled before the user attempts the mutation.

Exception: Branch delete is handled by the middleware allowlist, not by the permission system, so the permission report does not auto-deny delete on Branch objects.

## Status Transition in merge_branch()

`backend/infrahub/core/branch/tasks.py`

Setting `MERGED` is the **final** step of the merge flow — only after all other operations succeed (graph merge, repository merge, schema updates, migrations, diff tracking). If any earlier step fails, the branch remains `OPEN`.

After setting `MERGED`, the flow triggers `BRANCH_CANCEL_PROPOSED_CHANGES` to cancel any open proposed changes that reference the merged branch as their source.

## Adding a New Status Check

If a new endpoint or mutation must respect branch status:

1. Import `BranchStatusChecker` and call `check()` or a specific method.
2. If it's a GraphQL mutation that should be allowed on a restricted branch, add it to the appropriate `ALLOWED_MUTATIONS_*` constant in `middleware.py`.
3. Add a component test in `backend/tests/component/branch/test_status_checker.py` and a functional test for the specific endpoint (see `backend/tests/functional/merge/test_merge_in_progress_block.py`).

## See Also

- [architecture.md](architecture.md) — Overall backend structure
- [mutations.md](mutations.md) — GraphQL mutation dispatch flow
- [testing.md](testing.md) — Test infrastructure patterns
