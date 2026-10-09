# Implementation Plan: Number pool body for pools without an allocation scope

**Branch**: `number-pool-body-ifc-3362` | **Date**: 2026-10-08 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/ifc-3362-number-pool-body/spec.md`

**Jira**: [IFC-3362](https://opsmill.atlassian.net/browse/IFC-3362) | **Backend queries**: [IFC-3347](https://opsmill.atlassian.net/browse/IFC-3347), [PR #10932](https://github.com/opsmill/infrahub/pull/10932) | **Header**: [PR #10963](https://github.com/opsmill/infrahub/pull/10963)

## Summary

On a number pool's page, replace the old body (the properties card, the Resources card and the `resources/<id>` view) with two parts:

- a ranges card that lists "All ranges" and each range in fill order, with its weight and a usage bar
- a table of the allocated numbers in the selected range, which loads more rows as the user scrolls

The selected range lives in the address (`/resource-manager/<pool>/ranges/<id>`). The data comes from the two number pool queries of PR #10932:

- `InfrahubNumberPoolUtilization` returns the counts per range.
- `InfrahubNumberPoolAllocations` filters by `range_id` and returns the holder node and how each number got there.

The ranges card is the `@infrahub/ui` `ListBox` with link items. The table is react-aria's `Table` in a `Virtualizer`, built inside the resource-manager entity. The header, IP pools and the backend do not change.

## Technical Context

**Language/Version**: TypeScript 5.9, React 19.2 (React Compiler on: no manual memoisation)

**Primary Dependencies**:

- `react-aria-components` 1.20.0: `Table`, `TableLoadMoreItem`, `Virtualizer`, `TableLayout`, and `ListBox` through `@infrahub/ui`
- TanStack Query (`useQuery`, `useInfiniteQuery`)
- gql.tada with urql (`graphql`, `graphqlClient` from `@/shared/api/graphql/client`)
- React Router (nested route, `useParams`)
- Tailwind CSS 4.2

No new dependency.

**Storage**: N/A. The body reads data and writes nothing.

**Testing**:

- Vitest 4.1 in browser mode: unit tests for the rule, the use-cases and the mappers; component tests for the page and the entity components. Query hooks are mocked with `vi.mock`, and fakes live in `frontend/app/tests/fake/`.
- pytest-playwright end-to-end tests: one existing test is removed here (research R12); the new end-to-end test is tracked separately.

**Target Platform**: The Infrahub web app in current desktop browsers.

**Project Type**: Web application. This work is frontend only, in `frontend/app`, with one end-to-end test file in `tests/e2e`.

**Performance Goals**:

- Scrolling a 50,000-row table stays smooth: only the visible rows are rendered (SC-004).
- Each further page holds 100 rows.

**Constraints**:

- The header stays unchanged, and IP pools stay unchanged.
- The default branch is never identified by its name.
- Until IFC-3347 reads the database, the queries return fake data, and every real pool gets the scoped fake pool.

**Scale/Scope**:

- A pool has a few ranges and up to tens of thousands of numbers.
- About 10 new source files, about 4 changed files, and their tests.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | How the plan meets it |
|---|---|---|
| I. Schema-driven integrity | Pass | No schema change. The generated GraphQL types come from `pnpm codegen` after #10932 is merged in, never edited by hand. |
| II. Branch-safe by default | Pass | The body reads data only. It shows every branch on purpose (FR-004), because pools and ranges are branch-agnostic. The default branch is found with `is_default`, never by name (research R7). Holder links name the row's branch. |
| III. Type safety and explicit contracts | Pass | `BigInt` (typed `unknown`) is converted with `Number(...)` in mappers, with no `as` casts. The provenance is a union of declared constants. The GraphQL contract exists ([contracts/graphql-queries.md](./contracts/graphql-queries.md)), and generated types are used. |
| IV. Test discipline | Pass, with a split agreed with the user | This PR has unit tests (rule, use-cases, mappers) and component tests (page, ranges card, table, usage bar). The end-to-end test against real data needs IFC-3347. It is tracked in its own ticket and must pass before `feature-number-pools-1.12` merges into `stable`. One obsolete end-to-end test is removed (research R12). |
| V. Query performance | Pass | Both queries select only the fields shown. Numbers are paged (100 rows a page). A range that is not in the pool is caught before any request. |
| VI. Security and input boundaries | Pass | No mutation and no new input. `rangeId` from the address only selects data, and the backend validates it. |
| VII. Simplicity | Pass, with one recorded deviation | The table stays in the entity until a second caller exists. The existing `ListBox`, `MultipleProgressBar`, `formatNumberDisplay`, `ErrorScreen` and `getObjectDetailsUrl` are reused. Deviation: the client re-sorts ranges (see Complexity Tracking). |
| Documentation requirements | Deferred, needs confirmation | `docs/docs/resource-manager/` does not describe the number pool page today. Screenshots of real figures cannot be taken until IFC-3347 reads the database. Proposed: document the page in the `feature-number-pools-1.12` docs pass, before the merge into `stable`, under the same gate as the end-to-end test. No `dev/knowledge/frontend/` change, because no shared pattern is added. |

**Post-design re-check**: unchanged after Phase 1. The design adds no shared abstraction, no dependency and no backend change.

## Project Structure

### Documentation (this feature)

```text
specs/ifc-3362-number-pool-body/
├── spec.md
├── plan.md              # This file
├── research.md          # Phase 0
├── data-model.md        # Phase 1
├── quickstart.md        # Phase 1
├── contracts/
│   ├── graphql-queries.md
│   └── ui.md
├── checklists/
│   └── requirements.md
└── tasks.md             # Phase 2 (/speckit-tasks, not created here)
```

### Source Code (repository root)

```text
frontend/app/src/
├── app/
│   └── router.tsx                                          # changed: add { path: "ranges/:rangeId" } under :resourcePoolId
├── entities/
│   ├── nodes/object/ui/routing/
│   │   ├── object-urls.ts                                  # changed: resource-manager branch appends tabSegment
│   │   └── object-urls.test.ts                             # changed: cover /resource-manager/<id>/ranges/<id>
│   └── resource-manager/
│       ├── api/
│       │   ├── get-number-pool-utilization-from-api.ts     # new
│       │   ├── get-number-pool-allocations-from-api.ts     # new
│       │   ├── number-pool-utilization.mappers.ts          # new (+ .test.ts)
│       │   └── number-pool-allocation.mappers.ts           # new (+ .test.ts)
│       ├── domain/
│       │   ├── model/
│       │   │   ├── number-pool.ts                          # changed: + NumberPoolUsage, NumberPoolRange, NumberPoolUtilization, NumberPoolAllocation, NumberPoolProvenance
│       │   │   └── pool.ts                                 # changed: + NUMBER_POOL_RANGE_KIND
│       │   ├── rules/
│       │   │   └── sort-ranges-by-fill-order.ts            # new (+ .test.ts)
│       │   └── use-cases/
│       │       ├── get-number-pool-utilization.ts          # new (+ .test.ts)
│       │       └── get-number-pool-allocations.ts          # new (+ .test.ts)
│       └── ui/
│           ├── number-pool/
│           │   ├── number-pool-ranges-card.tsx             # new (+ .test.tsx)
│           │   ├── number-pool-usage-bar.tsx               # new (+ .test.tsx)
│           │   └── number-pool-allocations-table.tsx       # new (+ .test.tsx)
│           └── queries/
│               ├── resource-manager.query-keys.ts          # changed: numberPoolUtilization, numberPoolAllocations
│               ├── get-number-pool-utilization.query.ts    # new
│               └── get-number-pool-allocations.query.ts    # new (infinite, page size 100)
└── pages/resource-manager/
    ├── number-pool-details.tsx                             # changed: header + ranges card + table area
    └── number-pool-details.test.tsx                        # changed: states of the table area, selected range

