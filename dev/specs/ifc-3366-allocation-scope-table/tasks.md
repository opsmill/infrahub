# Tasks: Allocation scope table for scoped number pools

**Input**: Design documents from `specs/ifc-3366-allocation-scope-table/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md)

**Tests**: Included. The constitution (IV. Test Discipline) and the spec's Assumptions require component tests and an end-to-end test.

**Organization**: Grouped by user story. Only User Story 1 belongs to IFC-3366; User Story 2 is recorded but has no tasks here.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an unfinished task)
- **[Story]**: The user story the task belongs to

## Conventions for every task

- Paths starting with `frontend/app/src/` are the app source; `frontend/app/tests/` holds fakes; `tests/e2e/` is the repo-root e2e suite.
- Read `frontend/app/AGENTS.md`, `dev/guidelines/frontend/page-architecture.md`, `dev/knowledge/frontend/entities-structure.md` and `dev/guides/frontend/writing-component-tests.md` before the first frontend task.
- No new `domain/rules` file. A helper with one caller stays in its caller's file (research R7).
- Imports: `import React from "react"` and `React.X` for hooks; `import * as R from "remeda"`; no `useMemo` or `useCallback` (React Compiler).
- Layout with `Row` / `Col` from `shared/components/container`. Branch components with early returns.
- Interface copy says "allocation scope", never "scope" alone (spec FR-012).
- Comments explain a non-obvious why in one sentence. No ticket, spec or requirement IDs in comments or test names.
- Component tests: one `// GIVEN`, one `// WHEN`, one `// THEN` per test; mock the query hooks with `vi.mock`; render with `tests/components/render.tsx`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: URL parameter keys shared by the hooks, the URL helpers and the tests.

- [X] T001 Add `ALLOCATION_SCOPE: "allocation_scope"`, `ALLOCATION_SCOPE_SEARCH: "allocation_scope_search"` and `ALLOCATION_SCOPE_SORT: "allocation_scope_sort"` to `QSP` in `frontend/app/src/shared/config/qsp.ts`, next to `POOL_ALLOCATION_BRANCH` and `POOL_ALLOCATION_SOURCE`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The allocation scope types, the list query, and the `division` argument on the three existing queries. Every User Story 1 task depends on this phase.

**⚠️ CRITICAL**: No User Story 1 work can begin until this phase is complete.

### Domain types

- [X] T002 Add `NumberPoolDivisionValue`, `NumberPoolDivisionEntry`, `NumberPoolDivision`, `NumberPoolDivisions` and `NumberPoolDivisionSelector` to `frontend/app/src/entities/resource-manager/domain/model/number-pool.ts`, with the fields listed in [data-model.md](data-model.md) "New types"

### Allocation scope list (new query)

- [X] T003 [P] Export `mapToNumberPoolUsage` from `frontend/app/src/entities/resource-manager/api/number-pool-utilization.mappers.ts` so the allocation scope mapper can reuse it; keep its behavior unchanged
- [X] T004 [P] Create `frontend/app/src/entities/resource-manager/api/get-number-pool-divisions-from-api.ts` with the `GET_NUMBER_POOL_DIVISIONS` operation from [contracts/graphql.md](contracts/graphql.md) and `getNumberPoolDivisionsFromApi({ poolId, branchName, atDate })`, following `get-number-pool-utilization-from-api.ts::getNumberPoolUtilizationFromApi` (export the response node types with `ResultOf`)
- [X] T005 Create `frontend/app/src/entities/resource-manager/api/number-pool-division.mappers.ts::mapToNumberPoolDivisions` (depends on T002–T004): `fields` from `allocation_scope[].name`; each division's `label`, `entries` (`path`, `label` from `display_label`, `peerKind` from `peer_kind`, `value` narrowed from `GenericScalar` to `string | number | boolean`, anything else turned into a string) and `usage` through `mapToNumberPoolUsage`; keep the backend order
- [X] T006 [P] Test the mapper in `frontend/app/src/entities/resource-manager/api/number-pool-division.mappers.test.ts`: string, number and boolean values keep their type; another type becomes a string; an unreadable peer keeps the ID as its label; the order of divisions and entries is kept
- [X] T007 Create `frontend/app/src/entities/resource-manager/domain/use-cases/get-number-pool-divisions.ts::getNumberPoolDivisions` (params `GetNumberPoolDivisionsParams`), calling `getNumberPoolDivisionsFromApi` and the mapper, and throwing an `Error` built from the joined `errors` messages as `get-number-pool-utilization.ts::getNumberPoolUtilization` does
- [X] T008 [P] Test the use case in `frontend/app/src/entities/resource-manager/domain/use-cases/get-number-pool-divisions.test.ts`, mocking `getNumberPoolDivisionsFromApi`: returns the mapped list; throws with the joined error messages
- [X] T009 Add `numberPoolDivisions({ poolId, branchName, atDate })` to `frontend/app/src/entities/resource-manager/ui/queries/resource-manager.query-keys.ts::resourceManagerQueryKeys`, under `all`, and create `frontend/app/src/entities/resource-manager/ui/queries/get-number-pool-divisions.query.ts` with `getNumberPoolDivisionsQueryOptions` and `useGetNumberPoolDivisions(poolId)`, reading `currentBranch` and `datetimeAtom` as `get-number-pool-utilization.query.ts::useGetNumberPoolUtilization` does

