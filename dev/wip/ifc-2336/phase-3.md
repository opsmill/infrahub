# Phase 3: Git Branch Deletion Workflow

**Status:** ⬜ Todo
**Priority:** P2
**Requirements:** FR-005, FR-007, FR-010, FR-013
**Depends on:** Phase 1

---

## Goal

When an Infrahub branch with `sync_with_git=True` is deleted and `delete_git_branch_after_merge=True` (or `delete_from_git=True` on manual delete), delete the corresponding branch from all synced Git repositories. Runs asynchronously — per-repo failures are logged but never block the Infrahub branch deletion (FR-013).

---

## Checklist

- [ ] Add `has_branch(branch_name)` to `InfrahubRepositoryBase`
- [ ] Add `delete_remote_branch(branch_name)` to `InfrahubRepositoryBase`
- [ ] Add `GIT_REPOSITORIES_DELETE_BRANCH` workflow definition to catalogue
- [ ] Implement `delete_git_branch()` flow + `git_branch_delete` task in `git/tasks.py`
- [ ] Update `delete_branch()` to accept `delete_from_git` param and trigger git deletion
- [ ] Write unit tests

---

## Implementation

### 3.1 Add `has_branch` to InfrahubRepositoryBase

**File:** `backend/infrahub/git/base.py`

No branch-existence check currently exists. Add a method that checks remote refs (the authoritative source for what is pushed):

```python
def has_branch(self, branch_name: str) -> bool:
    """Return True if branch_name exists as a remote branch on origin."""
    remote_branches = self.get_branches_from_remote()
    return branch_name in remote_branches
```

`get_branches_from_remote()` already strips the `origin/` prefix from keys (base.py:491-509), so a plain equality check is correct.

### 3.2 Add `delete_remote_branch` to InfrahubRepositoryBase

**File:** `backend/infrahub/git/base.py`

No delete method currently exists. Add alongside `push()` / `fetch()`:

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

`repo.git.push("origin", "--delete", branch_name)` is the GitPython wrapper for `git push origin --delete <branch>`.

### 3.3 New workflow definition

**File:** `backend/infrahub/workflows/catalogue.py`

Add alongside the existing `GIT_REPOSITORIES_CREATE_BRANCH` definition:

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

Follow the `create_branch` / `git_branch_create` pattern in the same file — a `@flow` that fans out to a per-repo `@task` via a batch:

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
    if not repo.has_branch(branch):
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

Key notes:
- `log.exception(...)` captures the full traceback (matches `run_user_check` pattern in the same file).
- The `async with lock.registry.get(...)` prevents concurrent git operations on the same repo, consistent with `git_branch_create`.
- A missing branch is a silent no-op — the repo may never have had this Infrahub branch synced.

### 3.5 Update `delete_branch()` to trigger git deletion

**File:** `backend/infrahub/core/branch/tasks.py`

Update the flow signature:

```python
@flow(name="branch-delete", flow_run_name="Delete branch {branch}")
async def delete_branch(
    branch: str,
    context: InfrahubContext,
    delete_from_git: bool = False,
) -> None:
```

After the existing `BranchDeletedEvent` submission, add:

```python
from infrahub.config import get_settings
from infrahub.workflows.catalogue import GIT_REPOSITORIES_DELETE_BRANCH

settings = get_settings()
should_delete_git = (settings.main.delete_git_branch_after_merge or delete_from_git) and obj.sync_with_git
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

**New file:** `backend/tests/unit/git/test_delete_git_branch.py`

- `test_git_branch_deleted_from_all_repos` — mock repos that have the branch, assert `delete_remote_branch` called for each
- `test_git_branch_deletion_failure_logged_per_repo` — mock one repo to raise, assert `log.exception` called and other repos still processed
- `test_git_branch_deletion_skips_repos_without_branch` — repos where `has_branch` returns `False` should not call `delete_remote_branch`

**Verification:**

```bash
uv run pytest backend/tests/unit/git/test_delete_git_branch.py -v
```
