# Delete Branch After Merge — Implementation Plan

## Summary

Add optional automatic branch deletion after merge. Both Infrahub branch deletion and Git branch deletion default to disabled (opt-in). Reuses existing `BRANCH_DELETE` workflow and adds a new `GIT_REPOSITORIES_DELETE_BRANCH` workflow.

**Spec**: [dev/specs/infp-389-branch-merge-delete/spec.md](../../specs/infp-389-branch-merge-delete/spec.md)
**Jira**: INFP-389
**Scope**: Backend only

---

## Implementation Progress

| Phase | Description                             | Priority | Status      | Tests                |
|-------|-----------------------------------------|----------|-------------|----------------------|
| 1     | Configuration settings                  | P1       | ✅ Done     | 3 unit tests         |
| 2     | Auto-delete Infrahub branch after merge | P1       | ✅ Done     | 4 functional tests   |
| 3     | Git branch deletion workflow            | P2       | ⬜ Todo     | 3 unit tests         |
| 4     | Manual delete with Git option           | P3       | ⬜ Todo     | 2 unit tests         |

**Total Tests:** 12 tests (5 unit + 4 functional + 3 unit)

---

## Critical Files

| Component              | File                                                       |
|------------------------|------------------------------------------------------------|
| Config                 | `backend/infrahub/config.py`                               |
| Branch merge task      | `backend/infrahub/core/branch/tasks.py`                    |
| Proposed change merge  | `backend/infrahub/proposed_change/tasks.py`                |
| Git deletion task      | `backend/infrahub/git/tasks.py`                            |
| Workflow catalogue     | `backend/infrahub/workflows/catalogue.py`                  |
| BranchDelete mutation  | `backend/infrahub/graphql/mutations/branch.py`             |

---

## Full Verification

```bash
# All new tests
uv run pytest backend/tests/unit/test_config.py -v -k "delete_branch"
uv run pytest backend/tests/unit/git/test_delete_git_branch.py -v
uv run pytest backend/tests/unit/graphql/mutations/test_branch_delete.py -v
uv run pytest backend/tests/functional/branch/test_branch_delete_after_merge.py -v

# Full suite
uv run invoke backend.test-unit
uv run invoke format && uv run invoke lint
```

### Manual Test Flow

1. Set only `delete_git_branch_after_merge = true` (leave `delete_branch_after_merge = false`), restart — verify startup fails with a clear validation error
2. Set `delete_branch_after_merge = true` in `infrahub.toml`, restart service
2. Create a branch, make a change, merge via `BranchMerge` GraphQL mutation
3. Verify branch no longer appears in branch list
4. Repeat via proposed change merge — same result
5. Set `delete_git_branch_after_merge = true` as well, merge a Git-synced branch
6. Verify branch deleted from Git repositories; per-repo failures appear in repo task logs
