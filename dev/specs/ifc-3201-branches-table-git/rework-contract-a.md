# Rework contract A (2026-10-01): repository-anchored, page-owned data

Owner decision after the architecture review of the one-row-per-branch rework: the list reads the
epic's primitive, `InfrahubRepositoryBranchStatus`, once per repository, pivots the result to one
summary per branch in the branches domain, and renders it through cells that own no data. This
replaces the per-branch `CoreGenericRepository` requests issued from inside the cells.

Why: the cells owned and duplicated the data and its derivation (two cells, same query, same
ranking); pure derivation lived in `.tsx`; the roll-up reused the details card's band ordering and
showed an unreachable repository as "In Sync"; the per-branch query mirrored the backend's row-set
rule on the client (`getRepositoryListKind`), which the epic's query exists to keep server-side.

## Requests

1. Repository list, once: `useGetBranchRepositories({ branchName: <default branch name>, syncWithGit: true })`
   (#10779's hook; the default branch is the one with `is_default`, taken from the branches provider,
   never by name). Gives `BranchRepository[]` (id, name, kind, isReadOnly).
2. Status, once per repository: `InfrahubRepositoryBranchStatus(id: <repository id>, limit: 500)`
   via `useQueries`. Rows are per branch: `name`, `commit`, `sync_status`, `is_default`, `ref`.
   Row set is the backend's: read/write repositories list only `sync_with_git` branches, read-only
   repositories list every branch; MERGED, DELETING and the global branch are excluded.
3. `staleTime: 60_000` on the status queries (caps the refocus burst); `refetchInterval: 10_000`
   on a status query while any of its rows has `sync_status.value === "syncing"`.

Request count: 1 + R (16 on the dev stack), independent of how many branch pages are loaded.

## Lifted from PR #10658 (`ple-branches-card-ifc-3130`), byte-identical where possible

- `frontend/app/src/entities/repository/domain/model/repository-branch-status.ts`
- `frontend/app/src/entities/repository/api/get-repository-branch-status-from-api.ts`
- `frontend/app/src/entities/repository/domain/use-cases/get-repository-branch-status.ts` (needs
  `shared/api/graphql/error-handling.ts::hasThrownCatalogueCode`; if that helper is not on this
  base, lift it too if the change is additive, otherwise adapt the use case to the base's
  `CombinedError` unwrapping and record that the file is not byte-identical).
- Their tests from #10658 where they exist (`repository-branch-status.test.ts`, use-case test).
- NOT the hook `get-repository-branch-status.query.ts` (it forces the current branch). Instead add
  to this base's `entities/repository/ui/queries/repository.query-keys.ts` a `branchStatus(params)`
  member with the same name and key shape as #10658's (read its file), and write
  `entities/repository/ui/queries/get-repository-branch-status.query.ts` exporting
  `getRepositoryBranchStatusQueryOptions(params)` (queryOptions factory, no hook) so the future
  merge with #10658 is a small, visible conflict in one file.
- Record SHAs and `cmp` results in `pr-notes.md`.

## Domain (branches entity)

`domain/model/branch-repository-summary.ts`:

```ts
export interface BranchRepositoryState {
  repository: Pick<BranchRepository, "id" | "name" | "kind" | "isReadOnly">;
  commit: string | null;
  syncStatus: RepositoryBranchStatusDropdown;   // value, label, color, description
}
export interface SyncStatusCount { value: string | null; label: string; count: number }
export type BranchRepositorySummary =
  | { status: "pending" }
  | { status: "denied" }
  | { status: "error"; message: string }
  | { status: "ok"; repositories: BranchRepositoryState[]; counts: SyncStatusCount[] };
// `repositories` is ordered worst first (see severity); repositories[0] is the pill, the Git state and the "+N more" base.
```

`domain/rules/summarize-branch-repositories.ts` (pure, imports own model + repository severity rule):

```ts
export type RepositoryStatusFetch =
  | { status: "pending" } | { status: "denied" } | { status: "error"; message: string }
  | { status: "ok"; repository: Pick<BranchRepository, "id" | "name" | "kind" | "isReadOnly">; rows: RepositoryBranchStatusRow[] };
export function summarizeBranchRepositories(
  branches: readonly BranchListItem[],
  fetches: readonly RepositoryStatusFetch[],
): Record<string /* branch name */, BranchRepositorySummary>;
```

Rules: any `denied` → every branch `denied`; else any `pending` → every branch `pending` (the
repository list pending counts as pending); else any `error` → every branch `error` with the first
message; else ok: for each branch collect the rows whose `name === branch.name`, build
`BranchRepositoryState`s, sort by severity then repository name (case-insensitive), count by
`syncStatus.value` (label = `label || value || "Unknown"`). A branch with no rows → `ok` with
empty `repositories` and `counts` (the cell decides the text from `branch.sync_with_git`).

Severity: `entities/repository/domain/rules/sync-status-severity.ts` (new, repository entity):
`compareSyncStatusSeverity(a, b)` ordering `error-import` > `unknown` > `syncing` > `in-sync`;
unknown values rank with `unknown`. Unit-tested.

## UI

