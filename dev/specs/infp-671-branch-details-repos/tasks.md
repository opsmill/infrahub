# Tasks: Branch details — Git repositories and tasks

**Input**: Design documents from `dev/specs/infp-671-branch-details-repos/`
**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md)

**Tests**: Included. The constitution (IV) requires unit, component and e2e tests for user-facing features, and the handoff names a component test per scenario fixture, the 10/11 pagination boundary and an e2e for "import error band links to the task page".

**Conventions for every task**: paths are relative to the repo root; frontend paths are under `frontend/app/`. React Compiler is on: no `useMemo`/`useCallback`/`React.memo`. Theme tokens only, no hex (research R8). Entity layer per `dev/knowledge/frontend/entities-structure.md`; never import another entity's `api/`. Tests sit next to their source (`*.test.ts(x)`), render with `frontend/app/tests/components/render`, and mock query hooks with `vi.mock` (see `frontend/app/src/entities/repository/ui/repository-menu-section.test.tsx`). Visual reference: `git show ple-design-branch-details-repos:frontend/app/src/pages/_proto/branch-details/revs/rev-06/<file>`; rewrite, don't copy `_proto/` code verbatim.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on an unfinished task)
- **[Story]**: US1–US5 from spec.md

---

## Phase 1: Setup

**Purpose**: Verify the riskiest assumption and add the URL keys everything else reads.

- [ ] T001 Verify the import-task lookup (research R2) against a running stack: on a test branch, put a repository in Import Error through each path (initial add `git-repository-add-read-write`, "Import current commit" `git-repository-import-object`, periodic `sync-git-repo-with-origin`, read-only `git-repository-pull-read-only`/`git-read-only-repository-import-last-commit`) and run `InfrahubTask(branch, related_node__ids: [repo], workflow: IMPORT_WORKFLOWS, limit: 1, log_limit: 500)` in the GraphiQL sandbox. Record, per path, whether the task is found and whether its last `error`/`critical` log line is the real cause, in a new "R2 verification results" section at the end of `dev/specs/infp-671-branch-details-repos/research.md`. Non-blocking for the UI (the band has a fallback); it decides which path T058's e2e seeds.
- [ ] T002 Add `REPOSITORIES_PAGE: "repos_page"` and `TASKS_PAGE: "tasks_page"` to `QSP` in `frontend/app/src/shared/config/qsp.ts`.

---

## Phase 2: Foundational (blocking)

**Purpose**: Shared pagination, the refresh and link helpers, and the Details tab skeleton that every story plugs into.

