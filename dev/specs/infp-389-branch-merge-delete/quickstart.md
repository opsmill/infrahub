# Quickstart / Test Scenarios: Delete Branch After Merge

**Branch**: `infp-389-branch-merge-delete` | **Date**: 2026-03-19

These scenarios are derived from spec acceptance criteria. They serve as the manual verification checklist and as the basis for functional and E2E tests.

---

## US1: Global Configuration

### Scenario 1.1 — Default config: both settings disabled

**Setup**: Start Infrahub with no branch deletion settings in `infrahub.toml`.

**Steps**:
1. Merge any open branch
2. Check branch list

**Expected**: Branch still appears in branch list (status: MERGED). Nothing deleted automatically.

### Scenario 1.2 — Enable via config file

**Setup**: Add to `infrahub.toml`:
```toml
[main]
delete_branch_after_merge = true
```

**Steps**:
1. Restart Infrahub
2. Merge a branch

**Expected**: Branch disappears from branch list after merge completes.

### Scenario 1.3 — Enable via environment variable

**Setup**: Set `INFRAHUB_DELETE_BRANCH_AFTER_MERGE=true` before starting.

**Steps**:
1. Start Infrahub
2. Merge a branch

**Expected**: Branch is deleted after merge.

### Scenario 1.4 — Git deletion setting has no effect without main setting

**Setup**: `INFRAHUB_DELETE_BRANCH_AFTER_MERGE=false`, `INFRAHUB_GIT_DELETE_GIT_BRANCH_AFTER_MERGE=true`

**Steps**:
1. Merge a branch with `sync_with_git=true`

**Expected**: Branch stays in Infrahub (main auto-delete disabled). Git branch is NOT deleted (`delete_git_branch_after_merge` has no effect when `delete_branch_after_merge=false`).

---

## US2: Automatic Branch Deletion After Merge

### Scenario 2.1 — Standard branch merge with auto-delete enabled

**Setup**: `INFRAHUB_DELETE_BRANCH_AFTER_MERGE=true`

**Steps**:
1. Create branch `test-branch-001`
2. Make a change on the branch
3. Merge the branch (via `BranchMerge` mutation or UI)
4. Query branch list

**Expected**: `test-branch-001` no longer in branch list.

### Scenario 2.2 — Proposed change merge with auto-delete enabled

**Setup**: `INFRAHUB_DELETE_BRANCH_AFTER_MERGE=true`

**Steps**:
1. Create branch `test-branch-002`
2. Make a change on the branch
3. Create a proposed change for `test-branch-002`
4. Merge the proposed change
5. Query branch list

**Expected**: `test-branch-002` no longer in branch list.

### Scenario 2.3 — Auto-delete disabled: branch survives merge

**Setup**: `INFRAHUB_DELETE_BRANCH_AFTER_MERGE=false`

**Steps**:
1. Create branch `test-branch-003`
2. Merge the branch

**Expected**: `test-branch-003` still exists in branch list with status `MERGED`.

### Scenario 2.4 — Merge failure: branch not deleted

**Setup**: `INFRAHUB_DELETE_BRANCH_AFTER_MERGE=true`

**Steps**:
1. Create branch `test-branch-004`
2. Create a conflict on both `test-branch-004` and the default branch for the same node
3. Attempt to merge `test-branch-004` without resolving the conflict

**Expected**: Merge fails. `test-branch-004` still exists with status `OPEN`.

---

## US3: Automatic Git Branch Deletion After Merge

### Scenario 3.1 — Both settings enabled, synced repository

**Setup**: `INFRAHUB_DELETE_BRANCH_AFTER_MERGE=true`, `INFRAHUB_GIT_DELETE_GIT_BRANCH_AFTER_MERGE=true`
A `CoreRepository` is linked and has a branch named `test-branch-005`.

**Steps**:
1. Merge `test-branch-005` in Infrahub

**Expected**:
- `test-branch-005` deleted from Infrahub
- `test-branch-005` deleted from the linked Git repository (remote and local)

