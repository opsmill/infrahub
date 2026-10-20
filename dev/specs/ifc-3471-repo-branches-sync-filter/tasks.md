# Tasks: Filter a repository's branches by sync status

**Input**: `dev/specs/ifc-3471-repo-branches-sync-filter/` (spec.md, plan.md, research.md, data-model.md, contracts/branches-section-filter.md, quickstart.md)

**Tests**: Requested. The plan is test first: each test task is written and seen failing before its implementation task.

Paths are relative to `frontend/app/` unless they start with `tests/e2e/`, `changelog/` or `dev/`. Card folder: `src/entities/repository/ui/repository-branches-card/`, written `<card>/`.

**Rules for every implementer**: no `useMemo`, `useCallback` or `React.memo` (React Compiler). Comments are silent by default: add one only for a constraint, an invariant or a workaround, one sentence; see `.agents/rules/code-doc-style.md`. Tests use GIVEN / WHEN / THEN comments, as the neighbouring tests do. Run one file with `pnpm vitest run <path>` from `frontend/app`.

## Phase 1: Setup

- [x] T001 Check the worktree is on `ple-repo-branches-sync-filter-ifc-3471` and `frontend/app` dependencies are installed (`pnpm install --frozen-lockfile`); run `pnpm vitest run src/entities/repository src/entities/nodes/filters` once to record the baseline

## Phase 2: Foundational (blocks every user story)

### Sync status values (domain)

- [x] T002 [P] Write failing tests in `src/entities/repository/domain/model/repository.test.ts` (new file): `isFilterableSyncStatus` accepts each of `unknown`, `in-sync`, `error-import`, `error-ref-missing`, `syncing` and rejects `"bogus"`, `""` and `42`
- [x] T003 [P] In `src/entities/repository/domain/model/repository.ts`, add `REPOSITORY_SYNC_STATUS_ERROR_REF_MISSING = "error-ref-missing"`, `FILTERABLE_SYNC_STATUSES` (the five values in schema order, `as const`, built from the existing `REPOSITORY_SYNC_STATUS_*` constants), type `FilterableSyncStatus` and type guard `isFilterableSyncStatus(value: unknown): value is FilterableSyncStatus`, mirroring `isFilterableBranchStatus` in `<card>/branch-row-fields.ts`; make T002 pass

### Query variable

- [x] T004 [P] In `src/entities/repository/api/get-repository-branch-status-from-api.test.ts`, remove `"sync_status__value"` from `UNDECLARED_ARGUMENTS`, rewrite the comment above it so it describes only `internal_status__value` and `own_values_only`, and add a failing test that the printed query declares `$sync_status__value` and that calling with `sync_status__value: "error-import"` sends it in the request variables
- [x] T005 In `src/entities/repository/api/get-repository-branch-status-from-api.ts` (`REPOSITORY_BRANCH_STATUS` document), declare `$sync_status__value: String` and pass `sync_status__value: $sync_status__value` to `InfrahubRepositoryBranchStatus`; run `pnpm codegen:graphql` and keep the regenerated `src/shared/api/graphql/generated/graphql-cache.d.ts`; make T004 pass

### Choice labels on the shared filter tags

- [x] T006 [P] In `src/entities/nodes/filters/ui/active-filter-tags.test.ts` (`describe("formatAttributeFilterValue")` and `getFilterTagDisplay` tests), write failing tests: a Dropdown attribute with choices and no `showChoiceLabels` keeps the stored value (`error-import`), which guards every other table; with `showChoiceLabels` a Dropdown value shows its choice label (`Import Error`); with `showChoiceLabels` a value with no matching choice keeps the stored value; with `showChoiceLabels` a `Text` attribute with an `enum` keeps the stored value (`OPEN`); Boolean and DateTime cases keep their current results. Update the existing calls to the new signature
- [x] T007 In `src/entities/nodes/filters/ui/active-filter-tags.tsx`, change `formatAttributeFilterValue` to take `{ schema, value, formatDate, showChoiceLabels }` (the attribute schema instead of `kind`); for kind Dropdown with `showChoiceLabels`, return `schema.choices?.find(({ name }) => name === value)?.label ?? value`; leave every other branch unchanged. Add `showChoiceLabels?: boolean` to `ActiveFilterTagsProps` and pass it through `EditableFilterTag` to `getFilterTagDisplay` and on to `formatAttributeFilterValue`. Do not change the other two callers (`src/entities/nodes/object/ui/filters/active-object-filter-tags.tsx`, `src/entities/branches/ui/branches-list.tsx`); make T006 pass

