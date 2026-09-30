# Tasks: Repository, Git state and Commit columns on the branches table

**Input**: Design documents from `dev/specs/ifc-3201-branches-table-git/`
**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md)

**Tests**: Included and written first. Spec SC-006 asks for an automated test per state, and constitution IV asks for unit, component and E2E tests for a user-facing feature. In each user-story phase the test tasks come before the implementation tasks and must fail before the implementation lands.

**Conventions for every task**:

- Paths are relative to the repo root; frontend paths are under `frontend/app/`. Code sites are cited as `path::Symbol`.
- React Compiler is on: no `useMemo`/`useCallback`/`React.memo`. Theme tokens only (`text-subtle-muted`, `text-foreground-muted`); the only literal colour is the schema's dropdown colour, which `GitStatePill` already applies.
- Entity layering per `dev/knowledge/frontend/entities-structure.md`: `branches/domain/rules` imports only its own `domain/model`; `branches/ui` may import `repository/ui` and `repository/domain`. Never import another entity's `api/`.
- Tests sit next to their source (`*.test.ts(x)`), render with `frontend/app/tests/components/render`, and mock query hooks and use-cases with `vi.mock` (patterns: `frontend/app/src/entities/repository/ui/branch-repositories/branch-repositories-card.test.tsx`, `frontend/app/src/entities/nodes/object/ui/object-table/utils/get-object-table-columns.test.tsx`, `frontend/app/src/entities/branches/ui/hooks/use-confirm-branch-is-gone.test.ts`).
- Reused fakes: `frontend/app/tests/fake/branch.ts::generateBranch` and `frontend/app/tests/fake/branch-repositories.ts::{SYNC_STATUS, OPERATIONAL_STATUS, generateBranchRepository, generateBranchRepositoriesResult}` (#10779, not edited).
- Strings are verbatim from the spec: "Repository", "Git state", "Commit", "Not synced with Git", "No repositories", "No permission", "Could not load repositories", "Select <branch>", "Select <branch> (<repository name>)".
- Never run `wt`, never touch `CLAUDE.md`.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on an unfinished task)
- **[Story]**: US1–US3 from spec.md. Setup, Foundational, E2E and Polish tasks carry no story label.

---

## Phase 1: Setup

**Purpose**: Bring in the lifted `CommitHash`, and make the three small changes to shared or #10779 files that every story builds on.

- [X] T001 Lift `frontend/app/src/shared/components/display/commit-hash.tsx` and `frontend/app/src/shared/components/display/commit-hash.test.tsx` byte-identical from #10658 with `git -C /Users/paul/Projects/infrahub show ple-branches-card-ifc-3130:frontend/app/src/shared/components/display/commit-hash.tsx` (and the same for `commit-hash.test.tsx`), redirecting each output to its path; confirm with `cmp` against the `git show` output and run `pnpm vitest run src/shared/components/display/commit-hash.test.tsx` from `frontend/app` (research R8). Do not reformat, even if biome would. — comments: none unless a non-obvious constraint; see `.agents/rules/code-doc-style.md`.
- [X] T002 Create `dev/specs/ifc-3201-branches-table-git/pr-notes.md` with a "Lifted files" section recording the output of `git -C /Users/paul/Projects/infrahub rev-parse ple-branches-card-ifc-3130` taken at the time of T001, the two lifted paths, and the pre-merge check command (`git diff <sha-or-branch-tip> -- frontend/app/src/shared/components/display/commit-hash*`). Depends on T001.
- [X] T003 [P] In `frontend/app/src/entities/repository/api/get-branch-repositories-from-api.ts::fetchConnection`, add a no-op `processErrorMessage` to the request context next to `branch`, so a non-permission GraphQL error no longer toasts through `frontend/app/src/shared/api/graphql/error-handling.ts::handleGraphQLErrors` (research R10, FR-013). Covered by T029 (card) and T030 (table). Regression-tested by T029 (US3); the change is a one-line context option, so it is not test-first. — comments: none unless a non-obvious constraint; see `.agents/rules/code-doc-style.md`.
- [X] T004 [P] Write `frontend/app/src/entities/nodes/object/ui/object-table/utils/get-toggle-selected-row-handler.test.ts` (new, test-first for T005) over a small TanStack table of plain `{ id }` rows with `getRowId`: plain click toggles one row; shift-click selects the range between the last-selected row and the clicked one; after rows are inserted above the last-selected row (rerender with more data), shift-click still ranges from the same row **by id**; when the stored id no longer exists, shift-click falls back to a plain toggle; two tables keep independent anchors. — comments: none unless a non-obvious constraint; see `.agents/rules/code-doc-style.md`.
- [X] T005 In `frontend/app/src/entities/nodes/object/ui/object-table/utils/get-toggle-selected-row-handler.ts::getToggleSelectedRowHandler`, widen the generic from `<T extends NodeCore>` to `<T>` (drop the `NodeCore` import) and store the last-selected row **id** instead of `row.index` (rename `lastSelectedIndexByTable` accordingly), resolving both indexes at shift time via `table.getRow(id).index` and falling back to a plain toggle when the id is gone (plan Complexity Tracking, research R1). Make T004 pass and keep `get-object-table-columns.test.tsx` green. Depends on T004. — comments: none unless a non-obvious constraint; see `.agents/rules/code-doc-style.md`.
- [X] T006 [P] Extract `frontend/app/src/entities/repository/ui/branch-repositories/repository-name-link.tsx::RepositoryNameLink({ repository, branchName, isDefaultBranch })`, moving verbatim the first `<td>`'s content of `frontend/app/src/entities/repository/ui/branch-repositories/repository-row.tsx::RepositoryRow` (wrapper div, `FolderGitIcon`, `Link` to `getObjectDetailsUrl(kind, id, [getBranchQspOverride(branchName, isDefaultBranch)])` with `title={name}`, "Read-only" chip) per `contracts/ui-cells.md` § `RepositoryNameLink`; `RepositoryRow` renders `<td className="px-3"><RepositoryNameLink … /></td>` and keeps its Git state `<td>` (with the unreachable icon) and commit `<td>` (with the `—` fallback) unchanged. Run `pnpm vitest run src/entities/repository/ui/branch-repositories/branch-repositories-card.test.tsx` from `frontend/app`; it must stay green unmodified (research R7). — comments: none unless a non-obvious constraint; see `.agents/rules/code-doc-style.md`.

