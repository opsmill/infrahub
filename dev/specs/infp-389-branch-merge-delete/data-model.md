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

## New Workflow

### GIT_REPOSITORIES_DELETE_BRANCH (workflows/catalogue.py)

No new Pydantic model. The workflow passes parameters directly as kwargs.

```python
GIT_REPOSITORIES_DELETE_BRANCH = WorkflowDefinition(
    name="git-repositories-delete-branch",
    type=WorkflowType.CORE,
    module="infrahub.git.tasks",
    function="delete_git_branch",
)
```

The `delete_git_branch(branch: str)` flow fetches all `CoreRepository` nodes and fans out to one `git_branch_delete` task per repo. No typed payload model — repository identity is passed as individual kwargs (`repository_id`, `repository_name`, `repository_location`).

---

## GraphQL Mutation Change (US4 — pending)

### BranchDelete (graphql/mutations/branch.py)

A new `BranchDeleteInput` type replaces `BranchNameInput` for the `data` argument (so `BranchNameInput` remains unchanged for other mutations that use it):

```graphql
input BranchDeleteInput {
  name: String
  delete_from_git: Boolean   # NEW: override global config; null/false = use global config
}

BranchDelete(
  data: BranchDeleteInput!   # was BranchNameInput
  context: ContextInput
  wait_until_completion: Boolean
): BranchDeleteResult
```

This is backward-compatible: `delete_from_git` defaults to `false`.

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
