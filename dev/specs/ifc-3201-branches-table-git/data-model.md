# Data Model: Repositories and Git state columns on the branches list

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Research**: [research.md](./research.md)

This feature is frontend-only. It adds no schema, no migration and no backend change. The list reads its own repository list once and the epic's `InfrahubRepositoryBranchStatus` once per repository, then groups the rows into one Git status per branch. The types and rules live in the `branch-git-status` entity. Paths are relative to `frontend/app/src/`.

## Repository list: `BranchGitRepository` (`entities/branch-git-status/domain/model/branch-git-repository.ts`)

```ts
export interface BranchGitRepository {
  id: string;
  name: string;
  kind: BranchRepositoryKind; // "CoreRepository" | "CoreReadOnlyRepository"
  isReadOnly: boolean;
}

export interface BranchGitRepositoryPage {
  repositories: BranchGitRepository[];
  count: number;
}
```

`toBranchGitRepositoryPage` (`entities/branch-git-status/api/branch-git-repository.mappers.ts`) builds the page from the `CoreGenericRepository` connection: `kind` is the node's `__typename`, `isReadOnly` is true for `CoreReadOnlyRepository`, `name` falls back to the id, and a node without an id is dropped. `count > repositories.length` means the list was cut at the 500-row limit.

## Status rows: `RepositoryBranchGitStatus` (`entities/branch-git-status/domain/model/repository-branch-git-status.ts`)

```ts
export interface RepositoryBranchGitStatus {
  branchName: string;
  commit: string | null;
  syncStatus: BranchGitSyncStatus | null;
}

export interface RepositoryBranchGitStatusPage {
  rows: RepositoryBranchGitStatus[];
  count: number;
}
```

One row per branch of one repository's status page. `BranchGitSyncStatus` (`value`, `label`, `color`, `description`) is the entity's own type (`entities/branch-git-status/domain/model/branch-git-status.ts`), the shape `GitStatePill` takes. `toRepositoryBranchGitStatusPage` (`entities/branch-git-status/api/repository-branch-status.mappers.ts`) maps a `sync_status` without a value to `null`.

The row set is the backend's: read/write repositories list only branches with Sync with Git on, read-only repositories list every branch; merged, deleting and global branches are excluded.

## Per-branch status: `BranchGitStatus` (`entities/branch-git-status/domain/model/branch-git-status.ts`)

```ts
export interface BranchRepositoryState {
  repository: BranchGitRepository;
  commit: string | null;
  syncStatus: BranchGitSyncStatus;
}

export interface SyncStatusCount { value: string | null; label: string; count: number }

export type FailedRepository =
  | { status: "denied"; repository: BranchGitRepository }
  | { status: "error"; repository: BranchGitRepository; message: string };

export type UnloadedRepository =
  | { status: "pending"; repository: BranchGitRepository }
  | FailedRepository;

export type BranchGitStatus =
  | { status: "pending" }
  | { status: "denied" }
  | { status: "error"; message: string }
  | { status: "ok"; repositories: BranchRepositoryState[]; counts: SyncStatusCount[]; unloaded: UnloadedRepository[] };
```

`repositories` is ordered worst first; `repositories[0]` is the pill, the Git state and the base of "+N more". `unloaded` lists the repositories whose status read is pending, denied or failed.

## Errors: `BranchGitStatusError`

`BranchGitStatusError extends Error` with `code: "PERMISSION_DENIED" | "UNKNOWN"`. `toBranchGitStatusError` (`entities/branch-git-status/domain/rules/to-branch-git-status-error.ts`) sets `PERMISSION_DENIED` only when every GraphQL error carries that code (`hasOnlyThrownCatalogueCode`), so a denial mixed with another failure reads as `UNKNOWN`. The message is the error's message, or a fallback when the thrown value is not an `Error`. Both use cases (`getBranchGitRepositories`, `getRepositoryBranchStatus`) throw it.

## Hook input: `RepositoryListFetch` and `RepositoryStatusFetch` (`entities/branch-git-status/domain/rules/summarize-branch-git-statuses.ts`)

