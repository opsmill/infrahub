---
description: "Task list for the number pool body (pools without an allocation scope)"
---

# Tasks: Number pool body for pools without an allocation scope

**Input**: Design documents from `specs/ifc-3362-number-pool-body/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md)

**Tests**: Included. Constitution principle IV requires tests for every feature, and [quickstart.md](./quickstart.md) §1 lists the scenarios they must prove.

**Organization**: Tasks are grouped by user story. The shared data layer is foundational, because all three stories read the same two queries.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on an unfinished task)
- **[Story]**: the user story the task serves (US1, US2, US3)

## Path conventions

All frontend paths are relative to `frontend/app/`. `src/` paths use the `@/` alias in imports.

## Conventions every task follows

- **Layers**: entity layers per `dev/knowledge/frontend/entities-structure.md`:
  - `api/` imports only `shared/api` and its own `domain/model`
  - `domain/` has no React, TanStack Query or browser storage
  - `ui/` never imports another entity's `api/`
- **React**:
  - `import React from "react"` and `React.X`; never named imports from `"react"`
  - no `useMemo`, `useCallback` or `memo` (React Compiler is on)
  - `import * as R from "remeda"` if remeda is needed
- **Layout and icons**: use `Row` and `Col` from `@/shared/components/container` instead of raw flex divs; lucide icons sized by `className`.
- **Types**: no `as` casts and no `!`; use type guards. Props interfaces use `interface XProps extends …`.
- **Tests**:
  - next to the source as `*.test.ts(x)`
  - Vitest browser mode, rendered with `tests/components/render.tsx` and asserted with `await expect.element(...)`
  - one bare `// GIVEN`, `// WHEN` and `// THEN` each per test
  - query hooks mocked with `vi.mock(path)` and `vi.mocked(fn).mockReturnValue(...)`
  - fakes come from `tests/fake/`
- **Comments**: only a one-sentence why, and none that name other symbols (`dev/guidelines/code-doc-style.md`).
- **Default branch**: never compare a branch name with `"main"`. Use `is_default` from `useGetBranches()` (`dev/knowledge/frontend/branches.md`).

---

## Phase 1: Setup

**Purpose**: Make the PR #10932 queries available to the frontend types, and add the test data every later phase uses.

- [X] T001 Bring in PR #10932's GraphQL schema **without committing**:
  1. Run `git fetch origin pmi-number-pool-scoped-pools-ifc-3185`, then `git show origin/pmi-number-pool-scoped-pools-ifc-3185:schema/schema.graphql > schema/schema.graphql` from the repository root. This writes the working tree only; `git checkout <ref> -- <file>` would also stage the file.
  2. Run `cd frontend/app && pnpm codegen`.
  3. Verify that `src/shared/api/graphql/generated/graphql-env.d.ts` contains `InfrahubNumberPoolUtilization` and `InfrahubNumberPoolAllocations`.

  The real merge of #10932's branch happens when the user commits (plan step 1). Never stage or commit here.
- [X] T002 [P] Add fake generators to `tests/fake/number-pool.ts`, each taking `overrides?` and following the existing `generateNumberPoolData`:
  - `generateNumberPoolUsage`
  - `generateNumberPoolRange`
  - `generateNumberPoolUtilization`: defaults to two ranges, 1–50 (weight 10) and 51–100 (weight 0)
  - `generateNumberPoolAllocation`

  Types come from T003 and T004, so write this file after them, or in the same pass.

---

## Phase 2: Foundational (data layer, address, route)

**Purpose**: the domain types, queries, hooks, address helper and route that every story uses.

**⚠️ No user story work starts before this phase is complete.**

- [X] T003 [P] Add `NumberPoolUsage`, `NumberPoolRange` (extends `NodeCore`, attributes as `NodeAttribute`) and `NumberPoolUtilization` to `src/entities/resource-manager/domain/model/number-pool.ts`, exactly as in [data-model.md](./data-model.md), and `NUMBER_POOL_RANGE_KIND` to `domain/model/pool.ts`.
- [X] T004 [P] Add to `src/entities/resource-manager/domain/model/number-pool.ts`:
  - the constants `NUMBER_POOL_PROVENANCE_ALLOCATED = "ALLOCATED"` and `NUMBER_POOL_PROVENANCE_PROVIDED = "PROVIDED"`
  - the type `NumberPoolProvenance`
  - `NumberPoolAllocation` (`value`, `branch`, `holder: NodeCore`, `provenance`, `rangeId`)
