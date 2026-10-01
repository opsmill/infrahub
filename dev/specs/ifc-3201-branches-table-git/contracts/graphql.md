# Contract: GraphQL reads

**Feature**: [../spec.md](../spec.md)

**No new GraphQL document, field or backend change.** The feature reuses #10779's repository read unchanged, and the generated `gql.tada` types need no regeneration.

## Reused documents

They are defined in `frontend/app/src/entities/repository/api/get-branch-repositories-from-api.ts`:

- `GET_BRANCH_REPOSITORIES`, over `CoreGenericRepository(limit: $limit)`, used when the branch has `sync_with_git = true`.
- `GET_BRANCH_READONLY_REPOSITORIES`, over `CoreReadOnlyRepository(limit: $limit)`, used when `sync_with_git` is `false` or `null`.

Both select `count` and `edges.node { id __typename display_label name { value } commit { value } sync_status { value label color description } operational_status { value label color } }`. The table uses every field except `operational_status.color` and `count`. `display_label` serves as the name fallback, `commit` appears only in the repository pill's tooltip, and operational status serves ordering only.

## How the table calls them

| Aspect | Value |
|---|---|
| Entry point | `entities/repository/ui/queries/get-branch-repositories.query.ts::useGetBranchRepositories({ branchName, syncWithGit })`, called by both `BranchRepositoriesCell` and `BranchGitStateCell`; the two calls share one query by key (no table-level `useQueries` since 2026-10-01) |
| Requests | **One per loaded branch**: ≈40 for the first page (`BRANCHES_PER_PAGE`), +40 per further page. Independent of the repository count. Measured: 24 requests in 0.36 s total on a dev stack (research R14) |
| Branch | The **row's** branch name, sent as the request's branch context (`graphqlClient.query({ context: { branch: branchName } })` in `get-branch-repositories-from-api.ts::fetchConnection`). Never the branch selector's current branch |
| Variables | `{ limit: REPOSITORY_FETCH_LIMIT }` (500) |
| Query key | `repositoryQueryKeys.branch({ branchName, kind })`, i.e. `["repositories", "branch", <branchName>, "CoreGenericRepository" \| "CoreReadOnlyRepository"]`. This is the same key as the branch details card, so both pages share the cache |
| Polling | `refetchInterval` is 10 s while any returned repository has `sync_status.value === "syncing"`, otherwise off |
| Retry | none (`queryClient` default `retry: false`) |

## Result mapping (unchanged, `domain/use-cases/get-branch-repositories.ts::getBranchRepositories`)

| Response | Use-case result | Table cells |
|---|---|---|
| data, no errors | `{ status: "ok", repositories, count, isTruncated }` | first repository + "+N more", Git state roll-up; or an empty text |
| every GraphQL error is `PERMISSION_DENIED` | `{ status: "denied" }` | "No permission", Git state blank |
| any other GraphQL error, network error, or no data | throws | "Could not load repositories", Git state blank |

The shared client toasts non-permission GraphQL errors unless the request context sets `processErrorMessage`; this feature makes `fetchConnection` pass a no-op one, so FR-013's "no toast" holds, and the thrown error's message becomes the tooltip (and `sr-only` text) of "Could not load repositories" (research R10). A failed background refetch keeps the last loaded result, because the cells read `data` before the error.

## Single request for every branch: not available (research R14)

- Aliasing one `InfrahubRepositoryBranchStatus` field per repository (16 aliases) into one document returns HTTP 500 `read() called while another coroutine is already waiting for incoming data`.
- `Branch` has no repositories field.
- Backend follow-ups: a `repository_ids` list argument on `InfrahubRepositoryBranchStatus`, or a fix to the concurrent-resolver path.