### `division` argument on the existing queries

- [X] T010 [P] Add an optional `division?: NumberPoolDivisionSelector` through the utilization chain:
  - `$division: [NumberPoolDivisionEntryInput!]` variable and `division: $division` argument in `api/get-number-pool-utilization-from-api.ts`
  - the params of `domain/use-cases/get-number-pool-utilization.ts`
  - `division` in `resourceManagerQueryKeys.numberPoolUtilization`
  - a second optional parameter of `ui/queries/get-number-pool-utilization.query.ts::useGetNumberPoolUtilization`

  All paths are under `frontend/app/src/entities/resource-manager/`. Leaving `division` out must send the same request as today.
- [X] T011 [P] Do the same for the allocation list and count, in `frontend/app/src/entities/resource-manager/`:
  - API: `api/get-number-pool-allocations-from-api.ts`, `api/get-number-pool-allocation-count-from-api.ts`
  - use cases: `domain/use-cases/get-number-pool-allocations.ts`, `domain/use-cases/get-number-pool-allocation-count.ts`
  - query hooks: `ui/queries/get-number-pool-allocations.query.ts::useGetNumberPoolAllocations`, `ui/queries/get-number-pool-allocation-count.query.ts::useGetNumberPoolAllocationCount` (new `division` field in their params)
  - query keys: `numberPoolAllocations` and `numberPoolAllocationCount` in `resource-manager.query-keys.ts`
- [X] T012 [P] Extend the existing use-case tests in `frontend/app/src/entities/resource-manager/domain/use-cases/`: `get-number-pool-utilization.test.ts`, `get-number-pool-allocations.test.ts` and `get-number-pool-allocation-count.test.ts`. Check that a given `division` reaches the API function, and that leaving it out sends none.

### Test fakes

- [X] T013 [P] Add `generateNumberPoolDivisionEntry`, `generateNumberPoolDivision` and `generateNumberPoolDivisions({ fields, count })` to `frontend/app/tests/fake/number-pool.ts` (depends on T002). Use deterministic labels such as `device-0001`, and descending usage so the default order is predictable.

**Checkpoint**: the list of allocation scopes can be fetched, and the usage and allocations of one allocation scope can be requested. Nothing is visible yet.

---

## Phase 3: User Story 1 - View every allocation scope of a pool and open one (Priority: P1) 🎯 MVP

**Goal**: A scoped pool's details page shows the table of its allocation scopes instead of an error. Each row opens a shareable page with the ranges and allocations of that allocation scope.

**Independent Test**:
1. Create a pool scoped by Device and allocate numbers on two devices.
2. Open the pool and check that two rows appear, the fullest first.
3. Search to one row.
4. Open a row and check that only its numbers are listed, the URL contains `allocation_scope`, and reloading shows the same page ([quickstart.md](quickstart.md) Q1–Q11).

### URL state and URL helpers

- [X] T014 [US1] Create `frontend/app/src/entities/resource-manager/ui/hooks/use-number-pool-division.ts::useNumberPoolDivision(fields: string[])`.
  - It reads `QSP.ALLOCATION_SCOPE` as a raw string with nuqs `useQueryState`.
  - It returns one of these results:
    - `{ status: "none" }` when the parameter is absent
    - `{ status: "mismatch" }` when the value is not JSON, not an array of strings, numbers and booleans, or has a length different from `fields.length`
    - `{ status: "selected", values, selector }`, where `selector` pairs each field name with its value
  - Parsing and building the selector are functions in the same file (research R2, R3, R7).
