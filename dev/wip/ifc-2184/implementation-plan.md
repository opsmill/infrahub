# Branch Freeze Feature Implementation Plan

## Summary

Implement a `MERGED` status for branches that makes them read-only after successful merge operations. This prevents data corruption from re-merging and provides clear UX feedback.

**Reference:** [dev/specs/2026-01-branch-freeze.md](../../specs/2026-01-branch-freeze.md)

---

## Phase 1: Backend Core (Enum + Status Check)

### 1.1 Add MERGED status to BranchStatus enum

**File:** `backend/infrahub/core/branch/enums.py`

Add `MERGED = "MERGED"` to the enum.

### 1.2 Create merged status check module

**New file:** `backend/infrahub/core/branch/merged_status.py`

Follow pattern from `backend/infrahub/core/branch/needs_rebase_status.py`:

```python
from infrahub.core.branch import Branch
from infrahub.core.branch.enums import BranchStatus


def raise_merged_error(branch_name: str) -> None:
    raise ValueError(f"Branch '{branch_name}' has been merged and is read-only. No modifications are allowed.")


def check_merged_status(branch: Branch) -> None:
    if branch.status == BranchStatus.MERGED:
        raise_merged_error(branch_name=branch.name)
```

---

## Phase 2: Backend GraphQL Middleware

### 2.1 Update middleware to block mutations on MERGED branches

**File:** `backend/infrahub/graphql/middleware.py`

1. Import `check_merged_status`
2. Add constant: `ALLOWED_MUTATIONS_ON_MERGED_BRANCH = ["BranchDelete"]`
3. Add merged status check in the existing `raise_on_mutation_on_branch_needing_rebase` function (or rename it to be more generic)

```python
def raise_on_mutation_on_branch_needing_rebase(next, root, info, **kwargs):
    if info.operation.operation.value == "mutation":
        mutation_name = info.operation.selection_set.selections[0].name.value

        # Existing NEED_REBASE check
        if mutation_name not in ALLOWED_MUTATIONS_ON_NEED_REBASE_BRANCH:
            check_need_rebase_status(branch=info.context.branch)

        # NEW: MERGED status check
        if mutation_name not in ALLOWED_MUTATIONS_ON_MERGED_BRANCH:
            check_merged_status(branch=info.context.branch)

    return next(root, info, **kwargs)
```

---

## Phase 3: Backend Merge Flow

### 3.1 Set MERGED status after successful merge

**File:** `backend/infrahub/core/branch/tasks.py`

In `merge_branch()` function, after line ~355 (after `mark_tracking_ids_merged`), add:

```python
# Set branch status to MERGED to make it read-only
obj.status = BranchStatus.MERGED
await obj.save(db=db)
registry.branch[obj.name] = obj
```

### 3.2 Cancel open proposed changes for merged branch

After setting MERGED status, submit workflow to cancel related PCs:

```python
await get_workflow().submit_workflow(
    workflow=BRANCH_CANCEL_PROPOSED_CHANGES,
    context=context,
    parameters={"branch_name": obj.name},
)
```

---

## Phase 4: Backend Mutation Validations

### 4.1 Block BranchMerge on already-merged branches

**File:** `backend/infrahub/graphql/mutations/branch.py:298`

Add after existing `NEED_UPGRADE_REBASE` check:

```python
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

## Phase 5: Backend REST API Validation

### 5.1 Block schema loading on merged branches

**File:** `backend/infrahub/api/schema.py:326`

Add `check_merged_status(branch)` after existing `check_need_rebase_status(branch)`.

### 5.2 Block artifact generation on merged branches

**File:** `backend/infrahub/api/artifact.py:80`

Add `check_merged_status(branch_params.branch)` after existing rebase check.

---

## Phase 6: Backend Permission System Integration

### 6.1 Return DENY for create/update/delete on merged branches

**File:** `backend/infrahub/permissions/report.py:21`

In `get_permission_report()`, add early return for merged branches:

```python
def get_permission_report(
    permission_manager: PermissionManager,
    branch: Branch,
    node: MainSchemaTypes,
    action: str,
    global_permission_report: dict[GlobalPermissions, bool],
) -> BranchRelativePermissionDecision:
    # NEW: Block mutations on merged branches (except Branch delete)
    if branch.status == BranchStatus.MERGED and action != "view":
        # Allow delete for Branch kind only
        if not (node.kind == InfrahubKind.BRANCH and action == "delete"):
            return BranchRelativePermissionDecision.DENY

    # ... existing logic ...
```

---

## Phase 7: Testing

### Unit Tests

**New file:** `backend/tests/unit/core/branch/test_merged_status.py`

- Test `check_merged_status` raises for MERGED branches
- Test `check_merged_status` passes for other statuses

### Functional Tests

**New file:** `backend/tests/functional/branch/test_branch_merged.py`

Pattern: `backend/tests/functional/branch/test_branch_needs_rebase.py`

- Test merge sets branch status to MERGED
- Test mutations blocked on MERGED branch
- Test BranchDelete allowed on MERGED branch
- Test schema load blocked on MERGED branch
- Test ProposedChangeCreate blocked for MERGED source
- Test BranchMerge fails on already MERGED branch

---

## Verification Plan

1. **Manual Testing:**
   - Create branch, make changes, merge via BranchMerge mutation
   - Verify branch status is MERGED in GraphQL query
   - Verify mutations return error on merged branch
   - Verify BranchDelete works on merged branch

2. **Run Tests:**
   ```bash
   uv run invoke backend.test-unit
   uv run invoke backend.test-integration
   ```

3. **Lint/Format:**
   ```bash
   uv run invoke format && uv run invoke lint
   ```

---

## Critical Files Summary

| Component | File |
|-----------|------|
| BranchStatus enum | `backend/infrahub/core/branch/enums.py` |
| Merged status check | `backend/infrahub/core/branch/merged_status.py` (new) |
| GraphQL middleware | `backend/infrahub/graphql/middleware.py` |
| Merge flow | `backend/infrahub/core/branch/tasks.py` |
| BranchMerge mutation | `backend/infrahub/graphql/mutations/branch.py` |
| ProposedChangeCreate | `backend/infrahub/graphql/mutations/proposed_change.py` |
| Permission report | `backend/infrahub/permissions/report.py` |
| REST schema API | `backend/infrahub/api/schema.py` |
| REST artifact API | `backend/infrahub/api/artifact.py` |