### Request arguments (after T003 and T005)

- [x] T008 In `<card>/to-repository-branch-arguments.test.ts`, write failing tests: each of the five values maps to `{ sync_status__value }` (`it.each`); `"bogus"`, `""` and `42` produce `{}` and `hasRepositoryBranchFilters` is false for them; name, `OPEN` and `error-import` together produce all three arguments; `hasRepositoryBranchFilters` is true for a sync status filter alone. Do not reuse `sync_status` as the "unsupported field" example in the existing `it.each`
- [x] T009 In `<card>/to-repository-branch-arguments.ts`, add `"sync_status__value"` to the `RepositoryBranchArguments` `Pick`, add `toSyncStatusArguments(filters)` that keeps the value only when `isFilterableSyncStatus` passes, spread it in `toRepositoryBranchArguments`, and add an explicit `sync_status__value !== undefined` check to `hasRepositoryBranchFilters`; make T008 pass

### Test data

- [x] T010 In `tests/fake/repository.ts`, add `generateRepositorySyncStatusChoices()` returning five `DropdownChoiceRead` entries in schema order with the labels of `backend/infrahub/core/schema/definitions/core/repository.py` (`GenericRepository`, attribute `sync_status`): Unknown, Import Error, Tracked Ref Missing, In Sync, Syncing (copy `color` and `description` too). Use it as `choices` of `syncStatusAttribute` in `<card>/repository-branches-card.test.tsx` for both `repositorySchema` and `readOnlyRepositorySchema`; run the card tests and confirm they still pass

**Checkpoint**: domain guard, query variable, shared tag flag and request arguments are green.

## Phase 3: User Story 1 - List only the branches that failed to import (P1) 🎯 MVP

**Goal**: The filter picker offers Sync Status with five labelled values; applying one lists only matching branches, with the filtered count, the label in the tag and the filtered empty state.

**Independent test**: apply Sync Status "Import Error" from the picker; only matching rows, `1 branch` next to the heading, tag `Sync status contains Import Error`.

- [ ] T011 [US1] In `<card>/repository-branches-card.test.tsx`, copying the Status filter tests and the `openFilterField` / `expectServerDrivenChange` helpers, write failing tests: the picker offers a Sync status field whose value list shows the five labels in schema order; choosing "Import Error" sends `sync_status__value: "error-import"` (the stored value, not the label) and the total changes to the server count; with both filters applied, the tags read `Sync status contains Import Error` and `Status contains OPEN`; a filter matching nothing shows "No branch matches these filters"; removing the tag returns the unfiltered list; with `readOnlyRepositorySchema` the picker also offers Sync status
- [ ] T012 [US1] In `<card>/branch-row-fields.ts`, add `getSyncStatusAttribute(schema: ModelSchema)` using `REPOSITORY_SYNC_STATUS_ATTRIBUTE_NAME`, and replace `BRANCH_ROW_FILTER_DEFINITIONS` and `BRANCH_ROW_FILTER_DEFINITIONS_BY_NAME` with `getBranchRowFilterDefinitions(schema: ModelSchema): { list: FilterDefinition[]; byName: Record<string, FilterDefinition> }` returning Name, Status and, when the attribute exists, `{ type: "attribute", schema: syncStatusAttribute }`; update the comments that say the card filters on two fields
- [ ] T013 [US1] In `<card>/repository-branches-toolbar.tsx`, take `{ schema }: { schema: ModelSchema }`, build `getBranchRowFilterDefinitions(schema)` while rendering, pass `list` to `FilterPicker`, and pass `byName` plus `showChoiceLabels` to `ActiveFilterTags`; in `<card>/repository-branches-card.tsx`, render `<RepositoryBranchesToolbar schema={schema} />`; make T011 pass and fix any remaining import of the removed constants (`pnpm knip` must stay clean)

**Checkpoint**: User Story 1 works from the filter picker.

## Phase 4: User Story 2 - Filter from the Sync Status column header (P2)

**Goal**: The Sync Status column header offers a filter and no sort, writing the same filter as the picker.

