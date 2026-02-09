# Branch Freeze Feature Implementation Plan

## Summary

Implement a `MERGED` status for branches that makes them read-only after successful merge operations. This prevents data corruption from re-merging and provides clear UX feedback.

**Reference:** [dev/specs/2026-01-branch-freeze.md](../../specs/2026-01-branch-freeze.md)

**Status:** ✅ All phases complete

---

## Implementation Progress

| Phase | Description                               | Status      | Tests                                       |
| ----- | ----------------------------------------- | ----------- | ------------------------------------------- |
| 1     | Core Enum + Status Check                  | ✅ Complete | 2 unit tests                                |
| 2     | GraphQL Middleware                        | ✅ Complete | 7 unit tests                                |
| 3     | Merge Flow                                | ✅ Complete | 8 functional tests (MERGED and NEED_REBASE) |
| 4     | Mutation Validations                      | ✅ Complete | (included in Phase 3)                       |
| 5     | REST API Validation + BranchStatusChecker | ✅ Complete | 4 component tests                           |
| 6     | Permission System (MERGED + NEED_REBASE)  | ✅ Complete | 4 unit tests                                |

**Total Tests:** 25 tests (13 unit + 4 component + 8 functional)

---

## Phase 1: Core Enum and Status Check ✅

### Checklist

- [x] Add MERGED status to BranchStatus enum
- [x] Create unit tests (2 tests using actual Branch objects)

### Implementation

#### 1.1 Add MERGED status to BranchStatus enum

**File:** `backend/infrahub/core/branch/enums.py`

Add `MERGED = "MERGED"` to the enum.

**Note:** Status checking is consolidated in `BranchStatusChecker` class (see Phase 5). The standalone `merged_status.py` and `needs_rebase_status.py` modules were removed in favor of the unified checker class with instance methods.

### Tests

**File:** `backend/tests/unit/core/branch/test_merged_status.py`

Tests use actual `Branch` objects (not mocks) for realistic validation:

- Test `BranchStatusChecker().check_merge_status()` raises `BranchAlreadyMergedError` for MERGED branches
- Test `BranchStatusChecker().check_merge_status()` passes for OPEN, NEED_REBASE, NEED_UPGRADE_REBASE branches (parametrized)

**Verification:**

```bash
uv run pytest backend/tests/unit/core/branch/test_merged_status.py -v
```

---

## Phase 2: GraphQL Middleware ✅

### Checklist

- [x] Import `BranchStatusChecker` in middleware.py
- [x] Add `ALLOWED_MUTATIONS_ON_MERGED_BRANCH` constant
- [x] Add merged status check in middleware function
- [x] Create unit tests (7 tests)

### Implementation

**File:** `backend/infrahub/graphql/middleware.py`

1. Import `BranchStatusChecker` from unified status checker
2. Add constant: `ALLOWED_MUTATIONS_ON_MERGED_BRANCH = ["BranchDelete"]`
3. Use instance methods for status checks in `raise_on_mutation_for_branch_status` function

```python
from infrahub.branch.status_checker import BranchStatusChecker

ALLOWED_MUTATIONS_ON_NEED_REBASE_BRANCH = ["BranchRebase", "BranchDelete", "BranchCreate", "ProposedChangeCreate"]
ALLOWED_MUTATIONS_ON_MERGED_BRANCH = ["BranchDelete"]

def raise_on_mutation_for_branch_status(next, root, info, **kwargs):
    if info.operation.operation.value == "mutation":
        mutation_name = info.operation.selection_set.selections[0].name.value
        if mutation_name not in ALLOWED_MUTATIONS_ON_NEED_REBASE_BRANCH:
            BranchStatusChecker().check_needs_rebase_status(branch=info.context.branch)
        if mutation_name not in ALLOWED_MUTATIONS_ON_MERGED_BRANCH:
            BranchStatusChecker().check_merge_status(branch=info.context.branch)

    return next(root, info, **kwargs)
```

---

## Phase 3: Merge Flow ✅

### Checklist

- [x] Set `BranchStatus.MERGED` after successful merge in `tasks.py`
- [x] Update registry with merged branch
- [x] Submit workflow to cancel open proposed changes
- [x] Create functional tests

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

**TestMergedBranchStatus class:**

- Test merge sets branch status to MERGED
- Test merge failure does NOT set MERGED status
- Test merge cancels open proposed changes for the branch

**TestNeedRebaseBranchStatus class:**

