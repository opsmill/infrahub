# Contract: UI cells, hook and selection

**Feature**: [../spec.md](../spec.md) | **Data model**: [../data-model.md](../data-model.md)

Props and rendering contracts for what the feature adds or changes on `/branches`: the page owns the fetch and the cells only render. Paths are relative to `frontend/app/src/`. Texts are verbatim from the cell code; the component tests are the binding check.

## Common rules

- **Cells take no data of their own**: no hooks, no fetching. They render the `BranchGitStatus` the row carries (`BranchTableRow.gitStatus`).
- **Cell shape**: both cells render `TableCell` (`shared/components/table/table-cell.tsx`) with a minimum height, so rows keep their height while statuses load.
- **Test ids**: `branch-repositories-cell-<branch name>` and `branch-git-state-cell-<branch name>`, set on the `TableCell` in every state.
- **Ordering**: already applied by `summarizeBranchGitStatuses`; `repositories[0]` is "the first repository" and its state is the worst (FR-005).
- **Loading**: `@infrahub/ui` `Spinner` with `aria-hidden` plus `sr-only` "Loading repositories", in the Repositories cell only. There is no live status region per row, so a page of loading rows is not announced once per row. Git state stays blank while pending.
- **Blank**: an empty `TableCell`. No `-`, no `—`, no placeholder text (FR-007).
- **Muted text**: the empty and failure texts use the muted foreground colour (FR-007, FR-012, FR-013).
- **Headers**: `TableColumnHeaderSimple` over the `BRANCH_FIELD_SCHEMAS` entries, with no filter or sort control (FR-015).
- **Column position**: after `proposed_changes`; display column ids `repositories` and `git_state`. Each column sets its grid track in `meta.gridTrack`; the Repositories and Git state tracks are fixed widths, so cells filling in do not shift the columns (SC-004).
- **Link rule**: the repository pill carries the row's branch through `getBranchQsp(branch.name)`. The default branch's row also carries `branch=<default>`.

## `useGetBranchGitStatuses` (`entities/branch-git-status/ui/hooks/use-get-branch-git-statuses.ts`)

```ts
function useGetBranchGitStatuses(branchNames: readonly string[]): Record<string, BranchGitStatus>
```

Reads the repository list with `useQuery(getBranchGitRepositoriesQueryOptions({ limit: 500, offset: 0 }))`, without branch context. When the list loaded and was not cut, runs `useQueries` over the repositories with `getRepositoryBranchStatusQueryOptions({ repositoryId, limit: 500 })`. `combine` maps each result to a `RepositoryStatusFetch` (data first, `PERMISSION_DENIED` → `denied`) and returns `summarizeBranchGitStatuses(branchNames, repositoryList, unknownSyncStatus)`, where `unknownSyncStatus` comes from the `CoreGenericRepository` schema's `sync_status` choices. It takes branch names only and imports nothing from the `branches` entity. No `useMemo`. See [graphql.md](./graphql.md) for keys, polling and errors.

## `BranchRepositoriesCell` (`entities/branches/ui/branches-table/cells/branch-repositories-cell.tsx`)

```ts
interface BranchRepositoriesCellProps { branch: BranchTableRow }
```

| `branch.gitStatus` | Renders |
|---|---|
| `pending` | the spinner and `sr-only` "Loading repositories" |
| `denied` | muted "No permission" |
| `error` | muted "Could not load repositories", with `message` in a `Tooltip` and in `sr-only` text (FR-013) |
| `ok`, 0 repositories, a status read still pending | the spinner and `sr-only` "Loading repositories" |
| `ok`, 0 repositories, some status reads failed or denied | the failed-repositories notice alone |
| `ok`, 0 repositories, nothing unloaded, `branch.sync_with_git` falsy | muted "Not synced with Git" |
| `ok`, 0 repositories, nothing unloaded, `branch.sync_with_git` true | muted "No repositories" |
| `ok`, N ≥ 1 | the pill, then, when N > 1, the "+N more" link; below them, the failed-repositories notice when some status reads failed or were denied |

**Pill**: `LinkPill` to `getObjectDetailsUrl(kind, id, [getBranchQsp(branch.name)])` for `repositories[0].repository`, with a folder icon and the truncated repository name. Its `Tooltip` reads `formatRepositoryState(repositories[0])` (`entities/branch-git-status/domain/rules/format-branch-git-status.ts`): `<label or value> · <7-char commit> · read-only`, each part left out when absent (FR-004).

**"+N more"**: react-router `Link` to `getBranchDetailsUrl(branch.name)`. Visible text `+{N - 1} more`; accessible name `+{N - 1} more repositories on <branch>` (`repository` when N - 1 is 1), for example "+2 more repositories on feature-1".

**Failed-repositories notice**: muted small text `formatFailedRepositoryCount(count)`: "1 repository could not be loaded" or "N repositories could not be loaded". Its `Tooltip` and `sr-only` text list `<repository>: <message>` for a failed read and `<repository>: No permission` for a denied read, joined by " · ". Pending reads are not counted. Unloaded repositories are carried on every `ok` branch, so the notice shows on every row. Because the client does not re-derive which branches a repository lists, a failed read/write repository's notice also shows on branches not synced with Git. Accepted limit.

## `BranchGitStateCell` (`entities/branches/ui/branches-table/cells/branch-git-state-cell.tsx`)

```ts
interface BranchGitStateCellProps { branch: BranchTableRow }
```

| `branch.gitStatus` | Renders |
|---|---|
| not `ok`, or `ok` with 0 repositories | blank |
| `ok`, N = 1 | `GitStatePill` for `repositories[0].syncStatus` |
| `ok`, N > 1 | the same pill, then muted `n/N` text, where n is `counts[0].count` (the worst state's count) and N counts loaded repositories only. Only the count is wrapped in a `Tooltip` listing `counts` as `Label: n · Label: n` (for example `Import Error: 1 · In Sync: 3`); an `sr-only` span carries the same text (FR-006) |

`GitStatePill` (`entities/repository/ui/branch-repositories/git-state-pill.tsx`, #10779) is reused unchanged: a chip in the schema colour, or a grey badge when the choice has no colour; its own `Tooltip` carries the description. No unreachable icon (FR-016).

## Table (`branches-table.tsx`, `branches-data-table.tsx`, `get-branch-table-columns.tsx`)

| Aspect | Contract |
|---|---|
| Data | `BranchesTable` calls `useGetBranchGitStatuses(branches.map((branch) => branch.name))` and passes `toBranchTableRows(branches, gitStatuses)` |
| Row type | `BranchTableRow` (superset of `BranchListItem`) |
| Selection | The base branch's per-row selection, unchanged (FR-008, FR-009); toolbar and delete modal receive branches unchanged |
| Row checkbox | accessible name `Select <branch name>` |
| Memoization | none (React Compiler) |
