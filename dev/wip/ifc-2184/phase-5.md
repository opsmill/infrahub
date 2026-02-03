# Phase 5: REST API Validation

**Reference:** [dev/specs/2026-01-branch-freeze.md](../../specs/2026-01-branch-freeze.md)

**Status:** ✅ Complete

---

## Checklist

- [x] Create reusable `CheckBranchStatus` validator class (`backend/infrahub/api/validators.py`)
- [x] Block schema loading on merged branches (`backend/infrahub/api/schema.py`)
- [x] Block artifact generation on merged branches (`backend/infrahub/api/artifact.py`)
- [x] Extend functional tests (`backend/tests/functional/branch/test_branch_merged.py`)

---

## Implementation

### 5.1 Create reusable validator class

**New file:** `backend/infrahub/api/validators.py`

A reusable validator class that combines both `need_rebase` and `merged` status checks:

```python
from infrahub.core.branch.merged_status import check_merged_status
from infrahub.core.branch.needs_rebase_status import check_need_rebase_status
from infrahub.core.branch import Branch


class CheckBranchStatus:
    def __init__(self, branch: Branch):
        self.branch = branch

    def check(self):
        check_need_rebase_status(branch=self.branch)
        check_merged_status(branch=self.branch)
```

### 5.2 Block schema loading on merged branches

**File:** `backend/infrahub/api/schema.py:323`

```python
from infrahub.api.validators import CheckBranchStatus

# In load_schema function:
try:
    CheckBranchStatus(branch=branch).check()
except ValueError as err:
    raise SchemaNotValidError(message=str(err)) from err
```

### 5.3 Block artifact generation on merged branches

**File:** `backend/infrahub/api/artifact.py:77`

```python
from infrahub.api.validators import CheckBranchStatus

# In generate_artifact function:
try:
    CheckBranchStatus(branch=branch_params.branch).check()
except ValueError as err:
    raise ValidationError(input_value=str(err)) from err
```

---

## Tests

**Component tests:** `backend/tests/component/api/test_40_schema.py` and `backend/tests/component/api/test_11_artifact.py`

- `test_schema_load_blocked_on_merged_branch` - verifies 422 status code for merged branch
- `test_schema_load_blocked_on_need_rebase_branch` - verifies 422 status code for need_rebase branch
- `test_artifact_generate_blocked_on_merged_branch` - verifies 422 status code for merged branch
- `test_artifact_generate_blocked_on_need_rebase_branch` - verifies 422 status code for need_rebase branch

**Note:** `SchemaNotValidError` and `ValidationError` both return HTTP 422 (see `backend/infrahub/api/exceptions.py` and `backend/infrahub/exceptions.py`).

---

## Verification

```bash
uv run pytest backend/tests/component/api/test_40_schema.py -v -k "merged or rebase"
uv run pytest backend/tests/component/api/test_11_artifact.py -v -k "merged or rebase"
```