- Test mutations blocked on branches needing rebase
- Test BranchRebase allowed on branches needing rebase (key difference from MERGED)
- Test BranchDelete allowed on branches needing rebase

**Verification:**

```bash
uv run pytest backend/tests/functional/branch/test_branch_merged.py -v
```

---

## Phase 4: Mutation Validations ✅

### Checklist

- [x] Block BranchMerge on already-merged branches
- [x] Block ProposedChangeCreate for merged source branches
- [x] Block BranchRebase on merged branches (via middleware + direct check in mutation)
- [x] Extend functional tests

### Implementation

#### 4.1 Block BranchMerge on already-merged branches

**File:** `backend/infrahub/graphql/mutations/branch.py:303`

Add after existing `NEED_UPGRADE_REBASE` check:

```python
if obj.status == BranchStatus.MERGED:
    raise ValidationError(f"Branch '{branch_name}' has already been merged")
```

#### 4.2 Block ProposedChangeCreate for merged source branches

**File:** `backend/infrahub/graphql/mutations/proposed_change.py:87`

After getting `source_branch_name`, add validation **outside** the transaction context:

```python
source_branch_name = data.get("source_branch", {}).get("value")

# Query existing open PCs and validate source branch BEFORE transaction
existing_open_pcs = await NodeManager.query(
    db=graphql_context.db,
    schema=InfrahubKind.PROPOSEDCHANGE,
    filters={
        "source_branch__value": source_branch_name,
        "state__value": ProposedChangeState.OPEN.value,
    },
)
if existing_open_pcs:
    raise ValidationError(
        input_value=f"An open proposed change already exists for branch '{source_branch_name}'"
    )

try:
    source_branch_obj = await Branch.get_by_name(db=graphql_context.db, name=source_branch_name)
except BranchNotFoundError:
    raise ValidationError(
        input_value="The specified source branch for this proposed change was not found"
    ) from None
if source_branch_obj.status == BranchStatus.MERGED:
    raise ValidationError(
        input_value=f"Cannot create proposed change: branch '{source_branch_name}' has been merged"
    )

async with graphql_context.db.start_transaction() as dbt:
    # Create proposed change inside transaction
    ...
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

## Phase 5: REST API Validation ✅

### Checklist

- [x] Create reusable `BranchStatusChecker` class
- [x] Block schema loading on merged branches (`schema.py`)
- [x] Block artifact generation on merged branches (`artifact.py`)
- [x] Extend functional tests

### Implementation

#### 5.1 Create reusable BranchStatusChecker class

**New file:** `backend/infrahub/branch/status_checker.py`

The checker class consolidates both merged and needs-rebase status checking with separate methods for granular control:

```python
from infrahub.core.branch import Branch
from infrahub.core.branch.enums import BranchStatus
from infrahub.exceptions import BranchAlreadyMergedError, BranchNeedsRebaseError


class BranchStatusChecker:
    def check_merge_status(self, branch: Branch) -> None:
        if branch.status == BranchStatus.MERGED:
            raise BranchAlreadyMergedError(
                identifier=branch.name,
                message=f"Branch '{branch.name}' has been merged and is read-only. No modifications are allowed.",
            )

    def check_needs_rebase_status(self, branch: Branch) -> None:
        if branch.status == BranchStatus.NEED_REBASE:
            raise BranchNeedsRebaseError(
                identifier=branch.name, message=f"Branch {branch.name} must be rebased before any updates can be made"
            )

    def check(self, branch: Branch) -> None:
        self.check_needs_rebase_status(branch)
        self.check_merge_status(branch)
```

#### 5.2 Block schema loading on merged branches

**File:** `backend/infrahub/api/schema.py:327`

```python
from infrahub.branch.status_checker import BranchStatusChecker
from infrahub.exceptions import BranchStatusError, ValidationError

# In load_schema function:
try:
    BranchStatusChecker().check(branch=branch)
except BranchStatusError as err:
    raise ValidationError(input_value=str(err)) from err
```

#### 5.3 Block artifact generation on merged branches

**File:** `backend/infrahub/api/artifact.py:80`

```python
from infrahub.branch.status_checker import BranchStatusChecker
from infrahub.exceptions import BranchStatusError

# In generate_artifact function:
try:
    BranchStatusChecker().check(branch=branch_params.branch)
except BranchStatusError as err:
    raise ValidationError(input_value=str(err)) from err
