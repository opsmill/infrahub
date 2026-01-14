---
Title: Branch Freeze Feature
Author:
  - Wim Van Deun
Status: draft
JPD: [INFP-444](https://opsmill.atlassian.net/browse/INFP-444)
---
# Branch Freeze Feature

## Summary

After a branch is merged into the main branch (via proposed change or direct branch merge), the branch should become read-only. This prevents users from making additional changes to merged branches and attempting to merge them again, which can cause database corruption and relationship state issues.

## Problem Statement

Users can currently make changes to branches after they've been merged and attempt to merge them again. This causes:

- Database corruption with relationship state inconsistencies ([#7852](https://github.com/opsmill/infrahub/issues/7852))
- Confusing UX where merged branches appear modifiable
- Potential data integrity issues from double merges

## Solution Overview

Introduce a new `MERGED` branch status that:
- Is set atomically at the end of successful merge operations
- Blocks all data mutations on the branch
- Prevents creating new proposed changes with this branch as source
- Prevents re-merging the branch

## Backend

### Branch Status

Add new `MERGED` status to existing `BranchStatus` enum:

```python
# backend/infrahub/core/branch/enums.py
class BranchStatus(InfrahubStringEnum):
    OPEN = "OPEN"
    NEED_REBASE = "NEED_REBASE"
    NEED_UPGRADE_REBASE = "NEED_UPGRADE_REBASE"
    DELETING = "DELETING"
    MERGED = "MERGED"  # NEW
```

### Status Transition

The `MERGED` status should be set **only** after a successful merge completes. This is critical - if merge fails at any point, the branch must remain in its previous status.

**Order of operations in merge flow:**

1. Acquire locks
2. Validate conflicts resolved
3. Execute `merge_graph()` (with rollback on failure)
4. Merge repositories
5. Update schema if needed
6. Apply migrations
7. Mark diff tracking as merged
8. **Set branch status to MERGED** (final step)
9. Fire events and post-processing

If any step fails before step 8, the branch remains `OPEN` and can be modified/re-merged.

**Implementation location:** `backend/infrahub/core/branch/tasks.py` in `merge_branch()` flow:

```python
@flow(name="branch-merge", flow_run_name="Merge branch {branch} into main")
async def merge_branch(branch: str, context: InfrahubContext, proposed_change_id: str | None = None) -> None:
    # ... existing merge logic ...

    # After all merge operations succeed, set status to MERGED
    obj.status = BranchStatus.MERGED
    await obj.save(db=db, user_id=context.account.account_id)

    # ... fire events ...
```

### Mutation Blocking

Reuse the existing middleware pattern from `NEED_REBASE` status. The middleware at `backend/infrahub/graphql/middleware.py` already blocks mutations on `NEED_REBASE` branches - extend this for `MERGED`.

**Allowed mutations on MERGED branches:**

```python
ALLOWED_MUTATIONS_ON_MERGED_BRANCH = [
    "BranchDelete",  # Allow cleanup
    # Note: No BranchRebase, BranchMerge, or ProposedChangeCreate
]
```

**Blocked operations:**

- All data mutations (create, update, delete nodes/attributes/relationships)
- Schema modifications
- Branch rebase (`BranchRebase`)
- Branch merge (`BranchMerge`)
- Creating proposed changes with merged branch as source (`ProposedChangeCreate`)
- Branch update (description changes - optional, could allow)

**Implementation:**

```python
# backend/infrahub/core/branch/merged_status.py (new file)
from infrahub.core.branch import Branch
from infrahub.core.branch.enums import BranchStatus
from infrahub.exceptions import ValidationError


def check_merged_status(branch: Branch) -> None:
    """Raise error if branch is merged and cannot be modified."""
    if branch.status == BranchStatus.MERGED:
        raise ValidationError(
            f"Branch '{branch.name}' has been merged and is read-only. "
            "No modifications are allowed on merged branches."
        )
```

**Update middleware:**

```python
# backend/infrahub/graphql/middleware.py
from infrahub.core.branch.merged_status import check_merged_status
from infrahub.core.branch.needs_rebase_status import check_need_rebase_status

ALLOWED_MUTATIONS_ON_NEED_REBASE_BRANCH = ["BranchRebase", "BranchDelete", "BranchCreate", "ProposedChangeCreate"]
ALLOWED_MUTATIONS_ON_MERGED_BRANCH = ["BranchDelete"]


def raise_on_mutation_on_branch_needing_rebase(next, root, info, **kwargs):
    if info.operation.operation.value == "mutation":
        mutation_name = info.operation.selection_set.selections[0].name.value

        # Check NEED_REBASE status
        if mutation_name not in ALLOWED_MUTATIONS_ON_NEED_REBASE_BRANCH:
            check_need_rebase_status(branch=info.context.branch)

        # Check MERGED status
        if mutation_name not in ALLOWED_MUTATIONS_ON_MERGED_BRANCH:
            check_merged_status(branch=info.context.branch)

    return next(root, info, **kwargs)
```

### Proposed Change Validation

When creating or merging a proposed change, validate that the source branch is not `MERGED`:

**File:** `backend/infrahub/proposed_change/checker.py`

```python
async def verify_proposed_change_is_mergeable(
    proposed_change: CoreProposedChange,
    db: InfrahubDatabase,
    account_session: AccountSession,
) -> None:
    source_branch = await Branch.get_by_name(db=db, name=proposed_change.source_branch.value)

    # NEW: Check if source branch is already merged
    if source_branch.status == BranchStatus.MERGED:
        raise ValueError(
            f"Cannot merge proposed change: source branch '{source_branch.name}' "
            "has already been merged and is read-only."
        )

    # ... existing validation logic ...
```

**ProposedChange creation validation:**

When creating a ProposedChange, validate source branch is not `MERGED`:

```python
# In ProposedChangeCreate mutation
if source_branch.status == BranchStatus.MERGED:
    raise ValidationError(
        f"Cannot create proposed change: branch '{source_branch.name}' "
        "has already been merged."
    )
```

### Handling Existing Proposed Changes

When a branch is merged, any open proposed changes using that branch as source should be automatically closed/canceled:

**File:** `backend/infrahub/core/branch/tasks.py`

After setting branch status to `MERGED`, trigger cancellation of related proposed changes:

```python
# In merge_branch(), after setting MERGED status
await get_workflow().submit_workflow(
    workflow=BRANCH_CANCEL_PROPOSED_CHANGES,
    context=context,
    parameters={"branch_name": obj.name}
)
```

The existing `cancel_proposed_changes_branch()` workflow in `proposed_change/tasks.py` already handles this - it's triggered on branch delete. We reuse it for merged branches.

### BranchMerge Mutation Validation

Add validation in `BranchMerge` mutation to reject merged branches:

```python
# backend/infrahub/graphql/mutations/branch.py
class BranchMerge(Mutation):
    @classmethod
    async def mutate(cls, ...):
        obj = await Branch.get_by_name(db=graphql_context.db, name=branch_name)

        # Existing check
        if obj.status == BranchStatus.NEED_UPGRADE_REBASE:
            raise ValidationError(f"Cannot merge branch '{branch_name}' with status '{obj.status.name}'")

        # NEW: Check for merged status
        if obj.status == BranchStatus.MERGED:
            raise ValidationError(
                f"Cannot merge branch '{branch_name}': branch has already been merged"
            )
```

### GraphQL API

#### Branch Query

The existing `Branch` GraphQL type already exposes `status`. The new `MERGED` status will be automatically available:

```graphql
query {
  Branch(name: "feature-branch") {
    id
    name
    status  # Will return "MERGED" for merged branches
    is_default
    description
  }
}
```

#### Error Responses

Mutations on merged branches should return clear error messages:

```json
{
  "errors": [
    {
      "message": "Branch 'feature-branch' has been merged and is read-only. No modifications are allowed on merged branches.",
      "extensions": {
        "code": "VALIDATION_ERROR"
      }
    }
  ]
}
```

### REST API

The `/api/branch/{branch_name}` endpoint should return the `MERGED` status correctly. Existing serialization should handle this automatically since `status` is already exposed.

### Events

Add event for branch status change to `MERGED`:

Consider adding a `BranchFrozenEvent` or reusing `BranchMergedEvent` which already exists and is fired during merge.

The existing `BranchMergedEvent` in `backend/infrahub/events/branch_action.py` already signals merge completion. No additional events needed.

### Permission System

The permission system should respect the `MERGED` status - even users with write permissions cannot modify merged branches.

This is handled at the validation layer (middleware), which runs before permission checks. The status check takes precedence.

## Frontend

### Branch List View

- Display `MERGED` status in branch list with distinct styling (e.g., badge, icon)
- Potentially use different color/icon to indicate read-only state
- Consider graying out or disabling action buttons for merged branches

### Branch Detail View

- Show clear indication that branch is merged and read-only
- Disable or hide mutation actions (edit, delete data, create objects)
- Show informational message explaining the read-only state

### Proposed Change Creation

- When selecting source branch, filter out or visually indicate merged branches
- Show validation error if user attempts to create PC with merged source branch

### Error Handling

- Display clear, user-friendly error messages when operations are blocked
- Provide guidance on what actions are available (e.g., "You can delete this branch or create a new branch from a specific point in time")

## Python SDK

### Branch Status

The SDK should expose the new `MERGED` status through existing branch APIs:

```python
from infrahub_sdk import InfrahubClientSync

client = InfrahubClientSync()

# Get branch and check status
branch = client.branch.get(name="feature-branch")
print(branch.status)  # "MERGED"

# Check if branch is merged
if branch.status == "MERGED":
    print("Branch is read-only")
```

### Error Handling

SDK operations on merged branches should raise clear exceptions:

```python
from infrahub_sdk.exceptions import BranchMergedError

try:
    client.create(kind="InfraDevice", data={"name": "device1"}, branch="merged-branch")
except BranchMergedError as e:
    print(f"Cannot modify merged branch: {e}")
```

## Edge Cases and Considerations

### 1. Concurrent Merge Attempts

**Scenario:** Two users attempt to merge the same branch simultaneously.

**Handling:** Already handled by `DiffLocker` which acquires exclusive locks. Second merge will wait for lock, then fail validation since branch is now `MERGED`.

### 2. Merge Failure After Partial Operations

**Scenario:** Merge fails after `merge_graph()` but before status update.

**Handling:** The `BranchMerger.merge()` method has rollback logic. Status update is the final step, so if anything fails before, branch remains `OPEN`. The atomicity of the graph merge is handled separately.

### 3. Git Repository Merge Failure

**Scenario:** Data merge succeeds but git repo merge fails.

**Handling:** Current behavior: git merge happens after graph merge. If git fails, data is already merged. Branch should still be marked `MERGED` since the data state is final. Git repo state can be reconciled separately.

**Decision needed:** Should git merge failure block `MERGED` status? Recommendation: No, since data integrity is primary concern.

### 4. Branch Created From Merged Branch

**Scenario:** User creates new branch from a point in time when source branch was already merged.

**Handling:** New branch is created with `OPEN` status, independent of source branch state. The branched_from timestamp captures the point in time, not the current state.

### 5. Existing Open Proposed Changes

**Scenario:** Branch has open proposed changes when merged directly (not via PC).

**Handling:** Automatically cancel/close existing PCs for the merged branch. Reuse existing `cancel_proposed_changes_branch()` workflow.

### 6. Branch Rebase on Merged Branch

**Scenario:** User attempts to rebase a merged branch.

**Handling:** Block with validation error. Rebase makes no sense for merged branches since they're immutable.

### 7. Branch Description Update

**Scenario:** User wants to update description of merged branch.

**Decision needed:** Allow or block?

**Recommendation:** Block. While description is metadata, allowing any updates could be confusing. If needed, admin could change status back (see Migration below).

### 8. Viewing Diffs on Merged Branches

**Scenario:** User wants to view historical diff of merged branch.

**Handling:** Allow. Read operations are not blocked. This is important for audit and history purposes.

### 9. Branch Deletion

**Scenario:** User wants to delete a merged branch.

**Handling:** Allow. Cleanup of merged branches should be permitted. This is already in `ALLOWED_MUTATIONS_ON_MERGED_BRANCH`.

### 10. Migration of Existing Branches

**Scenario:** Branches merged before this feature don't have `MERGED` status.

**Options:**
1. Leave as-is (`OPEN`) - risk of double merge on old branches
2. Migration script to identify and update historically merged branches
3. Manual admin update when issues occur

**Recommendation:** Option 1 for initial release with documentation. Option 2 can be implemented later if needed. The merge tracking (`mark_tracking_ids_merged`) could help identify candidates.

### 11. Admin Override

**Scenario:** Admin needs to "unfreeze" a branch for exceptional circumstances.

**Handling:** Provide admin-only capability to change branch status. Could be:
- Direct database update (operational procedure)
- New GraphQL mutation `BranchUnfreeze` with admin-only permission
- CLI command

**Recommendation:** Document direct database/CLI approach for initial release. Admin mutation can be added later if needed.

### 12. Proposed Change State vs Branch Status

**Note:** `ProposedChange.state = MERGED` is different from `Branch.status = MERGED`. They're related but distinct:
- PC MERGED means the PC workflow completed
- Branch MERGED means the branch is now read-only

Both should be set when merging via PC. When merging directly (BranchMerge), only branch status is set.

## Testing Strategy

### Unit Tests

- `check_merged_status()` raises error for MERGED branches
- `check_merged_status()` allows OPEN branches
- Middleware blocks mutations on MERGED branches
- Middleware allows BranchDelete on MERGED branches
- BranchMerge mutation rejects MERGED branches
- ProposedChangeCreate mutation rejects MERGED source branches

### Integration Tests

- Full merge flow sets branch status to MERGED
- Merge failure does NOT set MERGED status
- PC merge sets both PC state and branch status
- Direct merge sets branch status
- Data mutations fail on MERGED branches
- Schema mutations fail on MERGED branches
- Branch deletion succeeds on MERGED branches
- New branch creation from MERGED branch succeeds
- Diff viewing works on MERGED branches

### E2E Tests

- UI correctly displays MERGED status
- UI prevents mutations on MERGED branches
- Error messages are user-friendly

## Documentation

- Update branch lifecycle documentation
- Add troubleshooting guide for "branch is read-only" errors
- Document admin override procedures
- Update API reference with new status

## Open Questions

1. Allow description updates on merged branches?
2. Git merge failure - should it block MERGED status?
3. Migration strategy for existing merged branches?
4. Admin override mechanism - DB-only or API?
5. Should we add a `merged_at` timestamp to branch model?
6. Should `BranchValidate` be allowed on merged branches?

## Uncertainty Map

### Least Confident About

- **Git merge failure handling**: The interaction between graph merge and git repo merge is complex. Unclear if git failure should affect branch status.
- **Migration of existing branches**: Identifying historically merged branches reliably may be difficult without explicit tracking.

### May Be Oversimplifying

- **Concurrent operations**: While DiffLocker handles merge concurrency, there may be race conditions with in-flight mutations when status transitions.
- **Registry/cache consistency**: Branch status is cached in registry. Cache invalidation timing relative to status update needs verification.

### Questions That Would Change Opinion

- Are there legitimate use cases for modifying a branch after merge? (e.g., adding metadata, annotations)
- How important is it to support "unfreezing" branches?
- Should merged branches be auto-deleted after a certain period?
- Is there a need to distinguish "merged via PC" vs "merged directly"?
