# Phase 3: Git Branch Deletion Workflow

**Status:** ✅ Done
**Priority:** P2
**Requirements:** FR-005, FR-007, FR-010, FR-013
**Depends on:** Phase 1

---

## Goal

When an Infrahub branch with `sync_with_git=True` is deleted and `delete_git_branch_after_merge=True`, delete the corresponding branch from all synced Git repositories. Runs asynchronously — per-repo failures are logged but never block the Infrahub branch deletion (FR-013).

---

## Checklist

- [x] Add `origin_has_branch(branch_name)` to `InfrahubRepositoryBase`
- [x] Add `delete_remote_branch(branch_name)` to `InfrahubRepositoryBase`
- [x] Add `GIT_REPOSITORIES_DELETE_BRANCH` workflow definition to catalogue
- [x] Implement `delete_git_branch()` flow + `git_branch_delete` task in `git/tasks.py`
- [x] Update `delete_branch()` to trigger git deletion when config enabled
- [x] Write unit/component/functional tests

---

## Implementation

### 3.1 Add `origin_has_branch` to InfrahubRepositoryBase

**File:** `backend/infrahub/git/base.py`

```python
def origin_has_branch(self, branch_name: str) -> bool:
    """Return True if branch_name exists as a remote branch on origin."""
    return branch_name in self.get_branches_from_remote()
```

`get_branches_from_remote()` already strips the `origin/` prefix from keys, so a plain equality check is correct.

### 3.2 Add `delete_remote_branch` to InfrahubRepositoryBase

**File:** `backend/infrahub/git/base.py`

```python
async def delete_remote_branch(self, branch_name: str) -> None:
    """Delete branch_name from origin and remove the local tracking ref."""
    if not self.has_origin:
        return
    repo = self.get_git_repo_main()
    repo.git.push("origin", "--delete", branch_name)
    # Remove local branch if it exists (non-fatal if absent)
    local_branches = self.get_branches_from_local(include_worktree=False)
    if branch_name in local_branches:
        repo.delete_head(branch_name, force=True)
```

### 3.3 New workflow definition

**File:** `backend/infrahub/workflows/catalogue.py`

```python
GIT_REPOSITORIES_DELETE_BRANCH = WorkflowDefinition(
    name="git-repositories-delete-branch",
    type=WorkflowType.CORE,
    module="infrahub.git.tasks",
    function="delete_git_branch",
)
```

### 3.4 Git deletion flow + task

**File:** `backend/infrahub/git/tasks.py`

```python
@flow(name="git-repositories-delete-branch", flow_run_name="Delete git branch '{branch}'")
async def delete_git_branch(branch: str) -> None:
    """Fan out branch deletion across all CoreRepository instances."""
    client = get_client()
    repositories: list[CoreRepository] = await client.filters(kind=CoreRepository)
    batch = await client.create_batch()
    for repository in repositories:
        batch.add(
            task=git_branch_delete,
            client=client,
            branch=branch,
            repository_name=repository.name.value,
            repository_id=repository.id,
            repository_location=repository.location.value,
        )
    async for _, _ in batch.execute():
        pass


@task(  # type: ignore[arg-type]
    name="git-branch-delete",
    task_run_name="Delete branch '{branch}' in repository {repository_name}",
    cache_policy=NONE,
)
async def git_branch_delete(
    client: InfrahubClient,
    branch: str,
    repository_id: str,
    repository_name: str,
    repository_location: str,
) -> None:
    log = get_run_logger()
    repo = await InfrahubRepository.init(
        id=repository_id, name=repository_name, location=repository_location, client=client
    )
    if not repo.origin_has_branch(branch):
        return
    async with lock.registry.get(name=repository_name, namespace="repository"):
        try:
            await repo.delete_remote_branch(branch_name=branch)
        except Exception:
            # Log per-repo failure; do not re-raise (FR-007, FR-010)
            log.exception(
                f"Failed to delete Git branch '{branch}' from repository '{repository_name}'"
            )
```

Note: `origin_has_branch` is a synchronous method — do not use `await`.

### 3.5 Update `delete_branch()` to trigger git deletion

**File:** `backend/infrahub/core/branch/tasks.py`

After the existing `BranchDeletedEvent` submission:

```python
should_delete_git = config.SETTINGS.git.delete_git_branch_after_merge and obj.sync_with_git
if should_delete_git:
    await get_workflow().submit_workflow(
        workflow=GIT_REPOSITORIES_DELETE_BRANCH,
        context=context,
        parameters={"branch": branch},
    )
```

`obj.sync_with_git` is the branch object already fetched earlier in `delete_branch()` — no extra DB call needed.

---

## Tests

**Component tests:** `backend/tests/component/git/test_delete_git_branch.py`

- `test_has_branch_returns_true_for_existing_branch` — `origin_has_branch` returns True for real branch
- `test_has_branch_returns_false_for_missing_branch` — returns False for absent branch
- `test_delete_remote_branch_removes_branch_from_origin` — verifies deletion from upstream repo
- `test_has_branch_true_for_all_remote_branches` — parametrized over branch01/branch02

**Functional tests:** `backend/tests/functional/branch/test_delete_git_branch.py`

- `TestDeleteBranchGitWorkflow.test_git_deletion_triggered_when_config_enabled_and_sync_with_git`
- `TestDeleteBranchGitWorkflow.test_git_deletion_not_triggered_when_sync_with_git_false`
- `TestDeleteBranchGitWorkflow.test_git_deletion_not_triggered_when_config_disabled`

**Verification:**

```bash
uv run pytest backend/tests/component/git/test_delete_git_branch.py -v
uv run pytest backend/tests/functional/branch/test_delete_git_branch.py -v
```
