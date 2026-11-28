# System inventory: what exists for the schema migration views

Read on `develop` at `ee2d2dc402`. Paths are relative to `frontend/app/src/` unless they
start with `frontend/` or `backend/`.

## Where the views could be displayed

- **Schema page** (`/schema`, `pages/schema/layout.tsx`): in the menu
  (`backend/infrahub/menu/menu.py:181`). It shows the schema of the branch selected in the
  header, main included. Its header switches between List and Graph with
  `LinkToggleButtonGroup`.
- **Branch details page** (`/branches/:branchName`): tabs Details, Data, Files, Artifacts and
  Schema (`entities/branches/ui/branch-tabs.tsx`, `BranchDetailsTab` in
  `entities/branches/ui/routing/branch-urls.ts:4`). It shows no tabs for the default branch
  (`pages/branches/details.tsx:49`).
- **Proposed change page** (`/proposed-changes/:id`): tabs Overview, Data, Files, Artifacts,
  Schema, Checks and Tasks (`entities/proposed-changes/ui/tabs/`). The Schema tab shows the
  node diff filtered on the `Schema` namespace (`pages/proposed-changes/proposed-change-details/schema.tsx`).
  The branch Schema tab does the same for a branch.
- **App header** (`entities/navigation/ui/app-header.tsx`): time selector, branch selector,
  breadcrumbs, then two status buttons: `TaskStatus` (tasks running on the branch, polled
  every 10 seconds) and `RepositorySyncStatus`.
- **Task pages** (`/tasks`, `/tasks/:taskId`): the task list and task details show a
  `progress` value for each task (`entities/tasks/ui/task-items.tsx:158`,
  `entities/tasks/ui/task-item-details.tsx:123`).

## Covered

- **Tabs**: `LinkTab` (`shared/components/ui/link.tsx`) in a `<nav aria-label="Tabs">`, with
  `getBranchDetailsUrl` and `getProposedChangeDetailsUrl` to build tab links.
- **Surfaces and layout**: `Card`, `CardHeader`, `CardContent` (`@infrahub/ui`);
  `Content.Card` and `Content.CardTitle` with a count badge; `Row`, `Col`, `HeaderContainer`;
  `ScrollArea`, `ResizablePanelGroup` and `Sheet` (`@infrahub/ui`) for a side panel with the
  details of one schema change.
- **Tables**: `DataTable` (`shared/components/table/data-table.tsx`) with `getRowId` for rows
  that are not nodes; `PagedTableCard` with its loading, permission denied, failed, empty and
  past-the-end states; `TablePagination` with `useTablePagination` for more than one paged
  list on a page. The history of a branch and the violations are both paged in the
  investigation.
- **Status badges**: `Badge` (`shared/components/ui/badge.tsx`) with the variants `green`,
  `red`, `warning`, `blue`, `yellow`, `gray`, `purple` and their outline versions.
- **Actions**: `Button`, `LinkButton` (`@infrahub/ui`); `RefreshButton`; `ModalConfirm`
  (`shared/components/modals/modal-confirm.tsx`) to confirm an apply or a discard.
- **Recalculating on request**: `DiffRefreshButton` and `DiffComputing`
  (`entities/diff/ui/`). INFP-719 asks for the impact to be recalculated "in the same way as
  the diff of a proposed change".
- **Counts by change type**: `DiffSummaryTagGroup` and `DiffSummaryTag`
  (`entities/proposed-changes/ui/diff-summary/`).
- **Progress**: `Meter` (`@infrahub/ui`) for nodes processed out of the total;
  `MultipleProgressBar` (`shared/components/stats/multiple-progress-bar.tsx`) for the
  migrations of an application counted by status.
- **Dates**: `DateDisplay` and `DurationDisplay` (`shared/components/display/`).
- **Operations as text**: `CodeViewer` (`shared/components/editor/code/code-viewer.tsx`) and
  `DataViewer` (`shared/components/data-viewer/`) with copy and download buttons.
