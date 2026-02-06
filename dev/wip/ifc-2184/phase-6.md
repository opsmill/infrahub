# Phase 6: Permission System Integration

**Reference:** [dev/specs/2026-01-branch-freeze.md](../../specs/2026-01-branch-freeze.md)

**Status:** ✅ Complete

---

## Checklist

- [x] Update `get_permission_report()` to return DENY for non-view actions on merged branches AND branches needing rebase (`backend/infrahub/permissions/report.py`)
- [x] Super admin bypass preserved (checked before merged status)
- [x] Branch delete handled via middleware `ALLOWED_MUTATIONS_ON_MERGED_BRANCH`
- [x] Create unit tests (`backend/tests/unit/permissions/test_merged_branch_permissions.py`) - 10 tests

**Note:** Implementation simplified from original plan - Branch delete is handled via GraphQL middleware allowlist rather than permission system check for `InfrahubKind.BRANCH`, since branches are deleted via GraphQL mutation not REST API. The permission check now covers both `MERGED` and `NEED_REBASE` statuses for consistent behavior.

---

## Implementation

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

---

## Tests

**New file:** `backend/tests/unit/permissions/test_merged_branch_permissions.py`

```python
import pytest
from infrahub.core.branch.enums import BranchStatus
from infrahub.permissions.constants import BranchRelativePermissionDecision


def test_permission_denies_create_on_merged_branch(permission_manager, mock_branch, mock_node):
    """Test that create permission is DENY on merged branch."""
    mock_branch.status = BranchStatus.MERGED

    result = get_permission_report(
        permission_manager=permission_manager,
        branch=mock_branch,
        node=mock_node,
        action="create",
        global_permission_report={...}
    )
    assert result == BranchRelativePermissionDecision.DENY


def test_permission_denies_update_on_merged_branch(permission_manager, mock_branch, mock_node):
    """Test that update permission is DENY on merged branch."""
    mock_branch.status = BranchStatus.MERGED

    result = get_permission_report(
        permission_manager=permission_manager,
        branch=mock_branch,
        node=mock_node,
        action="update",
        global_permission_report={...}
    )
    assert result == BranchRelativePermissionDecision.DENY


def test_permission_denies_delete_on_merged_branch(permission_manager, mock_branch, mock_node):
    """Test that delete permission is DENY on merged branch for non-Branch kinds."""
    mock_branch.status = BranchStatus.MERGED

    result = get_permission_report(
        permission_manager=permission_manager,
        branch=mock_branch,
        node=mock_node,  # Not a Branch kind
        action="delete",
        global_permission_report={...}
    )
    assert result == BranchRelativePermissionDecision.DENY


def test_permission_allows_view_on_merged_branch(permission_manager, mock_branch, mock_node):
    """Test that view permission is allowed on merged branch."""
    mock_branch.status = BranchStatus.MERGED

    result = get_permission_report(
        permission_manager=permission_manager,
        branch=mock_branch,
        node=mock_node,
        action="view",
        global_permission_report={...}
    )
    # Should proceed to normal permission logic, not auto-DENY
    assert result != BranchRelativePermissionDecision.DENY


def test_permission_denies_mutations_on_need_rebase_branch(permission_manager, mock_branch, mock_node):
    """Test that mutations are denied on branches needing rebase."""
    mock_branch.status = BranchStatus.NEED_REBASE

    result = get_permission_report(
        permission_manager=permission_manager,
        branch=mock_branch,
        node=mock_node,
        action="create",
        global_permission_report={...}
    )
    assert result == BranchRelativePermissionDecision.DENY
```

---

## Verification

```bash
uv run pytest backend/tests/unit/permissions/test_merged_branch_permissions.py -v
```

---

## Full Verification (All Phases)

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
