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

- [ ] T001 Verify the import-task lookup (research R2) against a running stack: on a test branch, put a repository in Import Error through each path (initial add `git-repository-add-read-write`, "Import current commit" `git-repository-import-object`, periodic `sync-git-repo-with-origin`, read-only `git-repository-pull-read-only`/`git-read-only-repository-import-last-commit`) and run `InfrahubTask(branch, related_node__ids: [repo], workflow: IMPORT_WORKFLOWS, limit: 1, log_limit: 10000)` in the GraphiQL sandbox. Record, per path, whether the task is found and whether its last `error`/`critical` log line is the real cause, in a new "R2 verification results" section at the end of `dev/specs/infp-671-branch-details-repos/research.md`. Non-blocking for the UI (the band has a fallback); it decides which path T058's e2e seeds. _(Partly verified. By code reading: research.md "R2 verification results" expects every path except the worker-bootstrap import to be findable, and one read-only query confirmed the log shape of a failed flow. On the seeded stack (`utilities/branch_details_scenarios/`): the "Import current commit" (`git-repository-import-object`) task is found on a non-default branch, but a failed periodic sync (`sync-git-repo-with-origin`) was tagged with the default branch only, so the lookup on another branch found nothing (cause not traced; Follow-ups below, item 2). Not verified on a stack: the initial add (read-write and read-only), the read-only pull and the read-only "import last commit". The band's "details couldn't be found" fallback covers any path that can't be found.)_
- [X] T002 Add `REPOSITORIES_PAGE: "repos_page"` and `TASKS_PAGE: "tasks_page"` to `QSP` in `frontend/app/src/shared/config/qsp.ts`.

---

## Phase 2: Foundational (blocking)

**Purpose**: Shared pagination, the refresh and link helpers, and the Details tab skeleton that every story plugs into.