- [X] T015 [P] [US1] Test the hook in `frontend/app/src/entities/resource-manager/ui/hooks/use-number-pool-division.test.ts`:
  - absent parameter
  - valid array with mixed types, keeping `100` apart from `"100"`
  - invalid JSON
  - wrong item type
  - wrong length
  - empty-string value
- [X] T016 [US1] Create `frontend/app/src/entities/resource-manager/ui/hooks/use-number-pool-division-table-state.ts::useNumberPoolDivisionTableState()` (research R6).
  - It exports the `NumberPoolDivisionSort` type, `{ by: "usage" | string; direction: "ascending" | "descending" }`.
  - **Search**: `QSP.ALLOCATION_SCOPE_SEARCH`, default `""`, URL writes through `limitUrlUpdates: debounce(300)`.
  - **Sort**: `QSP.ALLOCATION_SCOPE_SORT`, parsed with `createParser` from `<field>:<asc|desc>`, default usage descending, left out of the URL when it is the default.
  - It returns `[{ search, sort }, { setSearch, setSort }]`.
- [X] T017 [US1] Update `frontend/app/src/entities/resource-manager/ui/routing/number-pool-urls.ts` (contracts/url.md):
  - add `QSP.ALLOCATION_SCOPE` to `NUMBER_POOL_PRESERVED_QSP`
  - add `getNumberPoolDivisionUrl(poolId, values)`, which sets `allocation_scope` to `JSON.stringify(values)` on `/resource-manager/${poolId}`
  - add `getNumberPoolDivisionsUrl(poolId)`, which excludes `allocation_scope`

  Both new helpers use `constructPath`. Search and sort are dropped because they are not preserved.
- [X] T018 [P] [US1] Test the URL helpers in `frontend/app/src/entities/resource-manager/ui/routing/number-pool-urls.test.ts`:
  - range links keep `allocation_scope`, the branch and the allocation filters
  - the allocation scope URL drops the range, search and sort
  - the "All allocation scopes" URL drops `allocation_scope`

### Allocation scopes table and card