- [ ] T003 [P] Create `frontend/app/src/shared/utils/table-pagination.ts` with `TABLE_PAGE_SIZE = 10`, `TABLE_ROW_HEIGHT_PX = 40`, `getTotalPages`, `clampPage`, `getPageItems`, `formatPageWindow` (data-model § Pagination state; logic from rev-06 `table-pagination.tsx`), and `frontend/app/src/shared/utils/table-pagination.test.ts` covering: 0, 10, 11 and 40 rows; page 0, negative, `NaN`, past the end; ellipsis windows at first, middle and last pages; "Showing X of Z" when first = last.
- [ ] T004 Create `TablePagination` in `frontend/app/src/shared/components/table/table-pagination.tsx` per `contracts/ui-components.md` (nav `aria-label="Pagination"`, `role="status"` window text, Previous/Next `aria-label`s and disabled ends, `Page N` buttons with `aria-current`, `aria-hidden` ellipses), using `buttonVariants` from `@infrahub/ui`, lucide chevrons and theme tokens (`text-foreground-muted`, `hover:bg-content-muted`), and `frontend/app/src/shared/components/table/table-pagination.test.tsx` (renders window text, calls `onPageChange` with the right page, disables Previous on page 1 and Next on the last page). Depends on T003.
- [ ] T005 [P] Extend `RefreshButton` in `frontend/app/src/entities/nodes/object/ui/object-details/refresh-button.tsx` with optional `queryKeys?: ReadonlyArray<readonly unknown[]>` (wins over `queryKey`): invalidate every key on press, busy while any is fetching (`useIsFetching` with a `predicate` matching any key prefix). Keep the single-key behaviour for existing callers. Add cases to `frontend/app/src/entities/nodes/object/ui/object-details/refresh-button.test.tsx` for multiple keys.
- [ ] T006 [P] Add `withBranch(path: string, branchName: string, isDefault: boolean): string` to `frontend/app/src/entities/branches/ui/routing/branch-urls.ts`, returning `constructPath(path, [{ name: QSP.BRANCH, value: branchName }])` for a non-default branch and `constructPath(path)` with the `branch` parameter removed for the default branch (check `constructPath`'s `overrideParams` semantics in `frontend/app/src/shared/api/rest/fetch.ts::constructPath` for removal). Add `frontend/app/src/entities/branches/ui/routing/branch-urls.test.ts` cases: selector on `main`, page on `feature` → link has `branch=feature`; default branch → no `branch`.
- [ ] T007 [P] Extend `frontend/app/src/entities/repository/domain/model/repository.ts` with `REPOSITORY_SYNC_STATUS_IMPORT_ERROR`, `REPOSITORY_SYNC_STATUS_SYNCING = "syncing"`, `REPOSITORY_OPERATIONAL_ERRORS`, `REPOSITORY_FETCH_LIMIT = 500`, `IMPORT_WORKFLOWS`, `IMPORT_LOG_LIMIT = 500`, `MAX_VISIBLE_BANDS = 3` (values in data-model.md and research R2).
- [ ] T008 Restructure `BranchDetails` in `frontend/app/src/entities/branches/ui/branch-details.tsx` into the column of FR-005: `BranchAttributes` wrapped in an `@infrahub/ui` `Card` + `CardHeader` "Details" (drop `w-fit` on the inner card or render `BranchAttributes`' content inside the new card; keep its content unchanged), then — non-default branches only — a placeholder slot for the repositories card, today's action `Row` (Merge, Propose change, Rebase, Validate, Delete, unchanged), and a placeholder slot for the tasks card. Remove the tasks `Accordion` + `TaskDisplay` usage from this file (keep `TaskDisplay` itself; `entities/proposed-changes/ui/proposed-change-details.tsx` still uses it). Add props `reposPage`, `onReposPageChange`, `tasksPage`, `onTasksPageChange`.
- [ ] T009 Make `frontend/app/src/pages/branches/branch-details/details-tab.tsx` own the page parameters: read `QSP.REPOSITORIES_PAGE` and `QSP.TASKS_PAGE` with `nuqs` `useQueryState(…, parseAsInteger.withDefault(1))` and pass value/setter into `BranchDetails` (research R6). Depends on T002, T008.

**Checkpoint**: Details tab renders Details card + action row; no accordion; pagination primitives tested.

---

## Phase 3: User Story 1 — See every repository's Git state (P1) 🎯 MVP

**Goal**: The Git repositories card with rows, ranking, pagination and its loading/denied/empty/failed states.

**Independent Test**: spec US1 — 12 repositories, one in Import Error, one read-only: failing repo first, tag shown, schema pill colours, 10 rows + pager; 10 repos → no pager; 11 → page 2 same height.

### Tests for User Story 1

- [ ] T010 [P] [US1] Unit tests `frontend/app/src/entities/repository/domain/rules/rank-repositories.test.ts`: `hasImportError`, `isRepositoryUnreachable` (`error-cred`, `error-connection`, `error` true; `online`, `unknown`, `null` false), `getRepositoryRank`, `rankRepositories` (import error → unreachable → rest, name order inside groups, stable, doesn't mutate input), `getFailingRepositories`, `getBandKind` (import error wins when both).
- [ ] T011 [P] [US1] Unit tests `frontend/app/src/entities/repository/domain/use-cases/get-branch-repositories.test.ts` with the api function mocked: maps nodes to `BranchRepository` (name fallback to `display_label` then `id`, `isReadOnly` from `__typename`, null commit); `syncWithGit: false` queries the read-only kind; `PERMISSION_DENIED` in `errors[].extensions` → `{ status: "denied" }`; other errors throw; `isTruncated` when `count > edges.length`.
- [ ] T012 [P] [US1] Scenario fixtures in `frontend/app/tests/fake/branch-repositories.ts`: builders for `BranchRepository` and the results of the prototype scenarios trimmed to real fields (`incident`/`import-error`, `unreachable`, `many-errors` = 40 repos with 5 import errors at positions 2, 3, 7, 12, 18, `all-clear`, `no-repos` Sync off, `exactly-10`, `eleven`), with schema-like `sync_status` label/colour values (`In Sync`, `Import Error`, `Syncing`, `Unknown`).

### Implementation for User Story 1

- [ ] T013 [P] [US1] Create `BranchRepository` and `BranchRepositoriesResult` types in `frontend/app/src/entities/repository/domain/model/branch-repository.ts` (data-model.md).
- [ ] T014 [US1] Implement the rules in `frontend/app/src/entities/repository/domain/rules/rank-repositories.ts` to pass T010. Depends on T007, T013.
- [ ] T015 [US1] Create `frontend/app/src/entities/repository/api/get-branch-repositories-from-api.ts`: two static `gql.tada` documents (`CoreGenericRepository`, `CoreReadOnlyRepository`) with the selection in `contracts/graphql-queries.md` Q1, called with `context: { branch: branchName }` and `limit: REPOSITORY_FETCH_LIMIT`; return `{ data, errors }` unthrown. Run `pnpm codegen` if the `gql.tada` cache needs regenerating.
- [ ] T016 [US1] Implement `getBranchRepositories({ branchName, syncWithGit })` in `frontend/app/src/entities/repository/domain/use-cases/get-branch-repositories.ts` to pass T011, detecting permission errors with `parseCatalogueError` and `ERROR_CODES.PERMISSION_DENIED` from `frontend/app/src/shared/api/errors` (research R11). Depends on T013, T015.
- [ ] T017 [US1] Create `repositoryQueryKeys` in `frontend/app/src/entities/repository/ui/queries/repository.query-keys.ts` (`all`, `branch`, `importError`, research R7) and `useGetBranchRepositories` + `getBranchRepositoriesQueryOptions` in `frontend/app/src/entities/repository/ui/queries/get-branch-repositories.query.ts`, with `refetchInterval` returning 10 000 only while a returned repository is syncing (research R4). Depends on T016.
- [ ] T018 [P] [US1] Create `GitStatePill` in `frontend/app/src/entities/repository/ui/branch-repositories/git-state-pill.tsx`: schema `color` background with `getTextColor` (pattern: `frontend/app/src/entities/homepage/ui/git-repository.tsx::GitRepositoryItem`), `label`; raw value in a neutral token tag when label/colour are missing; `description` as tooltip when present.
- [ ] T019 [US1] Create `RepositoryRow` in `frontend/app/src/entities/repository/ui/branch-repositories/repository-row.tsx`: 40px row; name link to `withBranch(getObjectDetailsUrl(kind, id), branchName, isDefault)` truncated with `title`; "Read-only" tag; `GitStatePill`; warning icon with `aria-label` from the operational status label when unreachable (FR-012); commit in monospace `tabular-nums` on `bg-info-surface`, truncated with `title`, placeholder "—" when null. Depends on T006, T014, T018.
- [ ] T020 [US1] Create `BranchRepositoriesTable` in `frontend/app/src/entities/repository/ui/branch-repositories/branch-repositories-table.tsx`: headers Repository / Git state / Commit on `bg-content-muted`; ranks, clamps `page`, slices 10; container `min-height` = `(TABLE_PAGE_SIZE + 1) * TABLE_ROW_HEIGHT_PX` when more than one page; `TablePagination` only when more than one page; truncation notice with a link to the repository list when `isTruncated`. Depends on T004, T019.
- [ ] T021 [P] [US1] Create the card states in `frontend/app/src/entities/repository/ui/branch-repositories/branch-repositories-states.tsx`: loading (3 `Skeleton` rows at 40px, `role="status"`, `aria-busy`, sr-only "Loading repositories"), denied (lock icon, "You don't have access to this branch's repositories", "Ask an administrator for permission to view repositories."), empty-not-synced ("Not synchronised with Git" + "This branch was created with Sync with Git off, so repository imports and generators don't run on it."), empty-none ("No Git repositories" + one line), failed ("Repositories couldn't be loaded.").
- [ ] T022 [US1] Create `BranchRepositoriesCard` in `frontend/app/src/entities/repository/ui/branch-repositories/branch-repositories-card.tsx` per `contracts/ui-components.md` (props `branchName`, `isDefaultBranch`, `syncWithGit`, `page`, `onPageChange`; `Card` + `CardHeader` "Git repositories" with a `Badge variant="blue"` rounded count once loaded; `data-testid="branch-repositories-card"`), leaving a slot under the table for the bands (US2). Depends on T017, T020, T021.
- [ ] T023 [US1] Component tests `frontend/app/src/entities/repository/ui/branch-repositories/branch-repositories-card.test.tsx` using T012 fixtures and a mocked `useGetBranchRepositories`: US1 scenarios 1–9; 10 rows → no pager; 11 rows → page 2 has 1 row and the table container keeps its min-height; `many-errors` → every import-error repository on page 1; repository links carry `branch=<page branch>` (FR-053); no hex colour in rendered `class` attributes. Depends on T012, T022.
- [ ] T024 [US1] Mount `BranchRepositoriesCard` in the repositories slot of `frontend/app/src/entities/branches/ui/branch-details.tsx` with `branch.sync_with_git`, `branch.is_default` and the `reposPage` props from T008/T009. Depends on T009, T022.

**Checkpoint**: US1 independently testable on a real branch (quickstart rows 1–3).

---

## Phase 4: User Story 2 — Read why an import failed (P1)

**Goal**: Red import-error bands with the last error line and task link, amber unreachable bands, 3 + "Show all".

**Independent Test**: spec US2 — one repository failing with a known log line, one `error-cred`: red band with the verbatim line and working "View task log"; amber band with "Open repository"; 5 bands → 3 + summary + Show all.

### Tests for User Story 2

- [ ] T025 [P] [US2] Unit tests `frontend/app/src/entities/repository/domain/rules/get-last-error-line.test.ts`: picks the last `error` or `critical` (any case), ignores `info`/`warning`, keeps inner newlines, trims trailing whitespace, returns `null` for no logs or no error line.
- [ ] T026 [P] [US2] Unit tests `frontend/app/src/entities/repository/domain/use-cases/get-repository-import-error.test.ts` with the api mocked: task with error line → `found`; task without → `not-found` with `taskId`; no task → `not-found` with `taskId: null`; api error → `not-found` with `taskId: null` (the band never disappears, data-model § State transitions); variables carry `branch`, `[repositoryId]`, `IMPORT_WORKFLOWS`, `limit` 1, `IMPORT_LOG_LIMIT`.

### Implementation for User Story 2

- [ ] T027 [US2] Implement `getLastErrorLine` in `frontend/app/src/entities/repository/domain/rules/get-last-error-line.ts` to pass T025.
- [ ] T028 [US2] Create `frontend/app/src/entities/repository/api/get-repository-import-task-from-api.ts` with the Q2 document from `contracts/graphql-queries.md`.
- [ ] T029 [US2] Implement `getRepositoryImportError({ branchName, repositoryId })` in `frontend/app/src/entities/repository/domain/use-cases/get-repository-import-error.ts` to pass T026. Depends on T027, T028.
- [ ] T030 [US2] Create `useGetRepositoryImportError({ branchName, repositoryId, isSyncing })` in `frontend/app/src/entities/repository/ui/queries/get-repository-import-error.query.ts` with key `repositoryQueryKeys.importError(…)` and the same polling rule as T017. Depends on T017, T029.
- [ ] T031 [P] [US2] Create `ImportErrorBand` in `frontend/app/src/entities/repository/ui/branch-repositories/import-error-band.tsx`: calls `useGetRepositoryImportError` itself (so collapsed bands never fetch); `bg-danger-surface`, top border in a danger token, alert icon; "<name> — import failed"; `found` → message in a monospace `whitespace-pre-wrap break-words` paragraph (text only) + `Link` "View task log →" to `constructPath(\`/tasks/${taskId}\`)`; `not-found` → "The error details couldn't be found for this import." + link to the task when `taskId`, else "Open repository" via `withBranch`; loading → name + "Loading the import log…". `data-testid="repository-error-band"`.
- [ ] T032 [P] [US2] Create `UnreachableBand` in `frontend/app/src/entities/repository/ui/branch-repositories/unreachable-band.tsx`: `bg-warning-surface`, `border-warning-border`, triangle icon; "<name> — <operational status label>"; "Infrahub can't fetch new commits, so the commit shown may be out of date. Check the repository's credentials and location."; "Open repository" via `withBranch`. `data-testid="repository-error-band"`.
- [ ] T033 [US2] Create `RepositoryErrorBands` in `frontend/app/src/entities/repository/ui/branch-repositories/repository-error-bands.tsx`: takes all repositories, uses `getFailingRepositories` + `getBandKind`, shows the first `MAX_VISIBLE_BANDS` or all (local `useState`), and when more than 3 a summary line "<N> more repositories with errors: <names>" (singular "repository" for 1) with a ghost `Button` "Show all"/"Collapse" (text changes to "<N> repositories with errors" when expanded). Depends on T014, T031, T032.
- [ ] T034 [US2] Mount `RepositoryErrorBands` under the table in `frontend/app/src/entities/repository/ui/branch-repositories/branch-repositories-card.tsx` (only in the `ok` non-empty state), passing the syncing flag. Depends on T022, T033.
- [ ] T035 [US2] Component tests `frontend/app/src/entities/repository/ui/branch-repositories/repository-error-bands.test.tsx` with a mocked `useGetRepositoryImportError`: US2 scenarios 1–6; bands cover failing repositories on other pages (FR-024); only the first 3 bands call the hook until "Show all"; "View task log" href is `/tasks/<id>`; "Open repository" carries `branch=<page branch>`. Depends on T034.

**Checkpoint**: US1 + US2 cover the incident's import failure (quickstart row 4).

---

## Phase 5: User Story 3 — Act on the branch from the same place (P1)

**Goal**: The five buttons below the repositories card, behaviour unchanged, Merge ungated.

**Independent Test**: spec US3 — on a branch with a failing import, all five buttons below the card in order; Merge enabled and merges.

- [ ] T036 [US3] Component test `frontend/app/src/entities/branches/ui/branch-details.test.tsx` (mock `useGetBranchDetails`, the repositories and tasks hooks): on a non-default branch the order is Details card → `branch-repositories-card` → buttons Merge, Propose change, Rebase, Validate, Delete → `branch-tasks-card` (placeholder until US4); `BranchMergeButton` receives exactly `{ branch }` whatever the repositories/tasks state (FR-031; spy on the module with `vi.mock`); default branch → Details card only, no buttons, no cards. Depends on T024.
- [ ] T037 [US3] Update `tests/e2e/branches/test_branch_details.py` so the action-button assertions still pass with the new layout (buttons found by role and name, as today), and add an assertion that the Git repositories card (`branch-repositories-card`) renders above the Merge button on a non-default branch and is absent on the default branch. Depends on T024.

---

## Phase 6: User Story 4 — See every task that ran on the branch (P2)

**Goal**: The server-paginated Tasks card replacing the accordion.

**Independent Test**: spec US4 — 12 tasks: 10 newest, pager, count 12, "1 failed", title opens `/tasks/<id>`.

### Tests for User Story 4

- [ ] T038 [P] [US4] Unit tests `frontend/app/src/entities/tasks/domain/model/workflow-labels.test.ts` for every mapping in research R9, `null` → "—", unknown id → itself.
- [ ] T039 [P] [US4] Unit tests `frontend/app/src/entities/tasks/domain/rules/get-task-related-label.test.ts`: known repository → its name; several related nodes → first known repository wins; none → "This branch"; other kind → `getKindLabel(kind)` or the kind.
- [ ] T040 [P] [US4] Unit tests `frontend/app/src/entities/tasks/domain/use-cases/get-branch-tasks.test.ts` with `getTaskListFromApi` mocked: returns `{ tasks, count }`, drops null nodes/related nodes, passes `branchName`, `offset`, `limit`; errors throw.

### Implementation for User Story 4

- [ ] T041 [P] [US4] Create `BranchTask`/`BranchTasksPage` in `frontend/app/src/entities/tasks/domain/model/branch-task.ts` (data-model.md).
- [ ] T042 [P] [US4] Implement `getWorkflowLabel` in `frontend/app/src/entities/tasks/domain/model/workflow-labels.ts` to pass T038 (reuse `BRANCH_VALIDATE_WORKFLOW`, `BRANCH_REBASE_WORKFLOW`, `BRANCH_MERGE_WORKFLOW` from `frontend/app/src/entities/tasks/domain/model/task.ts`; the tasks entity keeps its own copy of the import workflow ids rather than importing `repository`).
- [ ] T043 [P] [US4] Implement `getTaskRelatedLabel` in `frontend/app/src/entities/tasks/domain/rules/get-task-related-label.ts` to pass T039.
- [ ] T044 [US4] Implement `getBranchTasks` in `frontend/app/src/entities/tasks/domain/use-cases/get-branch-tasks.ts` over `GET_TASK_LIST` from `frontend/app/src/entities/tasks/api/get-task-list-from-api.ts` to pass T040. Depends on T041.
- [ ] T045 [US4] Add `branchList` to `tasksQueryKeys` in `frontend/app/src/entities/tasks/ui/queries/tasks.query-keys.ts`, and create `useGetBranchTasks({ branchName, page })` (offset from page, `limit: TABLE_PAGE_SIZE`, `refetchInterval: page === 1 ? 10_000 : false`, `placeholderData: keepPreviousData`) and `useGetBranchFailedTaskCount({ branchName })` (reuses `getTaskCount` with `state: [TASK_STATE_FAILED, TASK_STATE_CRASHED]`, 10s) in `frontend/app/src/entities/tasks/ui/queries/get-branch-tasks.query.ts`. Depends on T044.
- [ ] T046 [US4] Create `BranchTasksTable` in `frontend/app/src/entities/tasks/ui/branch-tasks/branch-tasks-table.tsx`: columns Title (`Link` to `constructPath(\`/tasks/${id}\`)` as a `block truncate leading-10` cell-filling target, `title` attribute), State (`getLogBadge` from `frontend/app/src/entities/tasks/ui/task-display.tsx`, gray "UNKNOWN" fallback), Workflow (`getWorkflowLabel`), Related (`getTaskRelatedLabel` with `repositoryNames` and schema labels via `useSchema` when available), Updated (`DateDisplay`); failed rows tinted with `bg-danger-surface`; fixed min-height and `TablePagination` as T020, `totalCount` from the server. Depends on T004, T042, T043, T045.
- [ ] T047 [P] [US4] Create the tasks states in `frontend/app/src/entities/tasks/ui/branch-tasks/branch-tasks-states.tsx`: loading (3 skeleton rows, `role="status"`), empty ("No tasks have run on this branch yet. Imports, generators and validations appear here as they run."), failed ("Task results didn't load.").
- [ ] T048 [US4] Create `BranchTasksCard` in `frontend/app/src/entities/tasks/ui/branch-tasks/branch-tasks-card.tsx` per `contracts/ui-components.md` (props `branchName`, `isDefaultBranch`, `page`, `onPageChange`, `repositoryNames`): `CardHeader` "Tasks", count badge after load, "<N> failed" when N > 0 with a `Tooltip` ("Failed tasks on this branch, including runs retried since.") linking to the Tasks page on this branch filtered to failed states (use the Tasks page's existing `filters` parameter as written by `frontend/app/src/entities/tasks/ui/task-filters.tsx`), `LinkButton` "Open in Tasks" to `withBranch("/tasks", …)`; `data-testid="branch-tasks-card"`. Depends on T006, T046, T047.
- [ ] T049 [US4] Component tests `frontend/app/src/entities/tasks/ui/branch-tasks/branch-tasks-card.test.tsx` with mocked hooks: US4 scenarios 1–8; page 2 keeps the min-height; title href `/tasks/<id>`; "Open in Tasks" and failed link carry `branch=<page branch>`; no count while loading; only page 1 polls (assert the hook is called with the page). Depends on T048.
- [ ] T050 [US4] Mount `BranchTasksCard` in the tasks slot of `frontend/app/src/entities/branches/ui/branch-details.tsx`: call `useGetBranchRepositories` with the same params as the card (deduped) to build `repositoryNames: Map<id, name>` (empty map when loading/denied/failed), and pass `tasksPage` props from T009. Depends on T017, T048.
- [ ] T051 [US4] In `tests/e2e/branches/test_branch_details.py`, replace both `tasks-accordion` assertions with `branch-tasks-card` (hidden on the default branch, visible on a non-default branch), and add: after running Validate, a "Validate" row appears and its title opens `/tasks/<id>`. Depends on T050.

---

## Phase 7: User Story 5 — A branch page that looks like every other detail page (P3)

**Goal**: Object-page header, tab row and panel body; one Refresh for everything.

**Independent Test**: spec US5 — header parts present, copy button named "Copy branch name", Refresh refetches branch details, repositories, bands and tasks.

- [ ] T052 [US5] Create `BranchDetailsHeader` in `frontend/app/src/entities/branches/ui/branch-details/branch-details-header.tsx` per `contracts/ui-components.md`: `HeaderContainer` from `frontend/app/src/entities/nodes/object/ui/object-details/object-details-header.tsx`, `h1` (truncate, `title`), `CopyToClipboardButton` with `aria-label="Copy branch name"`, `NodeMetadataPopover objectKind="InfrahubBranch"`, `BranchDefaultBadge` or `BranchStatusBadge`, `RefreshButton className="ml-auto" queryKeys={[branchesQueryKeys.details({ branchName }), repositoryQueryKeys.all, tasksQueryKeys.all]}`; description paragraph under the row. Depends on T005, T017, T045.
- [ ] T053 [US5] Component test `frontend/app/src/entities/branches/ui/branch-details/branch-details-header.test.tsx`: parts and order, copy button accessible name, default vs status badge, description only when set, `RefreshButton` receives the three keys. Depends on T052.
- [ ] T054 [US5] In `frontend/app/src/pages/branches/details.tsx::BranchDetailsContent`, replace the `<header>` with `BranchDetailsHeader` (keep `BranchWorkingNotice` above it and `useTitle`), and wrap the tabs + `Outlet` in `Col className="gap-0 p-1"` with the `Outlet` inside `Card variant="panel"` (as `frontend/app/src/entities/nodes/object/ui/object-details/object-details-body.tsx::ObjectDetailsBody`). Depends on T052.
- [ ] T055 [US5] Restyle `BranchTabs` in `frontend/app/src/entities/branches/ui/branch-tabs.tsx` to the object tab row (`Row className="items-end gap-4 px-4"`, no bottom border, as `object-details-tabs.tsx::ObjectDetailsTabs`); tabs and routes unchanged. Depends on T054.
- [ ] T056 [US5] Update `tests/e2e/branches/test_branch_details.py` for the header: the copy button is found by its accessible name "Copy branch name", and Refresh is present. Depends on T054.

---

## Phase 8: Polish & cross-cutting

- [ ] T057 [P] Dark-mode pass: switch the theme to dark on a branch with every card state (fixtures or a live branch) and fix any class that isn't a theme token; `grep -rnE "#[0-9a-fA-F]{3,6}|neutral-|red-|amber-" frontend/app/src/entities/repository/ui/branch-repositories frontend/app/src/entities/tasks/ui/branch-tasks frontend/app/src/shared/components/table` returns nothing (FR-050).
- [ ] T058 Add the e2e test "import error band links to the task page" to `tests/e2e/branches/test_branch_details.py` (or a new `tests/e2e/branches/test_branch_details_repositories.py` if the fixture setup differs): seed a repository in Import Error on a branch through the path T001 proved resolvable, open the branch page, assert the red band shows the error line and "View task log" opens `/tasks/<id>`. If no path resolves deterministically, assert the not-found fallback band instead and note it in the PR. Depends on T001, T035.
- [ ] T059 [P] Add the Towncrier fragment `changelog/+infp-671-branch-details-repositories.added.md`: one or two sentences, user-facing ("The branch details page now lists the branch's Git repositories with their Git state and commit, shows the last error of failed imports, and lists every task that ran on the branch.").
- [ ] T060 [P] Add `TablePagination` (`shared/components/table/table-pagination.tsx`, "Paginated table footer, one per table; page state owned by the caller") to the reuse inventory in `dev/knowledge/frontend/shared-components.md`, next to the existing `Pagination` row, saying when to use which.
- [ ] T061 Run the full frontend CI gate and fix every failure: `cd frontend/app && pnpm exec biome ci .`, `pnpm knip` (remove any export left unused, e.g. unused `TaskDisplay` imports), `pnpm exec betterer ci`, `pnpm test`. Depends on all implementation tasks.
- [ ] T062 Walk `quickstart.md` scenarios 1–11 against a running stack, and record the R2 verification outcome (T001) plus the follow-up backend ask (tag `git-repository-import-object` with the repository id and `sync-git-repo-with-origin` with its branch, or add `last_import_task`) in the PR description, with the INFP-670 sign-off request for ungated Merge.

---

## Dependencies & Execution Order

### Phases

- **Setup (T001–T002)**: T002 first; T001 can run any time before T058.
- **Foundational (T003–T009)**: blocks all stories. T003 → T004; T005, T006, T007 in parallel; T008 → T009.
- **US1 (T010–T024)**: after Foundational. MVP.
- **US2 (T025–T035)**: after T022 (needs the card and its band slot). Tests T025/T026 can start with US1.
- **US3 (T036–T037)**: after T024.
- **US4 (T038–T051)**: after Foundational; domain/api tasks (T038–T045) run in parallel with US1; T050 needs T017.
- **US5 (T052–T056)**: after T005, T017, T045 (the refresh keys exist).
- **Polish (T057–T062)**: after the stories they touch.

### Story independence

- US1 alone: the page shows repositories (bands slot empty, tasks slot empty).
- US2 builds on US1's card.
- US3 only verifies placement and non-regression.
- US4 is independent of US1 except for the Related names (empty map without it).
- US5 is independent of the cards except for Refresh keys.

### Parallel examples

```text
# Foundational
T003 table-pagination utils  |  T005 RefreshButton queryKeys  |  T006 withBranch  |  T007 repository constants

# US1 + US4 domain in parallel
T010 rank tests | T011 use-case tests | T012 fixtures | T013 types | T038 workflow label tests | T039 related label tests | T040 branch tasks tests | T041 task types

# US2 bands
T031 ImportErrorBand  |  T032 UnreachableBand
```

## Implementation Strategy

1. **MVP**: Phases 1–3 (US1). The branch page lists repositories with Git state and commit, failing first. Demo with quickstart rows 1–3.
2. **Incident coverage**: add US2 (bands) and US3 (buttons confirmed below). This is the design's core: evidence directly above Merge.
3. **Tasks**: US4 replaces the accordion and removes the last reason to open the Tasks page.
4. **Consistency**: US5 header/tabs/body.
5. **Polish**: dark-mode pass, e2e band link, changelog, knowledge doc, CI gate, quickstart walk.

Stop at any checkpoint to validate the story on its own.
