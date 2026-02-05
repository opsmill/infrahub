# Phase 2: GraphQL Middleware

**Reference:** [dev/specs/2026-01-branch-freeze.md](../../specs/2026-01-branch-freeze.md)

**Status:** ✅ Complete

---

## Checklist

- [x] Import `check_merged_status` in middleware.py
- [x] Add `ALLOWED_MUTATIONS_ON_MERGED_BRANCH = ["BranchDelete"]` constant
- [x] Add merged status check in `raise_on_mutation_for_branch_status` function

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


def raise_on_mutation_for_branch_status(next, root, info, **kwargs):
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
