# Phase 3: Merge Flow

**Reference:** [dev/specs/2026-01-branch-freeze.md](../../specs/2026-01-branch-freeze.md)

**Status:** ✅ Complete

---

## Checklist

- [x] Update `merge_branch()` in `tasks.py` to set `BranchStatus.MERGED` after successful merge
- [x] Update registry with merged branch status
- [x] Add workflow call to cancel remaining open proposed changes
- [x] Create functional tests (`backend/tests/functional/branch/test_branch_merged.py`)

---

## Implementation

**File:** `backend/infrahub/core/branch/tasks.py`

In `merge_branch()` function, after `mark_tracking_ids_merged` (around line ~355):

```python
# Set branch status to MERGED to make it read-only
obj.status = BranchStatus.MERGED
await obj.save(db=db)
registry.branch[obj.name] = obj

# Cancel any remaining open proposed changes for this merged branch
await get_workflow().submit_workflow(
    workflow=BRANCH_CANCEL_PROPOSED_CHANGES,
    context=context,
    parameters={"branch_name": obj.name},
)
```

---

## Tests

**New file:** `backend/tests/functional/branch/test_branch_merged.py`

Pattern: `backend/tests/functional/branch/test_branch_needs_rebase.py`

```python
import pytest
from infrahub.core.branch.enums import BranchStatus


async def test_merge_branch_sets_merged_status(db, default_branch):
    """Test that merging a branch sets its status to MERGED."""
    branch = await create_branch(db=db, name="feature-branch")

    # Make some changes on the branch
    # ...

    # Merge the branch
    await merge_branch(branch=branch.name, context=context)

    # Reload and verify status
    merged_branch = await Branch.get_by_name(db=db, name="feature-branch")
    assert merged_branch.status == BranchStatus.MERGED


async def test_merge_failure_does_not_set_merged_status(db, default_branch):
    """Test that failed merge does NOT set MERGED status."""
    branch = await create_branch(db=db, name="feature-branch")

    # Setup conditions that will cause merge to fail
    # ...

    with pytest.raises(Exception):
        await merge_branch(branch=branch.name, context=context)

    # Verify status is still OPEN
    branch = await Branch.get_by_name(db=db, name="feature-branch")
    assert branch.status == BranchStatus.OPEN


async def test_merge_cancels_open_proposed_changes(db, default_branch):
    """Test that merging a branch cancels open proposed changes for that branch."""
    branch = await create_branch(db=db, name="feature-branch")

    # Create a proposed change for this branch
    pc = await create_proposed_change(source_branch=branch.name, ...)

    # Merge the branch directly (not via PC)
    await merge_branch(branch=branch.name, context=context)

    # Verify PC is cancelled
    pc = await get_proposed_change(id=pc.id)
    assert pc.state == "cancelled"
```

---

## Verification

```bash
uv run pytest backend/tests/functional/branch/test_branch_merged.py -v -k "merge_branch_sets or merge_failure or merge_cancels"
```
