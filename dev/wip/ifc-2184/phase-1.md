# Phase 1: Core Enum and Status Check

**Reference:** [dev/specs/2026-01-branch-freeze.md](../../specs/2026-01-branch-freeze.md)

**Status:** ✅ Complete

---

## Checklist

- [x] Add MERGED status to BranchStatus enum (`backend/infrahub/core/branch/enums.py`)
- [x] Create unit tests (`backend/tests/unit/core/branch/test_merged_status.py`) - 2 tests

**Note:** Status checking is consolidated in `BranchStatusChecker` class (see Phase 5). The standalone `merged_status.py` and `needs_rebase_status.py` modules were removed in favor of the unified checker class.

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

---

## Tests

**File:** `backend/tests/unit/core/branch/test_merged_status.py`

Tests use actual `Branch` objects (not mocks) for realistic validation. Tests now use `BranchStatusChecker().check_merge_status()` and `BranchAlreadyMergedError`:

```python
from infrahub.branch.status_checker import BranchStatusChecker
from infrahub.exceptions import BranchAlreadyMergedError
import pytest

from infrahub.core.branch import Branch
from infrahub.core.branch.enums import BranchStatus


def test_check_merged_status_raises_for_merged_branch() -> None:
    branch = Branch(name="merged-branch", status=BranchStatus.MERGED)

    with pytest.raises(BranchAlreadyMergedError, match=r"merged-branch.*has been merged and is read-only. No modifications are allowed"):
        BranchStatusChecker().check_merge_status(branch=branch)


@pytest.mark.parametrize(
    "status",
    [
        BranchStatus.OPEN,
        BranchStatus.NEED_REBASE,
        BranchStatus.DELETING,
        BranchStatus.NEED_UPGRADE_REBASE,
    ],
)
def test_check_merged_status_passes_for_non_merged_branch(status: BranchStatus) -> None:
    branch = Branch(name="test-branch", status=status)
    BranchStatusChecker().check_merge_status(branch=branch)
```

---

## Verification

```bash
uv run pytest backend/tests/unit/core/branch/test_merged_status.py -v
```
