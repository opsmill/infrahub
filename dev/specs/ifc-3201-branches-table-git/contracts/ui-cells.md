# Contract: UI cells, hook and selection

**Feature**: [../spec.md](../spec.md) | **Data model**: [../data-model.md](../data-model.md)

This file covers the props and rendering contracts for what the feature adds or changes on `/branches`. Paths are relative to `frontend/app/src/`. Strings are verbatim from the spec.

## Common rules

- **Cell shape**: every new cell renders `TableCell` (`shared/components/table/table-cell.tsx`) with `className="h-auto min-h-14"`, the same row height as the existing cells.
- **Cell input**: each new cell takes `{ row: BranchTableRow }` and switches on `row.state`, with an early return per state: `pending`, then non-`ok`, then `ok`.
- **Loading**: `@infrahub/ui` `Spinner`, the `cells/branch-proposed-changes-cell.tsx::BranchProposedChangesCell` pattern, in the Repository cell only. Git state and Commit stay blank while pending (FR-011), so a pending branch shows one `role=status`, not three.
- **Blank**: an empty `TableCell`. No `-`, no `—`, no placeholder text (FR-007).
- **Muted text**: `<span className="text-subtle-muted">…</span>`.
- **Headers**: `TableColumnHeaderSimple` over the new `BRANCH_FIELD_SCHEMAS` entries, with no filter or sort control (FR-015).
- **Column position**: the three columns sit after `proposed_changes`. The display column ids are `repository`, `git_state` and `commit`.
- **Link rule**: repository links carry the **row's** branch via `getBranchQspOverride(row.branch.name, Boolean(row.branch.is_default))`. The default branch gets no `branch` parameter.

## `BranchRepositoryCell` — `entities/branches/ui/branches-table/cells/branch-repository-cell.tsx` (new)

```ts
interface BranchRepositoryCellProps { row: BranchTableRow }
```