- `entities/branches/ui/hooks/use-branch-repository-summaries.ts`:
  `useBranchRepositorySummaries(branches: BranchListItem[]): Record<string, BranchRepositorySummary>`.
  Reads the default branch from the branches provider, calls `useGetBranchRepositories` for the
  repository list, `useQueries` over repositories with `getRepositoryBranchStatusQueryOptions({ id, branchName: default, limit: 500 })`
  plus `staleTime`/`refetchInterval` from § Requests, and `combine` → `summarizeBranchRepositories`.
  In `combine`, a result with `data` is `ok` even when `isError` is set (a failed background
  refetch keeps the last loaded rows); `error.code === "PERMISSION_DENIED"` → `denied`; other
  errors → `error`. Returns a record keyed by branch name (structural sharing keeps untouched
  branches' summaries by reference). No `useMemo`.
- Row view-model: `entities/branches/ui/branches-table/branch-table-row.ts`:
  `export interface BranchTableRow extends BranchListItem { repositorySummary: BranchRepositorySummary }`
  and `toBranchTableRows(branches, summaries)`. `BranchesTable` passes `data={toBranchTableRows(flatData, summaries)}`;
  `BranchesDataTable` and `getBranchTableColumns` are typed on `BranchTableRow` (a superset of
  `BranchListItem`, so selection, toolbar and the delete modal keep receiving branches unchanged;
  `getRowId: row.id` unchanged).
- Cells are pure (no hooks, no fetching):
  - `cells/branch-repositories-cell.tsx` `({ branch }: { branch: BranchTableRow })`: pending →
    `Spinner`; denied → "No permission"; error → "Could not load repositories" + `Tooltip` with the
    message + `sr-only` message; ok with none → "Not synced with Git" when `branch.sync_with_git`
    is falsy else "No repositories"; ok → `LinkPill` for `repositories[0]` to
    `getObjectDetailsUrl(kind, id, [getBranchQspOverride(branch.name, Boolean(branch.is_default))])`
    with `FolderGitIcon` and truncated name, `Tooltip` "<label> · <7-char commit> · read-only"
    (parts omitted when absent), and "+N more" `Link` to `getBranchDetailsUrl(branch.name)` when
    N > 1. Muted texts use `text-foreground-muted`. The tooltip/summary string builder is a tiny
    pure helper in `domain/rules/format-repository-summary.ts` with a test, not in the `.tsx`.
  - `cells/branch-git-state-cell.tsx` `({ summary })`: blank unless ok with ≥ 1 repository;
    `GitStatePill syncStatus={repositories[0].syncStatus}`; when N > 1, `<span className="text-foreground-muted text-xs">{n}/{N}</span>`
    with n = count of `repositories[0].syncStatus.value`, wrapped in `Tooltip` listing
    `counts` as "Label: n · Label: n", plus an `sr-only` span with the same text.
- Grid template: unchanged from the previous rework (`REPOSITORIES_TRACK`, `GIT_STATE_TRACK`,
  `repeat(columnCount - 6, …)`).
- `cells/branch-name-cell.tsx` keeps `aria-label={`Select ${branch.name}`}`.
- The per-branch `useGetBranchRepositories` call sites in cells are gone; #10779's hook stays for
  the repository list and the details page.

## Removed

`cells/branch-repositories-cell.tsx` / `branch-git-state-cell.tsx` current implementations
(rewritten as above); nothing else from the previous rework needs removing.

## Tests (vitest browser mode)

- `domain/rules/summarize-branch-repositories.test.ts`: denied wins; pending wins over error; error
  carries the first message; rows grouped by branch name; worst-first ordering with ties by name;
  counts; a branch with no rows → empty ok; a read-only repository appears on an unsynced branch
  while a read/write one does not (given rows as the backend would return them).
- `repository/domain/rules/sync-status-severity.test.ts`: order and unknown-value handling.
- `domain/rules/format-repository-summary.test.ts`: label · commit · read-only, each part optional.
- `ui/hooks/use-branch-repository-summaries.test.ts` (renderHook, mock `getBranchRepositories`
  and `getRepositoryBranchStatus` use cases): one repository-list request on the default branch;
  one status request per repository with `limit: 500`; summaries keyed by branch; a failed
  background refetch keeps the loaded summary (data-first); `PERMISSION_DENIED` → all denied;
  `refetchInterval` is 10 000 only while a row is syncing (assert via the options factory, not
  TanStack internals); `staleTime` 60 000.
- `get-branch-table-columns.test.tsx` (pure cells, summaries given as data): headers; pill for the
  worst repository with link + branch param (default branch: none); tooltip text; "+N more" link;
  Git state pill colour, `n/N`, tooltip and sr-only text; single repository: no count; colourless
  status → grey badge; pending → one `role="status"` in Repositories, blank Git state; denied,
  error (sr-only message), empty (two texts) in `text-foreground-muted`, no `-`/`—`; an unreachable
  but in-sync repository is NOT shown as worst when an import error exists elsewhere, and an
  `unknown` ranks above `in-sync`.
- `branches-table.test.tsx` (mock the two use cases): branch cells render while summaries are
  pending; 1 + R requests for a page of branches; loading a second page issues no new status
  requests; denied → every row "No permission", no toast; one status error → "Could not load
  repositories" on every row, no toast.
- E2E `test_branches_git_columns.py`: unchanged assertions (broken branch row: pill names the
  repository, Git state "Import Error"; unsynced branch: "Not synced with Git").

## Cubic findings folded in (local run 2026-10-01)

data-first in `combine`; `staleTime` 60 s; sr-only counts; the E2E helper fixture logs teardown
failures instead of `contextlib.suppress`; contract/data-model/quickstart corrections (tooltip on
the count only, `SYNC_STATUS_NO_COLOUR` has `label: null`, fixture lives in `conftest.py`, E2E
command carries `-c tests/e2e/pytest.ini`); the knowledge note drops the ticket id and history.

## Spec consequences

Permission: the status query needs repository view permission on all branches; a denial blanks the
Repositories column for every row ("No permission") rather than one row. Merged branches, if the
list filter shows them, read "No repositories". The commit shown for a fresh synced branch is the
fork-point commit, as the backend resolves it. Cache is no longer shared with the branch details
page (different query); the backend `repository_ids` follow-up collapses 1 + R to 2 requests
without touching cells or rules.