frontend/app/tests/fake/
└── number-pool.ts                                          # changed: generators for utilization, ranges, allocations

tests/e2e/resource-manager/
└── test_number_pool.py                                     # changed: remove test_displays_correct_details_for_created_number_pool

changelog/
└── +ifc-3362-number-pool-body.changed.md                   # new
```

**Structure decision**:

- New code follows the entity layers (`api/`, `domain/{model,rules,use-cases}/`, `ui/`) of `dev/knowledge/frontend/entities-structure.md`, next to the header's files.
- The page in `pages/resource-manager/` composes the entity components.
- Nothing is deleted: `ResourcePoolDetailsBody`, `ResourceSelector`, `resource-allocation-details.tsx` and the old pool queries are still used by IP pools and by the resource-manager breadcrumb.

## Implementation Order

Each step leaves the app building and the tests passing.

1. **Base**:
   1. Merge #10932's current branch into `number-pool-body-ifc-3362` and run `pnpm codegen`. The conflict in `graphql-cache.d.ts` is resolved by regenerating.
   2. Confirm that `InfrahubNumberPoolUtilization` and `InfrahubNumberPoolAllocations` appear in the generated types.
2. **Domain and data**: the model types, `sortRangesByFillOrder`, the two `-from-api` fetchers, the mappers and the two use-cases, each with unit tests. Then the query keys and the two query hooks.
3. **Address**: `getObjectDetailsUrl` appends `tabSegment` for resource-manager pages, with a test. The router gets `ranges/:rangeId`.
4. **Entity UI**: `NumberPoolUsageBar`, then `NumberPoolRangesCard`, then `NumberPoolAllocationsTable`, each with component tests and fakes.
5. **Page**: `NumberPoolDetailsPage` composes the header, the ranges card and the table area, with the states from [data-model.md](./data-model.md). `ResourcePoolDetailsBody` is no longer rendered for number pools.
6. **End-to-end and changelog**: remove the obsolete end-to-end test, add the changelog fragment, and run the checks in [quickstart.md](./quickstart.md).

## Risks

| Risk | Effect | Mitigation |
|---|---|---|
| #10932's stack changes again (its base already moved once) | Merge conflicts, or a contract field renamed | Merge #10932 only at step 1. The body selects few fields. The contract is pinned in [contracts/graphql-queries.md](./contracts/graphql-queries.md). |
| No real pool can render the body until IFC-3347 | Visual review on real data is impossible in this PR | Component tests with contract-shaped fakes. Manual query checks with `mock-unscoped` ([quickstart.md](./quickstart.md) §2). |
| `TableLayout` needs fixed row heights | A long holder label could overflow its cell | The cells truncate their text, and the full label is in the link's tooltip or title. |
| First react-aria `Table` in the app | No local example to copy | It stays in one entity file, and the component tests cover keyboard navigation and loading more rows. |

## Complexity Tracking

| Violation | Why needed | Simpler alternative rejected because |
|---|---|---|
| The client re-sorts ranges into fill order (`entities-structure.md` / `page-architecture.md` § "Backend is authoritative": do not mirror server sort order) | The user chose to list ranges in the order the pool fills them, so the top range is the one used next. The backend returns them by start. | Showing them by start hides which range fills next. Asking the backend to return them in fill order was offered, and the user chose the frontend. The rule is one tested file that copies `backend/infrahub/pools/number_ranges.py`'s order. |
| `ranges/:rangeId` has no element, and the parent reads it with `useParams` (`route-architecture.md` prefers child shims with outlet context) | An index child route under `:resourcePoolId` would also render in IP pools' `Outlet` (FR-002). The ranges card and the table share the selected range. | Child shims for "All ranges" need that index route. |