| `row.state` | Renders |
|---|---|
| `pending` | `Spinner` |
| `ok` | `<RepositoryNameLink repository={row.repository} branchName={row.branch.name} isDefaultBranch={Boolean(row.branch.is_default)} />` |
| `empty`, `row.branch.sync_with_git` falsy | muted "Not synced with Git" |
| `empty`, `row.branch.sync_with_git === true` | muted "No repositories" |
| `denied` | muted "No permission" |
| `error` | muted "Could not load repositories", carrying `row.errorMessage` (the query error's message) as a tooltip (`Tooltip` from `@infrahub/ui`), so the no-op `processErrorMessage` loses nothing (FR-013) |

## `BranchGitStateCell` — `cells/branch-git-state-cell.tsx` (new)

```ts
interface BranchGitStateCellProps { row: BranchTableRow }
```

| `row.state` | Renders |
|---|---|
| `ok` | `<GitStatePill syncStatus={row.repository.syncStatus} />` (`entities/repository/ui/branch-repositories/git-state-pill.tsx`) |
| `pending`, `empty`, `denied`, `error` | blank |

`GitStatePill` behaviour, reused unchanged:

- **Colour and label present**: a `rounded-md` chip. `backgroundColor` is the schema colour, and the text colour comes from `getTextColor(color)`.
- **Otherwise**: a grey `Badge` showing `value || label || "—"`.
- **Tooltip**: always wraps the chip, with `description` as its message.

The chip is `rounded-md`, which separates it from the Status column's `rounded-full` pill. The unreachable warning icon is **not** rendered here (FR-016).

## `BranchCommitCell` — `cells/branch-commit-cell.tsx` (new)

```ts
interface BranchCommitCellProps { row: BranchTableRow }
```

| `row.state` | Renders |
|---|---|
| `ok`, `repository.commit` non-null | `<CommitHash hash={row.repository.commit} copyable />` |
| `ok` with `commit === null`, or `pending`, `empty`, `denied`, `error` | blank, with no copy control |

`CommitHash` (`shared/components/display/commit-hash.tsx`, lifted from #10658) has the props `{ hash: string; copyable?: boolean }`. It renders:

- a `font-mono text-xs` span with `title={hash}` showing `hash.slice(0, 7)`;
- with `copyable`, a `CopyToClipboardButton` with `data={hash}` and `aria-label="Copy commit <hash>"`. Its tooltip reads "Copy" and then "Copied!" (FR-005, US1-AS3).

A fork-point commit on a new branch renders as returned.

## `RepositoryNameLink` — `entities/repository/ui/branch-repositories/repository-name-link.tsx` (new, extracted)

```ts
interface RepositoryNameLinkProps {
  repository: BranchRepository;
  branchName: string;
  isDefaultBranch: boolean;
}
```

It renders the markup `RepositoryRow`'s first `<td>` renders today, moved verbatim:

- a `div.flex.min-w-0.items-center.gap-1.5` wrapper;
- a `FolderGitIcon` (`size-3.5 text-foreground-muted`, `aria-hidden`);
- a `Link` to `getObjectDetailsUrl(kind, id, [getBranchQspOverride(branchName, isDefaultBranch)])` with `title={name}`, `className="truncate"` and the text `name`;
- when `isReadOnly`, a "Read-only" chip (`rounded bg-content-strong px-1 text-foreground-muted text-xs`).

`RepositoryRow` renders `<td className="px-3"><RepositoryNameLink … /></td>` and keeps its Git state `<td>` (with the unreachable icon) and its commit `<td>` (with the `—` fallback) unchanged.

## `useBranchTableRows` — `entities/branches/ui/hooks/use-branch-table-rows.ts` (new)

```ts
export function useBranchTableRows(branches: BranchListItem[]): BranchTableRow[];
```

- It calls `useQueries({ queries: branches.map((b) => getBranchRepositoriesQueryOptions({ branchName: b.name, syncWithGit: Boolean(b.sync_with_git) })), combine })`, one entry per branch. The `combine` returns a stable per-branch record, and rows are rebuilt only for branches whose result reference changed, so one resolution re-renders one branch's rows (SC-007, research R13). No `useMemo`. The query key, the `queryFn` and the 10 s "while syncing" `refetchInterval` are #10779's own, so the cache is shared with the branch details card.
- It maps result i to `BranchRepositoriesFetch` (`data` present → `data`; else `isError` → error with the error's message; else pending) under `branches[i].id`. A stale success therefore stays rendered when a background refetch fails (data-model invariant 9). It then returns `toBranchTableRows({ branches, fetchByBranchId, orderRepositories: rankRepositories })`.
- It shows no toast and throws no error, and it never reads the branch selector's current branch.
- Caller: `branches-table.tsx::BranchesTable`, as `data={useBranchTableRows(flatData)}`. `flatData` is today's ordering: default first, then `sortByName`. `BRANCHES_PER_PAGE` is unchanged.

## Selection contract — `branches-data-table.tsx::BranchesDataTable` and `get-branch-table-columns.tsx`

| Aspect | Contract |
|---|---|
| Row type | `columns: ColumnDef<BranchTableRow>[]`, `data: BranchTableRow[]`, `getRowId: (row) => row.id` |
| Selectable row | `enableRowSelection: (row) => isBranchAnchorRow(row.original)`. Only the anchor, the first row of each branch, is selectable |
| Row checkbox | Rendered on **every** row of a branch. `isSelected = table.getRow(row.original.branch.id).getIsSelected()`. `onClickCheckbox = getToggleSelectedRowHandler({ row: anchor, table })`. On the anchor row its accessible name is `Select <branch name>` and it is in the tab order; on every other row it is named `Select <branch name> (<repository name>)` and is excluded from the tab order (FR-008) |
| Ticking any row | Toggles the anchor, so every row of that branch shows as selected (FR-008) |
| Shift-click | The range is anchored on anchor rows. `get-toggle-selected-row-handler.ts::getToggleSelectedRowHandler` stores the last-selected row **id** and resolves both indexes at shift time via `table.getRow(id).index`, so a range stays correct after a branch above expands from pending to N; if the stored id no longer exists it falls back to a plain toggle. Non-anchor rows in the range are no-ops, so the count is in branches (FR-009) |
| Header checkbox | `getIsAllRowsSelected` / `getIsSomePageRowsSelected` / `toggleAllRowsSelected` over selectable rows, which means branches |
| `selectedRows` | `table.getSelectedRowModel().flatRows.map((r) => r.original.branch)`: `BranchListItem[]`, one per selected branch, in table order. It is passed unchanged to `BranchesToolbar({ selectedBranches })`, so "N selected" and the delete modal list each branch once (SC-003) |
| Logout | The existing effect `toggleAllRowsSelected(false)` is unchanged |
| Other columns | Accessors read `r.branch.*` with explicit ids (`status`, `branched_from`, `updated_at`, `created_at`, `created_by`). `proposed_changes` and `actions` read `row.original.branch`. All repeat on every row |
