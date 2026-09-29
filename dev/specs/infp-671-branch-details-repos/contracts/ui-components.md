# Contract: UI components

Props contracts for the components this feature adds or changes, so IFC-3200 and IFC-3130 can adopt them. All are controlled where state is shareable (page in the URL) and own only ephemeral UI state.

## Link rule (all components below)

Every link to branch-scoped data carries the **page's** branch, not the branch selector's: `constructPath(path, [{ name: QSP.BRANCH, value: branchName }])`, with no `branch` parameter for the default branch (spec FR-053). Applies to the repository name, "Open repository", "Open in Tasks" and the failed-tasks link. `/tasks/<id>` links use plain `constructPath`.

## `TablePagination` — `shared/components/table/table-pagination.tsx` (new, shared)

```ts
interface TablePaginationProps {
  page: number;            // 1-based, clamped internally
  pageSize: number;
  totalCount: number;
  onPageChange: (page: number) => void;
  className?: string;
}
```

- Renders `<nav aria-label="Pagination">` with a `role="status"` window text ("Showing X to Y of Z"), previous/next buttons (`aria-label` "Previous page"/"Next page", disabled at the ends) and page buttons (`aria-label="Page N"`, `aria-current="page"` on the current one), ellipses `aria-hidden`.
- Callers render it only when `getTotalPages(...) > 1`.
- Same path and props as IFC-3130's component; on merge, IFC-3130's version wins.

## `BranchRepositoriesCard` — `entities/repository/ui/branch-repositories/branch-repositories-card.tsx` (new)

```ts
interface BranchRepositoriesCardProps {
  branchName: string;
  syncWithGit: boolean;
  page: number;
  onPageChange: (page: number) => void;
}
```

- Owns its data (Q1, Q2 through `ui/queries/`), the "Show all" toggle, and nothing else.
- Children (same folder): `branch-repositories-table.tsx` (rows + fixed height + pager), `repository-row.tsx`, `git-state-pill.tsx`, `repository-error-bands.tsx` (list + summary line + toggle), `import-error-band.tsx`, `unreachable-band.tsx`, `branch-repositories-states.tsx` (loading, denied, empty, failed).
- Siblings that need the repositories (the Tasks card's Related column) read the same query through `BranchDetails`, never through this card's props.
- Test ids: `branch-repositories-card`, `repository-error-band`.

## `BranchTasksCard` — `entities/tasks/ui/branch-tasks/branch-tasks-card.tsx` (new)

```ts
interface BranchTasksCardProps {
  branchName: string;
  page: number;
  onPageChange: (page: number) => void;
  repositoryNames: ReadonlyMap<string, string>; // id → name, for the Related column; empty when unknown/denied
}
```

- `repositoryNames` is built by `BranchDetails` (which reads `useGetBranchRepositories` with the same params as the card; TanStack dedupes the request), so `tasks/ui` never imports `repository`.
- Children: `branch-tasks-table.tsx`, `branch-tasks-states.tsx`.
- Header: title "Tasks", count badge (after load), "<N> failed" (N > 0), `LinkButton` "Open in Tasks" → `constructPath("/tasks")`.
- Title cell: `Link to={constructPath(\`/tasks/${id}\`)}` filling the cell.
- Test id: `branch-tasks-card` (replaces `tasks-accordion` in e2e).

## `BranchDetailsHeader` — `entities/branches/ui/branch-details/branch-details-header.tsx` (new)

```ts
interface BranchDetailsHeaderProps { branch: BranchListItem }
```

- `HeaderContainer` row: `h1` name (truncate, `title`), `CopyToClipboardButton data={name} aria-label="Copy branch name"`, `NodeMetadataPopover`, default/status badge, `RefreshButton className="ml-auto" queryKeys={…}`; description paragraph below.

## `RefreshButton` — `entities/nodes/object/ui/object-details/refresh-button.tsx` (changed)

```ts
interface RefreshButtonProps extends ButtonProps {
  queryKey?: readonly unknown[];                       // unchanged
  queryKeys?: ReadonlyArray<readonly unknown[]>;       // new; wins over queryKey when set
}
```

- Busy while any watched key is fetching; invalidates every key on press. Existing callers unchanged.

## `BranchDetails` — `entities/branches/ui/branch-details.tsx` (changed)

Becomes the Details tab's column: `BranchAttributes` (inside `Card` + `CardHeader "Details"`) → `BranchRepositoriesCard` → action row (the five existing buttons) → `BranchTasksCard`. Non-default branches only for everything after the Details card. The tasks accordion and its `TaskDisplay` usage are removed from this page; `TaskDisplay` stays (the proposed change details page still uses it).

## `BranchTabs` / `pages/branches/details.tsx` (changed)

Tab row uses the object page's row classes; body wraps the `Outlet` in `Col className="gap-0 p-1"` + `Card variant="panel"`.