```

### Tests

**Extend:** `backend/tests/functional/branch/test_branch_merged.py`

- Test schema load blocked on merged branch (returns 422)
- Test artifact generation blocked on merged branch (returns 422)

**Component tests:** `backend/tests/component/api/test_40_schema.py` and `backend/tests/component/api/test_11_artifact.py`

- `test_schema_load_blocked_on_merged_branch` - verifies 422 status code
- `test_schema_load_blocked_on_need_rebase_branch` - verifies 422 status code
- `test_artifact_generate_blocked_on_merged_branch` - verifies 422 status code
- `test_artifact_generate_blocked_on_need_rebase_branch` - verifies 422 status code

**Verification:**

```bash
uv run pytest backend/tests/component/api/test_40_schema.py -v -k "merged or rebase"
uv run pytest backend/tests/component/api/test_11_artifact.py -v -k "merged or rebase"
```

---

## Phase 6: Permission System Integration ✅

### Checklist

- [x] Update `get_permission_report()` to return DENY for non-view actions on merged branches AND branches needing rebase
- [x] Super admin bypass preserved
- [x] Branch delete handled via middleware allowlist
- [x] Create unit tests (4 tests)

**Note:** Implementation simplified - Branch delete handled via GraphQL middleware `ALLOWED_MUTATIONS_ON_MERGED_BRANCH` rather than permission system check for `InfrahubKind.BRANCH`. The permission check now covers both `MERGED` and `NEED_REBASE` statuses for consistent behavior.

### Implementation

**File:** `backend/infrahub/permissions/report.py:34`

In `get_permission_report()`, add early return for merged/need_rebase branches:

```python
from infrahub.core.branch.enums import BranchStatus

def get_permission_report(
    permission_manager: PermissionManager,
    branch: Branch,
    node: MainSchemaTypes,
    action: str,
    global_permission_report: dict[GlobalPermissions, bool],
) -> BranchRelativePermissionDecision:
    # Block mutations on merged branches or branches needing rebase
    # Note: Branch delete is allowed via middleware, this covers node permissions
    if branch.status in (BranchStatus.MERGED, BranchStatus.NEED_REBASE,) and action != "view":
        return BranchRelativePermissionDecision.DENY

    # ... existing logic ...
```

### Tests

**New file:** `backend/tests/unit/permissions/test_merged_branch_permissions.py`

- Test permission denies create on merged branch
- Test permission denies update on merged branch
- Test permission denies delete on merged branch (non-Branch kinds)
- Test permission allows view on merged branch
- Test permission denies mutations on need_rebase branch

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
    backend/tests/unit/permissions/test_merged_branch_permissions.py \
    backend/tests/unit/branch/test_status_checker.py -v

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

| Component             | File                                                    |
| --------------------- | ------------------------------------------------------- |
| BranchStatus enum     | `backend/infrahub/core/branch/enums.py`                 |
| Branch status checker | `backend/infrahub/branch/status_checker.py` (new)       |
| GraphQL middleware    | `backend/infrahub/graphql/middleware.py`                |
| Merge flow            | `backend/infrahub/core/branch/tasks.py`                 |
| BranchMerge mutation  | `backend/infrahub/graphql/mutations/branch.py`          |
| ProposedChangeCreate  | `backend/infrahub/graphql/mutations/proposed_change.py` |
| Permission report     | `backend/infrahub/permissions/report.py`                |
| REST schema API       | `backend/infrahub/api/schema.py`                        |
| REST artifact API     | `backend/infrahub/api/artifact.py`                      |

**Note:** The standalone `merged_status.py` and `needs_rebase_status.py` modules were removed and consolidated into `BranchStatusChecker`.

### Test Files

| Test                                                | File                                                               |
| --------------------------------------------------- | ------------------------------------------------------------------ |
| Merged status unit tests                            | `backend/tests/unit/core/branch/test_merged_status.py`             |
| Permission unit tests (MERGED + NEED_REBASE)        | `backend/tests/unit/permissions/test_merged_branch_permissions.py` |
| Branch status checker unit tests                    | `backend/tests/unit/branch/test_status_checker.py`                 |
| Schema API component tests (MERGED + NEED_REBASE)   | `backend/tests/component/api/test_40_schema.py`                    |
| Artifact API component tests (MERGED + NEED_REBASE) | `backend/tests/component/api/test_11_artifact.py`                  |
| Functional tests (MERGED + NEED_REBASE)             | `backend/tests/functional/branch/test_branch_merged.py`            |
