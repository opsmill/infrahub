# Branch Freeze Feature Implementation Plan

## Summary

Implement a `MERGED` status for branches that makes them read-only after successful merge operations. This prevents data corruption from re-merging and provides clear UX feedback.

**Reference:** [dev/specs/2026-01-branch-freeze.md](../../specs/2026-01-branch-freeze.md)

---

## Phase 1: Core Enum and Status Check

### Implementation

#### 1.1 Add MERGED status to BranchStatus enum

**File:** `backend/infrahub/core/branch/enums.py`

Add `MERGED = "MERGED"` to the enum.

#### 1.2 Create merged status check module

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

### Tests

**New file:** `backend/tests/unit/core/branch/test_merged_status.py`

- Test `raise_merged_error` raises ValueError with correct message
- Test `check_merged_status` raises for MERGED branches
- Test `check_merged_status` passes for OPEN branches

**Verification:**
```bash
uv run pytest backend/tests/unit/core/branch/test_merged_status.py -v
```

---

## Phase 2: GraphQL Middleware

### Implementation

**File:** `backend/infrahub/graphql/middleware.py`

1. Import `check_merged_status`
2. Add constant: `ALLOWED_MUTATIONS_ON_MERGED_BRANCH = ["BranchDelete"]`
3. Add merged status check in the existing `raise_on_mutation_on_branch_needing_rebase` function

```python
from infrahub.core.branch.merged_status import check_merged_status

ALLOWED_MUTATIONS_ON_MERGED_BRANCH = ["BranchDelete"]

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

### Tests

**Extend:** `backend/tests/unit/graphql/test_middleware.py`

- Test middleware blocks mutation on MERGED branch
- Test middleware allows BranchDelete on MERGED branch

**Verification:**
```bash
uv run pytest backend/tests/unit/graphql/test_middleware.py -v -k merged
```

---

## Phase 3: Merge Flow

### Implementation

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

### Tests

**New file:** `backend/tests/functional/branch/test_branch_merged.py`

Pattern: `backend/tests/functional/branch/test_branch_needs_rebase.py`

- Test merge sets branch status to MERGED
- Test merge failure does NOT set MERGED status
- Test merge cancels open proposed changes for the branch

**Verification:**
```bash
uv run pytest backend/tests/functional/branch/test_branch_merged.py -v -k "merge_sets or merge_failure or merge_cancels"
```

---

## Phase 4: Mutation Validations

### Implementation

#### 4.1 Block BranchMerge on already-merged branches

**File:** `backend/infrahub/graphql/mutations/branch.py:298`

Add after existing `NEED_UPGRADE_REBASE` check:

```python
if obj.status == BranchStatus.MERGED:
    raise ValidationError(f"Branch '{branch_name}' has already been merged")
```

#### 4.2 Block ProposedChangeCreate for merged source branches

**File:** `backend/infrahub/graphql/mutations/proposed_change.py:85`

After getting `source_branch_name`, add:

```python
source_branch_obj = await Branch.get_by_name(db=dbt, name=source_branch_name)
if source_branch_obj.status == BranchStatus.MERGED:
    raise ValidationError(
        input_value=f"Cannot create proposed change: branch '{source_branch_name}' has been merged"
    )
```

### Tests

**Extend:** `backend/tests/functional/branch/test_branch_merged.py`

- Test BranchMerge mutation rejects already merged branch
- Test ProposedChangeCreate rejects merged source branch

**Verification:**
```bash
uv run pytest backend/tests/functional/branch/test_branch_merged.py -v -k "merge_rejects or proposed_change_create"
```

---

## Phase 5: REST API Validation

### Implementation

#### 5.1 Block schema loading on merged branches

**File:** `backend/infrahub/api/schema.py:326`

```python
from infrahub.core.branch.merged_status import check_merged_status

# In load_schema function:
check_need_rebase_status(branch)
check_merged_status(branch)  # Add this
```

#### 5.2 Block artifact generation on merged branches

**File:** `backend/infrahub/api/artifact.py:80`

```python
from infrahub.core.branch.merged_status import check_merged_status

# In generate_artifact function:
check_need_rebase_status(branch_params.branch)
check_merged_status(branch_params.branch)  # Add this
```

### Tests

**Extend:** `backend/tests/functional/branch/test_branch_merged.py`

- Test schema load blocked on merged branch (returns 400)
- Test artifact generation blocked on merged branch (returns 400)

**Verification:**
```bash
uv run pytest backend/tests/functional/branch/test_branch_merged.py -v -k "schema_load or artifact"
```

---

## Phase 6: Permission System Integration

### Implementation

**File:** `backend/infrahub/permissions/report.py:21`

In `get_permission_report()`, add early return for merged branches:

```python
from infrahub.core.branch.enums import BranchStatus
from infrahub.core.constants import InfrahubKind

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

### Tests

**New file:** `backend/tests/unit/permissions/test_merged_branch_permissions.py`

- Test permission denies create on merged branch
- Test permission denies update on merged branch
- Test permission denies delete on merged branch (non-Branch kinds)
- Test permission allows view on merged branch
- Test permission allows Branch delete on merged branch

**Verification:**
```bash
uv run pytest backend/tests/unit/permissions/test_merged_branch_permissions.py -v
```

---

## Full Verification

After all phases are complete:

```bash
# Run all new tests
uv run pytest backend/tests/unit/core/branch/test_merged_status.py \
    backend/tests/functional/branch/test_branch_merged.py \
    backend/tests/unit/permissions/test_merged_branch_permissions.py -v

# Run full test suite
uv run invoke backend.test-unit
uv run invoke backend.test-integration

# Lint and format
uv run invoke format && uv run invoke lint
```

### Manual Testing

1. Create a branch and make changes
2. Merge via `BranchMerge` mutation
3. Verify branch status is `MERGED` via GraphQL query
4. Verify mutations return "read-only" error
5. Verify `BranchDelete` works on merged branch

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
