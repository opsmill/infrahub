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

**File:** `backend/tests/functional/branch/test_branch_merged.py`

Pattern: `backend/tests/functional/branch/test_branch_needs_rebase.py`

### TestMergedBranchStatus class

- `test_merged_branch_blocks_mutations` - mutations are blocked on MERGED branches
- `test_merged_branch_allows_delete` - BranchDelete is allowed on MERGED branches
- `test_merged_branch_blocks_rebase` - BranchRebase is blocked on MERGED branches
- `test_branch_merge_rejects_already_merged_branch` - BranchMerge rejects already merged branches
- `test_proposed_change_create_rejects_merged_source_branch` - ProposedChangeCreate rejects merged source branches

### TestNeedRebaseBranchStatus class

- `test_need_rebase_branch_blocks_mutations` - mutations are blocked on NEED_REBASE branches
- `test_need_rebase_branch_allows_rebase` - BranchRebase is allowed on NEED_REBASE branches (key difference from MERGED)
- `test_need_rebase_branch_allows_delete` - BranchDelete is allowed on NEED_REBASE branches

---

## Verification

```bash
uv run pytest backend/tests/functional/branch/test_branch_merged.py -v
```
