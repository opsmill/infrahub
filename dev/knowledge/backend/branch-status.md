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
| `MERGED` | Successfully merged; permanently read-only | `BranchDelete` only |

`MERGED` is terminal — there is no transition back to `OPEN`.

## BranchStatusChecker

`backend/infrahub/branch/status_checker.py`

A single class that centralises both status checks. Use this instead of checking `branch.status` inline.

```python
from infrahub.branch.status_checker import BranchStatusChecker

checker = BranchStatusChecker()
checker.check_merge_status(branch)        # raises BranchAlreadyMergedError if MERGED
checker.check_needs_rebase_status(branch) # raises BranchNeedsRebaseError if NEED_REBASE
checker.check(branch)                     # runs both checks
```

Call `check()` when both statuses must be blocked (e.g., REST endpoints). Call individual methods when one status needs a carve-out (e.g., ProposedChangeCreate is allowed on NEED_REBASE but not MERGED).

## Enforcement Points

### 1. GraphQL Middleware (catch-all)

`backend/infrahub/graphql/middleware.py`

The primary gate. Intercepts every incoming mutation before it reaches the resolver.

```python
ALLOWED_MUTATIONS_ON_NEED_REBASE_BRANCH = ["BranchRebase", "BranchDelete", "BranchCreate", "ProposedChangeCreate"]
ALLOWED_MUTATIONS_ON_MERGED_BRANCH = ["BranchDelete"]
```

`raise_on_mutation_for_branch_status` checks both allowlists on every mutation call. Add new mutations to the appropriate allowlist if they must be permitted on restricted branches.

### 2. Per-Mutation Guards (defence-in-depth)

Some mutations need explicit status checks beyond the middleware for richer error messages or REST-path coverage:

| File | Mutation | Check |
|------|----------|-------|
| `graphql/mutations/branch.py` | `BranchMerge` | Rejects `MERGED` source |
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
2. If it's a GraphQL mutation that should be allowed on a restricted branch, add it to the appropriate `ALLOWED_MUTATIONS_ON_*` constant in `middleware.py`.
3. Add a unit test in `backend/tests/unit/branch/test_status_checker.py` and a functional or component test for the specific endpoint.

## See Also

- [architecture.md](architecture.md) — Overall backend structure
- [mutations.md](mutations.md) — GraphQL mutation dispatch flow
- [testing.md](testing.md) — Test infrastructure patterns