- [X] T005 [P] Create `src/entities/resource-manager/domain/rules/sort-ranges-by-fill-order.ts`. `sortRangesByFillOrder(ranges)` returns a new array sorted by `allocation_weight.value` descending, then `start` ascending, then `end` ascending, and never modifies its input.

  Add `sort-ranges-by-fill-order.test.ts` covering:
  - the weights decide the order
  - equal weights fall back to start
  - equal start falls back to end
  - the input array is unchanged
- [X] T006 [P] Create `src/entities/resource-manager/api/get-number-pool-utilization-from-api.ts`:
  - the document `GET_NUMBER_POOL_UTILIZATION` from [contracts/graphql-queries.md](./contracts/graphql-queries.md), written with `graphql()` from `@/shared/api/graphql/client`
  - an exported `NumberPoolUtilizationResponse` type via `ResultOf`
  - `getNumberPoolUtilizationFromApi({ poolId, branchName, atDate })`, which sends `context: { branch, date }` like `getNumberPoolFromApi`
- [X] T007 [P] Create `src/entities/resource-manager/api/get-number-pool-allocations-from-api.ts` the same way:
  - the document `GET_NUMBER_POOL_ALLOCATIONS`
  - the variables `poolId`, `rangeId` (optional), `offset` and `limit`
  - an exported response type
  - `getNumberPoolAllocationsFromApi(params)` with the branch and date context
- [X] T008 Create `src/entities/resource-manager/api/number-pool-utilization.mappers.ts`:
  - `mapToNumberPoolUtilization(response)` returns `NumberPoolUtilization`, with ranges in the API's order (the use-case sorts them)
  - every `BigInt` field (typed `unknown`) is converted through a small `toNumber(value: unknown): number` helper that uses `Number(value)` and returns 0 for anything that is not a finite number

  Add `number-pool-utilization.mappers.test.ts` covering string and number inputs, and the field renames (`used_default_branch` → `usedDefaultBranch`). Depends on T003 and T006.
- [X] T009 Create `src/entities/resource-manager/api/number-pool-allocation.mappers.ts`:
  - `mapToNumberPoolAllocation(node)` returns `NumberPoolAllocation`
  - the holder becomes a `NodeCore` (`kind` → `__typename`), and `range.id` becomes `rangeId`
  - the provenance is narrowed with a type guard; anything that is not `"PROVIDED"` maps to `"ALLOCATED"`
  - `BigInt` fields are converted to numbers

  Add `number-pool-allocation.mappers.test.ts`. Depends on T004 and T007.
- [X] T010 Create `src/entities/resource-manager/domain/use-cases/get-number-pool-utilization.ts`:
  - exports `GetNumberPoolUtilizationParams` (extends the fetcher params) and `getNumberPoolUtilization`
  - throws `new Error(messages joined with "; ")` on GraphQL `errors`
  - maps the response and returns ranges sorted with `sortRangesByFillOrder`

  Add `get-number-pool-utilization.test.ts`, which mocks the `-from-api` module with `mockResolvedValue` and covers the sorted result and the error path. Depends on T005 and T008.
- [X] T011 Create `src/entities/resource-manager/domain/use-cases/get-number-pool-allocations.ts`:
  - exports `GetNumberPoolAllocationsParams` (`poolId`, `rangeId?`, `offset`, `limit`, `branchName`, `atDate?`)
  - exports `GetNumberPoolAllocationsResult { allocations: NumberPoolAllocation[]; count: number }`
  - exports `getNumberPoolAllocations`, which throws on `errors`

  Add `get-number-pool-allocations.test.ts`. Depends on T009.
- [X] T012 Extend `src/entities/resource-manager/ui/queries/resource-manager.query-keys.ts` with:
  - `numberPoolUtilization(params: NumberPoolUtilizationKeysParams)`: `[...all, "number-pool-utilization", poolId, branchName, atDate]`
  - `numberPoolAllocations(params: NumberPoolAllocationsKeysParams)`: `[...all, "number-pool-allocations", poolId, rangeId ?? null, branchName, atDate]`
