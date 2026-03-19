# Contract: BranchDelete GraphQL Mutation (Modified)

**User Story**: US4 (Manual Branch Deletion with Git Option)
**Type**: GraphQL Mutation
**Change**: Extend existing mutation with optional `delete_git_branch` argument

---

## Mutation Signature

```graphql
mutation BranchDelete(
  $data: BranchNameInput!
  $context: ContextInput
  $waitUntilCompletion: Boolean
  $deleteGitBranch: Boolean
) {
  BranchDelete(
    data: $data
    context: $context
    wait_until_completion: $waitUntilCompletion
    delete_git_branch: $deleteGitBranch
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
| `data` | `BranchNameInput!` | Yes | — | Branch name to delete |
| `context` | `ContextInput` | No | null | External context |
| `wait_until_completion` | `Boolean` | No | true | Block until workflow completes |
| `delete_git_branch` | `Boolean` | No | null | Override Git deletion behavior. `null` = use global config. `true` = force Git deletion. `false` = skip Git deletion. |

## Return Type

```graphql
type BranchDeleteResult {
  ok: Boolean!
  task: TaskInfo   # Present only when wait_until_completion=false
}
```

## Behavior by `delete_git_branch` value

| `delete_git_branch` | Global `INFRAHUB_GIT_DELETE_GIT_BRANCH_AFTER_MERGE` | Git deletion happens? |
|---------------------|--------------------------------------------------|----------------------|
| `null` | `false` | No |
| `null` | `true` | Yes |
| `true` | `false` | Yes (override) |
| `true` | `true` | Yes |
| `false` | `false` | No |
| `false` | `true` | No (override) |

## Error Cases

- Branch is the default branch → `ValidationError: Unable to delete <name> it is the default branch.`
- Branch is global → `ValidationError: Unable to delete <name> this is an internal branch.`
- Branch not found → Standard GraphQL error

## Notes

- Backward-compatible: existing callers omitting `delete_git_branch` continue to work
- Git deletion failure does not cause mutation to return `ok: false`; it is logged to the task log
- The mutation passes `delete_git_branch` to the `BRANCH_DELETE` workflow parameters
