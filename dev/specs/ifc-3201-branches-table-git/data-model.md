# Data Model: Repository, Git state and Commit columns on the branches table

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Research**: [research.md](./research.md)

This feature is frontend-only. It adds no schema, no migration and no backend change. Since rework A (2026-10-01, `rework-contract-a.md`, research R15) the list reads the epic's `InfrahubRepositoryBranchStatus` once per repository and pivots the rows to one summary per branch in the branches domain. Paths are relative to `frontend/app/src/`.

## Consumed: `BranchRepository` (repository list) and `RepositoryBranchStatusRow` (status rows)

`BranchRepository` (`entities/repository/domain/model/branch-repository.ts`, #10779) comes from `useGetBranchRepositories({ branchName: <default branch>, syncWithGit: true })`, called once. The list reads `id`, `name`, `kind` and `isReadOnly`.

`RepositoryBranchStatusRow` (`entities/repository/domain/model/repository-branch-status.ts`, lifted from #10658) is one row per branch of one repository's status page:

| Field | Used for |
|---|---|
| `name` | the branch the row belongs to; the pivot key |
| `commit` (`string \| null`) | the 7-character commit in the pill's tooltip; `null` drops that part |
| `syncStatus` (`RepositoryBranchStatusDropdown`: `value`, `label`, `color`, `description`) | the Git state: severity, `GitStatePill`, counts; `syncing` drives the poll |
| `isDefault`, `ref` | not used |

The row set is the backend's: read/write repositories list only `sync_with_git` branches, read-only repositories list every branch; merged, deleting and global branches are excluded.

## `RepositoryStatusFetch` (`entities/branches/domain/rules/summarize-branch-repositories.ts`)

One per repository, built in the hook's `combine` from each `useQueries` result (plus one for the repository list):

```ts
export type RepositoryStatusFetch =
  | { status: "pending" }
  | { status: "denied" }
  | { status: "error"; message: string }
  | { status: "ok"; repository: Pick<BranchRepository, "id" | "name" | "kind" | "isReadOnly">; rows: RepositoryBranchStatusRow[]; count: number };
```

Mapping: a result with `data` is `ok` even when `isError` is set (a failed background refetch keeps the last loaded rows); else `error.code === "PERMISSION_DENIED"` → `denied`; else an error → `error` with its message; else `pending`. The repository list pending counts as `pending`.

## `BranchRepositorySummary` (`entities/branches/domain/model/branch-repository-summary.ts`)

```ts
export interface BranchRepositoryState {
  repository: Pick<BranchRepository, "id" | "name" | "kind" | "isReadOnly">;
  commit: string | null;
  syncStatus: RepositoryBranchStatusDropdown;
}
export interface SyncStatusCount { value: string | null; label: string; count: number }
export type BranchRepositorySummary =
  | { status: "pending" }
  | { status: "denied" }
  | { status: "error"; message: string }
  | { status: "ok"; repositories: BranchRepositoryState[]; counts: SyncStatusCount[] };
```

`repositories` is ordered worst first; `repositories[0]` is the pill, the Git state and the base of "+N more".

## `summarizeBranchRepositories(branches, fetches)` invariants

`summarizeBranchRepositories(branches: readonly BranchListItem[], fetches: readonly RepositoryStatusFetch[]): Record<string /* branch name */, BranchRepositorySummary>` is pure and imports only its own models (`entities/branches/domain/model/branch.ts`, `branch-repository-summary.ts`), `BranchStatus` from `shared/api/graphql/generated/types`, the status row types from `entities/repository/domain/model/repository-branch-status.ts`, and `entities/repository/domain/rules/sync-status-severity.ts`.

1. Every fetch `denied` (and at least one fetch) → every branch `denied`. Permission is checked per repository kind, so a denied kind among others is left out silently.
2. Else any `pending` fetch → every branch `pending`.
3. Else any `error` fetch → every branch `error` with the first error's message.
4. Else each branch collects the rows whose `name === branch.name`, across every `ok` fetch, as `BranchRepositoryState`s. If an `ok` fetch was cut short (`count > rows.length`), a branch absent from its rows that the repository could list (read-only repositories list every branch, read/write ones only synced branches, and no repository lists a merged or deleting branch) gets `{ status: "error" }` naming the cut repositories instead of a guessed summary.
5. The states are sorted by `compareSyncStatusSeverity` (`error-import` > `unknown` > `syncing` > `in-sync`; any other value ranks with `unknown`), then by repository name, case-insensitive.
6. `counts` has one entry per distinct `syncStatus.value`, with `label = label || value || "Unknown"`.
7. A branch with no rows → `{ status: "ok", repositories: [], counts: [] }`; the cell picks "Not synced with Git" or "No repositories" from `branch.sync_with_git`.
8. The record is keyed by branch name; structural sharing in `combine` keeps untouched branches' summaries by reference.

## Row: `BranchTableRow` (`entities/branches/ui/branches-table/branch-table-row.ts`)

```ts
export interface BranchTableRow extends BranchListItem { repositorySummary: BranchRepositorySummary }
```

`toBranchTableRows(branches, summaries)` adds each branch's summary. `BranchesTable` passes `data={toBranchTableRows(flatData, summaries)}`; `BranchesDataTable` and `getBranchTableColumns` are typed on `BranchTableRow`. Being a superset of `BranchListItem`, it leaves selection, the toolbar and the delete modal unchanged; `getRowId: (row) => row.id` is unchanged.

## `BRANCH_FIELD_SCHEMAS` additions (`entities/branches/ui/branches-table/branch-field-schemas.ts`)

Header-only schemas for `TableColumnHeaderSimple`, in the file's existing object shape:

```ts
repositories: { name: "repositories", label: "Repositories", kind: "Text" } as AttributeSchema,
git_state:    { name: "git_state",    label: "Git state",    kind: "Text" } as AttributeSchema,
```

Neither is added to `BRANCH_FILTER_DEFINITIONS` (FR-015). The column ids match the keys: `repositories`, `git_state`.

## Superseded

- 2026-10-01 (the one-row-per-branch rework, before rework A): "Derived per cell": each cell calling `useGetBranchRepositories` for its row's branch and ranking with `rankRepositories`. `BranchRepository.operationalStatus` no longer affects order. The list no longer reads `BranchRepositoriesResult`.
- 2026-10-01 (rework): `BranchRepositoriesFetch`, the fan-out `BranchTableRow` and `BranchTableRowState`, `isBranchAnchorRow`, the fan-out `toBranchTableRows` and its invariants, the `repository` and `commit` schema entries, and the `frontend/app/tests/fake/branch-table-rows.ts` fakes. Git history keeps them.

## Test fakes

Reused: `frontend/app/tests/fake/branch.ts::generateBranch` and `frontend/app/tests/fake/branch-repositories.ts` (outside `src/`). A colourless status `SYNC_STATUS_NO_COLOUR = { value: "mystery", label: null, color: null, description: null }` is a constant local to `get-branch-table-columns.test.tsx`.