**Independent test**: apply Import Error from the column header; same rows, tag and URL as from the picker; no sort action.

- [ ] T014 [US2] In `<card>/repository-branches-card.test.tsx` (and `<card>/columns.test.tsx` for the header alone), write failing tests: the Sync status header button opens a menu with "Filter" and no sort item; applying a value from it sends the same variables and writes `sync_status__value` to `${BRANCHES_URL_PREFIX}_filter`; the same holds with `readOnlyRepositorySchema`
- [ ] T015 [US2] In `<card>/columns.tsx` (`getSyncStatusColumn`), remove `isDisabled` and its comment, pass `filterConditions={BRANCH_ROW_FILTER_CONDITIONS}` without a `schema` prop, and replace `findAttribute(schema, "sync_status")` with `getSyncStatusAttribute(schema)`; remove `findAttribute` if it has no caller left; make T014 pass

**Checkpoint**: User Stories 1 and 2 work independently.

## Phase 5: User Story 3 - Combine, page and share a filtered list (P3)

**Goal**: The Sync Status filter combines with search and Status, resets paging, persists in the URL and ignores an invalid stored value.

**Independent test**: search + Status + Sync Status, reload; all three restored and sent together.

- [ ] T016 [US3] In `<card>/repository-branches-card.test.tsx`, write tests (they should pass on the code from T009 and T013; if one fails, fix the cause in the card files): search text, Status and Sync Status are sent in one request; applying, changing or removing the Sync Status filter returns to page 1; a `branches_filter` URL entry `sync_status__value: "error-import"` restores the filter and its tag on load; an entry `sync_status__value: "bogus"` sends `FIRST_PAGE_VARIABLES` with no sync status

## Phase 6: Polish and cross-cutting

- [ ] T017 Add `tests/e2e/repository/test_repository_branches_sync_filter.py` (marker `shard_branches_repo`), following `tests/e2e/repository/test_repository_sync_status.py` and research R7: create a branch with `sync_with_git=True`, wait until `demo-edge` is imported on it, set its `sync_status` to `error-import` with the SDK, open the `demo-edge` repository page, apply Sync Status "Import Error" from the Branches section, and assert with `expect` that the branch is listed and a branch with another sync status is not. If the value is overwritten by a synchronization cycle, use the fallback in R7 and state the reason in the fixture docstring. Run it with `uv run pytest -c tests/e2e/pytest.ini tests/e2e/repository/test_repository_branches_sync_filter.py -s --pdb` (prefix `sleep infinity |` in a non-interactive shell)
- [ ] T018 [P] Add the changelog fragment `changelog/+ifc-3471-repo-branches-sync-filter.added.md` with the `creating-changelog-entries` skill: a user can filter a repository's Branches section by Sync Status, from the filter picker or the Sync Status column header
- [ ] T019 Run the frontend CI gate and paste the output: `node_modules/.bin/biome ci .` in `frontend`, then `pnpm knip`, `pnpm exec betterer ci` and `pnpm test` in `frontend/app`; on a `graphql-cache.d.ts` conflict after a rebase, take either side and rerun `pnpm codegen:graphql`
- [ ] T020 Walk `dev/specs/ifc-3471-repo-branches-sync-filter/quickstart.md` scenarios 1 to 7 against the running stack

## Dependencies

- T001 → everything.
- T002 → T003; T004 → T005; T006 → T007 (three independent pairs).
- T003 and T005 → T008 → T009.
- T009, T007 and T010 → T011 → T012 → T013 (US1).
- T013 → T014 → T015 (US2 reuses the definitions and `getSyncStatusAttribute`).
- T013 → T016 (US3).
- T013, T015, T016 → T017, T019, T020. T018 any time.

## Parallel execution

- Wave 1: T002+T003, T004+T005 and T006+T007 as three parallel units (no shared file).
- Wave 2: T008, T009, then T010.
- Wave 3: T011 to T016 in order, one implementer, because they share `<card>/repository-branches-card.test.tsx`.
- T018 alongside any wave.

## Implementation strategy

MVP is Phase 2 plus User Story 1 (T001 to T013): the need from IFC-3156 is met from the filter picker. User Stories 2 and 3 follow in the same PR; they reuse the same definitions and add tests rather than new mechanisms.
