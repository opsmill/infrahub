# Contract: BranchDelete GraphQL Mutation (Modified)

**User Story**: US4 (Manual Branch Deletion with Git Option)
**Type**: GraphQL Mutation
**Change**: Switch `data` arg from `BranchNameInput` to new `BranchDeleteInput`; add `delete_from_git` field
**Status**: ⬜ Pending (US4 not yet implemented)

---

## New Input Type

```graphql
input BranchDeleteInput {
  name: String
  delete_from_git: Boolean   # null/false = use global config; true = force Git deletion
}
```

`BranchNameInput` is left unchanged (it is shared by `BranchRebase`, `BranchValidate`, and others).

## Mutation Signature

```graphql
mutation BranchDelete(
  $data: BranchDeleteInput!
  $context: ContextInput
  $waitUntilCompletion: Boolean
) {
  BranchDelete(
    data: $data
    context: $context
    wait_until_completion: $waitUntilCompletion
  ) {
    ok
    task {
      id
    }
  }
}
```

## Arguments

| Argument | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `data` | `BranchDeleteInput!` | Yes | — | Branch name + optional Git flag |
| `data.name` | `String` | Yes | — | Branch name to delete |
| `data.delete_from_git` | `Boolean` | No | false | Override Git deletion. `true` = force Git deletion regardless of global config. |
| `context` | `ContextInput` | No | null | External context |
| `wait_until_completion` | `Boolean` | No | true | Block until workflow completes |

## Return Type

```graphql
type BranchDeleteResult {
  ok: Boolean!
  task: TaskInfo   # Present only when wait_until_completion=false
}
```

## Behavior by `delete_from_git` value

| `delete_from_git` | Global `INFRAHUB_GIT_DELETE_GIT_BRANCH_AFTER_MERGE` | Git deletion happens? |
|-------------------|-----------------------------------------------------|----------------------|
| `null` / `false` | `false` | No |
| `null` / `false` | `true` | Yes |
| `true` | `false` | Yes (override) |
| `true` | `true` | Yes |

The backend condition: `should_delete_git = (config.SETTINGS.git.delete_git_branch_after_merge or delete_from_git) and obj.sync_with_git`

## Error Cases

- Branch is the default branch → `ValidationError: Unable to delete <name> it is the default branch.`
- Branch is global → `ValidationError: Unable to delete <name> this is an internal branch.`
- Branch not found → Standard GraphQL error

## Notes

- Backward-compatible: existing callers omitting `delete_git_branch` continue to work
- Git deletion failure does not cause mutation to return `ok: false`; it is logged to the task log
- The mutation passes `delete_from_git` to the `BRANCH_DELETE` workflow parameters
