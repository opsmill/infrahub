# Phase 4: Mutation Validations

**Reference:** [dev/specs/2026-01-branch-freeze.md](../../specs/2026-01-branch-freeze.md)

**Status:** ✅ Complete

---

## Checklist

- [x] Block BranchMerge on already-merged branches (`backend/infrahub/graphql/mutations/branch.py`)
- [x] Block ProposedChangeCreate for merged source branches (`backend/infrahub/graphql/mutations/proposed_change.py`)
- [x] Block BranchRebase on merged branches (via middleware - not in `ALLOWED_MUTATIONS_ON_MERGED_BRANCH`)
- [x] Block BranchRebase on merged branches (direct check in `BranchRebase.mutate()` for target branch validation)
- [x] Extend functional tests (`backend/tests/functional/branch/test_branch_merged.py`)

---

## Implementation

### 4.1 Block BranchMerge on already-merged branches

**File:** `backend/infrahub/graphql/mutations/branch.py:298`

Add after existing `NEED_UPGRADE_REBASE` check:

```python
if obj.status == BranchStatus.NEED_UPGRADE_REBASE:
    raise ValidationError(f"Cannot merge branch '{branch_name}' with status '{obj.status.name}'")
# Add this:
if obj.status == BranchStatus.MERGED:
    raise ValidationError(f"Branch '{branch_name}' has already been merged")
```

### 4.2 Block ProposedChangeCreate for merged source branches

**File:** `backend/infrahub/graphql/mutations/proposed_change.py:85`

After getting `source_branch_name`, add:

```python
source_branch_obj = await Branch.get_by_name(db=dbt, name=source_branch_name)
if source_branch_obj.status == BranchStatus.MERGED:
    raise ValidationError(
        input_value=f"Cannot create proposed change: branch '{source_branch_name}' has been merged"
    )
```

---

## Tests

**Extend:** `backend/tests/functional/branch/test_branch_merged.py`

```python
async def test_branch_merge_rejects_already_merged_branch(db, default_branch, client):
    """Test that BranchMerge mutation fails on already merged branch."""
    branch = await create_branch(db=db, name="already-merged")
    branch.status = BranchStatus.MERGED
    await branch.save(db=db)

    result = await client.execute(
        query=BRANCH_MERGE_MUTATION,
        variables={"name": "already-merged"}
    )
    assert "has already been merged" in str(result.errors)

async def test_proposed_change_create_rejects_merged_source_branch(db, default_branch, client):
    """Test that ProposedChangeCreate fails for merged source branch."""
    branch = await create_branch(db=db, name="merged-source")
    branch.status = BranchStatus.MERGED
    await branch.save(db=db)

    result = await client.execute(
        query=PROPOSED_CHANGE_CREATE_MUTATION,
        variables={"source_branch": "merged-source", "destination_branch": "main"}
    )
    assert "has been merged" in str(result.errors)
```

---

## Verification

```bash
uv run pytest backend/tests/functional/branch/test_branch_merged.py -v -k "merge_rejects or proposed_change_create"
```