- [X] T013 Create `src/entities/resource-manager/ui/queries/get-number-pool-utilization.query.ts` with `getNumberPoolUtilizationQueryOptions(params)` and `useGetNumberPoolUtilization(poolId)`. The hook reads `useCurrentBranch()` and `datetimeAtom`, mirroring `get-number-pool.query.ts`. Depends on T010 and T012.
- [X] T014 Create `src/entities/resource-manager/ui/queries/get-number-pool-allocations.query.ts`:
  - export `NUMBER_POOL_ALLOCATIONS_PAGE_SIZE = 100`
  - `getNumberPoolAllocationsInfiniteQueryOptions(params)` uses `infiniteQueryOptions`, with `initialPageParam: 0` and `queryFn: ({ pageParam }) => getNumberPoolAllocations({ ...params, offset: pageParam, limit: NUMBER_POOL_ALLOCATIONS_PAGE_SIZE })`
  - `getNextPageParam` sums the rows loaded across `allPages` and returns `undefined` once they reach `lastPage.count`; otherwise it returns `lastPageParam + NUMBER_POOL_ALLOCATIONS_PAGE_SIZE`
  - the hook is `useGetNumberPoolAllocations({ poolId, rangeId, enabled? })`

  Add `get-number-pool-allocations.query.test.ts` for `getNextPageParam` (stops exactly at `count`). Depends on T011 and T012.
- [X] T015 [P] In `src/entities/nodes/object/ui/routing/object-urls.ts`, make `getObjectDetailsUrl`'s resource-manager case append `tab`: `/resource-manager/${objectId ?? ""}${tab}` when `objectId` is set. Extend `object-urls.test.ts` with a case: `getObjectDetailsUrl(<a CoreNumberPool kind>, "p1", undefined, "ranges/r1")` returns `/resource-manager/p1/ranges/r1`.
- [X] T016 [P] In `src/app/router.tsx`, under the `:resourcePoolId` route's `children`, add `{ path: "ranges/:rangeId" }` as a sibling of `resources/:resourceId`, with no element or lazy import.

**Checkpoint**: `pnpm test -- resource-manager object-urls` passes, and the data layer is ready.

---

## Phase 3: User Story 1 - Find what uses a range (Priority: P1) 🎯 MVP

**Goal**: The pool page shows the ranges card in fill order and the table for the selected range, with holder links on the row's branch.

**Independent test**: render the page for a pool with two ranges and numbers on two branches, at `/resource-manager/p1/ranges/<id of 1–50>`. Only that range's rows show, there is no Range column, and a `b1` row links with `branch=b1`.

- [X] T017 [P] [US1] Create `src/entities/resource-manager/ui/number-pool/number-pool-usage-bar.tsx`, exporting `NumberPoolUsageBar({ usage })` (research R10):
  - `MultipleProgressBar` with two segments: `usedDefaultBranch / size * 100` and `usedBranches / size * 100`, guarding against `size === 0`
  - segment tooltips "Default branch: X of Y" and "Other branches only: X of Y"
  - a percentage label from a local `formatPercent(value)`: "0%", "<0.1%", one decimal below 10 with a trailing ".0" removed, otherwise a whole number, with a `Tooltip` "X of Y"
  - numbers formatted with `formatNumberDisplay` from `@/shared/utils/number`

  Add `number-pool-usage-bar.test.tsx`: `used 30`, `size 50` shows "60%".
- [X] T018 [US1] Create `src/entities/resource-manager/ui/number-pool/number-pool-ranges-card.tsx`, exporting `NumberPoolRangesCard({ poolId, poolType, utilization, selectedRangeId })` per [contracts/ui.md](./contracts/ui.md):
  - **Title:** "Ranges".
  - **List:** `ListBox` from `@infrahub/ui` with `aria-label="Ranges"`, `selectionMode="single"`, `selectionIndicator="highlight"` and `selectedKeys`:
    - `["all"]` when `selectedRangeId` is null
    - `[selectedRangeId]` when it matches a range
    - `[]` otherwise
  - **First item:** `id="all"`, `href={getObjectDetailsUrl(NUMBER_POOL_KIND, poolId)}`, showing "All ranges", "N ranges" (or "1 range") and the pool's `NumberPoolUsageBar`.
  - **Range items:** one per range in the given order, each with `href={getObjectDetailsUrl(NUMBER_POOL_KIND, poolId, undefined, \`ranges/${range.id}\`)}`, showing "<start> – <end>" (an en dash with spaces, numbers through `formatNumberDisplay`), "Weight N", and its usage bar.
  - **No ranges:** "No ranges" plus "Edit the pool to add one" when `poolType` is `NUMBER_POOL_TYPE_USER`, or "Add one in the schema" when it is `NUMBER_POOL_TYPE_SCHEMA`.
  - **Labels:** put the range label in a shared local helper `formatRangeLabel(range)` exported from this file, for reuse by the table.

  Add `number-pool-ranges-card.test.tsx`:
  - the option order matches the input
  - "All ranges" is selected when `selectedRangeId` is null
  - the matching range is selected
  - an unknown ID selects nothing
  - both no-ranges hints show for their pool type