- **Expanding a row**: `Accordion` (`shared/components/display/accordion.tsx`).
- **Empty, error and loading**: `NoDataFound`, `ErrorScreen`, `UnauthorizedScreen`,
  `LoadingIndicator`, `Spinner`.
- **Schema**: `useSchema`, `useGetSchemaHash`, and `SchemaViewerModal`
  (`entities/schema/ui/schema-viewer-modal.tsx`) to open the schema of a kind from a row.
- **Permissions**: `hasGlobalPermissionQueryOptions` with `EDIT_DEFAULT_BRANCH` and
  `SUPER_ADMIN` (`entities/permission/domain/model/permission.ts`).

## Close

- **`Alert`** (`shared/components/ui/alert.tsx`): built for toasts (`closeToast`,
  `onDismiss`), with an `ALERT_TYPES` enum. It has no slot for an action button. The views
  need an inline message with an action for "the impact is out of date", "the merge rolled
  back" and "this step would fail against main".
- **`NodeDiff`** (`entities/diff/ui/node-diff/`): renders the diff tree that the backend
  calculates between two branches. A staged schema is not in a diff tree; the investigation
  returns it as operations. The schema difference of a staged schema needs a view built
  from operations. `DiffBadge` and the added, removed and updated row styles can be reused.
- **`DiffComputing`**: the text is fixed to "We are computing the diff between X and Y". The
  running impact calculation needs its own text.
- **Branch details tabs**: hidden on the default branch, so a tab there does not cover main.
- **Task progress**: one `progress` value per task. The investigation (C1) puts the
  percentage of ended migrations there. The task page has no list of migrations.
- **Permission constants**: the frontend has no `MANAGE_SCHEMA` or `MERGE_BRANCH` constant.
  The backend defines both (`backend/infrahub/core/constants/__init__.py:126` and `:131`).
  The investigation requires `MANAGE_SCHEMA` to stage, recalculate, apply and discard.
- **`ModalConfirm`**: always shows a yellow warning icon. An apply that deletes data may need
  the danger tone.
- **`PagedTableCard`**: one flat paged table per card. A history where each schema change
  opens into its applications and migrations is a nested list.

## Missing

- **Status badge for three status lists**: one map from each status of a schema change, an
  application and a migration to a `Badge` variant and a label, so every view shows a status
  the same way. Small: a constant map and a component.
- **Schema change row**: name, version, status, a one-line summary of its operations, the
  number of applications and the migrations. Used by the history, the staged schema and the
  proposed change. New entity UI.
- **Operation as a sentence**: renders one stored operation (`kind`, `op`, `section`,
  `name`, `prop`, `value`, the value before) as text, for example "LocationSite, attribute
  shortname: optional changed from true to false". New.
- **Revision line**: version of the last applied schema change, its name, the time it was
  applied, and whether a staged schema is pending. New, small.
- **Application steps**: the migrations of one application with their status and their
  node counts (completed out of total, with `Meter`). New.
- **Violations by constraint**: violations grouped by constraint, with node links, and a
  count only for kinds the viewer cannot view. `DataTable` plus a new grouping.
- **Entity layer**: no `api`, `domain` or `ui` for schema changes. The prototype reads mock
  data from a `domain`-shaped module, so the API can replace it later without changing the
  views.

Nothing has been built to fill these gaps.

## Where the prototype mounts

Every direction changes only the content area, so the prototype mounts inside the app
layout at `/_proto/schema-migrations` (`frontend/app/src/app/router.tsx`), and the history
panel receives `frame`.

The migration views read mock data from `frontend/app/src/pages/_proto/schema-migrations/context.tsx`.
The app shell (login, branches, schema) needs a running Infrahub API. On this machine the
only one is the field-sections stack on `localhost:8002`, which accepts browser requests
only from `localhost:8080` and `localhost:8095`, both in use. The dev server therefore runs
on port 8097 with a proxy for `/api` and `/graphql` to `localhost:8002`, and
`VITE_INFRAHUB_API_SERVER_URL=http://localhost:8097` (read by
`frontend/app/src/shared/config/config.ts` in development only).
