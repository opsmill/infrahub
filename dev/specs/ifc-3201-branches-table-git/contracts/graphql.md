# Contract: GraphQL reads

**Feature**: [../spec.md](../spec.md)

**No backend change.** The list sends two documents, both owned by the `branch-git-status` entity: one repository list, then one `InfrahubRepositoryBranchStatus` read per repository. Neither request carries a branch context, so both go to `/graphql`, which reads the default branch; the status rows name their own branch. Paths are relative to `frontend/app/src/`.

## 1. Repository list, once

Defined in `entities/branch-git-status/api/get-branch-git-repositories-from-api.ts`:

```graphql
query GET_BRANCH_GIT_REPOSITORIES($limit: Int!, $offset: Int!) {
  CoreGenericRepository(
    limit: $limit
    offset: $offset
    order: { by: [{ field: "name__value", direction: ASC }] }
  ) {
    count
    edges { node { id __typename name { value } } }
  }
}
```

| Aspect | Value |
|---|---|
| Entry point | `entities/branch-git-status/ui/queries/get-branch-git-repositories.query.ts::getBranchGitRepositoriesQueryOptions(params)`, run by `useGetBranchGitStatuses` through `useQuery` |
| Variables | `{ limit: 500, offset: 0 }` |
| Query key | `branchGitStatusQueryKeys.repositories(params)`, that is `["branch-git-status", "repositories", { limit, offset }]` |
| Mapping | `toBranchGitRepositoryPage`: `kind` from `__typename`, `isReadOnly` for `CoreReadOnlyRepository` |
| Cut list | `count > repositories.length`: every row reads "Could not load repositories" |
| Retry | none: the app query client turns retries off |

## 2. Status, once per repository

Defined in `entities/branch-git-status/api/get-repository-branch-status-from-api.ts`:

```graphql
query GET_REPOSITORY_BRANCH_STATUS($id: String!, $limit: Int!) {
  InfrahubRepositoryBranchStatus(id: $id, limit: $limit) {
    count
    edges {
      node {
        name { value }
        commit { value }
        sync_status { value label color description }
      }
    }
  }
}
```

| Aspect | Value |
|---|---|
| Entry point | `entities/branch-git-status/ui/queries/get-repository-branch-status.query.ts::getRepositoryBranchStatusQueryOptions(params)`, run by `useGetBranchGitStatuses` through `useQueries`, only after the repository list loaded and was not cut |
| Variables | `{ id: <repository id>, limit: 500 }` (use-case params `{ repositoryId, limit }`) |
| Query key | `branchGitStatusQueryKeys.repositoryBranchStatus(params)`, that is `["branch-git-status", "repository-branch-status", { repositoryId, limit }]` |
| Row set | read/write repositories: branches with Sync with Git on; read-only repositories: every branch; merged, deleting and global branches excluded |
| Freshness | `staleTime: 60_000`; `refetchInterval`: every 10 s while any row of that repository is `syncing`, every 60 s after a failed read, none after a permission denial |
| Retry | none |
| Requests | 1 + R per page load (R = number of repositories), none when more branches load on scroll |

Branch creation, deletion, merge, rebase and the list's reload button invalidate `branchGitStatusQueryKeys.all`.

## Errors

Both fetchers pass a no-op `processErrorMessage` in the request context, so a failure shows in the cells and the shared client shows no toast. Both use cases wrap failures with `toBranchGitStatusError`:

| Response | Use-case result | Table cells |
|---|---|---|
| data | the mapped page | status per branch: pill, "+N more", Git state; or an empty text |
| `PERMISSION_DENIED` on every GraphQL error (`hasOnlyThrownCatalogueCode`) | throws `BranchGitStatusError` with `code: "PERMISSION_DENIED"` | list denied, or every status read denied: "No permission" on every row. One denied status read: the other repositories show, plus "1 repository could not be loaded" with "`<repository>`: No permission" in its tooltip |
| any other error | throws `BranchGitStatusError` with `code: "UNKNOWN"` and the message | list failed: "Could not load repositories" on every row, message in the tooltip and `sr-only` text. One failed status read: the other repositories show, plus the "could not be loaded" notice with "`<repository>`: `<message>`" |

A result holding `data` stays `ok` when a background refetch fails.

## Follow-up: 2 requests

A `repository_ids` list argument on `InfrahubRepositoryBranchStatus` collapses 1 + R to 2 requests without touching cells or rules. Aliasing one status field per repository into one document returns HTTP 500 today (research R14).
