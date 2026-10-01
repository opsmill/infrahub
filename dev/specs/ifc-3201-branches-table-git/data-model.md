# Data Model: Repository, Git state and Commit columns on the branches table

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Research**: [research.md](./research.md)

This feature is frontend-only. It adds no schema, no migration, no GraphQL document, no API mapper and, since the rework of 2026-10-01 (`rework-contract.md`, research R14), no domain type: the table keeps its `BranchListItem` rows and each cell reads #10779's repository query for its row's branch. Paths are relative to `frontend/app/src/`.

## Consumed as-is: `BranchRepository` and `BranchRepositorySyncStatus`

These are defined in `entities/repository/domain/model/branch-repository.ts` and are not redefined here. This feature reads:

| Field | Used for |
|---|---|
| `BranchRepository.id` | the pill's link target |
| `BranchRepository.kind` | the pill's link target (`getObjectDetailsUrl(kind, id, …)`) |
| `BranchRepository.name` | the pill text; the name sort inside `rankRepositories` |
| `BranchRepository.isReadOnly` | ` · read-only` in the pill's tooltip |
| `BranchRepository.commit` (`string \| null`) | the 7-character commit in the pill's tooltip; `null` drops that part |
| `BranchRepository.syncStatus` (`BranchRepositorySyncStatus`: `value`, `label`, `color`, `description`, all `string \| null`) | the pill's tooltip label; `GitStatePill`; the `n/N` count and per-label tooltip; `syncing` drives the poll |
| `BranchRepository.operationalStatus` | ordering only (rank 1). Never rendered (FR-016) |

`BranchRepositoriesResult` is `{ status: "ok"; repositories; count; isTruncated } | { status: "denied" }`. It is the use-case's return value. `count` and `isTruncated` are ignored (research R11): N is `repositories.length`.

## Row: `BranchListItem` (unchanged)

The table's row type is `BranchListItem` (`entities/branches/domain/model/branch.ts`), with `getRowId: (row) => row.id`, as on the base branch. Selection, pagination and ordering are unchanged.

## Derived per cell (not stored)

Each cell calls `useGetBranchRepositories({ branchName: branch.name, syncWithGit: Boolean(branch.sync_with_git) })`; both cells of a row hit the same query key, so they share one request and one result. From the query state:

| Query state | Repositories cell | Git state cell |
|---|---|---|
| pending | `Spinner` | blank |
| `data.status === "denied"` | "No permission" | blank |
| error (no `data`) | "Could not load repositories" + message | blank |
| `ok`, 0 repositories | "Not synced with Git" (`sync_with_git` falsy) / "No repositories" | blank |
| `ok`, N ≥ 1 | pill for `ranked[0]`, "+N−1 more" when N > 1 | `GitStatePill` for `ranked[0]`, `n/N` + per-label tooltip when N > 1 |

where:

- `ranked = rankRepositories(repositories)` (`entities/repository/domain/rules/rank-repositories.ts`): import errors first, then unreachable remotes, then by name, case-insensitive.
- `n` = the number of repositories whose `syncStatus.value` equals `ranked[0].syncStatus.value`.
- The per-label tooltip lists, for each distinct label, `<label>: <count>`, joined with ` · ` (for example `Import Error: 1 · In Sync: 15`).

`data` is checked before the error, so a stale success stays rendered when a background refetch fails, as #10779's card reads the same query.

## `BRANCH_FIELD_SCHEMAS` additions (`entities/branches/ui/branches-table/branch-field-schemas.ts`)

Header-only schemas for `TableColumnHeaderSimple`, in the file's existing object shape:

```ts
repositories: { name: "repositories", label: "Repositories", kind: "Text" } as AttributeSchema,
git_state:    { name: "git_state",    label: "Git state",    kind: "Text" } as AttributeSchema,
```

Neither is added to `BRANCH_FILTER_DEFINITIONS` (FR-015). The column ids match the keys: `repositories`, `git_state`.

## Superseded 2026-10-01

`BranchRepositoriesFetch`, `BranchTableRow`, `BranchTableRowState`, `isBranchAnchorRow`, `toBranchTableRows` and its invariants, the `repository` and `commit` schema entries, and the `tests/fake/branch-table-rows.ts` fakes (`FULL_COMMIT_HASH`, `generateBranchTableRow`) described the one-row-per-repository fan-out. They were deleted with it (research R14); git history keeps them.

## Test fakes

Reused, unchanged: `tests/fake/branch.ts::generateBranch` and `tests/fake/branch-repositories.ts::{SYNC_STATUS, OPERATIONAL_STATUS, generateBranchRepository, generateBranchRepositoriesResult}`. A colourless status (`{ value: "mystery", label: "Mystery", color: null, description: null }`) is a constant local to `get-branch-table-columns.test.tsx`.