- [X] T019 [US1] Create `src/entities/resource-manager/ui/number-pool/number-pool-allocations-table.tsx`, exporting `NumberPoolAllocationsTable({ poolId, ranges, selectedRange })` (research R4, R5, R7):
  - **Data:** call `useGetNumberPoolAllocations({ poolId, rangeId: selectedRange?.id })`, and flatten `data.pages` into rows.
  - **Heading:** "Allocations" with the `count` of the first page.
  - **Table:** `Virtualizer` with `layout={TableLayout}` and `layoutOptions={{ rowHeight: 36, headingHeight: 32, loaderHeight: 40 }}`, around a react-aria `Table` with `aria-label="Allocations"`. The `Table` is the scroll container (`overflow-auto`, bounded height through flex `min-h-0`), with `style={{ scrollPaddingTop: 32 }}`.
  - **Columns:**
    - Number: right-aligned, `formatNumberDisplay`
    - Object: a `Link` to `getObjectDetailsUrl(holder.kind, holder.id, [branchParam])`, where `branchParam` is `{ name: QSP.BRANCH, exclude: true }` when the row's branch is the default branch (from `useGetBranches()` and `is_default`), otherwise `{ name: QSP.BRANCH, value: row.branch }`
    - Kind
    - Branch: lucide `GitBranchIcon` before non-default branch names
    - Range: only when `selectedRange` is null and `ranges.length > 1`, shown with `formatRangeLabel`
    - Source: a tag reading "Allocated" or "Provided"
  - **Cells:** truncate long text.
  - **Loading more:** `TableBody` holds a `Collection` of rows, then `TableLoadMoreItem` with `onLoadMore={fetchNextPage}`, `isLoading={isFetchingNextPage}`, rendered while `hasNextPage`. Its content is a `Spinner` and "Loading more".
  - **Empty state** (`renderEmptyState`): "No allocations yet" without `selectedRange`, otherwise "No allocations in <range>".
  - **First load and errors:** a loading state while the first page is pending, and `ErrorScreen` with the error message on failure.

  Add `number-pool-allocations-table.test.tsx`, mocking `useGetNumberPoolAllocations` and `useGetBranches`:
  - the Range column appears or hides per the rule
  - a `b1` row's link `href` contains `branch=b1`
  - a default-branch row's link has no `branch` parameter
  - "Provided" shows
  - both empty messages show
  - with `hasNextPage` true, `fetchNextPage` is called after scrolling to the end
- [X] T020 [US1] Rewrite `src/pages/resource-manager/number-pool-details.tsx`. Keep `NumberPoolHeader` and `NumberPoolHeaderSkeleton` exactly as used today, and replace `ResourcePoolDetailsBody` with the body:
  - read `const { rangeId } = useParams<{ rangeId?: string }>()`
  - call `useGetNumberPoolUtilization(poolId)`
  - layout: a two-column grid (ranges card about 18rem, table card flexible) filling the remaining height of `Content.Card`, using `Card` from `@infrahub/ui` for both cards
  - while utilization is pending: a loading state in the body; on error: `ErrorScreen` with the message
  - the ranges card gets `selectedRangeId={rangeId ?? null}`
  - table area:
    - when there are no ranges, the ranges card alone carries the message
    - when `rangeId` is set and found, or not set, render `<NumberPoolAllocationsTable key={selectedRange?.id ?? "all"} … />`

  The header's loading and error behaviour does not change. Update `number-pool-details.test.tsx`: mock `useGetNumberPoolUtilization` and the table component, and cover the loading, error, no-ranges and selected-range cases (the table receives the matching range).

**Checkpoint**: User Story 1 works on its own. The page shows the ranges and the table for "All ranges" and for one range.

---

## Phase 4: User Story 2 - Share a range (Priority: P2)

**Goal**: opening a range address directly selects that range, and an address that names a range not in the pool shows a message instead of a request.

**Independent test**: render the page at `/resource-manager/p1/ranges/unknown`. "This range is not part of the pool" and a link "All ranges" show, no option is selected, and the table component is not rendered.