**Checkpoint**: `CommitHash` present and tested, SHA recorded, handler id-anchored, `RepositoryNameLink` has one caller and the card test is green.

---

## Phase 2: Foundational (blocking)

**Purpose**: The row model, the fan-out rule, the data hook, the header schemas and the grid tracks that every story's cells render into.

**⚠️ CRITICAL**: No user-story work starts until this phase is complete.

- [X] T007 Create `frontend/app/src/entities/branches/domain/model/branch-table-row.ts` with `BranchRepositoriesFetch`, `BranchTableRowState`, the discriminated `BranchTableRow` (`ok` carries `repository`; `error` carries `repository: null` and `errorMessage`; `pending`/`empty`/`denied` carry `repository: null`) and `isBranchAnchorRow(row)` (`row.id === row.branch.id`), exactly as `data-model.md` § `BranchRepositoriesFetch` and § `BranchTableRow`, importing `BranchListItem` from `entities/branches/domain/model/branch.ts` and `BranchRepository`/`BranchRepositoriesResult` from `entities/repository/domain/model/branch-repository.ts`. No `any`, no `!`. Covered by T009. — comments: none unless a non-obvious constraint; see `.agents/rules/code-doc-style.md`.
- [X] T008 Create `frontend/app/tests/fake/branch-table-rows.ts` with `FULL_COMMIT_HASH` (a 40-character lowercase hex string whose first 7 characters are `8f3c2a1`) and `generateBranchTableRow(overrides)` returning an `ok` row over `generateBranch` and `generateBranchRepository` (id = `branch.id`, `repository.commit = FULL_COMMIT_HASH`). Import `BranchListItem` from `entities/branches/domain/model/branch`; leave `tests/fake/branch.ts`'s stale import alone (betterer). The colourless status is **not** exported here: it is declared locally in the one test that uses it (T015). Depends on T007. — comments: none unless a non-obvious constraint; see `.agents/rules/code-doc-style.md`.
- [X] T009 Write `frontend/app/src/entities/branches/domain/rules/to-branch-table-rows.test.ts` (new, modelled on `entities/repository/domain/rules/rank-repositories.test.ts`), passing the real `rankRepositories` as `orderRepositories`, asserting data-model invariants 1–8: N repositories → N rows with unique ids, the first `id === branch.id` and the k-th `${branch.id}:${repository.id}`; an import-error repository in 3rd input place becomes the first row, then unreachable, then by name case-insensitive (FR-006a, US2-AS5); ok with 0 repositories → one `empty` row for `sync_with_git` true, false and null; read-only repositories on a `sync_with_git=false` branch are listed (FR-003, US3-AS3); `denied`, `error` (with `errorMessage`), `pending` and a missing map entry each give one row with id `branch.id`; the anchor id is identical across all states; two branches keep input order with consecutive rows, and a denial or error on one leaves the other's rows unchanged (SC-005). Must fail before T010. Depends on T007, T008. — comments: none unless a non-obvious constraint; see `.agents/rules/code-doc-style.md`.
- [X] T010 Implement `frontend/app/src/entities/branches/domain/rules/to-branch-table-rows.ts::toBranchTableRows({ branches, fetchByBranchId, orderRepositories })` per `data-model.md` § `toBranchTableRows` (pure; imports only its own `domain/model`; ignores `count` and `isTruncated`, research R11). Make T009 pass. Depends on T009. — comments: none unless a non-obvious constraint; see `.agents/rules/code-doc-style.md`.
- [X] T011 Write `frontend/app/src/entities/branches/ui/hooks/use-branch-table-rows.test.ts` (new, `renderHook` pattern of `use-confirm-branch-is-gone.test.ts`, with `entities/repository/domain/use-cases/get-branch-repositories.ts::getBranchRepositories` mocked): one query per branch, each with the row's `branchName` and `syncWithGit: Boolean(sync_with_git)` and the key `repositoryQueryKeys.branch({ branchName, kind })` shared with the branch details card; mapping order `data` → `isError` (message kept) → pending; a failed background refetch keeps the loaded rows (invariant 9); resolving one branch returns the **same row object references** for every other branch (SC-007, research R13); a repository with `sync_status.value === "syncing"` keeps the query's 10 s `refetchInterval` (FR-014, research R9); the hook never reads the branch selector's current branch. Must fail before T012. Depends on T010. — comments: none unless a non-obvious constraint; see `.agents/rules/code-doc-style.md`.
- [X] T012 Implement `frontend/app/src/entities/branches/ui/hooks/use-branch-table-rows.ts::useBranchTableRows(branches)` with `useQueries({ queries: branches.map((b) => getBranchRepositoriesQueryOptions({ branchName: b.name, syncWithGit: Boolean(b.sync_with_git) })), combine })`, where `combine` returns a stable per-branch record and rows are rebuilt only for branches whose result reference changed; then `toBranchTableRows({ …, orderRepositories: rankRepositories })` (`contracts/ui-cells.md` § `useBranchTableRows`). Options passed unchanged; no toast, no throw, no `useMemo`. Make T011 pass. Depends on T011. — comments: none unless a non-obvious constraint; see `.agents/rules/code-doc-style.md`.
- [X] T013 [P] Add `repository`, `git_state` and `commit` header-only entries (labels "Repository", "Git state", "Commit", `kind: "Text"`, the file's existing `as AttributeSchema` shape) to `frontend/app/src/entities/branches/ui/branches-table/branch-field-schemas.ts::BRANCH_FIELD_SCHEMAS`; add nothing to `BRANCH_FILTER_DEFINITIONS` (FR-015). Covered by T015 (headers, no filter/sort control). — comments: none unless a non-obvious constraint; see `.agents/rules/code-doc-style.md`.
- [X] T014 [P] In `frontend/app/src/entities/branches/ui/branches-table/branches-data-table.tsx`, declare `REPOSITORY_TRACK = "minmax(12rem, 18rem)"`, `GIT_STATE_TRACK = "9rem"` and `COMMIT_TRACK = "8rem"` next to `defaultGridTemplateColumns` and change it to `[fit-content(WIDE_COLUMN_MAX_WIDTH), fit-content(COLUMN_MAX_WIDTH), minmax(150px, 200px), REPOSITORY_TRACK, GIT_STATE_TRACK, COMMIT_TRACK, repeat(columnCount - 7, fit-content(COLUMN_MAX_WIDTH)), 2.5rem]` (research R4, SC-004). Covered by T023 (one track per column, three fixed tracks). — comments: none unless a non-obvious constraint; see `.agents/rules/code-doc-style.md`.

**Checkpoint**: `pnpm vitest run src/entities/branches/domain src/entities/branches/ui/hooks` is green; the table still renders the old columns.

---

## Phase 3: User Story 1 — Spot a broken repository from the branches list (Priority: P1) 🎯 MVP

**Goal**: Every branch row shows its repository name (linked on the row's branch), a Git state pill in the schema's label and colour, and the 7-character commit with a copy control; branch cells render immediately with one spinner in the Repository cell while repository data loads.

**Independent Test**: spec US1: with one repository in Import Error on one branch, `/branches` shows that branch's row with the repository name, the "Import Error" pill in its schema colour and the imported commit, while other branches show their own states.

### Tests for User Story 1

- [X] T015 [P] [US1] Write `frontend/app/src/entities/branches/ui/branches-table/get-branch-table-columns.test.tsx` (new, modelled on `get-object-table-columns.test.tsx`), rendering `getBranchTableColumns()` through `BranchesDataTable` with rows from `generateBranchTableRow` (mock `useAuth`, `get-proposed-changes.query`, `useSchema`, `get-objects-count.query`), and a local `const SYNC_STATUS_NO_COLOUR = { value: "mystery", label: "Mystery", color: null, description: null }` declared in this test file only. Cases: headers read "… Proposed Changes, Repository, Git state, Commit, …" in that order with no filter or sort control on the three new headers (FR-001, FR-015, FR-017); ok row: the repository name links to its page with `branch=<row branch>` and the default branch's row adds no `branch` parameter, and a read-only repository shows "Read-only" (FR-006); the pill shows the schema label with the schema colour as background and its description as tooltip (FR-004, US1-AS1, US1-AS2); `SYNC_STATUS_NO_COLOUR` renders a grey badge reading `mystery` (edge case); the commit shows `8f3c2a1` in a monospace span with `title` = `FULL_COMMIT_HASH`, and `Copy commit <hash>` writes the full hash and shows "Copied!" (clipboard stubs from `useCopyToClipboard.test.tsx`; FR-005, US1-AS3); `commit: null` → blank cell, no copy button; no unreachable warning icon, upstream, "behind by" or last-import text anywhere (FR-016); pending row: exactly one `role="status"` (in the Repository cell) and blank Git state and Commit cells (FR-011, US1-AS4). Must fail before T017–T020. — comments: none unless a non-obvious constraint; see `.agents/rules/code-doc-style.md`.
- [X] T016 [P] [US1] Write `frontend/app/src/entities/branches/ui/branches-table/branches-table.test.tsx` (new), mocking `useGetBranchesPaginated` and `getBranchRepositories`: branch name, status and proposed changes render while repositories are pending (SC-004, US1-AS4); on resolve the branch grows from 1 to 3 rows in place with the default branch still first and the others by name; a window refocus issues at most one repository request per loaded branch (SC-007). Must fail before T021. — comments: none unless a non-obvious constraint; see `.agents/rules/code-doc-style.md`.

### Implementation for User Story 1

- [X] T017 [P] [US1] Create `frontend/app/src/entities/branches/ui/branches-table/cells/branch-repository-cell.tsx::BranchRepositoryCell({ row })` rendering `TableCell className="h-auto min-h-14"` with early returns: `pending` → `Spinner` (the `cells/branch-proposed-changes-cell.tsx::BranchProposedChangesCell` pattern); `ok` → `RepositoryNameLink` with `branchName={row.branch.name}` and `isDefaultBranch={Boolean(row.branch.is_default)}`; other states render an empty `TableCell` for now (filled by T031). Depends on T006, T007. Covered by T015. — comments: none unless a non-obvious constraint; see `.agents/rules/code-doc-style.md`.
- [X] T018 [P] [US1] Create `frontend/app/src/entities/branches/ui/branches-table/cells/branch-git-state-cell.tsx::BranchGitStateCell({ row })`: `ok` → `GitStatePill syncStatus={row.repository.syncStatus}` from `entities/repository/ui/branch-repositories/git-state-pill.tsx`; every other state → blank `TableCell` (no spinner, no dash). No unreachable icon (FR-016). Depends on T007. Covered by T015. — comments: none unless a non-obvious constraint; see `.agents/rules/code-doc-style.md`.
- [X] T019 [P] [US1] Create `frontend/app/src/entities/branches/ui/branches-table/cells/branch-commit-cell.tsx::BranchCommitCell({ row })`: `ok` with a non-null commit → `<CommitHash hash={row.repository.commit} copyable />`; `commit === null` and every other state → blank `TableCell` with no copy control. Depends on T001, T007. Covered by T015. — comments: none unless a non-obvious constraint; see `.agents/rules/code-doc-style.md`.
- [X] T020 [US1] Retype `frontend/app/src/entities/branches/ui/branches-table/get-branch-table-columns.tsx` to `createColumnHelper<BranchTableRow>()`: accessors read `r.branch.*` with explicit ids (`status`, `branched_from`, `updated_at`, `created_at`, `created_by`), `proposed_changes`, `actions` and the identifier cell read `row.original.branch`, and three `columnHelper.display` columns with ids `repository`, `git_state`, `commit` (headers via `TableColumnHeaderSimple` over T013's schemas, cells T017–T019) are inserted after `proposed_changes`. Keep the existing accessor `as ColumnDef` casts; add no new `as`. Depends on T013, T017, T018, T019. — comments: none unless a non-obvious constraint; see `.agents/rules/code-doc-style.md`.
- [X] T021 [US1] Retype `frontend/app/src/entities/branches/ui/branches-table/branches-data-table.tsx::BranchesDataTable` to `ColumnDef<BranchTableRow>[]` / `BranchTableRow[]` with `getRowId: (row) => row.id`, and `selectedRows = table.getSelectedRowModel().flatRows.map((r) => r.original.branch)`; then in `frontend/app/src/entities/branches/ui/branches-table/branches-table.tsx::BranchesTable` pass `data={useBranchTableRows(flatData)}`, keeping `flatData`'s order and `BRANCHES_PER_PAGE`. Make T015 and T016 pass. Depends on T012, T014, T020. — comments: none unless a non-obvious constraint; see `.agents/rules/code-doc-style.md`.

**Checkpoint**: US1 is demonstrable on `/branches` (quickstart scenarios 1–4). Selection still counts rows until US2; do not ship this increment on its own.

---

## Phase 4: User Story 2 — A branch with several repositories reads as several rows (Priority: P2)

**Goal**: A branch with N repositories shows on N consecutive rows, and selection, shift-range, the header checkbox, the toolbar count and bulk delete all count branches.

**Independent Test**: spec US2: a branch with three repositories shows three consecutive rows; ticking any one reports "1 selected" and the delete dialog lists the branch once.

### Tests for User Story 2

- [ ] T022 [P] [US2] Write `frontend/app/src/entities/branches/ui/branches-table/branches-data-table.test.tsx` (new, patterns of `branch-repositories-card.test.tsx` and `modal-delete-branch.test.tsx`; mock `useAuth`, `get-proposed-changes.query`, `useSchema`, `get-objects-count.query`, `delete-branches.mutation`) with the selection cases: a 3-repository branch renders 3 consecutive rows with the same name, status and proposed changes and different repositories (US2-AS1); ticking the 2nd row's checkbox checks all 3 rows and the toolbar reads "1 selected" (US2-AS2, FR-008); the bulk delete dialog lists that branch once (SC-003); shift-click from one branch to a row of a later multi-repository branch reads "2 selected" (US2-AS3, FR-009); select-all counts branches; the header checkbox is indeterminate with one of two branches selected and checked with both, while non-anchor rows are present; a logout clears the selection; a selected branch stays selected through pending → N. — comments: none unless a non-obvious constraint; see `.agents/rules/code-doc-style.md`.
- [ ] T023 [US2] Extend `frontend/app/src/entities/branches/ui/branches-table/branches-data-table.test.tsx` with: shift-range after a branch above the anchor expanded from pending to N rows still selects exactly the intended branches (research R1); accessibility: only each branch's first-row checkbox is reachable by Tab and is named "Select <branch>", the others are named "Select <branch> (<repository name>)" and have `tabIndex=-1` (FR-008); the grid template has one track per rendered column (11) and the 4th–6th tracks equal `REPOSITORY_TRACK`, `GIT_STATE_TRACK`, `COMMIT_TRACK` (SC-004). Depends on T022. — comments: none unless a non-obvious constraint; see `.agents/rules/code-doc-style.md`.
- [ ] T024 [P] [US2] Extend `frontend/app/src/entities/branches/ui/branches-table/branches-table.test.tsx`: scrolling to the next page appends the new branches with their repository rows, and the paginated query is still called with `BRANCHES_PER_PAGE` branches (US2-AS4, FR-010). Depends on T016. — comments: none unless a non-obvious constraint; see `.agents/rules/code-doc-style.md`.

### Implementation for User Story 2

- [ ] T025 [P] [US2] In `frontend/app/src/entities/branches/ui/branches-table/cells/branch-name-cell.tsx::BranchNameCell`, add an optional `repositoryName` prop and an `excludeFromTabOrder` prop: the row `Checkbox` gets `aria-label={`Select ${branch.name}`}` when `repositoryName` is absent and `aria-label={`Select ${branch.name} (${repositoryName})`}` otherwise, and `tabIndex={-1}` when `excludeFromTabOrder` is set. Covered by T023. — comments: none unless a non-obvious constraint; see `.agents/rules/code-doc-style.md`.
- [ ] T026 [US2] In `frontend/app/src/entities/branches/ui/branches-table/get-branch-table-columns.tsx::getBranchIdentifierColumn`, resolve `anchor = table.getRow(row.original.branch.id)`, pass `isSelected={anchor.getIsSelected()}` and `onClickCheckbox={getToggleSelectedRowHandler({ row: anchor, table })}`, and on non-anchor rows pass `repositoryName={row.original.repository?.name}` and `excludeFromTabOrder` (`contracts/ui-cells.md` § Selection contract). Depends on T005, T020, T025. — comments: none unless a non-obvious constraint; see `.agents/rules/code-doc-style.md`.
- [ ] T027 [US2] In `frontend/app/src/entities/branches/ui/branches-table/branches-data-table.tsx::BranchesDataTable`, set `enableRowSelection: (row) => isBranchAnchorRow(row.original)`; leave the toolbar, the delete modal and the logout `toggleAllRowsSelected(false)` effect unchanged. Make T022–T024 pass. Depends on T021, T026. — comments: none unless a non-obvious constraint; see `.agents/rules/code-doc-style.md`.

**Checkpoint**: quickstart scenarios 5, 6 and 13 pass; selection counts branches.

---

## Phase 5: User Story 3 — A branch with no repositories reads as deliberately empty (Priority: P3)

**Goal**: A branch with zero repositories, denied repository access or a failed load keeps exactly one row with an explicit muted text; the failure reason stays reachable as a tooltip, and no toast appears on either page.

**Independent Test**: spec US3: a branch not synced with Git and with no read-only repositories shows one row reading "Not synced with Git", with blank Git state and Commit cells.

### Tests for User Story 3

- [ ] T028 [P] [US3] Extend `frontend/app/src/entities/branches/ui/branches-table/get-branch-table-columns.test.tsx`: `empty` row with `sync_with_git` false and null reads "Not synced with Git", with true reads "No repositories" (FR-007, US3-AS1, US3-AS2); `denied` reads "No permission" (FR-012, US3-AS4); `error` reads "Could not load repositories" and hovering it shows the row's `errorMessage` (FR-013, US3-AS5); every one of these texts carries `text-subtle-muted`, the branch cells render, the Git state and Commit cells are empty, and no `-` or `—` appears (SC-002). Depends on T015. — comments: none unless a non-obvious constraint; see `.agents/rules/code-doc-style.md`.
- [ ] T029 [P] [US3] Add to `frontend/app/src/entities/repository/ui/branch-repositories/branch-repositories-card.test.tsx` (it has no toast assertion today) a case where the repositories request fails with a non-permission GraphQL error through the real `fetchConnection` (mock the GraphQL client, not the use-case): the card renders its failed state and no toast is shown (research R10). — comments: none unless a non-obvious constraint; see `.agents/rules/code-doc-style.md`.
- [ ] T030 [P] [US3] Extend `frontend/app/src/entities/branches/ui/branches-table/branches-table.test.tsx`: with the GraphQL client mocked so one branch gets a non-permission GraphQL error and another gets `PERMISSION_DENIED`, the first reads "Could not load repositories", the second "No permission", each on one row, every other branch keeps its rows, and no toast or page-level error renders (FR-012, FR-013, SC-005). Depends on T024. — comments: none unless a non-obvious constraint; see `.agents/rules/code-doc-style.md`.

### Implementation for User Story 3

- [ ] T031 [US3] Complete `frontend/app/src/entities/branches/ui/branches-table/cells/branch-repository-cell.tsx::BranchRepositoryCell` with the `empty` (wording from `row.branch.sync_with_git`: falsy → "Not synced with Git", `true` → "No repositories"), `denied` ("No permission") and `error` ("Could not load repositories" wrapped in `@infrahub/ui` `Tooltip` with `row.errorMessage`) branches, each as `<span className="text-subtle-muted">` (`contracts/ui-cells.md` § `BranchRepositoryCell`). Make T028 and T030 pass; T029 already passes after T003 (T030 also depends on T003). Depends on T017, T003. — comments: none unless a non-obvious constraint; see `.agents/rules/code-doc-style.md`.

**Checkpoint**: quickstart scenarios 7–11 pass; every SC-006 state has a green test.

---

## Phase 6: E2E

**Purpose**: One happy-path `/branches` case over the promoted import-error fixture (constitution IV, plan Constitution Check IV).

- [ ] T032 Live-stack pre-step: on a running stack, create a `sync_with_git=False` branch holding a broken `CoreRepository` the way `tests/e2e/branches/test_branch_details_repositories.py::TestBranchDetailsRepositoryImportError::broken_repository` does (via `tests/e2e/helpers.py::BranchAPI.create`'s default), open its branch details page and record whether the card lists the repository; then repeat with `sync_with_git=True`. Write the outcome and the `sync_with_git` value each E2E needs in a new "E2E premise verification" section at the end of `dev/specs/ifc-3201-branches-table-git/research.md`. Blocks T033–T035.
- [ ] T033 Create `tests/e2e/branches/conftest.py` (new) and move into it the `broken_repository` fixture and its helpers from `tests/e2e/branches/test_branch_details_repositories.py::TestBranchDetailsRepositoryImportError`, function-scoped (it uses `tmp_path`), taking `sync_with_git: bool` explicitly as a factory fixture (`broken_repository(sync_with_git=True)`) and keeping its cleanup. Depends on T032. — comments: none unless a non-obvious constraint; see `.agents/rules/code-doc-style.md`.
- [ ] T034 Switch `tests/e2e/branches/test_branch_details_repositories.py` to the shared fixture, removing the class-local copy and passing the `sync_with_git` value T032 established; run `uv run pytest tests/e2e/branches/test_branch_details_repositories.py` with the e2e stack up. Depends on T033. — comments: none unless a non-obvious constraint; see `.agents/rules/code-doc-style.md`.
- [ ] T035 [P] Create `tests/e2e/branches/test_branches_git_columns.py` with `pytestmark = pytest.mark.shard_branches_repo` (`tests/e2e/conftest.py::_SHARD_MARKERS` is a fixed set): with `broken_repository(sync_with_git=True)`, open `/branches` and assert on the broken branch's row the repository name, the "Import Error" pill and a 7-character commit; assert a branch without repositories reads "Not synced with Git". Scope locators to the branch's rows (`dev/guides/frontend/writing-e2e-tests.md`). Run `uv run pytest tests/e2e/branches/test_branches_git_columns.py`. Depends on T027, T031, T033. — comments: none unless a non-obvious constraint; see `.agents/rules/code-doc-style.md`.
- [ ] T036 [P] Audit `tests/e2e/branches/test_branches.py` for locators that become strict-mode violations once a branch spans several rows (`get_by_role("link", name="main", exact=True)` and the other branch-name links, row and checkbox locators); scope any violation to the anchor row (the "Select <branch>" checkbox's row) and run the file. Change nothing if the audit is clean, and say so in `dev/specs/ifc-3201-branches-table-git/pr-notes.md`. Depends on T027. — comments: none unless a non-obvious constraint; see `.agents/rules/code-doc-style.md`.

**Checkpoint**: both E2E files green with the e2e stack up.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [ ] T037 Remove `React.useMemo` from `frontend/app/src/entities/branches/ui/branches-table/branches-table.tsx::BranchesTable` (`columns`, `flatData`) and `frontend/app/src/entities/branches/ui/branches-table/branches-data-table.tsx::BranchesDataTable` (`style`), and from any other file this feature touched (`/usr/bin/grep -n "useMemo\|useCallback\|React.memo"` over them); the React Compiler memoizes (research R12). All component tests from T015–T030 stay green. Depends on T027, T031. — comments: none unless a non-obvious constraint; see `.agents/rules/code-doc-style.md`.
- [ ] T038 [P] Add `changelog/+ifc-3201-branches-table-git.added.md` (Towncrier: `orphan_prefix = "+"` and the `added` type are defined in `pyproject.toml` `[tool.towncrier]`; precedent `changelog/+generic-repository-commit.added.md`): one user-facing sentence saying the branches list shows each branch's Git repositories with their Git state and imported commit, one row per repository.
- [ ] T039 [P] Docs phase: add a section to `docs/docs/git-integration/branch-synchronization.mdx` describing the Repository, Git state and Commit columns, the one-row-per-repository layout and the two empty texts ("Not synced with Git", "No repositories"); run `uv run invoke docs.lint`. Owned by the docs phase, same PR.
- [ ] T040 [P] Knowledge capture in `dev/knowledge/frontend/shared-components.md`: a short entry on the anchor-row selection pattern (`isBranchAnchorRow`, `enableRowSelection` predicate, id-keyed `getToggleSelectedRowHandler`) for tables that fan one entity out over several rows, plus the `CommitHash` row only if #10658 has not merged first (check `git -C /Users/paul/Projects/infrahub log --oneline origin/develop -- frontend/app/src/shared/components/display/commit-hash.tsx`).
- [ ] T041 Complete `dev/specs/ifc-3201-branches-table-git/pr-notes.md`: the lifted-file SHA (T002) and the result of the pre-merge `git diff` against `ple-branches-card-ifc-3130`'s tip; the three #10779 touches (`get-branch-repositories-from-api.ts::fetchConnection` no-op `processErrorMessage`, `RepositoryNameLink` extraction from `repository-row.tsx`, `broken_repository` fixture promotion) and the owner's option to land them on #10779 first; the shared `getToggleSelectedRowHandler` change; the Constitution V N+1 deviation (≈40 requests per page) and its follow-up (backend list-of-ids variant of `InfrahubRepositoryBranchStatus`, ticket to be created by the owner); the double-stack rebase note (`git rebase --onto` after a squash-merge of #10779); the T036 audit result; note that the error tooltip surfaces the raw GraphQL `error.message`, the same text the client toasts today. Depends on T002, T036.
- [ ] T042 Run `quickstart.md` scenarios 1–14 on a dev stack, including the dark theme (scenario 14) and the network-tab check of one repositories request per branch (scenario 12); fix any regression under the task that owns the file. Depends on T037.
- [ ] T043 CI gate, all four must pass: `cd frontend && pnpm exec biome ci .`, `cd frontend/app && pnpm knip`, `cd frontend/app && pnpm exec betterer ci`, `cd frontend/app && pnpm test`. The lifted `commit-hash*` files must stay byte-identical (re-run T001's `cmp`). Depends on T037–T042.

---

## Dependencies & Execution Order

### Phase dependencies

- **Setup (Phase 1)**: no dependencies. T002 after T001; T005 after T004.
- **Foundational (Phase 2)**: after Setup (T008–T012 chain on T007; T013 and T014 are free). Blocks every story.
- **US1 (Phase 3)**: after Foundational. Cells need T001 (`CommitHash`) and T006 (`RepositoryNameLink`).
- **US2 (Phase 4)**: after US1 (it edits the columns and data table US1 retypes) and T005.
- **US3 (Phase 5)**: after US1 (it completes `BranchRepositoryCell`) and T003; independent of US2 except that T030 extends the file T024 extends.
- **E2E (Phase 6)**: T032 first; T035 and T036 need US2 and US3 in place.
- **Polish (Phase 7)**: after all stories; T043 last.

### Story order

US1 (P1) → US2 (P2) → US3 (P3). US3 may run in parallel with US2 once US1 is done, if the two people coordinate on `branches-table.test.tsx`.

### Within each story

Test tasks first and failing, then cells, then columns, then table wiring.

## Parallel Examples

**Phase 1**: T001, T003, T004 and T006 in parallel (four different files); T002 after T001, T005 after T004.

**Phase 2**: T013 and T014 in parallel with the T007 → T008 → T009 → T010 → T011 → T012 chain.

**Phase 3 (US1)**:

```text
Tests:  T015 get-branch-table-columns.test.tsx  |  T016 branches-table.test.tsx
Cells:  T017 branch-repository-cell.tsx  |  T018 branch-git-state-cell.tsx  |  T019 branch-commit-cell.tsx
Then:   T020 → T021
```

**Phase 4 (US2)**: T022, T024 and T025 in parallel; then T023, T026, T027.

**Phase 5 (US3)**: T028, T029 and T030 in parallel; then T031.

**Phase 6**: after T032–T033, T035 and T036 in parallel with T034.

**Phase 7**: T038, T039 and T040 in parallel.

## Implementation Strategy

### MVP (Setup + Foundational + US1)

1. Phase 1, Phase 2.
2. Phase 3: US1 columns, cells and loading state.
3. **Stop and validate**: quickstart scenarios 1–4 and T015/T016 green. The MVP shows the Git signal, but selection counts rows until US2, so it is a demo increment, not a shippable one.

### Incremental delivery

1. MVP → US2 (branch-level selection makes the fan-out safe for bulk delete) → US3 (empty, denied, failed) → E2E → Polish.
2. The PR ships all stories together, targeting `ple-branch-details-repos-infp-671`.

## Completeness Check

| Requirement | Tasks |
|---|---|
| FR-001 columns and order | T013, T015, T020 |
| FR-002 one row per repository | T009, T010, T021, T022 |
| FR-003 backend-authoritative set | T009, T010, T011 |
| FR-004 Git state pill, no-colour fallback | T015, T018 |
| FR-005 commit 7 chars, hover, copy | T001, T015, T019 |
| FR-006 repository link and Read-only | T006, T015, T017 |
| FR-006a repository order | T009, T010, T012 |
| FR-007 empty texts, blank cells | T009, T028, T031 |
| FR-008 per-branch selection, a11y names, tab order | T022, T023, T025, T026, T027 |
| FR-009 shift-range counts branches | T004, T005, T022, T023, T026 |
| FR-010 pagination counts branches | T009, T021, T024 |
| FR-011 per-branch loading, one spinner | T015, T016, T017, T021 |
| FR-012 no permission | T009, T028, T030, T031 |
| FR-013 load failure, tooltip, no toast | T003, T028, T029, T030, T031 |
| FR-014 syncing refresh cadence | T011, T012, T042 |
| FR-015 no filter or sort | T013, T015 |
| FR-016 no upstream, last import, operational status | T015, T018 |
| FR-017 columns always shown | T015, T020 |
| SC-001 failed imports visible from the list | T015, T035 |
| SC-002 N rows or 1 row with text | T009, T022, T028, T035 |
| SC-003 bulk delete acts once per branch | T022, T027 |
| SC-004 branch cells first, no horizontal shift | T014, T016, T023, T042 |
| SC-005 one branch's failure isolated | T009, T030 |
| SC-006 a test per state, gates pass | T009, T015, T028, T043 |
| SC-007 per-branch re-render, bounded refocus | T011, T012, T016 |
