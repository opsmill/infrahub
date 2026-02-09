# Phase 2: GraphQL Middleware

**Reference:** [dev/specs/2026-01-branch-freeze.md](../../specs/2026-01-branch-freeze.md)

**Status:** ✅ Complete

---

## Checklist

- [x] Import `BranchStatusChecker` in middleware.py
- [x] Add `ALLOWED_MUTATIONS_ON_MERGED_BRANCH = ["BranchDelete"]` constant
- [x] Add merged status check in `raise_on_mutation_for_branch_status` function

---

## Implementation

**File:** `backend/infrahub/graphql/middleware.py`

1. Import `BranchStatusChecker` from unified status checker
2. Add constant: `ALLOWED_MUTATIONS_ON_MERGED_BRANCH = ["BranchDelete"]`
3. Use instance methods for status checks in `raise_on_mutation_for_branch_status` function

```python
from infrahub.branch.status_checker import BranchStatusChecker

ALLOWED_MUTATIONS_ON_NEED_REBASE_BRANCH = ["BranchRebase", "BranchDelete", "BranchCreate", "ProposedChangeCreate"]
ALLOWED_MUTATIONS_ON_MERGED_BRANCH = ["BranchDelete"]


def raise_on_mutation_for_branch_status(next, root, info, **kwargs):  # type: ignore  # noqa
    if info.operation.operation.value == "mutation":
        mutation_name = info.operation.selection_set.selections[0].name.value
        brach_status_checker = BranchStatusChecker()
        if mutation_name not in ALLOWED_MUTATIONS_ON_NEED_REBASE_BRANCH:
            brach_status_checker.check_needs_rebase_status(branch=info.context.branch)
        if mutation_name not in ALLOWED_MUTATIONS_ON_MERGED_BRANCH:
            brach_status_checker.check_merge_status(branch=info.context.branch)

    return next(root, info, **kwargs)

```