- [X] T021 [US2] In `src/pages/resource-manager/number-pool-details.tsx`, when `rangeId` is set and not found in `utilization.ranges`, render "This range is not part of the pool" and a `Link` "All ranges" to `getObjectDetailsUrl(NUMBER_POOL_KIND, poolId)` in the table card, and do not render `NumberPoolAllocationsTable`. Extend `number-pool-details.test.tsx`:
  - the unknown-range case: message, link `href`, and the table mock not called
  - a direct-address case: rendered at `/resource-manager/p1/ranges/<id>`, the matching option is selected and the table receives that range

**Checkpoint**: User Stories 1 and 2 both work on their own.

---

## Phase 5: User Story 3 - Use the page with the keyboard only (Priority: P3)

**Goal**: keyboard navigation through the ranges card and the table, provided by react-aria.

**Independent test**: focus the ranges list, press ArrowDown and Enter, and the address changes to the next range.

- [X] T022 [P] [US3] Extend `src/entities/resource-manager/ui/number-pool/number-pool-ranges-card.test.tsx` with a keyboard test, using `userEvent` from `vitest/browser`: tab into the listbox, press `ArrowDown`, then `Enter`, and assert that the router location becomes the next range's address. Fix `number-pool-ranges-card.tsx` if the test fails.
- [X] T023 [P] [US3] Extend `src/entities/resource-manager/ui/number-pool/number-pool-allocations-table.test.tsx` with a keyboard test: focus the grid, press `ArrowDown` to move between rows and `ArrowRight` into the Object cell, and assert that the holder `link` receives focus. Fix `number-pool-allocations-table.tsx` if needed (for example `keyboardNavigationBehavior`).

**Checkpoint**: all three stories work on their own.

---

## Phase 6: Polish and cross-cutting

- [X] T024 [P] Delete `TestNumberPool::test_displays_correct_details_for_created_number_pool` from `../../tests/e2e/resource-manager/test_number_pool.py` (research R12). Run `uv run ruff check tests/e2e/resource-manager/test_number_pool.py` from the repository root.
  - Found during implementation: two more tests in this file relied on the old body. `test_update_form_should_not_include_node_and_attribute_selects` now waits for the pool's heading instead of the old properties-card cell, and `test_number_pool_attribute_kind_resource_manager` no longer clicks the old "View" link before its docs screenshot.
- [X] T025 [P] Add `../../changelog/+ifc-3362-number-pool-body.changed.md`, following the `creating-changelog-entries` skill. It is one sentence on what a user now views on a number pool's page: ranges in fill order with their usage, and the numbers of the selected range with the node that holds each one.
- [X] T026 Run the frontend gate from [quickstart.md](./quickstart.md) §1 and fix what fails:
  - `cd frontend && pnpm exec biome ci .`
  - `cd frontend/app && pnpm knip`
  - `pnpm exec betterer ci`
  - `pnpm test -- resource-manager object-urls`
- [X] T027 Re-read the changed files against the conventions above (layers, React imports, no `as`, comments, default branch rule), and confirm that `ResourcePoolDetailsBody` is no longer imported by `number-pool-details.tsx` but is still used by `resource-pool-details.tsx`.

---

## Dependencies and execution order

- **Phase 1** → **Phase 2** → **Phases 3 to 5** → **Phase 6**.
- **Inside Phase 2**:
  - T003, T004, T005, T006 and T007 can start together.
  - T008 needs T003 and T006, and T009 needs T004 and T007.
  - T010 needs T005 and T008, and T011 needs T009.
  - T013 needs T010 and T012, and T014 needs T011 and T012.
  - T015 and T016 are independent.
- **US1**: T017 first. T018 needs T017. T019 needs T018 (it reuses `formatRangeLabel`). T020 needs T018 and T019.
- **US2**: T021 needs T020 (same file).
- **US3**: T022 needs T018, and T023 needs T019. The two can run in parallel.
- **Polish**: T024 and T025 can run any time. T026 and T027 run last.

## Parallel examples

```text
Phase 2 start:  T003, T004, T005, T006, T007, T015, T016 together
US3:            T022 and T023 together
Polish:         T024 and T025 together
```

## Implementation strategy

1. **MVP**: Phases 1 and 2, then US1 (T017–T020). The page replaces the old body for number pools.
2. **Then**: US2 (T021), then US3 (T022–T023).
3. **Finally**: Phase 6, then report to the user. Nothing is staged or committed at any point; the user decides how to commit and when to replace T001's schema checkout with the real merge of #10932.
