# Contract: GraphQL reads

**Feature**: [../spec.md](../spec.md)

**No new GraphQL document, field or backend change.** The feature reuses #10779's repository read unchanged, and the generated `gql.tada` types need no regeneration.

## Reused documents

They are defined in `frontend/app/src/entities/repository/api/get-branch-repositories-from-api.ts`:

- `GET_BRANCH_REPOSITORIES`, over `CoreGenericRepository(limit: $limit)`, used when the branch has `sync_with_git = true`.
- `GET_BRANCH_READONLY_REPOSITORIES`, over `CoreReadOnlyRepository(limit: $limit)`, used when `sync_with_git` is `false` or `null`.

Both select `count` and `edges.node { id __typename display_label name { value } commit { value } sync_status { value label color description } operational_status { value label color } }`. The table uses every field except `operational_status.color`, `count` and `display_label`. `display_label` serves only as the name fallback, and operational status serves ordering only.

## How the table calls them

| Aspect | Value |
|---|---|
| Entry point | `entities/repository/ui/queries/get-branch-repositories.query.ts::getBranchRepositoriesQueryOptions({ branchName, syncWithGit })`, via `useQueries` in `entities/branches/ui/hooks/use-branch-table-rows.ts::useBranchTableRows` |
| Requests | **One per loaded branch**: ≈40 for the first page (`BRANCHES_PER_PAGE`), +40 per further page. Independent of the repository count |
| Branch | The **row's** branch name, sent as the request's branch context (`graphqlClient.query({ context: { branch: branchName } })` in `get-branch-repositories-from-api.ts::fetchConnection`). Never the branch selector's current branch |
| Variables | `{ limit: REPOSITORY_FETCH_LIMIT }` (500) |
| Query key | `repositoryQueryKeys.branch({ branchName, kind })`, i.e. `["repositories", "branch", <branchName>, "CoreGenericRepository" \| "CoreReadOnlyRepository"]`. This is the same key as the branch details card, so both pages share the cache |
| Polling | `refetchInterval` is 10 s while any returned repository has `sync_status.value === "syncing"`, otherwise off |
| Retry | none (`queryClient` default `retry: false`) |

## Result mapping (unchanged, `domain/use-cases/get-branch-repositories.ts::getBranchRepositories`)

| Response | Use-case result | Table row state |
|---|---|---|
| data, no errors | `{ status: "ok", repositories, count, isTruncated }` | `ok` × N, or one `empty` row |
| every GraphQL error is `PERMISSION_DENIED` | `{ status: "denied" }` | one `denied` row |
| any other GraphQL error, network error, or no data | throws | one `error` row |

Only the per-branch GraphQL error toast differs from the spec (FR-013). The shared client toasts non-permission GraphQL errors because this context sets no `processErrorMessage`; see research R10.
