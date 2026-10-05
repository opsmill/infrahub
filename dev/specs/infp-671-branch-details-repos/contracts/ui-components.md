# Contract: UI components

Props contracts for the components this feature adds or changes, so IFC-3200 and IFC-3130 can adopt them. Each card owns its data and its page (in the URL, through `useTablePagination`); it owns no other state except ephemeral UI state.

> **2026-10-02, restructure.** The cards no longer take `isDefaultBranch`, `page` or `onPageChange`; the Tasks card no longer takes `repositoryNames`. `TablePagination` is IFC-3130's component; `TasksTable` lost its column configuration; `RefreshButton` has a single `queryKeys` prop.

## Link rule (all components below)

Every link to branch-scoped data carries the **page's** branch, not the branch selector's (spec FR-053): `constructPath(path, [getBranchQsp(branchName)])`. `getBranchQsp` (`entities/branches/ui/routing/branch-urls.ts`) sets `{ name: QSP.BRANCH, value: branchName }`. Both cards only render on non-default branches, so there is no default-branch case to drop the parameter for. Applies to the repository name, "Open repository", "Open in Tasks" and the failed-tasks link. `/tasks/<id>` links use plain `constructPath`. _(2026-10-02: replaces `getBranchQspOverride(branchName, isDefault)` and the `isDefaultBranch` prop drilled for it.)_

## `TablePagination` — `shared/components/table/table-pagination.tsx` (shared, IFC-3130)

```ts
interface TablePaginationProps {
  page: number;            // 1-based, clamped internally
  pageSize: number;
  totalCount: number;
  onPageChange: (page: number) => void;
  className?: string;
  "aria-label"?: string;   // this PR: the nav landmark's name, default "Pagination"
}
```

- IFC-3130's file, verbatim, plus two additions that must also land in IFC-3130: the `aria-label` prop (the branch page passes "Repositories pagination" and "Tasks pagination", so its two pagers are distinct landmarks) and `focusVisibleStyle` on the native buttons.
- Renders `<nav aria-label={ariaLabel}>` with a `role="status"` window text ("Showing X to Y of Z"), previous/next buttons (`aria-label` "Previous page"/"Next page", disabled at the ends) and page buttons (`aria-label="Page N"`, `aria-current="page"` on the current one), ellipses `aria-hidden`.
- Callers render it only when `count > PAGE_SIZE`.

## `BranchRepositoriesCard` — `entities/repository/ui/branch-repositories/branch-repositories-card.tsx`

```ts
interface BranchRepositoriesCardProps {
  branchName: string;   // the page's branch, never the selector's
  syncWithGit: boolean; // off: list read-only repositories only
}
```

- Owns its page (`useTablePagination({ urlKey: "repositories" })` → `repositories_page`), its data (Q1 page, Q1b health, Q2/Q2b per band through `ui/queries/`) and the "Show all" toggle.
- Computes `isSyncing = isAnyRepositorySyncing(health)` once and passes it to the page query and the bands.
- Children (same folder): `branch-repositories-table.tsx` (a plain hand-written table of one page's rows), `repository-row.tsx`, `git-state-pill.tsx`, `repository-error-bands.tsx` (list + summary line + toggle), `import-error-band.tsx`, `unreachable-band.tsx`, `branch-repositories-states.tsx` (loading, denied, empty, failed). The card renders the fixed-height wrapper and the pager.
- Rows come in the server's name order; failing ones are not moved to page 1, the bands show them whichever page the table is on.
- Test ids: `branch-repositories-card`, `branch-repositories-table`, `repository-error-band`.
- Each band is a `role="status"` (polite) region: bands render as the page loads, so an assertive alert would interrupt on every visit. The row's unreachable icon shows its reason in a `Tooltip` as well as its `aria-label`.

## `BranchTasksCard` — `entities/tasks/ui/branch-tasks/branch-tasks-card.tsx`

```ts
interface BranchTasksCardProps {
  branchName: string;
}
```

- Owns its page (`useTablePagination({ urlKey: "tasks" })` → `tasks_page`) and its data (Q3, Q4, Q5).
- Related names: one `useGetRepositoryNames({ branchName, ids: getRelatedNodeIds(page.tasks) })` (`repository/ui/queries`, a cross-entity `ui` import the layering table allows), so the Tasks card no longer needs the whole repository list from `BranchDetails`.
- Header: title "Tasks", count badge (after load), "<N> failed" (N > 0), `LinkButton` "Open in Tasks" → `constructPath("/tasks", [getBranchQsp(branchName), <branch__value filter>])`; the "<N> failed" link adds the `state__value` = `FAILED` filter.
- Body: the shared `TasksTable` inside the fixed-height wrapper (`data-testid="tasks-table"`), then the pager.
- Test id: `branch-tasks-card`.

## `TasksTable` — `entities/tasks/ui/tasks-table/tasks-table.tsx`

```ts
interface TasksTableProps {
  tasks: TaskListItem[];
  relatedNames: ReadonlyMap<string, string>; // node id → name for the Related column
  emptyRelatedLabel: string;                 // Related text for a task with no related node
}
```

- A plain table with the columns Title (link to `/tasks/<id>`), State, Workflow (`getWorkflowLabel`), Related (`getTaskRelatedLabel`), Updated. Failed and crashed rows are tinted.
- _(2026-10-02: the `columns` / `ALL_TASK_COLUMNS` configuration API is gone: it had one caller. The pager moved to the card. IFC-3245 generalises this table; see `follow-up-tasks-table.md`.)_

## `BranchDetailsHeader` — `entities/branches/ui/branch-details/branch-details-header.tsx`

```ts
interface BranchDetailsHeaderProps { branch: BranchListItem }
```

- `HeaderContainer` row: `h1` name (truncate, `title`), `CopyToClipboardButton data={name} aria-label="Copy branch name"`, `NodeMetadataPopover`, default/status badge, `RefreshButton className="ml-auto" queryKeys={[branchesQueryKeys.all, repositoryQueryKeys.all, tasksQueryKeys.all]}`; description paragraph below.

## `RefreshButton` — `entities/nodes/object/ui/object-details/refresh-button.tsx` (changed)

```ts
interface RefreshButtonProps extends ButtonProps {
  queryKeys?: ReadonlyArray<readonly unknown[]>; // default [objectQueryKeys.all]
}
```

- Busy only while a refresh the user started is running (from the press until every key's invalidation has settled), not while a background poll fetches a query under the same keys; invalidates every key on press; "Last data refresh" is the newest `dataUpdatedAt` among the **active queries under those keys** (it used to read every active query in the app).
- _(2026-10-02: `queryKey` is gone; the Tasks page passes `queryKeys={[tasksQueryKeys.all]}`. The button stays in `entities/nodes/object/ui/object-details/`: moving it would touch five callers for no behaviour change.)_

## `BranchDetails` — `entities/branches/ui/branch-details.tsx` (changed)

```ts
interface BranchDetailsProps { branchName: string }
```

The Details tab's column: `BranchAttributes` (inside `Card` + `CardHeader "Details"`) → `BranchRepositoriesCard branchName syncWithGit` → action row (the five existing buttons) → `BranchTasksCard branchName`. Non-default branches only for everything after the Details card. It fetches nothing for the cards. _(2026-10-02: `BranchTasksSection` and its second repositories query are gone, and the Details tab page no longer owns page state.)_

## `BranchTabs` / `pages/branches/details.tsx` (changed)

Tab row uses the object page's row classes; body wraps the `Outlet` in `Col className="gap-0 p-1"` + `Card variant="panel"`.
