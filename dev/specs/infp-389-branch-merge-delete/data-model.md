# Data Model: Delete Branch After Merge

**Branch**: `infp-389-branch-merge-delete` | **Date**: 2026-03-19

## Overview

This feature adds **no new schema nodes or relationships**. The implementation is purely configuration-driven, operating on existing `Branch`, `CoreRepository`, and `CoreReadOnlyRepository` nodes.

Changes are confined to:
- Application configuration (new config fields)
- Task/workflow payloads (new Pydantic model)
- GraphQL mutation signature (new optional argument)
- REST API config response (new fields surfaced)

---

## Existing Entities Used (No Modification)

### Branch (StandardNode)

Location: `backend/infrahub/core/branch/models.py`

| Field | Type | Relevance |
|-------|------|-----------|
| `name` | `str` | Used to identify branch in deletion workflows |
| `status` | `BranchStatus` | `MERGED` status is the trigger condition for auto-delete |
| `sync_with_git` | `bool` | Guards whether Git deletion is attempted |
| `is_default` | `bool` | Prevents deletion (existing guard) |
| `is_global` | `bool` | Prevents deletion (existing guard) |

**No fields added to Branch.**

### CoreRepository / CoreReadOnlyRepository

Location: `backend/infrahub/core/protocols.py` (generated)

Used to enumerate which repositories are synced to a given branch, when building the list of `GIT_REPOSITORY_DELETE_BRANCH` submissions.

**No fields added to repository nodes.**

---

## New Configuration Fields

These are application-level settings, not graph schema entities.

### MainSettings (config.py)

```python
delete_branch_after_merge: bool = Field(
    default=False,
    description="When enabled, branches are automatically deleted from Infrahub after a successful merge.",
)
```

Environment variable: `INFRAHUB_DELETE_BRANCH_AFTER_MERGE`
Config file key: `[main] delete_branch_after_merge = false`

### GitSettings (config.py)

```python
delete_git_branch_after_merge: bool = Field(
    default=False,
    description="When enabled, the Git branch is automatically deleted from linked repositories after the Infrahub branch is deleted following a merge.",
)
```

Environment variable: `INFRAHUB_GIT_DELETE_GIT_BRANCH_AFTER_MERGE`
Config file key: `[git] delete_git_branch_after_merge = false`

---

## New Workflow Payload Model

### GitRepositoryDeleteBranch (git/models.py)

New Pydantic model for the `GIT_REPOSITORY_DELETE_BRANCH` workflow.

```python
class GitRepositoryDeleteBranch(BaseModel):
    """Delete a branch from a Git repository after Infrahub branch deletion."""

    repository_id: str = Field(..., description="The unique ID of the Repository")
    repository_name: str = Field(..., description="The name of the repository")
    repository_kind: str = Field(..., description="The kind of the repository")
    branch_name: str = Field(..., description="The name of the branch to delete")
    default_branch: str | None = Field(default=None, description="The default branch in Git")
    context: InfrahubContext = Field(..., description="The context of the task")
```

---

## GraphQL Mutation Change

### BranchDelete (graphql/mutations/branch.py)

New optional argument added to the existing mutation:

```graphql
BranchDelete(
  data: BranchNameInput!
  context: ContextInput
  wait_until_completion: Boolean
  delete_git_branch: Boolean   # NEW: override global config; null = use global config
): BranchDeleteResult
```

This is backward-compatible (optional argument, defaults to `null`).

---

## REST Config Response Change

The `GET /api/config` endpoint will include two new fields in its response so the frontend can conditionally render the Git deletion checkbox:

```json
{
  "main": {
    "delete_branch_after_merge": false
  },
  "git": {
    "delete_git_branch_after_merge": false
  }
}
```

Location of REST config model: `backend/infrahub/api/config.py` (or equivalent config response schema).
