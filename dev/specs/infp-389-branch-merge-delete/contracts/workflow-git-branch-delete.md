# Contract: GIT_REPOSITORY_DELETE_BRANCH Workflow

**User Story**: US3 (Automatic Git Branch Deletion)
**Type**: Internal Prefect Workflow
**Change**: New workflow definition

---

## Workflow Definition

```python
GIT_REPOSITORY_DELETE_BRANCH = WorkflowDefinition(
    name="git-repository-delete-branch",
    type=WorkflowType.INTERNAL,
    module="infrahub.git.tasks",
    function="delete_git_repository_branch",
)
```

## Task Signature

```python
@task(name="git-repository-delete-branch")
async def delete_git_repository_branch(model: GitRepositoryDeleteBranch) -> None:
    """
    Delete a branch from a single Git repository.
    Failures are logged but do not propagate — Infrahub branch deletion has already completed.
    """
```

## Input Model: GitRepositoryDeleteBranch

```python
class GitRepositoryDeleteBranch(BaseModel):
    repository_id: str       # UUID of the CoreRepository node
    repository_name: str     # Human-readable name (for logging)
    repository_kind: str     # "CoreRepository" or "CoreReadOnlyRepository"
    branch_name: str         # Name of the branch to delete
    default_branch: str | None  # Git default branch (guards against deleting main/master)
    context: InfrahubContext
```

## Behavior

1. Initialize `InfrahubRepository` for the given `repository_id`
2. Call `repo.delete_branch_in_git(branch_name=branch_name)`
   - Remove branch worktree: `<repos_dir>/<repo_name>/branches/<branch_name>/`
   - Delete local Git branch ref
   - Push `--delete` to `origin/<branch_name>`
3. On any exception: `log.error(...)` with repository name and exception message; return without re-raising
4. On success: log info confirming deletion

## Error Handling

| Error | Action |
|-------|--------|
| Branch not found locally | Log warning, skip (idempotent) |
| Remote push failure | Log error with repo name, return |
| Permission error | Log error with repo name, return |
| Any other exception | Log error with repo name, return |

## Guard: Default Branch Protection

If `branch_name == default_branch` or `branch_name == "main"` or `branch_name == "master"`, raise `ValidationError` before any deletion attempt. This prevents accidental deletion of the default Git branch.

## Triggered By

`delete_branch()` task in `backend/infrahub/core/branch/tasks.py`, once per `CoreRepository` that has `sync_with_git=true` for the deleted branch.

**Prerequisite condition** (auto-delete path): both `config.SETTINGS.main.delete_branch_after_merge` and `config.SETTINGS.git.delete_git_branch_after_merge` must be `True`. The `delete_git_branch_after_merge` setting has no effect on its own — it is only evaluated inside the `delete_branch()` flow, which is only reached when `delete_branch_after_merge` triggered the deletion.

## Notes

- `CoreReadOnlyRepository` branches are not deleted (read-only repos track upstream; we don't own the branches)
- Task is submitted via `submit_workflow` (fire-and-forget) from `delete_branch()`
- One task submission per repository (not batched across repos, consistent with `GIT_REPOSITORIES_MERGE` pattern)
