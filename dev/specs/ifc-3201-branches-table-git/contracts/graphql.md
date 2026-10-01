# Contract: GraphQL reads

**Feature**: [../spec.md](../spec.md)

**No backend change.** Since rework A (2026-10-01) the list reads two documents: #10779's repository list once, and the epic's `InfrahubRepositoryBranchStatus` once per repository (lifted from #10658). The list does not query `CoreGenericRepository` per branch.

## 1. Repository list, once

`entities/repository/ui/queries/get-branch-repositories.query.ts::useGetBranchRepositories({ branchName: <default branch>, syncWithGit: true })` (#10779), i.e. `GET_BRANCH_REPOSITORIES` over `CoreGenericRepository(limit: 500)`, sent on the default branch (taken from the branches provider by `is_default`). The list reads `id`, `name`, `kind` (`__typename`) and `isReadOnly` from it.

## 2. Status, once per repository

Defined in `entities/repository/api/get-repository-branch-status-from-api.ts` (lifted from #10658):

```graphql
query REPOSITORY_BRANCH_STATUS($id: String!, $limit: Int, $offset: Int, $name__value: String,
  $partial_match: Boolean, $status__value: BranchStatus, $order: MetadataOrderInput) {
  InfrahubRepositoryBranchStatus(id: $id, limit: $limit, offset: $offset, name__value: $name__value,
    partial_match: $partial_match, status__value: $status__value, order: $order) {
    count
    edges { node { name { value } is_default { value } commit { value }
      sync_status { value label color description } ref { value } } }
  }
}
```

| Aspect | Value |
|---|---|
| Entry point | `entities/repository/ui/queries/get-repository-branch-status.query.ts::getRepositoryBranchStatusQueryOptions(params)` (factory, no hook), run by `useBranchRepositorySummaries` through `useQueries` |
| Variables | `{ id: <repository id>, limit: 500 }` |
| Branch | the default branch, as the request's branch context; the rows name their own branch |
| Query key | `repositoryQueryKeys.branchStatus(params)`, i.e. `["repositories", "branch-status", { id, branchName, limit }]` (#10658's member name and shape on this base's `all`) |
| Row set | read/write repositories: `sync_with_git` branches only; read-only repositories: every branch; MERGED, DELETING and the global branch excluded |
| Freshness | `staleTime: 60_000`; `refetchInterval: 10_000` while any row's `sync_status.value === "syncing"` |
| Retry | none (`queryClient` default `retry: false`) |
| Requests | 1 + R per page load (16 on the dev stack), none on scroll |

## Result mapping (`domain/use-cases/get-repository-branch-status.ts::getRepositoryBranchStatus`)

| Response | Use-case result | Table cells |
|---|---|---|
| data | `{ rows, count }` (`count` ignored) | pivoted per branch: pill + "+N more", Git state roll-up; or an empty text |
| `PERMISSION_DENIED` (`hasThrownCatalogueCode`) | throws `RepositoryBranchStatusError` with `code: "PERMISSION_DENIED"` | "No permission" on every row |
| any other error | throws `RepositoryBranchStatusError` with `code: "UNKNOWN"` and the message | "Could not load repositories" on every row, message as tooltip and `sr-only` text |

A result holding `data` stays `ok` when a background refetch fails.

## Follow-up: 2 requests

A `repository_ids` list argument on `InfrahubRepositoryBranchStatus` collapses 1 + R to 2 requests without touching cells or rules. Aliasing one status field per repository into one document returns HTTP 500 today (research R14).
