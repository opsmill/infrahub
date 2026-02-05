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
- Blocks all schema and data mutations on the branch
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

- All data mutations (create, update, delete nodes/attributes/relationships), even for branch agnostic nodes
- Schema modifications (loading schema using REST API, mutations to add/delete dropdown enum options)
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

Modify the existing `raise_on_mutation_for_branch_status` function:

- add logic in this is to validate allowed mutations on branches with status `MERGED`
- rename the function to indicate that is not just used for branches with status `NEED_REBASE`

```python
# backend/infrahub/graphql/middleware.py
from infrahub.core.branch.merged_status import check_merged_status
from infrahub.core.branch.needs_rebase_status import check_need_rebase_status

ALLOWED_MUTATIONS_ON_NEED_REBASE_BRANCH = ["BranchRebase", "BranchDelete", "BranchCreate", "ProposedChangeCreate"]
ALLOWED_MUTATIONS_ON_MERGED_BRANCH = ["BranchDelete"]


def raise_on_mutation_for_branch_status(next, root, info, **kwargs):
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

When a branch is merged, any open proposed changes using that branch as source should be automatically canceled:

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

The existing `cancel_proposed_changes_branch()` workflow in `proposed_change/tasks.py` already handles this - it's triggered on branch delete. We reuse it for merged branches. In the current implementation a this workflow is only triggered when we delete a branch.

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

The existing `Branch` and `InfrahubBranch` GraphQL queries already exposes `status`. The new `MERGED` status will be automatically available:

```graphql
query {
  Branch(name: "feature-branch") {
    id
    name
    status # Will return "MERGED" for merged branches
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

1. We should not be able to load new schemas using the schema REST API endpoints when a branch is in merged state
2. We should not be able to generate artifacts using the REST API endpoint when a branch is in merged state
3. The `/api/query` endpoints should not perform GraphQL queries that contain mutations within them, when the branch is in merged state. In the future we should consider not accepting GraphQL queries that contain mutations at all.

### Permission System

The permission system should respect the `MERGED` status - even users with write permissions cannot modify merged branches.

This is handled at the validation layer (middleware), which runs before permission checks. The status check takes precedence.

The permission system shall also be used to communicate to the frontend the current permissions for an object, when the branch is in `MERGED` status.

When the backend receives a query for the permissions for a node type, it will consider the branch argument and consider the status of that branch. If the branch is in `MERGED` status we should return a `DENY` permission for the create, update and delete action of the object. The `VIEW` permission will depend on the actual permissions defined in the system.

The exception to this is the permission for a branch object. The delete permission should still be `ALLOW`, depending on the defined permissions, since a branch in the `MERGED` status can still be deleted.

**OPEN QUESTION**

- [x] Do we use the permission system to communicate to the frontend what actions should be disabled when a branch is in the `MERGED` status.
      The decision has been made to use the permission system to communicate which actions are possible between the back- and frontend when a branch is in `MERGED` status.

## Frontend

### Branch List View

- Display `MERGED` status in branch list with distinct styling (e.g., badge, icon)
- Potentially use different color/icon to indicate read-only state
- Consider graying out or disabling action buttons for merged branches

### Branch Detail View

- Show clear indication that branch is merged and read-only
- Disable or hide mutation actions (merge, proposed change, rebase, validate, refresh diff, refresh schema diff, rebase on diff view)
- The delete action should be enabled

### Proposed Change Creation

- When selecting source branch, filter out merged branches
- Show validation error if user attempts to create PC with merged source branch

### Error Handling

- Display clear, user-friendly error messages when operations are blocked
- Provide guidance on what actions are available (e.g., "You can delete this branch or create a new branch from a specific point in time")

## Edge Cases and Considerations

### 1. Existing Open Proposed Changes

**Scenario:** Branch has open proposed changes when merged directly (not via PC).

**Handling:** Automatically cancel existing PCs for the merged branch. Reuse existing `cancel_proposed_changes_branch()` workflow.

### 2. Branch Rebase on Merged Branch

**Scenario:** User attempts to rebase a merged branch.

**Handling:** Block with validation error. Rebase makes no sense for merged branches since they're immutable.

### 3. Viewing Diffs on Merged Branches

**Scenario:** User wants to view historical diff of merged branch.

**Handling:** Allow. Read operations are not blocked. This is important for audit and history purposes.

### 4. Branch Deletion

**Scenario:** User wants to delete a merged branch.

**Handling:** Allow. Cleanup of merged branches should be permitted. This is already in `ALLOWED_MUTATIONS_ON_MERGED_BRANCH`.

### 5. Migration of Existing Branches

**Scenario:** Branches merged before this feature don't have `MERGED` status.

**Handling:** Leave as-is. Branches that were merged before this feature will stay in the open state. The user will need to delete these branches. We are not going to implement migrations for this scenario.

### Git repository

Merging a branch in Infrahub and in the Git repository are not a single transaction today. Also there is no good way to communicate an error back to the user when the merge in the Git repository fails and hence we can't properly "cancel" the transaction at the database level.

We opt not to handle that scenario for now.

If the git repository syncs new commits for a branch that has already been merged in Infrahub, then that synchronization will fail, but it will not affect the synchronization of other branches in Infrahub.

This is a known behavior that we should document.

When we have a better way to communicate errors, we should revisit handling this in a better way.

## Testing Strategy

### Component Tests

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
- Update API reference with new status

## How it works

When a user makes modifications to Infrahub's data or schema, the recommended workflow is to perform this through a branch in Infrahub. This branch can then be merged into the main branch using a branch merge or a merging a proposed change.

After a branch has been successfully merged (through a proposed change or branch merge), the status of the branch will be updated to `MERGED`. When there is a failure during the merge process, the branch will stay in `OPEN` status and no changes will have been made to the main branch.

A branch with status `MERGED` will not allow changes to the data or schema any longer, it is effectively in a read-only modus. A user can still consult the data or the schema in the branch but will not be able to make any changes.

When a branch is merged, any open proposed change open for this branch (other than the one that merges the branch) will move to the `cancelled` status.

A branch in the status `MERGED` can still be deleted by the user using the `BranchDelete` mutation, and the provided functionality in the UI to delete a branch.

(pending final UI design to explain the behavior in the UI)