- [X] T019 [US1] Create `frontend/app/src/entities/resource-manager/ui/number-pool/details/number-pool-divisions-table.tsx::NumberPoolDivisionsTable({ poolId, fields, divisions, sort, onSortChange })` (research R5).
  - `fields` is `Array<{ name: string; label: string }>`.
  - **Table**: a plain `<table>` inside a scroll container with `overflow: auto`, and a sticky `<thead>`.
  - **Columns**: one per field. A cell shows the entry label, truncated with the full text in `title`. A relationship cell also shows `peerKind` below the label in small mono text. An empty value shows "No value".
  - **Usage column**: last, with `position: sticky; right: 0`, an opaque background and its own left edge (see the prototype's `PINNED_EDGE` / `PINNED_SURFACE`). It reuses `NumberPoolUsageBar`.
  - **Sorting**: each header is a button that calls `onSortChange`. The sorted header has `aria-sort`.
  - **Links**: the first cell is the shared `Link` to `getNumberPoolDivisionUrl`. A click elsewhere on the row navigates to the same URL, ignoring clicks inside an anchor and clicks with a modifier key.
- [X] T020 [US1] Create `frontend/app/src/entities/resource-manager/ui/number-pool/details/number-pool-divisions-card.tsx::NumberPoolDivisionsCard({ pool })`.
  - **Data**: `useGetNumberPoolDivisions(pool.id)`, and `useNumberPoolDivisionTableState()`.
  - **Field labels**: from the node schema of `pool.node.value`, using `useSchema`, falling back to the field name.
  - **Search and sort**: done in this file with `React.useDeferredValue` on the search text.
    - Search matches any entry label, ignoring case.
    - Sort compares labels with `localeCompare` and `numeric: true`, or compares usage. Ties keep the backend order.
  - **Header bar**: the title "Allocation scopes", the total count, and a `SearchInput` whose placeholder names the fields.
  - **Other states**:
    - loading: skeleton rows
    - error: `ErrorScreen`
    - empty list: "No numbers allocated yet. An allocation scope appears here once an object in it holds a number from this pool."
    - no search match: "No allocation scope matches"
- [X] T021 [P] [US1] Test the table in `frontend/app/src/entities/resource-manager/ui/number-pool/details/number-pool-divisions-table.test.tsx`:
  - columns follow the field order
  - the usage header and cells are sticky on the right
  - the first cell links to the allocation scope URL
  - a row click navigates once
  - a modifier click on the link is not intercepted
  - the sorted header carries `aria-sort`
  - an empty value shows "No value"
- [X] T022 [P] [US1] Test the card in `frontend/app/src/entities/resource-manager/ui/number-pool/details/number-pool-divisions-card.test.tsx`, mocking `useGetNumberPoolDivisions`:
  - default order by usage
  - search ignoring case
  - sort by a field with numeric-aware order
  - total count
  - both empty messages
  - 1,000 generated rows render and the last one can be scrolled into view

### Allocation scope page pieces

- [X] T023 [P] [US1] Create `frontend/app/src/entities/resource-manager/ui/number-pool/details/number-pool-division-summary.tsx::NumberPoolDivisionSummary({ poolId, fields, values })`.
  - It reads the cached list with `useGetNumberPoolDivisions` and finds the allocation scope whose entry values equal `values`, with an in-file function.
  - It shows one "<field label>: <entry label>" line per field. When no row matches, it shows the raw value (research R4).
  - It shows the "All allocation scopes" link to `getNumberPoolDivisionsUrl`.
- [X] T024 [P] [US1] Test the summary in `frontend/app/src/entities/resource-manager/ui/number-pool/details/number-pool-division-summary.test.tsx`:
  - labels shown when the list holds the allocation scope
  - raw values shown when it does not
  - the link goes back to the table
- [X] T025 [P] [US1] Create `frontend/app/src/entities/resource-manager/ui/number-pool/details/number-pool-division-mismatch.tsx::NumberPoolDivisionMismatch({ poolId, fieldLabels })` with the message "This link does not match the pool's allocation scope (<labels joined with " + ">)." and the "All allocation scopes" link
- [X] T026 [US1] Add an optional `division?: NumberPoolDivisionSelector` prop:
  - to `number-pool-allocations-card.tsx::NumberPoolAllocationsCard`
  - to `number-pool-allocations-table.tsx::NumberPoolAllocationsTable`, which forwards it to `useGetNumberPoolAllocations` and `useGetNumberPoolAllocationCount`

  Both files are in `frontend/app/src/entities/resource-manager/ui/number-pool/details/`. The range links and the "View all ranges" link already keep `allocation_scope` through T017.
- [X] T027 [P] [US1] Extend `frontend/app/src/entities/resource-manager/ui/number-pool/details/number-pool-allocations-table.test.tsx`: a given `division` reaches both query hooks
- [X] T028 [P] [US1] Extend the private `AllocationSentence` in `frontend/app/src/entities/resource-manager/ui/number-pool/details/number-pool-header.tsx`:
  - **Scoped pool**: append "scoped by <labels joined with " + ">", with labels from the node schema and the field name as fallback.
  - **Unscoped pool**: nothing changes.
- [X] T029 [P] [US1] Extend `frontend/app/src/entities/resource-manager/ui/number-pool/details/number-pool-header.test.tsx`: a scoped pool shows "scoped by Device + Role"; an unscoped pool shows no "scoped by"

### Page

- [X] T030 [US1] Branch `frontend/app/src/pages/resource-manager/number-pool-details.tsx::NumberPoolBody` (research R8, data-model.md "States of the scoped body").
  - **Unscoped** (`pool.allocation_scope.value.length === 0`): today's body, unchanged.
  - **Scoped, no parameter** (`useNumberPoolDivision(...).status === "none"`): `NumberPoolDivisionsCard`, full width.
  - **Scoped, mismatch**: `NumberPoolDivisionMismatch`.
  - **Scoped, selected**: a left column with `NumberPoolDivisionSummary` above `NumberPoolRangesCard`, and `NumberPoolAllocationsCard` with `division={selector}`. `useGetNumberPoolUtilization(pool.id, selector)` is called only in this branch.

  If the page grows past about 250 lines, move the scoped branch into `frontend/app/src/entities/resource-manager/ui/number-pool/details/number-pool-scoped-body.tsx`.
- [X] T031 [US1] Extend `frontend/app/src/pages/resource-manager/number-pool-details.test.tsx` with one test per state:
  - unscoped page unchanged
  - scoped pool shows the allocation scopes card and does not call utilization without a division
  - mismatch message for an invalid value
  - selected allocation scope shows the summary, and utilization is called with the selector
  - range route with `allocation_scope` keeps the range selected

### End-to-end

- [ ] T032 [US1] Add a self-contained test to `tests/e2e/resource-manager/test_number_pool.py::TestNumberPool` (research R9).
  - **Setup on `number_pool_branch`, with `infrahub_client`:**
    1. Create a `CoreNumberPool` on `InfraInterfaceL3.speed`, with `allocation_scope` set to the `device` relationship's `{id, name}` from the branch schema.
    2. Create three L3 interfaces on one `data_sites` device and one on another, with `speed` taken from the pool.
  - **Checks in the browser:**
    1. Open the pool: two rows, the fullest first, and the header says "scoped by Device".
    2. Search to one row.
    3. Open the first row: only its three numbers are listed.
    4. Reload the page URL: the same numbers are listed.
  - If the SDK does not accept `allocation_scope` or `from_pool` for a Number attribute, use a GraphQL mutation through the SDK client instead.
  - Run it with `--pdb` while debugging, as `AGENTS.md` describes.

**Checkpoint**: User Story 1 works end to end and can be demonstrated on its own.

---

## Phase 4: User Story 2 - Switch allocation scope from the allocation scope page (Priority: P2)

Not part of IFC-3366 (spec, Out of Scope). No tasks. The summary block from T023 is the place where the picker will go.

---

## Phase 5: Polish & Cross-Cutting Concerns

- [ ] T033 [P] Add a section on viewing a scoped number pool to `docs/docs/resource-manager/overview.mdx`, under "Number pools" (research R10), using the `opsmill-docs:writing-infrahub-docs` skill. It covers:
  - what an allocation scope is
  - the table, with search and sort
  - opening one allocation scope
  - that the API calls one row a "division"

  Run `uv run invoke docs.lint`.
- [X] T034 [P] Add `changelog/+ifc-3366-number-pool-allocation-scopes.added.md` with the `creating-changelog-entries` skill, describing what landed, checked against the diff
- [X] T035 Delete `frontend/app/src/pages/proto/number-pool/` and the route block between `// PROTO number-pool — remove with the prototype` and `// END PROTO number-pool` in `frontend/app/src/app/router.tsx` (research R11)
- [ ] T036 Run the manual scenarios Q1–Q11, the width check and the volume check in [quickstart.md](quickstart.md) against a local Infrahub, and fix what fails
- [ ] T037 Run the gates and fix what fails:
  - `cd frontend && pnpm exec biome ci .`
  - `cd frontend/app && pnpm knip`
  - `cd frontend/app && pnpm exec betterer ci`
  - `cd frontend/app && pnpm test`
  - the e2e file
  - `/pre-ci`

---

## Dependencies & Execution Order

### Phase dependencies

- **Setup (T001)**: none.
- **Foundational (T002–T013)**: T002 first. T003 and T004 can run in parallel after it. Then T005, then T007, then T009 run in order. T010, T011, T012 and T013 can run in parallel after T002.
- **User Story 1 (T014–T032)**: needs Setup and Foundational.
- **Polish (T033–T037)**: T033 and T034 can start once US1's behavior is fixed. T035 comes after T030. T036 and T037 come last.

### Inside User Story 1

- T014, T016 and T017 come first. Each needs only T001 and the foundational phase.
- **T019 (table)** needs T017.
- **T020 (card)** needs T009, T016 and T019.
- **T023 (summary)** and **T025 (mismatch)** need T009 and T017.
- **T026 (allocations props)** needs T011.
- **T028 (header)** has no dependency inside the story.
- **T030 (page)** needs T014, T020, T023, T025, T026 and T010.
- **T031** needs T030. **T032** needs T030.

### Parallel opportunities

```text
After T002:   T003 · T004 · T010 · T011 · T013
After T009:   T014 · T016 · T017 · T026 · T028
After T017:   T019 · T023 · T025 · T018
Tests:        T006 · T008 · T012 · T015 · T021 · T022 · T024 · T027 · T029 (each next to its source task)
Polish:       T033 · T034
```

---

## Implementation Strategy

### MVP (User Story 1 only)

1. Phase 1 and Phase 2: data and types are ready; nothing is visible yet.
2. URL state and helpers (T014–T018).
3. Table and card (T019–T022). At this point the page could show the table.
4. Allocation scope page pieces (T023–T029).
5. Page branching (T030–T031). **Stop and validate** with quickstart Q1–Q11.
6. End-to-end test (T032), then the polish phase.

### Later work, not in this ticket

- User Story 2: the allocation scope picker.
- Virtualization of the allocation scopes table, for very large pools.
