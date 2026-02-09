# Phase 5: REST API Validation

**Reference:** [dev/specs/2026-01-branch-freeze.md](../../specs/2026-01-branch-freeze.md)

**Status:** ✅ Complete

---

## Checklist

- [x] Create reusable `BranchStatusChecker` class (`backend/infrahub/branch/status_checker.py`)
- [x] Block schema loading on merged branches (`backend/infrahub/api/schema.py`)
- [x] Block artifact generation on merged branches (`backend/infrahub/api/artifact.py`)
- [x] Extend functional tests (`backend/tests/functional/branch/test_branch_merged.py`)

---

## Implementation

### 5.1 Create reusable branch status checker class

**New file:** `backend/infrahub/branch/status_checker.py`

A reusable branch status class that consolidates both `need_rebase` and `merged` status checks with separate instance methods for granular control:

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

### 5.2 Block schema loading on merged branches

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

**Note:** Changed from `SchemaNotValidError` to `ValidationError` for consistency with other validation error handling.

### 5.3 Block artifact generation on merged branches

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

---

## Tests

**Component tests:** `backend/tests/component/api/test_40_schema.py` and `backend/tests/component/api/test_11_artifact.py`

- `test_schema_load_blocked_on_merged_branch` - verifies 422 status code for merged branch
- `test_schema_load_blocked_on_need_rebase_branch` - verifies 422 status code for need_rebase branch
- `test_artifact_generate_blocked_on_merged_branch` - verifies 422 status code for merged branch
- `test_artifact_generate_blocked_on_need_rebase_branch` - verifies 422 status code for need_rebase branch

**Unit tests:** `backend/tests/unit/branch/test_status_checker.py`

- `test_check_passes_for_open_branch` - OPEN status passes
- `test_check_raises_for_merged_branch` - MERGED status raises `BranchAlreadyMergedError`
- `test_check_raises_for_need_rebase_branch` - NEED_REBASE status raises `BranchNeedsRebaseError`
- `test_check_passes_for_need_upgrade_rebase_branch` - NEED_UPGRADE_REBASE status passes
- `test_check_passes_for_deleting_branch` - DELETING status passes

---

## Verification

```bash
uv run pytest backend/tests/unit/branch/test_status_checker.py -v
uv run pytest backend/tests/component/api/test_40_schema.py -v -k "merged or rebase"
uv run pytest backend/tests/component/api/test_11_artifact.py -v -k "merged or rebase"
```
