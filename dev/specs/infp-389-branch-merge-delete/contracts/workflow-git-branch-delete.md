# Contract: GIT_REPOSITORIES_DELETE_BRANCH Workflow

**User Story**: US3 (Automatic Git Branch Deletion)
**Type**: Internal Prefect Workflow (fan-out flow)
**Change**: New workflow definition
**Status**: ✅ Implemented

---

## Workflow Definition

```python
GIT_REPOSITORIES_DELETE_BRANCH = WorkflowDefinition(
    name="git-repositories-delete-branch",
    type=WorkflowType.CORE,
    module="infrahub.git.tasks",
    function="delete_git_branch",
)
```

## Flow Signature

```python
@flow(name="git-repositories-delete-branch", flow_run_name="Delete git branch '{branch}'")
async def delete_git_branch(branch: str) -> None:
    """Fan out branch deletion across all CoreRepository instances."""
```

## Fan-out Task Signature

```python
@task(
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
```

## Behavior

1. `delete_git_branch` fetches all `CoreRepository` nodes via the SDK client
2. Creates a Prefect batch; adds one `git_branch_delete` task per repository
3. Each `git_branch_delete` task:
   a. Initializes `InfrahubRepository` for the given `repository_id`
   b. Calls `repo.origin_has_branch(branch)` — if `False`, returns early (idempotent)
   c. Acquires the repository lock (`lock.registry.get(name=repository_name, namespace="repository")`)
   d. Calls `await repo.delete_remote_branch(branch_name=branch)`
   e. On any exception: `log.exception(...)` with branch name and repository name; returns without re-raising

## New Repository Methods (InfrahubRepositoryBase)

```python
def origin_has_branch(self, branch_name: str) -> bool:
    """Return True if branch_name exists as a remote branch on origin."""
    return branch_name in self.get_branches_from_remote()

async def delete_remote_branch(self, branch_name: str) -> None:
    """Delete branch_name from origin and remove the local tracking ref."""
    if not self.has_origin:
        return
    repo = self.get_git_repo_main()
    repo.git.push("origin", "--delete", branch_name)
    local_branches = self.get_branches_from_local(include_worktree=False)
    if branch_name in local_branches:
        repo.delete_head(branch_name, force=True)
```

## Error Handling

| Error | Action |
|-------|--------|
| Branch absent on remote | `origin_has_branch` returns `False`; task returns early |
| Remote push failure | `log.exception(...)` with repo name; task returns |
| Permission error | `log.exception(...)` with repo name; task returns |
| Any other exception | `log.exception(...)` with repo name; task returns |

## Triggered By

`delete_branch()` flow in `backend/infrahub/core/branch/tasks.py`:

```python
should_delete_git = config.SETTINGS.git.delete_git_branch_after_merge and obj.sync_with_git
if should_delete_git:
    await get_workflow().submit_workflow(
        workflow=GIT_REPOSITORIES_DELETE_BRANCH,
        context=context,
        parameters={"branch": branch},
    )
```

**Prerequisite condition**: `config.SETTINGS.git.delete_git_branch_after_merge` must be `True` AND the branch must have `sync_with_git=True`. The structural dependency on `main.delete_branch_after_merge` is implicit — `delete_branch()` is only reached when the main setting triggered it (or via manual deletion in US4).

## Notes

- No typed payload model — parameters are passed as direct kwargs to the batch task
- `CoreReadOnlyRepository` nodes are also queried; `has_origin=False` check in `delete_remote_branch` makes those a no-op
- Worktree directories are NOT removed — only the remote branch and local tracking ref
