# Contract: UI cells, hook and selection

**Feature**: [../spec.md](../spec.md) | **Data model**: [../data-model.md](../data-model.md)

This file covers the props and rendering contracts for what the feature adds or changes on `/branches`, after rework A (2026-10-01, `../rework-contract-a.md`): the page owns the fetch and the cells are pure. Paths are relative to `frontend/app/src/`. Strings are verbatim from the spec.

## Common rules

- **Cells are pure**: no hooks, no fetching. They render the `BranchRepositorySummary` the row carries (`BranchTableRow.repositorySummary`).
- **Cell shape**: every new cell renders `TableCell` (`shared/components/table/table-cell.tsx`) with `className="h-auto min-h-14"`.
- **Early returns** (Repositories cell): pending, then denied, then error, then ok with no repositories, then ok with repositories.
- **Ordering**: already applied by `summarizeBranchRepositories`; `repositories[0]` is "the first repository" and its state is the worst (FR-005).
- **Loading**: `@infrahub/ui` `Spinner`, in the Repositories cell only. Git state stays blank while pending, so a pending row shows one `role="status"`.
- **Blank**: an empty `TableCell`. No `-`, no `—`, no placeholder text (FR-007).
- **Muted text**: `<span className="text-foreground-muted">…</span>` (FR-007, FR-012, FR-013).
- **Headers**: `TableColumnHeaderSimple` over the `BRANCH_FIELD_SCHEMAS` entries, with no filter or sort control (FR-015).
- **Column position**: after `proposed_changes`; display column ids `repositories` and `git_state`.
- **Link rule**: the repository pill carries the **row's** branch via `getBranchQsp(branch.name)`. The default branch's row also carries `branch=<default>`.

## `useBranchRepositorySummaries` — `entities/branches/ui/hooks/use-branch-repository-summaries.ts` (new)

```ts
function useBranchRepositorySummaries(branches: BranchListItem[]): Record<string, BranchRepositorySummary>
```

Reads the default branch (`is_default`) from the branches provider; reads the repository list with `useQuery(getBranchRepositoriesQueryOptions({ branchName: <default>, syncWithGit: true, isSyncing: false, limit: 500, offset: 0 }))`; runs `useQueries` over the repositories with `getRepositoryBranchStatusQueryOptions({ id, branchName: <default>, limit: 500 })`, `staleTime: 60_000` and `refetchInterval: 10_000` while any row of that query is `syncing`; `combine` maps results to `RepositoryStatusFetch` (data-first, `PERMISSION_DENIED` → denied) and returns `summarizeBranchRepositories(branches, fetches, compareSyncStatusSeverity)`. No `useMemo`.

## `BranchRepositoriesCell` — `entities/branches/ui/branches-table/cells/branch-repositories-cell.tsx`

```ts
interface BranchRepositoriesCellProps { branch: BranchTableRow }
```

| `branch.repositorySummary` | Renders |
|---|---|
| `pending` | `Spinner` |
| `denied` | muted "No permission" |
| `error` | muted "Could not load repositories", wrapped in `Tooltip` with `message`, plus `<span className="sr-only">{message}</span>` (FR-013) |
| `ok`, 0 repositories, `branch.sync_with_git` falsy | muted "Not synced with Git" |
| `ok`, 0 repositories, `branch.sync_with_git === true` | muted "No repositories" |
| `ok`, N ≥ 1 | the pill, then, when N > 1, the "+N more" link (`Row className="flex-wrap"`) |

**Pill**: `LinkPill` to `getObjectDetailsUrl(kind, id, [getBranchQsp(branch.name)])` for `repositories[0].repository`, `className="max-w-40"`, content `FolderGitIcon` (`shrink-0`) + `<span className="truncate">{name}</span>`. Wrapped in `Tooltip` whose message is `formatRepositoryState / formatSyncStatusCounts(repositories[0])` (`entities/branches/domain/rules/format-repository-summary.ts`): `<label> · <7-char commit> · read-only`, each part omitted when absent (FR-004).

**"+N more"**: react-router `Link` to `getBranchDetailsUrl(branch.name)`, text `+{N - 1} more`, `className="shrink-0 whitespace-nowrap text-foreground-muted text-sm hover:underline"`.

## `BranchGitStateCell` — `cells/branch-git-state-cell.tsx`

```ts
interface BranchGitStateCellProps { summary: BranchRepositorySummary }
```

| `summary` | Renders |
|---|---|
| not `ok`, or `ok` with 0 repositories | blank |
| `ok`, N = 1 | `<GitStatePill syncStatus={repositories[0].syncStatus} />` |
| `ok`, N > 1 | the same pill, then `<span className="text-foreground-muted text-xs">{n}/{N}</span>` with n = the `counts` entry for `repositories[0].syncStatus.value`. The **count only** is wrapped in a `Tooltip` listing `counts` as `Label: n · Label: n` (for example `Import Error: 1 · In Sync: 15`); an `sr-only` span carries the same text (FR-006) |

`GitStatePill` (#10779) is reused unchanged: a `rounded-md` chip in the schema colour with `getTextColor(color)`, or a grey `Badge` showing `value || label || "—"`; its own `Tooltip` carries `description`. No unreachable icon (FR-016).

## Table — `branches-table.tsx`, `branches-data-table.tsx`, `get-branch-table-columns.tsx`

| Aspect | Contract |
|---|---|
| Data | `BranchesTable` calls `useBranchRepositorySummaries(flatData)` and passes `data={toBranchTableRows(flatData, summaries)}` |
| Row type | `BranchTableRow` (superset of `BranchListItem`), `getRowId: (row) => row.id` |
| Selection | The base branch's per-row selection, unchanged (FR-008, FR-009); toolbar and delete modal receive branches unchanged |
| Row checkbox | `aria-label={`Select ${branch.name}`}` |
| Grid template | `[fit-content(WIDE), fit-content(MAX), minmax(150px, 200px), REPOSITORIES_TRACK, GIT_STATE_TRACK, repeat(columnCount - 6, fit-content(MAX)), 2.5rem]`, `REPOSITORIES_TRACK = "minmax(12rem, 18rem)"`, `GIT_STATE_TRACK = "9rem"` (SC-004) |
| Memoization | none (React Compiler) |

## Superseded

- The one-row-per-branch rework (2026-10-01, before rework A), replaced by rework A: cells taking `{ branch: BranchListItem }` and calling `useGetBranchRepositories` per row, `rankRepositories` in the cells, and the tooltip wrapping both the Git state pill and the count.
- 2026-10-01 (rework): `BranchRepositoryCell`, `BranchCommitCell` (and `CommitHash`), `useBranchTableRows`, the anchor-row selection contract and the three-track grid template.
