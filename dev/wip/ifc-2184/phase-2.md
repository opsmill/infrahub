# Phase 2: GraphQL Middleware

**Reference:** [dev/specs/2026-01-branch-freeze.md](../../specs/2026-01-branch-freeze.md)

---

## Implementation

**File:** `backend/infrahub/graphql/middleware.py`

1. Import `check_merged_status`
2. Add constant: `ALLOWED_MUTATIONS_ON_MERGED_BRANCH = ["BranchDelete"]`
3. Add merged status check in existing middleware function

```python
from infrahub.core.branch.merged_status import check_merged_status

ALLOWED_MUTATIONS_ON_NEED_REBASE_BRANCH = ["BranchRebase", "BranchDelete", "BranchCreate", "ProposedChangeCreate"]
ALLOWED_MUTATIONS_ON_MERGED_BRANCH = ["BranchDelete"]  # Add this


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

## Tests

**Extend:** `backend/tests/unit/graphql/test_middleware.py` or create new test file

```python
import pytest
from infrahub.core.branch.enums import BranchStatus


async def test_middleware_blocks_mutation_on_merged_branch(db, default_branch, client):
    """Test that mutations are blocked on merged branches."""
    branch = await create_branch(db=db, name="test-merged")
    branch.status = BranchStatus.MERGED
    await branch.save(db=db)

    # Attempt a mutation - should fail
    result = await client.execute(
        query=SOME_MUTATION,
        context={"branch": branch}
    )
    assert "has been merged and is read-only" in str(result.errors)


async def test_middleware_allows_branch_delete_on_merged_branch(db, default_branch, client):
    """Test that BranchDelete is allowed on merged branches."""
    branch = await create_branch(db=db, name="test-merged")
    branch.status = BranchStatus.MERGED
    await branch.save(db=db)

    # BranchDelete should succeed
    result = await client.execute(
        query=BRANCH_DELETE_MUTATION,
        variables={"name": "test-merged"}
    )
    assert result.errors is None
```

---

## Verification

```bash
uv run pytest backend/tests/unit/graphql/test_middleware.py -v -k merged
```