### Scenario 3.2 — Infrahub delete enabled, Git delete disabled

**Setup**: `INFRAHUB_DELETE_BRANCH_AFTER_MERGE=true`, `INFRAHUB_GIT_DELETE_GIT_BRANCH_AFTER_MERGE=false`

**Steps**:
1. Merge `test-branch-006` (synced with Git)

**Expected**:
- `test-branch-006` deleted from Infrahub
- Git branch `test-branch-006` still exists in the repository

### Scenario 3.3 — Git deletion fails: logged, Infrahub deletion proceeds

**Setup**: Both settings enabled. Git remote is configured with a read-only remote (or permission error simulated).

**Steps**:
1. Merge branch that is synced with Git

**Expected**:
- Infrahub branch is deleted
- Task log for the repository contains an error message mentioning the repository name
- No error surfaced to user for the merge/delete operation itself

### Scenario 3.4 — Multiple repositories, partial failure

**Setup**: Both settings enabled. Branch is synced with two repositories; one has a permission error.

**Steps**:
1. Merge the branch

**Expected**:
- Infrahub branch deleted
- Task log for the failing repository shows error
- The successful repository's Git branch is deleted (not rolled back)

---

## US4: Manual Branch Deletion with Git Option

### Scenario 4.1 — Delete button visible on merged branch

**Setup**: `INFRAHUB_DELETE_BRANCH_AFTER_MERGE=false`

**Steps**:
1. Merge a branch (it will remain as MERGED)
2. Navigate to branch detail page

**Expected**: Delete button is visible.

### Scenario 4.2 — Git delete checkbox visible when global setting disabled

**Setup**: `INFRAHUB_DELETE_BRANCH_AFTER_MERGE=false`, `INFRAHUB_GIT_DELETE_GIT_BRANCH_AFTER_MERGE=false`

**Steps**:
1. Navigate to a MERGED branch that has `sync_with_git=true`
2. Click Delete

**Expected**: Delete confirmation dialog shows a checkbox "Also delete from Git repository".

### Scenario 4.3 — Git delete checkbox hidden when global setting enabled

**Setup**: `INFRAHUB_GIT_DELETE_GIT_BRANCH_AFTER_MERGE=true`

**Steps**:
1. Navigate to a MERGED branch with `sync_with_git=true`
2. Click Delete

**Expected**: Delete confirmation dialog does NOT show the Git deletion checkbox (it will happen automatically regardless).

### Scenario 4.4 — Manual delete with Git option selected

**Setup**: `INFRAHUB_GIT_DELETE_GIT_BRANCH_AFTER_MERGE=false`

**Steps**:
1. Navigate to MERGED branch with `sync_with_git=true`
2. Click Delete, check "Also delete from Git repository"
3. Confirm

**Expected**: Both Infrahub branch and Git branch are deleted.

### Scenario 4.5 — Manual delete without Git option

**Steps**:
1. Navigate to MERGED branch with `sync_with_git=true`
2. Click Delete, leave checkbox unchecked
3. Confirm

**Expected**: Infrahub branch deleted. Git branch remains.

---

## Edge Cases

### Scenario E.1 — Already-deleted branch handled gracefully

**Steps**:
1. Manually delete a branch via API
2. Attempt to delete it again

**Expected**: Error handled gracefully (no crash, appropriate error message or no-op).

### Scenario E.2 — Branch associated with multiple proposed changes

**Setup**: Branch has two proposed changes; one is merged, one is still open.

**Steps**:
1. Merge the first proposed change (with auto-delete enabled)

**Expected**: Branch is NOT deleted (second proposed change still open). Branch only deleted after all proposed changes are resolved.

> **Note**: This edge case may require additional investigation during implementation. The current `BRANCH_CANCEL_PROPOSED_CHANGES` workflow is called as part of `merge_branch()`. Whether to gate deletion on "all PCs merged" vs "any PC merged" needs verification against actual behavior.