- [X] T003 [P] Create `frontend/app/src/shared/utils/table-pagination.ts` with `PAGE_SIZE = 10`, `getTotalPages`, `clampPage`, `getPageItems`, `formatPageWindow` (data-model § Pagination state; logic from rev-06 `table-pagination.tsx`), and `frontend/app/src/shared/utils/table-pagination.test.ts` covering: 0, 10, 11 and 40 rows; page 0, negative, `NaN`, past the end; ellipsis windows at first, middle and last pages; "Showing X of Z" when first = last.
- [X] T004 Create `TablePagination` in `frontend/app/src/shared/components/table/table-pagination.tsx` per `contracts/ui-components.md` (nav `aria-label="Pagination"`, `role="status"` window text, Previous/Next `aria-label`s and disabled ends, `Page N` buttons with `aria-current`, `aria-hidden` ellipses), using `buttonVariants` from `@infrahub/ui`, lucide chevrons and theme tokens (`text-foreground-muted`, `hover:bg-content-muted`), and `frontend/app/src/shared/components/table/table-pagination.test.tsx` (renders window text, calls `onPageChange` with the right page, disables Previous on page 1 and Next on the last page). Depends on T003.
- [X] T005 [P] Extend `RefreshButton` in `frontend/app/src/entities/nodes/object/ui/object-details/refresh-button.tsx` with optional `queryKeys?: ReadonlyArray<readonly unknown[]>` (wins over `queryKey`): invalidate every key on press, busy while any is fetching (`useIsFetching` with a `predicate` matching any key prefix). Keep the single-key behaviour for existing callers. Add cases to `frontend/app/src/entities/nodes/object/ui/object-details/refresh-button.test.tsx` for multiple keys.
- [X] T006 [P] Add `getBranchQspOverride(branchName: string, isDefault: boolean)` to `frontend/app/src/entities/branches/ui/routing/branch-urls.ts`, returning the `constructPath` override `{ name: QSP.BRANCH, value: branchName }` for a non-default branch and `{ name: QSP.BRANCH, exclude: true }` (the `branch` parameter removed) for the default branch; callers pass it to `constructPath` or `getObjectDetailsUrl`. _(2026-10-02: first drafted as an exported `withBranch(path, branchName, isDefault)`; `withBranch` now exists only as a test-local composer in `branch-urls.test.ts`.)_ (check `constructPath`'s `overrideParams` semantics in `frontend/app/src/shared/api/rest/fetch.ts::constructPath` for removal). Add `frontend/app/src/entities/branches/ui/routing/branch-urls.test.ts` cases: selector on `main`, page on `feature` → link has `branch=feature`; default branch → no `branch`.
- [X] T007 [P] Extend `frontend/app/src/entities/repository/domain/model/repository.ts` with `REPOSITORY_SYNC_STATUS_ERROR_VALUE`, `REPOSITORY_SYNC_STATUS_SYNCING = "syncing"`, `REPOSITORY_OPERATIONAL_ERRORS`, `REPOSITORY_FETCH_LIMIT = 500`, `IMPORT_WORKFLOWS`, `IMPORT_LOG_LIMIT = 10_000`, `MAX_VISIBLE_BANDS = 3` (values in data-model.md and research R2).
- [X] T008 Restructure `BranchDetails` in `frontend/app/src/entities/branches/ui/branch-details.tsx` into the column of FR-005: `BranchAttributes` wrapped in an `@infrahub/ui` `Card` + `CardHeader` "Details" (drop `w-fit` on the inner card or render `BranchAttributes`' content inside the new card; keep its content unchanged), then — non-default branches only — a placeholder slot for the repositories card, today's action `Row` (Merge, Propose change, Rebase, Validate, Delete, unchanged), and a placeholder slot for the tasks card. Remove the tasks `Accordion` + `TaskDisplay` usage from this file (keep `TaskDisplay` itself; `entities/proposed-changes/ui/proposed-change-details.tsx` still uses it). Add props `reposPage`, `onReposPageChange`, `tasksPage`, `onTasksPageChange`.
- [X] T009 Make `frontend/app/src/pages/branches/branch-details/details-tab.tsx` own the page parameters: read `QSP.REPOSITORIES_PAGE` and `QSP.TASKS_PAGE` with `nuqs` `useQueryState(…, parseAsInteger.withDefault(1))` and pass value/setter into `BranchDetails` (research R6). Depends on T002, T008.

**Checkpoint**: Details tab renders Details card + action row; no accordion; pagination primitives tested.

---

## Phase 3: User Story 1 — See every repository's Git state (P1) 🎯 MVP

**Goal**: The Git repositories card with rows, ranking, pagination and its loading/denied/empty/failed states.

**Independent Test**: spec US1 — 12 repositories, one in Import Error, one read-only: failing repo first, tag shown, schema pill colours, 10 rows + pager; 10 repos → no pager; 11 → page 2 same height.

### Tests for User Story 1

- [X] T010 [P] [US1] Unit tests `frontend/app/src/entities/repository/domain/rules/rank-repositories.test.ts`: `hasImportError`, `isRepositoryUnreachable` (`error-cred`, `error-connection`, `error` true; `online`, `unknown`, `null` false), `getRepositoryRank`, `rankRepositories` (import error → unreachable → rest, name order inside groups, stable, doesn't mutate input), `getFailingRepositories`, `getBandKind` (import error wins when both). _(Superseded 2026-10-05: R003 removed `rankRepositories` and `getRepositoryRank`; the table keeps the server's order. The other rules and their tests are in `domain/rules/repository-failures.ts` and `repository-failures.test.ts`.)_
- [X] T011 [P] [US1] Unit tests `frontend/app/src/entities/repository/domain/use-cases/get-branch-repositories.test.ts` with the api function mocked: maps nodes to `BranchRepository` (name fallback to `display_label` then `id`, `isReadOnly` from `__typename`, null commit); `syncWithGit: false` queries the read-only kind; `PERMISSION_DENIED` in `errors[].extensions` → `{ status: "denied" }`; other errors throw; `isTruncated` when `count > edges.length`.
- [X] T012 [P] [US1] Scenario fixtures in `frontend/app/tests/fake/branch-repositories.ts`: builders for `BranchRepository` and the results of the prototype scenarios trimmed to real fields (`incident`/`import-error`, `unreachable`, `many-errors` = 40 repos with 5 import errors at positions 2, 3, 7, 12, 18, `all-clear`, `no-repos` Sync off, `exactly-10`, `eleven`), with schema-like `sync_status` label/colour values (`In Sync`, `Import Error`, `Syncing`, `Unknown`).

### Implementation for User Story 1

- [X] T013 [P] [US1] Create `BranchRepository` and `BranchRepositoriesResult` types in `frontend/app/src/entities/repository/domain/model/branch-repository.ts` (data-model.md).
- [X] T014 [US1] Implement the rules in `frontend/app/src/entities/repository/domain/rules/rank-repositories.ts` to pass T010. Depends on T007, T013. _(Superseded 2026-10-05: there is no `rank-repositories.ts`; the rules are in `domain/rules/repository-failures.ts`, see R003.)_
- [X] T015 [US1] Create `frontend/app/src/entities/repository/api/get-branch-repositories-from-api.ts`: two static `gql.tada` documents (`CoreGenericRepository`, `CoreReadOnlyRepository`) with the selection in `contracts/graphql-queries.md` Q1, called with `context: { branch: branchName }` and `limit: REPOSITORY_FETCH_LIMIT`; return `{ data, errors }` unthrown. Run `pnpm codegen` if the `gql.tada` cache needs regenerating.
- [X] T016 [US1] Implement `getBranchRepositories({ branchName, syncWithGit })` in `frontend/app/src/entities/repository/domain/use-cases/get-branch-repositories.ts` to pass T011, detecting permission errors with `parseCatalogueError` and `ERROR_CODES.PERMISSION_DENIED` from `frontend/app/src/shared/api/errors` (research R11). Depends on T013, T015.
- [X] T017 [US1] Create `repositoryQueryKeys` in `frontend/app/src/entities/repository/ui/queries/repository.query-keys.ts` (`all`, `branch`, `importError`, research R7) and `useGetBranchRepositories` + `getBranchRepositoriesQueryOptions` in `frontend/app/src/entities/repository/ui/queries/get-branch-repositories.query.ts`, with `refetchInterval` returning 10 000 only while a returned repository is syncing (research R4). Depends on T016.
- [X] T018 [P] [US1] Create `GitStatePill` in `frontend/app/src/entities/repository/ui/branch-repositories/git-state-pill.tsx`: schema `color` background with `getTextColor` (pattern: `frontend/app/src/entities/homepage/ui/git-repository.tsx::GitRepositoryItem`), `label`; raw value in a neutral token tag when label/colour are missing; `description` as tooltip when present.
- [X] T019 [US1] Create `RepositoryRow` in `frontend/app/src/entities/repository/ui/branch-repositories/repository-row.tsx`: 40px row; name link to `getObjectDetailsUrl(kind, id, [getBranchQspOverride(branchName, isDefault)])` truncated with `title`; "Read-only" tag; `GitStatePill`; warning icon with `aria-label` and a `Tooltip` from the operational status label when unreachable (FR-012); commit in monospace `tabular-nums` on `bg-info-surface`, truncated with `title`, placeholder "—" when null. Depends on T006, T014, T018.
- [X] T020 [US1] Create `BranchRepositoriesTable` in `frontend/app/src/entities/repository/ui/branch-repositories/branch-repositories-table.tsx`: headers Repository / Git state / Commit on `bg-content-muted`; ranks, clamps `page`, slices 10; container `min-height` = `(PAGE_SIZE + 1) * CELL_HEIGHT_PX` (`CELL_HEIGHT_PX` from `shared/components/table/style.tsx`) when more than one page; `TablePagination` only when more than one page; truncation notice with a link to the repository list when `isTruncated`. Depends on T004, T019.
- [X] T021 [P] [US1] Create the card states in `frontend/app/src/entities/repository/ui/branch-repositories/branch-repositories-states.tsx`: loading (3 `Skeleton` rows at 40px, `role="status"`, `aria-busy`, sr-only "Loading repositories"), denied (lock icon, "You don't have access to this branch's repositories", "Ask an administrator for permission to view repositories."), empty-not-synced ("Not synchronised with Git" + "This branch was created with Sync with Git off, so repository imports and generators don't run on it."), empty-none ("No Git repositories" + one line), failed ("Repositories couldn't be loaded.").
- [X] T022 [US1] Create `BranchRepositoriesCard` in `frontend/app/src/entities/repository/ui/branch-repositories/branch-repositories-card.tsx` per `contracts/ui-components.md` (props `branchName`, `isDefaultBranch`, `syncWithGit`, `page`, `onPageChange`; `Card` + `CardHeader` "Git repositories" with a `Badge variant="blue"` rounded count once loaded; `data-testid="branch-repositories-card"`), leaving a slot under the table for the bands (US2). Depends on T017, T020, T021.
- [X] T023 [US1] Component tests `frontend/app/src/entities/repository/ui/branch-repositories/branch-repositories-card.test.tsx` using T012 fixtures and a mocked `useGetBranchRepositories`: US1 scenarios 1–9; 10 rows → no pager; 11 rows → page 2 has 1 row and the table container keeps its min-height; `many-errors` → every import-error repository on page 1; repository links carry `branch=<page branch>` (FR-053). Depends on T012, T022. (2026-10-02: the "no hex colour in rendered `class` attributes" case was removed in review as a style check, not behaviour; FR-050 rests on the T057 grep and the computed-colour dark-theme test in `repository-error-bands.test.tsx`.)
- [X] T024 [US1] Mount `BranchRepositoriesCard` in the repositories slot of `frontend/app/src/entities/branches/ui/branch-details.tsx` with `branch.sync_with_git`, `branch.is_default` and the `reposPage` props from T008/T009. Depends on T009, T022.

**Checkpoint**: US1 independently testable on a real branch (quickstart rows 1–3).

---

## Phase 4: User Story 2 — Read why an import failed (P1)

**Goal**: Red import-error bands with the last error line and task link, amber unreachable bands, 3 + "Show all".

**Independent Test**: spec US2 — one repository failing with a known log line, one `error-cred`: red band with the verbatim line and working "View task log"; amber band with "Open repository"; 5 bands → 3 + summary + Show all.

### Tests for User Story 2

- [X] T025 [P] [US2] Unit tests `frontend/app/src/entities/repository/domain/rules/get-last-error-line.test.ts`: picks the last `error` or `critical` (any case), ignores `info`/`warning`, keeps inner newlines, trims trailing whitespace, returns `null` for no logs or no error line; unwraps Prefect's `Finished in state <State>('…'[, type=<TYPE>])` wrapper to the exception (research "R2 verification results"), and returns the wrapper as is when it unwraps to nothing.
- [X] T026 [P] [US2] Unit tests `frontend/app/src/entities/repository/domain/use-cases/get-repository-import-error.test.ts` with the api mocked: task with error line → `found`; task without → `not-found` with `taskId`; no task → `not-found` with `taskId: null`; api error → `not-found` with `taskId: null` (the band never disappears, data-model § State transitions); variables carry `branch`, `[repositoryId]`, `IMPORT_WORKFLOWS`, `limit` 1, `IMPORT_LOG_LIMIT`.

### Implementation for User Story 2

- [X] T027 [US2] Implement `getLastErrorLine` in `frontend/app/src/entities/repository/domain/rules/get-last-error-line.ts` to pass T025.
- [X] T028 [US2] Create `frontend/app/src/entities/repository/api/get-repository-import-task-from-api.ts` with the Q2 document from `contracts/graphql-queries.md`.
- [X] T029 [US2] Implement `getRepositoryImportError({ branchName, repositoryId })` in `frontend/app/src/entities/repository/domain/use-cases/get-repository-import-error.ts` to pass T026. Depends on T027, T028.
- [X] T030 [US2] Create `useGetRepositoryImportError({ branchName, repositoryId, isSyncing })` in `frontend/app/src/entities/repository/ui/queries/get-repository-import-error.query.ts` with key `repositoryQueryKeys.importError(…)` and the same polling rule as T017. Depends on T017, T029.
- [X] T031 [P] [US2] Create `ImportErrorBand` in `frontend/app/src/entities/repository/ui/branch-repositories/import-error-band.tsx`: calls `useGetRepositoryImportError` itself (so collapsed bands never fetch); `bg-danger-surface`, top border in a danger token, alert icon; "<name> — import failed"; `found` → message in a monospace `whitespace-pre-wrap break-words` paragraph (text only) + `Link` "View task log →" to `constructPath(\`/tasks/${taskId}\`)`; `not-found` → "The error details couldn't be found for this import." + link to the task when `taskId`, else "Open repository" via `getBranchQspOverride`; loading → name + "Loading the import log…". `data-testid="repository-error-band"`.
- [X] T032 [P] [US2] Create `UnreachableBand` in `frontend/app/src/entities/repository/ui/branch-repositories/unreachable-band.tsx`: `bg-warning-surface`, `border-warning-border`, triangle icon; "<name> — <operational status label>"; "Infrahub can't fetch new commits, so the commit shown may be out of date. Check the repository's credentials and location."; "Open repository" via `getBranchQspOverride`. `data-testid="repository-error-band"`.
- [X] T033 [US2] Create `RepositoryErrorBands` in `frontend/app/src/entities/repository/ui/branch-repositories/repository-error-bands.tsx`: takes all repositories, uses `getFailingRepositories` + `getBandKind`, shows the first `MAX_VISIBLE_BANDS` or all (local `useState`), and when more than 3 a summary line "<N> more repositories with errors: <names>" (singular "repository" for 1) with a ghost `Button` "Show all"/"Collapse" (text changes to "<N> repositories with errors" when expanded). Depends on T014, T031, T032.
- [X] T034 [US2] Mount `RepositoryErrorBands` under the table in `frontend/app/src/entities/repository/ui/branch-repositories/branch-repositories-card.tsx` (only in the `ok` non-empty state), passing the syncing flag. Depends on T022, T033.
- [X] T035 [US2] Component tests `frontend/app/src/entities/repository/ui/branch-repositories/repository-error-bands.test.tsx` with a mocked `useGetRepositoryImportError`: US2 scenarios 1–6; bands cover failing repositories on other pages (FR-024); only the first 3 bands call the hook until "Show all"; "View task log" href is `/tasks/<id>`; "Open repository" carries `branch=<page branch>`. Depends on T034.

**Checkpoint**: US1 + US2 cover the incident's import failure (quickstart row 4).

---

## Phase 5: User Story 3 — Act on the branch from the same place (P1)

**Goal**: The five buttons below the repositories card, behaviour unchanged, Merge ungated.

**Independent Test**: spec US3 — on a branch with a failing import, all five buttons below the card in order; Merge enabled and merges.

- [X] T036 [US3] Component test `frontend/app/src/entities/branches/ui/branch-details.test.tsx` (mock `useGetBranchDetails`, the repositories and tasks hooks): on a non-default branch the order is Details card → `branch-repositories-card` → buttons Merge, Propose change, Rebase, Validate, Delete → `branch-tasks-card` (placeholder until US4); `BranchMergeButton` receives exactly `{ branch }` whatever the repositories/tasks state (FR-031; spy on the module with `vi.mock`); default branch → Details card only, no buttons, no cards. Depends on T024.
- [X] T037 [US3] Update `tests/e2e/branches/test_branch_details.py` so the action-button assertions still pass with the new layout (buttons found by role and name, as today), and add an assertion that the Git repositories card (`branch-repositories-card`) renders above the Merge button on a non-default branch and is absent on the default branch. Depends on T024.

---

## Phase 6: User Story 4 — See every task that ran on the branch (P2)

**Goal**: The server-paginated Tasks card replacing the accordion.

**Independent Test**: spec US4 — 12 tasks: 10 newest, pager, count 12, "1 failed", title opens `/tasks/<id>`.

### Tests for User Story 4

- [X] T038 [P] [US4] Unit tests `frontend/app/src/entities/tasks/domain/model/workflow-labels.test.ts` for every mapping in research R9, `null` → "—", unknown id → itself. _(Superseded 2026-10-05: `getWorkflowLabel` is in `domain/rules/get-workflow-label.ts` (+ test) and turns an unknown id into readable words, for example "some-new_workflow" → "Some new workflow".)_
- [X] T039 [P] [US4] Unit tests `frontend/app/src/entities/tasks/domain/rules/get-task-related-label.test.ts`: known repository → its name; several related nodes → first known repository wins; none → "This branch"; other kind → `getKindLabel(kind)` or the kind.
- [X] T040 [P] [US4] Unit tests `frontend/app/src/entities/tasks/domain/use-cases/get-branch-tasks.test.ts` with `getTaskListFromApi` mocked: returns `{ tasks, count }`, drops null nodes/related nodes, passes `branchName`, `offset`, `limit`; errors throw.

### Implementation for User Story 4

- [X] T041 [P] [US4] Create `TaskListItem`/`TaskListPage` in `frontend/app/src/entities/tasks/domain/model/task-list-item.ts` (data-model.md).
- [X] T042 [P] [US4] Implement `getWorkflowLabel` in `frontend/app/src/entities/tasks/domain/model/workflow-labels.ts` to pass T038 (reuse `BRANCH_VALIDATE_WORKFLOW`, `BRANCH_REBASE_WORKFLOW`, `BRANCH_MERGE_WORKFLOW` from `frontend/app/src/entities/tasks/domain/model/task.ts`; the tasks entity keeps its own copy of the import workflow ids rather than importing `repository`).
- [X] T043 [P] [US4] Implement `getTaskRelatedLabel` in `frontend/app/src/entities/tasks/domain/rules/get-task-related-label.ts` to pass T039.
- [X] T044 [US4] Implement `getBranchTasks` in `frontend/app/src/entities/tasks/domain/use-cases/get-branch-tasks.ts` over `GET_TASK_LIST` from `frontend/app/src/entities/tasks/api/get-task-list-from-api.ts` to pass T040. Depends on T041.
- [X] T045 [US4] Add `branchList` to `tasksQueryKeys` in `frontend/app/src/entities/tasks/ui/queries/tasks.query-keys.ts`, and create `useGetBranchTasks({ branchName, page })` (offset from page, `limit: PAGE_SIZE`, `refetchInterval: page === 1 ? 10_000 : false`, `placeholderData: keepPreviousData`) and `useGetBranchFailedTaskCount({ branchName })` (reuses `getTaskCount` with `state: [TASK_STATE_FAILED]`, 10s; FAILED only so the count matches what the Tasks page link opens) in `frontend/app/src/entities/tasks/ui/queries/get-branch-tasks.query.ts`. Depends on T044.
- [X] T046 [US4] Create the shared `TasksTable` in `frontend/app/src/entities/tasks/ui/tasks-table/tasks-table.tsx`, with a configurable column set (other task lists adopt it in IFC-3245); the branch card uses columns Title (`Link` to `constructPath(\`/tasks/${id}\`)` as a `block truncate leading-10` cell-filling target, `title` attribute), State (`getLogBadge` from `frontend/app/src/entities/tasks/ui/task-display.tsx`, gray "UNKNOWN" fallback), Workflow (`getWorkflowLabel`), Related (`getTaskRelatedLabel` with `repositoryNames` and schema labels via `useSchema` when available), Updated (`DateDisplay`); failed rows tinted with `bg-danger-surface`; fixed min-height and `TablePagination` as T020, `totalCount` from the server. Depends on T004, T042, T043, T045.
- [X] T047 [P] [US4] Create the tasks states in `frontend/app/src/entities/tasks/ui/branch-tasks/branch-tasks-states.tsx`: loading (3 skeleton rows, `role="status"`), empty ("No tasks have run on this branch yet. Imports, generators and validations appear here as they run."), failed ("Task results didn't load.").
- [X] T048 [US4] Create `BranchTasksCard` in `frontend/app/src/entities/tasks/ui/branch-tasks/branch-tasks-card.tsx` per `contracts/ui-components.md` (props `branchName`, `isDefaultBranch`, `page`, `onPageChange`, `repositoryNames`): `CardHeader` "Tasks", count badge after load, "<N> failed" when N > 0 with a `Tooltip` ("Failed tasks on this branch, including runs retried since.") linking to the Tasks page on this branch filtered to failed states (use the Tasks page's existing `filters` parameter as written by `frontend/app/src/entities/tasks/ui/task-filters.tsx`), `LinkButton` "Open in Tasks" to `constructPath("/tasks", [getBranchQspOverride(…), …])`; `data-testid="branch-tasks-card"`. Depends on T006, T046, T047.
- [X] T049 [US4] Component tests `frontend/app/src/entities/tasks/ui/branch-tasks/branch-tasks-card.test.tsx` with mocked hooks: US4 scenarios 1–8; page 2 keeps the min-height; title href `/tasks/<id>`; "Open in Tasks" and failed link carry `branch=<page branch>`; no count while loading; only page 1 polls (assert the hook is called with the page). Depends on T048.
- [X] T050 [US4] Mount `BranchTasksCard` in the tasks slot of `frontend/app/src/entities/branches/ui/branch-details.tsx`: call `useGetBranchRepositories` with the same params as the card (deduped) to build `repositoryNames: Map<id, name>` (empty map when loading/denied/failed), and pass `tasksPage` props from T009. Depends on T017, T048.
- [X] T051 [US4] In `tests/e2e/branches/test_branch_details.py`, replace both `tasks-accordion` assertions with `branch-tasks-card` (hidden on the default branch, visible on a non-default branch), and add: after running Validate, a "Validate" row appears and its title opens `/tasks/<id>`. Depends on T050.

---

## Phase 7: User Story 5 — A branch page that looks like every other detail page (P3)

**Goal**: Object-page header, tab row and panel body; one Refresh for everything.

**Independent Test**: spec US5 — header parts present, copy button named "Copy branch name", Refresh refetches branch details, repositories, bands and tasks.

- [X] T052 [US5] Create `BranchDetailsHeader` in `frontend/app/src/entities/branches/ui/branch-details/branch-details-header.tsx` per `contracts/ui-components.md`: `HeaderContainer` from `frontend/app/src/entities/nodes/object/ui/object-details/object-details-header.tsx`, `h1` (truncate, `title`), `CopyToClipboardButton` with `aria-label="Copy branch name"`, `NodeMetadataPopover objectKind="InfrahubBranch"`, `BranchDefaultBadge` or `BranchStatusBadge`, `RefreshButton className="ml-auto" queryKeys={[branchesQueryKeys.all, repositoryQueryKeys.all, tasksQueryKeys.all]}` (`.all`, not `.details({ branchName })`: the header and the action buttons read other branch queries too); description paragraph under the row. Depends on T005, T017, T045.
- [X] T053 [US5] Component test `frontend/app/src/entities/branches/ui/branch-details/branch-details-header.test.tsx`: parts and order, copy button accessible name, default vs status badge, description only when set, `RefreshButton` receives the three keys. Depends on T052.
- [X] T054 [US5] In `frontend/app/src/pages/branches/details.tsx::BranchDetailsContent`, replace the `<header>` with `BranchDetailsHeader` (keep `BranchWorkingNotice` above it and `useTitle`), and wrap the tabs + `Outlet` in `Col className="gap-0 p-1"` with the `Outlet` inside `Card variant="panel"` (as `frontend/app/src/entities/nodes/object/ui/object-details/object-details-body.tsx::ObjectDetailsBody`). Depends on T052.
- [X] T055 [US5] Restyle `BranchTabs` in `frontend/app/src/entities/branches/ui/branch-tabs.tsx` to the object tab row (`Row className="items-end gap-4 px-4"`, no bottom border, as `object-details-tabs.tsx::ObjectDetailsTabs`); tabs and routes unchanged. Depends on T054.
- [X] T056 [US5] Update `tests/e2e/branches/test_branch_details.py` for the header: the copy button is found by its accessible name "Copy branch name", and Refresh is present. Depends on T054.

---

## Phase 8: Polish & cross-cutting

- [X] T057 [P] Dark-mode pass: switch the theme to dark on a branch with every card state (fixtures or a live branch) and fix any class that isn't a theme token; `grep -rnE "#[0-9a-fA-F]{3,6}|neutral-|red-|amber-" frontend/app/src/entities/repository/ui/branch-repositories frontend/app/src/entities/tasks/ui/branch-tasks frontend/app/src/shared/components/table` returns nothing (FR-050). Done by grep + token audit + a computed-colour dark-theme component test; the live visual check on a stack was not done.
- [X] T058 Add the e2e test "import error band links to the task page" to `tests/e2e/branches/test_branch_details.py` (or a new `tests/e2e/branches/test_branch_details_repositories.py` if the fixture setup differs): seed a repository in Import Error on a branch through the path T001 proved resolvable, open the branch page, assert the red band shows the error line and "View task log" opens `/tasks/<id>`. If no path resolves deterministically, assert the not-found fallback band instead and note it in the PR. Depends on T001, T035.
- [X] T059 [P] Add the Towncrier fragment `changelog/+infp-671-branch-details-repositories.added.md`: one or two sentences, user-facing ("The branch details page now lists the branch's Git repositories with their Git state and commit, shows the last error of failed imports, and lists every task that ran on the branch.").
- [X] T060 [P] Add `TablePagination` (`shared/components/table/table-pagination.tsx`, "Paginated table footer, one per table; page state owned by the caller") to the reuse inventory in `dev/knowledge/frontend/shared-components.md`, next to the existing `Pagination` row, saying when to use which.
- [X] T061 Run the full frontend CI gate and fix every failure: `cd frontend/app && pnpm exec biome ci .`, `pnpm knip` (remove any export left unused, e.g. unused `TaskDisplay` imports), `pnpm exec betterer ci`, `pnpm test`. Depends on all implementation tasks.
- [ ] T062 Walk `quickstart.md` scenarios 1–11 against a running stack, and record the R2 verification outcome (T001) plus the follow-up backend ask (make the worker-bootstrap import inside `git_repositories_sync` findable, or add `last_import_task`; `build_import_plan` already tags `git-repository-import-object` and `sync-git-repo-with-origin`, see research "R2 verification results") in the PR description, with the INFP-670 sign-off request for ungated Merge. ⚠️ Partly verified on the seeded stack (`utilities/branch_details_scenarios/`): `verify.mjs` loaded the page of every `scn-` branch (all clear, one import error, five import errors, failed generators, many tasks, Sync with Git off, unreachable repositories) and checked its text and a screenshot. The seed can't produce these states, so only component tests cover them: the "Not synchronised with Git" and "No Git repositories" empty states, exactly 10 repositories, a repository stuck in `syncing`, and the no-permission state. Scenarios 1–11 were not walked one by one by hand. The R2 outcome, the backend asks and the INFP-670 sign-off request are in the PR description; the asks are also under Follow-ups below.

---

## Restructure (2026-10-02)

Follows the accepted architecture review of PR #10779 (research.md § "Restructure (2026-10-02)", D1–D10). UX and copy unchanged, except that failing repositories no longer sort first in the table. Earlier tasks that describe the replaced design (T002 QSP keys, T006 `getBranchQspOverride`, the 500-row fetch and ranking, `usePageInRange`; the `branch` and `importError` query keys in T017 and T030, now `branchRepositories`, `branchHealth`, `importTask`, `importLog` and `names`; the `isDefaultBranch` prop and the `page`/`onPageChange` props in T022 and T048, now `getBranchQsp` and card-owned pages; the `repositoryNames` prop in T048, now the names query; and T045's `page === 1` polling condition, now `offset === 0`) are kept as history.

- [X] R001 Take IFC-3130's shared pagination verbatim: `table-pagination.ts` (+ test), `use-table-pagination.ts` (+ test), `CELL_HEIGHT_PX`, `hasThrownCatalogueCode`, `TablePagination` (+ test) with this PR's `aria-label` prop and focus ring added. Commit `5be40fe1c7`.
- [X] R002 Replace `usePageInRange` with `useCountClampedQuery` (clamp in the data hook, no effect); drop the `REPOSITORIES_PAGE`/`TASKS_PAGE` QSP keys. Commit `5be40fe1c7`.
- [X] R003 Server page for the repositories table (`limit`, `offset`, `count`, `order` by name); drop `REPOSITORY_FETCH_LIMIT`, `isTruncated` and the truncation notice, `rankRepositories` and `getRepositoryRank`. Commit `d865a236cc`.
- [X] R004 Server-filtered health query (import errors, unreachable, syncing count) feeding the bands and the shared polling condition `isAnyRepositorySyncing`. Each query adds its own conditions: the page query polls while its rows show a sync, the health query while its last fetch failed, and the import-task lookup while an import runs and up to 6 times while it finds nothing. A poll slows to 60s after a failed fetch and stops on a permission denial. Commit `d865a236cc`.
- [X] R005 Import-task lookup in two requests: a RUNNING import first (result `running`, no further request), then the newest FAILED/CRASHED import (result `failed` with its task id, or `not-found`). The failed task's log is a second query keyed on the task id, fetched once, never polled. Commit `d865a236cc`.
- [X] R006 Layering: mapper to `api/branch-repository.mappers.ts`, no `@urql/core` outside `client.ts`, `BranchRepositoriesError` for the (real) denied state, list-kind rule to `domain/rules`, query keys on the `["repository"]` root with IFC-3199's `syncHealth`. Commit `d865a236cc`.
- [X] R007 Cards own their page (`repositories_page`, `tasks_page`); `BranchTasksSection` and its second repositories query removed; Related names from one `ids` query over the page; `isDefaultBranch` drilling replaced by `getBranchQsp`; `TasksTable` without its column API; `getWorkflowLabel` to `domain/rules`. Commit `1431dddf00`.
- [X] R008 `RefreshButton`: single `queryKeys` prop, last-update time scoped to its keys; Tasks page updated. Commit `f0c9f4586c`.
- [X] R009 e2e: create the import-error branch with Sync with Git on (root cause of the two CI failures) and assert on the band, not the row. Commit `32a28e5163`.
- [X] R010 Spec docs (plan, research, data-model, contracts, follow-ups, seed scenarios) aligned with the restructure.

### Open decisions for the owner

1. **File paths shared with IFC-3200's plan.** IFC-3200 (`plan-synthesis.md` N2, N3, N4, N6) plans `entities/repository/api/get-branch-repositories-from-api.ts`, `domain/model/branch-repository.ts`, `domain/use-cases/get-branch-repositories.ts` and `ui/queries/get-branch-repositories.query.ts`, the paths this PR uses, with different shapes (its own `hasFailedImport`, `SYNC_STATUS_ERROR_IMPORT`, a `ref`/`default_branch` Tracking column). Pick one owner per file before IFC-3200 starts, or have IFC-3200 build on these.
2. **`clampToCount` vs `useCountClampedQuery`.** IFC-3200 (T001) plans a `clampToCount` on `use-table-pagination.ts` and to collapse IFC-3130's effect onto it. This PR keeps that file verbatim and adds a separate hook. One of the two should become the shared answer, and IFC-3130's card should use it.
3. **Two `TablePagination` additions** (`aria-label`, focus ring) need to land in IFC-3130, or this PR's version wins the merge.
4. **IFC-3130's `DataTable` vs hand-written tables** (D8). If the branches card's look should become the standard, both tables here move onto `DataTable` once IFC-3130 lands.
5. **Sync-off branch with a `CoreRepository` created on it** (D10). The card lists read-only repositories only and says "imports and generators don't run on it", yet such a repository does import there and can fail. Keep the rule, or list every kind when the branch has its own repositories.
6. ~~**Failing repositories are unbounded in the health query.**~~ Resolved 2026-10-05: each list is capped at 50, and the summary line counts the rest from the server's `count`.
7. **URL keys** (D9): `repos_page` is now `repositories_page`; no alias kept, since the feature hasn't shipped.

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
T003 table-pagination utils  |  T005 RefreshButton queryKeys  |  T006 getBranchQspOverride  |  T007 repository constants

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

## Follow-ups

Asks found while building this feature. None of them blocks it.

1. Backend: run the worker-bootstrap import (`bootstrap_local_repository` in `git_repositories_sync`) in its own tagged subflow, or at least log its failure at `error` instead of `info`, so a failed bootstrap import can be found as a task. To file.
2. Backend: tag a periodic sync (`sync-git-repo-with-origin`) with every branch it imports before the import can fail; on the seeded stack a failed sync was tagged with the default branch only. To file.
3. Backend: tag the branch and the repository as the first statement of every flow that imports or syncs a repository (`add_tags`), so a failure before `build_import_plan` can be found. To file.
4. Backend: fill `TaskError` for Git import flows, so the band stops parsing the last error log line. IFC-3034.
5. Backend: expose the latest import task and its error per branch on `CoreGenericRepository` (for example `last_import_task`). To file.
6. Backend: add a log order or "last N logs" option to `InfrahubTask`, so the band does not read up to 10,000 log lines. To file.
7. Frontend: use the exact `sync_status__values: ["error-import"]` filter for IFC-3199's `syncHealth` count too, so the header and the card count the same repositories. To file.
8. Frontend: land this PR's changes to IFC-3130's shared files (`TablePagination` `aria-label`, focus ring and icon size; `hasOnlyThrownCatalogueCode` and `isThrownShed`) in IFC-3130, or drop them here if IFC-3130 merges first. IFC-3130.
9. Frontend: use one tasks table across the app (`TaskItems` and `TasksTable`). IFC-3245.
