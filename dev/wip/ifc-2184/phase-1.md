# Phase 1: Core Enum and Status Check

**Reference:** [dev/specs/2026-01-branch-freeze.md](../../specs/2026-01-branch-freeze.md)

**Status:** ✅ Complete

---

## Checklist

- [x] Add MERGED status to BranchStatus enum (`backend/infrahub/core/branch/enums.py`)
- [x] Create merged status check module (`backend/infrahub/core/branch/merged_status.py`)
- [x] Create unit tests (`backend/tests/unit/core/branch/test_merged_status.py`) - 5 tests

---

## Implementation

### 1.1 Add MERGED status to BranchStatus enum

**File:** `backend/infrahub/core/branch/enums.py`

```python
class BranchStatus(InfrahubStringEnum):
    OPEN = "OPEN"
    NEED_REBASE = "NEED_REBASE"
    NEED_UPGRADE_REBASE = "NEED_UPGRADE_REBASE"
    DELETING = "DELETING"
    MERGED = "MERGED"  # Add this
```

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

## Tests

**New file:** `backend/tests/unit/core/branch/test_merged_status.py`

```python
import pytest
from infrahub.core.branch.enums import BranchStatus
from infrahub.core.branch.merged_status import check_merged_status, raise_merged_error


def test_raise_merged_error():
    with pytest.raises(ValueError, match="has been merged and is read-only"):
        raise_merged_error("test-branch")


def test_check_merged_status_raises_for_merged_branch(mock_branch):
    mock_branch.status = BranchStatus.MERGED
    mock_branch.name = "test-branch"
    with pytest.raises(ValueError):
        check_merged_status(mock_branch)


def test_check_merged_status_passes_for_open_branch(mock_branch):
    mock_branch.status = BranchStatus.OPEN
    check_merged_status(mock_branch)  # Should not raise
```

---

## Verification

```bash
uv run pytest backend/tests/unit/core/branch/test_merged_status.py -v
```