```ts
export type RepositoryStatusFetch =
  | { status: "ok"; repository: BranchGitRepository; rows: RepositoryBranchGitStatus[]; count: number }
  | UnloadedRepository;

export type RepositoryListFetch =
  | { status: "pending" }
  | { status: "denied" }
  | { status: "error"; message: string }
  | { status: "ok"; statuses: readonly RepositoryStatusFetch[] };
```

`useGetBranchGitStatuses` builds them in `combine`:

- A query result holding `data` is `ok`, even when a background refetch failed.
- Else an error with `code === "PERMISSION_DENIED"` is `denied`, any other error is `error` with its message, and no error is `pending`.
- A repository list cut at 500 rows is an `error` ("Only the first N of M repositories were read. Open the branch for the full list.").

## `summarizeBranchGitStatuses(branchNames, repositoryList, unknownSyncStatus)` invariants

`summarizeBranchGitStatuses(branchNames: readonly string[], repositoryList: RepositoryListFetch, unknownSyncStatus: BranchGitSyncStatus): Record<string, BranchGitStatus>` is pure. The record is keyed by branch name.

1. The repository list is not `ok` → every branch gets the list's status (`pending`, `denied`, or `error` with its message).
2. At least one status read and every status read `denied` → every branch is `denied`.
3. Otherwise each branch collects, across every loaded status page, the rows whose `branchName` matches, as `BranchRepositoryState`s. Pending, denied and failed reads go into `unloaded` on every `ok` branch; they no longer turn every branch into `pending` or `error`. Because the client does not re-derive which branches a repository lists, a failed read/write repository is also carried on branches not synced with Git. Accepted limit.
4. Truncated page: when a loaded page was cut (`count > rows.length`) and does not list the branch, the branch gets `{ status: "error" }` naming the cut repositories ("Too many branches to load for <names>, so this branch could not be checked. Open the branch for the full list."). Which branches a repository lists is the backend's rule, so the client does not tell "absent" from "past the cut". Past 500 branches per repository, a branch the repository would never list can read this error too. Accepted limit.
5. Ordering: `compareWorstSyncStatusFirst` (`entities/branch-git-status/domain/rules/sync-status-severity.ts`) ranks `error-import`, then `unknown` (and any other or missing value), then `syncing`, then `in-sync`; ties sort by repository name, case-insensitive.
6. A row without a sync status reads as `unknownSyncStatus`, so it counts with real `unknown` rows. `getUnknownSyncStatus(choices)` (`entities/branch-git-status/domain/rules/get-unknown-sync-status.ts`) builds it from the `sync_status` attribute's `unknown` choice in the `CoreGenericRepository` schema; when the choice is missing, its label, colour and description are `null`.
7. `counts` has one entry per distinct `syncStatus.value`, in the order of `repositories`, so `counts[0]` belongs to `repositories[0]`. Its label is `label || value || ""`.
8. A branch with no rows and nothing unloaded → `{ status: "ok", repositories: [], counts: [], unloaded: [] }`; the cell picks "Not synced with Git" or "No repositories" from `branch.sync_with_git`.

## Row: `BranchTableRow` (`entities/branches/ui/branches-table/branch-table-row.ts`)

```ts
export interface BranchTableRow extends BranchListItem { gitStatus: BranchGitStatus }
```

`toBranchTableRows(branches, gitStatusesByBranchName)` adds each branch's status, `{ status: "pending" }` when the record has no entry. `BranchesTable` passes the rows to `BranchesDataTable`; `getBranchTableColumns` is typed on `BranchTableRow`. Being a superset of `BranchListItem`, it leaves selection, the toolbar and the delete modal unchanged.

## `BRANCH_FIELD_SCHEMAS` additions (`entities/branches/ui/branches-table/branch-field-schemas.ts`)

Header-only schemas for `TableColumnHeaderSimple`, built by `buildDisplayColumnSchema(name, label)`: `repositories` ("Repositories") and `git_state` ("Git state"). Neither is added to `BRANCH_FILTER_DEFINITIONS` (FR-015). The column ids match the keys.

## Test fakes

Outside `src/`: `frontend/app/tests/fake/branch.ts::generateBranch` (reused) and `frontend/app/tests/fake/branch-git-status.ts` (`generateBranchGitRepository`, `generateRepositoryBranchGitStatus`, `generateRepositoryBranchGitStatusPage`, `generateRepositoryBranchGitStatusWire`).
